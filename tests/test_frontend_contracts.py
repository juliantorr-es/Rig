from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
JS_ROOT = ROOT / "src" / "rig_tools" / "static" / "js"
WIDGETS = JS_ROOT / "widgets"


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_registry_includes_canonical_widget_exports():
    content = read_text(WIDGETS / "registry.js")
    expected_imports = [
        "renderEmptyStateCard",
        "renderValidatorStack",
        "renderReceiptList",
        "renderBackendStatus",
        "renderWorkspaceHeader",
        "renderWorkspaceGitState",
        "renderWorkspaceLaneSummary",
        "renderLogStream",
        "renderCommandProgressCard",
        "renderProposalLifecycleConsole",
        "renderFundingSummaryCard",
        "renderIntegrityStatusCard",
        "renderAuditTrailCard",
        "renderReplayTimelineCard",
    ]
    for symbol in expected_imports:
        assert symbol in content


def test_widget_exports_are_present_and_registered():
    exports = {
        "empty-state-card.js": "renderEmptyStateCard",
        "validator-stack.js": "renderValidatorStack",
        "receipt-list.js": "renderReceiptList",
        "backend-status.js": "renderBackendStatus",
        "workspace-header.js": "renderWorkspaceHeader",
        "workspace-git-state.js": "renderWorkspaceGitState",
        "workspace-lane-summary.js": "renderWorkspaceLaneSummary",
        "log-stream.js": "renderLogStream",
        "command-progress-card.js": "renderCommandProgressCard",
        "proposal-lifecycle-console.js": "renderProposalLifecycleConsole",
        "funding-summary-card.js": "renderFundingSummaryCard",
        "integrity-status-card.js": "renderIntegrityStatusCard",
        "audit-trail-card.js": "renderAuditTrailCard",
        "replay-timeline-card.js": "renderReplayTimelineCard",
    }

    registry = read_text(WIDGETS / "registry.js")
    for filename, symbol in exports.items():
        content = read_text(WIDGETS / filename)
        assert f"export function {symbol}" in content or f"module.exports = {{ {symbol} }}" in content
        assert symbol in registry


def test_runtime_widget_registry_is_deterministic_and_projection_only():
    content = read_text(WIDGETS / "runtime-widget-registry.js")
    assert "Projection-only rendering (never fetches data)" in content
    assert "No authority inference" in content
    assert "deterministic rendering" in content.lower()
    assert "widgetMetadata" in content
    assert "RuntimeWidgetDesign" in content
    assert "renderRuntimeExecutionPanel" in content or "runtimeExecutionPanel" in content


def test_topology_widgets_participate_in_reduced_motion_and_disclosure_governance():
    runtime_topology = read_text(WIDGETS / "runtime-topology-panel.js")
    runtime_stream = read_text(WIDGETS / "runtime-stream-card.js")
    runtime_status = read_text(WIDGETS / "runtime-status-card.js")
    proposal_console = read_text(WIDGETS / "proposal-lifecycle-console.js")

    assert "MotionUtils" in runtime_topology
    assert "SvgExecutionLane" in runtime_topology
    assert "SvgStatefulLoader" in runtime_status
    assert "densityState.shouldCollapse" in runtime_stream
    assert "Apply remains blocked" in proposal_console
    assert "No recommendation available" in proposal_console


def test_esm_import_surface_is_valid():
    content = read_text(WIDGETS / "registry.js")
    assert "import { renderEmptyStateCard }" in content
    assert "import { renderProposalLifecycleConsole }" in content
    assert "import { renderReplayTimelineCard }" in content
    assert "export function buildWidgetRegistry" in content


def test_registry_has_fallback_for_unregistered_widgets():
    content = read_text(WIDGETS / "registry.js")
    assert "_fallback" in content
    assert "Unknown widget:" in content
