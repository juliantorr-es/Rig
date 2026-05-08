import { badge } from '../components/badges.js';
import { card } from '../components/cards.js';
import { listContainer } from '../components/lists.js';

function renderList(title, items, emptyLabel) {
  const section = document.createElement('section');
  const h3 = document.createElement('h3');
  h3.textContent = title;
  section.appendChild(h3);
  if (!Array.isArray(items) || items.length === 0) {
    const empty = document.createElement('p');
    empty.className = 'muted';
    empty.textContent = emptyLabel || 'None';
    section.appendChild(empty);
    return section;
  }
  const list = listContainer('proposal-lifecycle-list');
  items.forEach(item => {
    const row = document.createElement('div');
    row.className = 'proposal-lifecycle-item';
    const label = document.createElement('div');
    label.textContent = item.label || item.id || '';
    row.appendChild(label);
    if (item.reason) {
      const reason = document.createElement('div');
      reason.className = 'muted';
      reason.textContent = item.reason;
      row.appendChild(reason);
    } else if (item.description) {
      const description = document.createElement('div');
      description.className = 'muted';
      description.textContent = item.description;
      row.appendChild(description);
    }
    list.appendChild(row);
  });
  section.appendChild(list);
  return section;
}

function renderStateSection(title, state, emptyLabel = 'Unknown') {
  const section = document.createElement('section');
  const h3 = document.createElement('h3');
  h3.textContent = title;
  section.appendChild(h3);

  if (!state || typeof state !== 'object' || Object.keys(state).length === 0) {
    const empty = document.createElement('p');
    empty.className = 'muted';
    empty.textContent = emptyLabel;
    section.appendChild(empty);
    return section;
  }

  const statusBadge = badge(state.status || 'unknown', state.status === 'failed' ? 'attention' : (state.status === 'passed' || state.status === 'available' || state.status === 'review_ready' ? 'success' : 'info'));
  section.appendChild(statusBadge);

  const details = document.createElement('dl');
  details.className = 'proposal-lifecycle-state-details';

  const titleLabel = document.createElement('dt');
  titleLabel.textContent = 'Title';
  const titleValue = document.createElement('dd');
  titleValue.textContent = state.title || '';
  details.appendChild(titleLabel);
  details.appendChild(titleValue);

  const summaryLabel = document.createElement('dt');
  summaryLabel.textContent = 'Summary';
  const summaryValue = document.createElement('dd');
  summaryValue.textContent = state.summary || '';
  details.appendChild(summaryLabel);
  details.appendChild(summaryValue);

  // Type-specific fields
  if (state.source_surface) {
    const surfaceLabel = document.createElement('dt');
    surfaceLabel.textContent = 'Source Surface';
    const surfaceValue = document.createElement('dd');
    surfaceValue.textContent = state.source_surface;
    details.appendChild(surfaceLabel);
    details.appendChild(surfaceValue);
  }

  if (state.worktree_path) {
    const worktreeLabel = document.createElement('dt');
    worktreeLabel.textContent = 'Worktree Path';
    const worktreeValue = document.createElement('dd');
    worktreeValue.textContent = state.worktree_path;
    details.appendChild(worktreeLabel);
    details.appendChild(worktreeValue);
  }

  if (state.changed_files && Array.isArray(state.changed_files) && state.changed_files.length > 0) {
    const filesLabel = document.createElement('dt');
    filesLabel.textContent = 'Changed Files';
    const filesValue = document.createElement('dd');
    filesValue.textContent = state.changed_files.join(', ');
    details.appendChild(filesLabel);
    details.appendChild(filesValue);
  }

  if (state.command) {
    const commandLabel = document.createElement('dt');
    commandLabel.textContent = 'Command';
    const commandValue = document.createElement('dd');
    commandValue.textContent = state.command;
    details.appendChild(commandLabel);
    details.appendChild(commandValue);
  }

  if (state.passed_count !== undefined || state.failed_count !== undefined) {
    const countsLabel = document.createElement('dt');
    countsLabel.textContent = 'Counts';
    const countsValue = document.createElement('dd');
    const passed = state.passed_count !== undefined ? state.passed_count : 0;
    const failed = state.failed_count !== undefined ? state.failed_count : 0;
    countsValue.textContent = `${passed} passed, ${failed} failed`;
    details.appendChild(countsLabel);
    details.appendChild(countsValue);
  }

  if (state.last_updated || state.last_run_at) {
    const timeLabel = document.createElement('dt');
    timeLabel.textContent = state.last_run_at ? 'Last Run At' : 'Last Updated';
    const timeValue = document.createElement('dd');
    timeValue.textContent = state.last_run_at || state.last_updated || '';
    details.appendChild(timeLabel);
    details.appendChild(timeValue);
  }

  if (state.proof_status) {
    const proofLabel = document.createElement('dt');
    proofLabel.textContent = 'Proof Status';
    const proofValue = document.createElement('dd');
    proofValue.textContent = state.proof_status;
    details.appendChild(proofLabel);
    details.appendChild(proofValue);
  }

  if (state.files && Array.isArray(state.files) && state.files.length > 0) {
    const filesLabel = document.createElement('dt');
    filesLabel.textContent = 'Files';
    const filesValue = document.createElement('dd');
    filesValue.textContent = state.files.join(', ');
    details.appendChild(filesLabel);
    details.appendChild(filesValue);
  }

  if (state.next_action) {
    const nextActionLabel = document.createElement('dt');
    nextActionLabel.textContent = 'Next Action';
    const nextActionValue = document.createElement('dd');
    nextActionValue.textContent = state.next_action;
    details.appendChild(nextActionLabel);
    details.appendChild(nextActionValue);
  }

  section.appendChild(details);
  return section;
}

export function renderProposalLifecycleConsole(_id, data) {
  const el = card(data.title || 'Proposal Lifecycle Console');
  el.className = 'widget proposal-lifecycle-console';

  // Stage badge
  const stage = (data.stage || 'unknown').toString();
  const stageSeverity = stage === 'apply_blocked' ? 'attention' : (
    stage === 'validation_failed' ? 'danger' : (
      stage === 'review_ready' || stage === 'validation_passed' ? 'success' : 'info'
    )
  );
  el.appendChild(badge(stage === 'unknown' ? 'Unknown' : stage.replace(/_/g, ' '), stageSeverity));

  // Summary
  const summary = document.createElement('p');
  summary.className = 'muted';
  summary.textContent = data.summary || '';
  el.appendChild(summary);

  // Header details line: gate, workspace path, next safe action
  const headerDetails = document.createElement('div');
  headerDetails.className = 'proposal-lifecycle-header';
  const headerItems = [];
  if (data.current_gate) {
    headerItems.push(`gate: ${data.current_gate}`);
  }
  if (data.workspace_path) {
    headerItems.push(`workspace: ${data.workspace_path}`);
  }
  if (data.next_safe_action) {
    headerItems.push(`next: ${data.next_safe_action}`);
  }
  if (headerItems.length > 0) {
    headerDetails.textContent = headerItems.join(' \u00b7 ');
    headerDetails.className = 'muted';
    el.appendChild(headerDetails);
  }

  // Blocked apply note for Gate A
  const applyNote = document.createElement('div');
  applyNote.className = 'proposal-lifecycle-note muted';
  applyNote.textContent = 'Apply remains blocked under Dogfood Gate A.';
  el.appendChild(applyNote);

  // State sections
  const statesContainer = document.createElement('div');
  statesContainer.className = 'proposal-lifecycle-states';

  // Recommendation state
  statesContainer.appendChild(renderStateSection('Recommendation', data.recommendation_state, 'No recommendation available'));

  // Proposal state
  statesContainer.appendChild(renderStateSection('Proposal', data.proposal_state, 'No proposal available'));

  // Validation state
  statesContainer.appendChild(renderStateSection('Validation', data.validation_state, 'Validation not run'));

  el.appendChild(statesContainer);

  // Progress and auditability state summary
  const progressAuditContainer = document.createElement('div');
  progressAuditContainer.className = 'muted proposal-lifecycle-meta';

  const transient = data.progress_state && data.progress_state.transient !== false;
  const progressText = `progress: ${transient ? 'transient' : 'persistent'} \u00b7 ${data.auditability_state && data.auditability_state.progress_receipt_plan ? String(data.auditability_state.progress_receipt_plan).replace(/_/g, ' ') : 'advisory only'}`;
  progressAuditContainer.textContent = progressText;
  el.appendChild(progressAuditContainer);

  // Full auditability state details
  if (data.auditability_state) {
    const audit = document.createElement('div');
    audit.className = 'muted proposal-lifecycle-audit';
    const auditItems = [];
    if (data.auditability_state.progress_receipts) {
      auditItems.push(`receipts: ${data.auditability_state.progress_receipts}`);
    }
    if (data.auditability_state.receipt_candidate) {
      auditItems.push(`receipt_candidate: ${data.auditability_state.receipt_candidate}`);
    }
    if (data.auditability_state.evidence_refs) {
      auditItems.push(`evidence_refs: ${data.auditability_state.evidence_refs}`);
    }
    if (auditItems.length > 0) {
      audit.textContent = auditItems.join(' \u00b7 ');
      el.appendChild(audit);
    }
  }

  // Actions lists
  el.appendChild(renderList('Allowed Actions', data.allowed_actions, 'No allowed actions listed.'));
  el.appendChild(renderList('Blocked Actions', data.blocked_actions, 'No blocked actions listed.'));

  // Warnings
  if (Array.isArray(data.warnings) && data.warnings.length > 0) {
    const warn = document.createElement('div');
    warn.className = 'muted proposal-lifecycle-warnings';
    warn.textContent = `warnings: ${data.warnings.join(' \u00b7 ')}`;
    el.appendChild(warn);
  }

  return el;
}
