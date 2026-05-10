import { ExplainerNode } from '../core/render-graph.js';

/**
 * Educational Narration Layer
 * Defines specific explainer scenarios for the May 27 demo.
 */
export const ExplainerScenarios = {
  EXECUTION_PROPAGATION: {
    id: 'explainer-execution',
    content: 'Execution propagation: This node emitted a validated state transition. Downstream consumers are reconciling projections.',
    position: 'top'
  },
  GOVERNANCE_GATE: {
    id: 'explainer-governance',
    content: 'Governance gate: The runtime rejected this mutation because the proposal lacked deterministic validation receipts.',
    position: 'top'
  },
  TRUTHFUL_REPLAY: {
    id: 'explainer-replay',
    content: 'Truthful replay: The UI is not replaying video frames. The topology is being deterministically re-projected from historical state.',
    position: 'top'
  }
};

/**
 * Trigger an explainer overlay for a specific anchor.
 */
export function triggerExplainer(scenarioKey, anchorId, duration = 5000) {
  const scenario = ExplainerScenarios[scenarioKey];
  if (!scenario) return null;

  return new ExplainerNode(scenario.id, anchorId, scenario.content, scenario.position);
}
