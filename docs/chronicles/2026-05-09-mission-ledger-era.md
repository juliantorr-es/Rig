Historical narrative. Not current workflow authority.

# 2026-05-09 — Mission Ledger Era

## Situation
The workflow was becoming unwieldy. We needed a structured, deterministic way to manage what agents were doing, how they did it, and how we tracked the results.

## The Pain
Agents were prone to spinning out of control on tiny, meaningless subtasks or endless recursive loops. Without a rigid structure, agent sessions became chaotic, difficult to review, and almost impossible to merge cleanly, leading to catastrophic collisions when multiple agents were running.

## False Starts
Allowing agents to dictate their own subtasks or recursively slice their work. Fine-grained, continuous edits were resulting in a fragmented history and merge conflicts.

## Decision
We established the ADR/Sprint/Mission hierarchy, strictly rejecting tiny slices, subtasks, or recursive workstreams. We mandated Sprint Research (a read-only planning phase) before any mutation, moved to coherent Patch Batches, and instituted merge-friendliness checks. All of this is tracked via structured events, culminating in dataset exports to prove agent efficacy. Out-of-scope findings were designated to prevent mission creep.

## Evidence
- ADR 0009
- `docs/workflow/adr-sprint-mission-evidence.md`
- `scripts/work_research.py`
- `scripts/work_patch_batch.py`

## Lesson
Agent workflow requires rigid, flat hierarchies and read-only research phases; never let an agent define its own infinite subtasks.

## Channel Hook
The Mission Ledger Era: Forcing Agents to Research Before They Code.
