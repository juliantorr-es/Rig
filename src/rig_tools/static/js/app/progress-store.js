let progressEvents = [];
const subscribers = new Set();
const MAX_PROGRESS_EVENTS = 25;

export function appendProgressEvent(event) {
  progressEvents = [...progressEvents, event].slice(-MAX_PROGRESS_EVENTS);
  for (const cb of subscribers) cb(progressEvents);
}

export function getProgressEvents() {
  return progressEvents;
}

export function subscribeProgress(callback) {
  subscribers.add(callback);
  return () => subscribers.delete(callback);
}

export function clearProgress() {
  progressEvents = [];
  for (const cb of subscribers) cb(progressEvents);
}

