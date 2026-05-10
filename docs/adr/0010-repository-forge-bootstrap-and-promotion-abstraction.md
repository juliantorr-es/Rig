# Repository Forge Bootstrap and Promotion Abstraction

**ADR 0010**

Rig must support users who have no remote forge, users on GitHub, users on GitLab, users on Gitea, and future forges. The core promotion flow uses local Git as the canonical substrate. Remote forge integrations are adapters that map Rig-native promotion policy onto forge-specific capabilities.

**Status**: proposed

> [!IMPORTANT]
> **Core Principle**: Git is the canonical substrate. Remote forges are adapters. GitHub is not the architecture.

> [!NOTE]
> **Rig must support local-only users**. The default promotion mode requires no remote forge. All 13 gates of the Rite of Deterministic Passage are forge-neutral and require no remote forge connectivity. `work_promote.py` should prepare or execute promotion according to the selected adapter mode. Local-only mode promotes to a local branch after deterministic passage.

**Related ADRs**:
- [0007 Workspace Domain Authority](0007-workspace-domain-authority.md) — worktree isolation as the backbone of agent sandboxing
- [0009 Agentic Workflow Refinement](0009-agentic-workflow-refinement.md) — the Rite of Deterministic Passage with 13 forge-neutral gates

---

## Decision Summary

**Rig uses local Git as the canonical substrate. Remote forge integrations are adapters. Promotion policy is expressed in Rig-native terms and mapped onto local-only, GitHub, GitLab, Gitea, or future forge capabilities.**

---

## Problem

Rig currently assumes GitHub-like protected PR flow for preproduction promotion. This creates several issues:

1. **Local-only users are not first-class** — Current documentation and some scripts reference GitHub-specific concepts (PR flow, branch protection) that don't apply to local-only usage.
2. **Non-GitHub users are unsupported** — Users on GitLab, Gitea, or other forges cannot use Rig's promotion flow without GitHub-specific modifications.
3. **Core workflow depends on forge assumptions** — While `work_promote.py` is actually local-first, its terminology and references imply GitHub dependency.
4. **No adapter abstraction** — There is no formal interface for adding new forge integrations.

---

## Current State

### What Works Today (Forge-Neutral)

1. **`work_promote.py`** — Only does local git operations; does NOT push to remote. All 13 promotion gates use local git commands only.
2. **Worktree system** — Uses local git worktrees and branches exclusively.
3. **Ledger paths** — `.rig/work/adr/<adr-id>/` are local filesystem paths.
4. **Validation gates** — All 13 gates are local-only operations requiring no forge API.

### What is GitHub-Specific Today

1. **Terminology** — References to "pull request" and "branch protection" in documentation.
2. **Assumptions** — Default target branch `preproduction` assumes GitHub-like branching model.
3. **Connector stub** — `src/rig/domain/connectors/github_issues.py` exists as a stub only (does not connect to GitHub).

### Key Observation

**The core Rig infrastructure is already forge-neutral.** The only GitHub-specific code is in the `github_issues.py` connector stub, which is explicitly isolated. The promotion flow happens entirely through local git operations.

---

## Decision

**Create a forge adapter abstraction that keeps Git as the substrate.**

### Decision 1: Forge Adapter Interface

Define a standard `ForgeAdapter` protocol for forge-specific operations. Core Rig remains forge-neutral.

```python
# src/rig/domain/forge/__init__.py

from typing import Protocol, runtime_checkable

@runtime_checkable
class ForgeAdapter(Protocol):
    """Interface for forge-specific operations."""
    
    # Remote branch operations
    def push_branch(self, branch_name: str, force: bool = False) -> bool: ...
    def create_branch(self, branch_name: str, source_branch: str) -> bool: ...
    
    # Pull/Merge Request operations
    def create_pr(self, title: str, source_branch: str, target_branch: str, 
                  description: str = "") -> str | None: ...
    def get_pr_status(self, pr_id: str) -> dict: ...
    def merge_pr(self, pr_id: str, merge_strategy: str = "merge") -> bool: ...
    
    # Branch protection
    def is_branch_protected(self, branch_name: str) -> bool: ...
    def can_merge_to_branch(self, user: str, branch_name: str) -> bool: ...
    
    # Repository info
    def get_repo_info(self) -> dict: ...
```

### Decision 2: Local-Only First-Class Support

**Local-only mode is the default.** No remote forge is required. Promotion happens via local merge only.

```bash
# Local-only (default)
python3 scripts/work_promote.py <task_id> --target preproduction
```

### Decision 3: Adapter-Backed Promotion Modes

Support multiple promotion modes via adapter selection:

| Mode | Description | Adapter |
|------|-------------|---------|
| `local` | Local merge only, no remote | `LocalOnlyAdapter` |
| `github` | GitHub PR flow | `GitHubAdapter` |
| `gitlab` | GitLab MR flow | `GitLabAdapter` |
| `gitea` | Gitea PR flow | `GiteaAdapter` |
| `custom` | Future adapters | `CustomForgeAdapter` |

### Decision 4: Forge-Neutral Validation Gates

**The 13 gates of the Rite of Deterministic Passage are forge-neutral.** All gates use local git operations only. Adapters may add **additional** forge-specific gates as optional extensions (Gate 14+).

### Decision 5: Adapter Registry Pattern

Use a registry pattern (similar to `intake_registry.py`) for forge adapter discovery and configuration.

### Decision 6: Configuration File

Store forge adapter configuration in `.rig/config/forge.yaml`:

```yaml
# .rig/config/forge.yaml
adapter: local  # or github, gitlab, gitea, custom
credentials_file: ~/.rig/forge_credentials.json
# Optional forge-specific settings
github:
  repo: owner/repo
  default_branch: main
gitlab:
  project_id: 12345
  default_branch: main
```

---

## Authority Boundaries

| Boundary ID | Description | Must NOT |
|-------------|-------------|---------|
| `forge-neutral-core` | Rig core must not depend on any specific forge | Import forge-specific modules in core, Assume GitHub-only features, Require remote connectivity |
| `adapter-isolation` | Forge adapters must not leak provider-specific behavior into core | Modify core workflow based on adapter mode, Return forge-specific errors from core, Use forge APIs in core validation |
| `local-first` | Local-only mode must always work without any forge | Require forge API for promotion, Fail if remote unavailable, Assume remote branches exist |
| `test-isolation` | Tests must not depend on forge availability | Use real forge APIs in tests, Require network for tests, Test forge-specific behavior in core tests |
| `git-substrate` | Git is the canonical substrate | Replace git operations with forge APIs, Use forge APIs for local checks, Bypass git for remote operations |

---

## Reviewability Budget

Rig enforces a provider-neutral reviewability budget to keep promotion candidates small enough for both human reviewers and hosted AI review tools.

**Core Principle**: Rig does not depend on Copilot availability, but hosted AI review tools and human reviewers degrade on oversized diffs. Rig enforces a default reviewability budget of 300 changed files per promotion candidate. Exceeding the budget blocks promotion by default. Overrides require an explicit reason and evidence.

### Policy

| Aspect | Value | Rationale |
|--------|-------|-----------|
| Default max changed files | 300 | This is a provider-neutral budget. Public GitHub docs do not define a universal Copilot limit; this is Rig's own reviewability threshold. |
| Default action when exceeded | block_promotion | Ensures candidates are reviewable before promotion. |
| Override allowed | Yes | Some legitimate changes may exceed the budget. |
| Override requires reason | Yes | Explicit justification needed for audit trail. |
| Applies to | All modes | local_only, github, gitlab, gitea, and future adapters. |

### Rationale

1. **Hosted AI review tools degrade on oversized diffs** — While the specific limits are not universally documented, large PRs consistently reduce review quality for both AI and human reviewers.
2. **Provider-neutral** — This is Rig's own budget, not tied to any specific tool's limits.
3. **Block by default** — Safety-first: better to block and require explicit override than to allow oversized candidates through.
4. **Evidence requirement** — Overrides must be documented with reasoning for auditability.

### Implementation

The budget is enforced during the Rite of Deterministic Passage gate checks. If a promotion candidate exceeds 300 changed files:

1. The promotion is blocked at the gate
2. A finding is emitted with the actual count
3. An override mechanism allows proceeding with explicit reason
4. The override and reason are recorded in the promotion receipt

### Gate Integration

This budget check is integrated as an additional validation step within the existing 13 gates framework. It is forge-neutral and applies equally to all forge adapters.

---

## Supported Modes

### Mode 1: Local-Only (default)

**For**: Local-only users, airgapped environments, development/testing

```
Flow:
1. Agent works in worktree on agent/adrNNNN-mission branch
2. Agent runs: work_promote.py --target preproduction
3. Script checks all 13 gates locally
4. If all pass: git merge into local preproduction branch
5. No remote interaction

Characteristics:
- No forge API required
- No push to remote
- No PR/MR creation
- Promotion is local branch merge only
- All 13 gates pass locally
```

### Mode 2: GitHub

**For**: GitHub users, requires `gh` CLI or PyGithub

```
Flow:
1. Agent works in worktree on agent/adrNNNN-mission branch
2. Adapter pushes branch to GitHub
3. Adapter creates PR to preproduction
4. Script checks all 13 gates locally
5. Adapter verifies GitHub PR checks pass (optional Gate 14+)
6. If all pass: git merge locally, adapter updates PR
7. Adapter may auto-merge PR

Characteristics:
- Uses GitHub PR flow
- Branch protection enforced by GitHub
- CI checks run on GitHub Actions
- work_promote.py validates local state matches GitHub state
```

### Mode 3: GitLab

**For**: GitLab users, requires `glab` CLI or python-gitlab

```
Flow:
1. Agent works in worktree on agent/adrNNNN-mission branch
2. Adapter pushes branch to GitLab
3. Adapter creates Merge Request to preproduction
4. Script checks all 13 gates locally
5. Adapter verifies GitLab MR pipeline passes (optional Gate 14+)
6. If all pass: git merge locally, adapter updates MR
7. Adapter may merge MR

Characteristics:
- Uses GitLab Merge Request flow
- Branch protection enforced by GitLab
- CI checks run on GitLab CI/CD
- work_promote.py validates local state matches GitLab state
```

### Mode 4: Gitea

**For**: Gitea users

```
Flow:
1. Agent works in worktree on agent/adrNNNN-mission branch
2. Adapter pushes branch to Gitea
3. Adapter creates PR to preproduction
4. Script checks all 13 gates locally
5. Adapter verifies Gitea PR status (optional Gate 14+)
6. If all pass: git merge locally, adapter updates PR
7. Adapter may merge PR

Characteristics:
- Uses Gitea Pull Request flow
- Branch protection enforced by Gitea
- CI checks run on Gitea Actions or external
- Limited merge strategies compared to GitHub/GitLab
```

### Mode Selection

```bash
# Explicit mode selection
python3 scripts/work_promote.py <task_id> --target preproduction --forge github
python3 scripts/work_promote.py <task_id> --target preproduction --forge gitlab
python3 scripts/work_promote.py <task_id> --target preproduction --forge gitea
python3 scripts/work_promote.py <task_id> --target preproduction --forge local

# Default (local) - no --forge flag
python3 scripts/work_promote.py <task_id> --target preproduction
```

---

## Forge Adapter Interface

### LocalOnlyAdapter

Handling for local-only environments where no remote forge exists.

```python
class LocalOnlyAdapter:
    """Forge adapter for local-only usage. No remote operations."""
    
    def __init__(self):
        self.capabilities = {"push": False, "pr": False, "branch_protection": False}
    
    def push_branch(self, branch_name: str, force: bool = False) -> bool:
        # Local-only: never push
        return False
    
    def create_pr(self, title: str, source_branch: str, target_branch: str,
                  description: str = "") -> str | None:
        # Local-only: promotion is local merge, not PR
        return None
    
    def merge_pr(self, pr_id: str, merge_strategy: str = "merge") -> bool:
        raise NotSupportedError("Local-only mode uses git merge directly")
    
    def is_branch_protected(self, branch_name: str) -> bool:
        # Local-only: branches are never "protected" in remote sense
        return False
```

### GitHubAdapter

Handling for GitHub repositories.

```python
class GitHubAdapter:
    """Forge adapter for GitHub repositories."""
    
    def __init__(self, repo: str, auth_token: str | None = None):
        self.repo = repo  # "owner/repo"
        self.capabilities = {
            "push": True, 
            "pr": True, 
            "branch_protection": True,
            "merge_strategies": ["merge", "squash", "rebase"]
        }
    
    def push_branch(self, branch_name: str, force: bool = False) -> bool:
        # Use gh CLI: gh push --force if force else gh push
        pass
    
    def create_pr(self, title: str, source_branch: str, target_branch: str,
                  description: str = "") -> str | None:
        # Use gh CLI: gh pr create --title "..." --base "..." --head "..."
        pass
    
    def get_pr_status(self, pr_id: str) -> dict:
        # Check CI status, review status via GitHub API
        pass
    
    def merge_pr(self, pr_id: str, merge_strategy: str = "squash") -> bool:
        # Use gh CLI: gh pr merge --squash
        pass
    
    def is_branch_protected(self, branch_name: str) -> bool:
        # Check GitHub branch protection via API
        pass
```

### GitLabAdapter

Handling for GitLab repositories.

```python
class GitLabAdapter:
    """Forge adapter for GitLab repositories."""
    
    def __init__(self, project_id: str, auth_token: str | None = None):
        self.project_id = project_id
        self.capabilities = {
            "push": True,
            "pr": True,  # GitLab calls them Merge Requests
            "branch_protection": True,
            "merge_strategies": ["merge", "fast-forward", "rebase"]
        }
    
    def create_pr(self, title: str, source_branch: str, target_branch: str,
                  description: str = "") -> str | None:
        # Use glab CLI: glab mr create --title "..." --source-branch "..." --target-branch "..."
        pass
```

### GiteaAdapter

Handling for Gitea repositories.

```python
class GiteaAdapter:
    """Forge adapter for Gitea repositories."""
    
    def __init__(self, repo: str, base_url: str, auth_token: str | None = None):
        self.repo = repo  # "owner/repo"
        self.base_url = base_url  # For self-hosted: "https://gitea.example.com"
        self.capabilities = {
            "push": True,
            "pr": True,
            "branch_protection": True,
            "merge_strategies": ["merge"]  # Limited
        }
```

---

## Repository Bootstrap Flow

```
Adapter Bootstrap Sequence:
1. Adapter detects forge type (GitHub/GitLab/Gitea/Local)
   - Local: No remote URL -> local-only
   - GitHub: Remote URL matches github.com
   - GitLab: Remote URL matches gitlab.com or configured instance
   - Gitea: Remote URL matches gitea or configured instance
   - Custom: Explicit adapter configuration

2. Adapter validates repository structure
   - Check required files exist (pyproject.toml, AGENTS.md, etc.)
   - Validate Rig-specific configuration

3. Adapter creates required branches (if missing)
   - main (or configured default)
   - preproduction
   - Other required branches per repository policy

4. Adapter configures branch protection (if supported)
   - Protect main branch
   - Protect preproduction branch
   - Configure required checks (CI, reviews)

5. Adapter returns forge capabilities
   - Supported merge strategies
   - Available branch protection features
   - CI/CD integration capabilities

6. Rig stores adapter config in .rig/config/forge.yaml

7. Bootstrapping complete - repository ready for Rig workflow

Command:
```bash
python3 scripts/repo_bootstrap.py --forge auto
python3 scripts/repo_bootstrap.py --forge github
python3 scripts/repo_bootstrap.py --forge gitlab
```
```

---

## Promotion Flow

```
Forge-Abstracted Promotion Flow:

Phase 1: Pre-Promotion (Adapter-Specific)
1. Agent selects forge mode (--forge flag or config)
2. Adapter performs mode-specific pre-promotion checks
   - Local: No checks
   - GitHub: Verify gh CLI available, verify auth
   - GitLab: Verify glab CLI available, verify auth
   - Gitea: Verify API available, verify auth
3. Adapter performs forge-specific preflight
   - Local: None
   - GitHub: Check if PR exists, get PR status
   - GitLab: Check if MR exists, get MR pipeline status
   - Gitea: Check if PR exists, get PR status

Phase 2: Core Validation (Forge-Neutral)
4. Core work_promote.py runs all 13 gates locally
   - Sprint research completed
   - Mission handoff completed
   - Patch batches prechecked and applied
   - Merge-friendliness pass
   - work_doctor.py passed
   - Required tests passed
   - Out-of-scope findings recorded
   - Candidate source branch is clean
   - Candidate source branch HEAD recorded
   - Preproduction branch exists locally
   - Merge simulation against preproduction passes
   - Preproduction working tree is clean

Phase 3: Local Merge (Always)
5. If all 13 gates pass: git merge --ff-only into local preproduction
6. Local preproduction branch updated

Phase 4: Post-Promotion (Adapter-Specific)
7. If adapter mode is remote:
   a. Adapter pushes local preproduction to remote
   b. Adapter updates PR/MR status
   c. Adapter may auto-merge PR/MR (if configured)
8. Emit promotion receipt with:
   - All 13 gate results
   - Forge-specific status (if applicable)
   - Timestamp
   - Source and target commits

Command:
```bash
python3 scripts/work_promote.py <task_id> --target preproduction --forge github --dry-run
python3 scripts/work_promote.py <task_id> --target preproduction --forge gitlab
```
```

---

## Validation Gate Model

### The 13 Core Gates (Forge-Neutral)

| Gate | ID | Description | Local Check | Adapter Role |
|------|----|-------------|--------------|--------------|
| 1 | `gate-sprint-research` | Sprint research completed | Local ledger check | None |
| 2 | `gate-mission-handoff` | Mission handoff completed | Local ledger check | None |
| 3 | `gate-patch-batches-precheck` | Patch batches prechecked | `git apply --check` | None |
| 4 | `gate-patch-batches-applied` | Patch batches applied and validated | Local ledger check | None |
| 5 | `gate-merge-friendliness` | Merge friendliness pass | Local worktree check | None |
| 6 | `gate-work-doctor` | work_doctor.py passed | Local script | None |
| 7 | `gate-required-tests` | Required tests passed | Local pytest | None |
| 8 | `gate-out-of-scope` | Out-of-scope findings recorded | Local ledger check | None |
| 9 | `gate-source-clean` | Candidate source branch is clean | `git status --porcelain` | None |
| 10 | `gate-source-head-recorded` | Candidate source branch HEAD is recorded | `git rev-parse HEAD` | None |
| 11 | `gate-preproduction-exists` | Preproduction branch exists locally | `git branch --list` | May create remote |
| 12 | `gate-merge-simulation` | Merge simulation passes | `git merge-tree` | None |
| 13 | `gate-preproduction-clean` | Preproduction working tree is clean | `git status --porcelain` | None |

**Key insight**: All 13 gates are local git operations. No forge API required.

### Optional Adapter-Specific Gates (14+)

Adapters may add forge-specific gates as optional extensions:

| Gate | ID | Description | Forge |
|------|----|-------------|-------|
| 14 | `gate-github-ci-passing` | GitHub Actions checks passing | GitHub |
| 14 | `gate-gitlab-pipeline-passing` | GitLab CI/CD pipeline passing | GitLab |
| 14 | `gate-gitea-ci-passing` | Gitea Actions checks passing | Gitea |
| 15 | `gate-required-reviews` | Required reviews approved | GitHub, GitLab, Gitea |
| 16 | `gate-branch-protection` | Branch protection allows merge | GitHub, GitLab, Gitea |

These gates are **optional** and forge-specific. They are not part of the core 13 gates.

---

## Non-Goals

These are explicitly **out of scope** for this ADR:

1. **Rig becomes a CI/CD system** — Integration is via adapters only. Rig does not own CI/CD pipelines.
2. **Rig supports fork-based workflows** — Only linked worktrees are supported. Fork-based PR workflows are out of scope.
3. **Rig supports multiple forges simultaneously** — One adapter per repository. The repository has one forge type.
4. **Rig makes assumptions about branch naming** — Use canonical naming from ADR contracts (`sprint/`, `agent/`, `promotion/` prefixes).
5. **Rig manages forge credentials** — Credential storage and management is the user's responsibility (with optional helper utilities).
6. **Rig implements two-phase commit** — Local merge is authoritative. Adapters may sync state but do not change the local-first model.

---

## Consequences

### Positive

- **Forge-neutral core**: Rig's core workflow is independent of any specific forge.
- **Local-only first-class**: Local-only users are fully supported without any remote forge.
- **Extensible**: New forges can be added via adapter implementations without modifying core.
- **Consistent workflow**: The same 13 gates apply regardless of forge, with optional forge-specific extensions.
- **Testable**: Core workflow can be tested without any forge API access.
- **Maintainable**: Forge-specific code is isolated in adapters.

### Negative

- **Adapter maintenance burden**: Each forge adapter requires implementation and maintenance.
- **Feature parity limitations**: Some forges may not support all capabilities (e.g., Gitea's limited merge strategies).
- **Credential management complexity**: Users must configure forge credentials separately.
- **Initial learning curve**: Users need to understand adapter selection and configuration.

---

## Initial Implementation Sprints

**Note on Slice terminology**: This ADR uses "Sprint" to describe implementation phases. These are NOT workflow hierarchy levels. Sprints are internal staging for ADR implementation. The workflow hierarchy stops at Mission.

### Sprint 1: Adapter Interface Definition

**Mission**: Define the ForgeAdapter protocol and implement LocalOnlyAdapter.

- [ ] Create `src/rig/domain/forge/__init__.py` with `ForgeAdapter` protocol
- [ ] Create `src/rig/domain/forge/local_adapter.py` with `LocalOnlyAdapter`
- [ ] Create adapter registry in `src/rig/domain/forge/registry.py`
- [ ] Update `work_promote.py` to accept `--forge` flag (default: local)
- [ ] Add forge mode to progress ledger
- [ ] Add `LocalOnlyAdapter` tests with mocked git operations

**Branch**: `sprint/adr0010-sprint-adapter-interface`
**Ledger**: `.rig/work/adr/adr0010-repository-forge-bootstrap-and-promotion-abstraction/`

### Sprint 2: Repository Bootstrap

**Mission**: Implement repository bootstrap for forge detection and branch creation.

- [ ] Create `scripts/repo_bootstrap.py`
- [ ] Implement forge type detection (auto-detect based on remote URL)
- [ ] Implement branch creation and validation
- [ ] Create `.rig/config/forge.yaml` configuration
- [ ] Add bootstrap tests

**Branch**: `sprint/adr0010-sprint-repo-bootstrap`

### Sprint 3: GitHub Adapter

**Mission**: Implement GitHubAdapter with full capability support.

- [ ] Create `src/rig/domain/forge/github_adapter.py`
- [ ] Implement all GitHub-specific operations
- [ ] Add GitHub CLI dependency check
- [ ] Add GitHub adapter tests with mocked API
- [ ] Document GitHub-specific configuration

**Branch**: `sprint/adr0010-sprint-github-adapter`

### Sprint 4: GitLab Adapter

**Mission**: Implement GitLabAdapter.

- [ ] Create `src/rig/domain/forge/gitlab_adapter.py`
- [ ] Implement all GitLab-specific operations
- [ ] Add GitLab CLI dependency check
- [ ] Add GitLab adapter tests with mocked API
- [ ] Document GitLab-specific configuration

**Branch**: `sprint/adr0010-sprint-gitlab-adapter`

### Sprint 5: Gitea Adapter

**Mission**: Implement GiteaAdapter.

- [ ] Create `src/rig/domain/forge/gitea_adapter.py`
- [ ] Implement all Gitea-specific operations
- [ ] Add Gitea API dependency check
- [ ] Add Gitea adapter tests with mocked API
- [ ] Document Gitea-specific configuration

**Branch**: `sprint/adr0010-sprint-gitea-adapter`

### Sprint 6: Documentation and Polish

**Mission**: Complete documentation and polish the implementation.

- [ ] Update `docs/workflow/adr-sprint-mission-evidence.md` with forge abstraction details
- [ ] Add user documentation for forge configuration
- [ ] Add troubleshooting guide for forge adapters
- [ ] Final integration testing
- [ ] Prepare for ADR acceptance

**Branch**: `sprint/adr0010-sprint-documentation`

---

## Open Questions

1. **Adapter discovery**: How should Rig discover available adapters? Options: importlib metadata, explicit config file, auto-detection by remote URL.
2. **Credential management**: How should forge credentials be stored and secured? Options: environment variables, config file with encryption, external credential helper (git-credential, keyring).
3. **Two-phase promotion**: Should local merge happen before or after forge merge? Current proposal: local merge first, adapter sync second. Alternative: forge merge first, local sync second.
4. **Rollback/revert**: Should adapters support promotion rollback? Should there be a `work_revert.py` command?
5. **Branch naming validation**: Should adapters validate branch names against forge constraints? (GitHub: no leading/trailing hyphens, no consecutive hyphens, etc.)
6. **Self-hosted forge URLs**: How should self-hosted GitLab/Gitea instances be configured?
7. **Offline/airgapped handling**: How should adapters behave when offline? Current: fail gracefully, fall back to local-only warnings.
8. **Mixed adapter modes**: Can a repository have different adapter modes for different operations? (e.g., GitHub for PRs but local-only for promotion)

---

## Files Involved

### New Files (by Sprint)

**Sprint 1:**
- `src/rig/domain/forge/__init__.py`
- `src/rig/domain/forge/local_adapter.py`
- `src/rig/domain/forge/registry.py`
- `tests/forge/test_local_adapter.py`

**Sprint 2:**
- `scripts/repo_bootstrap.py`
- `.rig/config/forge.yaml` (template)
- `tests/forge/test_bootstrap.py`

**Sprint 3:**
- `src/rig/domain/forge/github_adapter.py`
- `tests/forge/test_github_adapter.py`
- `docs/forge/github.md`

**Sprint 4:**
- `src/rig/domain/forge/gitlab_adapter.py`
- `tests/forge/test_gitlab_adapter.py`
- `docs/forge/gitlab.md`

**Sprint 5:**
- `src/rig/domain/forge/gitea_adapter.py`
- `tests/forge/test_gitea_adapter.py`
- `docs/forge/gitea.md`

### Modified Files

- `scripts/work_promote.py` — Add `--forge` flag, adapter integration
- `docs/workflow/adr-sprint-mission-evidence.md` — Add forge abstraction section
- `docs/adr/README.md` — Add ADR 0010 to table
- `.gitignore` — Add `.rig/config/forge.yaml` if it contains sensitive data

---

## Sprint 001 Mission Implementation Status

### Sprint Forge Adapter Contract 001 - Missions 1-5

**Mission 1: Forge Adapter Contract Skeleton** — COMPLETED
- Created `src/rig/domain/forge.py` with domain types (ForgeMode, PromotionMode, ForgeIdentity, etc.)
- Created `src/rig/commands_forge.py` with CLI integration
- Created comprehensive tests in `tests/test_repository_forge.py`

**Mission 2: Reviewability Budget Detector** — COMPLETED
- Added `ReviewabilityBudget` and `ReviewabilityReport` dataclasses
- Added `git_merge_base()` and `git_changed_files()` Git helpers
- Added `build_reviewability_report()` function
- Integrated reviewability detector into `rig forge doctor` CLI

**Mission 3: Local Promotion Dry-Run Planner** — COMPLETED
- Added `PromotionPlanStep` and `PromotionPlan` dataclasses
- Added `build_promotion_plan()` function
- Added `rig forge promote --dry-run` subcommand
- All functions are read-only, no Git mutation

**Mission 4: Enforce Forge Promotion Gates in Agent Workflow** — COMPLETED
- Added `--skip-forge-gates` flag to `work_handoff.py`
- Enforced forge readiness checks in `work_handoff.py` before `ready_for_review`
- Added forge gate evidence recording in handoff events
- Added validation in `work_doctor.py` for forge gate evidence
- Added forge readiness display in `work_status.py`
- Updated workflow docs with ADR 0010 requirements

**Mission 5: Promotion Branch + PR Draft Planner** — COMPLETED
- Added `PromotionDraft` dataclass with: promotion_branch, base_ref, head_ref, title, body, provider_command, provider_url_hint, draft_only
- Added `derive_promotion_branch_name()` — pure function, deterministic Git-ref-safe branch naming
- Added `build_promotion_draft()` — pure function, builds PR/MR draft for all forge modes
- Extended `build_promotion_plan()` to include `draft` field
- Extended `rig forge promote --dry-run` output (human and JSON) to include draft information
- Added provider-specific command previews:
  - GitHub: `gh pr create --base <target> --head <promotion_branch> --title "<title>"`
  - GitLab: `glab mr create --base <target> --head <promotion_branch> --title "<title>"`
  - Gitea: URL hint for manual creation
  - Local-only: Comment noting future --apply
  - Unknown: Manual adapter required hint
- Draft body includes: promotion details, reviewability status, forge/promotion mode, validation expectations, blockers, no-mutation statement
- No personal names in generated body (uses project-neutral wording)
- Added 25 new tests for Mission 5 functionality

### Mission 5 No-Mutation Guarantee

- `derive_promotion_branch_name()` — Pure function using string manipulation only
- `build_promotion_draft()` — Pure function using plan/identity data only
- `build_promotion_plan()` — Still read-only, extended to call pure draft builder
- CLI — Displays draft info but does NOT execute any commands
- Explicit statements: `"dry_run_only": true` in JSON, `"Draft Only: Yes"` in human output, `"No Git or remote state was mutated."`

### Mission 5 Out-of-Scope

- `--apply` mode — Deferred to future mission
- Actual PR/MR creation — Deferred (gh pr create, glab mr create not executed)
- Branch creation — Not implemented (--dry-run only)
- Push to remote — Not implemented (--dry-run only)
- Provider adapters — GitHubAdapter, GitLabAdapter, GiteaAdapter still deferred
- Branch protection checks — Adapter-specific, deferred
- CI status verification — Adapter-specific, deferred

---

## Machine-Readable Contract

**This ADR has a machine-readable JSON companion at `docs/adr/0010-repository-forge-bootstrap-and-promotion-abstraction.json`.**

| Aspect | Human-Readable (Markdown) | Machine-Readable (JSON) |
|--------|-------------------------|-------------------------|
| **Purpose** | Explains the WHY: rationale, context, architectural decisions | Tells Rig WHAT to do: contracts, workflows, constraints |
| **Authority** | Rationale authority — the source of truth for understanding | Contract authority — the source of truth for automation |
| **Format** | Free-form Markdown prose | Structured JSON validated against `docs/schemas/rig-adr.schema.json` |

**Key Principle**: The Markdown explains the architectural rationale and must remain human-readable. The JSON contract enables Rig and external tools to parse, validate, and execute against this ADR programmatically. The JSON must conform to the schema; the Markdown must explain the thinking.

**Contract Fields:**
- `adr_id`: `adr0010` — canonical identifier
- `slug`: `repository-forge-bootstrap-and-promotion-abstraction` — derived from title
- `workflow.worktree_name`: `adr0010-repository-forge-bootstrap-and-promotion-abstraction` — canonical worktree directory
- `workflow.ledger_path`: `.rig/work/adr/adr0010-repository-forge-bootstrap-and-promotion-abstraction` — ADR-local ledger
- `workflow.sprint_branch`: `sprint/adr0010-repository-forge-bootstrap-and-promotion-abstraction` — default sprint branch
- `workflow.promotion_branch`: `promotion/adr0010-repository-forge-bootstrap-and-promotion-abstraction` — promotion target
- `workflow.mission_branch_prefix`: `agent/adr0010-` — prefix for mission branches
- `authority_boundaries` — constraints agents must not cross
- `sprints` — implementation sprints with missions
- `validation_gates` — the 13 forge-neutral gates plus optional forge-specific gates
- `related_adrs` — dependencies and relationships

**Validation**: Run `python3 -m pytest -q tests/test_rig_adr_contracts.py` to validate this ADR's JSON contract against the schema.

**For new ADRs**: Create both `.md` and `.json` companions. The Markdown is for humans; the JSON is for machines. Do not delete the Markdown. Do not make tests depend on Markdown prose (except for existence checks).
