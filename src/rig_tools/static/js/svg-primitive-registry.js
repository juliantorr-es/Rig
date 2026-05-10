/** Deterministic SVG Primitive Registry
 *
 * Bounded, replay-safe registry for visualization primitives.
 * Supports deterministic registration ordering and semantic metadata.
 * Primitives are registered with semantic metadata so extensions can
 * participate in disclosure, motion, and density governance without
 * introducing hidden frontend state.
 */

const DEFAULT_MAX_PRIMITIVES = 500;

function createDeterministicId(prefix, ...components) {
  const parts = [String(prefix), ...components.map(c => String(c))];
  const combined = parts.join('|');
  let hash = 0;
  for (let i = 0; i < combined.length; i++) {
    const char = combined.charCodeAt(i);
    hash = ((hash << 5) - hash) + char;
    hash = hash & hash;
  }
  return `${prefix}-${Math.abs(hash).toString(16).padStart(8, '0')}`;
}

function comparePrimitiveEntries(a, b) {
  const seqA = a.metadata.sequence ?? 0;
  const seqB = b.metadata.sequence ?? 0;
  if (seqA !== seqB) return seqA - seqB;

  const priorityOrder = { high: 0, medium: 1, low: 2 };
  const priA = priorityOrder[a.metadata.densityPriority] ?? 99;
  const priB = priorityOrder[b.metadata.densityPriority] ?? 99;
  if (priA !== priB) return priA - priB;

  return String(a.id).localeCompare(String(b.id));
}

export class SvgPrimitiveRegistry {
  constructor(options = {}) {
    this.maxPrimitives = options.maxPrimitives || DEFAULT_MAX_PRIMITIVES;
    this.primitives = new Map();
    this.order = [];
  }

  register(entry) {
    if (!entry || typeof entry !== 'object') {
      throw new TypeError('Primitive registration requires an entry object.');
    }

    const id = entry.id || createDeterministicId('primitive', entry.kind, entry.sequence, entry.disclosureLayer);
    const metadata = {
      kind: entry.kind || 'unknown',
      disclosureLayer: entry.disclosureLayer ?? 2,
      densityPriority: entry.densityPriority || 'medium',
      collapseBehavior: entry.collapseBehavior || 'summarize',
      reducedMotionBehavior: entry.reducedMotionBehavior || 'static',
      sequence: entry.sequence ?? 0,
      ownerId: entry.ownerId || null
    };

    const normalized = {
      id,
      metadata,
      build: entry.build,
      cleanup: entry.cleanup || null
    };

    if (this.primitives.has(id)) {
      this._remove(id);
    }

    this.primitives.set(id, normalized);
    this.order.push(id);
    this._trim();
    return normalized;
  }

  unregister(id) {
    this._remove(id);
  }

  get(id) {
    return this.primitives.get(id) || null;
  }

  getAll() {
    return this.order.map(id => this.primitives.get(id)).filter(Boolean);
  }

  getOrdered() {
    return this.getAll().slice().sort(comparePrimitiveEntries);
  }

  clear() {
    for (const id of [...this.order]) {
      this._remove(id);
    }
  }

  attach(ownerId, primitives = []) {
    return primitives.map((primitive, index) => this.register({
      ...primitive,
      ownerId,
      sequence: primitive.sequence ?? index
    }));
  }

  _trim() {
    while (this.order.length > this.maxPrimitives) {
      const oldestId = this.order.shift();
      this._remove(oldestId);
    }
  }

  _remove(id) {
    const existing = this.primitives.get(id);
    if (!existing) return;
    if (typeof existing.cleanup === 'function') {
      existing.cleanup(existing);
    }
    this.primitives.delete(id);
    this.order = this.order.filter(entryId => entryId !== id);
  }
}

export { createDeterministicId };
