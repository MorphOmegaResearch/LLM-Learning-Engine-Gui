#!/usr/bin/env python3
"""
Script Discovery Handler
=========================
Discovers and categorizes all Python scripts in the project.
Provides unified help system for orchestrator.py --scripts.

Categories:
- Core Systems: orchestrator, gap_analyzer, audit
- Integration Tools: activity_integration_bridge, onboarder
- Workflow Management: workflow_manager
- Analysis Tools: analyzer, import_organizer, pathfixer
- Utilities: Various utility scripts
"""

import os
import sys
import subprocess
import re
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, field

# Graceful import for classifier
try:
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'activities', 'tools', 'scripts'))
    from activity_integration_bridge import FiveWOneHClassifier
    HAS_CLASSIFIER = True
except ImportError:
    HAS_CLASSIFIER = False


@dataclass
class ScriptInfo:
    """Information about a discovered script"""
    name: str
    path: Path
    category: str
    description: str = ""
    help_output: str = ""
    has_argparse: bool = False
    classification: Dict[str, str] = field(default_factory=dict)
    is_init_script: bool = False  # Runs at initialization
    is_runtime_script: bool = False  # Runs during runtime


class ScriptDiscoveryHandler:
    """
    Discovers and categorizes Python scripts in the project.
    Provides unified interface for listing and describing scripts.
    """

    # Script categorization rules
    CATEGORIES = {
        'core_systems': {
            'name': 'Core Systems',
            'description': 'Primary linguistic processing and orchestration',
            'patterns': ['orchestrator', 'gap_analyzer', 'audit', 'interaction_resolver', 'realization_engine']
        },
        'integration': {
            'name': 'Integration & Bridge Systems',
            'description': 'Activity suggestions, capability management, tool classification',
            'patterns': ['activity_integration', 'onboarder', 'capability']
        },
        'workflow': {
            'name': 'Workflow Management',
            'description': 'Workflow execution, task management, agent coordination',
            'patterns': ['workflow_manager', 'workflow']
        },
        'analysis': {
            'name': 'Analysis Tools',
            'description': 'Code analysis, import organization, path fixing',
            'patterns': ['analyzer', 'import_organizer', 'pathfixer', 'import_organizer_seed']
        },
        'utilities': {
            'name': 'Utilities & Support',
            'description': 'Supporting scripts and utilities',
            'patterns': []  # Catch-all for anything not matching above
        }
    }

    def __init__(self, project_root: Path = None):
        """Initialize handler with project root"""
        if project_root is None:
            project_root = Path(__file__).parent

        self.project_root = project_root
        self.scripts: List[ScriptInfo] = []
        self.classifier = None

        if HAS_CLASSIFIER:
            try:
                self.classifier = FiveWOneHClassifier()
            except:
                pass

    def discover_scripts(self) -> List[ScriptInfo]:
        """
        Discover all Python scripts in the project.
        Returns list of ScriptInfo objects.
        """
        scripts = []

        # Search patterns
        search_paths = [
            self.project_root,  # Main directory
            self.project_root / 'activities' / 'tools' / 'scripts',  # Tools
        ]

        for search_path in search_paths:
            if not search_path.exists():
                continue

            # Find all .py files
            for py_file in search_path.rglob('*.py'):
                # Skip __pycache__, backups, test files, copies
                skip_patterns = [
                    '__pycache__', 'backup_MARK', '_backup_', 'test_', '.pyc',
                    '(copy', '.backup', '_seed.py'  # Also skip copies and seed files
                ]
                if any(skip in str(py_file) for skip in skip_patterns):
                    continue

                # Skip __init__.py
                if py_file.name == '__init__.py':
                    continue

                script_info = self._analyze_script(py_file)
                if script_info:
                    scripts.append(script_info)

        # Deduplicate by name - prefer scripts in main directory over subdirectories
        seen_names = {}
        unique_scripts = []
        for script in scripts:
            if script.name not in seen_names:
                seen_names[script.name] = script
                unique_scripts.append(script)
            else:
                # If this one is in main dir and existing is not, replace
                existing = seen_names[script.name]
                if script.path.parent == self.project_root and existing.path.parent != self.project_root:
                    # Remove existing and add this one
                    unique_scripts = [s for s in unique_scripts if s.name != script.name]
                    unique_scripts.append(script)
                    seen_names[script.name] = script

        self.scripts = sorted(unique_scripts, key=lambda s: (s.category, s.name))
        return self.scripts

    def _analyze_script(self, py_file: Path) -> Optional[ScriptInfo]:
        """Analyze a single Python script"""
        try:
            # Read file content
            content = py_file.read_text(encoding='utf-8', errors='ignore')

            # Determine category
            category = self._categorize_script(py_file.name, content)

            # Extract description from docstring
            description = self._extract_description(content)

            # Check if has argparse
            has_argparse = 'import argparse' in content or 'from argparse' in content

            # Get help output if has argparse
            help_output = ""
            if has_argparse:
                help_output = self._get_help_output(py_file)

            # Classify using 5W1H if available
            classification = {}
            if self.classifier:
                try:
                    classification = self.classifier.classify(py_file.name, content)
                except:
                    classification = {}

            # Determine if init or runtime script
            is_init_script = 'setup' in py_file.name.lower() or 'init' in py_file.name.lower()
            is_runtime_script = not is_init_script and has_argparse

            return ScriptInfo(
                name=py_file.stem,
                path=py_file,
                category=category,
                description=description,
                help_output=help_output,
                has_argparse=has_argparse,
                classification=classification,
                is_init_script=is_init_script,
                is_runtime_script=is_runtime_script
            )

        except Exception as e:
            print(f"Warning: Could not analyze {py_file}: {e}")
            return None

    def _categorize_script(self, filename: str, content: str) -> str:
        """Categorize script based on filename and content"""
        filename_lower = filename.lower()

        # Check each category's patterns
        for category_id, category_info in self.CATEGORIES.items():
            for pattern in category_info['patterns']:
                if pattern in filename_lower:
                    return category_id

        # Default to utilities
        return 'utilities'

    def _extract_description(self, content: str) -> str:
        """Extract description from docstring"""
        # Try to find module docstring
        docstring_match = re.search(r'"""(.+?)"""', content, re.DOTALL)
        if docstring_match:
            docstring = docstring_match.group(1).strip()
            # Get first non-empty line that's not just symbols
            lines = [l.strip() for l in docstring.split('\n') if l.strip() and not l.strip().startswith('=')]
            if lines:
                return lines[0][:100]  # First 100 chars

        return "No description available"

    def _get_help_output(self, py_file: Path) -> str:
        """Get -h output from script"""
        try:
            result = subprocess.run(
                ['python3', str(py_file), '-h'],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                return result.stdout
            else:
                # Try --help
                result = subprocess.run(
                    ['python3', str(py_file), '--help'],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                return result.stdout if result.returncode == 0 else ""
        except:
            return ""

    def get_scripts_by_category(self) -> Dict[str, List[ScriptInfo]]:
        """Get scripts organized by category"""
        categorized = {cat_id: [] for cat_id in self.CATEGORIES.keys()}

        for script in self.scripts:
            categorized[script.category].append(script)

        return categorized

    def format_help_output(self, verbose: bool = False) -> str:
        """
        Format scripts into organized help output.

        Args:
            verbose: If True, include full -h output for each script
        """
        if not self.scripts:
            self.discover_scripts()

        output = []
        output.append("=" * 70)
        output.append("AVAILABLE SCRIPTS - Unified Guidance System")
        output.append("=" * 70)
        output.append("")

        categorized = self.get_scripts_by_category()

        # Show init scripts first
        init_scripts = [s for s in self.scripts if s.is_init_script]
        if init_scripts:
            output.append("INITIALIZATION SCRIPTS")
            output.append("-" * 70)
            for script in init_scripts:
                output.append(f"  {script.name}.py")
                output.append(f"    {script.description}")
                output.append("")

        # Show runtime scripts by category
        output.append("RUNTIME SCRIPTS (by category)")
        output.append("-" * 70)
        output.append("")

        for category_id, category_info in self.CATEGORIES.items():
            scripts_in_cat = [s for s in categorized[category_id] if s.is_runtime_script]

            if not scripts_in_cat:
                continue

            output.append(f"[{category_info['name']}]")
            output.append(f"  {category_info['description']}")
            output.append("")

            for script in scripts_in_cat:
                output.append(f"  • {script.name}.py")

                # Show description
                desc = script.description if script.description != "No description available" else "unknown"
                output.append(f"      {desc}")

                # Show classification if available
                if script.classification and script.classification.get('confidence', 0) > 0:
                    what = script.classification.get('what', 'unknown')
                    how = script.classification.get('how', 'unknown')
                    output.append(f"      What: {what}")
                    output.append(f"      How: {how}")
                    output.append(f"      Confidence: {script.classification.get('confidence', 0):.0%}")

                # Show if has argparse
                if script.has_argparse:
                    output.append(f"      Usage: python3 {script.name}.py -h")

                    # Show brief help if verbose
                    if verbose and script.help_output:
                        # Extract just the description line from help
                        help_lines = script.help_output.split('\n')
                        for line in help_lines:
                            if line.strip() and not line.startswith('usage:'):
                                output.append(f"        {line.strip()}")
                                break

                output.append("")

        # Show other utilities
        other_scripts = [s for s in categorized['utilities'] if s.is_runtime_script]
        if other_scripts:
            output.append("[Other Utilities]")
            output.append("")
            for script in other_scripts:
                output.append(f"  • {script.name}.py")
                if script.has_argparse:
                    output.append(f"      Usage: python3 {script.name}.py -h")
                output.append("")

        output.append("=" * 70)
        output.append("GUIDANCE")
        output.append("-" * 70)
        output.append("  orchestrator.py      - Main entry point for text processing")
        output.append("  gap_analyzer.py      - Analyze understanding gaps")
        output.append("  audit.py             - Audit regex patterns and coverage")
        output.append("  workflow_manager.py  - Execute workflows with agents")
        output.append("")
        output.append("For detailed help on any script:")
        output.append("  python3 <script_name>.py -h")
        output.append("=" * 70)

        return "\n".join(output)

    def get_script_classification(self, script_name: str) -> str:
        """Get quick classification description for a script"""
        for script in self.scripts:
            if script.name == script_name:
                if script.classification and script.classification.get('confidence', 0) > 0:
                    return script.classification.get('what', 'unknown')
                return script.description if script.description != "No description available" else "unknown"
        return "unknown"


# Module-level functions for easy import
def discover_all_scripts(project_root: Path = None) -> List[ScriptInfo]:
    """Discover all scripts in project"""
    handler = ScriptDiscoveryHandler(project_root)
    return handler.discover_scripts()


def get_unified_help(verbose: bool = False, project_root: Path = None) -> str:
    """Get unified help output for all scripts"""
    handler = ScriptDiscoveryHandler(project_root)
    handler.discover_scripts()
    return handler.format_help_output(verbose)


if __name__ == "__main__":
    # Test the handler
    import argparse

    parser = argparse.ArgumentParser(description="Script Discovery Handler - Test Mode")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show verbose help")

    args = parser.parse_args()

    print(get_unified_help(verbose=args.verbose))
