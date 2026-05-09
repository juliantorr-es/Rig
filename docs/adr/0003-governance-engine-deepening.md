# Governance Engine Deepening

The **Governance Engine** concept is split shallowly: `governance/engine.py` has decision logic mixed with intent evaluation, while `intents/dispatcher.py` has its own preflight and capability checks. Delete `engine.py` and the intent legality logic scatters. We should deepen `GovernanceEngine` to own ALL "is this allowed?" decisions, with `IntentDispatcher` becoming a thin adapter.

**Status**: proposed

## Context

- `src/rig/domain/governance/engine.py` — `GovernanceEngine.evaluate_action_legality()` with 112 lines of conditional logic
- `src/rig/domain/governance/decisions.py` — `GateDecision`, `DecisionReason` types
- `src/rig/domain/intents/dispatcher.py` — `IntentDispatcher` with `_preflight()` doing capability checks
- `src/rig/domain/intent_defs.py` — `Intent` type and simple `IntentHandler`
- No single seam for governance decisions — callers import `GovernanceEngine` directly or go through dispatcher

## Decision

Depen `GovernanceEngine` to own all governance:
- Absorb preflight logic from `IntentDispatcher._preflight()`
- Absorb capability checks
- Own gate evaluation with workspace state, proposal status, evidence validation
- Expose single interface: `GovernanceEngine.evaluate(intent: Intent, context: EvaluationContext) -> GateDecision`
- `IntentDispatcher` becomes thin adapter: receives intent, calls `GovernanceEngine.evaluate()`, routes to handler if allowed

## Consequences

**Leverage**: One place for all "is X allowed?" logic. New gates added in one place. Consistent decision structure across all intents.

**Locality**: All governance knowledge concentrated. Policy changes in one module. Audit trail of decisions in one place.

**Testability**: Test governance through `evaluate()` interface. Feed it various intent/context combinations, assert on `GateDecision`. No need to test dispatcher's preflight separately.

**Seam**: `GateDecision` becomes the real seam. Two adapters exist: production `GovernanceEngine` and test mock that returns predefined decisions.

## Files Involved

- `src/rig/domain/governance/engine.py` — deepened to include preflight and capability logic
- `src/rig/domain/governance/decisions.py` — types remain, possibly extended
- `src/rig/domain/governance/context.py` — new: `EvaluationContext` dataclass
- `src/rig/domain/intents/dispatcher.py` — simplified: remove `_preflight()`, delegate to `GovernanceEngine`
- `src/rig/domain/intent_defs.py` — unchanged (pure types)

## Migration Path

1. Create `EvaluationContext` with workspace_id, proposal, evidence, policy, actor
2. Move `_preflight()` logic from dispatcher to engine as `evaluate()` helper
3. Extend `GateDecision` to include capability check results
4. Update `IntentDispatcher` to call engine for all decisions
5. Remove duplicate preflight from dispatcher
6. Update all direct `GovernanceEngine` callers to use new interface
