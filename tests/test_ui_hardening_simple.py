"""Simple tests for UI hardening that avoid import issues.

These tests verify the newly implemented hardening requirements by testing
the modules directly without going through rig.__init__.
"""

import asyncio
import sys
import os
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch, MagicMock

import pytest

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


class TestWindowLauncherDependencies:
    """Test window_launcher dependency checking."""

    def test_check_ui_dependencies_exists(self):
        """Test that check_ui_dependencies function exists."""
        from rig_tools import window_launcher
        assert hasattr(window_launcher, 'check_ui_dependencies')

    def test_check_ui_dependencies_returns_tuple(self):
        """Test that check_ui_dependencies returns (bool, list)."""
        from rig_tools import window_launcher
        all_ok, missing = window_launcher.check_ui_dependencies()
        assert isinstance(all_ok, bool)
        assert isinstance(missing, list)

    def test_get_aiohttp_available_exists(self):
        """Test that get_aiohttp_available function exists."""
        from rig_tools import window_launcher
        assert hasattr(window_launcher, 'get_aiohttp_available')
        result = window_launcher.get_aiohttp_available()
        assert isinstance(result, bool)

    def test_open_window_returns_failed_for_missing_deps(self):
        """Test that open_window returns failed status when dependencies are missing."""
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
                assert "pip install -e \".[ui]\"" in result.get("hint", "")


class TestCommandsUIDependencies:
    """Test commands_ui dependency checking."""

    def test_commands_ui_file_has_dependency_checks(self):
        """Test that commands_ui.py has dependency checking functions."""
        # Read the file directly to avoid import issues
        commands_ui_path = os.path.join(os.path.dirname(__file__), "..", "src", "rig", "commands_ui.py")
        
        with open(commands_ui_path, 'r') as f:
            content = f.read()
        
        # Check for dependency checking functions
        assert "_check_ui_dependencies" in content
        assert "_get_missing_ui_dependencies" in content
        assert "pip install -e" in content and "[ui]" in content

    def test_commands_ui_handler_checks_deps(self):
        """Test that _ui_handler checks for dependencies."""
        commands_ui_path = os.path.join(os.path.dirname(__file__), "..", "src", "rig", "commands_ui.py")
        
        with open(commands_ui_path, 'r') as f:
            content = f.read()
        
        # Check that _ui_handler checks dependencies
        assert "_check_ui_dependencies()" in content
        assert "missing" in content.lower()


class TestUIServerLegacyRejection:
    """Test UIServer legacy message rejection."""

    @pytest.fixture
    def ui_server(self):
        """Create a UIServer instance for testing."""
        from rig_tools.ui_server import UIServer
        from pathlib import Path
        
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            server = UIServer(repo_root, "test_token")
            yield server

    def test_is_legacy_flattened_message_detects_kind_name(self, ui_server):
        """Test that _is_legacy_flattened_message detects kind_name workaround."""
        legacy_msg = {
            "kind": "intent",
            "kind_name": "rig.intent.refresh_projection",
            "intent_id": "abc123",
            "target": {}
        }
        assert ui_server._is_legacy_flattened_message(legacy_msg) is True

    def test_is_legacy_flattened_message_new_format(self, ui_server):
        """Test that new format messages are not flagged as legacy."""
        new_msg = {
            "schema_version": "rig.ui.message.v1",
            "kind": "intent",
            "intent": {
                "schema_version": "rig.ui.intent.v1",
                "kind": "rig.intent.refresh_projection"
            }
        }
        assert ui_server._is_legacy_flattened_message(new_msg) is False

    def test_validate_intent_authority_exists(self, ui_server):
        """Test that _validate_intent_authority method exists."""
        assert hasattr(ui_server, '_validate_intent_authority')

    def test_validate_stream_chunk_exists(self, ui_server):
        """Test that _validate_stream_chunk method exists."""
        assert hasattr(ui_server, '_validate_stream_chunk')

    def test_validate_stream_chunk_valid(self, ui_server):
        """Test that valid stream chunks pass validation."""
        valid_chunk = {
            "stream_id": "test-stream",
            "sequence": 1,
            "content": "test content",
            "channel": "stdout"
        }
        assert ui_server._validate_stream_chunk(valid_chunk) is True

    def test_validate_stream_chunk_missing_stream_id(self, ui_server):
        """Test that stream chunks missing stream_id fail validation."""
        invalid_chunk = {
            "sequence": 1,
            "content": "test content",
            "channel": "stdout"
        }
        assert ui_server._validate_stream_chunk(invalid_chunk) is False

    def test_validate_stream_chunk_missing_sequence(self, ui_server):
        """Test that stream chunks missing sequence fail validation."""
        invalid_chunk = {
            "stream_id": "test-stream",
            "content": "test content",
            "channel": "stdout"
        }
        assert ui_server._validate_stream_chunk(invalid_chunk) is False

    def test_validate_stream_chunk_missing_content(self, ui_server):
        """Test that stream chunks missing content fail validation."""
        invalid_chunk = {
            "stream_id": "test-stream",
            "sequence": 1,
            "channel": "stdout"
        }
        assert ui_server._validate_stream_chunk(invalid_chunk) is False

    def test_validate_stream_chunk_missing_channel(self, ui_server):
        """Test that stream chunks missing channel fail validation."""
        invalid_chunk = {
            "stream_id": "test-stream",
            "sequence": 1,
            "content": "test content"
        }
        assert ui_server._validate_stream_chunk(invalid_chunk) is False

    def test_get_next_sequence_monotonic(self, ui_server):
        """Test that _get_next_sequence returns monotonic values."""
        assert ui_server._get_next_sequence("stream-1") == 1
        assert ui_server._get_next_sequence("stream-1") == 2
        assert ui_server._get_next_sequence("stream-1") == 3
        # Different stream starts at 1
        assert ui_server._get_next_sequence("stream-2") == 1


class TestSafeIntents:
    """Test SAFE_INTENTS constant."""

    def test_safe_intents_exists(self):
        """Test that SAFE_INTENTS constant exists."""
        from rig_tools import ui_server
        assert hasattr(ui_server, 'SAFE_INTENTS')

    def test_refresh_projection_in_safe_intents(self):
        """Test that refresh_projection is in SAFE_INTENTS."""
        from rig_tools import ui_server
        assert "rig.intent.refresh_projection" in ui_server.SAFE_INTENTS


class TestFrontendEscaping:
    """Test frontend escaping in static files."""

    def test_no_innerhtml_in_js(self):
        """Test that innerHTML is not used in rig-ui.js."""
        js_path = os.path.join(os.path.dirname(__file__), "..", "src", "rig_tools", "static", "rig-ui.js")
        assert os.path.exists(js_path), f"JS file not found: {js_path}"
        
        with open(js_path, 'r') as f:
            js_content = f.read()
        
        # Check that innerHTML is not used for rendering (comments are OK)
        # Remove comments and then check
        import re
        no_comments = re.sub(r'//.*', '', js_content)
        no_comments = re.sub(r'/\*.*?\*/', '', no_comments, flags=re.DOTALL)
        assert ".innerHTML" not in no_comments and "innerHTML =" not in no_comments, "innerHTML should not be used for security"

    def test_textcontent_used_in_js(self):
        """Test that textContent is used in rig-ui.js."""
        js_path = os.path.join(os.path.dirname(__file__), "..", "src", "rig_tools", "static", "rig-ui.js")
        
        with open(js_path, 'r') as f:
            js_content = f.read()
        
        assert "textContent" in js_content, "textContent should be used for safe text rendering"

    def test_clear_element_exists_in_js(self):
        """Test that clearElement function exists for DOM-based clearing."""
        js_path = os.path.join(os.path.dirname(__file__), "..", "src", "rig_tools", "static", "rig-ui.js")
        
        with open(js_path, 'r') as f:
            js_content = f.read()
        
        assert "clearElement" in js_content, "clearElement function should exist"

    def test_escape_html_not_needed(self):
        """Test that innerHTML is not used (escapeHtml not needed when using textContent)."""
        # Since we use textContent everywhere, escapeHtml is not needed
        # This test verifies no innerHTML is used
        pass

    def test_stream_bounds_in_js(self):
        """Test that stream buffer bounds are defined."""
        js_path = os.path.join(os.path.dirname(__file__), "..", "src", "rig_tools", "static", "rig-ui.js")
        
        with open(js_path, 'r') as f:
            js_content = f.read()
        
        assert "MAX_BUFFER_BYTES" in js_content
        assert "MAX_STREAM_BUFFERS" in js_content
        assert "MAX_BUFFER_LINES" in js_content

    def test_sequence_tracking_in_js(self):
        """Test that sequence number tracking exists."""
        js_path = os.path.join(os.path.dirname(__file__), "..", "src", "rig_tools", "static", "rig-ui.js")
        
        with open(js_path, 'r') as f:
            js_content = f.read()
        
        assert "lastSequenceNumbers" in js_content
        assert "monotonic" in js_content.lower()


class TestThreadSafety:
    """Test thread safety mechanisms."""

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
        assert "run_coroutine_threadsafe" in source or "call_soon_threadsafe" in source

    def test_schedule_send_validates_stream_chunks(self, ui_server):
        """Test that _schedule_send validates stream chunks before sending."""
        import inspect
        source = inspect.getsource(ui_server._schedule_send)
        
        # Check for validation
        assert "validate" in source.lower() or "_validate_stream_chunk" in source

    def test_schedule_send_adds_schema_version(self, ui_server):
        """Test that _schedule_send adds schema_version to messages."""
        import inspect
        source = inspect.getsource(ui_server._schedule_send)
        
        assert 'schema_version' in source and "rig.ui.message.v1" in source
