#!/usr/bin/env python3
"""
Split monolithic training data into categorized files
"""

import json
from pathlib import Path
from collections import defaultdict

# Get paths
SCRIPT_DIR = Path(__file__).parent
TRAINER_ROOT = SCRIPT_DIR.parent
TRAINING_DATA_DIR = TRAINER_ROOT / "Training_Data-Sets"
SOURCE_FILE = SCRIPT_DIR / "exports" / "training_data.jsonl"

# Category mapping: scenario -> (category, subcategory_file)
SCENARIO_MAPPING = {
    # Tools - File Operations
    "file_write_basic": ("Tools", "file_operations.jsonl"),
    "file_edit_basic": ("Tools", "file_operations.jsonl"),
    "file_read_basic": ("Tools", "file_operations.jsonl"),

    # Tools - Search Operations
    "file_search_basic": ("Tools", "search_operations.jsonl"),
    "grep_search_basic": ("Tools", "search_operations.jsonl"),
    "directory_list_basic": ("Tools", "search_operations.jsonl"),
    "auto_chain_search_read": ("Tools", "search_operations.jsonl"),

    # Tools - Git Operations
    "git_log": ("Tools", "git_operations.jsonl"),

    # Tools - System Operations
    "system_info_basic": ("Tools", "system_operations.jsonl"),
    "process_list": ("Tools", "system_operations.jsonl"),
    "system_inspection": ("Tools", "system_operations.jsonl"),

    # Tools - Web Operations
    "web_search_basic": ("Tools", "web_operations.jsonl"),
    "web_research": ("Tools", "web_operations.jsonl"),

    # Coding - Debugging
    "code_review": ("Coding", "debugging.jsonl"),
    "debug_session": ("Coding", "debugging.jsonl"),

    # Coding - Project Setup
    "project_setup": ("Coding", "project_setup.jsonl"),
    "multi_tool_workflow": ("Coding", "project_setup.jsonl"),

    # Tools - Error Recovery
    "error_recovery": ("Tools", "error_recovery.jsonl"),
}

def split_training_data():
    """Split monolithic training data into category files"""

    print("=" * 60)
    print("  Training Data Splitter")
    print("=" * 60)
    print()

    # Check source file exists
    if not SOURCE_FILE.exists():
        print(f"❌ Source file not found: {SOURCE_FILE}")
        return False

    print(f"📂 Source: {SOURCE_FILE}")
    print()

    # Read all examples
    examples_by_file = defaultdict(list)
    unknown_scenarios = []

    with open(SOURCE_FILE, 'r') as f:
        for line_num, line in enumerate(f, 1):
            try:
                example = json.loads(line.strip())
                scenario = example.get("scenario", "unknown")

                if scenario in SCENARIO_MAPPING:
                    category, filename = SCENARIO_MAPPING[scenario]
                    examples_by_file[(category, filename)].append(example)
                else:
                    unknown_scenarios.append((line_num, scenario))

            except json.JSONDecodeError as e:
                print(f"⚠️  Line {line_num}: JSON decode error - {e}")

    # Report unknown scenarios
    if unknown_scenarios:
        print(f"⚠️  Unknown scenarios ({len(unknown_scenarios)}):")
        for line_num, scenario in unknown_scenarios:
            print(f"   Line {line_num}: {scenario}")
        print()

    # Create category directories and write files
    total_written = 0

    print("📝 Writing category files...")
    print()

    for (category, filename), examples in sorted(examples_by_file.items()):
        # Create category directory
        category_dir = TRAINING_DATA_DIR / category
        category_dir.mkdir(parents=True, exist_ok=True)

        # Write file
        output_file = category_dir / filename

        with open(output_file, 'w') as f:
            for example in examples:
                f.write(json.dumps(example) + '\n')

        total_written += len(examples)
        print(f"  ✓ {category:20} {filename:30} ({len(examples):2} examples)")

    print()
    print("=" * 60)
    print(f"  ✅ Split complete!")
    print("=" * 60)
    print()
    print(f"Total examples written: {total_written}")
    print(f"Output directory: {TRAINING_DATA_DIR}")
    print()

    # Show directory tree
    print("📁 Directory structure:")
    for category_dir in sorted(TRAINING_DATA_DIR.iterdir()):
        if category_dir.is_dir():
            print(f"\n{category_dir.name}/")
            for file in sorted(category_dir.glob("*.jsonl")):
                count = sum(1 for _ in open(file))
                print(f"  ├── {file.name:30} ({count} examples)")

    print()
    return True


if __name__ == "__main__":
    success = split_training_data()

    if success:
        print("\n✅ Next steps:")
        print("  1. Review split files in Training_Data-Sets/")
        print("  2. Run interactive trainer: python3 interactive_trainer.py")
        print("  3. Select categories and start training")
    else:
        print("\n❌ Splitting failed - check errors above")
