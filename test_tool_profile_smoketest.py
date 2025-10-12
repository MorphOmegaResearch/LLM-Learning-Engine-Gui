#!/usr/bin/env python3
"""
Smoketest for Tool Profile hardening (from Commander's audit).
Tests atomic writes, soft validation, migration idempotency, and file filtering.
"""

import sys
from pathlib import Path

# Add Data directory to path
sys.path.insert(0, str(Path(__file__).parent / "Data"))

from config import (
    list_tool_profiles,
    load_tool_profile,
    save_tool_profile,
    get_unified_tool_profile,
    TOOL_PROFILES_DIR
)

def test_1_create_and_save():
    """Test atomic write + backup creation."""
    print("\n[Test 1] Create & save basic profile...")
    sample = {
        "tools": {"enabled_tools": {"file_search": True}},
        "execution": {"confirm_destructive": True, "max_parallel": 2},
        "chat": {"inject_schemas": True},
        "orchestrator": {"policies": {"file_delete": {"confirm": True}}},
        "notes": "smoketest"
    }
    path = save_tool_profile("smoke", sample)
    assert path.exists(), f"Profile not created at {path}"
    assert (path.with_suffix(".json.bak")).exists() is False, "No backup should exist on first write"
    print(f"   ✓ Created: {path}")

def test_2_list_and_load():
    """Test list filtering + load with soft defaults."""
    print("\n[Test 2] List + load with validation...")
    profiles = list_tool_profiles()
    assert "smoke" in profiles, f"'smoke' not in {profiles}"
    print(f"   ✓ Listed: {profiles}")

    loaded = load_tool_profile("smoke")
    # Check soft defaults were injected
    assert "tools" in loaded, "Missing 'tools' section"
    assert "execution" in loaded, "Missing 'execution' section"
    assert "chat" in loaded, "Missing 'chat' section"
    assert "orchestrator" in loaded, "Missing 'orchestrator' section"
    assert loaded["tools"]["enabled_tools"]["file_search"] is True, "Tool flag mismatch"
    print("   ✓ Loaded with defaults")

def test_3_auto_migration():
    """Test idempotent migration (should return existing if marker present)."""
    print("\n[Test 3] Auto-migration + idempotency...")
    prof = get_unified_tool_profile("Default", migrate=True)
    assert "tools" in prof, "Missing 'tools' after migration"
    assert "execution" in prof, "Missing 'execution' after migration"
    assert "chat" in prof, "Missing 'chat' after migration"
    assert "orchestrator" in prof, "Missing 'orchestrator' after migration"
    print(f"   ✓ Unified keys: {list(prof.keys())}")

    # Second call should not re-migrate (idempotency check)
    prof2 = get_unified_tool_profile("Default", migrate=True)
    if "_migration_marker" in prof:
        assert prof2.get("_migration_marker") == prof.get("_migration_marker"), "Migration marker changed (not idempotent)"
        print("   ✓ Idempotent: migration marker stable")
    else:
        print("   ⚠ No migration marker found (legacy files may not exist)")

def test_4_atomic_backup():
    """Test atomic write creates backup on update."""
    print("\n[Test 4] Atomic write + backup on update...")
    prof = load_tool_profile("smoke")
    prof["notes"] = "updated via smoketest"
    path = save_tool_profile("smoke", prof)
    bak = path.with_suffix(".json.bak")
    assert bak.exists(), f"Backup not created at {bak}"
    print(f"   ✓ Backup created: {bak}")

def test_5_corrupt_json_handling():
    """Test that corrupted JSON raises clear error."""
    print("\n[Test 5] Corrupt JSON handling...")
    corrupt_path = TOOL_PROFILES_DIR / "corrupt.json"
    with open(corrupt_path, "w") as f:
        f.write("{invalid json")

    try:
        load_tool_profile("corrupt")
        assert False, "Should have raised ValueError for corrupt JSON"
    except ValueError as e:
        assert "Invalid JSON" in str(e), f"Wrong error message: {e}"
        print(f"   ✓ Caught corrupt JSON: {e}")
    finally:
        corrupt_path.unlink()

def cleanup():
    """Remove test profiles."""
    print("\n[Cleanup] Removing test profiles...")
    for name in ["smoke", "corrupt"]:
        for suffix in [".json", ".json.bak", ".json.tmp"]:
            p = TOOL_PROFILES_DIR / f"{name}{suffix}"
            if p.exists():
                p.unlink()
                print(f"   ✗ Deleted: {p}")

if __name__ == "__main__":
    print("=" * 60)
    print("Tool Profile Smoketest (Hardening Verification)")
    print("=" * 60)

    try:
        test_1_create_and_save()
        test_2_list_and_load()
        test_3_auto_migration()
        test_4_atomic_backup()
        test_5_corrupt_json_handling()
        print("\n" + "=" * 60)
        print("✅ All tests passed!")
        print("=" * 60)
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        cleanup()
