import { badge } from '../components/badges.js';

export function renderWorkspaceHeader(_id, data) {
  const el = document.createElement('div');
  el.className = 'widget';
  const h2 = document.createElement('h2');
  h2.textContent = data.title || 'Workspace';
  el.appendChild(h2);
  el.appendChild(badge(data.authority_label || 'Workspace control plane', data.authority_label ? 'info' : 'idle'));
  if (data.schema_version || data.projection_revision !== undefined) {
    const lineage = document.createElement('div');
    lineage.className = 'muted';
    lineage.textContent = [
      data.schema_version ? `schema: ${data.schema_version}` : null,
      data.projection_revision !== undefined ? `revision: ${data.projection_revision}` : null,
    ].filter(Boolean).join(' · ');
    el.appendChild(lineage);
  }
  const details = document.createElement('div');
  details.className = 'muted';
  details.textContent = [
    data.repo_root ? `repo: ${data.repo_root}` : null,
    data.branch ? `branch: ${data.branch}` : null,
    data.head ? `HEAD: ${data.head}` : null,
    data.workspace_status ? `status: ${data.workspace_status}` : null,
  ].filter(Boolean).join(' · ');
  el.appendChild(details);
  return el;
}
