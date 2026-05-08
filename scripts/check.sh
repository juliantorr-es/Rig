#!/usr/bin/env bash
# Rig Canonical Validation Entrypoint
# 
# This script provides a single, deterministic validation entrypoint for Rig.
# It runs all required checks in a specific order to ensure system integrity.
#
# Usage:
#   bash scripts/check.sh
#   bash scripts/check.sh --fast    # Skip slower checks
#   bash scripts/check.sh --help   # Show this help
#
# Exit codes:
#   0 - All checks passed
#   1 - One or more checks failed
#
# Doctrine:
# - Deterministic ordering
# - Readable output
# - Fail-fast behavior
# - Explicit failure surfaces
# - No hidden mutation
#
# Related scripts:
#   scripts/verify_fresh_clone.sh    - Fresh clone verification
#   scripts/verify_release_artifacts.sh - Release artifact verification

set -euo pipefail

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

# Track overall status
OVERALL_STATUS=0
CHECK_COUNT=0
PASS_COUNT=0
FAIL_COUNT=0

# Helper functions
pass_check() {
    local name="$1"
    echo -e "${GREEN}✓ PASS${NC}: ${name}"
    PASS_COUNT=$((PASS_COUNT + 1))
    CHECK_COUNT=$((CHECK_COUNT + 1))
}

fail_check() {
    local name="$1"
    local message="$2"
    echo -e "${RED}✗ FAIL${NC}: ${name}"
    if [ -n "$message" ]; then
        echo "  ${message}"
    fi
    OVERALL_STATUS=1
    FAIL_COUNT=$((FAIL_COUNT + 1))
    CHECK_COUNT=$((CHECK_COUNT + 1))
}

section_header() {
    local name="$1"
    echo ""
    echo -e "${BLUE}=== ${name} ===${NC}"
}

# Parse arguments
FAST_MODE=false
for arg in "$@"; do
    case "$arg" in
        --fast)
            FAST_MODE=true
            ;;
        --help|-h)
            echo "Usage: $0 [--fast] [--help]"
            echo ""
            echo "Rig Canonical Validation Entrypoint"
            echo ""
            echo "Options:"
            echo "  --fast    Skip slower checks (UI dry-run)"
            echo "  --help    Show this help message"
            echo ""
            echo "Checks run in order:"
            echo "  1. Syntax compilation"
            echo "  2. Replay tests"
            echo "  3. Integrity tests"
            echo "  4. Projection contract tests"
            echo "  5. UI frontend logic tests"
            echo "  6. Doctor commands"
            echo "  7. Replay timeline"
            echo "  8. UI dry-run (skipped in --fast mode)"
            echo ""
            echo "Related verification scripts:"
            echo "  scripts/verify_fresh_clone.sh      - Fresh clone verification"
            echo "  scripts/verify_release_artifacts.sh - Release artifact verification"
            exit 0
            ;;
    esac
done

echo "============================================"
echo "  Rig Canonical Validation"
echo "============================================"
echo ""
echo "Doctrine: Deterministic ordering, readable output, fail-fast, explicit failures, no hidden mutation"
echo ""

# Start timer
START_TIME=$(date +%s)

# ============================================================================
# PHASE 1: Syntax Compilation
# ============================================================================
section_header "Phase 1: Syntax Compilation"

echo "Checking Python syntax in src/ and tests/..."
if python3.14 -m compileall -q src tests 2>&1; then
    pass_check "Python syntax check (src tests)"
else
    fail_check "Python syntax check" "Syntax errors found in source or test files"
    exit 1
fi

# ============================================================================
# PHASE 2: Core Test Suites
# ============================================================================
section_header "Phase 2: Core Test Suites"

# Replay tests
echo "Running replay tests..."
if python3.14 -m pytest tests/test_replay.py -q 2>&1; then
    pass_check "Replay tests (73+ tests)"
else
    fail_check "Replay tests" "Some replay tests failed"
fi

# Integrity tests
echo "Running integrity tests..."
if python3.14 -m pytest tests/test_integrity.py -q 2>&1; then
    pass_check "Integrity tests (38 tests)"
else
    fail_check "Integrity tests" "Some integrity tests failed"
fi

# Projection contract tests
echo "Running projection contract tests..."
if python3.14 -m pytest tests/test_projection_contracts.py -q 2>&1; then
    pass_check "Projection contract tests (32 tests)"
else
    fail_check "Projection contract tests" "Some projection tests failed"
fi

# UI frontend logic tests
echo "Running UI frontend logic tests..."
if python3.14 -m pytest tests/test_ui_frontend_logic.py -q 2>&1; then
    pass_check "UI frontend logic tests"
else
    fail_check "UI frontend logic tests" "Some UI logic tests failed"
fi

# ============================================================================
# PHASE 3: Doctor Commands
# ============================================================================
section_header "Phase 3: Doctor Commands"

# rigorous integrity check
echo "Running rig doctor all..."
if python3.14 -m rig doctor all 2>&1; then
    pass_check "rig doctor all"
else
    fail_check "rig doctor all" "Integrity check failed"
fi

# Projection contract validation
echo "Running rig doctor projections..."
if python3.14 -m rig doctor projections 2>&1; then
    pass_check "rig doctor projections"
else
    fail_check "rig doctor projections" "Projection contract validation failed"
fi

# ============================================================================
# PHASE 4: Replay Validation
# ============================================================================
section_header "Phase 4: Replay Validation"

echo "Running rig replay timeline..."
if python3.14 -m rig replay --json timeline > /dev/null 2>&1; then
    pass_check "rig replay --json timeline"
else
    fail_check "rig replay timeline" "Timeline replay failed"
fi

# ============================================================================
# PHASE 5: CLI Validation
# ============================================================================
section_header "Phase 5: CLI Validation"

echo "Checking rig ui --help..."
if python3.14 -m rig ui --help > /dev/null 2>&1; then
    pass_check "rig ui --help"
else
    fail_check "rig ui --help" "UI help command failed"
fi

# UI dry-run (skip in fast mode)
if [ "$FAST_MODE" = false ]; then
    echo "Running rig window open --dry-run..."
    if python3.14 -m rig window open --dry-run > /dev/null 2>&1; then
        pass_check "rig window open --dry-run"
    else
        fail_check "rig window open --dry-run" "UI dry-run failed"
    fi
else
    echo -e "${YELLOW}⊘ SKIP${NC}: rig window open --dry-run (--fast mode)"
    ((CHECK_COUNT++))
fi

# ============================================================================
# SUMMARY
# ============================================================================
END_TIME=$(date +%s)
ELAPSED_TIME=$((END_TIME - START_TIME))

echo ""
echo "============================================"
echo "  Validation Summary"
echo "============================================"
echo ""
echo "Checks run: $CHECK_COUNT"
echo -e "${GREEN}Passed: $PASS_COUNT${NC}"
echo -e "${RED}Failed: $FAIL_COUNT${NC}"
echo "Time: ${ELAPSED_TIME}s"
echo ""

if [ $OVERALL_STATUS -eq 0 ]; then
    echo -e "${GREEN}✓ All checks passed!${NC}"
    echo ""
    echo "Rig is validated and ready for development."
    exit 0
else
    echo -e "${RED}✗ $FAIL_COUNT check(s) failed${NC}"
    echo ""
    echo "Please fix the failures above and re-run this script."
    exit 1
fi
