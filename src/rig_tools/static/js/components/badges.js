export function badge(text, severity = 'idle') {
  const div = document.createElement('div');
  div.className = `badge severity-${severity}`;
  div.textContent = text || '';
  return div;
}
