"""
Settings Sub-Tab - Backend configuration for Custom Code features
Controls working directory, tool execution, chat behavior, and project settings
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
import json
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from tabs.base_tab import BaseTab
from logger_util import log_message


class SettingsTab(BaseTab):
    """Settings configuration interface for Custom Code tab"""

    def __init__(self, parent, root, style, parent_tab):
        super().__init__(parent, root, style)
        self.parent_tab = parent_tab
        self.settings_file = Path(__file__).parent.parent / "custom_code_settings.json"
        self.settings = self.load_settings()

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
        parent.rowconfigure(0, weight=0)  # Header
        parent.rowconfigure(1, weight=1)  # Scrollable content
        parent.rowconfigure(2, weight=0)  # Buttons

        # Header
        header_frame = ttk.Frame(parent, style='Category.TFrame')
        header_frame.grid(row=0, column=0, sticky=tk.EW, padx=10, pady=10)

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
        self.create_scrollable_content(parent)

        # Bottom buttons
        self.create_button_bar(parent)

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

    def create_scrollable_content(self, parent):
        """Create scrollable content area with all settings"""
        container = ttk.Frame(parent, style='Category.TFrame')
        container.grid(row=1, column=0, sticky=tk.NSEW, padx=10, pady=(0, 10))
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

    def create_button_bar(self, parent):
        """Create bottom button bar"""
        button_frame = ttk.Frame(parent, style='Category.TFrame')
        button_frame.grid(row=2, column=0, sticky=tk.EW, padx=10, pady=(0, 10))

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

        ttk.Label(
            button_frame,
            text="Settings are saved to: custom_code_settings.json",
            style='Config.TLabel',
            font=("Arial", 8)
        ).pack(side=tk.RIGHT, padx=5)

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

    def load_settings(self):
        """Load settings from file"""
        if self.settings_file.exists():
            try:
                with open(self.settings_file, 'r') as f:
                    settings = json.load(f)
                    log_message("CC_SETTINGS: Settings loaded successfully")
                    return settings
            except Exception as e:
                log_message(f"CC_SETTINGS ERROR: Failed to load settings: {e}")

        # Return defaults
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
        """Save settings to file"""
        try:
            # Collect all settings from UI
            settings = {
                'working_directory': self.working_dir_var.get(),
                'auto_update_working_dir': self.auto_update_wd_var.get(),
                'confirm_high_risk_tools': self.confirm_high_risk_var.get(),
                'confirm_critical_tools': self.confirm_critical_var.get(),
                'tool_timeout': int(self.tool_timeout_var.get()),
                'log_tool_execution': self.log_tool_execution_var.get(),
                'training_mode_enabled': self.training_mode_var.get(),
                'auto_mount_model': self.auto_mount_var.get(),
                'auto_save_history': self.auto_save_history_var.get(),
                'history_retention_days': int(self.history_retention_var.get()),
                'max_message_length': int(self.max_message_length_var.get()),
                'temperature': round(self.temperature_var.get(), 1),
                'default_project_dir': self.project_dir_var.get(),
                'auto_load_last_project': self.auto_load_project_var.get(),
                'enable_debug_logging': self.debug_logging_var.get(),
                'show_tool_call_details': self.show_tool_details_var.get(),
                'enable_experimental': self.experimental_var.get()
            }

            # Save to file
            with open(self.settings_file, 'w') as f:
                json.dump(settings, f, indent=2)

            self.settings = settings
            log_message("CC_SETTINGS: Settings saved successfully")
            messagebox.showinfo("Settings Saved", "Custom Code settings have been saved successfully!")

            # Update tool executor working directory if needed
            if hasattr(self.parent_tab, 'chat_interface') and self.parent_tab.chat_interface:
                if hasattr(self.parent_tab.chat_interface, 'tool_executor'):
                    if self.parent_tab.chat_interface.tool_executor:
                        self.parent_tab.chat_interface.tool_executor.set_working_directory(
                            settings['working_directory']
                        )

        except Exception as e:
            error_msg = f"Failed to save settings: {str(e)}"
            log_message(f"CC_SETTINGS ERROR: {error_msg}")
            messagebox.showerror("Save Error", error_msg)

    def reload_settings(self):
        """Reload settings from file"""
        self.settings = self.load_settings()

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

        log_message("CC_SETTINGS: Settings reloaded")
        messagebox.showinfo("Settings Reloaded", "Settings have been reloaded from file")

    def reset_to_defaults(self):
        """Reset all settings to defaults"""
        if messagebox.askyesno(
            "Reset to Defaults",
            "Are you sure you want to reset all settings to their default values?"
        ):
            self.settings = self.get_default_settings()

            # Update UI
            self.reload_settings()

            log_message("CC_SETTINGS: Settings reset to defaults")
            messagebox.showinfo("Reset Complete", "All settings have been reset to defaults")

    def refresh(self):
        """Refresh the settings tab"""
        log_message("CC_SETTINGS: Refreshing...")
        self.reload_settings()
