export function renderLogStream(_id, data, globalLogs, truncateText) {
  const el = document.createElement('div');
  el.className = 'rig-card log-stream-card';
  
  const title = document.createElement('div');
  title.className = 'card-title';
  title.textContent = data.title || 'Log Stream';
  el.appendChild(title);

  const streamDiv = document.createElement('div');
  streamDiv.className = 'log-stream-list';
  streamDiv.setAttribute('aria-live', 'polite');
  
  if (globalLogs && globalLogs.length > 0) {
    globalLogs.slice(-100).forEach(log => {
      const entry = document.createElement('div');
      entry.className = 'log-entry';
      
      // Parse [channel] content
      const match = log.match(/^\[(.*?)\] (.*)$/);
      if (match) {
        const [, channel, content] = match;
        const badge = document.createElement('span');
        badge.className = `log-badge badge-${channel.toLowerCase()}`;
        badge.textContent = channel;
        entry.appendChild(badge);
        
        const text = document.createElement('span');
        text.className = 'log-text';
        text.textContent = truncateText(content);
        entry.appendChild(text);
      } else {
        entry.textContent = truncateText(log);
      }
      
      streamDiv.appendChild(entry);
    });
  } else {
    const p = document.createElement('p');
    p.className = 'status-idle';
    p.style.fontSize = 'var(--fs-xs)';
    p.textContent = 'Monitoring runtime events...';
    streamDiv.appendChild(p);
  }
  
  el.appendChild(streamDiv);
  return el;
}
