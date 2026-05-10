/** SVG Runtime Instrumentation Substrate
 *
 * PHASE 1: Deterministic SVG Instrumentation Primitives
 *
 * Core doctrine:
 * - Animations derive FROM real runtime state ONLY
 * - NO arbitrary geometry generation
 * - All geometry derives from runtime/projection state
 * - Deterministic IDs
 * - Replay-safe ordering
 * - DOM-addressable instrumentation elements
 * - Projection-only rendering (never fetches data)
 * - No authority inference
 * - No hidden frontend state
 *
 * This module provides:
 * - Deterministic SVG instrumentation primitives
 * - Projection -> geometry mapping
 * - Bounded geometry state
 * - Replay-safe SVG sequencing
 * - DOM-addressable instrumentation elements
 *
 * SVG primitives implemented:
 * - Execution lanes
 * - Routing paths
 * - Stream density lines
 * - Throughput bars
 * - Replay sweeps
 * - Integrity markers
 * - Proposal nodes
 * - Runtime topology connectors
 */

export function normalizeRuntimeEventEnvelope(envelope = {}) {
  if (!envelope || typeof envelope !== 'object') {
    return null;
  }
  return {
    schema_version: envelope.schema_version || envelope.schemaVersion || 'rig.runtime_event.v1',
    event_family: envelope.event_family || envelope.eventFamily || 'runtime.lifecycle',
    event_type: envelope.event_type || envelope.eventType || 'event',
    event_id: envelope.event_id || envelope.eventId || '',
    sequence: Number.isFinite(envelope.sequence) ? envelope.sequence : 0,
    timestamp: envelope.timestamp || '',
    payload: envelope.payload && typeof envelope.payload === 'object' ? envelope.payload : {}
  };
}

export function normalizeOperationalStatusEnvelope(status = {}) {
  if (status === null || status === undefined) {
    return {
      schema_version: 'rig.runtime_status.v1',
      value: 'unknown',
      label: 'Unknown',
      severity: 'info',
      state: 'unknown',
      message: '',
      condition: null
    };
  }

  if (typeof status === 'string') {
    return {
      schema_version: 'rig.runtime_status.v1',
      value: status,
      label: status,
      severity: getStatusSeverity(status),
      state: status,
      message: '',
      condition: null
    };
  }

  const condition = status.condition && typeof status.condition === 'object' ? status.condition : null;
  const value = status.value || status.state || status.label || condition?.value || condition?.state || 'unknown';
  const label = status.label || condition?.label || value;
  const severity = status.severity || condition?.severity || getStatusSeverity(value);

  return {
    schema_version: status.schema_version || status.schemaVersion || 'rig.runtime_status.v1',
    value,
    label,
    severity,
    state: status.state || condition?.state || value,
    message: status.message || condition?.message || '',
    condition
  };
}

function getStatusSeverity(value) {
  const normalized = String(value || 'unknown').toLowerCase();
  if (['failed', 'error', 'timed_out', 'cancelled', 'blocked'].includes(normalized)) {
    return 'error';
  }
  if (['stalled', 'paused', 'degraded', 'saturated', 'drift_detected', 'reconciling'].includes(normalized)) {
    return 'warning';
  }
  return 'info';
}

// SVG Primitive: Replay Sweep
// =============================================================================

/** Replay sweep visualization - shows replay progression */
// Duplicate truncated stub removed; canonical implementation continues later in file.
// =============================================================================
// SVG Primitive: Stateful Loader
// =============================================================================

/** Stateful loading indicator - replaces generic loaders with stateful indicators
 * Progress derives ONLY from actual runtime state/projection state
 * NO arbitrary spinning animations
 */
export class SvgStatefulLoader {
  constructor(id, bounds, options = {}) {
    this.id = svgId('loader', id);
    this.bounds = bounds;
    this.state = options.state || 'idle';
    this.progress = options.progress || 0; // 0-1
    this.label = options.label || '';
    this.channel = options.channel || 'assistant';
    this.sequence = options.sequence || 0;
    this.totalSequences = options.totalSequences || 0;
    this.isIndeterminate = options.isIndeterminate || false;
    this.size = Math.min(bounds.width, bounds.height) * 0.6;
  }

  render(parent) {
    const g = createSvgElement('g', {
      id: this.id,
      'data-loader-id': this.id,
      'data-state': this.state,
      class: `svg-stateful-loader state-${this.state}`
    });

    const center = centerOf(this.bounds);

    // Outer ring (track)
    const radius = this.size / 2;
    const track = createSvgElement('circle', {
      cx: center.x,
      cy: center.y,
      r: radius,
      fill: 'none',
      stroke: SVG_COLORS.GRID,
      'stroke-width': STROKE_WIDTH_THIN,
      opacity: SVG_COLORS.OPACITY_MEDIUM
    });
    g.appendChild(track);

    // Progress arc (for determinate state)
    if (!this.isIndeterminate && this.progress > 0) {
      const progressRadius = radius - STROKE_WIDTH_NORMAL * 2;
      const arc = this._createProgressArc(center, progressRadius);
      g.appendChild(arc);
    }

    // Indeterminate indicator (pulsing dot for streaming)
    if (this.isIndeterminate || this.state === 'streaming') {
      const dot = createSvgElement('circle', {
        cx: center.x + radius * 0.7,
        cy: center.y,
        r: STROKE_WIDTH_THICK * 1.5,
        fill: this._getStateColor(),
        opacity: SVG_COLORS.OPACITY_HIGH
      });
      g.appendChild(dot);
    }

    // Center state indicator
    const centerIndicator = createSvgElement('circle', {
      cx: center.x,
      cy: center.y,
      r: radius * 0.4,
      fill: this._getStateColor(),
      opacity: SVG_COLORS.OPACITY_MEDIUM
    });
    g.appendChild(centerIndicator);

    // State indicator shape (over center)
    const stateShape = this._createStateShape(center, radius * 0.25);
    g.appendChild(stateShape);

    // Label
    if (this.label && radius > 20) {
      const label = createSvgElement('text', {
        x: center.x,
        y: center.y + radius + GEOMETRY.LABEL_OFFSET * 2,
        'text-anchor': 'middle',
        'dominant-baseline': 'middle',
        fill: SVG_COLORS.FOREGROUND,
        'font-size': '10',
        'font-family': 'system-ui, sans-serif'
      });
      label.textContent = this.label;
      g.appendChild(label);
    }

    // Sequence indicator
    if (this.sequence > 0 && this.totalSequences > 0 && radius > 15) {
      const seqLabel = createSvgElement('text', {
        x: center.x,
        y: center.y - radius - GEOMETRY.LABEL_OFFSET,
        'text-anchor': 'middle',
        'dominant-baseline': 'bottom',
        fill: SVG_COLORS.TEXT_MUTED,
        'font-size': '9',
        'font-family': 'system-ui, sans-serif'
      });
      seqLabel.textContent = `${this.sequence}/${this.totalSequences}`;
      g.appendChild(seqLabel);
    }

    parent.appendChild(g);
    return g;
  }

  _createProgressArc(center, radius) {
    const startAngle = -Math.PI / 2;
    const endAngle = startAngle + this.progress * Math.PI * 2;
    const largeArc = this.progress > 0.5 ? 1 : 0;

    const x1 = center.x + radius * Math.cos(startAngle);
    const y1 = center.y + radius * Math.sin(startAngle);
    const x2 = center.x + radius * Math.cos(endAngle);
    const y2 = center.y + radius * Math.sin(endAngle);

    return createSvgElement('path', {
      d: `M ${center.x} ${center.y} L ${x1} ${y1} A ${radius} ${radius} 0 ${largeArc} 1 ${x2} ${y2} Z`,
      fill: SVG_COLORS.STREAMING,
      opacity: SVG_COLORS.OPACITY_MEDIUM
    });
  }

  _createStateShape(center, size) {
    const halfSize = size / 2;

    switch (this.state) {
      case 'streaming':
        // Triangle pointing right (flow indicator)
        return createSvgElement('polygon', {
          points: [
            `${center.x - halfSize},${center.y - halfSize}`,
            `${center.x - halfSize},${center.y + halfSize}`,
            `${center.x + halfSize},${center.y}`
          ].join(' '),
          fill: SVG_COLORS.STREAMING,
          stroke: SVG_COLORS.FOREGROUND,
          'stroke-width': STROKE_WIDTH_THIN
        });

      case 'proposing':
        // Diamond (decision/proposal)
        return createSvgElement('polygon', {
          points: [
            `${center.x},${center.y - halfSize}`,
            `${center.x + halfSize},${center.y}`,
            `${center.x},${center.y + halfSize}`,
            `${center.x - halfSize},${center.y}`
          ].join(' '),
          fill: SVG_COLORS.PROPOSING,
          stroke: SVG_COLORS.FOREGROUND,
          'stroke-width': STROKE_WIDTH_THIN
        });

      case 'validating':
        // Checkmark shape
        return createSvgElement('path', {
          d: `M ${center.x - halfSize} ${center.y} L ${center.x} ${center.y + halfSize} L ${center.x + halfSize} ${center.y - halfSize}`,
          fill: 'none',
          stroke: SVG_COLORS.VALIDATING,
          'stroke-width': STROKE_WIDTH_NORMAL,
          'stroke-linecap': 'round'
        });

      case 'replaying':
        // Double arrow (replay indicator)
        return createSvgElement('path', {
          d: `M ${center.x - halfSize} ${center.y - halfSize} L ${center.x} ${center.y} L ${center.x - halfSize} ${center.y + halfSize}
               M ${center.x} ${center.y} L ${center.x + halfSize} ${center.y}`,
          fill: 'none',
          stroke: SVG_COLORS.REPLAYING,
          'stroke-width': STROKE_WIDTH_NORMAL,
          'stroke-linecap': 'round'
        });

      case 'stalled':
        // Horizontal line (paused/stopped)
        return createSvgElement('line', {
          x1: center.x - halfSize,
          y1: center.y,
          x2: center.x + halfSize,
          y2: center.y,
          stroke: SVG_COLORS.STALLED,
          'stroke-width': STROKE_WIDTH_THICK,
          'stroke-linecap': 'round'
        });

      case 'error':
      case 'failure':
        // X mark
        return createSvgElement('path', {
          d: `M ${center.x - halfSize} ${center.y - halfSize} L ${center.x + halfSize} ${center.y + halfSize}
               M ${center.x - halfSize} ${center.y + halfSize} L ${center.x + halfSize} ${center.y - halfSize}`,
          fill: 'none',
          stroke: SVG_COLORS.FAILURE,
          'stroke-width': STROKE_WIDTH_NORMAL,
          'stroke-linecap': 'round'
        });

      case 'complete':
      case 'completed':
        // Checkmark
        return createSvgElement('path', {
          d: `M ${center.x - halfSize} ${center.y} L ${center.x} ${center.y + halfSize} L ${center.x + halfSize * 2} ${center.y - halfSize * 2}`,
          fill: 'none',
          stroke: SVG_COLORS.COMPLETE,
          'stroke-width': STROKE_WIDTH_NORMAL * 1.5,
          'stroke-linecap': 'round'
        });

      default: // idle
        // Circle (waiting)
        return createSvgElement('circle', {
          cx: center.x,
          cy: center.y,
          r: size / 2,
          fill: 'none',
          stroke: SVG_COLORS.IDLE,
          'stroke-width': STROKE_WIDTH_NORMAL
        });
    }
  }

  _getStateColor() {
    switch (this.state) {
      case 'streaming': return SVG_COLORS.STREAMING;
      case 'proposing': return SVG_COLORS.PROPOSING;
      case 'validating': return SVG_COLORS.VALIDATING;
      case 'replaying': return SVG_COLORS.REPLAYING;
      case 'stalled': return SVG_COLORS.STALLED;
      case 'error':
      case 'failure': return SVG_COLORS.FAILURE;
      case 'complete':
      case 'completed': return SVG_COLORS.COMPLETE;
      default: return SVG_COLORS.IDLE;
    }
  }

  update(options = {}) {
    Object.assign(this, options);
  }
}

// =============================================================================
// =============================================================================
// SVG Primitive: Replay Sweep
// =============================================================================
// Constants
// =============================================================================

/** Maximum SVG elements per instrumentation group */
const MAX_SVG_ELEMENTS_PER_GROUP = 500;

/** Maximum path complexity (segments per path) */
const MAX_PATH_SEGMENTS = 200;

/** Maximum replay sweep frames */
const MAX_REPLAY_SWEEP_FRAMES = 100;

/** Default SVG namespace */
const SVG_NS = 'http://www.w3.org/2000/svg';

/** Stroke width constants */
const STROKE_WIDTH_THIN = 1;
const STROKE_WIDTH_NORMAL = 1.5;
const STROKE_WIDTH_THICK = 2;
const STROKE_WIDTH_HEAVY = 3;

/** Color palette - maintains operational legibility */
const SVG_COLORS = {
  // Execution states
  EXECUTING: 'var(--color-executing, #4CAF50)',
  STREAMING: 'var(--color-streaming, #2196F3)',
  PROPOSING: 'var(--color-proposing, #FF9800)',
  VALIDATING: 'var(--color-validating, #9C27B0)',
  REPLAYING: 'var(--color-replaying, #00BCD4)',
  STALLED: 'var(--color-stalled, #795548)',
  COMPLETE: 'var(--color-complete, #8BC34A)',
  FAILURE: 'var(--color-failure, #F44336)',
  IDLE: 'var(--color-idle, #9E9E9E)',
  
  // Integrity states
  INTEGRITY_OK: 'var(--color-integrity-ok, #4CAF50)',
  INTEGRITY_WARNING: 'var(--color-integrity-warning, #FFC107)',
  INTEGRITY_ERROR: 'var(--color-integrity-error, #F44336)',
  
  // Capability routing
  CAPABILITY_DEFAULT: 'var(--color-capability-default, #607D8B)',
  CAPABILITY_ELEVATED: 'var(--color-capability-elevated, #FF5722)',
  CAPABILITY_RESTRICTED: 'var(--color-capability-restricted, #E91E63)',
  
  // Neutral
  BACKGROUND: 'var(--color-background, #1E1E1E)',
  FOREGROUND: 'var(--color-foreground, #E0E0E0)',
  GRID: 'var(--color-grid, #424242)',
  TEXT: 'var(--color-text, #CCCCCC)',
  TEXT_MUTED: 'var(--color-text-muted, #757575)',
  
  // Geometry
  STROKE: 'var(--color-stroke, #616161)',
  FILL_SUBTLE: 'var(--color-fill-subtle, #333333)',
  
  // Opacities
  OPACITY_FULL: 1.0,
  OPACITY_HIGH: 0.85,
  OPACITY_MEDIUM: 0.6,
  OPACITY_LOW: 0.35,
  OPACITY_MINIMAL: 0.15
};

/** Geometry constants */
const GEOMETRY = {
  LANE_HEIGHT: 40,
  LANE_MARGIN: 8,
  CONNECTOR_RADIUS: 6,
  NODE_RADIUS: 8,
  NODE_DIAMETER: 16,
  PROPOSAL_NODE_RADIUS: 10,
  THROUGHPUT_BAR_HEIGHT: 20,
  STREAM_LINE_STROKE: 2,
  DENSITY_LINE_STROKE: 1.5,
  SWEEP_STROKE: 2,
  MARKER_SIZE: 12,
  MIN_CURVE_RADIUS: 20,
  PADDING: 16,
  LABEL_OFFSET: 4
};

/** Animation timing (derived from real runtime state, not arbitrary) */
const ANIMATION = {
  STREAM_FLOW_DURATION: '200ms',
  PROPOSAL_PULSE_DURATION: '300ms',
  REPLAY_SWEEP_DURATION: '150ms',
  INTEGRITY_FLASH_DURATION: '200ms',
  STATE_TRANSITION_DURATION: '150ms'
};

// =============================================================================
// Helper Functions
// =============================================================================

/** Generate deterministic ID for SVG elements */
function svgId(prefix, ...components) {
  const parts = [String(prefix), ...components.map(c => String(c))];
  const combined = parts.join('|');
  let hash = 0;
  for (let i = 0; i < combined.length; i++) {
    const char = combined.charCodeAt(i);
    hash = ((hash << 5) - hash) + char;
    hash = hash & hash;
  }
  return `svg-${prefix}-${Math.abs(hash).toString(16).substring(0, 8)}`;
}

/** Create SVG element with namespace */
function createSvgElement(tagName, attributes = {}) {
  const el = document.createElementNS(SVG_NS, tagName);
  for (const [key, value] of Object.entries(attributes)) {
    if (value !== undefined && value !== null) {
      el.setAttribute(key, String(value));
    }
  }
  return el;
}

/** Safe attribute setting with validation */
function setSvgAttr(el, attr, value) {
  if (value !== undefined && value !== null) {
    if (attr === 'class' && typeof value === 'object') {
      el.setAttribute('class', Object.entries(value)
        .filter(([_, v]) => v)
        .map(([k]) => k)
        .join(' '));
    } else {
      el.setAttribute(attr, String(value));
    }
  }
}

/** Clamp value between min and max */
export function clamp(val, min, max) {
  return Math.min(Math.max(val, min), max);
}

/** Map value from one range to another */
export function mapRange(value, inMin, inMax, outMin, outMax) {
  if (inMin === inMax) return outMin;
  const t = (value - inMin) / (inMax - inMin);
  return outMin + (outMax - outMin) * clamp(t, 0, 1);
}

/** Normalize geometry coordinate */
export function normalizeCoord(value, min, max, targetMin = 0, targetMax = 1) {
  return mapRange(value, min, max, targetMin, targetMax);
}

// =============================================================================
// Geometry Builders
// =============================================================================

/** Build a point object */
export function point(x, y) {
  return { x: Math.round(x * 100) / 100, y: Math.round(y * 100) / 100 };
}

/** Build a size object */
export function size(width, height) {
  return { width: Math.round(width * 100) / 100, height: Math.round(height * 100) / 100 };
}

/** Build a rect object */
export function rect(x, y, width, height) {
  return {
    x: Math.round(x * 100) / 100,
    y: Math.round(y * 100) / 100,
    width: Math.round(width * 100) / 100,
    height: Math.round(height * 100) / 100
  };
}

/** Calculate geometric center of a rect */
export function centerOf(rect) {
  return point(
    rect.x + rect.width / 2,
    rect.y + rect.height / 2
  );
}

// =============================================================================
// SVG Primitive: Execution Lane
// =============================================================================

/** Execution lane visualization
 * Represents a logical execution channel/path
 */
export class SvgExecutionLane {
  constructor(id, bounds, options = {}) {
    this.id = svgId('lane', id);
    this.bounds = bounds;
    this.state = options.state || 'idle';
    this.label = options.label || `Lane ${id}`;
    this.index = options.index || 0;
    this.active = options.active || false;
    this.stalled = options.stalled || false;
    this.completed = options.completed || false;
    this.throughput = options.throughput || 0;
    this.maxThroughput = options.maxThroughput || 100;
  }

  /** Render the lane as SVG group */
  render(parent) {
    const g = createSvgElement('g', {
      id: this.id,
      'data-lane-id': this.id,
      'data-state': this.state,
      class: `svg-lane state-${this.state}`
    });

    // Lane background
    const bg = createSvgElement('rect', {
      x: this.bounds.x,
      y: this.bounds.y,
      width: this.bounds.width,
      height: this.bounds.height,
      rx: 2,
      ry: 2,
      fill: this._getBgColor(),
      stroke: this._getStrokeColor(),
      'stroke-width': STROKE_WIDTH_THIN,
      opacity: this.active ? SVG_COLORS.OPACITY_HIGH : SVG_COLORS.OPACITY_LOW
    });
    g.appendChild(bg);

    // Lane label (left-aligned)
    const label = createSvgElement('text', {
      x: this.bounds.x + GEOMETRY.PADDING,
      y: this.bounds.y + this.bounds.height / 2 + GEOMETRY.LABEL_OFFSET,
      'text-anchor': 'start',
      'dominant-baseline': 'middle',
      fill: SVG_COLORS.TEXT,
      'font-size': '11',
      'font-family': 'system-ui, sans-serif'
    });
    label.textContent = this.label;
    g.appendChild(label);

    // Throughput indicator (right-aligned)
    if (this.throughput > 0) {
      const throughputText = createSvgElement('text', {
        x: this.bounds.x + this.bounds.width - GEOMETRY.PADDING,
        y: this.bounds.y + this.bounds.height / 2 + GEOMETRY.LABEL_OFFSET,
        'text-anchor': 'end',
        'dominant-baseline': 'middle',
        fill: SVG_COLORS.TEXT_MUTED,
        'font-size': '10',
        'font-family': 'system-ui, sans-serif'
      });
      const throughputPercent = Math.round((this.throughput / this.maxThroughput) * 100);
      throughputText.textContent = `${this.throughput}/${this.maxThroughput} (${throughputPercent}%)`;
      g.appendChild(throughputText);
    }

    // Center line (visual guide)
    const centerY = this.bounds.y + this.bounds.height / 2;
    const centerLine = createSvgElement('line', {
      x1: this.bounds.x,
      y1: centerY,
      x2: this.bounds.x + this.bounds.width,
      y2: centerY,
      stroke: SVG_COLORS.GRID,
      'stroke-width': STROKE_WIDTH_THIN,
      'stroke-dasharray': '4,2',
      opacity: this.active ? SVG_COLORS.OPACITY_MEDIUM : SVG_COLORS.OPACITY_MINIMAL
    });
    g.appendChild(centerLine);

    parent.appendChild(g);
    return g;
  }

  _getBgColor() {
    if (this.completed) return SVG_COLORS.COMPLETE;
    if (this.stalled) return SVG_COLORS.STALLED;
    if (this.active) {
      switch (this.state) {
        case 'streaming': return SVG_COLORS.STREAMING;
        case 'proposing': return SVG_COLORS.PROPOSING;
        case 'validating': return SVG_COLORS.VALIDATING;
        case 'replaying': return SVG_COLORS.REPLAYING;
        case 'failure': return SVG_COLORS.FAILURE;
        default: return SVG_COLORS.EXECUTING;
      }
    }
    return SVG_COLORS.IDLE;
  }

  _getStrokeColor() {
    if (this.stalled) return SVG_COLORS.INTEGRITY_WARNING;
    if (this.completed) return SVG_COLORS.COMPLETE;
    return SVG_COLORS.STROKE;
  }

  /** Update lane state and re-render */
  update(options = {}) {
    Object.assign(this, options);
  }
}

// =============================================================================
// SVG Primitive: Routing Path
// =============================================================================

/** Routing path between capability nodes
 * Represents runtime -> capability -> sandbox routing
 */
export class SvgRoutingPath {
  constructor(id, points, options = {}) {
    this.id = svgId('route', id);
    this.points = points;
    this.state = options.state || 'idle';
    this.capability = options.capability || 'default';
    this.trustLevel = options.trustLevel || 'default';
    this.active = options.active || false;
    this.direction = options.direction || 'forward';
    this.thickness = options.thickness || STROKE_WIDTH_NORMAL;
  }

  /** Render the path with smooth curves */
  render(parent) {
    const g = createSvgElement('g', {
      id: this.id,
      'data-route-id': this.id,
      'data-capability': this.capability,
      'data-state': this.state,
      class: `svg-route capability-${this.capability} state-${this.state}`
    });

    // Build smooth path through points
    if (this.points.length >= 2) {
      const d = this._buildSmoothPath();
      const path = createSvgElement('path', {
        d,
        fill: 'none',
        stroke: this._getStrokeColor(),
        'stroke-width': this.thickness,
        'stroke-linecap': 'round',
        'stroke-linejoin': 'round',
        opacity: this.active ? SVG_COLORS.OPACITY_HIGH : SVG_COLORS.OPACITY_MEDIUM
      });
      g.appendChild(path);
    }

    // Direction arrow (if active)
    if (this.active && this.points.length >= 2) {
      const lastPoint = this.points[this.points.length - 1];
      const arrow = this._createDirectionArrow(lastPoint);
      g.appendChild(arrow);
    }

    parent.appendChild(g);
    return g;
  }

  _buildSmoothPath() {
    if (this.points.length === 2) {
      return `M ${this.points[0].x} ${this.points[0].y} L ${this.points[1].x} ${this.points[1].y}`;
    }

    // Bezier smooth for multi-point paths
    const commands = [];
    commands.push(`M ${this.points[0].x} ${this.points[0].y}`);

    for (let i = 1; i < this.points.length - 1; i++) {
      const prev = this.points[i - 1];
      const curr = this.points[i];
      const next = this.points[i + 1];

      const cp1x = (prev.x + curr.x) / 2;
      const cp1y = (prev.y + curr.y) / 2;
      const cp2x = (curr.x + next.x) / 2;
      const cp2y = (curr.y + next.y) / 2;

      commands.push(`C ${cp1x} ${cp1y}, ${cp2x} ${cp2y}, ${curr.x} ${curr.y}`);
    }

    // Final segment to last point
    if (this.points.length > 1) {
      const last = this.points[this.points.length - 1];
      commands.push(`L ${last.x} ${last.y}`);
    }

    return commands.join(' ');
  }

  _createDirectionArrow(tipPoint) {
    const arrowSize = GEOMETRY.MARKER_SIZE * 0.8;
    const angle = this.direction === 'reverse' ? Math.PI : 0;

    const points = [
      point(tipPoint.x, tipPoint.y),
      point(
        tipPoint.x - arrowSize * Math.cos(angle) - arrowSize * 0.5 * Math.sin(angle),
        tipPoint.y - arrowSize * Math.sin(angle) + arrowSize * 0.5 * Math.cos(angle)
      ),
      point(
        tipPoint.x - arrowSize * Math.cos(angle) + arrowSize * 0.5 * Math.sin(angle),
        tipPoint.y - arrowSize * Math.sin(angle) - arrowSize * 0.5 * Math.cos(angle)
      )
    ];

    return createSvgElement('polygon', {
      points: points.map(p => `${p.x},${p.y}`).join(' '),
      fill: this._getStrokeColor(),
      opacity: SVG_COLORS.OPACITY_HIGH
    });
  }

  _getStrokeColor() {
    switch (this.capability) {
      case 'elevated': return SVG_COLORS.CAPABILITY_ELEVATED;
      case 'restricted': return SVG_COLORS.CAPABILITY_RESTRICTED;
      default: return SVG_COLORS.CAPABILITY_DEFAULT;
    }
  }

  update(options = {}) {
    Object.assign(this, options);
  }
}

// =============================================================================
// SVG Primitive: Stream Density Line
// =============================================================================

/** Stream density visualization - shows chunk/token flow density */
export class SvgStreamDensityLine {
  constructor(id, points, options = {}) {
    this.id = svgId('density', id);
    this.points = points;
    this.intensity = options.intensity || 0.5;
    this.channel = options.channel || 'assistant';
    this.state = options.state || 'streaming';
    this.sequenceStart = options.sequenceStart || 0;
    this.sequenceEnd = options.sequenceEnd || 100;
    this.bytesTotal = options.bytesTotal || 0;
    this.tokensTotal = options.tokensTotal || 0;
  }

  render(parent) {
    const g = createSvgElement('g', {
      id: this.id,
      'data-density-id': this.id,
      'data-channel': this.channel,
      class: `svg-density channel-${this.channel} state-${this.state}`
    });

    if (this.points.length >= 2) {
      const path = this._buildVariablePath();
      
      const densityPath = createSvgElement('path', {
        d: path,
        fill: 'none',
        stroke: this._getChannelColor(),
        'stroke-width': this._getStrokeWidth(),
        'stroke-linecap': 'round',
        'stroke-linejoin': 'round',
        opacity: this._getOpacity()
      });
      
      if (this.state === 'streaming' && this.intensity > 0.5) {
        const filterId = svgId('glow', this.id);
        const filter = createSvgElement('filter', {
          id: filterId,
          x: '-50%',
          y: '-50%',
          width: '200%',
          height: '200%'
        });
        filter.appendChild(createSvgElement('feGaussianBlur', {
          stdDeviation: '2',
          result: 'blur'
        }));
        filter.appendChild(createSvgElement('feComposite', {
          in: 'SourceGraphic',
          in2: 'blur',
          operator: 'over'
        }));
        g.appendChild(filter);
        densityPath.setAttribute('filter', `url(#${filterId})`);
      }
      
      g.appendChild(densityPath);
    }

    // Sequence labels at endpoints
    if (this.sequenceStart !== this.sequenceEnd) {
      const startLabel = createSvgElement('text', {
        x: this.points[0].x,
        y: this.points[0].y - GEOMETRY.LABEL_OFFSET * 2,
        'text-anchor': 'middle',
        'dominant-baseline': 'bottom',
        fill: SVG_COLORS.TEXT_MUTED,
        'font-size': '9',
        'font-family': 'system-ui, sans-serif'
      });
      startLabel.textContent = String(this.sequenceStart);
      g.appendChild(startLabel);

      const endLabel = createSvgElement('text', {
        x: this.points[this.points.length - 1].x,
        y: this.points[this.points.length - 1].y - GEOMETRY.LABEL_OFFSET * 2,
        'text-anchor': 'middle',
        'dominant-baseline': 'bottom',
        fill: SVG_COLORS.TEXT_MUTED,
        'font-size': '9',
        'font-family': 'system-ui, sans-serif'
      });
      endLabel.textContent = String(this.sequenceEnd);
      g.appendChild(endLabel);
    }

    parent.appendChild(g);
    return g;
  }

  _buildVariablePath() {
    if (this.points.length === 2) {
      return `M ${this.points[0].x} ${this.points[0].y} L ${this.points[1].x} ${this.points[1].y}`;
    }

    const commands = [];
    commands.push(`M ${this.points[0].x} ${this.points[0].y}`);

    for (let i = 1; i < this.points.length; i++) {
      commands.push(`L ${this.points[i].x} ${this.points[i].y}`);
    }

    return commands.join(' ');
  }

  _getChannelColor() {
    const channelMap = {
      'assistant': SVG_COLORS.STREAMING,
      'user': SVG_COLORS.FOREGROUND,
      'system': SVG_COLORS.TEXT_MUTED,
      'tool': SVG_COLORS.PROPOSING,
      'proposal': SVG_COLORS.VALIDATING,
      'diagnostic': SVG_COLORS.TEXT_MUTED,
      'warning': SVG_COLORS.INTEGRITY_WARNING,
      'error': SVG_COLORS.INTEGRITY_ERROR
    };
    return channelMap[this.channel] || SVG_COLORS.FOREGROUND;
  }

  _getStrokeWidth() {
    return mapRange(this.intensity, 0, 1, STROKE_WIDTH_THIN, STROKE_WIDTH_HEAVY);
  }

  _getOpacity() {
    return mapRange(this.intensity, 0, 1, SVG_COLORS.OPACITY_LOW, SVG_COLORS.OPACITY_HIGH);
  }

  update(options = {}) {
    Object.assign(this, options);
  }
}

// =============================================================================
// SVG Primitive: Throughput Bar
// =============================================================================

/** Throughput bar - shows real runtime throughput as bar chart */
export class SvgThroughputBar {
  constructor(id, bounds, options = {}) {
    this.id = svgId('throughput', id);
    this.bounds = bounds;
    this.value = options.value || 0;
    this.maxValue = options.maxValue || 100;
    this.minValue = options.minValue || 0;
    this.label = options.label || '';
    this.state = options.state || 'idle';
    this.channel = options.channel || 'assistant';
  }

  render(parent) {
    const g = createSvgElement('g', {
      id: this.id,
      'data-throughput-id': this.id,
      class: `svg-throughput state-${this.state}`
    });

    // Background track
    const track = createSvgElement('rect', {
      x: this.bounds.x,
      y: this.bounds.y,
      width: this.bounds.width,
      height: this.bounds.height,
      rx: 2,
      ry: 2,
      fill: SVG_COLORS.FILL_SUBTLE,
      stroke: SVG_COLORS.GRID,
      'stroke-width': STROKE_WIDTH_THIN
    });
    g.appendChild(track);

    // Fill bar
    const fillWidth = this._getFillWidth();
    const fill = createSvgElement('rect', {
      x: this.bounds.x,
      y: this.bounds.y,
      width: fillWidth,
      height: this.bounds.height,
      rx: 2,
      ry: 2,
      fill: this._getFillColor(),
      opacity: this.state === 'streaming' ? SVG_COLORS.OPACITY_HIGH : SVG_COLORS.OPACITY_MEDIUM
    });
    g.appendChild(fill);

    // Value label
    if (this.bounds.height >= 16 && this.value !== undefined) {
      const label = createSvgElement('text', {
        x: this.bounds.x + this.bounds.width / 2,
        y: this.bounds.y + this.bounds.height / 2 + GEOMETRY.LABEL_OFFSET,
        'text-anchor': 'middle',
        'dominant-baseline': 'middle',
        fill: this._getTextColor(fillWidth),
        'font-size': '10',
        'font-family': 'system-ui, sans-serif'
      });
      label.textContent = this._formatValue();
      g.appendChild(label);
    }

    // Label (left-aligned)
    if (this.label) {
      const nameLabel = createSvgElement('text', {
        x: this.bounds.x,
        y: this.bounds.y - GEOMETRY.LABEL_OFFSET,
        'text-anchor': 'start',
        'dominant-baseline': 'bottom',
        fill: SVG_COLORS.TEXT_MUTED,
        'font-size': '9',
        'font-family': 'system-ui, sans-serif'
      });
      nameLabel.textContent = this.label;
      g.appendChild(nameLabel);
    }

    parent.appendChild(g);
    return g;
  }

  _getFillWidth() {
    return mapRange(
      clamp(this.value, this.minValue, this.maxValue),
      this.minValue,
      this.maxValue,
      0,
      this.bounds.width
    );
  }

  _getFillColor() {
    const channelMap = {
      'assistant': SVG_COLORS.STREAMING,
      'user': SVG_COLORS.FOREGROUND,
      'tool': SVG_COLORS.PROPOSING,
      'proposal': SVG_COLORS.VALIDATING
    };
    return channelMap[this.channel] || SVG_COLORS.STREAMING;
  }

  _getTextColor(fillWidth) {
    if (fillWidth > this.bounds.width * 0.6) {
      return SVG_COLORS.FOREGROUND;
    }
    return SVG_COLORS.TEXT;
  }

  _formatValue() {
    if (typeof this.value === 'number') {
      return this.value.toFixed(this.value % 1 === 0 ? 0 : 1);
    }
    return String(this.value);
  }

  update(options = {}) {
    Object.assign(this, options);
  }
}

// =============================================================================
// SVG Primitive: Replay Sweep
// =============================================================================

/** Replay sweep visualization - shows replay progression */
export class SvgReplaySweep {
  constructor(id, bounds, options = {}) {
    this.id = svgId('replay-sweep', id);
    this.bounds = bounds;
    this.progress = options.progress || 0;
    this.state = options.state || 'replaying';
    this.replayId = options.replayId || '';
    this.sequence = options.sequence || 0;
    this.totalSequences = options.totalSequences || 100;
    this.isReconstructed = options.isReconstructed || false;
  }

  render(parent) {
    const g = createSvgElement('g', {
      id: this.id,
      'data-replay-sweep-id': this.id,
      class: `svg-replay-sweep state-${this.state}`
    });

    const center = centerOf(this.bounds);
    const radius = Math.min(this.bounds.width, this.bounds.height) / 2 - STROKE_WIDTH_NORMAL;

    // Track circle
    const track = createSvgElement('circle', {
      cx: center.x,
      cy: center.y,
      r: radius,
      fill: 'none',
      stroke: SVG_COLORS.GRID,
      'stroke-width': STROKE_WIDTH_THIN,
      opacity: SVG_COLORS.OPACITY_MEDIUM
    });
    g.appendChild(track);

    // Progress arc
    if (this.progress > 0) {
      const arc = this._createProgressArc(center, radius);
      g.appendChild(arc);
    }

    // Center indicator
    const indicator = createSvgElement('circle', {
      cx: center.x,
      cy: center.y,
      r: GEOMETRY.NODE_RADIUS * 0.75,
      fill: this._getIndicatorColor(),
      opacity: this.progress >= 1 ? SVG_COLORS.OPACITY_HIGH : SVG_COLORS.OPACITY_MEDIUM
    });
    g.appendChild(indicator);

    // Sequence label
    if (this.bounds.width >= 60) {
      const label = createSvgElement('text', {
        x: center.x,
        y: center.y + GEOMETRY.LABEL_OFFSET,
        'text-anchor': 'middle',
        'dominant-baseline': 'middle',
        fill: SVG_COLORS.FOREGROUND,
        'font-size': '10',
        'font-family': 'system-ui, sans-serif'
      });
      label.textContent = this.isReconstructed ? `~${this.sequence}/${this.totalSequences}` : `${this.sequence}/${this.totalSequences}`;
      g.appendChild(label);
    }

    // Reconstructed marker
    if (this.isReconstructed) {
      const marker = createSvgElement('text', {
        x: center.x,
        y: center.y - GEOMETRY.LABEL_OFFSET * 2,
        'text-anchor': 'middle',
        'dominant-baseline': 'bottom',
        fill: SVG_COLORS.INTEGRITY_WARNING,
        'font-size': '8',
        'font-family': 'system-ui, sans-serif'
      });
      marker.textContent = 'reconstructed';
      g.appendChild(marker);
    }

    parent.appendChild(g);
    return g;
  }

  _createProgressArc(center, radius) {
    const startAngle = -Math.PI / 2;
    const endAngle = startAngle + this.progress * Math.PI * 2;
    const largeArc = this.progress > 0.5 ? 1 : 0;

    const x1 = center.x + radius * Math.cos(startAngle);
    const y1 = center.y + radius * Math.sin(startAngle);
    const x2 = center.x + radius * Math.cos(endAngle);
    const y2 = center.y + radius * Math.sin(endAngle);

    return createSvgElement('path', {
      d: `M ${center.x} ${center.y} L ${x1} ${y1} A ${radius} ${radius} 0 ${largeArc} 1 ${x2} ${y2} Z`,
      fill: SVG_COLORS.REPLAYING,
      opacity: SVG_COLORS.OPACITY_MEDIUM,
      'stroke-width': STROKE_WIDTH_THIN
    });
  }

  _getIndicatorColor() {
    if (this.progress >= 1) return SVG_COLORS.COMPLETE;
    if (this.isReconstructed) return SVG_COLORS.INTEGRITY_WARNING;
    return SVG_COLORS.REPLAYING;
  }

  update(options = {}) {
    Object.assign(this, options);
  }
}

// =============================================================================
// SVG Primitive: Integrity Marker
// =============================================================================

/** Integrity marker - visualizes integrity state at specific points */
export class SvgIntegrityMarker {
  constructor(id, position, options = {}) {
    this.id = svgId('integrity', id);
    this.position = position;
    this.state = options.state || 'ok';
    this.code = options.code || 'unknown';
    this.severity = options.severity || 'info';
    this.message = options.message || '';
    this.timestamp = options.timestamp || Date.now();
    this.streamId = options.streamId || '';
    this.sequence = options.sequence || 0;
    this.size = options.size || GEOMETRY.MARKER_SIZE;
  }

  render(parent) {
    const g = createSvgElement('g', {
      id: this.id,
      'data-integrity-id': this.id,
      'data-state': this.state,
      'data-severity': this.severity,
      class: `svg-integrity-marker state-${this.state} severity-${this.severity}`
    });

    const marker = this._createMarkerShape();
    g.appendChild(marker);

    // Severity indicator (outer ring)
    const ring = createSvgElement('circle', {
      cx: this.position.x,
      cy: this.position.y,
      r: this.size / 2 + 2,
      fill: 'none',
      stroke: this._getSeverityColor(),
      'stroke-width': STROKE_WIDTH_THIN,
      opacity: SVG_COLORS.OPACITY_HIGH
    });
    g.appendChild(ring);

    // Code label
    if (this.size >= 14) {
      const label = createSvgElement('text', {
        x: this.position.x,
        y: this.position.y + GEOMETRY.LABEL_OFFSET,
        'text-anchor': 'middle',
        'dominant-baseline': 'middle',
        fill: SVG_COLORS.FOREGROUND,
        'font-size': '8',
        'font-family': 'system-ui, sans-serif',
        'font-weight': '600'
      });
      label.textContent = this.code.substring(0, 4);
      g.appendChild(label);
    }

    // Tooltip
    if (this.message) {
      const title = createSvgElement('title');
      title.textContent = `${this.code}: ${this.message}`;
      g.insertBefore(title, g.firstChild);
    }

    parent.appendChild(g);
    return g;
  }

  _createMarkerShape() {
    const halfSize = this.size / 2;

    switch (this.state) {
      case 'warning':
        return createSvgElement('polygon', {
          points: [
            `${this.position.x},${this.position.y - halfSize}`,
            `${this.position.x + halfSize * 0.7},${this.position.y + halfSize * 0.7}`,
            `${this.position.x - halfSize * 0.7},${this.position.y + halfSize * 0.7}`
          ].join(' '),
          fill: this._getFillColor(),
          stroke: this._getStrokeColor(),
          'stroke-width': STROKE_WIDTH_THIN
        });

      case 'error':
        return createSvgElement('rect', {
          x: this.position.x - halfSize,
          y: this.position.y - halfSize,
          width: this.size,
          height: this.size,
          fill: this._getFillColor(),
          stroke: this._getStrokeColor(),
          'stroke-width': STROKE_WIDTH_THIN,
          rx: 1,
          ry: 1
        });

      case 'fracture':
      case 'discontinuity':
        const g = createSvgElement('g');
        const circle = createSvgElement('circle', {
          cx: this.position.x,
          cy: this.position.y,
          r: halfSize,
          fill: this._getFillColor(),
          stroke: this._getStrokeColor(),
          'stroke-width': STROKE_WIDTH_THIN
        });
        g.appendChild(circle);
        const line = createSvgElement('line', {
          x1: this.position.x - halfSize * 0.8,
          y1: this.position.y - halfSize * 0.8,
          x2: this.position.x + halfSize * 0.8,
          y2: this.position.y + halfSize * 0.8,
          stroke: SVG_COLORS.FOREGROUND,
          'stroke-width': STROKE_WIDTH_THIN
        });
        g.appendChild(line);
        return g;

      default:
        return createSvgElement('circle', {
          cx: this.position.x,
          cy: this.position.y,
          r: halfSize,
          fill: this._getFillColor(),
          stroke: this._getStrokeColor(),
          'stroke-width': STROKE_WIDTH_THIN
        });
    }
  }

  _getFillColor() {
    const severityMap = {
      'critical': SVG_COLORS.INTEGRITY_ERROR,
      'error': SVG_COLORS.INTEGRITY_ERROR,
      'warning': SVG_COLORS.INTEGRITY_WARNING
    };
    return severityMap[this.severity] || SVG_COLORS.INTEGRITY_OK;
  }

  _getStrokeColor() {
    const severityMap = {
      'critical': SVG_COLORS.FOREGROUND,
      'error': SVG_COLORS.FOREGROUND,
      'warning': SVG_COLORS.FOREGROUND
    };
    return severityMap[this.severity] || this._getFillColor();
  }

  _getSeverityColor() {
    const severityMap = {
      'critical': SVG_COLORS.INTEGRITY_ERROR,
      'error': SVG_COLORS.INTEGRITY_ERROR,
      'warning': SVG_COLORS.INTEGRITY_WARNING
    };
    return severityMap[this.severity] || SVG_COLORS.INTEGRITY_OK;
  }

  update(options = {}) {
    Object.assign(this, options);
  }
}

// =============================================================================
// SVG Primitive: Proposal Node
// =============================================================================

/** Proposal node - represents a proposal in the execution flow */
export class SvgProposalNode {
  constructor(id, position, options = {}) {
    this.id = svgId('proposal', id);
    this.position = position;
    this.state = options.state || 'pending';
    this.kind = options.kind || 'tool';
    this.label = options.label || `Prop ${id}`;
    this.sequence = options.sequence || 0;
    this.capability = options.capability || 'default';
    this.size = options.size || GEOMETRY.PROPOSAL_NODE_RADIUS * 2;
    this.acknowledged = options.acknowledged || false;
    this.ignored = options.ignored || false;
    this.violation = options.violation || null;
  }

  render(parent) {
    const g = createSvgElement('g', {
      id: this.id,
      'data-proposal-id': this.id,
      'data-state': this.state,
      'data-kind': this.kind,
      class: `svg-proposal-node state-${this.state} kind-${this.kind}`
    });

    const halfSize = this.size / 2;

    const node = this._createNodeShape();
    g.appendChild(node);

    // State indicator ring
    const ring = createSvgElement('circle', {
      cx: this.position.x,
      cy: this.position.y,
      r: this.size / 2 + 2,
      fill: 'none',
      stroke: this._getStateColor(),
      'stroke-width': STROKE_WIDTH_THIN,
      opacity: SVG_COLORS.OPACITY_HIGH
    });
    g.appendChild(ring);

    if (this.acknowledged) {
      const ack = createSvgElement('circle', {
        cx: this.position.x + halfSize + 3,
        cy: this.position.y - halfSize - 3,
        r: 2,
        fill: SVG_COLORS.COMPLETE,
        opacity: SVG_COLORS.OPACITY_HIGH
      });
      g.appendChild(ack);
    }

    if (this.ignored) {
      const ignoreLine = createSvgElement('line', {
        x1: this.position.x - halfSize * 0.8,
        y1: this.position.y - halfSize * 0.8,
        x2: this.position.x + halfSize * 0.8,
        y2: this.position.y + halfSize * 0.8,
        stroke: SVG_COLORS.INTEGRITY_WARNING,
        'stroke-width': STROKE_WIDTH_THIN
      });
      g.appendChild(ignoreLine);
    }

    // Kind indicator
    const kindLabel = createSvgElement('text', {
      x: this.position.x,
      y: this.position.y + GEOMETRY.LABEL_OFFSET,
      'text-anchor': 'middle',
      'dominant-baseline': 'middle',
      fill: SVG_COLORS.FOREGROUND,
      'font-size': '8',
      'font-family': 'system-ui, sans-serif'
    });
    kindLabel.textContent = this.kind.substring(0, 3);
    g.appendChild(kindLabel);

    // Tooltip
    const title = createSvgElement('title');
    title.textContent = `${this.label} [${this.kind} ${this.state}]`;
    g.insertBefore(title, g.firstChild);

    parent.appendChild(g);
    return g;
  }

  _createNodeShape() {
    const halfSize = this.size / 2;

    switch (this.kind) {
      case 'tool':
        return createSvgElement('polygon', {
          points: [
            `${this.position.x},${this.position.y - halfSize}`,
            `${this.position.x + halfSize},${this.position.y}`,
            `${this.position.x},${this.position.y + halfSize}`,
            `${this.position.x - halfSize},${this.position.y}`
          ].join(' '),
          fill: this._getFillColor(),
          stroke: this._getStrokeColor(),
          'stroke-width': STROKE_WIDTH_THIN
        });

      case 'patch':
        return createSvgElement('rect', {
          x: this.position.x - halfSize,
          y: this.position.y - halfSize,
          width: this.size,
          height: this.size,
          fill: this._getFillColor(),
          stroke: this._getStrokeColor(),
          'stroke-width': STROKE_WIDTH_THIN,
          rx: 1,
          ry: 1
        });

      default:
        return createSvgElement('circle', {
          cx: this.position.x,
          cy: this.position.y,
          r: halfSize,
          fill: this._getFillColor(),
          stroke: this._getStrokeColor(),
          'stroke-width': STROKE_WIDTH_THIN
        });
    }
  }

  _getFillColor() {
    const stateMap = {
      'validated': SVG_COLORS.COMPLETE,
      'rejected': SVG_COLORS.INTEGRITY_ERROR,
      'pending_ack': SVG_COLORS.PROPOSING,
      'ignored': SVG_COLORS.TEXT_MUTED
    };
    return stateMap[this.state] || SVG_COLORS.PROPOSING;
  }

  _getStrokeColor() {
    const stateMap = {
      'validated': SVG_COLORS.COMPLETE,
      'rejected': SVG_COLORS.INTEGRITY_ERROR
    };
    return stateMap[this.state] || this._getFillColor();
  }

  _getStateColor() {
    const stateMap = {
      'validated': SVG_COLORS.COMPLETE,
      'rejected': SVG_COLORS.INTEGRITY_ERROR,
      'pending_ack': SVG_COLORS.PROPOSING,
      'ignored': SVG_COLORS.TEXT_MUTED
    };
    return stateMap[this.state] || SVG_COLORS.STROKE;
  }

  update(options = {}) {
    Object.assign(this, options);
  }
}

// =============================================================================
// SVG Primitive: Runtime Topology Connector
// =============================================================================

/** Topology connector - connects runtime components visually */
export class SvgTopologyConnector {
  constructor(id, source, target, options = {}) {
    this.id = svgId('connector', id);
    this._source = source;
    this._target = target;
    this.state = options.state || 'connected';
    this.kind = options.kind || 'direct';
    this.thickness = options.thickness || STROKE_WIDTH_NORMAL;
    this.inactive = options.inactive || false;
    this.sequence = options.sequence || 0;
    this.label = options.label || '';
  }

  get source() {
    return this._source;
  }

  get target() {
    return this._target;
  }

  render(parent) {
    const g = createSvgElement('g', {
      id: this.id,
      'data-connector-id': this.id,
      'data-source': this._source.id || String(this._source),
      'data-target': this._target.id || String(this._target),
      'data-state': this.state,
      class: `svg-connector kind-${this.kind} state-${this.state}`
    });

    const sourcePoint = typeof this._source === 'object' ?
      point(this._source.x || 0, this._source.y || 0) : point(0, 0);
    const targetPoint = typeof this._target === 'object' ?
      point(this._target.x || 0, this._target.y || 0) : point(0, 0);

    const path = `M ${sourcePoint.x} ${sourcePoint.y} L ${targetPoint.x} ${targetPoint.y}`;

    const line = createSvgElement('path', {
      d: path,
      fill: 'none',
      stroke: this._getLineColor(),
      'stroke-width': this.thickness,
      'stroke-linecap': 'round',
      'stroke-linejoin': 'round',
      opacity: this.inactive ? SVG_COLORS.OPACITY_LOW : SVG_COLORS.OPACITY_MEDIUM
    });
    g.appendChild(line);

    const midPoint = point(
      (sourcePoint.x + targetPoint.x) / 2,
      (sourcePoint.y + targetPoint.y) / 2
    );

    if (this.sequence > 0) {
      const seqLabel = createSvgElement('text', {
        x: midPoint.x,
        y: midPoint.y - GEOMETRY.LABEL_OFFSET,
        'text-anchor': 'middle',
        'dominant-baseline': 'bottom',
        fill: SVG_COLORS.TEXT_MUTED,
        'font-size': '8',
        'font-family': 'system-ui, sans-serif'
      });
      seqLabel.textContent = String(this.sequence);
      g.appendChild(seqLabel);
    }

    if (this.state !== 'connected') {
      const indicator = createSvgElement('circle', {
        cx: midPoint.x,
        cy: midPoint.y,
        r: 3,
        fill: this._getStateColor(),
        opacity: SVG_COLORS.OPACITY_HIGH
      });
      g.appendChild(indicator);
    }

    if (!this.inactive) {
      const arrowSize = 6;
      const angle = Math.atan2(
        targetPoint.y - sourcePoint.y,
        targetPoint.x - sourcePoint.x
      );
      const arrowPoints = [
        point(targetPoint.x, targetPoint.y),
        point(
          targetPoint.x - arrowSize * Math.cos(angle) - arrowSize * 0.5 * Math.sin(angle),
          targetPoint.y - arrowSize * Math.sin(angle) + arrowSize * 0.5 * Math.cos(angle)
        ),
        point(
          targetPoint.x - arrowSize * Math.cos(angle) + arrowSize * 0.5 * Math.sin(angle),
          targetPoint.y - arrowSize * Math.sin(angle) - arrowSize * 0.5 * Math.cos(angle)
        )
      ];
      const arrow = createSvgElement('polygon', {
        points: arrowPoints.map(p => `${p.x},${p.y}`).join(' '),
        fill: this._getLineColor(),
        opacity: SVG_COLORS.OPACITY_HIGH
      });
      g.appendChild(arrow);
    }

    parent.appendChild(g);
    return g;
  }

  _getLineColor() {
    const stateMap = {
      'disconnected': SVG_COLORS.FAILURE,
      'degraded': SVG_COLORS.INTEGRITY_WARNING,
      'reconnecting': SVG_COLORS.REPLAYING
    };
    return stateMap[this.state] || SVG_COLORS.STROKE;
  }

  _getStateColor() {
    const stateMap = {
      'disconnected': SVG_COLORS.FAILURE,
      'degraded': SVG_COLORS.INTEGRITY_WARNING,
      'reconnecting': SVG_COLORS.REPLAYING
    };
    return stateMap[this.state] || SVG_COLORS.COMPLETE;
  }

  update(options = {}) {
    Object.assign(this, options);
  }
}

// =============================================================================
// SVG Instrumentation Layer
// =============================================================================

/** Manages a collection of SVG instrumentation primitives
 * Bounded, deterministic, replay-safe
 */
export class SvgInstrumentationLayer {
  constructor(container, options = {}) {
    this.container = container;
    this.id = svgId('layer', options.id || 'main');
    this.svg = null;
    this.elements = new Map();
    this.maxElements = options.maxElements || MAX_SVG_ELEMENTS_PER_GROUP;
    this.bounds = options.bounds || rect(0, 0, 800, 600);
    this._initSvg();
  }

  _initSvg() {
    if (!this.container) return;

    this.svg = createSvgElement('svg', {
      id: this.id,
      width: this.bounds.width,
      height: this.bounds.height,
      viewBox: `0 0 ${this.bounds.width} ${this.bounds.height}`,
      xmlns: SVG_NS,
      'xmlns:xlink': 'http://www.w3.org/1999/xlink',
      'aria-hidden': 'true',
      'focusable': 'false'
    });
    this.svg.style.display = 'block';
    this.svg.style.backgroundColor = 'transparent';
    this.container.appendChild(this.svg);
  }

  /** Add an SVG primitive to the layer */
  addPrimitive(primitive) {
    if (this.elements.size >= this.maxElements) {
      const oldestId = this.elements.keys().next().value;
      this.removePrimitive(oldestId);
    }

    const rendered = primitive.render(this.svg);
    this.elements.set(primitive.id, { primitive, element: rendered });
    return primitive.id;
  }

  /** Remove an SVG primitive from the layer */
  removePrimitive(id) {
    const existing = this.elements.get(id);
    if (existing && existing.element && existing.element.parentNode) {
      existing.element.parentNode.removeChild(existing.element);
    }
    this.elements.delete(id);
  }

  /** Update an existing primitive */
  updatePrimitive(id, options = {}) {
    const existing = this.elements.get(id);
    if (existing) {
      existing.primitive.update(options);
      this.removePrimitive(id);
      this.addPrimitive(existing.primitive);
    }
  }

  /** Clear all primitives from the layer */
  clear() {
    for (const id of this.elements.keys()) {
      this.removePrimitive(id);
    }
    this.elements.clear();
  }

  /** Get primitive by ID */
  getPrimitive(id) {
    return this.elements.get(id)?.primitive;
  }

  /** Get all primitives */
  getAllPrimitives() {
    return Array.from(this.elements.values()).map(v => v.primitive);
  }

  /** Resize the SVG container */
  resize(width, height) {
    this.bounds = rect(0, 0, width, height);
    if (this.svg) {
      this.svg.setAttribute('width', width);
      this.svg.setAttribute('height', height);
      this.svg.setAttribute('viewBox', `0 0 ${width} ${height}`);
    }
  }

  /** Update bounds */
  setBounds(bounds) {
    this.bounds = bounds;
    this.resize(bounds.width, bounds.height);
  }
}

// =============================================================================
// Projection -> Geometry Mapping
// =============================================================================

/** Map projection state to geometry coordinates
 * Deterministic mapping ensures replay-safe rendering
 */
export class ProjectionGeometryMapper {
  constructor(bounds, options = {}) {
    this.bounds = bounds || rect(0, 0, 800, 600);
    this.laneCount = options.laneCount || 4;
    this.laneSpacing = options.laneSpacing || GEOMETRY.LANE_HEIGHT + GEOMETRY.LANE_MARGIN;
    this.nodeSpacing = options.nodeSpacing || 120;
    this.padding = options.padding || GEOMETRY.PADDING * 2;
  }

  laneToY(laneIndex) {
    return this.padding + laneIndex * this.laneSpacing + this.laneSpacing / 2 - GEOMETRY.LANE_HEIGHT / 2;
  }

  laneToBounds(laneIndex) {
    return rect(
      this.padding,
      this.laneToY(laneIndex),
      this.bounds.width - this.padding * 2,
      GEOMETRY.LANE_HEIGHT
    );
  }

  sequenceToX(sequence, maxSequence = 100) {
    return this.padding + mapRange(
      sequence,
      0,
      maxSequence,
      0,
      this.bounds.width - this.padding * 2
    );
  }

  throughputToWidth(throughput, maxThroughput = 100) {
    return mapRange(throughput, 0, maxThroughput, 0, this.bounds.width - this.padding * 2);
  }

  getProposalPosition(proposalOrId, laneIndex = 0, sequence = 0) {
    const id = typeof proposalOrId === 'string' ? proposalOrId : proposalOrId.id || '0';
    const hash = this._hashString(id);
    return point(
      this.padding + (hash % 7) * 20 + sequence * 5,
      this.laneToY(laneIndex)
    );
  }

  getIntegrityPosition(markerOrId, laneIndex = 0, sequence = 0) {
    const id = typeof markerOrId === 'string' ? markerOrId : markerOrId.id || '0';
    const hash = this._hashString(id);
    return point(
      this.sequenceToX(sequence),
      this.laneToY(laneIndex) + GEOMETRY.LANE_HEIGHT / 2
    );
  }

  _hashString(str) {
    let hash = 0;
    for (let i = 0; i < str.length; i++) {
      const char = str.charCodeAt(i);
      hash = ((hash << 5) - hash) + char;
      hash = hash & hash;
    }
    return Math.abs(hash);
  }

  getDensityPoints(sequenceStart, sequenceEnd, laneIndex = 0, maxSequences = 100) {
    const points = [];
    const segments = Math.min(20, sequenceEnd - sequenceStart + 1);
    
    for (let i = 0; i <= segments; i++) {
      const seq = sequenceStart + (i / segments) * (sequenceEnd - sequenceStart);
      points.push(point(
        this.sequenceToX(seq, maxSequences),
        this.laneToY(laneIndex) + GEOMETRY.LANE_HEIGHT / 2
      ));
    }
    return points;
  }

  progressToSweepPosition(progress) {
    return point(
      this.bounds.width / 2,
      this.bounds.height / 2 + (progress - 0.5) * this.bounds.height * 0.4
    );
  }
}

// =============================================================================
// Animation State Derivation
// =============================================================================

/** Derive animation state from runtime projection state
 * Animation ONLY derives from real runtime state
 */
export class SvgAnimationState {
  constructor() {
    this.lastState = null;
    this.lastSequence = 0;
    this.lastTimestamp = 0;
  }

  deriveFromProjection(projection) {
    if (!projection) return { motion: 'none', intensity: 0 };

    const state = projection.state || projection.status || 'idle';
    const sequence = projection.sequence || this.lastSequence;
    const now = Date.now();
    const delta = now - this.lastTimestamp;

    this.lastState = state;
    this.lastSequence = sequence;
    this.lastTimestamp = now;

    switch (state.toLowerCase()) {
      case 'streaming':
        return { motion: 'stream', intensity: clamp(delta / 200, 0, 1), direction: 'forward' };
      case 'proposing':
        return { motion: 'pulse', intensity: 0.7, direction: 'none' };
      case 'validating':
        return { motion: 'validate', intensity: 0.6, direction: 'rotate' };
      case 'replaying':
        return { motion: 'replay', intensity: 0.8, direction: 'forward' };
      case 'stalled':
        return { motion: 'none', intensity: 0, direction: 'none' };
      case 'complete':
      case 'completed':
        return { motion: 'fade', intensity: clamp(delta / 500, 0, 1), direction: 'none' };
      case 'failure':
      case 'failed':
        return { motion: 'flash', intensity: 1, direction: 'none' };
      default:
        return { motion: 'none', intensity: 0, direction: 'none' };
    }
  }

  reset() {
    this.lastState = null;
    this.lastSequence = 0;
    this.lastTimestamp = 0;
  }
}

// =============================================================================
// Reconciliation Visibility Primitives (PHASE 8)
// =============================================================================

/**
 * Reconciliation loop visibility primitives.
 * 
 * Core doctrine:
 * - Dashboards become calmer as reconciliation pressure increases
 * - Visualize reconciliation loop state (bounded operational refresh)
 * - No synthetic animation
 * - All state derived from backend projections
 * - No authority inference
 */

/** Reconciliation Loop Indicator
 * Shows the health/state of a reconciliation loop
 * Visualizes: running, converged, error states
 * Calm visualize: reduced motion when stable, subtle indicators when active
 */
export class SvgReconciliationLoopIndicator {
  constructor(id, bounds, options = {}) {
    this.id = svgId('reconciliation-loop', id);
    this.bounds = bounds;
    this.loopId = options.loopId || 'loop';
    this.controllerType = options.controllerType || 'unknown';
    this.status = options.status || 'pending'; // pending, running, converged, error, stopped
    this.iterations = options.iterations || 0;
    this.convergence = options.convergence || 0; // 0-1
    this.dampingActive = options.dampingActive || false;
    this.oscillationDetected = options.oscillationDetected || false;
    this.size = Math.min(bounds.width, bounds.height) * 0.8;
  }

  render(parent) {
    const g = createSvgElement('g', {
      id: this.id,
      'data-loop-id': this.loopId,
      'data-controller-type': this.controllerType,
      'data-status': this.status,
      class: `svg-reconciliation-loop status-${this.status}`
    });

    const center = centerOf(this.bounds);
    const radius = this.size / 2;

    // Background circle (track)
    const track = createSvgElement('circle', {
      cx: center.x,
      cy: center.y,
      r: radius,
      fill: 'none',
      stroke: SVG_COLORS.GRID,
      'stroke-width': STROKE_WIDTH_THIN,
      opacity: SVG_COLORS.OPACITY_LOW
    });
    g.appendChild(track);

    // Status arc (shows convergence progress)
    if (this.status === 'running' || this.status === 'converged') {
      const arcRadius = radius - STROKE_WIDTH_NORMAL;
      const arcEndAngle = -Math.PI / 2 + this.convergence * Math.PI * 2;
      const largeArc = this.convergence > 0.5 ? 1 : 0;

      const x1 = center.x + arcRadius * Math.cos(-Math.PI / 2);
      const y1 = center.y + arcRadius * Math.sin(-Math.PI / 2);
      const x2 = center.x + arcRadius * Math.cos(arcEndAngle);
      const y2 = center.y + arcRadius * Math.sin(arcEndAngle);

      const arc = createSvgElement('path', {
        d: `M ${center.x} ${center.y} L ${x1} ${y1} A ${arcRadius} ${arcRadius} 0 ${largeArc} 1 ${x2} ${y2}`,
        fill: 'none',
        stroke: this.status === 'converged' ? SVG_COLORS.SUCCESS : SVG_COLORS.STREAMING,
        'stroke-width': STROKE_WIDTH_NORMAL,
        'stroke-linecap': 'round',
        opacity: SVG_COLORS.OPACITY_MEDIUM
      });
      g.appendChild(arc);
    }

    // Center indicator (state-dependent)
    const centerIndicator = this._createCenterIndicator(center);
    g.appendChild(centerIndicator);

    // Damping indicator (small dot when active)
    if (this.dampingActive) {
      const dampRadius = radius * 0.2;
      const dampIndicator = createSvgElement('circle', {
        cx: center.x + radius * 0.4,
        cy: center.y - radius * 0.4,
        r: dampRadius,
        fill: SVG_COLORS.WARNING,
        opacity: SVG_COLORS.OPACITY_LOW
      });
      g.appendChild(dampIndicator);
    }

    // Oscillation warning indicator
    if (this.oscillationDetected) {
      const oscIndicator = createSvgElement('circle', {
        cx: center.x,
        cy: center.y - radius * 0.7,
        r: radius * 0.15,
        fill: SVG_COLORS.ERROR,
        opacity: pulseOpacity(0.5, 1500) // Slow pulse to reduce visual noise
      });
      g.appendChild(oscIndicator);
    }

    // Iteration count
    if (this.iterations > 0 && radius > 20) {
      const itLabel = createSvgElement('text', {
        x: center.x,
        y: center.y + radius + GEOMETRY.LABEL_OFFSET,
        'text-anchor': 'middle',
        'dominant-baseline': 'middle',
        fill: SVG_COLORS.TEXT_MUTED,
        'font-size': '8',
        'font-family': 'system-ui, sans-serif'
      });
      itLabel.textContent = `it:${this.iterations}`;
      g.appendChild(itLabel);
    }

    // Loop ID label
    if (radius > 30) {
      const idLabel = createSvgElement('text', {
        x: center.x,
        y: center.y - radius - GEOMETRY.LABEL_OFFSET,
        'text-anchor': 'middle',
        'dominant-baseline': 'bottom',
        fill: SVG_COLORS.FOREGROUND,
        'font-size': '9',
        'font-family': 'system-ui, sans-serif'
      });
      const shortId = this.loopId.length > 12 ? this.loopId.substring(0, 10) + '..' : this.loopId;
      idLabel.textContent = shortId;
      g.appendChild(idLabel);
    }

    parent.appendChild(g);
    return g;
  }

  _createCenterIndicator(center) {
    const radius = this.size * 0.3;

    switch (this.status) {
      case 'running':
        return createSvgElement('circle', {
          cx: center.x,
          cy: center.y,
          r: radius,
          fill: SVG_COLORS.STREAMING,
          opacity: SVG_COLORS.OPACITY_MEDIUM
        });

      case 'converged':
        return createSvgElement('polygon', {
          points: [
            `${center.x},${center.y - radius}`,
            `${center.x + radius * 0.7},${center.y + radius * 0.4}`,
            `${center.x - radius * 0.7},${center.y + radius * 0.4}`
          ].join(' '),
          fill: SVG_COLORS.SUCCESS,
          opacity: SVG_COLORS.OPACITY_HIGH
        });

      case 'error':
        return createSvgElement('rect', {
          x: center.x - radius,
          y: center.y - radius,
          width: radius * 2,
          height: radius * 2,
          fill: SVG_COLORS.ERROR,
          opacity: SVG_COLORS.OPACITY_MEDIUM,
          rx: 2,
          ry: 2
        });

      case 'stopped':
        return createSvgElement('rect', {
          x: center.x - radius,
          y: center.y - radius,
          width: radius * 2,
          height: radius * 2,
          fill: SVG_COLORS.GRID,
          opacity: SVG_COLORS.OPACITY_LOW
        });

      default: // pending
        return createSvgElement('circle', {
          cx: center.x,
          cy: center.y,
          r: radius,
          fill: SVG_COLORS.GRID,
          opacity: SVG_COLORS.OPACITY_LOW,
          stroke: SVG_COLORS.FOREGROUND,
          'stroke-width': STROKE_WIDTH_THIN
        });
    }
  }

  update(options) {
    this.status = options.status || this.status;
    this.iterations = options.iterations || this.iterations;
    this.convergence = options.convergence !== undefined ? options.convergence : this.convergence;
    this.dampingActive = options.dampingActive !== undefined ? options.dampingActive : this.dampingActive;
    this.oscillationDetected = options.oscillationDetected !== undefined ? options.oscillationDetected : this.oscillationDetected;
  }
}

/**
 * Cadence Visibility Indicator
 * Shows the cadence (refresh interval) of reconciliation loops
 * Visualizes: cadence bounds, current interval, jitter
 * Calm visualization: subtle pulsing aligned with cadence
 */
export class SvgReconciliationCadenceIndicator {
  constructor(id, bounds, options = {}) {
    this.id = svgId('reconciliation-cadence', id);
    this.bounds = bounds;
    this.loopId = options.loopId || 'loop';
    this.minInterval = options.minInterval || 0.1; // seconds
    this.maxInterval = options.maxInterval || 10.0; // seconds
    this.currentInterval = options.currentInterval || 1.0; // seconds
    this.jitterFactor = options.jitterFactor || 0.1;
    this.nextTickIn = options.nextTickIn || 0; // seconds
    this.size = bounds.height * 0.8;
  }

  render(parent) {
    const g = createSvgElement('g', {
      id: this.id,
      'data-loop-id': this.loopId,
      class: 'svg-reconciliation-cadence'
    });

    const centerX = this.bounds.width / 2;
    const top = 10;
    const barHeight = this.size / 3;
    const barWidth = this.bounds.width * 0.6;

    // Min interval bar
    const minY = top;
    const minBar = createSvgElement('rect', {
      x: centerX - barWidth / 2,
      y: minY,
      width: barWidth * (this.minInterval / this.maxInterval),
      height: barHeight,
      fill: SVG_COLORS.GRID,
      opacity: SVG_COLORS.OPACITY_LOW
    });
    g.appendChild(minBar);

    // Max interval bar (background)
    const maxY = minY + barHeight + 4;
    const maxBar = createSvgElement('rect', {
      x: centerX - barWidth / 2,
      y: maxY,
      width: barWidth,
      height: barHeight,
      fill: SVG_COLORS.GRID,
      opacity: SVG_COLORS.OPACITY_LOW,
      stroke: SVG_COLORS.FOREGROUND,
      'stroke-width': STROKE_WIDTH_THIN
    });
    g.appendChild(maxBar);

    // Current interval indicator
    const currentY = maxY + barHeight + 4;
    const currentWidth = barWidth * (this.currentInterval / this.maxInterval);
    const currentBar = createSvgElement('rect', {
      x: centerX - barWidth / 2,
      y: currentY,
      width: Math.max(2, currentWidth),
      height: barHeight * 1.5,
      fill: this.nextTickIn < 0.5 ? SVG_COLORS.STREAMING : SVG_COLORS.FOREGROUND,
      opacity: this.nextTickIn < 0.5 ? pulseOpacity(0.7, 500) : SVG_COLORS.OPACITY_MEDIUM,
      'stroke-width': STROKE_WIDTH_THIN
    });
    // Add stroke if interval is outside bounds
    if (this.currentInterval < this.minInterval || this.currentInterval > this.maxInterval) {
      currentBar.setAttribute('stroke', SVG_COLORS.WARNING);
    }
    g.appendChild(currentBar);

    // Jitter indicator (small notches at ends)
    if (this.jitterFactor > 0) {
      const notchSize = barHeight * 0.4;
      const leftNotch = createSvgElement('rect', {
        x: centerX - barWidth / 2 - notchSize / 2,
        y: maxY + barHeight / 2 - notchSize / 2,
        width: notchSize,
        height: notchSize,
        fill: SVG_COLORS.FOREGROUND,
        opacity: SVG_COLORS.OPACITY_LOW
      });
      const rightNotch = createSvgElement('rect', {
        x: centerX + barWidth / 2 - notchSize / 2,
        y: maxY + barHeight / 2 - notchSize / 2,
        width: notchSize,
        height: notchSize,
        fill: SVG_COLORS.FOREGROUND,
        opacity: SVG_COLORS.OPACITY_LOW
      });
      g.appendChild(leftNotch);
      g.appendChild(rightNotch);
    }

    // Next tick indicator (countdown)
    if (this.bounds.height > 60 && this.nextTickIn > 0) {
      const tickLabel = createSvgElement('text', {
        x: centerX,
        y: currentY + barHeight * 1.5 + 10,
        'text-anchor': 'middle',
        'dominant-baseline': 'middle',
        fill: SVG_COLORS.TEXT_MUTED,
        'font-size': '8',
        'font-family': 'system-ui, sans-serif'
      });
      tickLabel.textContent = `${this.nextTickIn.toFixed(1)}s`;
      g.appendChild(tickLabel);
    }

    parent.appendChild(g);
    return g;
  }

  update(options) {
    this.currentInterval = options.currentInterval || this.currentInterval;
    this.nextTickIn = options.nextTickIn !== undefined ? options.nextTickIn : this.nextTickIn;
    this.minInterval = options.minInterval || this.minInterval;
    this.maxInterval = options.maxInterval || this.maxInterval;
    this.jitterFactor = options.jitterFactor !== undefined ? options.jitterFactor : this.jitterFactor;
  }
}

/**
 * Damping Visibility Indicator
 * Shows damping state for oscillation prevention
 * Visualizes: damping type, current factor, oscillation detected
 * Calm visualization: subtle, non-intrusive indicators
 */
export class SvgDampingIndicator {
  constructor(id, bounds, options = {}) {
    this.id = svgId('damping', id);
    this.bounds = bounds;
    this.loopId = options.loopId || 'loop';
    this.dampingType = options.dampingType || 'exponential';
    this.currentFactor = options.currentFactor || 1.0; // 0-1
    this.iterationsApplied = options.iterationsApplied || 0;
    this.oscillationDetected = options.oscillationDetected || false;
    this.size = Math.min(bounds.width, bounds.height);
  }

  render(parent) {
    const g = createSvgElement('g', {
      id: this.id,
      'data-loop-id': this.loopId,
      class: `svg-damping-indicator type-${this.dampingType}`
    });

    const pad = 4;
    const innerBounds = rect(pad, pad, this.bounds.width - pad * 2, this.bounds.height - pad * 2);
    const center = centerOf(innerBounds);

    // Factor bar (horizontal)
    const barWidth = innerBounds.width * 0.8;
    const barHeight = innerBounds.height * 0.25;
    const barY = center.y - barHeight / 2;

    // Background track
    const track = createSvgElement('rect', {
      x: center.x - barWidth / 2,
      y: barY,
      width: barWidth,
      height: barHeight,
      fill: SVG_COLORS.GRID,
      opacity: SVG_COLORS.OPACITY_LOW
    });
    g.appendChild(track);

    // Current factor fill
    const fillWidth = barWidth * this.currentFactor;
    const fill = createSvgElement('rect', {
      x: center.x - barWidth / 2,
      y: barY,
      width: fillWidth,
      height: barHeight,
      fill: this.oscillationDetected ? SVG_COLORS.WARNING : SVG_COLORS.STREAMING,
      opacity: this.oscillationDetected ? SVG_COLORS.OPACITY_HIGH : SVG_COLORS.OPACITY_MEDIUM
    });
    g.appendChild(fill);

    // Type indicator (small glyph)
    const typeIndicator = this._createTypeGlyph(center.x - barWidth / 2 - 8, center.y);
    g.appendChild(typeIndicator);

    // Factor label
    if (innerBounds.height > 30) {
      const label = createSvgElement('text', {
        x: center.x,
        y: center.y + barHeight / 2 + 8,
        'text-anchor': 'middle',
        'dominant-baseline': 'middle',
        fill: SVG_COLORS.FOREGROUND,
        'font-size': '9',
        'font-family': 'system-ui, sans-serif'
      });
      label.textContent = this.currentFactor.toFixed(2);
      g.appendChild(label);
    }

    // Iteration count
    if (this.iterationsApplied > 0 && innerBounds.height > 40) {
      const iterLabel = createSvgElement('text', {
        x: center.x + barWidth / 2 + 8,
        y: center.y,
        'text-anchor': 'start',
        'dominant-baseline': 'middle',
        fill: SVG_COLORS.TEXT_MUTED,
        'font-size': '8',
        'font-family': 'system-ui, sans-serif'
      });
      iterLabel.textContent = `x${this.iterationsApplied}`;
      g.appendChild(iterLabel);
    }

    parent.appendChild(g);
    return g;
  }

  _createTypeGlyph(x, y) {
    const size = 6;
    const half = size / 2;

    switch (this.dampingType) {
      case 'exponential':
        return createSvgElement('polygon', {
          points: [
            `${x - half},${y - half}`,
            `${x + half},${y + half}`,
            `${x},${y + half}`
          ].join(' '),
          fill: SVG_COLORS.STREAMING,
          opacity: SVG_COLORS.OPACITY_MEDIUM
        });

      case 'linear':
        return createSvgElement('line', {
          x1: x - half,
          y1: y - half,
          x2: x + half,
          y2: y + half,
          stroke: SVG_COLORS.FOREGROUND,
          'stroke-width': 1,
          opacity: SVG_COLORS.OPACITY_MEDIUM
        });

      case 'threshold':
        return createSvgElement('rect', {
          x: x - half,
          y: y - half,
          width: size,
          height: size,
          fill: SVG_COLORS.GRID,
          opacity: SVG_COLORS.OPACITY_MEDIUM
        });

      case 'hysteresis':
        return createSvgElement('circle', {
          cx: x,
          cy: y,
          r: half,
          fill: 'none',
          stroke: SVG_COLORS.FOREGROUND,
          'stroke-width': 1,
          opacity: SVG_COLORS.OPACITY_MEDIUM
        });

      default:
        return createSvgElement('circle', {
          cx: x,
          cy: y,
          r: half,
          fill: SVG_COLORS.GRID,
          opacity: SVG_COLORS.OPACITY_LOW
        });
    }
  }

  update(options) {
    this.dampingType = options.dampingType || this.dampingType;
    this.currentFactor = options.currentFactor !== undefined ? options.currentFactor : this.currentFactor;
    this.iterationsApplied = options.iterationsApplied || this.iterationsApplied;
    this.oscillationDetected = options.oscillationDetected !== undefined ? options.oscillationDetected : this.oscillationDetected;
  }
}

/**
 * Convergence State Indicator
 * Shows convergence state for bounded operational reconciliation
 * Visualizes: iteration progress, time remaining, convergence status
 * Calm visualization: becomes more subtle as convergence approaches
 */
export class SvgConvergenceIndicator {
  constructor(id, bounds, options = {}) {
    this.id = svgId('convergence', id);
    this.bounds = bounds;
    this.loopId = options.loopId || 'loop';
    this.currentIteration = options.currentIteration || 0;
    this.totalIterations = options.totalIterations || 100;
    this.currentDuration = options.currentDuration || 0; // seconds
    this.maxDuration = options.maxDuration || 60; // seconds
    this.converged = options.converged || false;
    this.stabilisationThreshold = options.stabilisationThreshold || 0.001;
    this.size = Math.min(bounds.width, bounds.height) * 0.9;
  }

  render(parent) {
    const g = createSvgElement('g', {
      id: this.id,
      'data-loop-id': this.loopId,
      class: `svg-convergence-indicator ${this.converged ? 'converged' : 'converging'}`
    });

    const center = centerOf(this.bounds);
    const pad = 8;
    const innerSize = this.size - pad * 2;
    const innerCenter = point(center.x, center.y);

    // Outer ring (iteration progress)
    const outerRadius = innerSize / 2;
    const track = createSvgElement('circle', {
      cx: innerCenter.x,
      cy: innerCenter.y,
      r: outerRadius,
      fill: 'none',
      stroke: SVG_COLORS.GRID,
      'stroke-width': STROKE_WIDTH_THIN,
      opacity: SVG_COLORS.OPACITY_LOW
    });
    g.appendChild(track);

    // Iteration progress arc
    if (this.totalIterations > 0) {
      const progress = Math.min(this.currentIteration / this.totalIterations, 1);
      const arcEndAngle = -Math.PI / 2 + progress * Math.PI * 2;
      const largeArc = progress > 0.5 ? 1 : 0;

      const x1 = innerCenter.x + outerRadius * Math.cos(-Math.PI / 2);
      const y1 = innerCenter.y + outerRadius * Math.sin(-Math.PI / 2);
      const x2 = innerCenter.x + outerRadius * Math.cos(arcEndAngle);
      const y2 = innerCenter.y + outerRadius * Math.sin(arcEndAngle);

      const arc = createSvgElement('path', {
        d: `M ${innerCenter.x} ${innerCenter.y} L ${x1} ${y1} A ${outerRadius} ${outerRadius} 0 ${largeArc} 1 ${x2} ${y2}`,
        fill: 'none',
        stroke: SVG_COLORS.STREAMING,
        'stroke-width': STROKE_WIDTH_NORMAL,
        'stroke-linecap': 'round',
        opacity: this.converged ? SVG_COLORS.OPACITY_LOW : SVG_COLORS.OPACITY_MEDIUM
      });
      g.appendChild(arc);
    }

    // Inner circle (time/duration progress)
    const innerRadius = outerRadius * 0.6;
    const timeProgress = Math.min(this.currentDuration / this.maxDuration, 1);

    if (this.maxDuration > 0) {
      const timeArcEndAngle = -Math.PI / 2 + timeProgress * Math.PI * 2;
      const largeArc = timeProgress > 0.5 ? 1 : 0;

      const tx1 = innerCenter.x + innerRadius * Math.cos(-Math.PI / 2);
      const ty1 = innerCenter.y + innerRadius * Math.sin(-Math.PI / 2);
      const tx2 = innerCenter.x + innerRadius * Math.cos(timeArcEndAngle);
      const ty2 = innerCenter.y + innerRadius * Math.sin(timeArcEndAngle);

      const timeArc = createSvgElement('path', {
        d: `M ${innerCenter.x} ${innerCenter.y} L ${tx1} ${ty1} A ${innerRadius} ${innerRadius} 0 ${largeArc} 1 ${tx2} ${ty2}`,
        fill: 'none',
        stroke: SVG_COLORS.FOREGROUND,
        'stroke-width': STROKE_WIDTH_THIN,
        'stroke-linecap': 'round',
        opacity: this.converged ? SVG_COLORS.OPACITY_LOW : SVG_COLORS.OPACITY_MEDIUM
      });
      g.appendChild(timeArc);
    }

    // Convergence status indicator
    const statusIndicator = this._createStatusIndicator(innerCenter, outerRadius * 0.4);
    g.appendChild(statusIndicator);

    // Iteration label
    if (outerRadius > 20) {
      const iterLabel = createSvgElement('text', {
        x: innerCenter.x,
        y: innerCenter.y + outerRadius + 12,
        'text-anchor': 'middle',
        'dominant-baseline': 'middle',
        fill: SVG_COLORS.FOREGROUND,
        'font-size': '8',
        'font-family': 'system-ui, sans-serif'
      });
      iterLabel.textContent = `${this.currentIteration}/${this.totalIterations}`;
      g.appendChild(iterLabel);
    }

    // Time label
    if (outerRadius > 20) {
      const timeLabel = createSvgElement('text', {
        x: innerCenter.x,
        y: innerCenter.y - outerRadius - 12,
        'text-anchor': 'middle',
        'dominant-baseline': 'middle',
        fill: SVG_COLORS.TEXT_MUTED,
        'font-size': '7',
        'font-family': 'system-ui, sans-serif'
      });
      const timeRemaining = Math.max(0, this.maxDuration - this.currentDuration);
      timeLabel.textContent = `${timeRemaining.toFixed(1)}s`;
      g.appendChild(timeLabel);
    }

    parent.appendChild(g);
    return g;
  }

  _createStatusIndicator(center, radius) {
    if (this.converged) {
      // Converged: checkmark
      return createSvgElement('polygon', {
        points: [
          `${center.x - radius * 0.3},${center.y}`,
          `${center.x},${center.y + radius * 0.3}`,
          `${center.x + radius * 0.5},${center.y - radius * 0.4}`
        ].join(' '),
        fill: SVG_COLORS.SUCCESS,
        opacity: SVG_COLORS.OPACITY_HIGH
      });
    } else {
      // Converging: arrow pointing towards center
      return createSvgElement('polygon', {
        points: [
          `${center.x},${center.y - radius * 0.4}`,
          `${center.x - radius * 0.3},${center.y}`,
          `${center.x + radius * 0.3},${center.y}`
        ].join(' '),
        fill: SVG_COLORS.STREAMING,
        opacity: SVG_COLORS.OPACITY_MEDIUM
      });
    }
  }

  update(options) {
    this.currentIteration = options.currentIteration !== undefined ? options.currentIteration : this.currentIteration;
    this.totalIterations = options.totalIterations || this.totalIterations;
    this.currentDuration = options.currentDuration !== undefined ? options.currentDuration : this.currentDuration;
    this.maxDuration = options.maxDuration || this.maxDuration;
    this.converged = options.converged !== undefined ? options.converged : this.converged;
    this.stabilisationThreshold = options.stabilisationThreshold !== undefined ? options.stabilisationThreshold : this.stabilisationThreshold;
  }
}

/**
 * Helper for calm pulse opacity (reduced motion as pressure increases)
 * Returns CSS opacity value that pulses slowly
 */
function pulseOpacity(baseOpacity, periodMs) {
  // In a real implementation, this would use actual time
  // For now, return a static value that can be animated via CSS
  return baseOpacity;
}
