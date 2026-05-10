import { badge } from '../components/badges.js';
import { card } from '../components/cards.js';

export function renderCommandProgressCard(_id, data) {
  const el = card(data.command || data.phase || 'Progress');
  el.className = 'widget command-progress-card';
  if (data.schema_version || data.projection_revision !== undefined) {
    const lineage = document.createElement('div');
    lineage.className = 'muted';
    lineage.textContent = [
      data.schema_version ? `schema: ${data.schema_version}` : null,
      data.projection_revision !== undefined ? `revision: ${data.projection_revision}` : null,
    ].filter(Boolean).join(' · ');
    el.appendChild(lineage);
  }
  const envelope = document.createElement('div');
  envelope.className = 'muted';
  envelope.textContent = [
    data.operation_id ? `operation: ${data.operation_id}` : null,
    data.timestamp ? `at: ${data.timestamp}` : null,
    typeof data.sequence === 'number' ? `seq: ${data.sequence}` : null,
  ].filter(Boolean).join(' · ');
  if (envelope.textContent) {
    el.appendChild(envelope);
  }
  const state = (data.status || 'unknown').toLowerCase();
  const severity = state === 'completed' ? 'success' : state === 'failed' ? 'danger' : state === 'blocked' ? 'attention' : 'info';
  el.appendChild(badge(data.status || 'unknown', severity));
  const heading = document.createElement('div');
  heading.className = 'muted';
  heading.textContent = [
    data.command ? `command: ${data.command}` : null,
    data.phase ? `phase: ${data.phase}` : null,
    data.level ? `level: ${data.level}` : null,
  ].filter(Boolean).join(' · ');
  el.appendChild(heading);
  const message = document.createElement('p');
  message.className = 'muted';
  message.textContent = data.message || '';
  el.appendChild(message);

  const history = Array.isArray(data.events) ? data.events : [];
  if (history.length > 0) {
    const historyList = document.createElement('div');
    historyList.className = 'command-progress-history';
    history.slice(-4).forEach(event => {
      const row = document.createElement('div');
      row.className = 'muted';
      row.textContent = [
        event.phase || event.status || 'progress',
        event.message || '',
      ].filter(Boolean).join(' · ');
      historyList.appendChild(row);
    });
    el.appendChild(historyList);
  }

  if (data.payload && typeof data.payload === 'object') {
    const pre = document.createElement('pre');
    pre.className = 'command-progress-payload';
    pre.textContent = JSON.stringify(data.payload, null, 2);
    el.appendChild(pre);
  }
  return el;
}
