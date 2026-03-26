#!/usr/bin/env python3
"""Point 3: Tool Execution Flow Investigation"""

import re
from pathlib import Path

def trace_execution_path(file_path, start_pattern, depth=0, max_depth=3):
    """Trace execution flow from a starting point."""
    if depth > max_depth:
        return []

    with open(file_path, 'r') as f:
        content = f.read()
        lines = f.readlines()

    findings = []

    # Find the starting pattern
    matches = list(re.finditer(start_pattern, content, re.MULTILINE))
    for match in matches:
        # Get line number
        line_num = content[:match.start()].count('\n') + 1
        findings.append({
            'file': file_path.name,
            'line': line_num,
            'match': match.group(0)[:100],
            'depth': depth
        })

    return findings

def main():
    base_dir = Path('/home/commander/.local/lib/python3.10/site-packages/opencode')

    print("=" * 80)
    print("POINT 3: TOOL EXECUTION FLOW INVESTIGATION")
    print("=" * 80)
    print()

    # Trace execution from tool_call detection to actual execution
    print("EXECUTION PATH TRACE:")
    print("-" * 80)
    print()

    interactive_py = base_dir / 'interactive.py'

    # Step 1: Tool call detected
    print("Step 1: Tool Call Detection")
    print("  Location: interactive.py:3230")
    print("  Code: tool_call = self.lc_adapter.parse_and_validate(response)")
    print()

    # Step 2: Find where tool_call is used after detection
    if interactive_py.exists():
        with open(interactive_py, 'r') as f:
            lines = f.readlines()

        print("Step 2: After Detection - What happens to tool_call?")
        print("  Searching for tool_call usage after line 3230...")
        print()

        # Find usage patterns after line 3230
        for i in range(3230, min(len(lines), 3500)):
            line = lines[i].strip()
            if 'tool_call' in line and not line.startswith('#'):
                if any(keyword in line for keyword in ['if tool_call', 'tool_call.get', 'tool_call[', 'execute_tool']):
                    print(f"  Line {i+1}: {line[:100]}")

        print()

    # Step 3: Find tool execution methods
    print("Step 3: Tool Execution Methods")
    print("-" * 80)

    for filename in ['interactive.py', 'tool_orchestrator.py', 'tools.py']:
        filepath = base_dir / filename
        if not filepath.exists():
            continue

        with open(filepath, 'r') as f:
            content = f.read()

        # Find execute methods
        execute_methods = re.findall(r'(async def|def) (execute_tool|execute|_execute_\w+)\([^)]*\):', content)
        if execute_methods:
            print(f"\n  {filename}:")
            for async_marker, method_name in execute_methods:
                print(f"    • {async_marker} {method_name}()")

    print()

    # Step 4: Orchestrator validation flow
    print("Step 4: Tool Orchestrator Validation Flow")
    print("-" * 80)

    orchestrator = base_dir / 'tool_orchestrator.py'
    if orchestrator.exists():
        with open(orchestrator, 'r') as f:
            lines = f.readlines()

        print("\n  Validation methods:")
        for i, line in enumerate(lines, 1):
            if re.search(r'(async def|def) (validate_\w+|check_\w+)\(', line):
                print(f"    Line {i}: {line.strip()[:80]}")

        print("\n  Risk assessment:")
        for i, line in enumerate(lines, 1):
            if 'get_risk_level' in line or 'risk_level' in line.lower():
                if not line.strip().startswith('#'):
                    print(f"    Line {i}: {line.strip()[:80]}")
                    if i < len(lines) - 2:
                        # Show next line for context
                        next_line = lines[i].strip()
                        if next_line and not next_line.startswith('#'):
                            print(f"              {next_line[:80]}")
                    break

    print()

    # Step 5: Confirmation gate integration
    print("Step 5: Confirmation Gate Integration")
    print("-" * 80)

    if interactive_py.exists():
        with open(interactive_py, 'r') as f:
            lines = f.readlines()

        print("\n  Confirmation prompts:")
        for i, line in enumerate(lines, 1):
            if 'Confirm.ask' in line or 'confirm' in line.lower():
                if 'tool' in line.lower() or 'execute' in line.lower():
                    print(f"    Line {i}: {line.strip()[:80]}")

    print()

    # Step 6: Actual tool execution
    print("Step 6: Actual Tool Execution (tools.py)")
    print("-" * 80)

    tools_py = base_dir / 'tools.py'
    if tools_py.exists():
        with open(tools_py, 'r') as f:
            lines = f.readlines()

        print("\n  Tool classes with execute methods:")
        current_class = None
        for i, line in enumerate(lines, 1):
            if re.search(r'class (\w+Tool)\(BaseTool\):', line):
                current_class = re.search(r'class (\w+Tool)\(BaseTool\):', line).group(1)

            if current_class and 'async def execute(' in line:
                print(f"    {current_class}: Line {i}")
                current_class = None

    print()

    # Step 7: Result handling
    print("Step 7: Tool Result Handling")
    print("-" * 80)

    if interactive_py.exists():
        with open(interactive_py, 'r') as f:
            content = f.read()

        # Find ToolResult usage
        result_patterns = [
            r'ToolResult\(',
            r'result\.success',
            r'result\.output',
            r'result\.error'
        ]

        print("\n  ToolResult usage patterns:")
        for pattern in result_patterns:
            matches = list(re.finditer(pattern, content))
            if matches:
                print(f"    '{pattern}': {len(matches)} occurrences")

        # Find result formatting
        print("\n  Result formatting:")
        format_methods = re.findall(r'def (_format_\w+)\([^)]*\):', content)
        for method in format_methods:
            if 'result' in method or 'tool' in method:
                print(f"    • {method}()")

    print()
    print("=" * 80)

if __name__ == '__main__':
    main()
