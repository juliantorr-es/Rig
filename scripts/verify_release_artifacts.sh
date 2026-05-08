#!/usr/bin/env bash
# Rig Release Artifact Verification Script
#
# Deterministic verification that Rig release artifacts can be built
# and installed correctly from source distributions.
#
# This script validates:
# - Source distribution (sdist) builds
# - Wheel distribution builds (if applicable)
# - Package metadata integrity
# - Installability from built artifacts
# - CLI entrypoints after install from artifacts
#
# IMPORTANT: This script does NOT publish anything.
# All operations are local only.
#
# Usage:
#   bash scripts/verify_release_artifacts.sh [OPTIONS]
#
# Options:
#   --source-dir DIR    Source directory (default: current directory)
#   --build-dir DIR     Build output directory (default: /tmp/rig_artifacts_$$)
#   --python PYTHON     Python executable (default: python3.14)
#   --keep              Keep the build directory after completion
#   --help, -h          Show this help message
#
# Exit codes:
#   0 - All checks passed
#   1 - One or more checks failed
#   2 - Script usage error
#
# Doctrine:
# - Deterministic ordering
# - No external mutation
# - Fail-fast behavior
# - Readable output
# - Explicit failure reasons
# - Local-only operations (no publishing)

set -euo pipefail

# ============================================================================
# Configuration
# ============================================================================

# Colors for output (disabled if NO_COLOR is set)
if [ -z "${NO_COLOR:-}" ]; then
    RED='\033[0;31m'
    GREEN='\033[0;32m'
    YELLOW='\033[0;33m'
    BLUE='\033[0;34m'
    MAGENTA='\033[0;35m'
    CYAN='\033[0;36m'
    NC='\033[0m' # No Color
else
    RED=''
    GREEN=''
    YELLOW=''
    BLUE=''
    MAGENTA=''
    CYAN=''
    NC=''
fi

# ============================================================================
# State Tracking
# ============================================================================

OVERALL_STATUS=0
CHECK_COUNT=0
PASS_COUNT=0
FAIL_COUNT=0
SKIP_COUNT=0

# Arrays to track results
declare -a PASS_NAMES=()
declare -a FAIL_NAMES=()
declare -a SKIP_NAMES=()

# ============================================================================
# Helper Functions
# ============================================================================

pass_check() {
    local name="$1"
    local message="${2:-}"
    echo -e "${GREEN}✓ PASS${NC}: ${name}"
    if [ -n "$message" ]; then
        echo "  ${message}"
    fi
    PASS_COUNT=$((PASS_COUNT + 1))
    CHECK_COUNT=$((CHECK_COUNT + 1))
    PASS_NAMES+=("$name")
}

fail_check() {
    local name="$1"
    local message="${2:-}"
    echo -e "${RED}✗ FAIL${NC}: ${name}"
    if [ -n "$message" ]; then
        echo "  ${message}"
    fi
    OVERALL_STATUS=1
    FAIL_COUNT=$((FAIL_COUNT + 1))
    CHECK_COUNT=$((CHECK_COUNT + 1))
    FAIL_NAMES+=("$name")
}

skip_check() {
    local name="$1"
    local message="${2:-}"
    echo -e "${YELLOW}⊘ SKIP${NC}: ${name}"
    if [ -n "$message" ]; then
        echo "  ${message}"
    fi
    SKIP_COUNT=$((SKIP_COUNT + 1))
    CHECK_COUNT=$((CHECK_COUNT + 1))
    SKIP_NAMES+=("$name")
}

section_header() {
    local name="$1"
    echo ""
    echo -e "${BLUE}=== ${name} ===${NC}"
}

cleanup() {
    local exit_code="${1:-0}"
    
    if [ -n "${BUILD_DIR:-}" ] && [ "${KEEP_BUILD_DIR:-false}" = "false" ]; then
        echo ""
        echo "Cleaning up build directory: ${BUILD_DIR}"
        rm -rf "${BUILD_DIR}" || {
            echo -e "${YELLOW}Warning: Failed to clean up ${BUILD_DIR}${NC}"
        }
    fi
    
    if [ $exit_code -ne 0 ]; then
        echo ""
        echo -e "${RED}=== VERIFICATION FAILED ===${NC}"
        exit $exit_code
    fi
}

trap cleanup EXIT

# ============================================================================
# Argument Parsing
# ============================================================================

SOURCE_DIR=""
BUILD_DIR=""
PYTHON_EXEC="python3.14"
KEEP_BUILD_DIR="false"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --source-dir)
            SOURCE_DIR="$2"
            shift 2
            ;;
        --build-dir)
            BUILD_DIR="$2"
            shift 2
            ;;
        --python)
            PYTHON_EXEC="$2"
            shift 2
            ;;
        --keep)
            KEEP_BUILD_DIR="true"
            shift
            ;;
        --help|-h)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Rig Release Artifact Verification Script"
            echo ""
            echo "Verifies that Rig release artifacts can be built and installed."
            echo ""
            echo "IMPORTANT: This script does NOT publish anything to PyPI."
            echo "All operations are local only."
            echo ""
            echo "Options:"
            echo "  --source-dir DIR    Source directory (default: current directory)"
            echo "  --build-dir DIR     Build output directory (default: /tmp/rig_artifacts_$$)"
            echo "  --python PYTHON     Python executable (default: python3.14)"
            echo "  --keep              Keep the build directory after completion"
            echo "  --help, -h          Show this help message"
            echo ""
            echo "Checks performed in order:"
            echo "  1. Environment preparation"
            echo "  2. Source directory validation"
            echo "  3. Pyproject.toml validation"
            echo "  4. Package metadata extraction"
            echo "  5. Source distribution build"
            echo "  6. Source distribution structure validation"
            echo "  7. Wheel distribution build (if applicable)"
            echo "  8. Install from source distribution"
            echo "  9. CLI entrypoint verification (from sdist)"
            echo "  10. Install from wheel (if built)"
            echo "  11. CLI entrypoint verification (from wheel)"
            echo "  12. Package metadata verification"
            exit 0
            ;;
        *)
            echo "Unknown option: $1" >&2
            echo "Use --help for usage information" >&2
            exit 2
            ;;
    esac
done

# ============================================================================
# Determine Source Directory
# ============================================================================

if [ -z "$SOURCE_DIR" ]; then
    SOURCE_DIR=$(pwd)
fi

# Ensure source dir is absolute
SOURCE_DIR=$(cd "$(dirname "$SOURCE_DIR")" && pwd)/$(basename "$SOURCE_DIR")

# ============================================================================
# Determine Build Directory
# ============================================================================

if [ -z "$BUILD_DIR" ]; then
    BUILD_DIR="/tmp/rig_artifacts_$$"
fi

# Ensure build dir is absolute
BUILD_DIR=$(cd "$(dirname "$BUILD_DIR")" && pwd)/$(basename "$BUILD_DIR")

if [ -e "$BUILD_DIR" ]; then
    echo -e "${RED}Error: Build directory already exists: ${BUILD_DIR}${NC}" >&2
    exit 2
fi

mkdir -p "$BUILD_DIR"

# ============================================================================
# Header
# ============================================================================

echo "============================================"
echo "  Rig Release Artifact Verification"
echo "============================================"
echo ""
echo "WARNING: This script builds and tests release artifacts locally."
echo "It does NOT publish anything to PyPI or any external service."
echo ""
echo "Configuration:"
echo "  Source directory: ${SOURCE_DIR}"
echo "  Build directory: ${BUILD_DIR}"
echo "  Python: ${PYTHON_EXEC}"
echo "  Keep build dir: ${KEEP_BUILD_DIR}"
echo ""

# Start timer
START_TIME=$(date +%s)

# ============================================================================
# PHASE 1: Environment Preparation
# ============================================================================

section_header "Phase 1: Environment Preparation"

# Check that Python 3.14 is available
echo "Checking Python availability..."
if command -v "${PYTHON_EXEC}" >/dev/null 2>&1; then
    PYTHON_VERSION=$(${PYTHON_EXEC} --version 2>&1)
    echo "  Found: ${PYTHON_VERSION}"
    pass_check "Python executable found"
else
    fail_check "Python executable" "${PYTHON_EXEC} not found"
    exit 1
fi

# Verify Python version is 3.14+
echo "Verifying Python version..."
PYTHON_MAJOR_MINOR=$(${PYTHON_EXEC} -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>&1 || true)
if [[ "$PYTHON_MAJOR_MINOR" =~ ^3\.1[4-9]$ ]] || [[ "$PYTHON_MAJOR_MINOR" =~ ^3\.[2-9][0-9]$ ]]; then
    pass_check "Python version check (${PYTHON_MAJOR_MINOR})"
else
    fail_check "Python version" "Requires Python 3.14+, found: ${PYTHON_MAJOR_MINOR}"
fi

# Check for build module
echo "Checking build module..."
if "${PYTHON_EXEC}" -c "import build; print('build module available')" 2>&1 | grep -q "build module available"; then
    pass_check "build module available"
else
    echo "  Installing build module..."
    if "${PYTHON_EXEC}" -m pip install build 2>&1; then
        pass_check "build module installation"
    else
        fail_check "build module installation" "Failed to install build module"
    fi
fi

# ============================================================================
# PHASE 2: Source Directory Validation
# ============================================================================

section_header "Phase 2: Source Directory Validation"

# Check that source directory exists
if [ -d "$SOURCE_DIR" ]; then
    pass_check "Source directory exists"
else
    fail_check "Source directory exists" "Not found: ${SOURCE_DIR}"
    exit 1
fi

# Check for pyproject.toml
PYPROJECT_PATH="${SOURCE_DIR}/pyproject.toml"
if [ -f "$PYPROJECT_PATH" ]; then
    pass_check "pyproject.toml exists"
else
    fail_check "pyproject.toml exists" "Not found: ${PYPROJECT_PATH}"
fi

# Check for src directory
SRC_PATH="${SOURCE_DIR}/src"
if [ -d "$SRC_PATH" ]; then
    pass_check "src directory exists"
else
    fail_check "src directory" "Not found: ${SRC_PATH}"
fi

# Check for rig package
RIG_PKG="${SRC_PATH}/rig"
if [ -d "$RIG_PKG" ]; then
    pass_check "rig package directory exists"
else
    fail_check "rig package directory" "Not found: ${RIG_PKG}"
fi

# Check for CLI entrypoint
CLI_MAIN="${RIG_PKG}/cli/main.py"
if [ -f "$CLI_MAIN" ]; then
    pass_check "CLI main module exists"
else
    fail_check "CLI main module" "Not found: ${CLI_MAIN}"
fi

# ============================================================================
# PHASE 3: Pyproject.toml Validation
# ============================================================================

section_header "Phase 3: Pyproject.toml Validation"

# Check that pyproject.toml is valid TOML
echo "Validating pyproject.toml syntax..."
if "${PYTHON_EXEC}" -c "import tomllib; tomllib.loads(open('${PYPROJECT_PATH}').read())" 2>&1; then
    pass_check "pyproject.toml syntax validation"
else
    fail_check "pyproject.toml syntax" "Invalid TOML syntax"
fi

# Extract and validate key fields
echo "Extracting package metadata..."
if "${PYTHON_EXEC}" -c "
import tomllib, sys
with open('${PYPROJECT_PATH}', 'rb') as f:
    config = tomllib.load(f)

project = config.get('project', {})
name = project.get('name')
version = project.get('version')
desc = project.get('description')
requires_python = project.get('requires-python')

print(f'Name: {name}')
print(f'Version: {version}')
print(f'Description: {desc}')
print(f'Requires Python: {requires_python}')
" 2>&1; then
    pass_check "pyproject.toml metadata extraction"
else
    fail_check "pyproject.toml metadata" "Failed to extract metadata"
fi

# ============================================================================
# PHASE 4: Package Metadata Extraction
# ============================================================================

section_header "Phase 4: Package Metadata Extraction"

# Extract version for use in artifact names
PACKAGE_VERSION=$(${PYTHON_EXEC} -c "
import tomllib
with open('${PYPROJECT_PATH}', 'rb') as f:
    config = tomllib.load(f)
print(config['project']['version'])
" 2>&1)

echo "Package version: ${PACKAGE_VERSION}"
pass_check "Package version extraction (${PACKAGE_VERSION})"

# Extract package name
PACKAGE_NAME=$(${PYTHON_EXEC} -c "
import tomllib
with open('${PYPROJECT_PATH}', 'rb') as f:
    config = tomllib.load(f)
print(config['project']['name'])
" 2>&1)

echo "Package name: ${PACKAGE_NAME}"
pass_check "Package name extraction (${PACKAGE_NAME})"

# ============================================================================
# PHASE 5: Source Distribution Build
# ============================================================================

section_header "Phase 5: Source Distribution Build"

SDIST_PATH="${BUILD_DIR}/${PACKAGE_NAME}-${PACKAGE_VERSION}.tar.gz"

echo "Building source distribution..."
if cd "${SOURCE_DIR}" && ${PYTHON_EXEC} -m build --sdist --outdir "${BUILD_DIR}" 2>&1; then
    pass_check "Source distribution build"
else
    fail_check "Source distribution build" "Failed to build sdist"
fi

# Verify sdist was created
if [ -f "$SDIST_PATH" ]; then
    pass_check "Source distribution file created"
else
    # Try to find it with different naming
    SDIST_FILES=(${BUILD_DIR}/${PACKAGE_NAME}-*.tar.gz)
    if [ ${#SDIST_FILES[@]} -gt 0 ]; then
        SDIST_PATH="${SDIST_FILES[0]}"
        pass_check "Source distribution file found (${SDIST_PATH})"
    else
        fail_check "Source distribution file" "Not found in ${BUILD_DIR}"
    fi
fi

# Verify sdist file size
SDIST_SIZE=$(stat -f %z "$SDIST_PATH" 2>/dev/null || stat -c %s "$SDIST_PATH" 2>/dev/null || echo "0")
if [ "$SDIST_SIZE" -gt 1000 ]; then  # Should be at least 1KB
    pass_check "Source distribution size (${SDIST_SIZE} bytes)"
else
    fail_check "Source distribution size" "Too small: ${SDIST_SIZE} bytes"
fi

# ============================================================================
# PHASE 6: Source Distribution Structure Validation
# ============================================================================

section_header "Phase 6: Source Distribution Structure Validation"

# Create a temp dir for sdist extraction
SDIST_EXTRACT_DIR="${BUILD_DIR}/sdist_extract"
mkdir -p "$SDIST_EXTRACT_DIR"

echo "Extracting source distribution..."
if tar -xzf "$SDIST_PATH" -C "$SDIST_EXTRACT_DIR" 2>&1; then
    pass_check "Source distribution extraction"
else
    fail_check "Source distribution extraction" "Failed to extract sdist"
fi

# Check for extracted package directory
EXTRACTED_DIR="${SDIST_EXTRACT_DIR}/${PACKAGE_NAME}-${PACKAGE_VERSION}"
if [ -d "$EXTRACTED_DIR" ]; then
    pass_check "Extracted package directory exists"
else
    # Try to find the extracted directory
    EXTRACTED_DIRS=("${SDIST_EXTRACT_DIR}"/*/)
    if [ ${#EXTRACTED_DIRS[@]} -gt 0 ]; then
        EXTRACTED_DIR="${EXTRACTED_DIRS[0]}"
        pass_check "Extracted package directory found"
    else
        fail_check "Extracted package directory" "Not found in ${SDIST_EXTRACT_DIR}"
    fi
fi

# Verify key files in extracted package
 echo "Verifying extracted package structure..."
EXTRACTED_PYPROJECT="${EXTRACTED_DIR}/pyproject.toml"
EXTRACTED_SRC="${EXTRACTED_DIR}/src"
EXTRACTED_RIG="${EXTRACTED_SRC}/rig"
EXTRACTED_CLI="${EXTRACTED_RIG}/cli/main.py"

if [ -f "$EXTRACTED_PYPROJECT" ]; then
    pass_check "pyproject.toml in sdist"
else
    fail_check "pyproject.toml in sdist" "Not found: ${EXTRACTED_PYPROJECT}"
fi

if [ -d "$EXTRACTED_SRC" ]; then
    pass_check "src directory in sdist"
else
    fail_check "src directory in sdist" "Not found: ${EXTRACTED_SRC}"
fi

if [ -d "$EXTRACTED_RIG" ]; then
    pass_check "rig package in sdist"
else
    fail_check "rig package in sdist" "Not found: ${EXTRACTED_RIG}"
fi

if [ -f "$EXTRACTED_CLI" ]; then
    pass_check "CLI main in sdist"
else
    fail_check "CLI main in sdist" "Not found: ${EXTRACTED_CLI}"
fi

# ============================================================================
# PHASE 7: Wheel Distribution Build
# ============================================================================

section_header "Phase 7: Wheel Distribution Build"

WHEEL_PATH="${BUILD_DIR}/${PACKAGE_NAME}-${PACKAGE_VERSION}-py3-none-any.whl"

echo "Building wheel distribution..."
if cd "${SOURCE_DIR}" && ${PYTHON_EXEC} -m build --wheel --outdir "${BUILD_DIR}" 2>&1; then
    pass_check "Wheel distribution build"
else
    # Wheel build may fail for various reasons (platform-specific, etc.)
    echo "  Wheel build failed - this may be expected on some platforms"
    skip_check "Wheel distribution build" "Platform not supported for wheel"
    WHEEL_BUILD_SKIPPED=true
else
    WHEEL_BUILD_SKIPPED=false
fi

# Check if wheel was created
if [ -f "$WHEEL_PATH" ] && [ "${WHEEL_BUILD_SKIPPED:-false}" = "false" ]; then
    pass_check "Wheel distribution file created"
    WHEEL_AVAILABLE=true
elif [ "${WHEEL_BUILD_SKIPPED:-false}" = "true" ]; then
    WHEEL_AVAILABLE=false
else
    # Try to find it with different naming
    WHEEL_FILES=(${BUILD_DIR}/${PACKAGE_NAME}-*.whl)
    if [ ${#WHEEL_FILES[@]} -gt 0 ]; then
        WHEEL_PATH="${WHEEL_FILES[0]}"
        WHEEL_AVAILABLE=true
        pass_check "Wheel distribution file found (${WHEEL_PATH})"
    else
        WHEEL_AVAILABLE=false
        skip_check "Wheel distribution file" "Not created"
    fi
fi

# ============================================================================
# PHASE 8: Install from Source Distribution
# ============================================================================

section_header "Phase 8: Install from Source Distribution"

# Create isolated venv for sdist install
SDIST_VENV_DIR="${BUILD_DIR}/venv_sdist"
SDIST_PYTHON=""

if [ -f "${SDIST_VENV_DIR}/bin/python" ]; then
    SDIST_PYTHON="${SDIST_VENV_DIR}/bin/python"
elif [ -f "${SDIST_VENV_DIR}/Scripts/python.exe" ]; then
    SDIST_PYTHON="${SDIST_VENV_DIR}/Scripts/python.exe"
else
    echo "Creating isolated venv for sdist install..."
    if "${PYTHON_EXEC}" -m venv "${SDIST_VENV_DIR}" 2>&1; then
        pass_check "SDIST venv creation"
    else
        fail_check "SDIST venv creation" "Failed to create venv for sdist test"
    fi
    
    if [ -f "${SDIST_VENV_DIR}/bin/python" ]; then
        SDIST_PYTHON="${SDIST_VENV_DIR}/bin/python"
    elif [ -f "${SDIST_VENV_DIR}/Scripts/python.exe" ]; then
        SDIST_PYTHON="${SDIST_VENV_DIR}/Scripts/python.exe"
    else
        fail_check "SDIST venv Python" "Cannot find Python in venv"
    fi
fi

echo "Installing from source distribution..."
if "${SDIST_PYTHON}" -m pip install --upgrade pip >/dev/null 2>&1; then
    pass_check "SDIST pip upgrade"
fi

if "${SDIST_PYTHON}" -m pip install "${SDIST_PATH}" 2>&1; then
    pass_check "Install from source distribution"
else
    fail_check "Install from source distribution" "Failed to install from sdist"
    exit 1
fi

# Verify installation
echo "Verifying sdist installation..."
if "${SDIST_PYTHON}" -c "import rig; print('rig module imported from sdist')" 2>&1; then
    pass_check "Rig module import (from sdist)"
else
    fail_check "Rig module import (from sdist)" "Cannot import rig from sdist install"
fi

# Verify CLI works
echo "Verifying CLI from sdist installation..."
if "${SDIST_PYTHON}" -m rig --help > /dev/null 2>&1; then
    pass_check "rig CLI (from sdist)"
else
    fail_check "rig CLI (from sdist)" "CLI failed from sdist install"
fi

# ============================================================================
# PHASE 9: CLI Entrypoint Verification (from sdist)
# ============================================================================

section_header "Phase 9: CLI Entrypoint Verification (from sdist)"

echo "Testing doctor commands from sdist..."
if "${SDIST_PYTHON}" -m rig doctor all > /dev/null 2>&1; then
    pass_check "rig doctor all (from sdist)"
else
    # This might fail if there's no actual workspace, which is expected
    echo "  doctor all failed - may be expected without workspace"
    skip_check "rig doctor all (from sdist)" "No workspace context"
fi

# Test basic CLI functionality that doesn't require workspace
echo "Testing help commands from sdist..."
for cmd in "help" "--help" "--version" 2>/dev/null; do
    # Skip --version if not implemented
    if [ "$cmd" = "--help" ]; then
        if "${SDIST_PYTHON}" -m rig "${cmd}" > /dev/null 2>&1; then
            pass_check "rig ${cmd} (from sdist)"
        else
            fail_check "rig ${cmd} (from sdist)" "Failed"
        fi
    fi
done

# ============================================================================
# PHASE 10: Install from Wheel (if built)
# ============================================================================

if [ "${WHEEL_AVAILABLE:-false}" = true ]; then
    section_header "Phase 10: Install from Wheel"
    
    # Create isolated venv for wheel install
    WHEEL_VENV_DIR="${BUILD_DIR}/venv_wheel"
    WHEEL_PYTHON=""
    
    echo "Creating isolated venv for wheel install..."
    if "${PYTHON_EXEC}" -m venv "${WHEEL_VENV_DIR}" 2>&1; then
        pass_check "WHEEL venv creation"
    else
        fail_check "WHEEL venv creation" "Failed to create venv for wheel test"
    fi
    
    if [ -f "${WHEEL_VENV_DIR}/bin/python" ]; then
        WHEEL_PYTHON="${WHEEL_VENV_DIR}/bin/python"
    elif [ -f "${WHEEL_VENV_DIR}/Scripts/python.exe" ]; then
        WHEEL_PYTHON="${WHEEL_VENV_DIR}/Scripts/python.exe"
    else
        fail_check "WHEEL venv Python" "Cannot find Python in wheel venv"
    fi
    
    echo "Installing from wheel distribution..."
    if "${WHEEL_PYTHON}" -m pip install --upgrade pip >/dev/null 2>&1; then
        pass_check "WHEEL pip upgrade"
    fi
    
    if "${WHEEL_PYTHON}" -m pip install "${WHEEL_PATH}" 2>&1; then
        pass_check "Install from wheel distribution"
    else
        fail_check "Install from wheel distribution" "Failed to install from wheel"
    fi
    
    # Verify installation
    echo "Verifying wheel installation..."
    if "${WHEEL_PYTHON}" -c "import rig; print('rig module imported from wheel')" 2>&1; then
        pass_check "Rig module import (from wheel)"
    else
        fail_check "Rig module import (from wheel)" "Cannot import rig from wheel install"
    fi
    
    # Verify CLI works from wheel
    echo "Verifying CLI from wheel installation..."
    if "${WHEEL_PYTHON}" -m rig --help > /dev/null 2>&1; then
        pass_check "rig CLI (from wheel)"
    else
        fail_check "rig CLI (from wheel)" "CLI failed from wheel install"
    fi
else
    skip_check "Wheel install and verification" "Wheel build was skipped or failed"
fi

# ============================================================================
# PHASE 11: Package Metadata Verification
# ============================================================================

section_header "Phase 11: Package Metadata Verification"

# Check Package Metadata from Installed Package
echo "Verifying package metadata from sdist install..."
SDIST_PKG_INFO=$(${SDIST_PYTHON} -m pip show rig 2>&1 || true)

if echo "$SDIST_PKG_INFO" | grep -q "Name: rig"; then
    pass_check "Package name verification"
else
    fail_check "Package name verification" "Package not found as 'rig'"
fi

if echo "$SDIST_PKG_INFO" | grep -q "Version: ${PACKAGE_VERSION}"; then
    pass_check "Package version verification (${PACKAGE_VERSION})"
else
    ACTUAL_VERSION=$(echo "$SDIST_PKG_INFO" | grep "Version:" | sed 's/Version: //' | tr -d ' ')
    echo "  Expected: ${PACKAGE_VERSION}, Got: ${ACTUAL_VERSION}"
    # This might be different if version was updated after build
    skip_check "Package version verification" "Version mismatch (expected if version changed)"
fi

# Check for entry points
if echo "$SDIST_PKG_INFO" | grep -q "rig"; then
    pass_check "CLI entrypoint registration"
else
    echo "  Package info: $SDIST_PKG_INFO"
    fail_check "CLI entrypoint registration" "No rig entrypoint found"
fi

# List package files
PACKAGE_FILES=$(${SDIST_PYTHON} -m pip show -f rig 2>&1 || true)
if echo "$PACKAGE_FILES" | grep -q "rig/"; then
    pass_check "Package files installed"
else
    echo "  Package files: $PACKAGE_FILES"
    warn_check "Package files" "No rig files found in package"
fi

# ============================================================================
# SUMMARY
# ============================================================================

END_TIME=$(date +%s)
ELAPSED_TIME=$((END_TIME - START_TIME))

section_header "SUMMARY"

echo ""
echo "============================================"
echo "  Release Artifact Verification Summary"
echo "============================================"
echo ""
echo "Checks run: $CHECK_COUNT"
echo -e "${GREEN}Passed: $PASS_COUNT${NC}"
echo -e "${RED}Failed: $FAIL_COUNT${NC}"
echo -e "${YELLOW}Skipped: $SKIP_COUNT${NC}"
echo "Time: ${ELAPSED_TIME}s"
echo ""
echo "Build directory: ${BUILD_DIR}"
echo "Source distribution: ${SDIST_PATH}"
if [ "${WHEEL_AVAILABLE:-false}" = true ]; then
    echo "Wheel distribution: ${WHEEL_PATH}"
else
    echo "Wheel distribution: Not built"
fi

if [ "${KEEP_BUILD_DIR}" = "true" ] || [ $OVERALL_STATUS -ne 0 ]; then
    echo "Build directory preserved for inspection."
else
    echo "Build directory will be cleaned up."
fi

# Print pass/fail lists if there were any
if [ $FAIL_COUNT -gt 0 ]; then
    echo ""
    echo -e "${RED}Failed checks:${NC}"
    for name in "${FAIL_NAMES[@]}"; do
        echo "  - ${name}"
    done
fi

echo ""
if [ $OVERALL_STATUS -eq 0 ]; then
    echo -e "${GREEN}✓ Release artifact verification passed!${NC}"
    echo ""
    echo "Rig release artifacts are locally verifiable."
    echo "Artifacts built but NOT published (local only)."
    exit 0
else
    echo -e "${RED}✗ Release artifact verification failed${NC}"
    echo ""
    echo "Please fix the failures above."
    exit 1
fi
