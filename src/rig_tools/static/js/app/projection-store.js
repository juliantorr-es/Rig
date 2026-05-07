let projection = null;
let subscribers = new Set();

export function setProjection(nextProjection) {
  projection = nextProjection;
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
