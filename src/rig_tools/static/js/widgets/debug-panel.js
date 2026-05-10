import { RenderNode, createHtmlElement, setHtmlAttr, SceneGraphManager } from '../core/render-graph.js';

/**
 * DebugPanelNode - Retained RenderNode for global renderer observability.
 */
export class DebugPanelNode extends RenderNode {
  constructor(id) {
    super(id);
    this.isVisible = false;
    this.lastMetrics = null;
  }

  render(parent) {
    const container = createHtmlElement('div', { 
      id: 'rig-debug-panel',
      style: {
        position: 'fixed',
        bottom: '10px',
        right: '10px',
        width: '240px',
        backgroundColor: 'rgba(0, 0, 0, 0.85)',
        color: '#00ff00',
        fontFamily: 'monospace',
        fontSize: '10px',
        padding: '8px',
        borderRadius: '4px',
        border: '1px solid #333',
        zIndex: '9999',
        pointerEvents: 'none',
        display: 'none'
      }
    });

    container.appendChild(createHtmlElement('div', { 
      style: { fontWeight: 'bold', borderBottom: '1px solid #333', marginBottom: '4px', paddingBottom: '2px' }
    }, 'RIG RENDERER TELEMETRY'));

    container.appendChild(this._createMetricRow('Patch Calls:', 'debug-patch-calls'));
    container.appendChild(this._createMetricRow('Render Calls:', 'debug-render-calls'));
    container.appendChild(this._createMetricRow('GC Events:', 'debug-gc-events'));
    container.appendChild(this._createMetricRow('Active Nodes:', 'debug-active-nodes'));
    container.appendChild(this._createMetricRow('Regions:', 'debug-regions'));
    
    container.appendChild(createHtmlElement('div', { 
      style: { marginTop: '4px', fontSize: '9px', color: '#888', fontStyle: 'italic' }
    }, 'ADR 0011 Substrate Active'));

    parent.appendChild(container);
    return container;
  }

  _createMetricRow(label, id) {
    const row = createHtmlElement('div', { style: { display: 'flex', justifyContent: 'space-between' } });
    row.appendChild(createHtmlElement('span', {}, label));
    row.appendChild(createHtmlElement('span', { id: id, style: { fontWeight: 'bold' } }, '0'));
    return row;
  }

  patch(element) {
    const isDebug = window.RIG_DEBUG || false;
    if (isDebug !== this.isVisible) {
      setHtmlAttr(element, 'style', { display: isDebug ? 'block' : 'none' });
      this.isVisible = isDebug;
    }

    if (!isDebug) return;

    const metrics = SceneGraphManager.getGlobalMetrics();
    
    setHtmlAttr(element.querySelector('#debug-patch-calls'), 'text', String(metrics.patchCalls));
    setHtmlAttr(element.querySelector('#debug-render-calls'), 'text', String(metrics.renderCalls));
    setHtmlAttr(element.querySelector('#debug-gc-events'), 'text', String(metrics.garbageCollected));
    setHtmlAttr(element.querySelector('#debug-active-nodes'), 'text', String(metrics.activeNodes));
    setHtmlAttr(element.querySelector('#debug-regions'), 'text', String(metrics.managerCount));
  }

  getStateHash() {
    // Poll metrics every frame if visible
    if (!window.RIG_DEBUG) return 'hidden';
    return JSON.stringify(SceneGraphManager.getGlobalMetrics());
  }
}
