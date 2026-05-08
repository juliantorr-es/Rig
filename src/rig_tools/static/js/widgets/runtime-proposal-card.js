/** Runtime Proposal Card Widget
 *
 * Renders runtime proposal summaries from stream events.
 * 
 * Core doctrine:
 * - Projection-only rendering (never fetches data)
 * - No authority inference
 * - No timers
 * - Deterministic rendering
 * - Safe truncation
 * - textContent-only rendering
 * - Replay-safe rendering
 * - Advisory indicators
 *
 * This widget displays:
 * - Proposal summaries
 * - Capability usage
 * - Risk assessment
 * - Runtime diagnostics
 * - Replay linkage
 * - Integrity flags
 * - Advisory indicators
 */

export function renderRuntimeProposalCard(id, data, context) {
  const el = document.createElement('div');
  el.className = 'widget runtime-proposal-card';
  el.setAttribute('role', 'region');
  el.setAttribute('aria-label', 'Runtime Proposal');
  el.setAttribute('aria-live', 'polite');

  // Header with title and status
  const header = document.createElement('div');
  header.className = 'widget-header';
  header.style.display = 'flex';
  header.style.justifyContent = 'space-between';
  header.style.alignItems = 'center';

  const titleEl = document.createElement('h2');
  titleEl.textContent = data.title || 'Runtime Proposal';
  header.appendChild(titleEl);

  // Proposal status badge
  const status = data.status || data.proposal_status || 'pending';
  const severity = data.severity || 
                  (typeof status === 'object' ? status.severity : null) ||
                  getProposalSeverity(status);
  const statusBadge = document.createElement('div');
  statusBadge.className = 'badge severity-' + severity;
  const statusText = typeof status === 'string' ? status :
                    (status.label || status.value || 'pending');
  statusBadge.textContent = capitalizeFirst(statusText);
  header.appendChild(statusBadge);

  el.appendChild(header);

  // Proposal content section
  const contentSection = document.createElement('div');
  contentSection.className = 'runtime-proposal-content';
  contentSection.style.marginTop = '12px';

  // Proposal title/name
  if (data.proposal_title || data.name) {
    const proposalTitle = document.createElement('div');
    proposalTitle.className = 'runtime-proposal-title';
    proposalTitle.style.fontSize = '14px';
    proposalTitle.style.fontWeight = 'bold';
    proposalTitle.style.color = 'var(--text-primary, #e0e0e0)';
    proposalTitle.style.marginBottom = '8px';
    proposalTitle.textContent = data.proposal_title || data.name || 'Unnamed Proposal';
    contentSection.appendChild(proposalTitle);
  }

  // Proposal description
  if (data.description || data.proposal_description) {
    const descEl = document.createElement('div');
    descEl.className = 'runtime-proposal-description';
    descEl.style.fontSize = '13px';
    descEl.style.color = 'var(--text-secondary, #ccc)';
    descEl.style.marginBottom = '8px';
    descEl.style.lineHeight = '1.4';
    descEl.style.whiteSpace = 'pre-wrap';
    descEl.style.wordBreak = 'break-word';
    
    const maxDescLen = data.max_description_length || 500;
    let description = data.description || data.proposal_description || '';
    if (description.length > maxDescLen) {
      description = description.substring(0, maxDescLen) + '...';
    }
    descEl.textContent = description;
    contentSection.appendChild(descEl);
  }

  el.appendChild(contentSection);

  // Proposal details grid
  const detailsSection = document.createElement('div');
  detailsSection.className = 'runtime-proposal-details';
  detailsSection.style.marginTop = '12px';
  detailsSection.style.display = 'grid';
  detailsSection.style.gridTemplateColumns = 'auto 1fr';
  detailsSection.style.gap = '4px 8px';
  detailsSection.style.fontSize = '12px';

  // Collect detail fields
  const detailFields = [
    { label: 'Proposal ID', value: data.proposal_id },
    { label: 'Kind', value: data.kind || data.proposal_kind },
    { label: 'Capability', value: data.capability },
    { label: 'Command', value: data.command },
    { label: 'Tool', value: data.tool },
    { label: 'Arguments', value: data.arguments },
    { label: 'Path', value: data.path },
    { label: 'Language', value: data.language },
    { label: 'Line', value: data.line },
    { label: 'Column', value: data.column },
    { label: 'Diff', value: data.diff },
  ];

  for (const field of detailFields) {
    if (field.value !== undefined && field.value !== null && field.value !== '') {
      const keyEl = document.createElement('div');
      keyEl.style.color = 'var(--text-secondary, #888)';
      keyEl.textContent = field.label + ':';

      const valueEl = document.createElement('div');
      valueEl.style.color = 'var(--text-primary, #e0e0e0)';
      valueEl.textContent = truncateText(String(field.value), 40);

      detailsSection.appendChild(keyEl);
      detailsSection.appendChild(valueEl);
    }
  }

  el.appendChild(detailsSection);

  // Risk assessment section
  if (data.risk_assessment || data.risk) {
    const riskSection = document.createElement('div');
    riskSection.className = 'runtime-proposal-risk';
    riskSection.style.marginTop = '12px';

    const riskTitle = document.createElement('div');
    riskTitle.className = 'section-title';
    riskTitle.style.fontSize = '12px';
    riskTitle.style.color = 'var(--text-secondary, #888)';
    riskTitle.style.marginBottom = '4px';
    riskTitle.textContent = 'Risk Assessment:';
    riskSection.appendChild(riskTitle);

    const riskData = data.risk_assessment || data.risk || {};
    const riskGrid = document.createElement('div');
    riskGrid.style.display = 'flex';
    riskGrid.style.flexWrap = 'wrap';
    riskGrid.style.gap = '8px';

    // Risk level badge
    const riskLevel = riskData.level || riskData.risk_level || 'unknown';
    const riskLevelEl = document.createElement('span');
    riskLevelEl.className = 'badge severity-' + getRiskSeverity(riskLevel);
    riskLevelEl.style.fontSize = '11px';
    riskLevelEl.textContent = 'Risk: ' + capitalizeFirst(riskLevel);
    riskGrid.appendChild(riskLevelEl);

    // Risk score
    if (riskData.score !== undefined) {
      const scoreEl = document.createElement('span');
      scoreEl.className = 'badge severity-info';
      scoreEl.style.fontSize = '11px';
      scoreEl.textContent = 'Score: ' + formatNumber(riskData.score);
      riskGrid.appendChild(scoreEl);
    }

    // Risk reasons
    const reasons = riskData.reasons || riskData.reason || [];
    if (Array.isArray(reasons) && reasons.length > 0) {
      for (const reason of reasons.slice(0, 3)) {
        const reasonEl = document.createElement('span');
        reasonEl.className = 'badge severity-warning';
        reasonEl.style.fontSize = '10px';
        reasonEl.textContent = truncateText(reason, 20);
        riskGrid.appendChild(reasonEl);
      }
    } else if (typeof reasons === 'string' && reasons) {
      const reasonEl = document.createElement('span');
      reasonEl.className = 'badge severity-warning';
      reasonEl.style.fontSize = '10px';
      reasonEl.textContent = truncateText(reasons, 20);
      riskGrid.appendChild(reasonEl);
    }

    riskSection.appendChild(riskGrid);
    el.appendChild(riskSection);
  }

  // Capability usage
  if (data.capabilities && data.capabilities.length > 0) {
    const capSection = document.createElement('div');
    capSection.className = 'runtime-proposal-capabilities';
    capSection.style.marginTop = '12px';

    const capTitle = document.createElement('div');
    capTitle.className = 'section-title';
    capTitle.style.fontSize = '12px';
    capTitle.style.color = 'var(--text-secondary, #888)';
    capTitle.style.marginBottom = '4px';
    capTitle.textContent = 'Capabilities Required:';
    capSection.appendChild(capTitle);

    const capList = document.createElement('div');
    capList.className = 'capability-list';
    capList.style.display = 'flex';
    capList.style.flexWrap = 'wrap';
    capList.style.gap = '4px';

    for (const cap of data.capabilities) {
      const capEl = document.createElement('span');
      capEl.className = 'capability-item badge severity-info';
      capEl.style.fontSize = '11px';
      const capName = typeof cap === 'string' ? cap : 
                      (cap.name || cap.kind || cap.capability_id || cap.id || 'unknown');
      capEl.textContent = capName;
      capList.appendChild(capEl);
    }

    capSection.appendChild(capList);
    el.appendChild(capSection);
  }

  // Diagnostics section
  if (data.diagnostics && Object.keys(data.diagnostics).length > 0) {
    const diagnosticsSection = document.createElement('div');
    diagnosticsSection.className = 'runtime-proposal-diagnostics';
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

  // Code preview section (for patch proposals)
  if (data.code || data.diff || data.patch) {
    const codeSection = document.createElement('div');
    codeSection.className = 'runtime-proposal-code';
    codeSection.style.marginTop = '12px';

    const codeTitle = document.createElement('div');
    codeTitle.className = 'section-title';
    codeTitle.style.fontSize = '12px';
    codeTitle.style.color = 'var(--text-secondary, #888)';
    codeTitle.style.marginBottom = '4px';
    codeTitle.textContent = 'Code Preview:';
    codeSection.appendChild(codeTitle);

    const codeBlock = document.createElement('div');
    codeBlock.className = 'code-block';
    codeBlock.style.fontFamily = 'monospace';
    codeBlock.style.fontSize = '11px';
    codeBlock.style.whiteSpace = 'pre-wrap';
    codeBlock.style.wordBreak = 'break-all';
    codeBlock.style.backgroundColor = 'var(--bg-secondary, #1e1e1e)';
    codeBlock.style.color = 'var(--text-primary, #e0e0e0)';
    codeBlock.style.padding = '8px';
    codeBlock.style.borderRadius = '4px';
    codeBlock.style.border = '1px solid var(--border, #404040)';
    codeBlock.style.maxHeight = '200px';
    codeBlock.style.overflowY = 'auto';

    const codeContent = data.code || data.diff || data.patch || '';
    const maxCodeLen = data.max_code_length || 1000;
    codeBlock.textContent = codeContent.length > maxCodeLen 
      ? codeContent.substring(0, maxCodeLen) + '...' 
      : codeContent;

    codeSection.appendChild(codeBlock);
    el.appendChild(codeSection);
  }

  // Metadata footer
  const metadataArea = document.createElement('div');
  metadataArea.className = 'runtime-proposal-metadata';
  metadataArea.style.marginTop = '12px';
  metadataArea.style.display = 'flex';
  metadataArea.style.flexWrap = 'wrap';
  metadataArea.style.gap = '8px';
  metadataArea.style.fontSize = '11px';
  metadataArea.style.color = 'var(--text-secondary, #888)';

  const metadataItems = [
    { label: 'Proposal', value: data.proposal_id },
    { label: 'Stream', value: data.stream_id },
    { label: 'Invocation', value: data.invocation_id },
    { label: 'Provider', value: data.provider_id },
    { label: 'Model', value: data.model_id },
    { label: 'Created', value: data.created_at },
    { label: 'Sequence', value: data.sequence },
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

  // Blocked reason (if proposal was blocked)
  if (data.blocked_reason || data.violation) {
    const blockedSection = document.createElement('div');
    blockedSection.className = 'runtime-proposal-blocked';
    blockedSection.style.marginTop = '8px';
    blockedSection.style.padding = '8px';
    blockedSection.style.backgroundColor = 'var(--bg-error, rgba(255, 0, 0, 0.1))';
    blockedSection.style.borderRadius = '4px';
    blockedSection.style.border = '1px solid var(--border-error, #880000)';

    const blockedLabel = document.createElement('span');
    blockedLabel.style.color = 'var(--color-error, #ff5555)';
    blockedLabel.style.fontWeight = 'bold';
    blockedLabel.textContent = 'BLOCKED: ';
    blockedSection.appendChild(blockedLabel);

    const reason = data.blocked_reason || data.violation || 'Unknown reason';
    const blockedValue = document.createElement('span');
    blockedValue.style.color = 'var(--color-error, #ff5555)';
    blockedValue.textContent = reason;
    blockedSection.appendChild(blockedValue);

    el.appendChild(blockedSection);
  }

  // Advisory notice
  const advisoryEl = document.createElement('div');
  advisoryEl.className = 'advisory-notice';
  advisoryEl.style.marginTop = '8px';
  advisoryEl.style.fontSize = '11px';
  advisoryEl.style.color = 'var(--text-secondary, #888)';
  advisoryEl.style.fontStyle = 'italic';
  advisoryEl.textContent = 'Proposals are advisory evidence only. Only receipts become authoritative.';
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

  return el;
}

// Helper functions

function getProposalSeverity(status) {
  const severityMap = {
    pending: 'info',
    proposed: 'info',
    queued: 'info',
    active: 'info',
    running: 'info',
    succeeded: 'info',
    completed: 'info',
    accepted: 'info',

    reviewing: 'warning',
    assessing: 'warning',
    paused: 'warning',
    degraded: 'warning',
    stalled: 'warning',

    blocked: 'error',
    rejected: 'error',
    failed: 'error',
    error: 'error',
    violated: 'error',
    cancelled: 'error',
    forbidden: 'error'
  };
  const normalized = (status || 'pending').toLowerCase();
  return severityMap[normalized] || 'info';
}

function getRiskSeverity(level) {
  const severityMap = {
    none: 'info',
    low: 'info',
    minimal: 'info',

    medium: 'warning',
    moderate: 'warning',
    high: 'warning',

    critical: 'error',
    severe: 'error',
    extreme: 'error',
    forbidden: 'error'
  };
  const normalized = (level || 'unknown').toLowerCase();
  return severityMap[normalized] || 'warning';
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
export function registerRuntimeProposalCard(registry) {
  if (registry) {
    registry.RuntimeProposalCard = renderRuntimeProposalCard;
  }
}
