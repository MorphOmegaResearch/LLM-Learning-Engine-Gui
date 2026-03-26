#!/usr/bin/env python3
"""
Target Context & Action Routing System
--------------------------------------
Intelligent action routing based on target type, file patterns, and profiled capabilities.
Integrates with onboard_prober for script classification.

Location: Warrior_Flow_v09x_Monkey_Buisness_v2/Modules/action_panel/grep_flight_v0_2b/
Integration Points:
  - GrepSurgicalEngine (grep_flight_v2.py:249) - Enhanced with target context
  - IPC Handler (grep_flight_v2.py:576) - Passes target_type to engine
  - Action Execution (grep_flight_v2.py:2612) - Routes via context validation
"""

import os
import json
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime


# ============================================================================
# Target Context Data Structures
# ============================================================================

@dataclass
class TargetContext:
    """Complete context about a target path"""
    path: Path
    type: str  # "file" | "folder"
    exists: bool

    # File-specific
    is_python: bool = False
    is_script: bool = False
    is_executable: bool = False
    extension: str = ""
    size_bytes: int = 0

    # Folder-specific
    is_project: bool = False
    is_git_repo: bool = False
    has_venv: bool = False

    # Metadata from target.sh
    permissions: str = ""
    modified_time: str = ""

    # Derived capabilities
    available_actions: List[str] = field(default_factory=list)
    default_action: Optional[str] = None
    recommended_actions: List[str] = field(default_factory=list)

    # Profiling data (from onboard_prober)
    profile_data: Optional[Dict] = None

    def __str__(self):
        return f"TargetContext(type={self.type}, path={self.path.name}, actions={len(self.available_actions)})"


@dataclass
class ActionMetadata:
    """Metadata for an action/script"""
    name: str
    category: str  # "quality_check" | "execution" | "analysis" | "transformation"
    target_types: List[str]  # ["file", "folder", "project"]
    file_patterns: List[str] = field(default_factory=list)  # ["*.py", "*.js"]
    scope: str = "single_file"  # "single_file" | "directory" | "project"

    # Execution properties
    auto_executable: bool = False  # Can run without user confirmation
    requires_gui: bool = False
    has_side_effects: bool = False  # Modifies files
    read_only: bool = True

    # Profiling hints (from onboard_prober)
    expects_args: bool = False
    output_format: str = "text"  # "text" | "json" | "xml"
    estimated_duration: str = "fast"  # "fast" | "medium" | "slow"

    # Source
    source_path: Optional[str] = None
    command_template: Optional[str] = None
    args_template: Optional[str] = None

    # Safety classification
    safety_level: str = "unknown"  # "safe" | "needs_review" | "dangerous"

    def is_compatible_with(self, context: TargetContext) -> bool:
        """Check if this action is compatible with given target context"""
        # Check target type
        if context.type not in self.target_types:
            return False

        # Check file patterns if specified
        if self.file_patterns and context.type == "file":
            import fnmatch
            if not any(fnmatch.fnmatch(context.path.name, pattern) for pattern in self.file_patterns):
                return False

        # Check scope requirements
        if self.scope == "project" and not context.is_project:
            return False

        return True


# ============================================================================
# Target Context Resolver
# ============================================================================

class TargetContextResolver:
    """Resolves target context and available actions"""

    def __init__(self, prober_cache_path: Optional[Path] = None):
        self.prober_cache_path = prober_cache_path
        self.prober_cache: Dict = {}
        if prober_cache_path and prober_cache_path.exists():
            self._load_prober_cache()

    def _load_prober_cache(self):
        """Load onboard_prober cache"""
        if not self.prober_cache_path:
            return
        try:
            with open(self.prober_cache_path, 'r') as f:
                self.prober_cache = json.load(f)
        except Exception as e:
            print(f"Warning: Could not load prober cache: {e}")
            self.prober_cache = {}

    def resolve(self, target_path: str, target_type: str, metadata: str = "") -> TargetContext:
        """
        Resolve complete context for a target

        Args:
            target_path: Absolute path to target
            target_type: "file" or "folder" from target.sh
            metadata: Metadata string from target.sh (size=X,perms=Y,modified=Z)

        Returns:
            TargetContext with all available information
        """
        path = Path(target_path)

        # Create base context
        context = TargetContext(
            path=path,
            type=target_type,
            exists=path.exists()
        )

        # Parse metadata from target.sh
        if metadata:
            context.permissions, context.modified_time = self._parse_metadata(metadata)

        # Resolve file-specific properties
        if context.type == "file" and context.exists:
            self._resolve_file_context(context)

        # Resolve folder-specific properties
        elif context.type == "folder" and context.exists:
            self._resolve_folder_context(context)

        # Load profile data from onboard_prober if available
        if context.is_python and str(path) in self.prober_cache.get("scanned_files", {}):
            cache_entry = self.prober_cache["scanned_files"][str(path)]
            context.profile_data = cache_entry.get("manifest")

        return context

    def _parse_metadata(self, metadata: str) -> tuple:
        """Parse metadata string from target.sh"""
        # Format: "size=24963,perms=664,modified=2026-01-13 14:13:35.963894212 +1100"
        perms = ""
        modified = ""
        try:
            parts = metadata.split(',')
            for part in parts:
                if '=' in part:
                    key, value = part.split('=', 1)
                    if key == "perms":
                        perms = value
                    elif key == "modified":
                        modified = value
        except:
            pass
        return perms, modified

    def _resolve_file_context(self, context: TargetContext):
        """Resolve file-specific context"""
        path = context.path

        # Extension and type detection
        context.extension = path.suffix
        context.is_python = context.extension == '.py'
        context.is_executable = os.access(path, os.X_OK)

        # Check if it's a script (has shebang or executable)
        if context.is_executable or context.is_python:
            try:
                with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                    first_line = f.readline()
                    context.is_script = first_line.startswith('#!')
            except:
                pass

        # File size
        try:
            context.size_bytes = path.stat().st_size
        except:
            pass

    def _resolve_folder_context(self, context: TargetContext):
        """Resolve folder-specific context"""
        path = context.path

        # Check for project indicators
        context.is_project = any([
            (path / "setup.py").exists(),
            (path / "pyproject.toml").exists(),
            (path / "requirements.txt").exists(),
            (path / "Pipfile").exists()
        ])

        # Check for git repo
        context.is_git_repo = (path / ".git").exists()

        # Check for virtual environment
        context.has_venv = any([
            (path / "venv").exists(),
            (path / ".venv").exists(),
            (path / "env").exists()
        ])


# ============================================================================
# Action Registry
# ============================================================================

class ActionRegistry:
    """Registry of available actions with metadata"""

    def __init__(self):
        self.actions: Dict[str, ActionMetadata] = {}
        self._register_builtin_actions()

    def _register_builtin_actions(self):
        """Register built-in actions"""

        # Python file actions
        self.register(ActionMetadata(
            name="Syntax Check",
            category="quality_check",
            target_types=["file"],
            file_patterns=["*.py"],
            scope="single_file",
            auto_executable=True,
            read_only=True,
            has_side_effects=False,
            output_format="text",
            estimated_duration="fast",
            safety_level="safe",
            command_template="python3 -m py_compile {target}"
        ))

        self.register(ActionMetadata(
            name="Lint (Ruff)",
            category="quality_check",
            target_types=["file"],
            file_patterns=["*.py"],
            scope="single_file",
            auto_executable=False,
            read_only=True,
            output_format="text",
            estimated_duration="fast",
            safety_level="safe",
            command_template="ruff check {target}"
        ))

        self.register(ActionMetadata(
            name="Format (Black)",
            category="transformation",
            target_types=["file"],
            file_patterns=["*.py"],
            scope="single_file",
            auto_executable=False,
            read_only=False,
            has_side_effects=True,
            output_format="text",
            estimated_duration="fast",
            safety_level="needs_review",
            command_template="black {target}"
        ))

        self.register(ActionMetadata(
            name="Run Script",
            category="execution",
            target_types=["file"],
            file_patterns=["*.py", "*.sh"],
            scope="single_file",
            auto_executable=False,
            read_only=True,
            requires_gui=False,
            output_format="text",
            estimated_duration="medium",
            safety_level="needs_review",
            command_template="python3 {target}"
        ))

        # Directory actions
        self.register(ActionMetadata(
            name="Find Python Files",
            category="analysis",
            target_types=["folder"],
            scope="directory",
            auto_executable=True,
            read_only=True,
            output_format="text",
            estimated_duration="fast",
            safety_level="safe",
            command_template="find {target} -name '*.py' -type f"
        ))

        self.register(ActionMetadata(
            name="Project Test Suite",
            category="quality_check",
            target_types=["folder"],
            scope="project",
            auto_executable=False,
            read_only=True,
            output_format="text",
            estimated_duration="slow",
            safety_level="safe",
            command_template="pytest {target}"
        ))

    def register(self, action: ActionMetadata):
        """Register an action"""
        self.actions[action.name] = action

    def register_from_profile(self, profile: Dict, source_path: str):
        """Register action from onboard_prober profile"""
        cli_schema = profile.get("cli_schema", {})
        plumbing = profile.get("plumbing", {})

        # Extract action metadata from profile
        name = Path(source_path).stem

        # Classify safety level
        safety = self._classify_safety(cli_schema, plumbing)

        # Detect capabilities
        has_gui = "tkinter" in str(profile.get("dependencies", []))
        expects_args = len(cli_schema.get("flags", [])) > 0

        # Create action metadata
        action = ActionMetadata(
            name=name,
            category="custom_script",
            target_types=["file"],  # Default, could be smarter
            file_patterns=["*"],
            scope="single_file",
            auto_executable=safety == "safe",
            requires_gui=has_gui,
            read_only=safety == "safe",
            has_side_effects=safety != "safe",
            expects_args=expects_args,
            source_path=source_path,
            safety_level=safety
        )

        self.register(action)

    def _classify_safety(self, cli_schema: Dict, plumbing: Dict) -> str:
        """Classify script safety level"""
        description = cli_schema.get("description", "").lower()

        # Check for destructive keywords
        destructive_keywords = ["delete", "remove", "modify", "write", "overwrite", "replace"]
        if any(kw in description for kw in destructive_keywords):
            return "dangerous"

        # Check for read-only keywords
        safe_keywords = ["check", "lint", "analyze", "scan", "view", "read", "list"]
        if any(kw in description for kw in safe_keywords):
            return "safe"

        return "needs_review"

    def get_compatible_actions(self, context: TargetContext) -> List[ActionMetadata]:
        """Get all actions compatible with given context"""
        compatible = []
        for action in self.actions.values():
            if action.is_compatible_with(context):
                compatible.append(action)
        return compatible

    def get_default_action(self, context: TargetContext) -> Optional[ActionMetadata]:
        """Get default action for context"""
        compatible = self.get_compatible_actions(context)

        # Prioritize safe, auto-executable actions
        auto_safe = [a for a in compatible if a.auto_executable and a.safety_level == "safe"]
        if auto_safe:
            return auto_safe[0]

        # Fall back to first compatible
        return compatible[0] if compatible else None


# ============================================================================
# Smart Action Router
# ============================================================================

class ActionRouter:
    """Routes action execution with context validation"""

    def __init__(self, resolver: TargetContextResolver, registry: ActionRegistry):
        self.resolver = resolver
        self.registry = registry

    def route(self, action_name: str, target_path: str, target_type: str,
              metadata: str = "", auto: bool = False) -> Dict:
        """
        Route action execution with validation

        Returns:
            Dict with keys: success, message, action, context, command
        """
        # Resolve target context
        context = self.resolver.resolve(target_path, target_type, metadata)

        # Get action metadata
        action = self.registry.actions.get(action_name)
        if not action:
            return {
                "success": False,
                "message": f"Action '{action_name}' not found",
                "context": context
            }

        # Validate compatibility
        if not action.is_compatible_with(context):
            compatible = self.registry.get_compatible_actions(context)
            return {
                "success": False,
                "message": f"Action '{action_name}' not compatible with {context.type} target",
                "context": context,
                "suggestion": f"Compatible actions: {[a.name for a in compatible]}"
            }

        # Check auto-execution permission
        if auto and not action.auto_executable:
            return {
                "success": False,
                "message": f"Action '{action_name}' requires user confirmation",
                "context": context,
                "requires_confirmation": True
            }

        # Build command
        command = self._build_command(action, context)

        return {
            "success": True,
            "message": f"Ready to execute: {action_name}",
            "action": action,
            "context": context,
            "command": command
        }

    def _build_command(self, action: ActionMetadata, context: TargetContext) -> str:
        """Build execution command"""
        if not action.command_template:
            return ""

        cmd = action.command_template
        cmd = cmd.replace("{target}", str(context.path))

        # Add args if template exists
        if action.args_template:
            args = action.args_template.replace("{target}", str(context.path))
            cmd += f" {args}"

        return cmd

    def suggest_actions(self, target_path: str, target_type: str, metadata: str = "") -> List[str]:
        """Suggest actions for target"""
        context = self.resolver.resolve(target_path, target_type, metadata)
        compatible = self.registry.get_compatible_actions(context)

        # Sort by safety and auto-executable
        compatible.sort(key=lambda a: (
            a.safety_level != "safe",  # Safe first
            not a.auto_executable,      # Auto-executable first
            a.name                      # Alphabetical
        ))

        return [a.name for a in compatible]


# ============================================================================
# Integration Helpers
# ============================================================================

def create_integrated_system(warrior_flow_root: Path) -> tuple:
    """
    Create integrated target context system

    Returns:
        (resolver, registry, router) tuple
    """
    prober_cache = warrior_flow_root / ".docv2_workspace" / "prober_cache.json"

    resolver = TargetContextResolver(prober_cache if prober_cache.exists() else None)
    registry = ActionRegistry()
    router = ActionRouter(resolver, registry)

    return resolver, registry, router


# ============================================================================
# CLI Testing Interface
# ============================================================================

if __name__ == "__main__":
    import sys

    if len(sys.argv) < 3:
        print("Usage: python target_context_system.py <target_path> <target_type>")
        print("Example: python target_context_system.py /path/to/file.py file")
        sys.exit(1)

    target_path = sys.argv[1]
    target_type = sys.argv[2]

    # Create system
    warrior_flow_root = Path("/home/commander/3_Inventory/Warrior_Flow")
    resolver, registry, router = create_integrated_system(warrior_flow_root)

    # Resolve context
    context = resolver.resolve(target_path, target_type)

    print("=" * 60)
    print(f"TARGET CONTEXT: {context}")
    print("=" * 60)
    print(f"Path: {context.path}")
    print(f"Type: {context.type}")
    print(f"Exists: {context.exists}")
    print(f"Python: {context.is_python}")
    print(f"Script: {context.is_script}")
    print(f"Executable: {context.is_executable}")
    print(f"Extension: {context.extension}")
    print()

    # Get compatible actions
    compatible = registry.get_compatible_actions(context)
    print(f"COMPATIBLE ACTIONS: {len(compatible)}")
    print("=" * 60)
    for action in compatible:
        print(f"  • {action.name} ({action.category})")
        print(f"    Safety: {action.safety_level}, Auto: {action.auto_executable}")
        print()

    # Get default
    default = registry.get_default_action(context)
    if default:
        print(f"DEFAULT ACTION: {default.name}")
        print("=" * 60)

        # Route it
        result = router.route(default.name, target_path, target_type, auto=True)
        print(f"Route Result: {result['success']}")
        print(f"Message: {result['message']}")
        if result['success']:
            print(f"Command: {result['command']}")
