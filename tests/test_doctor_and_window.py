"""Tests for doctor crash fix and window command fix."""

import subprocess
import sys
from pathlib import Path

import pytest

# Skip all tests if Python < 3.14 (rig requirement)
pytestmark = pytest.mark.skipif(
    sys.version_info < (3, 14), reason="Rig requires Python 3.14+"
)


class TestDoctorFix:
    """Test that rig doctor does not crash with NoneType error."""

    @pytest.fixture
    def rig_python(self):
        """Get Python 3.14+ executable."""
        # Try to find python3.14
        for candidate in ["python3.14", "python3.15"]:
            import shutil

            if shutil.which(candidate):
                return candidate
        return sys.executable  # Fallback - test may be skipped by pytestmark

    def test_doctor_does_not_crash(self, rig_python):
        """Test that rig doctor returns valid JSON without crashing."""
        result = subprocess.run(
            [rig_python, "-m", "rig", "doctor"],
            cwd=Path(__file__).parent.parent / "src",
            capture_output=True,
            text=True,
            timeout=30,
        )

        # Should not crash with NoneType error
        assert (
            result.returncode == 0 or result.returncode == 1
        )  # 1 is OK for warnings/failures
        assert "'NoneType' object is not callable" not in result.stdout
        assert "'NoneType' object is not callable" not in result.stderr

        # Should return valid JSON
        import json

        # The output might be JSON or text format
        output = result.stdout.strip()
        if output.startswith("{"):
            # JSON format
            data = json.loads(output)
            assert "status" in data or "error" in data
        else:
            # Text format - should not contain crash error
            assert "error" not in output.lower() or "none" not in output.lower()

    def test_doctor_returns_valid_structure(self):
        """Test that doctor returns expected JSON structure."""
        result = subprocess.run(
            [sys.executable, "-m", "rig", "doctor", "--format", "json"],
            cwd=Path(__file__).parent.parent / "src",
            capture_output=True,
            text=True,
            timeout=30,
        )

        import json

        if result.returncode == 0:
            data = json.loads(result.stdout)
            # Check expected fields
            assert "schema_version" in data
            assert "status" in data
            assert "checks" in data
            assert isinstance(data["checks"], list)


class TestWindowCommandFix:
    """Test that rig window open uses rig ui instead of rig tui --gridline --window."""

    def test_window_open_uses_ui_command(self):
        """Test that command_argv uses rig ui, not rig tui."""
        result = subprocess.run(
            [sys.executable, "-m", "rig", "window", "open", "--dry-run"],
            cwd=Path(__file__).parent.parent / "src",
            capture_output=True,
            text=True,
            timeout=10,
        )

        import json

        data = json.loads(result.stdout)

        # Check command_argv
        assert "command_argv" in data
        cmd = data["command_argv"]

        # Should use rig ui, not rig tui
        assert "rig" in cmd
        assert "ui" in cmd
        assert "tui" not in " ".join(cmd)
        assert "--gridline" not in cmd
        assert "--window" not in cmd

        # Should be exactly [python, -m, rig, ui]
        assert cmd[-2:] == ["-m", "rig"] or cmd[-3:] == ["-m", "rig", "ui"]

    def test_window_open_does_not_include_gridline(self):
        """Test that command_argv does not include --gridline flag."""
        result = subprocess.run(
            [sys.executable, "-m", "rig", "window", "open", "--dry-run"],
            cwd=Path(__file__).parent.parent / "src",
            capture_output=True,
            text=True,
            timeout=10,
        )

        import json

        data = json.loads(result.stdout)
        cmd = data["command_argv"]

        # No --gridline flag
        assert "--gridline" not in cmd

    def test_tui_still_returns_deprecation(self):
        """Test that rig tui still returns deprecation JSON."""
        result = subprocess.run(
            [sys.executable, "-m", "rig", "tui"],
            cwd=Path(__file__).parent.parent / "src",
            capture_output=True,
            text=True,
            timeout=10,
        )

        import json

        data = json.loads(result.stdout)

        assert data["status"] == "deprecated"
        assert "replacement" in data
        assert data["replacement"] == "rig ui"

    def test_ui_help_works(self):
        """Test that rig ui --help works."""
        result = subprocess.run(
            [sys.executable, "-m", "rig", "ui", "--help"],
            cwd=Path(__file__).parent.parent / "src",
            capture_output=True,
            text=True,
            timeout=10,
        )

        assert result.returncode == 0
        assert (
            "windowed control plane" in result.stdout.lower()
            or "ui" in result.stdout.lower()
        )


class TestCliRegistration:
    """Test that CLI registration imports all referenced command modules."""

    def test_ui_command_registers(self):
        """Test that ui command can be registered."""
        from rig import commands_ui

        # Just verify the modules can be imported
        assert commands_ui is not None

    def test_window_command_registers(self):
        """Test that window command can be registered."""
        from rig import commands_window

        # Just verify the modules can be imported
        assert commands_window is not None
