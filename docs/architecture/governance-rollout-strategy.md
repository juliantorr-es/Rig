# Rig Governance Rollout & Activation Strategy

## 1. Strategy Summary

Rig is transitioning from **Architecture Invention** to **Operational Activation**. This document defines the canonical rollout sequence to activate governed workflows and enforce operational trust across the repository.

The `preproduction` branch is the primary governance proving ground.

---

## 2. Activation Roadmap

### Phase 0: Workflow Registration (CRITICAL)
**Goal**: Get validation checks running and selectable in GitHub settings.

1. **Merge Workflow Files**: Ensure `preproduction-validation.yml` and `replay-integrity.yml` are present in `.github/workflows/` on the `preproduction` branch.
2. **Execute First Runs**: Push to `preproduction` or open a dummy PR to trigger the workflows.
3. **Verify Artifacts**: Ensure validation summaries and logs are correctly uploaded as GitHub artifacts.

### Phase 1: Enforcement Lockdown
**Goal**: Make validation mandatory for promotion to `main`.

1. **Required Checks (preproduction)**: Once workflows have run, add them as "Required" in Branch Protection rules for `preproduction`.
2. **Enforce CODEOWNERS**: Verify that `preproduction` and `main` require approval from the designated owners for sensitive paths (e.g., `src/rig/domain/governance/`).
3. **Labels & Routing**: Verify that labels (e.g., `governance-sensitive`) trigger the appropriate review workflows.

### Phase 2: Promotion & Stability
**Goal**: Lock down the stable `main` branch.

1. **Merge to Main**: Once the pipeline is validated in `preproduction`, promote the stable workflow files to `main`.
2. **Required Checks (main)**: Add the same mandatory validation checks to the `main` branch protection rules.
3. **Governance Test PR**: Execute a "Synthetic Governance Test PR" (see Section 3) to verify the end-to-end enforcement loop.

### Phase 3: Ruleset Refinement (Optional)
**Goal**: Transition to GitHub Rulesets for more granular or multi-repo policy.

---

## 3. Synthetic Governance Test PR

To verify operational maturity, a test PR must be opened from `agent/test-governance` with the following targets:

| Action | Expected Governance Result |
|--------|----------------------------|
| **Touch Replay Logic** | Triggers `replay-sensitive` label + Replay CI check. |
| **Touch Frontend Contract** | Triggers `frontend-contract` label + Frontend CI check. |
| **Modify Governance Engine** | Requires explicit approval from Governance CODEOWNERS. |
| **Submit Without Receipt** | Blocked by Integrity Engine (if implemented). |
| **Bypass Checks** | Blocked by Branch Protection rules. |

## 4. Operational Maturity Matrix

| Capability | Old Phase (Research) | New Phase (Activation) |
|------------|-----------------------|-------------------------|
| **CI Validation** | Ad-hoc / Local scripts | Mandatory / Required GitHub Checks |
| **Branch Policy** | Documentation only | Enforced Branch Protections |
| **Review Routing** | Manual tagging | CODEOWNER-driven automation |
| **Artifacts** | Ephemeral logs | Persistent, auditable validation evidence |
| **Trust Boundary** | Conceptual | Enforced at the PR/Merge boundary |

## 5. Governance Decision Records

- **Decision**: Defer GitHub Rulesets.
- **Rationale**: Branch protection rules are sufficient for the current single-repo scope; premature escalation adds unnecessary complexity.
- **Decision**: `preproduction` as Proving Ground.
- **Rationale**: Allows testing of the governance pipeline without risking the stability of the `main` branch.
