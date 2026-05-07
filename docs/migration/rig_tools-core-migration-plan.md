# rig_tools Core Migration Plan

## Overview

This document outlines the plan to migrate all `rig_tools` modules to use the new consolidated `rig_tools.core` utilities and `rig_tools.backends` contracts.

**Status**: Phase 1 Complete (core utilities created, high-priority modules migrated)

---

## Completed Work

### Phase 1: Core Utilities (Commit: `fee827c`)
Created 19 new files in `src/rig_tools/core/` and `src/rig_tools/backends/`:

| Module | Purpose | Lines |
|--------|---------|-------|
| `core/__init__.py` | Public exports | 120 |
| `core/io.py` | JSON/YAML/TOML I/O | 140 |
| `core/process.py` | Subprocess with retry/timeout | 285 |
| `core/filesystem.py` | Atomic ops, file locking | 350 |
| `core/tracing.py` | Observability (Span, Tracer) | 420 |
| `core/errors.py` | RigError hierarchy | 350 |
| `core/config.py` | Configuration management | 400 |
| `backends/ml/base.py` | ML backend contract | 190 |
| `backends/ml/mlx.py` | MLX implementation | 240 |
| `backends/ml/llama_cpp.py` | LlamaCpp implementation | 250 |
| `backends/vcs/base.py` | VCS backend (Git) | 550 |
| `backends/storage/base.py` | Storage backend contract | 190 |
| `backends/storage/json_file.py` | JSON file storage | 130 |
| `backends/storage/sqlite.py` | SQLite storage | 200 |

### Phase 2: High-Priority Refactoring (Commit: `b3cf266`)
Migrated 9 files, net reduction of 119 lines:

| Module | Changes | Lines Reduced |
|--------|---------|---------------|
| `atomic_io.py` | Deprecated, wraps `core.io.write_json` + `core.filesystem` | -48 |
| `file_lock.py` | Deprecated, wraps `core.filesystem.locked()` | -49 |
| `action_manifest.py` | Uses `run_capture`, `read_json`, `write_json` | -45 |
| `agent_discovery.py` | Uses `run_capture`, `write_json` | -32 |
| `agent_launcher.py` | Uses `run`, `run_capture`, `read_json`, `write_json` | -120 |
| `settings_store.py` | Uses `read_json`, `write_json`, `read_toml`, `write_toml`, `ensure_dir` | -150 |
| `state_store.py` | Uses `SQLiteBackend`, `ensure_dir` | -100 |
| `work_queue.py` | Uses `read_json`, `write_json` | -23 |
| `workspace_governance.py` | Uses `run_capture`, `read_json`, `write_json`, `ensure_dir` | -35 |
| **Total** | | **-702** |

---

## Migration Targets

### Priority 1: Subprocess Calls (High ROI)
**40 occurrences across ~25 files**

These calls lack consistent error handling, tracing, and timeout management.

#### Migration Pattern
```python
# Before:
result = subprocess.run(cmd, cwd=cwd, text=True, capture_output=True, check=False, timeout=timeout)

# After:
from rig_tools.core import run_capture
result = run_capture(cmd, cwd=cwd, timeout=timeout)

# Benefits:
# - Automatic error wrapping with RigProcessError
# - Span tracing with timing
# - Consistent stdout/stderr handling
# - Breadcrumb logging on errors
```

#### Files to Migrate

| File | subprocess.run Count | Priority | Notes |
|------|---------------------|----------|-------|
| `mlx_local.py` | 10+ | HIGH | ML model operations |
| `doctor.py` | 8+ | HIGH | Diagnostic commands |
| `monitor.py` | 6+ | HIGH | Monitoring operations |
| `scheduler.py` | 5+ | HIGH | Scheduler job execution |
| `notifications.py` | 3 | MEDIUM | Notification delivery |
| `provider_credentials.py` | 3 | MEDIUM | Credential management |
| `cache_metadata.py` | 2 | MEDIUM | Cache operations |
| `session_bundle.py` | 2 | MEDIUM | Session bundling |
| `worktree_manager.py` | 1 | MEDIUM | Worktree operations |
| `runtime_executor.py` | 1 | MEDIUM | Runtime execution |
| `action_manifest.py` | ✓ DONE | - | Already migrated |
| `agent_discovery.py` | ✓ DONE | - | Already migrated |
| `agent_launcher.py` | ✓ DONE | - | Already migrated |

#### Estimated Effort
- **Time**: 1-2 hours
- **Lines reduced**: ~200-300
- **Benefit**: Consistent error handling + observability for all external commands

---

### Priority 2: JSON I/O (Medium ROI)
**232 occurrences across ~60 files**

Custom JSON serialization lacks orjson fallback and consistent error handling.

#### Migration Pattern
```python
# Before:
import json
data = json.loads(path.read_text())
path.write_text(json.dumps(data, indent=2))

# After:
from rig_tools.core.io import read_json, write_json
data = read_json(path)
write_json(path, data)

# Benefits:
# - orjson speedup when available
# - Fallback to stdlib json
# - Error wrapping
# - Consistent formatting (indent=2, sort_keys=True)
```

#### Files to Migrate (Sample)

| File | JSON Count | Priority |
|------|------------|----------|
| `llama_cpp_local.py` | 20+ | HIGH |
| `mlx_local.py` | 15+ | HIGH |
| `anigma_loop.py` | 12+ | MEDIUM |
| `supervisor_loop.py` | 10+ | MEDIUM |
| `orchestration.py` | 8+ | MEDIUM |
| `gc.py` | 8+ | MEDIUM |
| `project_digest.py` | 6+ | MEDIUM |
| `execution_engine.py` | 5+ | MEDIUM |
| `result_index.py` | 5+ | MEDIUM |
| `contract_audit.py` | 5+ | MEDIUM |

#### Estimated Effort
- **Time**: 2-3 hours
- **Lines reduced**: ~300-400
- **Benefit**: Performance (orjson) + consistency

---

### Priority 3: Directory Creation (Low-Medium ROI)
**108 occurrences across ~50 files**

Manual directory creation can be replaced with `ensure_dir()`.

#### Migration Pattern
```python
# Before:
path.parent.mkdir(parents=True, exist_ok=True)

# After:
from rig_tools.core.filesystem import ensure_dir
ensure_dir(path.parent)

# Benefits:
# - Handles edge cases (existing dirs, permissions)
# - Consistent error handling
# - Returns Path object
```

#### Estimated Effort
- **Time**: 30-60 minutes (do when already touching files)
- **Lines reduced**: ~50-100
- **Benefit**: Low - mostly consistency

---

### Priority 4: Custom Retry Loops (High ROI)
**Unknown count - need to identify**

Custom retry logic should use `@retry` decorator.

#### Migration Pattern
```python
# Before:
for attempt in range(3):
    try:
        return do_thing()
    except Exception as e:
        time.sleep(1)
        if attempt == 2:
            raise

# After:
from rig_tools.core.process import retry, RetryConfig

@retry(RetryConfig(max_attempts=3, delay=1.0))
def do_thing():
    ...

# Benefits:
# - Exponential backoff
# - Configurable retry conditions
# - Tracing integration
# - Error context preservation
```

#### Estimated Effort
- **Time**: 30-60 minutes to find and replace
- **Lines reduced**: ~100-200
- **Benefit**: High - proven retry logic with tracing

---

## Migration Strategy

### Approach
1. **Batch by pattern, not by file** - Migrate all `subprocess.run()` calls first, then JSON, then mkdir
2. **Preserve behavior** - Don't change logic, only the underlying utilities
3. **Add imports at top** - Group all `rig_tools.core` imports together
4. **Test incrementally** - Verify each file after migration
5. **Use deprecation for disruptive changes** - If interface changes significantly

### File Categorization

#### Tier A: High Impact, Low Risk (Do First)
- Files with `subprocess.run()` calls
- Files with retry loops
- Domain modules that use rig_tools (not rig_tools consuming rig_tools)

#### Tier B: Medium Impact, Medium Risk
- Files with custom JSON/YAML/TOML handling
- Files with directory creation patterns

#### Tier C: Low Impact, Low Risk (Do Last or Skip)
- Simple `mkdir()` calls in already-stable files
- One-off subprocess calls with good error handling already

---

## Execution Plan

### Week 1: Subprocess Migration
**Goal**: Migrate all `subprocess.run()` calls

1. **mlx_local.py** (10+ calls)
   - High priority - ML model operations
   - Replace with `run`, `run_capture`, `run_check`
   - Add timeout to all calls

2. **doctor.py** (8+ calls)
   - High priority - Diagnostic commands
   - Replace with `run_capture`
   - Add timeout=30s to all calls

3. **monitor.py** (6+ calls)
   - High priority - Monitoring operations
   - Replace with `run_capture`

4. **scheduler.py** (5+ calls)
   - High priority - Scheduler job execution
   - Replace with `run_capture`

5. **notifications.py** (3 calls)
   - Medium priority
   - Replace with `run`

6. **provider_credentials.py** (3 calls)
   - Medium priority
   - Replace with `run`

7. **Remaining files** (10+ calls across ~10 files)
   - Batch migrate

**Testing**: Run `python3 -m pytest` (if tests exist) or smoke test each module

### Week 2: JSON I/O Migration
**Goal**: Migrate all custom JSON handling

1. **llama_cpp_local.py** (20+ calls)
2. **mlx_local.py** (15+ calls)
3. **anigma_loop.py** (12+ calls)
4. **supervisor_loop.py** (10+ calls)
5. **orchestration.py** (8+ calls)
6. **gc.py** (8+ calls)
7. **project_digest.py** (6+ calls)
8. **execution_engine.py** (5+ calls)
9. **result_index.py** (5+ calls)
10. **contract_audit.py** (5+ calls)

**Testing**: Verify JSON files read/write correctly

### Week 3: Directory Creation + Retry Loops
**Goal**: Migrate remaining patterns

1. Identify all custom retry loops
2. Replace with `@retry` decorator
3. Replace remaining `mkdir()` calls with `ensure_dir()`

**Testing**: Verify functionality unchanged

---

## Success Metrics

| Metric | Current | Target | Status |
|--------|---------|--------|--------|
| Files using `subprocess.run()` | ~25 | 0 | In Progress |
| Files using custom JSON I/O | ~60 | 0 | Not Started |
| Files using manual `mkdir()` | ~50 | 0 | Not Started |
| Lines of duplicate code | ~1500 | < 500 | In Progress |
| Modules with tracing | 19 | 100+ | In Progress |

---

## Benefits Summary

### Immediate Benefits (After Full Migration)

1. **Debugging**
   - All operations emit traces with timing
   - Error context automatically preserved
   - Breadcrumb trails for complex operations
   - `get_tracer().get_trace()` shows full operation history

2. **Error Handling**
   - Consistent `RigError` hierarchy
   - Structured error metadata
   - Automatic context capture
   - Better error messages for users

3. **Performance**
   - orjson for JSON (when available)
   - Connection pooling for storage backends
   - Efficient subprocess execution

4. **Maintenance**
   - Single point of fix for bugs
   - Consistent API surface
   - Easier testing
   - Better documentation

### Long-Term Benefits

1. **New Feature Development**
   - Add features once (timeouts, retries, logging)
   - Swap implementations easily
   - Example: Switch from subprocess to asyncio with one change

2. **Observability Platform**
   - Foundation for metrics collection
   - Structured logging integration
   - Distributed tracing readiness
   - Performance monitoring

3. **Team Scalability**
   - Reduced cognitive load
   - Fewer patterns to learn
   - Better code reviews
   - Easier onboarding

---

## Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Breaking existing behavior | Low | High | Preserve interfaces, add deprecation warnings |
| Import cycles | Medium | Medium | Add imports lazily where needed |
| Performance regression | Low | Medium | Benchmark before/after, use orjson |
| Testing gaps | Medium | Medium | Add integration tests for core utilities |
| Merge conflicts | Medium | Low | Coordinate with team, batch changes |

---

## Checklists

### Pre-Migration
- [ ] Back up current state
- [ ] Ensure all tests pass
- [ ] Document current behavior
- [ ] Identify file owners (if applicable)

### During Migration
- [ ] Migrate one pattern at a time
- [ ] Test each file after changes
- [ ] Keep commits atomic
- [ ] Add deprecation warnings for breaking changes

### Post-Migration
- [ ] Run full test suite
- [ ] Smoke test in real environment
- [ ] Monitor error rates
- [ ] Update documentation
- [ ] Remove deprecated modules (in future release)

---

## Related Documents

- [Core Utilities Documentation](docs/dev/core-utilities.md) *(to be created)*
- [Backend Contracts Documentation](docs/dev/backend-contracts.md) *(to be created)*
- [Tracing and Observability Guide](docs/dev/tracing.md) *(to be created)*

---

## Appendix: File-by-File Migration Notes

### mlx_local.py
- **Pattern**: Heavy subprocess usage for ML commands
- **Action**: Replace all `subprocess.run()` with `run()` or `run_capture()`
- **Timeout**: Add 30-60s timeout to all ML commands
- **Tracing**: Add `trace_context` for long-running operations
- **Lines**: ~10 subprocess calls, ~20 JSON calls

### doctor.py
- **Pattern**: Diagnostic subprocess commands
- **Action**: Replace with `run_capture()`, most don't need check=True
- **Timeout**: 10-15s for most commands
- **Lines**: ~8 subprocess calls

### monitor.py
- **Pattern**: Monitoring subprocess commands
- **Action**: Replace with `run_capture()`
- **Lines**: ~6 subprocess calls

### scheduler.py
- **Pattern**: Job execution subprocess commands
- **Action**: Replace with `run()` or `run_capture()`
- **Important**: Preserve stdout/stderr capture for job logging
- **Lines**: ~5 subprocess calls

### notifications.py
- **Pattern**: Notification deliverycommands
- **Action**: Replace with `run()`, don't capture output for fire-and-forget
- **Lines**: ~3 subprocess calls

### provider_credentials.py
- **Pattern**: Security/keychain commands
- **Action**: Replace with `run()`, capture errors
- **Important**: macOS-specific, may need conditional logic
- **Lines**: ~3 subprocess calls

---

## Revision History

| Date | Author | Changes |
|------|--------|---------|
| 2025-01-XX | Mistral Vibe | Initial plan created |
