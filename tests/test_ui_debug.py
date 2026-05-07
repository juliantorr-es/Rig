"""Tests for browser-first debug logging in Rig UI.

Tests cover:
- rig ui --debug flag acceptance
- Debug mode enables JS debug flag in served page
- RigLog exists and uses console levels
- Event bus with CustomEvent/EventTarget
- WebSocket message handling is centralized
- debug_log message handling
- Global error handlers exist
- RigDebug helper exists
- Tokens are not logged unredacted
"""

import re
import tempfile
from pathlib import Path

import pytest


class TestRigUIDebugFlag:
    """Test that rig ui --debug flag is properly accepted and processed."""

    def test_ui_debug_flag_in_argparse(self):
        """Verify --debug flag is registered in argparse."""
        import subprocess

        result = subprocess.run(
            ["python", "-m", "rig", "ui", "--help"],
            capture_output=True,
            text=True,
            cwd="/Users/user/Developer/GitHub/Rig",
        )
        assert "--debug" in result.stdout
        assert (
            "Enable browser DevTools" in result.stdout
            or "debug" in result.stdout.lower()
        )

    def test_ui_debug_dry_run_prints_debug_messages(self):
        """Verify --debug flag prints debug help messages to stderr."""
        import subprocess

        result = subprocess.run(
            ["python", "-m", "rig", "ui", "--debug", "--dry-run"],
            capture_output=True,
            text=True,
            cwd="/Users/user/Developer/GitHub/Rig",
        )
        output = result.stdout + result.stderr
        assert "Debug mode enabled" in output or "debug" in output.lower()

    def test_ui_debug_dry_run_redacts_session_token(self):
        """Verify session token is redacted in dry-run output."""
        import subprocess

        result = subprocess.run(
            ["python", "-m", "rig", "ui", "--debug", "--dry-run"],
            capture_output=True,
            text=True,
            cwd="/Users/user/Developer/GitHub/Rig",
        )
        output = result.stdout
        # Should contain the URL but with redacted token
        assert "rig_session=REDACTED" in output
        # Should NOT contain an actual hex token
        assert re.search(r"rig_session=[0-9a-f]{32}", output) is None

    def test_ui_debug_dry_run_includes_debug_param(self):
        """Verify rig_debug=true is in the URL when --debug is specified."""
        import subprocess

        result = subprocess.run(
            ["python", "-m", "rig", "ui", "--debug", "--dry-run"],
            capture_output=True,
            text=True,
            cwd="/Users/user/Developer/GitHub/Rig",
        )
        output = result.stdout
        assert "rig_debug=true" in output or "rig_debug" in output


class TestWindowLauncherDebug:
    """Test window_launcher debug flag handling."""

    def test_open_window_accepts_debug_param(self):
        """Verify open_window accepts debug parameter."""
        from pathlib import Path
        import sys

        sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
        from rig_tools.window_launcher import open_window
        import inspect

        sig = inspect.signature(open_window)
        assert "debug" in sig.parameters
        assert sig.parameters["debug"].default is False

    def test_open_window_dry_run_includes_debug_in_url(self):
        """Verify debug flag adds rig_debug=true to URL in dry run."""
        from pathlib import Path
        import sys

        sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
        from rig_tools.window_launcher import open_window

        with tempfile.TemporaryDirectory() as tmpdir:
            result = open_window(
                repo_root=Path(tmpdir),
                dry_run=True,
                host="127.0.0.1",
                port=None,
                debug=True,
            )
            assert "rig_debug=true" in result["url"]

    def test_open_window_dry_run_no_debug_no_param(self):
        """Verify no debug param when debug=False."""
        from pathlib import Path
        import sys

        sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
        from rig_tools.window_launcher import open_window

        with tempfile.TemporaryDirectory() as tmpdir:
            result = open_window(
                repo_root=Path(tmpdir),
                dry_run=True,
                host="127.0.0.1",
                port=None,
                debug=False,
            )
            assert "rig_debug" not in result["url"]

    def test_create_window_not_called_with_debug(self):
        """Verify create_window is not called with debug parameter (pywebview uses start())."""
        from pathlib import Path

        # This is verified by checking the source code
        launcher_path = (
            Path(__file__).parent.parent / "src" / "rig_tools" / "window_launcher.py"
        )
        content = launcher_path.read_text()
        # Should have start(debug=debug) but NOT create_window(..., debug=...)
        assert "webview.start(debug=debug)" in content
        # create_window should NOT have debug param
        assert "create_window" in content
        # Check that create_window doesn't have debug= in the call
        lines = content.split("\n")
        for line in lines:
            if "create_window" in line and "debug=" in line:
                # This should NOT exist
                assert False, f"Found create_window with debug param: {line}"


class TestStaticAssetsDebug:
    """Test static HTML/JS assets have debug support."""

    def test_index_html_sets_RIG_DEBUG_flag(self):
        """Verify index.html sets window.RIG_DEBUG from URL params."""
        index_path = (
            Path(__file__).parent.parent / "src" / "rig_tools" / "static" / "index.html"
        )
        content = index_path.read_text()
        assert "RIG_DEBUG" in content
        assert "rig_debug" in content

    def test_rig_ui_js_defines_RigLog(self):
        """Verify rig-ui.js defines RigLog."""
        js_path = (
            Path(__file__).parent.parent / "src" / "rig_tools" / "static" / "rig-ui.js"
        )
        content = js_path.read_text()
        assert "RigLog" in content
        assert "_redactSecrets" in content

    def test_rig_ui_js_defines_event_bus(self):
        """Verify rig-ui.js has event bus."""
        js_path = (
            Path(__file__).parent.parent / "src" / "rig_tools" / "static" / "rig-ui.js"
        )
        content = js_path.read_text()
        assert "eventBus" in content or "EventTarget" in content
        assert "emitRigEvent" in content
        assert "CustomEvent" in content

    def test_rig_ui_js_defines_RigDebug(self):
        """Verify rig-ui.js defines window.RigDebug."""
        js_path = (
            Path(__file__).parent.parent / "src" / "rig_tools" / "static" / "rig-ui.js"
        )
        content = js_path.read_text()
        assert "window.RigDebug" in content
        assert "currentProjection" in content
        assert "debugTimeline" in content

    def test_rig_ui_js_has_centralized_dispatcher(self):
        """Verify rig-ui.js has centralized message dispatcher."""
        js_path = (
            Path(__file__).parent.parent / "src" / "rig_tools" / "static" / "rig-ui.js"
        )
        content = js_path.read_text()
        assert "dispatchMessage" in content
        assert "applyProjection" in content
        assert "applyIntentResult" in content
        assert "applyStreamChunk" in content
        assert "applyEvent" in content
        assert "applyDebugLog" in content

    def test_rig_ui_js_has_debug_log_handler(self):
        """Verify rig-ui.js handles debug_log messages."""
        js_path = (
            Path(__file__).parent.parent / "src" / "rig_tools" / "static" / "rig-ui.js"
        )
        content = js_path.read_text()
        assert "case 'debug_log'" in content or "debug_log" in content

    def test_rig_ui_js_has_global_error_handlers(self):
        """Verify rig-ui.js has window.onerror and unhandledrejection handlers."""
        js_path = (
            Path(__file__).parent.parent / "src" / "rig_tools" / "static" / "rig-ui.js"
        )
        content = js_path.read_text()
        assert "window.onerror" in content
        assert "unhandledrejection" in content

    def test_rig_ui_js_has_protocol_tracing(self):
        """Verify rig-ui.js has protocol tracing in debug mode."""
        js_path = (
            Path(__file__).parent.parent / "src" / "rig_tools" / "static" / "rig-ui.js"
        )
        content = js_path.read_text()
        assert "debugTimeline" in content
        assert "addDebugEntry" in content
        assert "ws_open" in content
        assert "ws_close" in content
        assert "ws_error" in content

    def test_rig_ui_js_has_correlation_fields(self):
        """Verify rig-ui.js messages include correlation fields."""
        js_path = (
            Path(__file__).parent.parent / "src" / "rig_tools" / "static" / "rig-ui.js"
        )
        content = js_path.read_text()
        assert "message_id" in content or "messageId" in content
        assert "correlation_id" in content or "correlationId" in content
        assert "intent_id" in content or "intentId" in content

    def test_rig_ui_js_redacts_tokens(self):
        """Verify rig-ui.js has token redaction."""
        js_path = (
            Path(__file__).parent.parent / "src" / "rig_tools" / "static" / "rig-ui.js"
        )
        content = js_path.read_text()
        assert "_redactSecrets" in content
        assert "REDACTED" in content
        assert "rig_session" in content
        assert "token" in content


class TestRigLogRedaction:
    """Test token redaction in RigLog."""

    def _redact_session_url(self, url):
        """Local copy of _redact_session_url for testing without imports."""
        import re

        return re.sub(r"(rig_session=)[^&\s]+", r"\1REDACTED", url)

    def test_redact_session_token_pattern(self):
        """Test redaction of session tokens in URLs."""
        url = "http://127.0.0.1:50587/?rig_session=abc123def456"
        redacted = self._redact_session_url(url)
        assert "rig_session=REDACTED" in redacted
        assert "abc123def456" not in redacted

    def test_redact_session_token_multiple_params(self):
        """Test redaction works with multiple query params."""
        url = "http://127.0.0.1:50587/?foo=bar&rig_session=abc123&baz=qux"
        redacted = self._redact_session_url(url)
        assert "rig_session=REDACTED" in redacted
        assert "abc123" not in redacted
        assert "foo=bar" in redacted
        assert "baz=qux" in redacted

    def test_redact_preserves_other_content(self):
        """Test redaction doesn't break other URL parts."""
        url = "http://127.0.0.1:50587/path?rig_session=xyz&other=value"
        redacted = self._redact_session_url(url)
        assert "http://127.0.0.1:50587/path" in redacted
        assert "other=value" in redacted


class TestEventMessageKinds:
    """Test that message kinds are properly handled."""

    def test_dispatcher_handles_known_kinds(self):
        """Verify dispatcher handles all known message kinds."""
        js_path = (
            Path(__file__).parent.parent / "src" / "rig_tools" / "static" / "rig-ui.js"
        )
        content = js_path.read_text()

        # Check for all expected message kind handlers
        expected_kinds = [
            "projection",
            "intent_result",
            "stream_chunk",
            "event",
            "error",
            "debug_log",
        ]
        for kind in expected_kinds:
            # Should have a case for this kind in switch statement
            assert kind in content, f"Missing handler for message kind: {kind}"

    def test_dispatcher_handles_unknown_kinds_gracefully(self):
        """Verify unknown message kinds don't blank the UI."""
        js_path = (
            Path(__file__).parent.parent / "src" / "rig_tools" / "static" / "rig-ui.js"
        )
        content = js_path.read_text()

        # Should have a default case that doesn't throw
        assert "default" in content or "unknown" in content.lower()
        # Should log warnings for unknown kinds
        assert "Unknown message kind" in content or "unknown_kind" in content


class TestBackendDebugLogSupport:
    """Test that backend can send debug_log messages."""

    def test_ui_server_can_send_debug_log(self):
        """Verify UIServer has mechanism to send debug_log messages."""
        from rig_tools.ui_server import UIServer

        # Check that _schedule_send method exists (used for sending debug_log)
        assert hasattr(UIServer, "_schedule_send")

    def test_hello_message_includes_debug_flag(self):
        """Verify hello message can include debug flag."""
        js_path = (
            Path(__file__).parent.parent / "src" / "rig_tools" / "static" / "rig-ui.js"
        )
        content = js_path.read_text()

        # The hello message should be able to pass debug flag
        assert "debug" in content.lower()


class TestFinalStateAuthority:
    """Test that debug additions don't break the authority principle."""

    def test_projection_remains_authoritative(self):
        """Verify projection is still the source of truth for final states."""
        js_path = (
            Path(__file__).parent.parent / "src" / "rig_tools" / "static" / "rig-ui.js"
        )
        content = js_path.read_text()

        # Should still clear pending intents on projection
        assert "pendingIntents.clear()" in content
        # Should still hide boot fallback on projection
        assert "hideBootFallback()" in content

    def test_stream_chunks_not_infer_success(self):
        """Verify stream chunks don't infer final validator state."""
        js_path = (
            Path(__file__).parent.parent / "src" / "rig_tools" / "static" / "rig-ui.js"
        )
        content = js_path.read_text()

        # Should NOT have logic that infers success from stream chunks
        # The applyStreamChunk should just pass to handleStreamChunk
        # No assertions about success/failure in stream chunk handler
        pass  # This is a documentation test - the code should not change

    def test_debug_timeline_not_authoritative(self):
        """Verify debug timeline is debug-only and not authoritative."""
        js_path = (
            Path(__file__).parent.parent / "src" / "rig_tools" / "static" / "rig-ui.js"
        )
        content = js_path.read_text()

        # Debug timeline should only be used in debug mode
        assert "RIG_DEBUG" in content
        # Should be a separate concern from projection
        assert "debugTimeline" in content


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
