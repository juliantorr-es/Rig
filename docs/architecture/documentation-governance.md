# Documentation Governance Doctrine

This document defines how Rig's documentation is managed, updated, and retired. It ensures that the documentation corpus remains a governed operational knowledge system rather than a collection of stale files.

---

## 1. Documentation Lifecycle

| State | Definition | Requirement |
|-------|------------|-------------|
| **Draft** | Initial proposal for a new doctrine or system. | Must be labeled `Status: DRAFT`. |
| **Active** | Canonical doctrine or implemented system documentation. | Must align with [terminology.md](terminology.md). |
| **Future** | Speculative design or planned capability. | Must be labeled `Status: FUTURE`. |
| **Stale** | Documentation that no longer reflects implementation or doctrine. | Must be marked for retirement or update. |
| **Retired** | Historical documentation kept for reference. | Moved to a `legacy/` or `retired/` folder if applicable. |

## 2. Adding New Doctrine

1. **Verify Necessity**: Ensure the new doctrine doesn't overlap significantly with existing layers in [doctrine-map.md](doctrine-map.md).
2. **Align Terminology**: Use canonical terms from [terminology.md](terminology.md). New terms must be added to the terminology doc.
3. **Cross-Link**: Add a "Related Documents" section and update the **Architecture Navigation Map** in `docs/architecture/README.md`.
4. **Define Authority**: Explicitly state where authority lives in the new doctrine.

## 3. Handling Terminology Changes

- Terminology changes must be treated as **breaking architectural changes**.
- Proposed changes must be updated in [terminology.md](terminology.md) first.
- All referencing documents must be updated in a single documentation convergence pass.

## 4. Resolving Doctrine Overlap

- If two documents cover the same concept inconsistently, the **Primary Authority** doc (as defined in [doctrine-map.md](doctrine-map.md)) takes precedence.
- Redundant logic should be extracted into a shared canonical doc (e.g., [terminology.md](terminology.md) for statuses).

## 5. Labeling Future Capabilities

- All documentation for non-implemented systems must carry a clear **FUTURE** banner at the top.
- Future specs should use the imperative mood for designs but explicitly state "not implemented" in the summary.
- Contributors must consult [current-vs-future.md](current-vs-future.md) before implementing based on documentation.

## 6. Documentation Review Gates

Documentation changes must pass the following checks:
1. **Navigability**: Does it fit into a reading path?
2. **Consistency**: Does it conflict with established doctrines?
3. **Clarity**: Is implemented vs. future state clear?
4. **Integrity**: Are cross-links valid?
