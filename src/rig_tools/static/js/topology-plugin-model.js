/** Deterministic Topology Plugin Model
 *
 * Lane-safe topology extension hooks for Rig visualization.
 * Plugins declare how they map projection data into topology additions
 * without mutating unrelated lanes or introducing nondeterministic layout.
 */

const DEFAULT_MAX_PLUGINS = 50;

function comparePlugins(a, b) {
  const seqA = a.sequence ?? 0;
  const seqB = b.sequence ?? 0;
  if (seqA !== seqB) return seqA - seqB;

  const layerA = a.disclosureLayer ?? 2;
  const layerB = b.disclosureLayer ?? 2;
  if (layerA !== layerB) return layerA - layerB;

  return String(a.id).localeCompare(String(b.id));
}

export class TopologyPluginModel {
  constructor(options = {}) {
    this.maxPlugins = options.maxPlugins || DEFAULT_MAX_PLUGINS;
    this.plugins = new Map();
    this.order = [];
  }

  register(plugin) {
    if (!plugin || typeof plugin !== 'object') {
      throw new TypeError('Topology plugin registration requires a plugin object.');
    }

    const id = plugin.id || `topology-plugin-${this.order.length}`;
    const normalized = {
      id,
      disclosureLayer: plugin.disclosureLayer ?? 2,
      densityPriority: plugin.densityPriority || 'medium',
      collapseBehavior: plugin.collapseBehavior || 'summarize',
      reducedMotionBehavior: plugin.reducedMotionBehavior || 'static',
      laneScope: plugin.laneScope || 'local',
      sequence: plugin.sequence ?? 0,
      build: plugin.build,
      cleanup: plugin.cleanup || null
    };

    if (this.plugins.has(id)) {
      this.unregister(id);
    }

    this.plugins.set(id, normalized);
    this.order.push(id);
    this._trim();
    return normalized;
  }

  unregister(id) {
    const existing = this.plugins.get(id);
    if (!existing) return;
    if (typeof existing.cleanup === 'function') {
      existing.cleanup(existing);
    }
    this.plugins.delete(id);
    this.order = this.order.filter(entryId => entryId !== id);
  }

  getOrdered() {
    return this.order
      .map(id => this.plugins.get(id))
      .filter(Boolean)
      .sort(comparePlugins);
  }

  composeTopology(projection, context = {}) {
    const ordered = this.getOrdered();
    const lanes = [];

    for (const plugin of ordered) {
      if (!this._canParticipate(plugin, context)) continue;
      const contribution = typeof plugin.build === 'function' ? plugin.build(projection, context) : null;
      if (contribution) {
        lanes.push({
          pluginId: plugin.id,
          disclosureLayer: plugin.disclosureLayer,
          densityPriority: plugin.densityPriority,
          collapseBehavior: plugin.collapseBehavior,
          reducedMotionBehavior: plugin.reducedMotionBehavior,
          contribution
        });
      }
    }

    return lanes;
  }

  _canParticipate(plugin, context) {
    if (context.disclosureLayer !== undefined && plugin.disclosureLayer > context.disclosureLayer) {
      return false;
    }
    if (context.lowStimulation && plugin.reducedMotionBehavior === 'animated') {
      return false;
    }
    return true;
  }

  _trim() {
    while (this.order.length > this.maxPlugins) {
      const oldestId = this.order.shift();
      this.unregister(oldestId);
    }
  }
}
