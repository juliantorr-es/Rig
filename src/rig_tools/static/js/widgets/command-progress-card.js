import { badge } from '../components/badges.js';
import { card } from '../components/cards.js';

export function renderCommandProgressCard(_id, data) {
  const el = card(data.kind || 'Progress');
  el.className = 'widget command-progress-card';
  el.appendChild(badge(data.status || 'unknown', data.status === 'operation.completed' ? 'success' : 'info'));
  const message = document.createElement('p');
  message.className = 'muted';
  message.textContent = data.message || '';
  el.appendChild(message);

  const details = document.createElement('div');
  details.className = 'muted';
  details.textContent = [
    data.operation_id ? `operation: ${data.operation_id}` : null,
    data.timestamp ? `at: ${data.timestamp}` : null,
  ].filter(Boolean).join(' · ');
  el.appendChild(details);

  if (data.payload && typeof data.payload === 'object') {
    const pre = document.createElement('pre');
    pre.className = 'command-progress-payload';
    pre.textContent = JSON.stringify(data.payload, null, 2);
    el.appendChild(pre);
  }
  return el;
}

