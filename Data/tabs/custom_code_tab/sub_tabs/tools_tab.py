"""
Tools Tab - Tool management and configuration
Manages which OpenCode tools are enabled for chat interactions
"""

import tkinter as tk
from tkinter import ttk, scrolledtext
from pathlib import Path
import sys
import json

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from tabs.base_tab import BaseTab
from logger_util import log_message


class ToolsTab(BaseTab):
    """Tools configuration and management tab"""

    # Available OpenCode tools from tools.py
    AVAILABLE_TOOLS = {
        "File Operations": {
            "file_read": {"name": "File Read", "desc": "Read file contents", "risk": "SAFE"},
            "file_write": {"name": "File Write", "desc": "Write/create files", "risk": "MEDIUM"},
            "file_edit": {"name": "File Edit", "desc": "Edit existing files", "risk": "MEDIUM"},
            "file_copy": {"name": "File Copy", "desc": "Copy files", "risk": "LOW"},
            "file_move": {"name": "File Move", "desc": "Move/rename files", "risk": "MEDIUM"},
            "file_delete": {"name": "File Delete", "desc": "Delete files", "risk": "HIGH"},
            "file_create": {"name": "File Create", "desc": "Create empty files", "risk": "LOW"},
            "file_fill": {"name": "File Fill", "desc": "Fill file with content", "risk": "MEDIUM"},
        },
        "Search & Discovery": {
            "grep_search": {"name": "Grep Search", "desc": "Search file contents", "risk": "SAFE"},
            "file_search": {"name": "File Search", "desc": "Find files by name/pattern", "risk": "SAFE"},
            "directory_list": {"name": "Directory List", "desc": "List directory contents", "risk": "SAFE"},
        },
        "Execution": {
            "bash_execute": {"name": "Bash Execute", "desc": "Run shell commands", "risk": "CRITICAL"},
            "git_operations": {"name": "Git Operations", "desc": "Git commands", "risk": "MEDIUM"},
        },
        "System": {
            "system_info": {"name": "System Info", "desc": "Get system information", "risk": "SAFE"},
            "change_directory": {"name": "Change Directory", "desc": "Change working directory", "risk": "LOW"},
            "resource_request": {"name": "Resource Request", "desc": "Request system resources", "risk": "LOW"},
            "think_time": {"name": "Think Time", "desc": "Pause execution to think or plan", "risk": "MEDIUM"}
        }
    }

    def __init__(self, parent, root, style, parent_tab):
        super().__init__(parent, root, style)
        self.parent_tab = parent_tab
        self.tool_vars = {}  # {tool_key: BooleanVar}
        self.load_tool_settings()

    def create_ui(self):
        """Create the tools configuration UI"""
        log_message("TOOLS_TAB: Creating UI...")

        self.parent.columnconfigure(0, weight=1)
        self.parent.rowconfigure(1, weight=1)

        # Header
        header_frame = ttk.Frame(self.parent, style='Category.TFrame')
        header_frame.grid(row=0, column=0, sticky=tk.EW, padx=10, pady=10)

        ttk.Label(
            header_frame,
            text="🔧 Tool Configuration",
            font=("Arial", 12, "bold"),
            style='CategoryPanel.TLabel'
        ).pack(side=tk.LEFT, padx=(0, 10))

        ttk.Button(
            header_frame,
            text="💾 Save Settings",
            command=self.save_tool_settings,
            style='Action.TButton'
        ).pack(side=tk.RIGHT, padx=5)

        ttk.Button(
            header_frame,
            text="🔄 Reset to Defaults",
            command=self.reset_to_defaults,
            style='Select.TButton'
        ).pack(side=tk.RIGHT)

        # Tools list frame with scrollbar
        list_container = ttk.Frame(self.parent, style='Category.TFrame')
        list_container.grid(row=1, column=0, sticky=tk.NSEW, padx=10, pady=(0, 10))
        list_container.columnconfigure(0, weight=1)
        list_container.rowconfigure(0, weight=1)

        # Canvas for scrolling
        self.tools_canvas = tk.Canvas(
            list_container,
            bg='#2b2b2b',
            highlightthickness=0
        )
        self.tools_scrollbar = ttk.Scrollbar(
            list_container,
            orient="vertical",
            command=self.tools_canvas.yview
        )
        self.tools_scroll_frame = ttk.Frame(self.tools_canvas, style='Category.TFrame')

        self.tools_scroll_frame.bind(
            "<Configure>",
            lambda e: self.tools_canvas.configure(scrollregion=self.tools_canvas.bbox("all"))
        )

        self.tools_canvas_window = self.tools_canvas.create_window(
            (0, 0),
            window=self.tools_scroll_frame,
            anchor="nw"
        )
        self.tools_canvas.configure(yscrollcommand=self.tools_scrollbar.set)

        self.tools_canvas.bind(
            "<Configure>",
            lambda e: self.tools_canvas.itemconfig(self.tools_canvas_window, width=e.width)
        )

        self.tools_canvas.grid(row=0, column=0, sticky=tk.NSEW)
        self.tools_scrollbar.grid(row=0, column=1, sticky=tk.NS)

        # Create tool categories
        self.create_tool_categories()

        log_message("TOOLS_TAB: UI created successfully")

    def create_tool_categories(self):
        """Create tool category sections with checkboxes"""
        for category, tools in self.AVAILABLE_TOOLS.items():
            # Category frame
            category_frame = ttk.LabelFrame(
                self.tools_scroll_frame,
                text=f"📂 {category}",
                style='TLabelframe'
            )
            category_frame.pack(fill=tk.X, padx=5, pady=5)

            # Tools in this category
            for tool_key, tool_info in tools.items():
                tool_row = ttk.Frame(category_frame, style='Category.TFrame')
                tool_row.pack(fill=tk.X, padx=10, pady=2)

                # Checkbox
                var = tk.BooleanVar(value=self.tool_vars.get(tool_key, tk.BooleanVar(value=True)).get())
                self.tool_vars[tool_key] = var

                cb = ttk.Checkbutton(
                    tool_row,
                    text=tool_info['name'],
                    variable=var,
                    style='Category.TCheckbutton'
                )
                cb.pack(side=tk.LEFT, padx=(0, 10))

                # Description
                desc_label = ttk.Label(
                    tool_row,
                    text=tool_info['desc'],
                    style='Config.TLabel',
                    font=("Arial", 9)
                )
                desc_label.pack(side=tk.LEFT, padx=(0, 10))

                # Risk indicator
                risk_color = {
                    'SAFE': '#98c379',
                    'LOW': '#61dafb',
                    'MEDIUM': '#e5c07b',
                    'HIGH': '#e06c75',
                    'CRITICAL': '#ff6b6b'
                }.get(tool_info['risk'], '#ffffff')

                risk_label = tk.Label(
                    tool_row,
                    text=tool_info['risk'],
                    font=("Arial", 8, "bold"),
                    bg='#2b2b2b',
                    fg=risk_color
                )
                risk_label.pack(side=tk.RIGHT, padx=5)

    def load_tool_settings(self):
        """Load tool settings from file"""
        settings_file = Path(__file__).parent.parent / "tool_settings.json"

        if settings_file.exists():
            try:
                with open(settings_file, 'r') as f:
                    settings = json.load(f)

                for tool_key, enabled in settings.get('enabled_tools', {}).items():
                    self.tool_vars[tool_key] = tk.BooleanVar(value=enabled)

                log_message("TOOLS_TAB: Settings loaded successfully")
            except Exception as e:
                log_message(f"TOOLS_TAB ERROR: Failed to load settings: {e}")
        else:
            # Default: all tools enabled except critical ones
            for category, tools in self.AVAILABLE_TOOLS.items():
                for tool_key, tool_info in tools.items():
                    default_enabled = tool_info['risk'] != 'CRITICAL'
                    self.tool_vars[tool_key] = tk.BooleanVar(value=default_enabled)

    def save_tool_settings(self):
        """Save tool settings to file"""
        settings_file = Path(__file__).parent.parent / "tool_settings.json"

        try:
            settings = {
                'enabled_tools': {
                    key: var.get() for key, var in self.tool_vars.items()
                }
            }

            with open(settings_file, 'w') as f:
                json.dump(settings, f, indent=2)

            log_message("TOOLS_TAB: Settings saved successfully")

            # Show success message
            from tkinter import messagebox
            messagebox.showinfo("Settings Saved", "Tool settings have been saved successfully!")

        except Exception as e:
            log_message(f"TOOLS_TAB ERROR: Failed to save settings: {e}")
            from tkinter import messagebox
            messagebox.showerror("Save Error", f"Failed to save settings: {e}")

    def reset_to_defaults(self):
        """Reset all tools to default settings"""
        from tkinter import messagebox

        if messagebox.askyesno("Reset to Defaults", "Reset all tool settings to defaults?"):
            # Reset: enable all except critical
            for category, tools in self.AVAILABLE_TOOLS.items():
                for tool_key, tool_info in tools.items():
                    default_enabled = tool_info['risk'] != 'CRITICAL'
                    if tool_key in self.tool_vars:
                        self.tool_vars[tool_key].set(default_enabled)

            log_message("TOOLS_TAB: Reset to defaults")

    def get_enabled_tools(self):
        """Get list of currently enabled tools"""
        return [key for key, var in self.tool_vars.items() if var.get()]

    def refresh(self):
        """Refresh the tools tab"""
        log_message("TOOLS_TAB: Refreshing...")
        self.load_tool_settings()
