"""
Settings Tab - Application configuration and preferences
Isolated module for settings-related functionality#
"""

import tkinter as tk
from tkinter import ttk, scrolledtext
import tkinter.messagebox as messagebox
import json
from pathlib import Path
import os
import sys
import glob
from datetime import datetime
import logger_util
import recovery_util
from logger_util import log_message
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from tabs.base_tab import BaseTab
from config import TRAINER_ROOT, DATA_DIR, MODELS_DIR


class SettingsTab(BaseTab):
    """Application settings and configuration tab"""

    def __init__(self, parent, root, style, main_gui=None, tab_instances=None):
        super().__init__(parent, root, style)

        # Reference to main GUI (for accessing other tabs)
        self.main_gui = main_gui
        self.tab_instances = tab_instances

        # Debug tab variables
        self.log_poll_job = None
        self.current_log_file = None
        self.last_read_position = 0

        # Changes polling variables
        self.changes_poll_job = None
        self.last_manifest_mtime = None
        self.log_file_paths = {} # Corrected indentation
        self.tab_enabled_vars = {} # For managing tab visibility
        self.reorder_mode = tk.StringVar(value='static') # New setting for tab reordering
        self.right_click_enabled = tk.BooleanVar(value=True) # Global right-click menu toggle
        self.right_click_tab_overrides = {}  # {tab_name: BooleanVar} per-tab overrides
        self.right_click_subtab_overrides = {}  # {tab_name.sub_label: BooleanVar} per-sub-tab overrides
        # Settings file
        self.settings_file = DATA_DIR / "settings.json"
        self.settings = self.load_settings()
        # Manifest data for undo operations
        self.current_manifest = {}

    def create_ui(self):
        """Create the settings tab UI with side menu and sub-tabs"""
        self.parent.columnconfigure(0, weight=1)
        self.parent.columnconfigure(1, weight=0)
        self.parent.rowconfigure(0, weight=1)

        # Left side: Settings content with sub-tabs
        settings_content_frame = ttk.Frame(self.parent, style='Category.TFrame')
        settings_content_frame.grid(row=0, column=0, sticky=tk.NSEW, padx=10, pady=10)
        settings_content_frame.columnconfigure(0, weight=1)
        settings_content_frame.rowconfigure(1, weight=1)

        # Header with title and refresh buttons
        header_frame = ttk.Frame(settings_content_frame, style='Category.TFrame')
        header_frame.grid(row=0, column=0, sticky=tk.EW, pady=5)
        header_frame.columnconfigure(0, weight=1)

        ttk.Label(header_frame, text="⚙️ Settings",
                 font=("Arial", 14, "bold"), style='CategoryPanel.TLabel').pack(side=tk.LEFT, padx=(0, 10))

        log_message("SETTINGS: Creating Quick Restart button.")
        # Quick Restart button
        quick_restart_btn = ttk.Button(header_frame, text="🚀 Quick Restart",
                  command=self.quick_restart_application,
                  style='Action.TButton')
        quick_restart_btn.pack(side=tk.RIGHT, padx=(5, 0))
        print(f"DEBUG: Quick Restart button created. Command bound to: {quick_restart_btn.cget('command')}")
        log_message(f"SETTINGS: Quick Restart button created. Command bound to: {quick_restart_btn.cget('command')}")

        # Settings tab refresh button
        ttk.Button(header_frame, text="🔄 Refresh Settings",
                  command=self.refresh_settings_tab,
                  style='Select.TButton').pack(side=tk.RIGHT, padx=5)

        # Sub-tabs notebook
        self.settings_notebook = ttk.Notebook(settings_content_frame)
        self.settings_notebook.grid(row=1, column=0, sticky=tk.NSEW, padx=5, pady=5)

        # General Settings Tab
        self.general_tab_frame = ttk.Frame(self.settings_notebook)
        self.settings_notebook.add(self.general_tab_frame, text="General")
        self.create_general_settings(self.general_tab_frame)

        # Paths Tab
        self.paths_tab_frame = ttk.Frame(self.settings_notebook)
        self.settings_notebook.add(self.paths_tab_frame, text="Paths")
        self.create_path_settings(self.paths_tab_frame)

        # Training Defaults Tab
        self.training_tab_frame = ttk.Frame(self.settings_notebook)
        self.settings_notebook.add(self.training_tab_frame, text="Training Defaults")
        self.create_training_defaults(self.training_tab_frame)

        # Interface Tab
        self.interface_tab_frame = ttk.Frame(self.settings_notebook)
        self.settings_notebook.add(self.interface_tab_frame, text="Interface")
        self.create_ui_settings(self.interface_tab_frame)

        # Tab Manager Tab
        self.tab_manager_frame = ttk.Frame(self.settings_notebook)
        self.settings_notebook.add(self.tab_manager_frame, text="Tab Manager")
        self.create_tab_manager(self.tab_manager_frame)

        # Resources Tab
        self.resources_tab_frame = ttk.Frame(self.settings_notebook)
        self.settings_notebook.add(self.resources_tab_frame, text="Resources")
        self.create_resource_settings(self.resources_tab_frame)

        # Custom Code Tab
        self.custom_code_settings_frame = ttk.Frame(self.settings_notebook)
        self.settings_notebook.add(self.custom_code_settings_frame, text="Custom Code")
        self.create_custom_code_settings(self.custom_code_settings_frame)

        # Backups & Logs Tab
        self.debug_tab_frame = ttk.Frame(self.settings_notebook)
        self.settings_notebook.add(self.debug_tab_frame, text="Backups & Logs")
        self.create_debug_tab(self.debug_tab_frame)

        # System Blueprints Tab
        self.blueprints_tab_frame = ttk.Frame(self.settings_notebook)
        self.settings_notebook.add(self.blueprints_tab_frame, text="System Blueprints")
        self.create_blueprints_tab(self.blueprints_tab_frame)

        # Help & Guide Tab
        self.help_tab_frame = ttk.Frame(self.settings_notebook)
        self.settings_notebook.add(self.help_tab_frame, text="Help & Guide")
        self.create_help_tab(self.help_tab_frame)

        # Bind sub-tab change event
        self.settings_notebook.bind("<<NotebookTabChanged>>", self._on_sub_tab_changed)

        # Right side: Settings categories menu
        self.create_right_panel(self.parent)

    def _on_sub_tab_changed(self, event):
        """Switch between help menu and backup manager based on selected sub-tab."""
        selected_tab_index = self.settings_notebook.index(self.settings_notebook.select())
        selected_tab_text = self.settings_notebook.tab(selected_tab_index, "text")

        if selected_tab_text == "Backups & Logs":
            self.help_menu_frame.grid_remove()
            self.backup_frame.grid()
            self.populate_backup_tree() # Fresh load on entry
            self.start_backup_polling() # Start periodic refresh
        else:
            self.stop_backup_polling()
            self.backup_frame.grid_remove()
            self.help_menu_frame.grid()

    def start_backup_polling(self):
        """Periodic refresh of the backup tree to catch live watcher updates."""
        if hasattr(self, 'backup_poll_job') and self.backup_poll_job:
            self.parent.after_cancel(self.backup_poll_job)
        self.poll_backups()

    def stop_backup_polling(self):
        """Stops the periodic refresh of the backup tree."""
        if hasattr(self, 'backup_poll_job') and self.backup_poll_job:
            self.parent.after_cancel(self.backup_poll_job)
            self.backup_poll_job = None

    def poll_backups(self):
        """Refreshes the tree if 'Backups & Logs' is still the active sub-tab."""
        # Only poll if this tab is visible and sub-tab is active
        try:
            selected_tab_index = self.settings_notebook.index(self.settings_notebook.select())
            if self.settings_notebook.tab(selected_tab_index, "text") == "Backups & Logs":
                self.populate_backup_tree()
                self.backup_poll_job = self.parent.after(10000, self.poll_backups) # Every 10s
        except Exception: pass

    def create_backup_manager_ui(self, parent):
        """Creates the Backup Manager interface."""
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(0, weight=1)

        # Main Layout: PanedWindow (Vertical) - Tree on top, Details on bottom
        paned = ttk.PanedWindow(parent, orient=tk.VERTICAL)
        paned.grid(row=0, column=0, sticky='nsew', padx=5, pady=5)

        # --- Top: Tree View ---
        tree_frame = ttk.Frame(paned, style='Category.TFrame')
        paned.add(tree_frame, weight=3)
        tree_frame.columnconfigure(0, weight=1)
        tree_frame.rowconfigure(1, weight=1)

        # Header
        header = ttk.Frame(tree_frame)
        header.grid(row=0, column=0, sticky='ew', padx=5, pady=5)
        ttk.Label(header, text="🛡️ Backup History & Health", font=('Arial', 10, 'bold'), style='CategoryPanel.TLabel').pack(side=tk.LEFT)
        ttk.Button(header, text="🔄 Refresh", command=self.populate_backup_tree, style='Select.TButton').pack(side=tk.RIGHT)

        # Tree
        self.backup_tree = ttk.Treeview(tree_frame, selectmode='browse', show='tree headings')
        self.backup_tree.grid(row=1, column=0, sticky='nsew', padx=5, pady=5)
        
        # Scrollbar
        sb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.backup_tree.yview)
        sb.grid(row=1, column=1, sticky='ns')
        self.backup_tree.configure(yscrollcommand=sb.set)

        self.backup_tree.heading('#0', text='File / Status / Backup Timestamp')
        self.backup_tree.bind('<<TreeviewSelect>>', self.on_backup_select)
        self.backup_tree.bind('<<TreeviewOpen>>', self._on_backup_tree_expand)

        # --- COORDINATED COLORATION SYSTEM ---
        # Unified status colors and styles
        self.status_colors = {
            'error': '#ff5555',     # Red
            'warning': '#ffaa00',   # Orange
            'active': '#55ff55',    # Green
            'stable': '#ffffff',    # White
            'backup': '#aaaaaa',    # Grey
            'tab': '#61dafb'        # Cyan
        }

        for tree in [self.backup_tree]:
            tree.tag_configure('error', foreground=self.status_colors['error'], font=('Arial', 10, 'bold'))
            tree.tag_configure('warning', foreground=self.status_colors['warning'], font=('Arial', 10, 'bold'))
            tree.tag_configure('active', foreground=self.status_colors['active'], font=('Arial', 10, 'bold'))
            tree.tag_configure('stable', foreground=self.status_colors['stable'])
            tree.tag_configure('backup', foreground=self.status_colors['backup'])
            tree.tag_configure('tab', foreground=self.status_colors['tab'], font=('Arial', 10, 'bold'))

        # --- Bottom: Detail View ---
        detail_frame = ttk.Frame(paned, style='Category.TFrame')
        paned.add(detail_frame, weight=2) # Give more weight to details
        detail_frame.columnconfigure(0, weight=1)
        detail_frame.rowconfigure(1, weight=1) # Text area expands
        
        ttk.Label(detail_frame, text="📋 Backup Details", font=('Arial', 10, 'bold'), style='CategoryPanel.TLabel').grid(row=0, column=0, sticky='w', padx=5, pady=5)
        
        # Scrollable Text Area for Details
        detail_text_container = ttk.Frame(detail_frame)
        detail_text_container.grid(row=1, column=0, sticky='nsew', padx=5, pady=5)
        detail_text_container.columnconfigure(0, weight=1)
        detail_text_container.rowconfigure(0, weight=1)

        self.backup_details_text = tk.Text(detail_text_container, height=12, width=40, state='disabled', bg='#1e1e1e', fg='#d4d4d4', font=('Courier', 9), relief='flat')
        self.backup_details_text.grid(row=0, column=0, sticky='nsew')
        
        detail_sb = ttk.Scrollbar(detail_text_container, orient="vertical", command=self.backup_details_text.yview)
        detail_sb.grid(row=0, column=1, sticky='ns')
        self.backup_details_text.configure(yscrollcommand=detail_sb.set)

        # Action buttons frame
        self.backup_action_frame = ttk.Frame(detail_frame)
        self.backup_action_frame.grid(row=2, column=0, sticky='ew', padx=5, pady=5)

        # Initial Population
        self.populate_backup_tree()

    def _scan_for_file_errors(self):
        """Scans the latest debug log for filenames associated with errors."""
        error_counts = {}
        try:
            log_path = logger_util.get_log_file_path()
            if not log_path or not os.path.exists(log_path): return {}
            
            with open(log_path, 'r') as f:
                log_content = f.read()
            
            import re
            # Matches: File "/path/to/file.py", line 123
            pattern = re.compile(r'File "([^"]+)", line \d+')
            matches = pattern.findall(log_content)
            
            for absolute_path in matches:
                # Normalize path separators
                path_str = str(Path(absolute_path))
                # Check if it's in our Data directory
                if str(TRAINER_ROOT) in path_str:
                    try:
                        # Extract relative path to match manifest keys
                        rel_path = str(Path(absolute_path).relative_to(TRAINER_ROOT))
                        error_counts[rel_path] = error_counts.get(rel_path, 0) + 1
                    except ValueError:
                        pass
        except Exception:
            pass
        return error_counts

    def populate_backup_tree(self):
        """Populates the backup tree with lazy-loaded file-first layout.

        Structure:
          📦 System Versions (N)        — all unique backup timestamps, grouped by date
          🟠 Live Changes (Unsaved)     — if any pending changes
          📂 File Backup History (N)    — each tracked file, backups loaded on expand
        """
        for item in self.backup_tree.get_children():
            self.backup_tree.delete(item)
        self._lazy_loaded_nodes = set()

        # --- Load data sources ---
        self.version_manifest = recovery_util.load_version_manifest()
        self._enriched_changes = self.version_manifest.get("enriched_changes", {})
        history_root = DATA_DIR / "backup" / "history"
        default_v = self.version_manifest.get("default_version")
        vm_versions = self.version_manifest.get("versions", {})

        # --- Collect ALL unique timestamps (fast: scan top 5 busiest history dirs only) ---
        all_timestamps = set(vm_versions.keys())
        if history_root.exists():
            # Find top dirs by file count (use dir size as proxy — faster than counting)
            h_dirs = []
            for hdir in history_root.iterdir():
                if hdir.is_dir():
                    try:
                        h_dirs.append((hdir, hdir.stat().st_mtime))
                    except OSError:
                        pass
            # Sort by mtime desc, scan top 10 for timestamps (covers 90%+ of unique ts)
            h_dirs.sort(key=lambda x: x[1], reverse=True)
            for hdir, _ in h_dirs[:10]:
                try:
                    for f in hdir.iterdir():
                        stem = f.stem
                        if len(stem) == 15 and '_' in stem:  # YYYYMMDD_HHMMSS format
                            all_timestamps.add(stem)
                except OSError:
                    pass

        # --- Section 1: System Versions (grouped by date) ---
        sorted_ts = sorted(all_timestamps, reverse=True)
        self.all_good_versions = sorted_ts

        if sorted_ts:
            versions_node = self.backup_tree.insert(
                '', 'end',
                text=f"📦 System Versions ({len(sorted_ts)})",
                open=True, tags=('stable',), values=("", "section")
            )
            current_date = None
            date_node = None
            for ts in sorted_ts:
                try:
                    dt = datetime.strptime(ts, "%Y%m%d_%H%M%S")
                    date_str = dt.strftime("%Y-%m-%d")
                    display_time = dt.strftime("%H:%M:%S")

                    # Group by date
                    if date_str != current_date:
                        current_date = date_str
                        # Count how many in this date
                        n_in_date = sum(1 for t in sorted_ts if t.startswith(ts[:8]))
                        date_node = self.backup_tree.insert(
                            versions_node, 'end',
                            text=f"📅 {date_str} ({n_in_date} versions)",
                            open=(date_str == dt.today().strftime("%Y-%m-%d")),
                            tags=('stable',), values=("", "date_group")
                        )

                    # Determine status
                    vm_entry = vm_versions.get(ts)
                    is_default = (ts == default_v)
                    if vm_entry:
                        status = self._infer_version_status(ts, vm_entry)
                    else:
                        status = "archived"  # exists in history but not in version_manifest

                    icon, tag = self._status_icon_tag(status)
                    prefix = "⭐ " if is_default else ""
                    self.backup_tree.insert(
                        date_node, 'end',
                        text=f"{prefix}{icon} {display_time} ({status.upper()})",
                        values=(ts, 'version'), tags=(tag,)
                    )
                except (ValueError, Exception):
                    continue

        # --- Section 2: Live Changes ---
        pending = self.version_manifest.get("pending_live_changes", {})
        if pending:
            live_node = self.backup_tree.insert(
                '', 'end', text=f"🟠 Live Changes ({len(pending)} unsaved)",
                open=True, tags=('warning',), values=("", "section")
            )
            for rel_path in sorted(pending.keys()):
                self.backup_tree.insert(
                    live_node, 'end', text=f"📝 {rel_path}",
                    values=(rel_path, 'live_change'), tags=('backup',)
                )

        # --- Section 3: File Backup History (lazy-loaded from manifest.json only) ---
        manifest_path = DATA_DIR / "backup" / "manifest.json"
        manifest = {}
        if manifest_path.exists():
            try:
                with open(manifest_path, 'r') as f:
                    manifest = json.load(f)
            except Exception:
                pass

        error_counts = self._scan_for_file_errors()

        # Sort manifest entries by last_modified descending
        sorted_files = sorted(
            manifest.items(),
            key=lambda x: x[1].get('last_modified', 0),
            reverse=True
        )

        if sorted_files:
            files_section = self.backup_tree.insert(
                '', 'end',
                text=f"📂 File Backup History ({len(sorted_files)} files)",
                open=False, tags=('stable',), values=("", "section")
            )

            for file_rel_path, manifest_data in sorted_files:
                feature = recovery_util.get_feature_for_path(file_rel_path)
                errors = error_counts.get(file_rel_path, 0)
                last_mod = manifest_data.get('last_modified', 0)
                time_since_mod = datetime.now().timestamp() - last_mod if last_mod else 99999

                file_status, file_icon, file_tag = self._infer_file_status(
                    file_rel_path, errors, time_since_mod
                )

                display_text = f"{file_icon} {file_rel_path} [{feature}] {file_status}"

                file_node = self.backup_tree.insert(
                    files_section, 'end', text=display_text, open=False,
                    values=(file_rel_path, 'file'), tags=(file_tag,)
                )

                # Lazy-load placeholder (always insert — real count on expand)
                self.backup_tree.insert(
                    file_node, 'end', text="⏳ Loading...",
                    values=("", "lazy_placeholder"), tags=('backup',)
                )

    def _on_backup_tree_expand(self, event):
        """Lazy-load backup versions when a file node is expanded."""
        item = self.backup_tree.focus()
        if not item:
            return
        values = self.backup_tree.item(item, "values")
        if not values or len(values) < 2:
            return

        path_str, type_ = values[0], values[1]

        # Only lazy-load file nodes
        if type_ != 'file':
            return
        if item in getattr(self, '_lazy_loaded_nodes', set()):
            return

        # Remove placeholder children
        for child in self.backup_tree.get_children(item):
            child_vals = self.backup_tree.item(child, "values")
            if child_vals and len(child_vals) >= 2 and child_vals[1] == "lazy_placeholder":
                self.backup_tree.delete(child)

        self._lazy_loaded_nodes.add(item)

        # Load actual backups
        safe_key = path_str.replace("/", "_").replace("\\", "_").replace(":", "")
        backup_dir = DATA_DIR / "backup" / "history" / safe_key
        backups_found = []

        if backup_dir.exists() and backup_dir.is_dir():
            for backup_file in backup_dir.iterdir():
                if backup_file.suffix not in ('.py', '.json', '.md'):
                    continue
                try:
                    ts_str = backup_file.stem
                    datetime.strptime(ts_str, "%Y%m%d_%H%M%S")
                    size_kb = backup_file.stat().st_size / 1024
                    backups_found.append({
                        'path': str(backup_file),
                        'ts': ts_str,
                        'size_kb': size_kb,
                    })
                except (ValueError, OSError):
                    pass

        # Also check for bulk backup pointer from manifest
        manifest_path = DATA_DIR / "backup" / "manifest.json"
        if manifest_path.exists():
            try:
                with open(manifest_path, 'r') as f:
                    m = json.load(f)
                mdata = m.get(path_str, {})
                ptr = mdata.get('latest_backup', '')
                if "backup_" in ptr:
                    full_bulk = DATA_DIR / "backup" / ptr
                    if full_bulk.exists():
                        backups_found.append({
                            'path': str(full_bulk),
                            'ts': "00000000_000000",
                            'size_kb': full_bulk.stat().st_size / 1024,
                            'bulk': True,
                        })
            except Exception:
                pass

        backups_found.sort(key=lambda x: x['ts'], reverse=True)

        # Check version statuses for each backup timestamp
        version_statuses = self.version_manifest.get("versions", {})

        for bk in backups_found:
            if bk.get('bulk'):
                text = f"📦 Initial/Bulk Snapshot ({bk['size_kb']:.0f} KB)"
                tag = 'stable'
            else:
                try:
                    dt = datetime.strptime(bk['ts'], "%Y%m%d_%H%M%S")
                    display = dt.strftime("%Y-%m-%d %H:%M:%S")
                except ValueError:
                    display = bk['ts']

                # Cross-reference with version status
                v_entry = version_statuses.get(bk['ts'])
                if v_entry:
                    v_status = self._infer_version_status(bk['ts'], v_entry)
                    icon, tag = self._status_icon_tag(v_status)
                    text = f"{icon} {display} ({bk['size_kb']:.0f} KB) [{v_status.upper()}]"
                else:
                    text = f"🕒 {display} ({bk['size_kb']:.0f} KB)"
                    tag = 'backup'

            self.backup_tree.insert(
                item, 'end', text=text,
                values=(bk['path'], 'backup'), tags=(tag,)
            )

        if not backups_found:
            self.backup_tree.insert(
                item, 'end', text="(No backups found)",
                values=("", "info"), tags=('backup',)
            )

    def _status_icon_tag(self, status):
        """Return (icon, tree_tag) for a version status string."""
        _map = {
            "stable":       ("✅", "active"),
            "unstable":     ("⚠️",  "warning"),
            "damaged":      ("❌", "error"),
            "testing":      ("🧪", "warning"),
            "pending":      ("⏳", "stable"),
            "initializing": ("⏳", "stable"),
            "archived":     ("📋", "backup"),
            "unknown":      ("❓", "stable"),
        }
        return _map.get(status, ("❓", "stable"))

    def _infer_version_status(self, ts, entry):
        """Infer version status from manifest entry + enriched_changes probe data.

        Status hierarchy:
          damaged    — crash before LAUNCH_SUCCESS (or manually marked)
          unstable   — launched but has probe failures OR failed tabs
          testing    — marked as testing (Quick Restart target)
          pending    — just created, not yet validated
          stable     — launched OK, no probe failures
          initializing — first run, not yet completed
        """
        explicit = entry.get("status", "unknown")

        # Trust explicit damaged mark
        if explicit == "damaged":
            return "damaged"

        # If explicitly set to testing/pending, keep it
        if explicit in ("testing", "pending"):
            return explicit

        # Check for failed tabs
        failed_tabs = entry.get("failed_tabs", [])
        if failed_tabs:
            return "unstable"

        # Check enriched_changes for probe/test failures in this version
        if hasattr(self, '_enriched_changes'):
            _fails = 0
            _unresolved = 0
            for eid, ch in self._enriched_changes.items():
                if ch.get("version_ts") != ts:
                    continue
                if ch.get("probe_status") == "FAIL" or ch.get("test_status") == "FAIL":
                    _fails += 1
                    if not ch.get("resolved_by"):
                        _unresolved += 1

            if _unresolved > 0:
                return "unstable"

        # If explicitly stable or unknown with no failures → stable
        if explicit in ("stable", "unknown"):
            return "stable" if explicit == "stable" else entry.get("status", "unknown")

        return explicit

    def _infer_file_status(self, file_rel_path, errors, time_since_mod):
        """Infer per-file health from errors, recency, and enriched probe data.

        Returns: (status_text, icon, tag)
        """
        # Check enriched_changes for probe failures on this file
        _probe_fails = 0
        _unresolved_probes = 0
        if hasattr(self, '_enriched_changes'):
            for eid, ch in self._enriched_changes.items():
                if not ch.get("file", "").endswith(Path(file_rel_path).name):
                    continue
                if ch.get("probe_status") == "FAIL" or ch.get("test_status") == "FAIL":
                    _probe_fails += 1
                    if not ch.get("resolved_by"):
                        _unresolved_probes += 1

        if errors > 0 or _unresolved_probes > 0:
            parts = []
            if errors > 0:
                parts.append(f"{errors} errors")
            if _unresolved_probes > 0:
                parts.append(f"{_unresolved_probes} probe fails")
            return f"({', '.join(parts)})", "🔴", "error"
        elif time_since_mod < 3600:
            return "(Active)", "🟢", "active"
        else:
            return "", "⚪", "stable"

    def on_backup_select(self, event):
        """Handles selection of a backup item."""
        selected = self.backup_tree.selection()
        if not selected: return
        
        item_id = selected[0]
        item_text = self.backup_tree.item(item_id, "text")
        values = self.backup_tree.item(item_id, "values")
        
        if not values: return
        
        path_str, type_ = values
        
        # Clear previous action buttons
        for widget in self.backup_action_frame.winfo_children():
            widget.destroy()

        info = ""
        if type_ == 'file':
             feature = recovery_util.get_feature_for_path(path_str)
             info = f"FILE: {path_str}\n"
             info += f"ASSIGNMENT: {feature}\n\n"
             
             # --- COORDINATION: Fetch Blame History for this file ---
             history = recovery_util.get_blame_for_file(path_str)
             if history:
                 info += "🚨 CRASH/BLAME HISTORY:\n"
                 for entry in history:
                     b = entry["blame"]
                     status = entry["status"].upper()
                     info += f"  • VERSION: {entry['version']} [{status}]\n"
                     info += f"    TARGET: {b.get('target')}\n"
                     info += f"    LINE: {b.get('line', '?')}\n"
                     if entry.get("traceback"):
                         snippet = entry["traceback"][-150:].replace("\n", " ")
                         info += f"    ERROR: ...{snippet}\n"
                     info += "\n"
             else:
                 info += "Status: No historic crashes recorded in manifest.\n\n"
                 info += "Select a timestamp below to view specific backup details."

        elif type_ == 'backup':
             p = Path(path_str)
             if p.exists():
                 stats = p.stat()
                 size_kb = stats.st_size / 1024
                 mtime = datetime.fromtimestamp(stats.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
                 
                 info = f"BACKUP: {item_text}\n"
                 info += f"Path: {p}\n"
                 info += f"Size: {size_kb:.2f} KB\n"
                 info += f"Created: {mtime}\n"
             else:
                 info = "File not found."
        elif type_ == 'version':
            version_ts = path_str
            entry = self.version_manifest["versions"].get(version_ts, {})

            status = entry.get("status", "unknown") if entry else "archived"
            changes = entry.get("files_changed", [])
            diffs = entry.get("diffs", [])

            info = f"SYSTEM VERSION: {item_text}\n"
            info += f"Timestamp: {version_ts}\n"
            info += f"Status: {status.upper()}\n"
            if entry.get("is_default"):
                info += "DEFAULT STATE: YES (Rollback point)\n"

            if status in ["damaged", "unstable"]:
                info += f"\n🚨 {status.upper()} CONTEXT:\n"
                blame_list = entry.get("blame", [])
                if blame_list:
                    info += "BLAME TARGETS:\n"
                    for b in blame_list:
                        if isinstance(b, dict):
                            mark = " [MODIFIED]" if b.get("modified_this_version") else ""
                            feat = f"({b.get('feature', 'Core')})"
                            info += f"  • {feat} {b.get('target', 'Unknown')}{mark} (Line {b.get('line', '?')})\n"
                        else:
                            info += f"  • {b}\n"
                info += f"\nTRACEBACK:\n{entry.get('traceback', 'N/A')}\n"

            if changes:
                info += f"\nFiles modified in this state ({len(changes)}):\n"
                for change in changes:
                    info += f"  • {change}\n"

            # For archived versions (not in version_manifest), scan history for files at this timestamp
            if not entry:
                info += "\n📋 ARCHIVED — backup files at this timestamp:\n"
                _history_root = DATA_DIR / "backup" / "history"
                if _history_root.exists():
                    _found = []
                    for _hdir in _history_root.iterdir():
                        if not _hdir.is_dir():
                            continue
                        _bk = _hdir / f"{version_ts}.py"
                        if not _bk.exists():
                            _bk = _hdir / f"{version_ts}.json"
                        if _bk.exists():
                            _size = _bk.stat().st_size / 1024
                            _found.append((_hdir.name, _size, str(_bk)))
                    for _name, _sz, _path in sorted(_found):
                        info += f"  • {_name} ({_sz:.0f} KB)\n"
                    if not _found:
                        info += "  (no backup files found)\n"

            if diffs:
                info += "\n--- CODE DIFF SUMMARY ---\n"
                for diff in diffs:
                    info += diff + "\n"
            
            # Action Buttons
            btn_restore = ttk.Button(
                self.backup_action_frame,
                text=f"🔄 Restore System to {version_ts}",
                command=lambda v=version_ts: self.restore_system_version(v),
                style='Action.TButton'
            )
            btn_restore.pack(side=tk.LEFT, padx=5)

            if not entry.get("is_default") and status == "stable":
                btn_default = ttk.Button(
                    self.backup_action_frame,
                    text="⭐ Set as Default",
                    command=lambda v=version_ts: self.set_as_default(v),
                    style='Select.TButton'
                )
                btn_default.pack(side=tk.LEFT, padx=5)
        
        elif type_ == 'live_change':
            rel_path = path_str
            pending = self.version_manifest.get("pending_live_changes", {})
            pending_data = pending.get(rel_path, "No diff available.")

            # Handle tuple format: (diff_text, before_content, after_content)
            if isinstance(pending_data, tuple) and len(pending_data) >= 1:
                diff_text = pending_data[0]
            else:
                diff_text = pending_data

            info = f"LIVE CHANGE: {rel_path}\n"
            info += "Status: UNSAVED (Modified since last launch)\n"
            info += "\n--- LIVE DIFF (Reference vs Current) ---\n"
            info += str(diff_text)

        self.backup_details_text.config(state='normal')
        self.backup_details_text.delete(1.0, tk.END)
        self.backup_details_text.insert(tk.END, info)
        self.backup_details_text.config(state='disabled')

    def restore_system_version(self, version_ts):
        """Initiates a direct system restore to a specific version."""
        msg = (f"⚠️ WARNING: This will overwrite your current project files with the versions from {version_ts}.\n\n"
               "Unsaved changes in the current state will be lost.\n\n"
               "Are you sure you want to proceed with this system restore?")
        
        if messagebox.askyesno("Confirm System Restore", msg):
            success, message = recovery_util.restore_project_to_version(version_ts)
            if success:
                messagebox.showinfo("Restore Succeeded", f"{message}\n\nPlease Quick Restart the application to apply changes.")
            else:
                messagebox.showerror("Restore Failed", f"Error during restore: {message}")

    def set_as_default(self, version_ts):
        """Designates a version as the system default."""
        if recovery_util.set_default_version(version_ts):
            messagebox.showinfo("Default Updated", f"Version {version_ts} is now the default for rollbacks.")
            self.populate_backup_tree()
            self.on_tree_select(None) # Refresh inspector
        else:
            messagebox.showerror("Error", "Could not set default version.")



    def create_right_panel(self, parent):
        """Create the right-side panel which can contain either the help menu or the terminal."""
        self.right_panel = ttk.Frame(parent)
        self.right_panel.grid(row=0, column=1, sticky=tk.NSEW, padx=10, pady=10)
        self.right_panel.columnconfigure(0, weight=1)
        self.right_panel.rowconfigure(0, weight=1)

        # --- Help Menu Frame ---
        self.help_menu_frame = ttk.Frame(self.right_panel, style='Category.TFrame')
        self.help_menu_frame.grid(row=0, column=0, sticky='nsew')
        self.help_menu_frame.columnconfigure(0, weight=1)
        self.help_menu_frame.rowconfigure(1, weight=1)

        ttk.Label(self.help_menu_frame, text="🆘 Help Menu",
                 font=("Arial", 11, "bold"), style='CategoryPanel.TLabel').grid(
            row=0, column=0, pady=5, sticky=tk.W, padx=5
        )

        paned_window = ttk.PanedWindow(self.help_menu_frame, orient=tk.VERTICAL)
        paned_window.grid(row=1, column=0, sticky='nsew', padx=5, pady=5)

        tree_container = ttk.Frame(paned_window)
        paned_window.add(tree_container, weight=1)
        tree_container.columnconfigure(0, weight=1)
        tree_container.rowconfigure(0, weight=1)

        tree_scroll = ttk.Scrollbar(tree_container, orient="vertical")
        tree_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.help_tree = ttk.Treeview(
            tree_container,
            yscrollcommand=tree_scroll.set,
            selectmode='browse',
            height=15
        )
        self.help_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tree_scroll.config(command=self.help_tree.yview)

        self.help_tree.heading('#0', text='Topic')
        self.help_tree.tag_configure('main_tab', font=('Arial', 10, 'bold'))
        self.help_tree.bind('<<TreeviewSelect>>', self.on_help_topic_select)
        
        self.populate_help_tree()

        help_text_frame = ttk.Frame(paned_window, style='Category.TFrame')
        paned_window.add(help_text_frame, weight=1)
        help_text_frame.columnconfigure(0, weight=1)
        help_text_frame.rowconfigure(0, weight=1)

        self.help_display = scrolledtext.ScrolledText(
            help_text_frame, wrap=tk.WORD, state=tk.DISABLED, font=("Arial", 9),
            bg="#1e1e1e", fg="#d4d4d4", relief='flat', padx=5, pady=5
        )
        self.help_display.grid(row=0, column=0, sticky='nsew')

        # --- Backup Manager Frame ---
        self.backup_frame = ttk.Frame(self.right_panel, style='Category.TFrame')
        self.backup_frame.grid(row=0, column=0, sticky='nsew')
        self.create_backup_manager_ui(self.backup_frame)
        self.backup_frame.grid_remove() # Hide it initially

    def populate_help_tree(self):
        """Populate the help tree with application structure and help text."""
        for item in self.help_tree.get_children():
            self.help_tree.delete(item)

        self.help_structure = {
            "Beginner’s Guide": {
                "description": "A step‑by‑step path from a fresh PyTorch model to a verified skillset: datasets → baseline → training → export → evaluation → compare.",
                "sub_tabs": {
                    "Getting Started": "Install or prepare a local PyTorch base model under Models/. In Models → Overview, select the base to work with. Ensure Ollama is running for inference (/api/chat).",
                    "Datasets": "Place evaluation suites under Training_Data‑Sets/Test (e.g., Tools/). Put training JSONL under Training_Data‑Sets (Tools, Coding, etc.). You can use or extend the examples provided.",
                    "Run Baseline": "Models → 🧪 Evaluation: choose a suite (e.g., Tools), select Tool Schema 'json_calls_full', and System Prompt 'Tools_JSON_Calls_Conformer'. Check 'Run as Baseline'. If no GGUF exists, export/pull first; the baseline will auto‑resume with the created tag and be saved under Models/benchmarks, set active.",
                    "Train & Level Up": "Training → Runner: commit your base and scripts, then train. Create Level 1 from adapters. Export level to GGUF (pick quant).",
                    "Evaluate & Compare": "Evaluate the Level; Compare vs the parent’s active baseline. Review overall Δ and per‑skill changes. History, Skills, and Baselines tabs update automatically.",
                    "Tips": "For Tools suite, json_calls_full + Tools_JSON_Calls_Conformer improves accuracy. Keep baselines full (no sampling). Use 'Create New' baselines to preserve history; optionally delete old when prompted."
                }
            },
            "Training Tab": {
                "description": "Prepare, run, and validate training. Left: sub‑tabs (Runner, Script Manager, Model Selection, Profiles, Summary). Right: selectors (Training Scripts, Prompts, Schemas).",
                "sub_tabs": {
                    "Runner": "Run training with a live console. Supports sequential execution (queues selected scripts) and delay between runs. Start/Stop/Clear/Status are fixed at the bottom for quick access. Early Stopping is shown only when a GPU is available. Save/Load Defaults persists runner controls.\n\nEvaluation Automation (scheduling): Auto‑run Baseline and Auto‑run Post‑Training.\nEvaluation Context: enable 'Use System Prompt' / 'Use Tool Schema' for automation.\nBaseline Controls: select baseline source (Auto/Base/Level) and open the Baselines manager.\n\n**(NEW)** Post-training evaluation is now automatically triggered after a training run, generating a report linked to the run's stats.",
                    "Script Manager": "A self-contained manager with three sub-tabs: 'Training Scripts', 'Prompts', and 'Schemas'. Each tab features an editor and a consistent set of action buttons at the bottom: `[➕ New File(s)] [📁 New Category] [💾 Save] [✏️ Rename] [🗑️ Delete] [❌ Clear] [📎 Copy]`. Selections in the main right-side panel of the Training Tab will load the corresponding file into the editor here.",
                    "Model Selection": "Dropdown lists only trainable models (local PyTorch and trained). Selecting shows detailed info (architecture, core parameters, latest training stats, and skills). Click 'Send To Training' to commit the selection (Runner's 'Training Model' updates then). Missing data is shown as 'Unverified'.",
                    "Profiles": "Save/load full setups: runner controls, committed model, right‑side selections (scripts/jsonl) and evaluation preferences (Use Prompt/Schema + selected names). Loading re‑applies toggles and selections.",
                    "Summary": "Read‑only preview: categories/files, core params, base model, and Use Prompt/Schema state (with names when enabled)."
                }
            },
            "Models Tab": {
                "description": "Inspect models, run evaluations, and compare results.",
                "sub_tabs": {
                    "Overview": "Parsed model info (type, path, size) and, when available, architecture/stats.",
                    "Raw Info": "Raw metadata (e.g., config.json) or Ollama show output.",
                    "Notes": "Free‑form notes per model.",
                    "Stats": "Training runs with filtering.\n\n**(NEW)** Now displays detailed evaluation results for each training run, including comparison against the active baseline (overall delta, regressions, improvements). Offers training suggestions if regressions are found.",
                    "Skills": "Skills aggregated from the latest evaluation report (per‑skill pass/total and status). **(NEW)** Now also displays the System Prompt and Tool Schema used for the evaluation.",
                    "🧪 Evaluation": "Suites come from `Training_Data-Sets/Test/<suite>`. Toggle 'Use System Prompt' / 'Use Tool Schema'. When a Tool Schema is selected, scoring is schema‑aware: tool name and args must validate against the schema before applying the test's policy (exact/partial/subset/function_call). 'Run as Pre‑Training Baseline' opens a confirm dialog and saves to `Models/benchmarks/`; otherwise to `Models/evaluations/`.",
                    "Baselines": "Manage baselines per model. View JSON, Set Active. Catalog stored at `Models/benchmarks/index.json`. Active baseline is used for regression checks and quick comparisons.",
                    "Compare": "Parent‑centric compare with three modes: (1) Baseline vs Baseline (Parent), (2) Latest Eval vs Reference (Parent), and (3) Advanced: Other Model (latest eval). Baseline lists autoload for the selected Parent with readable labels (date | pass% | suite | schema | prompt). Buttons below the result: '🧠 Generate Training Suggestions' (reason breakdown + JSONL stubs) and '💾 Save Example Stubs' (writes to Training_Data‑Sets/Tools).",
                    "Model List Sidebar": "Groups into Base (PyTorch), Trained, and Ollama (inference‑only)."
                }
            },
            "Settings Tab": {
                "description": "Global preferences and developer tools.",
                "sub_tabs": {
                    "General": "Overview and quick actions (save/reset settings).",
                    "Paths": "Key directories used by the app.",
                    "Training Defaults": "Default epochs/batch/lr used by Runner when not overridden.",
                    "Interface": "Tab visibility/order and reordering mode (static/dnd).",
                    "Tab Manager": "Create/edit tabs and panels programmatically.",
                    "Resources": "CPU threads, RAM %, seq length, gradient accumulation (applied in training).",
                    "Debug": "Live log viewer with history and 'Copy to Clipboard'. Captures wrapper early logs.",
                    "Evaluation Policy": "Regression checks: enable, drop threshold (in %), strict notifications; auto‑rollback is reserved for future use."
                }
            }
        }

        for main_tab_name, main_tab_data in self.help_structure.items():
            tab_node = self.help_tree.insert(
                '', 'end', text=main_tab_name, open=True, tags=('main_tab',)
            )
            # Add description for main tab
            if "description" in main_tab_data:
                self.help_tree.insert(tab_node, 'end', text="Description", tags=('description',))

            for sub_tab_name in main_tab_data.get("sub_tabs", {}).keys():
                self.help_tree.insert(tab_node, 'end', text=sub_tab_name)

    def on_help_topic_select(self, event):
        """Displays the help text for the selected topic."""
        selection = self.help_tree.selection()
        if not selection:
            return

        item_id = selection[0]
        parent_id = self.help_tree.parent(item_id)
        
        help_text = "No help available for this topic."

        if parent_id: # It's a sub-tab or a description node
            main_tab_text = self.help_tree.item(parent_id, 'text')
            item_text = self.help_tree.item(item_id, 'text')
            
            if item_text == "Description":
                help_text = self.help_structure.get(main_tab_text, {}).get("description", help_text)
            else:
                help_text = self.help_structure.get(main_tab_text, {}).get("sub_tabs", {}).get(item_text, help_text)
        else: # It's a main tab
            main_tab_text = self.help_tree.item(item_id, 'text')
            help_text = self.help_structure.get(main_tab_text, {}).get("description", help_text)

        self.help_display.config(state=tk.NORMAL)
        self.help_display.delete(1.0, tk.END)
        self.help_display.insert(tk.END, help_text)
        self.help_display.config(state=tk.DISABLED)

    def create_general_settings(self, parent):
        """Create general settings section using the proven scrollable layout pattern."""
        # This pattern (Canvas + Scrollbar + pack) is known to work from other tabs.
        canvas = tk.Canvas(parent, bg="#2b2b2b", highlightthickness=0)
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        content_frame = ttk.Frame(canvas, style='Category.TFrame')

        content_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas_window = canvas.create_window((0, 0), window=content_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True, padx=5, pady=5)
        scrollbar.pack(side="right", fill="y")

        canvas.bind("<Configure>", lambda e: canvas.itemconfig(canvas_window, width=e.width))
        
        content_frame.columnconfigure(0, weight=1) # Allow sections to expand horizontally

        # --- Content goes into content_frame using grid ---
        current_row = 0

        # Application info
        info_section = ttk.LabelFrame(content_frame, text="ℹ️ Application Info", style='TLabelframe')
        info_section.grid(row=current_row, column=0, sticky='ew', padx=10, pady=10); current_row += 1
        info_section.columnconfigure(1, weight=1)
        ttk.Label(info_section, text="Application:", font=("Arial", 10, "bold"), style='Config.TLabel').grid(row=0, column=0, sticky=tk.W, padx=10, pady=5)
        ttk.Label(info_section, text="OpenCode Trainer", style='Config.TLabel').grid(row=0, column=1, sticky=tk.W, padx=10, pady=5)
        ttk.Label(info_section, text="Version:", font=("Arial", 10, "bold"), style='Config.TLabel').grid(row=1, column=0, sticky=tk.W, padx=10, pady=5)
        ttk.Label(info_section, text="1.3 (Debug Enhanced)", style='Config.TLabel').grid(row=1, column=1, sticky=tk.W, padx=10, pady=5)
        ttk.Label(info_section, text="Location:", font=("Arial", 10, "bold"), style='Config.TLabel').grid(row=2, column=0, sticky=tk.W, padx=10, pady=5)
        ttk.Label(info_section, text=str(TRAINER_ROOT), style='Config.TLabel', wraplength=400, justify=tk.LEFT).grid(row=2, column=1, sticky=tk.W, padx=10, pady=5)

        # Quick actions
        actions_section = ttk.LabelFrame(content_frame, text="⚡ Quick Actions", style='TLabelframe')
        actions_section.grid(row=current_row, column=0, sticky='ew', padx=10, pady=10); current_row += 1
        actions_section.columnconfigure(0, weight=1)
        ttk.Button(actions_section, text="🔄 Refresh Ollama Models", command=self.refresh_models, style='Select.TButton').grid(row=0, column=0, sticky=tk.EW, padx=10, pady=5)
        ttk.Button(actions_section, text="🗑️ Clear Training Cache", command=self.clear_cache, style='Select.TButton').grid(row=1, column=0, sticky=tk.EW, padx=10, pady=5)
        ttk.Button(actions_section, text="📊 View System Info", command=self.show_system_info, style='Select.TButton').grid(row=2, column=0, sticky=tk.EW, padx=10, pady=5)

        # Main Action Buttons
        button_frame = ttk.Frame(content_frame, style='Category.TFrame')
        button_frame.grid(row=current_row, column=0, sticky='ew', padx=10, pady=(20, 10)); current_row += 1
        button_frame.columnconfigure(0, weight=1)
        button_frame.columnconfigure(1, weight=1)
        ttk.Button(button_frame, text="💾 Save All Settings", command=self.save_settings_to_file, style='Action.TButton').grid(row=0, column=0, padx=(0, 5), sticky=tk.EW)
        ttk.Button(button_frame, text="⚠️ Reset All Settings", command=self.reset_all_settings_to_default, style='Select.TButton').grid(row=0, column=1, padx=(5, 0), sticky=tk.EW)

    def reset_all_settings_to_default(self):
        """Resets all settings in this tab to their hardcoded default values."""
        if not messagebox.askyesno("Confirm Reset", "Are you sure you want to reset ALL settings to their original defaults?\nThis cannot be undone."):
            return

        log_message("SETTINGS: User initiated reset of all settings to default.")

        try:
            # Reset Training Defaults
            if hasattr(self, 'default_epochs'): self.default_epochs.set(3)
            if hasattr(self, 'default_batch'): self.default_batch.set(2)
            if hasattr(self, 'default_lr'): self.default_lr.set("2e-4")

            # Reset Interface
            if hasattr(self, 'auto_refresh'): self.auto_refresh.set(True)
            if hasattr(self, 'show_debug'): self.show_debug.set(False)
            if hasattr(self, 'confirm_training'): self.confirm_training.set(True)

            # Reset Resources
            if hasattr(self, 'max_cpu_threads'): self.max_cpu_threads.set(2)
            if hasattr(self, 'max_ram_percent'): self.max_ram_percent.set(70)
            if hasattr(self, 'max_seq_length'): self.max_seq_length.set(256)
            if hasattr(self, 'gradient_accumulation'): self.gradient_accumulation.set(16)

            log_message("SETTINGS: All settings variables have been reset in the UI.")
            messagebox.showinfo("Reset Complete", "All settings have been reset to their defaults. Click 'Save All Settings' to make them permanent.")
        except Exception as e:
            log_message(f"SETTINGS ERROR: Failed to reset settings. Error: {e}")
            messagebox.showerror("Reset Failed", f"An error occurred while resetting settings: {e}")

    def refresh_models(self):
        """Refresh Ollama models list"""
        messagebox.showinfo("Refresh Models", "Models list will be refreshed on next restart.")

    def clear_cache(self):
        """Clear training cache files"""
        if messagebox.askyesno("Clear Cache", "Clear all temporary training files?"):
            try:
                temp_files = list(DATA_DIR.glob("temp_*.jsonl"))
                for f in temp_files:
                    f.unlink()
                messagebox.showinfo("Cache Cleared", f"Removed {len(temp_files)} temporary files.")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to clear cache: {e}")

    def show_system_info(self):
        """Show system information"""
        import platform
        info = f"""System Information:

OS: {platform.system()} {platform.release()}
Python: {platform.python_version()}
Machine: {platform.machine()}

Trainer Root: {TRAINER_ROOT}
Models Dir: {MODELS_DIR}
Data Dir: {DATA_DIR}
"""
        messagebox.showinfo("System Info", info)

    def create_path_settings(self, parent):
        """Create path configuration section"""
        section = ttk.LabelFrame(parent, text="📁 Paths", style='TLabelframe')
        section.pack(fill=tk.X, pady=10)

        # Models directory
        ttk.Label(section, text="Models Directory:", style='Config.TLabel').grid(
            row=0, column=0, sticky=tk.W, padx=10, pady=5
        )
        models_path = ttk.Label(section, text=str(MODELS_DIR), style='Config.TLabel')
        models_path.grid(row=0, column=1, sticky=tk.W, padx=10, pady=5)

        # Training data directory
        ttk.Label(section, text="Training Data:", style='Config.TLabel').grid(
            row=1, column=0, sticky=tk.W, padx=10, pady=5
        )
        data_path = ttk.Label(section, text=str(TRAINER_ROOT / "Training_Data-Sets"),
                              style='Config.TLabel')
        data_path.grid(row=1, column=1, sticky=tk.W, padx=10, pady=5)

    def create_training_defaults(self, parent):
        """Create default training parameters section"""
        section = ttk.LabelFrame(parent, text="🎯 Training Defaults", style='TLabelframe')
        section.pack(fill=tk.X, pady=10)

        # Default epochs
        ttk.Label(section, text="Default Training Runs:", style='Config.TLabel').grid(
            row=0, column=0, sticky=tk.W, padx=10, pady=5
        )
        self.default_epochs = tk.IntVar(value=self.settings.get('default_epochs', 3))
        epochs_spin = ttk.Spinbox(
            section,
            from_=1,
            to=100,
            textvariable=self.default_epochs,
            width=10
        )
        epochs_spin.grid(row=0, column=1, sticky=tk.W, padx=10, pady=5)

        # Default batch size
        ttk.Label(section, text="Default Batch Size:", style='Config.TLabel').grid(
            row=1, column=0, sticky=tk.W, padx=10, pady=5
        )
        self.default_batch = tk.IntVar(value=self.settings.get('default_batch', 2))
        batch_spin = ttk.Spinbox(
            section,
            from_=1,
            to=32,
            textvariable=self.default_batch,
            width=10
        )
        batch_spin.grid(row=1, column=1, sticky=tk.W, padx=10, pady=5)

        # Default learning rate
        ttk.Label(section, text="Default Learning Strength:", style='Config.TLabel').grid(
            row=2, column=0, sticky=tk.W, padx=10, pady=5
        )
        self.default_lr = tk.StringVar(value=self.settings.get('default_learning_rate', '2e-4'))
        lr_entry = ttk.Entry(section, textvariable=self.default_lr, width=15)
        lr_entry.grid(row=2, column=1, sticky=tk.W, padx=10, pady=5)

    def create_ui_settings(self, parent):
        """Create UI preferences section"""
        section = ttk.LabelFrame(parent, text="🎨 Interface", style='TLabelframe')
        section.pack(fill=tk.X, pady=10)

        # Auto-refresh models list
        self.auto_refresh = tk.BooleanVar(value=self.settings.get('auto_refresh_models', True))
        ttk.Checkbutton(
            section,
            text="Auto-refresh models list on startup",
            variable=self.auto_refresh,
            style='Category.TCheckbutton'
        ).grid(row=0, column=0, sticky=tk.W, padx=10, pady=5)

        # Show debug info
        self.show_debug = tk.BooleanVar(value=self.settings.get('show_debug', False))
        ttk.Checkbutton(
            section,
            text="Show debug information",
            variable=self.show_debug,
            style='Category.TCheckbutton'
        ).grid(row=1, column=0, sticky=tk.W, padx=10, pady=5)

        # Confirm before training
        self.confirm_training = tk.BooleanVar(value=self.settings.get('confirm_training', True))
        ttk.Checkbutton(
            section,
            text="Confirm before starting training",
            variable=self.confirm_training,
            style='Category.TCheckbutton'
        ).grid(row=2, column=0, sticky=tk.W, padx=10, pady=5)

    def create_tab_manager(self, parent):
        """Create tab manager interface for creating/managing custom tabs"""
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(0, weight=1)

        # --- Scrollable Container Setup ---
        canvas = tk.Canvas(parent, bg="#2b2b2b", highlightthickness=0)
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        container = ttk.Frame(canvas) # Content frame

        container.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas_window = canvas.create_window((0, 0), window=container, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True, padx=5, pady=5)
        scrollbar.pack(side="right", fill="y")

        # Force container to expand to canvas width
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(canvas_window, width=e.width))

        # Configure container grid
        container.columnconfigure(0, weight=1)
        
        # --- Content Generation ---

        # Title
        ttk.Label(
            container,
            text="🗂️ Tab Manager - Create Custom Tabs",
            font=("Arial", 12, "bold"),
            style='CategoryPanel.TLabel'
        ).grid(row=0, column=0, pady=10, sticky=tk.W)

        # Create Tab Section
        create_frame = ttk.LabelFrame(container, text="➕ Create New Tab", style='TLabelframe')
        create_frame.grid(row=1, column=0, sticky=tk.EW, pady=10)

        # Tab name input
        name_frame = ttk.Frame(create_frame)
        name_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(name_frame, text="Tab Name:", style='Config.TLabel', width=15).pack(side=tk.LEFT, padx=(0, 10))
        self.new_tab_name = tk.StringVar()
        ttk.Entry(
            name_frame,
            textvariable=self.new_tab_name,
            font=("Arial", 10),
            width=30
        ).pack(side=tk.LEFT, fill=tk.X, expand=True)

        # Number of sub-tabs
        subtabs_frame = ttk.Frame(create_frame)
        subtabs_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Label(subtabs_frame, text="Sub-tabs:", style='Config.TLabel', width=15).pack(side=tk.LEFT, padx=(0, 10))
        self.num_subtabs = tk.IntVar(value=3)
        ttk.Spinbox(
            subtabs_frame,
            from_=1,
            to=10,
            textvariable=self.num_subtabs,
            width=10
        ).pack(side=tk.LEFT)

        # Side menu option
        options_frame = ttk.Frame(create_frame)
        options_frame.pack(fill=tk.X, padx=10, pady=10)

        self.has_side_menu = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            options_frame,
            text="Include side menu (like Model/Settings tabs)",
            variable=self.has_side_menu,
            style='Category.TCheckbutton'
        ).pack(anchor=tk.W)

        # Create button
        ttk.Button(
            create_frame,
            text="🚀 Create Tab",
            command=self.create_new_tab,
            style='Action.TButton'
        ).pack(pady=10, padx=10, fill=tk.X)


        # Onboard Standalone Script Section
        onboard_frame = ttk.LabelFrame(container, text="🚢 Onboard Standalone Script", style='TLabelframe')
        onboard_frame.grid(row=2, column=0, sticky=tk.EW, pady=10)
        onboard_frame.columnconfigure(0, weight=1)

        # File picker
        picker_row = ttk.Frame(onboard_frame)
        picker_row.pack(fill=tk.X, padx=10, pady=5)
        ttk.Label(picker_row, text="Script Path:", style='Config.TLabel', width=15).pack(side=tk.LEFT)
        self.onboard_script_path = tk.StringVar()
        ttk.Entry(picker_row, textvariable=self.onboard_script_path, width=40).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        ttk.Button(picker_row, text="Browse", command=self._browse_onboard_script).pack(side=tk.LEFT)
        
        # Profile & Preview button
        ttk.Button(onboard_frame, text="🔍 Profile Script", command=self._profile_onboard_script, style='Action.TButton').pack(pady=5, padx=10, fill=tk.X)

        # Profiling Preview Area
        self.onboard_preview_frame = ttk.Frame(onboard_frame)
        self.onboard_preview_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        # Will be populated by _profile_onboard_script

        # Target selection
        target_row = ttk.Frame(onboard_frame)
        target_row.pack(fill=tk.X, padx=10, pady=5)
        ttk.Label(target_row, text="Integration:", style='Config.TLabel').pack(side=tk.LEFT, padx=(0,10))
        self.onboard_target_type = tk.StringVar(value="main")
        ttk.Radiobutton(target_row, text="New Main Tab", variable=self.onboard_target_type, value="main").pack(side=tk.LEFT, padx=5)
        ttk.Radiobutton(target_row, text="Sub-Tab (Future)", variable=self.onboard_target_type, value="sub", state="disabled").pack(side=tk.LEFT, padx=5)

        ttk.Label(target_row, text="Tab Name:", style='Config.TLabel').pack(side=tk.LEFT, padx=(10,5))
        self.onboard_tab_name = tk.StringVar()
        ttk.Entry(target_row, textvariable=self.onboard_tab_name, width=15).pack(side=tk.LEFT)

        ttk.Button(onboard_frame, text="⚡ Onboard & Inject", command=self._execute_onboard, style='Action.TButton').pack(pady=10, padx=10, fill=tk.X)

        # Tab Visibility Section
        visibility_frame = ttk.LabelFrame(container, text="👁️ Tab Visibility", style='TLabelframe')
        visibility_frame.grid(row=3, column=0, sticky=tk.EW, pady=10)
        visibility_frame.columnconfigure(0, weight=1)

        # Populate with checkboxes for each tab
        self._populate_tab_visibility_controls(visibility_frame)

        # Right-Click Menu Configuration Section
        rcm_frame = ttk.LabelFrame(container, text="🖱 Right-Click Menus", style='TLabelframe')
        rcm_frame.grid(row=4, column=0, sticky=tk.EW, pady=10)
        rcm_frame.columnconfigure(0, weight=1)

        # Global enable/disable
        global_rc_frame = ttk.Frame(rcm_frame)
        global_rc_frame.pack(fill=tk.X, padx=10, pady=(8, 4))
        ttk.Checkbutton(
            global_rc_frame,
            text="Enable right-click context menus on tab headers (global)",
            variable=self.right_click_enabled,
            style='Category.TCheckbutton',
            command=self._on_right_click_toggle
        ).pack(side=tk.LEFT)

        # Per-tab overrides
        overrides_frame = ttk.Frame(rcm_frame)
        overrides_frame.pack(fill=tk.X, padx=20, pady=(0, 8))
        ttk.Label(
            overrides_frame,
            text="Per-tab overrides (uncheck to suppress menu for that tab):",
            style='Config.TLabel',
            foreground='#888888'
        ).grid(row=0, column=0, columnspan=4, sticky=tk.W, pady=(0, 4))

        tab_names = [
            ('settings_tab', 'Settings'),
            ('training_tab', 'Training'),
            ('models_tab', 'Models'),
            ('custom_code_tab', 'Custom Code'),
            ('map_tab', 'Digital Biosphere'),
        ]
        for col, (tab_key, tab_label) in enumerate(tab_names):
            if tab_key not in self.right_click_tab_overrides:
                self.right_click_tab_overrides[tab_key] = tk.BooleanVar(value=True)
            ttk.Checkbutton(
                overrides_frame,
                text=tab_label,
                variable=self.right_click_tab_overrides[tab_key],
                style='Category.TCheckbutton'
            ).grid(row=1, column=col, sticky=tk.W, padx=(0, 15))

        # Info label
        ttk.Label(
            rcm_frame,
            text="Right-click any tab header to: Refresh, View Profile, Undo Changes, Disable Tab",
            style='Config.TLabel',
            foreground='#666666',
            font=('Arial', 8)
        ).pack(anchor=tk.W, padx=10, pady=(0, 6))

        # Sub-Tab Right-Click Config
        subtab_frame = ttk.LabelFrame(container, text="🗂 Sub-Tab Right-Click Config", style='TLabelframe')
        subtab_frame.grid(row=5, column=0, sticky=tk.EW, pady=(0, 10))
        subtab_frame.columnconfigure(0, weight=1)
        ttk.Label(
            subtab_frame,
            text="Sub-notebooks are discovered after each tab loads. Toggle right-click per sub-tab.",
            style='Config.TLabel',
            foreground='#666666',
            font=('Arial', 8)
        ).pack(anchor=tk.W, padx=10, pady=(5, 4))
        subtab_checks_frame = ttk.Frame(subtab_frame)
        subtab_checks_frame.pack(anchor=tk.W, padx=10, pady=(0, 6))
        # Enumerate sub-notebooks from loaded tab instances
        found_any = False
        if getattr(self, 'tab_instances', None):
            for tab_name, meta in self.tab_instances.items():
                inst = meta.get('instance')
                if inst and hasattr(inst, '_sub_notebooks') and inst._sub_notebooks:
                    for sub in inst._sub_notebooks:
                        key = f"{tab_name}.{sub['label']}"
                        if key not in self.right_click_subtab_overrides:
                            self.right_click_subtab_overrides[key] = tk.BooleanVar(value=True)
                        ttk.Checkbutton(
                            subtab_checks_frame,
                            text=f"{meta.get('text', tab_name)} → {sub['label']}",
                            variable=self.right_click_subtab_overrides[key],
                            style='Category.TCheckbutton'
                        ).pack(anchor=tk.W, padx=5, pady=1)
                        found_any = True
        if not found_any:
            ttk.Label(
                subtab_checks_frame,
                text="No sub-notebooks detected yet — open each tab once to register them.",
                foreground='#666666',
                font=('Arial', 8)
            ).pack(anchor=tk.W, padx=5)

        # Existing Tabs Browser Section
        browser_frame = ttk.LabelFrame(container, text="📂 Tab Browser & Editor", style='TLabelframe')
        browser_frame.grid(row=6, column=0, sticky=tk.NSEW, pady=10)
        browser_frame.columnconfigure(0, weight=1)
        # We give the browser frame a fixed minimum height so it doesn't collapse
        browser_frame.rowconfigure(0, weight=1)

        # Split into left (tree) and right (editor)
        browser_paned = ttk.PanedWindow(browser_frame, orient=tk.HORIZONTAL)
        browser_paned.grid(row=0, column=0, sticky=tk.NSEW, padx=5, pady=5)

        # Left: Tree view of tabs/panels
        tree_frame = ttk.Frame(browser_paned)
        browser_paned.add(tree_frame, weight=1)

        ttk.Label(
            tree_frame,
            text="Tabs & Panels",
            font=("Arial", 10, "bold"),
            style='CategoryPanel.TLabel'
        ).pack(pady=5)

        # Tree view with scrollbar
        tree_container = ttk.Frame(tree_frame)
        tree_container.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        tree_scroll = ttk.Scrollbar(tree_container, orient="vertical")
        tree_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.tabs_tree = ttk.Treeview(
            tree_container,
            yscrollcommand=tree_scroll.set,
            selectmode='browse',
            height=12
        )
        self.tabs_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tree_scroll.config(command=self.tabs_tree.yview)

        # Configure tree columns
        self.tabs_tree.heading('#0', text='Structure')

        # Style the treeview for better visibility
        style = ttk.Style()
        style.configure("Treeview",
                       background="#2b2b2b",
                       foreground="white",
                       fieldbackground="#2b2b2b",
                       borderwidth=0)
        style.map('Treeview',
                 background=[('selected', '#3d3d3d')],
                 foreground=[('selected', '#61dafb')])

        # --- COORDINATED COLORATION SYSTEM ---
        # (Colors already defined in self.status_colors)
        if not hasattr(self, 'status_colors'):
            self.status_colors = {
                'error': '#ff5555', 'warning': '#ffaa00', 'active': '#55ff55',
                'stable': '#ffffff', 'backup': '#aaaaaa', 'tab': '#61dafb'
            }

        self.tabs_tree.tag_configure('error', foreground=self.status_colors['error'], font=('Arial', 10, 'bold'))
        self.tabs_tree.tag_configure('warning', foreground=self.status_colors['warning'], font=('Arial', 10, 'bold'))
        self.tabs_tree.tag_configure('active', foreground=self.status_colors['active'], font=('Arial', 10, 'bold'))
        self.tabs_tree.tag_configure('stable', foreground=self.status_colors['stable'])
        self.tabs_tree.tag_configure('backup', foreground=self.status_colors['backup'])
        self.tabs_tree.tag_configure('tab', foreground=self.status_colors['tab'], font=('Arial', 10, 'bold'))

        # Feature/Structure tags (kept specific)
        self.tabs_tree.tag_configure('file', foreground='#ffffff')
        self.tabs_tree.tag_configure('panel', foreground='#a8dadc')
        self.tabs_tree.tag_configure('class', foreground='#ffdd88', font=('Consolas', 9))  # Yellow for Classes
        self.tabs_tree.tag_configure('method', foreground='#aaaaaa', font=('Consolas', 8)) # Grey for Methods

        self.tabs_tree.bind('<<TreeviewSelect>>', self.on_tree_select)

        # Right: Panel Inspector & Global Actions
        right_pane = ttk.Frame(browser_paned) 
        browser_paned.add(right_pane, weight=2)
        
        # 1. Dynamic Inspector Area (Top, expands)
        self.inspector_frame = ttk.Frame(right_pane)
        self.inspector_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        # 2. Persistent Global Actions (Bottom, fixed)
        global_actions = ttk.Frame(right_pane, style='Category.TFrame')
        global_actions.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=10)
        
        ttk.Button(
            global_actions,
            text="🔄 Refresh Tree",
            command=self.refresh_tabs_tree,
            style='Select.TButton'
        ).pack(side=tk.RIGHT, padx=5)

        ttk.Button(
            global_actions,
            text="📂 Open Folder",
            command=lambda: __import__('subprocess').Popen(['xdg-open', str(DATA_DIR / "tabs")]),
            style='Select.TButton'
        ).pack(side=tk.RIGHT, padx=5)
        
        ttk.Label(global_actions, text="Global Actions:", style='Config.TLabel', foreground="#888888").pack(side=tk.LEFT, padx=5)

        # Initial State
        self.update_inspector_view(None)

        # Populate tree
        self.refresh_tabs_tree()

        # Store selected item
        self.selected_tree_item = None


    def _browse_onboard_script(self):
        from tkinter import filedialog
        path = filedialog.askopenfilename(
            title="Select Python Script to Onboard",
            filetypes=[("Python Scripts", "*.py")]
        )
        if path:
            self.onboard_script_path.set(path)

    def _profile_onboard_script(self):
        script_path = self.onboard_script_path.get().strip()
        if not script_path or not os.path.exists(script_path):
            messagebox.showerror("Error", "Invalid script path.")
            return

        from tab_onboarder import TabOnboarder
        onboarder = TabOnboarder(DATA_DIR)
        result = onboarder.analyze_candidate(script_path)

        # Clear existing preview
        for widget in self.onboard_preview_frame.winfo_children():
            widget.destroy()

        if not result['can_onboard']:
            ttk.Label(self.onboard_preview_frame, text=f"❌ Cannot Onboard: {', '.join(result.get('issues', ['Unknown error']))}", foreground="red").pack()
            return

        self._onboard_target_class = result['suggested_class']
        
        ttk.Label(self.onboard_preview_frame, text=f"✅ Ready! Detected Class: {result['suggested_class']}", foreground="green", font=("Arial", 10, "bold")).pack(anchor=tk.W)
        
        props = result.get('properties', [])
        if props:
            ttk.Label(self.onboard_preview_frame, text="Found Tkinter Variables (Lower-Order Properties):", font=("Arial", 9, "bold")).pack(anchor=tk.W, pady=(5,2))
            
            tree = ttk.Treeview(self.onboard_preview_frame, columns=("Type", "Default", "Line"), show="headings", height=5)
            tree.heading("Type", text="Type")
            tree.heading("Default", text="Default")
            tree.heading("Line", text="Line")
            tree.column("Type", width=100)
            tree.column("Default", width=100)
            tree.column("Line", width=50)
            
            for p in props:
                # Name goes in the first implied col if we had #0, but we use show="headings" so let's add Name col
                pass
            
            tree.destroy() # recreate with name
            tree = ttk.Treeview(self.onboard_preview_frame, columns=("Name", "Type", "Default", "Line"), show="headings", height=5)
            tree.heading("Name", text="Variable Name")
            tree.heading("Type", text="Type")
            tree.heading("Default", text="Default Value")
            tree.heading("Line", text="Line #")
            tree.column("Name", width=150)
            tree.column("Type", width=100)
            tree.column("Default", width=100)
            tree.column("Line", width=50)
            tree.pack(fill=tk.X)
            
            for p in props:
                tree.insert("", "end", values=(p['name'], p['type'], p['default'], p['lineno']))

    def _execute_onboard(self):
        script_path = self.onboard_script_path.get().strip()
        tab_name = self.onboard_tab_name.get().strip()
        
        if not script_path or not tab_name:
            messagebox.showerror("Error", "Please provide a script path and a tab name.")
            return
            
        if not hasattr(self, '_onboard_target_class') or not self._onboard_target_class:
            messagebox.showerror("Error", "Please profile the script first to detect the target class.")
            return

        from tab_onboarder import TabOnboarder
        onboarder = TabOnboarder(DATA_DIR)
        
        is_main = self.onboard_target_type.get() == "main"
        
        result = onboarder.onboard_script(
            script_path=script_path,
            tab_name=tab_name,
            target_class=self._onboard_target_class,
            is_main_tab=is_main
        )
        
        if result.get('success'):
            from logger_util import log_message
            log_message(f"Successfully onboarded {script_path} as {tab_name}.")
            messagebox.showinfo("Success", f"Script onboarded!\nWrapper created at: {result.get('wrapper_path')}\n\nPlease restart the application to load the new tab.")
            self.refresh_tabs_tree()
        else:
            messagebox.showerror("Error", f"Failed to onboard: {result.get('error')}")


    def create_new_tab(self):
        """Create a new tab with user specifications"""
        from tab_generator import TabGenerator

        tab_name = self.new_tab_name.get().strip()
        if not tab_name:
            messagebox.showwarning("No Name", "Please enter a tab name.")
            return

        generator = TabGenerator(DATA_DIR)
        result = generator.create_tab(
            tab_name=tab_name,
            num_subtabs=self.num_subtabs.get(),
            has_side_menu=self.has_side_menu.get()
        )

        if result['success']:
            messagebox.showinfo(
                "Tab Created",
                f"✅ Tab '{tab_name}' created successfully!\n\n"
                f"Files created:\n" + '\n'.join([f"  • {Path(f).name}" for f in result['files']]) +
                f"\n\nRestart the application to see the new tab."
            )
            self.new_tab_name.set("")
            self.refresh_tabs_tree()
        else:
            messagebox.showerror("Creation Failed", result['error'])

    def refresh_tabs_tree(self):
        """Refresh the tree view of tabs and panels - includes ALL tabs"""
        log_message("SETTINGS: Refreshing tabs tree.")
        log_message(f"SETTINGS: Tab order from settings: {self.settings.get('tab_order')}")
        
        # Load Manifest for profiling data
        manifest = {}
        manifest_path = DATA_DIR / "backup" / "manifest.json"
        if manifest_path.exists():
            try:
                with open(manifest_path, 'r') as f:
                    manifest = json.load(f)
            except: pass

        # Clear existing tree
        for item in self.tabs_tree.get_children():
            self.tabs_tree.delete(item)

        tabs_dir = DATA_DIR / "tabs"
        if not tabs_dir.exists():
            return

        # Define built-in tabs with special handling
        built_in_tabs = {
            'settings_tab': {
                'display': 'Settings',
                'icon': '⚙️',
                'main_file': 'settings_tab.py',
                'panels': []
            },
            'training_tab': {
                'display': 'Training',
                'icon': '⚙️',
                'main_file': 'training_tab.py',
                'panels': [
                    'runner_panel.py',
                    'category_manager_panel.py',
                    'dataset_panel.py',
                    'config_panel.py',
                    'profiles_panel.py',
                    'summary_panel.py'
                ]
            },
            'models_tab': {
                'display': 'Models',
                'icon': '🧠',
                'main_file': 'models_tab.py',
                'panels': []
            }
        }

        # Get the saved tab order
        saved_order = self.settings.get('tab_order', ['training_tab', 'models_tab', 'custom_code_tab', 'map_tab', 'settings_tab'])
        
        # Get all tab directories
        all_tab_dirs = {tab_dir.name: tab_dir for tab_dir in sorted(tabs_dir.iterdir()) if tab_dir.is_dir() and not tab_dir.name.startswith('__')}
        
        processed_tabs = set()

        # Add tabs in the saved order
        for tab_dir_name in saved_order:
            if tab_dir_name in all_tab_dirs:
                self._add_tab_to_tree(all_tab_dirs[tab_dir_name], built_in_tabs, manifest)
                processed_tabs.add(tab_dir_name)

        # Add any remaining tabs that were not in the saved order
        for tab_dir_name, tab_dir in all_tab_dirs.items():
            if tab_dir_name not in processed_tabs:
                self._add_tab_to_tree(tab_dir, built_in_tabs, manifest)
        
        # --- Add External Project Files (if in manifest) ---
        # Scan manifest for 'project' type entries
        project_entries = []
        for key, entry in manifest.items():
            if entry.get('type') == 'project':
                project_entries.append((key, entry))
        
        if project_entries:
            project_root = self.tabs_tree.insert(
                '',
                'end',
                text="📂 Custom Project",
                values=("Project Root", 'root'),
                tags=('tab',) # Reuse tab style
            )
            
            for key, entry in project_entries:
                file_path = Path(key) # Key is usually absolute path for project files
                file_name = file_path.name
                
                file_node = self.tabs_tree.insert(
                    project_root,
                    'end',
                    text=f"📄 {file_name}",
                    values=(str(file_path), 'project_file'),
                    tags=('file',)
                )
                self._add_file_features(file_node, file_path, manifest)

    def _add_tab_to_tree(self, tab_dir, built_in_tabs, manifest=None):
        """Helper function to add a single tab and its contents to the treeview."""
        tab_dir_name = tab_dir.name
        
        # Determine display name and base icon
        if tab_dir_name in built_in_tabs:
            tab_info = built_in_tabs[tab_dir_name]
            tab_display_name = tab_info['display']
            icon = tab_info['icon']
        else:
            # Custom tab
            tab_display_name = tab_dir.name.replace('_tab', '').replace('_', ' ').title()
            icon = '📂'

        # --- Check Runtime Status from Registry ---
        import logger_util
        registry_info = logger_util.TAB_REGISTRY.get(tab_dir_name, {})
        runtime_status = registry_info.get('status', 'UNKNOWN')
        
        status_icon = ""
        tag = 'tab' # default tag

        if runtime_status == 'SUCCESS':
            status_icon = "✅ "
            tag = 'active'
        elif runtime_status == 'FAILED':
            status_icon = "❌ "
            tag = 'error'
        elif runtime_status == 'DISABLED':
            status_icon = "⚠️ "
            tag = 'backup'
        else:
            # Not in registry
            status_icon = "⚪ "
            tag = 'stable'

        # --- COORDINATION: Check Version Manifest for Damaged State ---
        # If any file in this tab's directory is blamed in a damaged version, show warning
        v_manifest = getattr(self, 'version_manifest', {})
        if not v_manifest:
             v_manifest = recovery_util.load_version_manifest()
             
        for v in v_manifest.get("versions", {}).values():
            if v.get("status") == "damaged":
                for b in v.get("blame", []):
                    if isinstance(b, dict) and tab_dir_name in b.get("file", ""):
                        status_icon = "☢️ " # Biohazard for damaged
                        tag = 'warning'
                        break

        display_text = f"{status_icon}{icon} {tab_display_name}"

        # Add tab as root node
        tab_node = self.tabs_tree.insert(
            '',
            'end',
            text=display_text,
            values=(str(tab_dir), 'tab'),
            tags=(tag,)
        )

        # Find main tab file
        if tab_dir_name in built_in_tabs and built_in_tabs[tab_dir_name]['main_file']:
            main_file = tab_dir / built_in_tabs[tab_dir_name]['main_file']
        else:
            main_file = tab_dir / f"{tab_dir.name}.py"

        if main_file.exists():
            file_node = self.tabs_tree.insert(
                tab_node,
                'end',
                text=f"📄 {main_file.name}",
                values=(str(main_file), 'main_file'),
                tags=('file',)
            )
            # Profile Main File
            self._add_file_features(file_node, main_file, manifest)

        # Find all panel files
        if tab_dir_name in built_in_tabs and built_in_tabs[tab_dir_name]['panels']:
            # Use predefined panel list for built-in tabs
            panel_files = [tab_dir / p for p in built_in_tabs[tab_dir_name]['panels']
                          if (tab_dir / p).exists()]
        else:
            # Auto-detect panels for custom tabs and built-in tabs without predefined list
            panel_files = sorted([f for f in tab_dir.glob("*.py")
                                 if f.name not in ['__init__.py', main_file.name]])

        for panel_file in panel_files:
            # Determine panel type/label
            if 'panel' in panel_file.stem.lower():
                icon = '🔧'
            else:
                icon = '📦'

            panel_node = self.tabs_tree.insert(
                tab_node,
                'end',
                text=f"{icon} {panel_file.name}",
                values=(str(panel_file), 'panel'),
                tags=('panel',)
            )
            # Profile Panel File
            self._add_file_features(panel_node, panel_file, manifest)

        # Expand the tab node by default so panels are visible
        self.tabs_tree.item(tab_node, open=True)

    def _add_file_features(self, parent_node, file_path, manifest):
        """Helper to add Classes and Functions as child nodes to a file in the tree."""
        if not manifest:
            return

        # Try to find the file in the manifest
        entry = None
        try:
            # Prioritize relative path to TRAINER_ROOT
            rel_path_to_trainer_root = str(file_path.relative_to(TRAINER_ROOT))
            entry = manifest.get(rel_path_to_trainer_root)
        except ValueError:
            pass
        
        if not entry:
            # Fallback to absolute path (for external project files or if relative_to(TRAINER_ROOT) fails for some reason)
            entry = manifest.get(str(file_path.absolute()))
            
        if not entry:
            return

        profile = entry.get('profile', {})
        if not profile:
            return

        # Add Classes
        for cls in profile.get('classes', []):
            cls_name = cls['name']
            cls_node = self.tabs_tree.insert(
                parent_node,
                'end',
                text=f"C  {cls_name}",
                values=(f"{file_path}::{cls_name}", 'class'),
                tags=('class',)
            )
            
            for method_name in cls.get('methods', []):
                 self.tabs_tree.insert(
                    cls_node,
                    'end',
                    text=f"M  {method_name}",
                    values=(f"{file_path}::{cls_name}.{method_name}", 'method'),
                    tags=('method',)
                )

    def update_inspector_view(self, item_data):
        """
        Refreshes the right-hand Inspector panel based on selection.
        item_data: dict with 'path', 'type', 'values' (optional)
        """
        # Check if inspector_frame exists (it might not during initial load)
        if not hasattr(self, 'inspector_frame'):
            return

        # Clear existing
        for widget in self.inspector_frame.winfo_children():
            widget.destroy()

        if not item_data:
            ttk.Label(
                self.inspector_frame,
                text="👈 Select a Tab or Panel to inspect",
                font=("Arial", 12),
                foreground="#888888"
            ).pack(expand=True)
            return

        import logger_util
        from datetime import datetime
        
        path = item_data['path']
        item_type = item_data['type']
        name = path.name

        # --- Header ---
        header_frame = ttk.Frame(self.inspector_frame, style='Header.TFrame')
        header_frame.pack(fill=tk.X, pady=(0, 0)) # No padding at top to flush with container
        
        icon = "📄"
        if item_type == 'tab': icon = "📂"
        elif item_type == 'panel': icon = "🔧"
        
        ttk.Label(
            header_frame,
            text=f"{icon} {name}",
            font=("Arial", 14, "bold"),
            foreground="#61dafb",
            background="#1e1e1e"
        ).pack(padx=10, pady=15, anchor=tk.W)

        # --- Content Area ---
        content = ttk.Frame(self.inspector_frame)
        content.pack(fill=tk.BOTH, expand=True, padx=15, pady=10)

        if item_type == 'tab':
            # Status Section
            status_info = logger_util.TAB_REGISTRY.get(name, {})
            status = status_info.get('status', 'UNKNOWN')
            
            status_color = "#888888"
            if status == 'SUCCESS': status_color = "#4ade80"
            elif status == 'FAILED': status_color = "#ef4444"
            elif status == 'DISABLED': status_color = "#d1d5db"

            ttk.Label(content, text="Runtime Status:", style='Config.TLabel', font=("Arial", 10, "bold")).pack(anchor=tk.W, pady=(5,0))
            ttk.Label(
                content,
                text=f"  ● {status}",
                foreground=status_color,
                font=("Arial", 11, "bold")
            ).pack(anchor=tk.W, pady=(0, 5))

            # --- TAX Domain + UX Events ---
            probe_info = status_info.get('execution_probe') or {}
            domain = probe_info.get('domain', None)
            if domain:
                domain_color = {
                    'matplotlib_3d': '#ff9933',
                    'matplotlib': '#ffcc66',
                    'tkinter_canvas': '#66ccff',
                    'tkinter_composite': '#99ff99',
                    'tkinter_standard': '#cccccc',
                }.get(domain, '#aaaaaa')
                ttk.Label(content, text="Domain (TAX):", style='Config.TLabel', font=("Arial", 9, "bold")).pack(anchor=tk.W)
                ttk.Label(
                    content,
                    text=f"  {domain}",
                    foreground=domain_color,
                    font=("Arial", 10)
                ).pack(anchor=tk.W, pady=(0, 3))
                known_issues = probe_info.get('domain_known_issues', [])
                if known_issues:
                    ttk.Label(content, text=f"  ⚠ {'; '.join(known_issues[:2])}", foreground="#ffaa44", font=("Arial", 8)).pack(anchor=tk.W)

            # UX Events summary
            tab_ux = [e for e in logger_util.UX_EVENT_LOG if e.get('tab') == name]
            ux_errors = [e for e in tab_ux if e.get('outcome') == 'error']
            ux_label_color = '#ef4444' if ux_errors else '#4ade80' if tab_ux else '#888888'
            ux_text = f"UX Events: {len(tab_ux)} fired, {len(ux_errors)} errors"
            ttk.Label(content, text=ux_text, foreground=ux_label_color, font=("Arial", 9)).pack(anchor=tk.W, pady=(3, 0))
            if ux_errors:
                last_err = ux_errors[-1]
                ttk.Label(
                    content,
                    text=f"  Last error: {last_err.get('timestamp','')} — {last_err.get('widget','')}",
                    foreground="#ffaaaa", font=("Arial", 8)
                ).pack(anchor=tk.W)
            # --- end TAX / UX section ---

            # Error Log (if any)
            if status == 'FAILED':
                ttk.Label(content, text="Error Log:", style='Config.TLabel', foreground="#ef4444").pack(anchor=tk.W)
                error_text = tk.Text(content, height=8, width=40, bg="#2b1b1b", fg="#ffcccc", relief="flat", font=("Consolas", 9), highlightthickness=1, highlightbackground="#ef4444")
                error_text.pack(fill=tk.X, pady=5)
                error_text.insert("1.0", status_info.get('message', 'No details available.'))
                error_text.config(state=tk.DISABLED)

            # Actions
            ttk.Label(content, text="Actions:", style='Config.TLabel', font=("Arial", 10, "bold")).pack(anchor=tk.W, pady=(15,5))
            
            btn_frame = ttk.Frame(content)
            btn_frame.pack(fill=tk.X, pady=5)
            
            if status != 'UNKNOWN': # Only allow moving known tabs
                 ttk.Button(btn_frame, text="⬅️ Move Left", command=lambda: self.move_tab("left"), style='Select.TButton').pack(side=tk.LEFT, padx=(0, 5), fill=tk.X, expand=True)
                 ttk.Button(btn_frame, text="➡️ Move Right", command=lambda: self.move_tab("right"), style='Select.TButton').pack(side=tk.LEFT, padx=(5, 0), fill=tk.X, expand=True)
            
            ttk.Button(content, text="➕ Add New Panel", command=self.add_new_panel, style='Action.TButton').pack(fill=tk.X, pady=10)

            # --- DIAGNOSTIC: Check Version Manifest for specific blame on this tab ---
            v_manifest = getattr(self, 'version_manifest', {})
            if not v_manifest: v_manifest = recovery_util.load_version_manifest()
            
            found_blame = []
            for v in v_manifest.get("versions", {}).values():
                if v.get("status") == "damaged":
                    for b in v.get("blame", []):
                        if isinstance(b, dict) and name in b.get("file", ""):
                            found_blame.append({"version": v["timestamp"], "blame": b})
            
            if found_blame:
                ttk.Label(content, text="🚨 DAMAGED VERSION BLAME:", style='Config.TLabel', foreground="#ffaa00", font=("Arial", 10, "bold")).pack(anchor=tk.W, pady=(10, 5))
                diag_text = tk.Text(content, height=6, width=40, bg="#2b1b1b", fg="#ffcc66", relief="flat", font=("Consolas", 8))
                diag_text.pack(fill=tk.X, pady=5)
                for entry in found_blame:
                    b = entry["blame"]
                    diag_text.insert(tk.END, f"Version: {entry['version']}\n")
                    diag_text.insert(tk.END, f"Target: {b.get('target')}\n")
                    diag_text.insert(tk.END, f"Line: {b.get('line')}\n")
                    diag_text.insert(tk.END, f"Feature: {b.get('feature', 'Core')}\n\n")
                diag_text.config(state=tk.DISABLED)

        elif item_type in ['panel', 'main_file', 'project_file']:
            # File Info
            try:
                stats = path.stat()
                size_kb = stats.st_size / 1024
                mtime = datetime.fromtimestamp(stats.st_mtime).strftime('%Y-%m-%d %H:%M')
                
                info_frame = ttk.LabelFrame(content, text="File Info", style='TLabelframe')
                info_frame.pack(fill=tk.X, pady=10)
                
                ttk.Label(info_frame, text=f"Size: {size_kb:.1f} KB", style='Config.TLabel').pack(anchor=tk.W, padx=10, pady=2)
                ttk.Label(info_frame, text=f"Modified: {mtime}", style='Config.TLabel').pack(anchor=tk.W, padx=10, pady=2)
            except Exception:
                pass

            # Actions
            ttk.Label(content, text="Actions:", style='Config.TLabel', font=("Arial", 10, "bold")).pack(anchor=tk.W, pady=(15,5))
            
            ttk.Button(content, text="✏️ Edit File", command=self.edit_selected_panel, style='Action.TButton').pack(fill=tk.X, pady=5)
            
            if item_type == 'panel':
                ttk.Button(content, text="🗑️ Delete Panel", command=self.delete_selected_panel, style='Select.TButton').pack(fill=tk.X, pady=5)

            # --- DIAGNOSTIC: Check for specific blame on this file ---
            rel_path = ""
            try: rel_path = str(path.relative_to(TRAINER_ROOT))
            except: pass

            if rel_path:
                v_manifest = getattr(self, 'version_manifest', {})
                if not v_manifest: v_manifest = recovery_util.load_version_manifest()
                
                found_blame = []
                for v in v_manifest.get("versions", {}).values():
                    if v.get("status") == "damaged":
                        for b in v.get("blame", []):
                            if isinstance(b, dict) and rel_path == b.get("file"):
                                found_blame.append({"version": v["timestamp"], "blame": b, "traceback": v.get("traceback")})
                
                if found_blame:
                    ttk.Label(content, text="🚨 FILE CRASH HISTORY:", style='Config.TLabel', foreground="#ff5555", font=("Arial", 10, "bold")).pack(anchor=tk.W, pady=(10, 5))
                    diag_text = tk.Text(content, height=10, width=40, bg="#2b1b1b", fg="#ffcccc", relief="flat", font=("Consolas", 8))
                    diag_text.pack(fill=tk.X, pady=5)
                    for entry in found_blame:
                        b = entry["blame"]
                        diag_text.insert(tk.END, f"VERSION: {entry['version']}\n")
                        diag_text.insert(tk.END, f"METHOD: {b.get('method')}\n")
                        diag_text.insert(tk.END, f"LINE: {b.get('line')}\n")
                        diag_text.insert(tk.END, f"ERROR SNIPPET:\n{entry['traceback'][-200:] if entry['traceback'] else 'N/A'}\n")
                        diag_text.insert(tk.END, "-"*30 + "\n")
                    diag_text.config(state=tk.DISABLED)

    def on_tree_select(self, event):
        """Handle tree item selection"""
        selection = self.tabs_tree.selection()
        if not selection:
            self.selected_tree_item = None
            self.update_inspector_view(None)
            return

        item = selection[0]
        values = self.tabs_tree.item(item, 'values')

        if not values:
            self.selected_tree_item = None
            self.update_inspector_view(None)
            return

        file_path, item_type = values
        self.selected_tree_item = {'path': Path(file_path), 'type': item_type}
        
        # Update Inspector View
        self.update_inspector_view(self.selected_tree_item)

    def add_new_panel(self):
        """Add a new panel to selected tab"""
        if not self.selected_tree_item or self.selected_tree_item['type'] != 'tab':
            messagebox.showwarning(
                "No Tab Selected",
                "Please select a tab from the tree to add a panel."
            )
            return

        from tkinter import simpledialog
        panel_name = simpledialog.askstring(
            "New Panel",
            "Enter panel name (e.g., 'analytics', 'settings'):"
        )

        if not panel_name:
            return

        # Sanitize panel name
        import re
        panel_name = re.sub(r'[^a-zA-Z0-9_]', '_', panel_name).lower()

        tab_dir = self.selected_tree_item['path']
        panel_file = tab_dir / f"{panel_name}.py"

        if panel_file.exists():
            messagebox.showerror("Error", f"Panel '{panel_name}.py' already exists!")
            return

        # Generate panel content
        class_name = ''.join(word.capitalize() for word in panel_name.split('_'))
        panel_content = f'''"""
{class_name} Panel
"""

import tkinter as tk
from tkinter import ttk


class {class_name}:
    """Panel for {panel_name}"""

    def __init__(self, parent, style):
        self.parent = parent
        self.style = style

    def create_ui(self):
        """Create the panel UI"""
        self.parent.columnconfigure(0, weight=1)
        self.parent.rowconfigure(0, weight=1)

        # Main container
        container = ttk.Frame(self.parent, style='Category.TFrame')
        container.grid(row=0, column=0, sticky=tk.NSEW, padx=10, pady=10)

        # Title
        ttk.Label(
            container,
            text="{class_name} Panel",
            font=("Arial", 12, "bold"),
            style='CategoryPanel.TLabel'
        ).pack(pady=10)

        # Content
        ttk.Label(
            container,
            text="Add your content here",
            style='Config.TLabel'
        ).pack(pady=20)
'''

        try:
            panel_file.write_text(panel_content)
            messagebox.showinfo(
                "Panel Created",
                f"✅ Panel '{panel_name}.py' created!\n\n"
                f"Remember to:\n"
                f"1. Import it in the main tab file\n"
                f"2. Add it to the notebook\n"
                f"3. Restart the application"
            )
            self.refresh_tabs_tree()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to create panel: {e}")

    def edit_selected_panel(self):
        """Open selected panel file in default editor"""
        if not self.selected_tree_item:
            messagebox.showwarning(
                "No Selection",
                "Please select a file from the tree to edit.\n\n"
                "You can edit:\n"
                "• Panel files (🔧)\n"
                "• Main tab files (📄)"
            )
            return

        if self.selected_tree_item['type'] not in ['panel', 'main_file']:
            messagebox.showwarning(
                "Invalid Selection",
                f"Cannot edit {self.selected_tree_item['type']}.\n\n"
                "Please select a panel file (🔧) or main file (📄)."
            )
            return

        file_path = self.selected_tree_item['path']

        if not file_path.exists():
            messagebox.showerror(
                "File Not Found",
                f"File does not exist:\n{file_path}"
            )
            return

        try:
            import subprocess
            subprocess.Popen(['xdg-open', str(file_path)])
            messagebox.showinfo(
                "Opening File",
                f"Opening in default editor:\n\n{file_path.name}\n\n"
                "The file should open shortly in your system's default Python editor."
            )
        except Exception as e:
            messagebox.showerror("Failed to Open", f"Failed to open file: {e}")

    def delete_selected_panel(self):
        """Delete selected panel file with strict confirmation"""
        if not self.selected_tree_item:
            messagebox.showwarning(
                "No Selection",
                "Please select a panel file from the tree to delete."
            )
            return

        if self.selected_tree_item['type'] != 'panel':
            messagebox.showwarning(
                "Invalid Selection",
                "You can only delete panel files.\n\n"
                f"Selected: {self.selected_tree_item['type']}\n\n"
                "Please select a panel file (🔧 icon)."
            )
            return

        file_path = self.selected_tree_item['path']
        file_name = file_path.name

        # Check if it's a built-in critical panel
        critical_panels = [
            'runner_panel.py', 'category_manager_panel.py',
            'dataset_panel.py', 'config_panel.py',
            'profiles_panel.py', 'summary_panel.py'
        ]

        if file_name in critical_panels:
            messagebox.showerror(
                "Cannot Delete Built-in Panel",
                f"'{file_name}' is a built-in panel and cannot be deleted.\n\n"
                "This panel is essential to the application's functionality."
            )
            return

        # First confirmation
        if not messagebox.askyesno(
            "⚠️ Confirm Delete - Step 1/2",
            f"Are you sure you want to delete:\n\n"
            f"    {file_name}\n\n"
            f"This action CANNOT be undone!"
        ):
            return

        # Second strict confirmation with typing requirement
        from tkinter import simpledialog
        confirmation = simpledialog.askstring(
            "⚠️ Confirm Delete - Step 2/2",
            f"To confirm deletion, type the panel name:\n\n"
            f"{file_name}\n\n"
            f"Type it exactly (case-sensitive):",
            parent=self.parent
        )

        if confirmation != file_name:
            messagebox.showinfo(
                "Deletion Cancelled",
                "Panel name did not match. Deletion cancelled."
            )
            return

        # Perform deletion
        try:
            file_path.unlink()
            messagebox.showinfo(
                "Panel Deleted",
                f"✅ Panel '{file_name}' has been deleted.\n\n"
                f"⚠️ IMPORTANT:\n"
                f"• Update the main tab file to remove imports\n"
                f"• Remove panel initialization code\n"
                f"• Restart the application"
            )
            self.refresh_tabs_tree()
            self.selected_tree_item = None
            self.selected_info_label.config(text="Panel deleted - select another item")
        except Exception as e:
            messagebox.showerror("Deletion Failed", f"Failed to delete panel: {e}")

    def load_settings(self):
        """Load settings from file"""
        settings = {}
        if self.settings_file.exists():
            try:
                with open(self.settings_file, 'r') as f:
                    settings = json.load(f)
                logger_util.log_message("SETTINGS: Settings file loaded successfully.")
            except Exception as e:
                logger_util.log_message(f"SETTINGS ERROR: Error loading settings: {e}")
            
        # Load tab visibility settings into tk.BooleanVars
        for display_name, setting_key in [
            ("Training Tab", "training_tab_enabled"),
            ("Models Tab", "models_tab_enabled"),
            ("Settings Tab", "settings_tab_enabled"),
            ("Custom Code Tab", "custom_code_tab_enabled"),
            ("Map Tab", "map_tab_enabled"),
        ]:
            # Initialize var if not already done (e.g., in __init__)
            if setting_key not in self.tab_enabled_vars:
                self.tab_enabled_vars[setting_key] = tk.BooleanVar()
            self.tab_enabled_vars[setting_key].set(settings.get(setting_key, True)) # Default to enabled

            self.reorder_mode.set(settings.get('reorder_mode', 'static')) # Default to static
            self.right_click_enabled.set(settings.get('right_click_menu_enabled', True))
            for k, v in settings.get('right_click_subtab_overrides', {}).items():
                if k not in self.right_click_subtab_overrides:
                    self.right_click_subtab_overrides[k] = tk.BooleanVar(value=v)
                else:
                    self.right_click_subtab_overrides[k].set(v)

        return settings

    def save_settings_to_file(self):
        """Save current settings to file, preserving other sections."""
        log_message("SETTINGS: Saving all settings to file.")
        try:
            # Read existing settings to preserve other sections (like runner_defaults)
            all_settings = {}
            if self.settings_file.exists():
                try:
                    with open(self.settings_file, 'r') as f:
                        all_settings = json.load(f)
                except (json.JSONDecodeError, IOError) as e:
                    log_message(f"SETTINGS ERROR: Could not read existing settings file for merge: {e}")

            # Update the settings managed by this tab
            all_settings.update({
                'default_epochs': self.default_epochs.get(),
                'default_batch': self.default_batch.get(),
                'default_learning_rate': self.default_lr.get(),
                'auto_refresh_models': self.auto_refresh.get(),
                'show_debug': self.show_debug.get(),
                'confirm_training': self.confirm_training.get(),
            })
            # Resource vars are only created when the Resources sub-tab is first rendered
            if hasattr(self, 'max_cpu_threads'):
                all_settings['max_cpu_threads'] = self.max_cpu_threads.get()
            if hasattr(self, 'max_ram_percent'):
                all_settings['max_ram_percent'] = self.max_ram_percent.get()
            if hasattr(self, 'max_seq_length'):
                all_settings['max_seq_length'] = self.max_seq_length.get()
            if hasattr(self, 'gradient_accumulation'):
                all_settings['gradient_accumulation'] = self.gradient_accumulation.get()
            
            # Save tab visibility settings
            for setting_key, var in self.tab_enabled_vars.items():
                all_settings[setting_key] = var.get()

            # Save tab reordering setting
            all_settings['reorder_mode'] = self.reorder_mode.get()

            # Save right-click menu setting
            all_settings['right_click_menu_enabled'] = self.right_click_enabled.get()
            all_settings['right_click_subtab_overrides'] = {
                k: v.get() for k, v in self.right_click_subtab_overrides.items()
            }

            # Ensure custom_code_tab and map_tab are in tab_order if they are enabled
            tab_order = self.settings.get('tab_order', ['training_tab', 'models_tab', 'custom_code_tab', 'map_tab', 'settings_tab'])
            
            # Logic for ensuring enabled tabs are in the order
            for tab_key in ['custom_code_tab', 'map_tab']:
                setting_key = f"{tab_key}_enabled"
                if tab_key not in tab_order and self.tab_enabled_vars.get(setting_key, tk.BooleanVar(value=False)).get():
                    # Insert before settings_tab if enabled
                    if 'settings_tab' in tab_order:
                        idx = tab_order.index('settings_tab')
                        tab_order.insert(idx, tab_key)
                    else:
                        tab_order.append(tab_key)
            all_settings['tab_order'] = tab_order

            # Save Regression Policy
            if not hasattr(self, 'policy_alert_drop'):
                # Initialize defaults if UI not visited
                self.policy_enabled = tk.BooleanVar(value=True)
                self.policy_alert_drop = tk.DoubleVar(value=5.0)
                self.policy_strict_block = tk.BooleanVar(value=False)
                self.policy_auto_rollback = tk.BooleanVar(value=False)
            all_settings['regression_policy'] = {
                'enabled': self.policy_enabled.get(),
                'alert_drop_percent': float(self.policy_alert_drop.get()),
                'strict_block': self.policy_strict_block.get(),
                'auto_rollback': self.policy_auto_rollback.get()
            }

            with open(self.settings_file, 'w') as f:
                json.dump(all_settings, f, indent=2)

            log_message("SETTINGS: Settings saved successfully.")
            messagebox.showinfo("Settings Saved", "Settings have been saved successfully!")
            self.settings = all_settings
        except Exception as e:
            log_message(f"SETTINGS ERROR: Failed to save settings: {e}")
            messagebox.showerror("Save Error", f"Failed to save settings: {e}")

    def get_setting(self, key, default=None):
        """Get a setting value"""
        return self.settings.get(key, default)

    def create_resource_settings(self, parent):
        """Create resource limiting settings"""
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(0, weight=1)

        # Scrollable frame
        canvas = tk.Canvas(parent, bg="#2b2b2b", highlightthickness=0)
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        content_frame = ttk.Frame(canvas)

        content_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas_window = canvas.create_window((0, 0), window=content_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True, padx=5, pady=5)
        scrollbar.pack(side="right", fill="y")

        canvas.bind("<Configure>", lambda e: canvas.itemconfig(canvas_window, width=e.width))

        # CPU Settings
        cpu_section = ttk.LabelFrame(content_frame, text="💻 CPU Limits", style='TLabelframe')
        cpu_section.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(cpu_section, text="Max CPU Threads:", style='Config.TLabel').grid(
            row=0, column=0, sticky=tk.W, padx=10, pady=5
        )
        self.max_cpu_threads = tk.IntVar(value=self.settings.get('max_cpu_threads', 2))
        ttk.Spinbox(
            cpu_section,
            from_=1,
            to=32,
            textvariable=self.max_cpu_threads,
            width=10
        ).grid(row=0, column=1, sticky=tk.W, padx=10, pady=5)

        ttk.Label(
            cpu_section,
            text="Lower values prevent system freezing during training",
            font=("Arial", 8),
            foreground='#888888'
        ).grid(row=1, column=0, columnspan=2, sticky=tk.W, padx=10, pady=(0, 10))

        # Memory Settings
        mem_section = ttk.LabelFrame(content_frame, text="🧠 Memory Limits", style='TLabelframe')
        mem_section.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(mem_section, text="Max RAM Usage (%):", style='Config.TLabel').grid(
            row=0, column=0, sticky=tk.W, padx=10, pady=5
        )
        self.max_ram_percent = tk.IntVar(value=self.settings.get('max_ram_percent', 70))
        ttk.Spinbox(
            mem_section,
            from_=50,
            to=95,
            increment=5,
            textvariable=self.max_ram_percent,
            width=10
        ).grid(row=0, column=1, sticky=tk.W, padx=10, pady=5)

        ttk.Label(
            mem_section,
            text="Recommended: 70% for 8GB RAM, 80% for 16GB+",
            font=("Arial", 8),
            foreground='#888888'
        ).grid(row=1, column=0, columnspan=2, sticky=tk.W, padx=10, pady=(0, 10))

        # Training Memory Settings
        train_mem_section = ttk.LabelFrame(content_frame, text="⚙️ Training Memory", style='TLabelframe')
        train_mem_section.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(train_mem_section, text="Max Sequence Length:", style='Config.TLabel').grid(
            row=0, column=0, sticky=tk.W, padx=10, pady=5
        )
        self.max_seq_length = tk.IntVar(value=self.settings.get('max_seq_length', 256))
        seq_lengths = [128, 256, 512, 1024, 2048]
        seq_combo = ttk.Combobox(
            train_mem_section,
            textvariable=self.max_seq_length,
            values=seq_lengths,
            state="readonly",
            width=10
        )
        seq_combo.grid(row=0, column=1, sticky=tk.W, padx=10, pady=5)

        ttk.Label(train_mem_section, text="Gradient Accumulation:", style='Config.TLabel').grid(
            row=1, column=0, sticky=tk.W, padx=10, pady=5
        )
        self.gradient_accumulation = tk.IntVar(value=self.settings.get('gradient_accumulation', 16))
        ttk.Spinbox(
            train_mem_section,
            from_=1,
            to=32,
            textvariable=self.gradient_accumulation,
            width=10
        ).grid(row=1, column=1, sticky=tk.W, padx=10, pady=5)

        ttk.Label(
            train_mem_section,
            text="8GB RAM: Use 256 seq length + 16 accumulation\n16GB RAM: Use 512 seq length + 8 accumulation",
            font=("Arial", 8),
            foreground='#888888',
            justify=tk.LEFT
        ).grid(row=2, column=0, columnspan=2, sticky=tk.W, padx=10, pady=(0, 10))

        # Warning section
        warning_section = ttk.LabelFrame(content_frame, text="⚠️ Important Notes", style='TLabelframe')
        warning_section.pack(fill=tk.X, padx=10, pady=10)

        warning_text = """• Lower values = slower training but safer for your system
• If training crashes with OOM error, reduce sequence length
• If system freezes, reduce CPU threads
• These are DEFAULT values - you can override in Runner panel
• Changes take effect on next training session"""

        ttk.Label(
            warning_section,
            text=warning_text,
            font=("Arial", 9),
            foreground='#ffaa00',
            justify=tk.LEFT
        ).pack(padx=10, pady=10, anchor=tk.W)

    def _populate_tab_visibility_controls(self, parent_frame):
        """Populates the 'Tab Visibility' section with checkboxes for each tab."""
        # Clear existing controls
        for widget in parent_frame.winfo_children():
            widget.destroy()

        # Get a list of all known tabs (main tabs)
        known_tabs = [
            ("Training Tab", "training_tab_enabled"),
            ("Models Tab", "models_tab_enabled"),
            ("Settings Tab", "settings_tab_enabled"),
            ("Custom Code Tab", "custom_code_tab_enabled"),
            ("Map Tab", "map_tab_enabled"),
            ("Ag Knowledge Tab", "ag_forge_tab_enabled"),
        ]

        for display_name, setting_key in known_tabs:
            var = tk.BooleanVar(value=self.settings.get(setting_key, True)) # Default to enabled
            self.tab_enabled_vars[setting_key] = var

            cb = ttk.Checkbutton(
                parent_frame,
                text=f"Show {display_name}",
                variable=var,
                command=self._on_tab_visibility_changed,
                style='Category.TCheckbutton'
            )
            cb.pack(fill=tk.X, padx=10, pady=2, anchor=tk.W)

        # --- Tab Reordering Mode ---
        reorder_frame = ttk.LabelFrame(parent_frame, text="Tab Reordering Mode", style='TLabelframe')
        reorder_frame.pack(fill=tk.X, padx=10, pady=10)

        modes = [
            ("Static", "static"),
            ("D&D", "dnd"),
            ("Arrow Buttons", "arrow")
        ]

        for text, mode in modes:
            rb = ttk.Radiobutton(
                reorder_frame,
                text=text,
                variable=self.reorder_mode,
                value=mode,
                command=self._on_reorder_mode_changed,
                style='Category.TRadiobutton' # You might need to define this style
            )
            rb.pack(fill=tk.X, padx=10, pady=2, anchor=tk.W)

    def _on_tab_visibility_changed(self):
        """Callback when a tab visibility checkbox is toggled."""
        # Immediately save settings to persist the change
        self.save_settings_to_file()
        messagebox.showinfo("Tab Visibility Changed", "Tab visibility settings saved. Please Quick Restart the application to apply changes.")

    def _on_right_click_toggle(self):
        """Callback when the global right-click menu toggle changes."""
        enabled = self.right_click_enabled.get()
        log_message(f"SETTINGS: Right-click menus {'enabled' if enabled else 'disabled'} globally.")
        self.save_settings_to_file()

    def _on_reorder_mode_changed(self):
        """Callback when the reorder mode is changed."""
        mode = self.reorder_mode.get()
        
        if mode == 'arrow':
            if hasattr(self, 'move_left_button'):
                self.move_left_button.pack(fill=tk.X, pady=2)
                self.move_right_button.pack(fill=tk.X, pady=2)
        else:
            if hasattr(self, 'move_left_button'):
                self.move_left_button.pack_forget()
                self.move_right_button.pack_forget()

        if mode == 'static':
            self.save_settings_to_file()
            messagebox.showinfo("Settings Saved", "Tab order and reordering mode have been saved.")
        else:
            messagebox.showinfo("Reorder Mode Changed", f"Reorder mode set to '{mode}'.\n\nTab order changes are now temporary.\nSelect 'Static' to save the current order.")

    def move_tab(self, direction):
        """Move the selected tab left or right in the order, dynamically."""
        log_message(f"SETTINGS: move_tab called with direction: {direction}")
        if not self.selected_tree_item or self.selected_tree_item['type'] != 'tab':
            log_message("SETTINGS: move_tab aborted - no tab selected.")
            messagebox.showwarning("No Tab Selected", "Please select a tab from the tree to move.")
            return

        selected_tab_dir_name = self.selected_tree_item['path'].name
        log_message(f"SETTINGS: Selected tab for move: {selected_tab_dir_name}")

        if not self.main_gui or not hasattr(self.main_gui, 'notebook') or not self.tab_instances:
            log_message("SETTINGS ERROR: Main GUI, notebook, or tab_instances not available.")
            messagebox.showerror("Error", "Cannot reorder tabs. Internal components not found.")
            return

        notebook = self.main_gui.notebook

        if selected_tab_dir_name not in self.tab_instances:
            log_message(f"SETTINGS ERROR: Selected tab '{selected_tab_dir_name}' not in tab_instances.")
            messagebox.showerror("Error", "Selected tab not found in the application's tab registry.")
            return
            
        tab_to_move_frame = self.tab_instances[selected_tab_dir_name]['frame']

        try:
            current_index = notebook.index(tab_to_move_frame)
        except tk.TclError:
            log_message(f"SETTINGS ERROR: Could not find tab '{selected_tab_dir_name}' in the notebook.")
            messagebox.showerror("Error", "Could not find the selected tab in the notebook.")
            return

        new_index = current_index
        if direction == "left":
            if current_index > 0:
                new_index = current_index - 1
            else:
                log_message("SETTINGS: Cannot move tab further left.")
                return
        elif direction == "right":
            if current_index < len(notebook.tabs()) - 1:
                new_index = current_index + 1
            else:
                log_message("SETTINGS: Cannot move tab further right.")
                return
        
        log_message(f"SETTINGS: Moving tab from index {current_index} to {new_index}.")
        
        # Move the tab in the notebook
        notebook.insert(new_index, tab_to_move_frame)

        # Update the tab_order in settings dictionary (without saving to file)
        new_tab_order = []
        for tab_id in notebook.tabs():
            for name, info in self.tab_instances.items():
                if str(info['frame']) == tab_id:
                    new_tab_order.append(name)
                    break
        
        self.settings['tab_order'] = new_tab_order
        log_message(f"SETTINGS: New tab order in memory: {new_tab_order}")

        # Refresh the tree to show the new order based on the in-memory settings
        self.refresh_tabs_tree()
        
        # Restore selection
        if selected_tab_dir_name:
            # Find the item with the matching path/name in the tree
            for item in self.tabs_tree.get_children():
                # Values are (path_str, type)
                values = self.tabs_tree.item(item, 'values')
                if values and Path(values[0]).name == selected_tab_dir_name:
                    self.tabs_tree.selection_set(item)
                    self.tabs_tree.focus(item)
                    # Force update of inspector (on_tree_select should trigger, but to be safe)
                    self.on_tree_select(None) 
                    break

    def refresh_settings_tab(self):
        """Refresh the settings tab - reloads settings from file."""
        # Reload settings from file
        self.settings = self.load_settings()

        # Update all variable values from reloaded settings
        if hasattr(self, 'max_cpu_threads'):
            self.max_cpu_threads.set(self.settings.get('max_cpu_threads', 2))
        if hasattr(self, 'max_ram_percent'):
            self.max_ram_percent.set(self.settings.get('max_ram_percent', 70))
        if hasattr(self, 'max_seq_length'):
            self.max_seq_length.set(self.settings.get('max_seq_length', 256))
        if hasattr(self, 'gradient_accumulation'):
            self.gradient_accumulation.set(self.settings.get('gradient_accumulation', 16))

        log_message("SETTINGS: Settings tab refreshed.")

    def quick_restart_application(self):
        try:
            log_message("SETTINGS: User initiated Quick Restart. (Method entered)")
            # Call save_settings_to_file directly. It handles its own success/error messages.
            self.save_settings_to_file()

            # --- PRE-RESTART STATE FLUSH ---
            try:
                logger_util.flush_ux_events_to_disk()
                log_message("SETTINGS: Quick Restart — flushed UX events to disk")
                # Mark version stable (user chose restart, not crash)
                _vm = recovery_util.load_version_manifest()
                _cur = _vm.get("active_version")
                if _cur:
                    recovery_util.mark_version_status(_cur, "stable")
                    logger_util.log_successful_launch(_cur)
                    log_message(f"SETTINGS: Quick Restart — marked version {_cur} stable")
            except Exception as _fe:
                log_message(f"SETTINGS: Pre-restart flush error (non-fatal): {_fe}")

            # --- RESTART LOGIC ---
            # Launch a fresh instance (no --quick-restart flag so version gate runs normally).
            # Leave changes as pending (defer) — same as "Exit without saving" in on_closing.
            # Then cleanly shut down this process via main_gui._do_shutdown().
            try:
                main_script_path = DATA_DIR / "interactive_trainer_gui_NEW.py"
                if not main_script_path.exists():
                    main_script_path = Path(sys.argv[0])

                python_executable = sys.executable

                log_message(f"SETTINGS:   - Executable: {python_executable}")
                log_message(f"SETTINGS:   - Script: {main_script_path}")

                import subprocess
                subprocess.Popen([python_executable, str(main_script_path)])
                log_message("SETTINGS: Quick Restart — launched fresh instance, shutting down current process")

                # Cleanly shut down the current Tk process
                if self.main_gui and hasattr(self.main_gui, '_do_shutdown'):
                    self.main_gui._do_shutdown()
                else:
                    self.parent.winfo_toplevel().destroy()

            except Exception as e:
                messagebox.showerror("Restart Failed", f"Could not restart the application: {e}")
                log_message(f"SETTINGS ERROR: Restart failed: {e}")

        except Exception as e:
            log_message(f"SETTINGS CRITICAL ERROR: Unhandled exception in quick_restart_application: {e}")
            import traceback
            log_message(f"SETTINGS CRITICAL TRACEBACK: {traceback.format_exc()}")
            messagebox.showerror("Critical Error", f"An unexpected error occurred during Quick Restart: {e}\nCheck debug log for details.")

    def copy_log_to_clipboard(self):
        """Copies the content of the currently displayed log to the clipboard."""
        try:
            log_content = self.debug_output.get(1.0, tk.END)
            if not log_content.strip():
                messagebox.showinfo("Clipboard", "Log is empty. Nothing to copy.")
                return

            self.root.clipboard_clear()
            self.root.clipboard_append(log_content)
            messagebox.showinfo("Clipboard", "Log content copied to clipboard!")
            log_message("SETTINGS: Log content copied to clipboard.")
        except Exception as e:
            messagebox.showerror("Clipboard Error", f"Failed to copy log to clipboard: {e}")
            log_message(f"SETTINGS ERROR: Failed to copy log to clipboard: {e}")

    def create_custom_code_settings(self, parent):
        """Create Custom Code feature settings"""
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(0, weight=1)

        # Scrollable frame
        canvas = tk.Canvas(parent, bg="#2b2b2b", highlightthickness=0)
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        content_frame = ttk.Frame(canvas)

        content_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas_window = canvas.create_window((0, 0), window=content_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True, padx=5, pady=5)
        scrollbar.pack(side="right", fill="y")

        canvas.bind("<Configure>", lambda e: canvas.itemconfig(canvas_window, width=e.width))

        # Tool Orchestrator Section
        orchestrator_section = ttk.LabelFrame(content_frame, text="🎯 Tool Orchestrator", style='TLabelframe')
        orchestrator_section.pack(fill=tk.X, padx=10, pady=10)

        self.enable_tool_orchestrator = tk.BooleanVar(
            value=self.settings.get('custom_code', {}).get('enable_tool_orchestrator', False)
        )
        ttk.Checkbutton(
            orchestrator_section,
            text="Enable Advanced Tool Orchestrator",
            variable=self.enable_tool_orchestrator,
            style='Category.TCheckbutton'
        ).pack(anchor=tk.W, padx=10, pady=5)

        ttk.Label(
            orchestrator_section,
            text="Enables intelligent tool chaining, confirmation gates, and risk assessment",
            font=("Arial", 8),
            foreground='#888888'
        ).pack(anchor=tk.W, padx=10, pady=(0, 10))

        # Format Translators Section
        translators_section = ttk.LabelFrame(content_frame, text="🔄 Format Translators", style='TLabelframe')
        translators_section.pack(fill=tk.X, padx=10, pady=10)

        self.enable_json_translator = tk.BooleanVar(
            value=self.settings.get('custom_code', {}).get('enable_json_translator', True)
        )
        ttk.Checkbutton(
            translators_section,
            text="JSON Format Translator",
            variable=self.enable_json_translator,
            style='Category.TCheckbutton'
        ).pack(anchor=tk.W, padx=10, pady=5)

        self.enable_yaml_translator = tk.BooleanVar(
            value=self.settings.get('custom_code', {}).get('enable_yaml_translator', False)
        )
        ttk.Checkbutton(
            translators_section,
            text="YAML Format Translator",
            variable=self.enable_yaml_translator,
            style='Category.TCheckbutton'
        ).pack(anchor=tk.W, padx=10, pady=5)

        # Parsers Section
        parsers_section = ttk.LabelFrame(content_frame, text="📋 Response Parsers", style='TLabelframe')
        parsers_section.pack(fill=tk.X, padx=10, pady=10)

        self.enable_structured_parser = tk.BooleanVar(
            value=self.settings.get('custom_code', {}).get('enable_structured_parser', True)
        )
        ttk.Checkbutton(
            parsers_section,
            text="Structured Output Parser",
            variable=self.enable_structured_parser,
            style='Category.TCheckbutton'
        ).pack(anchor=tk.W, padx=10, pady=5)

        self.enable_datetime_parser = tk.BooleanVar(
            value=self.settings.get('custom_code', {}).get('enable_datetime_parser', False)
        )
        ttk.Checkbutton(
            parsers_section,
            text="DateTime Parser",
            variable=self.enable_datetime_parser,
            style='Category.TCheckbutton'
        ).pack(anchor=tk.W, padx=10, pady=5)

        self.enable_regex_parser = tk.BooleanVar(
            value=self.settings.get('custom_code', {}).get('enable_regex_parser', False)
        )
        ttk.Checkbutton(
            parsers_section,
            text="Regex Pattern Parser",
            variable=self.enable_regex_parser,
            style='Category.TCheckbutton'
        ).pack(anchor=tk.W, padx=10, pady=5)

        # Advanced Features Section
        advanced_section = ttk.LabelFrame(content_frame, text="⚙️ Advanced Features", style='TLabelframe')
        advanced_section.pack(fill=tk.X, padx=10, pady=10)

        self.enable_context_scorer = tk.BooleanVar(
            value=self.settings.get('custom_code', {}).get('enable_context_scorer', False)
        )
        ttk.Checkbutton(
            advanced_section,
            text="Context Scoring (RAG optimization)",
            variable=self.enable_context_scorer,
            style='Category.TCheckbutton'
        ).pack(anchor=tk.W, padx=10, pady=5)

        self.enable_time_slicer = tk.BooleanVar(
            value=self.settings.get('custom_code', {}).get('enable_time_slicer', False)
        )
        ttk.Checkbutton(
            advanced_section,
            text="Time-Sliced Generation",
            variable=self.enable_time_slicer,
            style='Category.TCheckbutton'
        ).pack(anchor=tk.W, padx=10, pady=5)

        self.enable_verification_engine = tk.BooleanVar(
            value=self.settings.get('custom_code', {}).get('enable_verification_engine', False)
        )
        ttk.Checkbutton(
            advanced_section,
            text="Verification Engine (output validation)",
            variable=self.enable_verification_engine,
            style='Category.TCheckbutton'
        ).pack(anchor=tk.W, padx=10, pady=5)

        # Save button
        ttk.Button(
            content_frame,
            text="💾 Save Custom Code Settings",
            command=self.save_custom_code_settings,
            style='Action.TButton'
        ).pack(pady=20, padx=10, fill=tk.X)

    def save_custom_code_settings(self):
        """Save custom code settings"""
        try:
            # Read existing settings
            all_settings = {}
            if self.settings_file.exists():
                try:
                    with open(self.settings_file, 'r') as f:
                        all_settings = json.load(f)
                except Exception as e:
                    log_message(f"SETTINGS ERROR: Could not read settings: {e}")

            # Update custom_code section
            all_settings['custom_code'] = {
                'enable_tool_orchestrator': self.enable_tool_orchestrator.get(),
                'enable_json_translator': self.enable_json_translator.get(),
                'enable_yaml_translator': self.enable_yaml_translator.get(),
                'enable_structured_parser': self.enable_structured_parser.get(),
                'enable_datetime_parser': self.enable_datetime_parser.get(),
                'enable_regex_parser': self.enable_regex_parser.get(),
                'enable_context_scorer': self.enable_context_scorer.get(),
                'enable_time_slicer': self.enable_time_slicer.get(),
                'enable_verification_engine': self.enable_verification_engine.get(),
            }

            # Save
            with open(self.settings_file, 'w') as f:
                json.dump(all_settings, f, indent=2)

            log_message("SETTINGS: Custom Code settings saved successfully")
            messagebox.showinfo("Settings Saved", "Custom Code settings have been saved successfully!")

        except Exception as e:
            log_message(f"SETTINGS ERROR: Failed to save custom code settings: {e}")
            messagebox.showerror("Save Error", f"Failed to save settings: {e}")

    def create_debug_tab(self, parent):
        """Create the live debug feed tab with log history viewer."""
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(2, weight=1) # Row 0 for header, Row 1 for controls, Row 2 for log display
        parent.rowconfigure(3, weight=0) # Row 3 for action panel (fixed height)

        # Header
        header = ttk.Frame(parent)
        header.grid(row=0, column=0, sticky=tk.EW, padx=10, pady=10)
        ttk.Label(header, text="🐞 Live Debug Log", font=("Arial", 12, "bold")).pack(side=tk.LEFT)

        # Log file selection controls
        controls_frame = ttk.Frame(parent)
        controls_frame.grid(row=1, column=0, sticky=tk.EW, padx=10, pady=5)
        controls_frame.columnconfigure(1, weight=1)

        ttk.Label(controls_frame, text="View Log History:", style='Config.TLabel').grid(row=0, column=0, sticky=tk.W, padx=(0, 5))

        self.log_file_var = tk.StringVar()
        self.log_file_combobox = ttk.Combobox(
            controls_frame,
            textvariable=self.log_file_var,
            state="readonly",
            width=50
        )
        self.log_file_combobox.grid(row=0, column=1, sticky=tk.EW, padx=(0, 5))
        self.log_file_combobox.bind("<<ComboboxSelected>>", self.on_log_file_selected)

        ttk.Button(controls_frame, text="🔄", command=self.populate_log_file_combobox, style='Select.TButton', width=4).grid(row=0, column=2, sticky=tk.E, padx=(0, 5))
        ttk.Button(controls_frame, text="📎", command=self.copy_log_to_clipboard, style='Select.TButton', width=4).grid(row=0, column=3, sticky=tk.E)

        # Log display
        self.debug_output = scrolledtext.ScrolledText(
            parent, wrap=tk.WORD, state=tk.DISABLED, font=("Courier", 9),
            bg="#1e1e1e", fg="#d4d4d4", relief='flat'
        )
        self.debug_output.grid(row=2, column=0, sticky='nsew', padx=10, pady=(0, 10))

        # #[Mark:PHASE_5_4_ACTION_PANEL] - Action panel for enriched changes
        self.create_action_panel(parent)

        # Populate combobox and start polling
        self.populate_log_file_combobox()
        self.start_log_polling()

    def create_action_panel(self, parent):
        """
        Creates the action panel at the bottom of Backups & Logs tab.
        Shows latest enriched changes with risk coloring and action buttons.
        #[Mark:PHASE_5_4_ACTION_PANEL_BUILD]
        """
        # Action panel frame
        action_panel = ttk.Frame(parent, relief=tk.SUNKEN, height=220)
        action_panel.grid(row=3, column=0, sticky='ew', padx=10, pady=(10, 10))
        action_panel.grid_propagate(False)
        action_panel.columnconfigure(0, weight=1)
        action_panel.columnconfigure(1, weight=0)

        # Left: Latest Changes List
        list_frame = ttk.LabelFrame(action_panel, text="Latest Changes", padding=5)
        list_frame.grid(row=0, column=0, sticky='nsew', padx=(0, 5))
        list_frame.columnconfigure(0, weight=1)
        list_frame.rowconfigure(0, weight=1)

        # Treeview for changes (organized by file) - no height limit, fills available space
        self.changes_tree = ttk.Treeview(
            list_frame, selectmode='browse',
            columns=('event_id', 'time', 'verb', 'tab', 'wherein'),
            show='tree headings'
        )
        self.changes_tree.grid(row=0, column=0, sticky='nsew')

        # Configure columns
        self.changes_tree.column('#0', width=260, anchor='w')
        self.changes_tree.column('event_id', width=0, anchor='w', stretch=False)  # Hidden storage
        self.changes_tree.column('time', width=80, anchor='w')
        self.changes_tree.column('verb', width=55, anchor='w')
        self.changes_tree.column('tab', width=100, anchor='w')
        self.changes_tree.column('wherein', width=160, anchor='w')
        self.changes_tree.heading('#0', text='Event / File', anchor='w')
        self.changes_tree.heading('event_id', text='ID', anchor='w')
        self.changes_tree.heading('time', text='Time', anchor='w')
        self.changes_tree.heading('verb', text='Type', anchor='w')
        self.changes_tree.heading('tab', text='Owning Tab', anchor='w')
        self.changes_tree.heading('wherein', text='Wherein', anchor='w')

        # Scrollbar for treeview
        scrollbar = ttk.Scrollbar(list_frame, command=self.changes_tree.yview)
        scrollbar.grid(row=0, column=1, sticky='ns')
        self.changes_tree.config(yscrollcommand=scrollbar.set)

        # Bind tree selection event
        self.changes_tree.bind('<<TreeviewSelect>>', self.on_change_tree_select)

        # Store selected event_id for button handlers
        self.selected_event_id = None

        # Status label + manual refresh button (below tree)
        status_frame = ttk.Frame(list_frame)
        status_frame.grid(row=1, column=0, columnspan=2, sticky='ew', padx=5, pady=(5, 0))
        self.changes_status_label = ttk.Label(status_frame, text="Scroll to see all files →", font=('Arial', 8))
        self.changes_status_label.pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(status_frame, text="🔄 Refresh", command=self.refresh_changes_list, width=8).pack(side=tk.RIGHT)

        # Right: Action Buttons
        button_frame = ttk.Frame(action_panel)
        button_frame.grid(row=0, column=1, sticky='n', padx=(5, 0))

        ttk.Button(
            button_frame,
            text="↶ Undo\nChange",
            command=self.on_undo_selected_change,
            width=12
        ).pack(pady=5)

        ttk.Button(
            button_frame,
            text="🔍 View\nBlame",
            command=self.on_view_blame,
            width=12
        ).pack(pady=5)

        ttk.Button(
            button_frame,
            text="⚠ Risk\nDetail",
            command=self.on_show_risk,
            width=12
        ).pack(pady=5)

        # Populate initial list
        self.refresh_changes_list()

        # Start auto-refresh polling
        self.start_changes_polling()

    def refresh_changes_list(self):
        """Populate changes tree with per-file grouping of enriched events."""
        # Clear the tree
        for item in self.changes_tree.get_children():
            self.changes_tree.delete(item)

        try:
            from pathlib import Path
            from datetime import datetime
            version_manifest_path = Path(__file__).parent.parent.parent / "backup" / "version_manifest.json"
            if not version_manifest_path.exists():
                self.changes_tree.insert('', 'end', text="No version manifest found", values=('', ''))
                return

            import json, time
            # Retry once on JSON parse error (race with concurrent atomic save)
            for _attempt in range(2):
                try:
                    with open(version_manifest_path, 'r') as f:
                        self.current_manifest = json.load(f)
                    break
                except json.JSONDecodeError:
                    if _attempt == 0:
                        time.sleep(0.3)
                    else:
                        self.changes_tree.insert('', 'end', text="Manifest temporarily unreadable — retry in a moment", values=('', ''))
                        return

            # Get enriched changes
            enriched = self.current_manifest.get("enriched_changes", {})

            if not enriched:
                self.changes_tree.insert('', 'end', text="No changes recorded yet", values=('', ''))
                return

            # Group events by file
            file_events = {}
            for event_id, change in enriched.items():
                file_path = change.get('file', 'Unknown')
                if file_path not in file_events:
                    file_events[file_path] = []
                file_events[file_path].append((event_id, change))

            # Sort files by most recent event timestamp (newest first)
            def get_latest_timestamp(file_path):
                events = file_events[file_path]
                timestamps = []
                for _, change in events:
                    ts = change.get('timestamp', '')
                    if ts:
                        timestamps.append(ts)
                return max(timestamps) if timestamps else ''
            sorted_files = sorted(file_events.keys(), key=get_latest_timestamp, reverse=True)

            # Build owning-tab lookup cache: file basename → tab name
            _tab_cache = {}
            for _tname, _treg in logger_util.TAB_REGISTRY.items():
                _src = _treg.get('source_file', '') or ''
                if _src:
                    import os as _os
                    _tab_cache[_os.path.basename(_src)] = _tname

            for file_path in sorted_files:
                events = file_events[file_path]
                # Sort events by event ID (newest first)
                events.sort(key=lambda x: x[0], reverse=True)

                # Resolve owning tab for this file
                file_basename = file_path.split('/')[-1] if '/' in file_path else file_path
                owning_tab_name = _tab_cache.get(file_basename, '—')

                # Insert file node
                file_short = file_basename
                file_node_text = f"📁 {file_short} [{len(events)} events]"
                try:
                    file_node = self.changes_tree.insert('', 'end', text=file_node_text,
                                                         values=('', '', '', owning_tab_name, ''),
                                                         tags=('file_node',))
                except Exception as file_error:
                    logger_util.log_message(f"SETTINGS_TAB: ERROR inserting file node for {file_path}: {file_error}")
                    continue

                # Insert event nodes under file
                for event_id, change in events:
                    try:
                        risk = change.get('risk_level', 'UNKNOWN')
                        risk_symbol = {'CRITICAL': '🔴', 'HIGH': '🟠', 'MEDIUM': '🟡', 'LOW': '🟢'}.get(risk, '⚪')
                        timestamp = change.get('timestamp', 'N/A')
                        verb = change.get('verb', 'unknown')

                        # Format time for display
                        try:
                            dt = datetime.fromisoformat(timestamp)
                            time_str = dt.strftime('%H:%M:%S')
                        except:
                            time_str = 'N/A'

                        # Wherein: explicit field, or construct from classes/lines if present
                        wherein = change.get('wherein', '')
                        if not wherein:
                            classes = change.get('classes', [])
                            lines = change.get('lines', [])
                            if classes:
                                wherein = f"∈ {classes[0]}"
                                if lines:
                                    wherein += f":{lines[0]}"
                            elif lines:
                                wherein = f"line {lines[0]}"

                        event_text = f"{risk_symbol} {event_id}"
                        event_node = self.changes_tree.insert(file_node, 'end', text=event_text,
                                                              values=(event_id, time_str, verb, owning_tab_name, wherein),
                                                              tags=('event_node',))
                    except Exception as e:
                        logger_util.log_message(f"SETTINGS_TAB: Error formatting event {event_id}: {e}")
                        continue

            # Expand all file nodes so events are visible
            for item in self.changes_tree.get_children():
                self.changes_tree.item(item, open=True)

            # Update status label
            self.changes_status_label.config(
                text=f"{len(enriched)} events across {len(file_events)} files"
            )

        except Exception as e:
            logger_util.log_message(f"SETTINGS_TAB: Error in refresh_changes_list: {e}")
            import traceback
            logger_util.log_message(f"SETTINGS_TAB: Traceback: {traceback.format_exc()}")
            self.changes_tree.insert('', 'end', text=f"Error loading changes: {str(e)}", values=('', '', '', ''))

    def on_change_tree_select(self, event=None):
        """Handle tree selection - enable undo only for event nodes."""
        try:
            selection = self.changes_tree.selection()
            if not selection:
                self.selected_event_id = None
                return

            item = selection[0]
            tags = self.changes_tree.item(item, 'tags')
            values = self.changes_tree.item(item, 'values')

            if 'event_node' in tags and values:
                # Event node selected - extract event_id from first value
                self.selected_event_id = values[0]
            else:
                # File node selected
                self.selected_event_id = None

        except Exception as e:
            logger_util.log_message(f"SETTINGS_TAB: Error in on_change_tree_select: {e}")
            self.selected_event_id = None

    def _extract_event_id(self, selection_index):
        """Extract event_id from listbox entry text."""
        try:
            entry_text = self.changes_listbox.get(selection_index)
            # Format: "🔴 #[Event:0001] | file | verb | feature"
            # Split by | and extract the event_id from first part
            parts = entry_text.split('|')
            if parts:
                event_part = parts[0].strip()
                # Extract event_id like "#[Event:0001]"
                import re
                match = re.search(r'#\[Event:\d+\]', event_part)
                if match:
                    return match.group(0)
            return None
        except Exception as e:
            logger_util.log_message(f"SETTINGS_TAB: Error extracting event_id: {e}")
            return None

    def on_undo_selected_change(self):
        """Handle undo button click - launch unified undo dialog."""
        if not self.selected_event_id:
            messagebox.showwarning("No Selection", "Please select a change to undo")
            return

        event_id = self.selected_event_id

        try:
            # Import and show undo dialog
            from .undo_changes import UndoChangesDialog

            logger_util.log_message(f"SETTINGS_TAB: Opening undo dialog for {event_id}")
            dialog = UndoChangesDialog(self.parent, event_id, self.current_manifest)

            # Refresh list after undo
            if dialog.result:
                logger_util.log_message(f"SETTINGS_TAB: Undo completed, refreshing list")
                self.refresh_changes_list()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to open undo dialog: {str(e)}")
            logger_util.log_message(f"SETTINGS_TAB: Error opening undo dialog: {e}")

    def on_view_blame(self):
        """Handle view blame button click - opens undo dialog with Blame & Risk tab."""
        if not self.selected_event_id:
            messagebox.showwarning("No Selection", "Please select a change to analyze")
            return
        self._open_undo_dialog_for_event(self.selected_event_id, initial_tab="blame_risk")

    def on_show_risk(self):
        """Handle show risk button click - opens undo dialog with Blame & Risk tab."""
        if not self.selected_event_id:
            messagebox.showwarning("No Selection", "Please select a change to analyze")
            return
        self._open_undo_dialog_for_event(self.selected_event_id, initial_tab="blame_risk")

    def _open_undo_dialog_for_event(self, event_id, initial_tab=None):
        """Open the unified undo dialog for a given event."""
        try:
            from .undo_changes import UndoChangesDialog
            dialog = UndoChangesDialog(self.parent, event_id, self.current_manifest, initial_tab=initial_tab)
            if dialog.result:
                self.refresh_changes_list()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open dialog: {str(e)}")
            logger_util.log_message(f"SETTINGS_TAB: Error opening dialog for {event_id}: {e}")

    def populate_log_file_combobox(self):
        """Populates the combobox with log files from BOTH DeBug directories.
        Scans:
          1. Trainer/DeBug/  — logger_util live logs (primary since ~Feb 17)
          2. Trainer/Data/DeBug/ — legacy logs + startup wrapper + training debug
        Sections the dropdown: Live Log first, then primary, separator, legacy.
        """
        self.log_file_paths.clear()

        # Two log directories: primary (logger_util) and legacy (Data/DeBug)
        from pathlib import Path as _P
        _primary_dir = _P(logger_util.get_log_file_path()).parent if logger_util.get_log_file_path() else None
        _legacy_dir = DATA_DIR / "DeBug"

        # Gather files from both dirs
        _primary_files = []
        _legacy_files = []
        if _primary_dir and _primary_dir.exists():
            _primary_files = glob.glob(str(_primary_dir / 'debug_log_*.txt'))
        if _legacy_dir.exists():
            _legacy_files = glob.glob(str(_legacy_dir / 'debug_log_*.txt'))
            # Also include startup wrapper logs
            _legacy_files += glob.glob(str(_legacy_dir / 'startup_wrapper_temp_*.log'))

        # Deduplicate if dirs happen to be the same
        _primary_set = set(_primary_files)
        _legacy_files = [f for f in _legacy_files if f not in _primary_set]

        _primary_files.sort(key=os.path.getctime, reverse=True)
        _legacy_files.sort(key=os.path.getctime, reverse=True)

        if not _primary_files and not _legacy_files:
            self.log_file_combobox['values'] = []
            self.log_file_var.set("No logs found")
            return

        display_names = []
        current_session_log_path = logger_util.get_log_file_path()

        # Section 1: Primary logs (Live + recent)
        for f_path in _primary_files:
            if str(f_path) == current_session_log_path:
                display_name = "★ Live Log"
            else:
                display_name = os.path.basename(f_path)
            display_names.append(display_name)
            self.log_file_paths[display_name] = str(f_path)

        # Section separator + Legacy logs
        if _legacy_files:
            sep_name = "── Data/DeBug (legacy + startup) ──"
            display_names.append(sep_name)
            self.log_file_paths[sep_name] = ""  # Non-selectable marker

            for f_path in _legacy_files[:30]:  # Cap legacy display
                display_name = f"[legacy] {os.path.basename(f_path)}"
                display_names.append(display_name)
                self.log_file_paths[display_name] = str(f_path)

        self.log_file_combobox['values'] = display_names

        # Select Live Log by default
        if "★ Live Log" in display_names:
            self.log_file_var.set("★ Live Log")
        elif display_names:
            self.log_file_var.set(display_names[0])

        self.on_log_file_selected()

    def on_log_file_selected(self, event=None):
        """Handles selection of a log file from the combobox, displaying its content and managing polling."""
        selected_display_name = self.log_file_var.get()
        if not selected_display_name or selected_display_name == "No logs found":
            return
        # Skip separator entries
        if selected_display_name.startswith("──"):
            return

        # Stop live polling initially
        self.stop_log_polling()

        selected_full_path = self.log_file_paths.get(selected_display_name)
        if not selected_full_path:
            self.debug_output.config(state=tk.NORMAL)
            self.debug_output.delete(1.0, tk.END)
            self.debug_output.insert(tk.END, f"Error: Log file path not found for: {selected_display_name}")
            self.debug_output.config(state=tk.DISABLED)
            return

        if not Path(selected_full_path).exists():
            self.debug_output.config(state=tk.NORMAL)
            self.debug_output.delete(1.0, tk.END)
            self.debug_output.insert(tk.END, f"Error: Log file not found on disk: {selected_full_path}")
            self.debug_output.config(state=tk.DISABLED)
            return

        self.current_log_file = selected_full_path
        self.last_read_position = 0

        self.debug_output.config(state=tk.NORMAL)
        self.debug_output.delete(1.0, tk.END)
        self.debug_output.insert(tk.END, f"--- Viewing log: {selected_display_name} ---\n\n")
        self.debug_output.config(state=tk.DISABLED)

        try:
            with open(self.current_log_file, 'r') as f:
                content = f.read()
                if content:
                    self.debug_output.config(state=tk.NORMAL)
                    self.debug_output.insert(tk.END, content)
                    self.debug_output.see(tk.END)
                    self.debug_output.config(state=tk.DISABLED)
                self.last_read_position = f.tell()
        except Exception as e:
            self.debug_output.config(state=tk.NORMAL)
            self.debug_output.insert(tk.END, f"\n--- ERROR READING LOG: {e} ---\n")
            self.debug_output.config(state=tk.DISABLED)

        # If the selected file is the current session's log, restart live polling
        # Compare resolved paths to handle symlinks/relative mismatches
        try:
            _is_live = (Path(self.current_log_file).resolve()
                       == Path(logger_util.get_log_file_path()).resolve())
        except Exception:
            _is_live = self.current_log_file == logger_util.get_log_file_path()
        if _is_live:
            self.start_log_polling() # Restart polling for the live log

    # --- Evaluation Policy UI ---
    def _init_policy_vars(self):
        data = self.settings.get('regression_policy', {}) if hasattr(self, 'settings') else {}
        self.policy_enabled = tk.BooleanVar(value=data.get('enabled', True))
        self.policy_alert_drop = tk.DoubleVar(value=data.get('alert_drop_percent', 5.0))
        self.policy_strict_block = tk.BooleanVar(value=data.get('strict_block', False))
        self.policy_auto_rollback = tk.BooleanVar(value=data.get('auto_rollback', False))

    def create_policy_settings(self, parent):
        parent.columnconfigure(0, weight=1)
        container = ttk.Frame(parent, style='Category.TFrame')
        container.grid(row=0, column=0, sticky=tk.NSEW, padx=10, pady=10)
        if not hasattr(self, 'policy_enabled'):
            self._init_policy_vars()

        ttk.Label(container, text="Evaluation & Regression Policy", font=("Arial", 12, "bold"), style='CategoryPanel.TLabel').grid(row=0, column=0, sticky=tk.W, pady=(0, 10))
        ttk.Checkbutton(container, text="Enable Regression Policy", variable=self.policy_enabled, style='Category.TCheckbutton').grid(row=1, column=0, sticky=tk.W, pady=5)

        row_frame = ttk.Frame(container)
        row_frame.grid(row=2, column=0, sticky=tk.W)
        ttk.Label(row_frame, text="Alert if drop > %:", style='Config.TLabel').pack(side=tk.LEFT, padx=(0, 8))
        ttk.Spinbox(row_frame, from_=0.0, to=100.0, increment=0.5, textvariable=self.policy_alert_drop, width=8).pack(side=tk.LEFT)

        ttk.Checkbutton(container, text="Strict Mode: Flag training if regressions detected", variable=self.policy_strict_block, style='Category.TCheckbutton').grid(row=3, column=0, sticky=tk.W, pady=5)
        ttk.Checkbutton(container, text="Auto-Rollback (not implemented)", variable=self.policy_auto_rollback, style='Category.TCheckbutton').grid(row=4, column=0, sticky=tk.W, pady=5)
        ttk.Button(container, text="💾 Save Policy", command=self.save_settings_to_file, style='Action.TButton').grid(row=5, column=0, sticky=tk.W, pady=(10,0))

    def start_log_polling(self):
        """Starts the periodic polling of the log file."""
        if self.log_poll_job:
            self.parent.after_cancel(self.log_poll_job)
        self.poll_log_file()

    def stop_log_polling(self):
        """Stops the periodic polling of the log file."""
        if self.log_poll_job:
            self.parent.after_cancel(self.log_poll_job)
            self.log_poll_job = None

    def start_changes_polling(self):
        """Start periodic polling of the version manifest for changes."""
        if self.changes_poll_job:
            self.parent.after_cancel(self.changes_poll_job)
        self.poll_changes_list()

    def stop_changes_polling(self):
        """Stop periodic polling of the version manifest."""
        if self.changes_poll_job:
            self.parent.after_cancel(self.changes_poll_job)
            self.changes_poll_job = None

    def poll_changes_list(self):
        """Check if manifest changed and refresh the changes tree if so."""
        try:
            from pathlib import Path
            version_manifest_path = Path(__file__).parent.parent.parent / "backup" / "version_manifest.json"

            if version_manifest_path.exists():
                current_mtime = version_manifest_path.stat().st_mtime
                # Only refresh if modification time changed
                if self.last_manifest_mtime is None or current_mtime != self.last_manifest_mtime:
                    self.last_manifest_mtime = current_mtime
                    self.refresh_changes_list()
        except Exception as e:
            logger_util.log_message(f"SETTINGS_TAB: Error in poll_changes_list: {e}")

        # Schedule next poll (every 8 seconds)
        self.changes_poll_job = self.parent.after(8000, self.poll_changes_list)

    def poll_log_file(self):
        """Checks the current log file for new content and updates the display. Only polls if viewing the live log."""
        # Only poll if the currently viewed log is the live log (resolve paths for cross-dir match)
        try:
            _is_live = (Path(self.current_log_file).resolve()
                       == Path(logger_util.get_log_file_path()).resolve())
        except Exception:
            _is_live = self.current_log_file == logger_util.get_log_file_path()
        if not _is_live:
            self.log_poll_job = self.parent.after(2000, self.poll_log_file)
            return

        # Use the actual live log directory (from logger_util), not DATA_DIR
        _live_dir = Path(logger_util.get_log_file_path()).parent
        list_of_files = glob.glob(str(_live_dir / 'debug_log_*.txt'))
        if not list_of_files:
            self.debug_output.config(state=tk.NORMAL)
            self.debug_output.delete(1.0, tk.END)
            self.debug_output.insert(tk.END, "No log files found in DeBug directory.")
            self.debug_output.config(state=tk.DISABLED)
            self.log_poll_job = self.parent.after(2000, self.poll_log_file)
            return

        # Ensure we are always polling the actual latest file if 'Live Log' is selected
        actual_latest_file = max(list_of_files, key=os.path.getctime)
        if self.current_log_file != actual_latest_file:
            self.current_log_file = actual_latest_file
            self.last_read_position = 0
            self.log_file_var.set("★ Live Log")
            self.debug_output.config(state=tk.NORMAL)
            self.debug_output.delete(1.0, tk.END)
            self.debug_output.insert(tk.END, f"--- Switched to live log: {os.path.basename(actual_latest_file)} ---\n\n")
            self.debug_output.config(state=tk.DISABLED)

        try:
            with open(self.current_log_file, 'r') as f:
                f.seek(self.last_read_position)
                new_content = f.read()
                if new_content:
                    self.debug_output.config(state=tk.NORMAL)
                    self.debug_output.insert(tk.END, new_content)
                    self.debug_output.see(tk.END)
                    self.debug_output.config(state=tk.DISABLED)
                self.last_read_position = f.tell()

        except Exception as e:
            self.debug_output.config(state=tk.NORMAL)
            self.debug_output.insert(tk.END, f"\n--- ERROR POLLING LOG: {e} ---\n")
            self.debug_output.config(state=tk.DISABLED)
        
        self.log_poll_job = self.parent.after(2000, self.poll_log_file) # Poll every 2 seconds

    def create_blueprints_tab(self, parent):
        """Create System Blueprints documentation tab"""
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(0, weight=1)

        # Scrollable frame
        canvas = tk.Canvas(parent, bg="#2b2b2b", highlightthickness=0)
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        content_frame = ttk.Frame(canvas)

        content_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas_window = canvas.create_window((0, 0), window=content_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True, padx=5, pady=5)
        scrollbar.pack(side="right", fill="y")

        canvas.bind("<Configure>", lambda e: canvas.itemconfig(canvas_window, width=e.width))

        # Header
        header_section = ttk.Frame(content_frame)
        header_section.pack(fill=tk.X, padx=10, pady=10)
        ttk.Label(
            header_section,
            text="🗺️ OpenCode Trainer System Architecture",
            font=("Arial", 14, "bold"),
            foreground='#4db8ff'
        ).pack(anchor=tk.W)
        ttk.Label(
            header_section,
            text="Complete End-to-End Integrated Training Pipeline",
            font=("Arial", 10),
            foreground='#888888'
        ).pack(anchor=tk.W)

        # Overview Section
        overview_section = ttk.LabelFrame(content_frame, text="📋 System Overview", style='TLabelframe')
        overview_section.pack(fill=tk.X, padx=10, pady=10)

        overview_text = """The OpenCode Trainer integrates multiple subsystems to provide a complete model lifecycle management platform:

        ✓ Model Lineage Tracking - Track model genealogy from base to fine-tuned versions
        ✓ Dual Skill Verification - Runtime usage validation vs evaluation test results
        ✓ Automated Training Data Generation - Multiple sources for training data creation
        ✓ Regression Detection - Identify skill degradation with auto-correction
        ✓ Complete Workflow Integration - Seamless flow from download to deployment"""

        overview_label = ttk.Label(
            overview_section,
            text=overview_text,
            font=("Arial", 9),
            foreground='#cccccc',
            justify=tk.LEFT,
            wraplength=700
        )
        overview_label.pack(padx=10, pady=10, anchor=tk.W)

        # Integrated Workflow Section
        workflow_section = ttk.LabelFrame(content_frame, text="🔄 Complete Integrated Workflow", style='TLabelframe')
        workflow_section.pack(fill=tk.X, padx=10, pady=10)

        workflow_text = """STEP 1: Model Download & Initial Evaluation
        • Download base model (e.g., Qwen 0.5B) to Models directory
        • Convert to GGUF format
        • Run initial evaluation tests (Models Tab → Evaluate)
        • Baseline skills recorded (claimed skills from tests)

STEP 2: Runtime Validation & Data Collection
        • Enable "Training Mode" in Custom Code Chat Interface
        • Use the model with real tasks and tool calls
        • ToolCallLogger captures every tool invocation with success/failure
        • Real-time skill scoring updated (verified skills from actual usage)
        • ChatHistoryManager saves conversations for later extraction

STEP 3: Skill Verification & Gap Analysis
        • Models Tab displays DUAL skill view:
          - Verified (Runtime): ≥80% success rate, actual usage proof
          - Claimed (Evaluation): Test results, may be false positives
          - Failed: <80% success rate, needs training
        • Identify gaps: skills with good eval but poor runtime = false positives
        • Identify needs: skills with 0% runtime usage = untrained capabilities

STEP 4: Automated Training Data Generation
        Multiple sources automatically create training data:
        • Chat History Extraction: Extract successful tool usage patterns
        • Runtime Log Conversion: Convert tool call logs to training format
        • Corrective Data Generation: Auto-generate examples for failed skills
        All outputs saved to Training_Data-Sets/ directory

STEP 5: LoRA Fine-Tuning with Lineage Tracking
        • Select generated training data in Training Tab
        • Configure LoRA parameters (r=16, alpha=32, etc.)
        • TrainingEngine automatically:
          - Fine-tunes with adapters
          - Records lineage (base model → adapter → metadata)
          - Runs post-training evaluation
          - Saves results to Models directory

STEP 6: Regression Detection & Continuous Improvement
        • EvaluationEngine compares new eval to baseline
        • Detects regressions: skills that dropped >5% accuracy
        • Auto-generates corrective training data targeting failed skills
        • Provides re-training recommendations
        • Complete cycle: evaluate → identify issues → generate fixes → retrain"""

        workflow_label = ttk.Label(
            workflow_section,
            text=workflow_text,
            font=("Courier", 8),
            foreground='#aaaaaa',
            justify=tk.LEFT,
            wraplength=700
        )
        workflow_label.pack(padx=10, pady=10, anchor=tk.W)

        # System Integration Map
        integration_section = ttk.LabelFrame(content_frame, text="🔗 System Integration Map", style='TLabelframe')
        integration_section.pack(fill=tk.X, padx=10, pady=10)

        integration_text = """┌─────────────────────────────────────────────────────────────┐
│                    DATA FLOW INTEGRATION                    │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ToolCallLogger ──────┬──────> RuntimeToTrainingConverter  │
│      (JSONL logs)     │              ↓                      │
│                       │     Training Data (JSONL)           │
│                       │              ↓                      │
│  ChatHistoryManager ──┤──────> TrainingEngine               │
│      (conversations)  │         (LoRA fine-tune)            │
│                       │              ↓                      │
│  EvaluationEngine ────┤──────> LineageTracker              │
│      (test reports)   │         (model genealogy)           │
│                       │              ↓                      │
│  config.py ───────────┘──────> Models Tab Display          │
│  (_get_runtime_skills)           (dual verification)       │
│                                                             │
└─────────────────────────────────────────────────────────────┘

KEY INTEGRATION POINTS:
• ToolCallLogger → RuntimeSkills: Real-time scoring in config.py
• ChatHistoryManager → Training Data: Extract successful patterns
• EvaluationEngine → Baseline Comparison: Detect regressions
• TrainingEngine → LineageTracker: Record model genealogy
• Models Tab: Merge runtime + evaluation skills for display"""

        integration_label = ttk.Label(
            integration_section,
            text=integration_text,
            font=("Courier", 8),
            foreground='#88ff88',
            justify=tk.LEFT
        )
        integration_label.pack(padx=10, pady=10, anchor=tk.W)

        # Key Components Section
        components_section = ttk.LabelFrame(content_frame, text="⚙️ Key System Components", style='TLabelframe')
        components_section.pack(fill=tk.X, padx=10, pady=10)

        components_text = """LINEAGE TRACKER (tabs/custom_code_tab/lineage_tracker.py)
• Singleton pattern for model genealogy tracking
• Records: base model, adapter path, training date, metadata
• File: Training_Data-Sets/ModelLineage/lineage.json
• Integration: Called automatically by TrainingEngine after training

TOOL CALL LOGGER (tabs/custom_code_tab/tool_call_logger.py)
• JSONL-based persistent logging of all tool calls
• Tracks: tool name, arguments, result, success/failure, timestamp
• Enhanced validation: Multi-level success detection
• File: Training_Data-Sets/ToolCallLogs/{model_name}_calls.jsonl
• Integration: Chat interface logs every tool execution

RUNTIME TO TRAINING CONVERTER (tabs/custom_code_tab/runtime_to_training.py)
• Converts tool call logs to OpenAI training format
• Generates corrective training data from failures
• Creates proper message sequences: user → assistant → tool → assistant
• Output: Training_Data-Sets/Training/{model}_runtime_{timestamp}.jsonl

CHAT HISTORY MANAGER (tabs/custom_code_tab/chat_history_manager.py)
• Persistent conversation storage with training extraction
• Filters by tool usage count and success rate
• Extracts complete tool usage patterns
• File: Training_Data-Sets/ChatHistories/{session_id}.json

EVALUATION ENGINE (Data/evaluation_engine.py)
• Test suite execution with regression detection
• Compares current results to baseline (first eval)
• Auto-triggers corrective training on regression
• Reports: Training_Data-Sets/Evaluations/{model}_eval_report.json

TRAINING ENGINE (Data/training_engine.py)
• LoRA fine-tuning with Unsloth
• Automatic post-training evaluation
• Lineage recording after every training run
• Output: Models/{model_name}/ (adapter + merged model)

MODELS TAB (tabs/models_tab/models_tab.py)
• Dual skill verification display:
  - Verified Runtime: Green, ≥80% success
  - Unverified Eval: Yellow, low/no runtime usage
  - Failed Runtime: Red, <80% success
• Merges _get_runtime_skills() + get_model_skills()
• Shows skill source: (Runtime/Eval/Both)"""

        components_label = ttk.Label(
            components_section,
            text=components_text,
            font=("Courier", 8),
            foreground='#ffaa88',
            justify=tk.LEFT
        )
        components_label.pack(padx=10, pady=10, anchor=tk.W)

        # Data Flow Section
        dataflow_section = ttk.LabelFrame(content_frame, text="📊 Data Persistence & Storage", style='TLabelframe')
        dataflow_section.pack(fill=tk.X, padx=10, pady=10)

        dataflow_text = """Training_Data-Sets/
├── ChatHistories/           # Saved conversations
│   ├── {session_id}.json
│   └── chat_index.json
├── ToolCallLogs/            # Runtime tool execution logs
│   └── {model_name}_calls.jsonl
├── ModelLineage/            # Model genealogy tracking
│   └── lineage.json
├── Evaluations/             # Test results and baselines
│   └── {model_name}_eval_report.json
└── Training/                # Generated training data
    ├── {model}_runtime_{timestamp}.jsonl
    ├── {model}_corrective_{timestamp}.jsonl
    └── chat_extracted_{model}_{timestamp}.jsonl

Models/
└── {model_name}/
    ├── adapter_model.safetensors  # LoRA adapter weights
    ├── adapter_config.json
    └── model_merged.gguf          # Final merged GGUF

JSONL Format (training data):
{"messages": [
  {"role": "system", "content": "..."},
  {"role": "user", "content": "..."},
  {"role": "assistant", "content": "...", "tool_calls": [...]},
  {"role": "tool", "content": "...", "tool_call_id": "..."},
  {"role": "assistant", "content": "..."}
]}"""

        dataflow_label = ttk.Label(
            dataflow_section,
            text=dataflow_text,
            font=("Courier", 8),
            foreground='#ffdd88',
            justify=tk.LEFT
        )
        dataflow_label.pack(padx=10, pady=10, anchor=tk.W)

    def create_help_tab(self, parent):
        """Create Help & Guide tab"""
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(0, weight=1)

        # Scrollable frame
        canvas = tk.Canvas(parent, bg="#2b2b2b", highlightthickness=0)
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        content_frame = ttk.Frame(canvas)

        content_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas_window = canvas.create_window((0, 0), window=content_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True, padx=5, pady=5)
        scrollbar.pack(side="right", fill="y")

        canvas.bind("<Configure>", lambda e: canvas.itemconfig(canvas_window, width=e.width))

        # Header
        header_section = ttk.Frame(content_frame)
        header_section.pack(fill=tk.X, padx=10, pady=10)
        ttk.Label(
            header_section,
            text="📖 OpenCode Trainer User Guide",
            font=("Arial", 14, "bold"),
            foreground='#4db8ff'
        ).pack(anchor=tk.W)
        ttk.Label(
            header_section,
            text="Complete guide to using the integrated training pipeline",
            font=("Arial", 10),
            foreground='#888888'
        ).pack(anchor=tk.W)

        # Quick Start Section
        quickstart_section = ttk.LabelFrame(content_frame, text="🚀 Quick Start Guide", style='TLabelframe')
        quickstart_section.pack(fill=tk.X, padx=10, pady=10)

        quickstart_text = """1. DOWNLOAD A MODEL
   • Go to Models Tab
   • Click "Download Model from Hugging Face"
   • Enter model ID (e.g., "Qwen/Qwen2.5-0.5B")
   • Wait for download and GGUF conversion

2. EVALUATE BASELINE SKILLS
   • Select your model in Models Tab
   • Click "Evaluate Model"
   • Review baseline skills in Skills section

3. COLLECT RUNTIME DATA
   • Go to Custom Code Tab → Chat Interface
   • Enable "Training Mode" checkbox
   • Use the model for real tasks with tool calls
   • System automatically logs all tool usage

4. VERIFY REAL SKILLS
   • Return to Models Tab
   • Review Skills display showing:
     - Verified Runtime (green): Actually works
     - Claimed Eval (yellow): Test says it works
     - Failed (red): Doesn't work in practice

5. GENERATE TRAINING DATA
   • In Custom Code Chat Interface:
     - Click "Export Runtime to Training" for tool logs
     - Click "Extract Chat Training Data" for conversations
   • Or use Evaluation Tab for corrective data generation

6. FINE-TUNE THE MODEL
   • Go to Training Tab
   • Select generated training data file
   • Configure LoRA settings (defaults work well)
   • Click "Start Training"
   • System auto-evaluates and records lineage

7. VERIFY IMPROVEMENTS
   • Check Models Tab Skills display
   • Runtime scores should improve
   • Re-train with corrective data if regressions detected"""

        quickstart_label = ttk.Label(
            quickstart_section,
            text=quickstart_text,
            font=("Courier", 8),
            foreground='#cccccc',
            justify=tk.LEFT
        )
        quickstart_label.pack(padx=10, pady=10, anchor=tk.W)

        # Training Mode Section
        training_mode_section = ttk.LabelFrame(content_frame, text="🎯 Using Training Mode", style='TLabelframe')
        training_mode_section.pack(fill=tk.X, padx=10, pady=10)

        training_mode_text = """WHAT IS TRAINING MODE?
Training Mode enables real-time data collection during chat interactions.
When enabled, the system logs every tool call with detailed success metrics.

HOW TO ENABLE:
1. Go to Custom Code Tab → Chat Interface sub-tab
2. Check the "Training Mode" checkbox at the top
3. Green indicator shows mode is active

WHAT GETS COLLECTED:
✓ Every tool call (name, arguments, result)
✓ Success/failure status with enhanced validation
✓ User message context for each tool call
✓ Complete conversation history
✓ Timestamp and execution metadata

WHERE DATA IS SAVED:
• Tool Call Logs: Training_Data-Sets/ToolCallLogs/{model}_calls.jsonl
• Chat History: Training_Data-Sets/ChatHistories/{session_id}.json

BEST PRACTICES:
• Enable for new/unverified models to collect baseline data
• Disable for production use after sufficient data collected
• Use diverse tasks to cover multiple tool types
• Review Models Tab regularly to check skill improvement

DATA PRIVACY:
All data stays local on your machine. Nothing is sent externally."""

        training_mode_label = ttk.Label(
            training_mode_section,
            text=training_mode_text,
            font=("Arial", 9),
            foreground='#aaffaa',
            justify=tk.LEFT,
            wraplength=700
        )
        training_mode_label.pack(padx=10, pady=10, anchor=tk.W)

        # Skill Verification Section
        skills_section = ttk.LabelFrame(content_frame, text="✅ Understanding Skill Verification", style='TLabelframe')
        skills_section.pack(fill=tk.X, padx=10, pady=10)

        skills_text = """DUAL VERIFICATION SYSTEM:
The system shows TWO types of skills to identify false positives.

VERIFIED RUNTIME SKILLS (Green)
• Source: Actual tool usage in Chat Interface
• Criteria: ≥80% success rate with ≥3 attempts
• Meaning: Model REALLY has this skill
• Example: file_read: 15 calls, 93% success → VERIFIED

CLAIMED EVALUATION SKILLS (Yellow)
• Source: Test suite results (Models Tab → Evaluate)
• Warning: May test base model, not your fine-tuned GGUF
• Meaning: Tests say it works, but no runtime proof
• Example: web_search: Passed tests but 0 real usage → CLAIMED

FAILED RUNTIME SKILLS (Red)
• Source: Runtime usage with poor success rate
• Criteria: <80% success rate
• Meaning: Model tried but failed
• Action: Generate corrective training data

WHY DUAL VERIFICATION MATTERS:
The evaluation tests run against the base PyTorch model, but you're
using the fine-tuned GGUF. This can create FALSE POSITIVES where
tests pass but the actual model fails.

Runtime verification proves skills by actual usage, not just tests.

HOW TO INTERPRET:
• Green + Yellow = Truly verified skill
• Yellow only = Possible false positive, needs runtime testing
• Red = Needs training
• No color = Never tested or used"""

        skills_label = ttk.Label(
            skills_section,
            text=skills_text,
            font=("Arial", 9),
            foreground='#ffffaa',
            justify=tk.LEFT,
            wraplength=700
        )
        skills_label.pack(padx=10, pady=10, anchor=tk.W)

        # Training Data Section
        training_data_section = ttk.LabelFrame(content_frame, text="📦 Training Data Generation", style='TLabelframe')
        training_data_section.pack(fill=tk.X, padx=10, pady=10)

        training_data_text = """THREE AUTOMATED SOURCES:

1. RUNTIME LOG CONVERSION
   Location: Chat Interface → "Export Runtime to Training"
   What: Converts tool call logs to training format
   Best for: Models with lots of usage data
   Output: Training_Data-Sets/Training/{model}_runtime_{timestamp}.jsonl

2. CHAT HISTORY EXTRACTION
   Location: Chat Interface → "Extract Chat Training Data"
   What: Extracts successful conversation patterns
   Filters: Min tool calls, successful only
   Best for: High-quality conversational patterns
   Output: Training_Data-Sets/Training/chat_extracted_{model}_{timestamp}.jsonl

3. CORRECTIVE DATA GENERATION
   Location: Evaluation Tab → Auto-triggered on regression
   What: Generates correct examples for failed skills
   Targets: Skills with <60% success rate
   Best for: Fixing specific skill failures
   Output: Training_Data-Sets/Training/{model}_corrective_{timestamp}.jsonl

MANUAL DATA CREATION:
You can also manually create training data in JSONL format:
{"messages": [
  {"role": "user", "content": "Search for Python tutorials"},
  {"role": "assistant", "content": "", "tool_calls": [...]},
  {"role": "tool", "content": "...", "tool_call_id": "..."},
  {"role": "assistant", "content": "I found..."}
]}

COMBINING SOURCES:
For best results, merge multiple sources:
• Runtime logs: Real usage patterns
• Chat extractions: Successful conversations
• Corrective data: Targeted fixes for failures"""

        training_data_label = ttk.Label(
            training_data_section,
            text=training_data_text,
            font=("Arial", 9),
            foreground='#ffaaff',
            justify=tk.LEFT,
            wraplength=700
        )
        training_data_label.pack(padx=10, pady=10, anchor=tk.W)

        # Regression Detection Section
        regression_section = ttk.LabelFrame(content_frame, text="⚠️ Regression Detection & Auto-Correction", style='TLabelframe')
        regression_section.pack(fill=tk.X, padx=10, pady=10)

        regression_text = """WHAT IS REGRESSION?
Regression occurs when a model's skills degrade after training.
Example: file_read was 90% accurate, now it's 75% after fine-tuning.

HOW DETECTION WORKS:
1. First evaluation creates BASELINE
2. Subsequent evaluations compare to baseline
3. Skills that drop >5% accuracy = REGRESSED
4. System identifies specific skills that degraded

AUTO-CORRECTION FLOW:
When regression detected:
1. EvaluationEngine.auto_trigger_corrective_training() runs
2. Identifies regressed skills (e.g., ["file_read", "web_search"])
3. Generates corrective training data from:
   - Runtime failures (shows what went wrong)
   - Chat history successes (shows correct patterns)
4. Saves corrective data files
5. Provides re-training recommendation

MANUAL REGRESSION CHECK:
• Go to Models Tab
• Click "Evaluate Model"
• Review evaluation report for regressions
• If found, check Training_Data-Sets/Training/ for corrective files

RE-TRAINING AFTER REGRESSION:
1. Use generated corrective training data
2. Reduce learning rate (try 1e-4 instead of 2e-4)
3. Fewer epochs (1-2) to avoid over-fitting
4. Re-evaluate to confirm improvement

PREVENTION TIPS:
• Don't over-train (3 epochs is usually enough)
• Use diverse training data
• Keep learning rate moderate (2e-4 default)
• Regular evaluation checks after training"""

        regression_label = ttk.Label(
            regression_section,
            text=regression_text,
            font=("Arial", 9),
            foreground='#ffaa88',
            justify=tk.LEFT,
            wraplength=700
        )
        regression_label.pack(padx=10, pady=10, anchor=tk.W)

        # Troubleshooting Section
        troubleshooting_section = ttk.LabelFrame(content_frame, text="🔧 Troubleshooting Common Issues", style='TLabelframe')
        troubleshooting_section.pack(fill=tk.X, padx=10, pady=10)

        troubleshooting_text = """ISSUE: "Model shows skills but fails in chat"
SOLUTION: False positive from evaluation. The test ran on base model,
          not your GGUF. Enable Training Mode and collect real usage data.

ISSUE: "Training data file is empty"
SOLUTION: No tool calls logged yet. Enable Training Mode and use the
          model with tools before exporting training data.

ISSUE: "Skills not improving after training"
SOLUTION:
  1. Check training data quality (open JSONL file)
  2. Increase epochs (try 5-10)
  3. Increase LoRA rank (try r=32)
  4. Ensure training data matches your use case

ISSUE: "Runtime scores not updating"
SOLUTION: Scores persist to config.py on:
  - Model switch
  - Training mode disable
  - Manual export
  Check Models Tab to verify persistence.

ISSUE: "Can't find generated training data"
SOLUTION: Check Training_Data-Sets/Training/ directory.
          Files named: {model}_runtime_{timestamp}.jsonl

ISSUE: "Regression detected after every training"
SOLUTION: You may be over-training. Reduce:
  - Epochs: 1-2 instead of 3+
  - Learning rate: 1e-4 instead of 2e-4
  - Use more diverse training data

ISSUE: "Models Tab shows no skills"
SOLUTION:
  1. Run evaluation first (Models Tab → Evaluate)
  2. Or use model in chat with Training Mode enabled
  3. Skills appear after either evaluation or runtime usage"""

        troubleshooting_label = ttk.Label(
            troubleshooting_section,
            text=troubleshooting_text,
            font=("Arial", 9),
            foreground='#ff8888',
            justify=tk.LEFT,
            wraplength=700
        )
        troubleshooting_label.pack(padx=10, pady=10, anchor=tk.W)

        # Best Practices Section
        best_practices_section = ttk.LabelFrame(content_frame, text="⭐ Best Practices", style='TLabelframe')
        best_practices_section.pack(fill=tk.X, padx=10, pady=10)

        best_practices_text = """MODEL LIFECYCLE:
1. Download → 2. Evaluate → 3. Runtime Test → 4. Collect Data →
5. Generate Training → 6. Fine-tune → 7. Re-evaluate → 8. Deploy

DATA COLLECTION:
• Collect at least 20-30 tool calls before training
• Use diverse tasks covering all tool types
• Include both successes and failures for balance
• Save conversations with good tool usage patterns

TRAINING:
• Start with defaults: 3 epochs, 2e-4 LR, r=16, alpha=32
• Use batch size 2 for 8GB RAM, 4 for 16GB+
• Combine multiple training data sources for best results
• Always run evaluation after training

SKILL VERIFICATION:
• Trust VERIFIED (green) skills - they're proven
• Test CLAIMED (yellow) skills - they may be false positives
• Re-train FAILED (red) skills with corrective data
• Regularly review Models Tab for skill status

REGRESSION HANDLING:
• Check for regressions after every training run
• Use auto-generated corrective data
• Reduce training intensity if regression persists
• Keep baseline evaluation for comparison

SYSTEM MAINTENANCE:
• Clear old logs periodically (Settings → Clear Cache)
• Archive successful training data for reuse
• Keep lineage.json for model tracking
• Regular evaluations to monitor skill drift"""

        best_practices_label = ttk.Label(
            best_practices_section,
            text=best_practices_text,
            font=("Arial", 9),
            foreground='#88ffff',
            justify=tk.LEFT,
            wraplength=700
        )
        best_practices_label.pack(padx=10, pady=10, anchor=tk.W)

    def _on_tab_visibility_changed(self):
        """Callback when a tab visibility checkbox is toggled."""
        # Immediately save settings to persist the change
        self.save_settings_to_file()
        messagebox.showinfo("Tab Visibility Changed", "Tab visibility settings saved. Please Quick Restart the application to apply changes.")
