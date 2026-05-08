/**
 * AuditTrailCard widget - Dumb rendering for workspace auditability state.
 * 
 * DOCTRINE:
 * - Dumb rendering only
 * - Projection-only data (no fetching)
 * - No authority decisions
 * - Safe fallbacks
 * - textContent only (no innerHTML)
 * - Preserves patch-based rendering
 * 
 * Data contract from backend projection:
 * - audit_completeness: string
 * - last_authoritative_event_id: string
 * - receipt_status_summary: object
 * - missing_receipts: array
 * - advisory_only_events: number
 * - authoritative_events: number
 * - advisory_only_warning: string
 * - next_missing_audit_action: string
 */

function renderAuditTrailCard(element, data) {
  const container = document.createElement('div');
  container.className = 'rig-card audit-trail-card';

  // Title
  const title = document.createElement('div');
  title.className = 'card-title';
  title.textContent = 'Audit Trail';
  container.appendChild(title);

  // Summary section
  const summary = document.createElement('div');
  summary.className = 'card-section';

  // Completeness status
  const completeness = document.createElement('div');
  completeness.className = 'status-row';
  const completenessLabel = document.createElement('span');
  completenessLabel.className = 'status-label';
  completenessLabel.textContent = 'Audit Completeness:';
  
  const completenessValue = document.createElement('span');
  completenessValue.className = 'status-value';
  const completnessText = (data && data.audit_completeness) || 'unknown';
  completenessValue.textContent = completnessText;
  
  // Add severity class based on completeness
  if (completenessText === 'complete') {
    completenessValue.className = 'status-value status-success';
  } else if (completenessText === 'not_proof' || completenessText === 'not_run') {
    completenessValue.className = 'status-value status-warning';
  } else if (completenessText === 'not_created') {
    completenessValue.className = 'status-value status-idle';
  } else {
    completenessValue.className = 'status-value status-info';
  }
  
  completeness.appendChild(completenessLabel);
  completeness.appendChild(completenessValue);
  summary.appendChild(completeness);
  container.appendChild(summary);

  // Event counts
  const counts = document.createElement('div');
  counts.className = 'status-row';
  
  const authLabel = document.createElement('span');
  authLabel.className = 'status-label';
  authLabel.textContent = 'Authoritative:';
  
  const authValue = document.createElement('span');
  authValue.className = 'status-value';
  authValue.textContent = String((data && data.authoritative_events) || 0);
  
  const advisoryLabel = document.createElement('span');
  advisoryLabel.className = 'status-label';
  advisoryLabel.textContent = 'Advisory Only:';
  
  const advisoryValue = document.createElement('span');
  advisoryValue.className = 'status-value';
  advisoryValue.textContent = String((data && data.advisory_only_events) || 0);
  
  counts.appendChild(authLabel);
  counts.appendChild(authValue);
  counts.appendChild(document.createTextNode(' '));
  counts.appendChild(advisoryLabel);
  counts.appendChild(advisoryValue);
  summary.appendChild(counts);

  // Last authoritative event
  if (data && data.last_authoritative_event_id) {
    const lastEvent = document.createElement('div');
    lastEvent.className = 'status-row';
    const lastEventLabel = document.createElement('span');
    lastEventLabel.className = 'status-label';
    lastEventLabel.textContent = 'Last Event:';
    const lastEventValue = document.createElement('span');
    lastEventValue.className = 'status-value status-mono';
    lastEventValue.textContent = data.last_authoritative_event_id;
    lastEvent.appendChild(lastEventLabel);
    lastEvent.appendChild(lastEventValue);
    summary.appendChild(lastEvent);
  }

  // Missing receipts
  const missing = (data && data.missing_receipts) || [];
  if (missing.length > 0) {
    const missingSection = document.createElement('div');
    missingSection.className = 'card-section';
    
    const missingTitle = document.createElement('div');
    missingTitle.className = 'section-title';
    missingTitle.textContent = 'Missing Receipts:';
    missingSection.appendChild(missingTitle);
    
    const missingList = document.createElement('ul');
    missingList.className = 'list-compact';
    for (const receiptKind of missing) {
      const item = document.createElement('li');
      item.textContent = receiptKind;
      missingList.appendChild(item);
    }
    missingSection.appendChild(missingList);
    container.appendChild(missingSection);
  }

  // Action hint
  if (data && data.next_missing_audit_action) {
    const actionHint = document.createElement('div');
    actionHint.className = 'card-section hint';
    actionHint.textContent = data.next_missing_audit_action;
    container.appendChild(actionHint);
  }

  // Advisory only warning
  if (data && data.advisory_only_warning) {
    const warning = document.createElement('div');
    warning.className = 'card-section warning';
    warning.textContent = data.advisory_only_warning;
    container.appendChild(warning);
  }

  // Clear existing content and append
  while (element.firstChild) {
    element.removeChild(element.firstChild);
  }
  element.appendChild(container);
}

// Register widget
if (typeof window !== 'undefined' && window.rigWidgets) {
  window.rigWidgets = window.rigWidgets || {};
  window.rigWidgets.AuditTrailCard = {
    render: renderAuditTrailCard
  };
}

// Export for module systems
if (typeof module !== 'undefined' && module.exports) {
  module.exports = { renderAuditTrailCard };
}
