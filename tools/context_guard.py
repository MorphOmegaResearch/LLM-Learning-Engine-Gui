#!/usr/bin/env python3
"""
Context Guard Tagger
--------------------
Scans the repository and:
  1. Tags legacy files with `[SYSTEM: LEGACY_TUI | STATUS: ARCHIVE]`
  2. Ensures active files declare `[SYSTEM: GUI | VERSION: 1.9f | STATUS: ACTIVE]`
  3. Logs results to context_guard_report.txt

Usage:
    python tools/context_guard.py [--dry-run] [--report-only]

Options:
    --dry-run       Show what would be tagged without modifying files
    --report-only   Generate report of current tags without changes
"""
import os
import sys
from pathlib import Path
from typing import List, Tuple

ROOT = Path(__file__).resolve().parents[1]

# Legacy paths (archived, do not modify)
LEGACY_PATHS = [
    "Data/tabs/custom_code_tab/Artifacts",
    "Data/tabs/custom_code_tab/experiments/v1.2old_sometoollogic",
]

# Active paths (current system)
ACTIVE_PATHS = [
    "Data/interactive_trainer_gui.py",
    "Data/training_engine.py",
    "Data/evaluation_engine.py",
    "Data/config.py",
    "Data/tool_trainer.py",
    "Data/training_data_generator.py",
    "Data/tabs/models_tab/",
    "Data/tabs/training_tab/",
    "Data/tabs/custom_code_tab/sub_tabs/",
    "Data/tabs/custom_code_tab/lineage_tracker.py",
    "Data/tabs/custom_code_tab/tool_call_logger.py",
    "Data/tabs/custom_code_tab/tool_executor.py",
    "Data/tabs/custom_code_tab/chat_history_manager.py",
]

# Tags to use
LEGACY_TAG = "# [SYSTEM: LEGACY_TUI | STATUS: ARCHIVE | DO NOT EXECUTE]"
ACTIVE_TAG = "# [SYSTEM: GUI | VERSION: 1.9f | STATUS: ACTIVE]"

def has_tag(file_path: Path, tag: str) -> bool:
    """Check if file already has the specified tag in first 3 lines"""
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            lines = [f.readline() for _ in range(3)]
            return any(tag in line for line in lines)
    except Exception:
        return False

def add_tag(file_path: Path, tag: str, dry_run: bool = False) -> bool:
    """Add header tag if missing"""
    try:
        if has_tag(file_path, tag):
            return False  # Already tagged

        text = file_path.read_text(encoding='utf-8', errors='ignore')

        # Handle shebang
        lines = text.split('\n')
        if lines and lines[0].startswith('#!'):
            # Insert tag after shebang
            updated = lines[0] + '\n' + tag + '\n' + '\n'.join(lines[1:])
        else:
            # Insert tag at top
            updated = tag + '\n' + text

        if not dry_run:
            file_path.write_text(updated, encoding='utf-8')

        return True
    except Exception as e:
        print(f"Error tagging {file_path}: {e}", file=sys.stderr)
        return False

def scan_and_tag(dry_run: bool = False, report_only: bool = False) -> Tuple[List[str], List[str]]:
    """
    Scan repository and tag files appropriately

    Returns:
        (legacy_tagged, active_tagged) - Lists of file paths that were tagged
    """
    legacy_tagged = []
    active_tagged = []

    # Tag legacy files
    for folder in LEGACY_PATHS:
        path = ROOT / folder
        if not path.exists():
            continue

        for file in path.rglob("*.py"):
            if report_only:
                if has_tag(file, LEGACY_TAG):
                    legacy_tagged.append(str(file.relative_to(ROOT)))
            else:
                if add_tag(file, LEGACY_TAG, dry_run):
                    legacy_tagged.append(str(file.relative_to(ROOT)))

    # Tag active files
    for item in ACTIVE_PATHS:
        path = ROOT / item

        if not path.exists():
            continue

        if path.is_file() and path.suffix == ".py":
            if report_only:
                if has_tag(path, ACTIVE_TAG):
                    active_tagged.append(str(path.relative_to(ROOT)))
            else:
                if add_tag(path, ACTIVE_TAG, dry_run):
                    active_tagged.append(str(path.relative_to(ROOT)))

        elif path.is_dir():
            for file in path.rglob("*.py"):
                # Skip legacy paths that might be nested
                if any(leg in str(file) for leg in LEGACY_PATHS):
                    continue

                if report_only:
                    if has_tag(file, ACTIVE_TAG):
                        active_tagged.append(str(file.relative_to(ROOT)))
                else:
                    if add_tag(file, ACTIVE_TAG, dry_run):
                        active_tagged.append(str(file.relative_to(ROOT)))

    return legacy_tagged, active_tagged

def generate_report(legacy_tagged: List[str], active_tagged: List[str],
                   dry_run: bool = False, report_only: bool = False) -> str:
    """Generate a report of tagged files"""
    mode = "REPORT ONLY" if report_only else ("DRY RUN" if dry_run else "COMPLETED")

    report = []
    report.append("=" * 70)
    report.append(f"Context Guard Tagger - {mode}")
    report.append("=" * 70)
    report.append("")

    report.append(f"Legacy Files Tagged (ARCHIVE): {len(legacy_tagged)}")
    report.append("-" * 70)
    for file in sorted(legacy_tagged):
        report.append(f"  🔒 {file}")
    report.append("")

    report.append(f"Active Files Tagged (GUI v1.9f): {len(active_tagged)}")
    report.append("-" * 70)
    for file in sorted(active_tagged):
        report.append(f"  ✅ {file}")
    report.append("")

    report.append("=" * 70)
    report.append(f"Total Files Processed: {len(legacy_tagged) + len(active_tagged)}")
    report.append("=" * 70)

    if dry_run:
        report.append("")
        report.append("NOTE: This was a dry run. No files were modified.")
        report.append("Run without --dry-run to apply tags.")
    elif report_only:
        report.append("")
        report.append("NOTE: This report shows currently tagged files only.")

    return "\n".join(report)

def main():
    """Main entry point"""
    dry_run = "--dry-run" in sys.argv
    report_only = "--report-only" in sys.argv

    if "--help" in sys.argv or "-h" in sys.argv:
        print(__doc__)
        return

    print("Context Guard Tagger")
    print("=" * 70)

    if dry_run:
        print("🔍 DRY RUN MODE - No files will be modified")
    elif report_only:
        print("📊 REPORT ONLY MODE - Showing current tags")
    else:
        print("⚡ LIVE MODE - Files will be tagged")

    print("")

    legacy_tagged, active_tagged = scan_and_tag(dry_run, report_only)

    report = generate_report(legacy_tagged, active_tagged, dry_run, report_only)

    # Write report to file
    report_file = ROOT / "context_guard_report.txt"
    report_file.write_text(report, encoding='utf-8')

    # Print report to console
    print(report)
    print("")
    print(f"📄 Report saved to: {report_file}")

if __name__ == "__main__":
    main()
