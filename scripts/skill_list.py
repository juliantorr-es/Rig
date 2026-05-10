#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

import yaml


ROOT = Path("docs/agents/skills")


def parse_frontmatter(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        raise ValueError(f"{path}: missing YAML frontmatter")
    _, rest = text.split("---\n", 1)
    fm_text, _body = rest.split("\n---\n", 1)
    data = yaml.safe_load(fm_text)
    if not isinstance(data, dict):
        raise ValueError(f"{path}: invalid YAML frontmatter")
    return data


def iter_skills() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for path in sorted(ROOT.glob("*/SKILL.md")):
        fm = parse_frontmatter(path)
        rows.append(
            {
                "path": str(path),
                "name": fm.get("name", path.parent.name),
                "category": fm.get("category", "unknown"),
                "workflow_stage": fm.get("workflow_stage", "unknown"),
                "description": fm.get("description", ""),
            }
        )
    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    rows = iter_skills()
    if args.json:
        print(json.dumps(rows, indent=2, sort_keys=True))
        return 0
    for row in rows:
        print(f"{row['name']} | {row['category']} | {row['workflow_stage']} | {row['description']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
