# Rig Installation Guide

> **Deterministic, reproducible, trustworthy install flows.**

This document covers all supported installation methods for Rig, including dependency management, Python version requirements, and verification steps.

## Prerequisites

### Python Version Policy

**Rig requires Python 3.14 or newer. No exceptions.**

| Python Version | Support Status | Notes |
|----------------|----------------|-------|
| 3.14.x | ✅ Fully supported | Primary target |
| 3.15.x | ✅ Supported | Tested when available |
| < 3.14 | ❌ Not supported | Will fail with explicit error |

**Verify your Python version before installing:**
```bash
python --version
# Must output: Python 3.14.x or higher
```

### Platform Support

| Platform | Support Status | Notes |
|----------|----------------|-------|
| macOS (Apple Silicon) | ✅ Primary target | Fully tested |
| macOS (Intel) | ✅ Supported | Tested |
| Linux (x86_64) | ⚠️ Community | May work, not officially tested |
| Windows | ⚠️ Community | May work, not officially tested |

**Rig is macOS-first.** The primary development and testing target is macOS with Apple Silicon. Other platforms may work but are not officially supported.

### Required System Tools

- **Git** (2.30+) — Rig uses Git worktrees extensively
- **pip** (24+) — Python package manager
- **venv** — Python virtual environment support (built-in)

## Installation Methods

### Method 1: Development Install (Recommended for Contributors)

For contributors and developers who want to modify Rig's source code.

```bash
# 1. Clone the repository
git clone https://github.com/juliantorr-es/Rig.git
cd Rig

# 2. Create a virtual environment (REQUIRED - do not use system Python)
python3.14 -m venv .venv

# 3. Activate the virtual environment
# macOS/Linux:
source .venv/bin/activate
# Windows (PowerShell):
# .\.venv\Scripts\activate
# Windows (cmd):
# .\.venv\Scripts\activate.bat

# 4. Install Rig in editable mode with all development dependencies
python -m pip install -e ".[ui,dev]"

# 5. Verify the installation
python -m rig doctor all
```

**Why editable mode?**
- Changes to source files take effect immediately
- Required for development and testing
- Allows you to run `python -m rig` from the source directory

### Method 2: Regular Install (for Testing)

For users who want to install Rig normally (not for development):

```bash
# 1. Create a virtual environment
python3.14 -m venv .venv
source .venv/bin/activate

# 2. Install Rig from source
python -m pip install /path/to/Rig

# 3. Verify
rig --help
```

### Method 3: pipx Install (for CLI-Only Usage)

For users who want Rig available globally via `pipx`:

```bash
# 1. Ensure pipx is installed
python -m pip install --user pipx
python -m pipx ensurepath

# 2. Install Rig (add --include-deps if you want dependencies isolated)
pipx install --python python3.14 /path/to/Rig

# 3. Verify
rig --help
```

**Note:** pipx installs Rig in an isolated environment. For development, use Method 1 instead.

### Method 4: Fresh Clone Install (Validation Path)

This is the canonical path to verify a clean install from scratch. Used for CI and validation.

```bash
# 1. Start from scratch
cd /tmp
rm -rf rig_test_install
mkdir rig_test_install
cd rig_test_install

# 2. Clone the repository
git clone https://github.com/juliantorr-es/Rig.git
cd Rig

# 3. Create virtual environment
python3.14 -m venv .venv
source .venv/bin/activate

# 4. Install with all optional dependencies
python -m pip install -e ".[ui,dev]"

# 5. Run verification commands (see below)
python -m rig doctor all
python -m pytest tests/test_replay.py -q
```

## Dependency Groups

Rig uses **optional dependency groups** to keep the base install lightweight.

| Group | Purpose | Install Command |
|-------|---------|-----------------|
| (none) | Core Rig only | `pip install -e .` |
| `ui` | Windowed UI (aiohttp, pywebview) | `pip install -e ".[ui]"` |
| `dev` | Development tools (pytest, pyright, ruff) | `pip install -e ".[dev]"` |
| `docs` | Documentation tools (mkdocs) | `pip install -e ".[docs]"` |
| `ml` | ML dependencies (macOS only) | `pip install -e ".[ml]"` |
| `legacy_tui` | Deprecated Textual TUI | `pip install -e ".[legacy_tui]"` |
| `all` | Everything | `pip install -e ".[all]"` |

### Base Dependencies (Always Installed)

These are the core dependencies required for Rig to function:

- `jsonschema>=4.23` — JSON schema validation for receipts
- `duckdb>=1.0.0` — Embedded database for audit events
- `PyYAML>=6.0` — YAML parsing for configuration
- `rich>=13.7` — Rich terminal output
- `psutil>=5.9` — Process and system monitoring
- `tomli-w>=1.0.0` — TOML parsing (Python 3.11+ compatible)

### UI Dependencies (Optional)

- `aiohttp>=3.9` — async HTTP for WebSocket server
- `pywebview>=5.3` — Windowed web UI

**Note:** The UI is optional. The CLI (`rig`) works without UI dependencies.

### Development Dependencies (Optional)

- `pytest>=8.0` — Test framework
- `pytest-asyncio>=0.23` — Async test support
- `build>=1.2` — Package building
- `pyright>=1.1` — Static type checking
- `ruff>=0.6` — Linting

### ML Dependencies (Optional, macOS only)

- `mlx>=0.20` — Apple ML framework (macOS ARM64 only)
- `llama-cpp-python>=0.3.0` — LLM inference

## Verification Steps

After installation, **always verify** your install is working correctly.

### Quick Verification

```bash
# Check that rig command is available
python -m rig --help

# Run the doctor command to check system integrity
python -m rig doctor all
```

**Expected output for `python -m rig --help`:**
```
usage: rig [-h] [--debug] [--json] <command> ...

Rig, a repo-local developer control plane for disciplined local automation.

positional arguments:
  <command>    Sub-command to run

options:
  -h, --help  Show this help message and exit
  ...
```

**Expected output for `python -m rig doctor all`:**
```
Integrity score: 1.00
All checks passed.
```

### Full Verification Suite

Run these commands to ensure everything is working:

```bash
# 1. Syntax check
python3.14 -m compileall -q src tests

# 2. Replay tests (73+ tests)
python -m pytest tests/test_replay.py -v

# 3. Integrity tests (38 tests)
python -m pytest tests/test_integrity.py -v

# 4. Projection contract tests (32 tests)
python -m pytest tests/test_projection_contracts.py -v

# 5. UI frontend logic tests
python -m pytest tests/test_ui_frontend_logic.py -v

# 6. Doctor commands
python -m rig doctor all
python -m rig doctor projections

# 7. Replay validation
python -m rig replay timeline --json

# 8. UI commands
python -m rig ui --help
python -m rig window open --dry-run
```

**All commands must exit with code 0 (success).**

### Canonical Validation Entrypoint

For a single command that runs all checks:

```bash
bash scripts/check.sh
```

This script runs all validation in deterministic order and provides clear pass/fail output.

## Troubleshooting Installation

### "Python 3.14 not found"

**Problem:** You don't have Python 3.14 installed.

**Solution:**
- macOS (Homebrew): `brew install python@3.14`
- Linux: Use your distribution's package manager or [pyenv](https://github.com/pyenv/pyenv)
- Windows: Download from [python.org](https://www.python.org/downloads/)

Verify: `python3.14 --version`

### "Module not found" errors

**Problem:** Python can't find installed packages.

**Solution:** Ensure you've activated the virtual environment:
```bash
source .venv/bin/activate
```

If you installed without a venv, try:
```bash
python -m pip install --user -e ".[ui,dev]"
```

### "Command not found: rig"

**Problem:** The `rig` command isn't in your PATH.

**Solution:**
1. Use `python -m rig` instead of `rig`
2. Or ensure the venv's `bin` directory is in PATH:
   ```bash
   export PATH=".venv/bin:$PATH"
   ```
3. Or install with pipx for global access

### Permission errors

**Problem:** Permission denied when installing packages.

**Solution:** Always use a virtual environment. Never install to system Python.

### Dependency conflicts

**Problem:** Package version conflicts.

**Solution:**
```bash
# Clean and reinstall
rm -rf .venv
python3.14 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[ui,dev]"
```

## Upgrading

### Upgrading Rig

```bash
# Pull the latest changes
cd Rig
git pull origin main

# Reinstall
source .venv/bin/activate
python -m pip install -e ".[ui,dev]" --force-reinstall
```

### Upgrading Dependencies

```bash
# Update all dependencies
python -m pip install --upgrade pip
python -m pip install -e ".[ui,dev]" --upgrade
```

**Warning:** Upgrading dependencies may introduce breaking changes. Always verify with `bash scripts/check.sh` after upgrading.

## Editable Install vs Regular Install

| Aspect | Editable Install (`-e`) | Regular Install |
|--------|--------------------------|-----------------|
| Source code editable | ✅ Yes | ❌ No (must reinstall) |
| Changes take effect | Immediately | After reinstall |
| Development | ✅ Recommended | ❌ Not ideal |
| Performance | Same | Same |
| Uninstall | `pip uninstall rig` | `pip uninstall rig` |

**Use editable install for development.** Use regular install only for deployment.

## Dependency Locking

Rig does **not** use lock files (e.g., `requirements.lock`, `poetry.lock`) by default. This is intentional:

- **Reproducibility:** `pyproject.toml` declares exact minimum versions
- **Determinism:** `pip install` with version specifiers provides reproducible installs
- **Flexibility:** Allows testing with newer patch versions

For exact reproducibility in CI, pin the commit hash when cloning:

```bash
git clone --branch main --depth 1 https://github.com/juliantorr-es/Rig.git
cd Rig
git checkout <specific-commit-hash>
```

## Supply Chain Transparency

### Dependency Sources

All Rig dependencies are sourced from PyPI (Python Package Index).

| Package | Purpose | Source | License |
|---------|---------|--------|---------|
| jsonschema | JSON validation | PyPI | MIT |
| duckdb | Embedded DB | PyPI | MIT |
| PyYAML | YAML parsing | PyPI | MIT |
| rich | Terminal output | PyPI | MIT |
| psutil | System monitoring | PyPI | BSD |
| tomli-w | TOML parsing | PyPI | MIT |
| aiohttp | Async HTTP | PyPI | Apache 2.0 |
| pywebview | Windowed UI | PyPI | BSD |
| pytest | Testing | PyPI | MIT |
| pyright | Type checking | PyPI | MIT |
| ruff | Linting | PyPI | MIT |

### Dependency Trust

Rig follows these supply chain principles:

1. **Minimal dependencies:** Only what's necessary for core functionality
2. **Well-maintained packages:** Actively maintained, widely used libraries
3. **Compatible licenses:** MIT, BSD, Apache 2.0 (permissive licenses only)
4. **No SaaS dependencies:** Core governance has zero cloud dependencies
5. **Static analysis:** Dependencies are scanned for security issues

### Dependency Auditing

To audit installed dependencies:

```bash
# List all installed packages
python -m pip list

# List with versions
python -m pip freeze

# Check for vulnerable packages (requires pip-audit)
python -m pip install pip-audit
pip-audit
```

## Uninstalling

### Uninstall Rig

```bash
# Deactivate venv first
source .venv/bin/activate

# Uninstall the package
python -m pip uninstall rig

# Remove the venv
cd ..
rm -rf Rig
```

### Clean Install

For a completely clean start:

```bash
# Remove everything
rm -rf Rig .venv

# Start fresh (see Development Install above)
```

## Environment Variables

Rig respects these environment variables:

| Variable | Purpose | Default |
|----------|---------|---------|
| `RIG_DEBUG` | Enable debug output | `0` |
| `RIG JSON` | Force JSON output | `0` |
| `NO_COLOR` | Disable colored output | (unset) |
| `PYTHONPATH` | Python module search path | (unset) |

## Platform-Specific Notes

### macOS

**Recommended:** Use Homebrew for Python 3.14:

```bash
brew install python@3.14
```

**Virtual environment location:** Rig assumes `.venv` in the project root. Adjust paths as needed.

### Linux

**Python 3.14:** May need to build from source or use a PPA.

**Required packages:**
```bash
# Debian/Ubuntu
sudo apt-get install python3.14 python3.14-venv python3.14-dev

# Fedora/RHEL
sudo dnf install python3.14 python3.14-virtualenv
```

### Windows

**Python 3.14:** Download from python.org.

**Virtual environment:**
```cmd
python -m venv .venv
.venv\Scripts\activate
```

**Note:** Windows support is community-maintained. Some features may not work.

## Install Verification

> **Trust but verify. Every install must be validated.**

After installing Rig, **you must verify** the installation is correct and complete.

### Quick Verification

```bash
# 1. Module import test
python -c "import rig; print('rig', rig.__version__ if hasattr(rig, '__version__') else 'ok')"

# 2. CLI entrypoint test
python -m rig --help

# 3. Doctor integrity check
python -m rig doctor all

# 4. Syntax compilation
python3.14 -m compileall -q src tests
```

**Expected outcomes:**
- All commands exit with code 0
- `python -m rig --help` shows command options
- `python -m rig doctor all` reports "All checks passed" with score 1.00
- No syntax errors reported

### Full Verification Suite

Run the complete validation suite:

```bash
bash scripts/check.sh
```

Or run individual checks:

```bash
# Replay tests (73+ tests)
python -m pytest tests/test_replay.py -v

# Integrity tests (38 tests)
python -m pytest tests/test_integrity.py -v

# Projection contract tests (32 tests)
python -m pytest tests/test_projection_contracts.py -v

# UI frontend logic tests
python -m pytest tests/test_ui_frontend_logic.py -v

# CLI validation
python -m rig ui --help
python -m rig window open --dry-run
```

### Fresh Clone Verification

For maximum trust, verify Rig works from a **completely fresh clone**:

```bash
# Use the dedicated verification script
bash scripts/verify_fresh_clone.sh --fast

# Or manually:
cd /tmp
rm -rf rig_fresh_test
mkdir rig_fresh_test
cd rig_fresh_test
git clone https://github.com/juliantorr-es/Rig.git
cd Rig
python3.14 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[ui,dev]"
python -m rig doctor all
python -m rig --help
bash scripts/check.sh --fast
```

The `scripts/verify_fresh_clone.sh` script automates this process with:
- Isolated temporary directory
- Fresh repository clone
- Virtual environment creation
- Editable install
- Editable install path verification
- CLI entrypoint verification
- Doctor commands validation
- Test suite execution
- Automatic cleanup

**Usage:**
```bash
# Basic usage (uses current repo origin)
bash scripts/verify_fresh_clone.sh

# With options
bash scripts/verify_fresh_clone.sh \
  --repo-url https://github.com/juliantorr-es/Rig.git \
  --branch main \
  --python python3.14 \
  --fast \
  --keep

# Show help
bash scripts/verify_fresh_clone.sh --help
```

### Editable Install Path Verification

Verify that Rig is installed in editable mode and the paths are correct:

```bash
# Check pip show output - should show "editable" 
python -m pip show rig

# The output should include:
# - Name: rig
# - Version: 0.1.0a1 (or current version)
# - Location: file:///path/to/your/Rig
# - Editable project location: /path/to/your/Rig
# - Requires: (list of dependencies)

# Verify CLI entrypoint
python -m rig --version  # If implemented
python -c "import rig.cli.main; print('CLI module ok')"
```

### Dependency Verification

Verify all dependencies are installed correctly:

```bash
# List installed packages
python -m pip list

# Check specific dependencies
python -c "import jsonschema; print('jsonschema', jsonschema.__version__)"
python -c "import duckdb; print('duckdb', duckdb.__version__)"
python -c "import rich; print('rich', rich.__version__)"
python -c "import psutil; print('psutil', psutil.__version__)"

# For UI dependencies (if installed)
python -c "import aiohttp; print('aiohttp', aiohttp.__version__)" 2>/dev/null || echo "aiohttp not installed"
python -c "import webview; print('pywebview', webview.__version__)" 2>/dev/null || echo "pywebview not installed"
```

## Summary

| Task | Command |
|------|---------|
| Install for development | `python -m pip install -e ".[ui,dev]"` |
| Install CLI only | `pipx install /path/to/Rig` |
| Verify install | `python -m rig doctor all` |
| Full validation | `bash scripts/check.sh` |
| Fresh clone verification | `bash scripts/verify_fresh_clone.sh --fast` |
| Run tests | `python -m pytest tests/` |
| Upgrade dependencies | `python -m pip install --upgrade -e ".[ui,dev]"` |

**Next steps:** After installation, see [Quickstart](../README.md#quickstart) for basic usage.
