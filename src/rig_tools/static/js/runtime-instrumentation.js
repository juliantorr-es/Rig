/** Runtime Instrumentation State Machine
 *
 * PHASE 1-2 & 5-7: Truthful Runtime Instrumentation
 *
 * Core doctrine:
 * - Animations derive FROM real runtime state ONLY
 * - NO timers as authority source
 * - NO fake thinking indicators
 * - NO meaningless shimmer
 * - NO arbitrary loading loops
 * - NO synthetic motion disconnected from runtime state
 * - Projection-only rendering (never fetches data)
 * - No authority inference
 * - Deterministic rendering
 * - Replay-safe rendering
 * - Bounded visual state buffers
 *
 * This module provides:
 * - Deterministic instrumentation state machine
 * - Runtime visualization state normalization
 * - Animation state derivation from projections
 * - Bounded visual state buffers
 * - Replay-safe visual sequencing
 * - Stream velocity visualization
 * - Integrity visualization
 * - Stateful loading system
 *
 * State categories:
 * - planning
 * - streaming
 * - proposing
 * - validating
 * - replaying
 * - stalled
 * - integrity-warning
 * - capability-routing
 * - completion
 * - failure
 *
 * Animation/state transitions derive from:
 * - websocket events
 * - projection state
 * - sequence progression
 * - runtime throughput
 * - replay state
 */

// =============================================================================
// Constants
// =============================================================================

/** Maximum number of visual state entries in buffer */
const MAX_VISUAL_STATE_ENTRIES = 100;

/** Maximum age of visual state entries (ms) */
const MAX_VISUAL_STATE_AGE_MS = 60000;

/** Maximum number of velocity samples */
const MAX_VELOCITY_SAMPLES = 50;

/** Maximum number of replay frames */
const MAX_REPLAY_FRAMES = 200;

/** Maximum number of integrity warnings to display */
const MAX_INTEGRITY_WARNINGS = 10;

/** Minimum time between state updates (ms) - prevents update storms */
const MIN_STATE_UPDATE_INTERVAL_MS = 16;

/** Stream state categories */
export const RuntimeInstrumentationState = {
  PLANNING: 'planning',
  STREAMING: 'streaming',
  PROPOSING: 'proposing',
  VALIDATING: 'validating',
  REPLAYING: 'replaying',
  STALLED: 'stalled',
  INTEGRITY_WARNING: 'integrity-warning',
  CAPABILITY_ROUTING: 'capability-routing',
  COMPLETION: 'completion',
  FAILURE: 'failure',
  IDLE: 'idle'
};

/** Severity levels */
export const InstrumentationSeverity = {
  DEBUG: 'debug',
  INFO: 'info',
  WARNING: 'warning',
  ERROR: 'error',
  CRITICAL: 'critical'
};

/** Channel types for visualization */
export const VisualizationChannel = {
  ASSISTANT: 'assistant',
  USER: 'user',
  SYSTEM: 'system',
  TOOL: 'tool',
  PROPOSAL: 'proposal',
  DIAGNOSTIC: 'diagnostic',
  STATUS: 'status',
  HEARTBEAT: 'heartbeat',
  WARNING: 'warning',
  ERROR: 'error',
  COMPLETION: 'completion',
  META: 'meta'
};

/** Motion types for animation */
export const MotionType = {
  NONE: 'none',
  PULSE: 'pulse',
  STREAM: 'stream',
  REPLAY: 'replay',
  STALLED: 'stalled',
  COMPLETE: 'complete',
  FAILURE: 'failure'
};

// =============================================================================
// Helper Functions
// =============================================================================

/** Generate deterministic ID from components */
function generateDeterministicId(prefix, ...components) {
  const parts = [String(prefix), ...components.map(c => String(c))];
  const combined = parts.join('|');
  // Simple hash-like function for deterministic IDs
  let hash = 0;
  for (let i = 0; i < combined.length; i++) {
    const char = combined.charCodeAt(i);
    hash = ((hash << 5) - hash) + char;
    hash = hash & hash; // Convert to 32-bit integer
  }
  return `${prefix}_${Math.abs(hash).toString(16).substring(0, 12)}`;
}

/** Safe string truncation */
function safeTruncate(str, maxLength) {
  if (!str || typeof str !== 'string') return '';
  if (str.length <= maxLength) return str;
  const lastSpace = str.lastIndexOf(' ', maxLength);
  const truncateAt = lastSpace > maxLength * 0.8 ? lastSpace : maxLength;
  return str.substring(0, truncateAt) + '...';
}

/** Format bytes to human readable */
function formatBytes(bytes) {
  if (!bytes || bytes === 0) return '0 B';
  if (bytes < 1024) return bytes + ' B';
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
  if (bytes < 1024 * 1024 * 1024) return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
  return (bytes / (1024 * 1024 * 1024)).toFixed(1) + ' GB';
}

/** Format tokens with commas */
function formatTokens(tokens) {
  if (tokens === undefined || tokens === null) return '0';
  return Number(tokens).toString().replace(/\B(?=(\d{3})+(?!\d))/g, ',');
}

/** Get color for severity */
function getColorForSeverity(severity) {
  const colors = {
    debug: 'var(--color-debug, #888)',
    info: 'var(--color-info, #e0e0e0)',
    warning: 'var(--color-warning, #ffa500)',
    error: 'var(--color-error, #ff5555)',
    critical: 'var(--color-critical, #ff4444)'
  };
  return colors[severity?.toLowerCase() || 'info'] || colors.info;
}

/** Get motion class for state */
function getMotionClassForState(state) {
  switch (state) {
    case RuntimeInstrumentationState.STREAMING:
      return MotionType.STREAM;
    case RuntimeInstrumentationState.PROPOSING:
      return MotionType.PULSE;
    case RuntimeInstrumentationState.REPLAYING:
      return MotionType.REPLAY;
    case RuntimeInstrumentationState.STALLED:
      return MotionType.STALLED;
    case RuntimeInstrumentationState.COMPLETION:
      return MotionType.COMPLETE;
    case RuntimeInstrumentationState.FAILURE:
      return MotionType.FAILURE;
    default:
      return MotionType.NONE;
  }
}

/** Clamp value between min and max */
function clamp(value, min, max) {
  return Math.min(Math.max(value, min), max);
}

/** Linear interpolation */
function lerp(a, b, t) {
  return a + (b - a) * clamp(t, 0, 1);
}

// =============================================================================
// Velocity Sample
// =============================================================================

/** Represents a velocity sample for stream throughput tracking */
export class VelocitySample {
  constructor(sequence, byteCount, tokenCount, timestamp = Date.now()) {
    this.sequence = sequence;
    this.byteCount = byteCount || 0;
    this.tokenCount = tokenCount || 0;
    this.timestamp = timestamp;
  }

  toJSON() {
    return {
      sequence: this.sequence,
      byteCount: this.byteCount,
      tokenCount: this.tokenCount,
      timestamp: this.timestamp
    };
  }

  static fromJSON(data) {
    return new VelocitySample(
      data.sequence,
      data.byteCount,
      data.tokenCount,
      data.timestamp
    );
  }
}

// =============================================================================
// Visual State Entry
// =============================================================================

/** Represents a single entry in the visual state buffer */
export class VisualStateEntry {
  constructor({
    sequence,
    state,
    severity = InstrumentationSeverity.INFO,
    channel = VisualizationChannel.ASSISTANT,
    content = '',
    byteCount = 0,
    tokenCount = 0,
    data = {},
    metadata = {},
    timestamp = Date.now()
  }) {
    this.id = generateDeterministicId('vse', sequence, state, timestamp);
    this.sequence = sequence;
    this.state = state;
    this.severity = severity;
    this.channel = channel;
    this.content = content;
    this.byteCount = byteCount;
    this.tokenCount = tokenCount;
    this.data = data || {};
    this.metadata = metadata || {};
    this.timestamp = timestamp;
    // Derived values
    this.motionType = getMotionClassForState(state);
    this.color = getColorForSeverity(severity);
  }

  toJSON() {
    return {
      id: this.id,
      sequence: this.sequence,
      state: this.state,
      severity: this.severity,
      channel: this.channel,
      content: this.content,
      byteCount: this.byteCount,
      tokenCount: this.tokenCount,
      data: this.data,
      metadata: this.metadata,
      timestamp: this.timestamp,
      motionType: this.motionType,
      color: this.color
    };
  }

  static fromJSON(data) {
    return new VisualStateEntry(data);
  }
}

// =============================================================================
// Replay Frame
// =============================================================================

/** Represents a frame in replay visualization */
export class ReplayFrame {
  constructor({
    sequence,
    streamId,
    kind,
    content = '',
    channel = VisualizationChannel.ASSISTANT,
    severity = InstrumentationSeverity.INFO,
    timestamp,
    data = {},
    isMarker = false,
    isReconstructed = false
  }) {
    this.id = generateDeterministicId('replay', streamId, sequence, kind);
    this.sequence = sequence;
    this.streamId = streamId || 'unknown';
    this.kind = kind;
    this.content = content;
    this.channel = channel;
    this.severity = severity;
    this.timestamp = timestamp || Date.now();
    this.data = data || {};
    this.isMarker = isMarker || false;
    this.isReconstructed = isReconstructed || false;
    this.color = getColorForSeverity(severity);
  }

  toJSON() {
    return {
      id: this.id,
      sequence: this.sequence,
      streamId: this.streamId,
      kind: this.kind,
      content: this.content,
      channel: this.channel,
      severity: this.severity,
      timestamp: this.timestamp,
      data: this.data,
      isMarker: this.isMarker,
      isReconstructed: this.isReconstructed,
      color: this.color
    };
  }

  static fromJSON(data) {
    return new ReplayFrame(data);
  }
}

// =============================================================================
// Integrity Warning
// =============================================================================

/** Represents an integrity warning for visualization */
export class IntegrityWarning {
  constructor({
    code,
    message,
    severity = InstrumentationSeverity.WARNING,
    streamId = '',
    sequence,
    details = {},
    timestamp = Date.now()
  }) {
    this.id = generateDeterministicId('integrity', code, streamId, sequence || 0);
    this.code = code || 'unknown';
    this.message = message || '';
    this.severity = severity;
    this.streamId = streamId || '';
    this.sequence = sequence;
    this.details = details || {};
    this.timestamp = timestamp;
    this.color = getColorForSeverity(severity);
  }

  toJSON() {
    return {
      id: this.id,
      code: this.code,
      message: this.message,
      severity: this.severity,
      streamId: this.streamId,
      sequence: this.sequence,
      details: this.details,
      timestamp: this.timestamp,
      color: this.color
    };
  }

  static fromJSON(data) {
    return new IntegrityWarning(data);
  }
}

// =============================================================================
// Bounded Visual State Buffer
// =============================================================================

/** Bounded buffer for visual state entries */
export class VisualStateBuffer {
  constructor(maxEntries = MAX_VISUAL_STATE_ENTRIES, maxAgeMs = MAX_VISUAL_STATE_AGE_MS) {
    this.bufferId = generateDeterministicId('vsb', maxEntries, maxAgeMs);
    this.maxEntries = maxEntries;
    this.maxAgeMs = maxAgeMs;
    this.entries = [];
    this.oldestSequence = null;
    this.newestSequence = null;
    this.createdAt = Date.now();
    this.updatedAt = Date.now();
    this.evictedCount = 0;
    this.truncated = false;
  }

  /** Add a new entry, evicting old entries if needed */
  add(entry) {
    const newEntries = [...this.entries];
    let newEvicted = this.evictedCount;
    let newTruncated = this.truncated;

    // Evict entries that exceed max age
    const now = Date.now();
    const ageThreshold = now - this.maxAgeMs;
    while (newEntries.length > 0 && newEntries[0].timestamp < ageThreshold) {
      newEntries.shift();
      newEvicted++;
      newTruncated = true;
    }

    // Evict entries if we exceed max entries
    while (newEntries.length >= this.maxEntries) {
      newEntries.shift();
      newEvicted++;
      newTruncated = true;
    }

    // Add new entry
    newEntries.push(entry);

    // Update sequence tracking
    const sequences = newEntries.map(e => e.sequence).filter(s => s !== undefined && s !== null);
    const newOldest = sequences.length > 0 ? Math.min(...sequences) : null;
    const newNewest = sequences.length > 0 ? Math.max(...sequences) : null;

    return new VisualStateBuffer(
      this.maxEntries,
      this.maxAgeMs
    ) {
      bufferId: this.bufferId,
      entries: newEntries,
      oldestSequence: newOldest,
      newestSequence: newNewest,
      createdAt: this.createdAt,
      updatedAt: now,
      evictedCount: newEvicted,
      truncated: newTruncated
    };
  }

  /** Get entry by sequence */
  getBySequence(sequence) {
    return this.entries.find(e => e.sequence === sequence);
  }

  /** Get entry by ID */
  getById(id) {
    return this.entries.find(e => e.id === id);
  }

  /** Get all entries in sequence order */
  getAllOrdered() {
    return [...this.entries].sort((a, b) => a.sequence - b.sequence);
  }

  /** Get entries filtered by state */
  getByState(state) {
    return this.entries.filter(e => e.state === state);
  }

  /** Get entries filtered by severity */
  getBySeverity(severity) {
    return this.entries.filter(e => e.severity === severity);
  }

  /** Get the current state of the buffer */
  getCurrentState() {
    if (this.entries.length === 0) return RuntimeInstrumentationState.IDLE;
    return this.entries[this.entries.length - 1].state;
  }

  /** Check if buffer is empty */
  get isEmpty() {
    return this.entries.length === 0;
  }

  /** Get count of entries */
  get count() {
    return this.entries.length;
  }

  /** Get total byte count */
  get totalBytes() {
    return this.entries.reduce((sum, e) => sum + (e.byteCount || 0), 0);
  }

  /** Get total token count */
  get totalTokens() {
    return this.entries.reduce((sum, e) => sum + (e.tokenCount || 0), 0);
  }

  toJSON() {
    return {
      bufferId: this.bufferId,
      maxEntries: this.maxEntries,
      maxAgeMs: this.maxAgeMs,
      entries: this.entries.map(e => e.toJSON()),
      oldestSequence: this.oldestSequence,
      newestSequence: this.newestSequence,
      createdAt: this.createdAt,
      updatedAt: this.updatedAt,
      evictedCount: this.evictedCount,
      truncated: this.truncated,
      count: this.count,
      totalBytes: this.totalBytes,
      totalTokens: this.totalTokens
    };
  }

  static fromJSON(data) {
    const buffer = new VisualStateBuffer(
      data.maxEntries || MAX_VISUAL_STATE_ENTRIES,
      data.maxAgeMs || MAX_VISUAL_STATE_AGE_MS
    );
    buffer.bufferId = data.bufferId;
    buffer.entries = (data.entries || []).map(e => VisualStateEntry.fromJSON(e));
    buffer.oldestSequence = data.oldestSequence;
    buffer.newestSequence = data.newestSequence;
    buffer.createdAt = data.createdAt;
    buffer.updatedAt = data.updatedAt;
    buffer.evictedCount = data.evictedCount || 0;
    buffer.truncated = data.truncated || false;
    return buffer;
  }
}

// =============================================================================
// Velocity Tracker
// =============================================================================

/** Tracks stream velocity for throughput visualization */
export class VelocityTracker {
  constructor(maxSamples = MAX_VELOCITY_SAMPLES) {
    this.trackerId = generateDeterministicId('vel', maxSamples);
    this.maxSamples = maxSamples;
    this.samples = [];
    this.startTime = null;
    this.endTime = null;
    this.totalBytes = 0;
    this.totalTokens = 0;
    this.createdAt = Date.now();
    this.updatedAt = Date.now();
  }

  /** Add a new sample */
  addSample(sequence, byteCount, tokenCount, timestamp = Date.now()) {
    const sample = new VelocitySample(sequence, byteCount, tokenCount, timestamp);

    const newSamples = [...this.samples];
    
    // Keep only recent samples
    while (newSamples.length >= this.maxSamples) {
      newSamples.shift();
    }
    
    newSamples.push(sample);

    // Update tracking
    const timestamps = newSamples.map(s => s.timestamp);
    const newStartTime = timestamps.length > 0 ? Math.min(...timestamps) : null;
    const newEndTime = timestamps.length > 0 ? Math.max(...timestamps) : null;
    const newTotalBytes = newSamples.reduce((sum, s) => sum + s.byteCount, 0);
    const newTotalTokens = newSamples.reduce((sum, s) => sum + s.tokenCount, 0);

    return new VelocityTracker(this.maxSamples) {
      trackerId: this.trackerId,
      samples: newSamples,
      startTime: newStartTime,
      endTime: newEndTime,
      totalBytes: newTotalBytes,
      totalTokens: newTotalTokens,
      createdAt: this.createdAt,
      updatedAt: timestamp
    };
  }

  /** Calculate average bytes per second */
  getBytesPerSecond() {
    if (!this.startTime || !this.endTime || this.endTime <= this.startTime) {
      return 0;
    }
    const duration = (this.endTime - this.startTime) / 1000; // Convert to seconds
    if (duration <= 0) return 0;
    return this.totalBytes / duration;
  }

  /** Calculate average tokens per second */
  getTokensPerSecond() {
    if (!this.startTime || !this.endTime || this.endTime <= this.startTime) {
      return 0;
    }
    const duration = (this.endTime - this.startTime) / 1000; // Convert to seconds
    if (duration <= 0) return 0;
    return this.totalTokens / duration;
  }

  /** Calculate average chunk interval in ms */
  getAverageChunkInterval() {
    if (this.samples.length < 2) return 0;
    let totalInterval = 0;
    for (let i = 1; i < this.samples.length; i++) {
      totalInterval += this.samples[i].timestamp - this.samples[i - 1].timestamp;
    }
    return totalInterval / (this.samples.length - 1);
  }

  /** Get the current velocity normalized (0-1) */
  getNormalizedVelocity(maxExpectedSeconds = 1000) {
    const bps = this.getBytesPerSecond();
    return clamp(bps / maxExpectedSeconds, 0, 1);
  }

  /** Get velocity samples in time order */
  getSamplesOrdered() {
    return [...this.samples].sort((a, b) => b.timestamp - a.timestamp);
  }

  toJSON() {
    return {
      trackerId: this.trackerId,
      maxSamples: this.maxSamples,
      samples: this.samples.map(s => s.toJSON()),
      startTime: this.startTime,
      endTime: this.endTime,
      totalBytes: this.totalBytes,
      totalTokens: this.totalTokens,
      createdAt: this.createdAt,
      updatedAt: this.updatedAt
    };
  }

  static fromJSON(data) {
    const tracker = new VelocityTracker(data.maxSamples || MAX_VELOCITY_SAMPLES);
    tracker.trackerId = data.trackerId;
    tracker.samples = (data.samples || []).map(s => VelocitySample.fromJSON(s));
    tracker.startTime = data.startTime;
    tracker.endTime = data.endTime;
    tracker.totalBytes = data.totalBytes || 0;
    tracker.totalTokens = data.totalTokens || 0;
    tracker.createdAt = data.createdAt;
    tracker.updatedAt = data.updatedAt;
    return tracker;
  }
}

// =============================================================================
// Replay Frame Buffer
// =============================================================================

/** Bounded buffer for replay frames */
export class ReplayFrameBuffer {
  constructor(maxFrames = MAX_REPLAY_FRAMES) {
    this.bufferId = generateDeterministicId('rfb', maxFrames);
    this.maxFrames = maxFrames;
    this.frames = [];
    this.streamIds = new Set();
    this.createdAt = Date.now();
    this.updatedAt = Date.now();
    this.markers = new Set();
    this.reconstructedFrames = new Set();
  }

  /** Add a frame or array of frames */
  add(frameOrFrames) {
    const frames = Array.isArray(frameOrFrames) ? frameOrFrames : [frameOrFrames];
    const newFrames = [...this.frames];
    const newStreamIds = new Set(this.streamIds);
    const newMarkers = new Set(this.markers);
    const newReconstructed = new Set(this.reconstructedFrames);

    for (const frame of frames) {
      // Evict if we exceed max frames
      while (newFrames.length >= this.maxFrames) {
        const removed = newFrames.shift();
        newReconstructed.delete(removed.id);
        newMarkers.delete(removed.id);
      }

      newFrames.push(frame);
      if (frame.streamId) newStreamIds.add(frame.streamId);
      if (frame.isMarker) newMarkers.add(frame.id);
      if (frame.isReconstructed) newReconstructed.add(frame.id);
    }

    return new ReplayFrameBuffer(this.maxFrames) {
      bufferId: this.bufferId,
      frames: newFrames,
      streamIds: newStreamIds,
      createdAt: this.createdAt,
      updatedAt: Date.now(),
      markers: newMarkers,
      reconstructedFrames: newReconstructed
    };
  }

  /** Get frames for a specific stream */
  getByStream(streamId) {
    return this.frames.filter(f => f.streamId === streamId);
  }

  /** Get all frames in sequence order */
  getAllOrdered() {
    return [...this.frames].sort((a, b) => a.sequence - b.sequence);
  }

  /** Get marker frames */
  getMarkers() {
    return this.frames.filter(f => f.isMarker);
  }

  /** Get reconstructed frames */
  getReconstructed() {
    return this.frames.filter(f => f.isReconstructed);
  }

  /** Get the current scrub position */
  getScrubPosition() {
    if (this.frames.length === 0) return 0;
    const lastSequence = Math.max(...this.frames.map(f => f.sequence));
    const firstSequence = Math.min(...this.frames.map(f => f.sequence));
    return lastSequence - firstSequence + 1;
  }

  toJSON() {
    return {
      bufferId: this.bufferId,
      maxFrames: this.maxFrames,
      frames: this.frames.map(f => f.toJSON()),
      streamIds: Array.from(this.streamIds),
      createdAt: this.createdAt,
      updatedAt: this.updatedAt,
      markerIds: Array.from(this.markers),
      reconstructedFrameIds: Array.from(this.reconstructedFrames)
    };
  }

  static fromJSON(data) {
    const buffer = new ReplayFrameBuffer(data.maxFrames || MAX_REPLAY_FRAMES);
    buffer.bufferId = data.bufferId;
    buffer.frames = (data.frames || []).map(f => ReplayFrame.fromJSON(f));
    buffer.streamIds = new Set(data.streamIds || []);
    buffer.createdAt = data.createdAt;
    buffer.updatedAt = data.updatedAt;
    buffer.markers = new Set(data.markerIds || []);
    buffer.reconstructedFrames = new Set(data.reconstructedFrameIds || []);
    return buffer;
  }
}

// =============================================================================
// Integrity Warning Buffer
// =============================================================================

/** Bounded buffer for integrity warnings */
export class IntegrityWarningBuffer {
  constructor(maxWarnings = MAX_INTEGRITY_WARNINGS) {
    this.bufferId = generateDeterministicId('iwb', maxWarnings);
    this.maxWarnings = maxWarnings;
    this.warnings = [];
    this.createdAt = Date.now();
    this.updatedAt = Date.now();
  }

  /** Add a warning */
  add(warning) {
    const newWarnings = [...this.warnings];
    
    // Remove warnings with the same code and stream
    newWarnings.filter(w => 
      !(w.code === warning.code && w.streamId === warning.streamId)
    );
    
    // Evict if we exceed max warnings
    while (newWarnings.length >= this.maxWarnings) {
      newWarnings.shift();
    }
    
    newWarnings.push(warning);

    return new IntegrityWarningBuffer(this.maxWarnings) {
      bufferId: this.bufferId,
      warnings: newWarnings,
      createdAt: this.createdAt,
      updatedAt: Date.now()
    };
  }

  /** Get warnings for a specific stream */
  getByStream(streamId) {
    return this.warnings.filter(w => w.streamId === streamId);
  }

  /** Get warnings by severity */
  getBySeverity(severity) {
    return this.warnings.filter(w => w.severity === severity);
  }

  /** Get warnings by code */
  getByCode(code) {
    return this.warnings.filter(w => w.code === code);
  }

  /** Check if there are any critical warnings */
  get hasCritical() {
    return this.warnings.some(w => w.severity === InstrumentationSeverity.CRITICAL);
  }

  /** Check if there are any errors */
  get hasErrors() {
    return this.warnings.some(w => w.severity === InstrumentationSeverity.ERROR);
  }

  toJSON() {
    return {
      bufferId: this.bufferId,
      maxWarnings: this.maxWarnings,
      warnings: this.warnings.map(w => w.toJSON()),
      createdAt: this.createdAt,
      updatedAt: this.updatedAt
    };
  }

  static fromJSON(data) {
    const buffer = new IntegrityWarningBuffer(data.maxWarnings || MAX_INTEGRITY_WARNINGS);
    buffer.bufferId = data.bufferId;
    buffer.warnings = (data.warnings || []).map(w => IntegrityWarning.fromJSON(w));
    buffer.createdAt = data.createdAt;
    buffer.updatedAt = data.updatedAt;
    return buffer;
  }
}

// =============================================================================
// Stateful Loading System
// =============================================================================

/** Represents a stateful loading indicator */
export class StatefulLoader {
  constructor({
    id,
    state = RuntimeInstrumentationState.IDLE,
    message = '',
    progress = 0,
    severity = InstrumentationSeverity.INFO,
    context = {}
  }) {
    this.id = id || generateDeterministicId('loader', Date.now());
    this.state = state;
    this.message = message;
    this.progress = clamp(progress, 0, 100);
    this.severity = severity;
    this.context = context || {};
    this.startTime = Date.now();
    this.lastUpdate = Date.now();
    this.color = getColorForSeverity(severity);
  }

  /** Update the loader state */
  update({ state, message, progress, severity, context }) {
    return new StatefulLoader({
      id: this.id,
      state: state || this.state,
      message: message || this.message,
      progress: progress !== undefined ? clamp(progress, 0, 100) : this.progress,
      severity: severity || this.severity,
      context: context || this.context
    }) {
      startTime: this.startTime,
      lastUpdate: Date.now()
    };
  }

  /** Derive progress from projection data */
  static fromProjection(projection) {
    const data = projection || {};
    const state = data.state || RuntimeInstrumentationState.IDLE;
    const severity = data.severity || InstrumentationSeverity.INFO;
    const message = data.message || '';
    
    // Calculate progress from available data
    let progress = 0;
    if (data.total_tokens && data.current_tokens) {
      progress = clamp((data.current_tokens / data.total_tokens) * 100, 0, 100);
    } else if (data.total_chunks && data.current_chunks) {
      progress = clamp((data.current_chunks / data.total_chunks) * 100, 0, 100);
    } else if (data.percent_complete !== undefined) {
      progress = clamp(data.percent_complete, 0, 100);
    }

    return new StatefulLoader({
      id: data.id || generateDeterministicId('loader', data.stream_id || Date.now()),
      state,
      message,
      progress,
      severity,
      context: data
    });
  }

  toJSON() {
    return {
      id: this.id,
      state: this.state,
      message: this.message,
      progress: this.progress,
      severity: this.severity,
      context: this.context,
      startTime: this.startTime,
      lastUpdate: this.lastUpdate,
      color: this.color
    };
  }

  static fromJSON(data) {
    return new StatefulLoader(data);
  }
}

// =============================================================================
// Runtime Instrumentation State Machine
// =============================================================================

/** Main instrumentation state machine for runtime visualization */
export class RuntimeInstrumentation {
  constructor({
    id,
    streamId,
    invocationId,
    providerId,
    maxEntries = MAX_VISUAL_STATE_ENTRIES,
    maxVelocitySamples = MAX_VELOCITY_SAMPLES,
    maxReplayFrames = MAX_REPLAY_FRAMES,
    maxWarnings = MAX_INTEGRITY_WARNINGS
  }) {
    // Identifiers
    this.id = id || generateDeterministicId('instrumentation', streamId, invocationId, Date.now());
    this.streamId = streamId || '';
    this.invocationId = invocationId || '';
    this.providerId = providerId || '';

    // Buffers
    this.visualStateBuffer = new VisualStateBuffer(maxEntries);
    this.velocityTracker = new VelocityTracker(maxVelocitySamples);
    this.replayFrameBuffer = new ReplayFrameBuffer(maxReplayFrames);
    this.integrityWarningBuffer = new IntegrityWarningBuffer(maxWarnings);

    // Stateful loaders
    this.loaders = new Map();

    // Current state
    this.currentState = RuntimeInstrumentationState.IDLE;
    this.currentSeverity = InstrumentationSeverity.INFO;
    this.lastSequence = -1;
    this.totalSequences = 0;

    // Statistics
    this.totalBytes = 0;
    this.totalTokens = 0;
    this.totalChunks = 0;

    // Timing
    this.startTime = null;
    this.endTime = null;
    this.lastUpdateTime = Date.now();
    this.createdAt = Date.now();
    this.updatedAt = Date.now();

    // Replay state
    this.isReplaying = false;
    this.replayPosition = 0;
    this.replayTotal = 0;

    // Capability routing state
    this.currentRuntime = null;
    this.currentCapabilities = [];
    this.currentTrustLevel = null;

    // Motion state
    this.currentMotionType = MotionType.NONE;
    this.motionIntensity = 0;

    //.ts for rate limiting state updates
    this.lastStateUpdateTime = 0;
  }

  /** Handle a stream event from WebSocket or projection */
  handleEvent(event) {
    // Rate limit state updates
    const now = Date.now();
    if (now - this.lastStateUpdateTime < MIN_STATE_UPDATE_INTERVAL_MS) {
      return this; // Skip rapid updates
    }
    this.lastStateUpdateTime = now;

    // Determine event type and process accordingly
    const kind = event.kind || event.type || '';
    const sequence = event.sequence !== undefined ? event.sequence : this.lastSequence + 1;
    const streamId = event.stream_id || this.streamId || '';
    const content = event.content || event.data?.content || '';
    const channel = event.channel || VisualizationChannel.ASSISTANT;
    const severity = event.severity || InstrumentationSeverity.INFO;
    const byteCount = event.byte_count || event.data?.byte_count || 0;
    const tokenCount = event.token_count || event.data?.token_count || 0;

    // Track sequence
    if (sequence > this.lastSequence) {
      this.lastSequence = sequence;
      this.totalSequences++;
    }

    // Track statistics
    this.totalBytes += byteCount;
    this.totalTokens += tokenCount;
    this.totalChunks++;

    // Track timing
    const timestamp = event.timestamp || Date.now();
    if (!this.startTime || timestamp < this.startTime) {
      this.startTime = timestamp;
    }
    if (!this.endTime || timestamp > this.endTime) {
      this.endTime = timestamp;
    }

    // Update velocity tracker
    this.velocityTracker = this.velocityTracker.addSample(
      sequence,
      byteCount,
      tokenCount,
      timestamp
    );

    // Determine state from event
    let state = this.currentState;
    
    switch (kind) {
      case 'chunk':
      case WS_MSG_TYPE_STREAM_CHUNK:
        state = RuntimeInstrumentationState.STREAMING;
        break;

      case 'status':
      case WS_MSG_TYPE_STREAM_STATUS:
        // Map status to instrumentation state
        const status = (event.data?.status || event.status || '').toLowerCase();
        if (status === 'active') state = RuntimeInstrumentationState.STREAMING;
        else if (status === 'completed') state = RuntimeInstrumentationState.COMPLETION;
        else if (status === 'failed') state = RuntimeInstrumentationState.FAILURE;
        else if (status === 'paused' || status === 'stalled') state = RuntimeInstrumentationState.STALLED;
        else if (status === 'pending') state = RuntimeInstrumentationState.PLANNING;
        break;

      case 'proposal':
      case WS_MSG_TYPE_STREAM_PROPOSAL:
      case 'tool_proposal':
      case 'patch_proposal':
        state = RuntimeInstrumentationState.PROPOSING;
        break;

      case 'warning':
      case WS_MSG_TYPE_STREAM_WARNING:
        state = RuntimeInstrumentationState.INTEGRITY_WARNING;
        break;

      case 'completion':
      case WS_MSG_TYPE_STREAM_COMPLETE:
        state = RuntimeInstrumentationState.COMPLETION;
        break;

      case 'failure':
      case WS_MSG_TYPE_STREAM_FAILURE:
        state = RuntimeInstrumentationState.FAILURE;
        break;

      case 'heartbeat':
      case WS_MSG_TYPE_STREAM_HEARTBEAT:
        // Heartbeats don't change state but update timing
        break;
    }

    // Handle capability routing info
    if (event.capability_ids || event.capabilities) {
      const capabilities = event.capability_ids || event.capabilities || [];
      this.currentCapabilities = Array.isArray(capabilities) ? capabilities : [capabilities];
    }
    if (event.runtime_id || event.provider_id) {
      this.currentRuntime = event.runtime_id || event.provider_id || this.currentRuntime;
    }
    if (event.trust_tier || event.trust_level) {
      this.currentTrustLevel = event.trust_tier || event.trust_level || this.currentTrustLevel;
    }

    // Create visual state entry
    const entry = new VisualStateEntry({
      sequence,
      state,
      severity,
      channel,
      content,
      byteCount,
      tokenCount,
      data: event.data || {},
      metadata: event.metadata || {},
      timestamp
    });

    // Add to visual state buffer
    this.visualStateBuffer = this.visualStateBuffer.add(entry);

    // Update current state
    this.currentState = state;
    this.currentSeverity = severity;
    this.currentMotionType = getMotionClassForState(state);

    // Update motion intensity based on velocity
    this.motionIntensity = this.velocityTracker.getNormalizedVelocity();

    // Update timestamps
    this.lastUpdateTime = timestamp;
    this.updatedAt = now;

    return this;
  }

  /** Handle a projection update */
  handleProjection(projection) {
    const event = {
      kind: projection.kind,
      sequence: projection.sequence,
      stream_id: projection.stream_id,
      invocation_id: projection.invocation_id,
      provider_id: projection.provider_id,
      content: projection.content,
      channel: projection.channel,
      severity: projection.severity,
      byte_count: projection.byte_count,
      token_count: projection.token_count,
      data: projection.metadata || {},
      timestamp: projection.timestamp
    };
    return this.handleEvent(event);
  }

  /** Handle a WebSocket message */
  handleWebSocketMessage(message) {
    // Normalize message
    const normalized = this.normalizeMessage(message);
    return this.handleEvent(normalized);
  }

  /** Normalize a WebSocket message */
  normalizeMessage(message) {
    return {
      kind: message.kind || '',
      sequence: message.sequence,
      stream_id: message.stream_id || message.streamId,
      invocation_id: message.invocation_id || message.invocationId,
      provider_id: message.provider_id || message.providerId,
      content: message.data?.content || message.content || '',
      channel: message.channel || message.data?.channel || VisualizationChannel.ASSISTANT,
      severity: message.severity || message.data?.severity || InstrumentationSeverity.INFO,
      byte_count: message.data?.byte_count || message.byteCount || 0,
      token_count: message.data?.token_count || message.tokenCount || 0,
      data: message.data || {},
      metadata: message.metadata || {},
      timestamp: message.timestamp || Date.now()
    };
  }

  /** Add a replay frame */
  addReplayFrame(frame) {
    this.replayFrameBuffer = this.replayFrameBuffer.add(frame);
    this.isReplaying = true;
    this.replayTotal = this.replayFrameBuffer.frames.length;
    this.updatedAt = Date.now();
    return this;
  }

  /** Set replay position */
  setReplayPosition(position) {
    this.replayPosition = clamp(position, 0, this.replayTotal);
    this.updatedAt = Date.now();
    return this;
  }

  /** Add an integrity warning */
  addIntegrityWarning(warning) {
    const warningObj = warning instanceof IntegrityWarning ? warning : new IntegrityWarning(warning);
    this.integrityWarningBuffer = this.integrityWarningBuffer.add(warningObj);
    
    // If warning is critical or error, update state
    if ([InstrumentationSeverity.CRITICAL, InstrumentationSeverity.ERROR].includes(warningObj.severity)) {
      this.currentState = RuntimeInstrumentationState.INTEGRITY_WARNING;
      this.currentSeverity = warningObj.severity;
    }
    
    this.updatedAt = Date.now();
    return this;
  }

  /** Update capability routing state */
  updateCapabilityRouting({ runtime, capabilities, trustLevel }) {
    this.currentRuntime = runtime || this.currentRuntime;
    this.currentCapabilities = capabilities || this.currentCapabilities;
    this.currentTrustLevel = trustLevel || this.currentTrustLevel;
    
    if (runtime || capabilities?.length > 0 || trustLevel) {
      this.currentState = RuntimeInstrumentationState.CAPABILITY_ROUTING;
    }
    
    this.updatedAt = Date.now();
    return this;
  }

  /** Get a stateful loader for a specific context */
  getLoader(contextId) {
    if (!this.loaders.has(contextId)) {
      this.loaders.set(contextId, new StatefulLoader({ id: contextId }));
    }
    return this.loaders.get(contextId);
  }

  /** Update a stateful loader */
  updateLoader(contextId, updates) {
    const loader = this.getLoader(contextId);
    const updated = loader.update(updates);
    this.loaders.set(contextId, updated);
    this.updatedAt = Date.now();
    return updated;
  }

  /** Remove a stateful loader */
  removeLoader(contextId) {
    this.loaders.delete(contextId);
    this.updatedAt = Date.now();
    return this;
  }

  /** Get the current motion parameters for animation */
  getMotionParams() {
    return {
      type: this.currentMotionType,
      intensity: this.motionIntensity,
      state: this.currentState,
      velocity: this.velocityTracker.getBytesPerSecond(),
      tokenRate: this.velocityTracker.getTokensPerSecond()
    };
  }

  /** Get stream velocity info */
  getStreamVelocity() {
    return {
      bytesPerSecond: this.velocityTracker.getBytesPerSecond(),
      tokensPerSecond: this.velocityTracker.getTokensPerSecond(),
      averageChunkInterval: this.velocityTracker.getAverageChunkInterval(),
      normalizedVelocity: this.velocityTracker.getNormalizedVelocity(),
      samples: this.velocityTracker.getSamplesOrdered()
    };
  }

  /** Get current statistics */
  getStats() {
    return {
      totalBytes: this.totalBytes,
      totalTokens: formatTokens(this.totalTokens),
      totalChunks: this.totalChunks,
      totalSequences: this.totalSequences,
      lastSequence: this.lastSequence,
      durationMs: this.endTime && this.startTime ? this.endTime - this.startTime : 0
    };
  }

  /** Get replay state */
  getReplayState() {
    return {
      isReplaying: this.isReplaying,
      position: this.replayPosition,
      total: this.replayTotal,
      frames: this.replayFrameBuffer.getAllOrdered(),
      markers: this.replayFrameBuffer.getMarkers(),
      reconstructedCount: this.replayFrameBuffer.getReconstructed().length
    };
  }

  /** Get integrity state */
  getIntegrityState() {
    return {
      warnings: this.integrityWarningBuffer.warnings,
      hasCritical: this.integrityWarningBuffer.hasCritical,
      hasErrors: this.integrityWarningBuffer.hasErrors,
      criticalCount: this.integrityWarningBuffer.warnings.filter(
        w => w.severity === InstrumentationSeverity.CRITICAL
      ).length,
      errorCount: this.integrityWarningBuffer.warnings.filter(
        w => w.severity === InstrumentationSeverity.ERROR
      ).length,
      warningCount: this.integrityWarningBuffer.warnings.filter(
        w => w.severity === InstrumentationSeverity.WARNING
      ).length
    };
  }

  /** Get capability routing state */
  getCapabilityRoutingState() {
    return {
      runtime: this.currentRuntime,
      capabilities: this.currentCapabilities,
      trustLevel: this.currentTrustLevel
    };
  }

  /** Get current state summary */
  getStateSummary() {
    return {
      state: this.currentState,
      severity: this.currentSeverity,
      color: getColorForSeverity(this.currentSeverity),
      motionType: this.currentMotionType,
      motionIntensity: this.motionIntensity
    };
  }

  /** Reset the instrumentation state */
  reset({
    streamId,
    invocationId,
    providerId,
    resetBuffers = true,
    resetStats = true
  }) {
    const keep = { id: this.id };
    
    if (streamId !== undefined) this.streamId = streamId;
    if (invocationId !== undefined) this.invocationId = invocationId;
    if (providerId !== undefined) this.providerId = providerId;

    if (resetBuffers) {
      this.visualStateBuffer = new VisualStateBuffer(this.visualStateBuffer.maxEntries);
      this.velocityTracker = new VelocityTracker(this.velocityTracker.maxSamples);
      this.replayFrameBuffer = new ReplayFrameBuffer(this.replayFrameBuffer.maxFrames);
      this.integrityWarningBuffer = new IntegrityWarningBuffer(this.integrityWarningBuffer.maxWarnings);
    }

    if (resetStats) {
      this.currentState = RuntimeInstrumentationState.IDLE;
      this.currentSeverity = InstrumentationSeverity.INFO;
      this.lastSequence = -1;
      this.totalSequences = 0;
      this.totalBytes = 0;
      this.totalTokens = 0;
      this.totalChunks = 0;
      this.startTime = null;
      this.endTime = null;
    }

    this.loaders.clear();
    this.isReplaying = false;
    this.replayPosition = 0;
    this.replayTotal = 0;
    this.currentRuntime = null;
    this.currentCapabilities = [];
    this.currentTrustLevel = null;
    this.currentMotionType = MotionType.NONE;
    this.motionIntensity = 0;
    this.lastStateUpdateTime = 0;

    this.updatedAt = Date.now();

    return this;
  }

  toJSON() {
    return {
      id: this.id,
      streamId: this.streamId,
      invocationId: this.invocationId,
      providerId: this.providerId,
      currentState: this.currentState,
      currentSeverity: this.currentSeverity,
      lastSequence: this.lastSequence,
      totalSequences: this.totalSequences,
      totalBytes: this.totalBytes,
      totalTokens: this.totalTokens,
      totalChunks: this.totalChunks,
      startTime: this.startTime,
      endTime: this.endTime,
      createdAt: this.createdAt,
      updatedAt: this.updatedAt,
      isReplaying: this.isReplaying,
      replayPosition: this.replayPosition,
      replayTotal: this.replayTotal,
      currentRuntime: this.currentRuntime,
      currentCapabilities: this.currentCapabilities,
      currentTrustLevel: this.currentTrustLevel,
      currentMotionType: this.currentMotionType,
      motionIntensity: this.motionIntensity,
      visualStateBuffer: this.visualStateBuffer.toJSON(),
      velocityTracker: this.velocityTracker.toJSON(),
      replayFrameBuffer: this.replayFrameBuffer.toJSON(),
      integrityWarningBuffer: this.integrityWarningBuffer.toJSON()
    };
  }

  static fromJSON(data) {
    const inst = new RuntimeInstrumentation({
      id: data.id,
      streamId: data.streamId,
      invocationId: data.invocationId,
      providerId: data.providerId,
      maxEntries: data.visualStateBuffer?.maxEntries,
      maxVelocitySamples: data.velocityTracker?.maxSamples,
      maxReplayFrames: data.replayFrameBuffer?.maxFrames,
      maxWarnings: data.integrityWarningBuffer?.maxWarnings
    });

    // Restore buffers
    if (data.visualStateBuffer) {
      inst.visualStateBuffer = VisualStateBuffer.fromJSON(data.visualStateBuffer);
    }
    if (data.velocityTracker) {
      inst.velocityTracker = VelocityTracker.fromJSON(data.velocityTracker);
    }
    if (data.replayFrameBuffer) {
      inst.replayFrameBuffer = ReplayFrameBuffer.fromJSON(data.replayFrameBuffer);
    }
    if (data.integrityWarningBuffer) {
      inst.integrityWarningBuffer = IntegrityWarningBuffer.fromJSON(data.integrityWarningBuffer);
    }

    // Restore state
    inst.currentState = data.currentState || RuntimeInstrumentationState.IDLE;
    inst.currentSeverity = data.currentSeverity || InstrumentationSeverity.INFO;
    inst.lastSequence = data.lastSequence || -1;
    inst.totalSequences = data.totalSequences || 0;
    inst.totalBytes = data.totalBytes || 0;
    inst.totalTokens = data.totalTokens || 0;
    inst.totalChunks = data.totalChunks || 0;
    inst.startTime = data.startTime;
    inst.endTime = data.endTime;
    inst.createdAt = data.createdAt;
    inst.updatedAt = data.updatedAt;
    inst.isReplaying = data.isReplaying || false;
    inst.replayPosition = data.replayPosition || 0;
    inst.replayTotal = data.replayTotal || 0;
    inst.currentRuntime = data.currentRuntime;
    inst.currentCapabilities = data.currentCapabilities || [];
    inst.currentTrustLevel = data.currentTrustLevel;
    inst.currentMotionType = data.currentMotionType || MotionType.NONE;
    inst.motionIntensity = data.motionIntensity || 0;

    return inst;
  }
}

// =============================================================================
// Motion Animation Functions
// =============================================================================

/** Animation utilities for truthful motion */
export const MotionUtils = {
  /** Determine whether the runtime should use low-stimulation motion */
  getLowStimulationMode: function(context = {}) {
    const density = clamp(context.density || 0, 0, 1);
    const overload = clamp(context.overload || 0, 0, 1);
    const reducedMotion = Boolean(context.reducedMotion);
    return reducedMotion || density >= 0.6 || overload >= 0.5;
  },

  /** Calculate density collapse state for overloaded views */
  calculateDensityCollapse: function(chunkCount, laneCount, violationCount = 0) {
    const chunks = clamp(chunkCount, 0, 500);
    const lanes = clamp(laneCount, 0, 16);
    const violations = clamp(violationCount, 0, 50);
    const densityScore = clamp((chunks / 250) * 0.5 + (lanes / 8) * 0.3 + (violations / 20) * 0.2, 0, 1);

    return {
      density: densityScore,
      shouldCollapse: densityScore >= 0.55,
      abstractionLevel: densityScore >= 0.85 ? 'extreme' : densityScore >= 0.7 ? 'high' : densityScore >= 0.55 ? 'medium' : 'low',
      visibleDetail: densityScore >= 0.85 ? 'summary' : densityScore >= 0.7 ? 'collapsed' : densityScore >= 0.55 ? 'condensed' : 'full'
    };
  },

  /** Calculate geometric pulse cadence based on velocity */
  calculatePulseCadence: function(velocity, intensity) {
    const clampedVelocity = clamp(velocity, 0, 1000);
    const clampedIntensity = clamp(intensity, 0, 1);
    const overloaded = clampedVelocity > 600 || clampedIntensity > 0.75;
    
    const duration = overloaded
      ? lerp(2200, 1400, clampedIntensity)
      : lerp(2000, 500, clampedIntensity);
    const scale = overloaded
      ? lerp(1.0, 1.03, clampedIntensity)
      : lerp(1.0, 1.15, clampedIntensity);
    
    return {
      duration: `${duration}ms`,
      scale: scale,
      opacity: overloaded ? lerp(0.45, 0.8, clampedIntensity) : lerp(0.5, 1.0, clampedIntensity)
    };
  },

  /** Calculate stream density indicators */
  calculateStreamDensity: function(chunkCount, velocity) {
    const clampedChunkCount = clamp(chunkCount, 0, 100);
    const clampedVelocity = clamp(velocity, 0, 1000);
    
    const density = clamp(clampedChunkCount * clampedVelocity / 100000, 0, 1);
    const collapse = density >= 0.5;
    
    return {
      density: density,
      gap: collapse ? lerp(4, 2, density) : lerp(4, 0, density),
      opacity: collapse ? lerp(0.35, 0.65, density) : lerp(0.3, 1.0, density),
      collapsed: collapse
    };
  },

  /** Calculate throughput modulation */
  calculateThroughputModulation: function(bytesPerSecond, tokensPerSecond) {
    const bps = clamp(bytesPerSecond, 0, 10000);
    const tps = clamp(tokensPerSecond, 0, 100);
    
    // Normalize to 0-1
    const normalizedBPS = clamp(bps / 10000, 0, 1);
    const normalizedTPS = clamp(tps / 100, 0, 1);
    
    // Combine both metrics
    const combined = (normalizedBPS + normalizedTPS) / 2;
    
    const overloaded = combined > 0.7;

    return {
      intensity: combined,
      colorIntensity: overloaded ? lerp(0, 70, combined) : lerp(0, 100, combined),
      barWidth: overloaded ? lerp(2, 5, combined) : lerp(2, 8, combined),
      reducedMotion: overloaded
    };
  },

  /** Calculate bounded historical visualization parameters */
  calculateHistoricalBounds: function(bufferSize, maxEntries) {
    const clampedSize = clamp(bufferSize, 0, maxEntries);
    const ratio = clampedSize / maxEntries;
    
    return {
      visibleCount: clampedSize,
      hiddenCount: Math.max(0, bufferSize - maxEntries),
      scrollPercentage: ratio * 100,
      truncationIndicator: bufferSize > maxEntries
    };
  },

  /** Calculate replay scrub state */
  calculateReplayScrub: function(position, total, isReplaying) {
    const clampedPosition = clamp(position, 0, total);
    const percentage = total > 0 ? (clampedPosition / total) * 100 : 0;
    
    return {
      position: clampedPosition,
      total: total,
      percentage: percentage,
      isAtStart: clampedPosition === 0,
      isAtEnd: clampedPosition >= total,
      isReplaying: isReplaying,
      pace: total > 0 && isReplaying ? lerp(0.9, 0.4, clampedPosition / total) : 1
    };
  },

  /** Calculate geometric visualization for runtime state */
  calculateRuntimeGeometricState: function(state, channel, severity) {
    const lowStim = MotionUtils.getLowStimulationMode({
      density: severity === InstrumentationSeverity.WARNING ? 0.6 : 0.2,
      overload: severity === InstrumentationSeverity.ERROR || severity === InstrumentationSeverity.CRITICAL ? 0.8 : 0,
      reducedMotion: channel === 'system'
    });
    switch (state) {
      case RuntimeInstrumentationState.STREAMING:
        return {
          shape: 'rectangle',
          motion: lowStim ? 'steady' : 'flow',
          direction: 'horizontal',
          color: getColorForSeverity(severity)
        };
      case RuntimeInstrumentationState.PROPOSING:
        return {
          shape: 'circle',
          motion: lowStim ? 'fade' : 'pulse',
          direction: 'none',
          color: getColorForSeverity(severity)
        };
      case RuntimeInstrumentationState.VALIDATING:
        return {
          shape: 'triangle',
          motion: lowStim ? 'hold' : 'rotate',
          direction: 'clockwise',
          color: getColorForSeverity(severity)
        };
      case RuntimeInstrumentationState.REPLAYING:
        return {
          shape: 'line',
          motion: lowStim ? 'snap' : 'scroll',
          direction: 'horizontal',
          color: getColorForSeverity(severity)
        };
      case RuntimeInstrumentationState.STALLED:
        return {
          shape: 'dash',
          motion: 'none',
          direction: 'none',
          color: getColorForSeverity(InstrumentationSeverity.WARNING)
        };
      case RuntimeInstrumentationState.FAILURE:
        return {
          shape: 'cross',
          motion: 'none',
          direction: 'none',
          color: getColorForSeverity(InstrumentationSeverity.ERROR)
        };
      case RuntimeInstrumentationState.COMPLETION:
        return {
          shape: 'check',
          motion: 'fade-in',
          direction: 'none',
          color: getColorForSeverity(InstrumentationSeverity.INFO)
        };
      default:
        return {
          shape: 'square',
          motion: 'none',
          direction: 'none',
          color: getColorForSeverity(InstrumentationSeverity.INFO)
        };
    }
  }
};

// =============================================================================
// WebSocket Message Types (from runtime_websocket.py)
// =============================================================================

export const WS_MSG_TYPE_STREAM_CHUNK = 'stream_chunk';
export const WS_MSG_TYPE_STREAM_STATUS = 'stream_status';
export const WS_MSG_TYPE_STREAM_PROJECTION = 'stream_projection';
export const WS_MSG_TYPE_STREAM_COMPLETE = 'stream_complete';
export const WS_MSG_TYPE_STREAM_FAILURE = 'stream_failure';
export const WS_MSG_TYPE_STREAM_HEARTBEAT = 'stream_heartbeat';
export const WS_MSG_TYPE_STREAM_WARNING = 'stream_warning';
export const WS_MSG_TYPE_STREAM_PROPOSAL = 'stream_proposal';
export const WS_MSG_TYPE_STREAM_ACKnowledgement = 'stream_ack';

// =============================================================================
// Module Exports
// =============================================================================

export {
  // Constants
  MAX_VISUAL_STATE_ENTRIES,
  MAX_VELOCITY_SAMPLES,
  MAX_REPLAY_FRAMES,
  MAX_INTEGRITY_WARNINGS,
  MIN_STATE_UPDATE_INTERVAL_MS,
  // Classes
  VelocitySample,
  VisualStateEntry,
  ReplayFrame,
  IntegrityWarning,
  VisualStateBuffer,
  VelocityTracker,
  ReplayFrameBuffer,
  IntegrityWarningBuffer,
  StatefulLoader,
  RuntimeInstrumentation,
  // Utilities
  MotionUtils,
  generateDeterministicId,
  safeTruncate,
  formatBytes,
  formatTokens,
  getColorForSeverity,
  getMotionClassForState,
  clamp,
  lerp
};
