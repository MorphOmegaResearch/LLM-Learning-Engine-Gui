#!/bin/bash
# Comprehensive Test Suite for Babel System
# Tests: Deferred status, Catalog queries, Zenity integrations, Sweeps 1-2

echo "=========================================="
echo "BABEL COMPREHENSIVE TEST SUITE"
echo "Date: $(date)"
echo "=========================================="
echo ""

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Test counter
PASS=0
FAIL=0

test_result() {
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ PASS${NC}: $1"
        ((PASS++))
    else
        echo -e "${YELLOW}✗ FAIL${NC}: $1"
        ((FAIL++))
    fi
}

echo "========================================"
echo "TEST GROUP 1: DEFERRED STATUS SUPPORT"
echo "========================================"
echo ""

# Test 1: Add a deferred todo
echo "[TEST 1] Adding deferred todo..."
python3 Os_Toolkit.py todo add "Test Deferred Feature" "This tests the new deferred status functionality" > /dev/null 2>&1
test_result "Add test todo"

# Get the ID of the last added todo
TODO_ID=$(python3 -c "import json; todos=json.load(open('plans/todos.json')); print(todos[-1]['id'])" 2>/dev/null)
echo "  Created todo ID: $TODO_ID"

# Test 2: Update todo to deferred
echo "[TEST 2] Updating todo to deferred status..."
python3 Os_Toolkit.py todo update "$TODO_ID" deferred > /dev/null 2>&1
test_result "Update todo to deferred"

# Test 3: View deferred todos
echo "[TEST 3] Viewing deferred todos..."
python3 Os_Toolkit.py todo view deferred | grep -q "Test Deferred Feature"
test_result "View deferred todos filter"

# Test 4: Verify status in todos.json
echo "[TEST 4] Verify deferred status persisted..."
grep -q "\"status\": \"deferred\"" plans/todos.json
test_result "Deferred status in todos.json"

echo ""
echo "========================================"
echo "TEST GROUP 2: CATALOG QUERY PERSPECTIVES"
echo "========================================"
echo ""

# Test 5: Query by filename
echo "[TEST 5] Query by filename (Os_Toolkit.py)..."
python3 Os_Toolkit.py query "Os_Toolkit.py" --max-results 5 | grep -q "Query Results"
test_result "Filename query"

# Test 6: Query by extension
echo "[TEST 6] Query by file type (.py)..."
python3 Os_Toolkit.py query "*.py" --type file --max-results 5 | grep -q "Query Results"
test_result "File type query"

# Test 7: Query by string content
echo "[TEST 7] Query by content (TrustRegistry)..."
python3 Os_Toolkit.py query "TrustRegistry" --type string --max-results 5 | grep -q "Query Results"
test_result "Content string query"

# Test 8: Query with suggestions (non-Zenity)
echo "[TEST 8] Query with --suggest flag..."
python3 Os_Toolkit.py query "Os_Toolkit.py" --suggest | grep -q "SUGGESTED ACTIONS"
test_result "Query suggestions output"

# Test 9: File analysis
echo "[TEST 9] Analyze specific file..."
python3 Os_Toolkit.py file Os_Toolkit.py --depth 2 | grep -q "6W1H Breakdown"
test_result "File analysis output"

# Test 10: File analysis with suggestions
echo "[TEST 10] File analysis with --suggest..."
python3 Os_Toolkit.py file Os_Toolkit.py --suggest | grep -q "SUGGESTED ACTIONS"
test_result "File suggestions output"

echo ""
echo "========================================"
echo "TEST GROUP 3: TODO SYNCHRONIZATION"
echo "========================================"
echo ""

# Test 11: Sync all todos
echo "[TEST 11] Running todo sync..."
python3 Os_Toolkit.py actions --run sync_all_todos > /dev/null 2>&1
test_result "Todo sync execution"

# Test 12: Latest shows sync status
echo "[TEST 12] Latest command shows sync status..."
python3 Os_Toolkit.py latest 2>/dev/null | grep -q "TODO SYNC STATUS"
test_result "Latest sync status section"

echo ""
echo "========================================"
echo "TEST GROUP 4: ZENITY WIDGETS (Manual)"
echo "========================================"
echo ""

echo -e "${BLUE}NOTE: Zenity tests require GUI interaction${NC}"
echo "These will launch GUI dialogs for you to confirm."
echo ""

read -p "Press Enter to test Zenity widgets (or Ctrl+C to skip)..."

# Test 13: Notification
echo "[TEST 13] Zenity notification..."
python3 test_zenity_widgets.py notification
test_result "Notification widget"
sleep 1

# Test 14: Question dialog
echo "[TEST 14] Zenity question dialog..."
python3 test_zenity_widgets.py question
test_result "Question widget (user interaction: $?)"

# Test 15: Forms
echo "[TEST 15] Zenity forms..."
python3 test_zenity_widgets.py forms
test_result "Forms widget"

# Test 16: Checklist
echo "[TEST 16] Zenity checklist..."
python3 test_zenity_widgets.py checklist
test_result "Checklist widget"

# Test 17: Radiolist
echo "[TEST 17] Zenity radiolist..."
python3 test_zenity_widgets.py radiolist
test_result "Radiolist widget"

# Test 18: Progress bar
echo "[TEST 18] Zenity progress..."
python3 test_zenity_widgets.py progress
test_result "Progress widget"

echo ""
echo "========================================"
echo "TEST GROUP 5: ZENITY INTEGRATIONS"
echo "========================================"
echo ""

read -p "Press Enter to test integrated Zenity features (or Ctrl+C to skip)..."

# Test 19: Latest with Zenity
echo "[TEST 19] Latest with Zenity (-z flag)..."
python3 Os_Toolkit.py latest -z &
ZENITY_PID=$!
sleep 2
if ps -p $ZENITY_PID > /dev/null 2>&1; then
    echo -e "${GREEN}✓ PASS${NC}: Latest Zenity window opened"
    ((PASS++))
    # Kill after showing
    pkill -P $ZENITY_PID zenity 2>/dev/null
else
    echo -e "${YELLOW}✗ FAIL${NC}: Latest Zenity didn't launch"
    ((FAIL++))
fi

# Test 20: Query with Zenity
echo "[TEST 20] Query with Zenity..."
python3 Os_Toolkit.py query "Os_Toolkit.py" -z &
ZENITY_PID=$!
sleep 2
if ps -p $ZENITY_PID > /dev/null 2>&1; then
    echo -e "${GREEN}✓ PASS${NC}: Query Zenity window opened"
    ((PASS++))
    pkill -P $ZENITY_PID zenity 2>/dev/null
else
    echo -e "${YELLOW}✗ FAIL${NC}: Query Zenity didn't launch"
    ((FAIL++))
fi

# Test 21: Todo view with Zenity
echo "[TEST 21] Todo view with Zenity..."
python3 Os_Toolkit.py todo view all -z &
ZENITY_PID=$!
sleep 2
if ps -p $ZENITY_PID > /dev/null 2>&1; then
    echo -e "${GREEN}✓ PASS${NC}: Todo Zenity window opened"
    ((PASS++))
    pkill -P $ZENITY_PID zenity 2>/dev/null
else
    echo -e "${YELLOW}✗ FAIL${NC}: Todo Zenity didn't launch"
    ((FAIL++))
fi

# Test 22: Actions list with Zenity
echo "[TEST 22] Actions with Zenity radiolist..."
python3 Os_Toolkit.py actions --list -z &
ZENITY_PID=$!
sleep 2
if ps -p $ZENITY_PID > /dev/null 2>&1; then
    echo -e "${GREEN}✓ PASS${NC}: Actions Zenity radiolist opened"
    ((PASS++))
    pkill -P $ZENITY_PID zenity 2>/dev/null
else
    echo -e "${YELLOW}✗ FAIL${NC}: Actions Zenity didn't launch"
    ((FAIL++))
fi

echo ""
echo "========================================"
echo "TEST GROUP 6: CROSS-SYSTEM INTEGRATION"
echo "========================================"
echo ""

# Test 23: Query shows Onboarder data
echo "[TEST 23] Query integrates Onboarder metadata..."
python3 Os_Toolkit.py query "Os_Toolkit.py" | grep -q "ONBOARDER TOOL PROFILE"
test_result "Onboarder integration in query"

# Test 24: Query shows Filesync timeline
echo "[TEST 24] Query integrates Filesync timeline..."
python3 Os_Toolkit.py query "Os_Toolkit.py" | grep -q "FILESYNC TIMELINE"
test_result "Filesync integration in query"

# Test 25: Query shows Project Status
echo "[TEST 25] Query shows Project Status (marks/todos)..."
python3 Os_Toolkit.py query "Os_Toolkit.py" | grep -q "PROJECT STATUS"
test_result "Project Status in query"

# Test 26: File command shows all three sources
echo "[TEST 26] File command integrates all data sources..."
python3 Os_Toolkit.py file Os_Toolkit.py 2>/dev/null | grep -q "6W1H" && \
python3 Os_Toolkit.py file Os_Toolkit.py 2>/dev/null | grep -q "FILESYNC" && \
python3 Os_Toolkit.py file Os_Toolkit.py 2>/dev/null | grep -q "PROJECT STATUS"
test_result "Unified file analysis (3 sources)"

echo ""
echo "========================================"
echo "TEST GROUP 7: SECURITY & TRUST"
echo "========================================"
echo ""

# Test 27: Trust registry exists
echo "[TEST 27] Trust registry file exists..."
[ -f "babel_data/profile/trust_registry.json" ]
test_result "Trust registry file"

# Test 28: Trust registry has structure
echo "[TEST 28] Trust registry has valid structure..."
python3 -c "import json; reg=json.load(open('babel_data/profile/trust_registry.json')); assert 'baseline_snapshot' in reg" 2>/dev/null
test_result "Trust registry structure"

# Test 29: Telemetry in artifacts
echo "[TEST 29] Session artifacts have telemetry..."
python3 -c "
import json, glob
sessions = sorted(glob.glob('babel_data/profile/sessions/*/session_data.json'))
if sessions:
    data = json.load(open(sessions[-1]))
    artifacts_with_telemetry = sum(1 for a in data.get('artifacts', {}).values() if 'telemetry' in a.get('properties', {}))
    print(f'Telemetry coverage: {artifacts_with_telemetry} artifacts')
    assert artifacts_with_telemetry > 0
" 2>/dev/null
test_result "Artifact telemetry coverage"

# Test 30: Security check runs
echo "[TEST 30] Security check action..."
python3 Os_Toolkit.py actions --run check_security > /dev/null 2>&1
test_result "Security check execution"

echo ""
echo "========================================"
echo "FINAL RESULTS"
echo "========================================"
echo ""
echo -e "Tests Passed: ${GREEN}$PASS${NC}"
echo -e "Tests Failed: ${YELLOW}$FAIL${NC}"
echo -e "Total Tests: $((PASS + FAIL))"
echo ""

if [ $FAIL -eq 0 ]; then
    echo -e "${GREEN}🎉 ALL TESTS PASSED!${NC}"
    exit 0
else
    echo -e "${YELLOW}⚠️  Some tests failed. Review output above.${NC}"
    exit 1
fi
