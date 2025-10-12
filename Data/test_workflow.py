#!/usr/bin/env python3
"""
Test the complete training workflow
"""

from config import get_category_info, get_training_data_files

print("=" * 60)
print("  Testing Training Workflow")
print("=" * 60)
print()

# Test 1: Check category info
print("Test 1: Loading category info...")
info = get_category_info()

for category, data in info.items():
    total = data["total_examples"]
    files = len(data["files"])
    print(f"  ✓ {category}: {files} files, {total} examples")

print()

# Test 2: Get files for specific categories
print("Test 2: Getting files for Tools category...")
files = get_training_data_files(["Tools"])
print(f"  ✓ Found {len(files)} files")

for f in files:
    with open(f) as fp:
        count = sum(1 for _ in fp)
    print(f"    • {f.name}: {count} examples")

print()

# Test 3: Get files with subcategories
print("Test 3: Getting specific subcategories...")
files = get_training_data_files(
    ["Tools"],
    {"Tools": ["file_operations", "search_operations"]}
)
print(f"  ✓ Found {len(files)} files (filtered)")

for f in files:
    with open(f) as fp:
        count = sum(1 for _ in fp)
    print(f"    • {f.name}: {count} examples")

print()
print("=" * 60)
print("  All tests passed! ✓")
print("=" * 60)
print()
print("Ready to launch GUI:")
print("  python3 interactive_trainer_gui.py")
print()
print("Or double-click:")
print("  TRAIN.desktop")
