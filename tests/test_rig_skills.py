from __future__ import annotations

import json
import subprocess
from pathlib import Path

import yaml


ROOT = Path("docs/agents/skills")
SCHEMA = Path("docs/schemas/rig-skill.schema.json")
REQUIRED = {
    "rig-grill-with-adrs",
    "rig-to-adr",
    "rig-to-sprints",
    "rig-to-missions",
    "rig-tdd",
    "rig-diagnose",
    "rig-handoff",
    "rig-forge-promote-dry-run",
    "rig-architecture-deepening",
    "rig-write-skill",
}
VALID_CATEGORIES = {"engineering", "governance", "workflow", "forge", "writing", "maintenance"}
VALID_STAGES = {"discovery", "adr", "sprint", "mission", "implementation", "validation", "handoff", "promotion"}


def parse_frontmatter(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8")
    assert text.startswith("---\n")
    _, rest = text.split("---\n", 1)
    fm_text, _ = rest.split("\n---\n", 1)
    data = yaml.safe_load(fm_text)
    assert isinstance(data, dict)
    return data


def test_schema_exists_and_is_valid_json() -> None:
    data = json.loads(SCHEMA.read_text(encoding="utf-8"))
    assert data["additionalProperties"] is False


def test_required_skills_exist() -> None:
    found = {p.parent.name for p in ROOT.glob("*/SKILL.md")}
    assert REQUIRED <= found


def test_skill_names_are_unique() -> None:
    names = [parse_frontmatter(p).get("name") for p in ROOT.glob("*/SKILL.md")]
    assert len(names) == len(set(names))


def test_skill_categories_and_stages_valid() -> None:
    for path in ROOT.glob("*/SKILL.md"):
        fm = parse_frontmatter(path)
        assert fm["category"] in VALID_CATEGORIES
        assert fm["workflow_stage"] in VALID_STAGES


def test_skill_validate_command_text_rules() -> None:
    for path in ROOT.glob("*/SKILL.md"):
        text = path.read_text(encoding="utf-8").lower()
        assert "recursive subtasks" not in text
        assert "push origin preproduction" not in text
        assert "git merge --no-ff" not in text


def test_forge_skill_mentions_required_commands() -> None:
    text = (ROOT / "rig-forge-promote-dry-run" / "SKILL.md").read_text(encoding="utf-8").lower()
    assert "rig forge doctor" in text
    assert "rig forge promote --dry-run" in text


def test_rig_to_adr_mentions_markdown_and_json_pair() -> None:
    text = (ROOT / "rig-to-adr" / "SKILL.md").read_text(encoding="utf-8").lower()
    assert "markdown" in text
    assert "json" in text


def test_rig_handoff_mentions_out_of_current_scope_findings() -> None:
    text = (ROOT / "rig-handoff" / "SKILL.md").read_text(encoding="utf-8").lower()
    assert "out-of-current-scope" in text


def test_skill_tools_run_cleanly() -> None:
    list_run = subprocess.run(["python3", "scripts/skill_list.py"], check=False, capture_output=True, text=True)
    validate_run = subprocess.run(["python3", "scripts/skill_validate.py"], check=False, capture_output=True, text=True)
    assert list_run.returncode == 0, list_run.stderr
    assert validate_run.returncode == 0, validate_run.stderr
