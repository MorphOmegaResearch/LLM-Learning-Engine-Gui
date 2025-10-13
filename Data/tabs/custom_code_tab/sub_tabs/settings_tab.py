# [SYSTEM: GUI | VERSION: 1.9f | STATUS: ACTIVE]
"""
Settings Sub-Tab - Backend configuration for Custom Code features
Controls working directory, tool execution, chat behavior, and project settings
Uses unified Tool Profile system for persistence.
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
import json
import sys
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from tabs.base_tab import BaseTab
from logger_util import log_message
from config import (
    list_tool_profiles,
    load_tool_profile,
    save_tool_profile,
    get_unified_tool_profile,
    TOOL_PROFILES_DIR
)


class SettingsTab(BaseTab):
    """Settings configuration interface for Custom Code tab"""

    def __init__(self, parent, root, style, parent_tab):
        super().__init__(parent, root, style)
        self.parent_tab = parent_tab

        # Unified Tool Profile integration
        self.current_profile_name = tk.StringVar(value="Default")
        self.profile = self.load_profile()
        self.settings = self.extract_settings_from_profile()

    def create_ui(self):
        """Create the settings interface UI with nested tabs"""
        log_message("CC_SETTINGS: Creating UI...")

        self.parent.columnconfigure(0, weight=1)
        self.parent.rowconfigure(0, weight=1)

        # Create notebook for sub-sub-tabs
        self.settings_notebook = ttk.Notebook(self.parent)
        self.settings_notebook.grid(row=0, column=0, sticky=tk.NSEW, padx=5, pady=5)

        # Basic Settings Sub-Sub-Tab
        self.basic_frame = ttk.Frame(self.settings_notebook)
        self.settings_notebook.add(self.basic_frame, text="⚙️ Basic")
        self.create_basic_settings(self.basic_frame)

        # Mode Selector Sub-Sub-Tab (positioned between Basic and Advanced)
        self.mode_frame = ttk.Frame(self.settings_notebook)
        self.settings_notebook.add(self.mode_frame, text="🎯 Mode")
        self.create_mode_selector(self.mode_frame)

        # Advanced Settings Sub-Sub-Tab
        self.advanced_frame = ttk.Frame(self.settings_notebook)
        self.settings_notebook.add(self.advanced_frame, text="🔧 Advanced")
        self.create_advanced_settings(self.advanced_frame)

        # Bind tab change event to refresh Advanced tab when switched to
        self.settings_notebook.bind("<<NotebookTabChanged>>", self._on_settings_tab_changed)

        log_message("CC_SETTINGS: UI created successfully")

    def _on_settings_tab_changed(self, event=None):
        """Called when user switches between Basic/Mode/Advanced tabs"""
        try:
            # Get currently selected tab
            current_tab_index = self.settings_notebook.index(self.settings_notebook.select())

            # Advanced tab is index 2 (Basic=0, Mode=1, Advanced=2)
            if current_tab_index == 2:
                # User switched to Advanced tab - refresh to show current mode
                if hasattr(self, 'advanced_settings_interface') and self.advanced_settings_interface:
                    if hasattr(self.advanced_settings_interface, 'refresh'):
                        log_message("CC_SETTINGS: Refreshing Advanced tab after tab switch")
                        self.advanced_settings_interface.refresh()
        except Exception as e:
            log_message(f"CC_SETTINGS ERROR: Failed to handle tab change: {e}")

    def create_basic_settings(self, parent):
        """Create basic settings content"""
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(0, weight=0)  # Profile picker
        parent.rowconfigure(1, weight=0)  # Header
        parent.rowconfigure(2, weight=1)  # Scrollable content
        parent.rowconfigure(3, weight=0)  # Buttons

        # Profile Picker
        self.create_profile_picker(parent, row=0)

        # Header
        header_frame = ttk.Frame(parent, style='Category.TFrame')
        header_frame.grid(row=1, column=0, sticky=tk.EW, padx=10, pady=10)

        ttk.Label(
            header_frame,
            text="⚙️ Basic Settings",
            font=("Arial", 12, "bold"),
            style='CategoryPanel.TLabel'
        ).pack(side=tk.LEFT, padx=(0, 10))

        ttk.Button(
            header_frame,
            text="🔄 Reset to Defaults",
            command=self.reset_to_defaults,
            style='Select.TButton'
        ).pack(side=tk.RIGHT)

        # Scrollable content area
        self.create_scrollable_content(parent, row=2)

        # Bottom buttons
        self.create_button_bar(parent, row=3)

    def create_mode_selector(self, parent):
        """Create mode selector sub-sub-tab"""
        from .mode_selector_tab import ModeSelectorTab

        self.mode_selector_interface = ModeSelectorTab(parent, self.root, self.style, self.parent_tab)
        self.mode_selector_interface.safe_create()

    def create_advanced_settings(self, parent):
        """Create advanced settings sub-sub-tab"""
        from .advanced_settings_tab import AdvancedSettingsTab

        self.advanced_settings_interface = AdvancedSettingsTab(parent, self.root, self.style, self.parent_tab)
        self.advanced_settings_interface.safe_create()

    def on_mode_changed(self, new_mode):
        """Called when mode changes - notify advanced settings tab"""
        if hasattr(self, 'advanced_settings_interface') and self.advanced_settings_interface:
            if hasattr(self.advanced_settings_interface, 'on_mode_changed'):
                self.advanced_settings_interface.on_mode_changed(new_mode)

    def create_profile_picker(self, parent, row=0):
        """Create profile picker UI at the top"""
        picker_frame = ttk.LabelFrame(
            parent,
            text="📋 Tool Profile",
            style='TLabelframe'
        )
        picker_frame.grid(row=row, column=0, sticky=tk.EW, padx=10, pady=10)
        picker_frame.columnconfigure(1, weight=1)

        # Profile dropdown
        ttk.Label(
            picker_frame,
            text="Active Profile:",
            style='Config.TLabel',
            font=("Arial", 9, "bold")
        ).grid(row=0, column=0, sticky=tk.W, padx=10, pady=10)

        self.profile_combo = ttk.Combobox(
            picker_frame,
            textvariable=self.current_profile_name,
            values=list_tool_profiles(),
            state='readonly',
            font=("Arial", 9),
            width=25
        )
        self.profile_combo.grid(row=0, column=1, sticky=tk.W, padx=(0, 5), pady=10)
        self.profile_combo.bind('<<ComboboxSelected>>', self.on_profile_changed)

        # Profile management buttons
        btn_frame = ttk.Frame(picker_frame, style='Category.TFrame')
        btn_frame.grid(row=0, column=2, sticky=tk.E, padx=10, pady=10)

        ttk.Button(
            btn_frame,
            text="➕ New",
            command=self.create_profile,
            style='Action.TButton',
            width=8
        ).pack(side=tk.LEFT, padx=2)

        ttk.Button(
            btn_frame,
            text="✏️ Rename",
            command=self.rename_profile,
            style='Select.TButton',
            width=8
        ).pack(side=tk.LEFT, padx=2)

        ttk.Button(
            btn_frame,
            text="🗑️ Delete",
            command=self.delete_profile,
            style='Action.TButton',
            width=8
        ).pack(side=tk.LEFT, padx=2)

    def create_scrollable_content(self, parent, row=1):
        """Create scrollable content area with all settings"""
        container = ttk.Frame(parent, style='Category.TFrame')
        container.grid(row=row, column=0, sticky=tk.NSEW, padx=10, pady=(0, 10))
        container.columnconfigure(0, weight=1)
        container.rowconfigure(0, weight=1)

        # Canvas for scrolling
        canvas = tk.Canvas(
            container,
            bg='#2b2b2b',
            highlightthickness=0
        )
        scrollbar = ttk.Scrollbar(
            container,
            orient="vertical",
            command=canvas.yview
        )
        self.scroll_frame = ttk.Frame(canvas, style='Category.TFrame')

        self.scroll_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas_window = canvas.create_window(
            (0, 0),
            window=self.scroll_frame,
            anchor="nw"
        )
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.bind(
            "<Configure>",
            lambda e: canvas.itemconfig(canvas_window, width=e.width)
        )

        canvas.grid(row=0, column=0, sticky=tk.NSEW)
        scrollbar.grid(row=0, column=1, sticky=tk.NS)

        # Enable mousewheel scrolling
        self.bind_mousewheel_to_canvas(canvas)

        # Add all settings sections
        self.create_working_directory_section()
        self.create_tool_execution_section()
        self.create_training_mode_section()
        self.create_chat_behavior_section()
        self.create_project_settings_section()
        self.create_advanced_settings_section()

    def create_working_directory_section(self):
        """Working Directory Management"""
        frame = ttk.LabelFrame(
            self.scroll_frame,
            text="📁 Working Directory",
            style='TLabelframe'
        )
        frame.pack(fill=tk.X, padx=10, pady=10)

        # Current working directory display
        ttk.Label(
            frame,
            text="Current Working Directory:",
            style='Config.TLabel',
            font=("Arial", 9, "bold")
        ).grid(row=0, column=0, sticky=tk.W, padx=10, pady=(10, 5))

        wd_frame = ttk.Frame(frame, style='Category.TFrame')
        wd_frame.grid(row=1, column=0, sticky=tk.EW, padx=10, pady=(0, 5))
        wd_frame.columnconfigure(0, weight=1)

        self.working_dir_var = tk.StringVar(value=self.settings.get('working_directory', str(Path.cwd())))
        working_dir_entry = ttk.Entry(
            wd_frame,
            textvariable=self.working_dir_var,
            font=("Arial", 9),
            state='readonly'
        )
        working_dir_entry.grid(row=0, column=0, sticky=tk.EW, padx=(0, 5))

        ttk.Button(
            wd_frame,
            text="Browse...",
            command=self.browse_working_directory,
            style='Action.TButton'
        ).grid(row=0, column=1)

        # Auto-update working directory
        self.auto_update_wd_var = tk.BooleanVar(value=self.settings.get('auto_update_working_dir', False))
        ttk.Checkbutton(
            frame,
            text="Automatically update working directory when changing projects",
            variable=self.auto_update_wd_var,
            style='TCheckbutton'
        ).grid(row=2, column=0, sticky=tk.W, padx=10, pady=(0, 10))

    def create_tool_execution_section(self):
        """Tool Execution Preferences"""
        frame = ttk.LabelFrame(
            self.scroll_frame,
            text="🔧 Tool Execution",
            style='TLabelframe'
        )
        frame.pack(fill=tk.X, padx=10, pady=10)

        # Confirmation gates
        ttk.Label(
            frame,
            text="Confirmation Requirements:",
            style='Config.TLabel',
            font=("Arial", 9, "bold")
        ).grid(row=0, column=0, sticky=tk.W, padx=10, pady=(10, 5))

        self.confirm_high_risk_var = tk.BooleanVar(value=self.settings.get('confirm_high_risk_tools', True))
        ttk.Checkbutton(
            frame,
            text="Require confirmation for HIGH risk tools (file_delete, etc.)",
            variable=self.confirm_high_risk_var,
            style='TCheckbutton'
        ).grid(row=1, column=0, sticky=tk.W, padx=20, pady=2)

        self.confirm_critical_var = tk.BooleanVar(value=self.settings.get('confirm_critical_tools', True))
        ttk.Checkbutton(
            frame,
            text="Require confirmation for CRITICAL risk tools (bash_execute)",
            variable=self.confirm_critical_var,
            style='TCheckbutton'
        ).grid(row=2, column=0, sticky=tk.W, padx=20, pady=2)

        # Tool timeouts
        ttk.Label(
            frame,
            text="Tool Execution Timeout (seconds):",
            style='Config.TLabel',
            font=("Arial", 9)
        ).grid(row=3, column=0, sticky=tk.W, padx=10, pady=(10, 5))

        self.tool_timeout_var = tk.StringVar(value=str(self.settings.get('tool_timeout', 30)))
        ttk.Entry(
            frame,
            textvariable=self.tool_timeout_var,
            font=("Arial", 9),
            width=10
        ).grid(row=4, column=0, sticky=tk.W, padx=20, pady=(0, 5))

        # Logging
        self.log_tool_execution_var = tk.BooleanVar(value=self.settings.get('log_tool_execution', True))
        ttk.Checkbutton(
            frame,
            text="Log all tool executions to file",
            variable=self.log_tool_execution_var,
            style='TCheckbutton'
        ).grid(row=5, column=0, sticky=tk.W, padx=10, pady=(5, 10))

    def create_training_mode_section(self):
        """Training Mode Settings"""
        frame = ttk.LabelFrame(
            self.scroll_frame,
            text="📊 Training Data Collection",
            style='TLabelframe'
        )
        frame.pack(fill=tk.X, padx=10, pady=10)

        # Training Mode toggle
        self.training_mode_var = tk.BooleanVar(value=self.settings.get('training_mode_enabled', False))
        ttk.Checkbutton(
            frame,
            text="Enable Training Mode (logs all tool calls for training data)",
            variable=self.training_mode_var,
            style='TCheckbutton',
            command=self.on_training_mode_toggled
        ).grid(row=0, column=0, sticky=tk.W, padx=10, pady=(10, 5))

        # Warning label
        ttk.Label(
            frame,
            text="⚠️ Note: Training Mode uses additional resources to log interactions",
            style='Config.TLabel',
            font=("Arial", 8),
            foreground='#ff8800'
        ).grid(row=1, column=0, sticky=tk.W, padx=10, pady=(0, 5))

        # Status label
        self.training_status_label = ttk.Label(
            frame,
            text="Status: Disabled",
            style='Config.TLabel',
            font=("Arial", 9)
        )
        self.training_status_label.grid(row=2, column=0, sticky=tk.W, padx=10, pady=(0, 10))

        # Update status label
        self.update_training_status_label()

    def on_training_mode_toggled(self):
        """Handle training mode toggle"""
        enabled = self.training_mode_var.get()
        log_message(f"CC_SETTINGS: Training mode {'enabled' if enabled else 'disabled'}")

        # Update status label
        self.update_training_status_label()

        # Notify parent tab if it has a method to handle training mode changes
        if hasattr(self.parent_tab, 'set_training_mode'):
            self.parent_tab.set_training_mode(enabled)

    def update_training_status_label(self):
        """Update training mode status label"""
        if self.training_mode_var.get():
            self.training_status_label.config(
                text="Status: ✅ Active - Logging tool calls",
                foreground='#00ff00'
            )
        else:
            self.training_status_label.config(
                text="Status: ⭕ Disabled",
                foreground='#888888'
            )

    def create_chat_behavior_section(self):
        """Chat Behavior Settings"""
        frame = ttk.LabelFrame(
            self.scroll_frame,
            text="💬 Chat Behavior",
            style='TLabelframe'
        )
        frame.pack(fill=tk.X, padx=10, pady=10)

        # Auto-mount
        self.auto_mount_var = tk.BooleanVar(value=self.settings.get('auto_mount_model', False))
        ttk.Checkbutton(
            frame,
            text="Automatically mount model when selected",
            variable=self.auto_mount_var,
            style='TCheckbutton'
        ).grid(row=0, column=0, sticky=tk.W, padx=10, pady=(10, 5))

        # Auto-save history
        self.auto_save_history_var = tk.BooleanVar(value=self.settings.get('auto_save_history', True))
        ttk.Checkbutton(
            frame,
            text="Automatically save conversation history",
            variable=self.auto_save_history_var,
            style='TCheckbutton'
        ).grid(row=1, column=0, sticky=tk.W, padx=10, pady=5)

        # History retention
        ttk.Label(
            frame,
            text="History Retention (days, 0 = forever):",
            style='Config.TLabel',
            font=("Arial", 9)
        ).grid(row=2, column=0, sticky=tk.W, padx=10, pady=(10, 5))

        self.history_retention_var = tk.StringVar(value=str(self.settings.get('history_retention_days', 0)))
        ttk.Entry(
            frame,
            textvariable=self.history_retention_var,
            font=("Arial", 9),
            width=10
        ).grid(row=3, column=0, sticky=tk.W, padx=20, pady=(0, 5))

        # Max message length
        ttk.Label(
            frame,
            text="Max Message Length (characters, 0 = unlimited):",
            style='Config.TLabel',
            font=("Arial", 9)
        ).grid(row=4, column=0, sticky=tk.W, padx=10, pady=(10, 5))

        self.max_message_length_var = tk.StringVar(value=str(self.settings.get('max_message_length', 0)))
        ttk.Entry(
            frame,
            textvariable=self.max_message_length_var,
            font=("Arial", 9),
            width=10
        ).grid(row=5, column=0, sticky=tk.W, padx=20, pady=(0, 10))

        # Temperature control
        temp_frame = ttk.Frame(frame, style='Category.TFrame')
        temp_frame.grid(row=6, column=0, sticky=tk.EW, padx=10, pady=(10, 5))
        temp_frame.columnconfigure(1, weight=1)

        self.temp_label = ttk.Label(
            temp_frame,
            text=f"Temperature: {self.settings.get('temperature', 0.8):.1f}",
            style='Config.TLabel',
            font=("Arial", 9, "bold")
        )
        self.temp_label.grid(row=0, column=0, sticky=tk.W)

        self.temperature_var = tk.DoubleVar(value=self.settings.get('temperature', 0.8))
        temp_scale = ttk.Scale(
            temp_frame,
            from_=0.0,
            to=2.0,
            orient=tk.HORIZONTAL,
            variable=self.temperature_var,
            command=self.update_temp_label
        )
        temp_scale.grid(row=0, column=1, sticky=tk.EW, padx=(10, 0))

    def update_temp_label(self, value):
        self.temp_label.config(text=f"Temperature: {float(value):.1f}")

    def create_project_settings_section(self):
        """Project Workspace Settings"""
        frame = ttk.LabelFrame(
            self.scroll_frame,
            text="📁 Project Settings",
            style='TLabelframe'
        )
        frame.pack(fill=tk.X, padx=10, pady=10)

        # Default project directory
        ttk.Label(
            frame,
            text="Default Project Directory:",
            style='Config.TLabel',
            font=("Arial", 9, "bold")
        ).grid(row=0, column=0, sticky=tk.W, padx=10, pady=(10, 5))

        proj_frame = ttk.Frame(frame, style='Category.TFrame')
        proj_frame.grid(row=1, column=0, sticky=tk.EW, padx=10, pady=(0, 5))
        proj_frame.columnconfigure(0, weight=1)

        self.project_dir_var = tk.StringVar(value=self.settings.get('default_project_dir', str(Path.home() / "Projects")))
        ttk.Entry(
            proj_frame,
            textvariable=self.project_dir_var,
            font=("Arial", 9),
            state='readonly'
        ).grid(row=0, column=0, sticky=tk.EW, padx=(0, 5))

        ttk.Button(
            proj_frame,
            text="Browse...",
            command=self.browse_project_directory,
            style='Action.TButton'
        ).grid(row=0, column=1)

        # Auto-load last project
        self.auto_load_project_var = tk.BooleanVar(value=self.settings.get('auto_load_last_project', False))
        ttk.Checkbutton(
            frame,
            text="Automatically load last opened project on startup",
            variable=self.auto_load_project_var,
            style='TCheckbutton'
        ).grid(row=2, column=0, sticky=tk.W, padx=10, pady=(5, 10))

    def create_advanced_settings_section(self):
        """Advanced Settings"""
        frame = ttk.LabelFrame(
            self.scroll_frame,
            text="⚡ Advanced Settings",
            style='TLabelframe'
        )
        frame.pack(fill=tk.X, padx=10, pady=10)

        # Enable debug logging
        self.debug_logging_var = tk.BooleanVar(value=self.settings.get('enable_debug_logging', False))
        ttk.Checkbutton(
            frame,
            text="Enable debug logging for Custom Code features",
            variable=self.debug_logging_var,
            style='TCheckbutton'
        ).grid(row=0, column=0, sticky=tk.W, padx=10, pady=(10, 5))

        # Show tool call details
        self.show_tool_details_var = tk.BooleanVar(value=self.settings.get('show_tool_call_details', True))
        ttk.Checkbutton(
            frame,
            text="Show detailed tool call information in chat",
            variable=self.show_tool_details_var,
            style='TCheckbutton'
        ).grid(row=1, column=0, sticky=tk.W, padx=10, pady=5)

        # Enable experimental features
        self.experimental_var = tk.BooleanVar(value=self.settings.get('enable_experimental', False))
        ttk.Checkbutton(
            frame,
            text="Enable experimental features (may be unstable)",
            variable=self.experimental_var,
            style='TCheckbutton'
        ).grid(row=2, column=0, sticky=tk.W, padx=10, pady=(5, 10))

    def create_button_bar(self, parent, row=2):
        """Create bottom button bar"""
        button_frame = ttk.Frame(parent, style='Category.TFrame')
        button_frame.grid(row=row, column=0, sticky=tk.EW, padx=10, pady=(0, 10))

        ttk.Button(
            button_frame,
            text="💾 Save Settings",
            command=self.save_settings,
            style='Action.TButton'
        ).pack(side=tk.LEFT, padx=5)

        ttk.Button(
            button_frame,
            text="↺ Reload",
            command=self.reload_settings,
            style='Select.TButton'
        ).pack(side=tk.LEFT, padx=5)

        self.profile_status_label = ttk.Label(
            button_frame,
            text=f"Profile: {self.current_profile_name.get()}",
            style='Config.TLabel',
            font=("Arial", 8)
        )
        self.profile_status_label.pack(side=tk.RIGHT, padx=5)

    def browse_working_directory(self):
        """Browse for working directory"""
        directory = filedialog.askdirectory(
            title="Select Working Directory",
            initialdir=self.working_dir_var.get()
        )
        if directory:
            self.working_dir_var.set(directory)
            log_message(f"CC_SETTINGS: Working directory set to {directory}")

    def browse_project_directory(self):
        """Browse for default project directory"""
        directory = filedialog.askdirectory(
            title="Select Default Project Directory",
            initialdir=self.project_dir_var.get()
        )
        if directory:
            self.project_dir_var.set(directory)
            log_message(f"CC_SETTINGS: Project directory set to {directory}")

    def load_profile(self):
        """Load Tool Profile from unified system"""
        try:
            profile_name = self.current_profile_name.get()
            profile = get_unified_tool_profile(profile_name, migrate=True)
            log_message(f"CC_SETTINGS: Loaded profile '{profile_name}'")
            return profile
        except Exception as e:
            log_message(f"CC_SETTINGS ERROR: Failed to load profile: {e}")
            # Return minimal default profile
            return {
                "profile_name": "Default",
                "version": "1.0",
                "tools": {"enabled_tools": {}},
                "execution": {
                    "working_directory": str(Path.cwd()),
                    "auto_update_working_dir": False,
                    "default_project_dir": str(Path.home() / "Projects")
                },
                "chat": {
                    "auto_mount_model": False,
                    "auto_save_history": True,
                    "history_retention_days": 0,
                    "max_message_length": 0
                },
                "orchestrator": {},
                "notes": ""
            }

    def extract_settings_from_profile(self):
        """Extract settings dict from unified profile for UI binding"""
        try:
            # Map profile sections to legacy settings format for UI compatibility
            execution = self.profile.get("execution", {})
            chat = self.profile.get("chat", {})
            tools = self.profile.get("tools", {})
            tools_logging = tools.get("logging", {})
            confirmation = tools.get("confirmation_policy", {})
            timeouts = tools.get("timeouts_sec", {})

            settings = {
                # Execution section
                'working_directory': execution.get('working_directory', str(Path.cwd())),
                'auto_update_working_dir': execution.get('auto_update_working_dir', False),
                'default_project_dir': execution.get('default_project_dir', str(Path.home() / "Projects")),

                # Chat section
                'auto_mount_model': chat.get('auto_mount_model', False),
                'auto_save_history': chat.get('auto_save_history', True),
                'history_retention_days': chat.get('history_retention_days', 0),
                'max_message_length': chat.get('max_message_length', 0),
                'temperature': chat.get('temperature', 0.8),

                # Tools section
                'confirm_high_risk_tools': confirmation.get('default_minimum_risk_to_confirm', 'high') in ['high', 'critical'],
                'confirm_critical_tools': confirmation.get('default_minimum_risk_to_confirm', 'critical') == 'critical',
                'tool_timeout': timeouts.get('default', 30),
                'log_tool_execution': tools_logging.get('tool_calls', True),

                # Local-only settings (not in profile)
                'training_mode_enabled': False,
                'auto_load_last_project': False,
                'enable_debug_logging': False,
                'show_tool_call_details': True,
                'enable_experimental': False
            }

            log_message("CC_SETTINGS: Extracted settings from profile")
            return settings

        except Exception as e:
            log_message(f"CC_SETTINGS ERROR: Failed to extract settings: {e}")
            return self.get_default_settings()

    def get_default_settings(self):
        """Get default settings"""
        return {
            'working_directory': str(Path.cwd()),
            'auto_update_working_dir': False,
            'confirm_high_risk_tools': True,
            'confirm_critical_tools': True,
            'tool_timeout': 30,
            'log_tool_execution': True,
            'training_mode_enabled': False,
            'auto_mount_model': False,
            'auto_save_history': True,
            'history_retention_days': 0,
            'max_message_length': 0,
            'temperature': 0.8,
            'default_project_dir': str(Path.home() / "Projects"),
            'auto_load_last_project': False,
            'enable_debug_logging': False,
            'show_tool_call_details': True,
            'enable_experimental': False
        }

    def save_settings(self):
        """Save settings to unified Tool Profile"""
        try:
            # Update profile sections from UI
            profile_name = self.current_profile_name.get()

            # Update execution section
            self.profile.setdefault("execution", {})
            self.profile["execution"]["working_directory"] = self.working_dir_var.get()
            self.profile["execution"]["auto_update_working_dir"] = self.auto_update_wd_var.get()
            self.profile["execution"]["default_project_dir"] = self.project_dir_var.get()

            # Update chat section
            self.profile.setdefault("chat", {})
            self.profile["chat"]["auto_mount_model"] = self.auto_mount_var.get()
            self.profile["chat"]["auto_save_history"] = self.auto_save_history_var.get()
            self.profile["chat"]["history_retention_days"] = int(self.history_retention_var.get())
            self.profile["chat"]["max_message_length"] = int(self.max_message_length_var.get())
            self.profile["chat"]["temperature"] = round(self.temperature_var.get(), 1)

            # Update tools section
            self.profile.setdefault("tools", {})
            self.profile["tools"].setdefault("confirmation_policy", {})
            self.profile["tools"].setdefault("timeouts_sec", {})
            self.profile["tools"].setdefault("logging", {})

            # Map confirmation checkboxes to risk levels
            if self.confirm_critical_var.get():
                risk_level = "critical"
            elif self.confirm_high_risk_var.get():
                risk_level = "high"
            else:
                risk_level = "none"
            self.profile["tools"]["confirmation_policy"]["default_minimum_risk_to_confirm"] = risk_level

            self.profile["tools"]["timeouts_sec"]["default"] = int(self.tool_timeout_var.get())
            self.profile["tools"]["logging"]["tool_calls"] = self.log_tool_execution_var.get()

            # Update metadata
            self.profile["profile_name"] = profile_name
            self.profile["updated_at"] = datetime.utcnow().isoformat() + "Z"

            # Save via unified API (atomic write + backup)
            save_tool_profile(profile_name, self.profile)

            # Update local settings cache
            self.settings = self.extract_settings_from_profile()

            log_message(f"CC_SETTINGS: Profile '{profile_name}' saved successfully")
            messagebox.showinfo("Profile Saved", f"Tool Profile '{profile_name}' has been saved successfully!")

            # Update tool executor working directory if needed
            if hasattr(self.parent_tab, 'chat_interface') and self.parent_tab.chat_interface:
                if hasattr(self.parent_tab.chat_interface, 'tool_executor'):
                    if self.parent_tab.chat_interface.tool_executor:
                        self.parent_tab.chat_interface.tool_executor.set_working_directory(
                            self.profile["execution"]["working_directory"]
                        )

            # Update status label
            self.profile_status_label.config(text=f"Profile: {profile_name} (saved)")

        except Exception as e:
            error_msg = f"Failed to save profile: {str(e)}"
            log_message(f"CC_SETTINGS ERROR: {error_msg}")
            messagebox.showerror("Save Error", error_msg)

    def reload_settings(self):
        """Reload settings from unified profile"""
        self.profile = self.load_profile()
        self.settings = self.extract_settings_from_profile()

        # Update all UI elements
        self.working_dir_var.set(self.settings.get('working_directory', str(Path.cwd())))
        self.auto_update_wd_var.set(self.settings.get('auto_update_working_dir', False))
        self.confirm_high_risk_var.set(self.settings.get('confirm_high_risk_tools', True))
        self.confirm_critical_var.set(self.settings.get('confirm_critical_tools', True))
        self.tool_timeout_var.set(str(self.settings.get('tool_timeout', 30)))
        self.log_tool_execution_var.set(self.settings.get('log_tool_execution', True))
        self.training_mode_var.set(self.settings.get('training_mode_enabled', False))
        self.update_training_status_label()
        self.auto_mount_var.set(self.settings.get('auto_mount_model', False))
        self.auto_save_history_var.set(self.settings.get('auto_save_history', True))
        self.history_retention_var.set(str(self.settings.get('history_retention_days', 0)))
        self.max_message_length_var.set(str(self.settings.get('max_message_length', 0)))
        self.temperature_var.set(self.settings.get('temperature', 0.8))
        self.update_temp_label(self.temperature_var.get())
        self.project_dir_var.set(self.settings.get('default_project_dir', str(Path.home() / "Projects")))
        self.auto_load_project_var.set(self.settings.get('auto_load_last_project', False))
        self.debug_logging_var.set(self.settings.get('enable_debug_logging', False))
        self.show_tool_details_var.set(self.settings.get('show_tool_call_details', True))
        self.experimental_var.set(self.settings.get('enable_experimental', False))

        log_message(f"CC_SETTINGS: Profile '{self.current_profile_name.get()}' reloaded")
        messagebox.showinfo("Profile Reloaded", f"Profile '{self.current_profile_name.get()}' has been reloaded")

    def reset_to_defaults(self):
        """Reset current profile to default values"""
        if messagebox.askyesno(
            "Reset to Defaults",
            f"Are you sure you want to reset profile '{self.current_profile_name.get()}' to default values?"
        ):
            # Get default settings and map to profile structure
            defaults = self.get_default_settings()
            profile_name = self.current_profile_name.get()

            # Create fresh profile with defaults
            self.profile = {
                "profile_name": profile_name,
                "version": "1.0",
                "created_at": self.profile.get("created_at", datetime.utcnow().isoformat() + "Z"),
                "updated_at": datetime.utcnow().isoformat() + "Z",
                "execution": {
                    "working_directory": defaults['working_directory'],
                    "auto_update_working_dir": defaults['auto_update_working_dir'],
                    "default_project_dir": defaults['default_project_dir']
                },
                "chat": {
                    "auto_mount_model": defaults['auto_mount_model'],
                    "auto_save_history": defaults['auto_save_history'],
                    "history_retention_days": defaults['history_retention_days'],
                    "max_message_length": defaults['max_message_length'],
                    "temperature": defaults['temperature']
                },
                "tools": {
                    "enabled_tools": self.profile.get("tools", {}).get("enabled_tools", {}),  # Preserve tool selections
                    "confirmation_policy": {
                        "default_minimum_risk_to_confirm": "high" if defaults['confirm_high_risk_tools'] else "none"
                    },
                    "timeouts_sec": {"default": defaults['tool_timeout']},
                    "logging": {"tool_calls": defaults['log_tool_execution']}
                },
                "orchestrator": self.profile.get("orchestrator", {}),
                "notes": ""
            }

            # Save and reload
            save_tool_profile(profile_name, self.profile)
            self.reload_settings()

            log_message(f"CC_SETTINGS: Profile '{profile_name}' reset to defaults")
            messagebox.showinfo("Reset Complete", f"Profile '{profile_name}' has been reset to defaults")

    def on_profile_changed(self, event=None):
        """Handle profile selection change"""
        new_profile = self.current_profile_name.get()
        log_message(f"CC_SETTINGS: Switching to profile '{new_profile}'")

        # Reload from new profile
        self.profile = self.load_profile()
        self.reload_settings()

        # Update status label
        self.profile_status_label.config(text=f"Profile: {new_profile}")

    def create_profile(self):
        """Create a new profile by cloning current or from defaults"""
        # Simple dialog to get new profile name
        dialog = tk.Toplevel(self.root)
        dialog.title("Create New Profile")
        dialog.geometry("400x150")
        dialog.transient(self.root)
        dialog.grab_set()

        ttk.Label(dialog, text="New Profile Name:", font=("Arial", 10)).pack(pady=(20, 5))

        name_var = tk.StringVar()
        name_entry = ttk.Entry(dialog, textvariable=name_var, font=("Arial", 10), width=30)
        name_entry.pack(pady=5)
        name_entry.focus()

        def do_create():
            new_name = name_var.get().strip()
            if not new_name:
                messagebox.showwarning("Invalid Name", "Profile name cannot be empty")
                return

            if new_name in list_tool_profiles():
                messagebox.showerror("Name Exists", f"Profile '{new_name}' already exists")
                return

            try:
                # Clone current profile with new name
                new_profile = self.profile.copy()
                new_profile["profile_name"] = new_name
                new_profile["created_at"] = datetime.utcnow().isoformat() + "Z"
                new_profile["updated_at"] = datetime.utcnow().isoformat() + "Z"

                save_tool_profile(new_name, new_profile)

                # Update combo and switch to new profile
                self.profile_combo['values'] = list_tool_profiles()
                self.current_profile_name.set(new_name)
                self.on_profile_changed()

                log_message(f"CC_SETTINGS: Created new profile '{new_name}'")
                messagebox.showinfo("Profile Created", f"New profile '{new_name}' created successfully!")
                dialog.destroy()

            except Exception as e:
                messagebox.showerror("Create Error", f"Failed to create profile: {e}")

        btn_frame = ttk.Frame(dialog)
        btn_frame.pack(pady=20)
        ttk.Button(btn_frame, text="Create", command=do_create, width=12).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=dialog.destroy, width=12).pack(side=tk.LEFT, padx=5)

        name_entry.bind('<Return>', lambda e: do_create())

    def rename_profile(self):
        """Rename the current profile"""
        current_name = self.current_profile_name.get()
        if current_name == "Default":
            messagebox.showwarning("Cannot Rename", "The 'Default' profile cannot be renamed")
            return

        # Simple dialog to get new name
        dialog = tk.Toplevel(self.root)
        dialog.title("Rename Profile")
        dialog.geometry("400x150")
        dialog.transient(self.root)
        dialog.grab_set()

        ttk.Label(dialog, text=f"Rename '{current_name}' to:", font=("Arial", 10)).pack(pady=(20, 5))

        name_var = tk.StringVar(value=current_name)
        name_entry = ttk.Entry(dialog, textvariable=name_var, font=("Arial", 10), width=30)
        name_entry.pack(pady=5)
        name_entry.focus()
        name_entry.select_range(0, tk.END)

        def do_rename():
            new_name = name_var.get().strip()
            if not new_name:
                messagebox.showwarning("Invalid Name", "Profile name cannot be empty")
                return

            if new_name == current_name:
                dialog.destroy()
                return

            if new_name in list_tool_profiles():
                messagebox.showerror("Name Exists", f"Profile '{new_name}' already exists")
                return

            try:
                # Rename by saving with new name and removing old
                old_path = TOOL_PROFILES_DIR / f"{current_name}.json"
                self.profile["profile_name"] = new_name
                self.profile["updated_at"] = datetime.utcnow().isoformat() + "Z"
                save_tool_profile(new_name, self.profile)

                # Move old to backup
                if old_path.exists():
                    backup_path = old_path.with_suffix(f".json.bak-{int(datetime.utcnow().timestamp())}")
                    old_path.rename(backup_path)

                # Update combo and switch
                self.profile_combo['values'] = list_tool_profiles()
                self.current_profile_name.set(new_name)
                self.profile_status_label.config(text=f"Profile: {new_name}")

                log_message(f"CC_SETTINGS: Renamed profile '{current_name}' → '{new_name}'")
                messagebox.showinfo("Profile Renamed", f"Profile renamed to '{new_name}' successfully!")
                dialog.destroy()

            except Exception as e:
                messagebox.showerror("Rename Error", f"Failed to rename profile: {e}")

        btn_frame = ttk.Frame(dialog)
        btn_frame.pack(pady=20)
        ttk.Button(btn_frame, text="Rename", command=do_rename, width=12).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=dialog.destroy, width=12).pack(side=tk.LEFT, padx=5)

        name_entry.bind('<Return>', lambda e: do_rename())

    def delete_profile(self):
        """Delete the current profile (with safety backup)"""
        current_name = self.current_profile_name.get()
        if current_name == "Default":
            messagebox.showwarning("Cannot Delete", "The 'Default' profile cannot be deleted")
            return

        if not messagebox.askyesno(
            "Delete Profile",
            f"Are you sure you want to delete profile '{current_name}'?\n\nA backup will be kept."
        ):
            return

        try:
            profile_path = TOOL_PROFILES_DIR / f"{current_name}.json"
            if profile_path.exists():
                # Move to timestamped backup instead of deleting
                backup_path = profile_path.with_suffix(f".json.bak-{int(datetime.utcnow().timestamp())}")
                profile_path.rename(backup_path)

                # Switch to Default
                self.current_profile_name.set("Default")
                self.profile_combo['values'] = list_tool_profiles()
                self.on_profile_changed()

                log_message(f"CC_SETTINGS: Deleted profile '{current_name}' (backed up to {backup_path.name})")
                messagebox.showinfo("Profile Deleted", f"Profile '{current_name}' deleted (backup: {backup_path.name})")

        except Exception as e:
            messagebox.showerror("Delete Error", f"Failed to delete profile: {e}")

    def refresh(self):
        """Refresh the settings tab"""
        log_message("CC_SETTINGS: Refreshing...")
        self.reload_settings()
