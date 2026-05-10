/**
 * ADR 0011: Runtime Visualization Substrate
 * Stable Core Module: Render Graph & Scene Graph Management
 */

/**
 * RenderNode Contract
 * Every visual primitive must implement this interface.
 */
export class RenderNode {
  constructor(id) {
    this.id = id;
    this.lastStateHash = null;
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
 * SceneGraphManager (Scene Graph Manager)
 * Manages the retention and patching of RenderNodes.
 */
export class SceneGraphManager {
  constructor(container) {
    this.container = container;
    this.elements = new Map(); // id -> { primitive, element }
    this.metrics = {
      patchCalls: 0,
      renderCalls: 0,
      garbageCollected: 0
    };
  }

  /**
   * Orchestrate the patching cycle for a primitive.
   * @param {RenderNode} primitive - The primitive to render or patch.
   * @returns {string} The primitive ID.
   */
  patchPrimitive(primitive) {
    const existing = this.elements.get(primitive.id);
    
    if (existing && existing.element) {
      // Invalidation Doctrine: Check state hash if available
      const newHash = primitive.getStateHash();
      if (newHash !== null && existing.primitive && existing.primitive.lastStateHash === newHash) {
        // Skip patching if state is identical
        return primitive.id;
      }

      this.metrics.patchCalls++;
      primitive.patch(existing.element);
      this.elements.set(primitive.id, { primitive, element: existing.element });
    } else {
      this.metrics.renderCalls++;
      const element = primitive.render(this.container);
      this.elements.set(primitive.id, { primitive, element });
    }

    // Update last state hash
    primitive.lastStateHash = primitive.getStateHash();
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
  for (const [name, val] of Object.entries(attrs)) {
    el.setAttribute(name, val);
  }
  return el;
}

export function setSvgAttr(el, name, value) {
  if (el.getAttribute(name) !== String(value)) {
    el.setAttribute(name, value);
    return true;
  }
  return false;
}

export function svgId(prefix, id) {
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
