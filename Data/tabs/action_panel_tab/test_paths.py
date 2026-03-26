#!/usr/bin/env python3
"""Quick diagnostic to verify OnboardingManager path resolution"""

from pathlib import Path

# Simulate onboarder.py initialization
base_dir = Path.cwd()
print(f"Current working directory: {base_dir}")
print()

BABEL_ROOT = "babel_data"
PROFILE_DIR_NAME = "profile"
TIMELINE_DIR_NAME = "timeline"
INVENTORY_DIR_NAME = "inventory"

babel_root = base_dir / BABEL_ROOT
inventory_dir = babel_root / INVENTORY_DIR_NAME
profile_dir = babel_root / PROFILE_DIR_NAME
timeline_dir = babel_root / TIMELINE_DIR_NAME

print("Computed paths:")
print(f"  babel_root:     {babel_root}")
print(f"  inventory_dir:  {inventory_dir}")
print(f"  profile_dir:    {profile_dir}")
print(f"  timeline_dir:   {timeline_dir}")
print()

print("Exists check:")
print(f"  babel_root exists:    {babel_root.exists()}")
print(f"  profile_dir exists:   {profile_dir.exists()}")
print(f"  timeline_dir exists:  {timeline_dir.exists()}")
print()

# Check what Os_Toolkit.py would compute
_babel_profile = Path.cwd() / "babel_data" / "profile"
DEFAULT_BASE_DIR = _babel_profile if _babel_profile.exists() else Path.cwd() / "forekit_data"

print("Os_Toolkit.py module constants:")
print(f"  DEFAULT_BASE_DIR: {DEFAULT_BASE_DIR}")
print(f"  Would create subdirs under: {DEFAULT_BASE_DIR}")
