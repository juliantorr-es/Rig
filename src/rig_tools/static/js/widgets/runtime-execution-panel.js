/** Runtime Execution Panel Widget
 *
 * PHASE 3-4: Truthful Runtime Execution Instrumentation Panel
 *
 * Core doctrine:
 * - Projection-only rendering (never fetches data)
 * - No authority inference
 * - No timers as authority source
 * - Deterministic rendering
 * - Safe truncation
 * - textContent-only rendering
 * - Replay-safe rendering
 * - Advisory indicators
 * - Truthful animations derive from real backend/runtime state
 *
 * This widget displays:
 * - Execution lane visualization
 * - Capability routing visibility
 * - Proposal flow visualization
 * - Runtime state transitions
 * - Supervision state visibility
 * - Bounded execution history
 *
 * Visual design:
 * - Geometric
 * - Dense but readable
 * - Operational
 * - Instrumentation-oriented
 * - Terminal-era systems aesthetic
 *
 * NO:
 * - fake thinking indicators
 * - meaningless shimmer
 * - arbitrary loading loops
 * - synthetic motion disconnected from runtime state
 * - decorative particle systems
 * - uncontrolled CSS chaos
 * - canvas-heavy visual effects
 * - hidden frontend state
 * - authority inference in UI
 * - direct backend mutation from widgets
 */

import { RuntimeInstrumentation, RuntimeInstrumentationState, MotionUtils, formatBytes, formatTokens, getColorForSeverity } from '../runtime-instrumentation.js';

// =============================================================================
// Constants
// =============================================================================

/** Maximum execution history entries */
const MAX_EXECUTION_HISTORY = 50;

/** Maximum lane count */
const MAX_LANES = 4;

/** Animation durations derived from real state */
const ANIMATION_DURATIONS = {
  streaming: '150ms',
  proposing: '250ms',
  validating: '300ms',
  replaying: '100ms',
  stalled: '0ms',
  completion: '500ms',
  failure: '200ms'
};

// =============================================================================
// Helper Functions
// =============================================================================

/** Generate deterministic element ID */
function genId(prefix, ...parts) {
  return [prefix, ...parts.filter(p => p !== undefined && p !== null)].join('-');
}

/** Safe text content setting */
function safeText(el, content) {
  if (content === null || content === undefined) return '';
  el.textContent = String(content);
  return content;
}

/** Truncate text with ellipsis */
function truncateText(text, maxLen = 40) {
  if (!text) return '';
  const str = String(text);
  if (str.length <= maxLen) return str;
  return str.substring(0, maxLen - 3) + '...';
}

/** Format timestamp for display */
function formatTimestamp(ts) {
  if (!ts) return '';
  try {
    const date = new Date(ts);
    return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  } catch {
    return String(ts).substring(0, 12);
  }
}

/** Get trust level color */
function getTrustLevelColor(trustLevel) {
  if (!trustLevel) return 'var(--text-secondary, #888)';
  const level = String(trustLevel).toLowerCase();
  if (level.includes('high') || level.includes('trusted')) return 'var(--color-success, #4CAF50)';
  if (level.includes('medium') || level.includes('standard')) return 'var(--color-warning, #ffa500)';
  if (level.includes('low') || level.includes('restricted')) return 'var(--color-error, #ff5555)';
  return 'var(--text-primary, #e0e0e0)';
}

/** Get capability icon */
function getCapabilityIcon(capability) {
  if (!capability) return 'FUNC';
  const cap = String(capability).toLowerCase();
  if (cap.includes('file') || cap.includes('fs')) return 'FILE';
  if (cap.includes('git')) return 'GIT';
  if (cap.includes('network') || cap.includes('http')) return 'NET';
  if (cap.includes('shell') || cap.includes('command') || cap.includes('exec')) return 'SHELL';
  if (cap.includes('read')) return 'READ';
  if (cap.includes('write')) return 'WRITE';
  if (cap.includes('patch') || cap.includes('diff')) return 'PATCH';
  if (cap.includes('tool')) return 'TOOL';
  return cap.substring(0, 4).toUpperCase();
}

/** Get runtime provider display name */
function getProviderName(providerId) {
  if (!providerId) return 'Unknown';
  // Map known provider IDs to display names
  const names = {
    'openai': 'OpenAI',
    'anthropic': 'Anthropic',
    'google': 'Google',
    'mistral': 'Mistral',
    'localhost': 'Local',
    'vibe': 'Vibe'
  };
  return names[providerId.toLowerCase()] || providerId.substring(0, 16);
}

/** Get state display label */
function getStateLabel(state) {
  const labels = {
    planning: 'Planning',
    streaming: 'Streaming',
    proposing: 'Proposing',
    validating: 'Validating',
    replaying: 'Replaying',
    stalled: 'Stalled',
    'integrity-warning': 'Integrity Warning',
    'capability-routing': 'Routing',
    completion: 'Complete',
    failure: 'Failed',
    idle: 'Idle'
  };
  return labels[state?.toLowerCase() || ''] || state || 'Unknown';
}

// =============================================================================
// Execution Lane
// =============================================================================

/** Represents a single execution lane */
class ExecutionLane {
  constructor({
    id,
    label,
    runtime,
    provider,
    capabilities = [],
    trustLevel,
    state = RuntimeInstrumentationState.IDLE,
    severity = 'info',
    usage = { tokens: 0, bytes: 0, chunks: 0 },
    history = [],
    isActive = false,
    lastActivity = null
  }) {
    this.id = id || 'lane-' + Math.random().toString(16).substring(2, 8);
    this.label = label || '';
    this.runtime = runtime || '';
    this.provider = provider || '';
    this.capabilities = Array.isArray(capabilities) ? capabilities : [capabilities];
    this.trustLevel = trustLevel || '';
    this.state = state;
    this.severity = severity;
    this.usage = usage || { tokens: 0, bytes: 0, chunks: 0 };
    this.history = Array.isArray(history) ? history : [history].filter(Boolean);
    this.isActive = isActive || false;
    this.lastActivity = lastActivity || null;
  }

  /** Add a history entry */
  addHistory(entry) {
    const newHistory = [...this.history];
    newHistory.push(entry);
    while (newHistory.length > MAX_EXECUTION_HISTORY) {
      newHistory.shift();
    }
    return new ExecutionLane({
      ...this,
      history: newHistory,
      lastActivity: entry.timestamp || Date.now()
    });
  }

  /** Update lane state */
  update({ state, severity, usage, isActive }) {
    return new ExecutionLane({
      ...this,
      state: state || this.state,
      severity: severity || this.severity,
      usage: usage || this.usage,
      isActive: isActive !== undefined ? isActive : this.isActive
    });
  }

  /** Get display color */
  getColor() {
    return getColorForSeverity(this.severity);
  }

  /** Get capability display */
  getCapabilityDisplay() {
    return this.capabilities.map(getCapabilityIcon).join(' | ');
  }

  toJSON() {
    return {
      id: this.id,
      label: this.label,
      runtime: this.runtime,
      provider: this.provider,
      capabilities: this.capabilities,
      trustLevel: this.trustLevel,
      state: this.state,
      severity: this.severity,
      usage: this.usage,
      history: this.history,
      isActive: this.isActive,
      lastActivity: this.lastActivity
    };
  }

  static fromJSON(data) {
    return new ExecutionLane(data);
  }
}

// =============================================================================
// Execution Lane Renderer
// =============================================================================

/** Render a single execution lane */
function renderExecutionLane(lane, options = {}) {
  const el = document.createElement('div');
  el.id = options.idPrefix ? genId(options.idPrefix, 'lane', lane.id) : lane.id;
  el.className = 'execution-lane';
  el.style.display = 'flex';
  el.style.flexDirection = 'column';
  el.style.gap = '4px';
  el.style.padding = '8px';
  el.style.borderRadius = '4px';
  el.style.backgroundColor = 'var(--bg-secondary, #1e1e1e)';
  el.style.border = '1px solid ' + (lane.isActive ? 'var(--border-active, #444)' : 'var(--border, #404040)');

  // Lane header
  const header = document.createElement('div');
  header.className = 'lane-header';
  header.style.display = 'flex';
  header.style.justifyContent = 'space-between';
  header.style.alignItems = 'center';
  header.style.gap = '8px';

  // Lane label and runtime info
  const info = document.createElement('div');
  info.className = 'lane-info';
  info.style.display = 'flex';
  info.style.alignItems = 'center';
  info.style.gap = '6px';

  // Label
  const label = document.createElement('span');
  label.className = 'lane-label';
  label.style.fontSize = '11px';
  label.style.fontWeight = 'bold';
  label.style.color = 'var(--text-primary, #e0e0e0)';
  label.textContent = lane.label || ('Lane ' + (options.index !== undefined ? options.index + 1 : ''));
  info.appendChild(label);

  // Runtime display
  if (lane.runtime || lane.provider) {
    const runtimeEl = document.createElement('span');
    runtimeEl.className = 'lane-runtime';
    runtimeEl.style.fontSize = '10px';
    runtimeEl.style.color = 'var(--text-secondary, #888)';
    runtimeEl.style.padding = '2px 4px';
    runtimeEl.style.backgroundColor = 'var(--bg-tertiary, #252526)';
    runtimeEl.style.borderRadius = '2px';
    runtimeEl.textContent = truncateText(getProviderName(lane.provider || lane.runtime), 12);
    info.appendChild(runtimeEl);
  }

  header.appendChild(info);

  // State badge
  const stateBadge = document.createElement('span');
  stateBadge.className = 'lane-state-badge badge severity-' + lane.severity;
  stateBadge.style.fontSize = '10px';
  stateBadge.style.fontWeight = 'bold';
  safeText(stateBadge, getStateLabel(lane.state).substring(0, 10));
  header.appendChild(stateBadge);

  el.appendChild(header);

  // Trust level indicator
  if (lane.trustLevel) {
    const trustEl = document.createElement('div');
    trustEl.className = 'lane-trust';
    trustEl.style.display = 'flex';
    trustEl.style.alignItems = 'center';
    trustEl.style.gap = '4px';
    trustEl.style.fontSize = '10px';

    const trustLabel = document.createElement('span');
    trustLabel.style.color = 'var(--text-secondary, #888)';
    trustLabel.textContent = 'Trust:';
    trustEl.appendChild(trustLabel);

    const trustValue = document.createElement('span');
    trustValue.style.color = getTrustLevelColor(lane.trustLevel);
    trustValue.style.fontWeight = 'bold';
    trustValue.textContent = truncateText(lane.trustLevel, 12);
    trustEl.appendChild(trustValue);

    el.appendChild(trustEl);
  }

  // Capability display
  if (lane.capabilities && lane.capabilities.length > 0) {
    const capEl = document.createElement('div');
    capEl.className = 'lane-capabilities';
    capEl.style.display = 'flex';
    capEl.style.flexWrap = 'wrap';
    capEl.style.gap = '2px';
    capEl.style.fontSize = '9px';
    capEl.style.marginTop = '4px';

    const capLabel = document.createElement('span');
    capLabel.style.color = 'var(--text-secondary, #888)';
    capLabel.textContent = 'Caps: ';
    capEl.appendChild(capLabel);

    for (const cap of lane.capabilities) {
      const capSpan = document.createElement('span');
      capSpan.className = 'cap-badge';
      capSpan.style.padding = '1px 3px';
      capSpan.style.backgroundColor = 'var(--bg-tertiary, #252526)';
      capSpan.style.borderRadius = '2px';
      capSpan.style.color = 'var(--text-primary, #e0e0e0)';
      capSpan.textContent = getCapabilityIcon(cap);
      capEl.appendChild(capSpan);
    }

    el.appendChild(capEl);
  }

  // Usage statistics
  const usageEl = document.createElement('div');
  usageEl.className = 'lane-usage';
  usageEl.style.display = 'flex';
  usageEl.style.gap = '12px';
  usageEl.style.fontSize = '10px';
  usageEl.style.marginTop = '4px';
  usageEl.style.padding = '4px';
  usageEl.style.backgroundColor = 'var(--bg-tertiary, #252526)';
  usageEl.style.borderRadius = '2px';

  const usageItems = [
    { label: 'Tokens', value: formatTokens(lane.usage.tokens), key: 'tokens' },
    { label: 'Bytes', value: formatBytes(lane.usage.bytes), key: 'bytes' },
    { label: 'Chunks', value: lane.usage.chunks || 0, key: 'chunks' }
  ];

  for (const item of usageItems) {
    const itemEl = document.createElement('span');
    itemEl.className = 'usage-item';
    itemEl.style.color = 'var(--text-secondary, #888)';
    
    const label = document.createElement('span');
    label.textContent = item.label + ': ';
    itemEl.appendChild(label);

    const value = document.createElement('span');
    value.style.color = 'var(--text-primary, #e0e0e0)';
    value.style.fontWeight = 'bold';
    value.textContent = item.value;
    itemEl.appendChild(value);

    usageEl.appendChild(itemEl);
  }

  el.appendChild(usageEl);

  return el;
}

// =============================================================================
// Capability Routing Visualization
// =============================================================================

/** Render capability routing visualization */
function renderCapabilityRouting(routingState, options = {}) {
  const el = document.createElement('div');
  el.id = options.id || genId('routing');
  el.className = 'capability-routing';
  el.style.display = 'flex';
  el.style.flexDirection = 'column';
  el.style.gap = '8px';
  el.style.padding = '8px';
  el.style.backgroundColor = 'var(--bg-secondary, #1e1e1e)';
  el.style.borderRadius = '4px';

  // Header
  const header = document.createElement('div');
  header.className = 'routing-header';
  header.style.display = 'flex';
  header.style.justifyContent = 'space-between';
  header.style.alignItems = 'center';
  header.style.marginBottom = '4px';

  const label = document.createElement('span');
  label.className = 'routing-label';
  label.style.fontSize = '12px';
  label.style.fontWeight = 'bold';
  label.style.color = 'var(--text-primary, #e0e0e0)';
  label.textContent = 'Capability Routing';
  header.appendChild(label);

  // Status indicator
  const statusEl = document.createElement('span');
  statusEl.className = 'routing-status';
  statusEl.style.fontSize = '10px';
  statusEl.style.padding = '2px 6px';
  statusEl.style.borderRadius = '2px';
  statusEl.style.backgroundColor = getColorForSeverity(routingState.severity || 'info');
  statusEl.style.color = 'var(--bg-primary, #1a1a1a)';
  statusEl.style.fontWeight = 'bold';
  statusEl.textContent = routingState.runtime ? truncateText(routingState.runtime, 12) : 'None';
  header.appendChild(statusEl);

  el.appendChild(header);

  // Runtime info
  if (routingState.runtime || routingState.trustLevel) {
    const runtimeInfo = document.createElement('div');
    runtimeInfo.className = 'routing-info';
    runtimeInfo.style.display = 'flex';
    runtimeInfo.style.gap = '8px';
    runtimeInfo.style.fontSize = '11px';

    if (routingState.runtime) {
      const runtimeItem = document.createElement('span');
      runtimeItem.style.color = 'var(--text-secondary, #888)';
      
      const runtimeLabel = document.createElement('span');
      runtimeLabel.textContent = 'Runtime: ';
      runtimeItem.appendChild(runtimeLabel);
      
      const runtimeValue = document.createElement('span');
      runtimeValue.style.color = 'var(--text-primary, #e0e0e0)';
      runtimeValue.style.fontWeight = 'bold';
      runtimeValue.textContent = getProviderName(routingState.runtime);
      runtimeItem.appendChild(runtimeValue);
      
      runtimeInfo.appendChild(runtimeItem);
    }

    if (routingState.trustLevel) {
      const trustItem = document.createElement('span');
      trustItem.style.color = 'var(--text-secondary, #888)';
      
      const trustLabel = document.createElement('span');
      trustLabel.textContent = 'Trust: ';
      trustItem.appendChild(trustLabel);
      
      const trustValue = document.createElement('span');
      trustValue.style.color = getTrustLevelColor(routingState.trustLevel);
      trustValue.style.fontWeight = 'bold';
      trustValue.textContent = routingState.trustLevel;
      trustItem.appendChild(trustValue);
      
      runtimeInfo.appendChild(trustItem);
    }

    el.appendChild(runtimeInfo);
  }

  // Capabilities list
  if (routingState.capabilities && routingState.capabilities.length > 0) {
    const capsEl = document.createElement('div');
    capsEl.className = 'routing-capabilities';
    capsEl.style.display = 'flex';
    capsEl.style.flexWrap = 'wrap';
    capsEl.style.gap = '4px';
    capsEl.style.marginTop = '4px';

    for (const cap of routingState.capabilities) {
      const capEl = document.createElement('span');
      capEl.className = 'capability-badge';
      capEl.style.fontSize = '10px';
      capEl.style.padding = '2px 6px';
      capEl.style.backgroundColor = 'var(--bg-tertiary, #252526)';
      capEl.style.borderRadius = '2px';
      capEl.style.color = 'var(--text-primary, #e0e0e0)';
      capEl.textContent = getCapabilityIcon(cap);
      capsEl.appendChild(capEl);
    }

    el.appendChild(capsEl);
  }

  // No routing info
  if (!routingState.runtime && (!routingState.capabilities || routingState.capabilities.length === 0)) {
    const emptyEl = document.createElement('div');
    emptyEl.className = 'routing-empty';
    emptyEl.style.fontSize = '11px';
    emptyEl.style.color = 'var(--text-secondary, #888)';
    emptyEl.style.fontStyle = 'italic';
    emptyEl.textContent = 'No capability routing active';
    el.appendChild(emptyEl);
  }

  return el;
}

// =============================================================================
// Execution History
// =============================================================================

/** Render execution history as a timeline */
function renderExecutionHistory(instrumentation, options = {}) {
  const el = document.createElement('div');
  el.id = options.id || genId('history');
  el.className = 'execution-history';
  el.style.display = 'flex';
  el.style.flexDirection = 'column';
  el.style.gap = '4px';
  el.style.padding = '8px';
  el.style.backgroundColor = 'var(--bg-secondary, #1e1e1e)';
  el.style.borderRadius = '4px';
  el.style.maxHeight = '200px';
  el.style.overflowY = 'auto';

  // Header
  const header = document.createElement('div');
  header.className = 'history-header';
  header.style.display = 'flex';
  header.style.justifyContent = 'space-between';
  header.style.alignItems = 'center';
  header.style.marginBottom = '4px';

  const label = document.createElement('span');
  label.className = 'history-label';
  label.style.fontSize = '12px';
  label.style.fontWeight = 'bold';
  label.style.color = 'var(--text-primary, #e0e0e0)';
  label.textContent = 'Execution History';
  header.appendChild(label);

  const countEl = document.createElement('span');
  countEl.className = 'history-count';
  countEl.style.fontSize = '10px';
  countEl.style.color = 'var(--text-secondary, #888)';
  countEl.textContent = `${instrumentation.visualStateBuffer ? instrumentation.visualStateBuffer.count : 0} events`;
  header.appendChild(countEl);

  el.appendChild(header);

  // History entries
  if (instrumentation.visualStateBuffer && !instrumentation.visualStateBuffer.isEmpty) {
    const entriesEl = document.createElement('div');
    entriesEl.className = 'history-entries';
    entriesEl.style.display = 'flex';
    entriesEl.style.flexDirection = 'column';
    entriesEl.style.gap = '2px';

    const entries = instrumentation.visualStateBuffer.getAllOrdered();
    const displayEntries = entries.slice(-MAX_EXECUTION_HISTORY).reverse();

    for (const entry of displayEntries) {
      const entryEl = document.createElement('div');
      entryEl.className = 'history-entry';
      entryEl.style.display = 'flex';
      entryEl.style.alignItems = 'center';
      entryEl.style.gap = '6px';
      entryEl.style.padding = '4px 6px';
      entryEl.style.fontSize = '10px';
      entryEl.style.backgroundColor = entry.severity === 'error' || entry.severity === 'critical' 
        ? 'rgba(255, 0, 0, 0.1)' 
        : 'var(--bg-tertiary, #252526)';
      entryEl.style.borderRadius = '2px';
      entryEl.style.borderLeft = `3px solid ${getColorForSeverity(entry.severity)}`;

      // Sequence and timestamp
      const metaEl = document.createElement('span');
      metaEl.className = 'entry-meta';
      metaEl.style.color = 'var(--text-secondary, #888)';
      metaEl.style.fontSize = '9px';
      metaEl.textContent = `#${entry.sequence} ${formatTimestamp(entry.timestamp)}`;
      entryEl.appendChild(metaEl);

      // State label
      const stateEl = document.createElement('span');
      stateEl.className = 'entry-state';
      stateEl.style.color = getColorForSeverity(entry.severity);
      stateEl.style.fontWeight = 'bold';
      stateEl.textContent = getStateLabel(entry.state).substring(0, 12);
      entryEl.appendChild(stateEl);

      // Channel
      const channelEl = document.createElement('span');
      channelEl.className = 'entry-channel';
      channelEl.style.color = 'var(--text-secondary, #888)';
      channelEl.style.fontSize = '9px';
      channelEl.textContent = `[${(entry.channel || '').substring(0, 6)}]`;
      entryEl.appendChild(channelEl);

      // Content preview
      if (entry.content && entry.content.length > 0) {
        const contentEl = document.createElement('span');
        contentEl.className = 'entry-content';
        contentEl.style.color = 'var(--text-primary, #e0e0e0)';
        contentEl.style.fontSize = '9px';
        contentEl.textContent = truncateText(entry.content, 24);
        entryEl.appendChild(contentEl);
      }

      entriesEl.appendChild(entryEl);
    }

    el.appendChild(entriesEl);
  } else {
    const emptyEl = document.createElement('div');
    emptyEl.className = 'history-empty';
    emptyEl.style.padding = '8px';
    emptyEl.style.fontSize = '11px';
    emptyEl.style.color = 'var(--text-secondary, #888)';
    emptyEl.style.fontStyle = 'italic';
    emptyEl.textContent = 'No execution history yet';
    el.appendChild(emptyEl);
  }

  return el;
}

// =============================================================================
// State Transition Visualization
// =============================================================================

/** Render state transition indicator */
function renderStateTransition(currentState, options = {}) {
  const el = document.createElement('div');
  el.id = options.id || genId('state-transition');
  el.className = 'state-transition';
  el.style.display = 'flex';
  el.style.alignItems = 'center';
  el.style.gap = '8px';
  el.style.padding = '8px';
  el.style.backgroundColor = 'var(--bg-secondary, #1e1e1e)';
  el.style.borderRadius = '4px';

  // State icon (geometric shape based on state)
  const iconEl = document.createElement('div');
  iconEl.className = 'state-icon';
  iconEl.style.width = '16px';
  iconEl.style.height = '16px';
  iconEl.style.color = getColorForSeverity(options.severity || 'info');

  // Render geometric icon based on state
  const state = currentState?.toLowerCase() || '';
  if (state === 'streaming') {
    iconEl.style.background = 'linear-gradient(90deg, transparent, currentColor, transparent)';
    iconEl.style.borderRadius = '2px';
  } else if (state === 'proposing') {
    iconEl.style.border = '2px solid currentColor';
    iconEl.style.borderRadius = '50%';
  } else if (state === 'validating') {
    iconEl.style.width = '0';
    iconEl.style.height = '0';
    iconEl.style.borderLeft = '8px solid transparent';
    iconEl.style.borderRight = '8px solid transparent';
    iconEl.style.borderBottom = '14px solid currentColor';
  } else if (state === 'replaying') {
    iconEl.style.background = 'currentColor';
    iconEl.style.height = '2px';
    iconEl.style.width = '16px';
  } else if (state === 'stalled') {
    iconEl.style.border = '2px dashed currentColor';
    iconEl.style.borderRadius = '2px';
  } else if (state === 'completion') {
    iconEl.style.transform = 'rotate(45deg)';
    iconEl.style.borderRight = '2px solid currentColor';
    iconEl.style.borderBottom = '2px solid currentColor';
    iconEl.style.width = '10px';
    iconEl.style.height = '16px';
    iconEl.style.background = 'transparent';
  } else if (state === 'failure') {
    iconEl.style.transform = 'rotate(45deg)';
    iconEl.style.borderTop = '2px solid currentColor';
    iconEl.style.borderLeft = '2px solid currentColor';
    iconEl.style.borderBottom = '2px solid currentColor';
    iconEl.style.borderRight = '2px solid currentColor';
    iconEl.style.width = '12px';
    iconEl.style.height = '12px';
    iconEl.style.background = 'transparent';
  } else {
    iconEl.style.background = 'currentColor';
    iconEl.style.width = '8px';
    iconEl.style.height = '8px';
    iconEl.style.borderRadius = '1px';
  }

  el.appendChild(iconEl);

  // State label
  const labelEl = document.createElement('span');
  labelEl.className = 'state-label';
  labelEl.style.fontSize = '14px';
  labelEl.style.fontWeight = 'bold';
  labelEl.style.color = getColorForSeverity(options.severity || 'info');
  labelEl.textContent = getStateLabel(currentState);
  el.appendChild(labelEl);

  // Status message
  if (options.message) {
    const messageEl = document.createElement('span');
    messageEl.className = 'state-message';
    messageEl.style.fontSize = '12px';
    messageEl.style.color = 'var(--text-secondary, #888)';
    messageEl.textContent = truncateText(options.message, 32);
    el.appendChild(messageEl);
  }

  // Motion indicator (derived from state)
  if (currentState && currentState !== RuntimeInstrumentationState.IDLE && currentState !== RuntimeInstrumentationState.COMPLETION) {
    const motionEl = document.createElement('div');
    motionEl.className = 'state-motion';
    motionEl.style.width = '8px';
    motionEl.style.height = '8px';
    motionEl.style.backgroundColor = getColorForSeverity(options.severity || 'info');
    motionEl.style.borderRadius = '50%';
    motionEl.style.animation = `pulse ${ANIMATION_DURATIONS[currentState?.toLowerCase()] || '200ms'} ease-in-out infinite`;
    el.appendChild(motionEl);
  }

  return el;
}

// =============================================================================
// Supervision State Indicator
// =============================================================================

/** Render supervision state indicator */
function renderSupervisionState(supervisionState, options = {}) {
  const el = document.createElement('div');
  el.id = options.id || genId('supervision');
  el.className = 'supervision-state';
  el.style.display = 'flex';
  el.style.flexDirection = 'column';
  el.style.gap = '4px';
  el.style.padding = '6px 8px';
  el.style.backgroundColor = 'var(--bg-secondary, #1e1e1e)';
  el.style.borderRadius = '4px';

  // Header
  const header = document.createElement('div');
  header.className = 'supervision-header';
  header.style.display = 'flex';
  header.style.justifyContent = 'space-between';
  header.style.alignItems = 'center';

  const label = document.createElement('span');
  label.className = 'supervision-label';
  label.style.fontSize = '11px';
  label.style.fontWeight = 'bold';
  label.style.color = 'var(--text-primary, #e0e0e0)';
  label.textContent = 'Supervision';
  header.appendChild(label);

  const statusBadge = document.createElement('span');
  statusBadge.className = 'supervision-status';
  statusBadge.style.fontSize = '10px';
  statusBadge.style.padding = '2px 4px';
  statusBadge.style.borderRadius = '2px';
  statusBadge.style.backgroundColor = 'var(--bg-tertiary, #252526)';
  statusBadge.style.color = getColorForSeverity(supervisionState.severity || 'info');
  statusBadge.style.fontWeight = 'bold';
  statusBadge.textContent = supervisionState.status || 'Active';
  header.appendChild(statusBadge);

  el.appendChild(header);

  // Details if available
  if (supervisionState.details) {
    const detailsEl = document.createElement('div');
    detailsEl.className = 'supervision-details';
    detailsEl.style.fontSize = '10px';
    detailsEl.style.color = 'var(--text-secondary, #888)';
    detailsEl.textContent = truncateText(supervisionState.details, 48);
    el.appendChild(detailsEl);
  }

  return el;
}

// =============================================================================
// Runtime Execution Panel Widget
// =============================================================================

/** Main widget rendering function */
export function renderRuntimeExecutionPanel(id, data, context) {
  const el = document.createElement('div');
  el.id = id || 'runtime-execution-panel';
  el.className = 'widget runtime-execution-panel';
  el.setAttribute('role', 'region');
  el.setAttribute('aria-label', 'Runtime Execution Panel');
  el.style.display = 'flex';
  el.style.flexDirection = 'column';
  el.style.gap = '12px';

  // Extract instrumentation from data or create fresh
  let instrumentation;
  if (data.instrumentation && data.instrumentation.id) {
    instrumentation = RuntimeInstrumentation.fromJSON(data.instrumentation);
  } else {
    instrumentation = new RuntimeInstrumentation({
      id: data.id || id,
      streamId: data.stream_id || data.streamId,
      invocationId: data.invocation_id || data.invocationId,
      providerId: data.provider_id || data.providerId
    });

    // Process events if provided
    if (data.events && Array.isArray(data.events)) {
      for (const event of data.events) {
        instrumentation.handleEvent(event);
      }
    }

    // Process projections if provided
    if (data.projections && Array.isArray(data.projections)) {
      for (const proj of data.projections) {
        instrumentation.handleProjection(proj);
      }
    }

    // Process capability routing if provided
    if (data.capability_routing) {
      instrumentation.updateCapabilityRouting(data.capability_routing);
    }
  }

  // Title section
  const titleEl = document.createElement('h2');
  titleEl.className = 'widget-title';
  titleEl.style.fontSize = '16px';
  titleEl.style.fontWeight = 'bold';
  titleEl.style.color = 'var(--text-primary, #e0e0e0)';
  titleEl.style.margin = '0';
  titleEl.textContent = data.title || 'Runtime Execution';
  el.appendChild(titleEl);

  // Current state indicator
  const stateSummary = instrumentation.getStateSummary();
  const stateEl = renderStateTransition(stateSummary.state, {
    severity: stateSummary.severity,
    message: data.status_message || data.message,
    id: genId(id, 'state')
  });
  el.appendChild(stateEl);

  // Execution lanes (PHASE 3)
  if (data.lanes || (data.execution_lanes && data.execution_lanes.length > 0)) {
    const lanes = (data.lanes || []).map(l => new ExecutionLane(l));
    
    if (lanes.length > 0) {
      const lanesContainer = document.createElement('div');
      lanesContainer.className = 'execution-lanes-container';
      lanesContainer.style.display = 'grid';
      lanesContainer.style.gridTemplateColumns = `repeat(${Math.min(lanes.length, MAX_LANES)}, 1fr)`;
      lanesContainer.style.gap = '8px';

      for (let i = 0; i < Math.min(lanes.length, MAX_LANES); i++) {
        const laneEl = renderExecutionLane(lanes[i], {
          idPrefix: id,
          index: i
        });
        lanesContainer.appendChild(laneEl);
      }

      el.appendChild(lanesContainer);
    }
  }

  // Capability routing visualization (PHASE 4)
  const routingState = {
    runtime: data.runtime || data.provider_id || instrumentation.currentRuntime,
    capabilities: data.capabilities || instrumentation.currentCapabilities,
    trustLevel: data.trust_level || data.trust_tier || instrumentation.currentTrustLevel,
    severity: stateSummary.severity
  };

  const routingEl = renderCapabilityRouting(routingState, {
    id: genId(id, 'routing')
  });
  el.appendChild(routingEl);

  // Supervision state
  if (data.supervision) {
    const supervisionEl = renderSupervisionState(data.supervision, {
      id: genId(id, 'supervision')
    });
    el.appendChild(supervisionEl);
  }

  // Execution history
  const historyEl = renderExecutionHistory(instrumentation, {
    id: genId(id, 'history')
  });
  el.appendChild(historyEl);

  // Statistics footer
  const stats = instrumentation.getStats();
  if (stats.totalChunks > 0 || stats.totalBytes > 0 || stats.totalTokens !== '0') {
    const statsEl = document.createElement('div');
    statsEl.className = 'execution-stats';
    statsEl.style.display = 'flex';
    statsEl.style.justifyContent = 'space-between';
    statsEl.style.alignItems = 'center';
    statsEl.style.padding = '6px 8px';
    statsEl.style.backgroundColor = 'var(--bg-secondary, #1e1e1e)';
    statsEl.style.borderRadius = '4px';
    statsEl.style.fontSize = '10px';

    const statItems = [
      { label: 'Chunks', value: stats.totalChunks },
      { label: 'Tokens', value: stats.totalTokens },
      { label: 'Bytes', value: formatBytes(stats.totalBytes) },
      { label: 'Duration', value: stats.durationMs > 0 ? (stats.durationMs / 1000).toFixed(1) + 's' : '0s' }
    ];

    for (const item of statItems) {
      if (item.value !== '0' && item.value !== '0s' && item.value !== 0) {
        const itemEl = document.createElement('span');
        itemEl.className = 'stat-item';
        itemEl.style.color = 'var(--text-secondary, #888)';
        
        const label = document.createElement('span');
        label.textContent = item.label + ': ';
        itemEl.appendChild(label);
        
        const value = document.createElement('span');
        value.style.color = 'var(--text-primary, #e0e0e0)';
        value.style.fontWeight = 'bold';
        value.textContent = item.value;
        itemEl.appendChild(value);
        
        statsEl.appendChild(itemEl);
      }
    }

    el.appendChild(statsEl);
  }

  // Advisory notice
  const advisoryEl = document.createElement('div');
  advisoryEl.className = 'advisory-notice';
  advisoryEl.style.fontSize = '10px';
  advisoryEl.style.color = 'var(--text-secondary, #888)';
  advisoryEl.style.fontStyle = 'italic';
  advisoryEl.textContent = 'Execution state is advisory evidence only. Only receipts become authoritative.';
  el.appendChild(advisoryEl);

  // Replay reference
  if (data.replay_ref) {
    const replayEl = document.createElement('div');
    replayEl.className = 'replay-ref';
    replayEl.style.fontSize = '10px';
    replayEl.style.color = 'var(--text-secondary, #888)';
    replayEl.textContent = 'Replay: ' + truncateText(data.replay_ref, 20);
    el.appendChild(replayEl);
  }

  return el;
}

// =============================================================================
// Widget Registration
// =============================================================================

/** Register the widget with a registry */
export function registerRuntimeExecutionPanel(registry) {
  if (registry) {
    registry.RuntimeExecutionPanel = renderRuntimeExecutionPanel;
  }
}

// Auto-register if global registry exists
if (typeof window !== 'undefined' && window.widgetRegistry) {
  registerRuntimeExecutionPanel(window.widgetRegistry);
}
