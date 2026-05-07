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

export function renderProposalLifecycleConsole(_id, data) {
  const el = card(data.title || 'Proposal Lifecycle Console');
  el.className = 'widget proposal-lifecycle-console';

  const stage = (data.stage || 'unknown').toString();
  el.appendChild(badge(stage === 'unknown' ? 'Unknown' : stage.replace(/_/g, ' '), stage === 'apply_blocked' ? 'attention' : 'info'));

  const summary = document.createElement('p');
  summary.className = 'muted';
  summary.textContent = data.summary || '';
  el.appendChild(summary);

  const details = document.createElement('div');
  details.className = 'muted';
  details.textContent = [
    data.current_gate ? `gate: ${data.current_gate}` : null,
    data.workspace_path ? `workspace: ${data.workspace_path}` : null,
    data.next_safe_action ? `next: ${data.next_safe_action}` : null,
  ].filter(Boolean).join(' · ');
  el.appendChild(details);

  const states = document.createElement('div');
  states.className = 'proposal-lifecycle-states';
  const recommendation = document.createElement('div');
  recommendation.className = 'muted';
  recommendation.textContent = `recommendation: ${(data.recommendation_state && data.recommendation_state.status) || 'unknown'}`;
  states.appendChild(recommendation);
  const proposal = document.createElement('div');
  proposal.className = 'muted';
  proposal.textContent = `proposal: ${(data.proposal_state && data.proposal_state.status) || 'unknown'}`;
  states.appendChild(proposal);
  const validation = document.createElement('div');
  validation.className = 'muted';
  validation.textContent = `validation: ${(data.validation_state && data.validation_state.status) || 'unknown'} · ${(data.validation_state && data.validation_state.proof_status) || 'not_proof'}`;
  states.appendChild(validation);
  const progress = document.createElement('div');
  progress.className = 'muted';
  const transient = data.progress_state && data.progress_state.transient !== false;
  progress.textContent = `progress: ${transient ? 'transient' : 'persistent'} · ${data.auditability_state && data.auditability_state.progress_receipt_plan ? String(data.auditability_state.progress_receipt_plan).replace(/_/g, ' ') : 'advisory only'}`;
  states.appendChild(progress);
  el.appendChild(states);

  el.appendChild(renderList('Allowed', data.allowed_actions, 'No allowed actions listed.'));
  el.appendChild(renderList('Blocked', data.blocked_actions, 'No blocked actions listed.'));

  if (data.auditability_state) {
    const audit = document.createElement('div');
    audit.className = 'muted';
    audit.textContent = [
      data.auditability_state.progress_receipts ? `receipts: ${data.auditability_state.progress_receipts}` : null,
      data.auditability_state.receipt_candidate ? `receipt_candidate: ${data.auditability_state.receipt_candidate}` : null,
      data.auditability_state.evidence_refs ? `evidence_refs: ${data.auditability_state.evidence_refs}` : null,
    ].filter(Boolean).join(' · ');
    el.appendChild(audit);
  }

  if (Array.isArray(data.warnings) && data.warnings.length > 0) {
    const warn = document.createElement('div');
    warn.className = 'muted';
    warn.textContent = `warnings: ${data.warnings.join(' · ')}`;
    el.appendChild(warn);
  }

  return el;
}

