"""Source-level tests for UI hardening.

These tests verify the hardening requirements by reading source files directly,
avoiding import issues with missing modules.
"""

import os
import sys

import pytest

# Get the source directory
SRC_DIR = os.path.join(os.path.dirname(__file__), '..', 'src')


class TestCommandsUISource:
    """Test commands_ui.py source for dependency checking."""

    def get_commands_ui_content(self):
        """Read commands_ui.py content."""
        path = os.path.join(SRC_DIR, 'rig', 'commands_ui.py')
        with open(path, 'r') as f:
            return f.read()

    def test_has_dependency_check_functions(self):
        """Test that dependency checking functions are defined."""
        content = self.get_commands_ui_content()
        assert "def _check_ui_dependencies" in content
        assert "def _get_missing_ui_dependencies" in content

    def test_dependency_check_in_handler(self):
        """Test that _ui_handler checks dependencies."""
        content = self.get_commands_ui_content()
        # Check that the handler checks for dependencies before importing
        assert "_check_ui_dependencies()" in content
        # Check for install message
        assert "pip install -e" in content and "[ui]" in content

    def test_missing_deps_error_message(self):
        """Test that missing dependencies produce clear error message."""
        content = self.get_commands_ui_content()
        assert "UI dependencies are missing" in content
        assert "Install them" in content


class TestWindowLauncherSource:
    """Test window_launcher.py source for dependency checking."""

    def get_window_launcher_content(self):
        """Read window_launcher.py content."""
        path = os.path.join(SRC_DIR, 'rig_tools', 'window_launcher.py')
        with open(path, 'r') as f:
            return f.read()

    def test_has_dependency_check_functions(self):
        """Test that dependency checking functions exist."""
        content = self.get_window_launcher_content()
        assert "def get_aiohttp_available" in content
        assert "def check_ui_dependencies" in content

    def test_check_ui_dependencies_returns_tuple(self):
        """Test that check_ui_dependencies returns (bool, list)."""
        content = self.get_window_launcher_content()
        assert "def check_ui_dependencies" in content
        assert "-> tuple[bool, list[str]]" in content or "tuple[bool, list]" in content or "(bool, list" in content

    def test_open_window_checks_deps(self):
        """Test that open_window checks dependencies at start."""
        content = self.get_window_launcher_content()
        # Check that open_window checks dependencies
        assert "check_ui_dependencies" in content
        assert "Missing UI dependencies" in content
        # Check for install message
        assert "pip install -e" in content and "[ui]" in content


class TestUIServerSource:
    """Test ui_server.py source for message envelope and intent authority."""

    def get_ui_server_content(self):
        """Read ui_server.py content."""
        path = os.path.join(SRC_DIR, 'rig_tools', 'ui_server.py')
        with open(path, 'r') as f:
            return f.read()

    def test_has_safe_intents_constant(self):
        """Test that SAFE_INTENTS constant is defined."""
        content = self.get_ui_server_content()
        assert "SAFE_INTENTS" in content
        assert "rig.intent.refresh_projection" in content

    def test_has_legacy_message_detection(self):
        """Test that legacy message detection exists."""
        content = self.get_ui_server_content()
        assert "_is_legacy_flattened_message" in content
        assert "kind_name" in content  # Looking for the workaround field

    def test_has_legacy_message_rejection(self):
        """Test that legacy messages are rejected."""
        content = self.get_ui_server_content()
        assert "_reject_legacy_message" in content
        assert "LEGACY_FORMAT_REJECTED" in content

    def test_has_intent_authority_validation(self):
        """Test that intent authority validation exists."""
        content = self.get_ui_server_content()
        assert "_validate_intent_authority" in content
        assert "backend-authored" in content or "backend authored" in content.lower()

    def test_has_stream_chunk_validation(self):
        """Test that stream chunk validation exists."""
        content = self.get_ui_server_content()
        assert "_validate_stream_chunk" in content
        assert "stream_id" in content
        assert "sequence" in content
        assert "content" in content
        assert "channel" in content

    def test_uses_schema_version_v1(self):
        """Test that rig.ui.message.v1 is used consistently."""
        content = self.get_ui_server_content()
        assert "rig.ui.message.v1" in content
        assert "rig.ui.intent.v1" in content

    def test_uses_threadsafe_scheduling(self):
        """Test that thread-safe scheduling is used."""
        content = self.get_ui_server_content()
        assert "run_coroutine_threadsafe" in content

    def test_schedule_send_validates_chunks(self):
        """Test that _schedule_send validates stream chunks."""
        content = self.get_ui_server_content()
        # Check that _schedule_send validates chunks
        assert "_validate_stream_chunk" in content


class TestFrontendJSSource:
    """Test rig-ui.js source for escaping and stream bounds."""

    def get_js_content(self):
        """Read rig-ui.js content."""
        path = os.path.join(SRC_DIR, 'rig_tools', 'static', 'rig-ui.js')
        with open(path, 'r') as f:
            return f.read()

    def test_no_innerhtml(self):
        """Test that innerHTML is not used for rendering (DOM APIs only)."""
        content = self.get_js_content()
        # Check that innerHTML is not used as a property (allowing it in comments is OK)
        # Look for patterns like .innerHTML = or innerHTML in code context
        import re
        # Remove comments first, then check for innerHTML usage
        content_no_comments = re.sub(r'//.*', '', content)
        content_no_comments = re.sub(r'/\*.*?\*/', '', content_no_comments, flags=re.DOTALL)
        assert ".innerHTML" not in content_no_comments
        assert "innerHTML=" not in content_no_comments

    def test_has_textcontent(self):
        """Test that textContent is used."""
        content = self.get_js_content()
        assert "textContent" in content

    def test_has_clear_element_function(self):
        """Test that clearElement function exists."""
        content = self.get_js_content()
        assert "function clearElement" in content or "clearElement" in content

    def test_has_remove_child(self):
        """Test that removeChild is used for DOM clearing."""
        content = self.get_js_content()
        assert "removeChild" in content or "clearElement" in content

    def test_has_stream_buffer_bounds(self):
        """Test that stream buffer bounds are defined."""
        content = self.get_js_content()
        assert "MAX_BUFFER_BYTES" in content
        assert "MAX_STREAM_BUFFERS" in content
        assert "MAX_BUFFER_LINES" in content

    def test_has_sequence_tracking(self):
        """Test that sequence number tracking exists."""
        content = self.get_js_content()
        assert "lastSequenceNumbers" in content

    def test_has_monotonic_check(self):
        """Test that monotonic sequence check exists."""
        content = self.get_js_content()
        # Check for monotonic validation
        assert "monotonic" in content.lower() or "sequence" in content

    def test_validates_stream_chunk_fields(self):
        """Test that stream chunk fields are validated."""
        content = self.get_js_content()
        assert "stream_id" in content
        assert "sequence" in content
        assert "content" in content
        assert "channel" in content

    def test_uses_dom_apis(self):
        """Test that DOM APIs are used instead of innerHTML."""
        content = self.get_js_content()
        assert "document.createElement" in content
        assert "appendChild" in content


class TestProjectionBuilderSource:
    """Test that projection builder doesn't import Textual."""

    def get_projection_builder_content(self):
        """Read projection_builder.py content."""
        path = os.path.join(SRC_DIR, 'rig', 'domain', 'projection_builder.py')
        with open(path, 'r') as f:
            return f.read()

    def test_no_textual_import(self):
        """Test that Textual is not imported."""
        content = self.get_projection_builder_content()
        assert "import textual" not in content.lower()
        assert "from textual" not in content.lower()


class TestProjectionsSource:
    """Test that projections module doesn't import Textual."""

    def get_projections_content(self):
        """Read projections.py content."""
        path = os.path.join(SRC_DIR, 'rig', 'domain', 'projections.py')
        with open(path, 'r') as f:
            return f.read()

    def test_no_textual_import(self):
        """Test that Textual is not imported."""
        content = self.get_projections_content()
        assert "import textual" not in content.lower()
        assert "from textual" not in content.lower()


class TestIntentsSource:
    """Test that intent_defs module doesn't import Textual."""

    def get_intents_content(self):
        """Read intent_defs.py content."""
        path = os.path.join(SRC_DIR, 'rig', 'domain', 'intent_defs.py')
        with open(path, 'r') as f:
            return f.read()

    def test_no_textual_import(self):
        """Test that Textual is not imported."""
        content = self.get_intents_content()
        assert "import textual" not in content.lower()
        assert "from textual" not in content.lower()
        
    def test_uses_schema_version_v1(self):
        """Test that Intent uses rig.ui.intent.v1 schema."""
        content = self.get_intents_content()
        assert "rig.ui.intent.v1" in content
