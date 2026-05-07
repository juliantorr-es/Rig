export function renderBackendStatus(_id, data) {
  const el = document.createElement('div');
  el.style.display = 'flex';
  el.style.justifyContent = 'space-between';
  el.style.padding = '4px';
  const leftSpan = document.createElement('span');
  leftSpan.textContent = (data.title || '') + ': ' + (data.body || '');
  el.appendChild(leftSpan);
  const rightSpan = document.createElement('span');
  rightSpan.textContent = 'Rev: ' + (data.revision !== undefined ? String(data.revision) : '');
  el.appendChild(rightSpan);
  return el;
}
