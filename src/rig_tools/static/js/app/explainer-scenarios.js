import { ExplainerNode } from '../core/render-graph.js';

/**
 * Educational Narration Layer
 * Defines specific explainer scenarios for the May 27 demo.
 */
export const ExplainerScenarios = {
  EXECUTION_PROPAGATION: {
    id: 'explainer-execution',
    title: 'Causal Propagation',
    content: 'A validated state transition has been emitted. Downstream observers are now reconciling their projections to maintain system-wide object constancy.',
    position: 'top'
  },
  GOVERNANCE_GATE: {
    id: 'explainer-governance',
    title: 'Governance Exception',
    content: 'The runtime has blocked this mutation. Causal evidence check failed: the proposal lacked the deterministic validation receipts required by the active policy.',
    position: 'top'
  },
  TRUTHFUL_REPLAY: {
    id: 'explainer-replay',
    title: 'Deterministic Re-Projection',
    content: 'This is not a video recording. The system is re-executing historical events through the projection engine to ensure total state traceability.',
    position: 'top'
  }
};

/**
 * Trigger an explainer overlay for a specific anchor.
 */
export function triggerExplainer(scenarioKey, anchorId, duration = 5000) {
  const scenario = ExplainerScenarios[scenarioKey];
  if (!scenario) return null;

  return new ExplainerNode(scenario.id, anchorId, scenario.title, scenario.content, scenario.position);
}

