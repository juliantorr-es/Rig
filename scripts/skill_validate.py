#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
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
    if not text.startswith("---\n") or "\n---\n" not in text:
        raise ValueError(f"{path}: missing YAML frontmatter")
    _, rest = text.split("---\n", 1)
    fm_text, _body = rest.split("\n---\n", 1)
    data = yaml.safe_load(fm_text)
    if not isinstance(data, dict):
        raise ValueError(f"{path}: invalid YAML frontmatter")
    return data


def fail(msg: str) -> int:
    print(msg, file=sys.stderr)
    return 1


def main() -> int:
    if not SCHEMA.exists():
        return fail(f"missing schema: {SCHEMA}")
    try:
        schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return fail(f"invalid schema JSON: {exc}")
    if schema.get("additionalProperties") is not False:
        return fail("schema must set additionalProperties to false")
    required_fields = set(schema.get("required", []))

    if not ROOT.exists():
        return fail(f"missing skills dir: {ROOT}")

    skills = sorted(ROOT.glob("*/SKILL.md"))
    found = {p.parent.name for p in skills}
    missing = sorted(REQUIRED - found)
    if missing:
        return fail("missing required skills: " + ", ".join(missing))

    names: set[str] = set()
    for path in skills:
        fm = parse_frontmatter(path)
        missing = required_fields - set(fm)
        if missing:
            return fail(f"{path}: missing required frontmatter fields: {', '.join(sorted(missing))}")
        name = fm["name"]
        if name in names:
            return fail(f"duplicate skill name: {name}")
        names.add(name)
        if fm["category"] not in VALID_CATEGORIES:
            return fail(f"{path}: invalid category {fm['category']}")
        if fm["workflow_stage"] not in VALID_STAGES:
            return fail(f"{path}: invalid workflow_stage {fm['workflow_stage']}")
        for field in ("use_when", "do_not_use_when", "inputs", "outputs", "required_context", "required_gates", "authority_boundaries", "handoff_requirements"):
            if not isinstance(fm[field], list) or not fm[field]:
                return fail(f"{path}: {field} must be a non-empty list")
        text = path.read_text(encoding="utf-8").lower()
        if "recursive subtasks" in text:
            return fail(f"{path}: recursive subtasks wording not allowed")
        if "git merge" in text and "protected" in text:
            return fail(f"{path}: protected-branch direct merge guidance not allowed")
        if path.parent.name == "rig-forge-promote-dry-run":
            if "rig forge doctor" not in text or "rig forge promote --dry-run" not in text:
                return fail(f"{path}: missing required forge commands")
        if path.parent.name == "rig-to-adr":
            if "markdown" not in text or "json" not in text:
                return fail(f"{path}: must mention Markdown + JSON ADR pair")
        if path.parent.name == "rig-handoff":
            if "out-of-current-scope" not in text:
                return fail(f"{path}: must mention out-of-current-scope findings")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
