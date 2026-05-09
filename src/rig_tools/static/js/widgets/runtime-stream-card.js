/** Runtime Stream Card Widget
 *
 * PHASE 3: Truthful Stream Visualization
 *
 * Renders live token/chunk rendering for runtime streams with SVG instrumentation.
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
 * - SVG-based truthful animation (derived from real runtime state)
 *
 * This widget displays:
 * - Live token/chunk rendering
 * - SVG throughput visualization
 * - SVG stream density visualization
 * - SVG state indicators
 * - Status updates
 * - Proposal visibility
 * - Runtime diagnostics
 * - Capability usage
 * - Replay linkage
 * - Integrity flags
 *
 * Animation derives ONLY from:
 * - Real stream events
 * - Real websocket state
 * - Real runtime throughput
 * - Real sequence progression
 *
 * NO:
 * - Fake activity loops
 * - Arbitrary loading indicators
 * - Synthetic motion disconnected from runtime state
 * - Decorative shimmer/gradients
 */

import {
  SvgThroughputBar,
  SvgStreamDensityLine,
  SvgReplaySweep,
  SvgIntegrityMarker,
  SvgInstrumentationLayer,
  ProjectionGeometryMapper,
  SvgReconciliationLoopIndicator,
  SvgReconciliationCadenceIndicator,
  SvgDampingIndicator,
  SvgConvergenceIndicator,
  point,
  rect,
  clamp,
  mapRange,
  MotionUtils,
  normalizeRuntimeEventEnvelope,
  normalizeOperationalStatusEnvelope
} from '../svg-runtime-instrumentation.js';

/** Runtime Stream Card Widget
 * Enhanced with SVG-based truthful stream visualization
 */
export function renderRuntimeStreamCard(id, data, context) {
  const el = document.createElement('div');
  el.className = 'widget runtime-stream-card';
  el.setAttribute('role', 'region');
  el.setAttribute('aria-label', 'Runtime Stream');
  el.setAttribute('aria-live', 'polite');
  
  // Configure bounds for SVG
  const cardWidth = data.width || 600;
  const cardHeight = data.height || 400;
  const svgHeight = data.svg_height || 120;
  
  // Initialize state tracking
  const state = {
    totalTokens: data.stats?.total_tokens || 0,
    totalChunks: data.stats?.total_chunks || 0,
    sequence: data.sequence || 0,
    maxSequence: data.max_sequence || 100,
    channel: data.channel || 'assistant'
  };
  const runtimeEnvelope = normalizeRuntimeEventEnvelope(data.runtime_event || data.event_envelope);

  // Title and stream info
  const header = document.createElement('div');
  header.className = 'widget-header';
  header.style.display = 'flex';
  header.style.justifyContent = 'space-between';
  header.style.alignItems = 'center';

  const titleEl = document.createElement('h2');
  titleEl.textContent = data.title || 'Runtime Stream';
  header.appendChild(titleEl);

  if (data.schema_version || data.projection_revision !== undefined) {
    const lineage = document.createElement('div');
    lineage.className = 'muted';
    lineage.style.fontSize = '12px';
    lineage.style.marginLeft = '12px';
    lineage.textContent = [
      data.schema_version ? `schema: ${data.schema_version}` : null,
      data.projection_revision !== undefined ? `revision: ${data.projection_revision}` : null,
    ].filter(Boolean).join(' · ');
    header.appendChild(lineage);
  }

  if (runtimeEnvelope) {
    const eventBadge = document.createElement('div');
    eventBadge.className = 'badge severity-info';
    eventBadge.textContent = `${runtimeEnvelope.event_family} · ${runtimeEnvelope.event_type}`;
    header.appendChild(eventBadge);
  }

  // Stream status badge
  const operationalStatus = normalizeOperationalStatusEnvelope(
    data.condition || data.status || data.overall_status || data.runtime_status
  );

  if (operationalStatus && operationalStatus.value !== 'unknown') {
    const statusBadge = document.createElement('div');
    const severity = operationalStatus.severity || 'info';
    statusBadge.className = 'badge severity-' + severity;
    const statusText = operationalStatus.label || operationalStatus.value || 'streaming';
    statusBadge.textContent = statusText.charAt(0).toUpperCase() + statusText.slice(1);
    header.appendChild(statusBadge);
  }

  el.appendChild(header);

  // Token/chunk statistics
  if (data.stats) {
    const statsRow = document.createElement('div');
    statsRow.className = 'runtime-stream-stats';
    statsRow.style.display = 'flex';
    statsRow.style.gap = '16px';
    statsRow.style.marginTop = '8px';
    statsRow.style.fontSize = '12px';
    
    const stats = [
      { label: 'Chunks', value: data.stats.total_chunks, key: 'total_chunks' },
      { label: 'Tokens', value: data.stats.total_tokens, key: 'total_tokens' },
      { label: 'Prompt', value: data.stats.prompt_tokens, key: 'prompt_tokens' },
      { label: 'Assistant', value: data.stats.assistant_tokens, key: 'assistant_tokens' },
    ];
    
    for (const stat of stats) {
      if (stat.value !== undefined && stat.value !== null) {
        const statEl = document.createElement('span');
        statEl.className = 'stat-item';
        const label = document.createElement('span');
        label.style.color = 'var(--text-secondary, #888)';
        label.textContent = stat.label + ': ';
        const value = document.createElement('span');
        value.style.color = 'var(--text-primary, #e0e0e0)';
        value.style.fontWeight = 'bold';
        value.textContent = formatNumber(stat.value);
        statEl.appendChild(label);
        statEl.appendChild(value);
        statsRow.appendChild(statEl);
      }
    }
    
    el.appendChild(statsRow);
  }

  // =========================================================================
  // SVG Stream Visualization (PHASE 3)
  // =========================================================================
  
  // Create SVG container for stream visualization
  const svgContainer = document.createElement('div');
  svgContainer.className = 'runtime-stream-svg-container';
  svgContainer.style.width = '100%';
  svgContainer.style.height = svgHeight + 'px';
  svgContainer.style.marginTop = '8px';
  svgContainer.style.backgroundColor = 'var(--bgtertiary, #121212)';
  svgContainer.style.borderRadius = '4px';
  svgContainer.style.overflow = 'hidden';
  
  el.appendChild(svgContainer);

  // Create instrumentation layer
  const svgBounds = rect(0, 0, cardWidth, svgHeight);
  const instrumentationLayer = new SvgInstrumentationLayer(svgContainer, {
    id: 'stream-card-layer',
    bounds: svgBounds,
    maxElements: 100
  });
  
  // Render SVG stream visualization
  _renderSvgStreamVisualization(data, instrumentationLayer, svgBounds);

  // =========================================================================
  // Stream content (text-based)
  // =========================================================================
  
  const contentArea = document.createElement('div');
  contentArea.className = 'runtime-stream-content';
  contentArea.style.marginTop = '12px';
  contentArea.style.overflowY = 'auto';
  contentArea.style.maxHeight = (cardHeight - svgHeight - 200) + 'px';
  contentArea.style.fontFamily = 'monospace';
  contentArea.style.fontSize = '12px';
  contentArea.style.whiteSpace = 'pre-wrap';
  contentArea.style.wordBreak = 'break-word';
  contentArea.style.backgroundColor = 'var(--bg-secondary, #1e1e1e)';
  contentArea.style.color = 'var(--text-primary, #e0e0e0)';
  contentArea.style.padding = '8px 12px';
  contentArea.style.borderRadius = '4px';
  contentArea.style.border = '1px solid var(--border, #404040)';

  // Render chunks
  const chunks = data.chunks || [];
  
  if (chunks.length === 0) {
    const emptyEl = document.createElement('div');
    emptyEl.className = 'muted';
    emptyEl.textContent = data.empty_message || 'Stream has no content yet.';
    contentArea.appendChild(emptyEl);
  } else {
    // Sort chunks by sequence if they have it
    const sortedChunks = [...chunks].sort((a, b) => {
      const seqA = a.sequence || 0;
      const seqB = b.sequence || 0;
      return seqA - seqB;
    });
    
    const maxVisible = data.max_lines || 50;
    const displayChunks = sortedChunks.slice(-maxVisible);
    
    for (const chunk of displayChunks) {
      const lineEl = document.createElement('div');
      lineEl.className = 'runtime-stream-line';
      
      // Build line content
      let content = '';
      
      // Add sequence number
      if (chunk.sequence !== undefined) {
        content += String(chunk.sequence).padStart(4, ' ') + ' ';
      }
      
      // Add channel prefix
      const channel = chunk.channel || 'assistant';
      const channelLabel = getChannelLabel(channel);
      content += '[' + channelLabel + '] ';
      
      // Add content
      content += chunk.content || '';
      
      // Truncate
      const maxLen = data.max_line_length || 500;
      if (content.length > maxLen) {
        content = content.substring(0, maxLen) + '...';
      }
      
      // Set text content
      lineEl.textContent = content;
      
      // Style based on severity
      const severity = chunk.severity || 
                       (channel === 'error' ? 'error' :
                        channel === 'warning' ? 'warning' : 'info');
      lineEl.style.color = getColorForSeverity(severity);
      
      contentArea.appendChild(lineEl);
    }
  }
  
  el.appendChild(contentArea);

  // Metadata and indicators
  const metadataArea = document.createElement('div');
  metadataArea.className = 'runtime-stream-metadata';
  metadataArea.style.marginTop = '12px';
  metadataArea.style.display = 'flex';
  metadataArea.style.flexWrap = 'wrap';
  metadataArea.style.gap = '8px';
  metadataArea.style.fontSize = '11px';
  metadataArea.style.color = 'var(--text-secondary, #888)';

  // Provider info
  if (data.provider_id) {
    const providerEl = document.createElement('span');
    providerEl.className = 'runtime-meta-item';
    providerEl.textContent = 'Provider: ' + truncateId(data.provider_id);
    metadataArea.appendChild(providerEl);
  }

  // Model info
  if (data.model_id) {
    const modelEl = document.createElement('span');
    modelEl.className = 'runtime-meta-item';
    modelEl.textContent = 'Model: ' + truncateId(data.model_id);
    metadataArea.appendChild(modelEl);
  }

  // Stream ID
  if (data.stream_id) {
    const streamEl = document.createElement('span');
    streamEl.className = 'runtime-meta-item';
    streamEl.textContent = 'Stream: ' + truncateId(data.stream_id);
    metadataArea.appendChild(streamEl);
  }

  // Invocation ID
  if (data.invocation_id) {
    const invocationEl = document.createElement('span');
    invocationEl.className = 'runtime-meta-item';
    invocationEl.textContent = 'Invocation: ' + truncateId(data.invocation_id);
    metadataArea.appendChild(invocationEl);
  }

  // Truncation indicator
  if (data.truncated || data.stats && data.stats.truncated) {
    const truncatedEl = document.createElement('span');
    truncatedEl.className = 'runtime-meta-item warning';
    truncatedEl.textContent = 'Output truncated';
    truncatedEl.style.color = 'var(--color-warning, #ffa500)';
    metadataArea.appendChild(truncatedEl);
  }

  el.appendChild(metadataArea);

  // Integrity flags
  const integrityArea = renderIntegrityFlags(data.integrity_flags || []);
  if (integrityArea) {
    integrityArea.style.marginTop = '8px';
    el.appendChild(integrityArea);
  }

  // Advisory notice
  const advisoryEl = document.createElement('div');
  advisoryEl.className = 'advisory-notice';
  advisoryEl.style.marginTop = '8px';
  advisoryEl.style.fontSize = '11px';
  advisoryEl.style.color = 'var(--text-secondary, #888)';
  advisoryEl.style.fontStyle = 'italic';
  advisoryEl.textContent = 'Stream content is advisory evidence only.';
  el.appendChild(advisoryEl);

  // Replay reference
  if (data.replay_ref) {
    const replayEl = document.createElement('div');
    replayEl.className = 'replay-ref';
    replayEl.style.marginTop = '4px';
    replayEl.style.fontSize = '11px';
    replayEl.textContent = 'Replay: ' + truncateId(data.replay_ref);
    el.appendChild(replayEl);
  }

  // Reconciliation visibility (PHASE 8)
  // Add reconciliation state display if data available
  if (data.reconciliation) {
    renderReconciliationState(data, el);
  }

  // Expose update method for dynamic updates
  el.update = (newData) => {
    // Update SVG visualization
    instrumentationLayer.clear();
    _renderSvgStreamVisualization(newData, instrumentationLayer, svgBounds);
    
    // Update text content if needed
    // (In a full implementation, this would re-render the content area)
  };

  return el;
}

// =============================================================================
// SVG Stream Visualization Rendering
// =============================================================================

/** Render SVG-based stream visualization
 * Truthful visualization derived from real runtime data
 */
function _renderSvgStreamVisualization(data, layer, bounds) {
  const geometryMapper = new ProjectionGeometryMapper(bounds);
  
  // Determine stream state
  const statusEnvelope = normalizeOperationalStatusEnvelope(
    data.condition || data.status || data.overall_status || data.runtime_status
  );
  const state = statusEnvelope.state || statusEnvelope.value || 'streaming';
  const channel = data.channel || 'assistant';
  const sequence = data.sequence || data.stats?.last_sequence || 0;
  const maxSequence = data.max_sequence || 
                      data.stats?.expected_sequences || 
                      Math.max(sequence * 1.5, 100);
  
  // Statistics
  const totalChunks = data.stats?.total_chunks || 0;
  const totalTokens = data.stats?.total_tokens || 0;
  const maxTotalTokens = data.stats?.max_tokens || 1000;
  const currentThroughput = data.stats?.tokens_per_second || 
                           data.stats?.current_throughput || 0;
  const maxThroughput = data.stats?.max_throughput || 100;
  
  // Replay state
  const isReplaying = state === 'replaying' || data.replay_ref;
  const replayProgress = data.replay_progress || (isReplaying ? 0.5 : 0);
  const isReconstructed = data.reconstructed || false;
  const densityState = MotionUtils.calculateDensityCollapse(totalChunks, currentThroughput > 0 ? 1 : 0, data.integrity_flags?.length || 0);

  // =========================================================================
  // 1. Stream Density Line (shows chunk flow)
  // =========================================================================
  
  const chunks = data.chunks || [];
  if (chunks.length >= 2) {
    const densityPoints = [];
    const geomBounds = geometryMapper.bounds;
   const segments = Math.min(50, chunks.length);
    
    for (let i = 0; i <= segments; i++) {
      const seq = (i / segments) * maxSequence;
      const x = geometryMapper.sequenceToX(seq, maxSequence);
      const y = bounds.height / 2;
      densityPoints.push(point(x, y));
    }
    
    // Calculate intensity based on throughput
    const intensity = densityState.shouldCollapse ? 0.45 : clamp(totalTokens / maxTotalTokens, 0.1, 1.0);
    
    const densityLine = new SvgStreamDensityLine('stream-density', densityPoints, {
      intensity,
      channel,
      state,
      sequenceStart: Math.max(0, sequence - 20),
      sequenceEnd: sequence,
      bytesTotal: data.stats?.total_bytes || 0,
      tokensTotal: totalTokens
    });
    
    layer.addPrimitive(densityLine);
  }

  // =========================================================================
  // 2. Throughput Bar (shows current throughput)
  // =========================================================================
  
  if (totalTokens > 0) {
    const barBounds = rect(
      bounds.width - 150,
      bounds.height - 25,
      130,
      16
    );
    
    const throughputBar = new SvgThroughputBar('stream-throughput', barBounds, {
      value: currentThroughput,
      maxValue: maxThroughput,
      label: 'Tok/s',
      state,
      channel
    });
    
    layer.addPrimitive(throughputBar);
  }

  // =========================================================================
  // 3. Sequence Progress Indicator (shows progression through expected)
  // =========================================================================
  
  const progressBounds = rect(
    bounds.width - 100,
    bounds.height - 45,
    80,
    80
  );

  const progress = maxSequence > 0 ? clamp(sequence / maxSequence, 0, 1) : 0;
  const replayMode = isReplaying || densityState.shouldCollapse;
  
  const sweep = new SvgReplaySweep('sequence-progress', progressBounds, {
    progress,
    state: replayMode ? 'replaying' : state,
    sequence,
    totalSequences: maxSequence,
    isReconstructed
  });
  
  layer.addPrimitive(sweep);

  // =========================================================================
  // 4. Integrity Markers (show violations/warnings at sequence positions)
  // =========================================================================
  
  if (data.integrity_flags) {
    const viols = data.integrity_flags;
    for (let i = 0; i < Math.min(viols.length, 10); i++) {
      const flag = viols[i];
      const violSequence = flag.sequence || sequence - i * 5;
      const x = geometryMapper.sequenceToX(violSequence, maxSequence);
      const y = bounds.height / 2;
      
      const marker = new SvgIntegrityMarker(`viol-${i}`, point(x, y), {
        state: 'warning',
        code: flag.code || 'INTEGRITY',
        severity: flag.severity || 'warning',
        message: flag.message || flag,
        sequence: violSequence
      });
      
      layer.addPrimitive(marker);
    }
  }
}

// =============================================================================
// Utility Functions
// =============================================================================

function getChannelLabel(channel) {
  const labels = {
    assistant: 'ASSIST',
    user: 'USER',
    system: 'SYSTEM',
    tool: 'TOOL',
    proposal: 'PROP',
    diagnostic: 'DIAG',
    status: 'STAT',
    heartbeat: 'HERT',
    warning: 'WARN',
    error: 'ERR',
    completion: 'COMP',
    meta: 'META'
  };
  return labels[channel] || channel.toUpperCase().substring(0, 4);
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
  
  // Format with commas for thousands
  return num.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ',');
}

function truncateId(id, length = 12) {
  if (!id) return '';
  const str = String(id);
  if (str.length <= length) return str;
  return str.substring(0, length - 3) + '...';
}

function getColorForSeverity(severity) {
  const colors = {
    debug: 'var(--color-debug, #888)',
    info: 'var(--color-info, #e0e0e0)',
    warning: 'var(--color-warning, #ffa500)',
    error: 'var(--color-error, #ff5555)',
    critical: 'var(--color-critical, #ff4444)',
  };
  return colors[severity] || colors.info;
}

function renderIntegrityFlags(flags) {
  if (!flags || flags.length === 0) return null;
  
  const container = document.createElement('div');
  container.className = 'integrity-flags';
  container.style.display = 'flex';
  container.style.flexWrap = 'wrap';
  container.style.gap = '4px';

  for (const flag of flags) {
    const flagEl = document.createElement('span');
    flagEl.className = 'integrity-flag badge severity-warning';
    flagEl.style.fontSize = '10px';
    flagEl.textContent = flag;
    container.appendChild(flagEl);
  }

  return container;
}

// =============================================================================
// Reconciliation Visibility Section (PHASE 8)
// =============================================================================

/** Render reconciliation loop state for runtime stream
 * Shows loop health, cadence, damping, and convergence state
 */
function renderReconciliationState(data, el) {
  // Create reconciliation info section
  const reconcileSection = document.createElement('div');
  reconcileSection.className = 'stream-reconciliation-section';
  reconcileSection.style.marginTop = '8px';
  reconcileSection.style.paddingTop = '8px';
  reconcileSection.style.borderTop = '1px solid var(--border-color, #333)';

  const reconcileTitle = document.createElement('h3');
  reconcileTitle.className = 'reconciliation-title';
  reconcileTitle.style.marginBottom = '4px';
  reconcileTitle.style.fontSize = '11px';
  reconcileTitle.textContent = 'Reconciliation';
  reconcileSection.appendChild(reconcileTitle);

  // Get reconciliation data from projection or defaults
  const reconciliation = data.reconciliation || {};
  const loopState = reconciliation.loop || {};
  const cadmiumData = reconciliation.cadence || {};
  const dampingData = reconciliation.damping || {};
  const convergenceData = reconciliation.convergence || {};

  // Create SVG container for reconciliation indicators
  const svgHeight = 40;
  const svgContainer = document.createElement('div');
  svgContainer.className = 'reconciliation-svg';
  svgContainer.style.width = '100%';
  svgContainer.style.height = svgHeight + 'px';
  svgContainer.style.display = 'flex';
  svgContainer.style.gap = '8px';
  svgContainer.style.alignItems = 'center';

  // Loop indicator
  if (loopState.status) {
    const loopBounds = rect(0, 0, 40, svgHeight);
    const loopIndicator = new SvgReconciliationLoopIndicator(
      'stream-loop',
      loopBounds,
      {
        loopId: loopState.loopId || 'stream-loop',
        controllerType: loopState.controllerType || 'runtime_supervision',
        status: loopState.status || 'running',
        iterations: loopState.iterations || 0,
        convergence: loopState.convergence || 0,
        dampingActive: dampingData.currentFactor < 1.0 || false,
        oscillationDetected: dampingData.oscillationDetected || false
      }
    );
    loopIndicator.render(svgContainer);
  }

  // Cadence indicator
  if (cadmiumData.minInterval) {
    const cadenceBounds = rect(0, 0, 80, svgHeight);
    const cadenceIndicator = new SvgReconciliationCadenceIndicator(
      'stream-cadence',
      cadenceBounds,
      {
        loopId: loopState.loopId || 'stream-loop',
        minInterval: cadmiumData.minInterval || 0.1,
        maxInterval: cadmiumData.maxInterval || 10.0,
        currentInterval: cadmiumData.currentInterval || 1.0,
        jitterFactor: cadmiumData.jitterFactor || 0.1,
        nextTickIn: cadmiumData.nextTickIn || 0
      }
    );
    cadenceIndicator.render(svgContainer);
  }

  // Convergence indicator
  if (convergenceData.converged !== undefined) {
    const convBounds = rect(0, 0, 60, svgHeight);
    const convIndicator = new SvgConvergenceIndicator(
      'stream-convergence',
      convBounds,
      {
        loopId: loopState.loopId || 'stream-loop',
        currentIteration: convergenceData.currentIteration || 0,
        totalIterations: convergenceData.totalIterations || 100,
        currentDuration: convergenceData.currentDuration || 0,
        maxDuration: convergenceData.maxDuration || 60,
        converged: convergenceData.converged || false,
        stabilisationThreshold: convergenceData.stabilisationThreshold || 0.001
      }
    );
    convIndicator.render(svgContainer);
  }

  reconcileSection.appendChild(svgContainer);

  // Text info
  const reconciliationInfo = document.createElement('div');
  reconciliationInfo.className = 'reconciliation-info';
  reconciliationInfo.style.marginTop = '4px';
  reconciliationInfo.style.fontSize = '10px';
  reconciliationInfo.style.color = 'var(--text-muted, #888)';

  const infoParts = [];
  if (loopState.status) {
    infoParts.push(`Loop: ${loopState.status}`);
  }
  if (loopState.iterations !== undefined) {
    infoParts.push(`Iterations: ${loopState.iterations}`);
  }
  if (convergenceData.converged !== undefined) {
    infoParts.push(`Converged: ${convergenceData.converged ? 'Yes' : 'No'}`);
  }

  reconciliationInfo.textContent = infoParts.join(' | ');
  reconcileSection.appendChild(reconciliationInfo);

  el.appendChild(reconcileSection);
}

// =============================================================================
// Widget Registration
// ==========================================================================================================================================================
// Widget Registration
// =============================================================================

/** Register widget with a registry */
export function registerRuntimeStreamCard(registry) {
  if (registry) {
    registry.RuntimeStreamCard = renderRuntimeStreamCard;
  }
}

// Auto-register if registry is available
if (typeof window !== 'undefined' && window.RigWidgetRegistry) {
  registerRuntimeStreamCard(window.RigWidgetRegistry);
}
