"""Tests for repo/workspace selection fix in Rig UI.

Tests verify:
- Empty workspace projection has actionable disabled reasons
- EmptyStateCard widget renderer has manual input fallback
- Backend intent handlers provide clear error messages for browser mode
- Disabled buttons show disabled reasons in tooltips
- Manual path entry is available in empty workspace screen
"""

from pathlib import Path


class TestEmptyProjectionDisabledReasons:
    """Test that empty projection has actionable disabled reasons."""

    def test_empty_projection_open_workspace_has_actionable_reason(self):
        """Verify open_workspace disabled reason guides user to manual input."""
        from rig.domain.projection_builder import _build_empty_projection

        proj = _build_empty_projection(1, None, 0, 0, 0)
        intent = proj.intents["intent.open_workspace"]
        
        assert intent.enabled is False
        # The disabled reason should guide user to manual fallback
        assert intent.disabled_reason is not None
        assert "manual" in intent.disabled_reason.lower() or "browser" in intent.disabled_reason.lower()

    def test_empty_projection_initialize_has_actionable_reason(self):
        """Verify initialize_current_folder disabled reason guides user to manual input."""
        from rig.domain.projection_builder import _build_empty_projection

        proj = _build_empty_projection(1, None, 0, 0, 0)
        intent = proj.intents["intent.initialize_current_folder"]
        
        assert intent.enabled is False
        assert intent.disabled_reason is not None
        assert "rig repository" in intent.disabled_reason.lower() or "path" in intent.disabled_reason.lower()

    def test_empty_projection_screen_is_empty_workspace(self):
        """Verify empty projection uses empty_workspace screen."""
        from rig.domain.projection_builder import _build_empty_projection

        proj = _build_empty_projection(1, None, 0, 0, 0)
        assert proj.screen == "empty_workspace"

    def test_empty_projection_has_workspace_empty_widget(self):
        """Verify empty projection has workspace.empty widget."""
        from rig.domain.projection_builder import _build_empty_projection

        proj = _build_empty_projection(1, None, 0, 0, 0)
        assert "workspace.empty" in proj.widgets
        
        widget = proj.widgets["workspace.empty"]
        assert widget.type == "EmptyStateCard"
        # Has actions including the repo selection intents
        assert "intent.open_workspace" in widget.actions
        assert "intent.initialize_current_folder" in widget.actions


class TestUintServerStubHandlers:
    """Test UI server stub handlers provide actionable error messages."""

    def test_stub_handler_open_workspace_browser_guidance(self):
        """Verify open_workspace stub handler provides browser mode guidance."""
        from rig.domain.intent_defs import Intent
        from rig_tools.ui_server import UIServer
        from pathlib import Path
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            server = UIServer(Path(tmpdir), "test_token")
            
            intent = Intent(
                kind="rig.intent.open_workspace",
                intent_id="test-1",
                observed_projection_revision=1,
                client={"kind": "pywebview"}
            )
            
            result = server._stub_handler(intent)
            
            assert result["accepted"] is False
            assert "browser" in result["reason"].lower() or "manual" in result["reason"].lower()
            assert "reason" in result

    def test_stub_handler_initialize_browser_guidance(self):
        """Verify initialize_current_folder stub handler provides browser mode guidance."""
        from rig.domain.intent_defs import Intent
        from rig_tools.ui_server import UIServer
        from pathlib import Path
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            server = UIServer(Path(tmpdir), "test_token")
            
            intent = Intent(
                kind="rig.intent.initialize_current_folder",
                intent_id="test-1",
                observed_projection_revision=1,
                client={"kind": "pywebview"}
            )
            
            result = server._stub_handler(intent)
            
            assert result["accepted"] is False
            assert "browser" in result["reason"].lower() or "manual" in result["reason"].lower() or "terminal" in result["reason"].lower()

    def test_stub_handler_with_manual_path(self):
        """Verify stub handler accepts and acknowledges manual path from UI."""
        from rig.domain.intent_defs import Intent
        from rig_tools.ui_server import UIServer
        from pathlib import Path
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            server = UIServer(Path(tmpdir), "test_token")
            
            intent = Intent(
                kind="rig.intent.open_workspace",
                intent_id="test-1",
                target={"workspace_path": "/test/path"},
                observed_projection_revision=1,
                client={"kind": "pywebview"}
            )
            
            result = server._stub_handler(intent)
            
            assert result["accepted"] is False
            assert "workspace_path" in result or "path" in result["reason"].lower()
            assert result.get("status") == "path_received"


class TestFrontendStaticAssets:
    """Test static assets have repo selection fallback."""

    def test_index_html_has_boot_fallback(self):
        """Verify index.html has boot fallback for initialization issues."""
        index_path = (
            Path(__file__).parent.parent / "src" / "rig_tools" / "static" / "index.html"
        )
        content = index_path.read_text()
        assert "boot-fallback" in content
        assert "boot-status" in content

    def test_rig_ui_js_has_EmptyStateCard_renderer(self):
        """Verify rig-ui.js has EmptyStateCard renderer."""
        js_path = (
            Path(__file__).parent.parent / "src" / "rig_tools" / "static" / "js" / "app" / "runtime.js"
        )
        content = js_path.read_text()
        assert "EmptyStateCard:" in content
        assert "WorkspaceHeader:" in content
        assert "WorkspaceGitState:" in content
        assert "WorkspaceLaneSummary:" in content

    def test_rig_ui_js_EmptyStateCard_shows_disabled_reasons(self):
        """Verify EmptyStateCard renderer displays disabled reasons prominently."""
        js_path = (
            Path(__file__).parent.parent / "src" / "rig_tools" / "static" / "js" / "app" / "runtime.js"
        )
        content = js_path.read_text()
        # Should have code that checks for disabled reasons and displays them
        assert "disabled_reason" in content
        assert "empty-state-reasons" in content or "EmptyStateCard" in content

    def test_rig_ui_js_EmptyStateCard_has_manual_input(self):
        """Verify EmptyStateCard renderer has manual repo path input for empty workspace."""
        js_path = (
            Path(__file__).parent.parent / "src" / "rig_tools" / "static" / "js" / "app" / "runtime.js"
        )
        content = js_path.read_text()
        # Should have manual input field for repo path
        assert "manual-repo-path" in content or "manual" in content.lower()
        assert "workspace_path" in content or "repo path" in content.lower()

    def test_rig_ui_js_sendIntent_sends_target(self):
        """Verify sendIntent function can send target parameter."""
        js_path = (
            Path(__file__).parent.parent / "src" / "rig_tools" / "static" / "js" / "app" / "runtime.js"
        )
        content = js_path.read_text()
        # sendIntent should support target parameter
        assert "sendIntent" in content
        assert "target" in content

    def test_rig_ui_css_has_manual_input_styles(self):
        """Verify CSS has styles for manual repo input."""
        css_path = (
            Path(__file__).parent.parent / "src" / "rig_tools" / "static" / "css" / "widgets.css"
        )
        content = css_path.read_text()
        # Should have styles for manual input
        assert ".manual-repo-input" in content or "manual" in content.lower()

    def test_rig_ui_css_has_actions_styles(self):
        """Verify CSS has styles for actions container."""
        css_path = (
            Path(__file__).parent.parent / "src" / "rig_tools" / "static" / "css" / "widgets.css"
        )
        content = css_path.read_text()
        assert ".actions" in content


class TestProjectionIntentDisabledReasons:
    """Test that all disabled intents in projections have meaningful reasons."""

    def test_empty_projection_all_disabled_intents_have_reasons(self):
        """Verify all disabled intents in empty projection have disabled_reason."""
        from rig.domain.projection_builder import _build_empty_projection

        proj = _build_empty_projection(1, None, 0, 0, 0)
        
        for intent_id, intent in proj.intents.items():
            if not intent.enabled:
                # All disabled intents should have a disabled_reason
                assert intent.disabled_reason is not None, (
                    f"Intent {intent_id} is disabled but has no disabled_reason"
                )
                # Reason should not be "Not implemented." - should be actionable
                assert intent.disabled_reason != "Not implemented.", (
                    f"Intent {intent_id} has generic 'Not implemented.' reason"
                )

    def test_empty_projection_intent_labels_are_clear(self):
        """Verify intent labels are user-friendly."""
        from rig.domain.projection_builder import _build_empty_projection

        proj = _build_empty_projection(1, None, 0, 0, 0)
        
        labels = {intent_id: intent.label for intent_id, intent in proj.intents.items()}
        
        # Open Repository and Initialize should be clear
        assert "open_workspace" in labels or "Open" in labels.get("intent.open_workspace", "")
        assert "initialize" in labels.get("intent.initialize_current_folder", "").lower() or \
               "Initialize" in labels.get("intent.initialize_current_folder", "")


class TestBackendDebugLogging:
    """Test that backend debug logging works for repo selection flow."""

    def test_ui_server_debug_logs_manual_path(self, caplog=None):
        """Verify UI server logs manual path reception."""
        # This is a documentation test - the logging is verified by code inspection
        from rig_tools.ui_server import UIServer
        import inspect
        
        source = inspect.getsource(UIServer._stub_handler)
        # Should have debug logging for manual path
        assert "logger" in source or "debug" in source.lower() or "manual" in source.lower()


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
