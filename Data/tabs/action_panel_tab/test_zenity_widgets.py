#!/usr/bin/env python3
"""
Test script for new Zenity widget functions (Sweep 1)
Verifies: zenity_forms, zenity_checklist, zenity_progress, zenity_notification,
          zenity_question, zenity_radiolist, display_output_with_actions

Usage: python3 test_zenity_widgets.py [test_name]
  test_name: all|forms|checklist|progress|notification|question|radiolist|actions
"""

import sys
import time
sys.path.insert(0, '.')

from Os_Toolkit import (
    zenity_forms,
    zenity_checklist,
    zenity_progress,
    zenity_notification,
    zenity_question,
    zenity_radiolist,
    display_output_with_actions
)


def test_notification():
    """Test desktop notification."""
    print("[TEST] Zenity Notification")
    zenity_notification("Test notification from Babel", urgency="normal")
    print("[PASS] Notification sent")
    time.sleep(1)


def test_question():
    """Test yes/no question dialog."""
    print("[TEST] Zenity Question")
    result = zenity_question(
        "Do you want to continue with the tests?",
        title="Zenity Test Suite",
        ok_label="Yes, continue",
        cancel_label="No, stop"
    )
    print(f"[RESULT] User selected: {'Yes' if result else 'No'}")
    return result


def test_forms():
    """Test forms dialog for input."""
    print("[TEST] Zenity Forms")
    result = zenity_forms([
        {'name': 'task_id', 'label': 'Task ID', 'default': 'P1-TEST'},
        {'name': 'title', 'label': 'Task Title', 'default': 'Test Task'},
        {'name': 'priority', 'label': 'Priority', 'default': 'P2'}
    ], title="Add Test Todo")

    if result:
        print(f"[RESULT] Form data: {result}")
    else:
        print("[RESULT] User cancelled")
    return result


def test_checklist():
    """Test multi-select checklist."""
    print("[TEST] Zenity Checklist")
    result = zenity_checklist([
        {'id': 'test-1', 'label': 'Run unit tests', 'checked': True},
        {'id': 'test-2', 'label': 'Check security', 'checked': False},
        {'id': 'test-3', 'label': 'Sync todos', 'checked': True}
    ], title="Select Actions", text="Which tests should we run?")

    if result:
        print(f"[RESULT] Selected: {result}")
    else:
        print("[RESULT] No items selected")
    return result


def test_radiolist():
    """Test single-select radiolist."""
    print("[TEST] Zenity Radiolist")
    result = zenity_radiolist([
        {'id': 'action1', 'label': 'Display file analysis', 'selected': True},
        {'id': 'action2', 'label': 'Run grep for imports', 'selected': False},
        {'id': 'action3', 'label': 'Check related todos', 'selected': False}
    ], title="Suggested Actions", text="What would you like to do?")

    if result:
        print(f"[RESULT] Selected action: {result}")
    else:
        print("[RESULT] User cancelled")
    return result


def test_progress():
    """Test progress bar."""
    print("[TEST] Zenity Progress Bar")
    progress = zenity_progress(
        title="Processing Test",
        text="Simulating file scan...",
        pulsate=False
    )

    if progress:
        for i in range(0, 101, 10):
            progress.stdin.write(f"{i}\n")
            progress.stdin.flush()
            time.sleep(0.3)
        progress.stdin.close()
        progress.wait()
        print("[PASS] Progress completed")
    else:
        print("[FAIL] Progress bar failed to start")


def test_display_with_actions():
    """Test enhanced display with action selection."""
    print("[TEST] display_output_with_actions")

    sample_output = """
=== Query Results ===
File: Os_Toolkit.py
Size: 122KB
Lines: 4400
Category: System Profiler
Trust Level: Native

Recent Changes:
- Added TrustRegistry class (line 736)
- Added UnifiedTodoSync class (line 948)
- Enhanced display_output with Zenity widgets (line 3820)
"""

    actions = [
        {
            'id': 'show_imports',
            'label': 'Show all imports in this file',
            'command': 'grep "^import\\|^from" Os_Toolkit.py',
            'selected': True
        },
        {
            'id': 'check_todos',
            'label': 'Find related todos',
            'command': 'python3 Os_Toolkit.py todo view',
            'selected': False
        },
        {
            'id': 'run_tests',
            'label': 'Run validation tests',
            'command': 'bash P0_VALIDATION_TESTS.sh',
            'selected': False
        }
    ]

    selected = display_output_with_actions(
        sample_output,
        actions,
        title="Test: Query Results",
        use_zenity=True
    )

    if selected:
        print(f"[RESULT] User selected action: {selected}")
        action = next(a for a in actions if a['id'] == selected)
        print(f"[INFO] Would execute: {action['command']}")
    else:
        print("[RESULT] No action selected")


def run_all_tests():
    """Run all widget tests in sequence."""
    print("=" * 60)
    print("Zenity Widget Test Suite - Sweep 1 Validation")
    print("=" * 60)
    print()

    # Start with notification (non-blocking)
    test_notification()
    time.sleep(1)

    # Question (exit early if user says no)
    if not test_question():
        print("\n[INFO] User stopped tests")
        return

    print()
    time.sleep(1)

    # Forms
    test_forms()
    time.sleep(1)
    print()

    # Checklist
    test_checklist()
    time.sleep(1)
    print()

    # Radiolist
    test_radiolist()
    time.sleep(1)
    print()

    # Progress bar
    test_progress()
    time.sleep(1)
    print()

    # Enhanced display with actions
    test_display_with_actions()

    print()
    print("=" * 60)
    print("Test Suite Complete!")
    print("=" * 60)


if __name__ == '__main__':
    if len(sys.argv) > 1:
        test_name = sys.argv[1].lower()
        tests = {
            'notification': test_notification,
            'question': test_question,
            'forms': test_forms,
            'checklist': test_checklist,
            'radiolist': test_radiolist,
            'progress': test_progress,
            'actions': test_display_with_actions,
            'all': run_all_tests
        }

        if test_name in tests:
            tests[test_name]()
        else:
            print(f"Unknown test: {test_name}")
            print(f"Available: {', '.join(tests.keys())}")
    else:
        run_all_tests()
