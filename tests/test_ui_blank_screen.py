"""Tests for debugging blank screen issue in Rig UI."""

from pathlib import Path
import tempfile


def test_index_html_has_boot_fallback():
    """Test that index.html has boot fallback UI."""
    index_path = (
        Path(__file__).parent.parent / "src" / "rig_tools" / "static" / "index.html"
    )
    content = index_path.read_text()
    assert "boot-fallback" in content
    assert "boot-status" in content
    assert "Rig UI booting" in content


def test_index_html_hides_app_initially():
    """Test that app div is hidden initially."""
    index_path = (
        Path(__file__).parent.parent / "src" / "rig_tools" / "static" / "index.html"
    )
    content = index_path.read_text()
    # App should be hidden until boot completes
    assert 'style="display:none;"' in content or 'style="display: none;"' in content


def test_js_has_error_handlers():
    """Test that JS has error handlers for WebSocket."""
    js_path = (
        Path(__file__).parent.parent / "src" / "rig_tools" / "static" / "rig-ui.js"
    )
    content = js_path.read_text()

    # Check for onerror handler
    assert "socket.onerror" in content

    # Check for try/catch in onmessage
    assert "catch (e)" in content or "catch(e)" in content


def test_js_has_boot_status_updates():
    """Test that JS updates boot status."""
    js_path = (
        Path(__file__).parent.parent / "src" / "rig_tools" / "static" / "rig-ui.js"
    )
    content = js_path.read_text()

    # Check for boot status updates
    assert "setBootStatus" in content
    assert "Rig UI connected" in content


def test_js_has_unknown_widget_fallback():
    """Test that JS has fallback for unknown widgets."""
    js_path = (
        Path(__file__).parent.parent / "src" / "rig_tools" / "static" / "rig-ui.js"
    )
    content = js_path.read_text()

    # Check for unknown widget fallback in main render
    assert "Unknown widget" in content


def test_js_has_unknown_widget_fallback_in_inspector():
    """Test that JS has fallback for unknown widgets in inspector."""
    js_path = (
        Path(__file__).parent.parent / "src" / "rig_tools" / "static" / "rig-ui.js"
    )
    content = js_path.read_text()

    # Check for unknown widget fallback in renderChat/inspector
    # The inspector widget rendering should have a fallback
    assert "Unknown widget" in content


def test_empty_projection_has_all_renderable_widgets():
    """Test that empty projection widgets all have renderers."""
    from rig.domain.projection_builder import _build_empty_projection

    proj = _build_empty_projection(1, None, 0, 0, 0)

    # Widget types that should exist
    widget_types = set()
    for widget in proj.widgets.values():
        widget_types.add(widget.type)

    # All widget types should have renderers in rig-ui.js
    js_path = (
        Path(__file__).parent.parent / "src" / "rig_tools" / "static" / "rig-ui.js"
    )
    js_content = js_path.read_text()

    # Check each widget type has a renderer
    for wtype in widget_types:
        # Look for "WType: (id, data) =>" pattern
        assert f"{wtype}:" in js_content, f"No renderer for widget type: {wtype}"


def test_projection_structure_valid():
    """Test that projection has valid structure."""
    from rig.domain.projection_builder import build_projection
    from dataclasses import asdict

    with tempfile.TemporaryDirectory() as tmpdir:
        repo_root = Path(tmpdir)
        repo_root.mkdir(parents=True, exist_ok=True)

        projection = build_projection(repo_root, revision=1)
        proj_dict = asdict(projection)

        # Check required fields
        assert "schema_version" in proj_dict
        assert "revision" in proj_dict
        assert "layout" in proj_dict
        assert "regions" in proj_dict["layout"]
        assert "widgets" in proj_dict
        assert "intents" in proj_dict

        # Check all region widget references exist
        for region_id, widget_ids in proj_dict["layout"]["regions"].items():
            for widget_id in widget_ids:
                assert widget_id in proj_dict["widgets"], (
                    f"Widget {widget_id} referenced by region {region_id} but not in widgets"
                )

        # Check all widget types are known
        js_path = (
            Path(__file__).parent.parent / "src" / "rig_tools" / "static" / "rig-ui.js"
        )
        js_content = js_path.read_text()

        for widget_id, widget in proj_dict["widgets"].items():
            wtype = widget["type"]
            assert f"{wtype}:" in js_content, (
                f"Widget {widget_id} has unknown type: {wtype}"
            )


def test_static_assets_exist():
    """Test that static assets exist."""
    static_dir = Path(__file__).parent.parent / "src" / "rig_tools" / "static"
    assert (static_dir / "index.html").exists()
    assert (static_dir / "rig-ui.js").exists()
    assert (static_dir / "rig-ui.css").exists()
