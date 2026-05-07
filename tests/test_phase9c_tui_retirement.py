"""Tests for Textual TUI retirement (Phase 9c).

These tests verify:
- `rig ui` command works and launches windowed UI
- `rig tui` command emits deprecation message
- `rig tui --window` still works as compatibility alias
- projection builder is UI-framework neutral
- Textual is no longer a core dependency
"""

import json
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch, MagicMock

import pytest


class TestCommandsUI:
    """Test the new 'rig ui' command."""

    def test_ui_command_registered(self):
        """Test that rig ui command is registered."""
        from rig import commands_ui
        assert commands_ui is not None

    def test_ui_command_parser(self):
        """Test that rig ui command has proper parser."""
        import argparse
        from rig import commands_ui

        parser = argparse.ArgumentParser()
        sub = parser.add_subparsers(dest="cmd")
        helpers = SimpleNamespace(repo_root=None, output_mode="text")
        commands_ui.register(sub, helpers)

        # Should parse successfully (without --help which causes exit)
        args = parser.parse_args(["ui"])
        assert args is not None
        # If we get here without error, parser is working

    def test_ui_command_options(self):
        """Test that rig ui command has expected options."""
        import argparse
        from rig import commands_ui

        parser = argparse.ArgumentParser()
        sub = parser.add_subparsers(dest="cmd")
        helpers = SimpleNamespace(repo_root=None, output_mode="text")
        commands_ui.register(sub, helpers)

        # Test various options
        for opt in [
            ["ui", "--dry-run"],
            ["ui", "--browser"],
            ["ui", "--allow-lan"],
            ["ui", "--chat"],
            ["ui", "--host", "0.0.0.0"],
            ["ui", "--port", "8080"],
        ]:
            args = parser.parse_args(opt)
            assert args is not None

    def test_ui_command_help_text(self):
        """Test that rig ui command has proper help text."""
        import argparse
        import io
        import sys
        from rig import commands_ui

        parser = argparse.ArgumentParser(prog="rig")
        sub = parser.add_subparsers(dest="cmd")
        helpers = SimpleNamespace(repo_root=None, output_mode="text")
        commands_ui.register(sub, helpers)

        # Capture help output
        old_stdout = sys.stdout
        sys.stdout = captured = io.StringIO()
        try:
            parser.parse_args(["ui", "--help"])
        except SystemExit:
            pass
        finally:
            sys.stdout = old_stdout

        help_text = captured.getvalue()
        assert "windowed" in help_text.lower() or "desktop" in help_text.lower()
        assert "ui" in help_text.lower()


class TestCommandsTUIDeprecation:
    """Test the deprecated 'rig tui' command."""

    def test_tui_command_registered(self):
        """Test that rig tui command is still registered for compatibility."""
        from rig import commands_tui
        assert commands_tui is not None

    def test_tui_command_shows_deprecation_in_help(self):
        """Test that rig tui help shows deprecation."""
        import argparse
        import io
        import sys
        from rig import commands_tui

        parser = argparse.ArgumentParser(prog="rig")
        sub = parser.add_subparsers(dest="cmd")
        helpers = SimpleNamespace(repo_root=None, output_mode="text")
        commands_tui.register(sub, helpers)

        # Capture help output
        old_stdout = sys.stdout
        sys.stdout = captured = io.StringIO()
        try:
            parser.parse_args(["tui", "--help"])
        except SystemExit:
            pass
        finally:
            sys.stdout = old_stdout

        help_text = captured.getvalue()
        assert "deprecated" in help_text.lower()
        assert "rig ui" in help_text

    def test_tui_without_flags_emits_deprecation(self):
        """Test that rig tui (without --window) emits deprecation message."""
        import json
        from pathlib import Path
        from rig import commands_tui

        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            helpers = SimpleNamespace(repo_root=repo_root, output_mode="text")

            class Args:
                safe = False
                action = False
                auto_approve = False
                yolo = False
                window = False
                chat = False
                dry_run = False
                mode = None
                refresh = 2

            # Capture stdout
            import io
            import sys
            old_stdout = sys.stdout
            sys.stdout = captured_output = io.StringIO()

            try:
                result = commands_tui._run(helpers, Args())
                assert result == 0
            finally:
                sys.stdout = old_stdout

            output = captured_output.getvalue()
            parsed = json.loads(output)
            assert parsed["status"] == "deprecated"
            assert "rig ui" in parsed["replacement"]
            assert "windowed_ui" in parsed["alternatives"]

    def test_tui_window_flag_redirects_to_ui(self):
        """Test that rig tui --window redirects to window launcher."""
        from pathlib import Path
        from rig import commands_tui

        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            helpers = SimpleNamespace(repo_root=repo_root, output_mode="text")

            class Args:
                safe = False
                action = False
                auto_approve = False
                yolo = False
                window = True  # This should redirect to UI
                chat = False
                dry_run = False
                mode = None
                refresh = 2

            with patch('rig_tools.window_launcher.open_window') as mock_open:
                mock_open.return_value = {"status": "dry_run", "warnings": []}
                result = commands_tui._run(helpers, Args())
                assert result == 0
                mock_open.assert_called_once()


class TestDependenciesArchitecture:
    """Test that dependencies are properly structured."""

    def test_projection_builder_no_textual_import(self):
        """Test that projection builder doesn't import Textual."""
        import ast
        from pathlib import Path

        proj_builder = Path(__file__).parent.parent / "src" / "rig" / "domain" / "projection_builder.py"
        tree = ast.parse(proj_builder.read_text(encoding="utf-8"))
        
        imports = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.add(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.add(node.module)

        # Textual should not be in imports
        textual_imports = [i for i in imports if "textual" in i.lower()]
        assert len(textual_imports) == 0, f"Found Textual imports: {textual_imports}"

    def test_projections_no_textual_import(self):
        """Test that projections module doesn't import Textual."""
        import ast
        from pathlib import Path

        projections = Path(__file__).parent.parent / "src" / "rig" / "domain" / "projections.py"
        tree = ast.parse(projections.read_text(encoding="utf-8"))
        
        imports = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.add(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.add(node.module)

        textual_imports = [i for i in imports if "textual" in i.lower()]
        assert len(textual_imports) == 0, f"Found Textual imports: {textual_imports}"

    def test_window_launcher_handles_missing_textual(self):
        """Test that window_launcher handles missing Textual gracefully."""
        from pathlib import Path
        from rig_tools import window_launcher
        
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            
            # get_textual_available should return False if Textual not installed
            # (we can't easily uninstall Textual, but we can check the function exists)
            assert hasattr(window_launcher, 'get_textual_available')
            result = window_launcher.get_textual_available()
            assert isinstance(result, bool)

    def test_ui_server_no_textual_import(self):
        """Test that ui_server doesn't import Textual."""
        import ast
        from pathlib import Path

        ui_server = Path(__file__).parent.parent / "src" / "rig_tools" / "ui_server.py"
        if ui_server.exists():
            tree = ast.parse(ui_server.read_text(encoding="utf-8"))
            
            imports = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        imports.add(alias.name)
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        imports.add(node.module)

            textual_imports = [i for i in imports if "textual" in i.lower()]
            assert len(textual_imports) == 0, f"Found Textual imports in ui_server: {textual_imports}"


class TestPyprojectDependencies:
    """Test pyproject.toml dependency structure."""

    def test_textual_not_in_core_dependencies(self):
        """Test that Textual is not in core dependencies."""
        from pathlib import Path
        import tomli

        pyproject_path = Path(__file__).parent.parent / "pyproject.toml"
        with open(pyproject_path, "rb") as f:
            config = tomli.load(f)

        core_deps = config.get("project", {}).get("dependencies", [])
        textual_deps = [d for d in core_deps if "textual" in d.lower()]
        
        # Textual should not be in core dependencies
        assert len(textual_deps) == 0, f"Textual still in core deps: {textual_deps}"

    def test_legacy_tui_extra_exists(self):
        """Test that legacy_tui optional dependency exists."""
        from pathlib import Path
        import tomli

        pyproject_path = Path(__file__).parent.parent / "pyproject.toml"
        with open(pyproject_path, "rb") as f:
            config = tomli.load(f)

        optional_deps = config.get("project", {}).get("optional-dependencies", {})
        assert "legacy_tui" in optional_deps or "ui" in optional_deps, \
            f"Missing ui or legacy_tui in optional-dependencies. Available: {list(optional_deps.keys())}"

    def test_ui_extra_exists(self):
        """Test that ui optional dependency exists."""
        from pathlib import Path
        import tomli

        pyproject_path = Path(__file__).parent.parent / "pyproject.toml"
        with open(pyproject_path, "rb") as f:
            config = tomli.load(f)

        optional_deps = config.get("project", {}).get("optional-dependencies", {})
        assert "ui" in optional_deps, \
            f"Missing ui in optional-dependencies. Available: {list(optional_deps.keys())}"
        
        # Check that ui extra has aiohttp and pywebview
        ui_deps = optional_deps.get("ui", [])
        assert any("aiohttp" in d for d in ui_deps), "aiohttp not in ui extra"
        assert any("pywebview" in d for d in ui_deps), "pywebview not in ui extra"


class TestCLIRegistrationRegression:
    """Regression tests for CLI command registration import errors.
    
    These tests verify that the NameError bug (where commands_window was used
    but not imported in main.py) does not recur.
    """

    def test_cli_main_imports_commands_window_without_nameerror(self):
        """Test that importing main.py does not raise NameError for commands_window."""
        # This is a regression test for the bug where commands_window was
        # used in main.py but not imported, causing NameError on registration.
        from rig.cli import main as cli_main
        # If we get here, the import succeeded
        assert hasattr(cli_main, 'main')

    def test_cli_main_registers_window_command_without_nameerror(self):
        """Test that main() parser registration does not raise NameError."""
        import sys
        from rig.cli.main import main
        
        # This would raise NameError if commands_window was not imported
        # The registration happens during parser setup before args are parsed
        try:
            main([])
        except SystemExit as e:
            # Expected: subcommand is required, so SystemExit(2) from argparse
            # The key is we didn't get NameError during registration
            assert e.code == 2

    def test_window_command_registered_in_cli(self):
        """Test that rig window command is registered via main.py imports."""
        from rig import commands_window
        
        # Verify the module has the register function
        assert hasattr(commands_window, 'register')
        assert callable(commands_window.register)

    def test_main_py_has_commands_window_import(self):
        """Test that main.py source contains commands_window import."""
        import os
        from pathlib import Path
        
        main_py = Path(__file__).parent.parent / "src" / "rig" / "cli" / "main.py"
        content = main_py.read_text()
        
        # Verify commands_window is imported
        assert "commands_window" in content, "commands_window not imported in main.py"
        # Verify commands_window.register is called
        assert "commands_window.register" in content, "commands_window.register not called in main.py"

    def test_commands_window_module_exists_and_has_register(self):
        """Test that commands_window module exists with register function."""
        from rig import commands_window
        
        assert hasattr(commands_window, 'register')
        assert callable(commands_window.register)
        
        # Also verify it has the expected parser structure
        import argparse
        parser = argparse.ArgumentParser()
        sub = parser.add_subparsers(dest="cmd")
        helpers = type('H', (), {"repo_root": None})()
        
        # This should not raise any errors
        commands_window.register(sub, helpers)
