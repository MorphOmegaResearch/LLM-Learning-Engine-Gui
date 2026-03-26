#!/usr/bin/env python3
"""
Grep Flight - Babel Edition
Ultra-slim bottom toolbar with surgical grep operations
Adapted for Babel v01a from Babel System v2.1.0
Author: Assistant | Integrated by: Babel System
Version: 2.1.0-babel
"""

import os
import sys
import re
import argparse
import subprocess
import shlex
import json
import threading
import queue
try:
    import pyperclip
    CLIPBOARD_AVAILABLE = True
except ImportError:
    CLIPBOARD_AVAILABLE = False
    pyperclip = None
import inspect
import traceback
import tkinter as tk
from tkinter import ttk, simpledialog, messagebox, scrolledtext, filedialog
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Any, Callable
from dataclasses import dataclass, field
from enum import Enum, auto

# BABEL: Chat backend disabled - not needed for Babel grep operations
# Original Babel System code attempted to import guillm/OllamaManager
# Babel version focuses on core grep functionality without chat integration
CHAT_BACKEND_AVAILABLE = False
ChatBackend = None

from tkinter.colorchooser import askcolor

try:
    from version_manager import VersionManager
    VERSION_MANAGER_AVAILABLE = True
except ImportError:
    VersionManager = None
    VERSION_MANAGER_AVAILABLE = False

# Import PFC Viewer
try:
    from pfc_viewer import show_pfc_results
except ImportError:
    show_pfc_results = None

# Import backup system
try:
    from backup_system import show_backup_dialog
    BACKUP_SYSTEM_AVAILABLE = True
except ImportError as e:
    print(f"Backup system not available: {e}")
    BACKUP_SYSTEM_AVAILABLE = False
    show_backup_dialog = None

try:
    pass
except ImportError:
    # Try parent directory if not found (in case of different execution context)
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
    try:
        from pfc_viewer import show_pfc_results
    except ImportError:
        show_pfc_results = None

# ============================================================================
# Global Traceback System - Event Types
# ============================================================================

class EventCategory(Enum):
    """Event categories for unified traceback logging"""
    GREP_FLIGHT = auto()  # grep_flight workflow events
    PFC = auto()          # Preflight check events
    CHAT = auto()          # Chat/AI events
    TASK = auto()          # Task operations
    FILE = auto()          # File operations
    STASH = auto()         # Stash operations
    SESSION = auto()       # Session management
    PROFILE = auto()       # Profile changes
    DEBUG = auto()         # Debug messages
    INFO = auto()          # Info messages
    WARNING = auto()       # Warnings
    ERROR = auto()         # Errors
    BABEL_CATALOG = auto() # Onboarder catalog events
    BABEL_SYNC = auto()    # Todo sync events
    BABEL_CONFORM = auto() # Conformity actions
    UI_EVENT = auto()      # UI interactions (button clicks, tab switches, etc.)

# Global engine instance for cross-module logging
_global_engine = None

def get_traceback_engine():
    """Get global traceback engine instance"""
    return _global_engine

def set_traceback_engine(engine):
    """Set global traceback engine instance"""
    global _global_engine
    _global_engine = engine

# Convenience logging functions for external modules
def log_to_traceback(category: EventCategory, operation: str, context: dict, result: dict = None, error: str = None):
    """Log event to traceback console from external module"""
    if _global_engine:
        level = "ERROR" if error else "INFO"
        if category == EventCategory.WARNING:
            level = "WARNING"
        elif category == EventCategory.DEBUG:
            level = "DEBUG"

        # Build event tag: #[Event:CATEGORY_OPERATION]
        event_tag = f"#[Event:{category.name}_{operation.upper().replace(' ', '_').replace('-', '_')}]"

        message = f"{event_tag} [{category.name}] {operation}"
        if context:
            message += f" | {context}"
        if result:
            message += f" → {result}"
        if error:
            message += f" ✗ {error}"

        _global_engine.log_debug(message, level)

        # Add to workflow steps for structured tracking
        _global_engine._add_workflow_step(
            f"{category.name}_{operation.upper().replace(' ', '_')}",
            message,
            {'context': context, 'result': result, 'error': error}
        )

        # Sync significant events to Os_Toolkit journal
        if hasattr(_global_engine, 'sync_to_journal'):
            _global_engine.sync_to_journal(category, operation, context, result, error)

def ui_event_tracker(event_name: str):
    """Decorator to automatically log UI events with full traceback context

    Usage:
        @ui_event_tracker("button_clicked")
        def _my_button_handler(self):
            ...

    Logs:
        - Event name and timestamp
        - Method name, file, line number
        - Self attributes (widget state, vars, etc.)
        - Exceptions with auto-bug marking
    """
    def decorator(func):
        def wrapper(self, *args, **kwargs):
            import inspect
            import traceback as tb

            # Get caller info
            frame = inspect.currentframe()
            caller_file = inspect.getfile(func)
            caller_line = inspect.getsourcelines(func)[1]
            method_name = func.__name__

            # Log event start
            context = {
                'method': method_name,
                'file': Path(caller_file).name,
                'line': caller_line,
                'args': str(args)[:100],
                'kwargs': str(kwargs)[:100]
            }

            log_to_traceback(EventCategory.UI_EVENT, f"{event_name}_START", context, {"status": "triggered"})

            try:
                # Execute the actual function
                result = func(self, *args, **kwargs)

                # Log success
                log_to_traceback(EventCategory.UI_EVENT, f"{event_name}_SUCCESS", context, {"status": "completed"})
                return result

            except Exception as e:
                # Log failure with full traceback
                error_tb = tb.format_exc()
                error_context = {
                    **context,
                    'error_type': type(e).__name__,
                    'error_msg': str(e)[:200],
                    'traceback': error_tb[:500]
                }

                log_to_traceback(EventCategory.UI_EVENT, f"{event_name}_ERROR", error_context, error=str(e))

                # Auto-mark bug in code
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                bug_marker = f"#TODO: [BUG_{timestamp}] [Log_/babel_data/logs/unified_traceback.log] {type(e).__name__}: {str(e)[:50]}"

                # Log bug marker
                _global_engine.log_debug(f"🐛 AUTO-MARKED BUG: {bug_marker}", "ERROR")
                _global_engine.log_debug(f"   File: {caller_file}:{caller_line}", "ERROR")
                _global_engine.log_debug(f"   Method: {method_name}", "ERROR")

                # 🎯 AUTO-TRIGGER TODOSYNC! (Runtime error → Bug marked → Sync todos → Terminal update!)
                try:
                    if hasattr(self, '_sync_todos'):
                        _global_engine.log_debug("🔄 Auto-triggering TodoSync after bug marking...", "INFO")
                        # Schedule async to not block error handling
                        import threading
                        threading.Thread(target=self._sync_todos, daemon=True).start()
                except Exception as sync_err:
                    _global_engine.log_debug(f"⚠️ Auto-sync failed: {sync_err}", "WARNING")

                # Re-raise for visibility
                raise

        return wrapper
    return decorator

# ============================================================================
# Configuration - Bottom Panel Focus
# ============================================================================

@dataclass
class PanelConfig:
    """Bottom panel specific configuration"""
    # Panel dimensions
    PANEL_HEIGHT: int = 36  # ~2.5cm at 96 DPI
    PANEL_WIDTH: int = None  # Full screen
    EXPANDED_HEIGHT: int = 320  # When expanded
    CLI_HEIGHT: int = 600 # CLI Mode height
    
    # Colors - Dark theme for bottom bar
    BG_COLOR: str = '#1a1a1a'
    FG_COLOR: str = '#e0e0e0'
    ACCENT_COLOR: str = '#4ec9b0'
    HOVER_COLOR: str = '#2a2a2a'
    PRESSED_COLOR: str = '#3a3a3a'
    BORDER_COLOR: str = '#4a4a4a'
    
    # Button layout
    BUTTON_WIDTH: int = 65
    BUTTON_HEIGHT: int = 26
    ICON_SIZE: int = 16
    
    # Animation
    EXPAND_SPEED: int = 12  # ms per step
    COLLAPSE_SPEED: int = 8
    
    # Native apps
    TERMINAL: str = 'xterm'
    EDITOR: str = 'mousepad'
    FILE_MANAGER: str = 'thunar'
    BROWSER: str = 'xdg-open'
    
    # Indicators
    INDICATOR_RADIUS: int = 6
    INDICATOR_SPACING: int = 3
    
    # Workflow colors
    WORKFLOW_COLORS: Dict[str, str] = field(default_factory=lambda: {
        'TARGET_SET': '#4ec9b0',
        'SCAN_STARTED': '#ffb74d',
        'SCAN_COMPLETE': '#4caf50',
        'PFL_FOUND': '#9c27b0',
        'VALIDATION': '#2196f3',
        'FIX_APPLIED': '#f44336',
        'COMPLETE': '#00bcd4',
        'ERROR': '#ff5252',
        'DEBUG': '#00ff00',  # Bright green for debug messages
        'INFO': '#e0e0e0'     # Default text color
    })

@dataclass 
class WorkflowStep:
    """Pre-defined workflow step"""
    id: str
    name: str
    description: str
    icon: str = "▶"
    command_template: str = ""
    requires_target: bool = True
    requires_pattern: bool = False
    preflight_check: Optional[str] = None
    post_action: Optional[str] = None
    
    def execute(self, **kwargs) -> Dict:
        """Execute this workflow step"""
        cmd = self.command_template
        for key, value in kwargs.items():
            if value:
                cmd = cmd.replace(f'{{{key}}}', str(value))
        
        return {
            'step_id': self.id,
            'name': self.name,
            'command': cmd,
            'timestamp': datetime.now().isoformat(),
            'kwargs': kwargs
        }

# ============================================================================
# Workflow Definitions
# ============================================================================

class WorkflowPresets:
    """Pre-defined surgical workflows"""
    
    @staticmethod
    def get_workflows() -> Dict[str, List[WorkflowStep]]:
        return {
            'quick_scan': [
                WorkflowStep('select_target', 'Select Target', 'Choose target directory or file', "📁"),
                WorkflowStep('set_pattern', 'Set Pattern', 'Enter search pattern', "🔍"),
                WorkflowStep('grep_scan', 'Grep Scan', 'Perform initial scan', "⚡", 
                           'grep -rn "{pattern}" {target}'),
                WorkflowStep('extract_pfl', 'Extract PFL', 'Find existing PFL tags', "🏷️",
                           'grep -rn "#\[PFL:" {target}'),
                WorkflowStep('validate', 'Validate', 'Validate results', "✅"),
            ],
            'deep_debug': [
                WorkflowStep('select_target', 'Select Target', 'Choose target', "📁"),
                WorkflowStep('preflight', 'Preflight Check', 'Run system checks', "🛫",
                           'echo "Running preflight checks..."'),
                WorkflowStep('grep_bugs', 'Find Bugs', 'Search for BUG/FIXME tags', "🐛",
                           'grep -rni "BUG\\|FIXME" {target}'),
                WorkflowStep('grep_todos', 'Find TODOs', 'Search for TODO tags', "📝",
                           'grep -rni "TODO" {target}'),
                WorkflowStep('analyze', 'Analyze', 'Analyze findings', "📊"),
                WorkflowStep('propose_fixes', 'Propose Fixes', 'Generate fix proposals', "🔧"),
            ],
            'pfl_audit': [
                WorkflowStep('select_target', 'Select Target', 'Choose target', "📁"),
                WorkflowStep('find_all_pfl', 'Find All PFL', 'Extract all PFL tags', "🏷️",
                           'grep -rn "#\[PFL:" {target}'),
                WorkflowStep('categorize', 'Categorize', 'Categorize by type', "📂"),
                WorkflowStep('prioritize', 'Prioritize', 'Set priorities', "🎯"),
                WorkflowStep('generate_report', 'Generate Report', 'Create audit report', "📋"),
            ],
            'surgical_fix': [
                WorkflowStep('select_target', 'Select Target', 'Select exact file', "📄"),
                WorkflowStep('identify_issue', 'Identify Issue', 'Specify exact issue', "🔎"),
                WorkflowStep('propose_fix', 'Propose Fix', 'Design fix', "💡"),
                WorkflowStep('apply_fix', 'Apply Fix', 'Apply the fix', "🛠️"),
                WorkflowStep('test_fix', 'Test Fix', 'Test the applied fix', "🧪"),
                WorkflowStep('add_pfl', 'Add PFL', 'Document the fix', "🏷️"),
            ]
        }

# ============================================================================
# Core Engine
# ============================================================================

class GrepSurgicalEngine:
    """Surgical grep engine with workflow tracking"""

    def __init__(self, config: PanelConfig):
        self.config = config
        self.current_target: Optional[str] = None
        self.current_pattern: Optional[str] = None
        self.current_workflow: Optional[str] = None
        self.workflow_steps: List[Dict] = []
        self.results_queue = queue.Queue()
        self.indicators: Dict[str, Dict] = {}
        self.recent_targets: List[str] = []  # History of recent targets
        self.recent_patterns: List[str] = []  # History of recent patterns
        self.max_history: int = 10  # Max items in history
        self.debug_log: List[str] = []  # Debug activity log
        self.max_debug_log: int = 1000  # Max debug log entries

    def log_debug(self, message: str, level: str = "DEBUG"):
        """Log debug message with timestamp and event tagging"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        # Ensure event tagging
        if "#[Event:" not in message:
            # Map level/module to reasonable event names if missing
            event_name = level.upper()
            if level == "DEBUG": event_name = "ENGINE_LOG"
            if level == "INFO": event_name = "STATUS_UPDATE"
            message = f"#[Event:{event_name}] {message}"

        log_entry = f"[{timestamp}] {message}"
        self.debug_log.append(log_entry)
        if len(self.debug_log) > self.max_debug_log:
            self.debug_log = self.debug_log[-self.max_debug_log:]
        
        print(log_entry)  # Also print to console

        # Write to shared unified_traceback.log
        try:
            # In Babel v01a: .../Babel_v01a/babel_data/inventory/action_panel/grep_flight_v0_2b/grep_flight_babel.py
            # parents[4] = Babel_v01a root
            # parents[3] = babel_data (already!)
            log_dir = Path(__file__).resolve().parents[4] / "babel_data" / "logs"
            log_dir.mkdir(parents=True, exist_ok=True)  # Ensure directory exists
            shared_log = log_dir / "unified_traceback.log"
            full_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
            with open(shared_log, 'a') as f:
                f.write(f"[{full_timestamp}] [grep_flight] [{level}] {message}\n")
        except Exception as e:
            # Don't silently fail - at least print the error
            print(f"⚠️ Failed to write to unified_traceback.log: {e}")

    def sync_to_journal(self, category: EventCategory, operation: str, context: dict, result: dict = None, error: str = None):
        """Sync significant events to Os_Toolkit journal"""
        if category not in [EventCategory.TASK, EventCategory.FILE, EventCategory.PFC, EventCategory.SESSION]:
            return

        try:
            # Construct content
            content = f"{operation}"
            if context:
                content += f" | {context}"
            if error:
                content += f" | Error: {error}"
            
            # Determine type
            entry_type = "process_detected" # default
            if category == EventCategory.TASK:
                entry_type = "action_executed"
            elif category == EventCategory.FILE:
                entry_type = "file_analyzed"
            elif category == EventCategory.PFC:
                entry_type = "analysis_complete"
            
            # Locate Os_Toolkit
            # We are in GrepSurgicalEngine, we need access to babel_root. 
            # It's not stored in engine, but config might have it or we can derive it.
            # config is PanelConfig.
            # Let's try to derive it same way as BottomPanel
            babel_root = Path(__file__).resolve().parents[4]
            os_toolkit = babel_root / "Os_Toolkit.py"
            
            if os_toolkit.exists():
                cmd = [
                    'python3', str(os_toolkit), 
                    'journal', '--add', 
                    '--type', entry_type,
                    '--content', content
                ]
                # Run in background
                subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                
        except Exception as e:
            print(f"Journal sync failed: {e}")
        
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

    def set_pattern(self, pattern: str):
        """Set current pattern"""
        self.current_pattern = pattern
        # Add to recent patterns (avoid duplicates)
        if pattern in self.recent_patterns:
            self.recent_patterns.remove(pattern)
        self.recent_patterns.insert(0, pattern)
        # Limit history size
        if len(self.recent_patterns) > self.max_history:
            self.recent_patterns = self.recent_patterns[:self.max_history]
        self._add_workflow_step('PATTERN_SET', f'Pattern set: {pattern}')
        
    def execute_command(self, command: str) -> Tuple[str, str]:
        """Execute shell command and return output"""
        self._add_workflow_step('COMMAND_EXEC', f'Executing: {command}')
        
        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                cwd=self.current_target if self.current_target else os.getcwd()
            )
            
            output = result.stdout
            error = result.stderr
            
            if result.returncode == 0:
                self._add_workflow_step('COMMAND_SUCCESS', f'Command successful')
            else:
                self._add_workflow_step('COMMAND_ERROR', f'Command failed: {error}')
                
            return output, error
            
        except Exception as e:
            self._add_workflow_step('COMMAND_EXCEPTION', f'Exception: {str(e)}')
            raise
    
    def _add_workflow_step(self, step_type: str, message: str, data: Dict = None):
        """Add step to workflow history"""
        step = {
            'type': step_type,
            'timestamp': datetime.now().isoformat(),
            'message': message,
            'data': data or {}
        }
        self.workflow_steps.append(step)
        
        # Add to queue for UI updates
        self.results_queue.put(('workflow_step', step))
        
    def launch_editor(self, file_path: str, line: int = None):
        """Launch file in editor"""
        cmd = [self.config.EDITOR, file_path]
        if line:
            # Try to support line numbers if editor supports it
            if self.config.EDITOR in ['vim', 'nvim']:
                cmd.extend(['+', str(line)])
            elif self.config.EDITOR == 'gedit':
                cmd.extend(['+', str(line)])
                
        subprocess.Popen(cmd, start_new_session=True)
        self._add_workflow_step('EDITOR_LAUNCHED', f'Launched editor: {file_path}:{line}')
        
    def launch_terminal(self, path: str = None):
        """Launch terminal at path"""
        path = path or self.current_target or os.getcwd()
        subprocess.Popen([self.config.TERMINAL], cwd=path, start_new_session=True)
        self._add_workflow_step('TERMINAL_LAUNCHED', f'Launched terminal at: {path}')

# ============================================================================
# UI Components
# ============================================================================

class TreeViewPanel(tk.Frame):
    """Tree view panel for file browsing (Adapted from uni_launch)"""
    
    def __init__(self, parent, engine, root_path=None):
        super().__init__(parent, bg='#1a1a1a')
        self.engine = engine
        self.root_path = root_path or os.getcwd()
        self.tree = None
        self.setup_ui()
        self.refresh_tree()
    
    def setup_ui(self):
        """Setup tree view UI"""
        # Toolbar
        toolbar = tk.Frame(self, bg='#1a1a1a')
        toolbar.pack(fill=tk.X, padx=5, pady=2)
        
        tk.Button(toolbar, text="↻ Refresh", command=self.refresh_tree, 
                 bg='#3c3c3c', fg='#e0e0e0', relief=tk.FLAT, padx=8).pack(side=tk.LEFT, padx=2)
        
        tk.Button(toolbar, text="📂 Open", command=self.open_folder,
                 bg='#3c3c3c', fg='#e0e0e0', relief=tk.FLAT, padx=8).pack(side=tk.LEFT, padx=2)

        tk.Button(toolbar, text="🎯 Set Target", command=self.set_as_target,
                 bg='#0e639c', fg='#ffffff', relief=tk.FLAT, padx=8).pack(side=tk.LEFT, padx=2)
        
        # Tree view with scrollbars
        tree_frame = tk.Frame(self, bg='#1a1a1a')
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Vertical scrollbar
        vsb = ttk.Scrollbar(tree_frame, orient="vertical")
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Horizontal scrollbar
        hsb = ttk.Scrollbar(tree_frame, orient="horizontal")
        hsb.pack(side=tk.BOTTOM, fill=tk.X)
        
        # Tree widget
        self.tree = ttk.Treeview(tree_frame, columns=("type", "size", "path"), 
                                 displaycolumns=("type", "size"),
                                 yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Configure scrollbars
        vsb.config(command=self.tree.yview)
        hsb.config(command=self.tree.xview)
        
        # Configure columns
        self.tree.heading("#0", text="Name")
        self.tree.heading("type", text="Type")
        self.tree.heading("size", text="Size")
        
        self.tree.column("#0", width=300)
        self.tree.column("type", width=80)
        self.tree.column("size", width=80)
        
        # Add tags for different file types
        self.tree.tag_configure('directory', foreground='#569cd6') # Blue
        self.tree.tag_configure('python', foreground='#4ec9b0')    # Teal
        self.tree.tag_configure('script', foreground='#ce9178')    # Orange
        self.tree.tag_configure('executable', foreground='#f44747') # Red
        self.tree.tag_configure('file', foreground='#d4d4d4')      # Grey
        
        # Bind events
        self.tree.bind('<<TreeviewOpen>>', self.on_expand)
        self.tree.bind('<<TreeviewSelect>>', self.on_select)
        self.tree.bind("<Double-1>", self.on_double_click)
        self.tree.bind("<Button-3>", self.show_context_menu)

    def on_select(self, event):
        """Handle tree selection logging"""
        node_id = self.tree.focus()
        if node_id:
            item = self.tree.item(node_id)
            values = item.get("values", [])
            if len(values) >= 3:
                path = values[2]
                node_type = values[0]
                self.engine.log_debug(f"Tree Select: {node_type} | {path}", "DEBUG")
                
                # If we can find the BottomPanel, log to its traceback
                widget = self.master
                while widget and not isinstance(widget, BottomPanel):
                    widget = widget.master
                    if widget is None: break
                
                if widget and isinstance(widget, BottomPanel):
                    widget._add_traceback(f"📁 Select: {os.path.basename(path)} ({node_type})", "DEBUG")

    def refresh_tree(self):
        """Refresh the tree view"""
        self.tree.delete(*self.tree.get_children())
        if self.root_path and os.path.exists(self.root_path):
            self.add_node("", self.root_path, self.root_path)
    
    def add_node(self, parent, node_text, path):
        """Add a node to the tree"""
        # Use basename for display if it's the root being added as child
        display_text = os.path.basename(path) if not node_text else node_text
        if not display_text: display_text = path

        if os.path.isdir(path):
            node_id = self.tree.insert(parent, "end", text=display_text, 
                                      values=("Directory", "", path),
                                      tags=('directory',))
            # Dummy node for expansion
            self.tree.insert(node_id, "end", text="Loading...")
        else:
            size = os.path.getsize(path) if os.path.exists(path) else 0
            file_type = self.get_file_type(path)
            tags = self.get_file_tags(path)
            
            self.tree.insert(parent, "end", text=display_text,
                            values=(file_type, self.format_size(size), path),
                            tags=tags)

    def on_expand(self, event):
        """Handle tree expansion"""
        node_id = self.tree.focus()
        if not node_id: return
        
        children = self.tree.get_children(node_id)
        if children and self.tree.item(children[0])["text"] == "Loading...":
            self.tree.delete(children[0])
            parent_path = self.tree.item(node_id, "values")[2]
            
            self.engine.log_debug(f"Tree Expand: {parent_path}", "DEBUG")

            if os.path.isdir(parent_path):
                try:
                    for item in sorted(os.listdir(parent_path)):
                        if item.startswith('.') and item != '.docv2_workspace': continue # Skip hidden except workspace
                        item_path = os.path.join(parent_path, item)
                        self.add_node(node_id, item, item_path)
                except PermissionError:
                    pass

    def on_double_click(self, event):
        """Handle double click"""
        node_id = self.tree.focus()
        if node_id:
            path = self.tree.item(node_id, "values")[2]
            if os.path.isfile(path):
                self.engine.launch_editor(path)

    def show_context_menu(self, event):
        """Show context menu"""
        item = self.tree.identify_row(event.y)
        if not item: return
        self.tree.selection_set(item)
        path = self.tree.item(item, "values")[2]
        
        menu = tk.Menu(self, tearoff=0, bg='#2a2a2a', fg='#e0e0e0')
        menu.add_command(label="🎯 Set as Target", command=lambda: self.set_as_target(path))
        menu.add_command(label="✏️ Open in Editor", command=lambda: self.engine.launch_editor(path))
        menu.add_command(label="📂 Open Folder", command=lambda: self.open_folder(path))
        menu.add_separator()
        menu.add_command(label="📋 Copy Path", command=lambda: self.copy_path(path))
        menu.post(event.x_root, event.y_root)

    def set_as_target(self, path=None):
        """Set selected or provided path as global target"""
        if not path:
            selected = self.tree.selection()
            if not selected: return
            path = self.tree.item(selected[0], "values")[2]
        
        # We need access to the parent BottomPanel to set the target variable
        # We can traverse up or expect 'engine' to have a reference, 
        # or better, use the IPC mechanism since we are INSIDE grep_flight
        
        # Direct set since we are inside grep_flight
        # Find BottomPanel instance by traversing up
        # This is a bit hacky but works for embedded widgets
        widget = self.master
        while widget and not isinstance(widget, BottomPanel):
            widget = widget.master
            if widget is None: break
        
        if widget and isinstance(widget, BottomPanel):
            widget.target_var.set(path)
            widget.engine.set_target(path)
            widget.status_var.set(f"✅ Target: {os.path.basename(path)}")
            
            # Log target set to traceback
            widget._add_traceback(f"🎯 Target Set (Tree): {path}", "TARGET_SET")
            
            # Also update pattern to filename if it's a file
            if os.path.isfile(path):
                widget.pattern_var.set(os.path.basename(path))

    def open_folder(self, path=None):
        """Open folder in file manager"""
        if not path:
            selected = self.tree.selection()
            if not selected: return
            path = self.tree.item(selected[0], "values")[2]
        
        target = path if os.path.isdir(path) else os.path.dirname(path)
        subprocess.Popen(['xdg-open', target])

    def copy_path(self, path):
        """Copy path to clipboard"""
        self.clipboard_clear()
        self.clipboard_append(path)

    @staticmethod
    def get_file_type(path):
        if path.endswith('.py'): return "Python"
        if path.endswith('.sh'): return "Shell"
        if path.endswith('.json'): return "JSON"
        if path.endswith('.md'): return "Markdown"
        return "File"

    @staticmethod
    def get_file_tags(path):
        if path.endswith('.py'): return ('python',)
        if path.endswith('.sh'): return ('script',)
        if os.access(path, os.X_OK): return ('executable',)
        return ('file',)

    @staticmethod
    def format_size(size):
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024.0: return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} TB"

# ============================================================================
# Bottom Panel UI
# ============================================================================

class BottomPanel(tk.Tk):
    """Main bottom panel window"""

    def __init__(self, config: PanelConfig, app_ref=None):
        # Configure root window
        super().__init__()
        self.config = config
        self.engine = GrepSurgicalEngine(config)
        self.app_ref = app_ref  # Reference to Universal Launcher for tab navigation
        
        # Resolve paths
        # File: .../Babel_v01a/babel_data/inventory/action_panel/grep_flight_v0_2b/grep_flight_babel.py
        # parents[0] = grep_flight_v0_2b
        # parents[1] = action_panel
        # parents[2] = inventory
        # parents[3] = babel_data
        # parents[4] = Babel_v01a (Babel Root)
        self.babel_root = Path(__file__).resolve().parents[4]
        self.version_root = self.babel_root / "babel_data"
        self.repo_root = self.babel_root
        self.project_root = self.babel_root

        # Define localized data paths (New Standalone Logic)
        self.morph_data_dir = self.version_root / "data" / "morph"
        self.config_dir = self.version_root / "data" / "config"
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.tasks_dir = self.version_root / "data" / "tasks"
        self.sessions_dir = self.version_root / "sessions"
        self.logs_dir = self.version_root / "logs"

        # Create directories if missing
        for d in [self.morph_data_dir, self.config_dir, self.tasks_dir, self.sessions_dir, self.logs_dir]:
            d.mkdir(parents=True, exist_ok=True)
        
        self.gemini_proc = None # Track Gemini process

        # Initialize Version Manager
        self.version_manager = None
        if VERSION_MANAGER_AVAILABLE:
            try:
                self.version_manager = VersionManager(str(self.project_root / "stable.json"))
                self.engine.log_debug("VersionManager initialized", "INFO")
            except Exception as e:
                self.engine.log_debug(f"VersionManager init failed: {e}", "ERROR")

        # Register as global traceback engine for cross-module logging
        set_traceback_engine(self.engine)
        self.engine.log_debug("grep_flight traceback engine initialized", "INFO")

        # Initialize chat backend
        self.chat_backend = None
        if CHAT_BACKEND_AVAILABLE:
            try:
                self.chat_backend = ChatBackend()
                self.chat_backend.create_session(session_type="task")
                self.engine.log_debug("Chat backend initialized", "INFO")
            except Exception as e:
                self.engine.log_debug(f"Chat backend init failed: {e}", "ERROR")
                self.chat_backend = None

        # State
        self.expansion_state = 0 # 0=Collapsed, 1=Standard, 2=CLI
        self.is_expanded = False # Deprecated but kept for compatibility if needed
        self.target_var = tk.StringVar()
        self.pattern_var = tk.StringVar()
        self.status_var = tk.StringVar(value="Ready - Click ▽ to expand | Press ❓ for help")
        self.current_workflow = None
        self.task_watcher_active = True
        self.task_mtimes = {} # Track modification times
        self.is_flashing = False
        
        # Context Management
        self.context_view_var = tk.BooleanVar(value=False)
        self.last_tool_context = {}  # Store last tool result

        # Plan Modules & Taxonomy State
        self.active_plan_module = tk.StringVar(value="Ag Forge / Clip")
        self.invocation_preview = tk.StringVar()
        self.taxonomy_vars = {}
        self.system_categories = [
            'UI & UX', 'System Health', 'Intelligence', 'Planning & Workflow', 
            'Tools & Arsenal', 'Version Control', 'System Launch', 'Observation', 
            'Communication', 'Tests & Diagnostics', 'Migration & Scripts'
        ]
        for cat in self.system_categories:
            self.taxonomy_vars[cat] = tk.BooleanVar(value=False)
        
        self._update_invocation_preview()

        # Workflow indicators
        self.indicator_canvas = None
        self.indicators = {}

        # Load workflow actions from profile (default profile if none set)
        self.active_profile = "default" # Use Babel default key
        self.workflow_actions = self._load_workflow_actions_config()
        self.toolkit_order = []  # Will be loaded when config UI opens
        self.current_profile_var = None  # Will be initialized in config UI
        self.tool_locations: Dict[str, str] = {}
        self.toolkit_popup = None
        
        # IPC for external target setting (Thunar integration)
        self.ipc_file = Path(os.getenv('XDG_RUNTIME_DIR', '/tmp')) / f"grep_flight_ipc_{os.getenv('USER', 'user')}.fifo"
        self._setup_ipc()
        
        # Setup
        self._setup_window()
        self._create_collapsed_panel()
        self._create_expanded_panel()
        self._create_traceback_popup()
        self._bind_events()

        # Profile Initial UI Structure
        self.after(500, self._profile_ui_structure)

        # Start update loop
        self.after(100, self._update_from_engine)

        # Start shared log monitor
        self._start_shared_log_monitor()

        # Start IPC monitor loop
        self.after(200, self._monitor_ipc)

    def _start_shared_log_monitor(self):
        """Start a background thread to tail the unified_traceback.log"""
        # logs_dir is self.version_root / "logs"
        self.shared_log_path = self.logs_dir / "unified_traceback.log"
        if not self.shared_log_path.exists():
            try:
                self.shared_log_path.parent.mkdir(parents=True, exist_ok=True)
                self.shared_log_path.touch()
            except: pass

        self.last_shared_log_size = self.shared_log_path.stat().st_size if self.shared_log_path.exists() else 0
        
        def monitor():
            while True:
                try:
                    if self.shared_log_path.exists():
                        current_size = self.shared_log_path.stat().st_size
                        if current_size > self.last_shared_log_size:
                            with open(self.shared_log_path, 'r') as f:
                                f.seek(self.last_shared_log_size)
                                new_lines = f.readlines()
                                for line in new_lines:
                                    line = line.strip()
                                    if line:
                                        # Process ALL logs including grep_flight's own
                                        # (Fixed: was filtering out "[grep_flight]" causing missing events)
                                        # Route to results queue for main thread to handle
                                        self.engine.results_queue.put(('shared_log', line))
                        
                        self.last_shared_log_size = current_size
                except Exception as e:
                    pass
                
                import time
                time.sleep(1.0) # Check every second

        import threading
        threading.Thread(target=monitor, daemon=True).start()

        # Register cleanup on exit
        self.protocol("WM_DELETE_WINDOW", self._cleanup_and_exit)

        # Log startup
        print("\n" + "="*60)
        print("🚀 GREP FLIGHT V2 - DEBUG MODE ENABLED")
        print("="*60)
        print("Keyboard Shortcuts:")
        print("  Ctrl+D  - Show/hide debug log window")
        print("  Ctrl+P  - Show/hide traceback window")
        print("  Ctrl+B  - Toggle panel expand/collapse")
        print("  Ctrl+G  - Execute grep search")
        print("  Ctrl+Q  - Quit application")
        print("  Esc     - Smart close (popups → collapse panel)")
        print("="*60)
        print("Debug logging to console AND debug window...")
        print("="*60 + "\n")

        self.engine.log_debug("="*60)
        self.engine.log_debug("GREP FLIGHT V2 INITIALIZED")
        self.engine.log_debug("="*60)
        self.engine.log_debug(f"Screen size: {self.winfo_screenwidth()}x{self.winfo_screenheight()}")
        self.engine.log_debug(f"Panel height: {self.config.PANEL_HEIGHT}px")
        self.engine.log_debug(f"Expanded height: {self.config.EXPANDED_HEIGHT}px")

        # Log startup state to TRACEBACK for visibility
        version_name = self.version_root.name if hasattr(self, 'version_root') else "Unknown"
        gf_module = Path(__file__).parent.name
        self._add_traceback(
            f"🚀 STARTUP\n"
            f"   Version: {version_name}\n"
            f"   Module: {gf_module}\n"
            f"   IPC: {self.ipc_file}\n"
            f"   Target Input: '{self.target_var.get() or '(empty)'}'\n"
            f"   Pattern Input: '{self.pattern_var.get() or '(empty)'}'"
        , "STARTUP")
        
    def _setup_window(self):
        """Setup the window as bottom panel"""
        # Use dock type hint instead of overrideredirect to allow input focus
        try:
            self.attributes('-type', 'dock')
            # Remove title bar via Motif hints if needed (usually handled by dock type)
            self.overrideredirect(False) 
        except:
            # Fallback for systems that don't support dock type
            self.overrideredirect(True)
        
        # Get screen dimensions
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        
        # Set position (bottom of screen)
        self.geometry(f"{screen_width}x{self.config.PANEL_HEIGHT}+0+{screen_height - self.config.PANEL_HEIGHT}")
        
        # Always on top
        self.attributes('-topmost', True)
        
        # Configure colors
        self.configure(bg=self.config.BG_COLOR)

    def _setup_ipc(self):
        """Setup IPC FIFO for receiving external target requests"""
        try:
            # Remove existing FIFO if it exists
            if self.ipc_file.exists():
                self.ipc_file.unlink()
                self.engine.log_debug(f"Removed existing IPC file: {self.ipc_file}", "DEBUG")

            # Create named pipe (FIFO)
            os.mkfifo(str(self.ipc_file), 0o600)
            self.engine.log_debug(f"✓ IPC FIFO created: {self.ipc_file}", "INFO")

            # Open FIFO in non-blocking read mode and KEEP IT OPEN
            # This allows writers to connect at any time
            self.ipc_fd = os.open(str(self.ipc_file), os.O_RDONLY | os.O_NONBLOCK)
            self.engine.log_debug(f"✓ IPC FIFO opened for reading (fd={self.ipc_fd})", "INFO")

            # TRACEBACK: Confirm IPC is ready
            self._add_traceback(f"📡 IPC READY\n   FIFO: {self.ipc_file}\n   Listening for target.sh...", "IPC")

            log_to_traceback(EventCategory.INFO, "ipc_setup",
                           {"path": str(self.ipc_file)},
                           {"status": "created"})

        except Exception as e:
            self.engine.log_debug(f"✗ IPC setup failed: {e}", "ERROR")
            log_to_traceback(EventCategory.ERROR, "ipc_setup_failed",
                           {"path": str(self.ipc_file)},
                           error=str(e))
            self.ipc_file = None
            self.ipc_fd = None

    def _monitor_ipc(self):
        """Monitor IPC FIFO for incoming messages (non-blocking)"""
        try:
            # Check if we have a valid fd
            if not hasattr(self, 'ipc_fd') or self.ipc_fd is None:
                if self.ipc_file and not self.ipc_file.exists():
                    self._add_traceback("⚠️ IPC FIFO missing, recreating...", "WARNING")
                    self._setup_ipc()
                self.after(500, self._monitor_ipc)
                return

            # Read from persistent fd (non-blocking)
            try:
                data = os.read(self.ipc_fd, 4096).decode('utf-8').strip()
                if data:
                    # LOG TO TRACEBACK - IPC message received!
                    self._add_traceback(f"📨 IPC RECEIVED\n   Raw: {data[:100]}{'...' if len(data) > 100 else ''}", "IPC")
                    self._process_ipc_message(data)
            except BlockingIOError:
                # No data available - normal for non-blocking
                pass
            except OSError as e:
                if e.errno == 9:  # Bad file descriptor - fd was closed
                    self.engine.log_debug("IPC fd closed, reopening...", "WARNING")
                    self._setup_ipc()
                else:
                    raise

        except Exception as e:
            self._add_traceback(f"❌ IPC MONITOR ERROR: {e}", "ERROR")
            self.engine.log_debug(f"IPC monitor error: {e}", "ERROR")

        # Schedule next check
        self.after(200, self._monitor_ipc)

    def _process_ipc_message(self, message: str):
        """Process incoming IPC message with target/pattern splitting logic"""
        try:
            self.engine.log_debug("="*60, "INFO")
            self.engine.log_debug(f"📨 IPC Message Received", "INFO")
            self.engine.log_debug("="*60, "INFO")
            self.engine.log_debug(f"Raw message: {message}", "DEBUG")

            # Parse message format: MESSAGE_TYPE|path|type|metadata|timestamp
            parts = message.split('|')
            if len(parts) < 2:
                raise ValueError(f"Invalid message format: expected 'TYPE|data...', got: {message}")

            msg_type = parts[0]
            self.engine.log_debug(f"Message type: {msg_type}", "DEBUG")

            if msg_type == "SET_TARGET":
                if len(parts) < 5:
                    raise ValueError(f"SET_TARGET requires 5 fields, got {len(parts)}")

                target_path = parts[1]
                target_type = parts[2]
                metadata = parts[3]
                timestamp = parts[4]

                # TRACEBACK: Log BEFORE state
                before_target = self.target_var.get() or "(empty)"
                before_pattern = self.pattern_var.get() or "(empty)"
                self._add_traceback(
                    f"🎯 SET_TARGET RECEIVED\n"
                    f"   Path: {target_path}\n"
                    f"   Type: {target_type}\n"
                    f"   BEFORE - Target Input: '{before_target}'\n"
                    f"   BEFORE - Pattern Input: '{before_pattern}'"
                , "TARGET")

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
                    self.status_var.set(f"✅ Target (folder): {path_obj.name}")
                    self.engine.log_debug(f"[TARGET_VAR] Set to directory: {target_path}", "DEBUG")
                elif os.path.isfile(target_path):
                    # It's a file: Lock target to Parent Dir, Inject Filename to Pattern
                    parent_dir = str(path_obj.parent)
                    filename = path_obj.name

                    self.target_var.set(parent_dir)
                    self.engine.set_target(parent_dir)
                    self.engine.log_debug(f"[TARGET_VAR] Set to parent dir: {parent_dir}", "DEBUG")

                    # Inject filename into input line (Pattern)
                    self.pattern_var.set(filename)
                    self.engine.log_debug(f"[PATTERN_VAR] Set to filename: {filename}", "DEBUG")

                    self.status_var.set(f"✅ Target: {path_obj.parent.name} | File: {filename}")

                # Force UI update - multiple approaches to ensure it takes
                self.update_idletasks()
                self.update()

                # Debug: verify the Entry widget exists and is linked
                if hasattr(self, 'target_entry'):
                    self.engine.log_debug(f"[TARGET_ENTRY] Widget exists, textvariable={self.target_entry.cget('textvariable')}", "DEBUG")
                    # Force Entry to refresh from StringVar
                    current_val = self.target_var.get()
                    self.target_entry.delete(0, tk.END)
                    self.target_entry.insert(0, current_val)
                    self.engine.log_debug(f"[TARGET_ENTRY] Manually inserted: {current_val}", "DEBUG")
                else:
                    self.engine.log_debug("[TARGET_ENTRY] Widget NOT FOUND - expanded panel may not be created yet", "WARNING")

                # TRACEBACK: Log AFTER state
                after_target = self.target_var.get() or "(empty)"
                after_pattern = self.pattern_var.get() or "(empty)"
                entry_exists = hasattr(self, 'target_entry')
                entry_value = self.target_entry.get() if entry_exists else "(no widget)"

                self._add_traceback(
                    f"✅ TARGET SET COMPLETE\n"
                    f"   AFTER - Target Input (var): '{after_target}'\n"
                    f"   AFTER - Pattern Input (var): '{after_pattern}'\n"
                    f"   AFTER - Entry Widget Value: '{entry_value}'\n"
                    f"   Entry Widget Exists: {entry_exists}"
                , "TARGET")

                self.engine.log_debug(f"[TARGET_VAR] Final value: {self.target_var.get()}", "DEBUG")

                # Expand panel if collapsed
                if not self.is_expanded:
                    self.engine.log_debug("Panel collapsed, expanding...", "INFO")
                    self._expand_panel()

                # Focus pattern entry for quick search
                if hasattr(self, 'pattern_entry'):
                    self.after(100, self.pattern_entry.focus)

                # Determine working directory for action panel context
                if os.path.isdir(target_path):
                    action_panel_dir = target_path
                else:
                    action_panel_dir = str(path_obj.parent)

                # Store directory context for action panel and other systems
                self.action_panel_context = {
                    "target_dir": action_panel_dir,
                    "target_path": target_path,
                    "target_type": target_type,
                    "target_name": path_obj.name,
                    "version_root": str(self.version_root) if hasattr(self, 'version_root') else "",
                    "grep_flight_module": Path(__file__).parent.name,
                    "timestamp": timestamp,
                    "metadata": metadata
                }

                # Log to traceback with FULL context including version and directory info
                version_info = self.version_root.name if hasattr(self, 'version_root') else "Unknown"
                gf_module = Path(__file__).parent.name

                log_to_traceback(EventCategory.FILE, "target_set_external", {
                    "source": "IPC",
                    "type": target_type,
                    "metadata": metadata,
                    "grep_flight_version": gf_module,
                    "babel_version": "v01a",
                    "action_panel_dir": action_panel_dir
                }, {
                    "path": target_path,
                    "timestamp": timestamp,
                    "context_set": True
                })

                # Detailed traceback entry for target onboarding
                self._add_traceback(
                    f"📂 Target: {path_obj.name}\n"
                    f"   Dir: {action_panel_dir}\n"
                    f"   Version: {version_info} [{gf_module}]\n"
                    f"   Type: {target_type}",
                    "TARGET_SET"
                )

                # Propagate context to PFC system
                log_to_traceback(EventCategory.PFC, "target_context_update", {
                    "action_panel_dir": action_panel_dir,
                    "sibling_files": self._get_sibling_files(action_panel_dir) if os.path.isdir(action_panel_dir) else [],
                    "target_file": path_obj.name if os.path.isfile(target_path) else None
                }, {"propagated": True})

                self.engine.log_debug("✓ Target set successfully with full context propagation", "INFO")

            elif msg_type == "ERROR":
                # Handle error messages from target.sh
                if len(parts) >= 3:
                    source = parts[1]
                    error_msg = parts[2]
                    context = parts[3] if len(parts) > 3 else ""

                    self.engine.log_debug(f"External script error from {source}: {error_msg}", "ERROR")
                    self._add_traceback(f"❌ External Error ({source}): {error_msg}", "ERROR")

                    if context:
                        self.engine.log_debug(f"Error context: {context}", "DEBUG")

                    log_to_traceback(EventCategory.ERROR, "external_script_error",
                                   {"source": source, "context": context},
                                   error=error_msg)
            else:
                self.engine.log_debug(f"Unknown message type: {msg_type}", "WARNING")
                raise ValueError(f"Unknown IPC message type: {msg_type}")

            self.engine.log_debug("="*60, "INFO")

        except Exception as e:
            self.engine.log_debug(f"✗ IPC message processing failed: {e}", "ERROR")
            self._add_traceback(f"❌ IPC Error: {str(e)}", "ERROR")
            log_to_traceback(EventCategory.ERROR, "ipc_message_failed",
                           {"message": message[:100]},
                           error=str(e))

    def _get_sibling_files(self, directory: str, limit: int = 20) -> list:
        """Get list of sibling files in directory for PFC context"""
        try:
            dir_path = Path(directory)
            if not dir_path.is_dir():
                return []
            files = []
            for item in sorted(dir_path.iterdir())[:limit]:
                if item.is_file():
                    files.append({
                        "name": item.name,
                        "ext": item.suffix,
                        "size": item.stat().st_size
                    })
            return files
        except Exception as e:
            self.engine.log_debug(f"Error getting sibling files: {e}", "WARNING")
            return []

    def _profile_ui_structure(self, root_widget=None):
        """Recursively profile UI structure for feature cataloging"""
        if root_widget is None:
            root_widget = self

        structure = {
            "type": root_widget.winfo_class(),
            "name": root_widget.winfo_name(),
            "children": []
        }

        # Count features
        features = {"buttons": 0, "labels": 0, "entries": 0, "frames": 0, "listboxes": 0}

        def _walk(widget, parent_struct):
            for child in widget.winfo_children():
                w_type = child.winfo_class()
                w_name = child.winfo_name()
                
                # Update counts
                if w_type == "Button": features["buttons"] += 1
                elif w_type == "Label": features["labels"] += 1
                elif w_type == "Entry": features["entries"] += 1
                elif w_type == "Frame": features["frames"] += 1
                elif w_type == "Listbox": features["listboxes"] += 1

                child_struct = {
                    "type": w_type,
                    "name": w_name,
                    "visible": child.winfo_ismapped(),
                    "children": []
                }
                parent_struct["children"].append(child_struct)
                _walk(child, child_struct)

        _walk(root_widget, structure)
        
        # Log summary
        summary = f"UI Profile: {features['buttons']} Buttons, {features['frames']} Frames, {features['entries']} Entries"
        self._add_traceback(summary, "DEBUG")
        
        # Save to file (Task 6)
        try:
            profile_dir = self.version_root / "profile" / "gui_profiles"
            profile_dir.mkdir(parents=True, exist_ok=True)
            profile_file = profile_dir / "grep_flight_ui.json"
            with open(profile_file, 'w') as f:
                json.dump({
                    "timestamp": datetime.now().isoformat(),
                    "summary": features,
                    "structure": structure
                }, f, indent=2)
        except Exception as e:
            self.engine.log_debug(f"UI Profile export failed: {e}", "WARNING")

        # Log to unified traceback
        log_to_traceback(EventCategory.DEBUG, "ui_profile", features, {"status": "profiled", "exported": True})
        
        return structure

    def _bind_mousewheel(self, widget, callback):
        """Bind mousewheel events to a widget for cross-platform scrolling"""
        # Linux uses Button-4 and Button-5
        widget.bind("<Button-4>", lambda e: callback("up"))
        widget.bind("<Button-5>", lambda e: callback("down"))
        # Windows/Mac use MouseWheel
        widget.bind("<MouseWheel>", lambda e: callback("up" if e.delta > 0 else "down"))

    def _cleanup_and_exit(self):
        """Cleanup IPC resources and exit"""
        try:
            # Close IPC file descriptor first
            if hasattr(self, 'ipc_fd') and self.ipc_fd is not None:
                try:
                    os.close(self.ipc_fd)
                    self.engine.log_debug(f"✓ Closed IPC fd: {self.ipc_fd}", "INFO")
                except:
                    pass

            # Remove IPC FIFO file
            if hasattr(self, 'ipc_file') and self.ipc_file and self.ipc_file.exists():
                self.ipc_file.unlink()
                self.engine.log_debug(f"✓ Cleaned up IPC file: {self.ipc_file}", "INFO")
        except Exception as e:
            self.engine.log_debug(f"IPC cleanup error: {e}", "WARNING")
        finally:
            self.quit()
        
        # Always on top
        self.attributes('-topmost', True)
        
        # Configure colors
        self.configure(bg=self.config.BG_COLOR)

        # Note: Escape is bound in _bind_events() with smart handler
        
    def _create_collapsed_panel(self):
        """Create the collapsed (minimal) panel - always stays at bottom"""
        self.collapsed_frame = tk.Frame(
            self,
            bg=self.config.BG_COLOR,
            height=self.config.PANEL_HEIGHT
        )
        self.collapsed_frame.pack(side=tk.BOTTOM, fill=tk.X, expand=False)
        self.collapsed_frame.pack_propagate(False)  # Maintain fixed height
        
        # Left side: Expand button and title
        left_frame = tk.Frame(self.collapsed_frame, bg=self.config.BG_COLOR)
        left_frame.pack(side=tk.LEFT, padx=5, pady=2)
        
        # Expand/collapse controls (Up/Down)
        expand_controls = tk.Frame(left_frame, bg=self.config.BG_COLOR)
        expand_controls.pack(side=tk.LEFT, padx=(0, 5))

        self.btn_up = tk.Button(
            expand_controls,
            text="▲",
            font=('Arial', 8, 'bold'),
            bg=self.config.BG_COLOR,
            fg=self.config.FG_COLOR,
            bd=0,
            relief=tk.FLAT,
            width=2,
            command=lambda: self._adjust_expansion(1)
        )
        self.btn_up.pack(side=tk.LEFT, padx=0)

        self.btn_down = tk.Button(
            expand_controls,
            text="▼",
            font=('Arial', 8, 'bold'),
            bg=self.config.BG_COLOR,
            fg='#555555',
            bd=0,
            relief=tk.FLAT,
            width=2,
            state='disabled',
            command=lambda: self._adjust_expansion(-1)
        )
        self.btn_down.pack(side=tk.LEFT, padx=0)
        
        # Title - display actual version from path
        version_name = self.version_root.name if hasattr(self, 'version_root') else "Unknown"
        gf_module_name = Path(__file__).parent.name  # e.g. "grep_flight_v0_2b"
        title_text = f"Grep Flight [{gf_module_name}] @ {version_name}"

        self.title_label = tk.Label(
            left_frame,
            text=title_text,
            font=('Arial', 10, 'bold'),
            bg=self.config.BG_COLOR,
            fg=self.config.ACCENT_COLOR
        )
        self.title_label.pack(side=tk.LEFT)
        
        # Center: Status and Indicators
        center_frame = tk.Frame(self.collapsed_frame, bg=self.config.BG_COLOR)
        center_frame.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=10)

        # Status label
        self.status_label = tk.Label(
            center_frame,
            textvariable=self.status_var,
            font=('Arial', 9),
            bg=self.config.BG_COLOR,
            fg=self.config.ACCENT_COLOR,
            anchor=tk.W
        )
        self.status_label.pack(side=tk.LEFT, padx=(0, 10))

        # Create indicator canvas
        self.indicator_canvas = tk.Canvas(
            center_frame,
            bg=self.config.BG_COLOR,
            height=self.config.PANEL_HEIGHT - 10,
            highlightthickness=0
        )
        self.indicator_canvas.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # Right side: Quick action buttons
        right_frame = tk.Frame(self.collapsed_frame, bg=self.config.BG_COLOR)
        right_frame.pack(side=tk.RIGHT, padx=5, pady=2)
        
        # Quick action buttons
        quick_actions = [
            ("📁", self._browse_target, "Set Target"),
            ("🔍", self._quick_search, "Quick Search"),
            ("🤖", self._show_ai_cli_menu, "AI CLI (Gemini/Claude)"),
            ("🏷️", self._show_pfl, "Show PFL"),
            ("🐛", self._debug_mode, "Debug Mode"),
            ("📊", self._show_traceback, "Show Traceback"),
            ("🗂", self._open_manage_versions, "Manage Versions"),
            ("👤", self._open_profiles_config, "Manage Profiles"),
            ("❓", self._show_help, "Help & Guidance"),
            ("⚙", self._show_settings, "Settings")
        ]
        
        for icon, command, tooltip in quick_actions:
            btn = tk.Button(
                right_frame,
                text=icon,
                font=('Arial', 12),
                bg=self.config.BG_COLOR,
                fg=self.config.FG_COLOR,
                bd=0,
                relief=tk.FLAT,
                width=2,
                command=command
            )
            btn.pack(side=tk.LEFT, padx=2)
            self._create_tooltip(btn, tooltip)

        # Exit button
        exit_btn = tk.Button(
            right_frame,
            text="✕",
            font=('Arial', 14, 'bold'),
            bg=self.config.BG_COLOR,
            fg='#ff5555',
            bd=0,
            relief=tk.FLAT,
            width=2,
            command=self.quit
        )
        exit_btn.pack(side=tk.LEFT, padx=(10, 0))
        self._create_tooltip(exit_btn, "Exit (Esc)")
            
    def _create_expanded_panel(self):
        """Create the expanded panel with TABS (hidden by default)"""
        self.expanded_frame = tk.Frame(
            self,
            bg=self.config.BG_COLOR
        )
        # Don't pack it yet - will be shown when expanded
        # self.expanded_frame will be packed above collapsed_frame when needed

        # Create Notebook (Tabs) for expanded panel
        self.notebook = ttk.Notebook(self.expanded_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.notebook.bind("<<NotebookTabChanged>>", self._on_tab_changed)

        # TAB 1: Grep (existing functionality)
        self._create_grep_tab()

        # TAB 2: Tasks (task list)
        self._create_tasks_tab()

        # TAB 3: Chat (5x5cm chat interface)
        self._create_chat_tab()

        # TAB 4: Inventory (provisions, stash, projects)
        self._create_inventory_tab()
        
        # TAB 5: Babel (Project Intelligence & Consolidated Tools)
        self._create_babel_tab()

    def _on_tab_changed(self, event):
        """Log tab changes and capture context"""
        selected_tab = self.notebook.select()
        tab_text = self.notebook.tab(selected_tab, "text")
        
        self.engine.log_debug(f"Tab Changed: {tab_text}", "INFO")
        self._add_traceback(f"📑 Tab Switched: {tab_text}", "DEBUG")
        
        # Capture context based on tab
        context = {
            "tab": tab_text,
            "target": self.target_var.get(),
            "pattern": self.pattern_var.get(),
            "timestamp": datetime.now().isoformat()
        }
        
        if tab_text == "🔍 Grep":
            self._add_traceback(f"   Context: Target='{context['target']}', Pattern='{context['pattern']}'", "DEBUG")
        elif tab_text == "💬 Chat":
            self._add_traceback(f"   Context: Provider='{self.chat_provider.get()}', Session='{self.chat_session_select.get()}'", "DEBUG")
        elif tab_text == "🏛️ Babel":
            self._add_traceback(f"   Context: Root='{self.babel_root}'", "DEBUG")

        # Profile UI on tab change to capture dynamic elements
        self.after(200, lambda: self._profile_ui_structure(self.notebook.nametowidget(selected_tab)))

    def _on_inventory_tab_changed(self, event):
        """Log inventory sub-tab changes"""
        selected_tab = self.inventory_notebook.select()
        tab_text = self.inventory_notebook.tab(selected_tab, "text")
        
        self.engine.log_debug(f"Inventory Tab Changed: {tab_text}", "INFO")
        self._add_traceback(f"📦 Inventory Sub-Tab: {tab_text}", "DEBUG")

    def _create_grep_tab(self):
        """Create the Grep tab with all grep functionality"""
        grep_tab = tk.Frame(self.notebook, bg=self.config.BG_COLOR)
        self.notebook.add(grep_tab, text="🔍 Grep")

        # Top section: Target and Pattern
        top_frame = tk.Frame(grep_tab, bg=self.config.BG_COLOR, pady=10)
        top_frame.pack(fill=tk.X, padx=10)
        
        # Target selection
        tk.Label(top_frame, text="Target:", bg=self.config.BG_COLOR,
                fg=self.config.FG_COLOR).pack(side=tk.LEFT, padx=(0, 5))

        self.target_entry = tk.Entry(
            top_frame,
            textvariable=self.target_var,
            width=40,
            bg='#2a2a2a',
            fg=self.config.FG_COLOR,
            insertbackground=self.config.FG_COLOR
        )
        self.target_entry.pack(side=tk.LEFT, padx=(0, 5))

        # Keyboard bindings for target entry
        # TODO: Formalize UX & Keyboard hooks - auto-target system needs better integration
        self.target_entry.bind('<Return>', lambda e: self._execute_grep())
        self.target_entry.bind('<Escape>', lambda e: self.target_var.set(''))  # Note: May not work with auto-target
        self.target_entry.bind('<Control-l>', lambda e: self.target_entry.select_range(0, tk.END))

        tk.Button(top_frame, text="Browse", command=self._browse_target,
                 bg=self.config.HOVER_COLOR, fg=self.config.FG_COLOR).pack(side=tk.LEFT, padx=(0, 5))

        # Recent targets dropdown
        tk.Button(top_frame, text="📜", command=self._show_recent_targets,
                 bg=self.config.HOVER_COLOR, fg=self.config.FG_COLOR,
                 width=2).pack(side=tk.LEFT, padx=(0, 10))
        self._create_tooltip_simple(top_frame.winfo_children()[-1], "Recent Targets")

        # Babel Profile Button (New)
        tk.Button(top_frame, text="🏛️ Profile", command=self._launch_profile_viewer,
                 bg='#2d7d46', fg='white', padx=8).pack(side=tk.LEFT, padx=(0, 10))
        self._create_tooltip_simple(top_frame.winfo_children()[-1], "View Babel Profile for Target")
        
        # Pattern input
        tk.Label(top_frame, text="Pattern:", bg=self.config.BG_COLOR,
                fg=self.config.FG_COLOR).pack(side=tk.LEFT, padx=(0, 5))

        self.pattern_entry = tk.Entry(
            top_frame,
            textvariable=self.pattern_var,
            width=30,
            bg='#2a2a2a',
            fg=self.config.FG_COLOR,
            insertbackground=self.config.FG_COLOR
        )
        self.pattern_entry.pack(side=tk.LEFT, padx=(0, 5))

        # Keyboard bindings for pattern entry
        self.pattern_entry.bind('<Return>', lambda e: self._execute_grep())
        self.pattern_entry.bind('<Escape>', lambda e: self.pattern_var.set(''))
        self.pattern_entry.bind('<Control-l>', lambda e: self.pattern_entry.select_range(0, tk.END))

        # Copy Target Button (New)
        tk.Button(top_frame, text="📋", command=self._copy_target_path,
                 bg=self.config.HOVER_COLOR, fg=self.config.FG_COLOR,
                 width=2).pack(side=tk.LEFT, padx=(0, 5))
        self._create_tooltip_simple(top_frame.winfo_children()[-1], "Copy Target Path")

        # Recent patterns dropdown
        tk.Button(top_frame, text="📜", command=self._show_recent_patterns,
                 bg=self.config.HOVER_COLOR, fg=self.config.FG_COLOR,
                 width=2).pack(side=tk.LEFT, padx=(0, 5))
        self._create_tooltip_simple(top_frame.winfo_children()[-1], "Recent Patterns")

        # Quick pattern presets
        tk.Button(top_frame, text="⚡", command=self._show_pattern_presets,
                 bg=self.config.HOVER_COLOR, fg=self.config.FG_COLOR,
                 width=2).pack(side=tk.LEFT, padx=(0, 5))
        self._create_tooltip_simple(top_frame.winfo_children()[-1], "Pattern Presets")

        # Middle section: Grep tools
        tools_frame = tk.Frame(grep_tab, bg=self.config.BG_COLOR, pady=10)
        tools_frame.pack(fill=tk.X, padx=10)

        tk.Label(tools_frame, text="Grep Tools:", bg=self.config.BG_COLOR,
                fg=self.config.FG_COLOR).pack(side=tk.LEFT, padx=(0, 10))

        # Grep tool buttons
        grep_tools = [
            ("G1: Pattern", "grep -rn {pattern} {target}", "Recursive pattern search"),
            ("G2: Exact", "grep -rnw {pattern} {target}", "Exact word match"),
            ("G3: Case Ins", "grep -rni {pattern} {target}", "Case insensitive"),
            ("G4: PFL Tags", "grep -rn '#\\[PFL:' {target}", "Find PFL tags"),
            ("G5: Os_Toolkit", "python3 {babel_root}/Os_Toolkit.py {pattern}", "Query file with Os_Toolkit")
        ]

        for label, template, tooltip in grep_tools:
            btn = tk.Button(
                tools_frame,
                text=label,
                command=lambda t=template: self._execute_template(t),
                bg=self.config.HOVER_COLOR,
                fg=self.config.FG_COLOR,
                relief=tk.RAISED,
                bd=1
            )
            btn.pack(side=tk.LEFT, padx=2)
            self._create_tooltip(btn, tooltip)

        # Backup button (moved here from controls_row)
        backup_btn = tk.Button(
            tools_frame,
            text="📦 Backup",
            command=self._backup_current_target,
            bg='#d67e00',
            fg='white',
            relief=tk.RAISED,
            bd=1,
            width=10
        )
        backup_btn.pack(side=tk.LEFT, padx=2)
        self._create_tooltip_simple(backup_btn, "Backup current target file")

        # Restore button with dropdown
        restore_frame = tk.Frame(tools_frame, bg=self.config.BG_COLOR)
        restore_frame.pack(side=tk.LEFT, padx=2)

        restore_btn = tk.Button(
            restore_frame,
            text="🔄 Restore",
            command=self._show_restore_menu,
            bg='#00a86b',
            fg='white',
            relief=tk.RAISED,
            bd=1,
            width=10
        )
        restore_btn.pack()
        self._create_tooltip_simple(restore_btn, "Restore from backup")

        # Workflow buttons (dynamic from profile config - up to 8 slots)
        self.workflow_frame = tk.Frame(grep_tab, bg=self.config.BG_COLOR, pady=10)
        self.workflow_frame.pack(fill=tk.X, padx=10)

        # Build workflow buttons (extracted to method for dynamic refresh)
        self._build_workflow_buttons()

        # Bottom section: Results preview
        results_frame = tk.Frame(grep_tab, bg=self.config.BG_COLOR)
        results_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        tk.Label(results_frame, text="Results:", bg=self.config.BG_COLOR,
                fg=self.config.FG_COLOR).pack(anchor=tk.W)

        # Results text
        self.results_text = scrolledtext.ScrolledText(
            results_frame,
            height=8,
            bg='#2a2a2a',
            fg=self.config.FG_COLOR,
            insertbackground=self.config.FG_COLOR,
            font=('Monospace', 9),
            cursor='hand2'
        )
        self.results_text.pack(fill=tk.BOTH, expand=True)

        # Configure tags for clickable results
        self.results_text.tag_config('clickable', foreground=self.config.ACCENT_COLOR, underline=True)
        self.results_text.tag_bind('clickable', '<Button-1>', self._on_result_click)
        self.results_text.tag_bind('clickable', '<Enter>', lambda e: self.results_text.config(cursor='hand2'))
        self.results_text.tag_bind('clickable', '<Leave>', lambda e: self.results_text.config(cursor=''))
        self.results_text.bind('<Button-3>', self._on_result_right_click)

        # Action buttons at bottom of grep tab
        action_frame = tk.Frame(grep_tab, bg=self.config.BG_COLOR)
        action_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

        actions = [
            ("✏️ Edit", self._open_editor),
            ("💻 Terminal", self._open_terminal),
            ("🚀 Context", self._push_context_to_ai),
            ("👤 Profile", self._launch_profile_viewer),
            ("🏛️ Babel", self._show_babel_actions),
            ("📁 Browser", self._open_file_browser),
            ("➕ PFL", self._add_pfl_tag),
            ("💾 Export", self._export_results),
            ("🧹 Clear", self._clear_results),
            ("📋 Copy", self._copy_results)
        ]

        for text, command in actions:
            tk.Button(action_frame, text=text, command=command,
                     bg=self.config.HOVER_COLOR, fg=self.config.FG_COLOR).pack(side=tk.LEFT, padx=2)

    def _launch_profile_viewer(self):
        """Launch Os_Toolkit profile viewer for the current target"""
        target = self.target_var.get()
        if not target:
            messagebox.showwarning("Target", "Please set a target file/directory first.")
            return
            
        os_toolkit = self.babel_root / "Os_Toolkit.py"
        
        try:
            # Launch Os_Toolkit file command in a new terminal/zenity window via target.sh logic
            # Or directly invoke Os_Toolkit with -z
            
            # Use zenity output for better visibility
            # Command: python3 Os_Toolkit.py file <target> --depth 2 | zenity --text-info ...
            
            cmd_str = f"python3 '{os_toolkit}' file '{target}' --depth 2 2>&1 | zenity --text-info --title='Babel Profile: {Path(target).name}' --width=900 --height=700 --font='Monospace 10'"
            
            subprocess.Popen(cmd_str, shell=True)
            self.status_var.set(f"👤 Launching Profile: {Path(target).name}")
            
            log_to_traceback(EventCategory.PROFILE, "launch_viewer", {"target": target}, {"status": "launched"})
            
        except Exception as e:
            self._add_traceback(f"Error launching profile viewer: {e}", "ERROR")

    def _show_babel_actions(self):
        """Show Babel Suggested Actions menu"""
        menu = tk.Menu(self, tearoff=0, bg='#2a2a2a', fg=self.config.FG_COLOR)
        menu.add_command(label="Sync Marks to Todos", command=lambda: self._run_babel_action('sync_marks'))
        menu.add_command(label="Run Conformity Check", command=lambda: self._run_babel_action('run_all_actions'))
        menu.add_command(label="Profile Current File", command=self._launch_profile_viewer)
        menu.add_command(label="Export Session", command=lambda: self._run_babel_action('export'))
        menu.add_separator()
        menu.add_command(label="Sync Tool Catalog", command=self._run_babel_action('catalog'))
        
        # Position near mouse
        x = self.winfo_pointerx()
        y = self.winfo_pointery()
        menu.post(x, y)

    def _run_babel_action(self, action_name: str):
        """Execute Os_Toolkit action from grep_flight with visual feedback"""
        target = self.target_var.get()
        os_toolkit = self.babel_root / "Os_Toolkit.py"
        
        base_cmd = f"python3 '{os_toolkit}' actions"
        title = f"Babel Action: {action_name}"
        
        if action_name == 'sync_marks':
            cmd_str = f"{base_cmd} --run sync_marks 2>&1 | zenity --text-info --title='{title}' --width=800 --height=600"
        elif action_name == 'run_all_actions':
            cmd_str = f"{base_cmd} --run-all 2>&1 | zenity --text-info --title='{title}' --width=800 --height=600"
        elif action_name == 'export':
            cmd_str = f"python3 '{os_toolkit}' export -z" # Export has built-in zenity support
        elif action_name == 'catalog':
            cmd_str = f"{base_cmd} --run catalog 2>&1 | zenity --text-info --title='{title}' --width=800 --height=600"
        else:
            return

        try:
            log_to_traceback(EventCategory.DEBUG, f"action_{action_name}", 
                           {"target": target}, {"launched": True})
            subprocess.Popen(cmd_str, shell=True)
            self.status_var.set(f"Running Babel action: {action_name}")
        except Exception as e:
            self._add_traceback(f"Error running action {action_name}: {e}", "ERROR")

    def _build_workflow_buttons(self):
        """Create or refresh the workflow action buttons"""
        if not hasattr(self, 'workflow_frame'):
            return

        for child in self.workflow_frame.winfo_children():
            child.destroy()

        actions = [a for a in (self.workflow_actions or []) if a.get('type') != 'placeholder']
        max_slots = 8

        container = tk.Frame(self.workflow_frame, bg=self.config.BG_COLOR)
        container.pack(fill=tk.X)

        buttons_row = tk.Frame(container, bg=self.config.BG_COLOR)
        buttons_row.pack(side=tk.LEFT, fill=tk.X, expand=True)

        controls_row = tk.Frame(container, bg=self.config.BG_COLOR)
        controls_row.pack(side=tk.RIGHT)

        config_btn = tk.Button(
            controls_row,
            text="⚙️",
            command=self._open_workflow_config_direct,
            bg=self.config.HOVER_COLOR,
            fg=self.config.FG_COLOR,
            width=3,
            relief=tk.RAISED,
            bd=1
        )
        config_btn.pack(side=tk.RIGHT, padx=(4, 0))
        self._create_tooltip_simple(config_btn, "Action-Panel Configuration")

        add_btn = tk.Button(
            controls_row,
            text="[ + ] Add / Swap",
            command=self._quick_add_workflow_tool,
            bg='#1f1f1f',
            fg=self.config.ACCENT_COLOR,
            relief=tk.RAISED,
            bd=1,
            width=14,
            height=1
        )
        add_btn.pack(side=tk.RIGHT, padx=(4, 0))
        self._create_tooltip_simple(add_btn, "Add or swap workflow buttons")

        scope_btn = tk.Button(
            controls_row,
            text="🔭 Scope",
            command=self._launch_scope_analyzer,
            bg='#1f1f1f',
            fg=self.config.FG_COLOR,
            relief=tk.RAISED,
            bd=1,
            width=10,
            height=1
        )
        scope_btn.pack(side=tk.RIGHT, padx=(4, 0))
        self._create_tooltip_simple(scope_btn, "Launch Scope Analyzer")

        indicator_value = self.active_profile or "Default Profile"
        if not hasattr(self, 'profile_indicator_var'):
            self.profile_indicator_var = tk.StringVar(value=indicator_value)
        else:
            self.profile_indicator_var.set(indicator_value)

        profile_frame = tk.Frame(controls_row, bg=self.config.BG_COLOR)
        profile_frame.pack(side=tk.RIGHT, padx=(4, 0))

        prev_btn = tk.Button(
            profile_frame,
            text='◀',
            command=lambda: self._cycle_workflow_profile(-1),
            bg='#202020',
            fg=self.config.FG_COLOR,
            width=2
        )
        prev_btn.pack(side=tk.LEFT, padx=(0, 2))

        profile_label = tk.Label(
            profile_frame,
            textvariable=self.profile_indicator_var,
            bg=self.config.BG_COLOR,
            fg=self.config.FG_COLOR,
            width=16,
            anchor='center'
        )
        profile_label.pack(side=tk.LEFT)

        next_btn = tk.Button(
            profile_frame,
            text='▶',
            command=lambda: self._cycle_workflow_profile(1),
            bg='#202020',
            fg=self.config.FG_COLOR,
            width=2
        )
        next_btn.pack(side=tk.LEFT, padx=(2, 0))
        self._create_tooltip_simple(profile_frame, "Cycle workflow profiles")

        if not actions:
            tk.Label(
                buttons_row,
                text="No workflow actions configured.",
                bg=self.config.BG_COLOR,
                fg=self.config.FG_COLOR
            ).pack(side=tk.LEFT, padx=5)
            return

        for idx, action in enumerate(actions[:max_slots]):
            button_text = action.get('name', f"Workflow {idx + 1}")
            btn = tk.Button(
                buttons_row,
                text=button_text,
                command=lambda act=action: self._execute_workflow_action(act),
                bg='#2c2c2c',
                fg=self.config.FG_COLOR,
                relief=tk.RAISED,
                bd=1,
                width=14,
                height=1,
                wraplength=130,
                justify=tk.CENTER
            )
            btn.pack(side=tk.LEFT, padx=2)
            btn.bind("<Button-3>", lambda e, act=action, i=idx: self._show_workflow_action_context_menu(e, act, i, refresh_workflow_list))

            tooltip_lines = [
                f"Target: {action.get('target_mode', 'auto')}",
                f"Output: {action.get('output_to', 'results')}"
            ]
            expectations = action.get('expectations')
            if expectations:
                tooltip_lines.append(f"Expect: {expectations}")
            self._create_tooltip(btn, "\n".join(tooltip_lines))

    def _prompt_workflow_configuration(self, slot_idx: int):
        """Guide users to configure empty workflow slots"""
        self.status_var.set(f"➕ Configure workflow slot {slot_idx + 1} via ⚙️ Action-Panel Configuration or use [ + ] Add Custom")
        messagebox.showinfo(
            "Configure Workflow Slot",
            "This slot is empty. Click the [ + ] Add Custom button or open the ⚙️ configuration to assign a workflow action."
        )

    def _open_workflow_config_direct(self):
        """Open workflow configuration without surfacing the legacy toolkit strip"""
        self._show_toolkit_config(parent=self)

    def _create_tasks_tab(self):
        """Create the Tasks tab with dual-pane layout"""
        tasks_tab = tk.Frame(self.notebook, bg=self.config.BG_COLOR)
        self.notebook.add(tasks_tab, text="📋 Tasks")

        # Root PanedWindow
        self.tasks_paned = tk.PanedWindow(tasks_tab, orient=tk.HORIZONTAL, bg=self.config.BG_COLOR, sashwidth=4, sashrelief=tk.RAISED)
        self.tasks_paned.pack(fill=tk.BOTH, expand=True)

        # --- LEFT PANE: Navigation & Lists ---
        left_frame = tk.Frame(self.tasks_paned, bg=self.config.BG_COLOR)
        self.tasks_paned.add(left_frame, minsize=300)

        # Scrollable container for Left Pane
        left_canvas = tk.Canvas(left_frame, bg=self.config.BG_COLOR, highlightthickness=0)
        left_scrollbar = ttk.Scrollbar(left_frame, orient="vertical", command=left_canvas.yview)
        left_content = tk.Frame(left_canvas, bg=self.config.BG_COLOR)

        left_content.bind(
            "<Configure>",
            lambda e: left_canvas.configure(scrollregion=left_canvas.bbox("all"))
        )

        left_canvas.create_window((0, 0), window=left_content, anchor="nw")
        left_canvas.configure(yscrollcommand=left_scrollbar.set)

        left_canvas.pack(side="left", fill="both", expand=True)
        left_scrollbar.pack(side="right", fill="y")

        # Bind mousewheel to Left Pane
        self._bind_mousewheel(left_canvas, lambda dir: left_canvas.yview_scroll(-1 if dir == "up" else 1, "units"))
        self._bind_mousewheel(left_content, lambda dir: left_canvas.yview_scroll(-1 if dir == "up" else 1, "units"))

        # --> Move existing controls to left_content
        
        # Task list header
        task_header = tk.Frame(left_content, bg=self.config.BG_COLOR, pady=10)
        task_header.pack(fill=tk.X, padx=5)

        tk.Label(task_header, text="Active Tasks", bg=self.config.BG_COLOR,
                fg=self.config.FG_COLOR, font=('Arial', 12, 'bold')).pack(side=tk.LEFT)

        self.current_project = tk.StringVar(value="Error Handling & Logging")
        project_indicator = tk.Label(task_header, textvariable=self.current_project,
                                     bg='#2d4d3d', fg=self.config.ACCENT_COLOR,
                                     font=('Arial', 9), padx=8, pady=2, relief=tk.SOLID, bd=1)
        project_indicator.pack(side=tk.LEFT, padx=(10, 5))

        tk.Button(task_header, text="[Set Project]", command=self._set_project,
                 bg=self.config.BG_COLOR, fg=self.config.ACCENT_COLOR,
                 font=('Arial', 9)).pack(side=tk.LEFT, padx=(0, 5))

        tk.Button(task_header, text="🔄", command=self._refresh_task_list,
                 bg=self.config.BG_COLOR, fg=self.config.FG_COLOR,
                 bd=0, relief=tk.FLAT, width=2, font=('Arial', 12)).pack(side=tk.RIGHT)
        self._create_tooltip(task_header.winfo_children()[-1], "Refresh task list")

        tk.Button(task_header, text="[Sync Todos]", command=self._sync_todos,
                 bg='#2d4d3d', fg=self.config.ACCENT_COLOR,
                 font=('Arial', 9)).pack(side=tk.RIGHT, padx=(0, 5))
        self._create_tooltip(task_header.winfo_children()[-1], "Sync todos from all sources")

        # --- PLAN MODULES CONTROL PANEL ---
        plan_module_frame = tk.Frame(left_content, bg='#252525', pady=5)
        plan_module_frame.pack(fill=tk.X, padx=5, pady=(0, 10))

        # Module Selection
        tk.Label(plan_module_frame, text="Active Plan Module:", bg='#252525',
                fg=self.config.ACCENT_COLOR, font=('Arial', 9, 'bold')).pack(side=tk.LEFT, padx=5)

        # Build module list with availability markers
        plan_modules = []
        plan_modules.append("Os_Toolkit / Babel")
        ag_clip = self.babel_root / "babel_data" / "inventory" / "action_panel" / "ag_forge" / "clip.py"
        plan_modules.append("Ag Forge / Clip" if ag_clip.exists() else "Ag Forge / Clip [N/A]")
        morph_path = self.babel_root / "babel_data" / "inventory" / "action_panel" / "morph" / "guillm.py"
        plan_modules.append("Morph / Guillm" if morph_path.exists() else "Morph / Guillm [N/A]")

        # Set default module to "Os_Toolkit / Babel"
        self.active_plan_module.set("Os_Toolkit / Babel")

        module_menu = ttk.Combobox(plan_module_frame, textvariable=self.active_plan_module,
                                  values=plan_modules,
                                  width=22, state='readonly')
        module_menu.pack(side=tk.LEFT, padx=5)
        module_menu.bind('<<ComboboxSelected>>', self._on_plan_module_changed)

        tk.Label(plan_module_frame, text="CMD:", bg='#252525',
                fg='#888888', font=('Arial', 8)).pack(side=tk.LEFT, padx=(10, 2))
        
        cmd_entry = tk.Entry(plan_module_frame, textvariable=self.invocation_preview,
                            bg='#1a1a1a', fg='#4ec9b0', font=('Monospace', 8),
                            relief=tk.FLAT, width=40) # Slightly reduced width
        cmd_entry.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        cmd_entry.config(state='readonly')

        # Navigation Notebook (Filters, Plans)
        nav_notebook = ttk.Notebook(left_content)
        nav_notebook.pack(fill=tk.X, padx=5, pady=(0, 10))

        # Tab 1: Filters
        filter_tab = tk.Frame(nav_notebook, bg=self.config.BG_COLOR)
        nav_notebook.add(filter_tab, text="📊 Filters")

        taxonomy_grid = tk.Frame(filter_tab, bg=self.config.BG_COLOR, pady=5)
        taxonomy_grid.pack(fill=tk.X, padx=5)
        cols = 3 # Reduced columns for narrower pane
        for i, cat in enumerate(self.system_categories):
            r, c = divmod(i, cols)
            cb = tk.Checkbutton(taxonomy_grid, text=cat, variable=self.taxonomy_vars[cat],
                               bg=self.config.BG_COLOR, fg='#d4d4d4',
                               selectcolor='#2a2a2a', font=('Arial', 8),
                               command=self._filter_tasks)
            cb.grid(row=r, column=c, sticky=tk.W, padx=2)

        filter_frame = tk.Frame(filter_tab, bg=self.config.BG_COLOR, pady=5)
        filter_frame.pack(fill=tk.X, padx=5)
        
        tk.Label(filter_frame, text="Type:", bg=self.config.BG_COLOR, fg=self.config.FG_COLOR).pack(side=tk.LEFT)
        self.task_type_filter = tk.StringVar(value="all")
        ttk.Combobox(filter_frame, textvariable=self.task_type_filter, values=["all", "research", "plan", "implement"], width=10, state='readonly').pack(side=tk.LEFT, padx=5)
        
        tk.Label(filter_frame, text="Status:", bg=self.config.BG_COLOR, fg=self.config.FG_COLOR).pack(side=tk.LEFT)
        self.task_status_filter = tk.StringVar(value="all")
        ttk.Combobox(filter_frame, textvariable=self.task_status_filter, values=["all", "pending", "in_progress", "completed"], width=10, state='readonly').pack(side=tk.LEFT, padx=5)

        # Tab 2: Plan Suite
        plan_tab = tk.Frame(nav_notebook, bg=self.config.BG_COLOR)
        nav_notebook.add(plan_tab, text="📝 Plan Suite")

        self.plans_dir = self.babel_root / "plans"

        plan_info_frame = tk.Frame(plan_tab, bg='#252525', pady=5)
        plan_info_frame.pack(fill=tk.X, padx=5, pady=5)
        tk.Label(plan_info_frame, text="Plans Dir:", bg='#252525', fg=self.config.ACCENT_COLOR, font=('Arial', 8, 'bold')).pack(side=tk.LEFT)
        tk.Label(plan_info_frame, text=str(self.plans_dir.name), bg='#252525', fg='#888888', font=('Arial', 8)).pack(side=tk.LEFT, padx=5)
        tk.Button(plan_info_frame, text="📂", command=self._open_plans_in_editor, bg='#2d4d3d', fg='white', width=2).pack(side=tk.RIGHT, padx=2)
        tk.Button(plan_info_frame, text="📋", command=self._show_todo_selector, bg='#3a7ca5', fg='white', width=2).pack(side=tk.RIGHT, padx=2) # Shortened labels

        self.plan_listbox = tk.Listbox(plan_tab, bg='#2a2a2a', fg=self.config.FG_COLOR, height=6)
        self.plan_listbox.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.plan_listbox.bind('<Double-1>', lambda e: self._open_selected_plan())
        self._refresh_plan_list()

        # Task List
        task_list_container = tk.Frame(left_content, bg='#2a2a2a')
        task_list_container.pack(fill=tk.BOTH, expand=True, padx=5, pady=(0, 10))
        
        self.task_listbox = tk.Listbox(task_list_container, bg='#2a2a2a', fg=self.config.FG_COLOR, selectbackground=self.config.ACCENT_COLOR, font=('Monospace', 10), height=15)
        self.task_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        task_scrollbar = tk.Scrollbar(task_list_container, command=self.task_listbox.yview)
        task_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.task_listbox.config(yscrollcommand=task_scrollbar.set)
        
        self.task_listbox.bind('<Double-Button-1>', self._on_task_double_click)
        self.task_listbox.bind('<Button-3>', self._on_task_right_click)

        # Task Actions
        task_actions = tk.Frame(left_content, bg=self.config.BG_COLOR)
        task_actions.pack(fill=tk.X, padx=5, pady=(0, 10))
        
        tk.Button(task_actions, text="App Tasks", command=self._open_tasks_tab, bg=self.config.ACCENT_COLOR, fg='black').pack(side=tk.LEFT, padx=2)
        tk.Button(task_actions, text="Planner", command=self._open_planner_tab, bg='#613d8c', fg='white').pack(side=tk.LEFT, padx=2)


        # --- RIGHT PANE: Workspace (Editor, Context, Timeline) ---
        right_frame = tk.Frame(self.tasks_paned, bg=self.config.BG_COLOR)
        self.tasks_paned.add(right_frame, minsize=400)

        # Workspace Header
        self.workspace_header_var = tk.StringVar(value="Select a task to view details")
        ws_header = tk.Label(right_frame, textvariable=self.workspace_header_var, 
                            bg='#333333', fg='white', font=('Arial', 10, 'bold'), pady=5)
        ws_header.pack(fill=tk.X)

        # Workspace Notebook
        self.workspace_notebook = ttk.Notebook(right_frame)
        self.workspace_notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Tab 1: Project Doc (Editable)
        project_doc_tab = tk.Frame(self.workspace_notebook, bg=self.config.BG_COLOR)
        self.workspace_notebook.add(project_doc_tab, text="📂 Project Doc")
        
        self.project_text = scrolledtext.ScrolledText(project_doc_tab, bg='#1e1e1e', fg='#4ec9b0', font=('Monospace', 10), insertbackground='white')
        self.project_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self._bind_mousewheel(self.project_text, lambda dir: self.project_text.yview_scroll(-1 if dir == "up" else 1, "units"))

        proj_doc_controls = tk.Frame(project_doc_tab, bg=self.config.BG_COLOR)
        proj_doc_controls.pack(fill=tk.X, padx=5, pady=5)
        tk.Button(proj_doc_controls, text="💾 Save Project Doc", command=self._save_project_doc, bg='#2d7d46', fg='white').pack(side=tk.RIGHT)

        # Tab 2: Editor (Editable Description)
        editor_tab = tk.Frame(self.workspace_notebook, bg=self.config.BG_COLOR)
        self.workspace_notebook.add(editor_tab, text="✏️ Editor")

        # Internal PanedWindow for Editor
        self.editor_paned = tk.PanedWindow(editor_tab, orient=tk.HORIZONTAL, bg=self.config.BG_COLOR, sashwidth=2)
        self.editor_paned.pack(fill=tk.BOTH, expand=True)

        # -- Left: Attribute Tree --
        attr_frame = tk.Frame(self.editor_paned, bg=self.config.BG_COLOR)
        self.editor_paned.add(attr_frame, minsize=250)
        tk.Label(attr_frame, text="Attributes & Routing", bg=self.config.BG_COLOR, fg=self.config.ACCENT_COLOR, font=('Arial', 9, 'bold')).pack(anchor=tk.W, padx=5)
        
        self.attr_tree = ttk.Treeview(attr_frame, columns=("Value"), show="tree headings")
        self.attr_tree.heading("#0", text="Property")
        self.attr_tree.heading("Value", text="Value")
        self.attr_tree.column("#0", width=120)
        self.attr_tree.column("Value", width=150)
        self.attr_tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.attr_tree.tag_configure('error', foreground='#ff5555')
        self.attr_tree.bind('<ButtonRelease-1>', self._on_attr_select)
        self.attr_tree.bind('<Button-3>', self._on_attr_right_click)
        
        # -- Center: Text Editor --
        text_frame = tk.Frame(self.editor_paned, bg=self.config.BG_COLOR)
        self.editor_paned.add(text_frame, minsize=350)
        
        # Strategic Routing Frame
        routing_frame = tk.Frame(text_frame, bg='#252525', pady=5)
        routing_frame.pack(fill=tk.X, padx=5, pady=5)
        
        tk.Label(routing_frame, text="Strategic Routing & Diffs", bg='#252525', fg=self.config.ACCENT_COLOR, font=('Arial', 9, 'bold')).pack(side=tk.LEFT, padx=5)
        
        self.btn_add_mark = tk.Button(routing_frame, text="+ Mark/Diff", command=self._add_diff_item, bg='#3c3c3c', fg='white', font=('Arial', 8))
        self.btn_add_mark.pack(side=tk.RIGHT, padx=2)
        
        self.btn_add_link = tk.Button(routing_frame, text="+ Meta Link", command=self._add_meta_link_item, bg='#3c3c3c', fg='white', font=('Arial', 8))
        self.btn_add_link.pack(side=tk.RIGHT, padx=2)

        tk.Label(text_frame, text="Task Body / Marks", bg=self.config.BG_COLOR, fg=self.config.ACCENT_COLOR, font=('Arial', 9, 'bold')).pack(anchor=tk.W, padx=5)
        
        self.editor_text = scrolledtext.ScrolledText(text_frame, bg='#1e1e1e', fg='#e0e0e0', font=('Monospace', 10), insertbackground='white')
        self.editor_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self._bind_mousewheel(self.editor_text, lambda dir: self.editor_text.yview_scroll(-1 if dir == "up" else 1, "units"))

        # -- Right: Inspector --
        self.inspector_frame = tk.LabelFrame(self.editor_paned, text="Property Inspector", bg='#252525', fg='#888888')
        self.editor_paned.add(self.inspector_frame, minsize=150)
        self.inspector_msg = tk.Text(self.inspector_frame, bg='#252525', fg='#d4d4d4', font=('Arial', 8), bd=0, wrap=tk.WORD)
        self.inspector_msg.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        editor_controls = tk.Frame(editor_tab, bg=self.config.BG_COLOR)
        editor_controls.pack(fill=tk.X, padx=5, pady=5)
        tk.Button(editor_controls, text="💾 Save Changes", command=self._save_task_edits, bg='#2d7d46', fg='white').pack(side=tk.RIGHT)

        # Tab 3: JSON (Raw Data)
        json_tab = tk.Frame(self.workspace_notebook, bg=self.config.BG_COLOR)
        self.workspace_notebook.add(json_tab, text="{ } JSON")
        
        self.json_text = scrolledtext.ScrolledText(json_tab, bg='#1e1e1e', fg='#ce9178', font=('Monospace', 10))
        self.json_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self._bind_mousewheel(self.json_text, lambda dir: self.json_text.yview_scroll(-1 if dir == "up" else 1, "units"))

        # Tab 4: Timeline (Historic Plans)
        timeline_tab = tk.Frame(self.workspace_notebook, bg=self.config.BG_COLOR)
        self.workspace_notebook.add(timeline_tab, text="📅 Timeline")
        
        # Timeline Treeview
        timeline_cols = ("Date", "Type", "Snapshot")
        self.timeline_tree = ttk.Treeview(timeline_tab, columns=timeline_cols, show="headings")
        self.timeline_tree.heading("Date", text="Date")
        self.timeline_tree.heading("Type", text="Type")
        self.timeline_tree.heading("Snapshot", text="Snapshot ID")
        self.timeline_tree.column("Date", width=120)
        self.timeline_tree.column("Type", width=100)
        self.timeline_tree.column("Snapshot", width=150)
        
        tl_scroll = ttk.Scrollbar(timeline_tab, orient="vertical", command=self.timeline_tree.yview)
        self.timeline_tree.configure(yscrollcommand=tl_scroll.set)
        
        self.timeline_tree.pack(side="left", fill="both", expand=True)
        tl_scroll.pack(side="right", fill="y")
        
        # Load timeline data
        self._refresh_timeline()

        # Tab 5: Projects (New - Management & Templates)
        projects_tab = tk.Frame(self.workspace_notebook, bg=self.config.BG_COLOR)
        self.workspace_notebook.add(projects_tab, text="🏗️ Projects")

        # Top: Controls
        proj_ctrl_frame = tk.Frame(projects_tab, bg=self.config.BG_COLOR, pady=5)
        proj_ctrl_frame.pack(fill=tk.X, padx=5)
        
        tk.Button(proj_ctrl_frame, text="✨ New Project", command=self._show_new_project_dialog, 
                 bg='#2d7d46', fg='white').pack(side=tk.LEFT, padx=2)
        tk.Button(proj_ctrl_frame, text="📂 Open Project Doc", command=self._open_active_project_doc,
                 bg='#3a7ca5', fg='white').pack(side=tk.LEFT, padx=2)
        tk.Button(proj_ctrl_frame, text="↻ Refresh Clusters", command=self._update_project_context,
                 bg='#444444', fg='white').pack(side=tk.LEFT, padx=2)

        # Middle: Split view for Clusters
        proj_paned = tk.PanedWindow(projects_tab, orient=tk.HORIZONTAL, bg=self.config.BG_COLOR, sashwidth=2)
        proj_paned.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Left: Cluster List
        cluster_list_frame = tk.Frame(proj_paned, bg=self.config.BG_COLOR)
        proj_paned.add(cluster_list_frame, minsize=200)
        tk.Label(cluster_list_frame, text="Inferred Clusters", bg=self.config.BG_COLOR, fg=self.config.ACCENT_COLOR, font=('Arial', 8, 'bold')).pack(anchor=tk.W)
        
        self.cluster_listbox = tk.Listbox(cluster_list_frame, bg='#2a2a2a', fg='#d4d4d4', font=('Arial', 9))
        self.cluster_listbox.pack(fill=tk.BOTH, expand=True, pady=2)
        self.cluster_listbox.bind('<<ListboxSelect>>', self._on_cluster_select)

        # Right: Inference Detail
        proj_info_frame = tk.LabelFrame(proj_paned, text="Cluster Attributes & Evidence", bg=self.config.BG_COLOR, fg=self.config.FG_COLOR)
        proj_paned.add(proj_info_frame, minsize=300)
        
        self.proj_inference_text = scrolledtext.ScrolledText(proj_info_frame, bg='#2a2a2a', fg='#4ec9b0', font=('Monospace', 9))
        self.proj_inference_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Load initial data
        self.after(1000, self._update_project_context)

        tk.Button(task_actions, text="List Plans", command=self._show_planner_files,
                 bg='#3c3c3c', fg='#cccccc',
                 font=('Arial', 10), padx=10).pack(side=tk.LEFT, padx=5)

        tk.Button(task_actions, text="Details", command=self._show_task_details,
                 bg=self.config.HOVER_COLOR, fg=self.config.FG_COLOR,
                 font=('Arial', 10), padx=10).pack(side=tk.LEFT, padx=5)

        tk.Button(task_actions, text="📦 Backup", command=self._backup_current_target,
                 bg='#d67e00', fg='white',
                 font=('Arial', 10), padx=10).pack(side=tk.LEFT, padx=5)

        tk.Button(task_actions, text="🔄 Restore", command=self._show_restore_menu,
                 bg='#00a86b', fg='white',
                 font=('Arial', 10), padx=10).pack(side=tk.LEFT, padx=5)

        # Store tasks data
        self.tasks_data = []

        # Load initial tasks
        self._refresh_task_list()

        # Start background watcher
        self._start_task_watcher()

    def _save_task_edits(self):
        """Save changes from the task editor to todos.json"""
        if not hasattr(self, 'task_listbox'): return
        
        selection = self.task_listbox.curselection()
        if not selection:
            self.status_var.set("⚠️ Select a task first")
            return

        index = selection[0]
        if index >= len(self.tasks_data): return
        
        task = self.tasks_data[index]
        task_id = task.get('id', 'Unknown')
        
        # Get new content from editor
        new_desc = self.editor_text.get("1.0", tk.END).strip()
        
        # Update local record
        task['description'] = new_desc
        task['updated_at'] = datetime.now().isoformat()
        
        # Save to plans/todos.json
        todos_path = self.babel_root / "plans" / "todos.json"
        try:
            # Load current file state to merge (avoid overwriting other changes if possible)
            # For now, we overwrite with our local state which is most recent
            with open(todos_path, 'w') as f:
                json.dump(self.tasks_data, f, indent=2)
            
            self.status_var.set(f"💾 Saved: {task_id[:8]}")
            self._add_traceback(f"Task {task_id} updated via UI Editor", "TASK")
            
            # Refresh list to show any status changes (if any)
            # self._refresh_task_list() 
        except Exception as e:
            self.engine.log_debug(f"Failed to save task: {e}", "ERROR")
            messagebox.showerror("Save Error", f"Could not save to {todos_path.name}:\n{e}")

    def _save_project_doc(self):
        """Save changes to the current project document with confirmation"""
        selection = self.task_listbox.curselection()
        if not selection:
            messagebox.showwarning("Selection", "Please select a task with a project association.")
            return

        task = self.tasks_data[selection[0]]
        proj_id = task.get('project_id', '(None)')
        
        if proj_id == '(None)':
            messagebox.showerror("Error", "This task has no project associated.")
            return

        # Sanitize name
        filename = proj_id.replace(" & ", "_").replace(" ", "_")
        project_file = self.babel_root / "plans" / f"{filename}.md"

        # Try variants
        if not project_file.exists():
            potential = list(self.babel_root.glob(f"plans/*{filename}*.md"))
            if potential: project_file = potential[0]

        if not project_file.exists():
            messagebox.showerror("Error", f"Could not find file: plans/{filename}.md")
            return

        if not messagebox.askyesno("Confirm Save", f"Are you sure you want to overwrite {project_file.name}?"):
            return

        try:
            content = self.project_text.get("1.0", tk.END)
            with open(project_file, 'w') as f:
                f.write(content)
            
            self.status_var.set(f"✅ Saved: {project_file.name}")
            self._add_traceback(f"Project Doc Saved: {project_file.name}", "FILE")
            
            # TODO: Trigger conformity check or sync here if needed
            
        except Exception as e:
            self.engine.log_debug(f"Failed to save project doc: {e}", "ERROR")
            messagebox.showerror("Save Error", f"Failed to save {project_file.name}:\n{e}")

    def _refresh_timeline(self):
        """Load historic plans from babel_data/timeline"""
        try:
            timeline_dir = self.babel_root / "babel_data" / "timeline" / "manifests"
            if not timeline_dir.exists():
                return

            # Clear existing
            for item in self.timeline_tree.get_children():
                self.timeline_tree.delete(item)

            # Load manifests
            manifests = sorted(timeline_dir.glob("manifest_*.json"), key=os.path.getmtime, reverse=True)
            for m in manifests:
                try:
                    timestamp = datetime.fromtimestamp(m.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
                    # Infer type from filename or content (simplified)
                    m_type = "Manifest"
                    snapshot_id = m.stem.replace("manifest_", "")
                    
                    self.timeline_tree.insert("", "end", values=(timestamp, m_type, snapshot_id))
                except Exception:
                    pass
        except Exception as e:
            self.engine.log_debug(f"Error refreshing timeline: {e}", "ERROR")

    def _show_new_project_dialog(self):
        """Show dialog to create a new project from template"""
        # Reuse existing new project logic from popup
        self._new_project(self)

    def _open_active_project_doc(self):
        """Open the currently active project document in editor"""
        current_name = self.current_project.get()
        if not current_name:
            messagebox.showwarning("No Project", "Please set an active project first.")
            return

        # Sanitize name for filename search
        # Try exact match first
        filename = current_name.replace(" & ", "_").replace(" ", "_")
        project_file = self.babel_root / "plans" / f"{filename}.md"
        
        if project_file.exists():
            subprocess.Popen([self.config.EDITOR, str(project_file)])
            self.status_var.set(f"📂 Opened: {project_file.name}")
        else:
            # Look for variants in plans/
            potential_files = list(self.babel_root.glob(f"plans/*{filename}*.md"))
            if not potential_files:
                # Try partial match on parts of the name
                parts = current_name.split()
                if len(parts) > 1:
                    potential_files = list(self.babel_root.glob(f"plans/*{parts[0]}*.md"))
            
            if potential_files:
                subprocess.Popen([self.config.EDITOR, str(potential_files[0])])
                self.status_var.set(f"📂 Opened: {potential_files[0].name}")
            else:
                messagebox.showerror("Not Found", f"Could not find project document for: {current_name}\nChecked plans/{filename}.md")

    @ui_event_tracker("chat_tab_init")
    def _create_chat_tab(self):
        """Create the Chat tab with 5x5cm chat interface"""
        chat_tab = tk.Frame(self.notebook, bg=self.config.BG_COLOR)
        self.notebook.add(chat_tab, text="💬 Chat")

        # Chat header
        chat_header = tk.Frame(chat_tab, bg=self.config.BG_COLOR, pady=10)
        chat_header.pack(fill=tk.X, padx=10)

        tk.Label(chat_header, text="Quick Chat", bg=self.config.BG_COLOR,
                fg=self.config.FG_COLOR, font=('Arial', 12, 'bold')).pack(side=tk.LEFT)

        # New Session Button
        tk.Button(chat_header, text="[New]", command=self._new_session,
                 bg='#2d7d46', fg='white', font=('Arial', 9),
                 bd=0, padx=5).pack(side=tk.LEFT, padx=(10, 2))

        # Copy Output Button
        tk.Button(chat_header, text="[Copy]", command=self._copy_chat_output,
                 bg='#3a7ca5', fg='white', font=('Arial', 9),
                 bd=0, padx=5).pack(side=tk.LEFT, padx=(0, 5))

        # Session Selector
        self.chat_session_select = ttk.Combobox(chat_header, 
                                              values=self._load_sessions(),
                                              width=18, state='readonly')
        self.chat_session_select.set("Select Session")
        self.chat_session_select.pack(side=tk.LEFT, padx=5)
        self.chat_session_select.bind('<<ComboboxSelected>>', self._on_session_selected)

        # Provider selector with config button
        provider_frame = tk.Frame(chat_header, bg=self.config.BG_COLOR)
        provider_frame.pack(side=tk.RIGHT, padx=(10, 0))

        # Provider config button (⚙️)
        tk.Button(provider_frame, text="⚙️", command=self._show_provider_config,
                 bg=self.config.HOVER_COLOR, fg=self.config.FG_COLOR,
                 font=('Arial', 10), width=2, height=1).pack(side=tk.RIGHT, padx=(5, 0))

        # Provider dropdown
        tk.Label(provider_frame, text="Provider:", bg=self.config.BG_COLOR,
                fg=self.config.FG_COLOR).pack(side=tk.RIGHT, padx=(10, 5))

        self.chat_provider = tk.StringVar(value="Ollama")
        provider_menu = ttk.Combobox(provider_frame, textvariable=self.chat_provider,
                                    values=["Ollama", "Claude", "Gemini", "Morph", "Bi-Hemi", "Manual"],
                                    width=12, state='readonly')
        provider_menu.pack(side=tk.RIGHT)
        provider_menu.bind('<<ComboboxSelected>>', lambda e: self._on_provider_changed(update_primed=True))

        # Morph Profile Selector (Conditional)
        self.morph_profile_frame = tk.Frame(chat_header, bg=self.config.BG_COLOR)
        # Packed only when provider is Morph
        
        tk.Label(self.morph_profile_frame, text="Morph Profile:", bg=self.config.BG_COLOR,
                fg=self.config.ACCENT_COLOR, font=('Arial', 9, 'bold')).pack(side=tk.LEFT, padx=(10, 5))
        
        self.morph_profile_var = tk.StringVar()
        self.morph_profile_menu = ttk.Combobox(self.morph_profile_frame, textvariable=self.morph_profile_var,
                                              width=15, state='readonly')
        self.morph_profile_menu.pack(side=tk.LEFT)
        self.morph_profile_menu.bind('<<ComboboxSelected>>', lambda e: self._refresh_morph_workflows())
        self._refresh_morph_profiles()

        # Morph Workflow Selector (Conditional)
        tk.Label(self.morph_profile_frame, text="Workflow:", bg=self.config.BG_COLOR,
                fg=self.config.ACCENT_COLOR, font=('Arial', 9)).pack(side=tk.LEFT, padx=(10, 5))
        self.morph_workflow_var = tk.StringVar()
        self.morph_workflow_menu = ttk.Combobox(self.morph_profile_frame, textvariable=self.morph_workflow_var,
                                               width=15, state='readonly')
        self.morph_workflow_menu.pack(side=tk.LEFT)

        # Model selector (dynamically updates based on provider)
        model_frame = tk.Frame(chat_header, bg=self.config.BG_COLOR)
        model_frame.pack(side=tk.RIGHT, padx=(0, 10))

        tk.Label(model_frame, text="Model:", bg=self.config.BG_COLOR,
                fg=self.config.FG_COLOR).pack(side=tk.LEFT, padx=(0, 5))

        self.chat_model = tk.StringVar()
        self.chat_model_menu = ttk.Combobox(model_frame, textvariable=self.chat_model,
                                           width=20, state='readonly')
        self.chat_model_menu.pack(side=tk.LEFT)
        self.chat_model_menu.bind('<<ComboboxSelected>>', lambda e: self._on_chat_model_selected())

        # Initialize models for default provider
        self._update_available_models()

        # Session switcher
        tk.Label(chat_header, text="Session:", bg=self.config.BG_COLOR,
                fg=self.config.FG_COLOR).pack(side=tk.RIGHT, padx=(10, 5))

        self.chat_session_type = tk.StringVar(value="Task")
        session_menu = ttk.Combobox(chat_header, textvariable=self.chat_session_type,
                                    values=["Plan", "Task"],
                                    width=8, state='readonly')
        session_menu.pack(side=tk.RIGHT)
        session_menu.bind('<<ComboboxSelected>>', lambda e: self._on_session_switch())

        # New Session button
        tk.Button(chat_header, text="[New]", command=self._new_session,
                 bg=self.config.BG_COLOR, fg=self.config.ACCENT_COLOR,
                 font=('Arial', 9)).pack(side=tk.RIGHT, padx=(5, 5))

        # Set Project Button (New in Chat)
        tk.Button(chat_header, text="[Set Project]", command=self._set_project,
                 bg=self.config.BG_COLOR, fg=self.config.ACCENT_COLOR,
                 font=('Arial', 9)).pack(side=tk.RIGHT, padx=(5, 5))

        # View Context toggle
        self.context_view_var = tk.BooleanVar(value=False)
        self.context_btn = tk.Button(chat_header, text="[Toggle Context]",
                      command=self._toggle_context_view,
                      bg=self.config.BG_COLOR, fg=self.config.FG_COLOR,
                      font=('Arial', 9))
        self.context_btn.pack(side=tk.RIGHT, padx=(10, 5))

        # Todo List selector with count
        self.selected_todo_ids = []  # Track selected todos for context
        todo_count = self._count_todos()
        self.todo_list_btn = tk.Button(chat_header, text=f"📋 Todos: [{todo_count}]",
                      command=self._show_todo_selector,
                      bg=self.config.BG_COLOR, fg=self.config.ACCENT_COLOR,
                      font=('Arial', 9))
        self.todo_list_btn.pack(side=tk.RIGHT, padx=(5, 0))

        # Chat messages area (189x189px ~ 5x5cm)
        chat_messages_frame = tk.Frame(chat_tab, bg='#2a2a2a', height=189)
        chat_messages_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
        chat_messages_frame.pack_propagate(False)

        # Scrollable text for messages
        chat_scrollbar = tk.Scrollbar(chat_messages_frame)
        chat_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.chat_messages = scrolledtext.ScrolledText(
            chat_messages_frame,
            bg='#2a2a2a',
            fg=self.config.FG_COLOR,
            font=('Arial', 9),
            wrap=tk.WORD,
            yscrollcommand=chat_scrollbar.set
        )
        self.chat_messages.pack(fill=tk.BOTH, expand=True)
        chat_scrollbar.config(command=self.chat_messages.yview)

        # Initial message
        self.chat_messages.insert(tk.END, "💬 Quick Chat Ready\n")
        self.chat_messages.insert(tk.END, "─" * 40 + "\n")
        self.chat_messages.config(state=tk.DISABLED)

        # Initialize (PRIME) session on tab creation ONLY if no session exists
        if not hasattr(self, 'current_session_id'):
            self._init_session()

        # Input area
        input_frame = tk.Frame(chat_tab, bg=self.config.BG_COLOR)
        input_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

        self.chat_input = tk.Entry(
            input_frame,
            bg='#2a2a2a',
            fg=self.config.FG_COLOR,
            insertbackground=self.config.FG_COLOR,
            font=('Arial', 9)
        )
        self.chat_input.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        self.chat_input.bind('<Return>', lambda e: self._send_chat_message())
        # Try focus_force again, but we might need window manager hints changes
        self.chat_input.bind('<Button-1>', lambda e: self.chat_input.focus_force())

        tk.Button(input_frame, text="Send", command=self._send_chat_message,
                 bg=self.config.ACCENT_COLOR, fg='black',
                 font=('Arial', 9), padx=10).pack(side=tk.RIGHT)

        # Tool switches
        tools_frame = tk.Frame(chat_tab, bg=self.config.BG_COLOR)
        tools_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

        tk.Label(tools_frame, text="Tools:", bg=self.config.BG_COLOR,
                fg=self.config.FG_COLOR, font=('Arial', 9, 'bold')).pack(side=tk.LEFT, padx=(0, 10))

        # Tool checkboxes
        self.tool_grep = tk.BooleanVar(value=True)
        self.tool_read = tk.BooleanVar(value=True)
        self.tool_write = tk.BooleanVar(value=False)

        tk.Checkbutton(tools_frame, text="Grep", variable=self.tool_grep,
                      bg=self.config.BG_COLOR, fg=self.config.FG_COLOR,
                      selectcolor='#2a2a2a').pack(side=tk.LEFT, padx=2)
        tk.Checkbutton(tools_frame, text="Read", variable=self.tool_read,
                      bg=self.config.BG_COLOR, fg=self.config.FG_COLOR,
                      selectcolor='#2a2a2a').pack(side=tk.LEFT, padx=2)
        tk.Checkbutton(tools_frame, text="Write", variable=self.tool_write,
                      bg=self.config.BG_COLOR, fg=self.config.FG_COLOR,
                      selectcolor='#2a2a2a').pack(side=tk.LEFT, padx=2)

        # Action buttons
        action_frame = tk.Frame(chat_tab, bg=self.config.BG_COLOR)
        action_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

        if self.app_ref:
            tk.Button(action_frame, text="Open Full Chat →", command=self._launch_chat,
                     bg=self.config.ACCENT_COLOR, fg='black',
                     font=('Arial', 10), padx=15).pack(side=tk.LEFT)

        # Log targeting button
        tk.Button(action_frame, text="📊 Target Logs", command=self._target_chat_logs,
                 bg='#3a7ca5', fg='white',
                 font=('Arial', 9), padx=10).pack(side=tk.LEFT, padx=(10, 0))

        tk.Button(action_frame, text="Clear", command=self._clear_chat,
                 bg=self.config.HOVER_COLOR, fg=self.config.FG_COLOR,
                 font=('Arial', 10), padx=15).pack(side=tk.RIGHT)

    @ui_event_tracker("context_toggle")
    def _toggle_context_view(self):
        """Toggle context PRIMING with comprehensive debug output"""
        # #[Event:CONTEXT_TOGGLE_START]
        current = self.context_view_var.get()
        new_state = not current

        self.engine.log_debug(f"#[Event:CONTEXT_TOGGLE_START] Current: {current}, New: {new_state}", "DEBUG")
        log_to_traceback(EventCategory.CHAT, "context_toggle_start",
                       {"current": current, "new": new_state},
                       {"status": "toggling"})

        self.context_view_var.set(new_state)

        if new_state:
            # #[Event:CONTEXT_PRIMING]
            self.engine.log_debug(f"#[Event:CONTEXT_PRIMING] Gathering context...", "INFO")

            # PRIMED: Context ready but invisible to user
            self.context_btn.config(bg='#2d4d3d', relief=tk.SUNKEN, text="🔋 Context PRIMED")

            # Show debug header FIRST
            debug_symbol = "🐛"
            self.chat_messages.config(state=tk.NORMAL)
            self.chat_messages.insert(tk.END, f"\n{'='*50}\n")
            self.chat_messages.insert(tk.END, f"🔋 CONTEXT PRIMING {debug_symbol} ACTIVE\n")
            self.chat_messages.insert(tk.END, f"{'='*50}\n")

            # Gather context with debug
            try:
                context_str, available_sources = self._gather_full_context()

                # Debug: Show what was gathered with detailed breakdown
                self.chat_messages.insert(tk.END, f"\n✅ Context gathered successfully:\n")
                self.chat_messages.insert(tk.END, f"   • Size: {len(context_str)} chars\n")

                # Show detailed source breakdown
                all_sources = ["clipboard", "os_toolkit", "todos", "morph"]
                self.chat_messages.insert(tk.END, f"\n   Source Status:\n")
                for src in all_sources:
                    if src in available_sources:
                        self.chat_messages.insert(tk.END, f"   ✅ {src}\n")
                    else:
                        self.chat_messages.insert(tk.END, f"   ⚠️ {src} (failed/unavailable)\n")

                self.chat_messages.insert(tk.END, f"\n   • Status: PRIMED (will send with next message)\n")

                # Show first 300 chars as preview
                preview = context_str[:300].replace('\n', ' ')
                self.chat_messages.insert(tk.END, f"\n📋 Preview: {preview}...\n")

                # Copy to clipboard
                try:
                    pyperclip.copy(context_str)
                    self.chat_messages.insert(tk.END, f"   • Clipboard: ✅ Synced\n")
                    self.engine.log_debug(f"#[Event:CLIPBOARD_SYNC] Context copied", "DEBUG")
                except Exception as e:
                    self.chat_messages.insert(tk.END, f"   • Clipboard: ⚠️ Failed ({str(e)[:50]})\n")
                    self.engine.log_debug(f"#[Event:CLIPBOARD_SYNC_ERROR] {e}", "ERROR")

                # #[Event:CONTEXT_PRIMED_SUCCESS]
                log_to_traceback(EventCategory.CHAT, "context_primed_success",
                               {"target": self.target_var.get(), "size": len(context_str)},
                               {"status": "Ready"})

            except Exception as e:
                # #[Event:CONTEXT_PRIMING_ERROR]
                self.chat_messages.insert(tk.END, f"\n❌ Context gathering FAILED: {str(e)}\n")
                self.engine.log_debug(f"#[Event:CONTEXT_PRIMING_ERROR] {e}", "ERROR")
                log_to_traceback(EventCategory.ERROR, "context_priming_error",
                               {"target": self.target_var.get()},
                               error=str(e))

            self.chat_messages.insert(tk.END, f"{'='*50}\n")
            self.chat_messages.config(state=tk.DISABLED)
            self.chat_messages.see(tk.END)

        else:
            # #[Event:CONTEXT_DISABLED]
            self.engine.log_debug(f"#[Event:CONTEXT_DISABLED]", "INFO")
            self.context_btn.config(bg=self.config.BG_COLOR, relief=tk.RAISED, text="Toggle Context")

            self.chat_messages.config(state=tk.NORMAL)
            self.chat_messages.insert(tk.END, f"\n📋 Context DISABLED 🐛\n")
            self.chat_messages.config(state=tk.DISABLED)
            self.chat_messages.see(tk.END)

            log_to_traceback(EventCategory.CHAT, "context_disabled",
                           {},
                           {"status": "off"})

    # _open_chat_input_popup removed - reverting to standard input handling

    def _create_inventory_tab(self):
        """Create the Inventory tab with File Tree, Provisions, Stash, and Projects sub-tabs"""
        inventory_tab = tk.Frame(self.notebook, bg=self.config.BG_COLOR)
        self.notebook.add(inventory_tab, text="📦 Inventory")

        # Create sub-notebook for File Tree, Provisions, Stash, Projects
        self.inventory_notebook = ttk.Notebook(inventory_tab)
        self.inventory_notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.inventory_notebook.bind("<<NotebookTabChanged>>", self._on_inventory_tab_changed)

        # Sub-tab 1: Files (File Tree) - NEW
        self._create_file_tree_tab(self.inventory_notebook)

        # Sub-tab 2: Provisions (from backup_manifest.json)
        self._create_provisions_subtab(self.inventory_notebook)

        # Sub-tab 3: Stash (stash_script controls)
        self._create_stash_subtab(self.inventory_notebook)

        # Sub-tab 4: Projects (shared projects)
        self._create_projects_subtab(self.inventory_notebook)

        # Sub-tab 5: Babel Catalog (onboarder + babel_data)
        self._create_babel_catalog_subtab(self.inventory_notebook)

    def _create_babel_tab(self):
        """Create Babel main tab (wrapping catalog subtab)"""
        # We reuse the catalog subtab logic but add it to the main notebook
        self._create_babel_catalog_subtab(self.notebook)

    def _create_file_tree_tab(self, parent_notebook):
        """Create File Tree sub-tab"""
        file_frame = tk.Frame(parent_notebook, bg=self.config.BG_COLOR)
        parent_notebook.add(file_frame, text="📂 Files")
        
        # Use our new TreeViewPanel
        # We pass self.project_root or version_root as initial path
        start_path = self.project_root if hasattr(self, 'project_root') else os.getcwd()
        self.file_tree_panel = TreeViewPanel(file_frame, self.engine, root_path=str(start_path))
        self.file_tree_panel.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    def _create_provisions_subtab(self, parent_notebook):
        """Create Provisions sub-tab showing working files from backup_manifest"""
        provisions_frame = tk.Frame(parent_notebook, bg=self.config.BG_COLOR)
        parent_notebook.add(provisions_frame, text="📋 Provisions")

        # Header
        header = tk.Frame(provisions_frame, bg='#3c3c3c', height=35)
        header.pack(fill=tk.X)
        header.pack_propagate(False)

        tk.Label(header, text="Working Files (from recent backups)",
                bg='#3c3c3c', fg='#ffffff', font=('Arial', 10, 'bold')).pack(
                side=tk.LEFT, padx=10)

        tk.Button(header, text="↻ Refresh", command=self._refresh_provisions,
                 bg='#0e639c', fg='white', font=('Arial', 9),
                 relief=tk.FLAT, padx=10).pack(side=tk.RIGHT, padx=5, pady=2)

        # Provisions list
        list_frame = tk.Frame(provisions_frame, bg=self.config.BG_COLOR)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        scrollbar = tk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.provisions_listbox = tk.Listbox(
            list_frame,
            bg='#2a2a2a',
            fg=self.config.FG_COLOR,
            font=('Courier', 9),
            selectmode=tk.SINGLE,
            yscrollcommand=scrollbar.set
        )
        self.provisions_listbox.pack(fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.provisions_listbox.yview)

        # Buttons for selected provision
        buttons_frame = tk.Frame(provisions_frame, bg=self.config.BG_COLOR)
        buttons_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

        tk.Button(buttons_frame, text="📂 Open", command=self._open_provision,
                 bg='#2d7d46', fg='white', font=('Arial', 9),
                 padx=10, pady=2).pack(side=tk.LEFT, padx=2)

        tk.Button(buttons_frame, text="🎯 Target", command=self._target_provision,
                 bg='#0e639c', fg='white', font=('Arial', 9),
                 padx=10, pady=2).pack(side=tk.LEFT, padx=2)

        tk.Button(buttons_frame, text="📊 Profile", command=self._profile_provision,
                 bg='#6e4c9e', fg='white', font=('Arial', 9),
                 padx=10, pady=2).pack(side=tk.LEFT, padx=2)

        tk.Button(buttons_frame, text="💾 Stash", command=self._stash_provision,
                 bg='#3c3c3c', fg='#cccccc', font=('Arial', 9),
                 padx=10, pady=2).pack(side=tk.LEFT, padx=2)

        tk.Button(buttons_frame, text="📦 Backup", command=self._backup_current_target,
                 bg='#d67e00', fg='white', font=('Arial', 9),
                 padx=10, pady=2).pack(side=tk.LEFT, padx=2)

        tk.Button(buttons_frame, text="🔄 Restore", command=self._show_restore_menu,
                 bg='#00a86b', fg='white', font=('Arial', 9),
                 padx=10, pady=2).pack(side=tk.LEFT, padx=2)

        # Load provisions
        self._refresh_provisions()

    def _create_stash_subtab(self, parent_notebook):
        """Create Stash sub-tab with stash_script controls"""
        stash_frame = tk.Frame(parent_notebook, bg=self.config.BG_COLOR)
        parent_notebook.add(stash_frame, text="💾 Stash")

        # Header
        header = tk.Frame(stash_frame, bg='#3c3c3c', height=35)
        header.pack(fill=tk.X)
        header.pack_propagate(False)

        tk.Label(header, text="Stash Management",
                bg='#3c3c3c', fg='#ffffff', font=('Arial', 10, 'bold')).pack(
                side=tk.LEFT, padx=10)

        # Stash controls
        controls_frame = tk.Frame(stash_frame, bg=self.config.BG_COLOR, pady=10)
        controls_frame.pack(fill=tk.X, padx=10)

        tk.Button(controls_frame, text="📦 Stash Current Target",
                 command=self._stash_current_target,
                 bg='#2d7d46', fg='white', font=('Arial', 10),
                 padx=15, pady=5).pack(fill=tk.X, pady=5)

        tk.Label(controls_frame, text="Stashed Files:", bg=self.config.BG_COLOR,
                fg=self.config.FG_COLOR, font=('Arial', 9, 'bold')).pack(
                anchor=tk.W, pady=(10, 5))

        # Stashed files list
        list_frame = tk.Frame(stash_frame, bg=self.config.BG_COLOR)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        scrollbar = tk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.stash_listbox = tk.Listbox(
            list_frame,
            bg='#2a2a2a',
            fg=self.config.FG_COLOR,
            font=('Courier', 9),
            selectmode=tk.SINGLE,
            yscrollcommand=scrollbar.set
        )
        self.stash_listbox.pack(fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.stash_listbox.yview)

        # Stash action buttons
        stash_buttons = tk.Frame(stash_frame, bg=self.config.BG_COLOR)
        stash_buttons.pack(fill=tk.X, padx=10, pady=(0, 10))

        tk.Button(stash_buttons, text="🔄 Unstash", command=self._unstash_file,
                 bg='#0e639c', fg='white', font=('Arial', 9),
                 padx=10, pady=2).pack(side=tk.LEFT, padx=2)

        tk.Button(stash_buttons, text="🗑️ Delete", command=self._delete_stash,
                 bg='#a54242', fg='white', font=('Arial', 9),
                 padx=10, pady=2).pack(side=tk.LEFT, padx=2)

        tk.Button(stash_buttons, text="↻ Refresh", command=self._refresh_stash,
                 bg='#3c3c3c', fg='#cccccc', font=('Arial', 9),
                 padx=10, pady=2).pack(side=tk.RIGHT, padx=2)

        # Load stash list
        self._refresh_stash()

    def _create_projects_subtab(self, parent_notebook):
        """Create Projects sub-tab showing shared project provisions"""
        projects_frame = tk.Frame(parent_notebook, bg=self.config.BG_COLOR)
        parent_notebook.add(projects_frame, text="🗂️ Projects")

        # Header
        header = tk.Frame(projects_frame, bg='#3c3c3c', height=35)
        header.pack(fill=tk.X)
        header.pack_propagate(False)

        tk.Label(header, text="Shared Project Provisions",
                bg='#3c3c3c', fg='#ffffff', font=('Arial', 10, 'bold')).pack(
                side=tk.LEFT, padx=10)

        tk.Button(header, text="↻ Refresh", command=self._refresh_projects,
                 bg='#0e639c', fg='white', font=('Arial', 9),
                 relief=tk.FLAT, padx=10).pack(side=tk.RIGHT, padx=5, pady=2)

        # Projects tree view
        tree_frame = tk.Frame(projects_frame, bg=self.config.BG_COLOR)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        scrollbar = tk.Scrollbar(tree_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.projects_listbox = tk.Listbox(
            tree_frame,
            bg='#2a2a2a',
            fg=self.config.FG_COLOR,
            font=('Courier', 9),
            selectmode=tk.SINGLE,
            yscrollcommand=scrollbar.set
        )
        self.projects_listbox.pack(fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.projects_listbox.yview)

        # Project action buttons
        buttons_frame = tk.Frame(projects_frame, bg=self.config.BG_COLOR)
        buttons_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

        tk.Button(buttons_frame, text="📂 Open", command=self._open_project,
                 bg='#2d7d46', fg='white', font=('Arial', 9),
                 padx=10, pady=2).pack(side=tk.LEFT, padx=2)

        tk.Button(buttons_frame, text="🎯 Target", command=self._target_project,
                 bg='#0e639c', fg='white', font=('Arial', 9),
                 padx=10, pady=2).pack(side=tk.LEFT, padx=2)

        # Load projects
        self._refresh_projects()

    def _create_babel_catalog_subtab(self, parent_notebook):
        """Create Babel Catalog subtab - shows onboarder tools + babel_data"""
        catalog_frame = tk.Frame(parent_notebook, bg=self.config.BG_COLOR)
        parent_notebook.add(catalog_frame, text="🏛️ Babel")

        # Header
        header = tk.Frame(catalog_frame, bg='#3c3c3c', height=35)
        header.pack(fill=tk.X)
        header.pack_propagate(False)

        tk.Label(header, text="Babel System Catalog",
                bg='#3c3c3c', fg='#ffffff', font=('Arial', 10, 'bold')).pack(
                side=tk.LEFT, padx=10)

        tk.Button(header, text="↻ Refresh", command=self._refresh_babel_catalog,
                 bg='#0e639c', fg='white', font=('Arial', 9),
                 relief=tk.FLAT, padx=10).pack(side=tk.RIGHT, padx=5, pady=2)

        tk.Button(header, text="🔄 Run Catalog", command=self._run_onboarder_catalog,
                 bg='#2d7d46', fg='white', font=('Arial', 9),
                 relief=tk.FLAT, padx=10).pack(side=tk.RIGHT, padx=5, pady=2)

        # Project Context Info
        self.context_frame = tk.Frame(catalog_frame, bg='#2a2a2a', height=25)
        self.context_frame.pack(fill=tk.X, padx=10, pady=(5, 0))
        
        self.project_context_var = tk.StringVar(value="Project Context: Unknown")
        tk.Label(self.context_frame, textvariable=self.project_context_var,
                bg='#2a2a2a', fg=self.config.ACCENT_COLOR, font=('Arial', 9)).pack(side=tk.LEFT, padx=5)

        # Split: Category list on left, items on right
        paned = ttk.PanedWindow(catalog_frame, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Left: Categories
        left_frame = tk.Frame(paned, bg=self.config.BG_COLOR)
        paned.add(left_frame, weight=1)

        tk.Label(left_frame, text="Categories", bg=self.config.BG_COLOR,
                fg='#4ec9b0', font=('Arial', 9, 'bold')).pack(anchor=tk.W)

        self.catalog_categories = tk.Listbox(
            left_frame, bg='#2a2a2a', fg=self.config.FG_COLOR,
            font=('Arial', 9), selectmode=tk.SINGLE, height=15
        )
        self.catalog_categories.pack(fill=tk.BOTH, expand=True, pady=5)

        # Right: Items in selected category
        right_frame = tk.Frame(paned, bg=self.config.BG_COLOR)
        paned.add(right_frame, weight=3)

        tk.Label(right_frame, text="Items", bg=self.config.BG_COLOR,
                fg='#4ec9b0', font=('Arial', 9, 'bold')).pack(anchor=tk.W)

        # Items tree
        tree_frame = tk.Frame(right_frame, bg=self.config.BG_COLOR)
        tree_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        columns = ('Type', 'Path', 'Details')
        self.catalog_tree = ttk.Treeview(tree_frame, columns=columns,
                                         show='tree headings', height=15)
        self.catalog_tree.heading('#0', text='Name')
        self.catalog_tree.heading('Type', text='Type')
        self.catalog_tree.heading('Path', text='Location')
        self.catalog_tree.heading('Details', text='Details')
        self.catalog_tree.column('#0', width=200)
        self.catalog_tree.column('Type', width=100)
        self.catalog_tree.column('Path', width=250)
        self.catalog_tree.column('Details', width=150)

        scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL,
                                  command=self.catalog_tree.yview)
        self.catalog_tree.configure(yscrollcommand=scrollbar.set)
        self.catalog_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Bind category selection
        self.catalog_categories.bind('<<ListboxSelect>>', self._on_catalog_category_select)

        # Action buttons
        btn_frame = tk.Frame(catalog_frame, bg=self.config.BG_COLOR)
        btn_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

        tk.Button(btn_frame, text="🎯 Set Target", command=self._set_catalog_item_as_target,
                 bg='#0e639c', fg='white', padx=10, pady=2).pack(side=tk.LEFT, padx=2)

        tk.Button(btn_frame, text="📊 Profile", command=self._profile_catalog_item,
                 bg='#2d7d46', fg='white', padx=10, pady=2).pack(side=tk.LEFT, padx=2)

        tk.Button(btn_frame, text="📂 Open", command=self._open_catalog_item,
                 bg='#6e4c9e', fg='white', padx=10, pady=2).pack(side=tk.LEFT, padx=2)

        # Load catalog
        self._refresh_babel_catalog()

    def _refresh_babel_catalog(self):
        """Refresh content of Babel catalog"""
        # Load consolidated_menu.json
        menu_path = self.version_root / 'inventory' / 'consolidated_menu.json'
        
        self.catalog_categories.delete(0, tk.END)
        self.catalog_data = {}
        
        if menu_path.exists():
            try:
                with open(menu_path, 'r') as f:
                    data = json.load(f)
                    
                # Group by category
                for tool in data.get('tools', []):
                    cat = tool.get('category', 'uncategorized')
                    if cat not in self.catalog_data:
                        self.catalog_data[cat] = []
                    self.catalog_data[cat].append(tool)
                    
                # Populate categories
                for cat in sorted(self.catalog_data.keys()):
                    self.catalog_categories.insert(tk.END, cat)
                    
            except Exception as e:
                self.engine.log_debug(f"Error loading catalog: {e}", "ERROR")
        else:
            self.catalog_categories.insert(tk.END, "[No Catalog Found]")

        # Log catalog refresh
        cat_count = len(self.catalog_data)
        item_count = sum(len(items) for items in self.catalog_data.values())
        self._add_traceback(f"🏛️ Babel Catalog Refreshed: {cat_count} categories, {item_count} items", "DEBUG")

        # NEW: Update Project Context from Filesync manifest
        self._update_project_context()

    def _update_project_context(self):
        """Load latest Filesync manifest to display project inference"""
        manifest_dir = self.babel_root / "babel_data" / "timeline" / "manifests"
        
        if not manifest_dir.exists():
            return

        try:
            # Find latest manifest
            manifests = sorted(manifest_dir.glob("manifest_*.json"))
            if not manifests:
                self.project_context_var.set("Project Context: No manifest found")
                return
                
            latest = manifests[-1]
            with open(latest, 'r') as f:
                data = json.load(f)
                
            self.projects_data = data.get('projects', {})
            
            # Populate Cluster Listbox
            if hasattr(self, 'cluster_listbox'):
                self.cluster_listbox.delete(0, tk.END)
                for cluster_id, proj in self.projects_data.items():
                    name = proj.get('name', cluster_id)
                    p_type = proj.get('inference', {}).get('type', 'Unknown')
                    self.cluster_listbox.insert(tk.END, f"{name} ({p_type})")

            # Look for primary project or inference for global indicator
            if self.projects_data:
                first_proj = list(self.projects_data.values())[0]
                inference = first_proj.get('inference', {})
                p_type = inference.get('type', 'Unknown')
                p_subtype = inference.get('subtype', '')
                conf = int(inference.get('confidence', 0) * 100)
                self.project_context_var.set(f"Project Context: {p_type} ({conf}%)")
            else:
                self.project_context_var.set("Project Context: No projects inferred")
                
        except Exception as e:
            self.engine.log_debug(f"Error loading project context: {e}", "WARNING")

    def _on_cluster_select(self, event):
        """Show detailed inference data for the selected cluster"""
        selection = self.cluster_listbox.curselection()
        if not selection or not hasattr(self, 'projects_data'):
            return

        idx = selection[0]
        cluster_id = list(self.projects_data.keys())[idx]
        proj = self.projects_data[cluster_id]
        
        inference = proj.get('inference', {})
        
        summary = []
        summary.append(f"CLUSTER ID: {cluster_id}")
        summary.append(f"NAME: {proj.get('name')}")
        summary.append("-" * 40)
        summary.append(f"INFERRED TYPE: {inference.get('type')}")
        summary.append(f"SUBTYPE: {inference.get('subtype')}")
        summary.append(f"CONFIDENCE: {int(inference.get('confidence', 0)*100)}%")
        summary.append("-" * 40)
        
        evidence = inference.get('evidence', {})
        summary.append("EVIDENCE:")
        for key, val in evidence.items():
            if isinstance(val, dict):
                summary.append(f"  {key.capitalize()}:")
                for k, v in val.items():
                    summary.append(f"    - {k}: {v}")
            else:
                summary.append(f"  {key.capitalize()}: {val}")
        
        summary.append("-" * 40)
        summary.append(f"FILES ({len(proj.get('file_ids', []))}):")
        # We'd need the catalog to resolve IDs to names, but for now we list IDs or basename if available
        for fid in proj.get('file_ids', [])[:20]:
            summary.append(f"  - {fid}")
        if len(proj.get('file_ids', [])) > 20:
            summary.append("  ... (truncated)")

        self.proj_inference_text.config(state='normal')
        self.proj_inference_text.delete("1.0", tk.END)
        self.proj_inference_text.insert(tk.END, "\n".join(summary))
        self.proj_inference_text.config(state='disabled')

    def _on_catalog_category_select(self, event):
        """Load items for selected category"""
        sel = self.catalog_categories.curselection()
        if not sel:
            return

        category = self.catalog_categories.get(sel[0])

        self.engine.log_debug(f"Catalog Category Select: {category}", "INFO")
        self._add_traceback(f"🏛️ Catalog View: {category}", "DEBUG")

        # Clear tree
        for item in self.catalog_tree.get_children():
            self.catalog_tree.delete(item)

        if "Onboarder Tools" in category:
            self._load_onboarder_tools()
        elif "Sessions" in category:
            self._load_sessions()
        elif "Manifests" in category:
            self._load_manifests()
        elif "Timeline" in category:
            self._load_timeline()
        elif "Profiles" in category:
            self._load_profiles()

    def _load_onboarder_tools(self):
        """Load tools from consolidated_menu.json"""
        menu_path = Path.cwd() / "babel_data" / "inventory" / "consolidated_menu.json"
        if not menu_path.exists():
            self.catalog_tree.insert('', 'end', text="No catalog found",
                                    values=('', 'Run: ./babel catalog', ''))
            return

        try:
            with open(menu_path) as f:
                menu = json.load(f)

            tools = menu.get('tools', [])
            for tool in tools:
                name = tool.get('name', 'Unknown')
                cat = tool.get('category', 'unknown')
                path = tool.get('path', tool.get('command', ''))
                desc = tool.get('description', '')[:50]

                self.catalog_tree.insert('', 'end', text=name,
                                        values=(cat, path, desc))

        except Exception as e:
            self.catalog_tree.insert('', 'end', text=f"Error: {e}",
                                    values=('', '', ''))

    def _load_sessions(self):
        """Load sessions from babel_data/profile/sessions/"""
        sessions_dir = Path.cwd() / "babel_data" / "profile" / "sessions"
        if not sessions_dir.exists():
            self.catalog_tree.insert('', 'end', text="No sessions found",
                                    values=('', '', ''))
            return

        for session_dir in sorted(sessions_dir.iterdir(), reverse=True):
            if session_dir.is_dir():
                name = session_dir.name
                artifacts_file = session_dir / "artifacts.json"
                count = "?"
                if artifacts_file.exists():
                    try:
                        with open(artifacts_file) as f:
                            data = json.load(f)
                            count = len(data) if isinstance(data, list) else len(data.get('artifacts', []))
                    except:
                        pass

                self.catalog_tree.insert('', 'end', text=name,
                                        values=('Session', str(session_dir), f'{count} artifacts'))

    def _load_manifests(self):
        """Load manifests from babel_data/profile/manifests/"""
        manifests_dir = Path.cwd() / "babel_data" / "profile" / "manifests"
        if not manifests_dir.exists():
            self.catalog_tree.insert('', 'end', text="No manifests found",
                                    values=('', '', ''))
            return

        for manifest_file in sorted(manifests_dir.glob("*.json"), reverse=True):
            name = manifest_file.stem
            size = manifest_file.stat().st_size
            self.catalog_tree.insert('', 'end', text=name,
                                    values=('Manifest', str(manifest_file), f'{size} bytes'))

    def _load_timeline(self):
        """Load timeline data from babel_data/timeline/"""
        timeline_dir = Path.cwd() / "babel_data" / "timeline"
        if not timeline_dir.exists():
            self.catalog_tree.insert('', 'end', text="No timeline data",
                                    values=('', '', ''))
            return

        # Show manifests and organized structure
        for subdir in timeline_dir.iterdir():
            if subdir.is_dir():
                file_count = len(list(subdir.rglob('*')))
                self.catalog_tree.insert('', 'end', text=subdir.name,
                                        values=('Directory', str(subdir), f'{file_count} items'))

    def _load_profiles(self):
        """Load agent profiles from babel_profiles.json"""
        profile_path = Path.cwd() / "babel_data" / "inventory" / "babel_profiles.json"
        if not profile_path.exists():
            self.catalog_tree.insert('', 'end', text="No profiles found",
                                    values=('', '', ''))
            return

        try:
            with open(profile_path) as f:
                data = json.load(f)

            profiles = data.get('profiles', {})
            for pid, pdata in profiles.items():
                name = pdata.get('name', pid)
                icon = pdata.get('icon', '')
                agent_type = pdata.get('agent_type', 'unknown')
                tool_count = len(pdata.get('tool_locations', {}))

                self.catalog_tree.insert('', 'end', text=f"{icon} {name}",
                                        values=(agent_type, pid, f'{tool_count} tools'))

        except Exception as e:
            self.catalog_tree.insert('', 'end', text=f"Error: {e}",
                                    values=('', '', ''))

    def _run_onboarder_catalog(self):
        """Run onboarder catalog command"""
        import subprocess
        os_toolkit = str(self.babel_root / 'Os_Toolkit.py')
        subprocess.Popen(['python3', os_toolkit, 'actions', '--run', 'catalog'])
        messagebox.showinfo("Catalog", "Running onboarder catalog...\nRefresh in a few seconds.")

    def _set_catalog_item_as_target(self):
        """Set selected catalog item as grep target"""
        sel = self.catalog_tree.selection()
        if not sel:
            return

        item = self.catalog_tree.item(sel[0])
        path = item['values'][1] if len(item['values']) > 1 else ''

        if path and Path(path).exists():
            self.target_var.set(path)
            messagebox.showinfo("Target Set", f"Target: {Path(path).name}")

    def _profile_catalog_item(self):
        """Profile selected item with Os_Toolkit"""
        sel = self.catalog_tree.selection()
        if not sel:
            return

        item = self.catalog_tree.item(sel[0])
        path = item['values'][1] if len(item['values']) > 1 else ''

        if path and Path(path).exists():
            import subprocess
            os_toolkit = str(self.babel_root / 'Os_Toolkit.py')
            subprocess.Popen(['python3', os_toolkit, 'file', path, '--depth', '2', '-z'])

    def _open_catalog_item(self):
        """Open selected catalog item"""
        sel = self.catalog_tree.selection()
        if not sel:
            return

        item = self.catalog_tree.item(sel[0])
        path = item['values'][1] if len(item['values']) > 1 else ''

        if path and Path(path).exists():
            import subprocess
            if Path(path).is_dir():
                subprocess.Popen([self.config.FILE_MANAGER, path])
            else:
                subprocess.Popen([self.config.EDITOR, path])

    def _gather_full_context(self) -> str:
        """Gather comprehensive context for chat interaction with event logging"""
        # #[Event:CONTEXT_GATHER_START]
        log_to_traceback(EventCategory.CHAT, "context_gather_start",
                       {"target": self.target_var.get()},
                       {"status": "initiating"})

        try:
            context_parts = []
            available_sources = []  # Track which sources successfully loaded
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.engine.log_debug(f"#[Event:CONTEXT_GATHER] Starting context aggregation", "DEBUG")

            # 1. 5xW Classification (Current Event)
            target = self.target_var.get()
            
            context_parts.append("=== 5xW EVENT CLASSIFICATION ===")
            context_parts.append(f"What: Context Aggregation Triggered")
            context_parts.append(f"When: {timestamp}")
            context_parts.append(f"Where: {target or 'System Global'}")
            context_parts.append(f"Why: User Toggle [ON]")
            context_parts.append(f"How: Morph Effect (Multi-Source Flip)")
            context_parts.append("")

            # 2. Clipboard Context (via clip.py trigger)
            # #TODO: This integrates with clip.py for clipboard-based context injection.
            #        Future: Add clip.py monitoring daemon that auto-triggers on clipboard changes.
            #        Currently relies on pyperclip for passive clipboard reading.
            try:
                import pyperclip as clip_module
                clip_text = clip_module.paste()
                if clip_text and len(clip_text.strip()) > 0:
                    context_parts.append("--- Clipboard Context ✅ ---")
                    context_parts.append(clip_text[:1000] + ("..." if len(clip_text) > 1000 else ""))
                    context_parts.append("")
                    available_sources.append("clipboard")
                    self.engine.log_debug(f"#[Event:CONTEXT_CLIPBOARD] Captured {len(clip_text)} chars", "DEBUG")
                else:
                    context_parts.append("--- Clipboard Context ⚠️ (Empty) ---")
                    context_parts.append("")
                    self.engine.log_debug(f"#[Event:CONTEXT_CLIPBOARD] Empty clipboard", "DEBUG")
            except ImportError as e:
                context_parts.append("--- Clipboard Context ⚠️ (pyperclip not installed) ---")
                context_parts.append("")
                self.engine.log_debug(f"#[Event:CONTEXT_CLIPBOARD_ERROR] ImportError: {e}", "DEBUG")
            except AttributeError as e:
                context_parts.append("--- Clipboard Context ⚠️ (Clipboard access failed) ---")
                context_parts.append(f"Error: {str(e)[:100]}")
                context_parts.append("")
                self.engine.log_debug(f"#[Event:CONTEXT_CLIPBOARD_ERROR] AttributeError: {e}", "DEBUG")
            except Exception as e:
                context_parts.append("--- Clipboard Context ⚠️ (Unavailable) ---")
                context_parts.append(f"Error: {type(e).__name__}: {str(e)[:100]}")
                context_parts.append("")
                self.engine.log_debug(f"#[Event:CONTEXT_CLIPBOARD_ERROR] {type(e).__name__}: {e}", "DEBUG")

            # 3. Core Target Context & Morph/Guillm Profiling
            if target and os.path.exists(target):
                context_parts.append(f"--- Targeted File: {os.path.basename(target)} ---")
                # Check for taxonomized module data in version manager
                if self.version_manager and target in self.version_manager.config.get("modules", {}):
                    mod_data = self.version_manager.config["modules"][target]
                    context_parts.append(f"Type: {mod_data.get('type')}")
                    context_parts.append(f"Taxonomy: {' > '.join(mod_data.get('taxonomy', {}).get('hierarchy', []))}")
                    context_parts.append(f"Features: {', '.join(mod_data.get('features', []))}")
                
                if os.path.isfile(target):
                    try:
                        with open(target, 'r') as f:
                            head = f.read(500)
                            context_parts.append(f"Source Preview:\n{head}...")
                    except: pass
                context_parts.append("")

            # 4. Backup/Restoration Lineage (Lineage Argumentation)
            if self.version_manager and target:
                # We need to resolve relative path if stored as absolute in manifest
                history = self.version_manager.get_backup_history(target)
                if history:
                    context_parts.append("--- Restoration Lineage (Health over Time) ---")
                    for entry in history[-5:]: # Last 5 events
                        context_parts.append(f"- {entry.get('timestamp', 'N/A')}: {entry.get('backup_name', 'N/A')}")
                    context_parts.append("")

            # 5. Os_Toolkit Latest State (Read from latest manifest)
            # #TODO: Read from babel_data/profile/manifests/manifest_*.json instead of subprocess call
            #        Latest manifest contains: metadata, taxonomic_tree, artifacts, journal_entries
            try:
                manifests_dir = self.version_root / "profile" / "manifests"
                if manifests_dir.exists():
                    # Find latest manifest_*.json (not system_package_manifest.json)
                    manifest_files = sorted(
                        [f for f in manifests_dir.glob("manifest_*.json") if "system_package" not in f.name],
                        key=lambda x: x.stat().st_mtime,
                        reverse=True
                    )
                    if manifest_files:
                        latest_manifest = manifest_files[0]
                        with open(latest_manifest, 'r') as f:
                            manifest_data = json.load(f)

                        context_parts.append("--- Os_Toolkit: Latest State ✅ ---")
                        context_parts.append(f"Manifest: {latest_manifest.name}")

                        # Extract metadata
                        meta = manifest_data.get("metadata", {})
                        context_parts.append(f"Session: {meta.get('session_id', 'unknown')}")
                        context_parts.append(f"Generated: {meta.get('generated', 'unknown')}")
                        stats = meta.get("statistics", {})
                        context_parts.append(f"Stats: {stats.get('artifacts', 0)} artifacts, {stats.get('journal_entries', 0)} journal entries")

                        # Extract recent journal entries (last 5)
                        journal = manifest_data.get("journal", [])
                        if journal:
                            context_parts.append("\nRecent Journal Entries:")
                            for entry in journal[-5:]:
                                entry_type = entry.get('type', 'unknown')
                                content = entry.get('content', '')[:80]
                                context_parts.append(f"  • [{entry_type}] {content}")

                        context_parts.append("")
                        available_sources.append("os_toolkit")
                        self.engine.log_debug(f"#[Event:CONTEXT_OS_TOOLKIT] Loaded manifest {latest_manifest.name}", "DEBUG")
                    else:
                        context_parts.append("--- Os_Toolkit: Latest State ⚠️ (No manifests found) ---")
                        context_parts.append("")
                else:
                    context_parts.append("--- Os_Toolkit: Latest State ⚠️ (Manifest dir missing) ---")
                    context_parts.append("")
            except json.JSONDecodeError as e:
                context_parts.append("--- Os_Toolkit: Latest State ⚠️ (Invalid JSON) ---")
                context_parts.append(f"Error: {str(e)[:100]}")
                context_parts.append("")
                self.engine.log_debug(f"#[Event:CONTEXT_OS_TOOLKIT_ERROR] JSONDecodeError: {e}", "DEBUG")
            except Exception as e:
                context_parts.append("--- Os_Toolkit: Latest State ⚠️ (Load Failed) ---")
                context_parts.append(f"Error: {str(e)[:100]}")
                context_parts.append("")
                self.engine.log_debug(f"#[Event:CONTEXT_OS_TOOLKIT_ERROR] {type(e).__name__}: {e}", "DEBUG")

            # 6. Todo Lifecycle Summary (Read from plans/todos.json)
            # #TODO: Read directly from plans/todos.json synced by Os_Toolkit sync_all_todos
            #        Shows latest 10 pending/in_progress tasks for current context
            try:
                # plans/ is at Babel_v01a root, not babel_data/
                todos_file = self.babel_root / "plans" / "todos.json"
                self.engine.log_debug(f"#[Event:CONTEXT_TODOS] Checking: {todos_file}", "DEBUG")

                if todos_file.exists():
                    self.engine.log_debug(f"#[Event:CONTEXT_TODOS] File exists, reading...", "DEBUG")
                    with open(todos_file, 'r') as f:
                        todos_data = json.load(f)

                    context_parts.append("--- Todo Lifecycle Summary ✅ ---")

                    # Count by status
                    pending = [t for t in todos_data if t.get('status') in ['pending', 'open', 'todo']]
                    in_progress = [t for t in todos_data if t.get('status') in ['in_progress', 'active', 'in-progress']]
                    completed = [t for t in todos_data if t.get('status') in ['completed', 'done', 'closed']]

                    context_parts.append(f"✅ Completed: {len(completed)}")
                    context_parts.append(f"○ Pending: {len(pending)}")
                    context_parts.append(f"◐ In Progress: {len(in_progress)}")

                    # Show selected todos OR latest 10 if none selected
                    if self.selected_todo_ids:
                        selected_tasks = [t for t in todos_data if t.get('id') in self.selected_todo_ids]
                        if selected_tasks:
                            context_parts.append(f"\n✓ Selected Tasks ({len(selected_tasks)}):")
                            for task in selected_tasks:
                                status_icon = "◐" if task.get('status') in ['in_progress', 'active', 'in-progress'] else "○"
                                if task.get('status') in ['completed', 'done', 'closed']:
                                    status_icon = "✅"
                                title = task.get('title', 'Untitled')[:60]
                                task_id = task.get('id', '?')
                                desc = task.get('description', '')[:100]
                                context_parts.append(f"  {status_icon} #{task_id}: {title}")
                                if desc:
                                    context_parts.append(f"      → {desc}")
                    else:
                        # Default: Show latest 10 pending/in_progress tasks
                        active_tasks = (in_progress + pending)[:10]
                        if active_tasks:
                            context_parts.append("\nActive Tasks (Latest 10):")
                            for task in active_tasks:
                                status_icon = "◐" if task.get('status') in ['in_progress', 'active', 'in-progress'] else "○"
                                title = task.get('title', 'Untitled')[:60]
                                task_id = task.get('id', '?')
                                context_parts.append(f"  {status_icon} #{task_id}: {title}")

                    context_parts.append("")
                    available_sources.append("todos")
                    self.engine.log_debug(f"#[Event:CONTEXT_TODOS] Loaded {len(todos_data)} todos successfully", "INFO")
                else:
                    context_parts.append("--- Todo Lifecycle Summary ⚠️ (File not found) ---")
                    context_parts.append(f"Expected: {todos_file}")
                    context_parts.append("")
                    self.engine.log_debug(f"#[Event:CONTEXT_TODOS_ERROR] File not found: {todos_file}", "WARNING")
            except json.JSONDecodeError as e:
                context_parts.append("--- Todo Lifecycle Summary ⚠️ (Invalid JSON) ---")
                context_parts.append(f"Error: {str(e)[:100]}")
                context_parts.append("")
                self.engine.log_debug(f"#[Event:CONTEXT_TODOS_ERROR] JSONDecodeError: {e}", "DEBUG")
            except Exception as e:
                context_parts.append("--- Todo Lifecycle Summary ⚠️ (Load Failed) ---")
                context_parts.append(f"Error: {str(e)[:100]}")
                context_parts.append("")
                self.engine.log_debug(f"#[Event:CONTEXT_TODOS_ERROR] {type(e).__name__}: {e}", "DEBUG")

            # 7. Morph Suggestions (Low Resource Engine - graceful fallback)
            # #TODO: Morph is an EXTERNAL project with GUI right-click context feature extraction.
            #        It allows users to right-click objects in GUI applications and extract feature data.
            #        Future: Integrate morph_profiles/ as USB module drop-in for portable context loading.
            #        Currently attempts to read morph_suggestions.json if available.
            morph_available = False
            try:
                # Try babel_data/providers/morph first (USB module location)
                morph_profiles = self.version_root / "babel_data" / "providers" / "morph" / "morph_profiles"
                sugg_path = morph_profiles / "morph_suggestions.json"
                if not sugg_path.exists():
                    # Fallback to old location
                    sugg_path = self.version_root / "modules" / "morph" / "morph_profiles" / "morph_suggestions.json"

                if sugg_path.exists():
                    with open(sugg_path, 'r') as f:
                        sdata = json.load(f)
                    context_parts.append("--- Morph Suggestions Engine ✅ ---")
                    context_parts.append(f"Traits: {', '.join(sdata.get('intents', []))}")
                    context_parts.append(f"Current Hook: {sdata.get('hooks', {}).get('health', 'N/A')}")
                    context_parts.append("")
                    morph_available = True
                    available_sources.append("morph")
                    self.engine.log_debug(f"#[Event:CONTEXT_MORPH] Loaded from {sugg_path}", "DEBUG")
                else:
                    context_parts.append("--- Morph Suggestions Engine ⚠️ (Not Found) ---")
                    context_parts.append(f"Expected: {morph_profiles / 'morph_suggestions.json'}")
                    context_parts.append("")
                    self.engine.log_debug(f"#[Event:CONTEXT_MORPH] Not found at {sugg_path}", "DEBUG")
            except FileNotFoundError as e:
                context_parts.append("--- Morph Suggestions Engine ⚠️ (Files Missing) ---")
                context_parts.append("")
                self.engine.log_debug(f"#[Event:CONTEXT_MORPH_ERROR] FileNotFoundError: {e}", "DEBUG")
            except json.JSONDecodeError as e:
                context_parts.append("--- Morph Suggestions Engine ⚠️ (Invalid JSON) ---")
                context_parts.append(f"Error parsing: {str(e)[:100]}")
                context_parts.append("")
                self.engine.log_debug(f"#[Event:CONTEXT_MORPH_ERROR] JSONDecodeError: {e}", "DEBUG")
            except Exception as e:
                context_parts.append("--- Morph Suggestions Engine ⚠️ (Unavailable) ---")
                context_parts.append(f"Error: {type(e).__name__}: {str(e)[:100]}")
                context_parts.append("")
                self.engine.log_debug(f"#[Event:CONTEXT_MORPH_ERROR] {type(e).__name__}: {e}", "DEBUG")

            # 8. Log context
            log_path = self.version_root / "logs" / "unified_traceback.log"
            if log_path.exists():
                context_parts.append(f"Log Reference: {log_path.name}")

            context_str = "\n".join(context_parts)

            # #[Event:CONTEXT_GATHER_SUCCESS]
            log_to_traceback(EventCategory.CHAT, "context_gather_success",
                           {"target": self.target_var.get(), "size": len(context_str)},
                           {"status": "completed", "sources": available_sources})

            self.engine.log_debug(f"#[Event:CONTEXT_GATHER_SUCCESS] Size: {len(context_str)} chars, Sources: {available_sources}", "INFO")
            return context_str, available_sources

        except Exception as e:
            self.engine.log_debug(f"#[Event:CONTEXT_GATHER_ERROR] {e}", "ERROR")
            log_to_traceback(EventCategory.ERROR, "context_gather_error",
                           {"target": self.target_var.get()},
                           error=str(e))
            return "Context gathering failed", []

    def _count_todos(self) -> int:
        """Count total todos from todos.json"""
        try:
            todos_file = self.babel_root / "plans" / "todos.json"
            if todos_file.exists():
                with open(todos_file, 'r') as f:
                    todos_data = json.load(f)
                return len(todos_data)
        except Exception:
            pass
        return 0

    def _load_all_todos(self) -> list:
        """Load all todos from todos.json"""
        try:
            todos_file = self.babel_root / "plans" / "todos.json"
            if todos_file.exists():
                with open(todos_file, 'r') as f:
                    todos_data = json.load(f)
                return todos_data
        except Exception as e:
            self.engine.log_debug(f"#[Event:TODO_LOAD_ERROR] {e}", "ERROR")
            return []

    @ui_event_tracker("todo_selector_opened")
    def _show_todo_selector(self):
        """Show popup window to select todos for context priming

        #TODO: Future enhancements:
        - Colorize todo types (feature, bug, refactor, etc.)
        - Pull deltas for todos by pooling plan and diff information
        - Add [+][-] buttons for routing/collecting todos for other tasks
        - Integrate with Os_Toolkit actions for marking todos by code routing
        """
        todos = self._load_all_todos()
        if not todos:
            self._add_chat_response("⚠️ No todos.json found")
            return

        # Create popup window
        # FIXED: [BUG_20260209_174728] Changed self.root → self (self IS the root Tk window)
        popup = tk.Toplevel(self)
        popup.title(f"📋 Todo Selector - {len(todos)} Total")
        popup.geometry("700x500")
        popup.configure(bg=self.config.BG_COLOR)

        # Header with stats
        header_frame = tk.Frame(popup, bg=self.config.BG_COLOR)
        header_frame.pack(fill=tk.X, padx=10, pady=10)

        # Count by status
        pending = [t for t in todos if t.get('status') in ['pending', 'open', 'todo']]
        in_progress = [t for t in todos if t.get('status') in ['in_progress', 'active', 'in-progress']]
        completed = [t for t in todos if t.get('status') in ['completed', 'done', 'closed']]

        tk.Label(header_frame, text=f"✅ {len(completed)} | ◐ {len(in_progress)} | ○ {len(pending)}",
                 bg=self.config.BG_COLOR, fg=self.config.FG_COLOR, font=('Arial', 10, 'bold')).pack(side=tk.LEFT)

        tk.Label(header_frame, text=f"Selected: {len(self.selected_todo_ids)}",
                 bg=self.config.BG_COLOR, fg=self.config.ACCENT_COLOR, font=('Arial', 10, 'bold')).pack(side=tk.RIGHT)

        # Scrollable list frame
        list_frame = tk.Frame(popup, bg='#2a2a2a')
        list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        # Scrollbar
        scrollbar = tk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Canvas for scrolling
        canvas = tk.Canvas(list_frame, bg='#2a2a2a', highlightthickness=0, yscrollcommand=scrollbar.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=canvas.yview)

        # Frame inside canvas
        todo_list_frame = tk.Frame(canvas, bg='#2a2a2a')
        canvas_window = canvas.create_window((0, 0), window=todo_list_frame, anchor='nw')

        # Track checkbutton variables
        todo_vars = {}

        # Add todos to list
        for i, todo in enumerate(todos):
            todo_id = todo.get('id', f'todo_{i}')
            title = todo.get('title', 'Untitled')
            desc = todo.get('description', 'No description')
            status = todo.get('status', 'unknown')

            # Status icon and color
            if status in ['completed', 'done', 'closed']:
                icon = "✅"
                fg_color = "#6d6d6d"  # Gray for completed
            elif status in ['in_progress', 'active', 'in-progress']:
                icon = "◐"
                fg_color = "#ffaa00"  # Orange for in progress
            else:
                icon = "○"
                fg_color = self.config.FG_COLOR  # White for pending

            # Create frame for each todo
            todo_frame = tk.Frame(todo_list_frame, bg='#2a2a2a')
            todo_frame.pack(fill=tk.X, pady=2, padx=5)

            # Checkbox variable
            var = tk.BooleanVar(value=(todo_id in self.selected_todo_ids))
            todo_vars[todo_id] = var

            # Checkbox
            cb = tk.Checkbutton(todo_frame, variable=var, bg='#2a2a2a', fg=fg_color,
                               selectcolor='#1a1a1a', activebackground='#2a2a2a',
                               command=lambda tid=todo_id, v=var: self._toggle_todo_selection(tid, v))
            cb.pack(side=tk.LEFT)

            # Todo info
            info_text = f"{icon} #{todo_id}: {title[:50]}"
            info_label = tk.Label(todo_frame, text=info_text, bg='#2a2a2a', fg=fg_color,
                                  font=('Arial', 9), anchor='w')
            info_label.pack(side=tk.LEFT, fill=tk.X, expand=True)

            # Hover to show description
            tooltip_text = f"Description: {desc[:200]}"
            self._create_tooltip(info_label, tooltip_text)

        # Update scroll region
        todo_list_frame.update_idletasks()
        canvas.config(scrollregion=canvas.bbox('all'))

        # Button frame
        button_frame = tk.Frame(popup, bg=self.config.BG_COLOR)
        button_frame.pack(fill=tk.X, padx=10, pady=10)

        # Select All / Clear All buttons
        tk.Button(button_frame, text="Select Top 10", bg='#2d4d3d', fg=self.config.FG_COLOR,
                  command=lambda: self._select_top_n_todos(10, todos, todo_vars, popup)).pack(side=tk.LEFT, padx=5)

        tk.Button(button_frame, text="Clear All", bg='#4d2d2d', fg=self.config.FG_COLOR,
                  command=lambda: self._clear_all_todos(todo_vars, popup)).pack(side=tk.LEFT, padx=5)

        # Close button
        tk.Button(button_frame, text="✓ Done", bg=self.config.ACCENT_COLOR, fg='black',
                  font=('Arial', 10, 'bold'), command=popup.destroy).pack(side=tk.RIGHT, padx=5)

        # Update button label count
        self.todo_list_btn.config(text=f"📋 Todos: [{len(todos)}] ({len(self.selected_todo_ids)} selected)")

    def _toggle_todo_selection(self, todo_id, var):
        """Toggle todo selection for context"""
        if var.get():
            if todo_id not in self.selected_todo_ids:
                self.selected_todo_ids.append(todo_id)
        else:
            if todo_id in self.selected_todo_ids:
                self.selected_todo_ids.remove(todo_id)

        # Update button
        total = self._count_todos()
        self.todo_list_btn.config(text=f"📋 Todos: [{total}] ({len(self.selected_todo_ids)} selected)")

    def _select_top_n_todos(self, n, todos, todo_vars, popup):
        """Select top N in-progress and pending todos"""
        self.selected_todo_ids.clear()

        # Filter active todos
        in_progress = [t for t in todos if t.get('status') in ['in_progress', 'active', 'in-progress']]
        pending = [t for t in todos if t.get('status') in ['pending', 'open', 'todo']]
        active = (in_progress + pending)[:n]

        for todo in active:
            todo_id = todo.get('id')
            if todo_id:
                self.selected_todo_ids.append(todo_id)
                if todo_id in todo_vars:
                    todo_vars[todo_id].set(True)

        # Update button
        total = self._count_todos()
        self.todo_list_btn.config(text=f"📋 Todos: [{total}] ({len(self.selected_todo_ids)} selected)")

    def _clear_all_todos(self, todo_vars, popup):
        """Clear all selected todos"""
        self.selected_todo_ids.clear()
        for var in todo_vars.values():
            var.set(False)

        # Update button
        total = self._count_todos()
        self.todo_list_btn.config(text=f"📋 Todos: [{total}] ({len(self.selected_todo_ids)} selected)")

    def _create_tooltip(self, widget, text):
        """Create a simple tooltip for a widget"""
        def on_enter(event):
            tooltip = tk.Toplevel()
            tooltip.wm_overrideredirect(True)
            tooltip.wm_geometry(f"+{event.x_root+10}+{event.y_root+10}")
            label = tk.Label(tooltip, text=text, background="#ffffe0", relief=tk.SOLID,
                            borderwidth=1, font=('Arial', 8), wraplength=400, justify=tk.LEFT)
            label.pack()
            widget.tooltip = tooltip

        def on_leave(event):
            if hasattr(widget, 'tooltip'):
                widget.tooltip.destroy()
                del widget.tooltip

        widget.bind('<Enter>', on_enter)
        widget.bind('<Leave>', on_leave)

    @ui_event_tracker("chat_message_send")
    def _send_chat_message(self):
        """Send a chat message with provider routing"""
        message = self.chat_input.get().strip()
        if not message:
            return

        # Get provider and model
        provider = self.chat_provider.get()
        model = self.chat_model.get() if hasattr(self, 'chat_model') else None

        # Check for warning models
        if model and model.startswith("⚠️"):
            self._add_chat_response(f"⚠️ {provider} not available. Please check installation.")
            return

        # Prepare message with context if enabled (PRIMED - show routing)
        final_message = message
        context_str = ""
        if self.context_view_var.get():
            # #[Event:CONTEXT_ATTACHING]
            self.engine.log_debug(f"#[Event:CONTEXT_ATTACHING] Wrapping context with message", "INFO")

            # Show debug in chat
            self.chat_messages.config(state=tk.NORMAL)
            self.chat_messages.insert(tk.END, f"\n🔋 🐛 Context ATTACHING to message...\n")
            self.chat_messages.config(state=tk.DISABLED)

            context_str, available_sources = self._gather_full_context()
            # Wrap context in special tags
            context_id = datetime.now().strftime("%Y%m%d_%H%M%S")
            final_message = f"</Context_Pack_{context_id}>: [\n{context_str}\n] <Context_Pack/>.\n\n{message}"

            # Show FULL PACKET PREVIEW with tags visible
            sources_str = ", ".join(available_sources) if available_sources else "None available"
            self.chat_messages.config(state=tk.NORMAL)
            self.chat_messages.insert(tk.END, f"\n{'─'*50}\n")
            self.chat_messages.insert(tk.END, f"📦 FULL PACKET PREVIEW (SENDING)\n")
            self.chat_messages.insert(tk.END, f"{'─'*50}\n")
            self.chat_messages.insert(tk.END, f"Provider: {provider} | Model: {model}\n")
            self.chat_messages.insert(tk.END, f"Sources: {sources_str}\n")
            self.chat_messages.insert(tk.END, f"Context Size: {len(context_str)} chars\n")
            self.chat_messages.insert(tk.END, f"Message Size: {len(message)} chars\n")
            self.chat_messages.insert(tk.END, f"Total Size: {len(final_message)} chars\n")
            self.chat_messages.insert(tk.END, f"{'─'*50}\n\n")

            # Show wrapped packet structure with tags
            self.chat_messages.insert(tk.END, f"</Primed>: [\n")
            self.chat_messages.insert(tk.END, f"  </Context_Pack_{context_id}>: [\n")
            # Preview first 500 chars of context
            preview_context = context_str[:500] + ("..." if len(context_str) > 500 else "")
            for line in preview_context.split('\n'):
                self.chat_messages.insert(tk.END, f"    {line}\n")
            if len(context_str) > 500:
                self.chat_messages.insert(tk.END, f"    ... ({len(context_str) - 500} more chars)\n")
            self.chat_messages.insert(tk.END, f"  ] <Context_Pack/>.\n\n")
            self.chat_messages.insert(tk.END, f"  Your message: \"{message}\"\n")
            self.chat_messages.insert(tk.END, f"] <Primed/>.\n\n")
            self.chat_messages.insert(tk.END, f"{'─'*50}\n")

            # Show routing info
            self.chat_messages.insert(tk.END, f"   ✅ Wrapped in </Context_Pack_{context_id}>\n")
            self.chat_messages.insert(tk.END, f"   • Original message: {len(message)} chars\n")
            self.chat_messages.insert(tk.END, f"   • Context payload: {len(context_str)} chars\n")
            self.chat_messages.insert(tk.END, f"   • Sources loaded: {sources_str}\n")
            self.chat_messages.insert(tk.END, f"   • Final message: {len(final_message)} chars\n")
            self.chat_messages.insert(tk.END, f"   → Routing to: {provider} ({model})\n")
            self.chat_messages.config(state=tk.DISABLED)

            # #[Event:CONTEXT_ATTACHED]
            log_to_traceback(EventCategory.CHAT, "context_attached",
                           {"provider": provider, "context_size": len(context_str), "total_size": len(final_message)},
                           {"status": "wrapped", "context_id": context_id, "sources": available_sources})

        # Add user message to chat
        self.chat_messages.config(state=tk.NORMAL)
        self.chat_messages.insert(tk.END, f"\n[You] {message}\n")
        self.chat_messages.config(state=tk.DISABLED)
        self.chat_messages.see(tk.END)

        # Clear input
        self.chat_input.delete(0, tk.END)

        # Save to session.jsonl with full metadata and context packet
        session_entry = {
            "timestamp": datetime.now().isoformat(),
            "role": "user",
            "provider": provider,
            "model": model,
            "message": message,  # User's actual input
            "context_primed": bool(context_str),
            "context_size": len(context_str) if context_str else 0,
            "full_message": final_message  # Context wrapper + message
        }

        # Include context packet separately for audit if primed
        if context_str:
            session_entry["context_packet"] = {
                "context_id": datetime.now().strftime("%Y%m%d_%H%M%S"),
                "sources": available_sources if 'available_sources' in locals() else [],
                "content": context_str  # Full 1444 chars context
            }

        self._save_to_session(session_entry)

        # Log to traceback
        self.engine.log_debug(f"Chat [{provider}]: {message[:50]}", "INFO")
        log_to_traceback(EventCategory.CHAT, "send_message",
                       {"provider": provider, "model": model, "message": message[:50]},
                       {"status": "sent", "context_included": bool(context_str)})

        # PROVIDER ROUTING
        if provider == "Claude":
            self._send_to_claude(final_message, model)
        elif provider == "Gemini":
            self._send_to_gemini(final_message, model)
        elif provider == "Ollama":
            self._send_to_ollama(final_message, model, context_str)
        elif provider == "Morph":
            self._send_to_morph(final_message, model, context_str)
        elif provider == "Bi-Hemi":
            # Detect GGUF path for bi-hemi launch
            _gguf_dir = Path(__file__).parents[7] / "Models" / "Morph0.1-10m-Babble" / "exports" / "gguf"
            _gguf_files = sorted(_gguf_dir.glob("*.gguf")) if _gguf_dir.exists() else []
            _gguf_path = str(_gguf_files[-1]) if _gguf_files else None
            self._send_to_bihemi(_gguf_path)
        else:
            self._add_chat_response(f"⚠️ Unknown provider: {provider}")

    def _send_to_claude(self, message: str, model: str):
        """Send message to Claude CLI with comprehensive logging"""
        # #[Event:CLAUDE_SEND_START]
        log_to_traceback(EventCategory.CHAT, "claude_send_start",
                       {"model": model, "message_len": len(message)},
                       {"status": "initiating"})

        try:
            # Build command: flags first, then prompt as final argument
            cwd = str(self._get_cli_working_directory())
            cmd = [
                'claude',
                '--print',
                '--add-dir', str(Path.home() / 'plans'),
                '--add-dir', cwd
            ]

            # Add model if specified
            if model and model != "Claude (CLI)" and "claude" in model.lower():
                cmd.extend(['--model', model])

            # Prompt must be last argument
            cmd.append(message)

            self._add_chat_response(f"🤖 [Claude] Thinking...")
            self.engine.log_debug(f"#[Event:CLAUDE_CMD] {' '.join(cmd[:3])}...", "INFO")

            # Run command
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)

            if result.returncode == 0:
                response = result.stdout.strip()
                self._add_chat_response(f"[Claude] {response}")

                # #[Event:CLAUDE_SEND_SUCCESS]
                log_to_traceback(EventCategory.CHAT, "claude_send_success",
                               {"model": model, "response_len": len(response)},
                               {"status": "completed", "returncode": 0})
            else:
                error = result.stderr.strip() or "Unknown error"
                self._add_chat_response(f"⚠️ Claude error: {error[:200]}")

                # #[Event:CLAUDE_SEND_ERROR]
                log_to_traceback(EventCategory.ERROR, "claude_send_error",
                               {"model": model, "returncode": result.returncode},
                               error=error[:200])

        except FileNotFoundError as e:
            self._add_chat_response("⚠️ Claude CLI not found. Install: https://docs.anthropic.com/claude/docs/cli")
            log_to_traceback(EventCategory.ERROR, "claude_cli_not_found",
                           {"cwd": cwd}, error=str(e))
        except subprocess.TimeoutExpired as e:
            self._add_chat_response("⚠️ Claude request timed out (120s)")
            log_to_traceback(EventCategory.ERROR, "claude_timeout",
                           {"model": model, "timeout": 120}, error=str(e))
        except Exception as e:
            self._add_chat_response(f"⚠️ Claude error: {str(e)[:200]}")
            log_to_traceback(EventCategory.ERROR, "claude_exception",
                           {"model": model}, error=str(e))

    def _send_to_gemini(self, message: str, model: str):
        """Send message to Gemini CLI with comprehensive logging"""
        # #[Event:GEMINI_SEND_START]
        log_to_traceback(EventCategory.CHAT, "gemini_send_start",
                       {"model": model, "message_len": len(message)},
                       {"status": "initiating"})

        try:
            cmd = ['gemini', '-p', message]

            # Add model if specified
            if model and model != "Gemini (CLI)":
                cmd.insert(1, '-m')
                cmd.insert(2, model)

            self._add_chat_response(f"🤖 [Gemini] Thinking...")
            self.engine.log_debug(f"#[Event:GEMINI_CMD] {' '.join(cmd[:3])}...", "INFO")

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)

            if result.returncode == 0:
                response = result.stdout.strip()
                self._add_chat_response(f"[Gemini] {response}")

                # #[Event:GEMINI_SEND_SUCCESS]
                log_to_traceback(EventCategory.CHAT, "gemini_send_success",
                               {"model": model, "response_len": len(response)},
                               {"status": "completed", "returncode": 0})
            else:
                error = result.stderr.strip() or "Unknown error"
                self._add_chat_response(f"⚠️ Gemini error: {error[:200]}")

                # #[Event:GEMINI_SEND_ERROR]
                log_to_traceback(EventCategory.ERROR, "gemini_send_error",
                               {"model": model, "returncode": result.returncode},
                               error=error[:200])

        except FileNotFoundError as e:
            self._add_chat_response("⚠️ Gemini CLI not found or API key missing")
            log_to_traceback(EventCategory.ERROR, "gemini_cli_not_found",
                           {}, error=str(e))
        except subprocess.TimeoutExpired as e:
            self._add_chat_response("⚠️ Gemini request timed out (120s)")
            log_to_traceback(EventCategory.ERROR, "gemini_timeout",
                           {"model": model, "timeout": 120}, error=str(e))
        except Exception as e:
            self._add_chat_response(f"⚠️ Gemini error: {str(e)[:200]}")
            log_to_traceback(EventCategory.ERROR, "gemini_exception",
                           {"model": model}, error=str(e))

    def _send_to_ollama(self, message: str, model: str, context_str: str):
        """Send message to Ollama backend with comprehensive logging"""
        # #[Event:OLLAMA_SEND_START]
        log_to_traceback(EventCategory.CHAT, "ollama_send_start",
                       {"model": model, "message_len": len(message)},
                       {"status": "initiating"})

        # Check if backend available
        if not self.chat_backend:
            self._add_chat_response("⚠️ Ollama backend not available. Install: pip install ollama")
            log_to_traceback(EventCategory.ERROR, "ollama_backend_unavailable",
                           {}, error="Backend not initialized")
            return

        if not model or model == "No models available":
            self._add_chat_response("⚠️ No Ollama model selected. Run: ollama pull llama3.1")
            log_to_traceback(EventCategory.ERROR, "ollama_no_model",
                           {}, error="No model selected")
            return

        # Set up callbacks with logging
        def on_response(response):
            self.after(0, lambda: self._add_chat_response(f"[Ollama] {response}"))
            # #[Event:OLLAMA_SEND_SUCCESS]
            log_to_traceback(EventCategory.CHAT, "ollama_send_success",
                           {"model": model, "response_len": len(response)},
                           {"status": "completed"})

        def on_error(error):
            self.after(0, lambda: self._add_chat_response(f"⚠️ Ollama: {error}"))
            # #[Event:OLLAMA_SEND_ERROR]
            log_to_traceback(EventCategory.ERROR, "ollama_send_error",
                           {"model": model}, error=error)

        self.chat_backend.on_response = on_response
        self.chat_backend.on_error = on_error

        # Update context
        context_data = {
            "provider": "Ollama",
            "cwd": self._get_cli_working_directory()
        }
        if context_str:
            context_data["active_context"] = context_str

        self.engine.log_debug(f"#[Event:OLLAMA_CONTEXT_UPDATE] CWD: {context_data['cwd']}", "DEBUG")
        self.chat_backend.update_context(context_data)
        self.chat_backend.send_message(message, model=model)

    def _send_to_morph(self, message: str, model: str, context_str: str):
        """Send message to Morph — detects local GGUF and routes to llama_cpp, else shows stub."""
        # Step 1: Detect local GGUF export
        _gguf_dir = Path(__file__).parents[7] / "Models" / "Morph0.1-10m-Babble" / "exports" / "gguf"
        _gguf_files = sorted(_gguf_dir.glob("*.gguf")) if _gguf_dir.exists() else []

        if not _gguf_files:
            # No GGUF found — show profile info as fallback
            profile = self.morph_profile_var.get()
            workflow = self.morph_workflow_var.get()
            self._add_chat_response(
                f"⚠️ No Morph GGUF found at:\n  {_gguf_dir}\n"
                f"Profile: {profile}  Workflow: {workflow}\n"
                f"Export a GGUF first: Models tab → Morph model → 📦 Exports."
            )
            return

        # Step 2: Load OsToolkitGroundingBridge for Omega grounding context
        _grounded = {}
        _gap_sev = 'low'
        try:
            _bdir = str(Path(__file__).parents[4] / "regex_project" / "activities" / "tools" / "scripts")
            if _bdir not in sys.path:
                sys.path.insert(0, _bdir)
            from activity_integration_bridge import OsToolkitGroundingBridge
            _grounded = OsToolkitGroundingBridge(Path(__file__).parents[7]).load()
            _gap_sev = _grounded.get('gap_severity', 'low')
            _hot = _grounded.get('temporal_hot_spots', [])[:3]
            _probe_fails = len(_grounded.get('probe_failures', []))
        except Exception as _e:
            _hot = []
            _probe_fails = 0
            self.engine.log_debug(f"#[Event:MORPH_GROUNDING_FAIL] {_e}", "WARNING")

        # Step 3: llama_cpp inference in a thread (to avoid blocking UI)
        _gguf_path = str(_gguf_files[-1])
        _gguf_name = _gguf_files[-1].name

        def _run_inference():
            try:
                from llama_cpp import Llama
                _llm = Llama(model_path=_gguf_path, n_ctx=2048, n_threads=4, verbose=False)
                _prompt = (
                    f"<|im_start|>user\n{message}<|im_end|>\n"
                    f"<|im_start|>assistant\n"
                )
                _out = _llm(
                    _prompt,
                    max_tokens=512,
                    temperature=0.7,
                    stop=["<|im_end|>", "</s>", "<|im_start|>"],
                )
                _resp = _out['choices'][0]['text'].strip()
                _header = (
                    f"🟣 [Morph GGUF: {_gguf_name}]\n"
                    f"   gap:{_gap_sev}  probe_fails:{_probe_fails}  hot_files:{len(_hot)}\n"
                )
                self._add_chat_response(_header + _resp)
                # Log to event stream
                self.engine.log_debug(
                    f"#[Event:MORPH_GGUF_RESPONSE] gap={_gap_sev} len={len(_resp)}", "INFO"
                )
            except Exception as _exc:
                self._add_chat_response(f"⚠️ Morph GGUF inference failed: {_exc}")
                self.engine.log_debug(f"#[Event:MORPH_GGUF_ERROR] {_exc}", "ERROR")

        self._add_chat_response(f"⏳ [Morph GGUF: {_gguf_name}] Inferring (gap:{_gap_sev})...")
        import threading
        threading.Thread(target=_run_inference, daemon=True).start()

    def _send_to_bihemi(self, gguf_path: str = None):
        """Spawn bi-hemi (Omega+Alpha) CLI session in a subprocess."""
        import subprocess as _sp
        _orchestrator = Path(__file__).parents[4] / "regex_project" / "orchestrator.py"
        if not _orchestrator.exists():
            self._add_chat_response(f"⚠️ orchestrator.py not found at:\n  {_orchestrator}")
            return
        _cmd = [sys.executable, str(_orchestrator), "--bi-hemi"]
        if gguf_path:
            _cmd += ["--gguf-path", gguf_path]
        try:
            _sp.Popen(_cmd, cwd=str(_orchestrator.parent))
            self._add_chat_response(
                f"🔵 [Bi-Hemi] Launched orchestrator.py --bi-hemi\n"
                f"  Session will save to: babel_data/sessions/session_bihemi_*.txt\n"
                f"  Use the Session dropdown above to view saved sessions."
            )
        except Exception as _e:
            self._add_chat_response(f"⚠️ Failed to spawn bi-hemi: {_e}")

    def _load_sessions(self):
        """Load list of available chat sessions"""
        try:
            # Determine session directory (same logic as guillm/chat_backend)
            # Try version root first, then project root
            base_dir = self.version_root
            sess_dir = base_dir / "sessions"
            
            if not sess_dir.exists():
                return []
                
            sessions = []
            for f in sorted(sess_dir.glob("session_*.txt"), key=os.path.getmtime, reverse=True):
                # Format: session_20240119_123045.txt -> 20240119_123045
                session_id = f.stem.replace("session_", "")
                sessions.append(session_id)
            return sessions
        except Exception as e:
            self.engine.log_debug(f"Error loading sessions: {e}", "ERROR")
            return []

    def _on_session_selected(self, event=None):
        """Load selected session content"""
        session_id = self.chat_session_select.get()
        if not session_id: return
        
        try:
            base_dir = self.version_root
            sess_file = base_dir / "sessions" / f"session_{session_id}.txt"
            
            if sess_file.exists():
                with open(sess_file, 'r') as f:
                    content = f.read()
                
                self.chat_messages.config(state=tk.NORMAL)
                self.chat_messages.delete(1.0, tk.END)
                self.chat_messages.insert(tk.END, content)
                self.chat_messages.insert(tk.END, f"\n[{datetime.now().strftime('%H:%M:%S')}] System: Loaded session {session_id}\n")
                self.chat_messages.see(tk.END)
                self.chat_messages.config(state=tk.DISABLED)
                
                # Update backend context if needed
                if self.chat_backend:
                    self.chat_backend.update_context({"session_id": session_id})
        except Exception as e:
            self._add_traceback(f"Error loading session: {e}", "ERROR")

    def _new_session(self):
        """Start a new chat session - PRIMES session, file created on first Send"""
        try:
            # Clear chat
            self.chat_messages.config(state=tk.NORMAL)
            self.chat_messages.delete(1.0, tk.END)
            self.chat_messages.insert(tk.END, "💬 Quick Chat Ready\n")
            self.chat_messages.insert(tk.END, "─" * 40 + "\n")
            self.chat_messages.config(state=tk.DISABLED)

            # Re-initialize (PRIME) new session
            self._init_session()

            # Log event
            log_to_traceback(EventCategory.SESSION, "new_session_button_clicked",
                           {"session_id": self.current_session_id},
                           {"status": "primed", "user_initiated": True})
            
            # Log to Traceback
            log_to_traceback(EventCategory.SESSION, "new_session", 
                           {"session_id": new_id}, 
                           {"status": "created"})
                           
            # Log to Uni_Launch Debug
            try:
                sys.path.insert(0, str(self.version_root.parent / "modules"))
                from launcher_integration import log_to_launcher
                log_to_launcher(f"New Chat Session: {new_id}", "INFO", "grep_flight")
            except:
                pass
                
        except Exception as e:
            self._add_traceback(f"Error creating session: {e}", "ERROR")

    def _copy_chat_output(self):
        """Copy current chat output to clipboard"""
        try:
            content = self.chat_messages.get(1.0, tk.END)
            self.clipboard_clear()
            self.clipboard_append(content)
            self.status_var.set("📋 Chat output copied to clipboard")
        except Exception as e:
            self._add_traceback(f"Error copying chat: {e}", "ERROR")

    def _copy_target_path(self):
        """Copy current target path to clipboard"""
        target = self.target_var.get()
        if target:
            try:
                self.clipboard_clear()
                self.clipboard_append(target)
                self.status_var.set(f"📋 Copied: {os.path.basename(target)}")
            except Exception as e:
                self._add_traceback(f"Clipboard Error: {e}", "ERROR")
        else:
            self.status_var.set("⚠️ No target to copy")

    def _refresh_session_list(self):
        """Refresh the session dropdown values"""
        if hasattr(self, 'chat_session_select'):
            sessions = self._load_sessions()
            self.chat_session_select['values'] = sessions

    @ui_event_tracker("model_selected")
    def _on_chat_model_selected(self):
        """Handle model selection"""
        model = self.chat_model.get()
        if model == "Gemini (CLI)":
            self._launch_gemini_terminal()
        elif model == "Claude (CLI)":
            self._launch_claude_terminal()

        # Update primed display if session exists
        if hasattr(self, 'current_session_id'):
            provider = self.chat_provider.get() if hasattr(self, 'chat_provider') else "Unknown"
            self._update_primed_display(provider, model)

    def _update_chat_input_display(self, action_name: str, result_status: str, target: str, context_log: str = ""):
        """
        Format tool execution result and push to chat input line.
        Format: What: Ran Tool {[Name]} | Result: [Pass/Fail] | Where: Target-/path/ | Why: Log... | How: {Profile} | When: TIME
        """
        try:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            profile_id = getattr(self, 'active_profile', 'Default')
            
            # Construct the formatted string
            log_ref = context_log or "See Traceback"
            
            formatted_text = (
                f"What: Ran Tool {{[{action_name}]}} | "
                f"Result: [{result_status}] | "
                f"Where: Target-{target} | "
                f"Why: {log_ref} | "
                f"How: {{{profile_id}}} | "
                f"When: {timestamp}"
            )
            
            # Update last tool context state
            self.last_tool_context = {
                "action": action_name,
                "status": result_status,
                "target": target,
                "profile": profile_id,
                "timestamp": timestamp,
                "log_ref": log_ref,
                "raw_text": formatted_text
            }
            
            # Ensure chat input is enabled and clear it
            if hasattr(self, 'chat_input'):
                self.chat_input.config(state=tk.NORMAL)
                self.chat_input.delete(0, tk.END)
                self.chat_input.insert(0, formatted_text)
                # Optional: Highlight or flash the input to draw attention
                self.chat_input.config(bg='#2d4d3d') # Slight green tint
                self.after(500, lambda: self.chat_input.config(bg='#2a2a2a')) # Restore
                
        except Exception as e:
            self.engine.log_debug(f"Error updating chat input: {e}", "ERROR")

    def _get_cli_working_directory(self) -> str:
        """
        Get appropriate working directory for CLI launch
        Priority: target > project > version workspace
        """
        # Priority 1: If target is set
        if self.target_var.get():
            target = Path(self.target_var.get())
            if target.is_dir():
                self._add_traceback(f"📂 CLI WorkDir: Target directory: {target}", "INFO")
                return str(target)
            elif target.is_file():
                work_dir = str(target.parent)
                self._add_traceback(f"📂 CLI WorkDir: Target file parent: {work_dir}", "INFO")
                return work_dir

        # Priority 2: If project is set via app_ref
        if self.app_ref and hasattr(self.app_ref, 'current_project'):
            project = self.app_ref.current_project
            if project and Path(project).exists():
                self._add_traceback(f"📂 CLI WorkDir: Project root: {project}", "INFO")
                return str(project)

        # Priority 3: Default to version workspace
        default_workspace = self.version_root / ".docv2_workspace"
        self._add_traceback(f"📂 CLI WorkDir: Default workspace: {default_workspace}", "INFO")
        return str(default_workspace)

    def _toggle_gemini_terminal(self):
        """Toggle Gemini CLI visibility/state"""
        # Check if running
        if self.gemini_proc and self.gemini_proc.poll() is None:
            # Running -> Toggle Visibility
            if not hasattr(self, 'gemini_wid') or not self.gemini_wid:
                self.gemini_wid = self._find_gemini_window_id()

            if self.gemini_wid:
                try:
                    # Toggle hidden state (Minimize/Restore)
                    # We also try to activate it when restoring to ensure focus
                    # But toggle,hidden is a single command.
                    # Let's try simple toggle first.
                    cmd = ["wmctrl", "-i", "-r", self.gemini_wid, "-b", "toggle,hidden"]
                    subprocess.Popen(cmd)

                    # If we just un-hid it, we should also raise it
                    # This is tricky without knowing if we just hid or unhid.
                    # We'll just run the toggle.
                    self.status_var.set("🤖 Gemini CLI Toggled")
                except Exception as e:
                    self._add_traceback(f"Error toggling Gemini: {e}", "ERROR")
            else:
                self._add_traceback("Gemini running but window not found yet", "WARNING")
        else:
            # Not running, launch it
            self._launch_gemini_terminal()

    def _launch_gemini_terminal(self):
        """Launch Gemini CLI in a positioned terminal (Left side)"""
        if self.gemini_proc and self.gemini_proc.poll() is None:
            self._add_traceback("Gemini CLI already running", "WARNING")
            return

        # Generate session ID
        if not hasattr(self, '_cli_session_counter'):
            self._cli_session_counter = 0
        self._cli_session_counter += 1
        session_id = f"Session#{self._cli_session_counter}/gemini"

        try:
            screen_height = self.winfo_screenheight()

            panel_height = self.winfo_height()
            if self.is_expanded:
                panel_height = self.config.EXPANDED_HEIGHT

            x_pos = 20
            y_pos = screen_height - panel_height - 450

            if y_pos < 0: y_pos = 0

            geometry = f"100x30+{x_pos}+{y_pos}"

            # Determine working directory
            work_dir = self._get_cli_working_directory()

            self._add_traceback(f"🚀 {session_id} | Launching at {geometry}", "INFO")

            cmd = [
                "xfce4-terminal",
                "--title=Gemini CLI",
                "--hold",
                f"--geometry={geometry}",
                f"--working-directory={work_dir}",
                "--command=gemini"
            ]
            self.engine.log_debug(f"Launch command: {cmd}", "DEBUG")

            self.gemini_proc = subprocess.Popen(cmd)
            self.status_var.set(f"🤖 {session_id} Active")

            # Log session to traceback
            log_to_traceback(EventCategory.INFO, "cli_session_start", {
                "session": session_id,
                "cli": "gemini",
                "target": self.target_var.get() if self.target_var.get() else None,
                "work_dir": work_dir
            }, {"launched": True})

        except Exception as e:
            self._add_traceback(f"❌ {session_id} Failed: {e}", "ERROR")
            messagebox.showerror("Error", f"Failed to launch Gemini CLI:\n{e}")

    def _show_ai_cli_menu(self):
        """Show popup menu to select AI CLI (Gemini or Claude)"""
        menu = tk.Menu(self, tearoff=0, bg=self.config.BG_COLOR, fg=self.config.FG_COLOR)

        # Gemini option with status
        gemini_status = "Running" if (self.gemini_proc and self.gemini_proc.poll() is None) else "Launch"
        menu.add_command(
            label=f"🤖 Gemini CLI [{gemini_status}]",
            command=self._toggle_gemini_terminal
        )

        # Claude option with status
        claude_status = "Running" if (hasattr(self, 'claude_proc') and self.claude_proc and self.claude_proc.poll() is None) else "Launch"
        menu.add_command(
            label=f"🧠 Claude CLI [{claude_status}]",
            command=self._toggle_claude_terminal
        )

        menu.add_separator()

        # Context injection option
        menu.add_command(
            label="📋 Copy Target Context to Clipboard",
            command=self._copy_context_for_ai
        )

        # Show menu at mouse position
        try:
            menu.tk_popup(self.winfo_pointerx(), self.winfo_pointery())
        finally:
            menu.grab_release()

    def _toggle_claude_terminal(self):
        """Toggle Claude CLI visibility/state"""
        if not hasattr(self, 'claude_proc'):
            self.claude_proc = None
            self.claude_wid = None

        if self.claude_proc and self.claude_proc.poll() is None:
            # Running -> Toggle Visibility
            if not hasattr(self, 'claude_wid') or not self.claude_wid:
                self.claude_wid = self._find_claude_window_id()

            if self.claude_wid:
                try:
                    cmd = ["wmctrl", "-i", "-r", self.claude_wid, "-b", "toggle,hidden"]
                    subprocess.Popen(cmd)
                    self.status_var.set("🧠 Claude CLI Toggled")
                except Exception as e:
                    self._add_traceback(f"Error toggling Claude: {e}", "ERROR")
            else:
                self._add_traceback("Claude running but window not found yet", "WARNING")
        else:
            self._launch_claude_terminal()

    def _launch_claude_terminal(self):
        """Launch Claude CLI in a positioned terminal (Right side of Gemini)"""
        if hasattr(self, 'claude_proc') and self.claude_proc and self.claude_proc.poll() is None:
            self._add_traceback("Claude CLI already running", "WARNING")
            return

        # Generate session ID
        if not hasattr(self, '_cli_session_counter'):
            self._cli_session_counter = 0
        self._cli_session_counter += 1
        session_id = f"Session#{self._cli_session_counter}/claude"

        try:
            screen_width = self.winfo_screenwidth()
            screen_height = self.winfo_screenheight()

            panel_height = self.winfo_height()
            if self.is_expanded:
                panel_height = self.config.EXPANDED_HEIGHT

            # Position: Right side (opposite to Gemini which is on left)
            x_pos = screen_width - 820
            y_pos = screen_height - panel_height - 450

            if y_pos < 0: y_pos = 0

            geometry = f"100x30+{x_pos}+{y_pos}"

            # Find claude binary - check common locations
            claude_paths = [
                os.path.expanduser("~/.claude/local/node_modules/.bin/claude"),
                "/usr/local/bin/claude",
                "claude"  # fallback to PATH
            ]
            claude_bin = None
            for p in claude_paths:
                if os.path.exists(p):
                    claude_bin = p
                    break
            if not claude_bin:
                claude_bin = "claude"  # hope it's in PATH

            # Determine working directory
            work_dir = self._get_cli_working_directory()

            self._add_traceback(f"🚀 {session_id} | Launching at {geometry}", "INFO")

            cmd = [
                "xfce4-terminal",
                "--title=Claude CLI",
                "--hold",
                f"--geometry={geometry}",
                f"--working-directory={work_dir}",
                f"--command={claude_bin}"
            ]
            self.engine.log_debug(f"Launch command: {cmd}", "DEBUG")

            self.claude_proc = subprocess.Popen(cmd)
            self.status_var.set(f"🧠 {session_id} Active")

            # Log session to traceback
            log_to_traceback(EventCategory.INFO, "cli_session_start", {
                "session": session_id,
                "cli": "claude",
                "binary": claude_bin,
                "work_dir": work_dir,
                "target": self.target_var.get() if self.target_var.get() else None
            }, {"launched": True})

        except Exception as e:
            self._add_traceback(f"❌ {session_id} Failed: {e}", "ERROR")
            messagebox.showerror("Error", f"Failed to launch Claude CLI:\n{e}")

    def _find_claude_window_id(self):
        """Find the Window ID for the Claude terminal using PID"""
        if not hasattr(self, 'claude_proc') or not self.claude_proc:
            return None
        try:
            target_pid = str(self.claude_proc.pid)
            result = subprocess.run(["wmctrl", "-lp"], capture_output=True, text=True)
            for line in result.stdout.strip().split('\n'):
                parts = line.split()
                if len(parts) >= 3:
                    wid, _, pid = parts[0], parts[1], parts[2]
                    if pid == target_pid:
                        return wid
            # Fallback: search by title
            for line in result.stdout.strip().split('\n'):
                if "Claude CLI" in line:
                    return line.split()[0]
        except Exception as e:
            self.engine.log_debug(f"Error finding Claude window: {e}", "WARNING")
        return None

    def _sync_claude_position(self, panel_y):
        """Sync Claude terminal position with panel movement"""
        if not hasattr(self, 'claude_proc') or not self.claude_proc or self.claude_proc.poll() is not None:
            return
        if not hasattr(self, 'claude_wid') or not self.claude_wid:
            self.claude_wid = self._find_claude_window_id()
            if not self.claude_wid:
                return
        try:
            screen_width = self.winfo_screenwidth()
            screen_height = self.winfo_screenheight()
            panel_height = self.config.EXPANDED_HEIGHT if self.is_expanded else self.config.PANEL_HEIGHT

            x_pos = screen_width - 820
            y_pos = panel_y - 450
            if y_pos < 0: y_pos = 0

            cmd = ["wmctrl", "-i", "-r", self.claude_wid, "-e", f"0,{x_pos},{y_pos},-1,-1"]
            subprocess.run(cmd, capture_output=True)
        except Exception as e:
            self.engine.log_debug(f"Error syncing Claude position: {e}", "DEBUG")

    def _copy_context_for_ai(self):
        """Copy current target context to clipboard for AI CLI usage"""
        try:
            context_parts = []

            if hasattr(self, 'action_panel_context') and self.action_panel_context:
                ctx = self.action_panel_context
                context_parts.append(f"Target: {ctx.get('target_path', 'Not set')}")
                context_parts.append(f"Directory: {ctx.get('target_dir', 'Not set')}")
                context_parts.append(f"Type: {ctx.get('target_type', 'Unknown')}")
                context_parts.append(f"Version: {ctx.get('version_root', 'Unknown')}")
            else:
                target = self.target_var.get() if hasattr(self, 'target_var') else ""
                context_parts.append(f"Target: {target or 'Not set'}")

            context_text = "\n".join(context_parts)
            self.clipboard_clear()
            self.clipboard_append(context_text)

            self.status_var.set("📋 Context copied to clipboard")
            self._add_traceback(f"📋 Copied context:\n{context_text}", "INFO")

        except Exception as e:
            self._add_traceback(f"Error copying context: {e}", "ERROR")

    def _add_chat_response(self, response):
        """Add a response to chat and save to session"""
        self.chat_messages.config(state=tk.NORMAL)
        self.chat_messages.insert(tk.END, f"[Assistant] {response}\n")
        self.chat_messages.config(state=tk.DISABLED)
        self.chat_messages.see(tk.END)

        # Save assistant response to session
        self._save_to_session({
            "timestamp": datetime.now().isoformat(),
            "role": "assistant",
            "provider": self.chat_provider.get() if hasattr(self, 'chat_provider') else "unknown",
            "message": response
        })

    def _update_primed_display(self, provider, model):
        """Update primed session display when provider/model changes mid-session"""
        # Show update in chat
        self.chat_messages.config(state=tk.NORMAL)
        self.chat_messages.insert(tk.END, f"\n")
        self.chat_messages.insert(tk.END, f"{'─'*50}\n")
        self.chat_messages.insert(tk.END, f"🔄 PROVIDER/MODEL UPDATED\n")
        self.chat_messages.insert(tk.END, f"{'─'*50}\n")
        self.chat_messages.insert(tk.END, f"Session: {self.current_session_id}\n")
        self.chat_messages.insert(tk.END, f"Provider: {provider}\n")
        self.chat_messages.insert(tk.END, f"Model: {model}\n")
        self.chat_messages.insert(tk.END, f"Status: ✅ SAME SESSION (Click 'New' for new session)\n")
        self.chat_messages.insert(tk.END, f"{'─'*50}\n\n")
        self.chat_messages.config(state=tk.DISABLED)

        # Log event
        log_to_traceback(EventCategory.SESSION, "provider_model_updated",
                       {"session_id": self.current_session_id, "provider": provider, "model": model},
                       {"status": "updated", "session_continues": True})

    @ui_event_tracker("new_session")
    def _new_session(self):
        """Create a new session (user-triggered)"""
        # Archive old session info
        old_session_id = getattr(self, 'current_session_id', None)

        # Clear session state
        if hasattr(self, 'current_session_id'):
            delattr(self, 'current_session_id')
        if hasattr(self, 'current_session_file'):
            delattr(self, 'current_session_file')
        if hasattr(self, 'session_primed'):
            delattr(self, 'session_primed')
        if hasattr(self, 'session_saved'):
            delattr(self, 'session_saved')

        # Re-initialize
        self._init_session()

        # Show notification
        self.chat_messages.config(state=tk.NORMAL)
        self.chat_messages.insert(tk.END, f"\n{'─'*50}\n")
        self.chat_messages.insert(tk.END, f"🆕 NEW SESSION CREATED\n")
        self.chat_messages.insert(tk.END, f"{'─'*50}\n")
        if old_session_id:
            self.chat_messages.insert(tk.END, f"Previous: {old_session_id}\n")
        self.chat_messages.insert(tk.END, f"New: {self.current_session_id}\n")
        self.chat_messages.insert(tk.END, f"{'─'*50}\n\n")
        self.chat_messages.config(state=tk.DISABLED)

        # Log
        log_to_traceback(EventCategory.SESSION, "new_session_created",
                       {"old_session": old_session_id, "new_session": self.current_session_id},
                       {"status": "created"})

    def _init_session(self):
        """Initialize (PRIME) session metadata - file created on first Send"""
        # Create session ID and metadata
        self.current_session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        session_dir = self.version_root / "sessions"
        session_dir.mkdir(parents=True, exist_ok=True)
        self.current_session_file = session_dir / f"session_{self.current_session_id}.jsonl"
        self.session_primed = True
        self.session_saved = False  # Track if file actually created

        # Get current provider/model
        provider = self.chat_provider.get() if hasattr(self, 'chat_provider') else "Unknown"
        model = self.chat_model.get() if hasattr(self, 'chat_model') else "Not selected"

        # Display session init in chat
        self.chat_messages.config(state=tk.NORMAL)
        self.chat_messages.insert(tk.END, f"\n")
        self.chat_messages.insert(tk.END, f"{'='*50}\n")
        self.chat_messages.insert(tk.END, f"📝 SESSION PRIMED\n")
        self.chat_messages.insert(tk.END, f"{'='*50}\n")
        self.chat_messages.insert(tk.END, f"Session ID: {self.current_session_id}\n")
        self.chat_messages.insert(tk.END, f"Provider: {provider}\n")
        self.chat_messages.insert(tk.END, f"Model: {model}\n")
        self.chat_messages.insert(tk.END, f"Path: {self.current_session_file}\n")
        self.chat_messages.insert(tk.END, f"Status: ⏳ WAITING FOR FIRST SEND\n")
        self.chat_messages.insert(tk.END, f"{'='*50}\n\n")
        self.chat_messages.config(state=tk.DISABLED)

        # Log to traceback
        log_to_traceback(EventCategory.SESSION, "session_primed",
                       {"session_id": self.current_session_id, "provider": provider, "model": model},
                       {"status": "primed", "path": str(self.current_session_file), "file_created": False})
        self.engine.log_debug(f"#[Event:SESSION_PATH] {self.current_session_file}", "INFO")

        # Update session dropdown to show primed session
        if hasattr(self, 'chat_session_select'):
            self.chat_session_select.set(f"PRIMED: {self.current_session_id}")

    def _save_to_session(self, entry: dict):
        """Save message to session.jsonl - creates file on FIRST save"""
        try:
            # Ensure session is initialized
            if not hasattr(self, 'current_session_id'):
                self._init_session()

            # Check if this is FIRST save (file creation)
            is_first_save = not hasattr(self, 'session_saved') or not self.session_saved

            if is_first_save:
                # Mark as file now created
                self.session_saved = True

                # Update chat to show file CREATED
                self.chat_messages.config(state=tk.NORMAL)
                self.chat_messages.insert(tk.END, f"\n")
                self.chat_messages.insert(tk.END, f"✅ SESSION FILE CREATED\n")
                self.chat_messages.insert(tk.END, f"   Path: {self.current_session_file}\n")
                self.chat_messages.insert(tk.END, f"   Status: 📝 SAVING\n\n")
                self.chat_messages.config(state=tk.DISABLED)

                # Log file creation
                log_to_traceback(EventCategory.SESSION, "session_file_created",
                               {"session_id": self.current_session_id, "path": str(self.current_session_file)},
                               {"status": "file_created", "first_save": True})

                # Update dropdown
                if hasattr(self, 'chat_session_select'):
                    self.chat_session_select.set(f"ACTIVE: {self.current_session_id}")

            # Add event marker to entry for audit
            entry['_event_mark'] = f"SESSION_ENTRY_{entry.get('role', 'unknown').upper()}"

            # Append as JSON Line
            with open(self.current_session_file, 'a') as f:
                f.write(json.dumps(entry, indent=None) + '\n')

            # #[Event:SESSION_SAVE]
            role = entry.get('role')
            provider = entry.get('provider', 'unknown')
            context_primed = entry.get('context_primed', False)
            self.engine.log_debug(
                f"#[Event:SESSION_SAVE] Role: {role}, Provider: {provider}, Context: {context_primed}",
                "DEBUG"
            )

        except Exception as e:
            self.engine.log_debug(f"#[Event:SESSION_SAVE_ERROR] {e}", "ERROR")
            log_to_traceback(EventCategory.ERROR, "session_save_failed",
                           {"session_id": getattr(self, 'current_session_id', 'unknown')},
                           error=str(e))

            # Show error in chat
            self.chat_messages.config(state=tk.NORMAL)
            self.chat_messages.insert(tk.END, f"\n⚠️ Session save failed: {str(e)[:100]}\n")
            self.chat_messages.config(state=tk.DISABLED)

    def _on_session_switch(self):
        """Handle session type switch (Plan/Task)"""
        if not self.chat_backend:
            return

        session_type = self.chat_session_type.get().lower()
        if session_type != self.chat_backend.session_type:
            self.chat_backend.switch_session_type(session_type)
            self.engine.log_debug(f"Switched to {session_type} session", "INFO")
            log_to_traceback(EventCategory.CHAT, "session_switch",
                           {"from": self.chat_backend.session_type, "to": session_type},
                           {"status": "switched"})

            # Clear messages and show new session info
            self.chat_messages.config(state=tk.NORMAL)
            self.chat_messages.insert(tk.END, f"\n─" * 40 + "\n")
            self.chat_messages.insert(tk.END, f"📋 Switched to {session_type.upper()} session\n")
            self.chat_messages.insert(tk.END, f"─" * 40 + "\n")
            self.chat_messages.config(state=tk.DISABLED)
            self.chat_messages.see(tk.END)

    def _clear_chat(self):
        """Clear chat messages"""
        if self.chat_backend:
            self.chat_backend.clear_history()

        self.chat_messages.config(state=tk.NORMAL)
        self.chat_messages.delete(1.0, tk.END)
        self.chat_messages.insert(tk.END, "💬 Quick Chat Ready\n")
        self.chat_messages.insert(tk.END, "─" * 40 + "\n")
        self.chat_messages.config(state=tk.DISABLED)

    @ui_event_tracker("provider_changed")
    def _on_provider_changed(self, event=None, update_primed=False):
        """Handle provider selection change"""
        provider = self.chat_provider.get()
        self._add_traceback(f"🔄 Provider changed to: {provider}", "INFO")

        # Show/Hide Morph Profile Selector
        if provider in ["Morph", "Manual", "Bi-Hemi"]:
            self.morph_profile_frame.pack(side=tk.RIGHT, padx=(10, 0))
        else:
            self.morph_profile_frame.pack_forget()

        self._update_available_models()

        # Update primed session display if requested
        if update_primed and hasattr(self, 'current_session_id'):
            model = self.chat_model.get() if hasattr(self, 'chat_model') else "Not selected"
            self._update_primed_display(provider, model)

        # Log to uni_launcher
        try:
            sys.path.insert(0, str(self.version_root.parent / "modules"))
            from launcher_integration import log_to_launcher
            log_to_launcher(f"Chat provider changed to: {provider}", "INFO", "grep_flight")
        except:
            pass

    def _refresh_morph_profiles(self):
        """Load available morph profiles from directory"""
        try:
            # Search order: 1. babel_data/providers/morph, 2. relative path
            current_dir = os.path.dirname(os.path.abspath(__file__))

            # Try babel_data first (for USB drop-in modules)
            babel_morph = os.path.abspath(os.path.join(current_dir, '..', '..', 'providers', 'morph', 'morph_profiles'))
            if os.path.exists(babel_morph):
                prof_dir = babel_morph
            else:
                # Fallback to original relative path
                prof_dir = os.path.abspath(os.path.join(current_dir, '..', '..', 'morph', 'morph_profiles'))

            profiles = [f.stem for f in Path(prof_dir).glob("*.json")] if os.path.exists(prof_dir) else []

            if not profiles:
                self._add_traceback(f"⚠️ No Morph profiles found. Drop profiles in: babel_data/providers/morph/morph_profiles/", "WARNING")

            self.morph_profile_menu['values'] = sorted(profiles) if profiles else ["No profiles found"]
            if profiles and not self.morph_profile_var.get():
                self.morph_profile_var.set(profiles[0])
                self._refresh_morph_workflows()
        except Exception as e:
            self.engine.log_debug(f"Morph profile refresh failed: {e}", "WARNING")

    def _refresh_morph_workflows(self):
        """Load workflows for the current morph profile"""
        profile_id = self.morph_profile_var.get()
        if not profile_id or profile_id == "No profiles found":
            return

        try:
            current_dir = os.path.dirname(os.path.abspath(__file__))

            # Search babel_data first, then fallback
            babel_path = os.path.abspath(os.path.join(current_dir, '..', '..', 'providers', 'morph', 'morph_profiles', f"{profile_id}.json"))
            fallback_path = os.path.abspath(os.path.join(current_dir, '..', '..', 'morph', 'morph_profiles', f"{profile_id}.json"))

            prof_path = babel_path if os.path.exists(babel_path) else fallback_path

            if os.path.exists(prof_path):
                with open(prof_path, 'r') as f:
                    data = json.load(f)
                workflows = list(data.get("workflows", {}).keys())
                workflows = sorted(workflows)
                workflows.insert(0, "Router (Chat)")
                self.morph_workflow_menu['values'] = workflows

                # Default to Router if not set or not in list
                current = self.morph_workflow_var.get()
                if not current or current not in workflows:
                    self.morph_workflow_var.set("Router (Chat)")
            else:
                self._add_traceback(f"⚠️ Morph profile not found: {profile_id}", "WARNING")
        except Exception as e:
            self.engine.log_debug(f"Morph workflow refresh failed: {e}", "WARNING")

    def _update_available_models(self):
        """Update available models based on selected provider"""
        provider = self.chat_provider.get()
        models = []

        if provider == "Ollama":
            # Get Ollama models dynamically
            if self.chat_backend:
                try:
                    # Try getting from backend first
                    models = self.chat_backend.get_available_models()
                except:
                    pass
            
            # Fallback to subprocess if backend fails or returns empty (and to verify backend isn't hardcoded)
            if not models:
                try:
                    result = subprocess.run(['ollama', 'list'], capture_output=True, text=True, timeout=3)
                    if result.returncode == 0:
                        lines = result.stdout.strip().split('\n')
                        # Skip header (NAME ID SIZE MODIFIED)
                        if len(lines) > 1:
                            for line in lines[1:]:
                                parts = line.split()
                                if parts:
                                    models.append(parts[0])
                except FileNotFoundError:
                    self.engine.log_debug("Ollama CLI not found in PATH", "WARNING")
                    self._add_traceback("⚠️ Ollama not installed - Download from https://ollama.ai", "WARNING")
                except subprocess.TimeoutExpired:
                    self.engine.log_debug("Ollama check timed out", "WARNING")
                    self._add_traceback("⚠️ Ollama not responding", "WARNING")
                except Exception as e:
                    self.engine.log_debug(f"Ollama list failed: {e}", "WARNING")
                    self._add_traceback(f"⚠️ Ollama unavailable: {str(e)[:50]}", "WARNING")

            if not models:
                models = ["⚠️ Ollama not available", "Install from: https://ollama.ai"]

        elif provider == "Claude":
            models = [
                "Claude (CLI)",
                "claude-3-5-sonnet-20241022",
                "claude-3-opus-20240229",
                "claude-3-haiku-20240307",
                "claude-3-5-haiku-20241022"
            ]

        elif provider == "Gemini":
            models = [
                "Gemini (CLI)",
                "gemini-2.0-flash-exp",
                "gemini-1.5-pro-latest",
                "gemini-1.5-flash-latest",
                "gemini-1.5-pro",
                "gemini-1.5-flash",
                "gemini-1.0-pro"
            ]

        elif provider == "Morph":
            # Morph uses all available models from all providers
            models = ["🎨 Morph (Auto-route)"]
            
            # Aggregate from other providers
            # 1. Ollama
            ollama_models = []
            try:
                result = subprocess.run(['ollama', 'list'], capture_output=True, text=True, timeout=3)
                if result.returncode == 0:
                    lines = result.stdout.strip().split('\n')
                    if len(lines) > 1:
                        for line in lines[1:]:
                            parts = line.split()
                            if parts:
                                ollama_models.append(parts[0])
            except (FileNotFoundError, subprocess.TimeoutExpired):
                self._add_traceback("⚠️ Ollama unavailable for Morph aggregation", "DEBUG")
            except Exception as e:
                self.engine.log_debug(f"Morph: Ollama check failed: {e}", "DEBUG")
            
            if ollama_models:
                models.append("--- Ollama ---")
                models.extend(ollama_models)
                
            # 2. Gemini
            models.append("--- Gemini ---")
            models.extend([
                "gemini-2.0-flash-exp",
                "gemini-1.5-pro-latest", 
                "gemini-1.5-flash-latest"
            ])
            
            # 3. Claude
            models.append("--- Claude ---")
            models.extend([
                "claude-3-5-sonnet-20241022",
                "claude-3-opus-20240229"
            ])

        # Update combobox
        self.chat_model_menu['values'] = models
        if models:
            self.chat_model.set(models[0])
        else:
            self.chat_model.set("No models available")

        self._add_traceback(f"📋 Loaded {len(models)} models for {provider}", "DEBUG")
        self.engine.log_debug(f"📋 Loaded {len(models)} models for {provider}", "INFO")

    def _show_provider_config(self):
        """Show provider configuration dialog"""
        dialog = tk.Toplevel(self)
        dialog.title("Provider Configuration")
        dialog.geometry("500x400")
        dialog.configure(bg='#1e1e1e')
        dialog.transient(self)
        dialog.grab_set()

        tk.Label(dialog, text="⚙️ Provider Configuration",
                bg='#1e1e1e', fg='#4ec9b0',
                font=('Arial', 14, 'bold')).pack(pady=15)

        # Config frame
        config_frame = tk.Frame(dialog, bg='#1e1e1e')
        config_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        # Claude API Key
        tk.Label(config_frame, text="Claude API Key:",
                bg='#1e1e1e', fg='#d4d4d4',
                font=('Arial', 10, 'bold')).pack(anchor=tk.W, pady=(0, 5))
        claude_key_var = tk.StringVar(value=self._get_provider_config("claude", "api_key"))
        claude_entry = tk.Entry(config_frame, textvariable=claude_key_var,
                               bg='#2a2a2a', fg='#d4d4d4',
                               insertbackground='#d4d4d4',
                               show='*', width=50)
        claude_entry.pack(fill=tk.X, pady=(0, 15))

        # Gemini API Key
        tk.Label(config_frame, text="Gemini API Key:",
                bg='#1e1e1e', fg='#d4d4d4',
                font=('Arial', 10, 'bold')).pack(anchor=tk.W, pady=(0, 5))
        gemini_key_var = tk.StringVar(value=self._get_provider_config("gemini", "api_key"))
        gemini_entry = tk.Entry(config_frame, textvariable=gemini_key_var,
                               bg='#2a2a2a', fg='#d4d4d4',
                               insertbackground='#d4d4d4',
                               show='*', width=50)
        gemini_entry.pack(fill=tk.X, pady=(0, 15))

        # Ollama Host
        tk.Label(config_frame, text="Ollama Host:",
                bg='#1e1e1e', fg='#d4d4d4',
                font=('Arial', 10, 'bold')).pack(anchor=tk.W, pady=(0, 5))
        ollama_host_var = tk.StringVar(value=self._get_provider_config("ollama", "host", "http://localhost:11434"))
        ollama_entry = tk.Entry(config_frame, textvariable=ollama_host_var,
                               bg='#2a2a2a', fg='#d4d4d4',
                               insertbackground='#d4d4d4',
                               width=50)
        ollama_entry.pack(fill=tk.X, pady=(0, 15))

        # Save button
        def save_config():
            self._save_provider_config("claude", "api_key", claude_key_var.get())
            self._save_provider_config("gemini", "api_key", gemini_key_var.get())
            self._save_provider_config("ollama", "host", ollama_host_var.get())
            self._add_traceback("✅ Provider config saved", "INFO")
            dialog.destroy()

        tk.Button(dialog, text="Save Configuration",
                 command=save_config,
                 bg='#4ec9b0', fg='black',
                 font=('Arial', 11, 'bold'),
                 padx=20, pady=8).pack(pady=15)

    def _get_provider_config(self, provider: str, key: str, default: str = ""):
        """Get provider configuration value"""
        try:
            config_path = Path.home() / '.babel' / 'grep_flight_config.json'
            if config_path.exists():
                with open(config_path, 'r') as f:
                    config = json.load(f)
                    return config.get(provider, {}).get(key, default)
        except:
            pass
        return default

    def _save_provider_config(self, provider: str, key: str, value: str):
        """Save provider configuration value"""
        try:
            config_path = Path.home() / '.babel' / 'grep_flight_config.json'
            config_path.parent.mkdir(parents=True, exist_ok=True)

            config = {}
            if config_path.exists():
                with open(config_path, 'r') as f:
                    config = json.load(f)

            if provider not in config:
                config[provider] = {}
            config[provider][key] = value

            with open(config_path, 'w') as f:
                json.dump(config, f, indent=2)
        except Exception as e:
            self._add_traceback(f"❌ Failed to save provider config: {e}", "ERROR")

    def _target_chat_logs(self):
        """Target chat logs to traceback UI and uni_launcher"""
        self._add_traceback("📊 Targeting chat logs to traceback UI", "INFO")

        # Show traceback window
        if hasattr(self, 'traceback_window') and self.traceback_window.winfo_exists():
            self.traceback_window.deiconify()
            self.traceback_window.lift()

        # Copy chat messages to traceback
        chat_content = self.chat_messages.get(1.0, tk.END)
        for line in chat_content.split('\n'):
            if line.strip():
                self._add_traceback(f"💬 {line}", "INFO")

        # Send to uni_launcher debug tab
        try:
            sys.path.insert(0, str(self.version_root.parent / "modules"))
            from launcher_integration import log_to_launcher
            log_to_launcher("=== Chat Log Dump ===", "INFO", "grep_flight")
            for line in chat_content.split('\n'):
                if line.strip():
                    log_to_launcher(line, "INFO", "grep_flight_chat")
            log_to_launcher("=== End Chat Log ===", "INFO", "grep_flight")
        except Exception as e:
            self._add_traceback(f"⚠️ Could not send to uni_launcher: {e}", "WARNING")

    def _create_traceback_popup(self):
        """Create traceback/procedure popup window"""
        self.traceback_window = tk.Toplevel(self)
        self.traceback_window.title("Procedure Traceback")
        self.traceback_window.geometry("600x400")
        self.traceback_window.configure(bg=self.config.BG_COLOR)
        self.traceback_window.withdraw()  # Hidden initially
        
        # Make it stay on top
        self.traceback_window.attributes('-topmost', True)
        
        # Header
        header_frame = tk.Frame(self.traceback_window, bg=self.config.BG_COLOR, pady=10)
        header_frame.pack(fill=tk.X, padx=10)
        
        tk.Label(header_frame, text="🐛 Debug & Traceback Log [Ctrl+D / Ctrl+P]",
                font=('Arial', 12, 'bold'),
                bg=self.config.BG_COLOR,
                fg=self.config.ACCENT_COLOR).pack(side=tk.LEFT)

        tk.Button(header_frame, text="Export", command=self._export_traceback_log,
                 bg=self.config.HOVER_COLOR, fg=self.config.FG_COLOR).pack(side=tk.RIGHT, padx=(5, 0))

        tk.Button(header_frame, text="Clear", command=self._clear_traceback,
                 bg=self.config.HOVER_COLOR, fg=self.config.FG_COLOR).pack(side=tk.RIGHT)

        # Log path info
        log_path = self.babel_root / "babel_data" / "logs" / "unified_traceback.log"
        log_info_frame = tk.Frame(self.traceback_window, bg=self.config.BG_COLOR)
        log_info_frame.pack(fill=tk.X, padx=10, pady=(0, 5))
        tk.Label(log_info_frame, text=f"📂 Log: {log_path}",
                font=('Arial', 8),
                bg=self.config.BG_COLOR,
                fg='#888888').pack(side=tk.LEFT)

        # Traceback text
        self.traceback_text = scrolledtext.ScrolledText(
            self.traceback_window,
            bg='#2a2a2a',
            fg=self.config.FG_COLOR,
            insertbackground=self.config.FG_COLOR,
            font=('Monospace', 9)
        )
        self.traceback_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
        
        # Configure tags for different step types
        for step_type, color in self.config.WORKFLOW_COLORS.items():
            self.traceback_text.tag_config(step_type, foreground=color)
        
        # Additional Babel-specific tags
        babel_colors = {
            'COMMAND_EXEC': '#f1c40f',    # Yellow
            'MANIFEST_SAVED': '#2ecc71', # Green
            'CATALOG_SAVED': '#3498db',  # Blue
            'ORCHESTRATION_START': '#9b59b6', # Purple
            'PROFILE_SELECTED': '#e67e22', # Orange
            'SCRIPT_TREE_CLICK': '#7f8c8d', # Gray
            'ERROR': '#e74c3c',          # Red
            'WARNING': '#f39c12'         # Dark Yellow
        }
        for tag, color in babel_colors.items():
            self.traceback_text.tag_config(tag, foreground=color)
        
        # Close button
        tk.Button(self.traceback_window, text="Close",
                 command=self.traceback_window.withdraw,
                 bg=self.config.HOVER_COLOR, fg=self.config.FG_COLOR).pack(pady=(0, 10))

        # Bind Esc to close traceback window
        self.traceback_window.bind('<Escape>', lambda e: self.traceback_window.withdraw())

    def _export_traceback_log(self):
        """Export traceback/debug log with options for clipboard or file"""
        self.engine.log_debug("Export traceback log requested")

        # Create export options popup
        export_popup = tk.Toplevel(self.traceback_window)
        export_popup.title("Export Debug Log")
        export_popup.geometry("400x250")
        export_popup.configure(bg=self.config.BG_COLOR)
        export_popup.attributes('-topmost', True)

        # Header
        tk.Label(export_popup, text="📋 Export Debug Log",
                 bg=self.config.BG_COLOR, fg=self.config.FG_COLOR,
                 font=('Arial', 12, 'bold')).pack(pady=10)

        # Option: Include Os_Toolkit latest
        include_latest_var = tk.BooleanVar(value=True)
        tk.Checkbutton(export_popup, text="Include Os_Toolkit latest file changes",
                      variable=include_latest_var, bg=self.config.BG_COLOR,
                      fg=self.config.FG_COLOR, selectcolor='#2a2a2a',
                      activebackground=self.config.BG_COLOR).pack(pady=5)

        # Buttons frame
        button_frame = tk.Frame(export_popup, bg=self.config.BG_COLOR)
        button_frame.pack(pady=20)

        def export_to_clipboard():
            export_popup.destroy()
            self._do_export_log(to_clipboard=True, include_latest=include_latest_var.get())

        def export_to_file():
            export_popup.destroy()
            self._do_export_log(to_clipboard=False, include_latest=include_latest_var.get())

        # Export buttons
        tk.Button(button_frame, text="📋 Copy to Clipboard",
                 bg='#2d4d3d', fg=self.config.FG_COLOR, font=('Arial', 10),
                 width=18, command=export_to_clipboard).pack(side=tk.LEFT, padx=5)

        tk.Button(button_frame, text="💾 Save to File",
                 bg='#4d3d2d', fg=self.config.FG_COLOR, font=('Arial', 10),
                 width=18, command=export_to_file).pack(side=tk.LEFT, padx=5)

        # Cancel button
        tk.Button(export_popup, text="Cancel", bg='#4d2d2d', fg=self.config.FG_COLOR,
                 command=export_popup.destroy).pack(pady=10)

    def _do_export_log(self, to_clipboard: bool, include_latest: bool):
        """Perform the actual export with </Debug> wrapping"""
        try:
            # Get latest file changes if requested
            latest_output = ""
            if include_latest:
                self.engine.log_debug("Fetching Os_Toolkit latest...")
                try:
                    result = subprocess.run(
                        ['python3', 'Os_Toolkit.py', 'latest'],
                        cwd=str(self.babel_root),
                        capture_output=True,
                        text=True,
                        timeout=10
                    )
                    if result.returncode == 0:
                        latest_output = result.stdout
                        self.engine.log_debug("✅ Latest file changes fetched")
                    else:
                        latest_output = f"⚠️ Os_Toolkit latest failed: {result.stderr[:200]}"
                except Exception as e:
                    latest_output = f"⚠️ Failed to fetch latest: {e}"

            # Build wrapped export content
            export_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            export_id = datetime.now().strftime('%Y%m%d_%H%M%S')

            content_parts = []
            content_parts.append(f"</Debug_{export_id}>: [")
            content_parts.append("")
            content_parts.append("="*80)
            content_parts.append("GREP FLIGHT v2 - DEBUG & TRACEBACK LOG")
            content_parts.append(f"Exported: {export_date}")
            content_parts.append("="*80)
            content_parts.append("")

            # Latest file changes
            if include_latest and latest_output:
                content_parts.append("="*80)
                content_parts.append("LATEST FILE MODIFICATIONS (Os_Toolkit)")
                content_parts.append("-"*80)
                content_parts.append(latest_output)
                content_parts.append("")

            # Full debug log from engine
            content_parts.append("="*80)
            content_parts.append("FULL DEBUG LOG (from engine)")
            content_parts.append("-"*80)
            content_parts.append('\n'.join(self.engine.debug_log))
            content_parts.append("")

            # Traceback window contents
            content_parts.append("="*80)
            content_parts.append("TRACEBACK WINDOW CONTENTS")
            content_parts.append("-"*80)
            content_parts.append(self.traceback_text.get(1.0, tk.END))
            content_parts.append("")

            # Read from unified_traceback.log
            log_path = self.babel_root / "babel_data" / "logs" / "unified_traceback.log"
            if log_path.exists():
                content_parts.append("="*80)
                content_parts.append("UNIFIED TRACEBACK LOG (babel_data/logs/unified_traceback.log)")
                content_parts.append("-"*80)
                with open(log_path, 'r') as f:
                    # Get last 500 lines
                    lines = f.readlines()
                    content_parts.append(''.join(lines[-500:]))
                content_parts.append("")

            content_parts.append("] <Debug/>.")

            full_content = '\n'.join(content_parts)

            # Export to clipboard or file
            if to_clipboard:
                try:
                    import pyperclip
                    pyperclip.copy(full_content)
                    self.engine.log_debug("✅ Log copied to clipboard")
                    self.status_var.set("📋 Debug log copied to clipboard")
                except ImportError:
                    self.engine.log_debug("⚠️ pyperclip not installed")
                    self.status_var.set("⚠️ pyperclip not installed - use 'Save to File'")
            else:
                # Save to file
                self.attributes('-topmost', False)
                self.traceback_window.attributes('-topmost', False)

                try:
                    filename = filedialog.asksaveasfilename(
                        title="Export Debug/Traceback Log",
                        defaultextension=".log",
                        filetypes=[("Log files", "*.log"), ("Text files", "*.txt"), ("All files", "*.*")],
                        initialfile=f"debug_export_{export_id}.log",
                        parent=self.traceback_window
                    )
                finally:
                    self.attributes('-topmost', True)
                    self.traceback_window.attributes('-topmost', True)

                if filename:
                    with open(filename, 'w') as f:
                        f.write(full_content)
                    self.engine.log_debug(f"✅ Log exported to: {filename}")
                    self.status_var.set(f"💾 Exported to {Path(filename).name}")

        except Exception as e:
            self.engine.log_debug(f"Export failed: {e}")
            self.status_var.set(f"⚠️ Export failed: {e}")

    def _bind_events(self):
        """Bind keyboard shortcuts"""
        try:
            self.engine.log_debug("Binding keyboard shortcuts...")
            self.bind('<Control-b>', lambda e: self._toggle_expand())
            self.engine.log_debug("  Ctrl+B bound (toggle expand)")

            self.bind('<Control-t>', lambda e: self._browse_target())
            self.engine.log_debug("  Ctrl+T bound (browse target)")

            # Only bind if pattern_entry exists
            if hasattr(self, 'pattern_entry'):
                self.bind('<Control-f>', lambda e: self.pattern_entry.focus())
                self.engine.log_debug("  Ctrl+F bound (focus pattern)")
            else:
                self.engine.log_debug("  WARNING: pattern_entry not found, Ctrl+F not bound")

            self.bind('<Control-g>', lambda e: self._execute_grep())
            self.engine.log_debug("  Ctrl+G bound (execute grep)")

            self.bind('<Control-p>', lambda e: self._show_traceback())
            self.engine.log_debug("  Ctrl+P bound (show traceback)")

            self.bind('<Control-d>', lambda e: (print(">>> Ctrl+D PRESSED <<<"), self._show_traceback()))
            self.engine.log_debug("  Ctrl+D bound (show traceback - same as Ctrl+P)")

            self.bind('<Control-q>', lambda e: self._confirm_quit())
            self.engine.log_debug("  Ctrl+Q bound (quit with confirmation)")

            # Global Esc handler
            self.bind('<Escape>', self._handle_escape)
            self.engine.log_debug("  Esc bound (smart escape handler)")

            self.engine.log_debug("All keyboard shortcuts bound successfully")
        except Exception as e:
            print(f"ERROR binding events: {e}")
            import traceback
            traceback.print_exc()

    def _handle_escape(self, event=None):
        """Smart escape handler - closes popups or collapses panel"""
        self.engine.log_debug("Escape pressed")

        # Check if traceback/debug window is open and close it first
        if self.traceback_window.winfo_viewable():
            self.engine.log_debug("  Closing traceback/debug window")
            self.traceback_window.withdraw()
            return

        # If panel is expanded, collapse it
        if self.is_expanded:
            self.engine.log_debug("  Collapsing expanded panel")
            self._collapse_panel()
            return

        # If nothing else, do nothing (don't quit)
        self.engine.log_debug("  Nothing to close, Esc ignored")

    def _find_gemini_window_id(self):
        """Find the Window ID for the Gemini terminal using PID"""
        if not self.gemini_proc:
            return None
            
        try:
            target_pid = str(self.gemini_proc.pid)
            # wmctrl -lp lists windows with PIDs: 0xWID  Desktop PID  Machine Title
            output = subprocess.check_output(["wmctrl", "-lp"], text=True)
            # self.engine.log_debug(f"wmctrl -lp output:\n{output}", "DEBUG")
            
            for line in output.splitlines():
                parts = line.split()
                if len(parts) > 2:
                    wid = parts[0]
                    pid = parts[2]
                    # Match exact PID
                    if pid == target_pid:
                        self.engine.log_debug(f"Found Gemini Window ID: {wid} (PID match: {pid})", "INFO")
                        return wid
                        
            self.engine.log_debug(f"Gemini window for PID {target_pid} not found yet", "DEBUG")
        except Exception as e:
            self.engine.log_debug(f"Error finding Gemini window: {e}", "ERROR")
        return None

    def _sync_gemini_position(self, panel_y):
        """Move Gemini window relative to panel Y using wmctrl"""
        if not self.gemini_proc or self.gemini_proc.poll() is not None:
            return

        if not hasattr(self, 'gemini_wid') or not self.gemini_wid:
            self.gemini_wid = self._find_gemini_window_id()
            if not self.gemini_wid:
                # self.engine.log_debug("Sync pos skipped: Window ID not found yet", "DEBUG")
                return 

        # Calculate position
        term_height_px = 550 # approximate
        margin = 10
        
        y_pos = panel_y - term_height_px - margin
        if y_pos < 0: y_pos = 0
        x_pos = 20
        
        # wmctrl -i -r <WID> -e 0,x,y,w,h (-1 for no change to dim)
        try:
            cmd = ["wmctrl", "-i", "-r", self.gemini_wid, "-e", f"0,{x_pos},{y_pos},-1,-1"]
            self.engine.log_debug(f"Syncing Pos: {cmd}", "DEBUG")
            subprocess.Popen(cmd)
        except Exception as e:
            self.engine.log_debug(f"Error moving Gemini window: {e}", "ERROR")

    def _confirm_quit(self):
        """Quit with confirmation if processes running"""
        self.engine.log_debug("Quit requested")

        # Check if any background processes are running
        # (For now, just quit, but we can add process tracking later)
        self.engine.log_debug("Quitting application")
        self.quit()
        
    def _toggle_expand(self):
        """Legacy toggle support (e.g. Ctrl+B) - toggles between 0 and 1"""
        if self.expansion_state > 0:
            # Collapse to 0
            self.expansion_state = 0
        else:
            # Expand to 1
            self.expansion_state = 1
        self._update_expansion_ui()

    def _adjust_expansion(self, direction):
        """Adjust expansion state by direction (+1 or -1)"""
        new_state = self.expansion_state + direction
        if 0 <= new_state <= 2:
            self.expansion_state = new_state
            self._update_expansion_ui()
    
    def _update_expansion_ui(self):
        """Update UI based on current expansion state"""
        target_h = self.config.PANEL_HEIGHT
        
        # Sync legacy flag
        self.is_expanded = (self.expansion_state > 0)

        # Update button states & calculate target height
        if self.expansion_state == 0: # Collapsed
            self.btn_up.config(state='normal', fg=self.config.FG_COLOR)
            self.btn_down.config(state='disabled', fg='#555555')
            self.status_var.set("Ready - Click ▲ to expand")
            target_h = self.config.PANEL_HEIGHT
            
        elif self.expansion_state == 1: # Standard
            self.btn_up.config(state='normal', fg=self.config.FG_COLOR)
            self.btn_down.config(state='normal', fg=self.config.FG_COLOR)
            self.status_var.set("Standard View - ▲ for CLI Mode, ▼ to Collapse")
            target_h = self.config.PANEL_HEIGHT + self.config.EXPANDED_HEIGHT
            # Ensure expanded frame is visible
            if not self.expanded_frame.winfo_ismapped():
                self.expanded_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
                
        elif self.expansion_state == 2: # CLI Mode
            self.btn_up.config(state='disabled', fg='#555555')
            self.btn_down.config(state='normal', fg=self.config.FG_COLOR)
            self.status_var.set("CLI Mode (Full) - Click ▼ to reduce")
            target_h = self.config.PANEL_HEIGHT + self.config.CLI_HEIGHT
            # Ensure expanded frame is visible
            if not self.expanded_frame.winfo_ismapped():
                self.expanded_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        
        self.engine.log_debug(f"State set to {self.expansion_state}, target height: {target_h}")
        self._animate_panel(target_h)

    def _animate_panel(self, target_height):
        """Animate panel to target height"""
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        target_y = screen_height - target_height
        
        def animate():
            current_geom = self.winfo_geometry()
            # Parse current geometry (WIDTHxHEIGHT+X+Y)
            try:
                parts = current_geom.replace('x', '+').split('+')
                current_h = int(parts[1])
                current_y = int(parts[3])
            except:
                return # Window destroyed or error

            # Determine difference
            diff_h = target_height - current_h
            
            if abs(diff_h) <= 20:
                # Snap to final position
                self.geometry(f"{screen_width}x{target_height}+0+{target_y}")
                self._sync_gemini_position(target_y)
                try: self._sync_claude_position(target_y)
                except: pass
                
                # If fully collapsed, hide expanded frame
                if target_height == self.config.PANEL_HEIGHT:
                    self.expanded_frame.pack_forget()
                
                self.engine.log_debug("Animation complete")
                return

            # Calculate step
            step_h = 20 if diff_h > 0 else -20
            new_h = current_h + step_h
            new_y = current_y - step_h # If growing height, Y must decrease to stay anchored at bottom
            
            self.geometry(f"{screen_width}x{new_h}+0+{new_y}")
            self._sync_gemini_position(new_y)
            try: self._sync_claude_position(new_y)
            except: pass
            
            self.after(self.config.EXPAND_SPEED, animate)
            
        animate()
    
    def _update_indicators(self):
        """Update workflow indicators on collapsed panel"""
        if not self.indicator_canvas:
            return
            
        # Clear canvas
        self.indicator_canvas.delete("all")
        
        # Get recent workflow steps (last 10)
        recent_steps = self.engine.workflow_steps[-10:]
        
        # Calculate positions
        canvas_width = self.indicator_canvas.winfo_width()
        indicator_count = len(recent_steps)
        if indicator_count == 0:
            return
            
        total_width = (self.config.INDICATOR_RADIUS * 2 + self.config.INDICATOR_SPACING) * indicator_count
        start_x = (canvas_width - total_width) // 2
        
        # Draw indicators
        for i, step in enumerate(recent_steps):
            x = start_x + i * (self.config.INDICATOR_RADIUS * 2 + self.config.INDICATOR_SPACING)
            y = self.config.PANEL_HEIGHT // 2
            
            # Get color for step type
            step_type = step['type']
            color = self.config.WORKFLOW_COLORS.get(step_type, self.config.FG_COLOR)
            
            # Draw indicator
            self.indicator_canvas.create_oval(
                x - self.config.INDICATOR_RADIUS,
                y - self.config.INDICATOR_RADIUS,
                x + self.config.INDICATOR_RADIUS,
                y + self.config.INDICATOR_RADIUS,
                fill=color,
                outline=self.config.BORDER_COLOR
            )
            
            # Store indicator info for tooltips
            indicator_id = f"indicator_{i}"
            bbox = (
                x - self.config.INDICATOR_RADIUS,
                y - self.config.INDICATOR_RADIUS,
                x + self.config.INDICATOR_RADIUS,
                y + self.config.INDICATOR_RADIUS
            )
            
            # Bind tooltip
            self.indicator_canvas.tag_bind(indicator_id, '<Enter>', 
                                          lambda e, s=step: self._show_indicator_tooltip(e, s))
    
    def _show_indicator_tooltip(self, event, step):
        """Show tooltip for indicator"""
        # Create tooltip window
        tooltip = tk.Toplevel(self)
        tooltip.wm_overrideredirect(True)
        
        # Format step info
        time_str = datetime.fromisoformat(step['timestamp']).strftime("%H:%M:%S")
        text = f"{step['type']}\n{step['message']}\n{time_str}"
        
        label = tk.Label(tooltip, text=text, bg='yellow', fg='black', padx=5, pady=2)
        label.pack()
        
        # Position near mouse
        x, y = self.winfo_pointerxy()
        tooltip.geometry(f"+{x+10}+{y+10}")
        
        # Schedule removal
        tooltip.after(2000, tooltip.destroy)
    
    def _log_to_json(self, entry_type: str, data: dict):
        """Log an entry to log.json (non-blocking)"""
        def do_log():
            try:
                log_path = Path(__file__).parent / "log.json"

                # Load existing log (with size limit check)
                log_data = []
                if log_path.exists():
                    # Check file size before reading
                    if log_path.stat().st_size > 10 * 1024 * 1024:  # 10MB limit
                        # File too large, truncate to last 100 entries
                        log_data = []
                    else:
                        with open(log_path, 'r') as f:
                            log_data = json.load(f)

                # Add new entry
                log_entry = {
                    "timestamp": datetime.now().isoformat(),
                    "type": entry_type,
                    **data
                }
                log_data.append(log_entry)

                # Keep last 500 entries (reduced for performance)
                if len(log_data) > 500:
                    log_data = log_data[-500:]

                # Write back
                with open(log_path, 'w') as f:
                    json.dump(log_data, f, indent=2)

            except Exception as e:
                print(f"Failed to write to log.json: {e}")

        # Run in background thread to prevent GUI blocking
        threading.Thread(target=do_log, daemon=True).start()

    def _update_backup_manifest(self, original_file: str, backup_file: str, backup_info: dict):
        """Update the backup manifest with new backup entry (non-blocking)"""
        def do_update():
            try:
                manifest_path = Path(__file__).parent / "backup_manifest.json"

                # Load existing manifest (with safety checks)
                manifest = {}
                if manifest_path.exists():
                    # Check file size
                    if manifest_path.stat().st_size > 5 * 1024 * 1024:  # 5MB limit
                        print(f"Warning: backup_manifest.json too large, resetting")
                        manifest = {}
                    else:
                        with open(manifest_path, 'r') as f:
                            manifest = json.load(f)

                # Get absolute paths (avoid slow resolve() on every call)
                original_abs = str(Path(original_file).absolute())

                # Add backup entry for this file
                if original_abs not in manifest:
                    manifest[original_abs] = []

                manifest[original_abs].append({
                    "backup_path": backup_file,
                    "timestamp": backup_info["timestamp"],
                    "backup_name": backup_info["backup_name"]
                })

                # Keep last 30 backups per file (reduced for performance)
                if len(manifest[original_abs]) > 30:
                    manifest[original_abs] = manifest[original_abs][-30:]

                # Write back
                with open(manifest_path, 'w') as f:
                    json.dump(manifest, f, indent=2)

            except Exception as e:
                print(f"Failed to update backup manifest: {e}")

        # Run in background thread
        threading.Thread(target=do_update, daemon=True).start()

    def _get_backups_for_file(self, target_file: str) -> list:
        """Get list of backups for a specific file from manifest"""
        try:
            manifest_path = Path(__file__).parent / "backup_manifest.json"

            if not manifest_path.exists():
                return []

            # Check file size before reading
            if manifest_path.stat().st_size > 5 * 1024 * 1024:  # 5MB limit
                print(f"Warning: backup_manifest.json too large")
                return []

            with open(manifest_path, 'r') as f:
                manifest = json.load(f)

            # Use absolute() instead of resolve() for speed
            target_abs = str(Path(target_file).absolute())
            backups = manifest.get(target_abs, [])

            # Filter to only existing backups (limit checks for performance)
            existing_backups = []
            for i, backup in enumerate(backups):
                if i >= 50:  # Limit to checking 50 backups max
                    break
                try:
                    if Path(backup["backup_path"]).exists():
                        existing_backups.append(backup)
                except:
                    continue  # Skip invalid entries

            return existing_backups

        except Exception as e:
            self.engine.log_debug(f"Failed to read backup manifest: {e}", "ERROR")
            return []

    def _backup_current_target(self):
        """Backup the current target file - Unified Storage"""
        self._add_traceback("📦 Backup started", "INFO")

        target = self.target_var.get().strip()

        # Get file from target + pattern
        if not target:
            self._add_traceback("❌ No target set", "ERROR")
            return

        if not os.path.isfile(target):
            pattern = self.pattern_var.get().strip()
            if os.path.isdir(target) and pattern:
                target = os.path.join(target, pattern)

        if not os.path.isfile(target):
            self._add_traceback(f"❌ Not a file: {target}", "ERROR")
            return

        try:
            import shutil
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            path = Path(target)
            file_size = path.stat().st_size

            # Check file size (warn if > 10MB)
            if file_size > 10 * 1024 * 1024:
                self._add_traceback(f"⚠️ Large file ({file_size // 1024 // 1024}MB), backup may take a moment...", "WARNING")

            # Determine backup path (Unified or Local)
            if self.version_manager:
                backup_root = self.version_manager.get_backup_path()
                # Create version-specific folder if possible, else generic
                current_ver = self.version_manager.get_current_version() or "generic"
                backup_dir = backup_root / current_ver
                backup_dir.mkdir(parents=True, exist_ok=True)
                
                # Keep original structure relative to project root if possible to avoid collisions
                try:
                    rel_path = path.relative_to(self.project_root)
                    backup_name = f"{rel_path.name}_{timestamp}{path.suffix}" # Flattened name for now
                except ValueError:
                    backup_name = f"{path.stem}_{timestamp}{path.suffix}"
                
                backup_path = backup_dir / backup_name
            else:
                # Fallback: Local backup
                backup_name = f"{path.stem}_backup_{timestamp}{path.suffix}"
                backup_path = path.parent / backup_name

            shutil.copy2(target, backup_path)

            # Use absolute() instead of resolve() for speed
            path_abs = str(path.absolute())
            backup_path_abs = str(backup_path.absolute())

            # Log to log.json
            self._log_to_json("backup", {
                "action": "backup_created",
                "original_file": path_abs,
                "backup_file": backup_path_abs,
                "backup_name": backup_name,
                "file_size": file_size,
                "storage": "unified" if self.version_manager else "local"
            })

            # Update backup manifest (Unified if possible)
            # For now we still update the local manifest for backward compat
            self._update_backup_manifest(
                path_abs,
                backup_path_abs,
                {
                    "timestamp": datetime.now().isoformat(),
                    "backup_name": backup_name,
                    "storage": "unified" if self.version_manager else "local"
                }
            )

            self._add_traceback(
                f"✅ BACKUP COMPLETE\n"
                f"   File: {path.name}\n"
                f"   Backup: {backup_name}\n"
                f"   Location: {backup_path.parent}\n"
                f"   Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                "SUCCESS"
            )

        except Exception as e:
            self._add_traceback(f"❌ Backup failed: {e}", "ERROR")
            self._log_to_json("backup", {
                "action": "backup_failed",
                "error": str(e),
                "target": target
            })

    def _show_restore_menu(self):
        """Show dropdown menu with available backups for current target (Unified)"""
        target = self.target_var.get().strip()

        # Get file from target + pattern
        if not target:
            self._add_traceback("❌ No target set - cannot show restore menu", "ERROR")
            return

        if not os.path.isfile(target):
            pattern = self.pattern_var.get().strip()
            if os.path.isdir(target) and pattern:
                target = os.path.join(target, pattern)

        if not os.path.isfile(target):
            self._add_traceback(f"❌ Not a file: {target}", "ERROR")
            return
            
        # Get backups
        backups = []
        
        # 1. Local backups (Manifest)
        manifest_backups = self._get_backups_for_file(str(Path(target).absolute()))
        if manifest_backups:
            backups.extend(manifest_backups)
            
        # 2. Unified backups (VersionManager)
        if self.version_manager:
            backup_root = self.version_manager.get_backup_path()
            current_ver = self.version_manager.get_current_version() or "generic"
            backup_dir = backup_root / current_ver
            
            if backup_dir.exists():
                # Scan for files matching the target name pattern
                target_stem = Path(target).stem
                for f in backup_dir.glob(f"*{target_stem}*"):
                    backups.append({
                        "path": str(f),
                        "timestamp": datetime.fromtimestamp(f.stat().st_mtime).isoformat(),
                        "name": f.name
                    })

        if not backups:
            messagebox.showinfo("Restore", "No backups found for this file.")
            return

        # Create popup menu
        menu = tk.Menu(self, tearoff=0)
        
        # Deduplicate by path
        seen_paths = set()
        
        for bk in sorted(backups, key=lambda x: x.get('timestamp', ''), reverse=True):
            path = bk.get('path') or bk.get('backup_file')
            if not path or path in seen_paths: continue
            seen_paths.add(path)
            
            ts = bk.get('timestamp', 'Unknown time')
            name = Path(path).name
            
            label = f"{ts} - {name}"
            menu.add_command(label=label, command=lambda p=path: self._perform_restore(p, target))

        x = self.winfo_pointerx()
        y = self.winfo_pointery()
        menu.post(x, y)

    def _perform_restore(self, backup_path, target_path):
        """Execute the restore operation"""
        if messagebox.askyesno("Confirm Restore", f"Overwrite:\n{target_path}\n\nWith:\n{backup_path}?"):
            try:
                import shutil
                shutil.copy2(backup_path, target_path)
                self._add_traceback(f"✅ Restored {Path(target_path).name} from backup", "SUCCESS")
                self.status_var.set("✅ File Restored")
            except Exception as e:
                self._add_traceback(f"❌ Restore failed: {e}", "ERROR")
                messagebox.showerror("Error", f"Restore failed:\n{e}")

        # Get backups for this file
        try:
            backups = self._get_backups_for_file(target)
        except Exception as e:
            self._add_traceback(f"❌ Error reading backups: {e}", "ERROR")
            return

        if not backups:
            self._add_traceback(f"ℹ️ No backups found for: {Path(target).name}", "INFO")
            return

        # Limit to last 20 backups for menu performance
        backups_sorted = sorted(backups, key=lambda x: x["timestamp"], reverse=True)[:20]

        # Create dropdown menu with proper styling
        menu = tk.Menu(
            self,
            tearoff=0,
            bg=self.config.BG_COLOR,
            fg=self.config.FG_COLOR,
            activebackground=self.config.HOVER_COLOR,
            activeforeground=self.config.ACCENT_COLOR,
            relief=tk.FLAT,
            bd=1
        )

        for backup in backups_sorted:
            # Format timestamp for display
            try:
                ts = datetime.fromisoformat(backup["timestamp"])
                time_str = ts.strftime("%Y-%m-%d %H:%M:%S")
            except:
                time_str = backup["timestamp"][:19]  # Truncate to reasonable length

            # Truncate backup name if too long
            backup_display = backup["backup_name"]
            if len(backup_display) > 40:
                backup_display = backup_display[:37] + "..."

            label = f"{time_str} - {backup_display}"

            menu.add_command(
                label=label,
                command=lambda b=backup["backup_path"], t=target: self._restore_from_backup(b, t)
            )

        # Show menu - use after_idle to prevent blocking
        def show_menu():
            try:
                x = self.winfo_pointerx()
                y = self.winfo_pointery()
                menu.post(x, y)

                # Make menu disappear on outside click
                def dismiss_menu(event=None):
                    try:
                        menu.unpost()
                    except:
                        pass

                # Bind to lose focus
                menu.bind('<FocusOut>', dismiss_menu)

                # Dismiss if user clicks outside the menu area
                def check_click(event):
                    widget = self.winfo_containing(event.x_root, event.y_root)
                    if widget != menu:
                        dismiss_menu()

                # Bind click event to root window after a short delay
                self.after(50, lambda: self.bind_all('<Button-1>', check_click, add='+'))

                # Auto-cleanup binding after menu is dismissed
                def cleanup():
                    try:
                        self.unbind_all('<Button-1>')
                    except:
                        pass

                self.after(5000, cleanup)  # Cleanup after 5 seconds max

            except Exception as e:
                self.engine.log_debug(f"Menu display error: {e}", "ERROR")

        self.after_idle(show_menu)

    def _restore_from_backup(self, backup_path: str, target_path: str):
        """Restore a file from backup, marking the current version with Bug

        Event Sequence:
        1. Verify backup and target exist
        2. Create Bug-marked copy of current file
        3. Restore backup to target location
        4. Update manifest with Bug-marked file
        5. Log operation to log.json
        6. Update UI (traceback only, non-blocking)
        """
        try:
            import shutil

            self._add_traceback("🔄 Restore started...", "INFO")

            # Verify backup exists
            backup_p = Path(backup_path)
            if not backup_p.exists():
                self._add_traceback(f"❌ Backup file not found: {backup_path}", "ERROR")
                return

            # Verify target exists
            target_p = Path(target_path)
            if not target_p.exists():
                self._add_traceback(f"❌ Target file not found: {target_path}", "ERROR")
                return

            # Check file sizes
            backup_size = backup_p.stat().st_size
            if backup_size > 10 * 1024 * 1024:
                self._add_traceback(f"⚠️ Large backup ({backup_size // 1024 // 1024}MB), restore may take a moment...", "WARNING")

            # Create Bug-marked version of current file (STEP 1)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            bug_name = f"{target_p.stem}_Bug_{timestamp}{target_p.suffix}"
            bug_path = target_p.parent / bug_name

            self._add_traceback(f"📝 Creating Bug-marked version: {bug_name}", "INFO")
            shutil.copy2(target_path, bug_path)

            # Restore backup to target (STEP 2)
            self._add_traceback(f"📦 Restoring from: {backup_p.name}", "INFO")
            shutil.copy2(backup_path, target_path)

            # Use absolute() instead of resolve() for speed
            target_abs = str(target_p.absolute())
            bug_path_abs = str(bug_path.absolute())
            restore_timestamp = datetime.now().isoformat()

            # Update manifest with Bug-marked file (STEP 3)
            # The Bug-marked file should be tracked in case we need to restore to it
            self._add_traceback(f"📋 Updating backup manifest...", "INFO")
            self._update_backup_manifest(
                target_abs,
                bug_path_abs,
                {
                    "timestamp": restore_timestamp,
                    "backup_name": bug_name
                }
            )

            # Log the restore operation (STEP 4)
            self._log_to_json("restore", {
                "action": "restore_completed",
                "target_file": target_abs,
                "backup_file": backup_path,
                "bug_marked_file": bug_path_abs,
                "restored_at": restore_timestamp
            })

            # Update UI - traceback only (STEP 5)
            self._add_traceback(
                f"✅ RESTORE COMPLETE\n"
                f"   Restored: {target_p.name}\n"
                f"   From backup: {backup_p.name}\n"
                f"   Bug-marked file: {bug_name}\n"
                f"   Location: {target_p.parent}\n"
                f"   Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                "SUCCESS"
            )

            # Refresh UI in background to prevent freezing (STEP 6)
            self.after(100, lambda: self.update_idletasks())

        except Exception as e:
            self._add_traceback(f"❌ Restore failed: {e}", "ERROR")
            self._log_to_json("restore", {
                "action": "restore_failed",
                "error": str(e),
                "target": target_path,
                "backup": backup_path
            })

    def _browse_target(self):
        """Open file browser to select target with extensive debug logging"""
        print("\n>>> BROWSE TARGET FUNCTION CALLED <<<")
        self.engine.log_debug("=" * 60)
        self.engine.log_debug("BROWSE TARGET REQUESTED")
        self.engine.log_debug("=" * 60)

        was_withdrawn = False
        try:
            # Step 1: Log current state
            self.engine.log_debug(f"Current topmost: {self.attributes('-topmost')}")
            self.engine.log_debug(f"Window geometry: {self.geometry()}")
            self.engine.log_debug(f"Window state: visible={self.winfo_viewable()}, mapped={self.winfo_ismapped()}")

            # Step 2: WITHDRAW main window to prevent dialog from spawning under it
            self.engine.log_debug("Step 1: Withdrawing main window to show dialog on top...")
            self.attributes('-topmost', False)
            try:
                # Temporarily hide the window
                self.withdraw()
                was_withdrawn = True
                self.engine.log_debug("  Main window withdrawn")
            except:
                self.engine.log_debug("  WARNING: Could not withdraw window")

            # Step 3: Update UI
            self.engine.log_debug("Step 2: Forcing UI update...")
            self.update_idletasks()
            self.update()
            self.engine.log_debug("  UI updated")

            # Step 4: Get initial directory - debug the target_var state
            raw_target = self.target_var.get()
            self.engine.log_debug(f"[BROWSE] target_var.get() raw value: '{raw_target}'", "DEBUG")
            self.engine.log_debug(f"[BROWSE] target_var id: {id(self.target_var)}", "DEBUG")

            # Also check if we have action_panel_context
            if hasattr(self, 'action_panel_context') and self.action_panel_context:
                self.engine.log_debug(f"[BROWSE] action_panel_context: {self.action_panel_context.get('target_dir', 'N/A')}", "DEBUG")
                # Use context if target_var is empty
                if not raw_target:
                    raw_target = self.action_panel_context.get('target_dir', '')
                    self.engine.log_debug(f"[BROWSE] Using action_panel_context instead: {raw_target}", "DEBUG")

            initial_dir = raw_target if raw_target and os.path.exists(raw_target) else os.path.expanduser("~")
            self.engine.log_debug(f"Step 3: Initial directory: {initial_dir}")

            # Step 5: Show file dialog (should now be on top!)
            self.engine.log_debug("Step 4: Opening file dialog...")
            self.engine.log_debug("  >> DIALOG OPENING - Should appear ON TOP now <<")

            target = filedialog.askdirectory(
                title="Select Target Directory",
                initialdir=initial_dir
            )

            self.engine.log_debug("  >> DIALOG RETURNED <<")
            self.engine.log_debug(f"  Selected: {target if target else 'CANCELLED'}")

        except Exception as e:
            self.engine.log_debug(f"EXCEPTION CAUGHT: {type(e).__name__}: {e}")
            import traceback
            self.engine.log_debug(f"Traceback: {traceback.format_exc()}")
            target = None

        finally:
            # Step 6: Restore main window
            self.engine.log_debug("Step 5: Restoring main window...")
            try:
                if was_withdrawn:
                    self.deiconify()
                    self.engine.log_debug("  Main window deiconified")
                self.attributes('-topmost', True)
                self.engine.log_debug(f"  Topmost restored: {self.attributes('-topmost')}")
            except Exception as e:
                self.engine.log_debug(f"  ERROR restoring window: {e}")

            # Step 7: Restore focus
            self.engine.log_debug("Step 6: Restoring focus...")
            try:
                self.lift()
                self.focus_force()
                self.engine.log_debug("  Focus restored")
            except Exception as e:
                self.engine.log_debug(f"  ERROR restoring focus: {e}")

        # Step 8: Process result
        if target:
            self.engine.log_debug(f"Step 7: Setting target to: {target}")
            self.target_var.set(target)
            self.engine.set_target(target)
            self.status_var.set(f"✅ Target: {Path(target).name}")
            self.engine.log_debug("SUCCESS: Target set")
        else:
            self.engine.log_debug("Step 7: No target selected (cancelled or error)")
            self.status_var.set("Target selection cancelled")

        self.engine.log_debug("=" * 60)
        self.engine.log_debug("BROWSE TARGET COMPLETED")
        self.engine.log_debug("=" * 60)
    
    def _execute_grep(self):
        """Execute basic grep command"""
        target = self.target_var.get()
        pattern = self.pattern_var.get()

        if not target:
            self.attributes('-topmost', False)
            messagebox.showerror("Error", "Please set a target first")
            self.attributes('-topmost', True)
            return

        if not pattern:
            self.attributes('-topmost', False)
            messagebox.showerror("Error", "Please enter a search pattern")
            self.attributes('-topmost', True)
            return

        cmd = f"grep -rn {shlex.quote(pattern)} {shlex.quote(target)}"
        self._execute_command(cmd)
    
    def _execute_template(self, template: str):
        """Execute command from template"""
        target = self.target_var.get() or '.'
        pattern = self.pattern_var.get() or ''
        
        # Determine if pattern needs quoting based on template content
        # Templates updated to remove quotes around {pattern}, so we quote here
        safe_pattern = shlex.quote(pattern)
        
        # Special case for templates that might still have hardcoded quotes or regex
        # But we updated G1-G3. G4 doesn't use pattern variable. G5 uses it as args.
        
        cmd = template.format(
            target=shlex.quote(target),
            pattern=safe_pattern,
            version_root=shlex.quote(str(self.version_root)),
            babel_root=shlex.quote(str(self.babel_root))
        )
        self._execute_command(cmd)
    
    def _execute_command(self, command: str):
        """Execute command in background"""
        def run_command():
            try:
                output, error = self.engine.execute_command(command)
                
                # Update results in main thread
                self.after(0, lambda: self._display_results(output, error))
                
            except Exception as e:
                self.after(0, lambda: self.results_text.insert(tk.END, f"Error: {str(e)}\n"))
        
        # Clear previous results
        self.results_text.delete(1.0, tk.END)
        self.results_text.insert(tk.END, f"Executing: {command}\n{'='*60}\n")
        
        # Run in background
        threading.Thread(target=run_command, daemon=True).start()
    
    def _display_results(self, output: str, error: str = ""):
        """Display command results with clickable file paths"""
        lines = output.split('\n')

        for line in lines:
            if not line.strip():
                self.results_text.insert(tk.END, '\n')
                continue

            # Try to parse grep output format: file:line:content or file:line:column:content
            match = re.match(r'^([^:]+):(\d+):(.*)', line)
            if match:
                file_path, line_num, content = match.groups()
                # Insert clickable file:line part
                start_idx = self.results_text.index(tk.END)
                self.results_text.insert(tk.END, f"{file_path}:{line_num}:")
                end_idx = self.results_text.index(tk.END)
                self.results_text.tag_add('clickable', f"{start_idx} linestart", f"{start_idx} lineend -{len(content)-1}c")
                # Store file and line info in tag
                tag_name = f"file_{start_idx.replace('.', '_')}"
                self.results_text.tag_add(tag_name, f"{start_idx} linestart", f"{start_idx} lineend -{len(content)-1}c")
                self.results_text.tag_bind(tag_name, '<Button-1>',
                                         lambda e, f=file_path, l=line_num: self._open_file_at_line(f, int(l)))
                # Insert the content part (not clickable)
                self.results_text.insert(tk.END, f"{content}\n")
            else:
                # Non-matching line, insert as-is
                self.results_text.insert(tk.END, f"{line}\n")

        if error:
            self.results_text.insert(tk.END, f"\nErrors:\n{error}")

        # Scroll to top
        self.results_text.see(1.0)

    def _push_context_to_ai(self):
        """Aggregate context and inject into either internal chat or external Gemini CLI"""
        target = self.target_var.get()
        if not target or not Path(target).exists():
            messagebox.showerror("Error", "Please set a valid target file first.")
            return

        current_model = self.chat_model.get()
        self.status_var.set(f"⌛ Aggregating Context for {current_model}...")
        self.engine.log_debug(f"Aggregating context for: {target}", "INFO")

        # Path to aggregator
        aggregator_script = self.version_root / "Modules" / "Ag_Forge_v1c" / "modules" / "dev_tools" / "context_aggregator.py"
        
        if not aggregator_script.exists():
            self.status_var.set("⚠️ Aggregator script not found")
            return

        def worker():
            try:
                # 1. Run Aggregator
                cmd = [
                    sys.executable, str(aggregator_script),
                    "--file", target,
                    "--request", "Please review this component and suggest refinements based on our current architecture."
                ]
                subprocess.run(cmd, capture_output=True, text=True, timeout=30)
                
                # 2. Read generated prompt
                temp_file = Path("/tmp/gemini_review_context.txt")
                if not temp_file.exists():
                    self.after(0, lambda: self.status_var.set("❌ Context file missing"))
                    return

                with open(temp_file, 'r') as f:
                    prompt = f.read()
                
                # 3. Handle based on model type
                if current_model == "Gemini (CLI)":
                    # External: Use Clipboard
                    self.after(0, lambda: self._copy_to_clipboard(prompt))
                    self.after(0, lambda: self.status_var.set("✅ Context in Clipboard!"))
                    self.after(0, lambda: messagebox.showinfo("Context Ready", 
                        "🚀 Context aggregated for Gemini CLI!\n\nIt has been copied to your clipboard.\nPaste it (Ctrl+Shift+V) into your terminal window."))
                else:
                    # Internal: Inject into ChatBackend
                    if self.chat_backend:
                        self.chat_backend.update_context({"deep_context": prompt})
                        self.after(0, lambda: self.status_var.set("✅ Deep Context Injected!"))
                        self.after(0, lambda: self._add_chat_response(f"ℹ️ Deep Context injected for {Path(target).name}. (Analysis & Script Knowledge Base uploaded)."))
                    else:
                        self.after(0, lambda: self.status_var.set("❌ Chat backend not ready"))

            except Exception as e:
                self.after(0, lambda: self.engine.log_debug(f"Aggregation failed: {e}", "ERROR"))
                self.after(0, lambda: self.status_var.set("❌ Aggregation failed"))

        threading.Thread(target=worker, daemon=True).start()

    def _on_result_right_click(self, event):
        """Handle right-click on results text"""
        # Get line content
        index = self.results_text.index(f"@{event.x},{event.y}")
        line_content = self.results_text.get(f"{index} linestart", f"{index} lineend")
        
        if not line_content.strip(): return

        # Create context menu
        menu = tk.Menu(self, tearoff=0, bg='#2a2a2a', fg=self.config.FG_COLOR)
        
        # Try to extract path
        path = self._extract_path_from_line(line_content)
        if path:
            menu.add_command(label=f"Create Task from: {Path(path).name}", 
                           command=lambda p=path: self._create_task_from_result(p))
            menu.add_separator()
        
        menu.add_command(label="Copy Line", command=lambda: self._copy_to_clipboard(line_content))
        menu.add_command(label="Clear Results", command=self._clear_results)

        try:
            menu.post(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def _extract_path_from_line(self, line):
        """Helper to extract file path from a result line"""
        # Grep format: path:line:content
        match = re.match(r'^([^:]+):(\d+):', line)
        if match: return match.group(1)
        
        # WarehouseProber format: Path: versions/...
        if "Path: " in line:
            return line.split("Path: ")[1].strip()
            
        return None

    def _create_task_from_result(self, file_path):
        """Launch task creation dialog with pre-filled file reference"""
        if self.app_ref and hasattr(self.app_ref, 'tasks_frame'):
            # Switch to tasks and trigger creation
            # We assume app_ref.tasks_frame is a TaskPanel instance
            self.app_ref.notebook.select(self.app_ref.tasks_frame)
            
            # Check if tasks_frame has create_new_task method
            if hasattr(self.app_ref.tasks_frame, 'create_new_task'):
                self.app_ref.tasks_frame.create_new_task(
                    marked_files=[file_path]
                )
            else:
                self.status_var.set("⚠️ Task creation logic not found in Uni_Launch")
        else:
            self.status_var.set("⚠️ Uni_Launch Tasks tab not available")

    def _copy_to_clipboard(self, text):
        self.clipboard_clear()
        self.clipboard_append(text)

    def _on_result_click(self, event):
        """Handle click on result line"""
        # This is handled by individual tag bindings now
        pass

    def _open_file_at_line(self, file_path: str, line_num: int):
        """Open file in editor at specific line"""
        # Make path absolute if relative
        if not os.path.isabs(file_path):
            target = self.target_var.get()
            if target and os.path.isdir(target):
                file_path = os.path.join(target, file_path)

        if os.path.exists(file_path):
            self.engine.launch_editor(file_path, line_num)
            self.status_var.set(f"📝 Opened {Path(file_path).name}:{line_num}")
        else:
            self.status_var.set(f"⚠️ File not found: {file_path}")
    
    def _execute_workflow_action(self, action: Dict):
        """Execute workflow action with target coordination and expectation tracking"""
        action_name = action.get('name', 'Unknown')
        action_type = action.get('type', 'builtin')
        target_mode = action.get('target_mode', 'auto')
        output_to = action.get('output_to', 'results')
        expectations = action.get('expectations', 'none')

        # Resolve paths in the action
        def resolve(val):
            if isinstance(val, str) and "{version_root}" in val:
                return val.replace("{version_root}", str(self.version_root))
            return val

        action_source = resolve(action.get('source', ''))
        action_command = resolve(action.get('command', ''))

        # Log to traceback
        log_to_traceback(
            EventCategory.GREP_FLIGHT,
            "workflow_action_start",
            {"action": action_name, "type": action_type, "target_mode": target_mode},
            {"output_to": output_to, "expectations": expectations}
        )

        # Get target based on target_mode
        target = self._get_target_for_workflow(target_mode)
        if not target:
            self.status_var.set(f"⚠️ No valid target for {action_name}")
            return

        self.status_var.set(f"⚡ Running: {action_name} on {target}...")

        # Execute based on type
        if action_type == 'builtin':
            # Map action name to builtin workflow
            workflow_map = {
                "Quick Scan": "quick_scan",
                "Deep Debug": "deep_debug",
                "PFL Audit": "pfl_audit",
                "Surgical Fix": "surgical_fix"
            }
            workflow_key = workflow_map.get(action_name)
            if workflow_key:
                self._start_workflow(workflow_key)
        elif action_type == 'custom':
            # Execute custom script from custom_scripts config
            self._execute_custom_script(action_name, target)
        elif action_type == 'script' or action_type == 'workflow_suite':
            # Direct script execution
            self._execute_direct_script(action, target, cmd_override=action_command)
        elif action_type in ('debug_suite', 'debug_script', 'toolkit'):
            # For toolkit/debug, use the resolved source as command
            self._execute_debug_tool(action, target, command_override=action_source or action_command)

        # Route output based on output_to
        self._route_workflow_output(action_name, output_to, expectations, target)

        self.status_var.set(f"✓ Completed: {action_name}")

    def _get_target_for_workflow(self, target_mode: str) -> Optional[str]:
        """Get target based on target_mode setting"""
        if target_mode == 'auto':
            # Use current target field value
            return self.target_var.get().strip() or os.getcwd()
        elif target_mode == 'manual':
            # Prompt user for target
            from tkinter import filedialog
            return filedialog.askdirectory(title="Select target directory")
        elif target_mode == 'marked_files':
            # Get marked files from app_ref (babel_gui planner)
            if self.app_ref and hasattr(self.app_ref, '_planner_marked_files'):
                files = self.app_ref._planner_marked_files
                return ','.join(files) if files else None
            return None
        elif target_mode == 'current_file':
            # Get currently open file in editor (if available)
            if self.app_ref and hasattr(self.app_ref, 'current_editor_file'):
                return self.app_ref.current_editor_file
            return None
        return self.target_var.get().strip() or os.getcwd()

    def _execute_custom_script(self, script_name: str, target: str):
        """Execute custom script from custom_scripts.json"""
        scripts = self._load_custom_scripts()
        script = next((s for s in scripts if s['name'] == script_name), None)

        if script:
            command = script['command']
            args = script.get('args', '').replace('{target}', target)
            full_command = f"{command} {args}"

            self._add_traceback(f"🔧 Running custom script: {script_name}")
            self._add_traceback(f"   Command: {full_command}")

            # Execute in thread
            def worker():
                try:
                    result = subprocess.run(full_command, shell=True, capture_output=True, text=True, timeout=30)
                    self.after(0, lambda: self._display_script_result(script_name, result))
                except Exception as e:
                    self.after(0, lambda: self._add_traceback(f"❌ Script error: {e}", "ERROR"))

            threading.Thread(target=worker, daemon=True).start()

    def _execute_direct_script(self, action: Dict, target: str, cmd_override=None):
        """Execute script directly from action config"""
        script_path = cmd_override or action.get('source', '')
        if script_path:
            # Re-resolve just in case
            if "{version_root}" in script_path:
                script_path = script_path.replace("{version_root}", str(self.version_root))
            
            # Handle args
            args_str = action.get('args', '')
            if "{target}" in args_str:
                args_str = args_str.replace("{target}", target)
            
            command = f"python3 {script_path} {args_str}"
            self._add_traceback(f"🔧 Running script: {command}")
            
            def worker():
                try:
                    result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=60)
                    self.after(0, lambda: self._display_script_result(action.get('name', 'Script'), result))
                except Exception as e:
                    self.after(0, lambda: self._add_traceback(f"❌ Script error: {e}", "ERROR"))

            threading.Thread(target=worker, daemon=True).start()
        else:
            self._add_traceback(f"Script source missing", "ERROR")

    def _execute_debug_tool(self, action: Dict, target: str, command_override=None):
        """Execute a babel_gui debug toolkit entry"""
        command_path = command_override or action.get('command') or action.get('source')
        if not command_path:
            self._add_traceback("No command specified for debug tool", "ERROR")
            return

        if "{version_root}" in command_path:
            command_path = command_path.replace("{version_root}", str(self.version_root))

        cmd_args = action.get('args', '')
        args_list: List[str] = []
        if cmd_args:
            try:
                # Replace tokens in args
                args_str = cmd_args.replace('{target}', target)
                if "{version_root}" in args_str:
                    args_str = args_str.replace("{version_root}", str(self.version_root))
                args_list = shlex.split(args_str)
            except ValueError:
                args_list = cmd_args.replace('{target}', target).split()

        cmd: List[str]
        if command_path.endswith('.py'):
            cmd = [sys.executable, command_path]
        else:
            cmd = [command_path]
        cmd.extend(args_list)

        def worker():
            try:
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
                self.after(0, lambda: self._display_script_result(action.get('name', 'Debug Tool'), result))
            except subprocess.TimeoutExpired:
                self.after(0, lambda: self._add_traceback("Debug tool timed out", "ERROR"))
            except Exception as exc:
                self.after(0, lambda: self._add_traceback(f"Debug tool error: {exc}", "ERROR"))

        threading.Thread(target=worker, daemon=True).start()

    def _route_workflow_output(self, action_name: str, output_to: str, expectations: str, target: str):
        """Route workflow output to appropriate destination(s)"""
        output_data = {
            "action": action_name,
            "target": target,
            "expectations": expectations,
            "timestamp": datetime.now().isoformat()
        }

        if output_to == 'results':
            # Display in results panel (already happens)
            pass
        elif output_to == 'pfc':
            # Send to PFC system for checks
            self._add_traceback(f"📊 Sending to PFC: {expectations}")
            log_to_traceback(EventCategory.PFC, "workflow_output", output_data, {"destination": "pfc"})
        elif output_to == 'pfc+results':
            # Both results and PFC
            self._add_traceback(f"📊 Sending to PFC + Results: {expectations}")
            log_to_traceback(EventCategory.PFC, "workflow_output", output_data, {"destination": "pfc+results"})
        elif output_to == 'diff_queue':
            # Send to diff queue with expectations
            self._add_traceback(f"📝 Sending to diff queue: {expectations}")
            log_to_traceback(EventCategory.FILE, "workflow_output", output_data, {"destination": "diff_queue"})
            # TODO: Create diff entry in .docv2_workspace/diff_queue/
        elif output_to == 'tasks':
            # Create task from workflow output
            self._add_traceback(f"📋 Creating task: {expectations}")
            log_to_traceback(EventCategory.TASK, "workflow_output", output_data, {"destination": "tasks"})
            # TODO: Create task in .docv2_workspace/tasks/
        elif output_to == 'traceback':
            # Just log to traceback (already done above)
            pass

        # Push result summary to Chat Input
        self._update_chat_input_display(
            action_name=action_name,
            result_status="Done", # Assuming success if we got here, failure handled elsewhere
            target=target,
            context_log=f"Check Traceback or Logs"
        )

    def _display_script_result(self, script_name: str, result):
        """Display custom script result"""
        if result.returncode == 0:
            self._add_traceback(f"✓ {script_name} completed successfully", "INFO")
            if result.stdout:
                self.results_text.insert(tk.END, f"\n--- {script_name} Output ---\n{result.stdout}\n")
        else:
            self._add_traceback(f"❌ {script_name} failed (exit code {result.returncode})", "ERROR")
            if result.stderr:
                self.results_text.insert(tk.END, f"\n--- {script_name} Errors ---\n{result.stderr}\n")

    def _start_workflow(self, workflow_name: str):
        """Start a predefined workflow"""
        self.current_workflow = workflow_name
        workflows = WorkflowPresets.get_workflows()

        if workflow_name in workflows:
            steps = workflows[workflow_name]

            # Add to traceback
            self._add_traceback(f"🚀 Started workflow: {workflow_name}")

            # Execute steps
            for step in steps:
                self._add_traceback(f"  {step.icon} {step.name}: {step.description}")
    
    def _add_traceback(self, message: str, step_type: str = "INFO"):
        """Add message to traceback window with fallback to console

        Now event-driven: Triggers suggestive actions based on event type
        """
        try:
            if not hasattr(self, 'traceback_text') or not self.traceback_text.winfo_exists():
                # Fallback to engine log if UI not ready
                self.engine.log_debug(f"[UI_MISSING] {message}", step_type)
                return

            timestamp = datetime.now().strftime("%H:%M:%S")
            formatted = f"[{timestamp}] {message}\n"

            self.traceback_text.insert(tk.END, formatted)
            self.traceback_text.tag_add(step_type, "end-2l", "end-1l")
            self.traceback_text.see(tk.END)

            # EVENT-DRIVEN SUGGESTIONS: Trigger actions based on event type
            self._handle_traceback_event(message, step_type, timestamp)

        except Exception as e:
            # Last resort fallback
            print(f"CRITICAL ERROR in _add_traceback: {e}")
            self.engine.log_debug(f"[TRACEBACK_ERROR] {message} (Error: {e})", "ERROR")

    def _handle_traceback_event(self, message: str, step_type: str, timestamp: str):
        """Handle traceback events and trigger suggestive actions

        Event-driven coordination:
        - ERROR events → Suggest debug tools, create #[Mark:BUG]
        - TARGET_SET events → Refresh suggested grep commands
        - STARTUP events → Check if backup needed (flash button)
        - File changes detected → Validate expected workflow
        """
        try:
            # 1. ERROR EVENTS → Auto-suggest debug tools
            if step_type == "ERROR":
                self._handle_error_event(message, timestamp)

            # 2. TARGET_SET → Refresh grep suggestions for new target
            elif step_type == "TARGET_SET" or "Target Set" in message:
                self._refresh_grep_suggestions()

            # 3. STARTUP → Check if backup needed
            elif step_type == "INFO" and "STARTUP" in message:
                self._check_backup_needed()

            # 4. File operations → Validate workflow (marks/todos/debug)
            elif step_type in ["FILE", "SAVE"]:
                self._validate_workflow(message)

        except Exception as e:
            self.engine.log_debug(f"Error handling traceback event: {e}", "ERROR")

    def _handle_error_event(self, message: str, timestamp: str):
        """Handle ERROR events - suggest debug tools, create marks"""
        # Parse error to determine suggested actions
        suggestions = []

        # Check for Python errors
        if "Traceback" in message or ".py" in message:
            suggestions.append({
                'label': '🐛 Run py_compile',
                'command': 'python3 -m py_compile',
                'flash': True
            })

        # Check for import errors
        if "ImportError" in message or "ModuleNotFoundError" in message:
            suggestions.append({
                'label': '📦 Check imports',
                'command': 'grep -E "^import |^from "',
                'flash': True
            })

        # TODO: Create #[Mark:BUG:line] at exact error location
        # TODO: Push to Os_Toolkit session data
        # TODO: Trigger latest sync

        if suggestions:
            self.engine.log_debug(f"Error detected → {len(suggestions)} suggestions generated")

    def _refresh_grep_suggestions(self):
        """Refresh suggested grep commands based on current target"""
        target = self.target_var.get()
        if not target or not self.babel_root:
            return

        try:
            # Call Os_Toolkit suggest command
            cmd = [
                'python3',
                str(self.babel_root / 'Os_Toolkit.py'),
                'suggest',
                target,
                '--format', 'json'
            ]

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                # Parse JSON suggestions
                import json
                suggestions = json.loads(result.stdout)
                self.engine.log_debug(f"✓ Loaded {len(suggestions)} suggestions for {Path(target).name}")

                # TODO: Update Grep tab buttons dynamically
                # self._update_grep_buttons(suggestions)

        except Exception as e:
            self.engine.log_debug(f"Failed to load suggestions: {e}", "WARNING")

    def _check_backup_needed(self):
        """Check if backup is needed on startup - flash button if yes"""
        try:
            # Call Os_Toolkit latest to get state
            cmd = ['python3', str(self.babel_root / 'Os_Toolkit.py'), 'latest']
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)

            if result.returncode == 0:
                output = result.stdout

                # Check for completed tasks
                if "✅" in output or "tasks have status conflicts" in output:
                    # TODO: Flash backup button
                    self.engine.log_debug("💡 Backup recommended: Recent task completions detected")

                # Check for file changes
                if "files modified" in output:
                    # TODO: Flash backup button
                    self.engine.log_debug("💡 Backup recommended: File changes detected")

        except Exception as e:
            self.engine.log_debug(f"Could not check backup status: {e}", "WARNING")

    def _validate_workflow(self, message: str):
        """Validate expected workflow - detect missing marks/todos/debug"""
        # TODO: Implement workflow validation
        # Expected: File changed → Mark added → Todo created → Debug run
        # If any step missing → Create conflict and suggest action
        pass

    def _show_traceback(self):
        """Show/hide traceback window with robust error handling"""
        self.engine.log_debug("="*60)
        self.engine.log_debug("SHOW TRACEBACK CALLED")
        self.engine.log_debug("="*60)

        try:
            # Check if window exists and is valid
            if not hasattr(self, 'traceback_window') or not self.traceback_window.winfo_exists():
                self.engine.log_debug("  Traceback window missing or destroyed, recreating...")
                self._create_traceback_popup()

            if self.traceback_window.winfo_viewable():
                self.engine.log_debug("  Traceback window is visible, hiding it")
                self.traceback_window.withdraw()
                self.engine.log_debug("  Traceback window hidden")
            else:
                self.engine.log_debug("  Traceback window is hidden, showing it")
                self.traceback_window.deiconify()
                self.traceback_window.lift()
                self.engine.log_debug("  Traceback window shown and lifted")
                
        except Exception as e:
            self.engine.log_debug(f"ERROR showing traceback window: {e}", "ERROR")
            messagebox.showerror("Error", f"Failed to open traceback window: {e}")
            # Try to recover by recreating next time
            if hasattr(self, 'traceback_window'):
                try:
                    self.traceback_window.destroy()
                except:
                    pass
                del self.traceback_window

        self.engine.log_debug("="*60)
    
    def _clear_traceback(self):
        """Clear traceback window"""
        self.traceback_text.delete(1.0, tk.END)
    
    def _quick_search(self):
        """Quick search with current pattern"""
        self.engine.log_debug("Quick search requested")

        # First check if expanded, if not expand it
        if not self.is_expanded:
            self.engine.log_debug("  Panel not expanded, expanding first...")
            self._expand_panel()
            self.after(300, self._quick_search)  # Retry after expansion animation
            return

        # Check for target
        if not self.target_var.get():
            self.engine.log_debug("  No target set")
            self.status_var.set("⚠️ Please set a target directory first (click 📁 or Browse)")
            self.pattern_entry.focus()
            return

        # Check for pattern
        if not self.pattern_var.get():
            self.engine.log_debug("  No pattern set")
            self.status_var.set("⚠️ Please enter a search pattern")
            self.pattern_entry.focus()
            return

        # Execute the search
        self.engine.log_debug(f"  Executing search: target={self.target_var.get()}, pattern={self.pattern_var.get()}")
        self._execute_grep()
    
    def _show_pfl(self):
        """Show PFL tags"""
        target = self.target_var.get() or '.'
        cmd = f"grep -rn '#\\[PFL:' '{target}'"
        self._execute_command(cmd)
    
    def _debug_mode(self):
        """Toggle debug mode"""
        self._add_traceback("🔧 Debug mode activated", "DEBUG")
        self.status_var.set("Debug Mode Active")
    
    def _open_editor(self):
        """Open current target in editor"""
        target = self.target_var.get()
        if target and os.path.exists(target):
            self.engine.launch_editor(target)
        else:
            self.attributes('-topmost', False)
            messagebox.showerror("Error", "No valid target selected")
            self.attributes('-topmost', True)
    
    def _open_terminal(self):
        """Open terminal at target"""
        target = self.target_var.get() or '.'
        self.engine.launch_terminal(target)
    
    def _open_file_browser(self):
        """Open file browser"""
        target = self.target_var.get() or os.path.expanduser("~")
        subprocess.Popen([self.config.FILE_MANAGER, target])
    
    def _add_pfl_tag(self):
        """Add a PFL tag dialog"""
        # Temporarily disable topmost
        self.attributes('-topmost', False)
        dialog = PFLTagDialog(self, self.config)
        self.attributes('-topmost', True)

        if dialog.result:
            tag_type, description = dialog.result
            self._add_traceback(f"🏷️ Added PFL tag: [{tag_type}] {description}", "PFL_FOUND")
    
    def _clear_results(self):
        """Clear results window"""
        self.results_text.delete(1.0, tk.END)
    
    def _copy_results(self):
        """Copy results to clipboard"""
        results = self.results_text.get(1.0, tk.END)
        self.clipboard_clear()
        self.clipboard_append(results)
        self.status_var.set("📋 Results copied to clipboard")

    def _export_results(self):
        """Export results to a file"""
        results = self.results_text.get(1.0, tk.END)
        if not results.strip():
            self.status_var.set("⚠️ No results to export")
            return

        # Temporarily disable topmost
        self.attributes('-topmost', False)

        try:
            from tkinter import filedialog
            filename = filedialog.asksaveasfilename(
                title="Export Results",
                defaultextension=".txt",
                filetypes=[
                    ("Text files", "*.txt"),
                    ("Log files", "*.log"),
                    ("All files", "*.*")
                ],
                initialfile=f"grep_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
                parent=self
            )
        finally:
            self.attributes('-topmost', True)
            self.lift()
            self.focus_force()

        if filename:
            try:
                with open(filename, 'w') as f:
                    f.write(results)
                self.status_var.set(f"💾 Exported to {Path(filename).name}")
                self._add_traceback(f"💾 Results exported to: {filename}", "EXPORT")
            except Exception as e:
                self.status_var.set(f"⚠️ Export failed: {e}")
    
    def _show_settings(self):
        """Show settings dialog"""
        self.attributes('-topmost', False)
        SettingsDialog(self, self.config)
        self.attributes('-topmost', True)

    def _open_profiles_config(self):
        """Open configuration directly to Profiles tab"""
        self._show_toolkit_config(initial_tab="Profiles")

    def _open_manage_versions(self):
        """Open the unified Version Manager dialog."""
        self.engine.log_debug("Opening Manage Versions dialog", "INFO")
        self._add_traceback("Opening Version Manager", "INFO")
        self.attributes('-topmost', False)

        try:
            dialog = tk.Toplevel(self)
            dialog.title("Version Manager")
            dialog.configure(bg='#2b2b2b')
            dialog.geometry("900x650")
            dialog.transient(self)

            if not VERSION_MANAGER_AVAILABLE:
                self.engine.log_debug("VersionManager module missing", "ERROR")
                messagebox.showerror("Error", "VersionManager module is missing.")
                dialog.destroy()
                return

            vm = VersionManager(os.path.join(self.project_root, "stable.json"))
            self.engine.log_debug(f"VersionManager initialized with root: {self.project_root}", "DEBUG")

            # Notebook for tabs
            notebook = ttk.Notebook(dialog)
            notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

            # Tab 1: Babel GUI Versions
            babel_tab = tk.Frame(notebook, bg='#2b2b2b')
            notebook.add(babel_tab, text="Babel GUI")
            self._build_babel_version_tab(babel_tab, vm)

            # Tab 2: Grep Flight Versions
            grep_tab = tk.Frame(notebook, bg='#2b2b2b')
            notebook.add(grep_tab, text="Grep Flight")
            self._build_grep_flight_version_tab(grep_tab, vm)

            # Close button at the bottom
            tk.Button(dialog, text="Close", command=dialog.destroy,
                     bg='#3c3c3c', fg='white', relief=tk.FLAT, width=15).pack(pady=10)

            dialog.wait_window()
        except Exception as e:
            self.engine.log_debug(f"Error in Version Manager: {e}", "ERROR")
            messagebox.showerror("Error", f"Failed to open Version Manager: {e}")
        finally:
            self.attributes('-topmost', True)
            self.engine.log_debug("Version Manager dialog closed", "DEBUG")

    def _build_babel_version_tab(self, parent, vm):
        """Build the UI for managing Babel GUI versions."""
        # Top: Selection
        top_frame = tk.Frame(parent, bg='#2b2b2b')
        top_frame.pack(fill=tk.X, padx=10, pady=10)

        versions = vm.get_versions()
        current = vm.get_current_version()
        
        tk.Label(top_frame, text="Select Version:", bg='#2b2b2b', fg='#cccccc').pack(side=tk.LEFT)
        
        version_var = tk.StringVar(value=current if current in versions else (versions[0] if versions else ""))
        combo = ttk.Combobox(top_frame, textvariable=version_var, values=versions, state='readonly', width=35)
        combo.pack(side=tk.LEFT, padx=10)

        # Details
        details_text = scrolledtext.ScrolledText(parent, height=15, bg='#1e1e1e', fg='#d4d4d4', 
                                               font=('Consolas', 10), state=tk.DISABLED)
        details_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        def update_details(event=None):
            v_name = version_var.get()
            data = vm.get_version_details(v_name)
            details_text.config(state=tk.NORMAL)
            details_text.delete(1.0, tk.END)
            if data:
                info = f"Version: {v_name}\n"
                if v_name == vm.get_current_version():
                    info += " (Active Default)\n"
                info += f"Status: {data.get('status', 'Unknown')}\n"
                info += f"Path: {data.get('path', 'N/A')}\n"
                info += f"Created: {data.get('created_at', 'N/A')}\n"
                info += f"Description: {data.get('description', '')}\n"
                details_text.insert(tk.END, info)
            details_text.config(state=tk.DISABLED)

        combo.bind("<<ComboboxSelected>>", update_details)
        update_details()

        # Actions
        btn_frame = tk.Frame(parent, bg='#2b2b2b')
        btn_frame.pack(fill=tk.X, padx=10, pady=10)

        def launch():
            try:
                vm.launch_version(version_var.get())
            except Exception as e:
                messagebox.showerror("Launch Error", str(e))

        def set_default():
            if vm.set_active_version(version_var.get()):
                messagebox.showinfo("Success", f"Set {version_var.get()} as default.")
                update_details()

        def migrate():
            self._migrate_version_ui(parent.winfo_toplevel(), vm, version_var.get())

        def scan_updates():
            v_name = version_var.get()
            if not v_name: return
            self.status_var.set(f"⌛ Scanning {v_name} for updates...")
            if vm.scan_for_updates(v_name):
                self.status_var.set(f"✅ Scan complete for {v_name}")
                messagebox.showinfo("Scan Complete", f"Successfully scanned '{v_name}' for updates.\nCheck the On-boarding Queue for new tools.")
                update_details()
            else:
                self.status_var.set("❌ Scan failed")

        def mark_status():
            v_name = version_var.get()
            if not v_name: return
            status = simpledialog.askstring("Mark Status", f"Enter status for {v_name} (Stable, Dev, Issues, Broken):", 
                                            initialvalue=vm.get_version_details(v_name).get('status', 'Development'))
            if status:
                if vm.mark_version_status(v_name, status):
                    messagebox.showinfo("Success", f"Marked {v_name} as {status}")
                    update_details()

        def set_active():
            v_name = version_var.get()
            if not v_name: return
            # Set active for current session
            self.active_version = v_name
            self.status_var.set(f"🚀 Active Version set to {v_name}")
            messagebox.showinfo("Success", f"Version '{v_name}' is now active for this panel session.")
            update_details()

        tk.Button(btn_frame, text="Launch", command=launch, bg='#2d7d46', fg='white').pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="Set Active", command=set_active, bg='#0e639c', fg='white').pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="Set Default", command=set_default, bg='#3c3c3c', fg='#ffffff').pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="Mark Status", command=mark_status, bg='#d67e00', fg='white').pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="Migrate/Clone", command=migrate, bg='#613d8c', fg='white').pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="Search for Updates", command=scan_updates, bg='#1e1e1e', fg='#4ec9b0').pack(side=tk.LEFT, padx=5)

    def _build_grep_flight_version_tab(self, parent, vm):
        """Build the UI for managing Grep Flight versions."""
        # Top: Selection
        top_frame = tk.Frame(parent, bg='#2b2b2b')
        top_frame.pack(fill=tk.X, padx=10, pady=10)

        versions = vm.get_grep_flight_versions()
        current = vm.get_current_grep_flight_version()
        
        tk.Label(top_frame, text="Select Version:", bg='#2b2b2b', fg='#cccccc').pack(side=tk.LEFT)
        
        version_var = tk.StringVar(value=current if current in versions else (versions[0] if versions else ""))
        combo = ttk.Combobox(top_frame, textvariable=version_var, values=versions, state='readonly', width=35)
        combo.pack(side=tk.LEFT, padx=10)

        # Details
        details_text = scrolledtext.ScrolledText(parent, height=15, bg='#1e1e1e', fg='#d4d4d4', 
                                               font=('Consolas', 10), state=tk.DISABLED)
        details_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        def update_details(event=None):
            v_name = version_var.get()
            data = vm.get_grep_flight_version_details(v_name)
            details_text.config(state=tk.NORMAL)
            details_text.delete(1.0, tk.END)
            if data:
                info = f"Version: {v_name}\n"
                if v_name == vm.get_current_grep_flight_version():
                    info += " (Active Default)\n"
                info += f"Path: {data.get('path', 'N/A')}\n"
                info += f"Created: {data.get('created_at', 'N/A')}\n"
                details_text.insert(tk.END, info)
            details_text.config(state=tk.DISABLED)

        combo.bind("<<ComboboxSelected>>", update_details)
        update_details()

        # Actions
        btn_frame = tk.Frame(parent, bg='#2b2b2b')
        btn_frame.pack(fill=tk.X, padx=10, pady=10)

        def set_active():
            v_name = version_var.get()
            if not v_name: return
            if vm.set_active_grep_flight_version(v_name):
                self.active_grep_flight_version = v_name
                self.status_var.set(f"🚀 Active Grep Flight: {v_name}")
                messagebox.showinfo("Success", f"Set {v_name} as active.")
                update_details()

        def set_default():
            v_name = version_var.get()
            if not v_name: return
            if messagebox.askyesno("Confirm Default", f"Set '{v_name}' as the permanent system default for Grep Flight?"):
                vm.config["current_grep_flight_version"] = v_name
                vm.save_config()
                self.status_var.set(f"⭐ System Default: {v_name}")
                update_details()

        def scan_updates():
            v_name = version_var.get()
            if not v_name: return
            self.status_var.set(f"⌛ Scanning {v_name} for updates...")
            if vm.scan_for_updates(v_name):
                self.status_var.set(f"✅ Scan complete for {v_name}")
                messagebox.showinfo("Scan Complete", f"Successfully scanned module '{v_name}'.")
                update_details()
            else:
                self.status_var.set("❌ Scan failed")

        def fetch_actions():
            """Fetch workflow actions from the selected version into current session"""
            v_name = version_var.get()
            if not v_name: return
            
            details = vm.get_grep_flight_version_details(v_name)
            v_path = self.project_root / details.get('path', '')
            profile_path = v_path / ".docv2_workspace" / "config" / "workflow_profiles.json"
            
            if profile_path.exists():
                try:
                    with open(profile_path, 'r') as f:
                        data = json.load(f)
                    
                    # Ask which profile to fetch from
                    profiles = list(data.get('profiles', {}).keys())
                    if not profiles:
                        messagebox.showwarning("Fetch Actions", "No profiles found in target version.")
                        return
                        
                    profile_to_fetch = simpledialog.askstring("Fetch Actions", 
                        f"Found {len(profiles)} profiles: {', '.join(profiles)}\n\nEnter profile name to fetch from:",
                        initialvalue=profiles[0])
                    
                    if profile_to_fetch in data['profiles']:
                        actions = data['profiles'][profile_to_fetch].get('workflow_actions', [])
                        count = 0
                        for action in actions:
                            if action.get('type') != 'placeholder':
                                if self._assign_workflow_slot(action):
                                    count += 1
                        
                        if count > 0:
                            self.status_var.set(f"📥 Fetched {count} actions from {v_name}")
                            messagebox.showinfo("Success", f"Successfully imported {count} actions into your current profile.")
                            self._build_workflow_buttons()
                        else:
                            messagebox.showwarning("Full", "No empty workflow slots available to import actions.")
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to fetch actions: {e}")
            else:
                messagebox.showwarning("Not Found", f"No workflow profiles found at:\n{profile_path}")

        def migrate():
            self._migrate_grep_flight_version_ui(parent.winfo_toplevel(), vm, version_var.get())

        tk.Button(btn_frame, text="Set Active", command=set_active, bg='#0e639c', fg='white').pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="Set Default", command=set_default, bg='#3c3c3c', fg='#ffffff').pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="Fetch Actions", command=fetch_actions, bg='#2d7d46', fg='white').pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="Search for Updates", command=scan_updates, bg='#1e1e1e', fg='#4ec9b0').pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="Migrate/Clone", command=migrate, bg='#d67e00', fg='white').pack(side=tk.LEFT, padx=5)

    def _migrate_grep_flight_version_ui(self, parent, vm, source_version):
        """UI for migrating a grep flight version."""
        if not source_version:
            return

        migration_win = tk.Toplevel(parent)
        migration_win.title(f"Migrate {source_version} (Grep Flight)")
        migration_win.geometry("500x350")
        migration_win.configure(bg='#2b2b2b')
        migration_win.transient(parent)

        tk.Label(migration_win, text=f"Source: {source_version}", bg='#2b2b2b', fg='#aaaaaa').pack(pady=10)

        tk.Label(migration_win, text="New Version Name:", bg='#2b2b2b', fg='white').pack()
        new_name_var = tk.StringVar(value=f"{source_version}_v2")
        tk.Entry(migration_win, textvariable=new_name_var, width=40).pack(pady=5)

        tk.Label(migration_win, text="Description / Notes:", bg='#2b2b2b', fg='white').pack()
        desc_text = tk.Text(migration_win, height=5, width=50)
        desc_text.pack(pady=5)

        def perform_migration():
            new_name = new_name_var.get().strip()
            desc = desc_text.get("1.0", tk.END).strip()
            
            if not new_name:
                messagebox.showerror("Error", "Version name is required.")
                return
            
            if new_name in vm.get_grep_flight_versions():
                messagebox.showerror("Error", "Version name already exists.")
                return

            if messagebox.askyesno("Confirm Migration", f"Create new Grep Flight version '{new_name}' from '{source_version}'?"):
                self.engine.log_debug(f"Migrating Grep Flight: {source_version} -> {new_name}", "INFO")
                if vm.create_new_grep_flight_version(source_version, new_name, desc):
                    self.engine.log_debug(f"Migration successful: {new_name}", "INFO")
                    messagebox.showinfo("Success", f"Version '{new_name}' created successfully.")
                    migration_win.destroy()
                else:
                    self.engine.log_debug(f"Migration failed for {new_name}", "ERROR")
                    messagebox.showerror("Error", "Migration failed. Check console for details.")

        tk.Button(migration_win, text="Migrate", bg='#d4a017', fg='black', command=perform_migration).pack(pady=20)

    def _migrate_version_ui(self, parent, vm, source_version):
        """UI for migrating a version."""
        if not source_version:
            return

        migration_win = tk.Toplevel(parent)
        migration_win.title(f"Migrate {source_version}")
        migration_win.geometry("500x350")
        migration_win.configure(bg='#2b2b2b')
        migration_win.transient(parent)

        tk.Label(migration_win, text=f"Source: {source_version}", bg='#2b2b2b', fg='#aaaaaa').pack(pady=10)

        tk.Label(migration_win, text="New Version Name:", bg='#2b2b2b', fg='white').pack()
        new_name_var = tk.StringVar(value=f"{source_version}_v2")
        tk.Entry(migration_win, textvariable=new_name_var, width=40).pack(pady=5)

        tk.Label(migration_win, text="Description / Notes:", bg='#2b2b2b', fg='white').pack()
        desc_text = tk.Text(migration_win, height=5, width=50)
        desc_text.pack(pady=5)

        def perform_migration():
            new_name = new_name_var.get().strip()
            desc = desc_text.get("1.0", tk.END).strip()
            
            if not new_name:
                messagebox.showerror("Error", "Version name is required.")
                return
            
            if new_name in vm.get_versions():
                messagebox.showerror("Error", "Version name already exists.")
                return

            if messagebox.askyesno("Confirm Migration", f"Create new version '{new_name}' from '{source_version}'?"):
                if vm.create_new_version(source_version, new_name, desc):
                    messagebox.showinfo("Success", f"Version '{new_name}' created successfully.")
                    migration_win.destroy()
                else:
                    messagebox.showerror("Error", "Migration failed. Check console for details.")

        tk.Button(migration_win, text="Migrate", bg='#d4a017', fg='black', command=perform_migration).pack(pady=20)


        def set_default_version():
            version_name = selected_version.get()
            if not version_name:
                messagebox.showwarning("Set Default", "Select a version first.")
                return
            details = stable_config.get("versions", {}).get(version_name, {})
            status = details.get('status', '')
            if status.lower() != 'stable':
                messagebox.showwarning("Set Default", "Mark the version as Stable before setting it as default.")
                return

            stable_config["current_stable_version"] = version_name
            stable_path = self.project_root / "stable.json"
            with open(stable_path, 'w') as f:
                json.dump(stable_config, f, indent=4)
            self.engine.log_debug(f"Version '{version_name}' set as default via Manage Versions panel", "INFO")
            self.status_var.set(f"✅ Default version set to {version_name}")
            display_version_details()

        version_combo.bind('<<ComboboxSelected>>', lambda e: display_version_details())
        refresh_btn.config(command=refresh_versions)
        open_btn.config(command=open_version_folder)
        set_default_btn.config(command=set_default_version)

        display_version_details()
        dialog.focus_set()
        dialog.grab_set()
        try:
            self.wait_window(dialog)
        finally:
            self.attributes('-topmost', True)

    def _show_help(self):
        """Show help dialog"""
        self.attributes('-topmost', False)
        HelpDialog(self, self.config)
        self.attributes('-topmost', True)

    # _load_and_sync_versions_config removed - replaced by VersionManager
    
    def _create_tooltip(self, widget, text):
        """Create a simple tooltip"""
        def show_tooltip(event):
            tooltip = tk.Toplevel(self)
            tooltip.wm_overrideredirect(True)
            label = tk.Label(tooltip, text=text, bg='lightyellow',
                           relief='solid', borderwidth=1)
            label.pack()
            x, y = self.winfo_pointerxy()
            tooltip.geometry(f"+{x+10}+{y+10}")

            def hide_tooltip():
                tooltip.destroy()

            widget.bind('<Leave>', lambda e: hide_tooltip())
            tooltip.after(2000, hide_tooltip)

        widget.bind('<Enter>', show_tooltip)

    def _create_tooltip_simple(self, widget, text):
        """Simplified tooltip creation"""
        self._create_tooltip(widget, text)

    def _show_recent_targets(self):
        """Show dropdown menu with recent targets"""
        try:
            if not hasattr(self.engine, 'recent_targets') or not self.engine.recent_targets:
                self.status_var.set("No recent targets")
                return

            menu = tk.Menu(self, tearoff=0, bg='#2a2a2a', fg=self.config.FG_COLOR)
            for target in list(self.engine.recent_targets)[:10]:  # Limit to 10
                display_name = Path(target).name if len(target) > 40 else target
                menu.add_command(label=f"📁 {display_name}",
                               command=lambda t=target: self._select_recent_target(t))

            # Use tk_popup instead of post - more reliable
            try:
                menu.tk_popup(self.winfo_pointerx(), self.winfo_pointery())
            finally:
                menu.grab_release()
        except Exception as e:
            self.engine.log_debug(f"Error showing recent targets: {e}", "ERROR")
            self.status_var.set(f"Error: {e}")

    def _select_recent_target(self, target: str):
        """Select a target from recent history"""
        self.target_var.set(target)
        self.engine.set_target(target)
        self.status_var.set(f"✅ Target: {Path(target).name}")

    def _show_recent_patterns(self):
        """Show dropdown menu with recent patterns"""
        try:
            if not hasattr(self.engine, 'recent_patterns') or not self.engine.recent_patterns:
                self.status_var.set("No recent patterns")
                return

            menu = tk.Menu(self, tearoff=0, bg='#2a2a2a', fg=self.config.FG_COLOR)
            for pattern in list(self.engine.recent_patterns)[:10]:  # Limit to 10
                menu.add_command(label=f"🔍 {pattern}",
                               command=lambda p=pattern: self._select_recent_pattern(p))

            try:
                menu.tk_popup(self.winfo_pointerx(), self.winfo_pointery())
            finally:
                menu.grab_release()
        except Exception as e:
            self.engine.log_debug(f"Error showing recent patterns: {e}", "ERROR")
            self.status_var.set(f"Error: {e}")

    def _select_recent_pattern(self, pattern: str):
        """Select a pattern from recent history"""
        self.pattern_var.set(pattern)
        self.engine.set_pattern(pattern)
        self.status_var.set(f"🔍 Pattern: {pattern}")

    def _show_pattern_presets(self):
        """Show dropdown menu with common pattern presets"""
        presets = {
            "TODO/FIXME/BUG": r"\(TODO\|FIXME\|BUG\):",
            "Email Addresses": r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
            "IP Addresses": r"([0-9]{1,3}\.){3}[0-9]{1,3}",
            "URLs (http/https)": r"https?://[a-zA-Z0-9./?=_-]+",
            "Hex Colors": r"#[0-9a-fA-F]{6}",
            "Phone Numbers (US)": r"\d{3}[-.]?\d{3}[-.]?\d{4}",
            "Python Functions": r"^def [a-zA-Z_][a-zA-Z0-9_]*",
            "Python Classes": r"^class [a-zA-Z_][a-zA-Z0-9_]*",
            "Python Imports": r"^import\|^from.*import",
            "Error/Exception": r"\(error\|exception\|fail\)",
            "Password Patterns": r"password\s*=\s*['\"][^'\"]+['\"]",
            "JSON Keys": r'"[^"]+"\s*:',
        }

        menu = tk.Menu(self, tearoff=0, bg='#2a2a2a', fg=self.config.FG_COLOR)
        for name, pattern in presets.items():
            menu.add_command(label=f"⚡ {name}",
                           command=lambda p=pattern, n=name: self._select_pattern_preset(p, n))

        try:
            menu.post(self.winfo_pointerx(), self.winfo_pointery())
        finally:
            menu.grab_release()

    def _select_pattern_preset(self, pattern: str, name: str):
        """Select a pattern preset"""
        self.pattern_var.set(pattern)
        self.engine.set_pattern(pattern)
        self.status_var.set(f"⚡ Pattern preset: {name}")

    # Quick Action Methods for babel_gui navigation
    def _launch_inventory(self):
        """Launch babel_gui Inventory tab"""
        if self.app_ref and hasattr(self.app_ref, 'notebook') and hasattr(self.app_ref, 'inventory_frame'):
            self.app_ref.notebook.select(self.app_ref.inventory_frame)
            self.engine.log_debug("Quick action: Switched to Inventory tab", "INFO")
            self.status_var.set("📦 Opened Inventory tab")
            log_to_traceback(EventCategory.INFO, "quick_action_inventory",
                           {"source": "grep_flight"}, {"status": "switched_to_inventory"})
        else:
            self.status_var.set("⚠️ Inventory tab not available")
            self.engine.log_debug("Quick action failed: Inventory tab not available", "WARNING")

    def _launch_tasks(self):
        """Launch babel_gui Tasks tab"""
        if self.app_ref and hasattr(self.app_ref, 'notebook') and hasattr(self.app_ref, 'tasks_frame'):
            self.app_ref.notebook.select(self.app_ref.tasks_frame)
            self.engine.log_debug("Quick action: Switched to Tasks tab", "INFO")
            self.status_var.set("📋 Opened Tasks tab")
            log_to_traceback(EventCategory.INFO, "quick_action_tasks",
                           {"source": "grep_flight"}, {"status": "switched_to_tasks"})
        else:
            self.status_var.set("⚠️ Tasks tab not available")
            self.engine.log_debug("Quick action failed: Tasks tab not available", "WARNING")

    def _launch_planner(self):
        """Launch babel_gui Planner tab"""
        if self.app_ref and hasattr(self.app_ref, 'notebook') and hasattr(self.app_ref, 'planner_panel'):
            self.app_ref.notebook.select(self.app_ref.planner_panel)
            self.engine.log_debug("Quick action: Switched to Planner tab", "INFO")
            self.status_var.set("📋 Opened Planner tab")
            log_to_traceback(EventCategory.INFO, "quick_action_planner",
                           {"source": "grep_flight"}, {"status": "switched_to_planner"})
        else:
            self.status_var.set("⚠️ Planner tab not available")
            self.engine.log_debug("Quick action failed: Planner tab not available", "WARNING")

    def _launch_chat(self):
        """Launch babel_gui Chat tab"""
        if self.app_ref and hasattr(self.app_ref, 'notebook') and hasattr(self.app_ref, 'chat_frame'):
            self.app_ref.notebook.select(self.app_ref.chat_frame)
            self.engine.log_debug("Quick action: Switched to Chat tab", "INFO")
            self.status_var.set("💬 Opened Chat tab")
            log_to_traceback(EventCategory.INFO, "quick_action_chat",
                           {"source": "grep_flight"}, {"status": "switched_to_chat"})
        else:
            self.status_var.set("⚠️ Chat tab not available")
            self.engine.log_debug("Quick action failed: Chat tab not available", "WARNING")

    def _launch_diff(self):
        """Launch babel_gui Diff tab"""
        if self.app_ref and hasattr(self.app_ref, 'notebook') and hasattr(self.app_ref, 'diff_frame'):
            self.app_ref.notebook.select(self.app_ref.diff_frame)
            self.engine.log_debug("Quick action: Switched to Diff tab", "INFO")
            self.status_var.set("📊 Opened Diff tab")
            log_to_traceback(EventCategory.INFO, "quick_action_diff",
                           {"source": "grep_flight"}, {"status": "switched_to_diff"})
        else:
            self.status_var.set("⚠️ Diff tab not available")
            self.engine.log_debug("Quick action failed: Diff tab not available", "WARNING")

    def _launch_editor_tab(self):
        """Launch babel_gui Editor tab"""
        if self.app_ref and hasattr(self.app_ref, 'notebook') and hasattr(self.app_ref, 'editor_frame'):
            self.app_ref.notebook.select(self.app_ref.editor_frame)
            self.engine.log_debug("Quick action: Switched to Editor tab", "INFO")
            self.status_var.set("✏️ Opened Editor tab")
            log_to_traceback(EventCategory.INFO, "quick_action_editor",
                           {"source": "grep_flight"}, {"status": "switched_to_editor"})
        else:
            self.status_var.set("⚠️ Editor tab not available")
            self.engine.log_debug("Quick action failed: Editor tab not available", "WARNING")

    # Engineers Toolkit Methods
    def _show_toolkit_popup(self):
        """Show Engineers Toolkit popup window"""
        # Close existing popup if open
        if self.toolkit_popup and self.toolkit_popup.winfo_exists():
            self.toolkit_popup.lift()
            return

        # Create popup window
        self.toolkit_popup = tk.Toplevel(self)
        self.toolkit_popup.title("Engineers Toolkit")
        self.toolkit_popup.geometry("650x350")
        self.toolkit_popup.configure(bg='#1e1e1e')
        self.toolkit_popup.transient(self)  # Keep on top of grep_flight
        self.toolkit_popup.attributes('-topmost', True)

        # Position at top of grep_flight expanded panel
        x = self.winfo_x()
        y = self.winfo_y() - 360  # Above the grep_flight window
        self.toolkit_popup.geometry(f"+{x}+{y}")

        # Bind ESC key to close
        self.toolkit_popup.bind('<Escape>', lambda e: self.toolkit_popup.destroy())

        # Header with config button
        header_frame = tk.Frame(self.toolkit_popup, bg='#1e1e1e')
        header_frame.pack(fill=tk.X, pady=10, padx=10)

        tk.Label(
            header_frame,
            text="🔧 Engineers Toolkit - Select a Tool",
            bg='#1e1e1e',
            fg='#4ec9b0',
            font=('Arial', 11, 'bold')
        ).pack(side=tk.LEFT)

        tk.Button(
            header_frame,
            text="⚙️ Configure",
            command=self._show_toolkit_config,
            bg='#2d2d2d',
            fg='#d4d4d4',
            relief=tk.RAISED,
            bd=1,
            font=('Arial', 8)
        ).pack(side=tk.RIGHT)

        # Instructions
        instructions = tk.Label(
            self.toolkit_popup,
            text="Click a tool to run on current target. Press ESC to close. Configure to reorder tools.",
            bg='#1e1e1e',
            fg='#888888',
            font=('Arial', 8)
        )
        instructions.pack(pady=(0, 10))

        # Main container for tools
        tools_container = tk.Frame(self.toolkit_popup, bg='#1e1e1e')
        tools_container.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        # Define Engineers Toolkit functions
        toolkit_functions = [
            ("✅ Syntax Check", self._run_syntax_check, "Check Python syntax errors"),
            ("↔️ Indentation", self._run_indentation_check, "Check indentation consistency"),
            ("📦 Imports", self._run_imports_check, "Analyze import statements"),
            ("🎨 Formatting", self._run_formatting_check, "Check code formatting (Black/Ruff)"),
            ("🔍 Linting", self._run_linting_check, "Run linting checks (Pyflakes/Ruff)"),
            ("📞 Call Changes", self._run_call_changes_check, "Detect function signature changes"),
            ("🚀 All Checks", self._run_all_checks, "Run all quality checks"),
            ("🔄 Auto-Fix", self._run_auto_fix, "Auto-fix formatting and style issues"),
            ("📸 Snapshot", self._create_snapshot, "Create project snapshot"),
            ("🧹 Clean", self._clean_project, "Clean build artifacts and cache"),
        ]

        # Create 2 rows of 5 buttons each
        for row_num in range(2):
            row_frame = tk.Frame(tools_container, bg='#1e1e1e')
            row_frame.pack(fill=tk.X, pady=5)

            start_idx = row_num * 5
            end_idx = start_idx + 5

            for i in range(start_idx, end_idx):
                if i < len(toolkit_functions):
                    text, command, tooltip = toolkit_functions[i]

                    btn = tk.Button(
                        row_frame,
                        text=text,
                        command=lambda c=command: self._run_toolkit_command(c),
                        bg='#2d2d2d',
                        fg='#d4d4d4',
                        activebackground='#4ec9b0',
                        activeforeground='#000000',
                        relief=tk.RAISED,
                        bd=2,
                        width=18,
                        height=2,
                        font=('Arial', 9)
                    )
                    btn.pack(side=tk.LEFT, padx=5, expand=True, fill=tk.X)
                    self._create_tooltip(btn, tooltip)

        # Close button
        close_btn = tk.Button(
            self.toolkit_popup,
            text="Close",
            command=self.toolkit_popup.destroy,
            bg='#2d2d2d',
            fg='#d4d4d4',
            relief=tk.RAISED,
            bd=1,
            width=10
        )
        close_btn.pack(pady=10)

        self.engine.log_debug("Engineers Toolkit popup opened", "INFO")
        self.status_var.set("🔧 Toolkit popup opened")

    def _run_toolkit_command(self, command):
        """Run toolkit command and keep popup visible"""
        command()
        # Popup stays open for multiple operations

    def _show_toolkit_config(self, parent=None, initial_tab=None):
        """Show comprehensive configuration UI with tabs for workflows, tools, profiles, and custom scripts"""
        host = parent
        if host is None:
            if self.toolkit_popup and self.toolkit_popup.winfo_exists():
                host = self.toolkit_popup
            else:
                host = self

        config_window = tk.Toplevel(host)
        config_window.title("Action-Panel Configuration")
        config_window.geometry("850x600")
        config_window.configure(bg='#1e1e1e')
        config_window.transient(host)
        config_window.attributes('-topmost', True)

        # Header with profile selector
        header_frame = tk.Frame(config_window, bg='#1e1e1e')
        header_frame.pack(fill=tk.X, pady=10, padx=20)

        tk.Label(
            header_frame,
            text="⚙️ Action-Panel Configuration",
            bg='#1e1e1e',
            fg='#4ec9b0',
            font=('Arial', 12, 'bold')
        ).pack(side=tk.LEFT)

        # Current profile selector
        profile_frame = tk.Frame(header_frame, bg='#1e1e1e')
        profile_frame.pack(side=tk.RIGHT)

        tk.Label(profile_frame, text="Profile:", bg='#1e1e1e', fg='#888888',
                font=('Arial', 9)).pack(side=tk.LEFT, padx=(0, 5))

        current_profile = getattr(self, 'active_profile', None) or "Default Profile"
        self.current_profile_var = tk.StringVar(value=current_profile)
        profile_combo = ttk.Combobox(
            profile_frame,
            textvariable=self.current_profile_var,
            values=self._load_profile_names(),
            width=20,
            state='readonly'
        )
        profile_combo.pack(side=tk.LEFT)

        # A1: Pre-select active profile
        if self.active_profile and self.active_profile in self._load_profile_names():
            self.current_profile_var.set(self.active_profile)

        # A2: Profile change refreshes all tabs
        def on_profile_change(e):
            self._load_profile_config()
            if hasattr(self, '_refresh_workflow_config'):
                self._refresh_workflow_config()
            if hasattr(self, '_refresh_toolkit_config'):
                self._refresh_toolkit_config()

        profile_combo.bind('<<ComboboxSelected>>', on_profile_change)

        # Create notebook for tabs
        notebook = ttk.Notebook(config_window)
        notebook.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        # TAB 1: Workflow Actions (existing 4 + custom, up to 8 total)
        self._create_workflow_config_tab(notebook)

        # TAB 2: Toolkit Tools (10 engineers_toolkit functions)
        self._create_toolkit_config_tab(notebook)

        # TAB 3: System Catalog (NEW: System-wide discovery)
        self._create_catalog_tab(notebook)

        # TAB 4: Script Profiles (create/edit/delete profiles)
        self._create_profiles_tab(notebook)

        # TAB 4: Custom Scripts (add custom tools with args)
        self._create_custom_scripts_tab(notebook)

        # TAB 5: Tool Profiles (aggregate view)
        self._create_tool_profiles_tab(notebook)

        # TAB 6: On-boarding Queue (📥)
        self._create_onboarding_queue_tab(notebook)
        
        # Select initial tab if specified
        if initial_tab is not None:
            # If string name passed
            if isinstance(initial_tab, str):
                for i in range(notebook.index("end")):
                    if notebook.tab(i, "text") == initial_tab:
                        notebook.select(i)
                        break
            # If integer index passed
            elif isinstance(initial_tab, int):
                if initial_tab < notebook.index("end"):
                    notebook.select(initial_tab)

        # Bottom buttons
        button_frame = tk.Frame(config_window, bg='#1e1e1e')
        button_frame.pack(fill=tk.X, pady=10, padx=20)

        tk.Button(
            button_frame,
            text="💾 Save Profile",
            command=lambda: self._save_profile_config(config_window),
            bg='#4ec9b0',
            fg='#000000',
            relief=tk.RAISED,
            bd=2,
            width=15,
            font=('Arial', 9, 'bold')
        ).pack(side=tk.LEFT, padx=5)

        tk.Button(
            button_frame,
            text="Close",
            command=config_window.destroy,
            bg='#2d2d2d',
            fg='#d4d4d4',
            relief=tk.RAISED,
            bd=1,
            width=10
        ).pack(side=tk.RIGHT, padx=5)

        # ESC to close
        config_window.bind('<Escape>', lambda e: config_window.destroy())

    def _create_workflow_config_tab(self, notebook):
        """TAB 1: Configure slot actions (up to 8)"""
        workflow_tab = tk.Frame(notebook, bg='#1e1e1e')
        notebook.add(workflow_tab, text="⚡ Slot Configuration")

        # Instructions
        tk.Label(
            workflow_tab,
            text="Configure the 8 action slots for the active profile. Drag and drop or use arrows to reorder. These are single commands or tools.",
            bg='#1e1e1e',
            fg='#888888',
            font=('Arial', 9),
            wraplength=750,
            justify=tk.LEFT
        ).pack(pady=10, padx=10)

        # Load current workflow order from config
        profile_actions = self._load_workflow_actions_from_profile()
        if profile_actions:
            self.workflow_actions = self._pad_workflow_actions(profile_actions)
        else:
            self.workflow_actions = self._pad_workflow_actions(self._default_workflow_actions())

        # Scrollable list
        list_container = tk.Frame(workflow_tab, bg='#1e1e1e')
        list_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        canvas = tk.Canvas(list_container, bg='#1e1e1e', highlightthickness=0)
        scrollbar = tk.Scrollbar(list_container, orient=tk.VERTICAL, command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg='#1e1e1e')

        scrollable_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    def _refresh_workflow_config_list(self):
        # A3: Re-read profile data on each refresh (not captured once at tab creation)
        profile_actions = self._load_workflow_actions_from_profile()
        if profile_actions:
            self.workflow_actions = self._pad_workflow_actions(profile_actions)

        for widget in self.scrollable_workflow_frame.winfo_children():
            widget.destroy()

        for i, action in enumerate(self.workflow_actions):
            row = tk.Frame(self.scrollable_workflow_frame, bg='#2d2d2d', relief=tk.RAISED, bd=1)
            row.pack(fill=tk.X, padx=5, pady=3)

            # Position
            tk.Label(row, text=f"{i+1}.", bg='#2d2d2d', fg='#888888',
                    font=('Monospace', 9), width=3).pack(side=tk.LEFT, padx=5)

            # Action name
            name_color = '#d4d4d4' if action['type'] != 'placeholder' else '#666666'
            tk.Label(row, text=action['name'], bg='#2d2d2d', fg=name_color,
                    font=('Arial', 9, 'bold'), width=15, anchor='w').pack(side=tk.LEFT, padx=5)

            # Type
            tk.Label(row, text=f"[{action['type']}]", bg='#2d2d2d', fg='#888888',
                    font=('Monospace', 7), width=12, anchor='w').pack(side=tk.LEFT, padx=2)

            # Target mode
            tk.Label(row, text=f"Target: {action.get('target_mode', 'auto')}", bg='#2d2d2d',
                    fg='#4ec9b0', font=('Monospace', 7), width=15, anchor='w').pack(side=tk.LEFT, padx=2)

            # Output destination
            tk.Label(row, text=f"→ {action.get('output_to', 'results')}", bg='#2d2d2d',
                    fg='#ce9178', font=('Monospace', 7), width=18, anchor='w').pack(side=tk.LEFT, padx=2)

            # Expectations
            tk.Label(row, text=f"Expects: {action.get('expectations', 'none')}", bg='#2d2d2d',
                    fg='#569cd6', font=('Monospace', 7), width=20, anchor='w').pack(side=tk.LEFT, padx=2)

            # Buttons frame
            buttons_frame = tk.Frame(row, bg='#2d2d2d')
            buttons_frame.pack(side=tk.RIGHT, padx=5)

            # Edit button (for custom or placeholder)
            if action['type'] in ['custom', 'placeholder']:
                tk.Button(buttons_frame, text="✏️", command=lambda idx=i: self._edit_workflow_action(idx, self._refresh_workflow_config_list),
                         bg='#3d3d3d', fg='#d4d4d4', relief=tk.RAISED, bd=1, width=2).pack(side=tk.LEFT, padx=1)

            # Up arrow
            if i > 0:
                tk.Button(buttons_frame, text="▲", command=lambda idx=i: self._move_workflow_up(idx, self._refresh_workflow_config_list),
                         bg='#3d3d3d', fg='#d4d4d4', relief=tk.RAISED, bd=1, width=2).pack(side=tk.LEFT, padx=1)

            # Down arrow
            if i < len(self.workflow_actions) - 1:
                tk.Button(buttons_frame, text="▼", command=lambda idx=i: self._move_workflow_down(idx, self._refresh_workflow_config_list),
                         bg='#3d3d3d', fg='#d4d4d4', relief=tk.RAISED, bd=1, width=2).pack(side=tk.LEFT, padx=1)

        self._build_workflow_buttons()

    def _create_toolkit_config_tab(self, notebook):
        """TAB 2: Configure toolkit tools order (existing functionality)"""
        toolkit_tab = tk.Frame(notebook, bg='#1e1e1e')
        notebook.add(toolkit_tab, text="🔧 Toolkit Tools")

        # Instructions
        tk.Label(
            toolkit_tab,
            text="Reorder Engineers Toolkit functions. These appear in the 'More Tools' popup.",
            bg='#1e1e1e',
            fg='#888888',
            font=('Arial', 9)
        ).pack(pady=10, padx=10)

        # Load current tool order from config (default order for now)
        if not self.toolkit_order:
            self.toolkit_order = self._default_toolkit_order()

        # Main list frame with scrollbar
        list_frame = tk.Frame(toolkit_tab, bg='#1e1e1e')
        list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Canvas for scrolling
        canvas = tk.Canvas(list_frame, bg='#1e1e1e', highlightthickness=0)
        scrollbar = tk.Scrollbar(list_frame, orient=tk.VERTICAL, command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg='#1e1e1e')

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Create tool list with arrow buttons
        def refresh_list():
            # Clear existing widgets
            for widget in scrollable_frame.winfo_children():
                widget.destroy()

            # Create rows for each tool
            for i, tool in enumerate(self.toolkit_order):
                row = tk.Frame(scrollable_frame, bg='#2d2d2d', relief=tk.RAISED, bd=1)
                row.pack(fill=tk.X, padx=5, pady=2)

                # Position indicator
                tk.Label(
                    row,
                    text=f"{i+1}.",
                    bg='#2d2d2d',
                    fg='#888888',
                    font=('Monospace', 9),
                    width=3
                ).pack(side=tk.LEFT, padx=5)

                # Tool name
                tk.Label(
                    row,
                    text=tool['name'],
                    bg='#2d2d2d',
                    fg='#d4d4d4',
                    font=('Arial', 9, 'bold'),
                    width=20,
                    anchor='w'
                ).pack(side=tk.LEFT, padx=5)

                # Function name
                tk.Label(
                    row,
                    text=f"→ {tool['func']}()",
                    bg='#2d2d2d',
                    fg='#4ec9b0',
                    font=('Monospace', 8),
                    width=20,
                    anchor='w'
                ).pack(side=tk.LEFT, padx=5)

                # Source path (shortened)
                source_short = ".../" + Path(tool['source']).name
                tk.Label(
                    row,
                    text=source_short,
                    bg='#2d2d2d',
                    fg='#888888',
                    font=('Monospace', 7),
                    width=25,
                    anchor='w'
                ).pack(side=tk.LEFT, padx=5)

                # Arrow buttons frame
                arrows_frame = tk.Frame(row, bg='#2d2d2d')
                arrows_frame.pack(side=tk.RIGHT, padx=5)

                # Up arrow
                if i > 0:
                    tk.Button(
                        arrows_frame,
                        text="▲",
                        command=lambda idx=i: move_up(idx),
                        bg='#3d3d3d',
                        fg='#d4d4d4',
                        relief=tk.RAISED,
                        bd=1,
                        width=2
                    ).pack(side=tk.LEFT, padx=1)

                # Down arrow
                if i < len(self.toolkit_order) - 1:
                    tk.Button(
                        arrows_frame,
                        text="▼",
                        command=lambda idx=i: move_down(idx),
                        bg='#3d3d3d',
                        fg='#d4d4d4',
                        relief=tk.RAISED,
                        bd=1,
                        width=2
                    ).pack(side=tk.LEFT, padx=1)

        def move_up(idx):
            if idx > 0:
                self.toolkit_order[idx], self.toolkit_order[idx-1] = self.toolkit_order[idx-1], self.toolkit_order[idx]
                refresh_list()

        def move_down(idx):
            if idx < len(self.toolkit_order) - 1:
                self.toolkit_order[idx], self.toolkit_order[idx+1] = self.toolkit_order[idx+1], self.toolkit_order[idx]
                refresh_list()

        refresh_list()
        # A2: Store refresh callback for cross-tab coordination
        self._refresh_toolkit_config = refresh_list

    def _create_catalog_tab(self, notebook):
        """TAB 3: System Catalog - System-wide file explorer with Os_Toolkit integration"""
        catalog_tab = tk.Frame(notebook, bg='#1e1e1e')
        notebook.add(catalog_tab, text="📂 System Catalog")

        # --- Data store ---
        self.cataloged_paths = set()
        self._load_cataloged_paths()

        # --- UI Layout ---
        main_pane = tk.PanedWindow(catalog_tab, orient=tk.HORIZONTAL, bg='#1e1e1e', sashrelief=tk.RAISED, sashwidth=4)
        main_pane.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Left Panel: File Tree (Starting from /)
        left_frame = tk.Frame(main_pane, bg='#1e1e1e')
        
        tree_header = tk.Frame(left_frame, bg='#1e1e1e')
        tree_header.pack(fill=tk.X)
        tk.Label(tree_header, text="File System (/) ", bg='#1e1e1e', fg='#4ec9b0', font=('Arial', 10, 'bold')).pack(side=tk.LEFT, pady=2)
        
        tk.Button(tree_header, text="↻", command=self._refresh_catalog_tree, bg='#1e1e1e', fg='#4ec9b0', bd=0, font=('Arial', 10, 'bold')).pack(side=tk.RIGHT, padx=5)

        tree_frame = tk.Frame(left_frame, bg='#2d2d2d')
        tree_frame.pack(fill=tk.BOTH, expand=True)
        
        self.catalog_tree = ttk.Treeview(tree_frame, show="tree", selectmode="browse")
        self.catalog_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Configure tags for catalog status
        self.catalog_tree.tag_configure('cataloged', foreground='#4ec9b0') # Teal
        self.catalog_tree.tag_configure('uncataloged', foreground='#888888') # Gray
        self.catalog_tree.tag_configure('directory', foreground='#569cd6') # Blue

        csb = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.catalog_tree.yview)
        self.catalog_tree.configure(yscrollcommand=csb.set)
        csb.pack(side=tk.RIGHT, fill=tk.Y)

        main_pane.add(left_frame, width=300, stretch="never")

        # Right Panel: Os_Toolkit Details
        right_frame = tk.Frame(main_pane, bg='#1e1e1e')
        tk.Label(right_frame, text="Profiling & Context", bg='#1e1e1e', fg='#4ec9b0', font=('Arial', 10, 'bold')).pack(anchor=tk.W, pady=2)
        
        # Action Buttons for Catalog
        catalog_btn_frame = tk.Frame(right_frame, bg='#1e1e1e')
        catalog_btn_frame.pack(fill=tk.X, pady=(0, 5))
        
        def run_catalog_action(cmd_args):
            item = self.catalog_tree.focus()
            if not item: return
            path = self.catalog_tree.item(item, "tags")[0]
            full_cmd = f"python3 '{self.babel_root}/Os_Toolkit.py' {cmd_args} '{path}' -z"
            subprocess.Popen(full_cmd, shell=True)
            self.status_var.set(f"Running: Os_Toolkit {cmd_args} on {Path(path).name}")
            
        def onboard_selected():
            item = self.catalog_tree.focus()
            if not item: return
            path = self.catalog_tree.item(item, "tags")[0]
            self.status_var.set(f"🚀 Onboarding: {Path(path).name}...")
            
            # Run onboarder discover on this specific file with targeted parameter
            onboard_cmd = f"python3 '{self.babel_root}/onboarder.py' discover --target '{path}' --consolidate -s current_session"
            subprocess.Popen(onboard_cmd, shell=True)
            
            # Re-load paths after a delay to reflect changes
            self.after(3000, self._load_cataloged_paths)
            self.after(3100, self._refresh_catalog_tree)
            self._add_traceback(f"🚀 Started Targeted Onboarding: {path}", "INFO")

        tk.Button(catalog_btn_frame, text="Analyze Branch", command=lambda: run_catalog_action("analyze --depth 2")).pack(side=tk.LEFT, padx=2)
        tk.Button(catalog_btn_frame, text="Profile File", command=lambda: run_catalog_action("file")).pack(side=tk.LEFT, padx=2)
        tk.Button(catalog_btn_frame, text="Onboard", command=onboard_selected, bg='#2d7d46', fg='white').pack(side=tk.LEFT, padx=10)
        tk.Button(catalog_btn_frame, text="Set as Target", command=self._set_catalog_as_target).pack(side=tk.RIGHT, padx=2)

        details_container = tk.Frame(right_frame, bg='#2d2d2d')
        details_container.pack(fill=tk.BOTH, expand=True)
        
        self.catalog_details = scrolledtext.ScrolledText(details_container, bg='#1e1e1e', fg='#d4d4d4', font=('Monospace', 9), relief=tk.FLAT)
        self.catalog_details.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)

        main_pane.add(right_frame, width=500, stretch="always")

        # --- Bindings ---
        self.catalog_tree.bind("<<TreeviewOpen>>", self._on_catalog_expand)
        self.catalog_tree.bind("<<TreeviewSelect>>", self._on_catalog_select)
        self.catalog_tree.bind("<Button-3>", self._on_catalog_right_click)

        # Initial populate
        self._refresh_catalog_tree()

    def _load_cataloged_paths(self):
        """Load paths that are already in the consolidated menu"""
        try:
            menu_file = self.babel_root / "babel_data" / "inventory" / "consolidated_menu.json"
            if menu_file.exists():
                with open(menu_file, 'r') as f:
                    data = json.load(f)
                    for tool in data.get('tools', []):
                        if tool.get('path'):
                            # Store both absolute and relative if possible
                            abs_path = str(Path(tool['path']).resolve())
                            self.cataloged_paths.add(abs_path)
            self.engine.log_debug(f"Loaded {len(self.cataloged_paths)} cataloged paths", "INFO")
        except Exception as e:
            self.engine.log_debug(f"Error loading cataloged paths: {e}", "ERROR")

    def _refresh_catalog_tree(self):
        """Rebuild the catalog tree starting from root"""
        self.catalog_tree.delete(*self.catalog_tree.get_children())
        self._add_catalog_node("", "/")

    def _add_catalog_node(self, parent, path):
        """Insert a node into the catalog tree with status-based coloring"""
        node_text = os.path.basename(path) or path
        
        # Determine status and tags
        tags = [path]
        if os.path.isdir(path):
            tags.append('directory')
        else:
            abs_path = str(Path(path).resolve())
            if abs_path in self.cataloged_paths:
                tags.append('cataloged')
            else:
                tags.append('uncataloged')

        node_id = self.catalog_tree.insert(parent, "end", text=f"  {node_text}", tags=tuple(tags))
        
        if os.path.isdir(path):
            # Check for dummy
            self.catalog_tree.insert(node_id, "end", text="Loading...")

    def _on_catalog_expand(self, event):
        """Handle tree expansion with dynamic loading"""
        node_id = self.catalog_tree.focus()
        if not node_id: return
        
        children = self.catalog_tree.get_children(node_id)
        if children and self.catalog_tree.item(children[0])["text"] == "Loading...":
            self.catalog_tree.delete(children[0])
            path = self.catalog_tree.item(node_id, "tags")[0]
            try:
                # Use sorted list of directories first, then files
                items = sorted(os.listdir(path))
                dirs = []
                files = []
                for item in items:
                    if item.startswith('.') and item != '.docv2_workspace': continue
                    full_path = os.path.join(path, item)
                    if os.path.isdir(full_path):
                        dirs.append(full_path)
                    else:
                        files.append(full_path)
                
                for d in dirs: self._add_catalog_node(node_id, d)
                for f in files: self._add_catalog_node(node_id, f)
                
            except Exception as e:
                self.catalog_tree.insert(node_id, "end", text=f"Error: {str(e)}")

    def _on_catalog_select(self, event):
        """Log catalog selection and query context"""
        item = self.catalog_tree.focus()
        if not item: return
        tags = self.catalog_tree.item(item, "tags")
        if not tags: return
        path = tags[0]
        
        self.catalog_details.delete(1.0, tk.END)
        self.catalog_details.insert(tk.END, f"Selected: {path}\n")
        
        is_cataloged = str(Path(path).resolve()) in self.cataloged_paths
        status_text = "STATUS: [✓] CATALOGED" if is_cataloged else "STATUS: [ ] UNCATALOGED"
        self.catalog_details.insert(tk.END, f"{status_text}\n")
        self.catalog_details.insert(tk.END, "Querying Os_Toolkit for context...\n")
        
        # Log to traceback
        self.engine.log_debug(f"#[Event:CATALOG_TREE_SELECT] Path: {path}, Cataloged: {is_cataloged}", "INFO")
        self._add_traceback(f"📂 Catalog Selection: {os.path.basename(path)} ({'Cataloged' if is_cataloged else 'Unknown'})", "DEBUG")

        import threading
        threading.Thread(target=self._query_catalog_context, args=(path,), daemon=True).start()

    def _on_catalog_right_click(self, event):
        """Show context menu for catalog items"""
        item = self.catalog_tree.identify_row(event.y)
        if not item: return
        self.catalog_tree.selection_set(item)
        path = self.catalog_tree.item(item, "tags")[0]
        
        menu = tk.Menu(self, tearoff=0, bg='#2a2a2a', fg='#e0e0e0')
        menu.add_command(label="🎯 Set as Target", command=self._set_catalog_as_target)
        menu.add_command(label="📊 Os_Toolkit Profile", command=lambda: subprocess.Popen(f"python3 '{self.babel_root}/Os_Toolkit.py' file '{path}' -z", shell=True))
        menu.add_command(label="🚀 Onboard Tool", command=lambda: self.status_var.set("Onboarding not implemented yet"))
        menu.add_command(label="🔍 Grep in Branch", command=lambda: self._grep_in_catalog_path(path))
        menu.add_separator()
        menu.add_command(label="📋 Copy Path", command=lambda: self.clipboard_clear() or self.clipboard_append(path))
        
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()
            menu.add_command(label="📂 Open Folder", command=lambda: subprocess.Popen(['xdg-open', os.path.dirname(path) if os.path.isfile(path) else path]))
            menu.post(event.x_root, event.y_root)

        # --- Initial Load ---
        add_catalog_node("", "/") # Start from root
        self.catalog_tree.bind("<<TreeviewOpen>>", on_catalog_expand)
        self.catalog_tree.bind("<<TreeviewSelect>>", on_catalog_select)
        self.catalog_tree.bind("<Button-3>", on_catalog_right_click)

    def _query_catalog_context(self, path):
        """Background thread function to query Os_Toolkit for path context"""
        try:
            cmd = ['python3', str(self.babel_root / "Os_Toolkit.py"), 'file', path, '--brief']
            if os.path.isdir(path):
                cmd = ['python3', str(self.babel_root / "Os_Toolkit.py"), 'query', path]
                
            result = subprocess.run(cmd, capture_output=True, text=True)
            output = result.stdout or result.stderr or "No profiling data found for this location."
            self.after(0, lambda: self._update_catalog_details(output))
        except Exception as e:
            self.after(0, lambda: self._update_catalog_details(f"Error querying Os_Toolkit: {str(e)}"))

    def _update_catalog_details(self, text):
        self.catalog_details.insert(tk.END, "\n" + "─" * 40 + "\n")
        self.catalog_details.insert(tk.END, text)
        self.catalog_details.see(tk.END)

    def _set_catalog_as_target(self):
        item = self.catalog_tree.focus()
        if not item: return
        path = self.catalog_tree.item(item, "tags")[0]
        self.target_var.set(path)
        self.engine.set_target(path)
        self.status_var.set(f"🎯 Target set from Catalog: {Path(path).name}")

    def _grep_in_catalog_path(self, path):
        self.target_var.set(path)
        self.engine.set_target(path)
        self.notebook.select(0) # Switch to Grep tab
        self.pattern_entry.focus()

    def _create_profiles_tab(self, notebook):
        """TAB 4: Manage script profiles with an advanced 3-panel UX."""
        profiles_tab = tk.Frame(notebook, bg='#1e1e1e')
        notebook.add(profiles_tab, text="📋 Script Profiles")

        # --- Data store ---
        self.script_profiles = self._load_script_profiles()
        self.all_scripts_data = self._get_all_custom_scripts()

        # --- UI ---
        main_pane = tk.PanedWindow(profiles_tab, orient=tk.HORIZONTAL, bg='#1e1e1e', sashrelief=tk.RAISED, sashwidth=4)
        main_pane.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # --- Left Panel: Profile List ---
        left_frame = tk.Frame(main_pane, bg='#1e1e1e')
        tk.Label(left_frame, text="Profiles", bg='#1e1e1e', fg='#4ec9b0', font=('Arial', 10, 'bold')).pack(anchor=tk.W, pady=2)
        
        profile_list_frame = tk.Frame(left_frame, bg='#2d2d2d')
        profile_list_frame.pack(fill=tk.BOTH, expand=True)
        profile_listbox = tk.Listbox(profile_list_frame, bg='#2d2d2d', fg='#d4d4d4', selectbackground='#4ec9b0', exportselection=False, relief=tk.FLAT, borderwidth=0, highlightthickness=0)
        profile_listbox.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)

        main_pane.add(left_frame, width=200, stretch="never")

        # --- Center Panel: Scripts & Metadata ---
        center_frame = tk.Frame(main_pane, bg='#1e1e1e')
        tk.Label(center_frame, text="Scripts & Context", bg='#1e1e1e', fg='#4ec9b0', font=('Arial', 10, 'bold')).pack(anchor=tk.W, pady=2)
        
        tree_frame = tk.Frame(center_frame, bg='#2d2d2d')
        tree_frame.pack(fill=tk.BOTH, expand=True)
        
        script_tree = ttk.Treeview(tree_frame, columns=("status",), show="tree headings")
        script_tree.heading("#0", text="Script Name")
        script_tree.heading("status", text="Assigned")
        script_tree.column("status", width=80, anchor='center')
        script_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        tsb = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=script_tree.yview)
        script_tree.configure(yscrollcommand=tsb.set)
        tsb.pack(side=tk.RIGHT, fill=tk.Y)

        main_pane.add(center_frame, width=400)

        # --- Right Panel: CLI Builder ---
        right_frame = tk.Frame(main_pane, bg='#1e1e1e')
        cli_builder_label = tk.Label(right_frame, text="CLI Builder", bg='#1e1e1e', fg='#4ec9b0', font=('Arial', 10, 'bold'))
        cli_builder_label.pack(anchor=tk.W, pady=2)
        
        cli_scroll_frame = tk.Frame(right_frame, bg='#2d2d2d')
        cli_scroll_frame.pack(fill=tk.BOTH, expand=True)
        
        cli_canvas = tk.Canvas(cli_scroll_frame, bg='#2d2d2d', highlightthickness=0)
        cli_vsb = tk.Scrollbar(cli_scroll_frame, orient=tk.VERTICAL, command=cli_canvas.yview)
        self.cli_builder_inner = tk.Frame(cli_canvas, bg='#2d2d2d')
        
        self.cli_builder_inner.bind("<Configure>", lambda e: cli_canvas.configure(scrollregion=cli_canvas.bbox("all")))
        cli_canvas.create_window((0, 0), window=self.cli_builder_inner, anchor="nw", width=300)
        cli_canvas.configure(yscrollcommand=cli_vsb.set)
        
        cli_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        cli_vsb.pack(side=tk.RIGHT, fill=tk.Y)

        self.cli_arg_vars = {} 
        
        main_pane.add(right_frame, width=300, stretch="always")

        # --- Functions ---
        def _insert_script_node(parent_node, script, status="[ ]"):
            """Insert a script and its meta children into the treeview."""
            script_node = script_tree.insert(parent_node, "end", text=script['name'],
                                             values=(status,), open=False, tags=('script',))
            script_tree.item(script_node, tags=(script['command'], 'script_item'))
            script_tree.insert(script_node, "end",
                               text=f"Description: {script.get('description', 'N/A')}", tags=('meta',))
            arg_count = len(script.get('cli_args', []))
            script_tree.insert(script_node, "end",
                               text=f"Args: {arg_count} argument{'s' if arg_count != 1 else ''}", tags=('meta',))
            cmd = script.get('command', '')
            script_tree.insert(script_node, "end", text=f"Path: {cmd}", tags=('meta',))
            ext = Path(cmd).suffix.lower() if cmd else ''
            lang_map = {'.py': 'Python', '.sh': 'Bash', '.bash': 'Bash', '.js': 'JavaScript',
                        '.c': 'C', '.cpp': 'C++', '.rb': 'Ruby', '.pl': 'Perl'}
            lang = lang_map.get(ext, 'Unknown')
            script_tree.insert(script_node, "end", text=f"Language: {lang}", tags=('meta',))

        def populate_script_tree(profile_key=None):
            script_tree.delete(*script_tree.get_children())

            # Determine which commands are assigned to the selected profile
            assigned_commands = set()
            if profile_key:
                profile = self.script_profiles.get(profile_key, {})
                for tname, tinfo in profile.get('tools', {}).items():
                    if isinstance(tinfo, dict) and tinfo.get('command'):
                        assigned_commands.add(tinfo['command'])

            # Split scripts into assigned vs unassigned
            assigned_scripts = []
            unassigned_by_cat = {}
            for script in self.all_scripts_data:
                if script['command'] in assigned_commands:
                    assigned_scripts.append(script)
                else:
                    cat = script.get('category', 'Custom')
                    unassigned_by_cat.setdefault(cat, []).append(script)

            # --- Assigned section (top, open by default) ---
            if assigned_scripts:
                profile_display = profile_key or "Profile"
                assigned_node = script_tree.insert("", "end",
                    text=f"Assigned ({len(assigned_scripts)})",
                    values=("",), open=True, tags=('assigned_section',))
                for script in sorted(assigned_scripts, key=lambda s: s['name']):
                    _insert_script_node(assigned_node, script, status="[✓]")

            # --- Consolidated Unassigned section (categorized) ---
            total_unassigned = sum(len(v) for v in unassigned_by_cat.values())
            unassigned_root = script_tree.insert("", "end",
                text=f"Consolidated Unassigned ({total_unassigned})",
                values=("",), open=not assigned_scripts, tags=('unassigned_section',))
            for cat_name in sorted(unassigned_by_cat.keys()):
                scripts = unassigned_by_cat[cat_name]
                cat_node = script_tree.insert(unassigned_root, "end",
                    text=f"{cat_name} ({len(scripts)})",
                    values=("",), open=False, tags=('category',))
                for script in scripts:
                    _insert_script_node(cat_node, script)

            script_tree.tag_configure('meta', foreground='#888888')
            script_tree.tag_configure('category', foreground='#4ec9b0')
            script_tree.tag_configure('assigned_section', foreground='#6a9955')
            script_tree.tag_configure('unassigned_section', foreground='#ce9178')
            script_tree.tag_configure('selected', background='#004050')

        def refresh_profile_list():
            profile_listbox.delete(0, tk.END)
            for name in sorted(self.script_profiles.keys()):
                profile = self.script_profiles[name]
                display = profile.get('display_name', name)
                icon = profile.get('icon', '')
                label = f"{icon} {display}" if icon else display
                profile_listbox.insert(tk.END, label)
            # Store the key mapping (listbox index -> profile key)
            self._profile_key_map = sorted(self.script_profiles.keys())

        def get_selected_profile_key():
            """Get the actual profile dict key from listbox selection."""
            selections = profile_listbox.curselection()
            if not selections:
                return None
            idx = selections[0]
            if hasattr(self, '_profile_key_map') and idx < len(self._profile_key_map):
                return self._profile_key_map[idx]
            return None

        def _get_all_script_items():
            """Get all script items across section/category groups."""
            items = []
            for top_node in script_tree.get_children():
                top_tags = script_tree.item(top_node, "tags")
                if top_tags and 'script_item' in top_tags:
                    items.append(top_node)
                    continue
                for mid_node in script_tree.get_children(top_node):
                    mid_tags = script_tree.item(mid_node, "tags")
                    if mid_tags and 'script_item' in mid_tags:
                        items.append(mid_node)
                        continue
                    for leaf in script_tree.get_children(mid_node):
                        leaf_tags = script_tree.item(leaf, "tags")
                        if leaf_tags and 'script_item' in leaf_tags:
                            items.append(leaf)
            return items

        def update_script_selections_for_profile(profile_name):
            for item in _get_all_script_items():
                script_tree.item(item, values=("[ ]",))

            if not profile_name:
                return
            profile = self.script_profiles.get(profile_name, {})
            profile_tools = profile.get('tools', {})

            for tool_name, tool_info in profile_tools.items():
                tool_cmd = tool_info.get('command', '') if isinstance(tool_info, dict) else ''
                matched = False
                # Match by command (tag)
                for item in _get_all_script_items():
                    item_tags = script_tree.item(item, "tags")
                    if item_tags and item_tags[0] == tool_cmd:
                        script_tree.item(item, values=("[✓]",))
                        matched = True
                        break
                # Fallback: match by display name
                if not matched:
                    for item in _get_all_script_items():
                        if script_tree.item(item, "text") == tool_name:
                            script_tree.item(item, values=("[✓]",))
                            break

        def on_profile_select(event):
            profile_key = get_selected_profile_key()
            if not profile_key:
                return
            
            # Log event with tagging
            self.engine.log_debug(f"#[Event:PROFILE_SELECTED] Key: {profile_key}", "INFO")
            self._add_traceback(f"#[Event:PROFILE_SELECTED] Loading Profile Config: {profile_key}", "PROFILE")

            profile = self.script_profiles.get(profile_key, {})
            # Refresh tree to show assigned vs unassigned split
            populate_script_tree(profile_key)
            for widget in self.cli_builder_inner.winfo_children(): widget.destroy()

            # Load existing slot assignments from profile tools
            self._profile_slot_assignments = {}
            tools = profile.get('tools', {})
            slot_idx = 0
            for tname, tinfo in tools.items():
                if not isinstance(tinfo, dict):
                    continue
                assigned_slot = tinfo.get('slot', slot_idx)
                self._profile_slot_assignments[assigned_slot] = {
                    'name': tname, 'command': tinfo.get('command', ''),
                    'args': tinfo.get('args', []),
                    'category': tinfo.get('category', 'Custom'),
                }
                slot_idx += 1
            _refresh_slot_preview()

            # Show profile info in CLI builder
            display_name = profile.get('display_name', profile_key)
            icon = profile.get('icon', '')
            tool_count = len(tools)
            system_tag = " [system]" if profile.get('system', False) else " [user]"
            cli_builder_label.config(text=f"{icon} {display_name}{system_tag} ({tool_count} tools)")

            # Profile metadata
            tk.Label(self.cli_builder_inner, text=f"Profile: {display_name}",
                     bg='#2d2d2d', fg='#4ec9b0', font=('Arial', 9, 'bold'),
                     anchor='w').pack(fill=tk.X, padx=5, pady=(5, 0))
            tk.Label(self.cli_builder_inner, text=f"Type: {'System' if profile.get('system') else 'User-defined'}  |  Tools: {tool_count}",
                     bg='#2d2d2d', fg='#888888', font=('Monospace', 8),
                     anchor='w').pack(fill=tk.X, padx=5)

            # List each tool in the profile with slot numbers
            if tools:
                sep = tk.Frame(self.cli_builder_inner, bg='#4ec9b0', height=1)
                sep.pack(fill=tk.X, padx=5, pady=6)
                tk.Label(self.cli_builder_inner, text="Assigned Tools:",
                         bg='#2d2d2d', fg='#d4d4d4', font=('Arial', 8, 'bold'),
                         anchor='w').pack(fill=tk.X, padx=5)

                for sidx in range(8):
                    assignment = self._profile_slot_assignments.get(sidx)
                    tool_frame = tk.Frame(self.cli_builder_inner, bg='#252525')
                    tool_frame.pack(fill=tk.X, padx=5, pady=1)
                    if assignment:
                        tname = assignment.get('name', '?')
                        args = assignment.get('args', [])
                        args_str = f" {' '.join(args)}" if args else ""
                        cmd = assignment.get('command', '')
                        short = f".../{Path(cmd).name}" if cmd else ""
                        tk.Label(tool_frame, text=f" {sidx+1}. {tname}{args_str}",
                                 bg='#252525', fg='#ce9178', font=('Monospace', 8),
                                 anchor='w').pack(side=tk.LEFT, fill=tk.X, expand=True)
                        tk.Label(tool_frame, text=short, bg='#252525', fg='#666666',
                                 font=('Monospace', 7)).pack(side=tk.RIGHT, padx=3)
                    else:
                        tk.Label(tool_frame, text=f" {sidx+1}. [empty]",
                                 bg='#252525', fg='#555555', font=('Monospace', 8),
                                 anchor='w').pack(side=tk.LEFT)
            else:
                tk.Label(self.cli_builder_inner, text="No tools assigned yet.\nClick a script in the center panel\nto configure arguments and assign to slots.",
                         bg='#2d2d2d', fg='#666666', font=('Arial', 8),
                         anchor='w', justify=tk.LEFT).pack(fill=tk.X, padx=5, pady=10)

            # Instruction
            sep2 = tk.Frame(self.cli_builder_inner, bg='#333', height=1)
            sep2.pack(fill=tk.X, padx=5, pady=8)
            tk.Label(self.cli_builder_inner,
                     text="Click a script in the center panel to\nselect arguments and assign to a slot.",
                     bg='#2d2d2d', fg='#569cd6', font=('Arial', 8),
                     anchor='w', justify=tk.LEFT).pack(fill=tk.X, padx=5)

        def toggle_script_selection(command_tag):
            nodes = script_tree.tag_has(command_tag)
            if not nodes: return
            item = nodes[0]
            current_val = script_tree.item(item, "values")[0]
            new_val = "[✓]" if current_val.strip() == "[ ]" else "[ ]"
            script_tree.item(item, values=(new_val,))

        def on_script_click(event):
            item = script_tree.identify_row(event.y)
            if not item: return
            
            # Log click event for debugging
            tags = script_tree.item(item, "tags")
            text = script_tree.item(item, "text")
            self.engine.log_debug(f"#[Event:SCRIPT_TREE_CLICK] Item: {text}, Tags: {tags}", "DEBUG")

            command = _resolve_script_command(item)
            if command:
                # Find the actual script node (not meta child)
                cmd_nodes = script_tree.tag_has(command)
                if cmd_nodes:
                    script_node = cmd_nodes[0]
                    # Focus and select the script node so CLI Builder populates
                    script_tree.focus(script_node)
                    script_tree.selection_set(script_node)
                    # Explicitly trigger CLI Builder (<<TreeviewSelect>> may not fire)
                    on_script_select(event)
            else:
                # If not a script command, it might be a category or section header
                # Provide some feedback in the right panel
                for widget in self.cli_builder_inner.winfo_children(): widget.destroy()
                tk.Label(self.cli_builder_inner, text=f"Category: {text}",
                         bg='#2d2d2d', fg='#4ec9b0', font=('Arial', 9, 'bold'),
                         anchor='w').pack(fill=tk.X, padx=5, pady=10)
                
                if 'category' in tags:
                    scripts_in_cat = len(script_tree.get_children(item))
                    tk.Label(self.cli_builder_inner, text=f"Contains {scripts_in_cat} scripts.",
                             bg='#2d2d2d', fg='#888888', font=('Arial', 8),
                             anchor='w').pack(fill=tk.X, padx=5)
                
                self._add_traceback(f"#[Event:SCRIPT_TREE_SELECT] View Category: {text}", "DEBUG")
            
        self._staged_profile_args = {}  # {command: [selected_args]} - persists across script switches
        # Slot assignments: {slot_index: {name, command, args[]}}
        if not hasattr(self, '_profile_slot_assignments'):
            self._profile_slot_assignments = {}

        def _flush_cli_builder_state():
            """Save current CLI builder checkbox states before switching scripts."""
            for cmd, arg_vars in self.cli_arg_vars.items():
                self._staged_profile_args[cmd] = [arg for arg, var in arg_vars.items() if var.get()]

        def _refresh_slot_preview():
            """Update the slot preview panel below the CLI Builder."""
            if not hasattr(self, '_slot_preview_frame') or not self._slot_preview_frame.winfo_exists():
                return
            for w in self._slot_preview_frame.winfo_children():
                w.destroy()
            tk.Label(self._slot_preview_frame, text="Slot Assignments:",
                     bg='#1a1a1a', fg='#4ec9b0', font=('Arial', 8, 'bold'),
                     anchor='w').pack(fill=tk.X, padx=3, pady=(2, 0))
            for slot_idx in range(8):
                assignment = self._profile_slot_assignments.get(slot_idx)
                if assignment:
                    name = assignment.get('name', '?')
                    args = assignment.get('args', [])
                    args_short = f" {' '.join(args)}" if args else ""
                    color = '#d4d4d4'
                    slot_text = f" {slot_idx+1}. {name}{args_short}"
                else:
                    color = '#555555'
                    slot_text = f" {slot_idx+1}. [empty]"
                row = tk.Frame(self._slot_preview_frame, bg='#1a1a1a')
                row.pack(fill=tk.X, padx=3)
                tk.Label(row, text=slot_text, bg='#1a1a1a', fg=color,
                         font=('Monospace', 7), anchor='w').pack(side=tk.LEFT, fill=tk.X, expand=True)
                if assignment:
                    tk.Button(row, text="x", command=lambda si=slot_idx: _clear_slot(si),
                              bg='#1a1a1a', fg='#a54242', font=('Monospace', 7),
                              bd=0, relief=tk.FLAT, width=2).pack(side=tk.RIGHT)

        def _clear_slot(slot_idx):
            if slot_idx in self._profile_slot_assignments:
                del self._profile_slot_assignments[slot_idx]
            _refresh_slot_preview()

        # Create slot preview frame below right panel
        self._slot_preview_frame = tk.Frame(right_frame, bg='#1a1a1a', relief=tk.SUNKEN, bd=1)
        self._slot_preview_frame.pack(fill=tk.X, padx=0, pady=(5, 0))
        _refresh_slot_preview()

        def _resolve_script_command(item):
            """Walk up from any treeview node to find the script command tag."""
            if not item:
                return None
            # Walk up the hierarchy looking for a script_item node
            current = item
            for _ in range(4):  # max depth: section > category > script > meta
                if not current:
                    return None
                tags = script_tree.item(current, "tags")
                if tags and 'script_item' in tags:
                    return tags[0]
                # Skip non-script nodes (category, section headers)
                if 'category' in tags or 'assigned_section' in tags or 'unassigned_section' in tags:
                    return None
                current = script_tree.parent(current)
            return None

        def on_script_select(event):
            item = script_tree.focus()
            if not item: return
            
            # Get text and tags for current item
            text = script_tree.item(item, "text")
            tags = script_tree.item(item, "tags")
            
            command = _resolve_script_command(item)
            
            if not command:
                # Handle non-script nodes (Category, Section, Meta)
                for widget in self.cli_builder_inner.winfo_children(): widget.destroy()
                
                header_text = text
                if 'assigned_section' in tags or 'unassigned_section' in tags:
                    header_text = f"Section: {text}"
                elif 'category' in tags:
                    header_text = f"Category: {text}"
                
                tk.Label(self.cli_builder_inner, text=header_text,
                         bg='#2d2d2d', fg='#4ec9b0', font=('Arial', 10, 'bold'),
                         anchor='w').pack(fill=tk.X, padx=5, pady=10)
                
                # Show child count if it's a grouping node
                children = script_tree.get_children(item)
                if children:
                    tk.Label(self.cli_builder_inner, text=f"Contains {len(children)} items.",
                             bg='#2d2d2d', fg='#888888', font=('Arial', 9),
                             anchor='w').pack(fill=tk.X, padx=5)
                
                self.engine.log_debug(f"#[Event:SCRIPT_TREE_SELECT] View Group: {text}", "DEBUG")
                return

            # Flush current CLI builder state before switching
            _flush_cli_builder_state()

            # Highlight selected
            for i in script_tree.tag_has('selected'):
                t = list(script_tree.item(i)['tags'])
                if 'selected' in t: t.remove('selected')
                script_tree.item(i, tags=t)

            nodes = script_tree.tag_has(command)
            if nodes:
                t = list(script_tree.item(nodes[0])['tags'])
                if 'selected' not in t: t.append('selected')
                script_tree.item(nodes[0], tags=t)

            for widget in self.cli_builder_inner.winfo_children(): widget.destroy()
            script_data = next((s for s in self.all_scripts_data if s['command'] == command), None)
            if not script_data: return

            cli_builder_label.config(text=f"CLI Builder: {script_data['name']}")

            # --- Script metadata header ---
            cmd_path = script_data.get('command', '')
            ext = Path(cmd_path).suffix.lower() if cmd_path else ''
            lang_map = {'.py': 'Python', '.sh': 'Bash', '.bash': 'Bash', '.js': 'JavaScript',
                        '.c': 'C', '.cpp': 'C++', '.rb': 'Ruby', '.pl': 'Perl'}
            lang = lang_map.get(ext, 'Unknown')

            info_frame = tk.Frame(self.cli_builder_inner, bg='#252525')
            info_frame.pack(fill=tk.X, padx=3, pady=(2, 0))
            tk.Label(info_frame, text=f"{lang}  |  {script_data.get('category', 'N/A')}",
                     bg='#252525', fg='#4ec9b0', font=('Monospace', 8), anchor='w').pack(fill=tk.X, padx=3)
            desc = script_data.get('description', 'N/A')
            if desc and desc != 'N/A':
                tk.Label(info_frame, text=desc[:120], bg='#252525', fg='#888888',
                         font=('Arial', 7), anchor='w', wraplength=280).pack(fill=tk.X, padx=3)
            tk.Label(info_frame, text=cmd_path, bg='#252525', fg='#555555',
                     font=('Monospace', 6), anchor='w', wraplength=280).pack(fill=tk.X, padx=3)

            # --- Arguments section ---
            sep1 = tk.Frame(self.cli_builder_inner, bg='#4ec9b0', height=1)
            sep1.pack(fill=tk.X, padx=5, pady=4)

            cli_args = script_data.get('cli_args', [])
            arg_count = len(cli_args)
            tk.Label(self.cli_builder_inner,
                     text=f"Arguments ({arg_count} catalogued):",
                     bg='#2d2d2d', fg='#d4d4d4', font=('Arial', 8, 'bold'),
                     anchor='w').pack(fill=tk.X, padx=5)

            # Get saved args from profile or staged state
            profile_key = get_selected_profile_key()
            saved_args = self._staged_profile_args.get(command, [])
            if not saved_args and profile_key:
                profile = self.script_profiles.get(profile_key, {})
                tool_info = profile.get('tools', {})
                for tname, tdata in tool_info.items():
                    if isinstance(tdata, dict) and tdata.get('command') == command:
                        saved_args = tdata.get('args', [])
                        break

            self.cli_arg_vars[command] = {}
            for arg_info in cli_args:
                arg = arg_info.get('arg', 'N/A')
                help_text = arg_info.get('desc', '')
                self.cli_arg_vars[command][arg] = tk.BooleanVar(value=(arg in saved_args))

                arg_row = tk.Frame(self.cli_builder_inner, bg='#2d2d2d')
                arg_row.pack(fill=tk.X, padx=5, pady=0)
                cb = tk.Checkbutton(arg_row, text=arg, variable=self.cli_arg_vars[command][arg],
                                    bg='#2d2d2d', fg='#d4d4d4', selectcolor='#1e1e1e',
                                    anchor='w', font=('Monospace', 8))
                cb.pack(side=tk.LEFT)
                if help_text and help_text != 'N/A':
                    tk.Label(arg_row, text=help_text[:50], bg='#2d2d2d', fg='#888888',
                             font=('Arial', 7), anchor='w').pack(side=tk.LEFT, padx=(4, 0))

            if not cli_args:
                tk.Label(self.cli_builder_inner, text="No catalogued arguments.\nIntrospection may discover args below.",
                         bg='#2d2d2d', fg='#666666', font=('Arial', 8),
                         anchor='w', justify=tk.LEFT).pack(fill=tk.X, padx=5, pady=3)

            # --- Slot assignment controls ---
            sep2 = tk.Frame(self.cli_builder_inner, bg='#569cd6', height=1)
            sep2.pack(fill=tk.X, padx=5, pady=6)

            assign_frame = tk.Frame(self.cli_builder_inner, bg='#252525')
            assign_frame.pack(fill=tk.X, padx=5, pady=2)

            tk.Label(assign_frame, text="Assign to Slot:", bg='#252525', fg='#d4d4d4',
                     font=('Arial', 8)).pack(side=tk.LEFT, padx=(3, 5))

            slot_var = tk.StringVar(value="1")
            # Find first empty slot as default
            for si in range(8):
                if si not in self._profile_slot_assignments:
                    slot_var.set(str(si + 1))
                    break
            slot_combo = ttk.Combobox(assign_frame, textvariable=slot_var,
                                      values=[str(i+1) for i in range(8)],
                                      width=3, state='readonly')
            slot_combo.pack(side=tk.LEFT, padx=2)

            def assign_to_slot():
                _flush_cli_builder_state()
                slot_idx = int(slot_var.get()) - 1
                selected_args = [arg for arg, var in self.cli_arg_vars.get(command, {}).items() if var.get()]
                self._profile_slot_assignments[slot_idx] = {
                    'name': script_data['name'],
                    'command': command,
                    'args': selected_args,
                    'category': script_data.get('category', 'Custom'),
                    'description': script_data.get('description', ''),
                }
                # Also mark script as checked in treeview
                cmd_nodes = script_tree.tag_has(command)
                if cmd_nodes:
                    script_tree.item(cmd_nodes[0], values=("[✓]",))
                _refresh_slot_preview()
                self.status_var.set(f"Slot {slot_idx+1}: {script_data['name']} ({len(selected_args)} args)")

            tk.Button(assign_frame, text="Assign", command=assign_to_slot,
                      bg='#0e639c', fg='white', font=('Arial', 8, 'bold'),
                      relief=tk.RAISED, bd=1, width=8).pack(side=tk.LEFT, padx=5)

            # Select all / none shortcuts
            def select_all_args():
                for var in self.cli_arg_vars.get(command, {}).values():
                    var.set(True)
            def select_none_args():
                for var in self.cli_arg_vars.get(command, {}).values():
                    var.set(False)

            tk.Button(assign_frame, text="All", command=select_all_args,
                      bg='#3d3d3d', fg='#d4d4d4', font=('Arial', 7),
                      relief=tk.RAISED, bd=1, width=4).pack(side=tk.RIGHT, padx=1)
            tk.Button(assign_frame, text="None", command=select_none_args,
                      bg='#3d3d3d', fg='#d4d4d4', font=('Arial', 7),
                      relief=tk.RAISED, bd=1, width=4).pack(side=tk.RIGHT, padx=1)

            # --- Command preview ---
            preview_frame = tk.Frame(self.cli_builder_inner, bg='#1a1a1a')
            preview_frame.pack(fill=tk.X, padx=5, pady=4)
            preview_var = tk.StringVar(value=cmd_path)
            def update_preview(*_):
                sel = [a for a, v in self.cli_arg_vars.get(command, {}).items() if v.get()]
                full = f"{cmd_path} {' '.join(sel)}".strip()
                preview_var.set(full)
            # Bind checkbox changes to update preview
            for var in self.cli_arg_vars.get(command, {}).values():
                var.trace_add('write', update_preview)
            update_preview()

            tk.Label(preview_frame, text="CMD:", bg='#1a1a1a', fg='#569cd6',
                     font=('Monospace', 7)).pack(anchor=tk.W, padx=3)
            cmd_preview = tk.Entry(preview_frame, textvariable=preview_var,
                                   bg='#1a1a1a', fg='#4ec9b0', font=('Monospace', 7),
                                   relief=tk.FLAT, readonlybackground='#1a1a1a', state='readonly')
            cmd_preview.pack(fill=tk.X, padx=3, pady=(0, 2))

            # --- Background introspection for Python scripts ---
            if lang == 'Python':
                status_label = tk.Label(self.cli_builder_inner, text="Introspecting...",
                                        bg='#2d2d2d', fg='#569cd6', font=('Monospace', 8), anchor='w')
                status_label.pack(fill=tk.X, padx=5, pady=2)

                introspect_target = cmd_path
                known_args = {a.get('arg', '') for a in cli_args}

                def run_introspection():
                    intro_data = self._introspect_script(introspect_target)
                    def update_ui():
                        if not status_label.winfo_exists():
                            return
                        status_label.config(text=f"Interpreter: {intro_data.get('interpreter', 'N/A')}")

                        # Discovered args — add as checkboxes too
                        discovered = [a for a in intro_data.get('parsed_args', [])
                                      if a['name'] not in known_args]
                        if discovered:
                            tk.Label(self.cli_builder_inner,
                                     text=f"Discovered {len(discovered)} extra arg(s):",
                                     bg='#2d2d2d', fg='#dcdcaa', font=('Monospace', 8),
                                     anchor='w').pack(fill=tk.X, padx=5, pady=(4, 0))
                            for arg in discovered:
                                arg_name = arg['name']
                                help_txt = arg.get('help', '')
                                if arg_name not in self.cli_arg_vars.get(command, {}):
                                    self.cli_arg_vars.setdefault(command, {})[arg_name] = tk.BooleanVar(value=False)
                                    drow = tk.Frame(self.cli_builder_inner, bg='#2d2d2d')
                                    drow.pack(fill=tk.X, padx=5)
                                    dcb = tk.Checkbutton(drow, text=arg_name,
                                                         variable=self.cli_arg_vars[command][arg_name],
                                                         bg='#2d2d2d', fg='#ce9178', selectcolor='#1e1e1e',
                                                         anchor='w', font=('Monospace', 8))
                                    dcb.pack(side=tk.LEFT)
                                    if help_txt:
                                        tk.Label(drow, text=help_txt[:40], bg='#2d2d2d', fg='#888888',
                                                 font=('Arial', 7)).pack(side=tk.LEFT, padx=(4, 0))
                                    # Re-bind preview
                                    self.cli_arg_vars[command][arg_name].trace_add('write', update_preview)

                        # Help text
                        help_text = intro_data.get('help_text', '')
                        if help_text:
                            tk.Label(self.cli_builder_inner, text="Help output (-h):",
                                     bg='#2d2d2d', fg='#888888', font=('Monospace', 8),
                                     anchor='w').pack(fill=tk.X, padx=5, pady=(6, 0))
                            help_box = tk.Text(self.cli_builder_inner, bg='#1e1e1e', fg='#d4d4d4',
                                               font=('Monospace', 7), height=6, wrap=tk.WORD,
                                               relief=tk.FLAT, borderwidth=0)
                            help_box.pack(fill=tk.X, padx=5, pady=2)
                            help_box.insert('1.0', help_text)
                            help_box.config(state=tk.DISABLED)

                    try:
                        self.cli_builder_inner.after(0, update_ui)
                    except Exception:
                        pass

                threading.Thread(target=run_introspection, daemon=True).start()

        script_tree.bind("<<TreeviewSelect>>", on_script_select)
        script_tree.bind("<Button-1>", on_script_click)

        def add_profile():
            new_name = simpledialog.askstring("New Profile", "Enter a name for the new profile:", parent=profiles_tab)
            if not new_name:
                return
            if new_name in self.script_profiles:
                messagebox.showwarning("Exists", f"Profile '{new_name}' already exists.", parent=profiles_tab)
                return
            self.script_profiles[new_name] = {
                'display_name': new_name, 'icon': '', 'system': False, 'tools': {}
            }
            # Clear slot assignments for fresh start
            self._profile_slot_assignments = {}
            self._staged_profile_args = {}
            # Clear all treeview checkmarks
            for item in _get_all_script_items():
                script_tree.item(item, values=("[ ]",))
            refresh_profile_list()
            _refresh_slot_preview()
            # Select the new profile
            if hasattr(self, '_profile_key_map') and new_name in self._profile_key_map:
                idx = self._profile_key_map.index(new_name)
                profile_listbox.selection_set(idx)
                on_profile_select(None)
            self.status_var.set(f"New profile '{new_name}' created. Select scripts and assign to slots.")

        def delete_profile():
            profile_key = get_selected_profile_key()
            if not profile_key: return
            profile = self.script_profiles.get(profile_key, {})
            if profile.get('system', False):
                messagebox.showwarning("System Profile",
                    f"'{profile.get('display_name', profile_key)}' is a system profile and cannot be deleted.",
                    parent=profiles_tab)
                return
            if messagebox.askyesno("Delete Profile", f"Delete '{profile_key}'?", parent=profiles_tab):
                del self.script_profiles[profile_key]
                self._save_script_profiles(self.script_profiles)
                refresh_profile_list()
                update_script_selections_for_profile(None)
                for widget in self.cli_builder_inner.winfo_children(): widget.destroy()

        def save_profile():
            profile_key = get_selected_profile_key()
            if not profile_key:
                messagebox.showwarning("Save Error", "No profile selected.", parent=profiles_tab)
                return

            profile = self.script_profiles.get(profile_key, {})
            if profile.get('system', False):
                messagebox.showwarning("System Profile",
                    f"'{profile.get('display_name', profile_key)}' is a system profile. Create a copy to customize.",
                    parent=profiles_tab)
                return

            # Flush current CLI builder state
            _flush_cli_builder_state()

            new_tools = {}

            # Prefer slot assignments if any exist (these are slot-aware)
            if self._profile_slot_assignments:
                for slot_idx in sorted(self._profile_slot_assignments.keys()):
                    assignment = self._profile_slot_assignments[slot_idx]
                    display_name = assignment.get('name', f'Tool {slot_idx+1}')
                    new_tools[display_name] = {
                        'command': assignment.get('command', ''),
                        'args': assignment.get('args', []),
                        'source': 'user',
                        'slot': slot_idx,
                        'category': assignment.get('category', 'Custom'),
                    }
            else:
                # Fallback: use treeview checkmarks + staged args
                for item in _get_all_script_items():
                    if script_tree.item(item, "values")[0].strip() == "[✓]":
                        tags = script_tree.item(item, "tags")
                        command = tags[0] if tags else ''
                        display_name = script_tree.item(item, "text")
                        selected_args = self._staged_profile_args.get(command, [])
                        new_tools[display_name] = {
                            'command': command, 'args': selected_args, 'source': 'user'
                        }

            self.script_profiles[profile_key]['tools'] = new_tools
            self._save_script_profiles(self.script_profiles)
            tool_count = len(new_tools)
            messagebox.showinfo("Saved", f"Profile '{profile_key}' saved with {tool_count} tool(s).", parent=profiles_tab)

        # --- Buttons ---
        btn_frame = tk.Frame(left_frame, bg='#1e1e1e')
        btn_frame.pack(fill=tk.X, pady=5)
        tk.Button(btn_frame, text="New", command=add_profile,
                  bg='#4ec9b0', fg='#000000', font=('Arial', 8, 'bold')).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=1)
        tk.Button(btn_frame, text="Delete", command=delete_profile,
                  bg='#3d3d3d', fg='#d4d4d4', font=('Arial', 8)).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=1)
        tk.Button(btn_frame, text="Save", command=save_profile,
                  bg='#0e639c', fg='white', font=('Arial', 8, 'bold')).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=1)

        def refresh_live():
            """Save and refresh the Grep tab buttons immediately."""
            profile_key = get_selected_profile_key()
            if not profile_key:
                messagebox.showwarning("No Selection", "Select a profile first.", parent=profiles_tab)
                return
            save_profile()
            # Re-apply from disk so cycling picks it up immediately
            self._apply_profile_config(profile_key)

        btn_frame2 = tk.Frame(left_frame, bg='#1e1e1e')
        btn_frame2.pack(fill=tk.X, pady=(0, 5))
        tk.Button(btn_frame2, text="Save + Refresh Live",
                  command=refresh_live,
                  bg='#2d7d46', fg='white', font=('Arial', 8, 'bold')).pack(fill=tk.X)

        populate_script_tree()
        refresh_profile_list()
        profile_listbox.bind('<<ListboxSelect>>', on_profile_select)

    def _get_all_custom_scripts(self) -> List[Dict[str, Any]]:
        """Consolidates scripts and their metadata from all available sources."""
        all_scripts = []
        seen_commands = set()

        def add_script(script_data):
            command = script_data.get('command') or script_data.get('path')
            if not command: return
            
            # Expand {babel_root}
            command = command.replace("{babel_root}", str(self.babel_root))
            
            if command and command not in seen_commands:
                cli_args = []
                args_data = script_data.get('arguments') or script_data.get('cli_args') or []
                for arg in args_data:
                    name = arg.get('name') or arg.get('arg')
                    help_text = arg.get('help') or arg.get('desc') or 'N/A'
                    if name: cli_args.append({'arg': name, 'desc': help_text})

                all_scripts.append({
                    'name': script_data.get('display_name') or script_data.get('name') or Path(command).name,
                    'command': command,
                    'description': script_data.get('description') or script_data.get('help') or 'N/A',
                    'category': script_data.get('category', 'Custom'),
                    'cli_args': cli_args
                })
                seen_commands.add(command)

        try:
            menu_path = self.version_root / "inventory" / "consolidated_menu.json"
            if menu_path.exists():
                with open(menu_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                for tool in data.get('tools', []): add_script(tool)
        except Exception as e:
            self.engine.log_debug(f"Error loading consolidated_menu: {e}", "ERROR")
            
        for script in self._load_custom_scripts(): add_script(script)

        # Action Panel tools (scope, scope_flow, engineers_toolkit)
        action_panel_dir = Path(__file__).resolve().parent.parent  # action_panel/
        ap_tools = [
            {'path': action_panel_dir / 'scope' / 'scope.py',
             'display_name': 'Scope Analyzer', 'description': 'Tkinter Object Inspector with hover analysis',
             'category': 'Debug Suite', 'cli_args': [{'arg': '--scope', 'desc': 'Run scope inspection'}]},
            {'path': action_panel_dir / 'scope' / 'variants' / 'scope_flow.py',
             'display_name': 'Scope Flow', 'description': 'Progressive analysis workflow tool',
             'category': 'Debug Suite', 'cli_args': []},
            {'path': action_panel_dir / 'engineers_toolkit.py',
             'display_name': 'Engineers Toolkit', 'description': 'GUI dev workflow with quality checks',
             'category': 'Toolkit', 'cli_args': []},
        ]
        for tool_def in ap_tools:
            if tool_def['path'].exists():
                add_script({
                    'display_name': tool_def['display_name'], 'command': str(tool_def['path']),
                    'description': tool_def['description'], 'category': tool_def['category'],
                    'cli_args': tool_def['cli_args'],
                })

        # Babel profile tools - ensure every profile-referenced tool is in the treeview
        try:
            sys_path = self.version_root / "inventory" / "babel_profiles.json"
            if sys_path.exists():
                with open(sys_path, 'r', encoding='utf-8') as f:
                    profiles_data = json.load(f).get('profiles', {})
                for p_data in profiles_data.values():
                    for tool_name, cmd in p_data.get('tool_locations', {}).items():
                        expanded = cmd.replace("{babel_root}", str(self.babel_root))
                        add_script({
                            'display_name': tool_name, 'command': expanded,
                            'description': f'Babel profile tool', 'category': 'Babel Core',
                        })
        except Exception:
            pass

        # Inject Triad subcommands (Os_Toolkit, onboarder, Filesync)
        for sub in self._get_triad_subcommands():
            add_script(sub)

        # Dedup versioned tools (strip HHMM prefixes like "2306 " or "1900_")
        seen_base_names = {}
        deduped = []
        for script in all_scripts:
            base_name = re.sub(r'^\d{4}\s+', '', script['name'])
            base_name = re.sub(r'^\d{4}_', '', base_name)
            if base_name not in seen_base_names:
                script['name'] = base_name
                seen_base_names[base_name] = script
                deduped.append(script)
        all_scripts = deduped

        return sorted(all_scripts, key=lambda x: x['name'])

    def _get_triad_subcommands(self) -> list:
        """Return Triad subcommands with their real CLI args from -h output."""
        babel_root = str(self.babel_root)
        os_toolkit = f"python3 {babel_root}/Os_Toolkit.py"
        onboarder = f"python3 {babel_root}/onboarder.py"
        filesync = f"python3 {babel_root}/Filesync.py"

        # Common Os_Toolkit args shared by all subcommands
        ost_common = [
            {'arg': '--session', 'desc': 'Session ID to load'},
            {'arg': '--base-dir', 'desc': 'Base directory for data'},
            {'arg': '--verbose', 'desc': 'Verbose output'},
            {'arg': '--zenity', 'desc': 'Display output via Zenity GUI'},
        ]

        triad = [
            # === Os_Toolkit subcommands (14) ===
            {'display_name': 'Os_Toolkit analyze', 'command': f'{os_toolkit} analyze',
             'description': 'Analyze system state with configurable depth',
             'category': 'Os_Toolkit', 'arguments': ost_common + [
                 {'name': '--depth', 'help': 'Depth of analysis (1=basic, 2=detailed, 3=deep)'},
                 {'name': '--save', 'help': 'Save after analysis'},
             ]},
            {'display_name': 'Os_Toolkit query', 'command': f'{os_toolkit} query',
             'description': 'Query session data by filename, path, keyword',
             'category': 'Os_Toolkit', 'arguments': ost_common + [
                 {'name': 'query_string', 'help': 'Search term (filename, path, keyword)'},
                 {'name': '--type', 'help': 'Query type: auto, file, string, hash, taxonomic, verb, imports, natural'},
                 {'name': '--max-results', 'help': 'Maximum results to return'},
                 {'name': '--output', 'help': 'Save results to JSON file'},
                 {'name': '--suggest', 'help': 'Show suggested follow-up actions'},
             ]},
            {'display_name': 'Os_Toolkit file', 'command': f'{os_toolkit} file',
             'description': 'Analyze specific file with forensic profiling',
             'category': 'Os_Toolkit', 'arguments': ost_common + [
                 {'name': 'filepath', 'help': 'Path to file to analyze'},
                 {'name': '--depth', 'help': 'Analysis depth (1-3)'},
                 {'name': '--suggest', 'help': 'Show suggested actions for this file'},
                 {'name': '--save', 'help': 'Save analysis results'},
             ]},
            {'display_name': 'Os_Toolkit manifest', 'command': f'{os_toolkit} manifest',
             'description': 'Generate system manifest',
             'category': 'Os_Toolkit', 'arguments': ost_common + [
                 {'name': '--format', 'help': 'Output format: json or text'},
             ]},
            {'display_name': 'Os_Toolkit journal', 'command': f'{os_toolkit} journal',
             'description': 'Journal management - add, query, or view stats',
             'category': 'Os_Toolkit', 'arguments': ost_common + [
                 {'name': '--add', 'help': 'Add journal entry'},
                 {'name': '--query', 'help': 'Search journal entries'},
                 {'name': '--stats', 'help': 'Show journal statistics'},
             ]},
            {'display_name': 'Os_Toolkit export', 'command': f'{os_toolkit} export',
             'description': 'Export session data',
             'category': 'Os_Toolkit', 'arguments': ost_common + [
                 {'name': '--format', 'help': 'Export format: json or text'},
             ]},
            {'display_name': 'Os_Toolkit latest', 'command': f'{os_toolkit} latest',
             'description': 'Show latest system state and session summary',
             'category': 'Os_Toolkit', 'arguments': ost_common},
            {'display_name': 'Os_Toolkit actions', 'command': f'{os_toolkit} actions',
             'description': 'Manage and run actions (sync, security, memory)',
             'category': 'Os_Toolkit', 'arguments': ost_common + [
                 {'name': '--list', 'help': 'List available actions'},
                 {'name': '--run', 'help': 'Run action by ID (sync_all_todos, check_security, update_memory)'},
             ]},
            {'display_name': 'Os_Toolkit todo', 'command': f'{os_toolkit} todo',
             'description': 'Task management - view, add, update todos',
             'category': 'Os_Toolkit', 'arguments': ost_common + [
                 {'name': 'subcommand', 'help': 'view, add, or update'},
             ]},
            {'display_name': 'Os_Toolkit plan', 'command': f'{os_toolkit} plan',
             'description': 'Plan management - show, scan, or generate report',
             'category': 'Os_Toolkit', 'arguments': ost_common + [
                 {'name': 'subcommand', 'help': 'show, scan, or report'},
             ]},
            {'display_name': 'Os_Toolkit sequence', 'command': f'{os_toolkit} sequence',
             'description': 'Run coordination sequences (startup, checkin, shutdown)',
             'category': 'Os_Toolkit', 'arguments': ost_common + [
                 {'name': 'sequence_name', 'help': 'startup, checkin, or shutdown'},
             ]},
            {'display_name': 'Os_Toolkit stats', 'command': f'{os_toolkit} stats',
             'description': 'Show session statistics',
             'category': 'Os_Toolkit', 'arguments': ost_common},
            {'display_name': 'Os_Toolkit save', 'command': f'{os_toolkit} save',
             'description': 'Save current session state',
             'category': 'Os_Toolkit', 'arguments': ost_common},
            {'display_name': 'Os_Toolkit interactive', 'command': f'{os_toolkit} interactive',
             'description': 'Launch interactive REPL mode',
             'category': 'Os_Toolkit', 'arguments': ost_common},

            # === onboarder subcommands (9) ===
            {'display_name': 'onboarder discover', 'command': f'{onboarder} discover',
             'description': 'Discover tools with recursive scanning and path fixing',
             'category': 'onboarder', 'arguments': [
                 {'name': '--recursive', 'help': 'Recursive discovery'},
                 {'name': '--depth', 'help': 'Maximum recursion depth (default: 3)'},
                 {'name': '--fix-paths', 'help': 'Fix path issues using pathfixer'},
                 {'name': '--consolidate', 'help': 'Consolidate after discovery'},
                 {'name': '--detailed', 'help': 'Detailed output'},
                 {'name': '--session', 'help': 'Session ID'},
                 {'name': '--new-session', 'help': 'Start new session'},
             ]},
            {'display_name': 'onboarder consolidate', 'command': f'{onboarder} consolidate',
             'description': 'Consolidate discovered tools into unified menu',
             'category': 'onboarder', 'arguments': [
                 {'name': '--name', 'help': 'Menu name (default: Org Tools)'},
                 {'name': '--session', 'help': 'Session ID'},
             ]},
            {'display_name': 'onboarder gui', 'command': f'{onboarder} gui',
             'description': 'Launch onboarder GUI interface',
             'category': 'onboarder', 'arguments': [
                 {'name': '--session', 'help': 'Session ID'},
             ]},
            {'display_name': 'onboarder list', 'command': f'{onboarder} list',
             'description': 'List discovered tools with optional filtering',
             'category': 'onboarder', 'arguments': [
                 {'name': '--session', 'help': 'Session ID'},
                 {'name': '--detailed', 'help': 'Detailed output'},
                 {'name': '--category', 'help': 'Filter by category'},
             ]},
            {'display_name': 'onboarder info', 'command': f'{onboarder} info',
             'description': 'Get detailed information about a specific tool',
             'category': 'onboarder', 'arguments': [
                 {'name': '--tool', 'help': 'Tool ID or name'},
                 {'name': '--session', 'help': 'Session ID'},
             ]},
            {'display_name': 'onboarder run-menu', 'command': f'{onboarder} run-menu',
             'description': 'Run the consolidated menu launcher',
             'category': 'onboarder', 'arguments': [
                 {'name': '--gui', 'help': 'Launch GUI'},
                 {'name': '--tool', 'help': 'Run specific tool'},
                 {'name': '--list', 'help': 'List tools'},
             ]},
            {'display_name': 'onboarder check-paths', 'command': f'{onboarder} check-paths',
             'description': 'Check and optionally fix path issues',
             'category': 'onboarder', 'arguments': [
                 {'name': '--fix', 'help': 'Fix issues'},
                 {'name': '--session', 'help': 'Session ID'},
             ]},
            {'display_name': 'onboarder session', 'command': f'{onboarder} session',
             'description': 'Session management - list, info, delete',
             'category': 'onboarder', 'arguments': [
                 {'name': '--list', 'help': 'List sessions'},
                 {'name': '--info', 'help': 'Session ID to show'},
                 {'name': '--delete', 'help': 'Session ID to delete'},
             ]},
            {'display_name': 'onboarder catalog', 'command': f'{onboarder} catalog',
             'description': 'Generate full system catalog (run all tools)',
             'category': 'onboarder', 'arguments': []},

            # === Filesync (complete args - the consolidated menu only has 5/22) ===
            {'display_name': 'Filesync', 'command': filesync,
             'description': 'Intelligent file organization and timeline reconstruction',
             'category': 'Filesync', 'arguments': [
                 {'name': 'source', 'help': 'Source directory to analyze'},
                 {'name': '--depth', 'help': 'Maximum recursion depth'},
                 {'name': '--string-match', 'help': 'Enable string matching between files'},
                 {'name': '--full', 'help': 'Enable full string matching (reads file content)'},
                 {'name': '--analyze-relationships', 'help': 'Analyze relationships between files'},
                 {'name': '--cluster-projects', 'help': 'Cluster files into projects'},
                 {'name': '--manifest', 'help': 'Generate JSON manifest'},
                 {'name': '--catalog', 'help': 'Generate file catalogs'},
                 {'name': '--report', 'help': 'Generate human-readable report'},
                 {'name': '--output-dir', 'help': 'Output directory'},
                 {'name': '--list-projects', 'help': 'List all projects with inferences'},
                 {'name': '--correct-project', 'help': 'Project ID to correct'},
                 {'name': '--set-type', 'help': 'Corrected project type'},
                 {'name': '--set-name', 'help': 'Corrected project name'},
                 {'name': '--set-notes', 'help': 'Notes about correction'},
                 {'name': '--organize', 'help': 'Organize files: date, project, category, extension'},
                 {'name': '--diff', 'help': 'Show what would be done without doing it'},
                 {'name': '--batch', 'help': 'Batch mode (no interactive confirmation)'},
                 {'name': '--match-file', 'help': 'Find documents that mention this file'},
                 {'name': '--documents-only', 'help': 'Only scan document files when matching'},
                 {'name': '--workers', 'help': 'Number of worker threads (default: 4)'},
                 {'name': '--max-files', 'help': 'Maximum files to process (default: 10000)'},
                 {'name': '--verbose', 'help': 'Verbose output'},
             ]},
        ]
        return triad

    def _load_script_profiles(self) -> Dict[str, Dict]:
        """Loads script profiles, merging system defaults with user profiles.

        Each profile has structure:
            { 'display_name': str, 'icon': str, 'system': bool,
              'tools': { tool_display_name: {'command': str, 'args': [], 'source': 'system'|'user'} } }
        """
        merged = {}
        try:
            sys_path = self.version_root / "inventory" / "babel_profiles.json"
            if sys_path.exists():
                with open(sys_path, 'r', encoding='utf-8') as f:
                    data = json.load(f).get('profiles', {})
                    for profile_key, p_data in data.items():
                        tools = {}
                        for tool_name, cmd in p_data.get('tool_locations', {}).items():
                            expanded_cmd = cmd.replace("{babel_root}", str(self.babel_root))
                            tools[tool_name] = {'command': expanded_cmd, 'args': [], 'source': 'system'}
                        merged[profile_key] = {
                            'display_name': p_data.get('name', profile_key),
                            'icon': p_data.get('icon', ''),
                            'system': True,
                            'tools': tools
                        }
        except Exception as e:
            self.engine.log_debug(f"Error loading system profiles: {e}", "ERROR")

        try:
            user_path = self.version_root / "inventory" / "grep_flight_profiles.json"
            if user_path.exists():
                with open(user_path, 'r', encoding='utf-8') as f:
                    user_data = json.load(f)
                    for name, pdata in user_data.items():
                        if 'tools' not in pdata:
                            pdata = {'display_name': name, 'system': False, 'tools': pdata}
                        pdata['system'] = False
                        merged[name] = pdata
        except Exception as e:
            self.engine.log_debug(f"Error loading user profiles: {e}", "ERROR")
        if not merged:
            merged["default"] = {'display_name': 'Default', 'icon': '', 'system': False, 'tools': {}}
        return merged

    def _save_script_profiles(self, profiles: Dict):
        """Saves user-defined script profiles and bridges them to workflow_profiles.json for Grep tab cycling."""
        try:
            sys_path = self.version_root / "inventory" / "babel_profiles.json"
            sys_names = []
            if sys_path.exists():
                with open(sys_path, 'r', encoding='utf-8') as f:
                    sys_names = list(json.load(f).get('profiles', {}).keys())
            user_profiles = {n: d for n, d in profiles.items()
                            if n not in sys_names and not d.get('system', False)}

            user_path = self.version_root / "inventory" / "grep_flight_profiles.json"
            with open(user_path, 'w', encoding='utf-8') as f:
                json.dump(user_profiles, f, indent=2)

            # Bridge: also write to workflow_profiles.json so Grep tab cycling picks them up
            wf_path = self.config_dir / "workflow_profiles.json"
            if wf_path.exists():
                with open(wf_path, 'r', encoding='utf-8') as f:
                    wf_data = json.load(f)
            else:
                wf_data = {"profiles": {}}

            for pname, pdata in user_profiles.items():
                workflow_actions = []
                for tool_name, tool_info in pdata.get('tools', {}).items():
                    if not isinstance(tool_info, dict):
                        continue
                    cmd = tool_info.get('command', '')
                    args = tool_info.get('args', [])
                    full_cmd = f"{cmd} {' '.join(args)}".strip() if args else cmd
                    workflow_actions.append({
                        "name": tool_name, "type": "custom",
                        "command": full_cmd, "source": cmd,
                        "target_mode": "auto", "output_to": "results",
                        "expectations": ""
                    })
                wf_data['profiles'][pname] = {
                    "workflow_actions": self._pad_workflow_actions(workflow_actions),
                    "last_updated": datetime.now().isoformat(),
                    "tool_locations": {tn: ti.get('command', '') for tn, ti in pdata.get('tools', {}).items() if isinstance(ti, dict)}
                }

            with open(wf_path, 'w', encoding='utf-8') as f:
                json.dump(wf_data, f, indent=2)

        except Exception as e:
            self.engine.log_debug(f"Error saving script profiles: {e}", "ERROR")


    def _create_custom_scripts_tab(self, notebook):
        """TAB 4: Add custom scripts/tools with arguments"""
        custom_tab = tk.Frame(notebook, bg='#1e1e1e')
        notebook.add(custom_tab, text="🛠️ Custom Scripts")

        tk.Label(
            custom_tab,
            text="Add custom scripts with arguments. These can be added to workflow action buttons or toolkit popup.",
            bg='#1e1e1e',
            fg='#888888',
            font=('Arial', 9),
            wraplength=750
        ).pack(pady=10, padx=10)

        # Custom scripts list
        scripts_frame = tk.Frame(custom_tab, bg='#1e1e1e')
        scripts_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        tk.Label(scripts_frame, text="Custom Scripts:", bg='#1e1e1e',
                fg='#4ec9b0', font=('Arial', 9, 'bold')).pack(anchor=tk.W, pady=(0, 5))

        scripts_list = tk.Listbox(scripts_frame, bg='#2d2d2d', fg='#d4d4d4',
                                  selectbackground='#4ec9b0', selectforeground='#000000',
                                  font=('Monospace', 8), height=12)
        scripts_list.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        scripts_catalog: List[Dict[str, Any]] = []

        def refresh_scripts_list():
            scripts_catalog.clear()
            scripts_list.delete(0, tk.END)
            
            # 1. Existing Local & GUI Scripts
            for script in self._load_custom_scripts():
                scripts_catalog.append({'entry': script, 'source': 'local'})
                scripts_list.insert(tk.END, f"[Local] {script['name']} → {script['command']}")
            
            # 2. Debug Tool Profiles
            debug_profile = self._load_debug_tool_profiles()
            for suite_path in debug_profile.get('tool_suites', []):
                display = "Scope Analyzer" if self._is_scope_path(suite_path) else Path(suite_path).name
                scripts_catalog.append({'entry': {'name': display, 'command': suite_path, 'category': 'suite'}, 'source': 'debug'})
                scripts_list.insert(tk.END, f"[GUI Suite] {display} → {suite_path}")
            for script_path in debug_profile.get('debug_scripts', []):
                display = Path(script_path).name
                scripts_catalog.append({'entry': {'name': display, 'command': script_path, 'category': 'script'}, 'source': 'debug'})
                scripts_list.insert(tk.END, f"[GUI Script] {display} → {script_path}")
            
            # 3. Taxonomized Draft Actions from On-boarding Queue
            draft_file = self.repo_root / ".docv2_workspace" / "draft_onboarding_actions.json"
            if draft_file.exists():
                try:
                    with open(draft_file, 'r') as f:
                        data = json.load(f)
                        for group_key, group_data in data.items():
                            tax = group_data.get('taxonomy', {})
                            tax_label = f"{tax.get('parent', 'Core')} > {tax.get('sub', 'Misc')}"
                            for action in group_data.get('draft_actions', []):
                                scripts_catalog.append({
                                    'entry': {**action, 'category': 'draft'}, 
                                    'source': 'onboarding',
                                    'taxonomy': tax
                                })
                                scripts_list.insert(tk.END, f"[Draft][{tax_label}] {action['name']} (from {Path(group_data['source_file']).name})")
                except Exception as e:
                    self.engine.log_debug(f"Error loading draft scripts: {e}", "ERROR")
            
            scripts_list.records = list(scripts_catalog)

        refresh_scripts_list()
        scripts_list.refresh = refresh_scripts_list

        # Buttons
        btn_frame = tk.Frame(custom_tab, bg='#1e1e1e')
        btn_frame.pack(fill=tk.X, padx=20, pady=10)

        tk.Button(btn_frame, text="➕ Add Script", command=lambda: self._add_custom_script(scripts_list),
                 bg='#4ec9b0', fg='#000000', width=15).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="✏️ Edit", command=lambda: self._edit_custom_script(scripts_list),
                 bg='#2d2d2d', fg='#d4d4d4', width=12).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="🗑️ Delete", command=lambda: self._delete_custom_script(scripts_list),
                 bg='#2d2d2d', fg='#d4d4d4', width=12).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="📤 Send to Workflow", command=lambda: self._send_script_to_workflow(scripts_list),
                 bg='#569cd6', fg='#ffffff', width=18).pack(side=tk.RIGHT, padx=5)
        tk.Button(btn_frame, text="Refresh", command=refresh_scripts_list,
                 bg='#2d2d2d', fg='#d4d4d4', width=10).pack(side=tk.RIGHT, padx=5)

    def _create_tool_profiles_tab(self, notebook):
        """TAB 5: Read-only view of available tool profiles"""
        profiles_tab = tk.Frame(notebook, bg='#1e1e1e')
        notebook.add(profiles_tab, text="🗂 Tool Profiles")

        tk.Label(
            profiles_tab,
            text="Combined view of default workflows, toolkit tools, custom scripts, and Debug Toolkit entries.",
            bg='#1e1e1e',
            fg='#888888',
            font=('Arial', 9),
            wraplength=780,
            justify=tk.LEFT
        ).pack(pady=10, padx=10)

        columns = ('Type', 'Name', 'Location')
        tree = ttk.Treeview(profiles_tab, columns=columns, show='headings', height=12)
        for col in columns:
            tree.heading(col, text=col)
            tree.column(col, anchor=tk.W, width=240 if col != 'Location' else 300)
        tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        def refresh_profiles():
            for item in tree.get_children():
                tree.delete(item)
            combined = (
                self._build_default_workflow_entries() +
                self._build_toolkit_entries() +
                self._build_custom_script_entries() +
                self._build_debug_tool_entries() +
                self._build_scope_entries()
            )
            for entry in combined:
                tree.insert('', tk.END, values=(entry.get('type', ''), entry.get('name', ''), entry.get('location', entry.get('source', ''))))

        refresh_profiles()

        btn_frame = tk.Frame(profiles_tab, bg='#1e1e1e')
        btn_frame.pack(pady=(0, 10))

        tk.Button(
            btn_frame,
            text="🔄 Refresh",
            command=refresh_profiles,
            bg='#2d2d2d',
            fg='#d4d4d4',
            width=12
        ).pack(side=tk.LEFT, padx=5)

        tk.Button(
            btn_frame,
            text="📜 Manage Scripts",
            command=lambda: self._select_tab_by_name(notebook, "Custom Scripts"),
            bg='#2d2d2d',
            fg='#d4d4d4',
            width=15
        ).pack(side=tk.LEFT, padx=5)

        tk.Button(
            btn_frame,
            text="⚙️ Manage Profiles",
            command=lambda: self._select_tab_by_name(notebook, "Script Profiles"),
            bg='#2d2d2d',
            fg='#d4d4d4',
            width=15
        ).pack(side=tk.LEFT, padx=5)

        tk.Button(
            btn_frame,
            text="🔭 Full Taxonomy Scan",
            command=self._run_full_taxonomy_scan,
            bg='#0e639c',
            fg='#ffffff',
            width=20
        ).pack(side=tk.RIGHT, padx=5)

    def _select_tab_by_name(self, notebook, name):
        """Select a notebook tab by partial text match."""
        for i in range(notebook.index("end")):
            if name in notebook.tab(i, "text"):
                notebook.select(i)
                return

    def _run_full_taxonomy_scan(self):
        """Invoke a full measurement registry scan and log result to traceback"""
        self.status_var.set("⌛ Running Full Taxonomy Scan...")
        self.engine.log_debug("Starting Full Taxonomy Scan (manual trigger)", "INFO")
        
        def worker():
            try:
                # Add modules path
                sys.path.insert(0, str(self.version_root / "modules"))
                import measurement_registry
                
                # Execute full scan
                reg = measurement_registry.scan_measurement_tools(mode="full")
                
                msg = f"✅ Taxonomy Scan Complete: {reg.get('total_tools')} tools taxonomized across {reg.get('files_scanned')} files."
                self.after(0, lambda: self.status_var.set(msg))
                
                # Log to Traceback
                log_to_traceback(EventCategory.PFC, "taxonomy_scan", 
                               {"mode": "full", "files": reg.get("files_scanned")}, 
                               {"tools_found": reg.get("total_tools")})
                               
            except Exception as e:
                err_msg = f"❌ Taxonomy Scan Failed: {str(e)}"
                self.after(0, lambda: self.status_var.set(err_msg))
                self.engine.log_debug(err_msg, "ERROR")

        threading.Thread(target=worker, daemon=True).start()

    def _save_toolkit_order(self, window):
        """Save toolkit order to config file"""
        config_dir = self.config_dir
        config_dir.mkdir(parents=True, exist_ok=True)
        config_file = config_dir / "toolkit_order.json"

        order_data = {
            "order": self.toolkit_order,
            "last_updated": datetime.now().isoformat()
        }

        with open(config_file, 'w') as f:
            json.dump(order_data, f, indent=2)

        self.status_var.set("💾 Toolkit order saved")
        self.engine.log_debug(f"Toolkit order saved to {config_file}", "INFO")
        messagebox.showinfo("Saved", f"Toolkit order saved to:\n{config_file}")
        self._save_current_profile()
        window.destroy()

    def _default_toolkit_order(self) -> List[Dict[str, Any]]:
        toolkit_source = Path(__file__).parent.parent / "engineers_toolkit.py"
        return [
            {"name": "✅ Syntax Check", "func": "check_syntax", "source": str(toolkit_source)},
            {"name": "↔️ Indentation", "func": "check_indentation", "source": str(toolkit_source)},
            {"name": "📦 Imports", "func": "check_imports", "source": str(toolkit_source)},
            {"name": "🎨 Formatting", "func": "check_formatting", "source": str(toolkit_source)},
            {"name": "🔍 Linting", "func": "check_linting", "source": str(toolkit_source)},
            {"name": "📞 Call Changes", "func": "check_call_changes", "source": str(toolkit_source)},
            {"name": "🚀 All Checks", "func": "run_all_checks", "source": str(toolkit_source)},
            {"name": "🔄 Auto-Fix", "func": "auto_fix", "source": str(toolkit_source)},
            {"name": "📸 Snapshot", "func": "create_snapshot", "source": str(toolkit_source)},
            {"name": "🧹 Clean", "func": "clean_project", "source": str(toolkit_source)},
        ]

    def _reset_toolkit_order(self):
        """Reset toolkit order to default"""
        self.toolkit_order = self._default_toolkit_order()
        self.status_var.set("🔄 Toolkit order reset to default")

    # ==== WORKFLOW PROFILE CONFIGURATION METHODS ====

    def _introspect_script(self, script_path: str) -> Dict[str, Any]:
        """Introspect a script for language, help text, and parsed arguments.

        Returns dict with: language, interpreter, help_text, parsed_args, arg_count_match
        """
        result = {
            'language': 'Unknown', 'interpreter': None, 'help_text': '',
            'parsed_args': [], 'arg_count_match': None, 'path': script_path
        }

        path = Path(script_path)
        if not path.exists():
            return result

        # Language detection by extension
        ext_map = {
            '.py': ('Python', 'python3'), '.sh': ('Bash', 'bash'),
            '.bash': ('Bash', 'bash'), '.js': ('JavaScript', 'node'),
            '.c': ('C', None), '.cpp': ('C++', None),
            '.rb': ('Ruby', 'ruby'), '.pl': ('Perl', 'perl'),
        }
        ext = path.suffix.lower()
        if ext in ext_map:
            result['language'], result['interpreter'] = ext_map[ext]

        # Shebang detection as fallback
        try:
            with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                first_line = f.readline().strip()
            if first_line.startswith('#!'):
                if 'python' in first_line:
                    result['language'] = 'Python'
                    result['interpreter'] = result['interpreter'] or 'python3'
                elif 'bash' in first_line or 'sh' in first_line:
                    result['language'] = 'Bash'
                    result['interpreter'] = result['interpreter'] or 'bash'
                elif 'node' in first_line:
                    result['language'] = 'JavaScript'
                    result['interpreter'] = result['interpreter'] or 'node'
        except Exception:
            pass

        # For Python scripts: run -h and parse source for add_argument
        if result['language'] == 'Python' and result['interpreter']:
            # Run -h with timeout
            try:
                proc = subprocess.run(
                    [result['interpreter'], str(path), '-h'],
                    capture_output=True, text=True, timeout=5,
                    env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'}
                )
                if proc.returncode == 0 and proc.stdout.strip():
                    result['help_text'] = proc.stdout.strip()
            except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
                pass

            # Parse source for add_argument calls
            try:
                source = path.read_text(encoding='utf-8', errors='ignore')
                arg_pattern = re.compile(
                    r"\.add_argument\(\s*['\"]([^'\"]+)['\"]"
                    r"(?:.*?help\s*=\s*['\"]([^'\"]*)['\"])?"
                    r"(?:.*?choices\s*=\s*(\[[^\]]*\]))?"
                    r"(?:.*?default\s*=\s*([^,\)]+))?"
                    r"(?:.*?action\s*=\s*['\"]([^'\"]*)['\"])?",
                    re.DOTALL
                )
                for m in arg_pattern.finditer(source):
                    arg_info = {
                        'name': m.group(1),
                        'help': m.group(2) or '',
                        'choices': m.group(3) or '',
                        'default': (m.group(4) or '').strip(),
                        'action': m.group(5) or '',
                    }
                    result['parsed_args'].append(arg_info)

                # Cross-reference counts
                if result['help_text']:
                    help_args = set(re.findall(r'(?:^|\s)(-{1,2}[\w-]+)', result['help_text']))
                    source_args = {a['name'] for a in result['parsed_args']}
                    result['arg_count_match'] = len(help_args - source_args) == 0
            except Exception:
                pass

        return result

    def _load_profile_names(self) -> List[str]:
        """Load list of available profile names from both config files"""
        profiles = set()
        
        # 1. Legacy/User Workflow Profiles
        profiles_file = self.config_dir / "workflow_profiles.json"
        if profiles_file.exists():
            try:
                with open(profiles_file, 'r') as f:
                    data = json.load(f)
                    profiles.update(data.get('profiles', {}).keys())
            except: pass

        # 2. Babel System Profiles
        babel_file = self.version_root / "inventory" / "babel_profiles.json"
        if babel_file.exists():
            try:
                with open(babel_file, 'r') as f:
                    data = json.load(f)
                    profiles.update(data.get('profiles', {}).keys())
            except: pass

        # 3. User Script Profiles (grep_flight_profiles.json)
        user_file = self.version_root / "inventory" / "grep_flight_profiles.json"
        if user_file.exists():
            try:
                with open(user_file, 'r') as f:
                    profiles.update(json.load(f).keys())
            except: pass

        if not profiles:
            return ["Default Profile"]
            
        return sorted(list(profiles))

    def _load_profile_config(self):
        """Load config for current selected profile (config UI callback)"""
        if not self.current_profile_var:
            return
        profile_name = self.current_profile_var.get()
        self._apply_profile_config(profile_name)

    def _apply_profile_config(self, profile_name: str) -> bool:
        """Load profile data from disk and apply it to the current session"""
        profile_data = None
        
        # 1. Try User Config
        profiles_file = self.config_dir / "workflow_profiles.json"
        if profiles_file.exists():
            try:
                with open(profiles_file, 'r') as f:
                    data = json.load(f)
                    profile_data = data.get('profiles', {}).get(profile_name)
            except: pass

        # 2. Try Babel Config if not found
        if not profile_data:
            babel_file = self.version_root / "inventory" / "babel_profiles.json"
            if babel_file.exists():
                try:
                    with open(babel_file, 'r') as f:
                        data = json.load(f)
                        # Babel profiles store tools in 'tool_locations', we need to convert to workflow actions if missing
                        raw_data = data.get('profiles', {}).get(profile_name)
                        if raw_data:
                            profile_data = raw_data
                            # Auto-convert tool_locations to workflow_actions if needed
                            if 'workflow_actions' not in profile_data and 'tool_locations' in profile_data:
                                actions = []
                                for name, cmd in profile_data['tool_locations'].items():
                                    cmd = cmd.replace("{babel_root}", str(self.babel_root))
                                    actions.append({
                                        "name": name,
                                        "type": "custom",
                                        "command": cmd,
                                        "source": cmd,
                                        "target_mode": "auto",
                                        "output_to": "results",
                                        "expectations": ""
                                    })
                                profile_data['workflow_actions'] = actions
                except: pass

        if not profile_data:
            return False

        self.workflow_actions = self._pad_workflow_actions(
            profile_data.get('workflow_actions', self.workflow_actions)
        )
        self.toolkit_order = profile_data.get('toolkit_order', self.toolkit_order or self._default_toolkit_order())
        self.tool_locations = profile_data.get('tool_locations', {})
        self.active_profile = profile_name
        if self.current_profile_var is not None:
            self.current_profile_var.set(profile_name)
        self.status_var.set(f"📋 Loaded profile: {profile_name}")
        self._build_workflow_buttons()
        return True

    def _save_profile_config(self, _window):
        """Save current config to selected profile"""
        profile_name = self.current_profile_var.get()
        profiles_file = self.config_dir / "workflow_profiles.json"

        # Load existing profiles
        if profiles_file.exists():
            with open(profiles_file, 'r') as f:
                data = json.load(f)
        else:
            data = {"profiles": {}}

        # Update profile
        data['profiles'][profile_name] = {
            "workflow_actions": self.workflow_actions,
            "toolkit_order": self.toolkit_order,
            "tool_locations": self.tool_locations,
            "last_updated": datetime.now().isoformat(),
            "version": Path(__file__).parent.parent.parent.name  # Track version
        }

        with open(profiles_file, 'w') as f:
            json.dump(data, f, indent=2)

        self.active_profile = profile_name
        self.status_var.set(f"💾 Saved profile: {profile_name}")
        messagebox.showinfo("Saved", f"Profile '{profile_name}' saved successfully!")

    def _default_workflow_actions(self) -> List[Dict[str, Any]]:
        grep_engine_source = Path(__file__).parent / "grep_engine.py"
        return [
            {"name": "Quick Scan", "type": "builtin", "source": str(grep_engine_source),
             "target_mode": "auto", "output_to": "results", "expectations": "basic_scan"},
            {"name": "Deep Debug", "type": "builtin", "source": str(grep_engine_source),
             "target_mode": "auto", "output_to": "pfc+results", "expectations": "detailed_analysis"},
            {"name": "PFL Audit", "type": "builtin", "source": str(grep_engine_source),
             "target_mode": "auto", "output_to": "pfc", "expectations": "pfl_tags"},
            {"name": "Surgical Fix", "type": "builtin", "source": str(grep_engine_source),
             "target_mode": "auto", "output_to": "diff_queue", "expectations": "targeted_fix"},
        ]

    def _scope_script_path(self) -> Optional[Path]:
        scope_path = Path(__file__).parent.parent / 'scope' / 'scope.py'
        return scope_path if scope_path.exists() else None

    def _is_scope_path(self, path_str: str) -> bool:
        scope_path = self._scope_script_path()
        if not scope_path:
            return False
        try:
            return Path(path_str).resolve() == scope_path.resolve()
        except Exception:
            return False

    def _build_profile_template_actions(self, template_choice: str) -> List[Dict[str, Any]]:
        choice = (template_choice or '').lower()
        if choice.startswith('clone') and self.workflow_actions:
            return [dict(action) for action in self.workflow_actions]
        if choice.startswith('default'):
            return self._default_workflow_actions()
        if 'engineer' in choice:
            return self._entries_to_actions(self._build_toolkit_entries())
        if 'debug' in choice:
            return self._entries_to_actions(self._build_debug_tool_entries())
        if 'scope' in choice:
            return self._entries_to_actions(self._build_scope_entries())
        return []

    def _entries_to_actions(self, entries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        actions: List[Dict[str, Any]] = []
        for entry in entries:
            base = {
                "name": entry.get('name', 'Workflow Tool'),
                "type": entry.get('type', 'custom'),
                "source": entry.get('source', ''),
                "target_mode": entry.get('target_mode', 'auto'),
                "output_to": entry.get('output_to', 'results'),
                "expectations": entry.get('expectations', ''),
            }
            if entry.get('command'):
                base['command'] = entry.get('command')
            if entry.get('args'):
                base['args'] = entry.get('args')
            actions.append(base)
            if len(actions) >= 8:
                break
        return actions

    def _placeholder_action(self) -> Dict[str, Any]:
        return {"name": "[Add Custom]", "type": "placeholder", "source": "", "target_mode": "auto",
                "output_to": "results", "expectations": ""}

    def _pad_workflow_actions(self, actions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        padded = list(actions)
        while len(padded) < 8:
            padded.append(self._placeholder_action())
        return padded[:8]

    def _load_workflow_actions_config(self) -> List[Dict]:
        """Load workflow actions from profile config"""
        actions = []
        
        # 1. Try loading Babel Profiles (Primary Source)
        profile_path = self.version_root / "inventory" / "babel_profiles.json"
        if profile_path.exists():
            try:
                with open(profile_path, 'r') as f:
                    data = json.load(f)
                    
                # Get active profile (default to 'default')
                if not self.active_profile:
                    self.active_profile = "default"
                    
                # Look for profile by ID or Name
                profile_data = data.get('profiles', {}).get(self.active_profile)
                if not profile_data:
                    # Fallback to finding by name
                    for pid, p in data.get('profiles', {}).items():
                        if p.get('name') == self.active_profile:
                            profile_data = p
                            break
                            
                if not profile_data:
                    # Fallback to 'default' key if active_profile not found
                    profile_data = data.get('profiles', {}).get('default')

                if profile_data:
                    # Log for debugging
                    profile_name = profile_data.get('name')
                    self.status_var.set(f"Loaded Profile: {profile_name}")
                    tools = profile_data.get('tool_locations', {})
                    
                    # Log profile load to traceback UI
                    self._add_traceback(f"📥 Loading Profile: {profile_name}", "PROFILE")
                    self._add_traceback(f"   Tools: {len(tools)} custom actions", "PROFILE")
                    
                    for name, cmd in tools.items():
                        # Resolve placeholders
                        cmd = cmd.replace("{babel_root}", str(self.babel_root))
                        actions.append({
                            "name": name, # Fixed: use 'name' not 'label'
                            "command": cmd,
                            "type": "custom",
                            "source": cmd,
                            "target_mode": "auto",
                            "output_to": "results"
                        })
                        # Log individual tool load
                        self.engine.log_debug(f"   + Tool: {name} -> {cmd[:50]}...", "DEBUG")
                        
                    return self._pad_workflow_actions(actions)

            except Exception as e:
                self.engine.log_debug(f"Error loading babel profiles: {e}", "ERROR")

        # 2. Fallback to existing logic (Legacy config locations)
        # Priority: Local Config Dir > Morph Data Dir > Legacy Workspace
        profiles_file = self.config_dir / "workflow_profiles.json"
        if not profiles_file.exists():
            profiles_file = self.morph_data_dir / "workflow_profiles.json"
            
        if not profiles_file.exists():
            legacy_file = self.version_root / ".docv2_workspace" / "config" / "workflow_profiles.json"
            if legacy_file.exists():
                profiles_file = legacy_file

        if profiles_file.exists():
            try:
                with open(profiles_file, 'r') as f:
                    data = json.load(f)
                    default_profile = data.get('default_profile', 'Default Profile')
                    self.active_profile = default_profile
                    profile_data = data.get('profiles', {}).get(default_profile, {})
                    if 'workflow_actions' in profile_data:
                        return self._pad_workflow_actions(profile_data['workflow_actions'])
            except Exception as e:
                print(f"Error loading workflow profile: {e}")

        # 3. Hardcoded defaults if nothing else found
        defaults = [
            {"name": "Status", "command": f"python3 {self.babel_root}/Os_Toolkit.py latest -z", "type": "custom"},
            {"name": "Analyze", "command": f"python3 {self.babel_root}/Os_Toolkit.py analyze --depth 2 -z", "type": "custom"},
            {"name": "Sync Todos", "command": f"python3 {self.babel_root}/Os_Toolkit.py actions --run sync_all_todos", "type": "custom"},
            {"name": "Security", "command": f"python3 {self.babel_root}/Os_Toolkit.py actions --run check_security", "type": "custom"}
        ]
        return self._pad_workflow_actions(defaults)

    def _load_workflow_actions_from_profile(self) -> Optional[List[Dict]]:
        """Load workflow actions from current profile (for config UI)"""
        profile_name = None
        if self.current_profile_var is not None:
            profile_name = self.current_profile_var.get()
        if not profile_name:
            profile_name = self.active_profile

        profiles_file = self.config_dir / "workflow_profiles.json"
        if not profiles_file.exists():
            profiles_file = self.morph_data_dir / "workflow_profiles.json"
        
        if not profiles_file.exists():
            profiles_file = self.version_root / ".docv2_workspace" / "config" / "workflow_profiles.json"
        
        if not profiles_file.exists():
            return None

        try:
            with open(profiles_file, 'r') as f:
                data = json.load(f)
            profile_data = data.get('profiles', {}).get(profile_name, {})
            if 'workflow_actions' in profile_data:
                self.tool_locations = profile_data.get('tool_locations', self.tool_locations)
                self.toolkit_order = profile_data.get('toolkit_order', self.toolkit_order)
                return profile_data['workflow_actions']
        except Exception as exc:
            print(f"Error reading workflow profile '{profile_name}': {exc}")
        return None

    def _load_all_workflow_profiles(self) -> Dict[str, Any]:
        """Return all stored workflow profiles"""
        profiles_file = self.config_dir / "workflow_profiles.json"
        if not profiles_file.exists():
            profiles_file = self.morph_data_dir / "workflow_profiles.json"
            
        if not profiles_file.exists():
            profiles_file = self.version_root / ".docv2_workspace" / "config" / "workflow_profiles.json"
            
        if not profiles_file.exists():
            return {}
        try:
            with open(profiles_file, 'r') as f:
                data = json.load(f)
            return data.get('profiles', {})
        except Exception as exc:
            print(f"Error loading workflow profiles: {exc}")
            return {}

    def _cycle_workflow_profile(self, direction: int = 1) -> None:
        """Rotate through all available profile names (Babel + User)"""
        # Get merged sorted list of all available profile names
        profiles = self._load_profile_names()
        if not profiles:
            return

        # Determine current profile name
        current = self.active_profile
        if self.current_profile_var is not None and self.current_profile_var.get():
            current = self.current_profile_var.get()

        try:
            # Find current index in the merged list
            idx = profiles.index(current)
        except ValueError:
            # If current not in list (e.g. initial 'default' vs 'Babel Core' name mapping)
            # Try to find by display name or default to 0
            idx = 0

        # Calculate new index with wraparound
        new_idx = (idx + direction) % len(profiles)
        new_profile = profiles[new_idx]
        
        # Apply the new profile
        if self._apply_profile_config(new_profile):
            self.status_var.set(f"🔁 Profile Swapped: {new_profile}")
            if hasattr(self, 'profile_indicator_var'):
                self.profile_indicator_var.set(new_profile)

    def _move_workflow_up(self, idx, refresh_func):
        """Move workflow action up in order"""
        if idx > 0:
            self.workflow_actions[idx], self.workflow_actions[idx-1] = self.workflow_actions[idx-1], self.workflow_actions[idx]
            refresh_func()

    def _move_workflow_down(self, idx, refresh_func):
        """Move workflow action down in order"""
        if idx < len(self.workflow_actions) - 1:
            self.workflow_actions[idx], self.workflow_actions[idx+1] = self.workflow_actions[idx+1], self.workflow_actions[idx]
            refresh_func()

    def _show_workflow_action_context_menu(self, event, action: Dict[str, Any], idx: int, refresh_func: Callable):
        """Show context menu for workflow action buttons."""
        menu = tk.Menu(self, tearoff=0, bg=self.config.BG_COLOR, fg=self.config.FG_COLOR)

        # Only allow editing arguments for 'custom', 'script', 'debug_suite', 'debug_script', 'toolkit' actions
        if action.get('type') in ['custom', 'script', 'debug_suite', 'debug_script', 'toolkit']:
            menu.add_command(label="✏️ Edit Arguments", command=lambda a=action, i=idx, r=refresh_func: self._edit_workflow_action_args(a, i, r))
            menu.add_separator()
        
        menu.add_command(label=f"Remove Slot {idx + 1}", command=lambda i=idx, r=refresh_func: self._remove_workflow_slot(i, r))
        menu.post(event.x_root, event.y_root)

    def _edit_workflow_action_args(self, action: Dict[str, Any], idx: int, refresh_func: Callable):
        """Edit the arguments for a custom workflow action."""
        dialog = tk.Toplevel(self)
        dialog.title(f"Edit Arguments for: {action.get('name', 'Custom Action')}")
        dialog.geometry("500x250")
        dialog.configure(bg='#1e1e1e')
        dialog.transient(self)
        dialog.grab_set()

        tk.Label(dialog, text=f"Edit Arguments for '{action.get('name', 'Custom Action')}'",
                bg='#1e1e1e', fg=self.config.ACCENT_COLOR,
                font=('Arial', 11, 'bold')).pack(pady=10)

        # Display Command
        tk.Label(dialog, text="Command:", bg='#1e1e1e', fg='#d4d4d4').pack(anchor=tk.W, padx=20)
        tk.Label(dialog, text=action.get('command', 'N/A'), bg='#2a2a2a', fg='#ce9178',
                font=('Monospace', 9), wraplength=450, justify=tk.LEFT, relief=tk.FLAT, bd=1).pack(fill=tk.X, padx=20, pady=2)

        # Arguments Input
        tk.Label(dialog, text="Arguments:", bg='#1e1e1e', fg='#d4d4d4').pack(anchor=tk.W, padx=20, pady=(10, 0))
        
        # Ensure args is a string for the Entry widget
        initial_args = ""
        if isinstance(action.get('args'), list):
            initial_args = " ".join(action['args'])
        elif isinstance(action.get('args'), str):
            initial_args = action['args']

        args_var = tk.StringVar(value=initial_args)
        args_entry = tk.Entry(dialog, textvariable=args_var, width=60, bg='#2a2a2a', fg='#d4d4d4',
                              insertbackground='#d4d4d4', font=('Monospace', 9))
        args_entry.pack(padx=20, pady=5)
        
        def save_args():
            new_args_str = args_var.get().strip()
            
            # Update the action in workflow_actions
            # Ensure it's stored as a list if that's the expected format for subprocess.run later
            if new_args_str:
                action['args'] = shlex.split(new_args_str) # Use shlex to split arguments properly
            else:
                action['args'] = []

            # Update the full command in the action if it's a 'custom' script type
            # This ensures the command property reflects the new args for execution
            if action.get('type') == 'custom' and 'command' in action:
                base_cmd = action['command'].split(None, 1)[0] # Get base command without old args
                if action['args']:
                    action['command'] = f"{base_cmd} {' '.join(action['args'])}"
                else:
                    action['command'] = base_cmd


            # Save the updated profile configuration
            self._save_current_profile()
            
            # Refresh the workflow buttons in the main UI
            refresh_func()
            
            dialog.destroy()
            self.status_var.set(f"✏️ Arguments updated for '{action.get('name', 'Custom Action')}'")
            self.engine.log_debug(f"Arguments for '{action.get('name')}' updated: {action.get('args')}", "INFO")

        def cancel_edit():
            dialog.destroy()

        button_frame = tk.Frame(dialog, bg='#1e1e1e')
        button_frame.pack(pady=15)

        tk.Button(button_frame, text="Save", command=save_args, bg='#4ec9b0',
                 fg='#000000', width=12, font=('Arial', 9, 'bold')).pack(side=tk.LEFT, padx=5)
        tk.Button(button_frame, text="Cancel", command=cancel_edit, bg='#2d2d2d',
                 fg='#d4d4d4', width=12, font=('Arial', 9)).pack(side=tk.LEFT, padx=5)

        dialog.bind('<Return>', lambda e: save_args())
        dialog.bind('<Escape>', lambda e: cancel_edit())
        
        self._add_traceback(f"Opened argument editor for: {action.get('name')}", "DEBUG")

    def _remove_workflow_slot(self, idx: int, refresh_func: Callable):
        """Remove a workflow action from a slot and replace with a placeholder."""
        if messagebox.askyesno("Remove Action", f"Are you sure you want to remove '{self.workflow_actions[idx]['name']}' from slot {idx + 1}?"):
            self.workflow_actions[idx] = self._placeholder_action()
            self._save_current_profile()
            refresh_func()
            self.status_var.set(f"Slot {idx + 1} cleared.")
            self.engine.log_debug(f"Workflow action removed from slot {idx + 1}", "INFO")

    def _edit_workflow_action(self, idx, refresh_func):
        """Edit workflow action (for custom/placeholder)"""
        action = self.workflow_actions[idx]

        # Create edit dialog
        dialog = tk.Toplevel(self)
        dialog.title("Edit Workflow Action")
        dialog.geometry("500x400")
        dialog.configure(bg='#1e1e1e')
        dialog.transient(self)

        tk.Label(dialog, text="Edit Workflow Action", bg='#1e1e1e', fg='#4ec9b0',
                font=('Arial', 11, 'bold')).pack(pady=10)

        # Name
        tk.Label(dialog, text="Action Name:", bg='#1e1e1e', fg='#d4d4d4').pack(anchor=tk.W, padx=20)
        name_var = tk.StringVar(value=action.get('name', ''))
        tk.Entry(dialog, textvariable=name_var, width=40).pack(padx=20, pady=5)

        # Type
        tk.Label(dialog, text="Type:", bg='#1e1e1e', fg='#d4d4d4').pack(anchor=tk.W, padx=20)
        type_var = tk.StringVar(value=action.get('type', 'custom'))
        ttk.Combobox(dialog, textvariable=type_var, values=["builtin", "custom", "script"],
                    width=37, state='readonly').pack(padx=20, pady=5)

        # Target mode
        tk.Label(dialog, text="Target Mode:", bg='#1e1e1e', fg='#d4d4d4').pack(anchor=tk.W, padx=20)
        target_var = tk.StringVar(value=action.get('target_mode', 'auto'))
        ttk.Combobox(dialog, textvariable=target_var, values=["auto", "manual", "marked_files", "current_file"],
                    width=37, state='readonly').pack(padx=20, pady=5)

        # Output destination
        tk.Label(dialog, text="Output To:", bg='#1e1e1e', fg='#d4d4d4').pack(anchor=tk.W, padx=20)
        output_var = tk.StringVar(value=action.get('output_to', 'results'))
        ttk.Combobox(dialog, textvariable=output_var,
                    values=["results", "pfc", "pfc+results", "diff_queue", "tasks", "traceback"],
                    width=37, state='readonly').pack(padx=20, pady=5)

        # Expectations
        tk.Label(dialog, text="Expectations:", bg='#1e1e1e', fg='#d4d4d4').pack(anchor=tk.W, padx=20)
        expect_var = tk.StringVar(value=action.get('expectations', 'none'))
        tk.Entry(dialog, textvariable=expect_var, width=40).pack(padx=20, pady=5)

        def save_action():
            self.workflow_actions[idx] = {
                "name": name_var.get(),
                "type": type_var.get(),
                "source": action.get('source', ''),  # Preserve source
                "target_mode": target_var.get(),
                "output_to": output_var.get(),
                "expectations": expect_var.get()
            }
            refresh_func()
            dialog.destroy()

        tk.Button(dialog, text="Save", command=save_action, bg='#4ec9b0',
                 fg='#000000', width=15).pack(pady=20)

    # ==== PROFILE MANAGEMENT METHODS ====

    def _create_new_profile(self, listbox: Optional[tk.Listbox] = None):
        """Create a new workflow profile with guided onboarding"""

        dialog = tk.Toplevel(self)
        dialog.title("Create Workflow Profile")
        dialog.configure(bg='#1e1e1e')
        dialog.geometry("420x360")
        dialog.transient(self)
        dialog.attributes('-topmost', True)

        tk.Label(dialog, text="Create Workflow Profile", bg='#1e1e1e', fg='#4ec9b0',
                 font=('Arial', 12, 'bold')).pack(pady=10)

        name_var = tk.StringVar()
        tk.Label(dialog, text="Profile Name", bg='#1e1e1e', fg='#d4d4d4').pack(anchor=tk.W, padx=20)
        tk.Entry(dialog, textvariable=name_var, width=32).pack(padx=20, pady=(0, 10))

        template_options = [
            "Blank (placeholders)",
            "Clone current profile",
            "Babel Core preset",
            "Debug Toolkit preset",
            "Scope Analyzer preset"
        ]
        template_var = tk.StringVar(value=template_options[2]) # Default to Babel Core
        tk.Label(dialog, text="Template", bg='#1e1e1e', fg='#d4d4d4').pack(anchor=tk.W, padx=20)
        ttk.Combobox(dialog, textvariable=template_var, values=template_options,
                     state='readonly', width=30).pack(padx=20, pady=(0, 10))

        open_add_swap = tk.BooleanVar(value=True)
        tk.Checkbutton(
            dialog,
            text="Open Add / Swap to finish setup",
            variable=open_add_swap,
            bg='#1e1e1e',
            fg='#d4d4d4',
            selectcolor='#1e1e1e',
            activebackground='#1e1e1e'
        ).pack(anchor=tk.W, padx=20, pady=(0, 10))

        status_label = tk.Label(dialog, text="", bg='#1e1e1e', fg='#c586c0', wraplength=360, justify=tk.LEFT)
        status_label.pack(padx=20, pady=(0, 10))

        def refresh_profile_list() -> None:
            if not listbox:
                return
            listbox.delete(0, tk.END)
            for profile in self._load_profile_names():
                listbox.insert(tk.END, profile)

        def create_profile():
            profile_name = name_var.get().strip()
            if not profile_name:
                status_label.config(text="Please enter a profile name.")
                return
            existing = self._load_profile_names()
            if profile_name in existing:
                status_label.config(text="Profile already exists. Choose a different name.")
                return

            template_choice = template_var.get()
            actions = []
            
            # Handle Babel Core preset specifically
            if "Babel Core" in template_choice:
                # Load from babel_profiles.json directly
                babel_file = self.version_root / "inventory" / "babel_profiles.json"
                if babel_file.exists():
                    try:
                        with open(babel_file, 'r') as f:
                            data = json.load(f)
                            pdata = data.get('profiles', {}).get('default')
                            if pdata and 'tool_locations' in pdata:
                                for name, cmd in pdata['tool_locations'].items():
                                    cmd = cmd.replace("{babel_root}", str(self.babel_root))
                                    actions.append({
                                        "name": name,
                                        "type": "custom",
                                        "command": cmd,
                                        "source": cmd,
                                        "target_mode": "auto",
                                        "output_to": "results"
                                    })
                    except: pass
            else:
                # Fallback to existing logic
                actions = self._build_profile_template_actions(template_choice)
                
            existing_locations = dict(self.tool_locations)
            lower_choice = (template_choice or '').lower()
            if lower_choice.startswith('clone'):
                new_locations = existing_locations
            else:
                new_locations = {}
                for action in actions:
                    source = action.get('source') or action.get('command')
                    if source:
                        new_locations[action.get('name', f"Tool {len(new_locations)+1}")] = source

            self.tool_locations = new_locations
            self.workflow_actions = self._pad_workflow_actions(actions)
            self.active_profile = profile_name
            if self.current_profile_var is not None:
                self.current_profile_var.set(profile_name)
            if hasattr(self, 'profile_indicator_var'):
                self.profile_indicator_var.set(profile_name)

            self._save_current_profile()
            self._build_workflow_buttons()
            refresh_profile_list()
            self.status_var.set(f"✨ Created profile '{profile_name}' using {template_choice}")
            dialog.destroy()

            if open_add_swap.get():
                self.after(150, lambda: self._quick_add_workflow_tool(profile_override=profile_name))

        tk.Button(dialog, text="Create Profile", command=create_profile,
                 bg='#4ec9b0', fg='#000000', width=16).pack(pady=5)
        tk.Button(dialog, text="Cancel", command=dialog.destroy,
                 bg='#2d2d2d', fg='#d4d4d4', width=12).pack()

        dialog.bind('<Return>', lambda _e: create_profile())
        dialog.bind('<Escape>', lambda _e: dialog.destroy())

    def _rename_profile(self, listbox):
        """Rename selected profile"""
        selection = listbox.curselection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a profile to rename")
            return

        old_name = listbox.get(selection[0])

        # Protect system profiles
        profile = self.script_profiles.get(old_name, {})
        if profile.get('system', False):
            messagebox.showwarning("System Profile",
                f"'{profile.get('display_name', old_name)}' is a system profile and cannot be renamed.")
            return

        new_name = simpledialog.askstring("Rename Profile", f"Rename '{old_name}' to:")
        if new_name and new_name != old_name:
            if new_name in self.script_profiles:
                messagebox.showwarning("Exists", f"Profile '{new_name}' already exists.")
                return
            self.script_profiles[new_name] = self.script_profiles.pop(old_name)
            self.script_profiles[new_name]['display_name'] = new_name
            self._save_script_profiles(self.script_profiles)
            listbox.delete(0, tk.END)
            for name in sorted(self.script_profiles.keys()):
                listbox.insert(tk.END, name)
            self.status_var.set(f"Renamed '{old_name}' to '{new_name}'")

    def _delete_profile(self, listbox):
        """Delete selected profile"""
        selection = listbox.curselection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a profile to delete")
            return

        profile_name = listbox.get(selection[0])

        # Protect system profiles
        profile = self.script_profiles.get(profile_name, {})
        if profile.get('system', False):
            messagebox.showwarning("System Profile",
                f"'{profile.get('display_name', profile_name)}' is a system profile and cannot be deleted.")
            return

        if messagebox.askyesno("Confirm Delete", f"Delete profile '{profile_name}'?"):
            del self.script_profiles[profile_name]
            self._save_script_profiles(self.script_profiles)
            listbox.delete(0, tk.END)
            for name in sorted(self.script_profiles.keys()):
                listbox.insert(tk.END, name)
            self.status_var.set(f"Deleted profile: {profile_name}")

    # ==== CUSTOM SCRIPTS METHODS ====

    def _load_custom_scripts(self) -> List[Dict]:
        """Load custom scripts from config"""
        config_dir = self.config_dir
        scripts_file = config_dir / "custom_scripts.json"

        if scripts_file.exists():
            with open(scripts_file, 'r') as f:
                return json.load(f).get('scripts', [])
        return []

    def _save_custom_scripts(self, scripts: List[Dict]):
        """Save scripts to custom_scripts.json"""
        config_path = self.config_dir / "custom_scripts.json"
        try:
            with open(config_path, 'w') as f:
                json.dump(scripts, f, indent=2)
        except Exception as e:
            self.engine.log_debug(f"Error saving custom scripts: {e}", "ERROR")

    def _load_debug_tool_profiles(self) -> Dict[str, Any]:
        """Load unified custom tool definitions"""
        config_path = self.config_dir / "custom_tools.json"
        
        if not config_path.exists():
            # Fallback/Migration: Check legacy workspace
            legacy_workspace = self.version_root / ".docv2_workspace" / "config" / "custom_tools.json"
            if legacy_workspace.exists():
                try:
                    with open(legacy_workspace, 'r') as f:
                        config = json.load(f)
                    with open(config_path, 'w') as f:
                        json.dump(config, f, indent=2)
                    return config
                except: pass

            # Fallback/Migration: Check legacy home path
            legacy_path = Path.home() / '.babel' / 'grep_flight_custom_tools.json'
            if legacy_path.exists():
                try:
                    with open(legacy_path, 'r') as f:
                        config = json.load(f)
                    # Save to new location
                    with open(config_path, 'w') as f:
                        json.dump(config, f, indent=2)
                    return config
                except Exception as e:
                    print(f"Error migrating legacy tools config: {e}")
            return {}
        else:
            try:
                with open(config_path, 'r') as f:
                    config = json.load(f)
            except Exception as exc:
                print(f"Error loading custom tools config: {exc}")
                config = {}

        changed = False
        scope_path = self._scope_script_path()
        if scope_path:
            suites = config.setdefault('tool_suites', [])
            scope_str = str(scope_path)
            if scope_str not in suites:
                suites.append(scope_str)
                changed = True
            tool_profiles = config.setdefault('tool_profiles', {})
            if scope_str not in tool_profiles:
                tool_profiles[scope_str] = '--scope'
                changed = True
        if changed:
            try:
                with open(config_path, 'w') as f:
                    json.dump(config, f, indent=2)
            except Exception as exc:
                print(f"Error writing custom tools config: {exc}")
        return config

    def _sync_script_with_debug_toolkit(self, script_entry: Dict[str, Any]) -> None:
        config_path = self.config_dir / "custom_tools.json"
        
        config = self._load_debug_tool_profiles()
        tool_profiles = config.get('tool_profiles', {})
        debug_scripts = config.get('debug_scripts', [])
        script_path = script_entry.get('command')
        if not script_path:
            return
        if script_path not in debug_scripts:
            debug_scripts.append(script_path)
        tool_profiles[script_path] = script_entry.get('args', '')
        config['debug_scripts'] = debug_scripts
        config['tool_profiles'] = tool_profiles
        config.setdefault('tool_suites', [])
        
        with open(config_path, 'w') as f:
            json.dump(config, f, indent=2)

    def _add_custom_script(self, listbox):
        """Add new custom script"""
        dialog = tk.Toplevel(self)
        dialog.title("Add Custom Script")
        dialog.geometry("500x350")
        dialog.configure(bg='#1e1e1e')

        tk.Label(dialog, text="Add Custom Script", bg='#1e1e1e', fg='#4ec9b0',
                font=('Arial', 11, 'bold')).pack(pady=10)

        # Script name
        tk.Label(dialog, text="Script Name:", bg='#1e1e1e', fg='#d4d4d4').pack(anchor=tk.W, padx=20)
        name_var = tk.StringVar()
        tk.Entry(dialog, textvariable=name_var, width=40).pack(padx=20, pady=5)

        # Command/path
        tk.Label(dialog, text="Command (or path to script):", bg='#1e1e1e', fg='#d4d4d4').pack(anchor=tk.W, padx=20)
        cmd_var = tk.StringVar()
        tk.Entry(dialog, textvariable=cmd_var, width=40).pack(padx=20, pady=5)

        def browse_script():
            path = filedialog.askopenfilename(title="Select Script", filetypes=[("Python", "*.py"), ("All", "*.*")])
            if path:
                cmd_var.set(path)

        tk.Button(dialog, text="Browse", command=browse_script,
                 bg='#2d2d2d', fg='#d4d4d4').pack(pady=(0, 10))

        # Arguments template
        tk.Label(dialog, text="Arguments (use {target} for target file):", bg='#1e1e1e', fg='#d4d4d4').pack(anchor=tk.W, padx=20)
        args_var = tk.StringVar()
        tk.Entry(dialog, textvariable=args_var, width=40).pack(padx=20, pady=5)

        help_preview = scrolledtext.ScrolledText(dialog, height=6, bg='#101010', fg='#d4d4d4')
        help_preview.pack(fill=tk.X, padx=20, pady=(5, 0))
        help_preview.config(state=tk.DISABLED)

        def preview_help():
            script_path = cmd_var.get().strip()
            if not script_path:
                messagebox.showwarning("No Script", "Please enter a script path first.")
                return
            try:
                result = subprocess.run([sys.executable, script_path, '-h'], capture_output=True, text=True, timeout=10)
                help_preview.config(state=tk.NORMAL)
                help_preview.delete(1.0, tk.END)
                output = result.stdout or result.stderr or "No help output."
                help_preview.insert(tk.END, output)
                help_preview.config(state=tk.DISABLED)
            except Exception as exc:
                messagebox.showerror("Help Error", f"Failed to retrieve -h output:\n{exc}")

        tk.Button(dialog, text="Preview -h Output", command=preview_help,
                 bg='#2d2d2d', fg='#d4d4d4').pack(pady=5)

        # Description
        tk.Label(dialog, text="Description:", bg='#1e1e1e', fg='#d4d4d4').pack(anchor=tk.W, padx=20)
        desc_var = tk.StringVar()
        tk.Entry(dialog, textvariable=desc_var, width=40).pack(padx=20, pady=5)

        def save_script():
            # Save to config
            scripts = self._load_custom_scripts()
            entry = {
                "name": name_var.get(),
                "command": cmd_var.get(),
                "args": args_var.get(),
                "description": desc_var.get()
            }
            scripts.append(entry)

            self._save_custom_scripts(scripts)
            self._sync_script_with_debug_toolkit(entry)

            if hasattr(listbox, 'refresh'):
                listbox.refresh()
            else:
                listbox.insert(tk.END, f"[Local] {name_var.get()} → {cmd_var.get()}")
            dialog.destroy()
            self.status_var.set(f"✨ Added custom script: {name_var.get()}")

        tk.Button(dialog, text="Add Script", command=save_script, bg='#4ec9b0',
                 fg='#000000', width=15).pack(pady=20)

    def _edit_custom_script(self, listbox):
        """Edit selected custom script"""
        selection = listbox.curselection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a script to edit")
            return
        records = getattr(listbox, 'records', [])
        idx = selection[0]
        if idx >= len(records):
            return
        record = records[idx]
        if record.get('source') != 'local':
            messagebox.showinfo("External Script", "This script is managed via the Babel GUI Debug Toolkit. Edit it there.")
            return

        script = record['entry']
        scripts = self._load_custom_scripts()
        script_idx = next((i for i, s in enumerate(scripts) if s.get('name') == script.get('name')), None)
        if script_idx is None:
            messagebox.showerror("Not Found", "Could not locate script in local config.")
            return

        dialog = tk.Toplevel(self)
        dialog.title("Edit Custom Script")
        dialog.geometry("500x360")
        dialog.configure(bg='#1e1e1e')

        tk.Label(dialog, text="Edit Custom Script", bg='#1e1e1e', fg='#4ec9b0',
                font=('Arial', 11, 'bold')).pack(pady=10)

        name_var = tk.StringVar(value=script.get('name', ''))
        cmd_var = tk.StringVar(value=script.get('command', ''))
        args_var = tk.StringVar(value=script.get('args', ''))
        desc_var = tk.StringVar(value=script.get('description', ''))

        tk.Label(dialog, text="Script Name:", bg='#1e1e1e', fg='#d4d4d4').pack(anchor=tk.W, padx=20)
        tk.Entry(dialog, textvariable=name_var, width=40).pack(padx=20, pady=5)

        tk.Label(dialog, text="Command:", bg='#1e1e1e', fg='#d4d4d4').pack(anchor=tk.W, padx=20)
        tk.Entry(dialog, textvariable=cmd_var, width=40).pack(padx=20, pady=5)

        tk.Label(dialog, text="Arguments:", bg='#1e1e1e', fg='#d4d4d4').pack(anchor=tk.W, padx=20)
        tk.Entry(dialog, textvariable=args_var, width=40).pack(padx=20, pady=5)

        tk.Label(dialog, text="Description:", bg='#1e1e1e', fg='#d4d4d4').pack(anchor=tk.W, padx=20)
        tk.Entry(dialog, textvariable=desc_var, width=40).pack(padx=20, pady=5)

        def save_edits():
            scripts[script_idx] = {
                'name': name_var.get(),
                'command': cmd_var.get(),
                'args': args_var.get(),
                'description': desc_var.get()
            }
            self._save_custom_scripts(scripts)
            self._sync_script_with_debug_toolkit(scripts[script_idx])
            if hasattr(listbox, 'refresh'):
                listbox.refresh()
            dialog.destroy()
            self.status_var.set(f"✏️ Updated script: {name_var.get()}")

        tk.Button(dialog, text="Save", command=save_edits,
                 bg='#4ec9b0', fg='#000000', width=15).pack(pady=15)

    def _delete_custom_script(self, listbox):
        """Delete selected custom script"""
        selection = listbox.curselection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a script to delete")
            return
        records = getattr(listbox, 'records', [])
        idx = selection[0]
        if idx >= len(records):
            return
        record = records[idx]
        if record.get('source') != 'local':
            messagebox.showinfo("External Script", "Delete external scripts via the Babel GUI Debug Toolkit.")
            return

        if messagebox.askyesno("Confirm Delete", "Delete this custom script?"):
            scripts = self._load_custom_scripts()
            scripts = [s for s in scripts if s.get('name') != record['entry'].get('name')]
            self._save_custom_scripts(scripts)
            if hasattr(listbox, 'refresh'):
                listbox.refresh()
            self.status_var.set("🗑️ Deleted custom script")

    def _send_script_to_workflow(self, listbox):
        """Add custom script to workflow actions"""
        selection = listbox.curselection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a script to add to workflow")
            return
        records = getattr(listbox, 'records', [])
        idx = selection[0]
        if idx >= len(records):
            return
        record = records[idx]
        entry = record['entry']
        category = record.get('entry', {}).get('category')
        if record.get('source') == 'local':
            action = {
                "name": entry.get('name', 'Custom Script'),
                "type": "custom",
                "source": "custom_scripts",
                "command": entry.get('command'),
                "args": entry.get('args', ''),
                "target_mode": "auto",
                "output_to": "results",
                "expectations": "custom_script"
            }
        else:
            entry_type = 'debug_suite' if category == 'suite' else 'debug_script'
            action = {
                "name": entry.get('name', 'Debug Script'),
                "type": entry_type,
                "source": entry.get('command'),
                "command": entry.get('command'),
                "args": self._load_debug_tool_profiles().get('tool_profiles', {}).get(entry.get('command'), ''),
                "target_mode": "auto",
                "output_to": "results",
                "expectations": "custom_tool"
            }

        for i, slot in enumerate(self.workflow_actions):
            if slot['type'] == 'placeholder':
                self.workflow_actions[i] = action
                self.status_var.set(f"📤 Added '{action['name']}' to workflow actions")
                messagebox.showinfo("Added", f"'{action['name']}' added to workflow position {i+1}")
                return

        messagebox.showwarning("No Slots", "All 8 workflow slots are filled. Remove a workflow action first.")

    def _has_placeholder_slot(self) -> bool:
        return any(action.get('type') == 'placeholder' for action in self.workflow_actions)

    def _quick_add_workflow_tool(self, profile_override: Optional[str] = None):
        """Guided picker to add toolkit/default/custom actions into workflow buttons"""

        quick_add = tk.Toplevel(self)
        quick_add.title("Add Workflow Action")
        quick_add.geometry("780x460")
        quick_add.configure(bg='#1e1e1e')
        quick_add.transient(self)
        quick_add.attributes('-topmost', True)

        x = self.winfo_x() + 120
        y = self.winfo_y() + 120
        quick_add.geometry(f"+{x}+{y}")

        tk.Label(
            quick_add,
            text="Choose an action, toolkit tool, or custom script to fill slots. Switch profiles or inspect lineage before committing.",
            bg='#1e1e1e',
            fg='#888888',
            font=('Arial', 9),
            wraplength=720
        ).pack(pady=10, padx=20)

        profile_frame = tk.Frame(quick_add, bg='#1e1e1e')
        profile_frame.pack(fill=tk.X, padx=20)

        tk.Label(profile_frame, text="Profile:", bg='#1e1e1e', fg='#d4d4d4').pack(side=tk.LEFT)
        profile_default = profile_override or self.active_profile or "Default Profile"
        profile_names = self._load_profile_names()
        if profile_default not in profile_names:
            profile_names.append(profile_default)
        profile_var = tk.StringVar(value=profile_default)
        profile_menu = ttk.Combobox(
            profile_frame,
            textvariable=profile_var,
            values=profile_names,
            state='readonly',
            width=24
        )
        profile_menu.pack(side=tk.LEFT, padx=10)

        category_frame = tk.Frame(quick_add, bg='#1e1e1e')
        category_frame.pack(fill=tk.X, padx=20, pady=(5, 0))

        tk.Label(category_frame, text="Category:", bg='#1e1e1e', fg='#d4d4d4').pack(side=tk.LEFT)
        categories = [
            "Default Workflows",
            "Engineer's Toolkit",
            "Custom Scripts",
            "Debug Toolkit",
            "Scope Analyzer"
        ]
        category_var = tk.StringVar(value=categories[0])
        category_menu = ttk.Combobox(category_frame, textvariable=category_var,
                                     values=categories, state='readonly')
        category_menu.pack(side=tk.LEFT, padx=10)

        lists_container = tk.Frame(quick_add, bg='#1e1e1e')
        lists_container.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        tools_frame = tk.Frame(lists_container, bg='#1e1e1e')
        tools_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        tk.Label(tools_frame, text="Available Tools:", bg='#1e1e1e',
                fg='#4ec9b0', font=('Arial', 9, 'bold')).pack(anchor=tk.W, pady=(0, 5))

        tools_listbox = tk.Listbox(
            tools_frame,
            bg='#2d2d2d',
            fg='#d4d4d4',
            selectbackground='#4ec9b0',
            selectforeground='#000000',
            font=('Monospace', 9),
            activestyle='none'
        )
        tools_listbox.pack(fill=tk.BOTH, expand=True)

        current_frame = tk.Frame(lists_container, bg='#1e1e1e')
        current_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(20, 0))

        tk.Label(current_frame, text="Current Workflow (Slot Order)", bg='#1e1e1e',
                 fg='#4ec9b0', font=('Arial', 9, 'bold')).pack(anchor=tk.W, pady=(0, 5))

        current_listbox = tk.Listbox(
            current_frame,
            bg='#2d2d2d',
            fg='#d4d4d4',
            selectbackground='#4ec9b0',
            selectforeground='#000000',
            font=('Monospace', 9),
            activestyle='none',
            height=12
        )
        current_listbox.pack(fill=tk.BOTH, expand=True)

        # RIGHT: Spellbook / Info / Args (Enhanced UX)
        self.spellbook_notebook = ttk.Notebook(lists_container, width=320)
        self.spellbook_notebook.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Tab 1: Profiled Args
        args_tab = tk.Frame(self.spellbook_notebook, bg='#1e1e1e')
        self.spellbook_notebook.add(args_tab, text="🪄 Args")
        
        self.args_scroll = tk.Frame(args_tab, bg='#1e1e1e')
        self.args_scroll.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.arg_vars = {} # Store checkbox vars for args

        # Tab 2: Sequence Builder (Spellbook)
        sequence_tab = tk.Frame(self.spellbook_notebook, bg='#1e1e1e')
        self.spellbook_notebook.add(sequence_tab, text="📜 Spellbook")
        
        self.sequence_list = tk.Listbox(sequence_tab, bg='#151515', fg='#d4d4d4', height=8)
        self.sequence_list.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        seq_btns = tk.Frame(sequence_tab, bg='#1e1e1e')
        seq_btns.pack(fill=tk.X)
        
        def add_to_seq():
            sel = tools_listbox.curselection()
            if not sel: return
            cat_items = category_items.get(category_var.get(), [])
            entry = cat_items[sel[0]]
            
            # Construct command with active args
            cmd = entry.get('command', '')
            active_args = [arg for arg, var in self.arg_vars.items() if var.get()]
            full_cmd = f"{cmd} {' '.join(active_args)}".strip()
            self.sequence_list.insert(tk.END, full_cmd)

        def clear_seq():
            self.sequence_list.delete(0, tk.END)

        tk.Button(seq_btns, text="Add to Combo", command=add_to_seq, bg='#2d7d46', fg='white').pack(side=tk.LEFT, padx=2)
        tk.Button(seq_btns, text="Clear", command=clear_seq, bg='#a54242', fg='white').pack(side=tk.LEFT, padx=2)

        # Tab 3: Help / Info
        info_tab = tk.Frame(self.spellbook_notebook, bg='#1e1e1e')
        self.spellbook_notebook.add(info_tab, text="❓ Help")

        info_text = scrolledtext.ScrolledText(
            info_tab,
            height=12,
            bg='#151515',
            fg='#d4d4d4',
            font=('Monospace', 9)
        )
        info_text.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)

        def refresh_current_list():
            current_listbox.delete(0, tk.END)
            for idx, action in enumerate(self.workflow_actions):
                name = action.get('name', 'Empty Slot')
                if action.get('type') == 'placeholder':
                    name = "[Empty Slot]"
                current_listbox.insert(tk.END, f"Slot {idx + 1}: {name}")

        def move_current(delta):
            selection = current_listbox.curselection()
            if not selection:
                return
            idx = selection[0]
            new_idx = idx + delta
            if new_idx < 0 or new_idx >= len(self.workflow_actions):
                return
            self.workflow_actions[idx], self.workflow_actions[new_idx] = (
                self.workflow_actions[new_idx], self.workflow_actions[idx]
            )
            refresh_current_list()
            current_listbox.selection_set(new_idx)
            self._build_workflow_buttons()
            self._save_current_profile()

        def remove_current_slot():
            selection = current_listbox.curselection()
            if not selection:
                return
            idx = selection[0]
            self.workflow_actions[idx] = self._placeholder_action()
            refresh_current_list()
            self._build_workflow_buttons()
            self._save_current_profile()

        current_btns = tk.Frame(current_frame, bg='#1e1e1e')
        current_btns.pack(fill=tk.X, pady=5)

        tk.Button(current_btns, text="▲", command=lambda: move_current(-1),
                 bg='#3d3d3d', fg='#d4d4d4', width=4).pack(side=tk.LEFT, padx=2)
        tk.Button(current_btns, text="▼", command=lambda: move_current(1),
                 bg='#3d3d3d', fg='#d4d4d4', width=4).pack(side=tk.LEFT, padx=2)
        tk.Button(current_btns, text="Remove", command=remove_current_slot,
                 bg='#c42b1c', fg='white', width=10).pack(side=tk.LEFT, padx=5)

        refresh_current_list()

        def update_info_panel(entry: Optional[Dict[str, Any]] = None):
            info_text.config(state=tk.NORMAL)
            info_text.delete('1.0', tk.END)
            
            # Clear args tab
            for w in self.args_scroll.winfo_children(): w.destroy()
            self.arg_vars = {}

            if not entry:
                info_text.insert(tk.END, "Select an entry to view metadata, arguments, and lineage.")
                info_text.config(state=tk.DISABLED)
                return

            # Update Metadata Info
            lines = [
                f"Name: {entry.get('name', 'Unnamed')}",
                f"Type: {entry.get('type', 'custom')}",
                f"Source: {entry.get('source', 'n/a')}",
            ]
            if entry.get('command'):
                lines.append(f"Command: {entry.get('command')}")
            if entry.get('args'):
                lines.append(f"Args: {entry.get('args')}")
            info_text.insert(tk.END, "\n".join(lines))
            info_text.config(state=tk.DISABLED)

            # Update Profiled Args Tab if it's a Babel tool
            if entry.get('expectations', '').startswith('babel_'):
                # Try to find tool in consolidated menu for args
                menu_path = self.version_root / "inventory" / "consolidated_menu.json"
                if menu_path.exists():
                    with open(menu_path) as f:
                        menu = json.load(f)
                    tool_data = next((t for t in menu.get('tools', []) if t.get('name') == entry.get('name')), None)
                    if tool_data and tool_data.get('arguments'):
                        tk.Label(self.args_scroll, text="Profiled Arguments:", bg='#1e1e1e', fg='#4ec9b0').pack(anchor=tk.W)
                        for arg in tool_data['arguments']:
                            var = tk.BooleanVar()
                            self.arg_vars[arg['name']] = var
                            tk.Checkbutton(self.args_scroll, text=f"{arg['name']} ({arg.get('help', 'No help')})", 
                                          variable=var, bg='#1e1e1e', fg='#d4d4d4', selectcolor='#2a2a2a').pack(anchor=tk.W)

        def apply_profile_selection(*_):
            target_profile = profile_var.get()
            if target_profile and self._apply_profile_config(target_profile):
                refresh_current_list()
                if hasattr(self, 'profile_indicator_var'):
                    self.profile_indicator_var.set(target_profile)

        def on_tool_select(*_):
            current_items = category_items.get(category_var.get(), [])
            selection = tools_listbox.curselection()
            if not selection or selection[0] >= len(current_items):
                update_info_panel(None)
                return
            entry = current_items[selection[0]]
            update_info_panel(entry)

        category_items = {
            "Babel Tools": self._build_babel_tool_entries(),
            "Default Workflows": self._build_default_workflow_entries(),
            "Engineer's Toolkit": self._build_toolkit_entries(),
            "Custom Scripts": self._build_custom_script_entries(),
            "Debug Toolkit": self._build_debug_tool_entries(),
            "Scope Analyzer": self._build_scope_entries(),
        }

        def refresh_list(*_):
            tools_listbox.delete(0, tk.END)
            current_items = category_items.get(category_var.get(), [])
            if not current_items:
                tools_listbox.insert(tk.END, "(No entries available)")
                tools_listbox.config(state=tk.DISABLED)
            else:
                tools_listbox.config(state=tk.NORMAL)
                for entry in current_items:
                    tools_listbox.insert(tk.END, entry.get('display', entry['name']))
            update_info_panel(None)

        profile_menu.bind('<<ComboboxSelected>>', apply_profile_selection)
        category_menu.bind('<<ComboboxSelected>>', lambda *_: (refresh_list(), on_tool_select()))
        tools_listbox.bind('<<ListboxSelect>>', on_tool_select)
        refresh_list()
        update_info_panel(None)

        def add_selected_tool():
            # Check if Spellbook has items (Combo Action)
            seq_items = self.sequence_list.get(0, tk.END)
            if seq_items:
                # Build combo action
                combo_cmd = " && ".join(seq_items)
                entry = {
                    "name": "Combo Action", # User can rename later
                    "type": "custom",
                    "command": combo_cmd,
                    "source": "spellbook",
                    "target_mode": "auto",
                    "output_to": "results",
                    "expectations": "combo"
                }
            else:
                # Single tool mode
                current_items = category_items.get(category_var.get(), [])
                if not current_items or tools_listbox.cget('state') == tk.DISABLED:
                    return
                selection = tools_listbox.curselection()
                if not selection:
                    messagebox.showwarning("No Selection", "Select an entry or build a sequence.")
                    return
                entry = current_items[selection[0]]
                
                # Apply active args if any
                active_args = [arg for arg, var in self.arg_vars.items() if var.get()]
                if active_args:
                    entry['args'] = f"{entry.get('args', '')} {' '.join(active_args)}".strip()
                    entry['command'] = f"{entry.get('command', '')} {' '.join(active_args)}".strip()

            if not self._has_placeholder_slot():
                messagebox.showinfo("Slots Full", "Workflow slots are filled. Remove a slot first.")
                return
            
            if self._assign_workflow_slot(entry):
                self._save_current_profile()
                self._build_workflow_buttons()
                refresh_current_list()
                self.status_var.set(f"✨ Added '{entry['name']}' to workflow")
                quick_add.destroy()

        # Action buttons at bottom
        action_frame = tk.Frame(quick_add, bg='#1e1e1e')
        action_frame.pack(fill=tk.X, padx=20, pady=10)
        tk.Button(action_frame, text="Add to Workflow", command=add_selected_tool,
                  bg='#2d7d46', fg='white', font=('Arial', 10, 'bold'), width=20).pack(side=tk.LEFT, padx=5)
        tk.Button(action_frame, text="Close", command=quick_add.destroy,
                  bg='#3d3d3d', fg='#d4d4d4', width=10).pack(side=tk.RIGHT, padx=5)

    def _build_babel_tool_entries(self) -> List[Dict[str, Any]]:
        """Load tools from Babel consolidated menu"""
        entries = []
        menu_path = self.version_root / "inventory" / "consolidated_menu.json"
        
        if menu_path.exists():
            try:
                with open(menu_path, 'r') as f:
                    menu = json.load(f)
                
                for tool in menu.get('tools', []):
                    name = tool.get('name', 'Unknown')
                    path = tool.get('path', '') or tool.get('command', '')
                    args = tool.get('default_args', '')
                    cat = tool.get('category', 'tool')
                    
                    # Clean up path for display
                    if str(self.babel_root) in path:
                        display_path = path.replace(str(self.babel_root), "{babel_root}")
                    else:
                        display_path = path

                    entries.append({
                        "name": name,
                        "type": "custom",
                        "source": path,
                        "command": path,
                        "args": args,
                        "target_mode": "auto",
                        "output_to": "results",
                        "expectations": f"babel_{cat}",
                        "display": f"[Babel] {name} ({cat})",
                        "location": f"python3 {display_path} {args}".strip(),
                    })
            except Exception as e:
                self.engine.log_debug(f"Error loading babel tools: {e}", "ERROR")
        
        if not entries:
            entries.append({
                "name": "No Babel Tools Found",
                "display": "[Error] consolidated_menu.json missing",
                "type": "placeholder"
            })
            
        return entries

    def _launch_scope_analyzer(self):
        """Launch Scope Analyzer utility"""
        scope_path = self._scope_script_path()
        if not scope_path:
            messagebox.showerror("Scope Analyzer", "scope.py not found in Modules/action_panel/scope")
            return

        target = self.target_var.get().strip()
        cmd = [sys.executable, str(scope_path), '--scope']
        if target:
            target_path = Path(target).expanduser()
            if target_path.is_file():
                cmd.extend(['--copy', str(target_path)])

        try:
            subprocess.Popen(cmd, cwd=str(scope_path.parent))
            self.status_var.set("🔭 Scope Analyzer launched")
        except Exception as exc:
            messagebox.showerror("Scope Analyzer", f"Failed to launch scope.py:\n{exc}")

    def _build_default_workflow_entries(self) -> List[Dict[str, Any]]:
        entries = []
        for action in self._default_workflow_actions():
            location = self.tool_locations.get(action['name']) or action.get('source', '')
            entries.append({
                "name": action['name'],
                "type": action.get('type', 'builtin'),
                "source": action.get('source', ''),
                "target_mode": action.get('target_mode', 'auto'),
                "output_to": action.get('output_to', 'results'),
                "expectations": action.get('expectations', ''),
                "display": f"[Workflow] {action['name']}",
                "location": location,
            })
        return entries

    def _build_toolkit_entries(self) -> List[Dict[str, Any]]:
        entries: List[Dict[str, Any]] = []
        order = self.toolkit_order or self._default_toolkit_order()
        for tool in order:
            location = self.tool_locations.get(tool['name']) or tool.get('source', '')
            entries.append({
                "name": tool['name'],
                "type": "toolkit",
                "source": tool.get('source', ''),
                "target_mode": "auto",
                "output_to": "results",
                "expectations": "toolkit_check",
                "display": f"[Toolkit] {tool['name']} ({tool.get('func', '')})",
                "location": location,
            })
        return entries

    def _build_custom_script_entries(self) -> List[Dict[str, Any]]:
        entries: List[Dict[str, Any]] = []
        for script in self._load_custom_scripts():
            entries.append({
                "name": script.get('name', 'Custom Script'),
                "type": "custom",
                "source": script.get('command', ''),
                "command": script.get('command', ''),
                "args": script.get('args', ''),
                "target_mode": "auto",
                "output_to": "results",
                "expectations": "custom_script",
                "display": f"[Custom] {script.get('name', 'Custom Script')}",
                "location": script.get('command', ''),
            })
        return entries

    def _build_scope_entries(self) -> List[Dict[str, Any]]:
        scope_path = self._scope_script_path()
        if not scope_path:
            return []

        scope_entries: List[Dict[str, Any]] = []
        scope_str = str(scope_path)
        scope_entries.append({
            "name": "Scope Analyzer",
            "type": "debug_suite",
            "source": scope_str,
            "command": scope_str,
            "args": "--scope",
            "target_mode": "auto",
            "output_to": "traceback",
            "expectations": "scope_inspect",
            "display": "[Scope] Analyzer (--scope)",
            "location": scope_str,
        })
        scope_entries.append({
            "name": "Scope Monitor",
            "type": "debug_suite",
            "source": scope_str,
            "command": scope_str,
            "args": "--monitor",
            "target_mode": "auto",
            "output_to": "traceback",
            "expectations": "scope_monitor",
            "display": "[Scope] Monitor (--monitor)",
            "location": scope_str,
        })
        return scope_entries

    def _build_debug_tool_entries(self) -> List[Dict[str, Any]]:
        entries: List[Dict[str, Any]] = []
        profile_data = self._load_debug_tool_profiles()
        suites = profile_data.get('tool_suites', [])
        debug_scripts = profile_data.get('debug_scripts', [])
        tool_profiles = profile_data.get('tool_profiles', {})

        for suite_path in suites:
            if self._is_scope_path(suite_path):
                continue
            display_name = Path(suite_path).name
            args_str = tool_profiles.get(suite_path, '')
            entries.append({
                "name": display_name,
                "type": "debug_suite",
                "source": suite_path,
                "command": suite_path,
                "args": args_str,
                "target_mode": "auto",
                "output_to": "results",
                "expectations": "custom_tool",
                "display": f"[Suite] {display_name}",
                "location": suite_path,
            })

        for script_path in debug_scripts:
            display_name = Path(script_path).name
            args_str = tool_profiles.get(script_path, '')
            entries.append({
                "name": display_name,
                "type": "debug_script",
                "source": script_path,
                "command": script_path,
                "args": args_str,
                "target_mode": "auto",
                "output_to": "results",
                "expectations": "custom_tool",
                "display": f"[Script] {display_name}",
                "location": script_path,
            })

        return entries

    def _create_onboarding_queue_tab(self, notebook):
        """TAB 6: Review and onboard discovered actions from prober manifest"""
        queue_tab = tk.Frame(notebook, bg='#1e1e1e')
        notebook.add(queue_tab, text="📥 On-boarding Queue")

        tk.Label(
            queue_tab,
            text="Review tools discovered by the prober. Select an action and click 'Onboard' to add it to the active profile.",
            bg='#1e1e1e',
            fg='#888888',
            font=('Arial', 9),
            wraplength=780,
            justify=tk.LEFT
        ).pack(pady=10, padx=10)

        # Queue List
        tree_frame = tk.Frame(queue_tab, bg='#1e1e1e')
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        columns = ('Name', 'Source', 'Target Tab', 'Description')
        queue_tree = ttk.Treeview(tree_frame, columns=columns, show='headings', height=12)
        for col in columns:
            queue_tree.heading(col, text=col)
            queue_tree.column(col, width=120 if col in ['Name', 'Target Tab'] else 250)
        
        queue_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=queue_tree.yview)
        queue_tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.draft_actions_store = {}

        def refresh_queue():
            for item in queue_tree.get_children():
                queue_tree.delete(item)
            
            # Load from .docv2_workspace/draft_onboarding_actions.json
            draft_file = self.repo_root / ".docv2_workspace" / "draft_onboarding_actions.json"
            if draft_file.exists():
                try:
                    with open(draft_file, 'r') as f:
                        data = json.load(f)
                        self.draft_actions_store = data
                        for group_key, group_data in data.items():
                            for action in group_data.get('draft_actions', []):
                                queue_tree.insert('', tk.END, values=(
                                    action['name'],
                                    Path(group_data['source_file']).name,
                                    action.get('affinity_tab', 'Grep'),
                                    action['expectations']
                                ), tags=(group_key, action['name']))
                except Exception as e:
                    self.engine.log_debug(f"Error loading draft actions: {e}", "ERROR")

        refresh_queue()

        def onboard_selected():
            selection = queue_tree.selection()
            if not selection: return
            
            item = queue_tree.item(selection[0])
            group_key, action_name = item['tags']
            
            # Find the full action data
            action_data = None
            for action in self.draft_actions_store.get(group_key, {}).get('draft_actions', []):
                if action['name'] == action_name:
                    action_data = action
                    break
            
            if action_data:
                # Ask target
                target = messagebox.askquestion("Onboard Target", 
                    f"Onboard '{action_name}' to:\n\n'Yes' - Active Profile\n'No' - Create New Version Branch",
                    icon='question')
                
                if target == 'yes':
                    # Add to current profile workflow_actions
                    if self._assign_workflow_slot(action_data):
                        self.status_var.set(f"📥 Onboarded: {action_name}")
                        messagebox.showinfo("Onboarded", f"Successfully added '{action_name}' to your active profile.")
                        self._build_workflow_buttons()
                    else:
                        messagebox.showwarning("Full", "No empty workflow slots available. Please edit your profile first.")
                else:
                    # Create new version
                    new_v_name = simpledialog.askstring("New Version", "Enter name for feature branch:", 
                                                       initialvalue=f"{self.active_version or 'v09x'}_{action_name.replace('[Auto] ', '').replace(' ', '_')}")
                    if new_v_name:
                        vm = VersionManager(os.path.join(self.project_root, "stable.json"))
                        if vm.create_new_grep_flight_version(self.active_version or "Grep_Flight_v2.0.0", new_v_name, f"Feature branch for {action_name}"):
                            # TODO: Logic to apply the action_data to the new version's profile
                            messagebox.showinfo("Success", f"Created branch '{new_v_name}'. Switch to it to finalize integration.")
                        else:
                            messagebox.showerror("Error", "Failed to create version branch.")

        # Buttons
        btn_frame = tk.Frame(queue_tab, bg='#1e1e1e')
        btn_frame.pack(fill=tk.X, padx=20, pady=10)

        tk.Button(btn_frame, text="📥 Onboard to Profile", command=onboard_selected,
                 bg='#4ec9b0', fg='#000000', width=20).pack(side=tk.LEFT, padx=5)
        
        tk.Button(btn_frame, text="🔄 Refresh Queue", command=refresh_queue,
                 bg='#2d2d2d', fg='#d4d4d4', width=15).pack(side=tk.RIGHT, padx=5)

    def _assign_workflow_slot(self, entry: Dict[str, Any]) -> bool:
        for i, action in enumerate(self.workflow_actions):
            if action.get('type') == 'placeholder':
                new_action = {
                    "name": entry['name'],
                    "type": entry.get('type', 'custom'),
                    "source": entry.get('source', ''),
                    "target_mode": entry.get('target_mode', 'auto'),
                    "output_to": entry.get('output_to', 'results'),
                    "expectations": entry.get('expectations', ''),
                }
                if 'command' in entry:
                    new_action['command'] = entry.get('command', '')
                if 'args' in entry:
                    new_action['args'] = entry.get('args', '')
                self.workflow_actions[i] = new_action
                self._register_tool_location(entry)
                log_to_traceback(
                    EventCategory.GREP_FLIGHT,
                    "workflow_slot_assigned",
                    {"tool": entry['name'], "slot": i + 1},
                    {"source": entry.get('source', ''), "category": entry.get('type', 'custom')}
                )
                return True
        return False

    def _register_tool_location(self, entry: Dict[str, Any]) -> None:
        location = entry.get('location') or entry.get('source')
        if location:
            self.tool_locations[entry['name']] = location

    def _get_stash_lineage_summary(self) -> str:
        """Summarize manifest activity from stash_script.py"""
        try:
            manifest_path = Path(__file__).resolve().parents[2] / 'quick_stash' / 'manifest.json'
        except IndexError:
            return "Stash manifest path unavailable."

        if not manifest_path.exists():
            return "No stash manifest found yet. Use stash_script.py to record lineage."

        try:
            with open(manifest_path, 'r') as f:
                entries = json.load(f)
        except Exception as exc:
            return f"Unable to read manifest: {exc}"

        if not isinstance(entries, list) or not entries:
            return "Manifest exists but contains no entries."

        latest = entries[-1]
        entry_type = latest.get('type', 'unknown')
        timestamp = latest.get('timestamp', 'unknown')
        total = len(entries)
        return f"Entries: {total}\nLast: {entry_type} @ {timestamp}"

    def _show_stash_help(self):
        """Display --help output from stash_script.py"""
        try:
            script_path = Path(__file__).resolve().parents[2] / 'quick_stash' / 'stash_script.py'
        except IndexError:
            messagebox.showerror("stash_script", "Unable to determine stash_script.py path")
            return

        if not script_path.exists():
            messagebox.showerror("stash_script", f"stash_script.py not found at {script_path}")
            return

        try:
            result = subprocess.run(
                [sys.executable, str(script_path), '-h'],
                capture_output=True,
                text=True,
                timeout=10
            )
            output = result.stdout or result.stderr or "No output"
            messagebox.showinfo("stash_script.py -h", output)
        except Exception as exc:
            messagebox.showerror("stash_script", f"Failed to query stash_script.py: {exc}")

    def _save_current_profile(self):
        """Save current workflow actions to active profile"""
        profile_name = None
        if self.current_profile_var is not None:
            profile_name = self.current_profile_var.get()
        if not profile_name:
            profile_name = self.active_profile or "Default Profile"
        
        profiles_file = self.config_dir / "workflow_profiles.json"

        # Load existing profiles
        if profiles_file.exists():
            with open(profiles_file, 'r') as f:
                data = json.load(f)
        else:
            data = {"profiles": {}}

        # Update profile
        if profile_name not in data['profiles']:
            data['profiles'][profile_name] = {}

        data['profiles'][profile_name]['workflow_actions'] = self.workflow_actions
        data['profiles'][profile_name]['last_updated'] = datetime.now().isoformat()
        data['profiles'][profile_name]['tool_locations'] = self.tool_locations
        data['default_profile'] = profile_name

        with open(profiles_file, 'w') as f:
            json.dump(data, f, indent=2)

        self.active_profile = profile_name
        self.engine.log_debug(f"Saved workflow to profile: {profile_name}", "INFO")

    def _get_toolkit_target(self) -> Optional[Path]:
        """Get target file/directory for toolkit operations"""
        target = self.target_var.get().strip()
        if not target:
            messagebox.showwarning("No Target", "Please specify a target file or directory in the Grep tab.")
            return None

        target_path = Path(target).expanduser()
        if not target_path.exists():
            messagebox.showerror("Target Not Found", f"Target does not exist: {target}")
            return None

        return target_path

    def _run_syntax_check(self):
        """Run syntax check on target"""
        target = self._get_toolkit_target()
        if not target:
            return

        self.status_var.set("Running syntax check...")
        self.engine.log_debug(f"Syntax check: {target}", "INFO")

        def worker():
            try:
                # Import and run check
                sys.path.insert(0, str(Path(__file__).parent.parent))
                from engineers_toolkit import QualityChecker

                checker = QualityChecker()
                if target.is_file():
                    result = checker.check_syntax(target)
                    self.after(0, lambda: self._display_toolkit_result("Syntax Check", result))
                else:
                    # Check all Python files in directory
                    py_files = list(target.rglob("*.py"))
                    results = [checker.check_syntax(f) for f in py_files[:10]]  # Limit to 10 files
                    self.after(0, lambda: self._display_toolkit_results("Syntax Check", results))

            except Exception as e:
                self.after(0, lambda: messagebox.showerror("Syntax Check Error", str(e)))
            finally:
                self.after(0, lambda: self.status_var.set("Ready"))

        threading.Thread(target=worker, daemon=True).start()

    def _run_indentation_check(self):
        """Run indentation check on target"""
        target = self._get_toolkit_target()
        if not target:
            return

        self.status_var.set("Checking indentation...")

        def worker():
            try:
                sys.path.insert(0, str(Path(__file__).parent.parent))
                from engineers_toolkit import QualityChecker

                checker = QualityChecker()
                result = checker.check_indentation(target)
                self.after(0, lambda: self._display_toolkit_result("Indentation Check", result))
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("Indentation Check Error", str(e)))
            finally:
                self.after(0, lambda: self.status_var.set("Ready"))

        threading.Thread(target=worker, daemon=True).start()

    def _run_imports_check(self):
        """Run imports analysis on target"""
        target = self._get_toolkit_target()
        if not target:
            return

        self.status_var.set("Analyzing imports...")

        def worker():
            try:
                sys.path.insert(0, str(Path(__file__).parent.parent))
                from engineers_toolkit import QualityChecker

                checker = QualityChecker()
                result = checker.check_imports(target)
                self.after(0, lambda: self._display_toolkit_result("Imports Analysis", result))
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("Imports Check Error", str(e)))
            finally:
                self.after(0, lambda: self.status_var.set("Ready"))

        threading.Thread(target=worker, daemon=True).start()

    def _run_formatting_check(self):
        """Run formatting check (Black/Ruff)"""
        target = self._get_toolkit_target()
        if not target:
            return

        self.status_var.set("Checking formatting...")

        def worker():
            try:
                sys.path.insert(0, str(Path(__file__).parent.parent))
                from engineers_toolkit import QualityChecker

                checker = QualityChecker()
                result = checker.check_formatting(target)
                self.after(0, lambda: self._display_toolkit_result("Formatting Check", result))
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("Formatting Check Error", str(e)))
            finally:
                self.after(0, lambda: self.status_var.set("Ready"))

        threading.Thread(target=worker, daemon=True).start()

    def _run_linting_check(self):
        """Run linting check (Pyflakes/Ruff)"""
        target = self._get_toolkit_target()
        if not target:
            return

        self.status_var.set("Running linting...")

        def worker():
            try:
                sys.path.insert(0, str(Path(__file__).parent.parent))
                from engineers_toolkit import QualityChecker

                checker = QualityChecker()
                result = checker.check_linting(target)
                self.after(0, lambda: self._display_toolkit_result("Linting Check", result))
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("Linting Error", str(e)))
            finally:
                self.after(0, lambda: self.status_var.set("Ready"))

        threading.Thread(target=worker, daemon=True).start()

    def _run_call_changes_check(self):
        """Run call changes detection"""
        target = self._get_toolkit_target()
        if not target:
            return

        self.status_var.set("Detecting call changes...")
        messagebox.showinfo("Call Changes", "This check requires a previous version of the file. Feature coming soon.")
        self.status_var.set("Ready")

    def _run_all_checks(self):
        """Run all quality checks"""
        target = self._get_toolkit_target()
        if not target:
            return

        self.status_var.set("Running all checks...")

        def worker():
            try:
                sys.path.insert(0, str(Path(__file__).parent.parent))
                from engineers_toolkit import QualityChecker

                checker = QualityChecker()
                result = checker.run_all_checks(target)
                self.after(0, lambda: self._display_toolkit_result("All Checks", result))
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("All Checks Error", str(e)))
            finally:
                self.after(0, lambda: self.status_var.set("Ready"))

        threading.Thread(target=worker, daemon=True).start()

    def _run_auto_fix(self):
        """Run auto-fix on target"""
        target = self._get_toolkit_target()
        if not target:
            return

        response = messagebox.askyesno(
            "Auto-Fix Confirmation",
            f"This will automatically fix formatting and style issues in:\n{target}\n\nContinue?"
        )
        if not response:
            return

        self.status_var.set("Running auto-fix...")
        messagebox.showinfo("Auto-Fix", "Auto-fix integration coming soon. Will use Black/Ruff for formatting.")
        self.status_var.set("Ready")

    def _create_snapshot(self):
        """Create project snapshot"""
        target = self._get_toolkit_target()
        if not target:
            return

        self.status_var.set("Creating snapshot...")

        def worker():
            try:
                sys.path.insert(0, str(Path(__file__).parent.parent))
                from engineers_toolkit import ProjectSnapshot

                snapshot = ProjectSnapshot(target if target.is_dir() else target.parent)
                result = snapshot.create_snapshot(description="Manual snapshot from grep_flight")

                msg = f"Snapshot created: {result['snapshot_id']}\n\nFiles scanned: {len(result.get('files', []))}"
                self.after(0, lambda: messagebox.showinfo("Snapshot Created", msg))
                self.engine.log_debug(f"Snapshot created: {result['snapshot_id']}", "INFO")
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("Snapshot Error", str(e)))
            finally:
                self.after(0, lambda: self.status_var.set("Ready"))

        threading.Thread(target=worker, daemon=True).start()

    def _clean_project(self):
        """Clean build artifacts"""
        target = self._get_toolkit_target()
        if not target:
            return

        response = messagebox.askyesno(
            "Clean Project",
            f"Clean __pycache__, .pyc files, and build artifacts in:\n{target}\n\nContinue?"
        )
        if not response:
            return

        self.status_var.set("Cleaning project...")
        messagebox.showinfo("Clean", "Project cleaning integration coming soon.")
        self.status_var.set("Ready")

    def _display_toolkit_result(self, check_name: str, result: Dict):
        """Display toolkit check result in results area"""
        self.results_text.delete(1.0, tk.END)

        # Header
        self.results_text.insert(tk.END, f"{'='*60}\n", 'header')
        self.results_text.insert(tk.END, f"{check_name} Results\n", 'header')
        self.results_text.insert(tk.END, f"{'='*60}\n\n", 'header')

        # Status
        passed = result.get('passed', False)
        status_text = "✅ PASSED" if passed else "❌ FAILED"
        self.results_text.insert(tk.END, f"Status: {status_text}\n\n")

        # File
        if 'file' in result:
            self.results_text.insert(tk.END, f"File: {result['file']}\n\n")

        # Errors
        if 'errors' in result and result['errors']:
            self.results_text.insert(tk.END, "Errors:\n", 'header')
            for error in result['errors'][:10]:  # Limit to 10
                self.results_text.insert(tk.END, f"  • {error}\n")
            if len(result['errors']) > 10:
                self.results_text.insert(tk.END, f"\n  ... and {len(result['errors']) - 10} more\n")
            self.results_text.insert(tk.END, "\n")

        # Details
        if 'message' in result:
            self.results_text.insert(tk.END, f"{result['message']}\n\n")

        # --- Integrated PFC Viewer for comprehensive checks ---
        if check_name == "All Checks" and show_pfc_results:
            # Add overall_status if missing for the viewer
            if 'overall_status' not in result:
                result['overall_status'] = "Passed" if passed else "Failed"
            self.after(500, lambda: show_pfc_results(self, result, {"title": "Toolkit: All Checks"}))

        # Log to traceback
        log_to_traceback(EventCategory.PFC, check_name.lower().replace(' ', '_'),
                       {"file": result.get('file', 'unknown')},
                       {"passed": passed, "errors": len(result.get('errors', []))})

    def _display_toolkit_results(self, check_name: str, results: List[Dict]):
        """Display multiple toolkit results"""
        self.results_text.delete(1.0, tk.END)

        self.results_text.insert(tk.END, f"{check_name} - Multiple Files\n", 'header')
        self.results_text.insert(tk.END, f"{'='*60}\n\n")

        total = len(results)
        passed = sum(1 for r in results if r.get('passed', False))
        failed = total - passed

        self.results_text.insert(tk.END, f"Total: {total} | Passed: {passed} | Failed: {failed}\n\n")

        for result in results:
            status = "✅" if result.get('passed') else "❌"
            self.results_text.insert(tk.END, f"{status} {result.get('file', 'unknown')}\n")

    # Task List Methods
    def _on_plan_module_changed(self, event=None):
        """Handle plan module selection change"""
        self._update_invocation_preview()
        self.status_var.set(f"📦 Plan Module: {self.active_plan_module.get()}")
        log_to_traceback(EventCategory.SESSION, "plan_module_switch", 
                       {"module": self.active_plan_module.get()}, 
                       {"status": "active"})

    def _update_invocation_preview(self):
        """Update the command-line preview for the active module"""
        module = self.active_plan_module.get()

        if "Clip" in module:
            path = self.babel_root / "babel_data" / "inventory" / "action_panel" / "ag_forge" / "clip.py"
            if path.exists():
                cmd = f"python3 {path} --workflow [recipe] --execute"
            else:
                cmd = f"[Not Available] ag_forge/clip.py not found"
        elif "Guillm" in module:
            path = self.babel_root / "babel_data" / "inventory" / "action_panel" / "morph" / "guillm.py"
            if path.exists():
                cmd = f"python3 {path} --change --instructions [message]"
            else:
                cmd = f"[Not Available] morph/guillm.py not found"
        elif "Os_Toolkit" in module:
            path = self.babel_root / "Os_Toolkit.py"
            cmd = f"python3 {path} [query]"
        elif "Babel" in module:
            path = self.babel_root / "babel"
            cmd = f"{path} [command]"
        else:
            cmd = "N/A"

        self.invocation_preview.set(cmd)

    def _refresh_task_list(self, trigger_sync=False):
        """Refresh task list from Babel plans/todos.json

        Args:
            trigger_sync: If True, run todosync before refreshing
        """
        if not hasattr(self, 'task_listbox'):
            return

        # Optional: Trigger todosync first
        if trigger_sync:
            self._sync_todos()
            return  # _sync_todos will call refresh after sync

        self.engine.log_debug("Refreshing task list from Babel todos", "INFO")

        # Clear current list
        self.task_listbox.delete(0, tk.END)
        self.tasks_data = []

        # Determine tasks file
        # Babel todos are in plans/todos.json
        todos_file = self.babel_root / "plans" / "todos.json"
        
        if not todos_file.exists():
            self.task_listbox.insert(tk.END, "No todos.json found")
            self.engine.log_debug(f"Todos file not found: {todos_file}", "WARNING")
            return

        try:
            with open(todos_file, 'r') as f:
                todos = json.load(f)
                
            # Convert babel todos to grep_flight task format
            # Support both list and dict formats (Babel might change)
            todo_list = todos if isinstance(todos, list) else todos.get('todos', [])
            
            for todo in todo_list:
                # Todo format: {"id": "...", "description": "...", "status": "open", ...}
                status = todo.get("status", "open")
                mapped_status = "completed" if status == "done" else "pending"
                if status == "in_progress": mapped_status = "in_progress"
                
                task_data = {
                    "id": todo.get("id", "unknown"),
                    "title": todo.get("description", "Untitled"),
                    "type": todo.get("category", "task"),
                    "status": mapped_status,
                    "files": [], 
                    "original": todo
                }
                self.tasks_data.append(task_data)

            # Group todos by category
            plan_linked = []
            system_todos = []  # BUG tags, auto-improvements
            unknown = []

            for task in self.tasks_data:
                original = task.get('original', {})
                # Check if linked to a plan
                if original.get('plan_id') or original.get('project'):
                    plan_linked.append(task)
                # Check if system-generated (BUG, improvement suggestions)
                elif 'BUG' in str(original.get('id', '')) or 'SUGGEST' in str(original.get('category', '')):
                    system_todos.append(task)
                else:
                    unknown.append(task)

            # Clear and rebuild display with sections
            self.task_listbox.delete(0, tk.END)

            # Section: Plan-linked todos
            if plan_linked:
                self.task_listbox.insert(tk.END, f"═══ Plan-Linked ({len(plan_linked)}) ═══")
                for task in plan_linked:
                    plan_id = task['original'].get('plan_id', 'Unknown')
                    self.task_listbox.insert(tk.END, f"  [{task['status'][:4].upper()}] {task['title'][:70]} (Plan: {plan_id})")
                self.task_listbox.insert(tk.END, "")

            # Section: System todos (BUG tags, suggestions)
            if system_todos:
                self.task_listbox.insert(tk.END, f"═══ System ({len(system_todos)}) ═══")
                for task in system_todos:
                    self.task_listbox.insert(tk.END, f"  [{task['status'][:4].upper()}] {task['title'][:70]}")
                self.task_listbox.insert(tk.END, "")

            # Section: Unknown/unlinked
            if unknown:
                self.task_listbox.insert(tk.END, f"═══ Unknown ({len(unknown)}) ═══")
                for task in unknown[:20]:  # Limit to 20 for readability
                    self.task_listbox.insert(tk.END, f"  [{task['status'][:4].upper()}] {task['title'][:70]}")

            log_to_traceback(EventCategory.TASK, "refresh_task_list",
                           {"source": "babel_todos", "file": str(todos_file)},
                           {"count": len(self.tasks_data), "plan_linked": len(plan_linked),
                            "system": len(system_todos), "unknown": len(unknown)})

        except Exception as e:
            self.task_listbox.insert(tk.END, f"Error loading todos: {e}")
            self.engine.log_debug(f"Error loading todos: {e}", "ERROR")

    @ui_event_tracker("sync_todos")
    def _sync_todos(self):
        """Trigger Os_Toolkit todosync with project template extraction

        Logs all output to unified_traceback.log and displays in traceback UI
        for instant visual feedback and debugging.
        """
        try:
            # Step 1: Extract todos from current project template
            project_name = self.current_project.get()
            project_file = self.plans_dir / f"{project_name.replace(' ', '_')}.md"

            self.engine.log_debug("="*60, "INFO")
            self.engine.log_debug("🔄 TODO SYNC TRIGGERED", "INFO")
            self.engine.log_debug("="*60, "INFO")
            self._add_traceback("="*60, "INFO")
            self._add_traceback("🔄 TODO SYNC TRIGGERED", "INFO")
            self._add_traceback("="*60, "INFO")

            extracted_todos = []
            if project_file.exists():
                self._add_traceback(f"📂 Scanning project: {project_name}", "INFO")
                extracted_todos = self._extract_project_todos(project_file, project_name)
                if extracted_todos:
                    msg = f"✅ Extracted {len(extracted_todos)} todos from {project_file.name}"
                    self.engine.log_debug(msg, "INFO")
                    self._add_traceback(msg, "INFO")
                    for todo in extracted_todos:
                        todo_msg = f"   - {todo['title'][:60]}"
                        self.engine.log_debug(todo_msg, "INFO")
                        self._add_traceback(todo_msg, "INFO")
                else:
                    self._add_traceback(f"ℹ️  No todos found in {project_file.name}", "INFO")

            # Step 2: Append to plans/todos.json before sync
            if extracted_todos:
                self._add_traceback(f"📝 Adding {len(extracted_todos)} todos to plans/todos.json...", "INFO")
                self._append_todos_to_json(extracted_todos)

            # Step 3: Trigger Os_Toolkit sync_all_todos
            self._add_traceback("🔄 Running Os_Toolkit sync_all_todos...", "INFO")
            self.engine.log_debug("Executing: python3 Os_Toolkit.py actions --run sync_all_todos", "INFO")

            result = subprocess.run(
                ['python3', 'Os_Toolkit.py', 'actions', '--run', 'sync_all_todos'],
                cwd=str(self.babel_root),
                capture_output=True,
                text=True,
                timeout=30
            )

            # Parse and log output line by line to unified logger AND traceback UI
            self._add_traceback("─"*60, "INFO")
            self._add_traceback("📊 SYNC RESULTS:", "INFO")
            self._add_traceback("─"*60, "INFO")

            for line in result.stdout.split('\n'):
                line = line.strip()
                if line:
                    # Determine log level from content
                    level = "INFO"
                    if "ERROR" in line or "⚠️" in line:
                        level = "ERROR"
                    elif "Conflict" in line:
                        level = "WARNING"
                    elif "✅" in line or "[+]" in line:
                        level = "INFO"

                    # Log to unified logger
                    self.engine.log_debug(line, level)
                    # Show in traceback UI
                    self._add_traceback(line, level)

            if result.stderr:
                self._add_traceback("⚠️ STDERR:", "WARNING")
                for line in result.stderr.split('\n'):
                    if line.strip():
                        self.engine.log_debug(f"STDERR: {line}", "WARNING")
                        self._add_traceback(line, "WARNING")

            self._add_traceback("─"*60, "INFO")
            self._add_traceback(f"✅ Sync exit code: {result.returncode}", "INFO")
            self._add_traceback("─"*60, "INFO")

            # Also show summary in chat if available
            if hasattr(self, 'chat_messages'):
                self.chat_messages.config(state=tk.NORMAL)
                self.chat_messages.insert(tk.END, f"\n{'─'*50}\n")
                self.chat_messages.insert(tk.END, f"🔄 TODO SYNC COMPLETE\n")
                self.chat_messages.insert(tk.END, f"{'─'*50}\n")
                if extracted_todos:
                    self.chat_messages.insert(tk.END, f"✅ Extracted {len(extracted_todos)} from {project_name}\n")
                # Show first 500 chars of output
                summary_lines = [l for l in result.stdout.split('\n') if l.strip()][:10]
                self.chat_messages.insert(tk.END, '\n'.join(summary_lines) + "\n")
                self.chat_messages.insert(tk.END, f"\n💡 See Traceback (Ctrl+D) for full output\n")
                self.chat_messages.insert(tk.END, f"{'─'*50}\n\n")
                self.chat_messages.config(state=tk.DISABLED)

            # Step 4: Refresh task list
            self.engine.log_debug("Refreshing task list...", "INFO")
            self._add_traceback("🔄 Refreshing task list...", "INFO")
            self._refresh_task_list()

            # Store delta to manifest (future: could create sync_manifest.json)
            delta_info = {
                "timestamp": datetime.now().isoformat(),
                "project": project_name,
                "extracted": len(extracted_todos),
                "exit_code": result.returncode,
                "output_lines": len(result.stdout.split('\n'))
            }

            log_to_traceback(EventCategory.TASK, "sync_todos_complete",
                           {"project": project_name, "extracted": len(extracted_todos)},
                           delta_info)

            self.engine.log_debug("="*60, "INFO")
            self.engine.log_debug("✅ TODO SYNC FINISHED", "INFO")
            self.engine.log_debug("="*60, "INFO")
            self._add_traceback("="*60, "INFO")
            self._add_traceback("✅ TODO SYNC FINISHED - Check logs above ↑", "INFO")
            self._add_traceback("="*60, "INFO")

        except subprocess.TimeoutExpired:
            error_msg = "⏱️ TodoSync timed out (>30s)"
            self.engine.log_debug(error_msg, "ERROR")
            self._add_traceback(error_msg, "ERROR")
            log_to_traceback(EventCategory.ERROR, "sync_todos_timeout", {}, error=error_msg)

        except Exception as e:
            error_msg = f"Sync todos failed: {e}"
            self.engine.log_debug(error_msg, "ERROR")
            self._add_traceback(error_msg, "ERROR")
            self._add_traceback(f"Traceback: {str(e)}", "ERROR")
            log_to_traceback(EventCategory.ERROR, "sync_todos_failed", {}, error=str(e))

    def _extract_project_todos(self, project_file: Path, project_name: str) -> List[Dict]:
        """Extract todos from </Current_Todos>: ... <Current_Todos/> block"""
        todos = []

        try:
            with open(project_file, 'r') as f:
                content = f.read()

            # Find </Current_Todos>: ... <Current_Todos/> block
            start_marker = "</Current_Todos>:"
            end_marker = "<Current_Todos/>"

            start_idx = content.find(start_marker)
            if start_idx == -1:
                return todos

            start_idx += len(start_marker)
            end_idx = content.find(end_marker, start_idx)
            if end_idx == -1:
                return todos

            todos_block = content[start_idx:end_idx].strip()

            # Parse todo lines (format: - Description)
            import re
            from datetime import datetime

            for line in todos_block.split('\n'):
                line = line.strip()
                if line.startswith('-') and len(line) > 2:
                    description = line[1:].strip()
                    if description:
                        # Generate unique ID
                        todo_id = f"project_{project_name.replace(' ', '_').lower()}_{len(todos) + 1}"

                        todos.append({
                            'id': todo_id,
                            'title': description[:60],  # First 60 chars as title
                            'description': description,
                            'status': 'pending',
                            'project': project_name,
                            'project_file': str(project_file),
                            'created_at': datetime.now().isoformat(),
                            'source': 'project_template'
                        })

        except Exception as e:
            self.engine.log_debug(f"Error extracting project todos: {e}", "ERROR")

        return todos

    def _append_todos_to_json(self, new_todos: List[Dict]):
        """Append extracted todos to plans/todos.json"""
        todos_file = self.babel_root / "plans" / "todos.json"

        try:
            # Read existing
            existing = []
            if todos_file.exists():
                with open(todos_file, 'r') as f:
                    existing = json.load(f)

            # Get existing IDs
            existing_ids = {t.get('id') for t in existing}

            # Append only new todos
            added = 0
            for todo in new_todos:
                if todo['id'] not in existing_ids:
                    existing.append(todo)
                    added += 1

            # Write back
            if added > 0:
                with open(todos_file, 'w') as f:
                    json.dump(existing, f, indent=2)
                self.engine.log_debug(f"Added {added} new todos to todos.json", "INFO")

        except Exception as e:
            self.engine.log_debug(f"Error appending todos: {e}", "ERROR")

    @ui_event_tracker("set_project")
    def _set_project(self):
        """Open dialog to set active project"""
        # Create project selection popup
        popup = tk.Toplevel(self)
        popup.title("Set Active Project")
        popup.geometry("500x400")
        popup.configure(bg=self.config.BG_COLOR)

        tk.Label(popup, text="Select Active Project", bg=self.config.BG_COLOR,
                fg=self.config.FG_COLOR, font=('Arial', 12, 'bold')).pack(pady=10)

        # Project list
        projects = [
            "Error Handling & Logging",
            "Babel Core Integration",
            "Filesync Enhancements",
            "Grep Flight UX",
            "Os_Toolkit Profiling"
        ]

        listbox = tk.Listbox(popup, bg='#2a2a2a', fg=self.config.FG_COLOR,
                            selectbackground=self.config.ACCENT_COLOR,
                            font=('Arial', 10), height=len(projects))
        listbox.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        for proj in projects:
            listbox.insert(tk.END, proj)

        # Select current
        try:
            current_idx = projects.index(self.current_project.get())
            listbox.selection_set(current_idx)
        except ValueError:
            pass

        def on_select():
            selection = listbox.curselection()
            if selection:
                self.current_project.set(projects[selection[0]])
                popup.destroy()
                self._refresh_task_list()  # Refresh to show project-filtered todos

        # Button frame
        button_frame = tk.Frame(popup, bg=self.config.BG_COLOR)
        button_frame.pack(pady=10, fill=tk.X, padx=20)

        tk.Button(button_frame, text="New", command=lambda: self._new_project(popup),
                 bg='#2d4d3d', fg=self.config.FG_COLOR,
                 font=('Arial', 10), width=10).pack(side=tk.LEFT, padx=5)

        tk.Button(button_frame, text="View", command=lambda: self._view_project(popup),
                 bg='#4d3d2d', fg=self.config.FG_COLOR,
                 font=('Arial', 10), width=10).pack(side=tk.LEFT, padx=5)

        tk.Button(button_frame, text="Select", command=on_select,
                 bg=self.config.ACCENT_COLOR, fg='black',
                 font=('Arial', 10, 'bold'), width=10).pack(side=tk.RIGHT, padx=5)

    @ui_event_tracker("new_project")
    def _new_project(self, parent_popup):
        """Create new project from template"""
        # Template selection popup
        template_popup = tk.Toplevel(parent_popup)
        template_popup.title("Select Project Template")
        template_popup.geometry("600x500")
        template_popup.configure(bg=self.config.BG_COLOR)

        tk.Label(template_popup, text="Choose Project Template",
                bg=self.config.BG_COLOR, fg=self.config.FG_COLOR,
                font=('Arial', 12, 'bold')).pack(pady=10)

        # Templates directory
        templates_dir = self.babel_root / "babel_data" / "templates" / "project_templates"

        # List available templates
        template_frame = tk.Frame(template_popup, bg=self.config.BG_COLOR)
        template_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        # Template list with scrollbar
        scroll = tk.Scrollbar(template_frame)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)

        template_list = tk.Listbox(template_frame, bg='#2a2a2a',
                                   fg=self.config.FG_COLOR,
                                   selectbackground=self.config.ACCENT_COLOR,
                                   font=('Arial', 10), yscrollcommand=scroll.set)
        template_list.pack(fill=tk.BOTH, expand=True)
        scroll.config(command=template_list.yview)

        # Populate templates
        templates = []
        if templates_dir.exists():
            for template_file in templates_dir.glob("*.md"):
                templates.append(template_file)
                template_list.insert(tk.END, template_file.stem.replace('_', ' '))

        # Template preview area
        preview_frame = tk.LabelFrame(template_popup, text="Template Preview",
                                     bg=self.config.BG_COLOR, fg=self.config.FG_COLOR)
        preview_frame.pack(fill=tk.X, padx=20, pady=(0, 10))

        preview_text = tk.Text(preview_frame, bg='#2a2a2a', fg='#888888',
                              height=6, font=('Monospace', 8), wrap=tk.WORD)
        preview_text.pack(fill=tk.X, padx=5, pady=5)
        preview_text.config(state=tk.DISABLED)

        def on_template_select(event):
            selection = template_list.curselection()
            if selection and templates:
                template_file = templates[selection[0]]
                # Show preview
                with open(template_file, 'r') as f:
                    preview_content = f.read()[:300] + "..."
                preview_text.config(state=tk.NORMAL)
                preview_text.delete(1.0, tk.END)
                preview_text.insert(1.0, preview_content)
                preview_text.config(state=tk.DISABLED)

        template_list.bind('<<ListboxSelect>>', on_template_select)

        def create_from_template():
            selection = template_list.curselection()
            if not selection or not templates:
                return

            template_file = templates[selection[0]]

            # Prompt for project name
            name_popup = tk.Toplevel(template_popup)
            name_popup.title("New Project Name")
            name_popup.geometry("400x150")
            name_popup.configure(bg=self.config.BG_COLOR)

            tk.Label(name_popup, text="Enter Project Name:",
                    bg=self.config.BG_COLOR, fg=self.config.FG_COLOR,
                    font=('Arial', 10)).pack(pady=10)

            name_entry = tk.Entry(name_popup, bg='#2a2a2a', fg=self.config.FG_COLOR,
                                 font=('Arial', 10), width=40)
            name_entry.pack(pady=10)
            name_entry.focus()

            def on_create():
                project_name = name_entry.get().strip()
                if not project_name:
                    return

                # Create project file from template
                project_file = self.plans_dir / f"{project_name.replace(' ', '_')}.md"

                # Copy template
                with open(template_file, 'r') as src:
                    content = src.read()

                # Replace template tag with project name
                content = content.replace('</PROJECT_', f'</PROJECT_{project_name.upper().replace(" ", "_")}_')

                # Write project file
                with open(project_file, 'w') as dst:
                    dst.write(content)

                # Open in editor
                subprocess.Popen(['mousepad', str(project_file)])

                # Set as active project
                self.current_project.set(project_name)

                # Log event
                log_to_traceback(EventCategory.FILE, "new_project_created",
                               {"name": project_name, "template": template_file.stem},
                               {"file": str(project_file)})

                # Close popups
                name_popup.destroy()
                template_popup.destroy()
                parent_popup.destroy()

                # Refresh
                self._refresh_task_list()
                self._refresh_plan_list()

            tk.Button(name_popup, text="Create & Open", command=on_create,
                     bg=self.config.ACCENT_COLOR, fg='black',
                     font=('Arial', 10, 'bold')).pack(pady=10)

        tk.Button(template_popup, text="Use Template", command=create_from_template,
                 bg=self.config.ACCENT_COLOR, fg='black',
                 font=('Arial', 10, 'bold')).pack(pady=10)

    @ui_event_tracker("view_project")
    def _view_project(self, parent_popup):
        """View/edit existing project docs"""
        # Get current project
        project_name = self.current_project.get()

        # Look for project file
        project_file = self.plans_dir / f"{project_name.replace(' ', '_')}.md"

        if not project_file.exists():
            # Show file browser to select project doc
            from tkinter import filedialog
            project_file = filedialog.askopenfilename(
                title=f"Select {project_name} Document",
                initialdir=str(self.plans_dir),
                filetypes=[("Markdown", "*.md"), ("Text", "*.txt"), ("All", "*.*")]
            )
            if not project_file:
                return
            project_file = Path(project_file)

        # Open in editor
        try:
            subprocess.Popen(['mousepad', str(project_file)])
            log_to_traceback(EventCategory.FILE, "view_project",
                           {"project": project_name, "file": str(project_file)},
                           {"status": "opened"})
        except Exception as e:
            log_to_traceback(EventCategory.ERROR, "view_project",
                           {"project": project_name},
                           error=str(e))

    def _open_plans_in_editor(self):
        """Open plans directory in native editor"""
        try:
            subprocess.Popen([self.config.FILE_MANAGER, str(self.plans_dir)])
            log_to_traceback(EventCategory.FILE, "open_plans_directory",
                           {"path": str(self.plans_dir)},
                           {"status": "opened"})
        except Exception as e:
            log_to_traceback(EventCategory.ERROR, "open_plans_directory",
                           {"path": str(self.plans_dir)},
                           error=str(e))

    def _refresh_plan_list(self):
        """Refresh the list of available plan files"""
        if not hasattr(self, 'plan_listbox'):
            return

        self.plan_listbox.delete(0, tk.END)

        if not self.plans_dir.exists():
            self.plan_listbox.insert(tk.END, "Plans directory not found")
            return

        # Find all plan files (md, txt, json)
        plan_files = []
        for ext in ['*.md', '*.txt', '*.json']:
            plan_files.extend(self.plans_dir.glob(ext))

        # Exclude backup files
        plan_files = [f for f in plan_files if 'backup' not in f.name.lower()]

        if not plan_files:
            self.plan_listbox.insert(tk.END, "No plan files found")
            return

        # Sort by modification time (newest first)
        plan_files.sort(key=lambda f: f.stat().st_mtime, reverse=True)

        for plan_file in plan_files[:20]:  # Show latest 20
            # Format: filename (size, modified date)
            size = plan_file.stat().st_size
            mtime = datetime.fromtimestamp(plan_file.stat().st_mtime).strftime('%Y-%m-%d %H:%M')
            display = f"{plan_file.name} ({size}B, {mtime})"
            self.plan_listbox.insert(tk.END, display)

    def _open_selected_plan(self):
        """Open selected plan file in native editor"""
        selection = self.plan_listbox.curselection()
        if not selection:
            return

        # Extract filename from display string
        display_text = self.plan_listbox.get(selection[0])
        filename = display_text.split(' (')[0]
        plan_file = self.plans_dir / filename

        if not plan_file.exists():
            return

        try:
            # Use mousepad (native editor)
            subprocess.Popen(['mousepad', str(plan_file)])
            log_to_traceback(EventCategory.FILE, "open_plan_file",
                           {"file": str(plan_file)},
                           {"status": "opened"})
        except Exception as e:
            log_to_traceback(EventCategory.ERROR, "open_plan_file",
                           {"file": str(plan_file)},
                           error=str(e))

    def _refresh_template_list(self):
        """Refresh the list of available templates"""
        if not hasattr(self, 'template_listbox'):
            return

        self.template_listbox.delete(0, tk.END)

        templates_dir = self.babel_root / "babel_data" / "templates" / "project_templates"

        if not templates_dir.exists():
            self.template_listbox.insert(tk.END, "Templates directory not found")
            return

        # Find all template files
        templates = list(templates_dir.glob("*.md"))

        if not templates:
            self.template_listbox.insert(tk.END, "No templates found")
            return

        # Sort by name
        templates.sort(key=lambda f: f.stem)

        for template_file in templates:
            # Format: Template Name (size)
            size = template_file.stat().st_size
            display = f"{template_file.stem.replace('_', ' ')} ({size}B)"
            self.template_listbox.insert(tk.END, display)

    def _open_selected_template(self):
        """Open selected template file in native editor"""
        selection = self.template_listbox.curselection()
        if not selection:
            return

        templates_dir = self.babel_root / "babel_data" / "templates" / "project_templates"

        # Extract filename from display string
        display_text = self.template_listbox.get(selection[0])
        template_name = display_text.split(' (')[0].replace(' ', '_')
        template_file = templates_dir / f"{template_name}.md"

        if not template_file.exists():
            return

        try:
            subprocess.Popen(['mousepad', str(template_file)])
            log_to_traceback(EventCategory.FILE, "open_template_file",
                           {"file": str(template_file)},
                           {"status": "opened"})
        except Exception as e:
            log_to_traceback(EventCategory.ERROR, "open_template_file",
                           {"file": str(template_file)},
                           error=str(e))

        except Exception as e:
            self.engine.log_debug(f"Error refreshing task list: {e}", "ERROR")
            self.task_listbox.insert(tk.END, f"Error: {str(e)}")

    def _filter_tasks(self):
        """Filter tasks based on type and status"""
        if not hasattr(self, 'task_listbox'):
            return

        # Clear display
        self.task_listbox.delete(0, tk.END)

        # Get filter values
        type_filter = self.task_type_filter.get()
        status_filter = self.task_status_filter.get()

        # Filter tasks
        filtered_tasks = []
        for task in self.tasks_data:
            # Type filter
            if type_filter != "all" and task.get('type', '') != type_filter:
                continue

            # Status filter
            if status_filter != "all" and task.get('status', '') != status_filter:
                continue

            filtered_tasks.append(task)

        # Display filtered tasks
        if not filtered_tasks:
            self.task_listbox.insert(tk.END, "No tasks match filters")
            return

        for task in filtered_tasks:
            task_id = task.get('id', 'unknown')
            task_title = task.get('title', 'Untitled')
            task_type = task.get('type', 'unknown')
            task_status = task.get('status', 'unknown')

            # Status icon
            status_icon = "⏳" if task_status == "pending" else "▶️" if task_status == "in_progress" else "✅"

            # Format: [icon] ID: Title (type)
            display_text = f"{status_icon} {task_id[:8]}: {task_title[:30]} ({task_type})"
            self.task_listbox.insert(tk.END, display_text)

        self.engine.log_debug(f"Filtered tasks: {len(filtered_tasks)}/{len(self.tasks_data)}", "INFO")

    def _on_task_double_click(self, event):
        """Handle double click on task - Populate Workspace"""
        selection = self.task_listbox.curselection()
        if not selection:
            return

        index = selection[0]
        if index < len(self.tasks_data):
            task = self.tasks_data[index]
            task_id = task.get('id', 'Unknown')
            title = task.get('title', 'Untitled')
            desc = task.get('description', '')
            
            # Update Header
            self.workspace_header_var.set(f"Task: {title} [{task_id}]")
            
            # Update Project Doc
            proj_id = task.get('project_id') or self.current_project.get() or '(None)'
            self.project_text.config(state='normal')
            self.project_text.delete("1.0", tk.END)
            
            if proj_id and proj_id != '(None)':
                filename = proj_id.replace(" & ", "_").replace(" ", "_")
                project_file = self.babel_root / "plans" / f"{filename}.md"
                
                # Try finding variants if exact match fails
                if not project_file.exists():
                    potential = list(self.babel_root.glob(f"plans/*{filename}*.md"))
                    if potential: project_file = potential[0]

                if project_file.exists():
                    try:
                        with open(project_file, 'r') as f:
                            self.project_text.insert("1.0", f.read())
                        self.engine.log_debug(f"Loaded project doc: {project_file.name}")
                    except Exception as e:
                        self.project_text.insert("1.0", f"Error reading {project_file.name}: {e}")
                else:
                    self.project_text.insert("1.0", f"No project document found for ID: {proj_id}\nExpected: plans/{filename}.md")
            else:
                self.project_text.insert("1.0", "Task has no project association.")
            
            # Update Editor
            self.editor_text.config(state='normal')
            self.editor_text.delete("1.0", tk.END)
            self.editor_text.insert("1.0", desc)
            
            # Update JSON
            self.json_text.config(state='normal')
            self.json_text.delete("1.0", tk.END)
            self.json_text.insert("1.0", json.dumps(task, indent=2))
            self.json_text.config(state='disabled')
            
            # --- Populate Attributes Tree ---
            if hasattr(self, 'attr_tree'):
                for item in self.attr_tree.get_children():
                    self.attr_tree.delete(item)
                
                # Metadata
                m_node = self.attr_tree.insert("", "end", text="Metadata", open=True)
                self.attr_tree.insert(m_node, "end", text="ID", values=(task_id,))
                self.attr_tree.insert(m_node, "end", text="Status", values=(task.get('status', 'unknown'),))
                
                # Routing
                r_node = self.attr_tree.insert("", "end", text="Routing", open=True)
                proj_id = task.get('project_id', '(None)')
                plan_id = task.get('plan_id', '(None)')
                
                self.attr_tree.insert(r_node, "end", text="Project ID", values=(proj_id,), 
                                     tags=('error' if proj_id == '(None)' else ''))
                self.attr_tree.insert(r_node, "end", text="Plan ID", values=(plan_id,),
                                     tags=('error' if plan_id == '(None)' else ''))
                
                # Features / Markers
                f_node = self.attr_tree.insert("", "end", text="Features", open=True)
                self.attr_tree.insert(f_node, "end", text="File Links", values=(len(task.get('files', [])),))
                self.attr_tree.insert(f_node, "end", text="Marks Found", values=(task.get('marks_count', 0),))
                
                # Diffs (Task 10)
                d_node = self.attr_tree.insert("", "end", text="Diffs", open=True)
                diffs = task.get('diffs', [])
                for i, diff in enumerate(diffs):
                    self.attr_tree.insert(d_node, "end", text=f"Diff {i+1}", values=(diff,))

                # Meta Links (Task 10)
                l_node = self.attr_tree.insert("", "end", text="Meta Links", open=True)
                links = task.get('meta_links', [])
                for i, link in enumerate(links):
                    self.attr_tree.insert(l_node, "end", text=f"Link {i+1}", values=(link,))

                # Log if routing lost
                if proj_id == '(None)' or plan_id == '(None)':
                    self._add_traceback(f"#[Mark:REFLOSS] Task {task_id} missing project/plan routing", "WARNING")
                    self._update_inspector(f"⚠️ ROUTING ERROR\nTask {task_id} is orphaned.\n\nMissing:\n" + 
                                         ("- Project Association\n" if proj_id == '(None)' else "") +
                                         ("- Plan Reference\n" if plan_id == '(None)' else "") +
                                         "\nClick 'Correct Routing' or edit JSON to fix.")
                else:
                    self._update_inspector(f"✅ Task Fully Routed\nProject: {proj_id}\nPlan: {plan_id}")

            # Switch to Editor tab
            self.workspace_notebook.select(1) # Index 1 is Editor

            # Log
            self.engine.log_debug(f"Task selected: {task_id}", "INFO")

    def _update_inspector(self, message):
        """Update the property inspector text"""
        if hasattr(self, 'inspector_msg'):
            self.inspector_msg.config(state='normal')
            self.inspector_msg.delete("1.0", tk.END)
            self.inspector_msg.insert(tk.END, message)
            self.inspector_msg.config(state='disabled')

    def _on_attr_select(self, event):
        """Handle selection in attribute tree"""
        item = self.attr_tree.focus()
        if not item: return
        
        name = self.attr_tree.item(item, "text")
        values = self.attr_tree.item(item, "values")
        val = values[0] if values else ""
        
        # If clicking Project ID or Plan ID, trigger correction dialog
        if name in ["Project ID", "Plan ID"]:
            self._show_routing_correction_dialog()
            return

        # Show detail in inspector
        self._update_inspector(f"Property: {name}\nValue: {val}\n\n" +
                             "Click 'Project ID' or 'Plan ID' in the list above to modify core routing attributes.")

    def _on_attr_right_click(self, event):
        """Show context menu for attribute tree"""
        item = self.attr_tree.identify_row(event.y)
        if not item: return
        self.attr_tree.selection_set(item)
        
        menu = tk.Menu(self, tearoff=0, bg='#2a2a2a', fg='#e0e0e0')
        menu.add_command(label="➕ Add Diff", command=self._add_diff_item)
        menu.add_command(label="🔗 Add Meta Link", command=self._add_meta_link_item)
        menu.add_separator()
        menu.add_command(label="🗑️ Remove Selected", command=self._remove_attr_item)
        menu.post(event.x_root, event.y_root)

    def _add_diff_item(self):
        """Add a new diff reference to the current task"""
        selection = self.task_listbox.curselection()
        if not selection: return
        task = self.tasks_data[selection[0]]
        
        new_diff = simpledialog.askstring("Add Diff", "Enter file path or #[Mark:###]:", parent=self)
        if new_diff:
            if 'diffs' not in task: task['diffs'] = []
            task['diffs'].append(new_diff)
            self._on_task_double_click(None) # Refresh view
            self._save_task_edits()

    def _add_meta_link_item(self):
        """Add a new meta link to the current task"""
        selection = self.task_listbox.curselection()
        if not selection: return
        task = self.tasks_data[selection[0]]
        
        new_link = simpledialog.askstring("Add Meta Link", "Enter provision/pkg/ref:", parent=self)
        if new_link:
            if 'meta_links' not in task: task['meta_links'] = []
            task['meta_links'].append(new_link)
            self._on_task_double_click(None) # Refresh view
            self._save_task_edits()

    def _remove_attr_item(self):
        """Remove selected item from diffs or meta_links"""
        item = self.attr_tree.focus()
        if not item: return
        
        selection = self.task_listbox.curselection()
        if not selection: return
        task = self.tasks_data[selection[0]]
        
        name = self.attr_tree.item(item, "text")
        values = self.attr_tree.item(item, "values")
        val = values[0] if values else ""
        
        parent = self.attr_tree.parent(item)
        parent_text = self.attr_tree.item(parent, "text")
        
        if parent_text == "Diffs":
            if val in task.get('diffs', []):
                task['diffs'].remove(val)
        elif parent_text == "Meta Links":
            if val in task.get('meta_links', []):
                task['meta_links'].remove(val)
        else:
            messagebox.showwarning("Remove", "Only items in Diffs or Meta Links can be removed here.")
            return

        self._on_task_double_click(None) # Refresh view
        self._save_task_edits()

    def _on_task_right_click(self, event):
        """Handle right-click on task - show context menu"""
        if not hasattr(self, 'task_listbox'):
            return

        # Get selected task
        # Note: curselection returns index in the listbox, need to map to data
        try:
            # Select the item under mouse if not already selected
            index = self.task_listbox.nearest(event.y)
            self.task_listbox.selection_clear(0, tk.END)
            self.task_listbox.selection_set(index)
            self.task_listbox.activate(index)
        except Exception:
            pass

        selection = self.task_listbox.curselection()
        if not selection:
            return

        # Create context menu
        menu = tk.Menu(self, tearoff=0, bg='#2a2a2a', fg=self.config.FG_COLOR)
        
        # Navigation
        menu.add_command(label="📂 Open in Workspace", command=lambda: self._on_task_double_click(None))
        menu.add_separator()
        
        # Actions
        menu.add_command(label="✅ Mark Complete", command=self._verify_and_complete_task)
        menu.add_command(label="📝 Edit Raw JSON", command=lambda: self._open_task_tab_action(2)) # Tab 2 is JSON
        menu.add_command(label="📅 View Timeline Context", command=lambda: self._open_task_tab_action(3)) # Tab 3 is Timeline
        
        # Advanced / Routing
        menu.add_separator()
        menu.add_command(label="🔧 Correct Routing (Properties)", command=self._show_routing_correction_dialog)
        menu.add_command(label="🔬 Review Absorb (Diff)", command=self._review_absorb_task)
        
        menu.add_separator()
        menu.add_command(label="🔄 Refresh List", command=self._refresh_task_list)

        try:
            menu.post(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def _open_task_tab_action(self, tab_index):
        """Helper to open a specific tab in the workspace notebook after selection"""
        # Ensure selection is processed
        self._on_task_double_click(None)
        # Switch tab
        if hasattr(self, 'workspace_notebook'):
            self.workspace_notebook.select(tab_index)

    def _show_routing_correction_dialog(self):
        """Dialog to correct inferred properties and routing"""
        if not hasattr(self, 'task_listbox'): return
        selection = self.task_listbox.curselection()
        if not selection: return
        
        index = selection[0]
        if index >= len(self.tasks_data): return
        task = self.tasks_data[index]
        task_id = task.get('id', 'Unknown')
        
        # Create correction popup
        popup = tk.Toplevel(self)
        popup.title(f"🔧 Correction: {task_id[:8]}")
        popup.geometry("400x350")
        popup.configure(bg=self.config.BG_COLOR)
        popup.transient(self)
        popup.grab_set()

        tk.Label(popup, text=f"Routing Correction: #{task_id}", 
                bg=self.config.BG_COLOR, fg=self.config.ACCENT_COLOR, 
                font=('Arial', 10, 'bold')).pack(pady=15)

        # Fields
        form_frame = tk.Frame(popup, bg=self.config.BG_COLOR)
        form_frame.pack(fill=tk.BOTH, expand=True, padx=20)

        # Project ID
        tk.Label(form_frame, text="Parent Project ID:", bg=self.config.BG_COLOR, fg='#888888').pack(anchor=tk.W)
        proj_entry = tk.Entry(form_frame, bg='#2a2a2a', fg='white', insertbackground='white')
        proj_entry.insert(0, task.get('project_id', ''))
        proj_entry.pack(fill=tk.X, pady=(0, 10))

        # Plan ID
        tk.Label(form_frame, text="Target Plan ID:", bg=self.config.BG_COLOR, fg='#888888').pack(anchor=tk.W)
        plan_entry = tk.Entry(form_frame, bg='#2a2a2a', fg='white', insertbackground='white')
        plan_entry.insert(0, task.get('plan_id', ''))
        plan_entry.pack(fill=tk.X, pady=(0, 10))

        # Status Override
        tk.Label(form_frame, text="Status Override:", bg=self.config.BG_COLOR, fg='#888888').pack(anchor=tk.W)
        status_var = tk.StringVar(value=task.get('status', 'pending'))
        status_menu = ttk.Combobox(form_frame, textvariable=status_var, 
                                  values=['pending', 'in_progress', 'completed', 'failed', 'deferred'],
                                  state='readonly')
        status_menu.pack(fill=tk.X, pady=(0, 10))

        def apply_changes():
            # Update local dict
            task['project_id'] = proj_entry.get().strip()
            task['plan_id'] = plan_entry.get().strip()
            task['status'] = status_var.get()
            task['updated_at'] = datetime.now().isoformat()
            
            # Save to disk
            self._save_task_edits()
            
            # Refresh UI
            self._on_task_double_click(None)
            self._refresh_task_list()
            
            popup.destroy()
            self._add_traceback(f"Corrected routing for Task {task_id}", "TASK")

        # Buttons
        btn_frame = tk.Frame(popup, bg=self.config.BG_COLOR)
        btn_frame.pack(fill=tk.X, pady=20, padx=20)

        tk.Button(btn_frame, text="Cancel", command=popup.destroy, 
                 bg='#444444', fg='white', width=10).pack(side=tk.LEFT)
        
        tk.Button(btn_frame, text="Apply & Save", command=apply_changes, 
                 bg='#2d7d46', fg='white', width=15).pack(side=tk.RIGHT)

    def _verify_and_complete_task(self):
        """Run mandatory code checks and mark task complete if passed"""
        selection = self.task_listbox.curselection()
        if not selection: return
        
        task_data = self.tasks_data[selection[0]]
        task_id = task_data.get('id')
        marked_files = task_data.get('files', [])

        if not marked_files:
            if not messagebox.askyesno("Verify Task", "No files associated with this task. Mark complete anyway?"):
                return

        # 1. Run Checks
        self.status_var.set(f"⌛ Verifying Task {task_id[:8]}...")
        self.engine.log_debug(f"Verifying task: {task_id}", "INFO")
        
        all_passed = True
        results = {}

        # Instantiate engine for checks if possible
        try:
            sys.path.insert(0, str(self.version_root))
            from docv2_engine import WorkflowEngine
            import argparse
            args = argparse.Namespace(verbose=False, workspace=self.version_root, resource_dedication=None)
            check_engine = WorkflowEngine(args)
        except Exception as e:
            self.engine.log_debug(f"Could not load check engine: {e}", "ERROR")
            messagebox.showerror("Error", "Could not load docv2_engine for verification.")
            return

        for rel_path in marked_files:
            # Resolve path
            if self.app_ref and hasattr(self.app_ref, 'current_project'):
                abs_path = self.app_ref.current_project / rel_path
            else:
                abs_path = Path(rel_path)

            if abs_path.exists() and abs_path.suffix == '.py':
                self.engine.log_debug(f"  Checking {abs_path.name}...", "DEBUG")
                check_res = check_engine.check_code(abs_path)
                results[rel_path] = check_res
                if not check_res.get('passed', False):
                    all_passed = False
            elif not abs_path.exists():
                self.engine.log_debug(f"  File missing: {rel_path}", "WARNING")
                all_passed = False

        # 2. Update Task Status
        new_status = 'completed' if all_passed else 'failed'
        task_data['status'] = new_status
        task_data['completed_at'] = datetime.now().isoformat()
        
        # Add PFC record to task
        if 'pfc_results_on_completion' not in task_data:
            task_data['pfc_results_on_completion'] = []
        
        pfc_run = {
            "timestamp": datetime.now().isoformat(),
            "overall_status": "Passed" if all_passed else "Failed",
            "file_checks": results
        }
        
        # --- Interactive PFC Review & Validation ---
        if show_pfc_results:
            confirmed = show_pfc_results(self, pfc_run, task_data)
            if not confirmed:
                self.status_var.set("Task completion cancelled by user")
                return
        
        task_data['pfc_results_on_completion'].append(pfc_run)

        # 3. Save Task
        # Find the actual task file path
        if self.app_ref and hasattr(self.app_ref, 'current_project'):
            tasks_dir = self.app_ref.current_project / ".docv2_workspace" / "tasks"
        else:
            tasks_dir = self.version_root / ".docv2_workspace" / "tasks"
            
        task_file = tasks_dir / f"task_{task_id}.json"
        try:
            with open(task_file, 'w') as f:
                json.dump(task_data, f, indent=2)
            
            self._refresh_task_list()
            
            if all_passed:
                self.status_var.set(f"✅ Task {task_id[:8]} Completed")
                messagebox.showinfo("Success", f"Task {task_id[:8]} verified and completed!")
            else:
                self.status_var.set(f"❌ Task {task_id[:8]} Failed Checks")
                messagebox.showwarning("Verification Failed", 
                                     f"Task {task_id[:8]} failed code checks. Status set to 'failed'.\nCheck details for info.")
        except Exception as e:
            self.engine.log_debug(f"Failed to save task update: {e}", "ERROR")
            messagebox.showerror("Error", f"Failed to update task file: {e}")

    def _review_absorb_task(self):
        """Run visual diff review (Absorb) for selected task files"""
        selection = self.task_listbox.curselection()
        if not selection: return
        
        task = self.tasks_data[selection[0]]
        marked_files = task.get('files', [])
        
        if not marked_files:
            messagebox.showinfo("Absorb Review", "No files associated with this task for review.")
            return

        # Stop flashing when user starts review
        self._stop_flash()

        self.engine.log_debug(f"Starting Absorb Review for {len(marked_files)} files", "INFO")
        
        # Integration logic: Launch scope_flow LiveGUIReview for each file
        # For this prototype, we'll open the first file or a selector
        file_to_review = marked_files[0]
        # Resolve full path
        if self.app_ref and hasattr(self.app_ref, 'current_project'):
            abs_path = self.app_ref.current_project / file_to_review
        else:
            abs_path = Path(file_to_review)

        if not abs_path.exists():
            messagebox.showerror("Error", f"File not found: {abs_path}")
            return

        # Launch LiveGUIReview
        try:
            from scope.variants.scope_flow import LiveGUIReview
            review_win = tk.Toplevel(self)
            review_win.withdraw() # We use the root from LiveGUIReview
            review = LiveGUIReview(self, str(abs_path))
            review.show_review()
        except Exception as e:
            self.engine.log_debug(f"Failed to launch LiveGUIReview: {e}", "ERROR")
            messagebox.showerror("Review Error", f"Could not launch visual diff:\n{e}")

    def _open_tasks_tab(self):
        """Open Tasks tab in babel_gui"""
        # Stop flashing when user goes to tasks
        self._stop_flash()
        if self.app_ref and hasattr(self.app_ref, 'notebook') and hasattr(self.app_ref, 'tasks_frame'):
            self.app_ref.notebook.select(self.app_ref.tasks_frame)
            self.engine.log_debug("Opened Tasks tab from task list", "INFO")
            self.status_var.set("📋 Opened Tasks tab")
            log_to_traceback(EventCategory.INFO, "open_tasks_from_list",
                           {"source": "grep_flight"}, {"status": "switched_to_tasks"})
        else:
            self.status_var.set("⚠️ Tasks tab not available")

    def _open_planner_tab(self):
        """Open Planner tab in babel_gui"""
        if self.app_ref and hasattr(self.app_ref, 'notebook') and hasattr(self.app_ref, 'planner_panel'):
            self.app_ref.notebook.select(self.app_ref.planner_panel)
            self.engine.log_debug("Opened Planner tab from task list", "INFO")
            self.status_var.set("🧭 Opened Planner tab")
        else:
            self.status_var.set("⚠️ Planner tab not available")

    def _show_planner_files(self):
        """Show list of project plan files in a popup"""
        # Determine plans directory
        if self.app_ref and hasattr(self.app_ref, 'current_project'):
            plans_dir = self.app_ref.current_project / "PlannerSuite"
        else:
            plans_dir = self.version_root / ".docv2_workspace" / "plans"

        if not plans_dir.exists():
            messagebox.showinfo("Plans", "No plans directory found for the current context.")
            return

        # Create popup
        win = tk.Toplevel(self)
        win.title("Project Plans")
        win.geometry("500x600")
        win.configure(bg='#1e1e1e')
        win.transient(self)

        tk.Label(win, text="Project Plan Files", font=('Arial', 12, 'bold'),
                 bg='#1e1e1e', fg='#4ec9b0').pack(pady=10)

        tree = ttk.Treeview(win, columns=('Type', 'Modified'), show='tree headings')
        tree.heading('#0', text='File / Folder')
        tree.heading('Type', text='Type')
        tree.heading('Modified', text='Modified')
        tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Populate tree
        def populate(parent_node, current_path):
            for item in sorted(current_path.iterdir()):
                if item.name.startswith('.'): continue
                
                mtime = datetime.fromtimestamp(item.stat().st_mtime).strftime('%Y-%m-%d %H:%M')
                item_type = "Folder" if item.is_dir() else item.suffix.upper() or "File"
                
                node = tree.insert(parent_node, 'end', text=item.name, values=(item_type, mtime), open=item.is_dir())
                if item.is_dir():
                    populate(node, item)

        populate('', plans_dir)

        tk.Button(win, text="Close", command=win.destroy, 
                 bg='#3c3c3c', fg='white').pack(pady=10)

    def _start_task_watcher(self):
        """Background loop to monitor task changes and trigger alerts"""
        if not self.task_watcher_active:
            return

        # Determine tasks directory
        if self.app_ref and hasattr(self.app_ref, 'current_project'):
            tasks_dir = self.app_ref.current_project / ".docv2_workspace" / "tasks"
        else:
            tasks_dir = self.version_root / ".docv2_workspace" / "tasks"

        if tasks_dir.exists():
            changed = False
            for task_file in tasks_dir.glob("*.json"):
                mtime = task_file.stat().st_mtime
                if str(task_file) not in self.task_mtimes:
                    self.task_mtimes[str(task_file)] = mtime
                    # Don't trigger on initial load
                elif mtime > self.task_mtimes[str(task_file)]:
                    self.task_mtimes[str(task_file)] = mtime
                    changed = True
            
            if changed and not self.is_flashing:
                self.engine.log_debug("Task changes detected! Triggering alert.", "INFO")
                self._flash_task_alert(True)

        # Schedule next check
        self.after(5000, self._start_task_watcher)

    def _flash_task_alert(self, start=False):
        """Toggle Tasks tab color to alert user"""
        if start:
            self.is_flashing = True
        
        if not self.is_flashing:
            # Reset tab style
            return

        # Note: tt.Notebook tab styling is complex. 
        # For now, we flash the status bar as well
        current_status_bg = self.status_label.cget("bg")
        next_bg = self.config.ACCENT_COLOR if current_status_bg == self.config.BG_COLOR else self.config.BG_COLOR
        next_fg = 'black' if next_bg == self.config.ACCENT_COLOR else self.config.ACCENT_COLOR
        
        self.status_label.config(bg=next_bg, fg=next_fg)
        
        if self.is_flashing:
            self.after(500, self._flash_task_alert)

    def _stop_flash(self):
        """Stop the flashing alert"""
        self.is_flashing = False
        self.status_label.config(bg=self.config.BG_COLOR, fg=self.config.ACCENT_COLOR)

    def _show_task_details(self):
        """Show detailed information about selected task"""
        if not hasattr(self, 'task_listbox'):
            return

        selection = self.task_listbox.curselection()
        if not selection:
            self.status_var.set("⚠️ No task selected")
            return

        # Get task index (accounting for filters)
        idx = selection[0]
        type_filter = self.task_type_filter.get()
        status_filter = self.task_status_filter.get()

        # Rebuild filtered list to match display
        filtered_tasks = []
        for task in self.tasks_data:
            if type_filter != "all" and task.get('type', '') != type_filter:
                continue
            if status_filter != "all" and task.get('status', '') != status_filter:
                continue
            filtered_tasks.append(task)

        if idx >= len(filtered_tasks):
            return

        task = filtered_tasks[idx]

        # Create details popup
        details_window = tk.Toplevel(self)
        details_window.title(f"Task Details: {task.get('id', 'unknown')}")
        details_window.geometry("500x400")
        details_window.configure(bg=self.config.BG_COLOR)
        details_window.transient(self)

        # Details text
        details_text = scrolledtext.ScrolledText(
            details_window,
            bg='#2a2a2a',
            fg=self.config.FG_COLOR,
            font=('Monospace', 9),
            wrap=tk.WORD
        )
        details_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Format task details
        details = f"""TASK DETAILS
{"="*60}

ID:          {task.get('id', 'N/A')}
Title:       {task.get('title', 'N/A')}
Type:        {task.get('type', 'N/A')}
Status:      {task.get('status', 'N/A')}

Description:
{task.get('description', 'No description')}

Phase:       {task.get('phase', 'N/A')}
Plan:        {task.get('plan', 'N/A')}
Epic:        {task.get('epic', 'N/A')}

Marked Files:
{chr(10).join(task.get('marked_files', ['None']))}

Created:     {task.get('created', 'N/A')}
Modified:    {task.get('modified', 'N/A')}

{"="*60}
"""
        details_text.insert(1.0, details)
        details_text.config(state=tk.DISABLED)

        # Close button
        tk.Button(details_window, text="Close", command=details_window.destroy,
                 bg=self.config.HOVER_COLOR, fg=self.config.FG_COLOR).pack(pady=(0, 10))

    def _update_from_engine(self):
        """Update UI from engine queue"""
        try:
            while True:
                item_type, data = self.engine.results_queue.get_nowait()

                if item_type == 'workflow_step':
                    # Update indicators
                    self._update_indicators()

                    # Add to traceback
                    self._add_traceback(data['message'], data['type'])

                elif item_type == 'debug':
                    # Route debug messages to traceback window
                    self._add_traceback(data['message'], data['level'])

                elif item_type == 'shared_log':
                    # Handle logs from other modules
                    line = data
                    if "#[Event:" in line:
                        # Extract event type for coloring
                        match = re.search(r'#\[Event:([^\]]+)\]', line)
                        event_type = match.group(1) if match else "INFO"
                        # Clean up line for display if needed
                        self._add_traceback(f"🔗 {line}", event_type)
                    else:
                        self._add_traceback(f"🔗 {line}", "INFO")

        except queue.Empty:
            pass

        # Schedule next update
        self.after(100, self._update_from_engine)

    # ========================================================================
    # Inventory Tab Helper Methods
    # ========================================================================

    def _refresh_provisions(self):
        """Refresh provisions list from backup_manifest.json (local and unified)"""
        self.provisions_listbox.delete(0, tk.END)

        try:
            all_backups = []

            # Load local backup manifest
            local_manifest_path = Path(__file__).parent / "backup_manifest.json"
            if local_manifest_path.exists():
                with open(local_manifest_path, 'r') as f:
                    local_manifest = json.load(f)
                    # Handle both old format (dict with file keys) and new format (list)
                    if isinstance(local_manifest, dict):
                        # New format: dict with file paths as keys
                        for file_path, backups_list in local_manifest.items():
                            for backup in backups_list:
                                backup['original_path'] = file_path
                                backup['source'] = 'grep_flight'
                                all_backups.append(backup)
                    elif isinstance(local_manifest, list):
                        # Old format: flat list
                        for backup in local_manifest:
                            backup['source'] = 'grep_flight'
                            all_backups.append(backup)

            # Load unified backup manifest from Morph snapshots
            unified_manifest_path = self.version_root.parent / "snapshots"
            if unified_manifest_path.exists():
                for snap_file in unified_manifest_path.glob("*.json"):
                    try:
                        with open(snap_file, 'r') as f:
                            snapshot = json.load(f)
                            if snapshot.get('backup_path'):
                                all_backups.append({
                                    'backup_path': snapshot['backup_path'],
                                    'original_path': 'guillm.py',
                                    'timestamp': snapshot.get('timestamp', 'N/A'),
                                    'backup_name': Path(snapshot['backup_path']).name,
                                    'source': 'morph'
                                })
                    except:
                        pass

            if not all_backups:
                self.provisions_listbox.insert(tk.END, "  No backups found")
                return

            # Sort by timestamp and get latest 30
            latest_backups = sorted(all_backups, key=lambda x: x.get("timestamp", ""), reverse=True)[:30]

            # Display with formatting
            for backup in latest_backups:
                original = backup.get("original_path", "Unknown")
                filename = Path(original).name if original != "Unknown" else "Unknown"
                timestamp = backup.get("timestamp", "N/A")[:16]
                source = backup.get("source", "unknown")
                source_icon = "🔧" if source == "grep_flight" else "🎨" if source == "morph" else "📦"

                entry = f"{source_icon} {filename:<35} | {timestamp}"
                self.provisions_listbox.insert(tk.END, entry)

                # Color code by source and existence
                color = '#4ec9b0' if Path(backup.get('backup_path', '')).exists() else '#888888'
                self.provisions_listbox.itemconfig(
                    self.provisions_listbox.size() - 1,
                    {'fg': color}
                )

            self._add_traceback(f"📋 Loaded {len(latest_backups)} provisions (local + unified)", "INFO")

        except Exception as e:
            self.provisions_listbox.insert(tk.END, f"  Error loading provisions: {e}")
            self._add_traceback(f"❌ Provisions load error: {e}", "ERROR")

    def _open_provision(self):
        """Open selected provision file"""
        selection = self.provisions_listbox.curselection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a provision file first")
            return

        try:
            # Parse filename from listbox entry
            entry_text = self.provisions_listbox.get(selection[0])
            filename = entry_text.split("|")[0].strip()

            # Find file path from manifest
            manifest_path = Path(__file__).parent / "backup_manifest.json"
            with open(manifest_path, 'r') as f:
                manifest = json.load(f)

            for backup in manifest.get("backups", []):
                if Path(backup.get("original_path", "")).name == filename:
                    file_path = backup.get("original_path")
                    if Path(file_path).exists():
                        os.system(f"xdg-open '{file_path}' &")
                        self._add_traceback(f"📂 Opened: {filename}", "INFO")
                        return

            messagebox.showerror("File Not Found", f"Could not locate file: {filename}")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to open provision: {e}")
            self._add_traceback(f"❌ Open provision error: {e}", "ERROR")

    def _target_provision(self):
        """Set selected provision as grep target"""
        selection = self.provisions_listbox.curselection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a provision file first")
            return

        try:
            entry_text = self.provisions_listbox.get(selection[0])
            filename = entry_text.split("|")[0].strip()

            manifest_path = Path(__file__).parent / "backup_manifest.json"
            with open(manifest_path, 'r') as f:
                manifest = json.load(f)

            for backup in manifest.get("backups", []):
                if Path(backup.get("original_path", "")).name == filename:
                    file_path = backup.get("original_path")
                    if Path(file_path).exists():
                        self.target_var.set(file_path)
                        self.engine.set_target(file_path)
                        self._add_traceback(f"🎯 Targeted: {filename}", "INFO")
                        return

            messagebox.showerror("File Not Found", f"Could not locate file: {filename}")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to target provision: {e}")

    def _profile_provision(self):
        """Show profile/lineage for selected provision - Placeholder for Phase 2.4"""
        messagebox.showinfo("Profile", "Profile functionality coming in Phase 2.4")

    def _stash_provision(self):
        """Stash selected provision file"""
        messagebox.showinfo("Stash", "Stash functionality integrated in Stash sub-tab")

    def _stash_current_target(self):
        """Stash the current target using stash_script"""
        target = self.target_var.get()
        if not target:
            messagebox.showwarning("No Target", "Please set a target file first")
            return

        messagebox.showinfo("Stash", f"Stash functionality to be integrated with stash_script.py\nTarget: {target}")
        self._add_traceback(f"💾 Stash requested for: {Path(target).name}", "INFO")

    def _refresh_stash(self):
        """Refresh stash list - Placeholder"""
        self.stash_listbox.delete(0, tk.END)
        self.stash_listbox.insert(tk.END, "  Stash integration with stash_script.py coming soon")
        self.stash_listbox.insert(tk.END, "  This will show files from quick_stash/ directory")

    def _unstash_file(self):
        """Unstash selected file - Placeholder"""
        messagebox.showinfo("Unstash", "Unstash functionality to be integrated with stash_script.py")

    def _delete_stash(self):
        """Delete selected stash - Placeholder"""
        messagebox.showinfo("Delete Stash", "Delete stash functionality to be implemented")

    def _refresh_projects(self):
        """Refresh shared projects list"""
        self.projects_listbox.delete(0, tk.END)

        try:
            # Get shared projects directory from workspace manager if available
            if self.app_ref and hasattr(self.app_ref, 'workspace_mgr'):
                shared_dir = self.app_ref.workspace_mgr.get_shared_projects_dir()
            else:
                # Fallback to repo root calculation
                repo_root = Path(__file__).parent.parent.parent.parent.parent
                shared_dir = repo_root / ".docv2_workspace" / "projects"

            if not shared_dir.exists():
                self.projects_listbox.insert(tk.END, f"  Shared projects directory not found:")
                self.projects_listbox.insert(tk.END, f"  {shared_dir}")
                self.projects_listbox.insert(tk.END, "  ")
                self.projects_listbox.insert(tk.END, "  Create with context toggle: Main/Stable or Shared")
                return

            # Scan for project directories
            projects_found = []
            for category_dir in shared_dir.iterdir():
                if category_dir.is_dir():
                    category_name = category_dir.name
                    self.projects_listbox.insert(tk.END, f"📁 {category_name.upper()}")

                    for project_dir in category_dir.iterdir():
                        if project_dir.is_dir():
                            projects_found.append(str(project_dir))
                            self.projects_listbox.insert(tk.END, f"  ├─ {project_dir.name}")

                            # Check for inventory subdirectory
                            inventory_dir = project_dir / "inventory"
                            if inventory_dir.exists():
                                file_count = len(list(inventory_dir.iterdir()))
                                self.projects_listbox.insert(tk.END, f"     └─ inventory/ ({file_count} files)")

            if not projects_found:
                self.projects_listbox.insert(tk.END, "  No projects found")
                self.projects_listbox.insert(tk.END, "  Use babel_gui [New Project] to create provisions")

            self._add_traceback(f"🗂️ Found {len(projects_found)} shared projects", "INFO")

        except Exception as e:
            self.projects_listbox.insert(tk.END, f"  Error loading projects: {e}")
            self._add_traceback(f"❌ Projects load error: {e}", "ERROR")

    def _open_project(self):
        """Open selected project directory - Placeholder"""
        messagebox.showinfo("Open Project", "Project navigation to be implemented")

    def _target_project(self):
        """Set selected project as target - Placeholder"""
        messagebox.showinfo("Target Project", "Project targeting to be implemented")

# ============================================================================
# Dialogs
# ============================================================================

class HelpDialog:
    """Comprehensive help and guidance dialog"""

    def __init__(self, parent, config):
        self.parent = parent
        self.config = config

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Grep Flight - Help & Guidance")
        self.dialog.geometry("800x600")
        self.dialog.configure(bg=config.BG_COLOR)
        self.dialog.transient(parent)

        self._setup_ui()

    def _setup_ui(self):
        """Setup help UI with tabs"""
        # Create notebook for different help sections
        notebook = ttk.Notebook(self.dialog)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Create tabs
        self._create_overview_tab(notebook)
        self._create_grep_basics_tab(notebook)
        self._create_patterns_tab(notebook)
        self._create_workflows_tab(notebook)
        self._create_shortcuts_tab(notebook)

        # Close button at bottom
        btn_frame = tk.Frame(self.dialog, bg=self.config.BG_COLOR)
        btn_frame.pack(pady=10)
        tk.Button(btn_frame, text="Close", command=self.dialog.destroy,
                 bg=self.config.ACCENT_COLOR, fg='black',
                 padx=20, pady=5).pack()

    def _create_overview_tab(self, notebook):
        """Create overview tab"""
        frame = tk.Frame(notebook, bg=self.config.BG_COLOR)
        notebook.add(frame, text="Overview")

        text = scrolledtext.ScrolledText(frame, bg='#2a2a2a', fg=self.config.FG_COLOR,
                                        font=('Monospace', 10), wrap=tk.WORD, padx=10, pady=10)
        text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        content = """
GREP FLIGHT v2 - SURGICAL GREP TOOLKIT
=====================================

Welcome to Grep Flight! This tool helps you perform precise grep operations
with an intuitive GUI interface.

QUICK START:
-----------
1. Click the expand button (▽) to open the main panel
2. Set a target directory using the Browse button or 📁 icon
3. Enter your search pattern
4. Use pre-built grep tools or workflows
5. View results in the results panel
6. Click on results to open in editor

MAIN FEATURES:
-------------
• Bottom panel design - stays out of your way
• Pre-configured grep templates for common tasks
• Workflow automation for complex search sequences
• Live workflow tracking and traceback
• PFL (Preflight) tag management
• Integration with editor, terminal, and file browser

GETTING STARTED:
---------------
• Press Ctrl+B to expand/collapse the panel
• Press Ctrl+T to browse for target
• Press Ctrl+F to focus pattern input
• Press Ctrl+G to execute grep
• Press Esc to exit

See other tabs for detailed grep guidance and examples.
        """
        text.insert(1.0, content)
        text.config(state=tk.DISABLED)

    def _create_grep_basics_tab(self, notebook):
        """Create grep basics tab"""
        frame = tk.Frame(notebook, bg=self.config.BG_COLOR)
        notebook.add(frame, text="Grep Basics")

        text = scrolledtext.ScrolledText(frame, bg='#2a2a2a', fg=self.config.FG_COLOR,
                                        font=('Monospace', 10), wrap=tk.WORD, padx=10, pady=10)
        text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        content = """
GREP BASICS - COMMAND LINE TEXT SEARCH
======================================

WHAT IS GREP?
------------
grep (Global Regular Expression Print) searches text files for patterns.
It's one of the most powerful text search tools in Unix/Linux.

COMMON GREP FLAGS:
-----------------
-r, --recursive    Search directories recursively
-n, --line-number  Show line numbers with output
-i, --ignore-case  Case-insensitive search
-w, --word-regexp  Match whole words only
-v, --invert       Invert match (show non-matching lines)
-l, --files-with-matches  Only show filenames
-c, --count        Count matching lines
-A NUM            Show NUM lines after match
-B NUM            Show NUM lines before match
-C NUM            Show NUM lines before and after match
-E, --extended-regexp  Use extended regex (same as egrep)
--include=PATTERN  Only search files matching PATTERN
--exclude=PATTERN  Skip files matching PATTERN

BASIC EXAMPLES:
--------------
# Find "error" in all files recursively
grep -r "error" /var/log

# Find "TODO" with line numbers (case-insensitive)
grep -rni "TODO" .

# Find exact word "test" (not "testing")
grep -rnw "test" .

# Find lines NOT containing "success"
grep -rnv "success" .

# Find in Python files only
grep -rn "def " --include="*.py" .

# Show 3 lines of context around matches
grep -rnC 3 "error" .

PRE-BUILT TEMPLATES IN GREP FLIGHT:
-----------------------------------
G1: Pattern      - Basic recursive pattern search
G2: Exact        - Exact word matching (-w flag)
G3: Case Ins     - Case-insensitive search (-i flag)
G4: PFL Tags     - Find PFL/TODO/FIXME tags
G5: File Type    - Search specific file types
        """
        text.insert(1.0, content)
        text.config(state=tk.DISABLED)

    def _create_patterns_tab(self, notebook):
        """Create regex patterns tab"""
        frame = tk.Frame(notebook, bg=self.config.BG_COLOR)
        notebook.add(frame, text="Patterns & Regex")

        text = scrolledtext.ScrolledText(frame, bg='#2a2a2a', fg=self.config.FG_COLOR,
                                        font=('Monospace', 10), wrap=tk.WORD, padx=10, pady=10)
        text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        content = """
REGULAR EXPRESSIONS IN GREP
============================

BASIC PATTERNS:
--------------
.           Any single character
^           Start of line
$           End of line
[abc]       Any character in set (a, b, or c)
[^abc]      Any character NOT in set
[a-z]       Any character in range
\\           Escape special character

QUANTIFIERS:
-----------
*           0 or more times
+           1 or more times (use -E for extended regex)
?           0 or 1 time (use -E for extended regex)
{n}         Exactly n times (use -E for extended regex)
{n,}        n or more times (use -E for extended regex)
{n,m}       Between n and m times (use -E for extended regex)

CHARACTER CLASSES:
-----------------
\\d          Digit [0-9]
\\w          Word character [A-Za-z0-9_]
\\s          Whitespace
\\b          Word boundary

GROUPING:
--------
(pattern)   Group (use -E for extended regex)
|           OR operator (use -E for extended regex)

PRACTICAL EXAMPLES:
------------------
# Find email addresses
grep -rE "[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}" .

# Find IP addresses
grep -rE "([0-9]{1,3}\\.){3}[0-9]{1,3}" .

# Find function definitions (Python)
grep -rn "^def [a-zA-Z_][a-zA-Z0-9_]*" --include="*.py" .

# Find TODO/FIXME/BUG comments
grep -rni "\\(TODO\\|FIXME\\|BUG\\):" .

# Find URLs
grep -rE "https?://[a-zA-Z0-9./?=_-]+" .

# Find hex colors
grep -rE "#[0-9a-fA-F]{6}" .

# Find Python imports
grep -rn "^import\\|^from.*import" --include="*.py" .

# Find empty lines
grep -rn "^$" .

# Find lines with only whitespace
grep -rn "^[[:space:]]*$" .

TIPS:
----
• Use quotes around patterns to prevent shell interpretation
• Use -E for extended regex (easier syntax)
• Test patterns on small files first
• Use tools like regex101.com to build complex patterns
        """
        text.insert(1.0, content)
        text.config(state=tk.DISABLED)

    def _create_workflows_tab(self, notebook):
        """Create workflows tab"""
        frame = tk.Frame(notebook, bg=self.config.BG_COLOR)
        notebook.add(frame, text="Workflows")

        text = scrolledtext.ScrolledText(frame, bg='#2a2a2a', fg=self.config.FG_COLOR,
                                        font=('Monospace', 10), wrap=tk.WORD, padx=10, pady=10)
        text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        content = """
GREP FLIGHT WORKFLOWS
=====================

Workflows automate common grep sequences for specific tasks.

AVAILABLE WORKFLOWS:
-------------------

1. QUICK SCAN
   Purpose: Fast search and PFL tag extraction
   Steps:
   • Select target directory
   • Set search pattern
   • Run grep scan
   • Extract existing PFL tags
   • Validate results

   Use when: You need a quick overview of matches and existing tags

2. DEEP DEBUG
   Purpose: Comprehensive debugging workflow
   Steps:
   • Select target
   • Run preflight checks
   • Search for BUG tags
   • Search for FIXME tags
   • Search for TODO tags
   • Analyze findings
   • Propose fixes

   Use when: Debugging code and need to find all issues

3. PFL AUDIT
   Purpose: Audit all PFL tags in codebase
   Steps:
   • Select target
   • Find all PFL tags
   • Categorize by type
   • Prioritize by importance
   • Generate audit report

   Use when: Managing technical debt and task tracking

4. SURGICAL FIX
   Purpose: Precise single-issue fix workflow
   Steps:
   • Select specific file
   • Identify exact issue
   • Propose fix
   • Apply fix
   • Test fix
   • Add PFL documentation

   Use when: Fixing a specific known issue

WORKFLOW TRACKING:
-----------------
• All workflow steps are logged to the traceback window
• View traceback with Ctrl+P or 📊 icon
• Colored indicators show workflow progress
• Rolling context maintains history

CUSTOM WORKFLOWS:
----------------
You can create custom workflows by:
1. Combining grep templates
2. Using the command input in expanded panel
3. Scripting with --cli mode
        """
        text.insert(1.0, content)
        text.config(state=tk.DISABLED)

    def _create_shortcuts_tab(self, notebook):
        """Create keyboard shortcuts tab"""
        frame = tk.Frame(notebook, bg=self.config.BG_COLOR)
        notebook.add(frame, text="Shortcuts")

        text = scrolledtext.ScrolledText(frame, bg='#2a2a2a', fg=self.config.FG_COLOR,
                                        font=('Monospace', 10), wrap=tk.WORD, padx=10, pady=10)
        text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        content = """
KEYBOARD SHORTCUTS
==================

PANEL CONTROLS:
--------------
Ctrl+B         Expand/collapse panel
Esc            Exit Grep Flight

NAVIGATION:
----------
Ctrl+T         Browse target directory
Ctrl+F         Focus pattern input field
Ctrl+G         Execute grep search
Ctrl+P         Show/hide workflow traceback

QUICK ACTIONS:
-------------
📁             Set target directory
🔍             Quick search with current pattern
🏷️             Show PFL tags in target
🐛             Activate debug mode
📊             Show workflow traceback
❓             Show this help
⚙             Open settings
✕              Exit application

RESULTS PANEL:
-------------
✏️ Edit        Open result in editor
💻 Terminal    Open terminal at target
📁 Browser     Open file browser
➕ PFL         Add PFL tag to code
🧹 Clear       Clear results
📋 Copy        Copy results to clipboard

TIPS:
----
• Use Enter in pattern field to execute search
• Double-click results to open in editor (if implemented)
• Right-click for context menu (if implemented)
• Drag and drop directories to set target (if implemented)

COMMAND LINE:
------------
grep_flight_v2.py --gui                    # Launch GUI (default)
grep_flight_v2.py --cli -t . -p "pattern"  # CLI mode
grep_flight_v2.py --workflow quick_scan    # Run workflow
grep_flight_v2.py --preflight              # System checks
grep_flight_v2.py --help                   # Show CLI help
        """
        text.insert(1.0, content)
        text.config(state=tk.DISABLED)

class PFLTagDialog:
    """Dialog for adding PFL tags"""
    
    def __init__(self, parent, config):
        self.parent = parent
        self.config = config
        self.result = None
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Add PFL Tag")
        self.dialog.configure(bg=config.BG_COLOR)
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        self._setup_ui()
        
    def _setup_ui(self):
        """Setup dialog UI"""
        main_frame = tk.Frame(self.dialog, bg=self.config.BG_COLOR, padx=20, pady=20)
        main_frame.pack()
        
        # Tag type
        tk.Label(main_frame, text="Tag Type:", bg=self.config.BG_COLOR,
                fg=self.config.FG_COLOR).grid(row=0, column=0, sticky=tk.W, pady=(0, 5))
        
        self.tag_type = tk.StringVar(value="TODO")
        tag_menu = ttk.Combobox(main_frame, textvariable=self.tag_type,
                               values=["BUG", "TODO", "FIXME", "TASK", "FEATURE", "OPTIMIZE", "NOTE"])
        tag_menu.grid(row=0, column=1, sticky=tk.W+tk.E, pady=(0, 5), padx=(5, 0))
        
        # Description
        tk.Label(main_frame, text="Description:", bg=self.config.BG_COLOR,
                fg=self.config.FG_COLOR).grid(row=1, column=0, sticky=tk.W, pady=(0, 5))
        
        self.desc_text = tk.Text(main_frame, height=4, width=40,
                                bg='#2a2a2a', fg=self.config.FG_COLOR)
        self.desc_text.grid(row=1, column=1, pady=(0, 10), padx=(5, 0))
        
        # Buttons
        btn_frame = tk.Frame(main_frame, bg=self.config.BG_COLOR)
        btn_frame.grid(row=2, column=0, columnspan=2, pady=(10, 0))
        
        tk.Button(btn_frame, text="Add Tag", command=self._add_tag,
                 bg=self.config.ACCENT_COLOR, fg='black').pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="Cancel", command=self.dialog.destroy,
                 bg=self.config.HOVER_COLOR, fg=self.config.FG_COLOR).pack(side=tk.LEFT, padx=5)
        
    def _add_tag(self):
        """Add the tag"""
        tag_type = self.tag_type.get()
        description = self.desc_text.get(1.0, tk.END).strip()
        
        if description:
            self.result = (tag_type, description)
            self.dialog.destroy()

class SettingsDialog:
    """Settings dialog"""
    
    def __init__(self, parent, config):
        self.parent = parent
        self.config = config
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Settings")
        self.dialog.geometry("400x300")
        self.dialog.configure(bg=config.BG_COLOR)
        
        self._setup_ui()
        
    def _setup_ui(self):
        """Setup settings UI"""
        notebook = ttk.Notebook(self.dialog)
        notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Appearance tab
        appear_frame = ttk.Frame(notebook)
        notebook.add(appear_frame, text="Appearance")
        
        # Color settings
        ttk.Label(appear_frame, text="Background:").grid(row=0, column=0, padx=5, pady=5)
        self.bg_color = tk.StringVar(value=self.config.BG_COLOR)
        ttk.Entry(appear_frame, textvariable=self.bg_color).grid(row=0, column=1, padx=5, pady=5)
        
        ttk.Button(appear_frame, text="Choose", 
                  command=lambda: self._choose_color(self.bg_color)).grid(row=0, column=2, padx=5, pady=5)
        
        # Apply button
        ttk.Button(appear_frame, text="Apply", command=self._apply_settings).grid(row=10, column=0, columnspan=3, pady=20)

    def _choose_color(self, color_var):
        """Open color chooser"""
        color = askcolor(color_var.get())[1]
        if color:
            color_var.set(color)
    
    def _apply_settings(self):
        """Apply settings"""
        # Would save to config file
        # Note: parent is the main window, need to access it
        if hasattr(self.parent, 'attributes'):
            self.parent.attributes('-topmost', False)
        messagebox.showinfo("Settings", "Settings applied (requires restart)")
        if hasattr(self.parent, 'attributes'):
            self.parent.attributes('-topmost', True)

# ============================================================================
# CLI Interface
# ============================================================================

def setup_cli_parser():
    """Setup CLI argument parser"""
    parser = argparse.ArgumentParser(
        description="Grep Flight v2 - Surgical Bottom Panel Toolkit",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --gui                    # Launch bottom panel GUI
  %(prog)s --cli --target ~/code --pattern "function"
  %(prog)s --cli --workflow quick_scan --target .
  %(prog)s --cli --preflight        # Run preflight checks
  %(prog)s --traceback              # Show traceback window only
        """
    )
    
    # Mode selection
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument('--gui', action='store_true', default=True,
                          help='Launch bottom panel GUI (default)')
    mode_group.add_argument('--cli', action='store_true',
                          help='Run in CLI mode')
    mode_group.add_argument('--traceback', action='store_true',
                          help='Show traceback window only')
    
    # Search options
    parser.add_argument('--target', '-t', help='Target directory or file')
    parser.add_argument('--pattern', '-p', help='Search pattern')
    parser.add_argument('--command', '-c', help='Direct command to execute')
    
    # Workflow options
    parser.add_argument('--workflow', '-w', 
                       choices=list(WorkflowPresets.get_workflows().keys()),
                       help='Run predefined workflow')
    
    # Preflight options
    parser.add_argument('--preflight', action='store_true',
                       help='Run preflight system checks')
    parser.add_argument('--debug', action='store_true',
                       help='Enable debug mode')
    parser.add_argument('--auto-fix', action='store_true',
                       help='Attempt auto-fix on issues')
    
    return parser

def run_preflight_checks():
    """Run system preflight checks with Taxonomy integration"""
    print("🔍 Running Preflight Checks...")
    
    # Setup log routing
    log_messages = []
    def log_print(msg):
        print(msg)
        log_messages.append(msg)

    log_print("-" * 40)
    
    # 1. Base Environment Checks
    checks = [
        ("Python 3.6+", sys.version_info >= (3, 6)),
        ("Tkinter available", True),
        ("grep command", subprocess.run(['which', 'grep'], capture_output=True).returncode == 0),
    ]
    
    # 1.1 Self-Introspection (NEW)
    try:
        critical_funcs = ['main', 'run_preflight_checks', 'BottomPanel']
        found_funcs = [name for name, obj in inspect.getmembers(sys.modules[__name__]) 
                      if name in critical_funcs and (inspect.isfunction(obj) or inspect.isclass(obj))]
        checks.append((f"Self-Introspection ({len(found_funcs)}/{len(critical_funcs)})", len(found_funcs) == len(critical_funcs)))
    except: pass

    # 2. Taxonomy & Modular Logic Checks (NEW)
    try:
        # Resolve path to modules
        v_root = Path(__file__).resolve().parents[3]
        modules_dir = v_root / "modules"
        
        sys.path.insert(0, str(modules_dir))
        import measurement_registry
        
        # Run scan in 'latest' mode for preflight efficiency
        log_print("📡 Scanning Taxonomy (mode: latest)...")
        reg = measurement_registry.scan_measurement_tools(mode="latest")
        checks.append((f"Taxonomy Scan ({reg.get('files_scanned', 0)} files)", True))
        checks.append((f"Registry Tools ({reg.get('total_tools', 0)})", reg.get('total_tools', 0) > 0))
        
        # 3. Deep Preflight Audit (NEW)
        log_print("🔬 Running Deep Taxonomical Audit (guillm)...")
        guillm_path = v_root / "modules" / "morph" / "guillm.py"
        audit_res = subprocess.run([sys.executable, str(guillm_path), "--workflow", "preflight_audit", "--depth", "1"], capture_output=True, text=True)
        if audit_res.stdout:
            log_print("--- Deep Audit Output ---")
            for line in audit_res.stdout.splitlines():
                if any(x in line for x in ["[Syntax]", "[Imports]", "[Taxonomy]", "TARGET:"]):
                    log_print(f"   {line}")
        checks.append(("Deep Taxonomical Audit", audit_res.returncode == 0))
        
    except Exception as e:
        checks.append((f"Taxonomy System: {str(e)}", False))

    all_passed = True
    for check, passed in checks:
        status = "✅" if passed else "❌"
        log_print(f"{status} {check}")
        if not passed:
            all_passed = True # Non-critical failure for now to allow launch
            if "❌" in status: all_passed = False # Critical logic

    log_print("-" * 40)
    final_status = "PASSED" if all_passed else "FAILED"
    log_print(f"Preflight {final_status}")
    
    # Write to shared log
    try:
        log_dir = Path(__file__).resolve().parents[4] / "logs"
        shared_log = log_dir / "unified_traceback.log"
        with open(shared_log, 'a') as f:
            ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            f.write(f"\n[{ts}] [PFC] --- PREFLIGHT SESSION ---\n")
            for m in log_messages:
                f.write(f"[{ts}] [PFC] {m}\n")
    except: pass
    
    return all_passed

def run_cli_mode(args):
    """Run in CLI mode"""
    if args.preflight:
        return 0 if run_preflight_checks() else 1
    
    if args.workflow:
        print(f"🚀 Running workflow: {args.workflow}")
        workflows = WorkflowPresets.get_workflows()
        if args.workflow in workflows:
            steps = workflows[args.workflow]
            for step in steps:
                print(f"  {step.icon} {step.name}")
                if step.command_template and args.target:
                    cmd = step.command_template.format(target=args.target, pattern=args.pattern or '')
                    print(f"    Command: {cmd}")
        return 0
    
    if args.command:
        print(f"Executing: {args.command}")
        result = subprocess.run(args.command, shell=True)
        return result.returncode
    
    print("Use --help for CLI options")
    return 0

# ============================================================================
# Main Entry
# ============================================================================

def main():
    """Main entry point"""
    parser = setup_cli_parser()
    args = parser.parse_args()
    
    # Preflight checks if requested
    if args.preflight:
        sys.exit(0 if run_preflight_checks() else 1)
    
    # CLI mode
    if args.cli:
        sys.exit(run_cli_mode(args))
    
    # Traceback-only mode
    if args.traceback:
        config = PanelConfig()
        root = tk.Tk()
        root.withdraw()
        panel = BottomPanel(config)
        panel._show_traceback()
        panel.mainloop()
        return
    
    # GUI mode (default)
    try:
        config = PanelConfig()
        if args.debug:
            config.BG_COLOR = '#0a0a0a'  # Darker for debug
        
        app = BottomPanel(config)
        
        # Seed GUI with CLI args if provided
        if args.target:
            # Normalize path
            target_path = os.path.abspath(args.target)
            app.target_var.set(target_path)
            app.engine.set_target(target_path)
            
            # Status update
            name = os.path.basename(target_path) or target_path
            app.status_var.set(f"✅ Target: {name}")
            
            # Auto-expand panel if target set
            app.is_expanded = False # Force expand state reset
            app._toggle_expand()
            
        if args.pattern:
            app.pattern_var.set(args.pattern)
            app.engine.set_pattern(args.pattern)
            # If both target and pattern, maybe auto-run?
            # For now, just pre-fill
            
        app.mainloop()
    except Exception as e:
        print(f"Error launching GUI: {e}")
        if args.debug:
            import traceback
            traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())
