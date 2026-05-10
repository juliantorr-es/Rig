import { RenderNode, createHtmlElement, setHtmlAttr } from '../core/render-graph.js';

/**
 * ReplayTimelineCardNode - Retained RenderNode for replay timeline visualization.
 * 
 * DOCTRINE:
 * - Retained rendering (patching only)
 * - Projection-only data
 * - Dumb rendering (no authority)
 * - Deterministic output
 */
export class ReplayTimelineCardNode extends RenderNode {
  constructor(id, data, sequence = null) {
    super(id, sequence);
    this.data = data;
  }

  render(parent) {
    const container = createHtmlElement('div', { class: 'rig-card replay-timeline-card' });

    // Title section
    container.appendChild(createHtmlElement('div', { class: 'card-title' }, 'Replay Timeline'));

    // Header: Replay ID and Workspace ID
    const headerRow = createHtmlElement('div', { class: 'replay-header-row' });
    headerRow.appendChild(createHtmlElement('span', { class: 'replay-header-label' }, 'Replay:'));
    headerRow.appendChild(createHtmlElement('span', { class: 'replay-header-value replay-mono', id: 'replay-id' }));
    headerRow.appendChild(createHtmlElement('span', { id: 'workspace-id-section' }));
    container.appendChild(headerRow);

    // Lineage section
    const lineageSection = createHtmlElement('div', { class: 'card-section replay-lineage-section' });
    lineageSection.appendChild(this._createMetaRow('Replay Schema:', 'schema-version'));
    lineageSection.appendChild(this._createMetaRow('Source Schema:', 'source-schema-version'));
    lineageSection.appendChild(this._createMetaRow('Source Event:', 'source-event-id'));
    lineageSection.appendChild(this._createMetaRow('Source Kind:', 'source-event-kind'));
    container.appendChild(lineageSection);

    // Frame info
    const frameInfoRow = createHtmlElement('div', { class: 'replay-frame-info' });
    frameInfoRow.appendChild(createHtmlElement('span', { class: 'replay-frame-label' }, 'Frame:'));
    frameInfoRow.appendChild(createHtmlElement('span', { class: 'replay-frame-value', id: 'frame-info' }));
    container.appendChild(frameInfoRow);

    // Status section
    const statusSection = createHtmlElement('div', { class: 'card-section replay-status-section' });
    const statusRow = createHtmlElement('div', { class: 'replay-status-row' });
    statusRow.appendChild(createHtmlElement('span', { class: 'replay-status-label' }, 'Current Status:'));
    statusRow.appendChild(createHtmlElement('span', { id: 'current-status-badge' }));
    statusSection.appendChild(statusRow);
    container.appendChild(statusSection);

    // Terminal/State sections
    container.appendChild(createHtmlElement('div', { id: 'terminal-section', class: 'card-section replay-terminal-section' }));
    
    const stateSection = createHtmlElement('div', { class: 'card-section replay-state-section' });
    const stateRow = createHtmlElement('div', { class: 'replay-state-row' });
    stateRow.appendChild(createHtmlElement('span', { class: 'replay-state-label' }, 'Replay State:'));
    stateRow.appendChild(createHtmlElement('span', { id: 'replay-state-badge' }));
    stateSection.appendChild(stateRow);
    container.appendChild(stateSection);

    // Continuity
    const continuitySection = createHtmlElement('div', { class: 'card-section replay-continuity-section' });
    continuitySection.appendChild(this._createMetaRow('Frame Hash:', 'frame-hash'));
    continuitySection.appendChild(this._createMetaRow('Previous Hash:', 'prev-hash'));
    continuitySection.appendChild(this._createMetaRow('Evidence Mode:', 'evidence-mode'));
    container.appendChild(continuitySection);

    // Dynamic sections (patched)
    container.appendChild(createHtmlElement('div', { id: 'chain-section', class: 'card-section replay-chain-section' }));
    container.appendChild(createHtmlElement('div', { id: 'history-section', class: 'card-section replay-history-section' }));
    container.appendChild(createHtmlElement('div', { id: 'evidence-section', class: 'card-section replay-evidence-section' }));
    container.appendChild(createHtmlElement('div', { id: 'conflicts-section', class: 'card-section replay-conflicts-section' }));
    container.appendChild(createHtmlElement('div', { id: 'findings-section', class: 'card-section replay-findings-section' }));
    container.appendChild(createHtmlElement('div', { id: 'flags-section', class: 'card-section replay-flags-section' }));
    container.appendChild(createHtmlElement('div', { id: 'completeness-section', class: 'card-section replay-completeness-section' }));

    // Advisory note
    container.appendChild(createHtmlElement('div', { class: 'replay-advisory-note' }, 'Replay findings are advisory. Rig remains the final authority.'));

    parent.appendChild(container);
    this.patch(container);
    return container;
  }

  patch(element) {
    const data = this.data;

    // Header
    setHtmlAttr(element.querySelector('#replay-id'), 'text', data.replay_id || 'unknown');
    const wsSection = element.querySelector('#workspace-id-section');
    if (data.workspace_id) {
      wsSection.innerHTML = '';
      wsSection.appendChild(createHtmlElement('span', { class: 'replay-separator' }, '|'));
      wsSection.appendChild(createHtmlElement('span', { class: 'replay-header-label' }, ' Workspace:'));
      wsSection.appendChild(createHtmlElement('span', { class: 'replay-header-value replay-mono' }, data.workspace_id));
    } else {
      wsSection.innerHTML = '';
    }

    // Lineage
    setHtmlAttr(element.querySelector('#schema-version'), 'text', data.schema_version || 'rig.replay.v1');
    setHtmlAttr(element.querySelector('#source-schema-version'), 'text', data.source_schema_version || 'unknown');
    setHtmlAttr(element.querySelector('#source-event-id'), 'text', data.source_event_id || 'unknown');
    setHtmlAttr(element.querySelector('#source-event-kind'), 'text', data.source_event_kind || 'unknown');

    // Frame
    const frameIndex = data.frame_index ?? -1;
    const totalFrames = data.total_frames || 0;
    setHtmlAttr(element.querySelector('#frame-info'), 'text', totalFrames > 0 ? `${frameIndex + 1}/${totalFrames}` : '0/0');

    // Status
    const currentStatus = data.workspace_status || 'unknown';
    const statusBadge = element.querySelector('#current-status-badge');
    setHtmlAttr(statusBadge, 'text', currentStatus);
    setHtmlAttr(statusBadge, 'class', 'replay-status-badge replay-status-current');

    // Terminal
    const terminalSection = element.querySelector('#terminal-section');
    if (data.is_terminal && data.terminal_reason) {
      setHtmlAttr(terminalSection, 'style', { display: 'block' });
      terminalSection.innerHTML = '';
      terminalSection.appendChild(createHtmlElement('span', { class: 'replay-terminal-label' }, 'Terminal:'));
      terminalSection.appendChild(createHtmlElement('span', { class: 'replay-terminal-value' }, data.terminal_reason));
    } else {
      setHtmlAttr(terminalSection, 'style', { display: 'none' });
    }

    // Replay State
    const replayState = data.state || 'unknown';
    const stateBadge = element.querySelector('#replay-state-badge');
    setHtmlAttr(stateBadge, 'text', replayState);
    setHtmlAttr(stateBadge, 'class', 'replay-status-badge replay-state-badge');

    // Continuity
    setHtmlAttr(element.querySelector('#frame-hash'), 'text', data.frame_hash || 'unknown');
    setHtmlAttr(element.querySelector('#prev-hash'), 'text', data.previous_frame_hash || 'unknown');
    setHtmlAttr(element.querySelector('#evidence-mode'), 'text', data.authoritative_evidence_available ? 'authoritative' : 'advisory');

    // Chain section
    this._patchChainSection(element.querySelector('#chain-section'), data);
    
    // History
    this._patchHistorySection(element.querySelector('#history-section'), data);

    // Evidence
    this._patchEvidenceSection(element.querySelector('#evidence-section'), data);

    // Conflicts
    this._patchConflictsSection(element.querySelector('#conflicts-section'), data);

    // Findings
    this._patchFindingsSection(element.querySelector('#findings-section'), data);

    // Flags
    this._patchFlagsSection(element.querySelector('#flags-section'), data);

    // Completeness
    const compSection = element.querySelector('#completeness-section');
    if (totalFrames > 0) {
      setHtmlAttr(compSection, 'style', { display: 'block' });
      compSection.innerHTML = '';
      compSection.appendChild(createHtmlElement('span', { class: 'replay-completeness-label' }, 'Timeline:'));
      compSection.appendChild(createHtmlElement('span', { class: 'replay-completeness-value' }, frameIndex >= totalFrames - 1 ? 'Complete' : 'Partial'));
    } else {
      setHtmlAttr(compSection, 'style', { display: 'none' });
    }
  }

  _createMetaRow(label, id) {
    const row = createHtmlElement('div', { class: 'replay-meta-row' });
    row.appendChild(createHtmlElement('span', { class: 'replay-meta-label' }, label));
    row.appendChild(createHtmlElement('span', { class: 'replay-meta-value', id: id }));
    return row;
  }

  _patchChainSection(el, data) {
    const receipts = data.receipt_chain || [];
    const audits = data.audit_chain || [];
    if (receipts.length > 0 || audits.length > 0) {
      setHtmlAttr(el, 'style', { display: 'block' });
      el.innerHTML = '';
      el.appendChild(createHtmlElement('div', { class: 'replay-chain-title' }, 'Chain Continuity'));
      el.appendChild(this._createCountRow('Receipt Chain:', receipts.length));
      el.appendChild(this._createCountRow('Audit Chain:', audits.length));
    } else {
      setHtmlAttr(el, 'style', { display: 'none' });
    }
  }

  _createCountRow(label, count) {
    const row = createHtmlElement('div', { class: 'replay-chain-row' });
    row.appendChild(createHtmlElement('span', { class: 'replay-chain-label' }, label));
    row.appendChild(createHtmlElement('span', { class: 'replay-chain-count' }, String(count)));
    return row;
  }

  _patchHistorySection(el, data) {
    const history = data.status_history || [];
    if (history.length > 1) {
      setHtmlAttr(el, 'style', { display: 'block' });
      el.innerHTML = '';
      el.appendChild(createHtmlElement('div', { class: 'replay-history-title' }, 'Status Transitions'));
      for (let i = 1; i < history.length; i++) {
        el.appendChild(this._renderTransition(history[i-1].status, history[i].status, history[i].at));
      }
    } else {
      setHtmlAttr(el, 'style', { display: 'none' });
    }
  }

  _renderTransition(from, to, at) {
    const item = createHtmlElement('div', { class: 'replay-transition-item' });
    item.appendChild(createHtmlElement('span', { class: 'replay-transition-from' }, from || 'unknown'));
    item.appendChild(createHtmlElement('span', { class: 'replay-transition-arrow' }, '→'));
    item.appendChild(createHtmlElement('span', { class: 'replay-transition-to' }, to || 'unknown'));
    item.appendChild(createHtmlElement('span', { class: 'replay-transition-time' }, this._formatTs(at)));
    return item;
  }

  _patchEvidenceSection(el, data) {
    setHtmlAttr(el, 'style', { display: 'block' });
    el.innerHTML = '';
    el.appendChild(createHtmlElement('div', { class: 'replay-evidence-title' }, 'Evidence Available'));
    el.appendChild(this._createEvidenceRow('Authoritative:', data.authoritative_evidence_available));
    el.appendChild(this._createEvidenceRow('Advisory Only:', data.advisory_only_evidence_present));
  }

  _createEvidenceRow(label, available) {
    const row = createHtmlElement('div', { class: 'replay-evidence-row' });
    row.appendChild(createHtmlElement('span', { class: 'replay-evidence-label' }, label));
    row.appendChild(createHtmlElement('span', { class: 'replay-evidence-value' }, available ? 'Yes' : 'No'));
    return row;
  }

  _patchConflictsSection(el, data) {
    const count = data.conflict_count || 0;
    const types = data.conflict_types || {};
    if (count > 0 || Object.keys(types).length > 0) {
      setHtmlAttr(el, 'style', { display: 'block' });
      el.innerHTML = '';
      el.appendChild(createHtmlElement('div', { class: 'replay-conflicts-title' }, `Conflicts (${count})`));
      for (const [type, c] of Object.entries(types)) {
        const item = createHtmlElement('div', { class: 'replay-conflict-item' });
        item.appendChild(createHtmlElement('span', { class: 'replay-conflict-label' }, type.replace(/_/g, ' ')));
        item.appendChild(createHtmlElement('span', { class: 'replay-separator' }, ':'));
        item.appendChild(createHtmlElement('span', { class: 'replay-conflict-value' }, String(c)));
        el.appendChild(item);
      }
    } else {
      setHtmlAttr(el, 'style', { display: 'none' });
    }
  }

  _patchFindingsSection(el, data) {
    const count = data.finding_count || 0;
    const severityMap = data.findings_by_severity || {};
    if (count > 0 || Object.keys(severityMap).length > 0) {
      setHtmlAttr(el, 'style', { display: 'block' });
      el.innerHTML = '';
      el.appendChild(createHtmlElement('div', { class: 'replay-findings-title' }, `Findings (${count})`));
      ['critical', 'error', 'warning', 'info'].forEach(sev => {
        const c = severityMap[sev] || 0;
        if (c > 0 || data.type === 'ReplaySummary') {
          const item = createHtmlElement('div', { class: 'replay-finding-item replay-finding-severity-' + sev });
          item.appendChild(createHtmlElement('span', { class: 'replay-finding-label' }, sev));
          item.appendChild(createHtmlElement('span', { class: 'replay-separator' }, ':'));
          item.appendChild(createHtmlElement('span', { class: 'replay-finding-value' }, String(c)));
          el.appendChild(item);
        }
      });
    } else {
      setHtmlAttr(el, 'style', { display: 'none' });
    }
  }

  _patchFlagsSection(el, data) {
    const flags = [
      { key: 'has_impossible_transitions', label: 'Impossible Transitions' },
      { key: 'has_missing_receipts', label: 'Missing Receipts' },
      { key: 'has_missing_audit_events', label: 'Missing Audit Events' },
      { key: 'has_stale_references', label: 'Stale References' },
      { key: 'has_orphaned_events', label: 'Orphaned Events' },
      { key: 'has_contradictions', label: 'Contradictions' },
    ];
    const active = flags.filter(f => data[f.key]);
    if (active.length > 0 || data.type === 'ReplaySummary') {
      setHtmlAttr(el, 'style', { display: 'block' });
      el.innerHTML = '';
      el.appendChild(createHtmlElement('div', { class: 'replay-flags-title' }, 'Integrity Flags'));
      flags.forEach(f => {
        if (data[f.key] || data.type === 'ReplaySummary') {
          el.appendChild(createHtmlElement('div', { 
            class: 'replay-flag-item ' + (data[f.key] ? 'replay-flag-active' : 'replay-flag-inactive') 
          }, f.label));
        }
      });
    } else {
      setHtmlAttr(el, 'style', { display: 'none' });
    }
  }

  _formatTs(ts) {
    if (!ts) return '';
    return String(ts).replace('T', ' ').replace('Z', '').split('.')[0];
  }

  getStateHash() {
    return JSON.stringify(this.data);
  }
}

export function renderReplayTimelineCard(id, data, actions) {
  return new ReplayTimelineCardNode(id, data, actions?.sequence);
}

// Register widget
if (typeof window !== 'undefined' && window.rigWidgets) {
  window.rigWidgets = window.rigWidgets || {};
  window.rigWidgets.ReplayTimelineCard = {
    render: renderReplayTimelineCard
  };
}
