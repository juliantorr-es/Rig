let projection = null;
let subscribers = new Set();

function normalizeProjectionEnvelope(nextProjection) {
  if (!nextProjection || typeof nextProjection !== 'object') {
    return null;
  }
  return {
    schema_version: nextProjection.schema_version || nextProjection.schemaVersion || 'rig.ui.projection.v1',
    projection_id: nextProjection.projection_id || nextProjection.projectionId || 'local-shell',
    revision: Number.isFinite(nextProjection.revision) ? nextProjection.revision : 1,
    generated_at: nextProjection.generated_at || nextProjection.generatedAt || '',
    screen: nextProjection.screen || 'empty_workspace',
    shell: nextProjection.shell && typeof nextProjection.shell === 'object' ? nextProjection.shell : {},
    chat: nextProjection.chat || null,
    layout: nextProjection.layout && typeof nextProjection.layout === 'object' ? nextProjection.layout : { regions: {} },
    widgets: nextProjection.widgets && typeof nextProjection.widgets === 'object' ? nextProjection.widgets : {},
    intents: nextProjection.intents && typeof nextProjection.intents === 'object' ? nextProjection.intents : {},
    ...nextProjection,
  };
}

export function setProjection(nextProjection) {
  projection = normalizeProjectionEnvelope(nextProjection);
  for (const cb of subscribers) cb(projection);
}

export function getProjection() {
  return projection;
}

export function subscribeProjection(callback) {
  subscribers.add(callback);
  return () => subscribers.delete(callback);
}

export function clearProjection() {
  projection = null;
}

export { normalizeProjectionEnvelope };
