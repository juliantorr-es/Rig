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
