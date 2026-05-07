export function listContainer(className) {
  const el = document.createElement('div');
  if (className) el.className = className;
  return el;
}
