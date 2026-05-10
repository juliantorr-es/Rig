# Troubleshooting Rig

> **Goal: A new contributor should know what to run when something breaks, how to interpret failures, and where governance failures surface.**

This document covers operational debugging ergonomics for Rig. Follow the flowcharts below to diagnose and resolve issues.

---

## Quick Diagnosis Flowchart

```
Something is wrong?
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│  What kind of problem do you have?                         │
├─────────────────────────────────────────────────────────────┤
│                                                                 │
│  Command not found? ───────────────────────────────▶ Installation │
│                                                                 │
│  Python version error? ────────────────────────────▶ Python    │
│                                                                 │
│  Test failures? ───────────────────────────────────▶ Tests      │
│                                                                 │
│  Replay issues? ───────────────────────────────────▶ Replay     │
│                                                                 │
│  Doctor findings? ─────────────────────────────────▶ Doctor    │
│                                                                 │
│  UI not working? ───────────────────────────────────▶ UI        │
│                                                                 │
│  Projection issues? ──────────────────────────────▶ Projections │
│                                                                 │
└─────────────────────────────────────────────────────────────┘
```

---

## 1. Installation Issues

### Command not found: `rig`

**Symptoms:**
```bash
$ rig --help
zsh: command not found: rig
```

**Diagnosis and Fix:**

1. **Check if installed:**
   ```bash
   python -m rig --help
   ```
   If this works, the package is installed but not in PATH.

2. **Check Python version:**
   ```bash
   python --version
   # Must be 3.14+
   ```

3. **Reinstall in development mode:**
   ```bash
   cd /path/to/Rig
   python3.14 -m venv .venv
   source .venv/bin/activate
   python -m pip install -e ".[ui,dev]"
   ```

4. **Verify:**
   ```bash
   which rig  # Should show path to rig binary
   rig --help
   ```

### Python version too old

**Symptoms:**
```bash
$ python -m rig --help
Error: Rig requires Python 3.14 or newer
```

**Diagnosis and Fix:**

1. **Check current version:**
   ```bash
   python --version
   ```

2. **Install Python 3.14:**
   - macOS (Homebrew): `brew install python@3.14`
   - Linux: Use your distribution's package manager or pyenv
   - Windows: Download from python.org

3. **Verify:**
   ```bash
   python3.14 --version
   ```

4. **Reinstall Rig with correct Python:**
   ```bash
   python3.14 -m venv .venv
   source .venv/bin/activate
   python -m pip install -e ".[ui,dev]"
   ```

### Import errors

**Symptoms:**
```bash
$ python -m rig --help
ImportError: cannot import name 'X' from 'module'
```

**Diagnosis and Fix:**

1. **Run syntax check:**
   ```bash
   python3.14 -m compileall -q src tests
   ```

2. **Check for circular imports:**
   ```bash
   python -c "from rig.domain.workspace import Workspace"
   ```

3. **Reinstall dependencies:**
   ```bash
   python -m pip uninstall rig -y
   python -m pip install -e ".[ui,dev]"
   ```

---

## 2. Python Environment Issues

### Wrong Python interpreter active

**Symptoms:**
```bash
$ python --version
Python 3.13.0  # Wrong!
$ python -m rig doctor all
Error: Rig requires Python 3.14+
```

**Diagnosis and Fix:**

1. **Activate correct venv:**
   ```bash
   source .venv/bin/activate
   ```

2. **Or use explicit Python:**
   ```bash
   python3.14 -m rig doctor all
   ```

3. **Check venv Python version:**
   ```bash
   .venv/bin/python --version
   ```

---

## 3. Test Failures

### Replay tests failing

**Symptoms:**
```bash
$ python -m pytest tests/test_replay.py -v
===== FAILED tests/test_replay.py::test_clean_workspace_lifecycle_replay
```

**Diagnosis and Fix:**

1. **Run specific failing test:**
   ```bash
   python -m pytest tests/test_replay.py::test_clean_workspace_lifecycle_replay -v
   ```

2. **Check for deterministic ordering issues:**
   ```bash
   python -m pytest tests/test_replay.py::TestReplayDeterminism -v
   ```

3. **Validate determinism manually:**
   ```python
   from rig.domain.replay import replay_workspace_lifecycle, ReplayResult
   # Run replay twice, compare results
   ```

4. **Common causes:**
   - Non-deterministic hashing (check `hash()` usage)
   - Mutable default arguments
   - Time-based values without `utc_now()`
   - Missing `frozen=True` on dataclasses

### Integrity tests failing

**Symptoms:**
```bash
$ python -m pytest tests/test_integrity.py -v
===== FAILED tests/test_integrity.py::test_workspace_validation_deterministic
```

**Diagnosis and Fix:**

1. **Run doctor to see current findings:**
   ```bash
   python -m rig doctor all
   ```

2. **Check specific validation:**
   ```bash
   python -m pytest tests/test_integrity.py::TestGoldenDeterminism -v
   ```

3. **Common causes:**
   - Workspace record has invalid status transition
   - Receipt chain has gaps
   - Audit events reference non-existent receipts

### Projection contract tests failing

**Symptoms:**
```bash
$ python -m pytest tests/test_projection_contracts.py -v
===== FAILED tests/test_projection_contracts.py::test_projection_widget_types_match_contracts
```

**Diagnosis and Fix:**

1. **Check projection contracts:**
   ```bash
   python -m rig doctor projections
   ```

2. **Validate specific projection:**
   ```python
   from rig.domain.replay import build_replay_projection
   from rig.domain.replay import replay_workspace_from_fs
   from pathlib import Path
   
   # Build projection and validate structure
   result = replay_workspace_from_fs(Path("."), "workspace-id")
   projection = build_replay_projection(result)
   ```

3. **Common causes:**
   - Widget expects field not in projection
   - Projection has extra required fields
   - Authority flags not preserved in projection

---

## 4. Doctor Command Failures

### rig doctor all reports issues

**Symptoms:**
```bash
$ python -m rig doctor all
Rig Integrity Check - All
Overall Status: FAILED
Integrity Score: 0.85
Total Findings: 3
```

**Diagnosis and Fix:**

1. **Save full output for inspection:**
   ```bash
   python -m rig doctor all --json > doctor.json
   ```

2. **Examine findings:**
   ```bash
   cat doctor.json | python -m json.tool
   ```

3. **Common findings and resolutions:**

   | Finding Type | Severity | Resolution |
   |--------------|----------|-------------|
   | Missing receipt | Warning | Create missing receipt or update workspace record |
   | Orphaned audit event | Warning | Fix receipt reference or remove audit event |
   | Invalid transition | Error | Correct workspace status history |
   | Stale receipt chain | Error | Rebuild receipt chain |

4. **Force re-validation:**
   ```bash
   rm -rf .build/rig/doctor_cache.json  # If cache exists
   python -m rig doctor all
   ```

### rig doctor projections reports drift

**Symptoms:**
```bash
$ python -m rig doctor projections
Projection contract drift detected
```

**Diagnosis and Fix:**

1. **Identify drifting widget:**
   ```bash
   python -m rig doctor projections --json | grep -A5 "drift"
   ```

2. **Check widget contract:**
   - Widget file: `src/rig_tools/static/js/widgets/<widget>.js`
   - Expected fields: Check widget's data contract comment

3. **Check projection output:**
   ```python
   from rig.domain.projection import build_workspace_projection
   # Inspect actual projection structure
   ```

4. **Common causes:**
   - Widget added required field not in projection
   - Projection stopped including field widget needs
   - Field name changed in projection

---

## 5. Replay Issues

### Replay produces unexpected results

**Symptoms:**
```bash
$ python -m rig replay workspace my-workspace --summary
Replay: Workspace my-workspace
  State: partial
  Total frames: 3
  Current status: executed
  Expected: validated
```

**Diagnosis and Fix:**

1. **Inspect replay with full output:**
   ```bash
   python -m rig replay workspace my-workspace --json
   ```

2. **Check for findings:**
   ```bash
   python -m rig replay workspace my-workspace --json | grep -A10 "findings"
   ```

3. **Check receipt chain:**
   ```bash
   ls -la .build/rig/receipts/ | grep my-workspace
   ```

4. **Load and inspect receipts:**
   ```python
   from rig.domain.receipt_envelope import read_receipt
   from pathlib import Path
   
   receipt_dir = Path(".build/rig/receipts")
   for f in receipt_dir.glob("*.json"):
       envelope = read_receipt(f)
       if envelope and "my-workspace" in str(envelope.subject):
           print(f"{f.name}: {envelope.receipt_type} -> {envelope.decision}")
   ```

5. **Common causes:**
   - Missing receipt in chain
   - Corrupted receipt file
   - Incorrect status in receipt
   - Audit event with wrong workspace_id

### Replay timeline is empty

**Symptoms:**
```bash
$ python -m rig replay timeline --json
{"type": "timeline_all", "total_events": 0, "workspaces": {}}
```

**Diagnosis and Fix:**

1. **Check if receipts exist:**
   ```bash
   ls .build/rig/receipts/*.json 2>/dev/null | wc -l
   ls .build/rig/audit/*.json 2>/dev/null | wc -l
   ```

2. **Check if workspaces exist:**
   ```bash
   ls .build/rig/workspaces/*.json 2>/dev/null | wc -l
   ```

3. **If no files, you need to create a workspace first:**
   ```bash
   python -m rig workspace create my-workspace
   ```

4. **If files exist but not loaded:**
   ```bash
   # Check file permissions
   ls -la .build/rig/receipts/
   
   # Check file validity
   python -c "import json; json.load(open('.build/rig/receipts/test.json'))"
   ```

### Corrupted replay file

**Symptoms:**
- Replay silently skips files
- Findings mention file corruption

**Diagnosis and Fix:**

1. **Check for corrupted files:**
   ```bash
   python -c "
   import json
   from pathlib import Path
   for f in Path('.build/rig/receipts').glob('*.json'):
       try:
           json.load(open(f))
       except:
           print(f'Corrupted: {f}')
   "
   ```

2. **Remove corrupted file or fix it:**
   ```bash
   # If file is truly corrupted and cannot be recovered:
   mv .build/rig/receipts/corrupted.json .build/rig/receipts/corrupted.json.bak
   
   # Replay will now report missing receipt instead of corruption
   ```

3. **Replay will emit explicit finding:**
   ```bash
   python -m rig replay workspace my-workspace --json
   # Look for "finding_type": "replay_file_corruption"
   ```

---

## 6. UI Issues

### rig ui fails to start

**Symptoms:**
```bash
$ python -m rig ui
Error: pywebview not installed
```

**Diagnosis and Fix:**

1. **Install UI dependencies:**
   ```bash
   python -m pip install -e ".[ui]"
   ```

2. **Check pywebview installation:**
   ```bash
   python -c "import webview; print(webview.__version__)"
   ```

3. **Check platform support:**
   ```bash
   python -c "import webview; print(webview.Windows.get_all())"
   ```

4. **Try browser mode:**
   ```bash
   python -m rig --debug ui --browser
   ```

### UI shows wrong status

**Symptoms:**
- UI shows "active" but workspace is "executed"
- UI shows authoritative evidence when it should be advisory only

**Diagnosis and Fix:**

1. **Check projection output:**
   ```bash
   python -m rig replay workspace my-workspace --json
   ```

2. **Check for projection contract drift:**
   ```bash
   python -m rig doctor projections
   ```

3. **Common causes:**
   - Widget reading wrong field from projection
   - Widget not handling advisory_only flag
   - Projection includes wrong authority state

4. **Widget development rules:**
   - Consume projections ONLY
   - No direct authority inference
   - No side effects
   - Handle missing fields gracefully

---

## 7. Projection Issues

### Projection missing expected fields

**Symptoms:**
```javascript
// In widget
const status = data.workspace_status;  // undefined
```

**Diagnosis and Fix:**

1. **Check projection structure:**
   ```bash
   python -m rig replay workspace my-workspace --json | python -m json.tool | head -50
   ```

2. **Check projection builder:**
   ```python
   from rig.domain.replay import build_replay_projection_summary
   from rig.domain.replay import replay_workspace_from_fs
   from pathlib import Path
   
   result = replay_workspace_from_fs(Path("."), "my-workspace")
   projection = build_replay_projection_summary(result)
   print(projection.keys())
   ```

3. **Check widget contract:**
   - Each widget has a data contract comment at the top
   - Verify widget expects same fields as projection provides

### Projection includes invented data

**Symptoms:**
- Projection shows status not in receipts
- Projection shows receipt IDs not in chain

**Diagnosis and Fix:**

1. **This is a CRITICAL bug** — Projections must never invent data

2. **Check projection builder for state invention:**
   ```python
   # Look for default values that don't trace to source
   # Look for fallback values that aren't placeholders
   ```

3. **Verify determinism:**
   ```python
   # Run build_replay_projection twice with same inputs
   # Compare outputs - should be identical
   ```

4. **Common causes:**
   - Using current time instead of receipt timestamp
   - Using workspace record as fallback without receipt
   - Inventing "sensible defaults"

---

## 8. Governance & Authority Issues

### Authority escalation detected

**Symptoms:**
```bash
$ python -m rig replay workspace my-workspace --json
# Finding: "advisory_escalation" or similar
```

**Diagnosis and Fix:**

1. **This is a CRITICAL bug** — Advisory-only data became authoritative

2. **Check receipt authority flags:**
   ```python
   from rig.domain.receipt_envelope import read_receipt
   from pathlib import Path
   
   for f in Path(".build/rig/receipts").glob("*.json"):
       envelope = read_receipt(f)
       if envelope:
           print(f"{f.name}: authoritative={not envelope.advisory_only}, advisory_only={envelope.advisory_only}")
   ```

3. **Check replay preserves flags:**
   ```python
   from rig.domain.replay import replay_workspace_from_fs
   result = replay_workspace_from_fs(Path("."), "my-workspace")
   for frame in result.frames:
       for event in frame.events:
           print(f"{event.event_id}: authoritative={event.authoritative}, advisory_only={event.advisory_only}")
   ```

4. **Common causes:**
   - ReplayEvent.from_receipt not preserving advisory_only
   - ReplayEvent.from_audit_event not preserving advisory_only
   - Projection including authoritative flag from wrong source

### Impossible transition detected

**Symptoms:**
```bash
$ python -m rig replay workspace my-workspace --json
# Finding: "impossible_transition"
```

**Diagnosis and Fix:**

1. **Check workspace status history:**
   ```bash
   cat .build/rig/workspaces/my-workspace.json | python -m json.tool | grep status_history
   ```

2. **Check allowed transitions:**
   ```python
   from rig.domain.replay import ALLOWED_TRANSITIONS
   print(ALLOWED_TRANSITIONS)
   ```

3. **Valid transitions:**
   ```
   planned -> active
   active -> executed or blocked
   executed -> validated or blocked
   validated -> review_ready or blocked
   review_ready -> applied or blocked
   blocked -> (no transitions)
   applied -> (no transitions)
   ```

4. **Fix workspace record:**
   ```bash
   # Correct the status_history to have valid transitions
   # Then re-run replay
   ```

---

## Debug Bundle

### Creating a debug bundle

When reporting issues, create a debug bundle:

```bash
# Dry-run first to see what will be included
python -m rig debug bundle --dry-run

# Create actual bundle
python -m rig debug bundle --output rig-debug-$(date +%Y%m%d-%H%M%S).zip

# Create with custom output
python -m rig debug bundle --output my-bundle.zip
```

### What's included in debug bundle

- Workspace records (with token redaction)
- Receipt envelopes (with token redaction)
- Audit events
- Replay results
- Doctor findings
- System information (Python version, OS, etc.)

### What's EXCLUDED (redacted)

- API tokens and keys
- Model weights and embeddings
- Private file contents outside .build/rig/
- User-specific configuration

---

## Common Recovery Procedures

### Recovery from corrupted state

1. **Identify corrupted files:**
   ```bash
   python -m rig doctor all --json | grep -i "corrupt\|error\|failed"
   ```

2. **Backup corrupted files:**
   ```bash
   mv .build/rig/receipts/corrupted.json .build/rig/receipts/corrupted.json.bak
   ```

3. **Replay to see impact:**
   ```bash
   python -m rig replay workspace my-workspace --json
   ```

4. **Recreate missing receipts if possible:**
   ```bash
   # This requires understanding what the receipt should contain
   # Consult documentation or ask maintainers
   ```

### Recovery from bad merge

If a bad merge introduced issues:

1. **DO NOT use `git reset --hard`** — This violates Git discipline

2. **Identify the bad commit:**
   ```bash
   git log --oneline -10
   ```

3. **Create a fix commit:**
   ```bash
   git checkout -b fix/bad-merge
   # Make minimal fixes
   git add -p  # Review each change
   git commit -m "Fix: correct bad merge in workspace records"
   git push origin fix/bad-merge
   ```

4. **Open PR for review**

---

## Command Reference

### Validation Commands

| Command | Purpose | When to Run |
|---------|---------|-------------|
| `bash scripts/check.sh` | Full validation | Before PR, CI |
| `python3.14 -m compileall -q src tests` | Syntax check | After any code change |
| `python -m pytest tests/test_replay.py -v` | Replay tests | After replay code changes |
| `python -m pytest tests/test_integrity.py -v` | Integrity tests | After validation code changes |
| `python -m pytest tests/test_projection_contracts.py -v` | Projection tests | After projection changes |
| `python -m rig doctor all` | Full integrity check | Regularly, before PR |
| `python -m rig doctor projections` | Projection validation | After UI changes |
| `python -m rig replay timeline --json` | Replay timeline | After receipt changes |

### Diagnostic Commands

| Command | Purpose | Output |
|---------|---------|--------|
| `rig log list` | List all log entries | Log IDs and summaries |
| `rig log show <id>` | Show specific log | Full log content |
| `rig debug bundle --dry-run` | Preview debug bundle | Included files list |
| `rig debug bundle` | Create debug bundle | ZIP file |
| `rig doctor all --json` | Machine-readable doctor | JSON with all findings |
| `rig replay workspace <id> --json` | Full replay output | JSON with all frames |

### Repair Commands

| Command | Purpose | Effect |
|---------|---------|--------|
| `rig doctor repair --queue` | Repair malformed jobs | Fixes queue state |
| `rig doctor repair --migrate-legacy-queue` | Migrate legacy queue | Updates queue format |

---

## Where Governance Failures Surface

Governance failures (violation of Rig's core doctrine) surface in these locations:

| Failure Type | Detection | Surface Location |
|--------------|-----------|-----------------|
| Authority escalation | Replay validation | `replay.result.findings` |
| Missing receipts | Receipt continuity | `replay.result.findings` |
| Impossible transition | State validation | `replay.result.findings` and `doctor all` |
| Projection drift | Projection validation | `doctor projections` |
| Stale references | Replay validation | `replay.result.findings` |
| Corrupted files | File loading | `replay.result.findings` (explicit) |
| Token exposure | Debug bundle | Redacted in output |

---

## Summary

1. **Start with validation:** `bash scripts/check.sh`
2. **Isolate the problem:** Find which check fails
3. **Check doctor output:** `python -m rig doctor all --json`
4. **Check replay output:** `python -m rig replay workspace <id> --json`
5. **Check logs:** `rig log list`, `rig log show <id>`
6. **Create debug bundle:** `python -m rig debug bundle`
7. **Report issue:** Include bundle, steps to reproduce, expected vs actual

**Remember:**
- **No silent failures** — Rig always produces explicit findings
- **No hidden mutation** — All operations are traceable
- **Replay is source of truth** — If replay shows it, it's real
- **Projections are derived** — If projection shows it wrong, check the source
