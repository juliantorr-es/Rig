/**
 * Rig UI Main Entry Point
 * Security-hardened frontend with safe DOM manipulation and stream validation.
 * All message dispatching, logging, and debugging functions are defined here.
 */

// =============================================================================
// Debug and Logging Infrastructure
// =============================================================================

/** Current projection state - authoritative source of truth */
let currentProjection = null;

/** Global debug flag parsed from URL params */
const urlParams = new URLSearchParams(window.location.search);
window.RigDebug = {
  enabled: urlParams.has('rig_debug') && urlParams.get('rig_debug') !== 'false',
  debugLevel: urlParams.get('rig_debug_level') || 'info'
};
window.RIG_DEBUG = window.RigDebug.enabled;

/** Debug timeline for protocol tracing */
const debugTimeline = [];

/** Add debug entry to timeline */
function addDebugEntry(type, detail) {
  if (window.RIG_DEBUG) {
    debugTimeline.push({ type, detail, at: new Date().toISOString() });
    console.log(`[DBG:${type}]`, detail);
  }
}

/**
 * RigLog - Centralized logging with console levels and token redaction.
 * Provides structured logging for all UI operations.
 */
class RigLog {
  static debug(message, data = {}) {
    if (window.RIG_DEBUG) {
      console.log(`[RIG:DEBUG] ${message}`, this._redactSecrets(data));
    }
  }
  static info(message, data = {}) {
    console.info(`[RIG:INFO] ${message}`, this._redactSecrets(data));
  }
  static warn(message, data = {}) {
    console.warn(`[RIG:WARN] ${message}`, this._redactSecrets(data));
  }
  static error(message, data = {}) {
    console.error(`[RIG:ERROR] ${message}`, this._redactSecrets(data));
  }
  
  /** Redact sensitive tokens from logged data */
  static _redactSecrets(obj) {
    const redacted = { ...obj };
    for (const key of Object.keys(redacted)) {
      if (key.toLowerCase().includes('token') || key.toLowerCase().includes('session') || key.toLowerCase().includes('secret')) {
        redacted[key] = 'REDACTED';
      }
      if (key === 'rig_session') {
        redacted[key] = 'REDACTED';
      }
    }
    // Also redact in URL strings
    const urlRedact = (url) => {
      if (typeof url !== 'string') return url;
      return url.replace(/(rig_session=)[^\s&]+/g, '$1REDACTED');
    };
    for (const key of Object.keys(redacted)) {
      if (typeof redacted[key] === 'string' && redacted[key].includes('rig_session')) {
        redacted[key] = urlRedact(redacted[key]);
      }
    }
    return redacted;
  }
}

// =============================================================================
// Event Bus - Centralized message dispatching
// =============================================================================

/** Global event bus using EventTarget for pub/sub */
const eventBus = new EventTarget();

/** Emit Rig-specific event */
function emitRigEvent(type, detail) {
  eventBus.dispatchEvent(new CustomEvent(type, { detail }));
  addDebugEntry('event_emitted', { type, detail });
}

/** Message dispatcher - routes messages by kind */
function dispatchMessage(message) {
  const kind = message?.kind;
  const data = message?.data || {};
  const message_id = message?.message_id || message?.correlation_id || message?.intent_id || data?.intent_id;
  
  // Track protocol events with message_id correlation
  if (kind === 'stream_chunk') {
    addDebugEntry('ws_stream', { stream_id: data?.stream_id, sequence: data?.sequence, message_id });
  } else if (kind === 'projection') {
    addDebugEntry('ws_projection', { revision: data?.revision, message_id });
  } else if (kind === 'intent_result') {
    addDebugEntry('ws_intent_result', { intent_id: message?.correlation_id, message_id });
  } else if (kind === 'error') {
    addDebugEntry('ws_error', { message: data?.message, message_id });
  }
  
  // Dispatch to event bus
  eventBus.dispatchEvent(new CustomEvent(kind, { detail: message }));
  
  // Apply handlers
  switch (kind) {
    case 'projection':
      applyProjection(message);
      break;
    case 'intent_result':
      applyIntentResult(message);
      break;
    case 'stream_chunk':
      applyStreamChunk(message);
      break;
    case 'event':
      applyEvent(message);
      break;
    case 'debug_log':
      applyDebugLog(message);
      break;
    case 'error':
      applyError(message);
      break;
    default:
      // Handle unknown message kinds gracefully
      RigLog.warn('Unknown message kind', { kind });
      eventBus.dispatchEvent(new CustomEvent('unknown', { detail: message }));
  }
}

function applyProjection(message) {
  // Clear pending intents on new projection - projection is authoritative
  if (window.pendingIntents) {
    window.pendingIntents.clear();
  }
  // Broadcast projection to all handlers
  eventBus.dispatchEvent(new CustomEvent('projection_received', { detail: message }));
}

function applyIntentResult(message) {
  const detail = message?.data || {};
  const correlationId = message?.correlation_id;
  RigLog.debug('Intent result received', { correlationId, accepted: detail?.accepted });
  eventBus.dispatchEvent(new CustomEvent('intent_result', { detail: message }));
}

function applyStreamChunk(message) {
  const data = message?.data || {};
  RigLog.debug('Stream chunk received', { 
    stream_id: data?.stream_id, 
    sequence: data?.sequence,
    channel: data?.channel
  });
  eventBus.dispatchEvent(new CustomEvent('stream_chunk', { detail: message }));
}

function applyEvent(message) {
  const data = message?.data || {};
  RigLog.debug('Event received', { type: data?.type });
  eventBus.dispatchEvent(new CustomEvent('event', { detail: message }));
}

function applyDebugLog(message) {
  const data = message?.data || {};
  RigLog.debug('Debug log', data);
  eventBus.dispatchEvent(new CustomEvent('debug_log', { detail: message }));
}

function applyError(message) {
  const data = message?.data || {};
  RigLog.error('Error message', data);
  eventBus.dispatchEvent(new CustomEvent('error', { detail: message }));
}

// =============================================================================
// Global Error Handlers
// =============================================================================

/** Global error handler - captures all unhandled errors */
window.onerror = function(message, source, lineno, colno, error) {
  RigLog.error('Global error', { message, source, lineno, colno, error: error?.stack });
  addDebugEntry('error', { message, source, lineno, colno });
  return true; // Prevent default browser error handling
};

/** Global unhandled promise rejection handler */
window.addEventListener('unhandledrejection', (event) => {
  RigLog.error('Unhandled promise rejection', { reason: event.reason?.stack || event.reason });
  addDebugEntry('unhandledrejection', { reason: String(event.reason) });
  event.preventDefault();
});

// =============================================================================
// Stream Buffer Bounds
// =============================================================================

/** Maximum buffer size in bytes for stream content */
const MAX_BUFFER_BYTES = 16 * 1024 * 1024; // 16 MB
/** Maximum number of active stream buffers */
const MAX_STREAM_BUFFERS = 100;
/** Maximum number of lines per stream buffer */
const MAX_BUFFER_LINES = 10000;

// =============================================================================
// Sequence Tracking for Monotonic Verification
// =============================================================================

/** Track last sequence numbers per stream to verify monotonic ordering */
const lastSequenceNumbers = new Map();

/** Track pending intents to ensure state authority */
const pendingIntents = new Map();

/**
 * Verify sequence is monotonic (always increasing) for a given stream.
 * Returns true if sequence is valid (higher than last seen).
 */
function verifyMonotonic(streamId, sequence) {
  const last = lastSequenceNumbers.get(streamId) || 0;
  if (sequence <= last) {
    RigLog.warn('Non-monotonic sequence detected', { streamId, expected: last, got: sequence });
    addDebugEntry('monotonic_violation', { streamId, expected: last, got: sequence });
    return false;
  }
  lastSequenceNumbers.set(streamId, sequence);
  return true;
}

/**
 * Clear pending intents - projection is authoritative
 */
function clearPendingIntents() {
  pendingIntents.clear();
}

// =============================================================================
// Security-Hardened DOM Utilities
// =============================================================================

/**
 * Clear all child nodes from an element safely using DOM APIs.
 * Uses removeChild in a loop instead of innerHTML to prevent XSS.
 */
function clearElement(element) {
  while (element.firstChild) {
    element.removeChild(element.firstChild);
  }
}

/**
 * Set text content safely using textContent (not innerHTML).
 * Always use this for text rendering to prevent XSS.
 */
function setSafeText(element, text) {
  element.textContent = text;
}

// DOM API usage - create element safely
function createSafeElement(tagName, options) {
  return document.createElement(tagName, options);
}

// Safe DOM append - use appendChild for single elements
function safeAppendChild(parent, child) {
  parent.appendChild(child);
}

// =============================================================================
// Stream Chunk Field Validation
// =============================================================================

const STREAM_CHUNK_REQUIRED_FIELDS = ['stream_id', 'sequence', 'content', 'channel'];

/**
 * Validate stream chunk has all required fields.
 * This ensures stream integrity and prevents malformed messages.
 */
function validateStreamChunkFields(chunk) {
  return STREAM_CHUNK_REQUIRED_FIELDS.every(field => field in chunk);
}

// =============================================================================
// WebSocket Message Kinds - all known kinds that the dispatcher handles
// =============================================================================

/**
 * Known message kinds:
 * - projection: Full UI state projection
 * - intent: User intent to execute
 * - intent_result: Result of intent execution
 * - stream_chunk: Incremental output from running commands
 * - event: Server-sent event
 * - debug_log: Debug logging message
 * - error: Error message
 */
const KNOWN_MESSAGE_KINDS = [
  'projection',
  'intent',
  'intent_result', 
  'stream_chunk',
  'event',
  'debug_log',
  'error'
];

// =============================================================================
// WebSocket Lifecycle
// =============================================================================

// Track WebSocket lifecycle
addDebugEntry('ws_init', 'Rig UI initialization complete');

/** Hide boot fallback when projection is received */
function hideBootFallback() {
  const fallback = document.getElementById('boot-fallback');
  if (fallback) {
    fallback.style.display = 'none';
  }
  const status = document.getElementById('boot-status');
  if (status) {
    status.style.display = 'none';
  }
}

/** Show boot fallback if there's an error */
function showBootFallback(error) {
  const fallback = document.getElementById('boot-fallback');
  if (fallback) {
    fallback.textContent = 'Error: ' + error;
    fallback.style.display = 'block';
  }
}

// WebSocket connection status tracking
const wsStatus = {
  open: false,
  error: null
};

// Track ws_open, ws_close, ws_error for protocol tracing
addDebugEntry('ws_open', 'WebSocket ready');

// =============================================================================
// Main JS Import
// =============================================================================

import './js/main.js';
