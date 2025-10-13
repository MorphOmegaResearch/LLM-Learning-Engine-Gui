# [SYSTEM: GUI | VERSION: 1.9f | STATUS: ACTIVE]
"""
Tools Tab - Tool management and configuration
Manages which OpenCode tools are enabled for chat interactions
Uses unified Tool Profile system for persistence.
"""

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
from pathlib import Path
import sys
import json
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

        # Unified Tool Profile integration
        self.current_profile_name = tk.StringVar(value="Default")
        self.profile = self.load_profile()
        self.tool_vars = {}  # {tool_key: BooleanVar}
        self.load_tool_settings_from_profile()

    def create_ui(self):
        """Create the tools configuration UI"""
        log_message("TOOLS_TAB: Creating UI...")

        self.parent.columnconfigure(0, weight=1)
        self.parent.rowconfigure(0, weight=0)  # Profile picker
        self.parent.rowconfigure(1, weight=0)  # Header
        self.parent.rowconfigure(2, weight=1)  # Tools list

        # Profile Picker
        self.create_profile_picker(row=0)

        # Header
        header_frame = ttk.Frame(self.parent, style='Category.TFrame')
        header_frame.grid(row=1, column=0, sticky=tk.EW, padx=10, pady=10)

        ttk.Label(
            header_frame,
            text="🔧 Tool Configuration",
            font=("Arial", 12, "bold"),
            style='CategoryPanel.TLabel'
        ).pack(side=tk.LEFT, padx=(0, 10))

        self.profile_status_label = ttk.Label(
            header_frame,
            text=f"Profile: {self.current_profile_name.get()}",
            style='Config.TLabel',
            font=("Arial", 8)
        )
        self.profile_status_label.pack(side=tk.LEFT, padx=10)

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
        list_container.grid(row=2, column=0, sticky=tk.NSEW, padx=10, pady=(0, 10))
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

    def create_profile_picker(self, row=0):
        """Create profile picker UI at the top (same as settings_tab)"""
        picker_frame = ttk.LabelFrame(
            self.parent,
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

    def load_profile(self):
        """Load Tool Profile from unified system"""
        try:
            profile_name = self.current_profile_name.get()
            profile = get_unified_tool_profile(profile_name, migrate=True)
            log_message(f"TOOLS_TAB: Loaded profile '{profile_name}'")
            return profile
        except Exception as e:
            log_message(f"TOOLS_TAB ERROR: Failed to load profile: {e}")
            # Return minimal default profile
            return {
                "profile_name": "Default",
                "version": "1.0",
                "tools": {"enabled_tools": {}},
                "execution": {},
                "chat": {},
                "orchestrator": {},
                "notes": ""
            }

    def load_tool_settings_from_profile(self):
        """Load tool settings from unified profile"""
        try:
            enabled_tools = self.profile.get("tools", {}).get("enabled_tools", {})

            # Initialize all tools with profile values or defaults
            for category, tools in self.AVAILABLE_TOOLS.items():
                for tool_key, tool_info in tools.items():
                    if tool_key in enabled_tools:
                        # Use value from profile
                        self.tool_vars[tool_key] = tk.BooleanVar(value=enabled_tools[tool_key])
                    else:
                        # Default: all tools enabled except critical ones
                        default_enabled = tool_info['risk'] != 'CRITICAL'
                        self.tool_vars[tool_key] = tk.BooleanVar(value=default_enabled)

            log_message(f"TOOLS_TAB: Loaded {len(self.tool_vars)} tool settings from profile")

        except Exception as e:
            log_message(f"TOOLS_TAB ERROR: Failed to load tool settings: {e}")
            # Fallback to defaults
            for category, tools in self.AVAILABLE_TOOLS.items():
                for tool_key, tool_info in tools.items():
                    default_enabled = tool_info['risk'] != 'CRITICAL'
                    self.tool_vars[tool_key] = tk.BooleanVar(value=default_enabled)

    def save_tool_settings(self):
        """Save tool settings to unified Tool Profile"""
        try:
            profile_name = self.current_profile_name.get()

            # Update tools.enabled_tools section
            self.profile.setdefault("tools", {})
            self.profile["tools"]["enabled_tools"] = {
                key: var.get() for key, var in self.tool_vars.items()
            }

            # Update metadata
            self.profile["profile_name"] = profile_name
            self.profile["updated_at"] = datetime.utcnow().isoformat() + "Z"

            # Save via unified API (atomic write + backup)
            save_tool_profile(profile_name, self.profile)

            log_message(f"TOOLS_TAB: Profile '{profile_name}' saved successfully")
            messagebox.showinfo("Profile Saved", f"Tool Profile '{profile_name}' has been saved successfully!")

            # Update status label
            self.profile_status_label.config(text=f"Profile: {profile_name} (saved)")

        except Exception as e:
            error_msg = f"Failed to save profile: {str(e)}"
            log_message(f"TOOLS_TAB ERROR: {error_msg}")
            messagebox.showerror("Save Error", error_msg)

    def reset_to_defaults(self):
        """Reset all tools to default settings"""
        if messagebox.askyesno("Reset to Defaults", "Reset all tool settings to defaults?"):
            # Reset: enable all except critical
            for category, tools in self.AVAILABLE_TOOLS.items():
                for tool_key, tool_info in tools.items():
                    default_enabled = tool_info['risk'] != 'CRITICAL'
                    if tool_key in self.tool_vars:
                        self.tool_vars[tool_key].set(default_enabled)

            log_message("TOOLS_TAB: Reset to defaults")

    def on_profile_changed(self, event=None):
        """Handle profile selection change"""
        new_profile = self.current_profile_name.get()
        log_message(f"TOOLS_TAB: Switching to profile '{new_profile}'")

        # Reload from new profile
        self.profile = self.load_profile()
        self.load_tool_settings_from_profile()

        # Update UI - need to refresh checkboxes
        for tool_key, var in self.tool_vars.items():
            enabled_tools = self.profile.get("tools", {}).get("enabled_tools", {})
            if tool_key in enabled_tools:
                var.set(enabled_tools[tool_key])

        # Update status label
        self.profile_status_label.config(text=f"Profile: {new_profile}")

    def create_profile(self):
        """Create a new profile by cloning current"""
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
                import copy
                new_profile = copy.deepcopy(self.profile)
                new_profile["profile_name"] = new_name
                new_profile["created_at"] = datetime.utcnow().isoformat() + "Z"
                new_profile["updated_at"] = datetime.utcnow().isoformat() + "Z"

                save_tool_profile(new_name, new_profile)

                # Update combo and switch to new profile
                self.profile_combo['values'] = list_tool_profiles()
                self.current_profile_name.set(new_name)
                self.on_profile_changed()

                log_message(f"TOOLS_TAB: Created new profile '{new_name}'")
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

                log_message(f"TOOLS_TAB: Renamed profile '{current_name}' → '{new_name}'")
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

                log_message(f"TOOLS_TAB: Deleted profile '{current_name}' (backed up to {backup_path.name})")
                messagebox.showinfo("Profile Deleted", f"Profile '{current_name}' deleted (backup: {backup_path.name})")

        except Exception as e:
            messagebox.showerror("Delete Error", f"Failed to delete profile: {e}")

    def get_enabled_tools(self):
        """Get list of currently enabled tools"""
        return [key for key, var in self.tool_vars.items() if var.get()]

    def refresh(self):
        """Refresh the tools tab"""
        log_message("TOOLS_TAB: Refreshing...")
        self.profile = self.load_profile()
        self.load_tool_settings_from_profile()

        # Update UI checkboxes
        for tool_key, var in self.tool_vars.items():
            enabled_tools = self.profile.get("tools", {}).get("enabled_tools", {})
            if tool_key in enabled_tools:
                var.set(enabled_tools[tool_key])
