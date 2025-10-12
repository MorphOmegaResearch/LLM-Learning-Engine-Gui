#!/usr/bin/env python3
"""Point 1: Tool Registration Consistency Investigation"""

import yaml
import ast
import re
from pathlib import Path

def extract_tools_from_python(file_path, pattern):
    """Extract tool names from Python source code."""
    with open(file_path, 'r') as f:
        content = f.read()

    tools = set()

    # Find the specific dict/section
    if 'ToolManager.tools' in pattern:
        # Extract from self.tools = {...}
        match = re.search(r'self\.tools\s*=\s*\{([^}]+)\}', content, re.DOTALL)
        if match:
            dict_content = match.group(1)
            # Extract quoted strings (tool names)
            tool_names = re.findall(r'"([^"]+)":', dict_content)
            tools.update(tool_names)

    elif 'tool_definitions' in pattern:
        # Extract from tool_definitions = {...}
        # We need to find top-level keys only, which have "type": "function"
        match = re.search(r'tool_definitions\s*=\s*\{', content)
        if match:
            start_pos = match.end()
            brace_count = 1
            pos = start_pos
            dict_section = '{'

            while pos < len(content) and brace_count > 0:
                char = content[pos]
                dict_section += char
                if char == '{':
                    brace_count += 1
                elif char == '}':
                    brace_count -= 1
                pos += 1

            # Extract only top-level tool names (those followed by "type": "function")
            # Pattern: "tool_name": { "type": "function"
            tool_names = re.findall(r'"([^"]+)":\s*\{\s*"type":\s*"function"', dict_section)
            tools.update(tool_names)

    elif 'risk_profiles' in pattern:
        # Extract from risk_profiles
        match = re.search(r'risk_profiles\s*=\s*\{', content)
        if match:
            start_pos = match.end()
            brace_count = 1
            pos = start_pos
            dict_section = '{'

            while pos < len(content) and brace_count > 0:
                char = content[pos]
                dict_section += char
                if char == '{':
                    brace_count += 1
                elif char == '}':
                    brace_count -= 1
                pos += 1

            # Extract tool names from the dict section (may use single or double quotes)
            tool_names = re.findall(r"['\"]([^'\"]+)['\"]:\s*ToolRiskLevel", dict_section)
            tools.update(tool_names)

    return sorted(tools)

def extract_tools_from_yaml(file_path):
    """Extract tool names from YAML config."""
    with open(file_path, 'r') as f:
        config = yaml.safe_load(f)

    if 'tools' in config and 'enabled' in config['tools']:
        return sorted(config['tools']['enabled'])
    return []

def main():
    base_dir = Path('/home/commander/.local/lib/python3.10/site-packages/opencode')
    config_dir = Path('/home/commander/Desktop/BackupOpencode/versions/v1.2')

    print("=" * 80)
    print("POINT 1: TOOL REGISTRATION CONSISTENCY INVESTIGATION")
    print("=" * 80)
    print()

    # 1. Tools registered in ToolManager.tools dict
    print("1. ToolManager.tools dict (tools.py ~line 1145):")
    tools_py = base_dir / 'tools.py'
    manager_tools = extract_tools_from_python(tools_py, 'ToolManager.tools')
    print(f"   Count: {len(manager_tools)}")
    for tool in manager_tools:
        print(f"   - {tool}")
    print()

    # 2. Tools with schemas in tool_definitions dict
    print("2. tool_definitions dict (tools.py ~line 1238):")
    schema_tools = extract_tools_from_python(tools_py, 'tool_definitions')
    print(f"   Count: {len(schema_tools)}")
    for tool in schema_tools:
        print(f"   - {tool}")
    print()

    # 3. Tools in config.yaml enabled list
    print("3. config.yaml tools.enabled (v1.2/config.yaml line 135):")
    config_yaml = config_dir / 'config.yaml'
    config_tools = extract_tools_from_yaml(config_yaml)
    print(f"   Count: {len(config_tools)}")
    for tool in config_tools:
        print(f"   - {tool}")
    print()

    # 4. Tools in tool_orchestrator risk_profiles
    print("4. tool_orchestrator.py risk_profiles (line 100):")
    orchestrator_py = base_dir / 'tool_orchestrator.py'
    risk_tools = extract_tools_from_python(orchestrator_py, 'risk_profiles')
    print(f"   Count: {len(risk_tools)}")
    for tool in risk_tools:
        print(f"   - {tool}")
    print()

    # ANALYSIS
    print("=" * 80)
    print("CONSISTENCY ANALYSIS:")
    print("=" * 80)
    print()

    # Find discrepancies
    all_tools = set(manager_tools + schema_tools + config_tools + risk_tools)

    print(f"Total unique tools across all locations: {len(all_tools)}")
    print()

    # Check each location against others
    manager_set = set(manager_tools)
    schema_set = set(schema_tools)
    config_set = set(config_tools)
    risk_set = set(risk_tools)

    print("Missing from ToolManager.tools:")
    missing = (schema_set | config_set | risk_set) - manager_set
    if missing:
        for tool in sorted(missing):
            print(f"  - {tool}")
    else:
        print("  None - All tools registered!")
    print()

    print("Missing from tool_definitions (schemas):")
    missing = (manager_set | config_set | risk_set) - schema_set
    if missing:
        for tool in sorted(missing):
            print(f"  - {tool}")
    else:
        print("  None - All tools have schemas!")
    print()

    print("Missing from config.yaml enabled:")
    missing = (manager_set | schema_set | risk_set) - config_set
    if missing:
        for tool in sorted(missing):
            print(f"  - {tool}")
    else:
        print("  None - All tools enabled!")
    print()

    print("Missing from risk_profiles:")
    missing = (manager_set | schema_set | config_set) - risk_set
    if missing:
        for tool in sorted(missing):
            print(f"  - {tool}")
    else:
        print("  None - All tools have risk profiles!")
    print()

    # Check for perfect consistency
    if manager_set == schema_set == config_set == risk_set:
        print("✅ PERFECT CONSISTENCY: All 4 locations have identical tool sets!")
    else:
        print("❌ INCONSISTENCY DETECTED: Tool sets differ across locations")

    print()
    print("=" * 80)

if __name__ == '__main__':
    main()
