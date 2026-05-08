/**
 * ReplayTimelineCard widget - Dumb rendering for governance replay timeline.
 * 
 * DOCTRINE:
 * - Dumb rendering only (no fetching, no mutation, no timers)
 * - Projection-only data inputs (from build_replay_projection or build_replay_projection_summary)
 * - No authority decisions
 * - No side effects
 * - Deterministic: same input -> same DOM output
 * - textContent only (no innerHTML)
 * - Safe fallbacks for missing data
 * - Preserves advisory vs authoritative distinctions
 * 
 * Data contract from backend projection:
 * - replay_id: string
 * - workspace_id: string
 * - frame_index: number (current frame)
 * - total_frames: number
 * - workspace_status: string
 * - status_history: array of {status, at} objects
 * - receipt_chain: array of receipt IDs
 * - audit_chain: array of audit event IDs
 * - authoritative_evidence_available: boolean
 * - advisory_only_evidence_present: boolean
 * - is_terminal: boolean
 * - terminal_reason: string
 * - has_conflicts: boolean
 * - conflict_count: number
 * - conflict_types: object (type -> count)
 * - finding_count: number
 * - findings_by_severity: object (severity -> count)
 * - state: string (replay state)
 */

function createElement(tag, className, text) {
  const el = document.createElement(tag);
  if (className) el.className = className;
  if (text !== null && text !== undefined) el.textContent = String(text);
  return el;
}

function getValue(data, key, defaultValue) {
  if (!data) return defaultValue;
  const value = data[key];
  return value !== null && value !== undefined ? value : defaultValue;
}

function formatTimestamp(ts) {
  if (!ts) return '';
  try {
    // Clean up the timestamp string for display
    let cleaned = String(ts);
    // Remove trailing Z and replace T with space for readability
    cleaned = cleaned.replace('T', ' ').replace('Z', '');
    // Truncate to seconds (remove milliseconds)
    const dotIndex = cleaned.indexOf('.');
    if (dotIndex > 0) {
      cleaned = cleaned.substring(0, dotIndex);
    }
    return cleaned;
  } catch {
    return String(ts);
  }
}

function renderStatusBadge(status, className) {
  const badge = createElement('span', 'replay-status-badge', status || 'unknown');
  if (className) {
    badge.className += ' ' + className;
  }
  return badge;
}

function renderConflictTypeCount(type, count) {
  const item = createElement('div', 'replay-conflict-item');
  const label = createElement('span', 'replay-conflict-label', type.replace(/_/g, ' '));
  const value = createElement('span', 'replay-conflict-value', String(count));
  item.appendChild(label);
  item.appendChild(createElement('span', 'replay-separator', ':'));
  item.appendChild(value);
  return item;
}

function renderFindingSeverityCount(severity, count) {
  const item = createElement('div', 'replay-finding-item');
  const label = createElement('span', 'replay-finding-label', severity);
  const value = createElement('span', 'replay-finding-value', String(count));
  item.appendChild(label);
  item.appendChild(createElement('span', 'replay-separator', ':'));
  item.appendChild(value);
  return item;
}

function renderStatusTransition(fromStatus, toStatus, at) {
  const item = createElement('div', 'replay-transition-item');
  const arrow = createElement('span', 'replay-transition-arrow', '→');
  const from = createElement('span', 'replay-transition-from', fromStatus || 'unknown');
  const to = createElement('span', 'replay-transition-to', toStatus || 'unknown');
  const timestamp = createElement('span', 'replay-transition-time', formatTimestamp(at));
  
  item.appendChild(from);
  item.appendChild(arrow);
  item.appendChild(to);
  item.appendChild(timestamp);
  return item;
}

function renderReplayTimelineCard(element, data) {
  const container = createElement('div', 'rig-card replay-timeline-card');

  // Title section
  const titleSection = createElement('div', 'card-title');
  const title = createElement('span', 'replay-title', 'Replay Timeline');
  titleSection.appendChild(title);
  container.appendChild(titleSection);

  // Header: Replay ID and Workspace ID
  const headerRow = createElement('div', 'replay-header-row');
  const replayIdLabel = createElement('span', 'replay-header-label', 'Replay:');
  const replayIdValue = createElement('span', 'replay-header-value replay-mono', 
    getValue(data, 'replay_id', 'unknown'));
  headerRow.appendChild(replayIdLabel);
  headerRow.appendChild(replayIdValue);
  
  if (getValue(data, 'workspace_id', null)) {
    const separator = createElement('span', 'replay-separator', '|');
    const workspaceLabel = createElement('span', 'replay-header-label', ' Workspace:');
    const workspaceValue = createElement('span', 'replay-header-value replay-mono', 
      getValue(data, 'workspace_id', 'unknown'));
    headerRow.appendChild(separator);
    headerRow.appendChild(workspaceLabel);
    headerRow.appendChild(workspaceValue);
  }
  container.appendChild(headerRow);

  // Frame navigation info
  const frameInfoRow = createElement('div', 'replay-frame-info');
  const frameIndex = getValue(data, 'frame_index', -1);
  const totalFrames = getValue(data, 'total_frames', 0);
  const frameLabel = createElement('span', 'replay-frame-label', 'Frame:');
  const frameValue = createElement('span', 'replay-frame-value', 
    totalFrames > 0 ? `${frameIndex + 1}/${totalFrames}` : '0/0');
  frameInfoRow.appendChild(frameLabel);
  frameInfoRow.appendChild(frameValue);
  container.appendChild(frameInfoRow);

  // Current Status section
  const statusSection = createElement('div', 'card-section replay-status-section');
  const statusRow = createElement('div', 'replay-status-row');
  const statusLabel = createElement('span', 'replay-status-label', 'Current Status:');
  const currentStatus = getValue(data, 'workspace_status', 'unknown');
  const statusValue = renderStatusBadge(currentStatus, 'replay-status-current');
  statusRow.appendChild(statusLabel);
  statusRow.appendChild(statusValue);
  statusSection.appendChild(statusRow);
  container.appendChild(statusSection);

  // Terminal state indicator
  const isTerminal = getValue(data, 'is_terminal', false);
  const terminalReason = getValue(data, 'terminal_reason', '');
  if (isTerminal && terminalReason) {
    const terminalSection = createElement('div', 'card-section replay-terminal-section');
    const terminalLabel = createElement('span', 'replay-terminal-label', 'Terminal:');
    const terminalValue = createElement('span', 'replay-terminal-value', terminalReason);
    terminalSection.appendChild(terminalLabel);
    terminalSection.appendChild(terminalValue);
    container.appendChild(terminalSection);
  }

  // Replay State
  const replayState = getValue(data, 'state', 'unknown');
  const stateSection = createElement('div', 'card-section replay-state-section');
  const stateRow = createElement('div', 'replay-state-row');
  const stateLabel = createElement('span', 'replay-state-label', 'Replay State:');
  const stateBadge = renderStatusBadge(replayState, 'replay-state-badge');
  stateRow.appendChild(stateLabel);
  stateRow.appendChild(stateBadge);
  stateSection.appendChild(stateRow);
  container.appendChild(stateSection);

  // Chain continuity section
  const chainSection = createElement('div', 'card-section replay-chain-section');
  
  // Receipt chain
  const receiptChain = getValue(data, 'receipt_chain', []);
  const auditChain = getValue(data, 'audit_chain', []);
  
  if (receiptChain.length > 0 || auditChain.length > 0) {
    const chainTitle = createElement('div', 'replay-chain-title', 'Chain Continuity');
    chainSection.appendChild(chainTitle);
    
    const receiptRow = createElement('div', 'replay-chain-row');
    const receiptLabel = createElement('span', 'replay-chain-label', 'Receipt Chain:');
    const receiptCount = createElement('span', 'replay-chain-count', String(receiptChain.length));
    receiptRow.appendChild(receiptLabel);
    receiptRow.appendChild(receiptCount);
    chainSection.appendChild(receiptRow);
    
    const auditRow = createElement('div', 'replay-chain-row');
    const auditLabel = createElement('span', 'replay-chain-label', 'Audit Chain:');
    const auditCount = createElement('span', 'replay-chain-count', String(auditChain.length));
    auditRow.appendChild(auditLabel);
    auditRow.appendChild(auditCount);
    chainSection.appendChild(auditRow);
    
    container.appendChild(chainSection);
  }

  // Status History / Timeline section
  const history = getValue(data, 'status_history', []);
  if (history && history.length > 0) {
    const historySection = createElement('div', 'card-section replay-history-section');
    const historyTitle = createElement('div', 'replay-history-title', 'Status Transitions');
    historySection.appendChild(historyTitle);
    
    for (let i = 1; i < history.length; i++) {
      const prev = history[i - 1];
      const curr = history[i];
      const transition = renderStatusTransition(
        prev && prev.status ? prev.status : 'unknown',
        curr && curr.status ? curr.status : 'unknown',
        curr && curr.at ? curr.at : ''
      );
      historySection.appendChild(transition);
    }
    
    container.appendChild(historySection);
  }

  // Evidence availability
  const authAvailable = getValue(data, 'authoritative_evidence_available', false);
  const advisoryPresent = getValue(data, 'advisory_only_evidence_present', false);
  
  const evidenceSection = createElement('div', 'card-section replay-evidence-section');
  const evidenceTitle = createElement('div', 'replay-evidence-title', 'Evidence Available');
  evidenceSection.appendChild(evidenceTitle);
  
  const authRow = createElement('div', 'replay-evidence-row');
  const authLabel = createElement('span', 'replay-evidence-label', 'Authoritative:');
  const authValue = createElement('span', 'replay-evidence-value', 
    authAvailable ? 'Yes' : 'No');
  authRow.appendChild(authLabel);
  authRow.appendChild(authValue);
  evidenceSection.appendChild(authRow);
  
  const advisoryRow = createElement('div', 'replay-evidence-row');
  const advisoryLabel = createElement('span', 'replay-evidence-label', 'Advisory Only:');
  const advisoryValue = createElement('span', 'replay-evidence-value', 
    advisoryPresent ? 'Yes' : 'No');
  advisoryRow.appendChild(advisoryLabel);
  advisoryRow.appendChild(advisoryValue);
  evidenceSection.appendChild(advisoryRow);
  
  container.appendChild(evidenceSection);

  // Conflicts section
  const conflictCount = getValue(data, 'conflict_count', 0);
  const conflictTypes = getValue(data, 'conflict_types', {});
  const hasConflicts = getValue(data, 'has_conflicts', false);
  
  if (hasConflicts || conflictCount > 0 || Object.keys(conflictTypes).length > 0) {
    const conflictsSection = createElement('div', 'card-section replay-conflicts-section');
    const conflictsTitle = createElement('div', 'replay-conflicts-title', 
      `Conflicts (${conflictCount})`);
    conflictsSection.appendChild(conflictsTitle);
    
    for (const [type, count] of Object.entries(conflictTypes)) {
      conflictsSection.appendChild(renderConflictTypeCount(type, count));
    }
    
    container.appendChild(conflictsSection);
  }

  // Findings section
  const findingCount = getValue(data, 'finding_count', 0);
  const findingsBySeverity = getValue(data, 'findings_by_severity', {});
  
  if (findingCount > 0 || Object.keys(findingsBySeverity).length > 0) {
    const findingsSection = createElement('div', 'card-section replay-findings-section');
    const findingsTitle = createElement('div', 'replay-findings-title', 
      `Findings (${findingCount})`);
    findingsSection.appendChild(findingsTitle);
    
    const severityOrder = ['critical', 'error', 'warning', 'info'];
    for (const severity of severityOrder) {
      const count = findingsBySeverity[severity] || 0;
      if (count > 0) {
        const item = renderFindingSeverityCount(severity, count);
        item.className += ' replay-finding-severity-' + severity;
        findingsSection.appendChild(item);
      }
    }
    
    // Also show zero counts for completeness in summary view
    const showAllSeverities = getValue(data, 'type', '') === 'ReplaySummary';
    if (showAllSeverities) {
      for (const severity of severityOrder) {
        const count = findingsBySeverity[severity] || 0;
        if (count === 0) {
          const item = renderFindingSeverityCount(severity, 0);
          item.className += ' replay-finding-severity-' + severity;
          findingsSection.appendChild(item);
        }
      }
    }
    
    container.appendChild(findingsSection);
  }

  // Boolean flags (from summary projection)
  const flagsSection = createElement('div', 'card-section replay-flags-section');
  const flags = [
    { key: 'has_impossible_transitions', label: 'Impossible Transitions' },
    { key: 'has_missing_receipts', label: 'Missing Receipts' },
    { key: 'has_missing_audit_events', label: 'Missing Audit Events' },
    { key: 'has_stale_references', label: 'Stale References' },
    { key: 'has_orphaned_events', label: 'Orphaned Events' },
    { key: 'has_contradictions', label: 'Contradictions' },
  ];
  
  let hasAnyFlag = false;
  for (const flag of flags) {
    const flagValue = getValue(data, flag.key, false);
    if (flagValue) {
      hasAnyFlag = true;
      const flagElement = createElement('div', 'replay-flag-item replay-flag-active', flag.label);
      flagsSection.appendChild(flagElement);
    }
  }
  
  // Show inactive flags in summary view for completeness
  const showAllFlags = getValue(data, 'type', '') === 'ReplaySummary';
  if (showAllFlags && !hasAnyFlag) {
    for (const flag of flags) {
      const flagValue = getValue(data, flag.key, false);
      const flagElement = createElement('div', 'replay-flag-item replay-flag-inactive', flag.label);
      flagsSection.appendChild(flagElement);
    }
    hasAnyFlag = true;
  }
  
  if (hasAnyFlag) {
    const flagsTitle = createElement('div', 'replay-flags-title', 'Integrity Flags');
    flagsSection.insertBefore(flagsTitle, flagsSection.firstChild);
    container.appendChild(flagsSection);
  }

  // Timeline completeness indicator
  if (totalFrames > 0) {
    const timelineComplete = frameIndex >= totalFrames - 1;
    const completenessSection = createElement('div', 'card-section replay-completeness-section');
    const completenessLabel = createElement('span', 'replay-completeness-label', 'Timeline:');
    const completenessValue = createElement('span', 'replay-completeness-value',
      timelineComplete ? 'Complete' : 'Partial');
    completenessSection.appendChild(completenessLabel);
    completenessSection.appendChild(completenessValue);
    container.appendChild(completenessSection);
  }

  // Authoritative vs Advisory note
  const authNote = createElement('div', 'replay-advisory-note');
  authNote.textContent = 'Replay findings are advisory. Rig remains the final authority.';
  container.appendChild(authNote);

  // Clear existing content and append
  while (element.firstChild) {
    element.removeChild(element.firstChild);
  }
  element.appendChild(container);
}

// Register widget
if (typeof window !== 'undefined' && window.rigWidgets) {
  window.rigWidgets = window.rigWidgets || {};
  window.rigWidgets.ReplayTimelineCard = {
    render: renderReplayTimelineCard
  };
}

// Export for module systems
if (typeof module !== 'undefined' && module.exports) {
  module.exports = { renderReplayTimelineCard };
}
