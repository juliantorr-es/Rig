import { badge } from '../components/badges.js';

export function renderWorkspaceGitState(_id, data) {
  const el = document.createElement('div');
  el.className = 'widget';
  const h2 = document.createElement('h2');
  h2.textContent = 'Workspace Git State';
  el.appendChild(h2);
  el.appendChild(badge(data.safe_to_commit ? 'safe to commit' : 'not ready', data.safe_to_commit ? 'success' : 'attention'));
  const details = document.createElement('div');
  details.className = 'muted';
  details.textContent = [
    data.branch ? `branch: ${data.branch}` : null,
    data.head ? `HEAD: ${data.head}` : null,
    typeof data.dirty === 'boolean' ? `dirty: ${data.dirty}` : null,
    typeof data.dirty_files_count === 'number' ? `dirty files: ${data.dirty_files_count}` : null,
    data.reason ? `reason: ${data.reason}` : null,
  ].filter(Boolean).join(' · ');
  el.appendChild(details);
  return el;
}
