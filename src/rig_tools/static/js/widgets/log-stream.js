export function renderLogStream(_id, data, globalLogs, truncateText) {
  const el = document.createElement('div');
  el.className = 'widget';
  const h2 = document.createElement('h2');
  h2.textContent = data.title || '';
  el.appendChild(h2);
  const streamDiv = document.createElement('div');
  streamDiv.className = 'log-stream';
  streamDiv.setAttribute('aria-live', 'polite');
  if (globalLogs.length > 0) {
    globalLogs.slice(-100).forEach(log => {
      const div = document.createElement('div');
      div.textContent = truncateText(log);
      streamDiv.appendChild(div);
    });
  } else {
    const p = document.createElement('p');
    p.className = 'muted';
    p.textContent = 'No recent logs.';
    streamDiv.appendChild(p);
  }
  el.appendChild(streamDiv);
  return el;
}
