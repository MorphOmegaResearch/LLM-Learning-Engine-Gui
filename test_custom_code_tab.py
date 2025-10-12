#!/usr/bin/env python3
"""
Test script for Custom Code Tab
Verifies that the tab loads correctly
"""

import sys
from pathlib import Path

# Add Data directory to path
sys.path.insert(0, str(Path(__file__).parent / "Data"))

print("Testing Custom Code Tab imports...")

try:
    from tabs.custom_code_tab import CustomCodeTab
    print("✓ CustomCodeTab imported successfully")
except Exception as e:
    print(f"✗ Failed to import CustomCodeTab: {e}")
    sys.exit(1)

try:
    from tabs.custom_code_tab.sub_tabs.chat_interface_tab import ChatInterfaceTab
    print("✓ ChatInterfaceTab imported successfully")
except Exception as e:
    print(f"✗ Failed to import ChatInterfaceTab: {e}")
    sys.exit(1)

print("\n✓ All imports successful!")
print("\nTo enable the Custom Code tab:")
print("1. Launch the trainer: ./launch_trainer.sh")
print("2. Go to Settings → Tab Manager")
print("3. Enable 'Custom Code Tab'")
print("4. Restart the application")

print("\nAlternatively, edit Data/settings.json and set:")
print('  "custom_code_tab_enabled": true')
