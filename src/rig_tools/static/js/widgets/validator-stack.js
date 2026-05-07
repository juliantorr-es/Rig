import { badge } from '../components/badges.js';

export function renderValidatorStack(_id, data, actions, projection, sendIntent) {
  const el = document.createElement('div');
  el.className = 'widget';
  const headerDiv = document.createElement('div');
  headerDiv.style.display = 'flex';
  headerDiv.style.justifyContent = 'space-between';
  headerDiv.style.alignItems = 'baseline';
  const h2 = document.createElement('h2');
  h2.textContent = data.title || '';
  headerDiv.appendChild(h2);
  headerDiv.appendChild(badge(data.state ? (data.state.label || '') : '', data.state ? data.state.severity || 'info' : 'info'));
  el.appendChild(headerDiv);
  if (data.run_in_progress) {
    const runningDiv = document.createElement('div');
    runningDiv.className = 'validator-running';
    runningDiv.style.color = 'var(--attention)';
    runningDiv.style.fontSize = '0.85rem';
    runningDiv.style.marginBottom = '8px';
    const spinner = document.createElement('span');
    spinner.textContent = '● ';
    const runningText = document.createElement('span');
    runningText.textContent = data.running_validator_id ? `Running: ${data.running_validator_id}` : 'Validating...';
    runningDiv.appendChild(spinner);
    runningDiv.appendChild(runningText);
    el.appendChild(runningDiv);
  }
  if (data.summary) {
    const summaryDiv = document.createElement('div');
    summaryDiv.className = 'muted';
    summaryDiv.style.marginBottom = '8px';
    summaryDiv.textContent = data.summary;
    el.appendChild(summaryDiv);
  }
  const listDiv = document.createElement('div');
  listDiv.className = 'validator-list';
  (data.items || []).forEach(item => {
    const itemDiv = document.createElement('div');
    itemDiv.className = `validator-item state-${item.state || 'unknown'}`;
    const itemHeader = document.createElement('div');
    itemHeader.style.display = 'flex';
    itemHeader.style.justifyContent = 'space-between';
    const symbol = item.state === 'passed' ? '✓ ' :
      item.state === 'failed' ? '✗ ' :
      item.state === 'running' ? '→ ' : '○ ';
    const labelSpan = document.createElement('span');
    labelSpan.textContent = symbol + (item.label || '');
    const stateSpan = document.createElement('span');
    stateSpan.className = 'muted';
    stateSpan.textContent = item.state || '';
    itemHeader.appendChild(labelSpan);
    itemHeader.appendChild(stateSpan);
    itemDiv.appendChild(itemHeader);
    if (item.detail) {
      const pre = document.createElement('pre');
      pre.className = 'validator-detail';
      pre.textContent = item.detail;
      itemDiv.appendChild(pre);
    }
    listDiv.appendChild(itemDiv);
  });
  el.appendChild(listDiv);
  const actionsDiv = document.createElement('div');
  actionsDiv.className = 'actions';
  actionsDiv.style.marginTop = '12px';
  (actions || []).forEach(actionId => {
    const intent = projection.intents[actionId];
    if (!intent) return;
    const btn = document.createElement('button');
    btn.onclick = () => sendIntent(actionId);
    if (!intent.enabled || data.run_in_progress) btn.disabled = true;
    btn.textContent = data.run_in_progress && intent.kind === 'rig.intent.run_validators' ? 'Running...' : (intent.label || actionId);
    actionsDiv.appendChild(btn);
  });
  el.appendChild(actionsDiv);
  return el;
}
