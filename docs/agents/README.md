# Rig Agent Skills

Rig skills are installed operating instructions for agents.

They route behavior toward the current source of truth:
- `AGENTS.md`
- ADR Markdown and JSON
- schema files
- workflow docs
- code

Skills are not the source of truth themselves. They are short, composable guides that tell agents which authorities to consult and which gates to respect.

Skills live in `docs/agents/skills/` and must validate with `scripts/skill_validate.py`.
