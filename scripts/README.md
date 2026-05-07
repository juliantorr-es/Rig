# Agent Workflow Scripts

This directory contains scripts for the OpenCode agent workflow system for the Anigma codebase.

## Scripts

### 1. Roadmap Planning
- **`roadmap_plan_start.sh`** - Establish baseline before starting a new plan
- **`roadmap_plan_end.sh`** - Update completion and capture learnings after plan completion
- **`roadmap_weekly_scan.sh`** - Overall system health and cross-plan tracking (runs on first commit of week)

### 2. Digestion Pipeline
- **`digestion_pipeline.sh`** - Analyze inspiration repos, extract patterns, save to Shared memory, clean up

### 3. Testing & Validation
- **`test_workflow.sh`** - Test the complete agent workflow system
- **`validate_gates.sh`** - Existing CI gates validation

### 4. Shared Agent Memory Utility
- **`memory_store_cli.py`** - Small cross-CLI Shared memory helper (`add`, `search`, `get`) using direct API calls

### 5. Copilot + Vibe Coordination
- **`copilot_vibe_orchestrator.sh`** - Resume the latest Copilot roadmap session for this repo, run a roadmap-constrained Copilot implementation prompt, then ask Vibe to critique the resulting diff and optionally feed that critique back into Copilot.

### 6. TD Coordination
- **`td_milestone_progress.sh`** - Report milestone completion percentage after task approval or administrative closure.
- **`td_stale_tasks.sh`** - Classify `in_progress` TD tasks as `ACTIVE`, `REVIEW`, `STALE`, or `UNKNOWN` from their last update timestamp so agents can recover abandoned work safely.
- **`td_agent_memory_sync.sh`** - Post curated Gemini/Copilot/Codex task memory summaries into TD without dumping raw memory stores.
- **`td_finish_or_block.sh`** - Enforce that completed tasks go straight to review and failed tasks are linked to a blocker before the agent stops.

### 7. Governed Agent Lanes
- **`rig_agent_worktree.py`** - Safe per-agent Git worktree helper for creating, attaching, prompting, checkpointing, and removing isolated lanes.

## Usage

### Starting a New Plan
```bash
./scripts/roadmap_plan_start.sh "Plan Name"
```

### Ending a Plan
```bash
./scripts/roadmap_plan_end.sh "Plan Name" "YYYY-MM-DD"
```

### Running Digestion Pipeline
```bash
./scripts/digestion_pipeline.sh
```

### Testing the System
```bash
./scripts/test_workflow.sh
```

### Using Shared memory Helper
```bash
export SHARED_MEMORY_API_KEY="your_key"

# Add memory from stdin
echo "Harmonia linker blocker fixed via SyntaxNative source list" | \
  python3 ./scripts/memory_store_cli.py add --content - --container-tag anigma --meta source=codex

# Search memories
python3 ./scripts/memory_store_cli.py search --query "Harmonia blocker" --limit 5 --pretty

# Get memory/document status
python3 ./scripts/memory_store_cli.py get mem_your_id --pretty
```

### Coordinating Copilot and Vibe
```bash
# Show the latest Copilot roadmap session for this repo
./scripts/copilot_vibe_orchestrator.sh status

# Ask Copilot to implement work while following the roadmap in its current plan.md
./scripts/copilot_vibe_orchestrator.sh implement "Trim launcher-only app behavior and remove legacy CLI aliases"

# Have Vibe review the current diff for roadmap alignment and code quality
./scripts/copilot_vibe_orchestrator.sh review

# Apply justified Vibe review items through Copilot
./scripts/copilot_vibe_orchestrator.sh apply-review

# Full loop: Copilot implement -> Vibe critique -> Copilot refinement
./scripts/copilot_vibe_orchestrator.sh all "Trim launcher-only app behavior and remove legacy CLI aliases"
```

### Coordinating TD Agents
```bash
# Check ongoing work before claiming a task
./Scripts/td_stale_tasks.sh

# Machine-readable output for dashboards or wrappers
./Scripts/td_stale_tasks.sh --json

# Use stricter thresholds for short sessions
./Scripts/td_stale_tasks.sh --stale-minutes 30 --long-minutes 60
```

Agents should claim work with `td start`, log a `CLAIM`, keep `HEARTBEAT`
updates fresh during long work, and add a `RECOVERY` log before taking over
stale tasks. See `AGENTS.md` for the full protocol.

### Finishing Or Blocking TD Work
```bash
# Finished work must go directly to review
./scripts/td_finish_or_block.sh review --issue td-abc123 --summary "Implemented X and verified with command Y."

# Failed work must depend on a known blocker
./scripts/td_finish_or_block.sh block --issue td-abc123 --blocker td-def456 --reason "Cannot compile until blocker API exists."

# Or create the blocker while blocking the task
./scripts/td_finish_or_block.sh block --issue td-abc123 --create-blocker-title "Fix missing API" --reason "Task cannot proceed because API is missing."
```

### Governing Agent Lanes
```bash
# Create a new isolated lane
python scripts/rig_agent_worktree.py start gemini ui-entrypoint --dry-run
python scripts/rig_agent_worktree.py start gemini ui-entrypoint

# Attach to an existing linked worktree
python scripts/rig_agent_worktree.py attach gemini ui-cockpit --path .rig/worktrees/ui-cockpit

# Print the guarded handoff prompt
python scripts/rig_agent_worktree.py prompt gemini ui-entrypoint

# Preview a selective checkpoint
python scripts/rig_agent_worktree.py checkpoint gemini ui-cockpit --path .rig/worktrees/ui-cockpit --message "Add UI cockpit projection widgets" --dry-run
python scripts/rig_agent_worktree.py checkpoint gemini ui-cockpit --path .rig/worktrees/ui-cockpit --message "Add UI cockpit projection widgets" --exclude src/rig/domain/_git_helper.py

# Inspect promotion readiness without mutating the lane
python scripts/rig_agent_worktree.py review gemini ui-cockpit --path .rig/worktrees/ui-cockpit

# List or remove a lane
python scripts/rig_agent_worktree.py list
python scripts/rig_agent_worktree.py remove gemini ui-entrypoint
```

`start` creates an isolated lane, `attach` recognizes an existing lane without mutation, `prompt` prints guarded handoff text, `checkpoint` commits only selected files on non-main branches, `review` is read-only and reports readiness for promotion, and `remove` refuses dirty worktrees. Do not use `push`, `merge`, `rebase`, `reset`, `clean`, or `stash` in this workflow.

### Syncing Agent Memory Into TD
```bash
# Generate the accepted summary shape
./scripts/td_agent_memory_sync.sh --template

# Sync a curated Gemini summary into one TD issue
./scripts/td_agent_memory_sync.sh --issue td-dbdb41 --source gemini --file /tmp/gemini-task-summary.md

# Sync a Copilot summary from stdin
cat /tmp/copilot-task-summary.md | ./scripts/td_agent_memory_sync.sh --issue td-dbdb41 --source copilot
```

Only sync task-scoped summaries with headings such as `DECISION:`, `BLOCKER:`,
`FILES:`, `VERIFICATION:`, `NEXT:`, and `UNCERTAIN:`. Keep raw agent memories,
scratchpads, and transcripts out of TD.

## Git Integration

### Pre-commit Hook
The `.git/hooks/pre-commit` hook automatically runs `roadmap_weekly_scan.sh` on the first commit of each week.

### Worktree Management
Use `git worktree` commands for isolated development:
```bash
# Create worktree
git worktree add ../anigma-plan-feature feature-branch

# List worktrees
git worktree list

# Remove worktree
git worktree remove ../anigma-plan-feature
```

## Directory Structure

```
.auto-claude/
├── roadmap/          # Roadmap JSON files
├── digestion/        # Digestion logs and patterns
├── plans/           # Individual plan files
└── reports/         # Weekly and plan reports
```

## Shared memory Integration

Always check Shared memory first:
```bash
# In OpenCode agent
memory_store(mode: "search", query: "[topic]", scope: "project")
```

Add new insights:
```bash
memory_store(mode: "add", content: "Insight text", type: "learned-pattern", scope: "project")
```

## Documentation

See the main `AGENTS_*.md` files for detailed guidance:
- `AGENTS.md` - Overview and quick start
- `AGENTS_PLUGINS.md` - OpenCode plugin usage
- `AGENTS_SUPERMEMORY.md` - Three-tier memory system
- `AGENTS_GIT.md` - Git management and workflow
- `AGENTS_DIGESTION.md` - Inspiration repo analysis
- `AGENTS_ROADMAP.md` - Roadmap relevance pipeline
- `AGENTS_QUICKREF.md` - Quick reference commands
- `AGENTS_EXAMPLES.md` - Complete workflow examples

## Dependencies

- `git` - Version control
- `jq` - JSON processing
- `bash` - Shell scripting
- `python3` - For `memory_store_cli.py`

## Created By

OpenCode agent workflow system initialized on 2025-01-27 as part of Shared memory integration for Anigma codebase.
