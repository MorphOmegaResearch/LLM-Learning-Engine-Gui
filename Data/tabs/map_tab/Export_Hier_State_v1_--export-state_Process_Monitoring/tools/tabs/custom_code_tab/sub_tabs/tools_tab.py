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
from logger_util import get_tab_logger

log_message, log_error, log_exception = get_tab_logger('custom_code')
from config import (
    list_tool_profiles,
    load_tool_profile,
    save_tool_profile,
    get_unified_tool_profile,
    TOOL_PROFILES_DIR,
    DATA_DIR,
    TOOL_SKILL_ALIASES
)
from tabs.custom_code_tab.tool_schemas import TOOL_SCHEMAS


class ToolsTab(BaseTab):
    """Tools configuration and management tab"""

    CATEGORY_ORDER = [
        "File Operations",
        "Search & Discovery",
        "Execution & Runtime",
        "System & Environment",
        "Version Control",
        "Browser Automation",
        "Web & Data Access",
        "Diagnostics & Observability",
        "Agents & Orchestration",
        "Project Management",
        "Templates & Docs",
        "Analysis & Utilities",
        "Media IO",
        "Other Tools"
    ]

    CATEGORY_DEFAULT_RISK = {
        "File Operations": "MEDIUM",
        "Search & Discovery": "SAFE",
        "Execution & Runtime": "HIGH",
        "System & Environment": "LOW",
        "Version Control": "MEDIUM",
        "Browser Automation": "MEDIUM",
        "Web & Data Access": "MEDIUM",
        "Diagnostics & Observability": "LOW",
        "Agents & Orchestration": "MEDIUM",
        "Project Management": "SAFE",
        "Templates & Docs": "SAFE",
        "Analysis & Utilities": "MEDIUM",
        "Media IO": "LOW",
        "Other Tools": "MEDIUM"
    }

    CATEGORY_SETS = {
        "File Operations": {
            "file_read", "file_write", "file_edit", "file_copy",
            "file_move", "file_delete", "file_create", "file_fill", "apply_patch",
        },
        "Search & Discovery": {"file_search", "grep_search", "directory_list"},
        "Execution & Runtime": {"bash_execute"},
        "System & Environment": {"system_info", "change_directory", "resource_request", "think_time", "wait"},
        "Version Control": {"git_operations"},
        "Browser Automation": {
            "browser_screenshot", "browser_click", "browser_double_click",
            "browser_right_click", "browser_drag", "browser_type",
            "browser_press", "browser_hotkey", "browser_scroll", "browser_navigate",
            "element_detect", "get_mouse_position", "get_pixel_color",
            "browser_alert", "browser_confirm", "browser_search",
            "page_extract", "html_to_markdown", "browser_automation"
        },
        "Web & Data Access": {"web_fetch", "web_search"},
        "Diagnostics & Observability": {
            "collect_metrics", "search_logs", "tail_file",
            "start_diagnostics_command", "stop_diagnostics_command",
            "start_log_tail", "stop_log_tail", "record_debug_fix"
        },
        "Agents & Orchestration": {
            "agent_request", "agents_mount_all", "agents_unmount_all",
            "agents_status", "agents_route_task", "agents_set_roster",
            "agents_open_tab", "agents_highlight_in_collections", "agents_focus_mounts"
        },
        "Project Management": {"create_todo", "link_todo", "link_plan", "update_plan"},
        "Templates & Docs": {"template_generate", "template_transform", "template_agent"},
        "Analysis & Utilities": {"code_analyze", "process_manage", "package_check"},
        "Media IO": {"audio_read", "image_read"},
    }

    TOOL_CATEGORY_OVERRIDES = {
        name: category
        for category, names in CATEGORY_SETS.items()
        for name in names
    }

    TOOL_RISK_OVERRIDES = {
        "bash_execute": "CRITICAL",
        "apply_patch": "HIGH",
        "file_delete": "HIGH",
        "agent_request": "MEDIUM",
        "agents_mount_all": "MEDIUM",
        "agents_unmount_all": "MEDIUM",
        "agents_route_task": "MEDIUM",
        "agents_set_roster": "MEDIUM",
        "agents_status": "MEDIUM",
        "start_diagnostics_command": "HIGH",
        "stop_diagnostics_command": "LOW",
        "start_log_tail": "LOW",
        "stop_log_tail": "SAFE",
        "web_fetch": "MEDIUM",
        "web_search": "MEDIUM",
        "browser_drag": "MEDIUM",
        "browser_hotkey": "MEDIUM",
        "browser_press": "MEDIUM",
        "browser_type": "MEDIUM",
        "browser_screenshot": "SAFE",
        "browser_scroll": "LOW",
        "browser_navigate": "LOW",
        "element_detect": "LOW",
        "get_mouse_position": "SAFE",
        "get_pixel_color": "SAFE",
        "browser_alert": "LOW",
        "browser_confirm": "LOW",
        "browser_search": "MEDIUM",
        "page_extract": "MEDIUM",
        "html_to_markdown": "SAFE",
        "code_analyze": "MEDIUM",
        "process_manage": "MEDIUM",
        "package_check": "MEDIUM",
        "system_info": "SAFE",
        "resource_request": "LOW",
        "think_time": "MEDIUM",
        "wait": "SAFE",
        "collect_metrics": "LOW",
        "search_logs": "SAFE",
        "tail_file": "SAFE",
        "record_debug_fix": "SAFE",
        "create_todo": "SAFE",
        "link_todo": "SAFE",
        "link_plan": "SAFE",
        "update_plan": "SAFE",
        "template_generate": "SAFE",
        "template_transform": "SAFE",
        "template_agent": "SAFE",
        "audio_read": "SAFE",
        "image_read": "SAFE",
        "browser_automation": "MEDIUM",
    }

    TOOL_NAME_OVERRIDES = {
        "agent_request": "Delegate to Agent",
        "agents_mount_all": "Mount All Agents",
        "agents_unmount_all": "Unmount All Agents",
        "agents_status": "Agents Status",
        "agents_route_task": "Route Task to Agent",
        "agents_set_roster": "Set Agent Roster",
        "agents_open_tab": "Open Agents Tab",
        "agents_highlight_in_collections": "Highlight in Collections",
        "agents_focus_mounts": "Focus Agent Mounts",
        "start_diagnostics_command": "Start Diagnostics Command",
        "stop_diagnostics_command": "Stop Diagnostics Command",
        "start_log_tail": "Start Log Tail",
        "stop_log_tail": "Stop Log Tail",
        "collect_metrics": "Collect Metrics",
        "search_logs": "Search Logs",
        "tail_file": "Tail File",
        "record_debug_fix": "Record Debug Fix",
        "create_todo": "Create TODO",
        "link_todo": "Link TODO",
        "link_plan": "Link Plan",
        "update_plan": "Update Plan",
        "template_generate": "Generate Template",
        "template_transform": "Transform Template",
        "template_agent": "Template Agent",
        "browser_hotkey": "Browser Hotkey",
        "browser_press": "Browser Key Press",
        "browser_type": "Browser Type Text",
        "browser_search": "Browser Search",
        "page_extract": "Page Extract",
        "html_to_markdown": "HTML → Markdown",
        "browser_automation": "Browser Automation Suite",
        "code_analyze": "Code Analyze",
        "process_manage": "Process Manage",
        "package_check": "Package Check",
        "web_fetch": "Web Fetch",
        "web_search": "Web Search",
        "audio_read": "Audio Read",
        "image_read": "Image Read",
    }

    TOOL_DESCRIPTION_OVERRIDES = {
        "apply_patch": "Apply a unified diff patch to modify files atomically.",
        "browser_search": "Search the current browser context for matching content.",
        "web_fetch": "Fetch data from an HTTP endpoint using the launcher allowlist.",
        "web_search": "Run a web search using the configured search provider.",
        "code_analyze": "Analyze code structure and summarize potential issues.",
        "process_manage": "Inspect or manage local processes through the sandboxed runner.",
        "package_check": "Inspect package metadata and dependency status.",
        "collect_metrics": "Collect runtime metrics for diagnostics dashboards.",
        "search_logs": "Search captured logs for matching entries.",
        "tail_file": "Stream file changes in real time (tail -f style).",
        "start_diagnostics_command": "Launch an allowlisted diagnostics command via the workspace console.",
        "stop_diagnostics_command": "Stop the active diagnostics command if one is running.",
        "start_log_tail": "Begin streaming the workspace launcher log output.",
        "stop_log_tail": "Stop the active log tail stream.",
        "record_debug_fix": "Record a fix/rollback event in the bug tracker registry.",
        "create_todo": "Create a Living Project TODO item with metadata wiring.",
        "link_todo": "Link an existing TODO entry to a Living Project timeline.",
        "link_plan": "Associate a plan document with a Living Project.",
        "update_plan": "Update plan metadata and blueprint references.",
        "template_generate": "Generate structured content from a template definition.",
        "template_transform": "Transform content using the configured template pipeline.",
        "template_agent": "Invoke the Template agent to craft reusable templates.",
        "browser_automation": "Run a higher-level browser automation sequence.",
        "audio_read": "Read audio metadata or transcripts for analysis.",
        "image_read": "Read image metadata or run OCR extraction.",
    }

    TOOL_ALIAS_MAP = {
        "agents_request": "agent_request",
        "orchestrator_status": "agents_status",
        "focus_mounts": "agents_focus_mounts",
        "set_roster": "agents_set_roster",
        "list_directory": "directory_list",
        "run_bash_command": "bash_execute",
        "run_command": "bash_execute",
        "grep": "grep_search",
        "glob": "file_search",
        "open_file": "file_read",
        "read_text": "file_read",
        "python": None,
        "python_repl": None,
        "all": None,
    }

    BASE_TOOL_NAMES = {
        "file_read", "file_write", "file_edit", "file_copy", "file_move", "file_delete",
        "file_create", "file_fill", "file_search", "grep_search", "directory_list",
        "bash_execute", "git_operations", "system_info", "change_directory",
        "resource_request", "think_time", "wait", "browser_screenshot", "browser_click",
        "browser_double_click", "browser_right_click", "browser_drag", "browser_type",
        "browser_press", "browser_hotkey", "browser_scroll", "browser_navigate",
        "element_detect", "get_mouse_position", "get_pixel_color", "browser_alert",
        "browser_confirm", "browser_search", "page_extract", "html_to_markdown",
        "browser_automation", "web_fetch", "web_search", "code_analyze", "process_manage",
        "package_check", "collect_metrics", "search_logs", "tail_file",
        "start_diagnostics_command", "stop_diagnostics_command", "start_log_tail",
        "stop_log_tail", "record_debug_fix", "create_todo", "link_todo", "link_plan",
        "update_plan", "template_generate", "template_transform", "template_agent",
        "agent_request", "agents_mount_all", "agents_unmount_all", "agents_status",
        "agents_route_task", "agents_set_roster", "agents_open_tab",
        "agents_highlight_in_collections", "agents_focus_mounts", "audio_read",
        "image_read", "apply_patch"
    }

    AVAILABLE_TOOLS = None

    @classmethod
    def initialize_catalog(cls):
        """Build the tool catalog once per session."""
        if cls.AVAILABLE_TOOLS is None:
            cls.AVAILABLE_TOOLS = cls.build_available_tools()
            total_tools = sum(len(tools) for tools in cls.AVAILABLE_TOOLS.values())
            log_message(f"TOOLS_TAB: Tool catalog initialized ({len(cls.AVAILABLE_TOOLS)} categories, {total_tools} tools)")

    @classmethod
    def build_available_tools(cls):
        """Construct the categorized tool catalog with risk metadata."""
        catalog = {}
        known_tools = set(cls.BASE_TOOL_NAMES)
        known_tools.update(TOOL_SCHEMAS.keys())
        known_tools.update(cls._load_tool_skill_names())
        known_tools.update(cls._load_permissions_tools())

        normalized = set()
        for name in known_tools:
            canonical = cls._canonicalize(name)
            if canonical:
                normalized.add(canonical)

        for tool_name in sorted(normalized):
            category = cls.TOOL_CATEGORY_OVERRIDES.get(tool_name, "Other Tools")
            display_name = cls.TOOL_NAME_OVERRIDES.get(tool_name) or cls._humanize_tool_name(tool_name)
            description = cls.TOOL_DESCRIPTION_OVERRIDES.get(tool_name)

            if not description:
                schema = TOOL_SCHEMAS.get(tool_name)
                if schema:
                    description = (
                        schema.get("function", {}).get("description")
                        or schema.get("description")
                    )

            if not description:
                description = cls._default_description(tool_name)

            risk = cls.TOOL_RISK_OVERRIDES.get(
                tool_name,
                cls.CATEGORY_DEFAULT_RISK.get(category, "MEDIUM")
            )

            category_bucket = catalog.setdefault(category, {})
            category_bucket[tool_name] = {
                "name": display_name,
                "desc": description,
                "risk": risk
            }

        # Sort categories (respect defined order) and tool names
        ordered_catalog = {}
        for category in cls.CATEGORY_ORDER:
            if category in catalog:
                ordered_catalog[category] = dict(sorted(catalog[category].items()))
        for category in sorted(catalog.keys()):
            if category not in ordered_catalog:
                ordered_catalog[category] = dict(sorted(catalog[category].items()))
        return ordered_catalog

    @classmethod
    def _canonicalize(cls, name):
        if not name:
            return None
        key = str(name).strip()
        if not key:
            return None
        normalized = key.lower()
        mapped = cls.TOOL_ALIAS_MAP.get(normalized, normalized)
        if mapped is None:
            return None
        return mapped

    @classmethod
    def _load_tool_skill_names(cls):
        return set(TOOL_SKILL_ALIASES.keys())

    @classmethod
    def _load_permissions_tools(cls):
        path = DATA_DIR / "tool_permissions.json"
        if not path.exists():
            return set()

        try:
            with path.open("r", encoding="utf-8") as fh:
                data = json.load(fh)

            names = set()
            global_tools = data.get("global_tools", {}).get("tools", [])
            for tool in global_tools or []:
                if isinstance(tool, str):
                    names.add(tool)

            for type_entry in (data.get("type_permissions") or {}).values():
                for tier_tools in type_entry.values():
                    if isinstance(tier_tools, list):
                        for tool in tier_tools:
                            if isinstance(tool, str):
                                names.add(tool)

            return names
        except Exception as exc:
            log_message(f"TOOLS_TAB: Failed to load tool_permissions.json ({exc})")
            return set()

    @staticmethod
    def _humanize_tool_name(name: str) -> str:
        return name.replace("_", " ").title()

    @staticmethod
    def _default_description(name: str) -> str:
        readable = name.replace("_", " ")
        return f"Enable or disable the '{readable}' tool for model calls."

    def _iter_categories(self, catalog: dict):
        seen = set()
        for category in self.CATEGORY_ORDER:
            if category in catalog:
                seen.add(category)
                yield category
        for category in sorted(catalog.keys()):
            if category not in seen:
                yield category

    def __init__(self, parent, root, style, parent_tab):
        super().__init__(parent, root, style)
        self.parent_tab = parent_tab

        type(self).initialize_catalog()
        self.available_tools = type(self).AVAILABLE_TOOLS or {}

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
        self._rebuild_catalog_ui()

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
        catalog = self.available_tools or {}
        for category in self._iter_categories(catalog):
            tools = catalog.get(category, {})
            if not tools:
                continue

            category_frame = ttk.LabelFrame(
                self.tools_scroll_frame,
                text=f"📂 {category}",
                style='TLabelframe'
            )
            category_frame.pack(fill=tk.X, padx=5, pady=5)

            for tool_key, tool_info in tools.items():
                tool_row = ttk.Frame(category_frame, style='Category.TFrame')
                tool_row.pack(fill=tk.X, padx=10, pady=2)

                var = self.tool_vars.get(tool_key)
                if not isinstance(var, tk.BooleanVar):
                    default_enabled = tool_info['risk'] != 'CRITICAL'
                    var = tk.BooleanVar(value=default_enabled)
                    self.tool_vars[tool_key] = var

                cb = ttk.Checkbutton(
                    tool_row,
                    text=tool_info['name'],
                    variable=var,
                    style='Category.TCheckbutton'
                )
                cb.pack(side=tk.LEFT, padx=(0, 10))

                desc_label = ttk.Label(
                    tool_row,
                    text=tool_info['desc'],
                    style='Config.TLabel',
                    font=("Arial", 9)
                )
                desc_label.pack(side=tk.LEFT, padx=(0, 10))

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

    def _rebuild_catalog_ui(self):
        """Recreate category frames when catalog or profile changes."""
        for child in list(self.tools_scroll_frame.winfo_children()):
            child.destroy()
        self.create_tool_categories()
        try:
            self.tools_canvas.configure(scrollregion=self.tools_canvas.bbox("all"))
        except Exception:
            pass

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
            catalog = self.available_tools or {}
            current_vars = getattr(self, "tool_vars", {}) or {}
            new_vars = {}

            for tools in catalog.values():
                for tool_key, tool_info in tools.items():
                    default_enabled = tool_info['risk'] != 'CRITICAL'
                    value = enabled_tools.get(tool_key, default_enabled)
                    existing_var = current_vars.get(tool_key)
                    if isinstance(existing_var, tk.BooleanVar):
                        existing_var.set(bool(value))
                        new_vars[tool_key] = existing_var
                    else:
                        new_vars[tool_key] = tk.BooleanVar(value=bool(value))

            self.tool_vars = new_vars

            missing = sorted(set(enabled_tools.keys()) - set(self.tool_vars.keys()))
            if missing:
                log_message(f"TOOLS_TAB: Ignored {len(missing)} unknown tools from profile: {missing[:5]}")

            log_message(f"TOOLS_TAB: Loaded {len(self.tool_vars)} tool settings from profile")
        except Exception as e:
            log_message(f"TOOLS_TAB ERROR: Failed to load tool settings: {e}")
            # Fallback to defaults
            fallback_vars = {}
            for tools in (self.available_tools or {}).values():
                for tool_key, tool_info in tools.items():
                    default_enabled = tool_info['risk'] != 'CRITICAL'
                    fallback_vars[tool_key] = tk.BooleanVar(value=default_enabled)
            self.tool_vars = fallback_vars

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
            for tools in (self.available_tools or {}).values():
                for tool_key, tool_info in tools.items():
                    default_enabled = tool_info['risk'] != 'CRITICAL'
                    if tool_key in self.tool_vars:
                        self.tool_vars[tool_key].set(default_enabled)

            log_message("TOOLS_TAB: Reset to defaults")

    def on_profile_changed(self, event=None):
        """Handle profile selection change"""
        new_profile = self.current_profile_name.get()
        log_message(f"TOOLS_TAB: Switching to profile '{new_profile}'")

        type(self).initialize_catalog()
        self.available_tools = type(self).AVAILABLE_TOOLS or {}

        # Reload from new profile
        self.profile = self.load_profile()
        self.load_tool_settings_from_profile()
        self._rebuild_catalog_ui()

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
        return {key: bool(var.get()) for key, var in self.tool_vars.items()}

    def refresh(self):
        """Refresh the tools tab"""
        log_message("TOOLS_TAB: Refreshing...")
        type(self).AVAILABLE_TOOLS = type(self).build_available_tools()
        self.available_tools = type(self).AVAILABLE_TOOLS or {}

        self.profile = self.load_profile()
        self.load_tool_settings_from_profile()
        self._rebuild_catalog_ui()
