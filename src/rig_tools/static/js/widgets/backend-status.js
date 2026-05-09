export function renderBackendStatus(_id, data) {
  const el = document.createElement('div');
  el.style.display = 'flex';
  el.style.flexDirection = 'column';
  el.style.justifyContent = 'space-between';
  el.style.padding = '4px';
  const leftSpan = document.createElement('span');
  leftSpan.textContent = (data.title || '') + ': ' + (data.body || '');
  el.appendChild(leftSpan);
  const rightSpan = document.createElement('span');
  rightSpan.textContent = 'Rev: ' + (
    data.revision !== undefined
      ? String(data.revision)
      : data.projection_revision !== undefined
        ? String(data.projection_revision)
        : ''
  );
  el.appendChild(rightSpan);
  if (data.schema_version || data.projection_revision !== undefined) {
    const lineage = document.createElement('div');
    lineage.style.width = '100%';
    lineage.style.fontSize = '0.75rem';
    lineage.style.opacity = '0.8';
    lineage.textContent = [
      data.schema_version ? `schema: ${data.schema_version}` : null,
      data.projection_revision !== undefined ? `projection: ${data.projection_revision}` : null,
    ].filter(Boolean).join(' · ');
    el.appendChild(lineage);
  }
  return el;
}
