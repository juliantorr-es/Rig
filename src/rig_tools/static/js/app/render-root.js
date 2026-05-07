import { getProgressEvents } from './progress-store.js';

export function renderRoot({ projection, widgetRegistry, pendingIntents, renderChat, renderProgress }) {
  if (!projection()) return;

  Object.keys(projection().layout.regions).forEach(regionId => {
    if (regionId === 'inspector') return;
    const el = document.getElementById(regionId);
    if (!el) return;
    el.innerHTML = '';
    const widgetIds = projection().layout.regions[regionId];
    widgetIds.forEach(widgetId => {
      const widget = projection().widgets[widgetId];
      const renderer = widgetRegistry[widget.type] || widgetRegistry._fallback;
      const widgetEl = renderer(widgetId, widget.data, widget.actions);
      if (widgetEl) widgetEl.id = widgetId;
      if (widgetEl) el.appendChild(widgetEl);
    });
  });

  renderChat();
  if (renderProgress) renderProgress(getProgressEvents());
}
