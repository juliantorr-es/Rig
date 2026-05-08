# Guided Onboarding System

> **Rig Onboarding Philosophy: Operational, Contextual, Progressive**

## Core Principle

Rig onboarding teaches the **runtime itself**, not the tool. Users learn through **guided interaction with real runtime behavior**, not through tutorials about the interface. Onboarding is **contextual, not sequential** - it appears when relevant to the user's current operational state.

**Onboarding MUST NOT be:**
- A giant tutorial dump
- Overwhelming walkthrough
- Modal spam
- Feature avalanche
- flashy AI spectacle
- Gamification

**Onboarding MUST be:**
- Operational literacy
- Guided discovery
- Contextual hints
- Progressive depth
- Experiential learning
- Calm and focused

---

## Onboarding Philosophy

### The Runtime Teaches Itself
Rig's onboarding is **runtime-native**: the runtime itself is the teacher. Users learn by:
1. Observing real runtime behavior
2. Interacting with actual runtime state
3. Seeing explanations of what just happened
4. Receiving contextually relevant hints

### Learning Through Interaction
- **NOT**: "Click here to learn about X"
- **BUT**: "You just saw a proposal event. Here's what that means for runtime semantics."

### Progressive Feature Reveal
Features are revealed **when the user needs them**, not when the system wants to show them:
- Workspace basics appear on first startup
- Topology understanding appears when user first sees topology
- Replay systems appear when user first has data to replay
- DTGs appear when user first encounters a decision chain

### Cognitive Load Governance
Onboarding respects **cognitive load limits**:
- Maximum 1 onboarding message at a time
- Messages auto-dismiss after user interaction or timeout
- User can always dismiss any onboarding element
- Onboarding never blocks user interaction
- Reduced motion mode applies to all onboarding

---

## Onboarding Stages

### STAGE 1: Workspace Basics & Runtime Overview
**When**: First startup, before any interaction
**Context**: User sees empty or restored workspace
**Goal**: Understand what Rig is and how to navigate it

#### Stage 1 Lessons
| Lesson | Trigger | Content | Duration |
|--------|---------|---------|----------|
| Welcome | First startup only | "Rig is a governed runtime workspace. The.runtime teaches itself." | Persistent until dismissed |
| Layout Overview | Workspace first render | "This is your runtime workspace. Widgets show different aspects of runtime behavior." | 10s timeout, click dismiss |
| Widget Introduction | Widget render | "Widgets display real runtime state. You can move and resize them." | On first widget interaction |
| Runtime State | Status card render | "Runtime state shows the current operational mode. Green = streaming." | On first state change |

#### Stage 1 Visuals
- Single non-blocking overlay in bottom-right corner
- Static text with optional "Got it" button
- No animation, no auto-advance
- Plain background, high contrast text

---

### STAGE 2: Topology Understanding & Routing
**When**: User first sees topology visualization or stream activity
**Context**: Runtime is active, streams are flowing
**Goal**: Understand topology structure and routing semantics

#### Stage 2 Lessons
| Lesson | Trigger | Content | Duration |
|--------|---------|---------|----------|
| Lane Concept | First lane visible | "Lanes represent execution contexts. Each lane has a purpose." | 10s timeout |
| Node Introduction | First node appears | "Nodes represent runtime components. Their position is deterministic." | On node appearance |
| Connector Meaning | First connector visible | "Connectors show relationships between components. They're always straight lines." | On connector appearance |
| Routing Basics | First multi-node topology | "Routing shows how data flows. Follow the paths to see the flow." | On topology change |
| Provider Scope | First provider indicator | "Providers execute capabilities. Their trust tier determines routing." | On provider change |

#### Stage 2 Visuals
- Contextual hints appear near relevant topology elements
- Hints have leader lines pointing to the element they describe
- Hints auto-position to avoid overlap
- Maximum 1 hint visible at a time

---

### STAGE 3: DTGs & Integrity & Supervision
**When**: User first encounters decision chains or integrity events
**Context**: Complex runtime behavior with supervision
**Goal**: Understand decision topology, integrity validation, and supervision

#### Stage 3 Lessons
| Lesson | Trigger | Content | Duration |
|--------|---------|---------|----------|
| DTG Introduction | First DTG node beyond root | "DTGs show decision lineage. Explore to understand runtime choices." | 15s timeout |
| Integrity Concept | First integrity marker | "Integrity markers show validation results.Green = passed." | On marker appearance |
| Supervision Meaning | First supervision overlay | "Supervision overlays show governance. Yellow = active supervision." | On overlay appearance |
| Capability Routing | First capability-based route | "Capabilities determine what can execute. Routes respect capability rules." | On route change |

#### Stage 3 Visuals
- Contextual hints appear within DTG viewer or topology panel
- Hints highlight the specific element being explained
- User can click to expand explanation
- Expanded explanation shows in onboarding panel

---

### STAGE 4: Forensic Replay & Deep Operational Workflows
**When**: User first uses replay or debugging features
**Context**: User has history to replay and investigate
**Goal**: Understand forensic replay, debugging, and deep operational analysis

#### Stage 4 Lessons
| Lesson | Trigger | Content | Duration |
|--------|---------|---------|----------|
| Replay Introduction | First replay controls visible | "Replay lets you re-examine runtime behavior. Scrub to explore." | On replay panel open |
| Replay Fidelity | First replay start | "Replay is deterministic. You'll see exactly what happened." | On first replay |
| Forensic Markers | First replay with integrity events | "Markers show significant events. Click to see details." | On replay with markers |
| Debug Mode | First debug panel open | "Debug mode shows internal state. Use for investigation." | On debug open |
| Deep Analysis | First complex topology replay | "Complex topologies can be examined step-by-step. Use replay to understand." | On complex replay |

#### Stage 4 Visuals
- Replay controls have built-in hints on first use
- Forensic markers have tooltips explaining their meaning
- Debug panel has contextual help
- Complex topology has guided walkthrough option

---

## Onboarding Triggers

### Contextual Trigger System
Onboarding lessons are triggered by **runtime events**, not by interface events:

| Trigger Type | Example | Lesson Scope |
|--------------|---------|--------------|
| Runtime State | Runtime enters streaming | Stage 1: Runtime Overview |
| Topology Change | Node added/removed | Stage 2: Topology |
| Integrity Event | Violation detected | Stage 3: Integrity |
| Replay Action | Replay started | Stage 4: Replay |
| Complexity Threshold | Topology exceeds 10 nodes | Stage 3: DTG |
| User Action | Widget moved/resized | Stage 1: Workspace |

### Trigger Priority
When multiple triggers fire simultaneously:
1. **Highest stage first** (Stage 4 > Stage 3 > Stage 2 > Stage 1)
2. **Most specific first** (specific event > general state)
3. **First occurrence wins** (only show each lesson once)

### Trigger Debouncing
- Multiple rapid triggers for same lesson: only first fires
- Same lesson won't repeat within 5 minutes
- User dismissal prevents re-trigger for 1 hour
- Workspace changes reset trigger state

---

## Progressive Feature Reveal

### Feature Availability by Stage
| Feature | Available From | Reveal Mechanism |
|---------|----------------|------------------|
| Widget move/resize | Stage 1 | Always available, hint on first interaction |
| Topology visualization | Stage 1 | Always visible (if data exists) |
| Replay controls | Stage 2 | Visible but disabled until data exists |
| DTG viewer | Stage 3 | Hidden until first DTG data, then hinted |
| Integrity panel | Stage 3 | Hidden until first integrity event, then hinted |
| Debug panel | Stage 4 | Hidden until explicitly enabled |
| Plugin inspector | Stage 4 | Hidden until needed |
| Advanced replay | Stage 4 | Visible but requires explicit opt-in |

### Feature Badges
New features get a **subtle badge** indicating they're new:
- Badge appears for 1 session after feature becomes available
- Badge is static, not animated
- Hover shows brief description
- Clicking badge shows onboarding lesson

---

## Onboarding Persistence

### State Persistence
```json
{
  "onboarding": {
    "version": "1.0",
    "completedLessons": ["workspace.welcome", "workspace.layout"],
    "dismissedLessons": ["topology.lanes"],
    "StageProgress": {
      "1": {"isComplete": false, "lessonsRemaining": 3},
      "2": {"isComplete": false, "lessonsRemaining": 5},
      "3": {"isComplete": false, "lessonsRemaining": 4},
      "4": {"isComplete": false, "lessonsRemaining": 5}
    },
    "preferences": {
      "reducedMotion": false,
      "autoAdvance": false,
      "hintPosition": "bottom-right"
    }
  }
}
```

### Progress Tracking
- Each lesson tracked as completed or pending
- Stage completion: all lessons in stage either completed or dismissed
- User can reset onboarding state
- Reset doesn't re-show already-seen lessons immediately

### Dismissal Memory
- Dismissed lessons remembered permanently
- User can re-enable lessons in settings
- Lessons can per-locked (never show again) by user

---

## Tutorial Replayability

### All Lessons Replayable
- All onboarding lessons can be re-viewed
- Accessible through help menu or onboarding panel
- Organized by stage and topic
- Searchable by keyword

### Tutorial Formats
| Format | When Used | Characteristics |
|--------|-----------|----------------|
| Inline Hint | Contextual, first occurrence | Brief, auto-dismiss, non-blocking |
| Onboarding Panel | User-requested | Full lesson, interactive, persistent |
| Guided Walkthrough | Complex features | Step-by-step, user-paced, cancellable |
| Reference Card | Help menu | Static documentation, always available |

### Guided Walkthrough
Step-by-step guided tours for complex features:

```
1. User clicks "Learn about DTGs"
2. Onboarding panel opens with DTG explanation
3. Panel highlights DTG viewer widget
4. User clicks "Next"
5. Panel highlights first DTG node
6. Panel explains node meaning
7. User clicks "Next" or interacts with DTG
8. Continue through steps or cancel
```

### Walkthrough Guarantees
- User can cancel at any time
- Progress is saved
- User can resume later
- Walkthrough never blocks interaction
- Reduced motion mode applies
- Walkthrough is replay-safe (same steps every time)

---

## Reduced Stimulation Onboarding

### Low-Stimulation Mode
Activated when:
- `prefers-reduced-motion: reduce`
- Workspace density > 0.6
- User explicitly enables in settings
- Runtime overload detected

### Low-Stimulation Onboarding
- No animations on onboarding elements
- No auto-advance on lessons
- No pulsing or highlighting
- Static positioning only
- Instant appearance/dismissal
- Plain styling (no shadows, no rounded corners beyond baseline)

### Stimulation Scale
| Level | Motion | Positioning | Styling |
|-------|--------|-------------|---------|
| Normal | Subtle animations | Smooth positioning | Full styling |
| Reduced | No animations | Instant positioning | Plain styling |
| Minimal | No motion | Static positioning | Minimal styling |

---

## Operational Storytelling

### Runtime Event Explanation
When significant runtime events occur, onboarding can provide **operational explanations**:

| Event | Explanation | When |
|-------|-------------|------|
| Proposal created | "Rig created a proposal. This represents a suggested change to the workspace." | On first proposal |
| Proposal validated | "The proposal passed validation.It can now be applied." | On first validation |
| Intent executed | "Your intent was executed. Here's what changed." | On first intent |
| Integrity violation | "An integrity rule was violated. This means the runtime detected a problem." | On first violation |
| Replay started | "You're now replaying runtime behavior. Everything you see is deterministic." | On first replay |

### Explanation Format
```
Event: [Event Name]
What happened: [Brief description]
Why it matters: [Operational significance]
What to do: [User action, if applicable]
Learn more: [Link to documentation]
```

### Explanation Delivery
- Appears in onboarding panel when event occurs
- Auto一个人 dismissed after 20 seconds or user interaction
- User can pin explanation for reference
- Pinned explanations appear in help menu

---

## Runtime Semantics Teaching

### What Rig Teaches Progressively
| Concept | Stage | Teaching Method |
|---------|-------|-----------------|
| Runtime state | 1 | Runtime Overview widget + hints |
| Lane purpose | 1 | Workspace layout + hints |
| Widget system | 1 | Interactive exploration + hints |
| Topology structure | 2 | Topology visualization + contextual hints |
| Routing semantics | 2 | Flow visualization + explanations |
| Provider trust | 2 | Provider indicators + tooltips |
| DTG lineage | 3 | DTG viewer + guided walkthrough |
| Integrity system | 3 | Integrity panel + event explanations |
| Capability routing | 3 | Capability indicators + explanations |
| Replay determinism | 4 | Replay controls + fidelity explanations |
| Forensic analysis | 4 | Replay markers + debugging hints |

### Teaching Through Replay
The most powerful teaching happens during **replay**:
- User can re-examine past behavior
- Onboarding highlights significant events
- User can scrub to see cause and effect
- Explanations appear at the moment they're relevant

---

## Compliance Checklist

- [ ] Onboarding teaches runtime, not interface
- [ ] All lessons are contextual, not sequential
- [ ] Maximum 1 onboarding message at a time
- [ ] Onboarding never blocks user interaction
- [ ] Reduced motion mode applies to all onboarding
- [ ] All lessons are dismissible
- [ ] All lessons are replayable
- [ ] Onboarding respects cognitive load limits
- [ ] Feature reveal is progressive and contextual
- [ ] Tutorial walkthroughs are user-paced and cancellable
- [ ] Runtime event explanations are operational, not decorative
- [ ] All onboarding state is persisted
- [ ] Onboarding is replay-safe

---

## See Also

- [Startup Experience Doctrine](./startup-experience.md) - First experience
- [Workspace Composition System](./workspace-composition.md) - Layout system
- [Widget Disclosure Scaling](./widget-disclosure-scaling.md) - Progressive detail
- [Experiential Runtime Learning](./experiential-runtime-learning.md) - Learning philosophy
- [Progressive Disclosure Doctrine](../progressive-disclosure-doctrine.md) - Information hierarchy
- [Governed Motion Doctrine](./governed-motion.md) - Motion constraints
