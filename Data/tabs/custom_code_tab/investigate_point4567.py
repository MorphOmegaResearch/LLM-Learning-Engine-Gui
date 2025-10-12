#!/usr/bin/env python3
"""Points 4-7: Tool Chains Investigation"""

import re
from pathlib import Path

def main():
    base_dir = Path('/home/commander/.local/lib/python3.10/site-packages/opencode')

    print("=" * 80)
    print("POINTS 4-7: TOOL CHAINS INVESTIGATION")
    print("=" * 80)
    print()

    # POINT 4: Tool Chain Detection
    print("POINT 4: TOOL CHAIN DETECTION")
    print("-" * 80)

    interactive_py = base_dir / 'interactive.py'
    if interactive_py.exists():
        with open(interactive_py, 'r') as f:
            lines = f.readlines()

        print("\nChain detection patterns in interactive.py:")
        for i, line in enumerate(lines, 1):
            if 'tool_chain' in line.lower() and 'detect' in line.lower():
                print(f"  Line {i}: {line.strip()[:90]}")

        # Find the actual detection logic
        print("\nChain format detection (lines 3238-3280):")
        in_chain_detect = False
        for i in range(3238, min(3290, len(lines))):
            line = lines[i]
            if 'TOOL CHAIN DETECTION' in line or 'Format 1:' in line or 'Format 2:' in line:
                in_chain_detect = True
            if in_chain_detect:
                print(f"  {i+1}: {line.rstrip()}")
                if 'tool_chain_detected = True' in line:
                    break

    print()

    # POINT 5: Individual Tool Handling in Chains
    print("POINT 5: TOOL CHAINS - INDIVIDUAL TOOL HANDLING")
    print("-" * 80)

    if interactive_py.exists():
        with open(interactive_py, 'r') as f:
            lines = f.readlines()

        print("\nSequential execution logic (lines 3313-3350):")
        for i in range(3313, min(3351, len(lines))):
            line = lines[i]
            if line.strip():
                print(f"  {i+1}: {line.rstrip()}")

    print()

    # POINT 6: Auto-Chaining Logic
    print("POINT 6: AUTO-CHAINING LOGIC")
    print("-" * 80)

    # Check config for auto_chain setting
    config_path = Path('/home/commander/Desktop/BackupOpencode/versions/v1.2/config.yaml')
    if config_path.exists():
        with open(config_path, 'r') as f:
            content = f.read()

        if 'auto_chain' in content:
            print("\n  Config setting found:")
            for i, line in enumerate(content.split('\n'), 1):
                if 'auto_chain' in line:
                    print(f"    Line {i}: {line}")
        else:
            print("\n  ⚠️  No auto_chain config setting found")

    # Check system prompt for auto-chain documentation
    print("\n  System prompt documentation (config.yaml lines 128-131):")
    if config_path.exists():
        with open(config_path, 'r') as f:
            lines = f.readlines()
        for i in range(127, min(132, len(lines))):
            print(f"    {i+1}: {lines[i].rstrip()}")

    # Check for auto-chain implementation
    print("\n  Auto-chain implementation in interactive.py:")
    if interactive_py.exists():
        with open(interactive_py, 'r') as f:
            content = f.read()

        # Find auto-chain logic
        auto_chain_matches = list(re.finditer(r'auto.?chain', content, re.IGNORECASE))
        if auto_chain_matches:
            print(f"    Found {len(auto_chain_matches)} references to auto-chain")
            # Show unique line numbers
            lines_found = set()
            for match in auto_chain_matches:
                line_num = content[:match.start()].count('\n') + 1
                lines_found.add(line_num)
            print(f"    Lines: {sorted(list(lines_found))[:10]}")
        else:
            print("    ⚠️  No auto-chain implementation found")

    print()

    # POINT 7: Tool Chain Result Communication
    print("POINT 7: TOOL CHAIN RESULT COMMUNICATION")
    print("-" * 80)

    if interactive_py.exists():
        with open(interactive_py, 'r') as f:
            lines = f.readlines()

        print("\nChain result aggregation (lines 3315-3350):")
        print("  Key variables:")
        for i in range(3315, min(3351, len(lines))):
            line = lines[i]
            if 'chain_results' in line or 'result' in line.lower():
                if not line.strip().startswith('#'):
                    print(f"    {i+1}: {line.rstrip()[:90]}")

        # Find where results are communicated to model
        print("\n  Result formatting for model:")
        for i, line in enumerate(lines, 1):
            if 'format_tool_result' in line or '_format_' in line:
                if 'chain' in line.lower():
                    print(f"    Line {i}: {line.strip()[:90]}")

    # Check for auto_chain field in results
    print("\n  Auto-chain result field:")
    if interactive_py.exists():
        with open(interactive_py, 'r') as f:
            content = f.read()

        auto_chain_field = re.findall(r'"auto_chain":\s*\w+', content)
        if auto_chain_field:
            print(f"    Found: {len(auto_chain_field)} occurrences")
            for field in set(auto_chain_field)[:3]:
                print(f"      {field}")
        else:
            print("    ⚠️  No auto_chain field in results")

    print()
    print("=" * 80)
    print("TOOL CHAIN FINDINGS SUMMARY:")
    print("=" * 80)
    print()

    print("Format Support:")
    print("  ✓ Format 1: {\"type\":\"tool_chain\",\"tools\":[...]}")
    print("  ✓ Format 2: [{\"name\":\"tool1\",...},{\"name\":\"tool2\",...}]")
    print()

    print("Execution:")
    print("  ✓ Sequential execution with early termination on failure")
    print("  ✓ Each tool goes through _safe_execute_tool()")
    print("  ✓ Progress tracking with chain_results list")
    print()

    print("Auto-chaining:")
    print("  Status: Checking implementation...")

    # Final check for auto-chain
    if interactive_py.exists():
        with open(interactive_py, 'r') as f:
            content = f.read()

        if 'file_search' in content and 'file_read' in content and 'auto' in content:
            # Look for file_search -> file_read auto-chain
            pattern = r'file_search.*?file_read|auto.*?chain.*?file_search'
            if re.search(pattern, content, re.IGNORECASE | re.DOTALL):
                print("  ⚠️  Possible auto-chain logic found (needs manual verification)")
            else:
                print("  ❌ No auto-chain implementation detected")
        else:
            print("  ❌ No auto-chain implementation detected")

    print()

if __name__ == '__main__':
    main()
