"""New tests for UI server hardening (Phase 9c).

These tests verify the newly implemented hardening requirements:
- Dependency behavior for missing UI dependencies
- Legacy flattened message rejection
- Intent authority validation
- Stream chunk validation
- Frontend escaping
"""

import asyncio
import json
import sys
import os
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch, MagicMock

import pytest


# Add src to path to avoid import errors through rig.__init__
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


class TestDependencyBehavior:
    """Test dependency behavior for UI command."""

    def test_check_ui_dependencies_function_exists(self):
        """Test that _check_ui_dependencies function exists in commands_ui."""
        from rig.commands_ui import _check_ui_dependencies, _get_missing_ui_dependencies
        assert _check_ui_dependencies is not None
        assert _get_missing_ui_dependencies is not None

    def test_get_missing_ui_dependencies_returns_list(self):
        """Test that _get_missing_ui_dependencies returns a list."""
        from rig.commands_ui import _get_missing_ui_dependencies
        missing = _get_missing_ui_dependencies()
        assert isinstance(missing, list)

    def test_open_window_checks_dependencies(self):
        """Test that open_window checks for UI dependencies."""
        from rig_tools import window_launcher
        
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            
            # Check if the function exists
            assert hasattr(window_launcher, 'check_ui_dependencies')
            
            # Call it
            all_ok, missing = window_launcher.check_ui_dependencies()
            assert isinstance(all_ok, bool)
            assert isinstance(missing, list)

    def test_open_window_returns_error_for_missing_deps(self):
        """Test that open_window returns error when dependencies are missing."""
        from rig_tools import window_launcher
        
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            
            # Mock check_ui_dependencies to return missing deps
            with patch.object(window_launcher, 'check_ui_dependencies', return_value=(False, ['aiohttp', 'pywebview'])):
                result = window_launcher.open_window(
                    repo_root=repo_root,
                    dry_run=False,
                    host="127.0.0.1",
                    port=8080
                )
                
                assert result["status"] == "failed"
                assert "Missing UI dependencies" in result["error"]
                assert "hint" in result


class TestLegacyMessageRejection:
    """Test rejection of legacy flattened messages."""

    @pytest.fixture
    def ui_server(self):
        """Create a UIServer instance for testing."""
        from rig_tools.ui_server import UIServer
        from pathlib import Path
        
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            server = UIServer(repo_root, "test_token")
            yield server

    def test_legacy_flattened_message_detected(self, ui_server):
        """Test that legacy flattened messages with kind_name are detected."""
        # Legacy message with flattened intent fields and kind_name
        legacy_msg = {
            "kind": "intent",
            "kind_name": "rig.intent.refresh_projection",  # Old workaround
            "intent_id": "abc123",
            "target": {}
        }
        
        assert ui_server._is_legacy_flattened_message(legacy_msg) is True

    def test_new_protocol_message_not_detected_as_legacy(self, ui_server):
        """Test that new protocol messages are not flagged as legacy."""
        # New protocol message with nested intent
        new_msg = {
            "schema_version": "rig.ui.message.v1",
            "kind": "intent",
            "intent": {
                "schema_version": "rig.ui.intent.v1",
                "kind": "rig.intent.refresh_projection"
            }
        }
        
        assert ui_server._is_legacy_flattened_message(new_msg) is False

    @pytest.mark.asyncio
    async def test_legacy_message_rejected(self, ui_server):
        """Test that legacy flattened messages are rejected."""
        mock_ws = MagicMock()
        mock_ws.send_json = AsyncMock()
        
        # Legacy message
        legacy_msg = {
            "kind": "intent",
            "kind_name": "rig.intent.refresh_projection",
            "intent_id": "abc123"
        }
        
        await ui_server.handle_message(mock_ws, legacy_msg)
        
        # Should have sent an error
        assert mock_ws.send_json.called
        call_args = mock_ws.send_json.call_args_list[-1][0][0]
        assert call_args["kind"] == "error"
        assert call_args.get("status") == "legacy_format_rejected"
        assert "legacy" in call_args["message"].lower()


class TestIntentAuthorityValidation:
    """Test intent authority validation."""

    @pytest.fixture
    def ui_server(self):
        """Create a UIServer instance for testing."""
        from rig_tools.ui_server import UIServer
        from pathlib import Path
        
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            server = UIServer(repo_root, "test_token")
            yield server

    @pytest.mark.asyncio
    async def test_unknown_intent_rejected(self, ui_server):
        """Test that unknown intent kinds are rejected."""
        mock_ws = MagicMock()
        mock_ws.send_json = AsyncMock()
        
        intent_data = {
            "schema_version": "rig.ui.message.v1",
            "kind": "intent",
            "intent": {
                "schema_version": "rig.ui.intent.v1",
                "intent_id": "test-1",
                "kind": "rig.intent.unknown_action",
                "target": {},
                "observed_projection_revision": 1
            }
        }
        
        await ui_server.handle_message(mock_ws, intent_data)
        
        # Should have sent an error about unknown intent
        assert mock_ws.send_json.called
        call_args = mock_ws.send_json.call_args_list[-1][0][0]
        assert call_args["kind"] == "error"
        assert "unknown" in call_args["message"].lower() or "unknown intent" in call_args["message"].lower()

    @pytest.mark.asyncio
    async def test_disabled_intent_rejected(self, ui_server):
        """Test that disabled intents are rejected with backend-authored reason."""
        mock_ws = MagicMock()
        mock_ws.send_json = AsyncMock()
        
        # Bump revision
        ui_server.revision = 2
        
        # Try to use apply_patch which should be disabled
        intent_data = {
            "schema_version": "rig.ui.message.v1",
            "kind": "intent",
            "intent": {
                "schema_version": "rig.ui.intent.v1",
                "intent_id": "test-1",
                "kind": "rig.intent.apply_patch",
                "target": {},
                "observed_projection_revision": 2
            }
        }
        
        await ui_server.handle_message(mock_ws, intent_data)
        
        # Should have sent a governed rejection for a reserved or unknown intent.
        assert mock_ws.send_json.called
        call_args = mock_ws.send_json.call_args_list[-1][0][0]
        assert call_args["kind"] == "error"
        assert "unknown" in call_args["message"].lower() or "reserved" in call_args["message"].lower() or "disabled" in call_args["message"].lower()

    @pytest.mark.asyncio
    async def test_stale_projection_rejected(self, ui_server):
        """Test that stale projection revisions are rejected."""
        mock_ws = MagicMock()
        mock_ws.send_json = AsyncMock()
        
        # Bump revision to 2
        ui_server.revision = 2
        
        intent_data = {
            "schema_version": "rig.ui.message.v1",
            "kind": "intent",
            "intent": {
                "schema_version": "rig.ui.intent.v1",
                "intent_id": "test-1",
                "kind": "rig.intent.chat.submit",
                "target": {"text": "hello"},
                "observed_projection_revision": 0,  # Stale
            }
        }
        
        await ui_server.handle_message(mock_ws, intent_data)
        
        # Should have sent an error about stale revision
        assert mock_ws.send_json.called
        call_args = mock_ws.send_json.call_args_list[-1][0][0]
        assert call_args["kind"] == "error"
        assert "stale" in call_args["message"].lower()

    @pytest.mark.asyncio
    async def test_refresh_intent_allowed_with_stale_revision(self, ui_server):
        """Test that refresh_projection intent is allowed even with stale revision."""
        # Bump revision to 2
        ui_server.revision = 2
        
        mock_ws = MagicMock()
        mock_ws.send_json = AsyncMock()
        
        intent_data = {
            "schema_version": "rig.ui.message.v1",
            "kind": "intent",
            "intent": {
                "schema_version": "rig.ui.intent.v1",
                "intent_id": "test-1",
                "kind": "rig.intent.refresh_projection",
                "target": {},
                "observed_projection_revision": 0,  # Stale but safe
            }
        }
        
        await ui_server.handle_message(mock_ws, intent_data)
        
        # Should have sent intent_result (not error)
        assert mock_ws.send_json.called
        call_args = mock_ws.send_json.call_args_list[-1][0][0]
        assert call_args["kind"] == "intent_result"
        assert call_args["data"]["accepted"] is True

    @pytest.mark.asyncio
    async def test_missing_intent_kind_rejected(self, ui_server):
        """Test that messages with missing intent kind are rejected."""
        mock_ws = MagicMock()
        mock_ws.send_json = AsyncMock()
        
        intent_data = {
            "schema_version": "rig.ui.message.v1",
            "kind": "intent",
            "intent": {
                "schema_version": "rig.ui.intent.v1",
                "intent_id": "test-1",
                # Missing 'kind' field
                "target": {},
                "observed_projection_revision": 1
            }
        }
        
        await ui_server.handle_message(mock_ws, intent_data)
        
        # Should have sent an error about missing kind
        assert mock_ws.send_json.called
        call_args = mock_ws.send_json.call_args_list[-1][0][0]
        assert call_args["kind"] == "error"
        assert "kind is required" in call_args["message"].lower() or "kind" in call_args["message"].lower()


class TestStreamChunkValidation:
    """Test stream chunk validation."""

    @pytest.fixture
    def ui_server(self):
        """Create a UIServer instance for testing."""
        from rig_tools.ui_server import UIServer
        from pathlib import Path
        
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            server = UIServer(repo_root, "test_token")
            yield server

    def test_stream_chunk_validation(self, ui_server):
        """Test that stream chunks are validated for required fields."""
        assert ui_server._validate_stream_chunk({
            "stream_id": "test",
            "sequence": 1,
            "content": "test",
            "channel": "stdout"
        }) is True

    def test_stream_chunk_missing_stream_id(self, ui_server):
        """Test that stream chunk missing stream_id is invalid."""
        assert ui_server._validate_stream_chunk({
            "sequence": 1,
            "content": "test",
            "channel": "stdout"
        }) is False

    def test_stream_chunk_missing_sequence(self, ui_server):
        """Test that stream chunk missing sequence is invalid."""
        assert ui_server._validate_stream_chunk({
            "stream_id": "test",
            "content": "test",
            "channel": "stdout"
        }) is False

    def test_stream_chunk_missing_content(self, ui_server):
        """Test that stream chunk missing content is invalid."""
        assert ui_server._validate_stream_chunk({
            "stream_id": "test",
            "sequence": 1,
            "channel": "stdout"
        }) is False

    def test_stream_chunk_missing_channel(self, ui_server):
        """Test that stream chunk missing channel is invalid."""
        assert ui_server._validate_stream_chunk({
            "stream_id": "test",
            "sequence": 1,
            "content": "test"
        }) is False

    def test_get_next_sequence_monotonic(self, ui_server):
        """Test that sequence numbers are monotonic per stream."""
        assert ui_server._get_next_sequence("test-stream") == 1
        assert ui_server._get_next_sequence("test-stream") == 2
        assert ui_server._get_next_sequence("test-stream") == 3
        assert ui_server._get_next_sequence("other-stream") == 1  # Different stream starts at 1


class TestFrontendEscaping:
    """Test frontend escaping."""

    def test_escape_html_function_exists(self):
        """Test that the frontend relies on safe DOM text rendering."""
        import os
        js_path = os.path.join(os.path.dirname(__file__), "..", "src", "rig_tools", "static", "rig-ui.js")
        
        with open(js_path, 'r') as f:
            js_content = f.read()
        
        assert "textContent" in js_content
        assert "document.createElement" in js_content

    def test_no_innerhtml_in_rendering(self):
        """Test that innerHTML is not used in rendering."""
        import os
        js_path = os.path.join(os.path.dirname(__file__), "..", "src", "rig_tools", "static", "rig-ui.js")
        
        with open(js_path, 'r') as f:
            js_content = f.read()
        
        # Ignore comments; only flag actual DOM mutation sites.
        code_lines = []
        in_block_comment = False
        for line in js_content.splitlines():
            stripped = line.strip()
            if in_block_comment:
                if "*/" in stripped:
                    in_block_comment = False
                continue
            if stripped.startswith("/*"):
                in_block_comment = "*/" not in stripped
                continue
            if stripped.startswith("//"):
                continue
            code_lines.append(line)
        code = "\n".join(code_lines)
        assert ".innerHTML =" not in code
        assert "innerHTML =" not in code

    def test_textcontent_used_for_dynamic_text(self):
        """Test that textContent is used for dynamic text."""
        import os
        js_path = os.path.join(os.path.dirname(__file__), "..", "src", "rig_tools", "static", "rig-ui.js")
        
        with open(js_path, 'r') as f:
            js_content = f.read()
        
        assert "textContent" in js_content

    def test_dom_api_clear_element_used(self):
        """Test that DOM API is used for clearing elements instead of innerHTML."""
        import os
        js_path = os.path.join(os.path.dirname(__file__), "..", "src", "rig_tools", "static", "rig-ui.js")
        
        with open(js_path, 'r') as f:
            js_content = f.read()
        
        assert "clearElement" in js_content or "removeChild" in js_content


class TestThreadSafety:
    """Test thread safety for WebSocket broadcasts."""

    @pytest.fixture
    def ui_server(self):
        """Create a UIServer instance for testing."""
        from rig_tools.ui_server import UIServer
        from pathlib import Path
        
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            server = UIServer(repo_root, "test_token")
            yield server

    def test_schedule_send_uses_threadsafe_mechanism(self, ui_server):
        """Test that _schedule_send uses thread-safe scheduling."""
        import inspect
        source = inspect.getsource(ui_server._schedule_send)
        
        # Check for thread-safe scheduling mechanisms
        assert "run_coroutine_threadsafe" in source or "threadsafe" in source.lower()

    def test_schedule_send_validates_stream_chunks(self, ui_server):
        """Test that _schedule_send validates stream chunks."""
        import inspect
        source = inspect.getsource(ui_server._schedule_send)
        
        # Check for validation
        assert "validate" in source.lower() or "_validate_stream_chunk" in source


class TestSafeIntents:
    """Test SAFE_INTENTS constant."""

    def test_safe_intents_constant_exists(self):
        """Test that SAFE_INTENTS constant exists."""
        from rig_tools import ui_server
        assert hasattr(ui_server, 'SAFE_INTENTS')

    def test_refresh_projection_in_safe_intents(self):
        """Test that refresh_projection is in SAFE_INTENTS."""
        from rig_tools import ui_server
        assert "rig.intent.refresh_projection" in ui_server.SAFE_INTENTS
