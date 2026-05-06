#!/usr/bin/env python3
from __future__ import annotations

import os
import sys
import json
import tempfile
import hashlib
from pathlib import Path
from unittest.mock import MagicMock, patch
import rig_os_sentinel as sentinel

def test_sentinel_hash_detection() -> None:
    with tempfile.TemporaryDirectory() as td:
        repo = Path(td)
        sentinel_script = repo / "Scripts" / "rig_os_sentinel.py"
        sentinel_script.parent.mkdir()
        sentinel_script.write_text("print('hello')", encoding="utf-8")
        
        gov_dir = repo / "Docs" / "governance"
        gov_dir.mkdir(parents=True)
        hash_file = gov_dir / "rig_os_sentinel.sha256"
        
        # 1. Test missing hash
        with patch("rig_os_sentinel.SENTINEL_PATH", sentinel_script), \
             patch("rig_os_sentinel.HASH_PATH", hash_file), \
             patch("rig_os_sentinel.REPO_ROOT", repo):
            info = sentinel.check_hash()
            assert info["hash_status"] == "missing"
            
        # 2. Test matching hash
        actual_hash = hashlib.sha256(b"print('hello')").hexdigest()
        hash_file.write_text(actual_hash, encoding="utf-8")
        with patch("rig_os_sentinel.SENTINEL_PATH", sentinel_script), \
             patch("rig_os_sentinel.HASH_PATH", hash_file), \
             patch("rig_os_sentinel.REPO_ROOT", repo):
            info = sentinel.check_hash()
            assert info["hash_status"] == "match"
            
        # 3. Test mismatch (tamper)
        hash_file.write_text("wrong-hash", encoding="utf-8")
        with patch("rig_os_sentinel.SENTINEL_PATH", sentinel_script), \
             patch("rig_os_sentinel.HASH_PATH", hash_file), \
             patch("rig_os_sentinel.REPO_ROOT", repo):
            info = sentinel.check_hash()
            assert info["hash_status"] == "mismatch"

def test_sentinel_json_output() -> None:
    # Use dry-run to avoid writing artifacts
    with patch("sys.exit") as mock_exit, \
         patch("sys.argv", ["sentinel", "--format", "json", "--dry-run"]):
        # Capture stdout
        from io import StringIO
        stdout = StringIO()
        with patch("sys.stdout", stdout):
            try:
                sentinel.main()
            except SystemExit:
                pass
            
        output = json.loads(stdout.getvalue())
        assert output["schema_version"] == "rig.os_sentinel.v1"
        assert "status" in output
        assert "issues" in output
        assert "missing_required_subsystems" in output
        assert output["authoritative"] is True

def test_sentinel_failure_on_missing_subsystems() -> None:
    # On a clean run in this test environment, most subsystems should fail
    results = sentinel.validate_subsystems()
    # Check that at least one core subsystem fails (e.g., state_store)
    state_store = next(r for r in results if r["subsystem_id"] == "state_store")
    assert state_store["status"] == "fail"
    assert len(state_store["issues"]) > 0

def main() -> int:
    try:
        test_sentinel_hash_detection()
        test_sentinel_json_output()
        test_sentinel_failure_on_missing_subsystems()
        print("All Rig OS Sentinel tests passed.")
        return 0
    except Exception as e:
        print(f"Tests failed: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())
