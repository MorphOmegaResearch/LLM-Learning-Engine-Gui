#!/usr/bin/env python3
"""
One-time migration script to convert legacy tool settings to unified Tool Profile.
Run this manually if you want to migrate without waiting for GUI auto-migration.
"""

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import migrate_tool_profile_from_legacy, TOOL_PROFILES_DIR

if __name__ == "__main__":
    print("=" * 60)
    print("Tool Profile Migration")
    print("=" * 60)
    print()

    try:
        prof = migrate_tool_profile_from_legacy("Default")
        print("✅ Successfully migrated to unified Tool Profile: 'Default'")
        print()
        print(f"📁 Location: {TOOL_PROFILES_DIR / 'Default.json'}")
        print()
        print("📋 Profile sections:")
        for key in prof.keys():
            print(f"   - {key}")
        print()
        print("🔧 Enabled tools:")
        enabled = prof.get("tools", {}).get("enabled_tools", {})
        if enabled:
            for tool, status in enabled.items():
                if status:
                    print(f"   ✓ {tool}")
        else:
            print("   (none)")
        print()
        print("⚠️  Legacy files remain unchanged. After verifying the profile works,")
        print("   you can optionally remove:")
        print("   - Data/tabs/custom_code_tab/tool_settings.json")
        print("   - Data/tabs/custom_code_tab/custom_code_settings.json")

    except Exception as e:
        print(f"❌ Migration failed: {e}")
        sys.exit(1)
