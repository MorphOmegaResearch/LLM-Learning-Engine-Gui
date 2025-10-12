#!/usr/bin/env python3
"""
Reorganize Trainer folder to new structure
"""

import os
import shutil
from pathlib import Path

TRAINER_ROOT = Path(__file__).parent.parent

print("=" * 60)
print("  Reorganizing Trainer Folder")
print("=" * 60)
print()

# Create new structure
folders = {
    "Models": "Trained models and their outputs",
    "Training_Data-Sets/Tools": "OpenCode tool training examples",
    "Training_Data-Sets/App_Development": "App development training data",
    "Training_Data-Sets/Coding": "General coding training data",
    "Training_Data-Sets/Semantic_States": "Semantic state training data",
    "Data": "Python scripts and utilities"
}

print("Creating folder structure...")
for folder, desc in folders.items():
    path = TRAINER_ROOT / folder
    path.mkdir(parents=True, exist_ok=True)
    print(f"  ✓ {folder:40} - {desc}")

print()

# Move files to correct locations
moves = [
    # Python scripts to Data/
    ("*.py", "Data/"),

    # Training outputs to Models/
    ("training_*", "Models/"),

    # Exports to Data/
    ("exports", "Data/"),

    # Desktop launchers stay at root
    # (TRAIN.desktop, TEST.desktop)
]

print("Moving files...")
for pattern, dest in moves:
    src_path = TRAINER_ROOT / pattern
    dest_path = TRAINER_ROOT / dest

    if '*' in pattern:
        # Glob pattern
        import glob
        for file in glob.glob(str(src_path)):
            if os.path.basename(file) not in ['reorganize.py']:
                try:
                    shutil.move(file, str(dest_path))
                    print(f"  ✓ Moved {os.path.basename(file)} → {dest}")
                except Exception as e:
                    print(f"  ⚠ {os.path.basename(file)}: {e}")
    else:
        # Single file/folder
        if src_path.exists():
            try:
                shutil.move(str(src_path), str(dest_path))
                print(f"  ✓ Moved {pattern} → {dest}")
            except Exception as e:
                print(f"  ⚠ {pattern}: {e}")

print()
print("=" * 60)
print("  Reorganization Complete!")
print("=" * 60)
print()
print("New structure:")
print(f"{TRAINER_ROOT}/")
print("├── TRAIN.desktop")
print("├── TEST.desktop")
print("├── Models/")
print("│   └── training_<model>_<timestamp>/")
print("├── Training_Data-Sets/")
print("│   ├── Tools/")
print("│   ├── App_Development/")
print("│   ├── Coding/")
print("│   └── Semantic_States/")
print("└── Data/")
print("    ├── *.py (scripts)")
print("    └── exports/")
