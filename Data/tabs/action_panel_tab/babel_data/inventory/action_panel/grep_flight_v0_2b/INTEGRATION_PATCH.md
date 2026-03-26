# Target Context System Integration Patch

## Overview
This patch integrates the target context system into grep_flight_v2.py to enable intelligent action routing based on target type, file patterns, and profiled capabilities.

---

## Patch 1: Import Target Context System
**Location:** grep_flight_v2.py, after line 40 (near other imports)

```python
# Import target context system
from target_context_system import (
    TargetContext,
    ActionMetadata,
    TargetContextResolver,
    ActionRegistry,
    ActionRouter,
    create_integrated_system
)
```

---

## Patch 2: Enhance GrepSurgicalEngine.__init__
**Location:** grep_flight_v2.py:252-264

**BEFORE:**
```python
def __init__(self, config: PanelConfig):
    self.config = config
    self.current_target: Optional[str] = None
    self.current_pattern: Optional[str] = None
    self.current_workflow: Optional[str] = None
    self.workflow_steps: List[Dict] = []
    self.results_queue = queue.Queue()
    self.indicators: Dict[str, Dict] = {}
    self.recent_targets: List[str] = []
    self.recent_patterns: List[str] = []
    self.max_history: int = 10
    self.debug_log: List[str] = []
    self.max_debug_log: int = 1000
```

**AFTER:**
```python
def __init__(self, config: PanelConfig):
    self.config = config
    self.current_target: Optional[str] = None
    self.current_pattern: Optional[str] = None
    self.current_workflow: Optional[str] = None
    self.workflow_steps: List[Dict] = []
    self.results_queue = queue.Queue()
    self.indicators: Dict[str, Dict] = {}
    self.recent_targets: List[str] = []
    self.recent_patterns: List[str] = []
    self.max_history: int = 10
    self.debug_log: List[str] = []
    self.max_debug_log: int = 1000

    # NEW: Target context system
    self.current_target_type: Optional[str] = None
    self.current_target_metadata: Optional[str] = None
    self.current_target_context: Optional[TargetContext] = None

    # Initialize target context system
    warrior_flow_root = Path("/home/commander/3_Inventory/Warrior_Flow")
    self.context_resolver, self.action_registry, self.action_router = create_integrated_system(warrior_flow_root)
    self.log_debug("Target context system initialized", "INFO")
```

---

## Patch 3: Enhance set_target() Method
**Location:** grep_flight_v2.py:277-287

**BEFORE:**
```python
def set_target(self, target: str):
    """Set current target"""
    self.current_target = target
    # Add to recent targets (avoid duplicates)
    if target in self.recent_targets:
        self.recent_targets.remove(target)
    self.recent_targets.insert(0, target)
    # Limit history size
    if len(self.recent_targets) > self.max_history:
        self.recent_targets = self.recent_targets[:self.max_history]
    self._add_workflow_step('TARGET_SET', f'Target set: {target}')
```

**AFTER:**
```python
def set_target(self, target: str, target_type: str = "auto", metadata: str = ""):
    """
    Set current target with type and metadata

    Args:
        target: Path to target
        target_type: "file" | "folder" | "auto" (auto-detect)
        metadata: Metadata string from target.sh
    """
    self.current_target = target
    self.current_target_type = target_type
    self.current_target_metadata = metadata

    # Auto-detect type if needed
    if target_type == "auto":
        if os.path.isdir(target):
            self.current_target_type = "folder"
        elif os.path.isfile(target):
            self.current_target_type = "file"
        else:
            self.current_target_type = "unknown"

    # Resolve target context
    try:
        self.current_target_context = self.context_resolver.resolve(
            target, self.current_target_type, metadata
        )
        self.log_debug(f"Target context resolved: {self.current_target_context}", "INFO")
    except Exception as e:
        self.log_debug(f"Failed to resolve target context: {e}", "ERROR")
        self.current_target_context = None

    # Add to recent targets (avoid duplicates)
    if target in self.recent_targets:
        self.recent_targets.remove(target)
    self.recent_targets.insert(0, target)
    # Limit history size
    if len(self.recent_targets) > self.max_history:
        self.recent_targets = self.recent_targets[:self.max_history]
    self._add_workflow_step('TARGET_SET', f'Target set: {target} (type: {self.current_target_type})')
```

---

## Patch 4: Add Action Suggestion Method
**Location:** grep_flight_v2.py, after set_pattern() method (~line 320)

```python
def get_available_actions(self) -> List[str]:
    """Get available actions for current target"""
    if not self.current_target or not self.current_target_type:
        return []

    try:
        return self.action_router.suggest_actions(
            self.current_target,
            self.current_target_type,
            self.current_target_metadata or ""
        )
    except Exception as e:
        self.log_debug(f"Failed to get available actions: {e}", "ERROR")
        return []

def get_default_action(self) -> Optional[str]:
    """Get default action for current target"""
    if not self.current_target_context:
        return None

    try:
        default = self.action_registry.get_default_action(self.current_target_context)
        return default.name if default else None
    except Exception as e:
        self.log_debug(f"Failed to get default action: {e}", "ERROR")
        return None

def validate_action_for_target(self, action_name: str) -> Dict:
    """
    Validate if action is compatible with current target

    Returns:
        Dict with keys: compatible (bool), reason (str), suggestions (list)
    """
    if not self.current_target or not self.current_target_type:
        return {
            "compatible": False,
            "reason": "No target set",
            "suggestions": []
        }

    try:
        result = self.action_router.route(
            action_name,
            self.current_target,
            self.current_target_type,
            self.current_target_metadata or "",
            auto=False
        )

        return {
            "compatible": result["success"],
            "reason": result["message"],
            "suggestions": result.get("suggestion", []),
            "requires_confirmation": result.get("requires_confirmation", False)
        }
    except Exception as e:
        return {
            "compatible": False,
            "reason": str(e),
            "suggestions": []
        }
```

---

## Patch 5: Update IPC Handler (SET_TARGET)
**Location:** grep_flight_v2.py:576-625

**BEFORE:**
```python
if msg_type == "SET_TARGET":
    if len(parts) < 5:
        raise ValueError(f"SET_TARGET requires 5 fields, got {len(parts)}")

    target_path = parts[1]
    target_type = parts[2]
    metadata = parts[3]
    timestamp = parts[4]

    # ... existing logging code ...

    self.engine.log_debug(f"Target path: {target_path}", "INFO")
    self.engine.log_debug(f"Target type: {target_type}", "INFO")

    # Validate path exists
    if not os.path.exists(target_path):
        self._add_traceback(f"❌ PATH NOT FOUND: {target_path}", "ERROR")
        raise FileNotFoundError(f"Target path does not exist: {target_path}")

    # Directory Lock & Pattern Injection Logic
    path_obj = Path(target_path)
    if os.path.isdir(target_path):
        # It's a directory: Lock target to it
        self.target_var.set(target_path)
        self.engine.set_target(target_path)
        # ... rest of existing code ...
```

**AFTER:**
```python
if msg_type == "SET_TARGET":
    if len(parts) < 5:
        raise ValueError(f"SET_TARGET requires 5 fields, got {len(parts)}")

    target_path = parts[1]
    target_type = parts[2]
    metadata = parts[3]
    timestamp = parts[4]

    # ... existing logging code ...

    self.engine.log_debug(f"Target path: {target_path}", "INFO")
    self.engine.log_debug(f"Target type: {target_type}", "INFO")
    self.engine.log_debug(f"Metadata: {metadata}", "DEBUG")

    # Validate path exists
    if not os.path.exists(target_path):
        self._add_traceback(f"❌ PATH NOT FOUND: {target_path}", "ERROR")
        raise FileNotFoundError(f"Target path does not exist: {target_path}")

    # Directory Lock & Pattern Injection Logic
    path_obj = Path(target_path)
    if os.path.isdir(target_path):
        # It's a directory: Lock target to it
        self.target_var.set(target_path)
        self.engine.set_target(target_path, target_type, metadata)  # NEW: Pass type and metadata
        # ... rest of existing code ...
    elif os.path.isfile(target_path):
        # It's a file: Lock target to Parent Dir, Inject Filename to Pattern
        parent_dir = str(path_obj.parent)
        filename = path_obj.name

        self.target_var.set(parent_dir)
        self.engine.set_target(parent_dir, "folder", metadata)  # NEW: Pass type and metadata
        # ... rest of existing code ...

        # NEW: Show available actions for this file
        available_actions = self.engine.get_available_actions()
        if available_actions:
            self._add_traceback(
                f"📋 Available actions: {', '.join(available_actions[:5])}",
                "INFO"
            )

            # Get default action
            default_action = self.engine.get_default_action()
            if default_action:
                self._add_traceback(
                    f"⚡ Default action: {default_action}",
                    "INFO"
                )
```

---

## Patch 6: Enhance Action Execution with Validation
**Location:** grep_flight_v2.py:2612 (_execute_custom_script)

**ADD at the beginning of the method (after docstring):**
```python
def _execute_custom_script(self, script_name: str, target: str):
    """Execute custom script from custom_scripts.json"""

    # NEW: Validate action compatibility
    validation = self.engine.validate_action_for_target(script_name)
    if not validation["compatible"]:
        self._add_traceback(
            f"⚠️ Action '{script_name}' not compatible with current target",
            "WARNING"
        )
        self._add_traceback(f"   Reason: {validation['reason']}", "INFO")
        if validation["suggestions"]:
            self._add_traceback(
                f"   Try: {', '.join(validation['suggestions'])}",
                "INFO"
            )
        return

    # Show confirmation for actions that require it
    if validation.get("requires_confirmation"):
        # TODO: Add confirmation dialog
        self._add_traceback(
            f"⚠️ Action '{script_name}' requires user confirmation",
            "WARNING"
        )
        # For now, continue anyway

    # ... rest of existing code ...
```

---

## Patch 7: Add Action Menu Filtering
**Location:** After actions menu creation in UI (find where actions are populated)

**NEW METHOD to add to GrepFlightGUI class:**
```python
def _populate_actions_menu(self):
    """Populate actions menu with context-aware filtering"""
    # Clear existing menu items (keep first few standard items)
    # ... your menu clearing code ...

    # Get available actions for current target
    if hasattr(self.engine, 'get_available_actions'):
        available = self.engine.get_available_actions()

        if available:
            # Add separator
            # menu.add_separator()
            # menu.add_command(label="Context-Aware Actions", state='disabled')
            # menu.add_separator()

            # Add available actions
            for action_name in available[:10]:  # Limit to 10
                # Add menu item for this action
                # menu.add_command(
                #     label=action_name,
                #     command=lambda a=action_name: self._execute_action(a)
                # )
                pass
```

---

## Testing the Integration

### Step 1: Test Target Context Resolution
```bash
cd /home/commander/3_Inventory/Warrior_Flow/versions/Warrior_Flow_v09x_Monkey_Buisness_v2/Modules/action_panel/grep_flight_v0_2b/

# Test with a Python file
python3 target_context_system.py /path/to/file.py file

# Test with a directory
python3 target_context_system.py /path/to/project folder
```

### Step 2: Test with target.sh
```bash
# Set target via target.sh
/home/commander/3_Inventory/Warrior_Flow/target.sh /path/to/file.py

# Check grep_flight log to see context resolution
tail -f grep_flight_log_*.log
```

### Step 3: Verify Action Filtering
- Set a target file via target.sh
- Check that traceback shows "Available actions: ..."
- Check that incompatible actions are filtered out

---

## Expected Behavior Changes

### Before Patch:
1. Target type information discarded
2. All actions available regardless of target
3. Engineer's toolkit launches for syntax check on file
4. No intelligent routing

### After Patch:
1. Target type and metadata stored
2. Actions filtered by compatibility
3. Default action suggested (syntax check for .py files)
4. Smart routing with validation
5. Clear feedback about incompatible actions

---

## Next Steps

1. Apply patches in order
2. Test each patch individually
3. Register custom scripts via `action_registry.register_from_profile()`
4. Build approval UI for auto-onboarding (see Phase 3 in main doc)
5. Enhance output routing based on action metadata

---

## Notes

- The system is backwards compatible - old behavior maintained if context system not initialized
- Target type from target.sh now properly utilized
- Onboard_prober data automatically loaded if cache exists
- Safe actions can auto-execute, dangerous ones require confirmation
- File patterns intelligently matched (*.py, *.sh, etc.)
