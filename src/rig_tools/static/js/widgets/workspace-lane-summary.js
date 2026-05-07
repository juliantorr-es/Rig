import { badge } from '../components/badges.js';

export function renderWorkspaceLaneSummary(_id, data) {
  const el = document.createElement('div');
  el.className = 'widget';
  const h2 = document.createElement('h2');
  h2.textContent = 'Workspace Lane Summary';
  el.appendChild(h2);
  el.appendChild(badge(data.status || 'unknown', data.status === 'not_connected' ? 'idle' : 'info'));
  const p = document.createElement('p');
  p.className = 'muted';
  p.textContent = data.message || '';
  el.appendChild(p);
  const summary = document.createElement('div');
  summary.className = 'muted';
  summary.textContent = [
    typeof data.workspace_records === 'number' ? `workspace records: ${data.workspace_records}` : null,
    typeof data.lane_count === 'number' ? `lanes: ${data.lane_count}` : null,
    typeof data.review_ready_lanes === 'number' ? `review-ready: ${data.review_ready_lanes}` : null,
    data.next_action ? `next: ${data.next_action}` : null,
  ].filter(Boolean).join(' · ');
  el.appendChild(summary);
  return el;
}
