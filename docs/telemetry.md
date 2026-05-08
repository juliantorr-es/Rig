# Telemetry Transparency

> **Inspectable, explicit, technically honest.**

This document provides complete transparency about Rig's telemetry, data export, and network behavior. It describes what data exists, what may leave the machine, and what absolutely does not.

## Philosophy

Rig's telemetry philosophy is built on three pillars:

1. **Local First** — Core governance operates entirely offline
2. **Explicit Export** — Any data that leaves the machine must be explicitly requested by the user
3. **Inspectable** — Users can see exactly what would be exported before it leaves

### Core Doctrine

> "If the user didn't explicitly ask for it to leave, it stays on the machine."

This means:
- **No automatic telemetry** — No phone-home, no usage tracking by default
- **No implicit exports** — No data leaves without explicit user action
- **No surprises** — Network operations are always user-initiated
- **Inspectable** — All outbound data is visible to the user

## Data Classification

Rig classifies all data into one of four categories:

| Category | Export Status | User Control | Example |
|----------|---------------|--------------|---------|
| **Local-only** | NEVER exported | N/A | Receipts, Git history, workspace state |
| **Inspectable outbound** | MAY be exported | Explicit command | `--json` output, debug bundles |
| **Forbidden** | NEVER exported | N/A | Tokens, prompts, model responses |
| **Future optional** | Paused | Opt-in only (not implemented) | Usage metrics, error reports |

## What Stays Local

These data types **never leave the machine** under any circumstances in the current implementation:

### Canonical Evidence

| Data Type | Storage | Retention | Export |
|-----------|---------|----------|--------|
| Receipt envelopes | DuckDB (workspace-local) | Permanent | ❌ Never |
| Audit events | DuckDB (workspace-local) | Permanent | ❌ Never |
| Receipt signatures | Filesystem (workspace) | Permanent | ❌ Never |
| Workspace metadata | Filesystem (workspace) | Permanent | ❌ Never |
| Intent definitions | DuckDB (workspace-local) | Until applied/archived | ❌ Never |

### Code and Configuration

| Data Type | Storage | Export |
|-----------|---------|--------|
| Repository source code | Git | ❌ Never |
| `pyproject.toml` | Filesystem | ❌ Never |
| Rig configuration files | Filesystem | ❌ Never |
| Git history | `.git` directory | ❌ Never |
| Git worktree contents | Filesystem | ❌ Never |

### State and Projections

| Data Type | Storage | Export |
|-----------|---------|--------|
| Replay results | Memory (from L0) | ❌ Never |
| Projection state | Memory (from L1) | ❌ Never |
| Validation findings | Memory | ❌ Never |
| Doctor results | Memory | ❌ Never |

### User Data

| Data Type | Storage | Export |
|-----------|---------|--------|
| Prompts to models | Provider-dependent | ❌ Never (Rig doesn't store) |
| Model responses | Provider-dependent | ❌ Never (Rig doesn't store) |
| Conversation history | N/A (Rig doesn't store) | ❌ Never |
| File edits | Git worktrees | ❌ Never |

## What May Be Exported (User-Controlled)

These are the **only** ways data can leave the machine, and **all require explicit user action**:

### JSON Output

**Command:** `python -m rig <command> --json`

**What's exported:** Structured JSON representation of command output

**Example commands:**
```bash
python -m rig replay timeline --json
python -m rig doctor all --json
python -m rig doctor projections --json
python -m rig workspace status --json
```

**What's included:**
- Replay timeline (receipt metadata only, no content)
- Projection state (backend-authored display data)
- Doctor findings (integrity scores, findings)
- Workspace status (state summary)

**What's red acted:**
- File contents
- Git history details
- Tokens/credentials
- Full receipt JSON (only metadata summaries)

**User control:** User must explicitly add `--json` flag

### Debug Bundles

**Command:** `python -m rig debug bundle`

**What's exported:** A ZIP archive containing diagnostic information

**What's included:**
- Rig version
- Python version
- Platform information (OS, architecture)
- Configuration summary (paths redacted)
- Recent rig commands (from history file)
- Doctor output
- Replay timeline summary
- Projection state snapshot

**What's red acted:**
- All file paths (normalized and hashed)
- Usernames
- Hostnames
- IP addresses
- Tokens/credentials
- Repository content
- Full receipt content
- Prompt history
- Model responses

**User control:** User must explicitly run the command

**Available flags:**
- `--dry-run` — Show what would be included without creating bundle
- `--output FILE` — Specify output file

**Example:**
```bash
# See what would be included
python -m rig debug bundle --dry-run

# Create a redacted bundle for support
python -m rig debug bundle --output rig-debug.zip
```

### Log Files

Rig does not currently write persistent log files. If implemented in the future:

- Logs will be **local-only by default**
- No sensitive data will be written to logs
- Log rotation will prevent unbounded disk usage

## What is Explicitly Forbidden

These data types **will never** be exported by Rig, under any circumstances:

| Category | Data Type | Reason |
|----------|-----------|--------|
| **Secrets** | API keys, tokens, credentials | Security policy |
| **Authentication** | Passwords, session tokens | Security policy |
| **Prompts** | User prompts to AI models | Privacy, intellectual property |
| **Model output** | Raw model responses | Privacy, intellectual property |
| **File contents** | Source code, documents | Privacy, intellectual property |
| **System identifiers** | Hostname, IP, MAC addresses | Privacy |
| **User identifiers** | Username, email, real name | Privacy |
| **Full receipts** | Complete receipt JSON | Contains potentially sensitive metadata |

### Redaction Rules

Rig applies redaction to all potentially sensitive data:

| Data Type | Redaction Method | Example |
|-----------|------------------|---------|
| File paths | Hashed or normalized | `/home/user/project` → ` sha256:abc123` |
| Usernames | Replaced with `[REDACTED]` | `alice` → `[REDACTED]` |
| Hostnames | Replaced with `[REDACTED]` | `my-machine` → `[REDACTED]` |
| IP addresses | Replaced with `[REDACTED]` | `192.168.1.1` → `[REDACTED]` |
| Tokens | Replaced with `[TOKEN REDACTED]` | `sk-...` → `[TOKEN REDACTED]` |
| API keys | Replaced with `[API KEY REDACTED]` | Any key format → `[API KEY REDACTED]` |
| Prompts | Not stored, not logged | N/A |
| Model responses | Not stored, not logged | N/A |

## Trust Boundaries

Rig enforces trust boundaries between its components. Each boundary represents a trust level reduction:

```
┌─────────────────────────────────────────────────────────────┐
│                TRUST LEVEL 0 (Canonical Evidence)               │
│  ┌─────────────────────────────────────────────────────────┐│
│  │ Receipts (DuckDB)                                        ││
│  │ Audit events (DuckDB)                                    ││
│  │ Git history                                              ││
│  │ Workspace state                                          ││
│  └─────────────────────────────────────────────────────────┘│
│  Export: NEVER                                                              │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼ (Deterministic derivation)
┌─────────────────────────────────────────────────────────────┐
│                TRUST LEVEL 1 (Derived State)                  │
│  ┌─────────────────────────────────────────────────────────┐│
│  │ Replay results                                          ││
│  │ Continuity validation                                     ││
│  │ Integrity findings                                        ││
│  └─────────────────────────────────────────────────────────┘│
│  Export: NEVER                                                              │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼ (Projection mapping)
┌─────────────────────────────────────────────────────────────┐
│                TRUST LEVEL 2 (Projections)                    │
│  ┌─────────────────────────────────────────────────────────┐│
│  │ Backend-authored UI data                                ││
│  │ No authority inference                                   ││
│  │ Display-only data                                         ││
│  └─────────────────────────────────────────────────────────┘│
│  Export: ONLY via --json flag (user-initiated)               │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼ (Rendering)
┌─────────────────────────────────────────────────────────────┐
│                TRUST LEVEL 3 (frontend)                        │
│  ┌─────────────────────────────────────────────────────────┐│
│  │ dumb renderer                                            ││
│  │ No state invention                                        ││
│  │ No authority inference                                    ││
│  └─────────────────────────────────────────────────────────┘│
│  Export: NEVER                                                              │
└─────────────────────────────────────────────────────────────┘

Invariant: Trust NEVER increases when moving down levels.
         Data export is ONLY possible at L2 with --json flag.
```

## Network Behavior Classification

### Offline-Only Operations (No Network)

These operations **never** make network requests:

| Category | Operations | Networks Access |
|----------|------------|-----------------|
| **Core Governance** | Workspace create, intent exec, validation, apply | ❌ None |
| **Receipt System** | Receipt creation, signing, validation, chain verification | ❌ None |
| **Replay** | Timeline replay, workspace replay | ❌ None |
| **Doctor** | All doctor commands | ❌ None |
| **Projections** | All projection generation | ❌ None |
| **Governance Engine** | All legality checks | ❌ None |
| **Testing** | All pytest suites | ❌ None |

### User-Initiated Network Operations

These operations **may** make network requests **only when explicitly triggered by the user**:

| Operation | Trigger | Purpose | Data Sent | Data Received |
|-----------|---------|---------|-----------|---------------|
| `rig debug bundle` | Explicit command | Create support archive | None (local-only) | None |
| `--json` flag | Explicit flag | Export structured data | See above | None |
| Provider integration | `--provider` flag | Send to external AI | User-provided only | Model response |
| Git operations | Implicit (Git) | Version control | Git protocol | Git data |

**Important:** Git operations are the exception — they use the Git protocol to fetch/push repository data. This is standard Git behavior, not Rig telemetry.

### Forbidden Network Operations

These operations are **never** performed by Rig:

| Operation | Reason |
|-----------|--------|
| Automatic version checks | No phone-home |
| Automatic update downloads | No auto-update |
| Usage metric collection | No telemetry by default |
| Error reporting | No auto-report |
| Crash reporting | No auto-report |
| Analytics | No tracking |
| Ad fetching | No advertising |
| Documentation auto-fetch | Paused (future may be opt-in) |

## Provider Integration Model

Rig can integrate with external AI providers through the `--provider` flag. This integration follows strict principles:

### Principles

1. **User-Initiated Only** — Provider calls are never automatic
2. **Minimal Data** — Only what the user explicitly provides is sent
3. **Untrusted Output** — All provider output is treated as malicious until validated
4. **No Auto-Apply** — Provider output must go through governance gates
5. **No Persistence** — Rig does not store prompts or responses (provider may)

### Data Flow

```
User Input (prompt, task description)
         │
         ▼
┌─────────────────────────┐
│   Rig Governance Engine │ ◄── Deny-by-default
└─────────────────────────┘
         │
         ▼ (Explicit --provider flag)
┌─────────────────────────┐
│   Provider Integration   │
│   - Sends: User input    │
│   - Receives: Model out  │
└─────────────────────────┘
         │
         ▼
┌─────────────────────────┐
│   Provider Response       │ ◄── TREATED AS UNTRUSTED
└─────────────────────────┘
         │
         ▼
┌─────────────────────────┐
│   Receipt Creation        │ ◄── Immutable record of intent
└─────────────────────────┘
         │
         ▼
┌─────────────────────────┐
│   Validation Gate        │ ◄── Must pass before apply
└─────────────────────────┘
         │
         ▼
┌─────────────────────────┐
│   Review & Apply         │ ◄── User must explicitly approve
└─────────────────────────┘
```

### What Rig Sends to Providers

Rig sends **only** what the user explicitly provides in the command:

```bash
# User provides: --provider custom-command --task "write hello world"
# Rig sends: Only "write hello world" (the task description)

# User provides: --provider custom-command --prompt "Implement feature X"
# Rig sends: Only "Implement feature X" (the prompt)
```

**Rig does NOT send:**
- Repository content (unless explicitly referenced by user)
- File contents (unless explicitly referenced by user)
- Git history
- Receipts
- Configuration files
- Environment variables
- System information

### What Rig Receives from Providers

Rig receives whatever the provider returns, which is **treated as untrusted**:

- Model-generated code
- Model-generated text
- Model-generated suggestions
- Error messages from provider

All received data:
1. Is stored in a receipt as an **intent** (not applied)
2. Must pass validation gates
3. Must be explicitly reviewed and approved
4. Can be replayed for audit

## Dataset and Training Posture

### Rig's Stance

**Rig does not train models. Rig does not create datasets. Rig does not use user data for training.**

### User Responsibility

When using Rig with external providers:

- **You control what's sent** — Only what you explicitly provide goes to the provider
- **Provider terms apply** — You are subject to the provider's terms and privacy policy
- **No data retention by Rig** — Rig does not store provider requests or responses
- **Provider may retain data** — Check your provider's data retention policy

### Training Data Concerns

Some providers may use your prompts and outputs for training. To minimize this:

1. **Use local providers** — Run models locally (no external API calls)
2. **Check provider settings** — Some providers offer opt-out for training
3. **Use data exclusion requests** — Some providers allow you to request data exclusion
4. **Self-host models** — Full control over data

Rig provides no opinions on which providers to use. This is a user decision.

## Future "Outgate" Philosophy

Rig may introduce **opt-in, inspectable outbound data** in the future. This section describes the principles that would govern such features.

### Principles

If Rig ever implements outbound data collection, it will follow these **non-negotiable** principles:

1. **Opt-in by default** — Disabled unless explicitly enabled by user
2. **Granular control** — Enable/disable specific categories of data
3. **Inspect before export** — User can see exactly what will be sent
4. **Redacted by default** — Sensitive data always removed
5. **Minimal collection** — Only what's necessary for the stated purpose
6. **Clear purpose** — Each data point has a documented reason for collection
7. **User deletable** — Users can delete their data
8. **Transparency** — Full documentation of what's collected and why

### Proposed Categories (NOT IMPLEMENTED)

These are **not currently implemented** but represent the design if they were:

| Category | Purpose | Data Collected | Status |
|----------|---------|----------------|--------|
| **Usage metrics** | Understand feature adoption | Command counts, feature flags | Paused |
| **Error metrics** | Improve reliability | Error types, stack trace hashes | Paused |
| **Performance metrics** | Improve performance | Operation durations, resource usage | Paused |
| **Update checks** | Notify of new versions | Current version, latest version | Paused |
| **Documentation fetch** | Cache latest docs | None (cached locally) | Paused |

### Inspection Mechanism (Proposed)

If implemented, users would be able to:

```bash
# See what would be collected
python -m rig telemetry preview

# Enable specific categories
python -m rig config set telemetry.usage_metrics true
python -m rig config set telemetry.error_metrics true

# Disable all telemetry
python -m rig config set telemetry.enabled false

# Export inspection log
python -m rig telemetry inspect --output telemetry-log.json
```

### Guarantees (If Implemented)

1. **No content** — Never collects file contents, prompts, or responses
2. **No identifiers** — Never collects usernames, hostnames, IPs
3. **Aggregated only** — All metrics would be aggregated (counts, not individual events)
4. **Local first** — Data would be cached locally and exported in batches (if enabled)
5. **No blocking** — Telemetry failures would never block Rig functionality

## Inspectability Expectations

Rig aims to make all its behavior inspectable. Users should be able to:

### Verify What's Collected

```bash
# Check all possible outbound data
python -m rig telemetry categories

# See what would be in a debug bundle
python -m rig debug bundle --dry-run

# See what --json outputs
python -m rig replay timeline --json | python -m json.tool
```

### Monitor Network Activity

Users can monitor Rig's network activity:

```bash
# Use system tools to monitor network connections
# macOS:
sudo lsof -i -P | grep python

# Linux:
ss -tulnp | grep python

# Or use a network monitoring tool
```

**Expected result:** Only connections initiated by explicit user actions (provider calls, Git operations) should appear.

### Audit All Outbound Data

Since currently there is **no automatic telemetry**, the only outbound data is what the user explicitly requests:

| User Action | Data Exported | Inspectable Via |
|-------------|---------------|----------------|
| `--json` flag | JSON output | Terminal/stdout |
| `debug bundle` | ZIP archive | `--dry-run` preview |
| Provider use | User's input/output | Provider's own logs |
| Git operations | Git data | Git's own mechanisms |

## Transparency Summary

| Question | Answer |
|----------|--------|
| Does Rig phone home? | ❌ No |
| Does Rig collect usage metrics? | ❌ No (paused) |
| Does Rig track errors? | ❌ No (paused) |
| Does Rig send crash reports? | ❌ No (paused) |
| Does Rig check for updates? | ❌ No (paused) |
| Does Rig export receipts? | ❌ No |
| Does Rig export file contents? | ❌ No |
| Does Rig export Git history? | ❌ No |
| Does Rig export prompts? | ❌ No |
| Does Rig export model responses? | ❌ No |
| Does Rig export tokens? | ❌ No |
| Can `--json` export data? | ✅ Yes (user-initiated, redacted) |
| Can debug bundles export data? | ✅ Yes (user-initiated, redacted) |

## Summary

Rig's telemetry posture in one sentence:

> "**Rig is offline-first: core governance never touches the network, and the only data that can leave the machine is what the user explicitly requests through clearly documented commands.**"

### Current State (v0.1.0a1)

- ✅ **No automatic telemetry**
- ✅ **No phone-home behavior**
- ✅ **No hidden network calls**
- ✅ **All outbound data is user-initiated**
- ✅ **All outbound data is inspectable**
- ✅ **Sensitive data is always redacted**

### Future State (If Implemented)

- ✅ **Opt-in by default** (disabled unless enabled)
- ✅ **Granular controls** (enable specific categories)
- ✅ **Inspect before export** (see what's collected)
- ✅ **Redacted by default** (sensitive data removed)
- ✅ **Fully documented** (transparency about all collection)

---

**Document Version:** 1.0
**Last Updated:** May 2025
**Status:** Current (no telemetry implemented)
