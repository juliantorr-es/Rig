const subscribers = new Set();
const MAX_OPERATIONS = 12;
const MAX_EVENTS_PER_OPERATION = 8;

let operationOrder = [];
const operationMap = new Map();

function cloneEvent(event) {
  return {
    ...event,
    evidence_refs: Array.isArray(event?.evidence_refs) ? [...event.evidence_refs] : [],
    metadata: event && typeof event.metadata === 'object' && event.metadata !== null ? { ...event.metadata } : {},
  };
}

function eventSortKey(event) {
  return [
    Number.isFinite(Number(event.sequence)) ? Number(event.sequence) : 0,
    String(event.timestamp || ''),
  ];
}

function normalizeOperation(operation_id) {
  if (!operationMap.has(operation_id)) {
    operationMap.set(operation_id, {
      operation_id,
      command: '',
      phase: 'operation.log',
      message: '',
      level: 'info',
      status: 'unknown',
      sequence: 0,
      timestamp: '',
      receipt_candidate: false,
      receipt_kind: null,
      evidence_refs: [],
      metadata: {},
      events: [],
    });
    operationOrder.push(operation_id);
  }
  return operationMap.get(operation_id);
}

function emitSnapshot() {
  const operations = getProgressOperations();
  for (const cb of subscribers) cb(operations);
}

export function appendProgressEvent(event) {
  if (!event || !event.operation_id) return;
  const op = normalizeOperation(event.operation_id);
  const next = cloneEvent(event);
  op.command = next.command || op.command;
  op.phase = next.phase || op.phase;
  op.message = next.message || op.message;
  op.level = next.level || op.level;
  op.status = next.status || op.status;
  op.sequence = Number.isFinite(Number(next.sequence)) ? Number(next.sequence) : op.sequence;
  op.timestamp = next.timestamp || op.timestamp;
  op.receipt_candidate = Boolean(next.receipt_candidate);
  op.receipt_kind = next.receipt_kind || op.receipt_kind;
  op.evidence_refs = Array.isArray(next.evidence_refs) ? [...next.evidence_refs] : op.evidence_refs;
  op.metadata = next.metadata && typeof next.metadata === 'object' ? { ...next.metadata } : op.metadata;
  op.events = [...op.events, next]
    .sort((a, b) => {
      const [aseq, ats] = eventSortKey(a);
      const [bseq, bts] = eventSortKey(b);
      return aseq - bseq || ats.localeCompare(bts);
    })
    .slice(-MAX_EVENTS_PER_OPERATION);
  operationOrder = operationOrder.filter(item => item !== event.operation_id);
  operationOrder.push(event.operation_id);
  operationOrder = operationOrder.slice(-MAX_OPERATIONS);
  for (const opId of [...operationMap.keys()]) {
    if (!operationOrder.includes(opId)) operationMap.delete(opId);
  }
  emitSnapshot();
}

export function getProgressOperations() {
  return operationOrder
    .map(operation_id => operationMap.get(operation_id))
    .filter(Boolean)
    .map(op => ({ ...op, events: op.events.map(cloneEvent) }))
    .sort((a, b) => (b.sequence - a.sequence) || String(b.timestamp || '').localeCompare(String(a.timestamp || '')));
}

export function getProgressEvents() {
  return getProgressOperations().flatMap(op => op.events);
}

export function subscribeProgress(callback) {
  subscribers.add(callback);
  return () => subscribers.delete(callback);
}

export function clearProgress() {
  operationOrder = [];
  operationMap.clear();
  emitSnapshot();
}
