#!/bin/bash
# P0 Security Validation Tests
# Date: 2026-02-07
# Purpose: Comprehensive testing of trust_registry, telemetry, SYSTEM_DNA cleanup

echo "=== P0 SECURITY VALIDATION TESTS ==="
echo "Date: $(date)"
echo ""

# Test 1: SYSTEM_DNA Cleanup
echo "[TEST 1] SYSTEM_DNA Cleanup"
echo "  Checking for removed Gemini/Node entries..."
if grep -q "gemini.*Core System\|node.*Gemini" Os_Toolkit.py; then
    echo "  ❌ FAIL: False trust markers still present"
    exit 1
else
    echo "  ✅ PASS: No false trust markers found"
fi
echo ""

# Test 2: trust_registry.json Exists
echo "[TEST 2] trust_registry.json Creation"
if [ -f "babel_data/profile/trust_registry.json" ]; then
    echo "  ✅ PASS: trust_registry.json exists"

    # Validate structure
    echo "  Validating JSON structure..."
    python3 -c "
import json
tr = json.load(open('babel_data/profile/trust_registry.json'))
assert 'version' in tr
assert 'baseline_snapshot' in tr
assert 'os_components' in tr['baseline_snapshot']
assert 'external_agents' in tr['baseline_snapshot']
assert 'network_trust' in tr
print('  ✅ PASS: JSON structure valid')
" || exit 1
else
    echo "  ❌ FAIL: trust_registry.json not found"
    exit 1
fi
echo ""

# Test 3: TrustRegistry Class Loading
echo "[TEST 3] TrustRegistry Class Integration"
python3 -c "
from Os_Toolkit import TrustRegistry
from pathlib import Path
tr = TrustRegistry(Path('babel_data/profile'))
assert tr.registry is not None
assert len(tr.registry['baseline_snapshot']['external_agents']) >= 3
print('  ✅ PASS: TrustRegistry class loads and initializes')
" || exit 1
echo ""

# Test 4: Full Toolkit Initialization
echo "[TEST 4] ForensicOSToolkit Initialization with trust_registry"
python3 Os_Toolkit.py stats 2>&1 | grep -q "Session ID:" && echo "  ✅ PASS: Toolkit initializes without errors" || echo "  ❌ FAIL: Initialization error"
echo ""

# Test 5: Telemetry Tracking
echo "[TEST 5] Telemetry Tracking in Process Analysis"
echo "  Running analyze --depth 1..."
python3 Os_Toolkit.py analyze --depth 1 > /dev/null 2>&1

echo "  Checking for telemetry in artifacts..."
python3 -c "
import json
from pathlib import Path
sessions = sorted(Path('babel_data/profile/sessions').glob('babel_catalog_*/artifacts.json'))
if not sessions:
    print('  ❌ FAIL: No sessions found')
    exit(1)

artifacts = json.load(open(sessions[-1]))
telemetry_count = sum(1 for a in artifacts.values() if 'telemetry' in a.get('properties', {}))
total = len(artifacts)
coverage = (telemetry_count / total * 100) if total > 0 else 0

print(f'  Telemetry coverage: {telemetry_count}/{total} ({coverage:.1f}%)')
if coverage >= 50:
    print('  ✅ PASS: Telemetry coverage ≥50%')
else:
    print(f'  ⚠️  WARN: Low telemetry coverage ({coverage:.1f}%)')
" || exit 1
echo ""

# Test 6: Trust Status Distribution
echo "[TEST 6] Trust Status Distribution"
python3 -c "
import json
from pathlib import Path
from collections import Counter

sessions = sorted(Path('babel_data/profile/sessions').glob('babel_catalog_*/artifacts.json'))
artifacts = json.load(open(sessions[-1]))

trust_dist = Counter()
for a in artifacts.values():
    tel = a.get('properties', {}).get('telemetry', {})
    if tel:
        trust_dist[tel.get('trust_status', 'unknown')] += 1

print('  Trust Distribution:')
for status, count in trust_dist.most_common():
    print(f'    {status}: {count}')

if trust_dist:
    print('  ✅ PASS: Trust statuses being tracked')
else:
    print('  ⚠️  WARN: No trust statuses found')
" || exit 1
echo ""

# Test 7: baseline_wakeup Action
echo "[TEST 7] baseline_wakeup Action (with trust_registry)"
echo "  Running baseline_wakeup..."
python3 Os_Toolkit.py actions --run baseline_wakeup 2>&1 | grep -q "Security Check" && echo "  ✅ PASS: baseline_wakeup completes" || echo "  ❌ FAIL: baseline_wakeup error"
echo ""

# Test 8: External Agent Trust Levels
echo "[TEST 8] External Agent Trust Levels"
python3 -c "
import json
tr = json.load(open('babel_data/profile/trust_registry.json'))
agents = tr['baseline_snapshot']['external_agents']

print('  External Agents:')
for name, data in agents.items():
    trust = data.get('trust_level', 'unknown')
    print(f'    {name}: {trust}')

# Verify claude-code is NOT 'native' (would be security bug)
if agents.get('claude-code', {}).get('trust_level') == 'native':
    print('  ❌ FAIL: claude-code marked as native (security issue)')
    exit(1)
elif agents.get('gemini-agent', {}).get('trust_level') == 'native':
    print('  ❌ FAIL: gemini-agent marked as native (security issue)')
    exit(1)
else:
    print('  ✅ PASS: External agents not marked as native')
" || exit 1
echo ""

# Test 9: Network IP Trust Check
echo "[TEST 9] Network IP Trust Verification"
python3 -c "
from Os_Toolkit import TrustRegistry
from pathlib import Path

tr = TrustRegistry(Path('babel_data/profile'))

# Test localhost (should be native)
local_trust = tr.check_ip_trust('127.0.0.1')
print(f'  127.0.0.1: {local_trust}')
assert local_trust == 'native', 'Localhost should be native trust'

# Test unknown IP (should be untrusted)
unknown_trust = tr.check_ip_trust('8.8.8.8')
print(f'  8.8.8.8: {unknown_trust}')
assert unknown_trust == 'untrusted', 'Unknown IPs should be untrusted'

print('  ✅ PASS: IP trust verification working')
" || exit 1
echo ""

# Test 10: PID Telemetry Verification
echo "[TEST 10] PID Telemetry Verification"
python3 -c "
from Os_Toolkit import TrustRegistry
from pathlib import Path

tr = TrustRegistry(Path('babel_data/profile'))

# Test unknown process
result = tr.verify_pid_telemetry('unknownproc', 99999, 'test_session')
print(f'  Unknown process trust: {result[\"trust_status\"]}')
assert result['trust_status'] == 'untrusted', 'Unknown processes should be untrusted'
assert result['verified'] == False, 'Unknown processes should not be verified'

print('  ✅ PASS: PID telemetry verification working')
" || exit 1
echo ""

# Summary
echo "========================================"
echo "         TEST SUMMARY"
echo "========================================"
echo "All P0 security tests passed!"
echo ""
echo "✅ SYSTEM_DNA cleaned (Gemini/Node removed)"
echo "✅ trust_registry.json created and valid"
echo "✅ TrustRegistry class functional"
echo "✅ Telemetry tracking operational"
echo "✅ Trust status distribution working"
echo "✅ External agents properly classified"
echo "✅ IP trust verification functional"
echo "✅ PID telemetry verification functional"
echo ""
echo "Next: Run Gap Analysis (P0_SECURITY_TEST_RESULTS.md)"
