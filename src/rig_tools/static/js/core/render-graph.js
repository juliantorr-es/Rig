/**
 * ADR 0011: Runtime Visualization Substrate
 * Stable Core Module: Render Graph & Scene Graph Management
 */

/**
 * RenderNode Contract
 * Every visual primitive must implement this interface.
 */
export class RenderNode {
  constructor(id, sequence = null, status = null) {
    this.id = id;
    this.sequence = sequence;
    this.status = status;
    this.lastStateHash = null;
    this.lastSequence = null;
  }

  /**
   * Initial DOM creation and mounting.
   * @param {Element} parent - The parent DOM element.
   * @returns {Element} The created element.
   */
  render(parent) {
    throw new Error("RenderNode.render() must be implemented");
  }

  /**
   * Incremental update of an existing DOM element.
   * @param {Element} element - The existing DOM element.
   */
  patch(element) {
    throw new Error("RenderNode.patch() must be implemented");
  }

  /**
   * Calculate a hash of the current state to determine if patching is needed.
   * Part of the Invalidation Doctrine.
   */
  getStateHash() {
    return null;
  }
}

/**
 * LegacyWidgetNode
 * Bridge for existing HTMLElement-based widgets to live in the SceneGraph.
 */
export class LegacyWidgetNode extends RenderNode {
  constructor(id, element) {
    super(id);
    this.element = element;
    this.element.id = id;
  }

  render(parent) {
    parent.appendChild(this.element);
    return this.element;
  }

  patch(element) {
    // Legacy widgets are destructive; they recreate the element every time.
    // We swap the old element with the new one.
    if (element !== this.element) {
      element.parentNode.replaceChild(this.element, element);
    }
  }

  getStateHash() {
    // Force patch every time for legacy widgets
    return Math.random();
  }
}

/**
 * ExplainerNode
 * A specialized RenderNode for educational callouts and annotations.
 * Anchors to an existing RenderNode ID in the scene graph.
 */
export class ExplainerNode extends RenderNode {
  constructor(id, anchorId, content, position = 'top') {
    super(id);
    this.anchorId = anchorId;
    this.content = content;
    this.position = position;
  }

  render(parent) {
    const el = createHtmlElement('div', { 
      id: this.id, 
      class: 'rig-explainer animate-entry' 
    });
    
    const bubble = createHtmlElement('div', { class: 'rig-explainer-bubble' });
    bubble.textContent = this.content;
    el.appendChild(bubble);

    const arrow = createHtmlElement('div', { class: 'rig-explainer-arrow' });
    el.appendChild(arrow);

    parent.appendChild(el);
    this.updatePosition(el);
    return el;
  }

  patch(element) {
    const bubble = element.querySelector('.rig-explainer-bubble');
    if (bubble && bubble.textContent !== this.content) {
      bubble.textContent = this.content;
    }
    this.updatePosition(element);
  }

  updatePosition(element) {
    const anchor = document.getElementById(this.anchorId);
    if (!anchor) {
      element.style.display = 'none';
      return;
    }

    element.style.display = 'block';
    const anchorRect = anchor.getBoundingClientRect();
    const parentRect = element.offsetParent ? element.offsetParent.getBoundingClientRect() : { left: 0, top: 0 };

    // Basic top-centered positioning
    const left = (anchorRect.left - parentRect.left) + (anchorRect.width / 2);
    const top = (anchorRect.top - parentRect.top);

    element.style.left = `${left}px`;
    element.style.top = `${top}px`;
  }

  getStateHash() {
    return JSON.stringify({ anchorId: this.anchorId, content: this.content, position: this.position });
  }
}

// Global registry of active managers for observability
const activeManagers = new Set();

export class SceneGraphManager {
  constructor(container) {
    this.container = container;
    this.elements = new Map(); // id -> { primitive, element }
    this.metrics = {
      patchCalls: 0,
      renderCalls: 0,
      garbageCollected: 0
    };
    activeManagers.add(this);
  }

  /**
   * Get aggregated metrics from all active managers.
   */
  static getGlobalMetrics() {
    const global = {
      patchCalls: 0,
      renderCalls: 0,
      garbageCollected: 0,
      activeNodes: 0,
      managerCount: activeManagers.size
    };
    for (const manager of activeManagers) {
      global.patchCalls += manager.metrics.patchCalls;
      global.renderCalls += manager.metrics.renderCalls;
      global.garbageCollected += manager.metrics.garbageCollected;
      global.activeNodes += manager.elements.size;
    }
    return global;
  }

  /**
   * Orchestrate the patching cycle for a primitive.
   * @param {RenderNode} primitive - The primitive to render or patch.
   * @returns {string} The primitive ID.
   */
  patchPrimitive(primitive) {
    const existing = this.elements.get(primitive.id);
    
    if (existing && existing.element) {
      // Invalidation Doctrine: Check sequence and state hash
      const newHash = primitive.getStateHash();
      const isSequenceStable = primitive.sequence !== null && existing.primitive && existing.primitive.lastSequence === primitive.sequence;
      const isStateStable = newHash !== null && existing.primitive && existing.primitive.lastStateHash === newHash;

      if (isSequenceStable && isStateStable) {
        // Skip patching if both sequence and state are identical
        return primitive.id;
      }

      this.metrics.patchCalls++;
      primitive.patch(existing.element);
      
      // Motion Doctrine: Apply semantic state classes if changed
      if (primitive.status) {
        const oldStatus = existing.primitive ? existing.primitive.status : null;
        if (primitive.status !== oldStatus) {
          if (oldStatus) existing.element.classList.remove(`state-${oldStatus}`);
          existing.element.classList.add(`state-${primitive.status}`);
          // Add entry animation if it's a new "active" state
          if (primitive.status === 'executing' || primitive.status === 'streaming') {
            existing.element.classList.add('animate-entry');
          }
        }
      }

      primitive.lastSequence = primitive.sequence;
      primitive.lastStateHash = newHash;
      this.elements.set(primitive.id, { primitive, element: existing.element });
    } else {
      this.metrics.renderCalls++;
      const element = primitive.render(this.container);
      
      // Motion Doctrine: Initial state class
      if (primitive.status) {
        element.classList.add(`state-${primitive.status}`, 'animate-entry');
      }

      primitive.lastSequence = primitive.sequence;
      primitive.lastStateHash = primitive.getStateHash();
      this.elements.set(primitive.id, { primitive, element });
    }

    return primitive.id;
  }

  /**
   * Prune elements that were not visited during the current render pass.
   * @param {Set<string>} activeIds - The IDs of primitives rendered in the current pass.
   */
  garbageCollect(activeIds) {
    for (const [id, entry] of this.elements.entries()) {
      if (!activeIds.has(id)) {
        if (entry.element && entry.element.parentNode) {
          entry.element.parentNode.removeChild(entry.element);
          this.metrics.garbageCollected++;
        }
        this.elements.delete(id);
      }
    }
  }

  /**
   * Full teardown of the scene graph.
   */
  clear() {
    for (const entry of this.elements.values()) {
      if (entry.element && entry.element.parentNode) {
        entry.element.parentNode.removeChild(entry.element);
      }
    }
    this.elements.clear();
  }

  getMetrics() {
    return { ...this.metrics };
  }
}

/**
 * SVG Utility Helpers (Extracted from instrumentation)
 */
export const SVG_NS = "http://www.w3.org/2000/svg";

export function createSvgElement(tag, attrs = {}) {
  const el = document.createElementNS(SVG_NS, tag);
  for (const [key, val] of Object.entries(attrs)) {
    setSvgAttr(el, key, val);
  }
  return el;
}

export function setSvgAttr(el, key, val) {
  if (val === null || val === undefined) {
    el.removeAttribute(key);
    return true;
  }
  const strVal = String(val);
  if (el.getAttribute(key) !== strVal) {
    el.setAttribute(key, strVal);
    return true;
  }
  return false;
}

export function createHtmlElement(tag, attrs = {}, text = null) {
  const el = document.createElement(tag);
  for (const [key, val] of Object.entries(attrs)) {
    setHtmlAttr(el, key, val);
  }
  if (text !== null) el.textContent = text;
  return el;
}

export function setHtmlAttr(el, key, val) {
  if (key === 'class') {
    if (el.className !== (val || '')) {
      el.className = val || '';
      return true;
    }
  } else if (key === 'style' && typeof val === 'object') {
    Object.assign(el.style, val);
    return true;
  } else if (key === 'text') {
    if (el.textContent !== (val || '')) {
      el.textContent = val || '';
      return true;
    }
  } else if (val === null || val === undefined) {
    if (el.hasAttribute(key)) {
      el.removeAttribute(key);
      return true;
    }
  } else {
    const strVal = String(val);
    if (el.getAttribute(key) !== strVal) {
      el.setAttribute(key, strVal);
      return true;
    }
  }
  return false;
}

export function domId(prefix, id) {
  return `rig-${prefix}-${id}`;
}

/**
 * Math Utilities
 */
export function clamp(val, min, max) {
  return Math.max(min, Math.min(max, val));
}

export function mapRange(value, inMin, inMax, outMin, outMax) {
  if (inMax === inMin) return outMin;
  return ((value - inMin) * (outMax - outMin)) / (inMax - inMin) + outMin;
}
