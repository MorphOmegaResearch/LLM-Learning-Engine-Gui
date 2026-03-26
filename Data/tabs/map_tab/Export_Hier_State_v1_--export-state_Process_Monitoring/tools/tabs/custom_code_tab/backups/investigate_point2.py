#!/usr/bin/env python3
"""Point 2: Tool Call Detection & Parsing Investigation"""

import re
from pathlib import Path

def find_detection_logic(file_path, search_terms):
    """Find where tool calls are detected in source code."""
    with open(file_path, 'r') as f:
        lines = f.readlines()

    findings = []
    for i, line in enumerate(lines, 1):
        for term in search_terms:
            if term in line and not line.strip().startswith('#'):
                findings.append({
                    'line': i,
                    'content': line.strip(),
                    'term': term
                })
    return findings

def main():
    base_dir = Path('/home/commander/.local/lib/python3.10/site-packages/opencode')

    print("=" * 80)
    print("POINT 2: TOOL CALL DETECTION & PARSING INVESTIGATION")
    print("=" * 80)
    print()

    # Key files to investigate
    files_to_check = {
        'interactive.py': base_dir / 'interactive.py',
        'langchain_adapter_simple.py': base_dir / 'langchain_adapter_simple.py',
        'format_translator.py': base_dir / 'format_translator.py',
        'tool_orchestrator.py': base_dir / 'tool_orchestrator.py'
    }

    # Detection terms
    detection_terms = [
        'tool_call',
        'parse',
        'detect',
        '"type":',
        'json.loads',
        'translate_tool_call',
        'parse_and_validate'
    ]

    print("DETECTION POINTS:")
    print("-" * 80)
    print()

    for filename, filepath in files_to_check.items():
        if not filepath.exists():
            print(f"⚠️  {filename}: FILE NOT FOUND")
            continue

        print(f"📄 {filename}:")
        findings = find_detection_logic(filepath, detection_terms)

        if findings:
            # Group by term
            by_term = {}
            for f in findings:
                term = f['term']
                if term not in by_term:
                    by_term[term] = []
                by_term[term].append(f)

            for term, items in sorted(by_term.items()):
                print(f"\n  Term: '{term}' ({len(items)} occurrences)")
                for item in items[:3]:  # Show first 3 of each term
                    print(f"    Line {item['line']}: {item['content'][:100]}")
                if len(items) > 3:
                    print(f"    ... and {len(items) - 3} more")
        else:
            print("  No detection logic found")

        print()

    # PARSING STRATEGIES
    print("=" * 80)
    print("PARSING STRATEGIES ANALYSIS:")
    print("=" * 80)
    print()

    # Check langchain_adapter_simple.py for parsing strategies
    lc_adapter = base_dir / 'langchain_adapter_simple.py'
    if lc_adapter.exists():
        with open(lc_adapter, 'r') as f:
            content = f.read()

        print("SimpleLangChainAdapter Parsing Methods:")
        print("-" * 80)

        # Find method definitions
        methods = re.findall(r'def (_try_\w+|parse_and_validate)\(self.*?\):', content)
        for method in methods:
            print(f"  • {method}()")

            # Find the method body
            method_pattern = rf'def {re.escape(method)}\(.*?\):(.*?)(?=\n    def |\nclass |\Z)'
            match = re.search(method_pattern, content, re.DOTALL)
            if match:
                body = match.group(1)
                # Extract key logic lines
                lines = [l.strip() for l in body.split('\n') if l.strip() and not l.strip().startswith('#')]
                print(f"    Strategy lines: {len(lines)}")

                # Show return statements
                returns = [l for l in lines if 'return' in l]
                if returns:
                    print(f"    Returns:")
                    for r in returns[:2]:
                        print(f"      - {r[:80]}")

        print()

    # Check format_translator.py
    translator = base_dir / 'format_translator.py'
    if translator.exists():
        with open(translator, 'r') as f:
            content = f.read()

        print("FormatTranslator Methods:")
        print("-" * 80)

        methods = re.findall(r'def (translate_\w+|_\w+_format)\(self.*?\):', content)
        for method in methods:
            print(f"  • {method}()")

        print()

    # PARSING FLOW
    print("=" * 80)
    print("PARSING FLOW:")
    print("=" * 80)
    print()

    interactive_py = base_dir / 'interactive.py'
    if interactive_py.exists():
        with open(interactive_py, 'r') as f:
            lines = f.readlines()

        print("Main loop tool detection (interactive.py):")
        print("-" * 80)

        # Find main processing logic
        for i, line in enumerate(lines, 1):
            if 'lc_adapter.parse_and_validate' in line:
                print(f"  Line {i}: Uses lc_adapter.parse_and_validate()")
                # Show context
                start = max(0, i - 3)
                end = min(len(lines), i + 3)
                for j in range(start, end):
                    prefix = ">>>" if j == i - 1 else "   "
                    print(f"    {prefix} {j+1}: {lines[j].rstrip()}")
                print()

            if 'format_translator.translate_tool_call' in line:
                print(f"  Line {i}: Uses format_translator.translate_tool_call()")
                start = max(0, i - 3)
                end = min(len(lines), i + 3)
                for j in range(start, end):
                    prefix = ">>>" if j == i - 1 else "   "
                    print(f"    {prefix} {j+1}: {lines[j].rstrip()}")
                print()

    print("=" * 80)

if __name__ == '__main__':
    main()
