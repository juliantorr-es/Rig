import { badge } from '../components/badges.js';

export function renderWorkspaceLaneSummary(_id, data) {
  const el = document.createElement('div');
  el.className = 'widget';
  const h2 = document.createElement('h2');
  h2.textContent = 'Workspace Lane Summary';
  el.appendChild(h2);
  el.appendChild(badge(data.status || 'unknown', data.status === 'not_connected' ? 'idle' : 'info'));
  if (data.schema_version || data.projection_revision !== undefined) {
    const lineage = document.createElement('div');
    lineage.className = 'muted';
    lineage.textContent = [
      data.schema_version ? `schema: ${data.schema_version}` : null,
      data.projection_revision !== undefined ? `revision: ${data.projection_revision}` : null,
    ].filter(Boolean).join(' · ');
    el.appendChild(lineage);
  }
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
