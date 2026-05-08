# Experiential Runtime Learning

> **How Users Learn Rig Operationally - Through Interaction, Discovery, and Reflection**

## Core Principle

Rig's learning philosophy is **experiential**: users learn by **doing, observing, and reflecting** on real runtime behavior. There are no abstract tutorials - all learning happens in the context of actual runtime operations, with the runtime itself serving as the teacher.

**Learning by:**
1. **Doing** - Executing intents and observing results
2. **Seeing** - Watching runtime behavior through visualization
3. **Understanding** - Receiving contextual explanations
4. **Reflecting** - Replaying and analyzing past behavior
5. **Applying** - Using learned concepts in new situations

---

## Learning Through Interaction

### The Interaction-Explanation Loop
```
User Action -> Runtime Behavior -> Visualization Update -> Contextual Explanation -> User Understanding
```

Every user interaction with Rig triggers this loop:
1. User performs action (intent, command, configuration)
2. Runtime processes action and produces behavioral change
3. Visualization updates to reflect new state
4. If the behavior teaches a new concept, show contextual explanation
5. User gains understanding of runtime semantics

### Interaction Granularity
| Interaction Level | Learning Scope | Example |
|------------------|---------------|---------|
| Micro | Immediate feedback | Hover over element shows tooltip |
| Short | Single concept | Submit intent, see proposal created |
| Medium | Workflow understanding | Create proposal, validate, apply |
| Long | System understanding | Runtime streaming session with replay |

---

## Guided Discovery

### Discovery Through Exploration
Users discover Rig's capabilities by **exploring the runtime**, not by reading documentation:

| Discovery Method | When | What User Learns |
|----------------|------|-----------------|
| Hover tooltips | Always | Element purpose and current state |
| Click exploration | User clicks on element | Element's detail and related concepts |
| Contextual hints | Runtime event occurs | What just happened and why |
| Guided walkthrough | User opens tutorial | Step-by-step feature exploration |
| Replay investigation | User replays session | How runtime behavior unfolded |

### Discovery Principles
1. **Just-in-Time**: Information appears when needed, not before
2. **Contextual**: Explanations are specific to current runtime state
3. **Progressive**: Each discovery builds on previous understanding
4. **Non-Blocking**: Discovery never interrupts user workflow
5. **User-Controlled**: User can dismiss, pause, or skip any discovery

---

## Operational Storytelling

### The Runtime as Narrator
Rig tells **operational stories** - narratives about what the runtime is doing and why:

| Story Type | Trigger | Narrative | Outcome |
|-----------|---------|-----------|--------|
| Proposal Creation | Proposal created event | "A proposal was created for your intent. Proposals represent suggested changes that must pass validation before execution." | User understands proposal system |
| Validation Success | Proposal validated | "The proposal passed all validation checks. Integrity rules confirmed no violations. It's now ready to apply." | User understands validation |
| Stream Flow | Data flowing through topology | "Stream chunks are flowing through the topology. Each chunk carries content from provider to capability." | User understands streaming |
| Integrity Violation | Violation detected | "An integrity violation was detected. The runtime prevented an action that would violate governed rules." | User understands integrity |
| Replay Session | Replay started | "You're now viewing a playback of runtime behavior. Everything you see is deterministic - the same as when it originally occurred." | User understands replay |

### Story Structure
All operational stories follow this structure:
```
[Event]: What happened
[Context]: Where this fits in the runtime
[Meaning]: What this means operationally
[Significance]: Why this matters for the user's understanding
[Next]: What the user might want to do or observe next
```

### Story Delivery
| Delivery Mode | When | Characteristics |
|---------------|------|----------------|
| Inline | Runtime event occurs | Brief, temporary, non-blocking |
| Panel | User requests detail | Full story, persistent, interactive |
| Walkthrough | Complex event chain | Guided, step-by-step, user-paced |
| Replay | Historical investigation | Annotated, scrubble, detailed |

---

## Replay-Driven Understanding

### Replay as Teaching Tool
Replay is Rig's most powerful teaching mechanism. Users learn by:
1. **Re-examining** past behavior at their own pace
2. **Scrubbing** through events to see causal relationships
3. **Comparing** different moments in runtime history
4. **Understanding** why the runtime made specific decisions

### Replay Annotations
During replay, Rig can **annotate** the visualization with explanations:

| Annotation Type | Appearance | Content |
|---------------|------------|---------|
| Event Marker | Vertical line at sequence position | Event name and timestamp |
| State Change | Background color shift | New state and transition reason |
| Topology Change | Highlight on changed element | What changed and why |
| Integrity Event | Badge on relevant element | Violation/correctness details |
| Capability Change | Pulse on capability indicator | New capability and its meaning |

### Annotated Replay Workflow
```
1. User starts replay
2. Rig identifies significant events (first of each type, state changes, etc.)
3. As user scrubs, annotations appear at relevant moments
4. User can click annotation to see full explanation
5. User can enable "teaching mode" to see all annotations
6. User can scrub freely with annotations following
```

### Replay Learning Scenarios
| Scenario | What User Learns | How |
|----------|-----------------|-----|
| First replay of proposal lifecycle | Proposal creation -> validation -> apply flow | Annotated scrub through lifecycle |
| Replay with integrity violation | How integrity system prevents problems | Highlight violation moment with explanation |
| Replay of multi-stream topology | How data flows through complex routing | Flow animation with node-by-node explanation |
| Replay of supervision event | How supervision governs runtime | Supervision overlay with governance explanation |
| Replay of error and recovery | How Rig handles and recovers from errors | Error marker with recovery path |

---

## Topology Literacy

### Learning Topology Concepts
Users develop **topology literacy** - understanding how runtime components connect and interact:

| Concept | How Taught | Visualization |
|---------|-----------|---------------|
| Lane | Workspace layout shows lanes | Horizontal bands, labeled |
| Node | Nodes appear in topology | Points/rectangles at deterministic positions |
| Connector | Lines between nodes | Straight SVG lines |
| Routing Path | Flow through nodes | Animated or static path highlighting |
| Provider | Label on node | Color-coded by trust tier |
| Capability | Badge on provider | Icon indicating capability set |
| Supervision | Overlay on topology | Semi-transparent layer |
| Integrity | Markers on elements | Small badges indicating status |

### Topology Understanding Progression
1. **Static Understanding**: User can identify elements (lane, node, connector)
2. **Dynamic Understanding**: User can trace data flow through topology
3. **Causal Understanding**: User can explain why topology changed
4. **Predictive Understanding**: User can predict topology behavior
5. **Optimization Understanding**: User can suggest topology improvements

---

## Instrumentation Literacy

### Learning What Instruments Mean
Users develop **instrumentation literacy** - understanding what each visualization element represents:

| Instrument | What it Shows | How Taught |
|------------|--------------|-----------|
| Lane Band | Lane identity and purpose | Label + color coding |
| Node Symbol | Component type and status | Shape + color |
| Connector Line | Relationship type | Line style (solid/dashed/dotted) |
| Flow Indicator | Data movement | Arrow direction |
| Throughput Bar | Activity volume | Bar height/length |
| State Icon | Current operational state | Icon + color |
| Integrity Marker | Validation status | Badge + color |
| Capability Badge | Execution capabilities | Icon set |
| Replay Sweep | Replay position | Line across visualization |
| DTG Node | Decision point | Shape + label |
| DTG Edge | Decision lineage | Line with direction |

### Instrumentation Understanding Progression
1. **Recognition**: User can identify instrument type
2. **Reading**: User can read current value from instrument
3. **Interpretation**: User can explain what the value means
4. **Comparison**: User can compare values across instruments
5. **Prediction**: User can predict future values
6. **Configuration**: User can configure instruments for their needs

---

## Runtime Semantics Education

### What Users Must Learn
| Semantic | Definition | Teaching Method |
|----------|------------|-----------------|
| Runtime State | Current operational mode | Status card + state indicators |
| Streaming | Active data flow | Throughput bars + flow animation |
| Proposing | Suggestion generation | Proposal indicators + intent console |
| Validating | Integrity checking | Integrity markers + validation state |
| Executing | Action performance | Activity indicators + state changes |
| Stalled | Blocked state | Stalled indicators + diagnostic info |
| Complete | Finished state | Completion markers + summary |
| Error | Problem state | Error indicators + diagnostic info |

### Semantic Learning Path
```
Unknown -> Aware -> Understanding -> Proficient -> Expert

Unknown: User doesn't know the semantic exists
Aware: User has seen the semantic in action
Understanding: User can explain what the semantic means
Proficient: User can predict semantic transitions
Expert: User can design workflows using semantics
```

### Semantic Teaching Examples
| Semantic | Teaching Moment | Explanation |
|----------|----------------|-------------|
| Streaming | First data flows | "Streaming means the runtime is actively processing data. Chunks flow from providers through the topology." |
| Proposing | First proposal created | "Proposing means Rig is generating a suggestion based on your intent. Proposals must pass validation before execution." |
| Validating | First validation runs | "Validating means Rig is checking the proposal against integrity rules. Violations block execution." |
| Executing | First execution | "Executing means Rig is applying the validated proposal. The workspace changes to match the intent." |
| Stalled | First stall | "Stalled means data flow is blocked. Check for integrity violations or missing capabilities." |
| Error | First error | "Error means something went wrong. Rig has paused to prevent further problems. Check diagnostics for details." |

---

## Governance Semantics Literacy

### Understanding Runtime Governance
Users learn **governance semantics** - how Rig ensures safety and correctness:

| Governance Concept | What it Does | Teaching Method |
|-------------------|--------------|-----------------|
| Integrity Rules | Prevent invalid state | Integrity panel + violation explanations |
| Capability System | Control what can execute | Capability badges + routing explanations |
| Trust Tiers | Determine provider authority | Provider indicators + trust explanations |
| Validation Gates | Ensure proposal quality | Proposal console + gate state |
| Supervision | Monitor runtime behavior | Supervision overlay + governance explanations |
| Density Collapse | Prevent overload | Workspace density + simplification hints |
| Motion Governance | Reduce stimulation | Motion settings + low-stimulation mode |

### Governance Understanding Progression
1. **Awareness**: User knows governance exists
2. **Observation**: User can see governance in action
3. **Understanding**: User can explain why governance took action
4. **Appreciation**: User understands the value of governance
5. **Mastery**: User can configure governance for their needs

---

## Contextual Hints

### Hint System
Contextual hints appear when:
1. User hovers over an element for >1 second
2. Runtime event occurs that introduces a new concept
3. User seems confused (repeated failed interactions)
4. User requests help (clicks ? icon or presses F1)

### Hint Content Structure
```
Element: [Name]
Type: [Type]
Purpose: [What it does]
Current State: [Current value/state]
Meaning: [What this state means]
Learn More: [Link to documentation]
Actions: [What user can do with this element]
```

### Hint Types
| Hint Type | When | Duration | Interaction |
|-----------|------|----------|-------------|
| Tooltip | Hover | Persistent while hover | None |
| Event Hint | Runtime event | 10s timeout | Click to expand |
| Confusion Hint | Detected confusion | Persistent until dismissed | Click to understand |
| Requested Hint | User requests | Persistent until dismissed | Interactive |

---

## Operational Annotations

### Annotation Types
| Annotation | Trigger | Content | Visual |
|------------|---------|---------|--------|
| State Label | State change | New state name | Text label |
| Flow Arrow | Data flow | Direction and type | Arrow overlay |
| Integrity Badge | Integrity event | Pass/fail/warn | Color badge |
| Capability Icon | Capability relevant | Capability name | Icon |
| Provider Tag | Provider active | Provider name + tier | Tag |
| Supervision Layer | Supervision active | Supervision type | Overlay |
| Density Indicator | Density change | Density level | Meter |
| Replay Marker | Replay event | Event type | Marker |

### Annotation Rules
1. **Non-Intrusive**: Annotations never cover primary content
2. **Temporary**: Most annotations auto-dismiss
3. **Contextual**: Annotations appear near what they annotate
4. **Consistent**: Same events always produce same annotations
5. **Bounded**: Maximum annotations visible simultaneously
6. **User-Controlled**: User can hide/show annotation types

---

## Routing Explanations

### Teaching Routing Semantics
Users learn **routing semantics** - how data flows through the topology:

| Routing Concept | Explanation | Visualization |
|----------------|-------------|---------------|
| Lane Routing | Data stays within lane | Horizontal flow within lane |
| Cross-Lane Routing | Data moves between lanes | Vertical connector lines |
| Provider Routing | Data goes to specific provider | Target highlighting |
| Capability Routing | Data goes to capable provider | Capability matching indicators |
| Trust Routing | Data respects trust tiers | Trust tier coloring on paths |
| Supervision Routing | Supervision monitors flow | Supervision overlay on paths |

### Routing Understanding Progression
1. **Basic**: User can trace data flow through topology
2. **Capability-Aware**: User understands capability-based routing
3. **Trust-Aware**: User understands trust-tier constraints
4. **Supervision-Aware**: User understands supervision impact
5. **Optimization-Aware**: User can suggest routing improvements

---

## Integrity Event Explanation

### Explaining Integrity
| Integrity Event | Explanation | User Learns |
|----------------|-------------|-------------|
| Violation Detected | "Rule X was violated. This means [explanation]." | Specific rule meaning |
| Violation Prevented | "Action was blocked because it would violate Rule X." | Preventive integrity |
| Validation Passed | "Proposal passed all integrity checks." | Validation system |
| Validation Failed | "Proposal failed Rule X. Fix and retry." | Validation requirements |
| Integrity Warning | "Potential issue with Rule X. Review recommended." | Warning severity |
| Integrity Chain | "These events are causally related through integrity." | Causal relationships |

### Integrity Teaching Progression
1. **Awareness**: User knows integrity system exists
2. **Observation**: User sees integrity events
3. **Understanding**: User understands what violations mean
4. **Diagnosis**: User can identify why violations occur
5. **Prevention**: User can avoid causing violations
6. **Configuration**: User can configure integrity rules

---

## Runtime Transition Explanation

### Explaining State Changes
| Transition | Explanation | Visualization |
|------------|-------------|---------------|
| Idle -> Streaming | "Runtime entering streaming mode. Data will begin flowing." | State icon change |
| Streaming -> Proposing | "Runtime detected intent. Generating proposal." | State + proposal indicator |
| Proposing -> Validating | "Proposal created. Validating against integrity rules." | Validation overlay |
| Validating -> Executing | "Proposal passed validation. Executing changes." | Execution animation |
| Executing -> Streaming | "Changes applied. Returning to streaming mode." | State icon change |
| Any -> Stalled | "Data flow stalled. Check integrity panel." | Stalled indicators |
| Any -> Error | "Error occurred. Check diagnostics." | Error indicators |

### Transition Understanding Progression
1. **Recognition**: User can identify state changes
2. **Understanding**: User can explain what each state means
3. **Causality**: User can explain why transitions occur
4. **Prediction**: User can predict future transitions
5. **Control**: User can trigger desired transitions

---

## Compliance Checklist

- [ ] Learning is experiential (doing, not reading)
- [ ] Runtime is the teacher (not abstract tutorials)
- [ ] All learning is contextual (tied to current runtime state)
- [ ] Learning respects cognitive load (one concept at a time)
- [ ] Replay is a primary teaching tool
- [ ] Topology literacy is progressively developed
- [ ] Instrumentation literacy is progressively developed
- [ ] Runtime semantics are taught through interaction
- [ ] Governance semantics are taught through observation
- [ ] Contextual hints are always relevant
- [ ] Operational annotations explain, don't decorate
- [ ] Routing explanations are visual and textual
- [ ] Integrity events are fully explained
- [ ] Runtime transitions are comprehensible
- [ ] All learning respects reduced motion preferences
- [ ] Users can always control their learning experience

---

## See Also

- [Guided Onboarding System](./guided-onboarding.md) - Onboarding stages and triggers
- [Startup Experience Doctrine](./startup-experience.md) - First experience
- [Workspace Composition System](./workspace-composition.md) - Layout and widgets
- [Widget Disclosure Scaling](./widget-disclosure-scaling.md) - Progressive detail
- [Progressive Disclosure Doctrine](../progressive-disclosure-doctrine.md) - Information hierarchy
- [Governed Motion Doctrine](./governed-motion.md) - Motion and stimulation
- [Calm Dashboard Governance](./calm-dashboard-governance.md) - Overload prevention
