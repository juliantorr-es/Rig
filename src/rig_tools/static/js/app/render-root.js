import { getProgressEvents } from './progress-store.js';
import { SceneGraphManager, RenderNode, LegacyWidgetNode } from '../core/render-graph.js';
import { DebugPanelNode } from '../widgets/debug-panel.js';
import { shouldShowWidget, getCognitiveLayer } from './cognitive-disclosure.js';

// Persistent managers per region to maintain retained state
const regionManagers = new Map();
let debugPanel = null;

export function renderRoot({ projection, widgetRegistry, pendingIntents, renderChat, renderProgress }) {
  if (!projection()) return;

  function renderWidgetSafely(renderer, widgetId, widget) {
    try {
      const proj = projection();
      // Pass projection and other context to widgets that need it
      return renderer(widgetId, widget.data, {
        ...widget.actions,
        projection: proj,
        pendingIntents: pendingIntents(),
        sequence: widget.data.sequence || proj.sequence || null
      });
    } catch (error) {
      console.error(`Failed to render widget ${widgetId} (${widget.type}):`, error);
      const fallback = widgetRegistry._fallback || (() => null);
      return fallback(widget);
    }
  }

  Object.keys(projection().layout.regions).forEach(regionId => {
    if (regionId === 'inspector') return;
    const el = document.getElementById(regionId);
    if (!el) return;

    // Initialize or retrieve manager for this region
    let manager = regionManagers.get(regionId);
    if (!manager) {
      manager = new SceneGraphManager(el);
      regionManagers.set(regionId, manager);
    }

    const widgetIds = projection().layout.regions[regionId];
    const activeIds = new Set();

    widgetIds.forEach(widgetId => {
      const widget = projection().widgets[widgetId];
      if (!widget) return;

      // Cognitive Disclosure Filter
      if (!shouldShowWidget(widget.type)) return;
      
      const renderer = widgetRegistry[widget.type] || widgetRegistry._fallback;
      const result = renderWidgetSafely(renderer, widgetId, widget);
      
      if (!result) return;

      if (result instanceof RenderNode) {
        // Retained RenderNode path
        manager.patchPrimitive(result);
        activeIds.add(result.id);
      } else if (result instanceof HTMLElement) {
        // Legacy/Stateless HTMLElement path wrapped in a RenderNode bridge
        const node = new LegacyWidgetNode(widgetId, result);
        manager.patchPrimitive(node);
        activeIds.add(widgetId);
      }
    });

    // Garbage collect widgets that are no longer in the projection for this region
    manager.garbageCollect(activeIds);
  });

  // Handle global Debug Panel
  if (!debugPanel) {
    debugPanel = new DebugPanelNode('global-debug-panel');
    debugPanel.render(document.body);
  }
  debugPanel.patch(document.getElementById('rig-debug-panel'));

  renderChat();
  if (renderProgress) renderProgress(getProgressEvents());
}
