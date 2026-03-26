#!/bin/bash
# Apply critical tool system fixes

echo "Applying critical tool system fixes..."
echo ""

# Fix 1: Add read_text schema to tools.py
echo "1. Adding read_text to tool_definitions..."
# This needs manual edit - too complex for sed

# Fix 2: Add missing tools to config.yaml
echo "2. Updating config.yaml enabled tools..."
# Already has 20 tools, just needs git_operations and resource_request documented as disabled

# Fix 3: Add read_text to risk_profiles
echo "3. Adding read_text to risk_profiles..."
# This needs manual edit in tool_orchestrator.py

echo ""
echo "MANUAL FIXES REQUIRED:"
echo ""
echo "1. tools.py (~line 1571) - Add read_text schema:"
echo "   'read_text': {"
echo "       'type': 'function',"
echo "       'function': {"
echo "           'name': 'read_text',"
echo "           'description': 'Read contents of a file (alias for file_read - if filename only, auto-searches)',"
echo "           'parameters': {"
echo "               'type': 'object',"
echo "               'properties': {"
echo "                   'file_path': {'type': 'string', 'description': 'Path to file'}"
echo "               },"
echo "               'required': ['file_path']"
echo "           }"
echo "       }"
echo "   }"
echo ""
echo "2. tool_orchestrator.py (~line 126) - Add to risk_profiles:"
echo "   'read_text': ToolRiskLevel.SAFE,  # Alias for file_read"
echo ""
echo "3. config.yaml - System prompt should mention:"
echo "   - 23 tools registered (20 enabled, 3 disabled)"
echo "   - Auto-chain capabilities"
echo "   - Alias support"
echo ""
echo "4. Test with:"
echo '   User: find "read2.txt" and describe the animal named inside'
echo "   Expected: Auto-chain file_search → file_read"
echo ""
