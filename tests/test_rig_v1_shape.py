from __future__ import annotations

import json
from pathlib import Path

from rig_tools import action_manifest, context_compression, monitor, policy, schema_validation, work_queue


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_v1_artifacts_exist_or_can_be_written() -> None:
    pack = context_compression.write_context_pack(REPO_ROOT, task="td-cleanup-005", purpose="loop-planner", max_chars=4000, use_llm=False)
    assert pack["schema_version"] == "rig.context_pack.v1"
    queue_payload = {
        "schema_version": "rig.queue.v1",
        "jobs": [
            {
                "job_id": "td-cleanup-005-compat",
                "task": "td-cleanup-005",
                "mode": "read-only",
                "max_steps": 1,
                "status": "queued",
            }
        ],
        "warnings": [],
    }
    work_queue.save_queue(REPO_ROOT, queue_payload)
    queue = work_queue.load_queue(REPO_ROOT)
    decision = policy.check(REPO_ROOT, action="loop.run", mode="read-only")
    manifest = action_manifest.write_action_manifest(
        REPO_ROOT,
        task="td-cleanup-005",
        action_kind="test.v1",
        command_group="rig",
        command=["python", "scripts/rig.py", "action", "list"],
        inputs=[{"path": str(REPO_ROOT / ".build" / "rig" / "context" / "latest.md"), "kind": "context_pack"}],
        outputs=[{"path": str(REPO_ROOT / ".build" / "rig" / "actions" / "latest.json"), "kind": "action_manifest", "status": "produced"}],
        result_path=REPO_ROOT / ".build" / "rig" / "actions" / "latest.json",
    )
    state = monitor.build_state(REPO_ROOT)
    assert state["context_pack_summary"]["path"].endswith("latest.json")
    assert queue["jobs"][0]["status"] == "queued"
    assert decision["decision"] == "allow"
    assert manifest.manifest["schema_version"] == "rig.action.v1"


def test_schema_families_validate() -> None:
    assert schema_validation.validate_artifacts(REPO_ROOT, family="rig.action.v1").validated_artifact_count >= 1
    assert schema_validation.validate_artifacts(REPO_ROOT, family="rig.queue.v1").validated_artifact_count >= 1
    assert schema_validation.validate_artifacts(REPO_ROOT, family="rig.checkpoint.v1").validated_artifact_count >= 0
    assert schema_validation.validate_artifacts(REPO_ROOT, family="rig.context_pack.v1").validated_artifact_count >= 1
    assert schema_validation.validate_artifacts(REPO_ROOT, family="rig.policy_decision.v1").validated_artifact_count >= 1


def main() -> None:
    test_v1_artifacts_exist_or_can_be_written()
    test_schema_families_validate()


if __name__ == "__main__":
    main()
