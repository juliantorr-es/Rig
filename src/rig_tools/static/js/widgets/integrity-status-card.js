/**
 * IntegrityStatusCard widget - Dumb rendering for projection integrity status.
 * 
 * DOCTRINE:
 * - Dumb rendering only
 * - Projection-only data (no fetching)
 * - No authority decisions
 * - No mutation
 * - Safe fallbacks
 * - textContent only (no innerHTML)
 * 
 * Data contract from backend projection:
 * - integrity_status: string ("unknown", "clean", "warnings", "errors", "critical")
 * - contract_status: string ("unknown", "all_passed", "violations_found")
 * - projection_violation_count: number
 * - authority_mismatch_count: number
 * - receipt_backing_failure_count: number
 * - audit_backing_failure_count: number
 * - next_integrity_action: string
 * - stale_receipt_detected: boolean (optional)
 * - orphaned_receipt_detected: boolean (optional)
 * - orphaned_audit_detected: boolean (optional)
 * - schema_version: string
 * - source_schema_version: string
 */

export function renderIntegrityStatusCard(id, data, actions) {
  const container = document.createElement('div');
  container.className = 'rig-card integrity-status-card';

  // Title
  const title = document.createElement('div');
  title.className = 'card-title';
  title.textContent = 'Integrity Status';
  container.appendChild(title);

  // Main status section
  const statusSection = document.createElement('div');
  statusSection.className = 'integrity-main-status';

  if (data && (data.schema_version || data.source_schema_version)) {
    const lineage = document.createElement('div');
    lineage.className = 'integrity-row';
    const lineageLabel = document.createElement('span');
    lineageLabel.className = 'integrity-row-label';
    lineageLabel.textContent = 'Lineage:';
    const lineageValue = document.createElement('span');
    lineageValue.className = 'integrity-row-value';
    lineageValue.textContent = `${data.schema_version || 'rig.integrity.v1'} / ${data.source_schema_version || 'unknown'}`;
    lineage.appendChild(lineageLabel);
    lineage.appendChild(lineageValue);
    statusSection.appendChild(lineage);
  }

  // Overall integrity status
  const integrityStatus = (data && data.integrity_status) || 'unknown';
  const statusBadge = document.createElement('div');
  statusBadge.className = 'integrity-badge';
  
  // Set severity class based on status
  if (integrityStatus === 'critical') {
    statusBadge.className = 'integrity-badge status-critical';
  } else if (integrityStatus === 'errors') {
    statusBadge.className = 'integrity-badge status-errors';
  } else if (integrityStatus === 'warnings') {
    statusBadge.className = 'integrity-badge status-warning';
  } else if (integrityStatus === 'clean') {
    statusBadge.className = 'integrity-badge status-clean';
  } else {
    statusBadge.className = 'integrity-badge status-info';
  }
  
  statusBadge.textContent = integrityStatus.toUpperCase();
  statusSection.appendChild(statusBadge);

  // Status label
  const statusLabel = document.createElement('span');
  statusLabel.className = 'integrity-label';
  statusLabel.textContent = integrityStatus.replace(/_/g, ' ');
  statusSection.appendChild(statusLabel);
  
  container.appendChild(statusSection);

  // Contract status
  const contractStatus = (data && data.contract_status) || 'unknown';
  const contractRow = document.createElement('div');
  contractRow.className = 'integrity-row';
  
  const contractLabel = document.createElement('span');
  contractLabel.className = 'integrity-row-label';
  contractLabel.textContent = 'Contract Status:';
  
  const contractValue = document.createElement('span');
  contractValue.className = 'integrity-row-value';
  contractValue.textContent = contractStatus.replace(/_/g, ' ');
  
  contractRow.appendChild(contractLabel);
  contractRow.appendChild(contractValue);
  container.appendChild(contractRow);

  // Violation counts section
  const countsSection = document.createElement('div');
  countsSection.className = 'integrity-counts';

  // Projection violations
  const projViolations = (data && typeof data.projection_violation_count === 'number') ? data.projection_violation_count : 0;
  if (projViolations > 0) {
    const projRow = document.createElement('div');
    projRow.className = 'integrity-count-item';
    const projLabel = document.createElement('span');
    projLabel.className = 'integrity-count-label';
    projLabel.textContent = 'Projection Violations:';
    const projValue = document.createElement('span');
    projValue.className = 'integrity-count-value';
    projValue.textContent = String(projViolations);
    projRow.appendChild(projLabel);
    projRow.appendChild(projValue);
    countsSection.appendChild(projRow);
  }

  // Authority mismatches
  const authMismatches = (data && typeof data.authority_mismatch_count === 'number') ? data.authority_mismatch_count : 0;
  if (authMismatches > 0) {
    const authRow = document.createElement('div');
    authRow.className = 'integrity-count-item';
    const authLabel = document.createElement('span');
    authLabel.className = 'integrity-count-label';
    authLabel.textContent = 'Authority Mismatches:';
    const authValue = document.createElement('span');
    authValue.className = 'integrity-count-value';
    authValue.textContent = String(authMismatches);
    authRow.appendChild(authLabel);
    authRow.appendChild(authValue);
    countsSection.appendChild(authRow);
  }

  // Receipt backing failures
  const receiptFailures = (data && typeof data.receipt_backing_failure_count === 'number') ? data.receipt_backing_failure_count : 0;
  if (receiptFailures > 0) {
    const receiptRow = document.createElement('div');
    receiptRow.className = 'integrity-count-item';
    const receiptLabel = document.createElement('span');
    receiptLabel.className = 'integrity-count-label';
    receiptLabel.textContent = 'Receipt Backing Failures:';
    const receiptValue = document.createElement('span');
    receiptValue.className = 'integrity-count-value';
    receiptValue.textContent = String(receiptFailures);
    receiptRow.appendChild(receiptLabel);
    receiptRow.appendChild(receiptValue);
    countsSection.appendChild(receiptRow);
  }

  // Audit backing failures
  const auditFailures = (data && typeof data.audit_backing_failure_count === 'number') ? data.audit_backing_failure_count : 0;
  if (auditFailures > 0) {
    const auditRow = document.createElement('div');
    auditRow.className = 'integrity-count-item';
    const auditLabel = document.createElement('span');
    auditLabel.className = 'integrity-count-label';
    auditLabel.textContent = 'Audit Backing Failures:';
    const auditValue = document.createElement('span');
    auditValue.className = 'integrity-count-value';
    auditValue.textContent = String(auditFailures);
    auditRow.appendChild(auditLabel);
    auditRow.appendChild(auditValue);
    countsSection.appendChild(auditRow);
  }

  // Only add counts section if there are any counts to show
  if (projViolations > 0 || authMismatches > 0 || receiptFailures > 0 || auditFailures > 0) {
    container.appendChild(countsSection);
  }

  // Detected issues (boolean flags)
  const issuesSection = document.createElement('div');
  issuesSection.className = 'integrity-issues';

  const staleReceipt = data && data.stale_receipt_detected === true;
  const orphanedReceipt = data && data.orphaned_receipt_detected === true;
  const orphanedAudit = data && data.orphaned_audit_detected === true;

  if (staleReceipt || orphanedReceipt || orphanedAudit) {
    if (staleReceipt) {
      const staleRow = document.createElement('div');
      staleRow.className = 'integrity-issue-item';
      staleRow.textContent = 'Stale receipt detected';
      issuesSection.appendChild(staleRow);
    }
    if (orphanedReceipt) {
      const orphanRow = document.createElement('div');
      orphanRow.className = 'integrity-issue-item';
      orphanRow.textContent = 'Orphaned receipt detected';
      issuesSection.appendChild(orphanRow);
    }
    if (orphanedAudit) {
      const auditRow = document.createElement('div');
      auditRow.className = 'integrity-issue-item';
      auditRow.textContent = 'Orphaned audit event detected';
      issuesSection.appendChild(auditRow);
    }
    container.appendChild(issuesSection);
  }

  // Next action hint
  const nextAction = (data && data.next_integrity_action) || 'No integrity issues detected';
  const actionHint = document.createElement('div');
  actionHint.className = 'integrity-hint';
  actionHint.textContent = nextAction;
  container.appendChild(actionHint);

  // Advisory only note (always present for integrity)
  const advisoryNote = document.createElement('div');
  advisoryNote.className = 'integrity-advisory';
  advisoryNote.textContent = 'Integrity validation is advisory. Rig remains the authority.';
  container.appendChild(advisoryNote);

  return container;
}

// Register widget
if (typeof window !== 'undefined' && window.rigWidgets) {
  window.rigWidgets = window.rigWidgets || {};
  window.rigWidgets.IntegrityStatusCard = {
    render: renderIntegrityStatusCard
  };
}

// Export for module systems
if (typeof module !== 'undefined' && module.exports) {
  module.exports = { renderIntegrityStatusCard };
}
