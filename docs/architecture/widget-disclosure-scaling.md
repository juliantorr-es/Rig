# Progressive Disclosure Widget Sizes

> **Three Disclosure Scales Per Widget - Canonical Instrumentation Depths**

## Core Principle

Every Rig widget has **exactly three disclosure scales**: SMALL, MEDIUM, LARGE. Each scale provides a **deterministic, bounded, replay-safe** visualization depth. Disclosure scaling is **progressive, intentional, and cognitively governed** - users expand depth deliberately, not automatically.

---

## Disclosure Scale Philosophy

### SMALL: Calm Overview
- **Purpose**: Operational snapshot at a glance
- **Cognitive Load**: Minimal
- **Motion**: None (static only)
- **Information Density**: Low (summary level)
- **User Intent**: "What's the status?"

### MEDIUM: Active Instrumentation
- **Purpose**: Active monitoring and interaction
- **Cognitive Load**: Moderate
- **Motion**: Minimal (calm indicators only)
- **Information Density**: Medium (detail level)
- **User Intent**: "What's happening?"

### LARGE: Deep Inspection
- **Purpose**: Detailed analysis and forensics
- **Cognitive Load**: High (requires focus)
- **Motion**: Reduced (governed, low-stimulation)
- **Information Density**: High (full detail)
- **User Intent**: "Why is this happening?"

---

## Scale Definitions by Widget

### Runtime Overview Widget

| Scale | Content | Motion | Density | Geometry |
|-------|---------|--------|---------|----------|
| SMALL (3x1) | Current runtime state, overall health indicator | None | Low | Single state icon, 2-3 metrics |
| MEDIUM (3x2) | Runtime state, throughput summary, lane activity overview | Subtle pulsing on active lanes | Medium | State icon + 4-6 metrics, lane sparklines |
| LARGE (3x3) | Full runtime state, all metrics, per-lane throughput, provider status | Governed pulsing, throughput animation | High | State icon + 8-12 metrics, lane detail bars |

**Content by Scale:**
- SMALL: `state`, `overall_health`, `stream_count`
- MEDIUM: SMALL + `throughput`, `lane_activity`, `provider_count`, `latency_avg`
- LARGE: MEDIUM + `per_lane_throughput`, `provider_status`, `memory_usage`, `error_rate`

---

### Status Card Widget

| Scale | Content | Motion | Density | Geometry |
|-------|---------|--------|---------|----------|
| SMALL (3x1) | Current sequence, runtime state, integrity summary | None | Low | 3 compact indicators |
| MEDIUM (3x2) | Sequence, state, integrity, capability summary, recent alerts | Minimal state transitions | Medium | 4-6 indicators, compact sparkline |
| LARGE (3x3) | Full sequence info, state history, integrity chain, capability matrix, alert log | Reduced-motion state transitions | High | 8-10 indicators, full sparklines |

**Content by Scale:**
- SMALL: `current_sequence`, `state`, `integrity_summary`
- MEDIUM: SMALL + `capability_summary`, `recent_alerts`, `timestamp`
- LARGE: MEDIUM + `state_history`, `integrity_chain`, `capability_matrix`, `alert_log`

---

### Topology Panel Widget

| Scale | Content | Motion | Density | Geometry |
|-------|---------|--------|---------|----------|
| SMALL (6x4) | Static topology skeleton, lane boundaries, lane labels | None | Low | Lane boundaries only, node positions as points |
| MEDIUM (6x6) | Full topology, nodes, connectors, routing paths, basic flow indicators | Subtle flow animation | Medium | Full nodes + connectors + routing paths |
| LARGE (9x8) | Full topology + DTG overlay, integrity markers, throughput bars, replay sweep | Governed flow animation, reduced-motion replay sweep | High | Full topology + DTG nodes + edges + all overlays |

**Content by Scale:**
- SMALL: `lanes`, `lane_boundaries`, `lane_labels`, `node_positions`
- MEDIUM: SMALL + `nodes`, `connectors`, `routing_paths`, `flow_indicators`
- LARGE: MEDIUM + `dtg_nodes`, `dtg_edges`, `integrity_markers`, `throughput_bars`, `replay_sweep`

---

### DTG Viewer Widget

| Scale | Content | Motion | Density | Geometry |
|-------|---------|--------|---------|----------|
| SMALL (6x4) | Root node only, summary stats | None | Low | Single root node with summary |
| MEDIUM (6x6) | Root + immediate children, basic edge visibility | None | Medium | Root + children (max 15 nodes), basic edges |
| LARGE (9x8) | Full DTG, all nodes, all edges, lineage paths, supervision detail | None (static visualization) | High | Full DTG (max 200 nodes, 500 edges) |

**Content by Scale:**
- SMALL: `root_node`, `total_nodes`, `total_edges`, `max_depth`
- MEDIUM: SMALL + `immediate_children` (max 10), `immediate_edges` (max 20)
- LARGE: Full DTG with `all_nodes`, `all_edges`, `lineage_paths`, `supervision_overlay`

**DTG Collapse Behavior:**
- SMALL: Only root visible, all children abstracted
- MEDIUM: Root + children visible, grandchildren abstracted
- LARGE: Full hierarchy visible with optional manual collapse

---

### Stream Card Widget

| Scale | Content | Motion | Density | Geometry |
|-------|---------|--------|---------|----------|
| SMALL (3x2) | Stream ID, channel, sequence, timestamp | None | Low | 4 compact fields |
| MEDIUM (4x3) | Stream ID, channel, sequence, content preview, provider, integrity | Minimal pulsing on new chunks | Medium | 6-8 fields, preview text |
| LARGE (6x4) | Full stream data, all chunks, provider detail, capability, full content | Reduced-motion chunk arrival | High | All fields, full content, chunk list |

**Content by Scale:**
- SMALL: `stream_id`, `channel`, `sequence`, `timestamp`
- MEDIUM: SMALL + `content_preview` (50 chars), `provider`, `integrity`
- LARGE: MEDIUM + `full_content`, `all_chunks`, `provider_detail`, `capability`

**Stream Card Lane Alignment:**
- Must be placed in sidebar row corresponding to its lane
- Height scales with disclosure, width fixed at lane width
- Multiple stream cards in same lane stack vertically

---

### Replay Controls Widget

| Scale | Content | Motion | Density | Geometry |
|-------|---------|--------|---------|----------|
| SMALL (4x1) | Play, pause, stop, position indicator | None | Low | 4 buttons + position text |
| MEDIUM (4x2) | Play, pause, stop, scrub bar, position, speed, mode | Scrub bar interaction (no animation) | Medium | 4 buttons + scrub bar + 4 controls |
| LARGE (6x2) | Full controls, scrub bar with markers, speed controls, mode selector, replay history | Instant scrub (no animation), reduced-motion sweep | High | Full control set + scrub bar with markers + history |

**Content by Scale:**
- SMALL: `play`, `pause`, `stop`, `position_text`
- MEDIUM: SMALL + `scrub_bar`, `speed_control`, `mode_selector`, `replay_state`
- LARGE: MEDIUM + `scrub_markers` (integrity, capability events), `speed_presets`, `mode_options`, `replay_history`

**Replay Motion Governance:**
- Scrubbing is INSTANT - no animation
- Replay sweep is REDUCED-MOTION - low stimulation
- Position indicator updates instantly
- No smooth transitions on replay state changes

---

### Intent Console Widget

| Scale | Content | Motion | Density | Geometry |
|-------|---------|--------|---------|----------|
| SMALL (3x2) | Current intent, status, timestamp | None | Low | 3 fields |
| MEDIUM (3x3) | Intent, status, progress, recent history, next safe action | Minimal progress indicator | Medium | 5-6 fields, compact history |
| LARGE (6x4) | Full intent detail, complete history, validation state, blocked actions, allowed actions | Reduced-motion progress | High | Full intent data, complete history, action matrices |

**Content by Scale:**
- SMALL: `intent`, `status`, `timestamp`
- MEDIUM: SMALL + `progress`, `recent_history` (5 entries), `next_safe_action`
- LARGE: MEDIUM + `complete_history`, `validation_state`, `blocked_actions`, `allowed_actions`, `recommendation`

---

### Integrity Panel Widget

| Scale | Content | Motion | Density | Geometry |
|-------|---------|--------|---------|----------|
| SMALL (3x2) | Integrity summary, overall health score | None | Low | 2 compact indicators |
| MEDIUM (3x3) | Health score, violation count, recent violations, severity breakdown | Minimal severity coloring | Medium | 4-6 indicators, compact list |
| LARGE (6x4) | Full integrity state, all violations, severity breakdown, historical trends, resolution suggestions | Reduced-motion violation highlighting | High | Complete violation list, charts, suggestions |

**Content by Scale:**
- SMALL: `health_score`, `violation_count`
- MEDIUM: SMALL + `recent_violations` (5), `severity_breakdown`
- LARGE: MEDIUM + `all_violations`, `historical_trends`, `resolution_suggestions`, `integrity_chain`

---

### Proposal Console Widget

| Scale | Content | Motion | Density | Geometry |
|-------|---------|--------|---------|----------|
| SMALL (6x4) | Proposal summary, current gate, next safe action | None | Low | 3-4 fields |
| MEDIUM (6x4) | Proposal summary, gate state, validation summary, changed files | Minimal state transition | Medium | 6-8 fields, file list |
| LARANGE (9x6) | Full proposal, gate state, validation detail, changed files with diffs, recommendation state, validation history | Reduced-motion gate transitions | High | Complete proposal data, full diffs, history |

**Content by Scale:**
- SMALL: `proposal_summary`, `current_gate`, `next_safe_action`
- MEDIUM: SMALL + `validation_summary`, `changed_files` (names only)
- LARGE: MEDIUM + `validation_detail`, `file_diffs`, `recommendation_state`, `validation_history`

---

### Onboarding Panel Widget

| Scale | Content | Motion | Density | Geometry |
|-------|---------|--------|---------|----------|
| SMALL (4x3) | Current stage, stage title, progress indicator | None | Low | 3 fields |
| MEDIUM (4x4) | Stage title, progress, current lesson, hint | Minimal stage transition | Medium | 4-6 fields |
| LARGE (6x5) | Full onboarding, stage content, interactive tutorial, contextual hints | Reduced-motion stage transitions, instant tutorial steps | High | Complete tutorial content, interactive elements |

**Content by Scale:**
- SMALL: `stage`, `stage_title`, `progress_indicator`
- MEDIUM: SMALL + `current_lesson`, `hint`, `action_button`
- LARGE: MEDIUM + `full_stage_content`, `interactive_tutorial`, `contextual_hints`, `runtime_explanation`

---

## Canonical Scale Properties

### Deterministic Scaling
All scaling between states is **deterministic**:
- Same widget type + same scale = same geometry
- Same widget instance + same scale = same render output
- Scale transitions are instant, not animated

### Replay-Safe Scaling
Scaling behavior is **replay-safe**:
- Widget at scale N during recording = widget at scale N during replay
- All content visible at scale N is identical on replay
- Scale state is part of workspace persistence

### Density-Aware Scaling
Scaling respects **density collapse**:
- At high density, widgets auto-scale down (LARGE -> MEDIUM -> SMALL)
- Auto-scaling is deterministic and user-overridable
- User can force a specific scale regardless of density

### Reduced-Motion Participation
All motion at all scales respects `prefers-reduced-motion`:
- SMALL: No motion (always compliant)
- MEDIUM: Has reduced-motion variants of all animations
- LARGE: Has reduced-motion variants, plus low-stimulation mode

---

## Scaling Transitions

### Transition Philosophy
**Widgets do NOT animate between scales.** Scale changes are instantaneous:
1. Old scale render removed
2. New scale render added
3. No intermediate states
4. No fade, slide, or scale transitions

### Transition Timing
| Action | Duration | Reasoning |
|--------|----------|-----------|
| Scale change | 0ms | Instant, no animation |
| Content update within scale | 0ms | Instant, maintains truthfulness |
|Hover interaction | 0ms | Instant feedback |
| Focus interaction | 0ms | Instant feedback |

### Transition Governance
- No `transition:` CSS properties for scale changes
- No `animation:` CSS properties for scale changes
- Scale change is a discrete state change, not a continuous animation
- Content within a scale may have minimal motion (per widget rules)

---

## Semantic Hierarchy Across Scales

### Information Priority
Each scale preserves **semantic hierarchy**:
1. **Critical**: Always visible at all scales (runtime state, integrity summary)
2. **Primary**: Visible at MEDIUM and LARGE
3. **Secondary**: Visible at LARGE only
4. **Contextual**: Visible only when relevant (context-dependent)

### Visual Hierarchy
| Layer | Content | Visibility |
|-------|---------|------------|
| Foreground | Primary metrics, current state | Always |
| Midground | Secondary metrics, historical context | MEDIUM+ |
| Background | Full detail, analytics, forensics | LARGE only |

---

## Disclosure Persistence

### Scale State Persistence
- Widget scale is persisted with workspace layout
- Default scale per widget type is MEDIUM
- User can set preferred scale per widget
- Scale persists across workspace sessions

### Disclosure Memory
- Each widget remembers its last scale
- Expanding disclosure layer restores widget to its last scale
- Collapsing disclosure layer persists widget scale (restored on expand)

### Scale Inheritance
- Widget scale is independent of disclosure layer
- Disclosure layer controls **visibility**, widget scale controls **detail level**
- Both are persisted independently

---

## Topology Expansion Behavior

### Topology at Different Scales
| Widget | SMALL | MEDIUM | LARGE |
|--------|-------|--------|-------|
| Topology Panel | Static skeleton | Full topology | Full + DTG overlay |
| DTG Viewer | Root only | Root + children | Full hierarchy |
| Stream Card | Compact metadata | Preview + metadata | Full stream |
| Replay Controls | Basic controls | Controls + scrub | Full controls + markers |

### Topology Visual Consistency
- Topology visualization is **consistent** across scales
- Same topology data renders differently, but **semantically equivalently**
- SMALL abstracts, MEDIUM summarizes, LARGE details
- All scales show the **same underlying truth**

### Expansion Governance
- Expanding a widget NEVER changes other widgets
- Expanding a widget NEVER triggers automatic expansion of related widgets
- All expansion is **explicit user action**
- No cascade expansion

---

## Compliance Checklist

- [ ] All widgets have exactly three scales (SMALL, MEDIUM, LARGE)
- [ ] Scale content is deterministic
- [ ] Scale geometry is stable across renders
- [ ] Scale transitions are instant (no animation)
- [ ] Replay produces identical scales
- [ ] Density-aware scaling is active
- [ ] Reduced-motion compliance at all scales
- [ ] Semantic hierarchy preserved across scales
- [ ] Disclosure persistence for scale state
- [ ] Topology expansion is governed
- [ ] Weaponization (BAD) is impossible - cannot override scale bounds

---

## See Also

- [Startup Experience Doctrine](./startup-experience.md) - Startup scaling
- [Workspace Composition System](./workspace-composition.md) - Widget placement
- [Progressive Disclosure Doctrine](../progressive-disclosure-doctrine.md) - Layer hierarchy
- [Governed Motion Doctrine](./governed-motion.md) - Motion constraints
- [Calm Dashboard Governance](./calm-dashboard-governance.md) - Overload handling
- [Visualization Composition](./visualization-composition.md) - Component system
