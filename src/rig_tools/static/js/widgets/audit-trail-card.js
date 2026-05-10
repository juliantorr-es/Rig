import { RenderNode, createHtmlElement, setHtmlAttr } from '../core/render-graph.js';

/**
 * AuditTrailCardNode - Retained RenderNode for audit trail visualization.
 * 
 * DOCTRINE:
 * - Retained rendering (patching only)
 * - Projection-only data
 * - No authority decisions
 * - Safe fallbacks
 * - textContent only
 */
export class AuditTrailCardNode extends RenderNode {
  constructor(id, data, sequence = null) {
    super(id, sequence);
    this.data = data;
  }

  render(parent) {
    const container = createHtmlElement('div', { class: 'rig-card audit-trail-card' });
    
    // Title
    container.appendChild(createHtmlElement('div', { class: 'card-title' }, 'Audit Trail'));

    // Summary section
    const summary = createHtmlElement('div', { class: 'card-section' });
    
    // Lineage
    const lineage = createHtmlElement('div', { class: 'status-row' });
    lineage.appendChild(createHtmlElement('span', { class: 'status-label' }, 'Lineage:'));
    lineage.appendChild(createHtmlElement('span', { class: 'status-value status-mono', id: 'audit-lineage' }));
    summary.appendChild(lineage);

    // Completeness
    const completeness = createHtmlElement('div', { class: 'status-row' });
    completeness.appendChild(createHtmlElement('span', { class: 'status-label' }, 'Audit Completeness:'));
    completeness.appendChild(createHtmlElement('span', { class: 'status-value', id: 'audit-completeness' }));
    summary.appendChild(completeness);

    // Event counts
    const counts = createHtmlElement('div', { class: 'status-row' });
    counts.appendChild(createHtmlElement('span', { class: 'status-label' }, 'Authoritative:'));
    counts.appendChild(createHtmlElement('span', { class: 'status-value', id: 'audit-auth-count' }));
    counts.appendChild(document.createTextNode(' '));
    counts.appendChild(createHtmlElement('span', { class: 'status-label' }, 'Advisory Only:'));
    counts.appendChild(createHtmlElement('span', { class: 'status-value', id: 'audit-advisory-count' }));
    summary.appendChild(counts);

    // Last event
    const lastEvent = createHtmlElement('div', { class: 'status-row', id: 'audit-last-event-row' });
    lastEvent.appendChild(createHtmlElement('span', { class: 'status-label' }, 'Last Event:'));
    lastEvent.appendChild(createHtmlElement('span', { class: 'status-value status-mono', id: 'audit-last-event' }));
    summary.appendChild(lastEvent);

    container.appendChild(summary);

    // Dynamic sections (will be patched)
    container.appendChild(createHtmlElement('div', { id: 'audit-missing-section' }));
    container.appendChild(createHtmlElement('div', { id: 'audit-action-hint', class: 'card-section hint' }));
    container.appendChild(createHtmlElement('div', { id: 'audit-warning', class: 'card-section warning' }));

    parent.appendChild(container);
    this.patch(container);
    return container;
  }

  patch(element) {
    const data = this.data;

    // Lineage
    const lineageVal = `${data.schema_version || 'rig.workspace_audit.v1'} / ${data.source_schema_version || 'unknown'}`;
    setHtmlAttr(element.querySelector('#audit-lineage'), 'text', lineageVal);

    // Completeness
    const completenessText = data.audit_completeness || 'unknown';
    const completenessEl = element.querySelector('#audit-completeness');
    setHtmlAttr(completenessEl, 'text', completenessText);
    
    let severityClass = 'status-value';
    if (completenessText === 'complete') severityClass += ' status-success';
    else if (completenessText === 'not_proof' || completenessText === 'not_run') severityClass += ' status-warning';
    else if (completenessText === 'not_created') severityClass += ' status-idle';
    else severityClass += ' status-info';
    setHtmlAttr(completenessEl, 'class', severityClass);

    // Counts
    setHtmlAttr(element.querySelector('#audit-auth-count'), 'text', String(data.authoritative_events || 0));
    setHtmlAttr(element.querySelector('#audit-advisory-count'), 'text', String(data.advisory_only_events || 0));

    // Last event
    const lastEventRow = element.querySelector('#audit-last-event-row');
    if (data.last_authoritative_event_id) {
      setHtmlAttr(lastEventRow, 'style', { display: 'flex' });
      setHtmlAttr(element.querySelector('#audit-last-event'), 'text', data.last_authoritative_event_id);
    } else {
      setHtmlAttr(lastEventRow, 'style', { display: 'none' });
    }

    // Missing receipts (destructive patch for sub-list for now, but better than full card)
    const missing = data.missing_receipts || [];
    const missingSection = element.querySelector('#audit-missing-section');
    if (missing.length > 0) {
      missingSection.innerHTML = '';
      missingSection.className = 'card-section';
      missingSection.appendChild(createHtmlElement('div', { class: 'section-title' }, 'Missing Receipts:'));
      const list = createHtmlElement('ul', { class: 'list-compact' });
      missing.forEach(r => list.appendChild(createHtmlElement('li', {}, r)));
      missingSection.appendChild(list);
    } else {
      missingSection.innerHTML = '';
      missingSection.className = '';
    }

    // Action hint
    const hintEl = element.querySelector('#audit-action-hint');
    if (data.next_missing_audit_action) {
      setHtmlAttr(hintEl, 'style', { display: 'block' });
      setHtmlAttr(hintEl, 'text', data.next_missing_audit_action);
    } else {
      setHtmlAttr(hintEl, 'style', { display: 'none' });
    }

    // Warning
    const warningEl = element.querySelector('#audit-warning');
    if (data.advisory_only_warning) {
      setHtmlAttr(warningEl, 'style', { display: 'block' });
      setHtmlAttr(warningEl, 'text', data.advisory_only_warning);
    } else {
      setHtmlAttr(warningEl, 'style', { display: 'none' });
    }
  }

  getStateHash() {
    return JSON.stringify(this.data);
  }
}

export function renderAuditTrailCard(id, data, actions) {
  return new AuditTrailCardNode(id, data, actions?.sequence);
}

// Register widget
if (typeof window !== 'undefined' && window.rigWidgets) {
  window.rigWidgets = window.rigWidgets || {};
  window.rigWidgets.AuditTrailCard = {
    render: renderAuditTrailCard
  };
}
