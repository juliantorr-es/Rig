export function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

export function textOrEmpty(value) {
  return value === undefined || value === null ? '' : String(value);
}
