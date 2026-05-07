export function card(title, body) {
  const el = document.createElement('div');
  el.className = 'widget';
  const h2 = document.createElement('h2');
  h2.textContent = title || '';
  el.appendChild(h2);
  if (body) {
    const p = document.createElement('p');
    p.textContent = body;
    el.appendChild(p);
  }
  return el;
}
