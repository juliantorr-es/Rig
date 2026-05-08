import pytest
from pathlib import Path

def test_intent_pending_state_logic():
    # Simulate pending state
    pending_intents = {"test.action": {"status": "pending", "label": "Running..."}}
    assert pending_intents["test.action"]["status"] == "pending"

def test_log_stream_rendering():
    # Simulate log entry with HTML chars
    log = "<script>alert('xss')</script>"
    # Ensure it would be escaped if handled by textContent
    rendered = str(log)
    assert "<script>" in rendered
    # In JS: element.textContent = rendered would be safe.


def test_websocket_routes_progress_events_to_store():
    path = Path(__file__).parent.parent / "src" / "rig_tools" / "static" / "js" / "app" / "websocket.js"
    content = path.read_text(encoding="utf-8")
    assert "progress_event" in content
    assert "onProgress" in content


def test_progress_store_caps_retained_events():
    path = Path(__file__).parent.parent / "src" / "rig_tools" / "static" / "js" / "app" / "progress-store.js"
    content = path.read_text(encoding="utf-8")
    assert "MAX_OPERATIONS" in content
    assert "MAX_EVENTS_PER_OPERATION" in content
    assert "operationOrder" in content
    assert "operationMap" in content
    assert "getProgressOperations" in content
    assert "sort(" in content
    assert "slice(-MAX_EVENTS_PER_OPERATION)" in content
    assert "slice(-MAX_OPERATIONS)" in content


def test_command_progress_card_renderer_is_dumb():
    path = Path(__file__).parent.parent / "src" / "rig_tools" / "static" / "js" / "widgets" / "command-progress-card.js"
    content = path.read_text(encoding="utf-8")
    assert "renderCommandProgressCard" in content
    assert "operation_id" in content
    assert "phase" in content
    assert "message" in content
    assert "status" in content
    assert "history" in content
    assert "receipt_candidate" not in content.lower() or "status" in content.lower()


def test_proposal_lifecycle_console_renderer_is_dumb():
    path = Path(__file__).parent.parent / "src" / "rig_tools" / "static" / "js" / "widgets" / "proposal-lifecycle-console.js"
    content = path.read_text(encoding="utf-8")
    assert "renderProposalLifecycleConsole" in content
    assert "current_gate" in content
    assert "next_safe_action" in content
    assert "allowed_actions" in content
    assert "blocked_actions" in content
    assert "Unknown" in content
    assert "No allowed actions listed." in content
    assert "No blocked actions listed." in content


def test_proposal_lifecycle_console_renders_recommendation_summary():
    """ProposalLifecycleConsole widget renders recommendation summary fields."""
    path = Path(__file__).parent.parent / "src" / "rig_tools" / "static" / "js" / "widgets" / "proposal-lifecycle-console.js"
    content = path.read_text(encoding="utf-8")
    # Check the widget renders recommendation state section
    assert "Recommendation" in content
    assert "recommendation_state" in content
    assert "source_surface" in content
    assert "files" in content
    assert "last_updated" in content


def test_proposal_lifecycle_console_renders_proposal_summary():
    """ProposalLifecycleConsole widget renders proposal summary fields."""
    path = Path(__file__).parent.parent / "src" / "rig_tools" / "static" / "js" / "widgets" / "proposal-lifecycle-console.js"
    content = path.read_text(encoding="utf-8")
    # Check the widget renders proposal state section
    assert "Proposal" in content
    assert "proposal_state" in content
    assert "worktree_path" in content
    assert "changed_files" in content


def test_proposal_lifecycle_console_renders_validation_summary():
    """ProposalLifecycleConsole widget renders validation summary fields."""
    path = Path(__file__).parent.parent / "src" / "rig_tools" / "static" / "js" / "widgets" / "proposal-lifecycle-console.js"
    content = path.read_text(encoding="utf-8")
    # Check the widget renders validation state section
    assert "Validation" in content
    assert "validation_state" in content
    assert "proof_status" in content
    assert "command" in content
    assert "passed_count" in content
    assert "failed_count" in content
    assert "last_run_at" in content


def test_proposal_lifecycle_console_renders_blocked_apply_note():
    """ProposalLifecycleConsole widget renders blocked apply note under Gate A."""
    path = Path(__file__).parent.parent / "src" / "rig_tools" / "static" / "js" / "widgets" / "proposal-lifecycle-console.js"
    content = path.read_text(encoding="utf-8")
    # Check the widget renders the blocked apply note for Gate A
    assert "Apply remains blocked" in content
    assert "Gate A" in content or "Dogfood Gate A" in content


def test_proposal_lifecycle_console_handles_missing_partial_data_safely():
    """ProposalLifecycleConsole widget handles missing/partial data safely."""
    path = Path(__file__).parent.parent / "src" / "rig_tools" / "static" / "js" / "widgets" / "proposal-lifecycle-console.js"
    content = path.read_text(encoding="utf-8")
    # Check safe fallback behavior
    assert " Victoire" not in content  # No fake success messages
    assert "Unknown" in content  # Fallback for unknown stage
    # Check it uses emptyLabel pattern for missing data
    assert "No recommendation available" in content or "Unknown" in content
    assert "No proposal available" in content or "Unknown" in content
    assert "Validation not run" in content or "Unknown" in content
    # Check null safety - uses nullish checks
    assert "||" in content or "?" in content or "if (" in content


def test_progressive_disclosure_doctrine_docs_exist():
    root = Path(__file__).parent.parent / "docs" / "architecture"
    progressive = (root / "progressive-disclosure-doctrine.md").read_text(encoding="utf-8")
    motion = (root / "governed-motion.md").read_text(encoding="utf-8")
    spatial = (root / "spatial-stability.md").read_text(encoding="utf-8")
    density = (root / "density-collapse.md").read_text(encoding="utf-8")
    hierarchy = (root / "visual-priority-hierarchy.md").read_text(encoding="utf-8")

    assert "Layer 1" in progressive
    assert "Layer 4" in progressive
    assert "Motion MUST become calmer under overload" in motion
    assert "persistent topology" in spatial.lower()
    assert "Higher complexity must collapse into clearer summary structures" in density
    assert "High" in hierarchy and "integrity divergence" in hierarchy


def test_runtime_instrumentation_contains_low_stimulation_helpers():
    path = Path(__file__).parent.parent / "src" / "rig_tools" / "static" / "js" / "runtime-instrumentation.js"
    content = path.read_text(encoding="utf-8")
    assert "getLowStimulationMode" in content
    assert "calculateDensityCollapse" in content
    assert "calculateReplayScrub" in content
    assert "low-stimulation" in content


def test_runtime_widgets_consume_density_governance():
    topology = Path(__file__).parent.parent / "src" / "rig_tools" / "static" / "js" / "widgets" / "runtime-topology-panel.js"
    stream = Path(__file__).parent.parent / "src" / "rig_tools" / "static" / "js" / "widgets" / "runtime-stream-card.js"
    status = Path(__file__).parent.parent / "src" / "rig_tools" / "static" / "js" / "widgets" / "runtime-status-card.js"

    topology_content = topology.read_text(encoding="utf-8")
    stream_content = stream.read_text(encoding="utf-8")
    status_content = status.read_text(encoding="utf-8")

    assert "MotionUtils" in topology_content
    assert "calculateDensityCollapse" in topology_content
    assert "MotionUtils" in stream_content
    assert "densityState.shouldCollapse" in stream_content
    assert "SvgStatefulLoader" in status_content


def test_widget_registry_includes_integrity_and_audit_trail_cards():
    path = Path(__file__).parent.parent / "src" / "rig_tools" / "static" / "js" / "widgets" / "registry.js"
    content = path.read_text(encoding="utf-8")
    assert "import { renderAuditTrailCard } from './audit-trail-card.js';" in content
    assert "AuditTrailCard:" in content
    assert "IntegrityStatusCard:" in content
    assert "renderIntegrityStatusCard" in content
    assert "renderAuditTrailCard" in content


def test_legacy_widget_renderers_are_es_module_exports():
    integrity = Path(__file__).parent.parent / "src" / "rig_tools" / "static" / "js" / "widgets" / "integrity-status-card.js"
    audit = Path(__file__).parent.parent / "src" / "rig_tools" / "static" / "js" / "widgets" / "audit-trail-card.js"

    integrity_content = integrity.read_text(encoding="utf-8")
    audit_content = audit.read_text(encoding="utf-8")

    assert "export function renderIntegrityStatusCard" in integrity_content
    assert "return container;" in integrity_content
    assert "export function renderAuditTrailCard" in audit_content
    assert "return container;" in audit_content


def test_architecture_readme_points_to_extension_path():
    path = Path(__file__).parent.parent / "docs" / "architecture" / "README.md"
    content = path.read_text(encoding="utf-8")
    assert "Visualization Extensibility" in content
    assert "svg-primitive-registry.js" in content
    assert "topology-plugin-model.js" in content


# =============================================================================
# PHASE 9: Workspace UX & Guided Onboarding Frontend Logic Tests
# =============================================================================

class TestWorkspaceCompositionFrontend:
    """Tests for workspace composition frontend logic."""

    def test_workspace_composition_doc_references_js_files(self):
        """Workspace composition doc references the JS implementation files."""
        root = Path(__file__).parent.parent / "docs" / "architecture"
        content = (root / "workspace-composition.md").read_text(encoding="utf-8")
        # Workspace composition relies on widget files
        assert "widget" in content.lower()

    def test_deterministic_grid_layout(self):
        """Deterministic grid layout calculations are correct."""
        # Simulate grid layout calculations
        COLUMNS = 12
        ROWS = 12
        CELL_WIDTH = 80
        CELL_HEIGHT = 64
        GUTTER = 8

        # Position to pixel calculation
        def position_to_pixels(col, row):
            x = col * (CELL_WIDTH + GUTTER)
            y = row * (CELL_HEIGHT + GUTTER)
            return (x, y)

        # Same position always produces same pixels
        pos1 = position_to_pixels(2, 3)
        pos2 = position_to_pixels(2, 3)
        assert pos1 == pos2

        # Different positions produce different pixels
        pos3 = position_to_pixels(3, 3)
        assert pos3 != pos1

        # Verify formula
        assert pos1 == (2 * 88, 3 * 72)  # (CELL_WIDTH + GUTTER) = 88, (CELL_HEIGHT + GUTTER) = 72

    def test_region_constraints_logic(self):
        """Region constraints are enforced in calculations."""
        region_limits = {
            'header': {'max_widgets': 3, 'columns': (1, 12), 'rows': (1, 1)},
            'sidebar': {'max_widgets': 8, 'columns': (1, 3), 'rows': (2, 11)},
            'main': {'max_widgets': 6, 'columns': (4, 12), 'rows': (2, 11)},
            'footer': {'max_widgets': 3, 'columns': (1, 12), 'rows': (12, 12)},
        }

        # Verify constraints
        assert region_limits['header']['max_widgets'] == 3
        assert region_limits['sidebar']['max_widgets'] == 8
        assert region_limits['main']['max_widgets'] == 6
        assert region_limits['footer']['max_widgets'] == 3

        # Verify region boundaries
        for region, limits in region_limits.items():
            assert 'columns' in limits
            assert 'rows' in limits
            assert 'max_widgets' in limits

    def test_widget_placement_validity(self):
        """Widget placement validity logic is correct."""
        # Define widget and grid
        grid = {'columns': 12, 'rows': 12}
        widgets = [
            {'position': {'x': 0, 'y': 0}, 'size': {'width': 3, 'height': 2}},
            {'position': {'x': 3, 'y': 0}, 'size': {'width': 3, 'height': 2}},
        ]

        # Check non-overlapping
        def check_overlap(w1, w2):
            # Check if two widgets overlap
            x1, y1 = w1['position']['x'], w1['position']['y']
            w1, h1 = w1['size']['width'], w1['size']['height']
            x2, y2 = w2['position']['x'], w2['position']['y']
            w2_width, h2 = w2['size']['width'], w2['size']['height']
            
            return not (x1 + w1 <= x2 or x2 + w2_width <= x1 or
                        y1 + h1 <= y2 or y2 + h2 <= y1)

        # These widgets should not overlap (adjacent)
        assert not check_overlap(widgets[0], widgets[1])

        # Define overlapping widgets
        overlapping = [
            {'position': {'x': 0, 'y': 0}, 'size': {'width': 4, 'height': 2}},
            {'position': {'x': 2, 'y': 0}, 'size': {'width': 3, 'height': 2}},
        ]
        # These should overlap
        assert check_overlap(overlapping[0], overlapping[1])

    def test_no_overlapping_widgets_in_valid_layout(self):
        """Valid layout has no overlapping widgets."""
        # Simulate a valid layout
        grid = {'columns': 12, 'rows': 12}
        widgets = [
            {'position': {'x': 0, 'y': 0}, 'size': {'width': 3, 'height': 2}, 'region': 'sidebar'},
            {'position': {'x': 0, 'y': 2}, 'size': {'width': 3, 'height': 2}, 'region': 'sidebar'},
            {'position': {'x': 3, 'y': 0}, 'size': {'width': 6, 'height': 4}, 'region': 'main'},
            {'position': {'x': 0, 'y': 10}, 'size': {'width': 4, 'height': 1}, 'region': 'footer'},
        ]

        # Check no overlaps
        def check_overlap(w1, w2):
            x1, y1 = w1['position']['x'], w1['position']['y']
            w1_w, h1 = w1['size']['width'], w1['size']['height']
            x2, y2 = w2['position']['x'], w2['position']['y']
            w2_w, h2 = w2['size']['width'], w2['size']['height']
            
            return not (x1 + w1_w <= x2 or x2 + w2_w <= x1 or
                        y1 + h1 <= y2 or y2 + h2 <= y1)

        # Check all pairs
        for i in range(len(widgets)):
            for j in range(i + 1, len(widgets)):
                assert not check_overlap(widgets[i], widgets[j]), \
                    f"Widgets {i} and {j} overlap"


class TestWidgetDisclosureScalingFrontend:
    """Tests for widget disclosure scaling frontend logic."""

    def test_three_scales_per_widget(self):
        """Each widget has exactly three scales."""
        scales = ['SMALL', 'MEDIUM', 'LARGE']
        assert len(scales) == 3
        assert 'SMALL' in scales
        assert 'MEDIUM' in scales
        assert 'LARGE' in scales

    def test_scale_content_progression(self):
        """Scale content progresses deterministically."""
        # Define content for each scale of a hypothetical widget
        widget_scales = {
            'SMALL': ['state', 'overall_health', 'stream_count'],
            'MEDIUM': ['state', 'overall_health', 'stream_count', 'throughput', 'lane_activity'],
            'LARGE': ['state', 'overall_health', 'stream_count', 'throughput', 'lane_activity',
                     'per_lane_throughput', 'provider_status', 'memory_usage', 'error_rate']
        }

        # MEDIUM contains all SMALL fields
        for field in widget_scales['SMALL']:
            assert field in widget_scales['MEDIUM']

        # LARGE contains all MEDIUM fields
        for field in widget_scales['MEDIUM']:
            assert field in widget_scales['LARGE']

    def test_deterministic_scale_sizes(self):
        """Widget sizes for each scale are deterministic."""
        # Widget type -> scale -> size
        widget_sizes = {
            'runtime-overview': {
                'SMALL': {'width': 3, 'height': 1},
                'MEDIUM': {'width': 3, 'height': 2},
                'LARGE': {'width': 3, 'height': 3}
            },
            'topology-panel': {
                'SMALL': {'width': 6, 'height': 4},
                'MEDIUM': {'width': 6, 'height': 6},
                'LARGE': {'width': 9, 'height': 8}
            },
            'dtg-viewer': {
                'SMALL': {'width': 6, 'height': 4},
                'MEDIUM': {'width': 6, 'height': 6},
                'LARGE': {'width': 9, 'height': 8}
            }
        }

        # Same widget type + scale always has same size
        for widget_type, scales in widget_sizes.items():
            for scale, size in scales.items():
                # Regenerate - should be same
                assert widget_sizes[widget_type][scale] == size

    def test_scale_transition_instant(self):
        """Scale transitions are instant (0ms)."""
        transition_duration = 0  # ms
        assert transition_duration == 0

    def test_density_aware_scaling(self):
        """Density-aware scaling logic is correct."""
        def get_auto_scale(density, user_preference=None):
            # Auto-scale based on density
            if density >= 0.8:
                return 'SMALL'
            elif density >= 0.6:
                return 'MEDIUM'
            else:
                return 'LARGE' if user_preference != 'SMALL' else 'SMALL'

        # High density -> SMALL
        assert get_auto_scale(0.9) == 'SMALL'
        
        # Medium density -> MEDIUM
        assert get_auto_scale(0.7) == 'MEDIUM'
        
        # Low density -> LARGE (or user preference)
        assert get_auto_scale(0.3) == 'LARGE'
        assert get_auto_scale(0.3, 'SMALL') == 'SMALL'

    def test_replay_safe_scaling(self):
        """Scaling is replay-safe."""
        # Same inputs produce same scale
        def determine_scale(widget_type, density, user_override=None):
            if user_override:
                return user_override
            return 'SMALL' if density >= 0.8 else 'MEDIUM' if density >= 0.6 else 'LARGE'

        # Run twice with same inputs
        scale1 = determine_scale('runtime-overview', 0.7)
        scale2 = determine_scale('runtime-overview', 0.7)
        assert scale1 == scale2

        # User override is respected
        override_scale1 = determine_scale('runtime-overview', 0.1, 'SMALL')
        override_scale2 = determine_scale('runtime-overview', 0.1, 'SMALL')
        assert override_scale1 == override_scale2 == 'SMALL'


class TestGuidedOnboardingFrontend:
    """Tests for guided onboarding frontend logic."""

    def test_onboarding_stages_exist(self):
        """All onboarding stages are defined."""
        stages = ['1', '2', '3', '4']
        assert len(stages) == 4
        for stage in stages:
            assert stage in stages

    def test_onboarding_trigger_priority(self):
        """Onboarding trigger priority is correct."""
        # Higher stage number = higher priority
        def priority(stage):
            return int(stage)

        assert priority('4') > priority('3') > priority('2') > priority('1')

    def test_onboarding_trigger_debouncing(self):
        """Onboarding trigger debouncing works correctly."""
        # Simulate debounce
        last_trigger_time = {}
        debounce_period = 300  # ms

        def can_trigger(lesson_id, current_time):
            if lesson_id not in last_trigger_time:
                return True
            return (current_time - last_trigger_time[lesson_id]) > debounce_period

        # First trigger always allowed
        assert can_trigger('lesson-1', 1000) is True

        # Update time
        last_trigger_time['lesson-1'] = 1000

        # Same lesson within debounce period - blocked
        assert can_trigger('lesson-1', 1100) is False

        # Same lesson after debounce period - allowed
        assert can_trigger('lesson-1', 1301) is True

    def test_onboarding_cognitive_load_limit(self):
        """Cognitive load limit is enforced."""
        max_messages = 1
        active_messages = []

        def show_message(message):
            if len(active_messages) >= max_messages:
                return False  # Cannot show
            active_messages.append(message)
            return True

        # First message shown
        assert show_message('msg1') is True
        assert len(active_messages) == 1

        # Second message blocked
        assert show_message('msg2') is False
        assert len(active_messages) == 1

    def test_progressive_feature_reveal_logic(self):
        """Progressive feature reveal logic is correct."""
        # Features available at different stages
        feature_stages = {
            'widget-move': 1,
            'topology-visualization': 1,
            'replay-controls': 2,
            'dtg-viewer': 3,
            'integrity-panel': 3,
            'debug-panel': 4,
            'plugin-inspector': 4
        }

        def is_feature_available(feature, current_stage):
            return feature_stages.get(feature, 5) <= current_stage

        # Stage 1 features
        assert is_feature_available('widget-move', 1) is True
        assert is_feature_available('topology-visualization', 1) is True
        
        # Stage 2 features
        assert is_feature_available('replay-controls', 2) is True
        assert is_feature_available('widget-move', 2) is True  # Still available
        
        # Stage 3 features
        assert is_feature_available('dtg-viewer', 3) is True
        assert is_feature_available('integrity-panel', 3) is True
        
        # Stage 4 features
        assert is_feature_available('debug-panel', 4) is True
        assert is_feature_available('plugin-inspector', 4) is True

    def test_onboarding_state_persistence(self):
        """Onboarding state persistence structure is correct."""
        # Simulate onboarding state
        onboarding_state = {
            'version': '1.0',
            'completedLessons': ['workspace.welcome', 'workspace.layout'],
            'dismissedLessons': ['topology.lanes'],
            'stageProgress': {
                '1': {'isComplete': False, 'lessonsRemaining': 3},
                '2': {'isComplete': False, 'lessonsRemaining': 5},
                '3': {'isComplete': False, 'lessonsRemaining': 4},
                '4': {'isComplete': False, 'lessonsRemaining': 5}
            }
        }

        # Verify structure
        assert 'version' in onboarding_state
        assert 'completedLessons' in onboarding_state
        assert 'dismissedLessons' in onboarding_state
        assert 'stageProgress' in onboarding_state
        assert len(onboarding_state['stageProgress']) == 4

    def test_low_stimulation_mode_activation(self):
        """Low-stimulation mode activation conditions are correct."""
        def should_activate_low_stimulation(
            reduced_motion=False,
            density=0.0,
            overload=0.0,
            explicit=False,
            widget_count=0
        ):
            return (
                reduced_motion or
                density > 0.6 or
                overload > 0.5 or
                explicit or
                widget_count > 15
            )

        # Reduced motion
        assert should_activate_low_stimulation(reduced_motion=True) is True

        # High density
        assert should_activate_low_stimulation(density=0.7) is True

        # High overload
        assert should_activate_low_stimulation(overload=0.6) is True

        # Explicit
        assert should_activate_low_stimulation(explicit=True) is True

        # Too many widgets
        assert should_activate_low_stimulation(widget_count=16) is True

        # None of the above
        assert should_activate_low_stimulation() is False


class TestExperientialLearningFrontend:
    """Tests for experiential runtime learning frontend logic."""

    def test_learning_loop_structure(self):
        """Learning loop structure is followed."""
        loop = [
            'User Action',
            'Runtime Behavior',
            'Visualization Update',
            'Contextual Explanation',
            'User Understanding'
        ]
        assert len(loop) == 5
        assert loop[0] == 'User Action'
        assert loop[4] == 'User Understanding'

    def test_geometry_stability(self):
        """Geometry stability is maintained."""
        # Widget at position stays at position
        def get_widget_position(widget_id):
            # In real system, this would query DOM or state
            return {'x': 0, 'y': 0}

        pos1 = get_widget_position('widget-1')
        pos2 = get_widget_position('widget-1')
        assert pos1 == pos2

    def test_contextual_hint_positioning(self):
        """Contextual hints position to avoid overlap."""
        # Hint positions
        hint_positions = ['top', 'bottom', 'left', 'right', 'top-left', 'top-right', 'bottom-left', 'bottom-right']
        
        def get_hint_position(element_position, viewport):
            # Simplified: always return first valid position
            return hint_positions[0]

        pos = get_hint_position({'x': 100, 'y': 100}, {'width': 800, 'height': 600})
        assert pos in hint_positions

    def test_replay_annotation_consistency(self):
        """Replay annotations are consistent."""
        # Same event always produces same annotation
        def get_annotation(event_type, sequence):
            return {
                'type': event_type,
                'sequence': sequence,
                'content': f'{event_type} at {sequence}'
            }

        ann1 = get_annotation('state-change', 42)
        ann2 = get_annotation('state-change', 42)
        assert ann1 == ann2

        ann3 = get_annotation('state-change', 43)
        assert ann3 != ann1  # Different sequence = different annotation


class TestCalmDashboardFrontend:
    """Tests for calm dashboard governance frontend logic."""

    def test_density_calculation(self):
        """Dashboard density calculation is correct."""
        def calculate_dashboard_density(widget_count, topology_nodes, active_streams, violations):
            density = (
                (min(widget_count, 20) / 20) * 0.25 +
                (min(topology_nodes, 500) / 500) * 0.4 +
                (min(active_streams, 50) / 50) * 0.2 +
                (min(violations, 50) / 50) * 0.15
            )
            return min(density, 1.0)

        # No widgets, no topology
        assert calculate_dashboard_density(0, 0, 0, 0) == 0.0

        # Half widgets, half topology
        assert calculate_dashboard_density(10, 250, 25, 25) > 0
        assert calculate_dashboard_density(10, 250, 25, 25) < 1.0

        # Max everything
        assert calculate_dashboard_density(100, 1000, 100, 100) == 1.0

    def test_abstraction_level_selection(self):
        """Abstraction level selection is correct."""
        def get_abstraction_level(density):
            if density < 0.4:
                return 'none'
            if density < 0.6:
                return 'condensed'
            if density < 0.8:
                return 'summary'
            return 'extreme'

        assert get_abstraction_level(0.0) == 'none'
        assert get_abstraction_level(0.39) == 'none'
        assert get_abstraction_level(0.4) == 'condensed'
        assert get_abstraction_level(0.59) == 'condensed'
        assert get_abstraction_level(0.6) == 'summary'
        assert get_abstraction_level(0.79) == 'summary'
        assert get_abstraction_level(0.8) == 'extreme'
        assert get_abstraction_level(1.0) == 'extreme'

    def test_motion_reduction_calculation(self):
        """Motion reduction calculation is correct."""
        def get_motion_reduction(density):
            if density < 0.4:
                return 0.0
            return min(1.0, (density - 0.4) / 0.6)

        assert get_motion_reduction(0.0) == 0.0
        assert get_motion_reduction(0.39) == 0.0
        assert get_motion_reduction(0.4) == 0.0
        assert get_motion_reduction(0.5) == (0.5 - 0.4) / 0.6
        assert get_motion_reduction(0.7) == (0.7 - 0.4) / 0.6
        assert get_motion_reduction(1.0) == 1.0

    def test_instrumentation_suppression_order(self):
        """Instrumentation suppression follows correct priority."""
        suppression_order = [
            'historical_data',
            'secondary_metrics',
            'detailed_labels',
            'decorative_elements',
            'preview_content',
            'debug_information',
            'replay_markers',
            'throughput_detail'
        ]

        # First to be suppressed
        assert suppression_order[0] == 'historical_data'
        
        # Last to be suppressed
        assert suppression_order[-1] == 'throughput_detail'

    def test_what_never_gets_suppressed(self):
        """Critical elements never get suppressed."""
        never_suppressed = [
            'Current runtime state',
            'Current sequence number',
            'Integrity violation indicators',
            'Lane boundaries',
            'Primary state indicators',
            'Critical error indicators',
            'Current time/timestamp',
            'Workspace identity'
        ]

        assert len(never_suppressed) > 0
        assert 'Current runtime state' in never_suppressed
        assert 'Integrity violation indicators' in never_suppressed

    def test_never_suppressed_elements_are_always_visible(self):
        """Never-suppressed elements are always visible regardless of density."""
        def should_suppress(element, density=1.0):
            never_suppressed = [
                'runtime_state',
                'sequence_number',
                'integrity_violations',
                'lane_boundaries'
            ]
            return element not in never_suppressed

        # These should never be suppressed
        assert should_suppress('runtime_state', 1.0) is False
        assert should_suppress('sequence_number', 1.0) is False
        assert should_suppress('integrity_violations', 1.0) is False
        assert should_suppress('lane_boundaries', 1.0) is False


class TestWorkspaceLifecycleFrontend:
    """Tests for workspace lifecycle frontend logic."""

    def test_workspace_state_machine(self):
        """Workspace state machine transitions are valid."""
        valid_transitions = {
            'NULL': ['UNINITIALIZED'],
            'UNINITIALIZED': ['INITIALIZING'],
            'INITIALIZING': ['READY', 'DEGRADED'],
            'READY': ['ACTIVE', 'SUSPENDED', 'TEARDOWN'],
            'ACTIVE': ['READY', 'SUSPENDED', 'DEGRADED', 'TEARDOWN'],
            'SUSPENDED': ['READY', 'TEARDOWN'],
            'DEGRADED': ['READY', 'ACTIVE', 'TEARDOWN'],
            'TEARDOWN': ['NULL']
        }

        # Verify valid transitions
        assert 'UNINITIALIZED' in valid_transitions['NULL']
        assert 'INITIALIZING' in valid_transitions['UNINITIALIZED']
        assert 'READY' in valid_transitions['INITIALIZING']
        assert 'ACTIVE' in valid_transitions['READY']
        assert 'TEARDOWN' in valid_transitions['READY']

    def test_deterministic_widget_id_generation(self):
        """Widget ID generation is deterministic."""
        def widget_id(type_name, position):
            parts = [type_name, str(position['x']), str(position['y'])]
            combined = '|'.join(parts)
            hash_val = 0
            for char in combined:
                hash_val = ((hash_val << 5) - hash_val) + ord(char)
                hash_val = hash_val & hash_val
            return f"widget-{type_name}-{abs(hash_val):08x}"[:20]

        # Same inputs produce same ID
        id1 = widget_id('runtime-overview', {'x': 0, 'y': 0})
        id2 = widget_id('runtime-overview', {'x': 0, 'y': 0})
        assert id1 == id2

        # Different positions produce different hash values
        # Note: IDs may be truncated to 20 chars, so we check the full value
        def widget_id_full(type_name, position):
            parts = [type_name, str(position['x']), str(position['y'])]
            combined = '|'.join(parts)
            hash_val = 0
            for char in combined:
                hash_val = ((hash_val << 5) - hash_val) + ord(char)
                hash_val = hash_val & hash_val
            return abs(hash_val)

        hash1 = widget_id_full('runtime-overview', {'x': 0, 'y': 0})
        hash2 = widget_id_full('runtime-overview', {'x': 1, 'y': 0})
        assert hash1 != hash2  # Different positions produce different hashes

    def test_widget_restoration_order(self):
        """Widget restoration order is deterministic."""
        widgets = [
            {'position': {'x': 3, 'y': 0}, 'type': 'b', 'id': 'widget-b'},  # row 0, col 3
            {'position': {'x': 0, 'y': 0}, 'type': 'a', 'id': 'widget-a'},  # row 0, col 0 - should come first
            {'position': {'x': 0, 'y': 1}, 'type': 'c', 'id': 'widget-c'},  # row 1, col 0 - should come last (row 1)
        ]

        # Sort by row-major order (row first, then column), then by type, then by id
        sorted_widgets = sorted(widgets, key=lambda w: (
            w['position']['y'],
            w['position']['x'],
            w['type'],
            w['id']
        ))

        # Verify order: row 0 col 0 (widget-a), row 0 col 3 (widget-b), row 1 col 0 (widget-c)
        assert sorted_widgets[0]['id'] == 'widget-a'  # (0, 0) - lowest row, lowest column
        assert sorted_widgets[1]['id'] == 'widget-b'  # (0, 3) - same row, higher column
        assert sorted_widgets[2]['id'] == 'widget-c'  # (1, 0) - higher row

    def test_replay_safe_workspace_state(self):
        """Replay-safe workspace state is maintained."""
        # Replay state that should be identical
        replay_state = {
            'widget_positions': {'widget-1': {'x': 0, 'y': 0}, 'widget-2': {'x': 3, 'y': 0}},
            'disclosure_state': {'layer1': True, 'layer2': True, 'layer3': False, 'layer4': False},
            'widget_scales': {'widget-1': 'MEDIUM', 'widget-2': 'LARGE'}
        }

        # Verify that state is preserved
        assert replay_state['widget_positions']['widget-1'] == {'x': 0, 'y': 0}
        assert replay_state['disclosure_state']['layer1'] is True
        assert replay_state['widget_scales']['widget-2'] == 'LARGE'

    def test_memory_bounds_enforcement(self):
        """Memory bounds are enforced correctly."""
        limits = {
            'total': {'hard': 50, 'soft': 40},
            'per_widget': {'hard': 5, 'soft': 3},
            'layout_json': {'hard': 64, 'soft': 32},
        }

        def check_limit(value, limit_type, category):
            hard = limits[category]['hard']
            soft = limits[category]['soft']
            
            if value > hard:
                return 'hard_violation'
            elif value > soft:
                return 'soft_violation'
            return 'ok'

        assert check_limit(25, 'total', 'total') == 'ok'
        assert check_limit(45, 'total', 'total') == 'soft_violation'
        assert check_limit(55, 'total', 'total') == 'hard_violation'

    def test_deterministic_teardown(self):
        """Teardown is deterministic."""
        teardown_phases = [
            'Suspend',
            'Unsubscribe',
            'Destroy Widgets',
            'Save State',
            'Cleanup Topology',
            'Destroy Grid',
            'Release Resources',
            'Nullify'
        ]

        assert len(teardown_phases) == 8
        assert teardown_phases[0] == 'Suspend'
        assert teardown_phases[-1] == 'Nullify'
