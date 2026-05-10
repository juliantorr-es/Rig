import { actionButton } from '../components/buttons.js';

export function renderEmptyStateCard(id, data, actions, projection, sendIntent, showError) {
  const el = document.createElement('div');
  el.className = 'widget';
  const h2 = document.createElement('h2');
  h2.textContent = data.title || '';
  el.appendChild(h2);
  const p = document.createElement('p');
  p.textContent = data.body || '';
  el.appendChild(p);
  if (data.schema_version || data.projection_revision !== undefined) {
    const lineage = document.createElement('div');
    lineage.className = 'muted';
    lineage.textContent = [
      data.schema_version ? `schema: ${data.schema_version}` : null,
      data.projection_revision !== undefined ? `revision: ${data.projection_revision}` : null,
    ].filter(Boolean).join(' · ');
    el.appendChild(lineage);
  }
  const disabledReasons = [];
  (actions || []).forEach(actionId => {
    const intent = projection.intents[actionId];
    if (intent && !intent.enabled && intent.disabled_reason) disabledReasons.push(intent.disabled_reason);
  });
  if (disabledReasons.length > 0) {
    const reasonsEl = document.createElement('div');
    reasonsEl.className = 'empty-state-reasons';
    reasonsEl.textContent = disabledReasons.join(' ');
    el.appendChild(reasonsEl);
  }
  const actionsDiv = document.createElement('div');
  actionsDiv.className = 'actions';
  (actions || []).forEach(actionId => {
    const intent = projection.intents[actionId];
    if (!intent) return;
    actionsDiv.appendChild(actionButton(intent.label || actionId, actionId, intent, sendIntent));
  });
  el.appendChild(actionsDiv);
  if (id === 'workspace.empty') {
    const manualDiv = document.createElement('div');
    manualDiv.className = 'manual-repo-input';
    const label = document.createElement('label');
    label.textContent = 'Enter repository path:';
    manualDiv.appendChild(label);
    const input = document.createElement('input');
    input.type = 'text';
    input.id = 'manual-repo-path';
    input.placeholder = '/path/to/rig';
    manualDiv.appendChild(input);
    const manualBtn = document.createElement('button');
    manualBtn.textContent = 'Open Repository';
    manualBtn.onclick = () => {
      const path = input.value.trim();
      if (!path) {
        showError('Enter a repository path first.');
        return;
      }
      if (!projection.intents['intent.open_workspace']) {
        showError('Repository selection intent is unavailable.');
        return;
      }
      sendIntent('intent.open_workspace', { workspace_path: path, source: 'manual_path_input' });
    };
    manualDiv.appendChild(manualBtn);
    const hint = document.createElement('p');
    hint.className = 'empty-state-reasons';
    hint.textContent = 'Manual path input is available when native file dialogs are unavailable.';
    manualDiv.appendChild(hint);
    el.appendChild(manualDiv);
  }
  return el;
}
