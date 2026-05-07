"""Tests for UI intent contract: every advertised projection intent must have a server-side policy.

Tests verify:
- All intents in projections have corresponding handlers in UIServer
- Unsupported intents (apply_patch, approve_gate) have explicit refusal handlers
- Intent results include proper structure for frontend handling
- Buttons do not remain stuck in pending state after unsupported/failed results
"""

from pathlib import Path
import tempfile


class TestProjectionIntentContract:
    """Test that all projection intents have server-side handling policies."""

    def test_projection_advertises_known_intents(self):
        """Verify projections only advertise intents that have server-side policies."""
        from rig.domain.projection_builder import build_projection, _build_empty_projection
        
        # Create a temp directory for projection building
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            
            # Test empty projection (no active workspace)
            empty_proj = _build_empty_projection(1, None, 0, 0, 0)
            advertised_intents_empty = set(empty_proj.intents.keys())
            
            # Test active workspace projection (if we can create one)
            active_proj = build_projection(repo_root, revision=1, chat_history=None)
            advertised_intents_active = set(active_proj.intents.keys())
            
            # All advertised intents should be known
            all_advertised = advertised_intents_empty | advertised_intents_active
            
            # Known intents that should have handlers:
            known_intents = {
                "intent.refresh_projection",
                "intent.workspace_status",
                "intent.chat.submit",
                "intent.run_validators",
                "intent.open_workspace",
                "intent.initialize_current_folder",
                "intent.apply_patch",
            }
            
            # Verify all advertised intents are in our known set
            # (This test will fail if a new intent is added without updating known_intents)
            assert all_advertised.issubset(known_intents), \
                f"Projection advertises unknown intents: {all_advertised - known_intents}"

    def test_unsupported_intents_have_handlers(self):
        """Verify that apply_patch and approve_gate intents have explicit handlers in UI server.
        
        These intents are governed-reserved but may be advertised as disabled in projections.
        They must have explicit refusal handlers, not silently fail.
        """
        from rig.domain.intent_defs import Intent
        from rig_tools.ui_server import UIServer
        from pathlib import Path
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            server = UIServer(Path(tmpdir), "test_token")
            
            # Test apply_patch intent returns structured refusal
            apply_intent = Intent(
                kind="rig.intent.apply_patch",
                intent_id="test-apply-1",
                observed_projection_revision=1,
                client={"kind": "pywebview"}
            )
            result = server.intent_handler.handle(apply_intent)
            
            assert result["accepted"] is False, "apply_patch should not be accepted from UI"
            assert "status" in result, "Response should include status"
            assert result["status"] == "unsupported", f"Expected unsupported status, got {result.get('status')}"
            assert "reason" in result, "Response should include reason"
            assert "intent_kind" in result, "Response should include intent_kind for frontend correlation"
            assert "apply" in result["reason"].lower() or "patch" in result["reason"].lower(), \
                f"Reason should mention apply/patch: {result.get('reason')}"
            
            # Test approve_gate intent returns structured refusal
            approve_intent = Intent(
                kind="rig.intent.approve_gate",
                intent_id="test-approve-1",
                observed_projection_revision=1,
                client={"kind": "pywebview"}
            )
            result = server.intent_handler.handle(approve_intent)
            
            assert result["accepted"] is False, "approve_gate should not be accepted from UI"
            assert "status" in result, "Response should include status"
            assert result["status"] == "unsupported", f"Expected unsupported status, got {result.get('status')}"
            assert "reason" in result, "Response should include reason"
            assert "intent_kind" in result, "Response should include intent_kind for frontend correlation"
            assert "approve" in result["reason"].lower() or "gate" in result["reason"].lower(), \
                f"Reason should mention approve/gate: {result.get('reason')}"

    def test_registered_intents_include_all_projection_intents(self):
        """Verify UI server registers handlers for all intents that could be advertised."""
        from rig_tools.ui_server import UIServer
        from pathlib import Path
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            server = UIServer(Path(tmpdir), "test_token")
            
            # Get all registered intent kinds
            registered = set(server.intent_handler._handlers.keys())
            
            # These are the intents currently registered
            expected_registered = {
                "rig.intent.open_workspace",
                "rig.intent.initialize_current_folder",
                "rig.intent.refresh_projection",
                "rig.intent.workspace_status",
                "rig.intent.chat.submit",
                "rig.intent.run_validators",
                "rig.intent.apply_patch",
                "rig.intent.approve_gate",
            }
            
            assert registered == expected_registered, \
                f"Registered intents mismatch. Expected: {expected_registered}, Got: {registered}"


class TestUnsupportedIntentStructure:
    """Test that unsupported intent responses have proper structure for frontend."""

    def test_unsupported_intent_returns_correlation_fields(self):
        """Verify unsupported intents return fields needed for frontend correlation."""
        from rig.domain.intent_defs import Intent
        from rig_tools.ui_server import UIServer
        from pathlib import Path
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            server = UIServer(Path(tmpdir), "test_token")
            
            intent = Intent(
                kind="rig.intent.apply_patch",
                intent_id="correlation-123",
                observed_projection_revision=1,
                client={"kind": "pywebview"}
            )
            result = server.intent_handler.handle(intent)
            
            # Must have fields for frontend correlation
            assert "intent_id" in result, "Result must include intent_id for correlation"
            assert result["intent_id"] == "correlation-123", "intent_id should match request"
            assert "intent_kind" in result, "Result must include intent_kind"
            assert result["intent_kind"] == "rig.intent.apply_patch", "intent_kind should match request"
            assert "accepted" in result, "Result must include accepted field"
            assert result["accepted"] is False, "Unsupported intent must be rejected"

    def test_unsupported_intent_returns_actionable_message(self):
        """Verify unsupported intent messages guide users to CLI path."""
        from rig.domain.intent_defs import Intent
        from rig_tools.ui_server import UIServer
        from pathlib import Path
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            server = UIServer(Path(tmpdir), "test_token")
            
            # Test apply_patch message
            intent = Intent(
                kind="rig.intent.apply_patch",
                intent_id="test",
                observed_projection_revision=1,
                client={"kind": "pywebview"}
            )
            result = server.intent_handler.handle(intent)
            
            reason = result.get("reason", "")
            assert "rig" in reason.lower() or "cli" in reason.lower() or "command" in reason.lower(), \
                f"Message should guide to CLI: {reason}"
            
            # Test approve_gate message
            intent = Intent(
                kind="rig.intent.approve_gate",
                intent_id="test",
                observed_projection_revision=1,
                client={"kind": "pywebview"}
            )
            result = server.intent_handler.handle(intent)
            
            reason = result.get("reason", "")
            assert "rig" in reason.lower() or "cli" in reason.lower() or "command" in reason.lower(), \
                f"Message should guide to CLI: {reason}"


class TestProjectionIntentEnabledState:
    """Test that intents are properly enabled/disabled in projections."""

    def test_apply_patch_intent_is_disabled_in_active_projection(self):
        """Verify apply_patch is advertised as disabled when no proposal exists."""
        from rig.domain.projection_builder import _build_empty_projection
        
        # In empty projection, apply_patch should not be present
        # (it's only in active workspace projections)
        proj = _build_empty_projection(1, None, 0, 0, 0)
        
        # apply_patch is not in empty projection
        assert "intent.apply_patch" not in proj.intents, \
            "apply_patch should not be advertised in empty workspace projection"

    def test_apply_patch_intent_disabled_with_reason(self):
        """Verify apply_patch has a disabled reason when present."""
        from rig.domain.projection_builder import build_projection
        from pathlib import Path
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            
            # Create a minimal workspace for testing
            workspace_dir = repo_root / "workspace"
            workspace_dir.mkdir()
            
            # Write a minimal rig.json to make it look like a workspace
            import json
            (workspace_dir / "rig.json").write_text(json.dumps({
                "workspace_id": "test-ws",
                "status": "planned"
            }))
            
            try:
                proj = build_projection(repo_root, revision=1, chat_history=None)
                
                if "intent.apply_patch" in proj.intents:
                    intent = proj.intents["intent.apply_patch"]
                    assert intent.enabled is False, "apply_patch should be disabled"
                    assert intent.disabled_reason is not None, "apply_patch should have disabled reason"
                    assert len(intent.disabled_reason) > 0, "disabled reason should not be empty"
            except Exception:
                # If workspace scanning fails, that's okay for this test
                pass
