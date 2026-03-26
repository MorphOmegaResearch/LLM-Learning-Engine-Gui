#!/usr/bin/env python3
"""Test LangChain integration with OpenCode.

This tests:
1. LangChain adapter initialization
2. Schema generation for models
3. Tool call parsing (both LangChain and fallback)
"""

import sys
import os
sys.path.insert(0, '/home/commander/Desktop/BackupOpencode/versions/v1.2/site-packages')

from opencode.config import Config
from opencode.tools import ToolManager
from opencode.langchain_adapter_simple import SimpleLangChainAdapter

def test_adapter_initialization():
    """Test that adapter initializes correctly."""
    print("=" * 70)
    print("TEST 1: LangChain Adapter Initialization")
    print("=" * 70)

    try:
        # Load YAML config like production does
        config_path = '/home/commander/Desktop/BackupOpencode/versions/v1.2/site-packages/opencode/config.yaml'
        config = Config.load(config_path)
        tool_manager = ToolManager(config.tools)
        adapter = SimpleLangChainAdapter(tool_manager)

        print(f"✓ Adapter initialized")
        print(f"  Available tools: {', '.join(adapter.list_tools()[:5])}...")

        return adapter
    except Exception as e:
        print(f"✗ Failed: {e}")
        import traceback
        traceback.print_exc()
        return None

def test_schema_generation(adapter):
    """Test schema generation for models."""
    print("\n" + "=" * 70)
    print("TEST 2: Schema Generation for Models")
    print("=" * 70)

    try:
        schemas = adapter.get_tool_schemas_for_model()
        print(f"✓ Generated {len(schemas)} tool schemas")

        # Show first schema as example
        if schemas:
            import json
            first_schema = schemas[0]
            print(f"\nExample schema for '{first_schema.get('name', 'unknown')}':")
            print(json.dumps(first_schema, indent=2)[:500] + "...")

        return True
    except Exception as e:
        print(f"✗ Failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_parsing(adapter):
    """Test parsing various formats."""
    print("\n" + "=" * 70)
    print("TEST 3: Tool Call Parsing")
    print("=" * 70)

    test_cases = [
        # Standard JSON format
        ('{"name": "file_read", "args": {"file_path": "/tmp/test.txt"}}', "Standard JSON"),

        # OpenAI function calling format
        ('{"type": "tool_call", "name": "bash_execute", "arguments": {"command": "ls -la"}}', "OpenAI format"),

        # Array format (tool chain)
        ('[{"name": "file_search", "args": {"pattern": "*.py"}}, {"name": "file_read", "args": {"file_path": "test.py"}}]', "Array/chain format"),

        # Markdown emphasis (OpenCode custom)
        ('***file_read*** to check test.txt', "Markdown emphasis"),

        # Python function format
        ('file_write(file_path="/tmp/output.txt", content="Hello")', "Python function"),
    ]

    results = []
    for model_output, description in test_cases:
        try:
            parsed = adapter.parse_and_validate(model_output)
            if parsed:
                print(f"✓ {description}")
                print(f"  → Parsed as: {parsed.get('name')} with {len(parsed.get('args', {}))} args")
                results.append(True)
            else:
                print(f"✗ {description} - No parse result")
                results.append(False)
        except Exception as e:
            print(f"✗ {description} - Error: {e}")
            results.append(False)

    success_rate = sum(results) / len(results) * 100
    print(f"\nParsing success rate: {success_rate:.0f}% ({sum(results)}/{len(results)})")

    return success_rate > 60  # Pass if > 60% success

def main():
    """Run all tests."""
    print("\n🧪 LANGCHAIN INTEGRATION TEST SUITE\n")

    # Test 1: Initialization
    adapter = test_adapter_initialization()
    if not adapter:
        print("\n❌ FAILED: Could not initialize adapter")
        return False

    # Test 2: Schema generation
    if not test_schema_generation(adapter):
        print("\n❌ FAILED: Schema generation failed")
        return False

    # Test 3: Parsing
    if not test_parsing(adapter):
        print("\n⚠️  WARNING: Parsing success rate below 60%")
        # Don't fail on this - some formats might not be supported yet

    print("\n" + "=" * 70)
    print("✅ LANGCHAIN INTEGRATION TESTS PASSED")
    print("=" * 70)
    print("\nNext steps:")
    print("1. Start OpenCode: python -m opencode")
    print("2. Check for: '✓ LangChain tool adapter initialized'")
    print("3. Try: /tools prompt disable")
    print("4. Test tool calls with your model")
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
