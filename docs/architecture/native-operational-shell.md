# Native Operational Shell

Rig's native macOS surface should be a calm operational shell, not an Electron-first application and not a browser-only experience.

## Shell Responsibilities

| Responsibility | Meaning |
|---|---|
| Menu bar observability | Lightweight runtime awareness |
| Runtime monitoring | Live status, load, and health visibility |
| Topology notifications | Important operational changes surfaced natively |
| Governance alerts | Policy-relevant state changes |
| Reduced-motion integration | Calm behavior under load |
| Projection rendering | Truthful display of backend-authored state |

## Design Doctrine

- Native shell behavior must respect system conventions.
- Observability should be progressive and low-noise.
- The shell is for supervision, not for inventing state.
- Frontend rendering must remain projection-driven.

## Explicit Rejections

- Electron-first operational shell.
- Browser-only operational UX.
- Hidden client-side authority over operational truth.

