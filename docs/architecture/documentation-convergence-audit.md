# Documentation Information Architecture Audit

## Summary
This audit evaluates the current state of Rig's documentation, identifying areas of overlap, semantic drift, navigation gaps, and confusion between implemented vs. future systems.

---

## 1. Audit Findings

### 1.1 Doctrine Duplication
| Concept | Redundant Locations | Issue |
|---------|---------------------|-------|
| Replay Determinism | `governance-replay.md`, `replay-determinism.md`, `convergence-audit.md` | Core guarantees are spread across multiple docs with varying levels of technical detail. |
| Visual Doctrine | `UI_DOCTRINE.md`, `visual-execution-doctrine.md`, `visual-semantic-normalization.md` | The philosophy of "truthful visualization" is stated in multiple places. |
| Workspace Status | `workspace-integrity-rules.md`, `governance-replay.md`, `workspace-status-summary.md` | The list of valid statuses and transitions is repeated. |

### 1.2 Semantic Drift
| Term | Current Variations | Proposed Canonical Term |
|------|--------------------|-------------------------|
| Trust Level | Trust Level (0-3), Authority Level | **Trust Level** (for data propagation), **Authority** (for decision rights) |
| Replay | Replay, Deterministic Reconstruction, Trace Reconstruction | **Replay** |
| Projection | UI Projection, Projection Output, Derived View | **Projection** |
| Lane | AgentLane, Task Lane, Lane branch | **AgentLane** |

### 1.3 Navigation Fragmentation
- `docs/architecture/README.md` provides a good map but lacks explicit **Reading Paths** for different personas (e.g., Frontend vs. Runtime contributor).
- Many docs lack a "Related Documents" section, making discovery difficult once deep in the hierarchy.
- The distinction between "Domain" docs and "Architecture" docs is sometimes blurry.

### 1.4 Layer Ambiguity
- The boundary between **Runtime Doctrine** (how things execute) and **Governance Doctrine** (how things are allowed) is occasionally blurred in `governance-engine.md`.
- **Visualization Doctrine** is well-defined but its connection to **Replay Doctrine** (how visualization is reconstructed) could be more explicit.

### 1.5 Future vs. Current Confusion
- `proposal-lifecycle.md` is marked "Future Implementation".
- `public-ops.md` is marked "Status: FUTURE".
- `workspace-control-plane.md` mentions "The full workspace runtime is future work" in the text, but the doc itself isn't explicitly tagged as a future spec.
- Speculative capabilities (e.g., sandbox hardening) are mixed with implemented reality (Git worktrees).

---

## 2. Identified Risks

1. **Contributor Overload**: New contributors face a "wall of doctrine" without a clear starting point.
2. **Implementation Drift**: If documentation for future systems looks identical to documentation for active systems, developers may attempt to use non-existent APIs.
3. **Redundancy Maintenance**: Updating core concepts (like workspace statuses) requires touching 4+ files.

---

## 3. Recommended Convergence Actions

1. **Establish Canonical Reading Paths**: Update `docs/architecture/README.md` with persona-based paths.
2. **Create Terminology Glossary**: Consolidate drifted terms in `docs/architecture/terminology.md`.
3. **Map Doctrine Boundaries**: Define responsibilities for each doctrine layer in `docs/architecture/doctrine-map.md`.
4. **Explicitly Tag Future Specs**: Use a consistent banner or status field for planned vs. implemented systems.
5. **Consolidate Duplicate Logic**: Move "Source of Truth" tables (like workspace statuses) to a single canonical doc (`docs/architecture/terminology.md` or a specific domain doc).
