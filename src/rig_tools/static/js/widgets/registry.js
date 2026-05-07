import { renderEmptyStateCard } from './empty-state-card.js';
import { renderValidatorStack } from './validator-stack.js';
import { renderReceiptList } from './receipt-list.js';
import { renderBackendStatus } from './backend-status.js';
import { renderWorkspaceHeader } from './workspace-header.js';
import { renderWorkspaceGitState } from './workspace-git-state.js';
import { renderWorkspaceLaneSummary } from './workspace-lane-summary.js';
import { renderLogStream } from './log-stream.js';
import { renderCommandProgressCard } from './command-progress-card.js';

export function buildWidgetRegistry(context) {
  const registry = {
    AppTitle: (id, data) => {
      const el = document.createElement('div');
      el.style.display = 'flex';
      el.style.justifyContent = 'space-between';
      const left = document.createElement('span');
      left.textContent = data.title || '';
      const right = document.createElement('span');
      right.textContent = data.subtitle || '';
      el.appendChild(left);
      el.appendChild(right);
      return el;
    },
    GateBadge: (id, data) => {
      const el = document.createElement('div');
      el.className = `badge severity-${data.severity || 'info'}`;
      el.textContent = data.label || '';
      return el;
    },
    MetricStack: (id, data) => {
      const el = document.createElement('div');
      el.className = 'widget';
      const h2 = document.createElement('h2');
      h2.textContent = data.title || '';
      el.appendChild(h2);
      (data.items || []).forEach(item => {
        const row = document.createElement('div');
        row.className = 'metric-item';
        const label = document.createElement('span');
        label.className = 'label';
        label.textContent = item.label || '';
        const value = document.createElement('span');
        value.className = 'value';
        value.textContent = String(item.value ?? '');
        row.appendChild(label);
        row.appendChild(value);
        el.appendChild(row);
      });
      return el;
    },
    EmptyStateCard: (id, data, actions) => renderEmptyStateCard(id, data, actions, context.projection(), context.sendIntent, context.showError),
    EvidenceCard: (id, data) => {
      const el = document.createElement('div');
      el.className = 'widget';
      const h2 = document.createElement('h2');
      h2.textContent = data.title || '';
      el.appendChild(h2);
      if (data.state) {
        const badge = document.createElement('div');
        badge.className = `badge severity-${data.state.severity || 'info'}`;
        badge.textContent = data.state.label || '';
        el.appendChild(badge);
      }
      const p = document.createElement('p');
      p.className = 'muted';
      p.textContent = data.body || '';
      el.appendChild(p);
      return el;
    },
    ValidatorStack: (id, data, actions) => renderValidatorStack(id, data, actions, context.projection(), context.sendIntent),
    ReceiptList: (id, data) => renderReceiptList(id, data),
    BackendStatus: (id, data) => renderBackendStatus(id, data),
    WorkspaceHeader: (id, data) => renderWorkspaceHeader(id, data),
    WorkspaceGitState: (id, data) => renderWorkspaceGitState(id, data),
    WorkspaceLaneSummary: (id, data) => renderWorkspaceLaneSummary(id, data),
    LogStream: (id, data) => renderLogStream(id, data, context.globalLogs(), context.truncateText),
    CommandProgressCard: (id, data) => renderCommandProgressCard(id, data),
  };

  registry._fallback = (widget) => {
    const div = document.createElement('div');
    div.className = 'widget';
    div.textContent = 'Unknown widget: ' + (widget.type || 'unknown');
    return div;
  };

  return registry;
}
