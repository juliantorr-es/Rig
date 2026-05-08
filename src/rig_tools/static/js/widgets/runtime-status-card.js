/** Runtime Status Card Widget
 *
 * PHASE 10: UI Convergence Pass
 * Enhanced with SVG instrumentation for truthful status visualization
 * 
 * Core doctrine:
 * - Projection-only rendering (never fetches data)
 * - No authority inference
 * - No timers as authority source
 * - Deterministic rendering
 * - Safe truncation
 * - textContent-only rendering for meaningful content
 * - Replay-safe rendering
 * - Advisory indicators only
 * - SVG-based truthful visualization
 *
 * This widget displays:
 * - Runtime status with SVG state indicator
 * - SVG progress visualization
 * - SVG capability routing visualization
 * - Token usage with SVG throughput bars
 * - Capability usage visibility
 * - Runtime diagnostics
 * - Replay linkage
 * - Integrity flags
 *
 * SVG visualizations:
 * - Status state indicator (SvgStatefulLoader)
 * - Progress sweep for completion status
 * - Throughput bars for token usage
 * - Capability routing paths
 */

import {
  SvgStatefulLoader,
  SvgThroughputBar,
  SvgReplaySweep,
  SvgIntegrityMarker,
  SvgInstrumentationLayer,
  ProjectionGeometryMapper,
  rect,
  point
} from '../svg-runtime-instrumentation.js';

export function renderRuntimeStatusCard(id, data, context) {
  const el = document.createElement('div');
  el.className = 'widget runtime-status-card';
  el.setAttribute('role', 'region');
  el.setAttribute('aria-label', 'Runtime Status');
  
  // Configure dimensions
  const cardWidth = data.width || 600;
  const svgHeight = data.svg_height || 80;

  // Title and header
  const header = document.createElement('div');
  header.className = 'widget-header';
  header.style.display = 'flex';
  header.style.justifyContent = 'space-between';
  header.style.alignItems = 'center';

  const titleEl = document.createElement('h2');
  titleEl.textContent = data.title || 'Runtime Status';
  header.appendChild(titleEl);

  // Overall status badge
  const overallStatus = data.status || data.overall_status || 'unknown';
  const statusBadge = document.createElement('div');
  const severity = data.severity || 
                   (typeof overallStatus === 'object' ? overallStatus.severity : null) ||
                   getSeverityFromStatus(overallStatus);
  statusBadge.className = 'badge severity-' + severity;
  const statusText = typeof overallStatus === 'string' ? overallStatus :
                    (overallStatus.label || overallStatus.value || 'unknown');
  statusBadge.textContent = capitalizeFirst(statusText);
  header.appendChild(statusBadge);

  el.appendChild(header);

  // =========================================================================
  // SVG Status Visualization (PHASE 10)
  // =========================================================================
  
  // Create SVG container for status visualization
  const svgContainer = document.createElement('div');
  svgContainer.className = 'runtime-status-svg-container';
  svgContainer.style.width = '100%';
  svgContainer.style.height = svgHeight + 'px';
  svgContainer.style.marginTop = '8px';
  svgContainer.style.backgroundColor = 'var(--bg-tertiary, #121212)';
  svgContainer.style.borderRadius = '4px';
  svgContainer.style.overflow = 'hidden';
  
  el.appendChild(svgContainer);

  // Create instrumentation layer
  const svgBounds = rect(0, 0, cardWidth, svgHeight);
  const instrumentationLayer = new SvgInstrumentationLayer(svgContainer, {
    id: 'status-card-layer',
    bounds: svgBounds,
    maxElements: 50
  });
  
  // Render SVG status visualization
  _renderSvgStatusVisualization(data, instrumentationLayer, svgBounds);

  // =========================================================================
  // Status summary section
  // =========================================================================
  
  const summarySection = document.createElement('div');
  summarySection.className = 'runtime-status-summary';
  summarySection.style.marginTop = '12px';

  // Status message
  if (data.message) {
    const messageEl = document.createElement('div');
    messageEl.className = 'runtime-status-message';
    messageEl.style.fontSize = '14px';
    messageEl.style.marginBottom = '8px';
    messageEl.style.color = 'var(--text-primary, #e0e0e0)';
    messageEl.textContent = data.message;
    summarySection.appendChild(messageEl);
  }

  // Progress indicators
  const progressArea = document.createElement('div');
  progressArea.className = 'runtime-status-progress';
  progressArea.style.display = 'flex';
  progressArea.style.gap = '16px';
  progressArea.style.flexWrap = 'wrap';
  progressArea.style.marginTop = '8px';

  // Add progress items
  const progressItems = [
    { label: 'Provider', value: data.provider_id, key: 'provider' },
    { label: 'Model', value: data.model_id, key: 'model' },
    { label: 'State', value: data.state, key: 'state' },
    { label: 'Phase', value: data.phase, key: 'phase' },
  ];

  for (const item of progressItems) {
    if (item.value) {
      const itemEl = document.createElement('span');
      itemEl.className = 'progress-item';
      itemEl.style.fontSize = '12px';
      
      const labelEl = document.createElement('span');
      labelEl.style.color = 'var(--text-secondary, #888)';
      labelEl.textContent = item.label + ': ';
      
      const valueEl = document.createElement('span');
      valueEl.style.color = 'var(--text-primary, #e0e0e0)';
      valueEl.textContent = truncateText(item.value, 20);
      
      itemEl.appendChild(labelEl);
      itemEl.appendChild(valueEl);
      progressArea.appendChild(itemEl);
    }
  }

  summarySection.appendChild(progressArea);
  el.appendChild(summarySection);

  // Capability usage section
  if (data.capabilities && data.capabilities.length > 0) {
    const capabilitiesSection = document.createElement('div');
    capabilitiesSection.className = 'runtime-status-capabilities';
    capabilitiesSection.style.marginTop = '12px';
    
    const capTitle = document.createElement('div');
    capTitle.className = 'section-title';
    capTitle.style.fontSize = '12px';
    capTitle.style.color = 'var(--text-secondary, #888)';
    capTitle.style.marginBottom = '4px';
    capTitle.textContent = 'Capabilities Used:';
    capabilitiesSection.appendChild(capTitle);
    
    const capList = document.createElement('div');
    capList.className = 'capability-list';
    capList.style.display = 'flex';
    capList.style.flexWrap = 'wrap';
    capList.style.gap = '4px';
    
    for (const cap of data.capabilities) {
      const capEl = document.createElement('span');
      capEl.className = 'capability-item badge severity-info';
      capEl.style.fontSize = '11px';
      const capName = typeof cap === 'string' ? cap : (cap.name || cap.kind || cap.capability_id || 'unknown');
      capEl.textContent = capName;
      capList.appendChild(capEl);
    }
    
    capabilitiesSection.appendChild(capList);
    el.appendChild(capabilitiesSection);
  }

  // Diagnostics section
  if (data.diagnostics && Object.keys(data.diagnostics).length > 0) {
    const diagnosticsSection = document.createElement('div');
    diagnosticsSection.className = 'runtime-status-diagnostics';
    diagnosticsSection.style.marginTop = '12px';
    
    const diagTitle = document.createElement('div');
    diagTitle.className = 'section-title';
    diagTitle.style.fontSize = '12px';
    diagTitle.style.color = 'var(--text-secondary, #888)';
    diagTitle.style.marginBottom = '4px';
    diagTitle.textContent = 'Diagnostics:';
    diagnosticsSection.appendChild(diagTitle);
    
    const diagGrid = document.createElement('div');
    diagGrid.style.display = 'grid';
    diagGrid.style.gridTemplateColumns = 'auto 1fr';
    diagGrid.style.gap = '4px 8px';
    diagGrid.style.fontSize = '12px';
    
    for (const [key, value] of Object.entries(data.diagnostics)) {
      const keyEl = document.createElement('div');
      keyEl.style.color = 'var(--text-secondary, #888)';
      keyEl.textContent = key + ':';
      
      const valueEl = document.createElement('div');
      valueEl.style.color = 'var(--text-primary, #e0e0e0)';
      valueEl.textContent = formatDiagnosticValue(value);
      
      diagGrid.appendChild(keyEl);
      diagGrid.appendChild(valueEl);
    }
    
    diagnosticsSection.appendChild(diagGrid);
    el.appendChild(diagnosticsSection);
  }

  // Tokens info with SVG bars
  if (data.tokens) {
    const tokensSection = document.createElement('div');
    tokensSection.className = 'runtime-status-tokens';
    tokensSection.style.marginTop = '12px';
    
    const tokensTitle = document.createElement('div');
    tokensTitle.className = 'section-title';
    tokensTitle.style.fontSize = '12px';
    tokensTitle.style.color = 'var(--text-secondary, #888)';
    tokensTitle.style.marginBottom = '4px';
    tokensTitle.textContent = 'Token Usage:';
    tokensSection.appendChild(tokensTitle);
    
    // Create SVG token bars
    const tokenSvgContainer = document.createElement('div');
    tokenSvgContainer.style.width = '100%';
    tokenSvgContainer.style.height = '40px';
    tokenSvgContainer.style.marginBottom = '8px';
    
    const tokenBounds = rect(0, 0, cardWidth, 40);
    const tokenLayer = new SvgInstrumentationLayer(tokenSvgContainer, {
      id: 'token-layer',
      bounds: tokenBounds,
      maxElements: 10
    });
    
    _renderTokenBars(data.tokens, tokenLayer, tokenBounds);
    tokensSection.appendChild(tokenSvgContainer);
    
    // Token statistics (text)
    const tokenStats = document.createElement('div');
    tokenStats.style.display = 'flex';
    tokenStats.style.gap = '16px';
    tokenStats.style.flexWrap = 'wrap';
    tokenStats.style.fontSize = '12px';
    
    const tokenFields = [
      { label: 'Prompt', key: 'prompt_tokens' },
      { label: 'Completion', key: 'completion_tokens' },
      { label: 'Total', key: 'total_tokens' },
    ];
    
    for (const field of tokenFields) {
      if (data.tokens[field.key] !== undefined) {
        const statEl = document.createElement('span');
        const label = document.createElement('span');
        label.style.color = 'var(--text-secondary, #888)';
        label.textContent = field.label + ': ';
        const value = document.createElement('span');
        value.style.color = 'var(--text-primary, #e0e0e0)';
        value.style.fontWeight = 'bold';
        value.textContent = formatNumber(data.tokens[field.key]);
        statEl.appendChild(label);
        statEl.appendChild(value);
        tokenStats.appendChild(statEl);
      }
    }
    
    tokensSection.appendChild(tokenStats);
    el.appendChild(tokensSection);
  }

  // Metadata footer
  const metadataArea = document.createElement('div');
  metadataArea.className = 'runtime-status-metadata';
  metadataArea.style.marginTop = '12px';
  metadataArea.style.display = 'flex';
  metadataArea.style.flexWrap = 'wrap';
  metadataArea.style.gap = '8px';
  metadataArea.style.fontSize = '11px';
  metadataArea.style.color = 'var(--text-secondary, #888)';

  const metadataItems = [
    { label: 'Stream', value: data.stream_id },
    { label: 'Invocation', value: data.invocation_id },
    { label: 'Provider', value: data.provider_id },
    { label: 'Started', value: data.started_at },
    { label: 'Completed', value: data.completed_at },
  ];

  for (const item of metadataItems) {
    if (item.value) {
      const metaEl = document.createElement('span');
      metaEl.className = 'meta-item';
      const label = item.label + ': ';
      const value = truncateText(String(item.value), 16);
      metaEl.textContent = label + value;
      metadataArea.appendChild(metaEl);
    }
  }

  el.appendChild(metadataArea);

  // Integrity flags
  if (data.integrity_flags && data.integrity_flags.length > 0) {
    const flagsEl = document.createElement('div');
    flagsEl.className = 'integrity-flags';
    flagsEl.style.marginTop = '8px';
    flagsEl.style.display = 'flex';
    flagsEl.style.flexWrap = 'wrap';
    flagsEl.style.gap = '4px';
    
    for (const flag of data.integrity_flags) {
      const flagEl = document.createElement('span');
      flagEl.className = 'badge severity-warning';
      flagEl.style.fontSize = '10px';
      flagEl.textContent = flag;
      flagsEl.appendChild(flagEl);
    }
    
    el.appendChild(flagsEl);
  }

  // Advisory notice
  const advisoryEl = document.createElement('div');
  advisoryEl.className = 'advisory-notice';
  advisoryEl.style.marginTop = '8px';
  advisoryEl.style.fontSize = '11px';
  advisoryEl.style.color = 'var(--text-secondary, #888)';
  advisoryEl.style.fontStyle = 'italic';
  advisoryEl.textContent = 'Status is advisory evidence only. Only receipts become authoritative.';
  el.appendChild(advisoryEl);

  // Replay reference
  if (data.replay_ref) {
    const replayEl = document.createElement('div');
    replayEl.className = 'replay-ref';
    replayEl.style.marginTop = '4px';
    replayEl.style.fontSize = '11px';
    replayEl.textContent = 'Replay: ' + truncateText(data.replay_ref, 20);
    el.appendChild(replayEl);
  }

  // Expose update method
  el.update = (newData) => {
    instrumentationLayer.clear();
    _renderSvgStatusVisualization(newData, instrumentationLayer, svgBounds);
    
    if (newData.tokens && tokenLayer) {
      tokenLayer.clear();
      _renderTokenBars(newData.tokens, tokenLayer, tokenBounds);
    }
  };

  return el;
}

// =============================================================================
// SVG Status Visualization Rendering
// =============================================================================

/** Render SVG-based status visualization */
function _renderSvgStatusVisualization(data, layer, bounds) {
  const geometryMapper = new ProjectionGeometryMapper(bounds);
  
  // State for SVG elements
  const state = data.status?.value || data.status || data.state || 'unknown';
  const progress = data.progress || 0;
  const isComplete = state === 'complete' || state === 'completed' || state === 'succeeded';
  const isFailed = state === 'failed' || state === 'error' || state === 'timed_out';
  const isStalled = state === 'stalled' || state === 'paused' || state === 'degraded';
  const isActive = state === 'active' || state === 'running' || state === 'streaming';
  
  // Calculate completion percentage if we have progress data
  const completionPercent = data.completion_percentage || 
                           (isComplete ? 1.0 : progress);

  // 1. Main status indicator (SvgStatefulLoader)
  const statusBounds = rect(
    bounds.width - 100,
    bounds.height - 60,
    80,
    60
  );
  
  const statefulLoader = new SvgStatefulLoader('status-main', statusBounds, {
    state,
    progress: isComplete ? 1.0 : completionPercent,
    label: 'Status',
    channel: 'system',
    isIndeterminate: !isComplete && !isFailed && progress === 0
  });
  
  layer.addPrimitive(statefulLoader);

  // 2. Completion progress sweep (if applicable)
  if (completionPercent > 0 && completionPercent < 1) {
    const sweepBounds = rect(
      bounds.width - 80,
      bounds.height - 80,
      70,
      70
    );
    
    const sweep = new SvgReplaySweep('status-progress', sweepBounds, {
      progress: completionPercent,
      state: isFailed ? 'failure' : isStalled ? 'stalled' : state,
      sequence: data.sequence || 0,
      totalSequences: data.total_sequences || 100,
      isReconstructed: data.reconstructed || false
    });
    
    layer.addPrimitive(sweep);
  }

  // 3. Phase indicator bar
  if (data.phase) {
    const phases = ['idle', 'planning', 'executing', 'streaming', 'proposing', 'validating', 'completing', 'complete'];
    const currentPhaseIndex = phases.indexOf(data.phase.toLowerCase());
    const phaseProgress = currentPhaseIndex >= 0 ? (currentPhaseIndex + 1) / phases.length : 0;
    
    const phaseBounds = rect(
      bounds.width - 200,
      bounds.height - 30,
      150,
      12
    );
    
    const phaseBar = new SvgThroughputBar('phase-progress', phaseBounds, {
      value: currentPhaseIndex + 1,
      maxValue: phases.length,
      label: 'Phase',
      state: state,
      channel: 'system'
    });
    
    layer.addPrimitive(phaseBar);
  }
}

/** Render token usage bars */
function _renderTokenBars(tokens, layer, bounds) {
  const padding = 16;
  const barWidth = (bounds.width - padding * 2) / 3 - 8;
  
  const tokenFields = [
    { key: 'prompt_tokens', label: 'Prompt', colorChannel: 'user' },
    { key: 'completion_tokens', label: 'Completion', colorChannel: 'assistant' },
    { key: 'total_tokens', label: 'Total', colorChannel: 'system' },
  ];
  
  const maxValue = tokens.total_tokens || 
                  Math.max(tokens.prompt_tokens || 0, tokens.completion_tokens || 0, 1);
  
  for (let i = 0; i < tokenFields.length; i++) {
    const field = tokenFields[i];
    const value = tokens[field.key] || 0;
    
    const barBounds = rect(
      padding + i * (barWidth + 8),
      bounds.height / 2 - 10,
      barWidth,
      20
    );
    
    const bar = new SvgThroughputBar(`token-${field.key}`, barBounds, {
      value: value,
      maxValue: maxValue,
      label: field.label,
      state: 'idle',
      channel: field.colorChannel
    });
    
    layer.addPrimitive(bar);
  }
}

// =============================================================================
// Utility Functions
// =============================================================================

function getSeverityFromStatus(status) {
  const severityMap = {
    active: 'info',
    running: 'info',
    streaming: 'info',
    idle: 'info',
    pending: 'info',
    connecting: 'info',
    connected: 'info',
    completed: 'info',
    succeeded: 'info',
    
    stalled: 'warning',
    paused: 'warning',
    degraded: 'warning',
    
    failed: 'error',
    error: 'error',
    timed_out: 'error',
    cancelled: 'error',
    blocked: 'error'
  };
  const normalized = (status || 'unknown').toLowerCase();
  return severityMap[normalized] || 'info';
}

function capitalizeFirst(str) {
  if (!str) return '';
  return String(str).charAt(0).toUpperCase() + String(str).slice(1);
}

function truncateText(text, maxLen) {
  if (!text) return '';
  const str = String(text);
  if (str.length <= maxLen) return str;
  return str.substring(0, maxLen - 2) + '..';
}

function formatNumber(num) {
  if (num === undefined || num === null) return '0';
  if (typeof num !== 'number') {
    try {
      num = Number(num);
    } catch {
      return String(num);
    }
  }
  return num.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ',');
}

function formatDiagnosticValue(value) {
  if (value === undefined || value === null) return 'N/A';
  if (typeof value === 'object') {
    return JSON.stringify(value).substring(0, 30);
  }
  return String(value).substring(0, 30);
}

// Register widget
export function registerRuntimeStatusCard(registry) {
  if (registry) {
    registry.RuntimeStatusCard = renderRuntimeStatusCard;
  }
}

// Auto-register if registry is available
if (typeof window !== 'undefined' && window.RigWidgetRegistry) {
  registerRuntimeStatusCard(window.RigWidgetRegistry);
}
