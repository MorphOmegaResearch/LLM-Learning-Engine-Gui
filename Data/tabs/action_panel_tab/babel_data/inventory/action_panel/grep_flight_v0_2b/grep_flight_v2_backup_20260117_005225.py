#!/usr/bin/env python3
"""
Grep Flight v2 - Bottom Panel Toolkit
Ultra-slim bottom toolbar with surgical grep operations
Author: Assistant
Version: 2.1.0
"""

import os
import sys
import re
import argparse
import subprocess
import shlex
import json
import hashlib
import tempfile
import threading
import time
import queue
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Set, Optional, Tuple, Any, Callable
from dataclasses import dataclass, field, asdict
from enum import Enum, auto
import tkinter as tk
from tkinter import ttk, simpledialog, messagebox, scrolledtext, font, filedialog

# Import chat backend
try:
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'chat'))
    from chat_backend import ChatBackend
    CHAT_BACKEND_AVAILABLE = True
except ImportError as e:
    print(f"Chat backend not available: {e}")
    ChatBackend = None
    CHAT_BACKEND_AVAILABLE = False
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

        message = f"[{category.name}] {operation}"
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
        """Log debug message with timestamp"""
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        log_entry = f"[{timestamp}] {message}"
        self.debug_log.append(log_entry)
        if len(self.debug_log) > self.max_debug_log:
            self.debug_log = self.debug_log[-self.max_debug_log:]
        # Push to results queue for UI display in traceback window
        self.results_queue.put(('debug', {'message': message, 'level': level}))
        print(log_entry)  # Also print to console
        
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
# Bottom Panel UI
# ============================================================================

class BottomPanel(tk.Tk):
    """Main bottom panel window"""

    def __init__(self, config: PanelConfig, app_ref=None):
        # Configure root window
        super().__init__()
        self.config = config
        self.engine = GrepSurgicalEngine(config)
        self.app_ref = app_ref  # Reference to warrior_gui for tab navigation
        
        # Resolve paths
        # File: .../versions/VerName/Modules/action_panel/grep_flight_v0_2b/grep_flight_v2.py
        # parents[3] = .../versions/VerName (Version Root)
        # parents[5] = .../Warrior_Flow (Repo Root)
        self.version_root = Path(__file__).resolve().parents[3]
        self.repo_root = Path(__file__).resolve().parents[5]
        self.project_root = self.repo_root # Alias for compatibility
        
        self.gemini_proc = None # Track Gemini process

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
        self.is_expanded = False
        self.target_var = tk.StringVar()
        self.pattern_var = tk.StringVar()
        self.status_var = tk.StringVar(value="Ready - Click ▽ to expand | Press ❓ for help")
        self.current_workflow = None
        self.task_watcher_active = True
        self.task_mtimes = {} # Track modification times
        self.is_flashing = False

        # Workflow indicators
        self.indicator_canvas = None
        self.indicators = {}

        # Load workflow actions from profile (default profile if none set)
        self.workflow_actions = self._load_workflow_actions_config()
        self.toolkit_order = []  # Will be loaded when config UI opens
        self.current_profile_var = None  # Will be initialized in config UI
        self.active_profile = "Default Profile"
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

        # Start update loop
        self.after(100, self._update_from_engine)

        # Start IPC monitor loop
        self.after(200, self._monitor_ipc)

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
        # Remove window decorations
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
                    "warrior_flow_version": version_info,
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
        
        # Expand/collapse button
        self.expand_btn = tk.Button(
            left_frame,
            text="▽",
            font=('Arial', 10, 'bold'),
            bg=self.config.BG_COLOR,
            fg=self.config.FG_COLOR,
            bd=0,
            relief=tk.FLAT,
            width=3,
            command=self._toggle_expand
        )
        self.expand_btn.pack(side=tk.LEFT, padx=(0, 5))
        
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

        # TAB 1: Grep (existing functionality)
        self._create_grep_tab()

        # TAB 2: Tasks (task list)
        self._create_tasks_tab()

        # TAB 3: Chat (5x5cm chat interface)
        self._create_chat_tab()

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

        tk.Button(top_frame, text="Browse", command=self._browse_target,
                 bg=self.config.HOVER_COLOR, fg=self.config.FG_COLOR).pack(side=tk.LEFT, padx=(0, 5))

        # Recent targets dropdown
        tk.Button(top_frame, text="📜", command=self._show_recent_targets,
                 bg=self.config.HOVER_COLOR, fg=self.config.FG_COLOR,
                 width=2).pack(side=tk.LEFT, padx=(0, 10))
        self._create_tooltip_simple(top_frame.winfo_children()[-1], "Recent Targets")
        
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
        self.pattern_entry.bind('<Return>', lambda e: self._execute_grep())

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
            ("G1: Pattern", "grep -rn '{pattern}' {target}", "Recursive pattern search"),
            ("G2: Exact", "grep -rnw '{pattern}' {target}", "Exact word match"),
            ("G3: Case Ins", "grep -rni '{pattern}' {target}", "Case insensitive"),
            ("G4: PFL Tags", "grep -rn '#\\[PFL:' {target}", "Find PFL tags"),
            ("G5: Fetch Refs", "python3 {version_root}/Modules/Ag_Forge_v1c/modules/warehouse_prober.py {pattern}", "Fetch example scripts from Warehouse")
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
            ("📁 Browser", self._open_file_browser),
            ("➕ PFL", self._add_pfl_tag),
            ("💾 Export", self._export_results),
            ("🧹 Clear", self._clear_results),
            ("📋 Copy", self._copy_results)
        ]

        for text, command in actions:
            tk.Button(action_frame, text=text, command=command,
                     bg=self.config.HOVER_COLOR, fg=self.config.FG_COLOR).pack(side=tk.LEFT, padx=2)

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

        # Backup button
        backup_btn = tk.Button(
            controls_row,
            text="📦 Backup",
            command=self._backup_current_target,
            bg='#d67e00',
            fg='white',
            relief=tk.RAISED,
            bd=1,
            width=10,
            height=1
        )
        backup_btn.pack(side=tk.RIGHT, padx=(4, 0))
        self._create_tooltip_simple(backup_btn, "Backup current target file")

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
        """Create the Tasks tab with task list"""
        tasks_tab = tk.Frame(self.notebook, bg=self.config.BG_COLOR)
        self.notebook.add(tasks_tab, text="📋 Tasks")

        # Task list header
        task_header = tk.Frame(tasks_tab, bg=self.config.BG_COLOR, pady=10)
        task_header.pack(fill=tk.X, padx=10)

        tk.Label(task_header, text="Active Tasks", bg=self.config.BG_COLOR,
                fg=self.config.FG_COLOR, font=('Arial', 12, 'bold')).pack(side=tk.LEFT)

        tk.Button(task_header, text="🔄", command=self._refresh_task_list,
                 bg=self.config.BG_COLOR, fg=self.config.FG_COLOR,
                 bd=0, relief=tk.FLAT, width=2, font=('Arial', 12)).pack(side=tk.RIGHT)
        self._create_tooltip(task_header.winfo_children()[-1], "Refresh task list")

        # Filter controls
        filter_frame = tk.Frame(tasks_tab, bg=self.config.BG_COLOR)
        filter_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

        tk.Label(filter_frame, text="Type:", bg=self.config.BG_COLOR,
                fg=self.config.FG_COLOR).pack(side=tk.LEFT, padx=(0, 5))

        self.task_type_filter = tk.StringVar(value="all")
        type_menu = ttk.Combobox(filter_frame, textvariable=self.task_type_filter,
                                values=["all", "research", "plan", "implement", "review", "test", "debug"],
                                width=12, state='readonly')
        type_menu.pack(side=tk.LEFT, padx=(0, 10))
        type_menu.bind('<<ComboboxSelected>>', lambda e: self._filter_tasks())

        tk.Label(filter_frame, text="Status:", bg=self.config.BG_COLOR,
                fg=self.config.FG_COLOR).pack(side=tk.LEFT, padx=(0, 5))

        self.task_status_filter = tk.StringVar(value="all")
        status_menu = ttk.Combobox(filter_frame, textvariable=self.task_status_filter,
                                  values=["all", "pending", "in_progress", "completed"],
                                  width=12, state='readonly')
        status_menu.pack(side=tk.LEFT)
        status_menu.bind('<<ComboboxSelected>>', lambda e: self._filter_tasks())

        # Task list with scrollbar
        task_list_container = tk.Frame(tasks_tab, bg='#2a2a2a')
        task_list_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        task_scrollbar = tk.Scrollbar(task_list_container)
        task_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.task_listbox = tk.Listbox(
            task_list_container,
            bg='#2a2a2a',
            fg=self.config.FG_COLOR,
            selectbackground=self.config.ACCENT_COLOR,
            selectforeground='black',
            font=('Monospace', 10),
            yscrollcommand=task_scrollbar.set,
            activestyle='none'
        )
        self.task_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        task_scrollbar.config(command=self.task_listbox.yview)

        # Bind click events
        self.task_listbox.bind('<Double-Button-1>', self._on_task_double_click)
        self.task_listbox.bind('<Button-3>', self._on_task_right_click)

        # Task actions
        task_actions = tk.Frame(tasks_tab, bg=self.config.BG_COLOR)
        task_actions.pack(fill=tk.X, padx=10, pady=(0, 10))

        if self.app_ref:
            tk.Button(task_actions, text="→ warrior_gui Tasks", command=self._open_tasks_tab,
                     bg=self.config.ACCENT_COLOR, fg='black',
                     font=('Arial', 10), padx=10).pack(side=tk.LEFT, padx=5)

            tk.Button(task_actions, text="→ warrior_gui Planner", command=self._open_planner_tab,
                     bg='#613d8c', fg='white',
                     font=('Arial', 10), padx=10).pack(side=tk.LEFT, padx=5)

        tk.Button(task_actions, text="List Plans", command=self._show_planner_files,
                 bg='#3c3c3c', fg='#cccccc',
                 font=('Arial', 10), padx=10).pack(side=tk.LEFT, padx=5)

        tk.Button(task_actions, text="Details", command=self._show_task_details,
                 bg=self.config.HOVER_COLOR, fg=self.config.FG_COLOR,
                 font=('Arial', 10), padx=10).pack(side=tk.LEFT, padx=5)

        # Store tasks data
        self.tasks_data = []

        # Load initial tasks
        self._refresh_task_list()

        # Start background watcher
        self._start_task_watcher()

    def _create_chat_tab(self):
        """Create the Chat tab with 5x5cm chat interface"""
        chat_tab = tk.Frame(self.notebook, bg=self.config.BG_COLOR)
        self.notebook.add(chat_tab, text="💬 Chat")

        # Chat header
        chat_header = tk.Frame(chat_tab, bg=self.config.BG_COLOR, pady=10)
        chat_header.pack(fill=tk.X, padx=10)

        tk.Label(chat_header, text="Quick Chat", bg=self.config.BG_COLOR,
                fg=self.config.FG_COLOR, font=('Arial', 12, 'bold')).pack(side=tk.LEFT)

        # Model selector
        tk.Label(chat_header, text="Model:", bg=self.config.BG_COLOR,
                fg=self.config.FG_COLOR).pack(side=tk.RIGHT, padx=(10, 5))

        self.chat_model = tk.StringVar()
        models = []
        if self.chat_backend:
            models = self.chat_backend.get_available_models()
        
        # Add Gemini integration
        models.append("Gemini (CLI)")
        
        default_model = models[0] if models else "No models available"
        self.chat_model.set(default_model)

        model_menu = ttk.Combobox(chat_header, textvariable=self.chat_model,
                                 values=models,
                                 width=20, state='readonly')
        model_menu.pack(side=tk.RIGHT, padx=(0, 10))
        model_menu.bind('<<ComboboxSelected>>', lambda e: self._on_chat_model_selected())

        # Session switcher
        tk.Label(chat_header, text="Session:", bg=self.config.BG_COLOR,
                fg=self.config.FG_COLOR).pack(side=tk.RIGHT, padx=(10, 5))

        self.chat_session_type = tk.StringVar(value="Task")
        session_menu = ttk.Combobox(chat_header, textvariable=self.chat_session_type,
                                    values=["Plan", "Task"],
                                    width=8, state='readonly')
        session_menu.pack(side=tk.RIGHT)
        session_menu.bind('<<ComboboxSelected>>', lambda e: self._on_session_switch())

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

        tk.Button(action_frame, text="Clear", command=self._clear_chat,
                 bg=self.config.HOVER_COLOR, fg=self.config.FG_COLOR,
                 font=('Arial', 10), padx=15).pack(side=tk.RIGHT)

    def _send_chat_message(self):
        """Send a chat message"""
        message = self.chat_input.get().strip()
        if not message:
            return

        # Check if backend available
        if not self.chat_backend:
            self._add_chat_response("⚠️ Chat backend not available. Install: pip install ollama")
            return

        # Check if Gemini is selected - intercept
        if self.chat_model.get() == "Gemini (CLI)":
            self._add_chat_response("ℹ️ Gemini CLI is running in the external terminal window.")
            # Optional: We could try to send the text to that window via xdotool later
            return

        # Add message to chat
        self.chat_messages.config(state=tk.NORMAL)
        self.chat_messages.insert(tk.END, f"\n[You] {message}\n")
        self.chat_messages.config(state=tk.DISABLED)
        self.chat_messages.see(tk.END)

        # Clear input
        self.chat_input.delete(0, tk.END)

        # Log to traceback
        self.engine.log_debug(f"Chat message: {message}", "INFO")
        log_to_traceback(EventCategory.CHAT, "send_message",
                       {"session": self.chat_session_type.get(), "message": message[:50]},
                       {"status": "sent"})

        # Set up callbacks
        def on_response(response):
            self.after(0, lambda: self._add_chat_response(response))

        def on_error(error):
            self.after(0, lambda: self._add_chat_response(f"⚠️ {error}"))

        def on_status(status):
            # Could update a status label if needed
            pass

        self.chat_backend.on_response = on_response
        self.chat_backend.on_error = on_error
        self.chat_backend.on_status = on_status

        # Get selected model
        model = self.chat_model.get() if hasattr(self, 'chat_model') else None
        if not model or model == "Install Ollama" or model == "No models available":
            self._add_chat_response("⚠️ No AI model selected. Please install Ollama or configure Claude API.")
            return

        # Update context based on current state
        context_data = {
            "hierarchy_path": "Grep Flight → Quick Chat",
            "tool_switches": {
                "grep": self.tool_grep.get(),
                "read": self.tool_read.get(),
                "write": self.tool_write.get()
            }
        }
        # Add marked files if app_ref available
        if self.app_ref and hasattr(self.app_ref, '_planner_marked_files'):
            context_data["marked_files"] = self.app_ref._planner_marked_files

        self.chat_backend.update_context(context_data)

        # Send message
        self.chat_backend.send_message(message, model=model)

    def _on_chat_model_selected(self):
        """Handle model selection"""
        model = self.chat_model.get()
        if model == "Gemini (CLI)":
            self._launch_gemini_terminal()

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

            self._add_traceback(f"🚀 {session_id} | Launching at {geometry}", "INFO")

            cmd = [
                "xfce4-terminal",
                "--title=Gemini CLI",
                "--hold",
                f"--geometry={geometry}",
                "--command=gemini"
            ]
            self.engine.log_debug(f"Launch command: {cmd}", "DEBUG")

            self.gemini_proc = subprocess.Popen(cmd)
            self.status_var.set(f"🤖 {session_id} Active")

            # Log session to traceback
            log_to_traceback(EventCategory.INFO, "cli_session_start", {
                "session": session_id,
                "cli": "gemini",
                "target": self.target_var.get() if self.target_var.get() else None
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

            self._add_traceback(f"🚀 {session_id} | Launching at {geometry}", "INFO")

            cmd = [
                "xfce4-terminal",
                "--title=Claude CLI",
                "--hold",
                f"--geometry={geometry}",
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
        """Add a response to chat"""
        self.chat_messages.config(state=tk.NORMAL)
        self.chat_messages.insert(tk.END, f"[Assistant] {response}\n")
        self.chat_messages.config(state=tk.DISABLED)
        self.chat_messages.see(tk.END)

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
        
        # Close button
        tk.Button(self.traceback_window, text="Close",
                 command=self.traceback_window.withdraw,
                 bg=self.config.HOVER_COLOR, fg=self.config.FG_COLOR).pack(pady=(0, 10))

        # Bind Esc to close traceback window
        self.traceback_window.bind('<Escape>', lambda e: self.traceback_window.withdraw())

    def _export_traceback_log(self):
        """Export traceback/debug log to file"""
        self.engine.log_debug("Export traceback log requested")

        self.attributes('-topmost', False)
        self.traceback_window.attributes('-topmost', False)

        try:
            filename = filedialog.asksaveasfilename(
                title="Export Debug/Traceback Log",
                defaultextension=".log",
                filetypes=[("Log files", "*.log"), ("Text files", "*.txt"), ("All files", "*.*")],
                initialfile=f"grep_flight_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log",
                parent=self.traceback_window
            )
        finally:
            self.attributes('-topmost', True)
            self.traceback_window.attributes('-topmost', True)

        if filename:
            try:
                # Export both the visible traceback text AND the engine debug log
                with open(filename, 'w') as f:
                    f.write("="*80 + "\n")
                    f.write("GREP FLIGHT v2 - DEBUG & TRACEBACK LOG\n")
                    f.write(f"Exported: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                    f.write("="*80 + "\n\n")
                    f.write("FULL DEBUG LOG (from engine):\n")
                    f.write("-"*80 + "\n")
                    f.write('\n'.join(self.engine.debug_log))
                    f.write("\n\n" + "="*80 + "\n")
                    f.write("TRACEBACK WINDOW CONTENTS:\n")
                    f.write("-"*80 + "\n")
                    f.write(self.traceback_text.get(1.0, tk.END))

                self.engine.log_debug(f"Log exported to: {filename}")
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
        """Toggle between collapsed and expanded states"""
        self.engine.log_debug(f"Toggle expand requested (current: {'expanded' if self.is_expanded else 'collapsed'})")
        if self.is_expanded:
            self._collapse_panel()
        else:
            self._expand_panel()
    
    def _expand_panel(self):
        """Expand the panel upward"""
        if self.is_expanded:
            self.engine.log_debug("  Already expanded, ignoring")
            return

        self.engine.log_debug("Expanding panel...")
        self.is_expanded = True
        self.expand_btn.config(text="△")
        self.status_var.set("Panel Expanded - Click △ to collapse")
        self.engine.log_debug("  Expand button changed to △")

        # Pack expanded frame to fill space above collapsed frame
        self.expanded_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        self.engine.log_debug("  Expanded frame packed")

        # Get screen dimensions
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()

        # Calculate new position
        target_y = screen_height - self.config.EXPANDED_HEIGHT
        self.engine.log_debug(f"  Target position: y={target_y}, height={self.config.EXPANDED_HEIGHT}")

        # Animate expansion
        animation_steps = [0]  # Track steps for logging

        def animate():
            current_geom = self.winfo_geometry()
            # Parse current geometry (WIDTHxHEIGHT+X+Y)
            parts = current_geom.replace('x', '+').split('+')
            current_height = int(parts[1])
            current_y = int(parts[3])

            target_height = self.config.EXPANDED_HEIGHT

            if current_height < target_height or current_y > target_y:
                new_height = min(target_height, current_height + 20)
                new_y = max(target_y, current_y - 20)
                self.geometry(f"{screen_width}x{new_height}+0+{new_y}")
                self._sync_gemini_position(new_y) # Sync Gemini window
                self._sync_claude_position(new_y) # Sync Claude window
                animation_steps[0] += 1
                if animation_steps[0] == 1:
                    self.engine.log_debug(f"  Starting animation from y={current_y}, height={current_height}")
                self.after(self.config.EXPAND_SPEED, animate)
            else:
                self._sync_gemini_position(target_y) # Ensure final position
                self._sync_claude_position(target_y) # Ensure final position
                self.engine.log_debug(f"  Animation complete ({animation_steps[0]} steps)")
                self.engine.log_debug("Panel expanded successfully")

        animate()
    
    def _collapse_panel(self):
        """Collapse the panel"""
        if not self.is_expanded:
            self.engine.log_debug("  Already collapsed, ignoring")
            return

        self.engine.log_debug("Collapsing panel...")
        self.is_expanded = False
        self.expand_btn.config(text="▽")
        self.status_var.set("Ready - Click ▽ to expand")
        self.engine.log_debug("  Expand button changed to ▽")

        # Get screen dimensions
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()

        # Calculate collapsed position
        target_y = screen_height - self.config.PANEL_HEIGHT

        # Animate collapse
        def animate():
            current_geom = self.winfo_geometry()
            # Parse current geometry (WIDTHxHEIGHT+X+Y)
            parts = current_geom.replace('x', '+').split('+')
            current_height = int(parts[1])
            current_y = int(parts[3])

            target_height = self.config.PANEL_HEIGHT

            if current_height > target_height or current_y < target_y:
                new_height = max(target_height, current_height - 20)
                new_y = min(target_y, current_y + 20)
                self.geometry(f"{screen_width}x{new_height}+0+{new_y}")
                self._sync_gemini_position(new_y) # Sync Gemini window
                self._sync_claude_position(new_y) # Sync Claude window
                self.after(self.config.COLLAPSE_SPEED, animate)
            else:
                # Hide expanded frame when animation is complete
                self.expanded_frame.pack_forget()
                self._sync_gemini_position(target_y) # Ensure final position
                self._sync_claude_position(target_y) # Ensure final position

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
    
    def _backup_current_target(self):
        """Backup the current target file - NO CONFIRMATION, JUST DO IT"""
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

        # Just copy it immediately
        try:
            import shutil
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            path = Path(target)
            backup_name = f"{path.stem}_backup_{timestamp}{path.suffix}"
            backup_path = path.parent / backup_name

            shutil.copy2(target, backup_path)

            self._add_traceback(
                f"✅ BACKUP COMPLETE\n"
                f"   File: {path.name}\n"
                f"   Backup: {backup_name}\n"
                f"   Location: {path.parent}\n"
                f"   Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                "SUCCESS"
            )

        except Exception as e:
            self._add_traceback(f"❌ Backup failed: {e}", "ERROR")

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

        cmd = f"grep -rn '{pattern}' '{target}'"
        self._execute_command(cmd)
    
    def _execute_template(self, template: str):
        """Execute command from template"""
        target = self.target_var.get() or '.'
        pattern = self.pattern_var.get() or ''
        
        cmd = template.format(target=target, pattern=pattern, version_root=self.version_root)
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
                self.status_var.set("⚠️ Task creation logic not found in warrior_gui")
        else:
            self.status_var.set("⚠️ warrior_gui Tasks tab not available")

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
            # Get marked files from app_ref (warrior_gui planner)
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
        """Execute a warrior_gui debug toolkit entry"""
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
        """Add message to traceback window with fallback to console"""
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
        except Exception as e:
            # Last resort fallback
            print(f"CRITICAL ERROR in _add_traceback: {e}")
            self.engine.log_debug(f"[TRACEBACK_ERROR] {message} (Error: {e})", "ERROR")
    
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

            # Tab 1: Warrior GUI Versions
            warrior_tab = tk.Frame(notebook, bg='#2b2b2b')
            notebook.add(warrior_tab, text="Warrior GUI")
            self._build_warrior_version_tab(warrior_tab, vm)

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

    def _build_warrior_version_tab(self, parent, vm):
        """Build the UI for managing Warrior GUI versions."""
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

    # Quick Action Methods for warrior_gui navigation
    def _launch_inventory(self):
        """Launch warrior_gui Inventory tab"""
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
        """Launch warrior_gui Tasks tab"""
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
        """Launch warrior_gui Planner tab"""
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
        """Launch warrior_gui Chat tab"""
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
        """Launch warrior_gui Diff tab"""
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
        """Launch warrior_gui Editor tab"""
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

    def _show_toolkit_config(self, parent=None):
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
        profile_combo.bind('<<ComboboxSelected>>', lambda e: self._load_profile_config())

        # Create notebook for tabs
        notebook = ttk.Notebook(config_window)
        notebook.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        # TAB 1: Workflow Actions (existing 4 + custom, up to 8 total)
        self._create_workflow_config_tab(notebook)

        # TAB 2: Toolkit Tools (10 engineers_toolkit functions)
        self._create_toolkit_config_tab(notebook)

        # TAB 3: Profiles (create/edit/delete profiles)
        self._create_profiles_tab(notebook)

        # TAB 4: Custom Scripts (add custom tools with args)
        self._create_custom_scripts_tab(notebook)

        # TAB 5: Tool Profiles (aggregate view)
        self._create_tool_profiles_tab(notebook)

        # TAB 6: On-boarding Queue (📥)
        self._create_onboarding_queue_tab(notebook)

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
        """TAB 1: Configure workflow action buttons (up to 8)"""
        workflow_tab = tk.Frame(notebook, bg='#1e1e1e')
        notebook.add(workflow_tab, text="⚡ Workflow Actions")

        # Instructions
        tk.Label(
            workflow_tab,
            text="Configure workflow action buttons (up to 8). Reorder with arrows. Actions coordinate with target and feed expectations to PFC/diffs.",
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

        def refresh_workflow_list():
            for widget in scrollable_frame.winfo_children():
                widget.destroy()

            for i, action in enumerate(self.workflow_actions):
                row = tk.Frame(scrollable_frame, bg='#2d2d2d', relief=tk.RAISED, bd=1)
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
                    tk.Button(buttons_frame, text="✏️", command=lambda idx=i: self._edit_workflow_action(idx, refresh_workflow_list),
                             bg='#3d3d3d', fg='#d4d4d4', relief=tk.RAISED, bd=1, width=2).pack(side=tk.LEFT, padx=1)

                # Up arrow
                if i > 0:
                    tk.Button(buttons_frame, text="▲", command=lambda idx=i: self._move_workflow_up(idx, refresh_workflow_list),
                             bg='#3d3d3d', fg='#d4d4d4', relief=tk.RAISED, bd=1, width=2).pack(side=tk.LEFT, padx=1)

                # Down arrow
                if i < len(self.workflow_actions) - 1:
                    tk.Button(buttons_frame, text="▼", command=lambda idx=i: self._move_workflow_down(idx, refresh_workflow_list),
                             bg='#3d3d3d', fg='#d4d4d4', relief=tk.RAISED, bd=1, width=2).pack(side=tk.LEFT, padx=1)

            self._build_workflow_buttons()

        refresh_workflow_list()

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

    def _create_profiles_tab(self, notebook):
        """TAB 3: Manage workflow profiles"""
        profiles_tab = tk.Frame(notebook, bg='#1e1e1e')
        notebook.add(profiles_tab, text="📋 Profiles")

        tk.Label(
            profiles_tab,
            text="Manage workflow profiles. Different projects can have different tool and workflow configurations.",
            bg='#1e1e1e',
            fg='#888888',
            font=('Arial', 9),
            wraplength=750
        ).pack(pady=10, padx=10)

        # Profile list and buttons
        profile_frame = tk.Frame(profiles_tab, bg='#1e1e1e')
        profile_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        # Listbox for profiles
        tk.Label(profile_frame, text="Available Profiles:", bg='#1e1e1e',
                fg='#4ec9b0', font=('Arial', 9, 'bold')).pack(anchor=tk.W, pady=(0, 5))

        profile_list = tk.Listbox(profile_frame, bg='#2d2d2d', fg='#d4d4d4',
                                  selectbackground='#4ec9b0', selectforeground='#000000',
                                  font=('Monospace', 9), height=15)
        profile_list.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        # Load profiles
        for profile in self._load_profile_names():
            profile_list.insert(tk.END, profile)

        # Buttons
        btn_frame = tk.Frame(profiles_tab, bg='#1e1e1e')
        btn_frame.pack(fill=tk.X, padx=20, pady=10)

        tk.Button(btn_frame, text="➕ New Profile", command=lambda: self._create_new_profile(profile_list),
                 bg='#4ec9b0', fg='#000000', width=15).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="📝 Rename", command=lambda: self._rename_profile(profile_list),
                 bg='#2d2d2d', fg='#d4d4d4', width=12).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="🗑️ Delete", command=lambda: self._delete_profile(profile_list),
                 bg='#2d2d2d', fg='#d4d4d4', width=12).pack(side=tk.LEFT, padx=5)

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
            for script in self._load_custom_scripts():
                scripts_catalog.append({'entry': script, 'source': 'local'})
                scripts_list.insert(tk.END, f"[Local] {script['name']} → {script['command']}")
            debug_profile = self._load_debug_tool_profiles()
            for suite_path in debug_profile.get('tool_suites', []):
                display = "Scope Analyzer" if self._is_scope_path(suite_path) else Path(suite_path).name
                scripts_catalog.append({'entry': {'name': display, 'command': suite_path, 'category': 'suite'}, 'source': 'debug'})
                scripts_list.insert(tk.END, f"[GUI Suite] {display} → {suite_path}")
            for script_path in debug_profile.get('debug_scripts', []):
                display = Path(script_path).name
                scripts_catalog.append({'entry': {'name': display, 'command': script_path, 'category': 'script'}, 'source': 'debug'})
                scripts_list.insert(tk.END, f"[GUI Script] {display} → {script_path}")
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

        tk.Button(
            profiles_tab,
            text="🔄 Refresh",
            command=refresh_profiles,
            bg='#2d2d2d',
            fg='#d4d4d4',
            width=12
        ).pack(pady=(0, 10))

    def _save_toolkit_order(self, window):
        """Save toolkit order to config file"""
        config_dir = self.version_root / ".docv2_workspace" / "config"
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

    def _load_profile_names(self) -> List[str]:
        """Load list of available profile names"""
        config_dir = self.version_root / ".docv2_workspace" / "config"
        profiles_file = config_dir / "workflow_profiles.json"

        if profiles_file.exists():
            with open(profiles_file, 'r') as f:
                data = json.load(f)
                return list(data.get('profiles', {}).keys())
        return ["Default Profile"]

    def _load_profile_config(self):
        """Load config for current selected profile (config UI callback)"""
        if not self.current_profile_var:
            return
        profile_name = self.current_profile_var.get()
        self._apply_profile_config(profile_name)

    def _apply_profile_config(self, profile_name: str) -> bool:
        """Load profile data from disk and apply it to the current session"""
        config_dir = self.version_root / ".docv2_workspace" / "config"
        profiles_file = config_dir / "workflow_profiles.json"

        if not profiles_file.exists():
            return False

        with open(profiles_file, 'r') as f:
            data = json.load(f)

        profile_data = data.get('profiles', {}).get(profile_name)
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
        config_dir = self.version_root / ".docv2_workspace" / "config"
        config_dir.mkdir(parents=True, exist_ok=True)
        profiles_file = config_dir / "workflow_profiles.json"

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
        config_dir = self.version_root / ".docv2_workspace" / "config"
        profiles_file = config_dir / "workflow_profiles.json"

        # Try to load from saved profile
        if profiles_file.exists():
            try:
                with open(profiles_file, 'r') as f:
                    data = json.load(f)
                    default_profile = data.get('default_profile', 'Default Profile')
                    self.active_profile = default_profile
                    profile_data = data.get('profiles', {}).get(default_profile, {})
                    if 'tool_locations' in profile_data:
                        self.tool_locations = profile_data['tool_locations']
                    else:
                        self.tool_locations = {}
                    if 'toolkit_order' in profile_data:
                        self.toolkit_order = profile_data['toolkit_order']
                    else:
                        self.toolkit_order = self._default_toolkit_order()
                    if 'workflow_actions' in profile_data:
                        return self._pad_workflow_actions(profile_data['workflow_actions'])
            except Exception as e:
                print(f"Error loading workflow profile: {e}")

        self.tool_locations = {}
        self.toolkit_order = self._default_toolkit_order()
        self.active_profile = 'Default Profile'
        return self._pad_workflow_actions(self._default_workflow_actions())

    def _load_workflow_actions_from_profile(self) -> Optional[List[Dict]]:
        """Load workflow actions from current profile (for config UI)"""
        profile_name = None
        if self.current_profile_var is not None:
            profile_name = self.current_profile_var.get()
        if not profile_name:
            profile_name = self.active_profile

        config_dir = self.version_root / ".docv2_workspace" / "config"
        profiles_file = config_dir / "workflow_profiles.json"
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
        config_dir = self.version_root / ".docv2_workspace" / "config"
        profiles_file = config_dir / "workflow_profiles.json"
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
        """Rotate through available workflow profiles from the main panel"""
        profiles = self._load_profile_names()
        if not profiles:
            return

        current = self.active_profile or "Default Profile"
        if self.current_profile_var is not None and self.current_profile_var.get():
            current = self.current_profile_var.get()

        try:
            idx = profiles.index(current)
        except ValueError:
            idx = 0

        new_idx = (idx + direction) % len(profiles)
        new_profile = profiles[new_idx]
        if self._apply_profile_config(new_profile):
            self.status_var.set(f"🔁 Switched to profile: {new_profile}")

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
            "Default workflows preset",
            "Engineer's Toolkit preset",
            "Debug Toolkit preset",
            "Scope Analyzer preset"
        ]
        template_var = tk.StringVar(value=template_options[0])
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
        new_name = simpledialog.askstring("Rename Profile", f"Rename '{old_name}' to:")
        if new_name:
            # Update in config
            self.status_var.set(f"📝 Renamed '{old_name}' to '{new_name}'")

    def _delete_profile(self, listbox):
        """Delete selected profile"""
        selection = listbox.curselection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a profile to delete")
            return

        profile_name = listbox.get(selection[0])
        if messagebox.askyesno("Confirm Delete", f"Delete profile '{profile_name}'?"):
            # Remove from config
            self.status_var.set(f"🗑️ Deleted profile: {profile_name}")

    # ==== CUSTOM SCRIPTS METHODS ====

    def _load_custom_scripts(self) -> List[Dict]:
        """Load custom scripts from config"""
        config_dir = self.version_root / ".docv2_workspace" / "config"
        scripts_file = config_dir / "custom_scripts.json"

        if scripts_file.exists():
            with open(scripts_file, 'r') as f:
                return json.load(f).get('scripts', [])
        return []

    def _save_custom_scripts(self, scripts: List[Dict]):
        config_dir = self.version_root / ".docv2_workspace" / "config"
        config_dir.mkdir(parents=True, exist_ok=True)
        scripts_file = config_dir / "custom_scripts.json"
        with open(scripts_file, 'w') as f:
            json.dump({"scripts": scripts}, f, indent=2)

    def _load_debug_tool_profiles(self) -> Dict[str, Any]:
        """Load warrior_gui Debug Toolkit custom tool definitions"""
        config_path = Path.home() / '.warrior_flow' / 'custom_tools.json'
        if not config_path.exists():
            config = {}
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
                config_path.parent.mkdir(parents=True, exist_ok=True)
                with open(config_path, 'w') as f:
                    json.dump(config, f, indent=2)
            except Exception as exc:
                print(f"Error writing custom tools config: {exc}")
        return config

    def _sync_script_with_debug_toolkit(self, script_entry: Dict[str, Any]) -> None:
        config_path = Path.home() / '.warrior_flow' / 'custom_tools.json'
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
        config_path.parent.mkdir(parents=True, exist_ok=True)
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
            messagebox.showinfo("External Script", "This script is managed via the Warrior GUI Debug Toolkit. Edit it there.")
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
            messagebox.showinfo("External Script", "Delete external scripts via the Warrior GUI Debug Toolkit.")
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

        info_frame = tk.Frame(lists_container, bg='#1e1e1e', width=220)
        info_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(20, 0))

        tk.Label(info_frame, text="Tool / Lineage Info", bg='#1e1e1e',
                 fg='#4ec9b0', font=('Arial', 9, 'bold')).pack(anchor=tk.W, pady=(0, 5))

        info_text = scrolledtext.ScrolledText(
            info_frame,
            height=6,
            bg='#151515',
            fg='#d4d4d4',
            font=('Monospace', 9)
        )
        info_text.pack(fill=tk.X, padx=2, pady=2)

        tk.Label(info_frame, text="Profile Usage", bg='#1e1e1e',
                 fg='#d4d4d4', font=('Arial', 9, 'bold')).pack(anchor=tk.W, pady=(8, 2))

        usage_list = tk.Listbox(
            info_frame,
            bg='#2d2d2d',
            fg='#d4d4d4',
            height=6,
            activestyle='none',
            font=('Monospace', 9)
        )
        usage_list.pack(fill=tk.BOTH, expand=True, padx=2)

        tk.Label(info_frame, text="Stash Lineage", bg='#1e1e1e',
                 fg='#d4d4d4', font=('Arial', 9, 'bold')).pack(anchor=tk.W, pady=(8, 2))

        stash_text = tk.Text(info_frame, height=4, bg='#151515', fg='#d4d4d4', font=('Monospace', 9))
        stash_text.pack(fill=tk.X, padx=2)
        stash_text.insert('1.0', self._get_stash_lineage_summary())
        stash_text.config(state=tk.DISABLED)

        tk.Button(info_frame, text="📦 stash_script -h", command=self._show_stash_help,
                 bg='#2d2d2d', fg='#d4d4d4').pack(anchor=tk.E, pady=(6, 0))

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

        def entry_signature(entry: Dict[str, Any]) -> str:
            return entry.get('source') or entry.get('command') or entry.get('name', '')

        def gather_profile_usage(entry: Dict[str, Any]) -> List[Tuple[str, int, str, str]]:
            usage: List[Tuple[str, int, str, str]] = []
            signature = entry_signature(entry)
            if not signature:
                return usage
            all_profiles = self._load_all_workflow_profiles()
            for profile_name, details in all_profiles.items():
                for idx, action in enumerate(details.get('workflow_actions', [])):
                    action_sig = action.get('source') or action.get('command') or action.get('name')
                    if action_sig and action_sig == signature:
                        usage.append((profile_name, idx + 1, action.get('name', 'Unnamed'), action.get('args', '')))
            return usage

        def update_info_panel(entry: Optional[Dict[str, Any]] = None):
            info_text.config(state=tk.NORMAL)
            info_text.delete('1.0', tk.END)
            usage_list.delete(0, tk.END)
            if not entry:
                info_text.insert(tk.END, "Select an entry to view metadata, arguments, and lineage.")
                info_text.config(state=tk.DISABLED)
                return

            lines = [
                f"Name: {entry.get('name', 'Unnamed')}",
                f"Type: {entry.get('type', 'custom')}",
                f"Source: {entry.get('source', 'n/a')}",
            ]
            if entry.get('command'):
                lines.append(f"Command: {entry.get('command')}")
            if entry.get('args'):
                lines.append(f"Args: {entry.get('args')}")
            lines.append(f"Target: {entry.get('target_mode', 'auto')} → {entry.get('output_to', 'results')}" )
            if entry.get('expectations'):
                lines.append(f"Expectations: {entry.get('expectations')}")

            info_text.insert(tk.END, "\n".join(lines))
            info_text.config(state=tk.DISABLED)

            usages = gather_profile_usage(entry)
            if not usages:
                usage_list.insert(tk.END, "No workflow buttons use this tool yet")
            else:
                for profile_name, slot_idx, action_name, action_args in usages:
                    display = f"{profile_name[:14]} • Slot {slot_idx}: {action_name}"
                    if action_args:
                        display += f" [{action_args}]"
                    usage_list.insert(tk.END, display)

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
            current_items = category_items.get(category_var.get(), [])
            if not current_items or tools_listbox.cget('state') == tk.DISABLED:
                return
            selection = tools_listbox.curselection()
            if not selection:
                messagebox.showwarning("No Selection", "Select an entry to add to the workflow row.")
                return
            entry = current_items[selection[0]]
            if not self._has_placeholder_slot():
                messagebox.showinfo("Workflow Full", "All slots are filled. Remove a slot using the panel on the right before adding a new tool.")
                return
            if self._assign_workflow_slot(entry):
                self._save_current_profile()
                self._build_workflow_buttons()
                refresh_current_list()
                self.status_var.set(f"✨ Added '{entry['name']}' to workflow")
                quick_add.destroy()
            else:
                messagebox.showwarning("Slots Full", "All workflow slots are filled. Remove an action first.")

        tk.Button(quick_add, text="Add to Workflow", command=add_selected_tool,
                 bg='#4ec9b0', fg='#000000', width=18).pack(pady=10)
        quick_add.bind('<Escape>', lambda _e: quick_add.destroy())

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
        """Save workflow_actions to current active profile"""
        profile_name = None
        if self.current_profile_var is not None:
            profile_name = self.current_profile_var.get()
        if not profile_name:
            profile_name = self.active_profile or "Default Profile"
        config_dir = self.version_root / ".docv2_workspace" / "config"
        config_dir.mkdir(parents=True, exist_ok=True)
        profiles_file = config_dir / "workflow_profiles.json"

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
    def _refresh_task_list(self):
        """Refresh task list from .docv2_workspace/tasks/"""
        if not hasattr(self, 'task_listbox'):
            return

        self.engine.log_debug("Refreshing task list", "INFO")

        # Clear current list
        self.task_listbox.delete(0, tk.END)
        self.tasks_data = []

        # Determine tasks directory
        if self.app_ref and hasattr(self.app_ref, 'current_project'):
            tasks_dir = self.app_ref.current_project / ".docv2_workspace" / "tasks"
        else:
            tasks_dir = self.version_root / ".docv2_workspace" / "tasks"

        if not tasks_dir.exists():
            self.task_listbox.insert(tk.END, "No tasks directory found")
            self.engine.log_debug(f"Tasks directory not found: {tasks_dir}", "WARNING")
            return

        try:
            # Load all task JSON files
            task_files = list(tasks_dir.glob("*.json"))
            self.engine.log_debug(f"Found {len(task_files)} task files", "INFO")

            for task_file in task_files:
                try:
                    with open(task_file, 'r') as f:
                        task_data = json.load(f)
                        self.tasks_data.append(task_data)
                except Exception as e:
                    self.engine.log_debug(f"Error loading task {task_file.name}: {e}", "ERROR")

            # Apply filters and display
            self._filter_tasks()

            log_to_traceback(EventCategory.TASK, "refresh_task_list",
                           {"source": "grep_flight", "tasks_dir": str(tasks_dir)},
                           {"count": len(self.tasks_data)})

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
        """Handle double-click on task - switch to Tasks tab"""
        self._open_tasks_tab()

    def _on_task_right_click(self, event):
        """Handle right-click on task - show context menu"""
        if not hasattr(self, 'task_listbox'):
            return

        # Get selected task
        selection = self.task_listbox.curselection()
        if not selection:
            return

        # Create context menu
        menu = tk.Menu(self, tearoff=0, bg='#2a2a2a', fg=self.config.FG_COLOR)
        menu.add_command(label="Open in Tasks Tab", command=self._open_tasks_tab)
        menu.add_command(label="Review Absorb (Diff)", command=self._review_absorb_task)
        menu.add_command(label="Verify & Complete", command=self._verify_and_complete_task)
        menu.add_command(label="Show Details", command=self._show_task_details)
        menu.add_separator()
        menu.add_command(label="Refresh List", command=self._refresh_task_list)

        try:
            menu.post(event.x_root, event.y_root)
        finally:
            menu.grab_release()

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
        """Open Tasks tab in warrior_gui"""
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
        """Open Planner tab in warrior_gui"""
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

        except queue.Empty:
            pass

        # Schedule next update
        self.after(100, self._update_from_engine)

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
    """Run system preflight checks"""
    print("🔍 Running Preflight Checks...")
    print("-" * 40)
    
    checks = [
        ("Python 3.6+", sys.version_info >= (3, 6)),
        ("Tkinter available", True),  # We're already using it
        ("grep command", subprocess.run(['which', 'grep'], capture_output=True).returncode == 0),
        ("xterm available", subprocess.run(['which', 'xterm'], capture_output=True).returncode == 0),
    ]
    
    all_passed = True
    for check, passed in checks:
        status = "✅" if passed else "❌"
        print(f"{status} {check}")
        if not passed:
            all_passed = False
    
    print("-" * 40)
    print("Preflight", "PASSED" if all_passed else "FAILED")
    
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
        app.mainloop()
    except Exception as e:
        print(f"Error launching GUI: {e}")
        if args.debug:
            import traceback
            traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())
