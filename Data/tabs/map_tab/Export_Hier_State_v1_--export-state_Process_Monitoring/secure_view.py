#!/usr/bin/env python3
import os
import sys
import traceback
from datetime import datetime

# --- UNIFIED LOGGING BOOTSTRAP ---
from unified_logger import get_logger, setup_exception_handler, log_startup, get_current_log_file, initialize_session

# Initialize session-wide log file first
initialize_session("secure_view")

# Initialize logger for GUI
logging = get_logger("gui", console_output=True)

# Setup global exception handler with popups enabled
setup_exception_handler(logging, enable_popup=True)

# Log startup
log_startup(logging, "Secure View GUI", "1.0")

# Get directories for backwards compatibility
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.join(SCRIPT_DIR, "logs")

# Standard Imports
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import json
import subprocess
import threading
import time
import re
import psutil
import hashlib
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path

# Project Imports
try:
    from shared_gui import SharedPopupGUI
    from process_organizer import CM, scanner_main, C as ScannerC, get_category
    import pyview
    from hierarchy_analyzer import HierarchyAnalyzer
    from process_brain_viz import ProcessBrainVisualization
except Exception as e:
    logging.critical(f"Module Import Error: {e}")
    raise

class SecureViewApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Secure View")
        
        # 0. Core Tools
        self.analyzer = HierarchyAnalyzer(logger=logging)
        self.current_snapshot = None
        self.self_process = psutil.Process(os.getpid())
        self.performance_bugs = []
        self.behavior_map = {} # {file_path: {pid, last_event}}
        self.intent_log = [] # List of {intent_id, source, action, status}
        self.last_intent = None
        
        # 1. State & Config
        self.prefs = CM.config.get('user_prefs', {})
        i_cfg = self.prefs.get('inspection_config', {})
        self.root.geometry(self.prefs.get('window_geometry', "1280x800"))
        
        self.hover_enabled = i_cfg.get('enable_hover', True)
        self.hover_delay = int(i_cfg.get('hover_delay', 500))
        self.indicator_pos = i_cfg.get('indicator_pos', 'right')
        self.sticky_selection = i_cfg.get('sticky_bind_selection', True)
        self.hover_job = None

        # 2. Colors & Tagging
        self.colors = {
            "bg": "#1e1e1e", "fg": "#d4d4d4", "sidebar": "#252526", "accent": "#007acc",
            "keyword": "#569cd6", "string": "#ce9178", "comment": "#6a9955", "function": "#dcdcaa",
            "variable": "#9cdcfe", "import": "#c586c0", "text_bg": "#2d2d2d", "error": "#f44336"
        }
        self.hier_colors = self.prefs.get('hier_colors', {})
        
        self.current_dir = SCRIPT_DIR
        self.current_file = None
        self.focused_pid = None
        self.refresh_ms = tk.IntVar(value=self.prefs.get('refresh_rate', 2000))
        
        # Load startup state from config
        pm_cfg = self.prefs.get('process_monitor', {})
        start_frozen = pm_cfg.get('start_frozen', True)
        self.proc_active = tk.BooleanVar(value=not start_frozen)
        
        self.active_group = set() # Track PIDs in current focus cluster
        self.tracked_processes = set() # Manually tracked PIDs for persistent monitoring
        self.search_filter = None # Active search filter for process names
        self.manifest_path = os.path.join(self.current_dir, "manifest.json")
        
        # Dimension & Positioning Manifest (Loaded from config)
        self.ui_dim = self.prefs.get("ui_dim", {
            "left_panel": 250,
            "right_panel": 320,
            "menu_est_width": 140,
            "menu_est_height": 150,
            "standard_offset": 10,
            "sticky_gap": 5
        })
        logging.info(f"UI Dimensions initialized. Indicator Pos: {self.indicator_pos}")
        
        # 3. UI Components
        self.setup_styles()
        self.setup_menu()
        self.setup_layout()
        
        # 4. Tooltip / Hover Setup
        self.tooltip = tk.Toplevel(self.root)
        self.tooltip.withdraw()
        self.tooltip.overrideredirect(True)
        self.tip_label = tk.Label(self.tooltip, bg="#333333", fg="white", relief="solid", borderwidth=1, font=("Arial", 9))
        self.tip_label.pack()

        # 5. Initialization
        self.apply_theme(self.prefs.get('theme', 'dark'))
        self.load_manifest()
        self.refresh_file_tree()
        self.refresh_log_list()
        self.tail_latest_log()
        self.run_performance_check()
        self.run_security_pulse()
        
        # Initial full sync of all components (Monitor, Brain, Hierarchy)
        self.refresh_hierarchy()
        
        # CLI Argument handling for automated export
        if "--export-state" in sys.argv:
            logging.info("CLI Trigger: --export-state detected. Generating report...")
            self.export_system_state(silent=True)
            self.root.after(1000, self.root.quit) # Exit after short delay to ensure save
        
        # Set frozen state indicator correctly if starting frozen
        if not self.proc_active.get():
            self.freeze_indicator.config(text=f"❄️ Frozen @ {datetime.now().strftime('%H:%M:%S')}", foreground="cyan")
            if hasattr(self, 'brain_viz'):
                self.brain_viz.frozen.set(True)
        
        # 6. Global Bindings
        self.root.bind("<Button-1>", self.on_global_click)
        self.root.bind("<Shift-Button-3>", self.inspect_ui_object)

    def setup_styles(self):
        style = ttk.Style()
        style.theme_use('clam')
        style.configure("Treeview", background=self.colors["sidebar"], foreground=self.colors["fg"], fieldbackground=self.colors["sidebar"])
        style.map("Treeview", background=[('selected', self.colors["accent"])])

    def setup_menu(self):
        menubar = tk.Menu(self.root)
        file_m = tk.Menu(menubar, tearoff=0)
        file_m.add_command(label="Open Directory", command=self.open_directory)
        file_m.add_command(label="Save File", command=self.save_current_file)
        file_m.add_separator()
        file_m.add_command(label="View Crash Logs", command=self.view_crash_logs)
        file_m.add_command(label="Exit", command=self.root.quit)
        menubar.add_cascade(label="File", menu=file_m)
        
        scan_m = tk.Menu(menubar, tearoff=0)
        scan_m.add_command(label="Quick Scan", command=lambda: self.run_security_scan(False))
        scan_m.add_command(label="Full Scan", command=lambda: self.run_security_scan(True))
        scan_m.add_command(label="View Integrity", command=self.check_integrity)
        menubar.add_cascade(label="Scans", menu=scan_m)
        
        menubar.add_command(label="Tools", command=lambda: SharedPopupGUI(self.root, "tools"))
        menubar.add_command(label="Config", command=lambda: SharedPopupGUI(self.root, "config"))
        self.root.config(menu=menubar)

    def setup_layout(self):
        # 1. Left Panel (Project & Activity) - #LEFT
        self.left_p = ttk.Frame(self.root, width=self.ui_dim["left_panel"])
        self.left_p.pack(side=tk.LEFT, fill=tk.Y)
        self.left_p.pack_propagate(False)
        
        # Manifest & Process Detail Summary (Relocated to LEFT)
        self.mf_f = ttk.LabelFrame(self.left_p, text="🛡️ Activity Context")
        self.mf_f.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.manifest_display = tk.Text(self.mf_f, height=12, font=('Monospace', 9), bg="#1e1e1e", fg="#ffffff")
        self.manifest_display.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)

        # Scan Kit Action Bar (At bottom of context)
        self.sk_f = ttk.Frame(self.mf_f)
        self.sk_f.pack(fill=tk.X, padx=2, pady=2, side=tk.BOTTOM)
        ttk.Button(self.sk_f, text="Route", width=6, command=self.route_process_to_source).pack(side=tk.LEFT, padx=1)
        ttk.Button(self.sk_f, text="Trace", width=6, command=self.deep_trace_process).pack(side=tk.LEFT, padx=1)
        ttk.Button(self.sk_f, text="Group", width=6, command=self.group_related_processes).pack(side=tk.LEFT, padx=1)
        ttk.Button(self.sk_f, text="Copy", width=6, command=self.copy_activity_context).pack(side=tk.LEFT, padx=1)
        ttk.Button(self.sk_f, text="Journal", width=7, command=self.view_daily_journal).pack(side=tk.LEFT, padx=1)
        ttk.Button(self.sk_f, text="Scan", width=6, command=lambda: self.run_security_scan(False)).pack(side=tk.RIGHT, padx=1)

        ttk.Label(self.left_p, text="📁 Project Tree", font=('Arial', 10, 'bold')).pack(pady=5)
        self.tree = ttk.Treeview(self.left_p, show="tree headings")
        self.tree.pack(fill=tk.BOTH, expand=True)
        self.tree.bind("<<TreeviewSelect>>", self.on_tree_select)
        
        # 2. Right Panel (Logs & Monitor) - #RIGHT
        self.right_p = ttk.Frame(self.root, width=self.ui_dim["right_panel"])
        self.right_p.pack(side=tk.RIGHT, fill=tk.Y)
        self.right_p.pack_propagate(False)

        # Right panel notebook with Log and Monitor tabs
        self.right_notebook = ttk.Notebook(self.right_p)
        self.right_notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Log Tab
        self.log_tab = ttk.Frame(self.right_notebook)
        self.right_notebook.add(self.log_tab, text="📡 Logs")

        sel_f = ttk.Frame(self.log_tab)
        sel_f.pack(fill=tk.X, padx=2, pady=2)
        self.log_selector = ttk.Combobox(sel_f, state="readonly")
        self.log_selector.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.log_selector.bind("<<ComboboxSelected>>", self.on_log_selected)
        ttk.Button(sel_f, text="⟳", width=3, command=self.refresh_log_list).pack(side=tk.LEFT)

        self.log_display = tk.Text(self.log_tab, height=15, font=('Monospace', 8), bg="black", fg="#00ff00")
        self.log_display.pack(fill=tk.BOTH, expand=True)

        # Monitor Tab - Process Hierarchy View
        self.monitor_tab = ttk.Frame(self.right_notebook)
        self.right_notebook.add(self.monitor_tab, text="📊 Monitor")

        # Monitor controls
        monitor_ctrl = ttk.Frame(self.monitor_tab)
        monitor_ctrl.pack(fill=tk.X, padx=2, pady=2)

        ttk.Button(monitor_ctrl, text="❄️ Freeze Time", command=self.freeze_system_snapshot).pack(side=tk.LEFT, padx=2)
        ttk.Button(monitor_ctrl, text="⟳ Refresh", command=self.refresh_hierarchy).pack(side=tk.LEFT, padx=2)
        self.freeze_indicator = ttk.Label(monitor_ctrl, text="", font=('Arial', 8))
        self.freeze_indicator.pack(side=tk.LEFT, padx=5)

        # Hierarchy TreeView
        self.hierarchy_tree = ttk.Treeview(
            self.monitor_tab,
            columns=("pid", "depth", "descendants", "dominance", "category"),
            show="tree headings"
        )
        self.hierarchy_tree.heading("#0", text="Process")
        self.hierarchy_tree.heading("pid", text="PID")
        self.hierarchy_tree.heading("depth", text="Depth")
        self.hierarchy_tree.heading("descendants", text="Children")
        self.hierarchy_tree.heading("dominance", text="Score")
        self.hierarchy_tree.heading("category", text="Category")

        self.hierarchy_tree.column("pid", width=60)
        self.hierarchy_tree.column("depth", width=50)
        self.hierarchy_tree.column("descendants", width=60)
        self.hierarchy_tree.column("dominance", width=60)
        self.hierarchy_tree.column("category", width=100)

        self.hierarchy_tree.pack(fill=tk.BOTH, expand=True)
        self.hierarchy_tree.bind("<Double-1>", self.on_hierarchy_double_click)
        self.hierarchy_tree.bind("<<TreeviewSelect>>", self.on_hierarchy_select)

        # Scrollbar for hierarchy
        hier_scroll = ttk.Scrollbar(self.monitor_tab, orient=tk.VERTICAL, command=self.hierarchy_tree.yview)
        self.hierarchy_tree.configure(yscrollcommand=hier_scroll.set)

        # Initialize hierarchy analyzer
        self.frozen_snapshot = None  # Stores frozen system state
        
        # 3. Center Notebook (Fills remainder)
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Hier-View Tab
        self.hier_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.hier_frame, text="Hier-View")
        self.hier_tree = ttk.Treeview(self.hier_frame, columns=("type", "line", "details"), show="tree headings")
        self.hier_tree.heading("#0", text="Element")
        self.hier_tree.heading("type", text="Type")
        self.hier_tree.heading("line", text="Line")
        self.hier_tree.pack(fill=tk.BOTH, expand=True)
        self.hier_tree.bind("<Double-1>", self.on_hier_double_click)
        self.hier_tree.bind("<Motion>", self.on_hier_hover)
        self.hier_tree.bind("<<TreeviewSelect>>", self.on_hier_select)

        # Editor Tab
        self.editor_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.editor_frame, text="Editor")
        ed_tools = ttk.Frame(self.editor_frame)
        ed_tools.pack(fill=tk.X)
        ttk.Button(ed_tools, text="🔍 Find", command=self.show_search_dialog).pack(side=tk.LEFT, padx=2)
        ttk.Button(ed_tools, text="🛡️ Inspect", command=self.inspect_current_file).pack(side=tk.LEFT, padx=2)
        ttk.Button(ed_tools, text="💾 Save", command=self.save_current_file).pack(side=tk.LEFT, padx=2)
        
        # Get editor config
        editor_cfg = self.prefs.get('editor', {})
        font_cfg = editor_cfg.get('font', {})
        behavior_cfg = editor_cfg.get('behavior', {})

        editor_font = (
            font_cfg.get('family', 'Monospace'),
            font_cfg.get('size', 11),
            font_cfg.get('weight', 'normal')
        )
        wrap_mode = tk.WORD if behavior_cfg.get('line_wrap', False) else tk.NONE

        ed_c = ttk.Frame(self.editor_frame)
        ed_c.pack(fill=tk.BOTH, expand=True)
        self.line_canvas = tk.Canvas(ed_c, width=40, bg="#252526", highlightthickness=0)
        self.line_canvas.pack(side=tk.LEFT, fill=tk.Y)
        self.editor = tk.Text(ed_c, bg="#2d2d2d", font=editor_font, wrap=wrap_mode, undo=True)
        self.editor.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.editor.bind("<KeyRelease>", self.on_editor_change)
        self.editor.bind("<MouseWheel>", self.on_editor_scroll)

        # Store editor config for later use
        self.editor_config = editor_cfg

        # Setup auto-save if enabled
        if behavior_cfg.get('auto_save', False):
            interval = behavior_cfg.get('auto_save_interval', 30) * 1000  # Convert to ms
            self.auto_save_timer = None
            self.setup_auto_save(interval)

        # CLI Output Tab
        self.cli_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.cli_frame, text="CLI Output")
        self.cli_text = tk.Text(self.cli_frame, bg="black", fg="white", font=('Monospace', 10))
        self.cli_text.pack(fill=tk.BOTH, expand=True)
        
        # Monitor Tab
        self.proc_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.proc_frame, text="Monitor")
        
        # Brain Map Tab (Integrated Visualization)
        self.brain_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.brain_frame, text="Brain Map")
        self.setup_brain_map_tab()

        # Bind tab change to sync right panel
        self.notebook.bind("<<NotebookTabChanged>>", self.on_center_tab_changed)

        # Controls Bar
        ctrl_f = ttk.Frame(self.proc_frame)
        ctrl_f.pack(fill=tk.X, padx=5, pady=2)
        
        self.proc_active_cb = ttk.Checkbutton(ctrl_f, text="Active Monitor", variable=self.proc_active, command=self.toggle_proc_monitor)
        self.proc_active_cb.pack(side=tk.LEFT, padx=5)
        
        ttk.Label(ctrl_f, text="Refresh (ms):").pack(side=tk.LEFT, padx=(10, 2))
        ttk.Entry(ctrl_f, textvariable=self.refresh_ms, width=6).pack(side=tk.LEFT, padx=2)

        res_level = CM.config['user_prefs'].get('brain_map', {}).get('resource_level', 50)
        self.res_indicator = ttk.Label(ctrl_f, text=f"Resource: {res_level}%", font=('Arial', 8, 'italic'))
        self.res_indicator.pack(side=tk.LEFT, padx=10)

        ttk.Separator(ctrl_f, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=10)
        
        self.target_label = ttk.Label(ctrl_f, text="No selection", font=('Arial', 9, 'bold'))
        self.target_label.pack(side=tk.LEFT, padx=10)
        
        self.kill_btn = ttk.Button(ctrl_f, text="KILL", state="disabled", command=self.kill_targeted_process)
        self.kill_btn.pack(side=tk.RIGHT, padx=2)
        self.suspend_btn = ttk.Button(ctrl_f, text="SUSP", state="disabled", command=self.suspend_targeted_process)
        self.suspend_btn.pack(side=tk.RIGHT, padx=2)
        
        ttk.Button(ctrl_f, text="Export Hierarchy", command=self.export_hierarchy_snapshot).pack(side=tk.RIGHT, padx=2)
        
        # Treeview with Functional Headings
        cols = ("pid", "dom", "group", "ghost", "cpu", "mem", "name", "cmd")
        self.proc_tree = ttk.Treeview(self.proc_frame, columns=cols, show="headings")

        for col in cols:
            self.proc_tree.heading(col, text=col.upper(), command=lambda c=col: self.sort_proc_tree(c))
            if col in ('pid', 'dom', 'cpu', 'mem'): width = 60
            elif col == 'ghost': width = 80
            elif col == 'group': width = 120
            elif col == 'name': width = 150
            else: width = 400
            self.proc_tree.column(col, width=width, anchor=tk.W)
            
        self.proc_tree.pack(fill=tk.BOTH, expand=True)
        self.proc_tree.bind("<<TreeviewSelect>>", self.on_proc_select)
        
        # Sort state
        self.proc_sort_col = "cpu"
        self.proc_sort_desc = True
        
        # Context Menus
        self.context_menu = tk.Menu(self.root, tearoff=0)
        for action in self.prefs.get('context_menu_actions', []):
            self.context_menu.add_command(
                label=action['label'],
                command=lambda a=action['action']: self.execute_menu_action(a)
            )

        # Dedicated context menu for process tree with Track/Search
        self.proc_context_menu = tk.Menu(self.root, tearoff=0)
        self.proc_context_menu.add_command(label="📌 Track Process", command=self.track_process)
        self.proc_context_menu.add_command(label="🔍 Search Process Name", command=self.search_process)
        self.proc_context_menu.add_separator()
        self.proc_context_menu.add_command(label="📤 Export Snapshot", command=self.export_full_process_snapshot)
        self.proc_context_menu.add_separator()
        self.proc_context_menu.add_command(label="🗑️ Clear Tracked", command=self.clear_tracked_processes)
        self.proc_context_menu.add_command(label="↩️ Clear Search", command=self.clear_search_filter)

        self.tree.bind("<Button-3>", self.show_context_menu)
        self.proc_tree.bind("<Button-3>", self.show_proc_context_menu)
        self.hier_tree.bind("<Button-3>", self.show_context_menu)

    def execute_menu_action(self, action_name):
        """Safely execute a method by name from the context menu."""
        if hasattr(self, action_name):
            func = getattr(self, action_name)
            func()
        else:
            logging.error(f"Context menu action '{action_name}' not found.")

    def cancel_hover(self):
        """Authoritatively cancel any pending hover tasks and hide non-sticky tooltips."""
        if hasattr(self, 'hover_job') and self.hover_job:
            try:
                self.root.after_cancel(self.hover_job)
            except: pass
            self.hover_job = None
        
        # Only withdraw if we aren't currently 'locked' in a sticky focus
        if not getattr(self, 'tooltip_focused', False):
            self.tooltip.withdraw()

    def on_hier_select(self, event):
        """Handle sticky binding to selection with hover preemption."""
        if not self.sticky_selection: return
        
        # PREEMPTION: Kill any hover tasks scheduled just before this click
        self.cancel_hover()

        sel = self.hier_tree.selection()
        if not sel: return
        
        item_id = sel[0]
        bbox = self.hier_tree.bbox(item_id)
        if bbox:
            # rootx + bbox[0] is the start of the item area.
            # We anchor to the mouse pointer's Y but the item's X for 'binding' feel.
            x = self.hier_tree.winfo_rootx() + bbox[0] + (bbox[2] // 2)
            y = self.hier_tree.winfo_rooty() + bbox[1]
            self.show_hier_tooltip(item_id, x, y, sticky=True, use_menu_offset=False)

    # --- Hover Logic (Hier Tab Only) ---
    def on_hier_hover(self, event):
        """Show relationship chain only on Hier-View nodes with a state-check mutex."""
        if not self.hover_enabled: return
        
        # MUTEX: If tooltip is locked by a click/selection, ignore mouse movement
        if getattr(self, 'tooltip_focused', False):
            return

        if self.hover_job:
            self.root.after_cancel(self.hover_job)
        
        item = self.hier_tree.identify_row(event.y)
        if item:
            self.hover_job = self.root.after(self.hover_delay, lambda: self.show_hier_tooltip(item, event.x_root, event.y_root))
        else:
            self.tooltip.withdraw()

    def get_hier_lineage(self, item_id):
        """Trace the parent path of a node in the hierarchical tree."""
        path = []
        curr = item_id
        while curr:
            text = self.hier_tree.item(curr, 'text')
            if text:
                path.insert(0, text)
            curr = self.hier_tree.parent(curr)
        return " > ".join(path)

    def show_hier_tooltip(self, item, x, y, sticky=False, use_menu_offset=False):
        vals = self.hier_tree.item(item, "values")
        text = self.hier_tree.item(item, "text")
        lineage = self.get_hier_lineage(item)
        
        kind = vals[0] if vals else 'Node'
        line = vals[1] if len(vals)>1 else 'N/A'
        chain = f"Lineage: {lineage}\nElement: {text}\nType: {kind}\nLine: {line}"
        if len(vals) > 2 and vals[2]:
            chain += f"\nDetails: {vals[2]}"
            
        self.tip_label.config(text=chain, justify=tk.LEFT, padx=10, pady=5)
        self.tooltip.deiconify()
        self.tooltip.update_idletasks()
        
        tw, th = self.tooltip.winfo_width(), self.tooltip.winfo_height()
        pos = self.indicator_pos.lower()
        
        # Calculate Coordinates based on Orientation
        if pos == "right":
            nx = x + (self.ui_dim["menu_est_width"] if use_menu_offset else self.ui_dim["standard_offset"]) + self.ui_dim["sticky_gap"]
            ny = y
        elif pos == "left":
            nx = x - tw - (self.ui_dim["standard_offset"] if not use_menu_offset else 20)
            ny = y
        elif pos == "top":
            nx = x - (tw / 2)
            ny = y - th - self.ui_dim["sticky_gap"]
        elif pos == "bottom":
            nx = x - (tw / 2)
            # Clear menu height if right-clicked
            v_gap = self.ui_dim["menu_est_height"] if use_menu_offset else 30
            ny = y + v_gap + self.ui_dim["sticky_gap"]
        else:
            nx, ny = x + 20, y
            
        self.tooltip.geometry(f"+{int(nx)}+{int(ny)}")
        
        if sticky:
            self.tooltip_focused = True
            self.tip_label.config(bg="#444444", borderwidth=2)
        else:
            self.tooltip_focused = False
            self.tip_label.config(bg="#333333", borderwidth=1)

    # --- Inspector Logic ---
    def open_inspector_popup(self):
        w = getattr(self.context_menu, 'widget', None)
        if not w: return
        sel = w.selection()
        if not sel: return
        
        item_id = sel[0]
        item = w.item(item_id)
        
        # Show sticky tooltip next to context menu location
        x = getattr(self, 'last_menu_x', self.root.winfo_pointerx())
        y = getattr(self, 'last_menu_y', self.root.winfo_pointery())
        
        if w == self.hier_tree:
            self.show_hier_tooltip(item_id, x, y, sticky=True)
        else:
            lineage = ""
            if w == self.tree:
                # Simple file tree lineage
                parts = []
                curr = item_id
                while curr:
                    parts.insert(0, w.item(curr, 'text'))
                    curr = w.parent(curr)
                lineage = " / ".join(parts)
            
            msg = f"Lineage: {lineage}\n" if lineage else ""
            msg += f"Technical context for: {item['text']}\n"
            if w == self.tree:
                msg += f"File Path: {item['values'][0]}"
            elif w == self.proc_tree:
                msg += f"PID: {item['values'][0]}\nCommand: {item['values'][4]}"
            messagebox.showinfo("Security Inspector", msg)

    def export_entity_context(self):
        """Export current entity context to clipboard and a markdown file."""
        w = getattr(self.context_menu, 'widget', None)
        if not w: return
        sel = w.selection()
        if not sel: return
        
        item_id = sel[0]
        item = w.item(item_id)
        text = item['text']
        vals = item['values']
        
        ctx = f"# Entity Report: {text}\n\n"
        ctx += f"- **Source Widget**: {w.winfo_name()}\n"
        ctx += f"- **Timestamp**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        
        if w == self.hier_tree:
            ctx += f"- **Lineage**: {self.get_hier_lineage(item_id)}\n"
        
        ctx += "\n"
        
        if w == self.tree:
            ctx += f"## File Information\n- **Path**: {vals[0]}\n"
        elif w == self.proc_tree:
            # Indices: 0:pid, 1:group, 2:cpu, 3:mem, 4:name, 5:cmd
            ctx += f"## Process Information\n"
            ctx += f"- **PID**:      {vals[0]}\n"
            ctx += f"- **Group**:    {vals[1]}\n"
            ctx += f"- **CPU**:      {vals[2]}%\n"
            ctx += f"- **Memory**:   {vals[3]}%\n"
            ctx += f"- **Name**:     {vals[4]}\n"
            ctx += f"- **Command**:  {vals[5]}\n\n"
            
            # Include the detailed context currently in the display panel
            display_ctx = self.manifest_display.get(1.0, tk.END).strip()
            if "Process Context" in display_ctx:
                ctx += f"## Technical Context\n```\n{display_ctx}\n```\n"
            
            # Extended: Match running processes (if still alive)
            matching_procs = []
            try:
                import psutil
                search_term = vals[4].lower() # use name col
                for p in psutil.process_iter(['pid', 'name', 'cmdline']):
                    try:
                        cmd = " ".join(p.info['cmdline'] or [])
                        if search_term in p.info['name'].lower() or search_term in cmd.lower():
                            matching_procs.append(f"- PID: {p.info['pid']} | Name: {p.info['name']} | Command: {cmd[:100]}...")
                    except: pass
            except: pass

            if matching_procs:
                ctx += "## Cluster Relatives (Live)\n"
                ctx += "\n".join(matching_procs) + "\n\n"
            
        elif w == self.hier_tree:
            ctx += f"## Code Element\n- **Type**: {vals[0]}\n- **Line**: {vals[1]}\n"
            if len(vals) > 2: ctx += f"- **Details**: {vals[2]}\n"
            
        # Add to clipboard
        self.root.clipboard_clear()
        self.root.clipboard_append(ctx)
        
        # Save to file
        filename = f"Entity_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
        try:
            with open(filename, 'w') as f:
                f.write(ctx)
            messagebox.showinfo("Export Success", f"Context captured to clipboard and saved to {filename}")
        except Exception as e:
            messagebox.showerror("Export Error", f"Failed to save file: {e}")

    def inspect_ui_object(self, event):
        w = self.root.winfo_containing(event.x_root, event.y_root)
        if w:
            info = f"Widget: {w.winfo_name()}\nClass: {w.winfo_class()}\nParent: {w.winfo_parent()}"
            messagebox.showinfo("UI Object Context", info)

    def show_context_menu(self, event):
        # Prevent hover overlap during menu activation
        self.cancel_hover()

        item = event.widget.identify_row(event.y)
        if item:
            event.widget.selection_set(item)
            self.context_menu.widget = event.widget
            self.last_menu_x = event.x_root
            self.last_menu_y = event.y_root
            self.context_menu.post(event.x_root, event.y_root)
            
            # Show sticky tooltip dynamically next to the menu
            if event.widget == self.hier_tree:
                self.show_hier_tooltip(item, event.x_root, event.y_root, sticky=True, use_menu_offset=True)

    def on_global_click(self, event):
        self.context_menu.unpost()
        self.proc_context_menu.unpost()
        # Hide tooltip if user clicks away from a sticky one
        if hasattr(self, 'tooltip_focused') and self.tooltip_focused:
            tw = self.tooltip.winfo_width()
            th = self.tooltip.winfo_height()
            tx = self.tooltip.winfo_rootx()
            ty = self.tooltip.winfo_rooty()
            if not (tx <= event.x_root <= tx+tw and ty <= event.y_root <= ty+th):
                self.tooltip.withdraw()
                self.tooltip_focused = False

    def show_proc_context_menu(self, event):
        """Show dedicated context menu for process tree with Track/Search options."""
        self.cancel_hover()

        item = event.widget.identify_row(event.y)
        if item:
            event.widget.selection_set(item)
            self.proc_context_menu.widget = event.widget
            self.last_menu_x = event.x_root
            self.last_menu_y = event.y_root

            # Get PID from selected item to update menu labels
            values = event.widget.item(item, 'values')
            if values:
                pid = int(values[0])
                # Update track menu label based on whether already tracked
                if pid in self.tracked_processes:
                    self.proc_context_menu.entryconfig(0, label="📌 Untrack Process")
                else:
                    self.proc_context_menu.entryconfig(0, label="📌 Track Process")

            self.proc_context_menu.post(event.x_root, event.y_root)

    def track_process(self):
        """Toggle tracking for selected process - adds persistent visual marker."""
        w = getattr(self.proc_context_menu, 'widget', None)
        if not w:
            return

        sel = w.selection()
        if not sel:
            return

        item_id = sel[0]
        values = w.item(item_id, 'values')
        if not values:
            return

        pid = int(values[0])
        name = values[6] if len(values) > 6 else "Unknown"

        # Toggle tracking
        if pid in self.tracked_processes:
            self.tracked_processes.remove(pid)
            messagebox.showinfo("Untracked", f"Process {pid} ({name}) removed from tracking list.")
        else:
            self.tracked_processes.add(pid)
            messagebox.showinfo("Tracked", f"Process {pid} ({name}) added to tracking list.\nTracked processes are highlighted with ★ marker.")

        # Refresh display to show tracking indicator
        self.update_proc_list()

    def search_process(self):
        """Search and filter process tree by name/command."""
        w = getattr(self.proc_context_menu, 'widget', None)
        if not w:
            return

        sel = w.selection()
        if not sel:
            return

        item_id = sel[0]
        values = w.item(item_id, 'values')
        if not values:
            return

        name = values[6] if len(values) > 6 else ""

        # Show search dialog with pre-filled name
        from tkinter import simpledialog
        search_term = simpledialog.askstring(
            "Search Processes",
            "Enter process name or command to filter:",
            initialvalue=name
        )

        if search_term:
            self.search_filter = search_term.lower()
            self.update_proc_list()
            messagebox.showinfo("Search Active", f"Filtering processes matching: '{search_term}'\nUse 'Clear Search' to show all processes.")

    def clear_tracked_processes(self):
        """Remove all tracked processes."""
        if not self.tracked_processes:
            messagebox.showinfo("No Tracked Processes", "No processes are currently being tracked.")
            return

        count = len(self.tracked_processes)
        self.tracked_processes.clear()
        self.update_proc_list()
        messagebox.showinfo("Tracking Cleared", f"Removed {count} processes from tracking list.")

    def clear_search_filter(self):
        """Clear active search filter and show all processes."""
        if not self.search_filter:
            messagebox.showinfo("No Active Filter", "No search filter is currently active.")
            return

        self.search_filter = None
        self.update_proc_list()
        messagebox.showinfo("Filter Cleared", "Showing all processes.")

    # --- Feature Methods ---
    def route_to_editor(self):
        w = getattr(self.context_menu, 'widget', self.tree)
        sel = w.selection()
        if not sel: return
        p = None
        if w == self.tree:
            p = w.item(sel[0], "values")[0]
        elif w == self.proc_tree:
            pid = w.item(sel[0], "values")[0]
            try:
                import psutil
                proc = psutil.Process(int(pid))
                for a in proc.cmdline():
                    if a.endswith('.py') and os.path.exists(a):
                        p = os.path.abspath(a); break
            except: pass
        if p and os.path.isfile(p):
            self.load_file_to_editor(p)

    def route_to_hier(self):
        self.route_to_editor()
        self.notebook.select(self.hier_frame)

    def visualize_code(self, path):
        try:
            pf = pyview.analyze_file(Path(path))
            for i in self.hier_tree.get_children():
                self.hier_tree.delete(i)
            
            # Root file node
            root_details = f"Lines: {pf.lines} | Error: {pf.error if pf.error else 'None'}"
            root = self.hier_tree.insert("", "end", text=pf.path.name, values=("FILE", "0", root_details), open=True, tags=("File",))
            
            if pf.imports:
                n = self.hier_tree.insert(root, "end", text="Imports", values=("FOLDER", "", f"Count: {len(pf.imports)}"), open=True)
                for im in pf.imports:
                    details = f"As: {im.value}" if im.value else ""
                    self.hier_tree.insert(n, "end", text=im.name, values=("Import", im.line, details), tags=("Import",))
            
            if pf.elements:
                n = self.hier_tree.insert(root, "end", text="Structure", values=("FOLDER", "", f"Count: {len(pf.elements)}"), open=True)
                for el in pf.elements:
                    tag = el.kind.title()
                    details = f"Range: {el.line}-{el.end_line}" if el.end_line else ""
                    p = self.hier_tree.insert(n, "end", text=el.name, values=(el.kind.upper(), el.line, details), tags=(tag,))
                    for ch in el.children:
                        cdetails = f"Range: {ch.line}-{ch.end_line}" if ch.end_line else ""
                        self.hier_tree.insert(p, "end", text=ch.name, values=("METHOD", ch.line, cdetails), tags=("Method",))
            
            if hasattr(pf, 'strings') and pf.strings:
                sn = self.hier_tree.insert(root, "end", text="Suspicious Strings", values=("FOLDER", "", f"Count: {len(pf.strings)}"), open=False)
                for s in pf.strings:
                    self.hier_tree.insert(sn, "end", text=s.name[:50], values=("STRING", s.line, s.name), tags=("String/IP",))

            for t, c in self.hier_colors.items():
                self.hier_tree.tag_configure(t, foreground=c)
        except Exception as e:
            logging.error(f"Hier Error: {e}")

    def on_hier_double_click(self, event):
        sel = self.hier_tree.selection()
        if sel:
            v = self.hier_tree.item(sel[0], "values")
            if len(v) > 1 and v[1]:
                self.notebook.select(self.editor_frame)
                self.editor.mark_set("insert", f"{v[1]}.0")
                self.editor.see(f"{v[1]}.0")
                self.editor.focus_set()

    def on_editor_change(self, e=None):
        self.update_line_numbers()
        self.apply_syntax_highlighting()

    def on_editor_scroll(self, e=None):
        self.update_line_numbers()

    def update_line_numbers(self):
        self.line_canvas.delete("all")
        i = self.editor.index("@0,0")
        while True:
            d = self.editor.dlineinfo(i)
            if not d: break
            self.line_canvas.create_text(35, d[1], anchor="ne", text=str(i).split(".")[0], fill="#858585")
            i = self.editor.index("%s + 1line" % i)

    def apply_syntax_highlighting(self):
        for t in ["keyword", "string", "comment", "function"]:
            self.editor.tag_configure(t, foreground=self.colors.get(t, "#ffffff"))
            self.editor.tag_remove(t, "1.0", tk.END)
        c = self.editor.get("1.0", tk.END)
        pats = [
            (r'\b(def|class|if|else|import|from|return|for|while|try|except|with|as)\b', "keyword"),
            (r'".*?"|".*?"', "string"), (r'#.*', "comment"), (r'\b[a-zA-Z_]\w*(?=\()', "function")
        ]
        for p, t in pats:
            for m in re.finditer(p, c):
                self.editor.tag_add(t, f"1.0 + {m.start()} chars", f"1.0 + {m.end()} chars")

    def apply_theme(self, theme_name):
        themes = {
            "dark": { "bg": "#1e1e1e", "fg": "#d4d4d4", "sidebar": "#252526", "accent": "#007acc", "text_bg": "#2d2d2d" },
            "light": { "bg": "#ffffff", "fg": "#000000", "sidebar": "#f3f3f3", "accent": "#007acc", "text_bg": "#ffffff" },
            "monokai": { "bg": "#272822", "fg": "#f8f8f2", "sidebar": "#1e1f1c", "accent": "#ae81ff", "text_bg": "#272822" }
        }
        cfg = themes.get(theme_name, themes["dark"])
        self.colors.update(cfg)
        self.root.configure(bg=cfg["bg"])
        for txt in [self.editor, self.log_display, self.hier_text if hasattr(self, 'hier_text') else None]:
            if txt: txt.configure(bg=cfg["text_bg"], fg=cfg["fg"], insertbackground=cfg["fg"])
        style = ttk.Style()
        style.configure("Treeview", background=cfg["sidebar"], foreground=cfg["fg"], fieldbackground=cfg["sidebar"])
        CM.config['user_prefs']['theme'] = theme_name
        CM.save_config()

    def load_file_to_editor(self, p):
        try:
            with open(p, 'r', errors='ignore') as f:
                self.editor.delete(1.0, tk.END)
                self.editor.insert(tk.END, f.read())
            self.current_file = p
            self.on_editor_change()
            self.notebook.select(self.editor_frame)
            if p.endswith('.py'): self.visualize_code(p)
        except Exception as e:
            messagebox.showerror("Load Error", str(e))

    def on_tree_select(self, e):
        try:
            p = self.tree.item(self.tree.selection()[0], "values")[0]
            if os.path.isfile(p):
                self.load_file_to_editor(p)
                if p.endswith('.log'):
                    fn = os.path.basename(p)
                    if fn in self.log_selector['values']:
                        self.log_selector.set(fn); self.on_log_selected(None)
        except: pass

    def save_current_file(self):
        if self.current_file:
            with open(self.current_file, 'w') as f:
                f.write(self.editor.get(1.0, tk.END))
            messagebox.showinfo("Saved", "File updated.")
            self.refresh_file_tree()

    def setup_auto_save(self, interval_ms):
        """Setup periodic auto-save for editor."""
        def auto_save():
            if self.current_file and self.editor.edit_modified():
                try:
                    with open(self.current_file, 'w') as f:
                        f.write(self.editor.get(1.0, tk.END))
                    logging.info(f"Auto-saved: {self.current_file}")
                    self.editor.edit_modified(False)
                except Exception as e:
                    logging.error(f"Auto-save failed: {e}")

            # Schedule next auto-save
            self.auto_save_timer = self.root.after(interval_ms, auto_save)

        # Start the auto-save loop
        self.auto_save_timer = self.root.after(interval_ms, auto_save)

    def copy_activity_context(self):
        """Copy the current contents of the Activity Context panel to the clipboard."""
        content = self.manifest_display.get(1.0, tk.END).strip()
        if content:
            self.root.clipboard_clear()
            self.root.clipboard_append(content)
            logging.info("Activity Context copied to clipboard.")
        else:
            messagebox.showwarning("Copy", "No content to copy.")

    def log_communication_event(self, pid, name, details):
        """Append a communication event to the daily log."""
        today = datetime.now().strftime("%Y%m%d")
        comm_log = os.path.join(LOG_DIR, f"comm_{today}.log")
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        # Format: [TIME] [PID] NAME | DETAILS
        entry = f"[{timestamp}] [{pid}] {name} | {details}\n"
        
        try:
            with open(comm_log, 'a') as f:
                f.write(entry)
        except Exception as e:
            logging.error(f"Failed to write to comm log: {e}")

    def on_log_selected(self, e):
        """Display the content of the selected log file."""
        p = os.path.join(LOG_DIR, self.log_selector.get())
        if os.path.exists(p):
            with open(p, 'r') as f:
                self.log_display.delete(1.0, tk.END)
                self.log_display.insert(tk.END, f.read())
                self.log_display.see(tk.END)

    def refresh_log_list(self):
        """Update log selector with all logs, prioritizing gui and comm logs."""
        ls = sorted([f for f in os.listdir(LOG_DIR) if f.endswith('.log')], reverse=True)
        # Move comm logs to the top if they are for today
        today_str = f"comm_{datetime.now().strftime('%Y%m%d')}"
        ls = sorted(ls, key=lambda x: (not x.startswith(today_str), not x.startswith('gui_'), x), reverse=False)
        
        self.log_selector['values'] = ls
        if ls:
            self.log_selector.set(ls[0])

    def tail_latest_log(self):
        if self.log_selector.get() and self.log_selector.current() == 0:
            self.on_log_selected(None)
        self.root.after(5000, self.tail_latest_log)

    def run_performance_check(self):
        """Monitor self-performance against configuration expectations."""
        try:
            # 1. Check FPS
            if hasattr(self, 'brain_viz') and hasattr(self.brain_viz, 'debugger') and self.brain_viz.debugger:
                bm_cfg = self.prefs.get('brain_map', {})
                target_fps = bm_cfg.get('fps_target', 30)
                self.brain_viz.debugger.set_fps_expectation(target_fps)
                
                findings = self.brain_viz.debugger.verify_expectations()
                for bug in findings:
                    self.performance_bugs.append(bug)

            # 2. Check Self CPU
            cpu_usage = self.self_process.cpu_percent()
            # If CPU > 20% and we aren't even doing deep scans, mark a bug
            res_level = self.prefs.get('brain_map', {}).get('resource_level', 50)
            if cpu_usage > 30 and res_level < 50:
                self.performance_bugs.append({
                    'type': 'CPU_INEFFICIENCY',
                    'detail': f'App using {cpu_usage:.1f}% CPU at low resource level ({res_level}%)',
                    'timestamp': datetime.now().strftime("%H:%M:%S")
                })

            # 3. Limit bug history
            if len(self.performance_bugs) > 10:
                self.performance_bugs = self.performance_bugs[-10:]

            # 4. Trigger manifest refresh if bugs found
            if findings or cpu_usage > 30:
                self.run_conflict_resolution()
                self.load_manifest()
                self.update_hier_performance_alerts()

        except Exception as e:
            logging.error(f"Performance Check Error: {e}")
        
        # Schedule next check (every 5 seconds)
        self.root.after(5000, self.run_performance_check)
        self.resolve_behavioral_ghosts()

    def resolve_behavioral_ghosts(self):
        """Parse unified logs to map external behavioral data back to the process list."""
        log_file = get_current_log_file()
        if not log_file or not os.path.exists(log_file) or not self.current_snapshot:
            return

        try:
            with open(log_file, 'r') as f:
                # Read last 50 lines for real-time resolution
                lines = f.readlines()[-50:]
                
            for line in lines:
                # Example parser for targeted directory output tracking
                # Matches patterns like: [Module] ... file: /path/to/output.log
                match = re.search(r'file:\s*([^\s,]+)', line)
                if match:
                    target_file = match.group(1)
                    # Trace back: Which PID has this file open?
                    for pid, node in self.current_snapshot.all_nodes.items():
                        if any(target_file in p for p in node.open_file_paths):
                            self.behavior_map[target_file] = {
                                'pid': pid,
                                'name': node.name,
                                'last_event': line.strip()
                            }
                            logging.debug(f"Resolved Behavioral Ghost: {node.name}({pid}) -> {target_file}")

        except Exception as e:
            logging.error(f"Ghost Resolution Error: {e}")

    def record_intent(self, source, action, expectation=None):
        """Record a system or user intent for later correlation."""
        intent = {
            'id': f"INT_{datetime.now().strftime('%H%M%S')}",
            'source': source,
            'action': action,
            'expectation': expectation,
            'timestamp': datetime.now().strftime("%H:%M:%S"),
            'status': 'PENDING'
        }
        self.intent_log.append(intent)
        self.last_intent = intent
        logging.info(f"Intent Recorded: {intent['id']} | {source}: {action}")
        if len(self.intent_log) > 20: self.intent_log.pop(0)
        return intent['id']

    def run_conflict_resolution(self):
        """Self-matching bugs to their intent and resolving if possible."""
        if not self.performance_bugs or not self.last_intent:
            return

        latest_bug = self.performance_bugs[-1]
        
        # If bug happened within 10 seconds of an intent, correlate them
        if self.last_intent['status'] == 'PENDING':
            # Resolve Conflict: If user increased level but FPS dropped, mark as 'Observed'
            if latest_bug['type'] == 'FPS_MISMATCH' and self.last_intent['action'] == 'resource_change':
                self.last_intent['status'] = 'RESOLVED_UNDERPERFORMANCE'
                logging.info(f"#[ResolvedConflict:{{{self.last_intent['id']}}}] -> Intent caused performance breach.")
                
                # Socratic: Should we auto-lower the slider? 
                # For now, we just tag it in the manifest.
                latest_bug['detail'] = f"Correlated to {self.last_intent['id']}"

    def run_security_pulse(self):
        """Periodically log a high-frequency hash pulse of the session state."""
        try:
            # Hash core state
            state_str = f"{len(self.performance_bugs)}{len(self.intent_log)}{self.proc_active.get()}"
            pulse_hash = hashlib.sha256(state_str.encode()).hexdigest()[:8]
            
            logging.info(f"🛡️  SECURITY_PULSE: {pulse_hash} (Bugs:{len(self.performance_bugs)}, Intents:{len(self.intent_log)})")
            
            # Hook back to Hierarchy for 'Pulse' visualization later
            if self.current_snapshot:
                self.manifest_display.insert(tk.END, f"Security Pulse: {pulse_hash} @ {datetime.now().strftime('%H:%M:%S')}\n", "pulse")
                self.manifest_display.tag_configure("pulse", foreground="#6bcb77", font=('Monospace', 8))

        except Exception as e:
            logging.error(f"Security Pulse Error: {e}")
        
        interval = CM.get('user_prefs.automata.security_pulse_interval_ms', 10000)
        self.root.after(interval, self.run_security_pulse)

    def update_hier_performance_alerts(self):
        """Inject performance alerts into the Hier-View tree."""
        if not self.performance_bugs:
            return
            
        # Look for the 'Performance' group or create it
        perf_node = None
        for item in self.hier_tree.get_children():
            if self.hier_tree.item(item, "text") == "⚠️ PERFORMANCE ALERTS":
                perf_node = item
                break
        
        if not perf_node:
            perf_node = self.hier_tree.insert("", 0, text="⚠️ PERFORMANCE ALERTS", values=("ALERT", "", "Real-time mismatches"), open=True, tags=("Alert",))
            self.hier_tree.tag_configure("Alert", foreground="#ff6b6b", font=('Arial', 9, 'bold'))

        # Add recent bugs
        existing = [self.hier_tree.item(c, "text") for c in self.hier_tree.get_children(perf_node)]
        for bug in self.performance_bugs[-3:]:
            bug_text = f"[{bug['timestamp']}] {bug['type']}"
            if bug_text not in existing:
                detail = bug.get('detail', f"Exp: {bug.get('expected')}, Act: {bug.get('actual')}")
                self.hier_tree.insert(perf_node, "end", text=bug_text, values=("BUG", bug['timestamp'], detail))

    def freeze_system_snapshot(self):
        """Capture and freeze current system state with full hierarchy."""
        try:
            # Check if we're unfreezing
            if self.frozen_snapshot is not None:
                self.unfreeze_system()
                return

            self.freeze_indicator.config(text="⏳ Capturing...")
            self.root.update_idletasks()

            # Get resource level
            res_level = CM.config['user_prefs'].get('brain_map', {}).get('resource_level', 50)

            # Capture snapshot
            self.frozen_snapshot = self.analyzer.capture_snapshot(resource_level=res_level)

            # Update the hierarchy tree
            self.refresh_hierarchy()

            # Update indicator
            timestamp = self.frozen_snapshot.timestamp
            self.freeze_indicator.config(
                text=f"❄️ Frozen @ {timestamp}",
                foreground="cyan"
            )

            # Sync all freeze states
            self._sync_freeze_states(frozen=True)

            # Update the center monitor list with frozen data
            self.update_proc_list()

            logging.info(f"System snapshot frozen at {timestamp}: {self.frozen_snapshot.total_processes} processes")

        except Exception as e:
            logging.error(f"Failed to freeze snapshot: {e}", exc_info=True)
            self.freeze_indicator.config(text="❌ Freeze Failed", foreground="red")

    def unfreeze_system(self):
        """Unfreeze system and resume live monitoring."""
        try:
            self.frozen_snapshot = None
            self.freeze_indicator.config(text="🔴 Live", foreground="lime")

            # Refresh hierarchy with live data
            self.refresh_hierarchy()

            # Sync all freeze states
            self._sync_freeze_states(frozen=False)

            # Resume live monitoring loop
            self.update_proc_list()

            logging.info("System unfrozen, resuming live monitoring")

        except Exception as e:
            logging.error(f"Failed to unfreeze: {e}", exc_info=True)

    def _sync_freeze_states(self, frozen):
        """Synchronize all freeze states across Monitor, Activity toggle, and Brain Map."""
        # Sync Activity Monitor toggle
        self.proc_active.set(not frozen)
        if frozen:
            self.proc_active_cb.config(text="Monitor FROZEN")
        else:
            self.proc_active_cb.config(text="Active Monitor")

        # Sync Brain Map freeze state
        if hasattr(self, 'brain_viz') and hasattr(self.brain_viz, 'frozen'):
            self.brain_viz.frozen.set(frozen)

        # Update freeze button text
        if frozen:
            # Change button to show "Unfreeze" option
            for widget in self.monitor_tab.winfo_children():
                if isinstance(widget, ttk.Frame):
                    for btn in widget.winfo_children():
                        if isinstance(btn, ttk.Button) and "Freeze" in btn.cget("text"):
                            btn.config(text="🔥 Unfreeze")
        else:
            # Change back to "Freeze Time"
            for widget in self.monitor_tab.winfo_children():
                if isinstance(widget, ttk.Frame):
                    for btn in widget.winfo_children():
                        if isinstance(btn, ttk.Button) and "Unfreeze" in btn.cget("text"):
                            btn.config(text="❄️ Freeze Time")

    def refresh_hierarchy(self):
        """Refresh the hierarchy tree view, updating snapshots if frozen."""
        try:
            # Clear existing items
            for item in self.hierarchy_tree.get_children():
                self.hierarchy_tree.delete(item)

            # Coordinate with Resource Level
            bm_cfg = CM.get('user_prefs.brain_map', {})
            res_level = bm_cfg.get('resource_level', 50)
            self.record_intent("USER", "resource_change", expectation=f"Level:{res_level}%")
            
            # CPU Layer Controls: Analysis Depth and Complexity based on Level
            # 1-30: Minimal (Depth 2, no code analysis)
            # 31-70: Standard (Depth 5, basic code analysis)
            # 71-100: Deep (Full Depth, full code analysis)
            
            max_depth = 2 if res_level < 30 else (5 if res_level < 70 else 10)
            
            # If frozen, update the snapshot to 'refresh' the frozen state
            if self.frozen_snapshot is not None:
                self.frozen_snapshot = self.analyzer.capture_snapshot(resource_level=res_level)
                snapshot = self.frozen_snapshot
                self.freeze_indicator.config(text=f"❄️ Frozen @ {snapshot.timestamp}", foreground="cyan")
            else:
                # Capture a fresh snapshot for the full refresh
                snapshot = self.analyzer.capture_snapshot(resource_level=res_level)
                self.freeze_indicator.config(text="🔴 Live", foreground="lime")

            # Update the global current_snapshot
            self.current_snapshot = snapshot

            # Populate tree with dominant processes (Limited by depth logic)
            for node in snapshot.dominant_processes[:20]:  # Top 20
                category, cat_color, priority = get_category(node)

                item_id = self.hierarchy_tree.insert(
                    "",
                    "end",
                    text=f"{node.name}",
                    values=(
                        node.pid,
                        node.depth,
                        node.descendant_count,
                        f"{node.dominance_score():.0f}",
                        category
                    )
                )

                # Add children if any
                if node.children_pids and node.descendant_count > 0:
                    for child_pid in node.children_pids[:5]:  # Show top 5 children
                        if child_pid in snapshot.all_nodes:
                            child = snapshot.all_nodes[child_pid]
                            child_category, child_color, child_priority = get_category(child)
                            self.hierarchy_tree.insert(
                                item_id,
                                "end",
                                text=f"  └─ {child.name}",
                                values=(
                                    child.pid,
                                    child.depth,
                                    child.descendant_count,
                                    f"{child.dominance_score():.0f}",
                                    child_category
                                )
                            )

            # Sync other views
            self.update_proc_list()
            if hasattr(self, "brain_viz"):
                self.brain_viz.refresh_process_data()

            # Auto-switch to Monitor tab when refreshing
            self.right_notebook.select(self.monitor_tab)

        except Exception as e:
            logging.error(f"Failed to refresh hierarchy: {e}", exc_info=True)

    def on_hierarchy_double_click(self, event):
        """Handle double-click on hierarchy tree item - focus in Brain Map."""
        try:
            selection = self.hierarchy_tree.selection()
            if not selection:
                return

            item = selection[0]
            values = self.hierarchy_tree.item(item, "values")
            if not values:
                return

            pid = int(values[0])

            # Focus this PID in the Brain Map
            self._focus_pid_in_brain_map(pid)

            # If we have a snapshot, show detailed info
            if self.current_snapshot and pid in self.current_snapshot.all_nodes:
                node = self.current_snapshot.all_nodes[pid]

                # Build detailed context
                details = []
                details.append(f"=== Process {pid}: {node.name} ===\n")
                details.append(f"PID: {pid}")
                details.append(f"Command: {' '.join(node.cmdline[:5])}")
                details.append(f"Depth: {node.depth}")
                details.append(f"Descendants: {node.descendant_count}")
                details.append(f"Dominance Score: {node.dominance_score():.0f}")
                details.append(f"CPU: {node.cpu_aggregate:.1f}%")
                details.append(f"Memory: {node.mem_aggregate:.1f}%")
                details.append(f"Threads: {node.threads}")
                details.append(f"Network Connections: {node.network_connections}")

                if node.source_file:
                    details.append(f"\nSource File: {node.source_file}")

                if node.imports:
                    details.append(f"\nImports ({len(node.imports)}):")
                    for imp in node.imports[:10]:
                        details.append(f"  • {imp}")

                if node.classes:
                    details.append(f"\nClasses ({len(node.classes)}):")
                    for cls in node.classes[:5]:
                        details.append(f"  • {cls}")

                if node.functions:
                    details.append(f"\nFunctions ({len(node.functions)}):")
                    for func in node.functions[:10]:
                        details.append(f"  • {func}")

                if node.connected_to:
                    details.append(f"\nConnected to PIDs: {list(node.connected_to)}")

                # Show in a popup
                detail_text = "\n".join(details)
                messagebox.showinfo(f"Process {pid} Details", detail_text)

                # Also route to editor if source file exists
                if node.source_file and os.path.exists(node.source_file):
                    self.load_file_to_editor(node.source_file)

        except Exception as e:
            logging.error(f"Failed to handle hierarchy double-click: {e}", exc_info=True)

    def on_hierarchy_select(self, event):
        """Handle selection in hierarchy tree - update brain map focus without switching tabs."""
        try:
            selection = self.hierarchy_tree.selection()
            if not selection:
                return

            item = selection[0]
            values = self.hierarchy_tree.item(item, "values")
            if not values:
                return

            pid = int(values[0])

            # Update brain map focus without switching tabs
            if hasattr(self, 'brain_viz'):
                self.brain_viz.focused_pid = pid
                # Update active group
                self.brain_viz.active_group.clear()
                self.brain_viz.active_group.add(pid)

                # If we have the snapshot, add related processes
                if self.current_snapshot and pid in self.current_snapshot.all_nodes:
                    node = self.current_snapshot.all_nodes[pid]
                    # Add children
                    for child_pid in node.children_pids:
                        self.brain_viz.active_group.add(child_pid)
                    # Add parent
                    if node.parent_pid:
                        self.brain_viz.active_group.add(node.parent_pid)
                    # Add connected processes
                    for connected_pid in node.connected_to:
                        self.brain_viz.active_group.add(connected_pid)

                logging.debug(f"Selected PID {pid} in hierarchy, updated brain map focus")

        except Exception as e:
            logging.error(f"Failed to handle hierarchy selection: {e}", exc_info=True)

    def _focus_pid_in_brain_map(self, pid):
        """Focus a specific PID in the Brain Map visualization and switch to Brain Map tab."""
        try:
            # First update the selection (same as on_hierarchy_select)
            if hasattr(self, 'brain_viz'):
                self.brain_viz.focused_pid = pid
                # Add to active group
                self.brain_viz.active_group.clear()
                self.brain_viz.active_group.add(pid)

                # If we have the snapshot, add related processes
                if self.current_snapshot and pid in self.current_snapshot.all_nodes:
                    node = self.current_snapshot.all_nodes[pid]
                    # Add children
                    for child_pid in node.children_pids:
                        self.brain_viz.active_group.add(child_pid)
                    # Add parent
                    if node.parent_pid:
                        self.brain_viz.active_group.add(node.parent_pid)
                    # Add connected processes
                    for connected_pid in node.connected_to:
                        self.brain_viz.active_group.add(connected_pid)

                logging.info(f"Focused PID {pid} in Brain Map with {len(self.brain_viz.active_group)} related processes")

            # Switch to Brain Map tab
            self.notebook.select(self.brain_frame)

            # Trigger a refresh if method exists
            if hasattr(self, 'brain_viz') and hasattr(self.brain_viz, 'update_visualization'):
                self.brain_viz.update_visualization()

        except Exception as e:
            logging.error(f"Failed to focus PID in brain map: {e}", exc_info=True)

    def on_center_tab_changed(self, event):
        """Handle center notebook tab changes - sync with right panel."""
        try:
            # Get the currently selected tab
            current_tab = self.notebook.select()
            tab_text = self.notebook.tab(current_tab, "text")

            # If Brain Map is selected, switch right panel to Monitor and refresh
            if tab_text == "Brain Map":
                self.right_notebook.select(self.monitor_tab)
                # Refresh hierarchy in live mode (not frozen)
                if not self.frozen_snapshot:
                    self.refresh_hierarchy()

        except Exception as e:
            logging.error(f"Failed to handle tab change: {e}", exc_info=True)

    def export_full_process_snapshot(self):
        """Export comprehensive process snapshot with ghost detection to markdown."""
        try:
            # Use frozen snapshot if available, otherwise capture fresh
            snapshot = self.frozen_snapshot
            if snapshot is None:
                snapshot = self.analyzer.capture_snapshot()

            # Gather all process data
            ghost_processes = []
            traced_processes = []
            suspicious_processes = []
            unknown_processes = []

            for pid, node in snapshot.all_nodes.items():
                try:
                    proc = psutil.Process(pid)
                    proc_info = {
                        'pid': proc.pid,
                        'name': proc.name(),
                        'cmdline': proc.cmdline(),
                        'cpu_percent': proc.cpu_percent(),
                        'memory_percent': proc.memory_info().rss / psutil.virtual_memory().total * 100,
                    }
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    proc_info = {
                        'pid': pid,
                        'name': node.name,
                        'cmdline': node.cmdline,
                        'cpu_percent': node.cpu_aggregate,
                        'memory_percent': node.mem_aggregate,
                    }

                category = get_category(proc) if pid in [p.pid for p in psutil.process_iter()] else node.category
                ghost_status = self._detect_ghost_status(pid, proc_info, category)

                # Build detailed record
                record = {
                    'pid': pid,
                    'name': node.name,
                    'cmdline': ' '.join(node.cmdline) if node.cmdline else 'N/A',
                    'category': category,
                    'ghost_status': ghost_status,
                    'depth': node.depth,
                    'descendants': node.descendant_count,
                    'dominance': node.dominance_score(),
                    'cpu': proc_info.get('cpu_percent', 0),
                    'memory': proc_info.get('memory_percent', 0),
                    'threads': node.threads,
                    'network_connections': node.network_connections,
                    'source_file': node.source_file,
                    'imports': node.imports,
                    'classes': node.classes,
                    'functions': node.functions,
                    'connected_to': list(node.connected_to),
                    'parent_pid': node.parent_pid,
                    'children_pids': node.children_pids,
                }

                # Categorize
                if ghost_status == "ACCESS":
                    ghost_processes.append(record)
                elif ghost_status in ["UNKNOWN", "No Source", "No Hier", "No Code"]:
                    unknown_processes.append(record)
                elif ghost_status == "✓":
                    traced_processes.append(record)

                    # Check for suspicious patterns
                    if node.network_connections > 5 or any(keyword in ' '.join(node.cmdline).lower() for keyword in ['telemetry', 'analytics', 'tracking']):
                        suspicious_processes.append(record)

            # Build markdown report
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            export_path = os.path.join(LOG_DIR, f"process_snapshot_{timestamp}.md")

            with open(export_path, 'w') as f:
                f.write(f"# Process Snapshot Report\n\n")
                f.write(f"**Generated**: {snapshot.timestamp}\n")
                f.write(f"**Total Processes**: {snapshot.total_processes}\n")
                f.write(f"**Total Threads**: {snapshot.total_threads}\n")
                f.write(f"**Total Network Connections**: {snapshot.total_connections}\n\n")

                f.write("---\n\n")

                # Summary statistics
                f.write("## Summary Statistics\n\n")
                f.write(f"- ✅ **Fully Traced**: {len(traced_processes)}\n")
                f.write(f"- ⚠️  **Suspicious**: {len(suspicious_processes)}\n")
                f.write(f"- ❓ **Unknown/Partial**: {len(unknown_processes)}\n")
                f.write(f"- 👻 **Ghosts (Access Denied)**: {len(ghost_processes)}\n\n")

                coverage = (len(traced_processes) / snapshot.total_processes * 100) if snapshot.total_processes > 0 else 0
                f.write(f"**Coverage**: {coverage:.1f}%\n\n")

                f.write("---\n\n")

                # Section 1: True Ghosts (Access Denied)
                if ghost_processes:
                    f.write("## 👻 Ghost Processes (Access Denied)\n\n")
                    f.write("These processes cannot be accessed - likely system protected or kernel processes.\n\n")
                    for rec in sorted(ghost_processes, key=lambda x: x['dominance'], reverse=True):
                        f.write(f"### PID {rec['pid']}: {rec['name']}\n")
                        f.write(f"- **Category**: {rec['category']}\n")
                        f.write(f"- **Command**: `{rec['cmdline'][:100]}`\n")
                        f.write(f"- **Dominance**: {rec['dominance']:.0f}\n")
                        f.write(f"- **Depth**: {rec['depth']}\n")
                        f.write(f"- **Descendants**: {rec['descendants']}\n\n")

                    f.write("---\n\n")

                # Section 2: Unknown/Partial Traces
                if unknown_processes:
                    f.write("## ❓ Unknown or Partially Traced Processes\n\n")
                    f.write("These processes are accessible but missing key context (source file, hierarchy, or code analysis).\n\n")

                    # Group by ghost status
                    by_status = {}
                    for rec in unknown_processes:
                        status = rec['ghost_status']
                        if status not in by_status:
                            by_status[status] = []
                        by_status[status].append(rec)

                    for status, recs in sorted(by_status.items()):
                        f.write(f"### Status: {status}\n\n")
                        for rec in sorted(recs, key=lambda x: x['dominance'], reverse=True):
                            f.write(f"#### PID {rec['pid']}: {rec['name']}\n")
                            f.write(f"- **Category**: {rec['category']}\n")
                            f.write(f"- **Command**: `{rec['cmdline'][:100]}`\n")
                            f.write(f"- **Dominance**: {rec['dominance']:.0f} | Depth: {rec['depth']} | Descendants: {rec['descendants']}\n")
                            f.write(f"- **Resources**: CPU: {rec['cpu']:.1f}% | Memory: {rec['memory']:.1f}%\n")
                            f.write(f"- **Source File**: {rec['source_file'] or 'NOT FOUND'}\n")
                            if rec['parent_pid']:
                                f.write(f"- **Parent PID**: {rec['parent_pid']}\n")
                            if rec['children_pids']:
                                f.write(f"- **Children PIDs**: {', '.join(map(str, rec['children_pids'][:5]))}\n")
                            f.write(f"- **Network Connections**: {rec['network_connections']}\n")
                            if rec['connected_to']:
                                f.write(f"- **Connected To PIDs**: {', '.join(map(str, rec['connected_to'][:5]))}\n")

                            # What's missing
                            missing = []
                            if not rec['source_file']:
                                missing.append("source file")
                            if not rec['imports'] and not rec['classes'] and not rec['functions']:
                                missing.append("code analysis")
                            if rec['depth'] == 0 and not rec['children_pids']:
                                missing.append("hierarchy context")

                            if missing:
                                f.write(f"- **⚠️  Missing**: {', '.join(missing)}\n")

                            f.write("\n")

                    f.write("---\n\n")

                # Section 3: Suspicious Processes
                if suspicious_processes:
                    f.write("## ⚠️  Suspicious Processes\n\n")
                    f.write("These processes are fully traced but exhibit suspicious behavior.\n\n")
                    for rec in sorted(suspicious_processes, key=lambda x: x['network_connections'], reverse=True):
                        f.write(f"### PID {rec['pid']}: {rec['name']}\n")
                        f.write(f"- **Category**: {rec['category']}\n")
                        f.write(f"- **Command**: `{rec['cmdline'][:100]}`\n")
                        f.write(f"- **Source File**: `{rec['source_file']}`\n")
                        f.write(f"- **Network Connections**: {rec['network_connections']} ⚠️\n")
                        if rec['connected_to']:
                            f.write(f"- **Connected To PIDs**: {', '.join(map(str, rec['connected_to']))}\n")

                        # Suspicious indicators
                        indicators = []
                        if rec['network_connections'] > 5:
                            indicators.append(f"High network activity ({rec['network_connections']} connections)")
                        if 'telemetry' in rec['cmdline'].lower():
                            indicators.append("Contains 'telemetry' in command")
                        if 'analytics' in rec['cmdline'].lower():
                            indicators.append("Contains 'analytics' in command")
                        if 'tracking' in rec['cmdline'].lower():
                            indicators.append("Contains 'tracking' in command")

                        f.write(f"- **Indicators**: {'; '.join(indicators)}\n")

                        if rec['imports']:
                            f.write(f"- **Imports ({len(rec['imports'])})**: {', '.join(rec['imports'][:10])}\n")

                        f.write("\n")

                    f.write("---\n\n")

                # Section 4: Fully Traced (Summary Only)
                f.write("## ✅ Fully Traced Processes\n\n")
                f.write(f"**Count**: {len(traced_processes)}\n\n")
                f.write("Top 10 by dominance:\n\n")
                for rec in sorted(traced_processes, key=lambda x: x['dominance'], reverse=True)[:10]:
                    f.write(f"- **PID {rec['pid']}**: {rec['name']} (Dominance: {rec['dominance']:.0f}, Source: {os.path.basename(rec['source_file']) if rec['source_file'] else 'N/A'})\n")

                f.write("\n---\n\n")

                # Section 5: Coverage Gaps
                f.write("## 📊 Coverage Gaps\n\n")

                total_with_source = len([r for r in traced_processes + unknown_processes if r['source_file']])
                total_with_hier = len([r for r in traced_processes + unknown_processes if r['depth'] > 0 or r['children_pids']])
                total_with_code = len([r for r in traced_processes + unknown_processes if r['imports'] or r['classes'] or r['functions']])

                f.write(f"- **Source File Detection**: {total_with_source}/{snapshot.total_processes} ({total_with_source/snapshot.total_processes*100:.1f}%)\n")
                f.write(f"- **Hierarchy Context**: {total_with_hier}/{snapshot.total_processes} ({total_with_hier/snapshot.total_processes*100:.1f}%)\n")
                f.write(f"- **Code Analysis**: {total_with_code}/{snapshot.total_processes} ({total_with_code/snapshot.total_processes*100:.1f}%)\n\n")

                # Recommendations
                f.write("### Recommendations\n\n")
                if len(unknown_processes) > len(traced_processes):
                    f.write("- ⚠️  **HIGH**: Over 50% of processes lack full context - consider expanding pyview language support\n")
                if len(ghost_processes) > 10:
                    f.write("- ⚠️  **MEDIUM**: Many ghost processes detected - may need elevated permissions for full system visibility\n")
                if len(suspicious_processes) > 0:
                    f.write(f"- ⚠️  **CRITICAL**: {len(suspicious_processes)} suspicious processes detected - recommend immediate security scan\n")
                if total_with_source / snapshot.total_processes < 0.5:
                    f.write("- ⚠️  **MEDIUM**: Less than 50% source file detection - improve cmdline parsing or add binary analysis\n")

                f.write("\n---\n\n")
                f.write(f"*Report generated by Process Monitoring Suite on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*\n")

            messagebox.showinfo("Export Complete", f"Full process snapshot exported to:\n{export_path}")
            logging.info(f"Full process snapshot exported to {export_path}")

        except Exception as e:
            logging.error(f"Failed to export full snapshot: {e}", exc_info=True)
            messagebox.showerror("Export Failed", str(e))

    def export_system_state(self, silent=False):
        """Export the full current state of the GUI, logs, and process profiles."""
        try:
            # 1. Gather all context
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            export_path = os.path.join(LOG_DIR, f"system_state_{timestamp}.md")
            
            snapshot = self.frozen_snapshot or self.analyzer.capture_snapshot()
            
            with open(export_path, 'w') as f:
                f.write(f"# Unified System State Report\n\n")
                f.write(f"- **Generated**: {datetime.now()}\n")
                f.write(f"- **Session Log**: {get_current_log_file()}\n")
                f.write(f"- **Resource Level**: {CM.get('user_prefs.brain_map.resource_level', 50)}%\n\n")
                
                f.write("## 1. Intent & Outcome Log\n\n")
                for intent in self.intent_log:
                    f.write(f"- [{intent['timestamp']}] **{intent['id']}** | {intent['source']}: {intent['action']} -> *{intent['status']}*\n")
                
                f.write("\n## 2. Runtime Anomalies (Performance Guard)\n\n")
                if not self.performance_bugs:
                    f.write("No bugs recorded in current session.\n")
                for bug in self.performance_bugs:
                    f.write(f"- [{bug['timestamp']}] **{bug['type']}**: {bug.get('detail', 'N/A')}\n")
                
                f.write("\n## 3. Behavioral Mapping (Catch Log)\n\n")
                if not self.behavior_map:
                    f.write("No behavioral ghosts resolved.\n")
                for path, data in self.behavior_map.items():
                    f.write(f"### {os.path.basename(path)}\n")
                    f.write(f"- **PID**: {data['pid']} ({data['name']})\n")
                    f.write(f"- **Event**: `{data['last_event']}`\n\n")
                
                f.write("## 4. Process Hierarchy & Dominance\n\n")
                f.write("```\n")
                f.write(self.analyzer.build_hierarchy_text(snapshot, max_depth=5))
                f.write("\n```\n\n")
                
                f.write("## 5. Detailed Process Profiles (Top 10 Dominant)\n\n")
                for node in snapshot.dominant_processes[:10]:
                    f.write(f"### PID {node.pid}: {node.name}\n")
                    f.write(f"- **Dominance**: {node.dominance_score():.1f}\n")
                    f.write(f"- **Source**: `{node.source_file or 'Unknown'}`\n")
                    f.write(f"- **Threads**: {node.threads} | **Connections**: {node.network_connections}\n")
                    if node.open_file_paths:
                        f.write("- **Active Files**:\n")
                        for fp in node.open_file_paths[:5]:
                            f.write(f"  - `{fp}`\n")
                    if node.imports:
                        f.write(f"- **Key Imports**: {', '.join(node.imports[:10])}\n")
                    f.write("\n")

            if not silent:
                messagebox.showinfo("System Export", f"Full state report generated:\n{export_path}")
            
            logging.info(f"System State Exported to {export_path}")
            return export_path

        except Exception as e:
            logging.error(f"Failed to export system state: {e}")
            if not silent: messagebox.showerror("Export Error", str(e))
            return None

    def export_hierarchy_snapshot(self):
        """Export current hierarchy snapshot to text file and CLI display."""
        try:
            # Use frozen snapshot if available, otherwise capture fresh
            snapshot = self.frozen_snapshot
            if snapshot is None:
                snapshot = self.analyzer.capture_snapshot()

            # Build hierarchy text
            text = self.analyzer.build_hierarchy_text(snapshot, max_depth=5)

            # Save to file
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            export_path = os.path.join(LOG_DIR, f"hierarchy_export_{timestamp}.txt")

            with open(export_path, 'w') as f:
                f.write(text)
                f.write("\n\n=== Detailed Process List ===\n")
                for node in snapshot.dominant_processes:
                    f.write(f"\n[{node.pid}] {node.name}\n")
                    f.write(f"  Depth: {node.depth}, Descendants: {node.descendant_count}\n")
                    f.write(f"  Dominance Score: {node.dominance_score():.0f}\n")
                    if node.source_file:
                        f.write(f"  Source: {node.source_file}\n")
                    if node.imports:
                        f.write(f"  Imports: {', '.join(node.imports[:5])}\n")

            # Also show in CLI output
            self.cli_text.delete(1.0, tk.END)
            self.cli_text.insert(tk.END, text)
            self.notebook.select(self.cli_frame)

            messagebox.showinfo("Export Complete", f"Hierarchy exported to:\n{export_path}")
            logging.info(f"Hierarchy snapshot exported to {export_path}")

        except Exception as e:
            logging.error(f"Failed to export hierarchy: {e}", exc_info=True)
            messagebox.showerror("Export Failed", str(e))

    def refresh_file_tree(self):
        [self.tree.delete(i) for i in self.tree.get_children()]
        n = self.tree.insert('', 'end', text=os.path.basename(self.current_dir), values=(self.current_dir,), open=True)
        self.add_to_tree(self.current_dir, n)

    def add_to_tree(self, path, parent):
        try:
            for item in sorted(os.listdir(path)):
                if item.startswith('.'): continue
                abs_p = os.path.join(path, item)
                node = self.tree.insert(parent, 'end', text=item, values=(abs_p,))
                if os.path.isdir(abs_p):
                    self.add_to_tree(abs_p, node)
        except: pass

    def kill_targeted_process(self):
        """Terminate the currently focused process."""
        try:
            import psutil
            psutil.Process(int(self.focused_pid)).terminate()
            self.update_proc_list()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def suspend_targeted_process(self):
        """Toggle suspend/resume state of the focused process."""
        try:
            import psutil
            p = psutil.Process(int(self.focused_pid))
            if p.status() == psutil.STATUS_STOPPED:
                p.resume()
                self.suspend_btn.config(text="SUSP")
            else:
                p.suspend()
                self.suspend_btn.config(text="RESM")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def on_proc_select(self, e):
        """Display detailed technical context and detected traits in the LEFT panel."""
        sel = self.proc_tree.selection()
        if not sel: return
        
        v = self.proc_tree.item(sel[0], "values")
        self.focused_pid = v[0]
        # Adjust indices due to DOM column insertion
        # 0:pid, 1:dom, 2:group, 3:cpu, 4:mem, 5:name, 6:cmd
        self.target_label.config(text=f"TARGET: [{v[0]}] {v[5]}")
        self.kill_btn.config(state="normal")
        self.suspend_btn.config(state="normal")

        # Update brain visualization with focused PID
        if hasattr(self, 'brain_viz'):
            self.brain_viz.set_focused_pid(int(v[0]))
        
        self.manifest_display.delete(1.0, tk.END)
        self.manifest_display.insert(tk.END, f"--- Process Context ---\n", "header")
        self.manifest_display.tag_configure("header", font=('Monospace', 10, 'bold'), foreground="#007acc")
        
        self.manifest_display.insert(tk.END, f"PID:      {v[0]}\n")
        self.manifest_display.insert(tk.END, f"Name:     {v[5]}\n")
        
        try:
            import psutil
            p = psutil.Process(int(v[0]))
            
            # Show dominance if we have a current snapshot
            if self.current_snapshot and int(v[0]) in self.current_snapshot.all_nodes:
                node = self.current_snapshot.all_nodes[int(v[0])]
                self.manifest_display.insert(tk.END, f"Dominance: {node.dominance_score():.1f}\n", "header")
                self.manifest_display.insert(tk.END, f"  Depth:   {node.depth}\n")
                self.manifest_display.insert(tk.END, f"  Descendants: {node.descendant_count}\n")
                if node.connected_to:
                    self.manifest_display.insert(tk.END, f"  Talking to: {len(node.connected_to)} PIDs\n")

            # 1. Lineage & Grouping
            parents = []
            curr = p.parent()
            while curr:
                parents.insert(0, f"{curr.name()}({curr.pid})")
                curr = curr.parent()
            self.manifest_display.insert(tk.END, f"Lineage:  {' > '.join(parents[-2:])}\n")
            
            # 2. Behavioural Traits
            traits = []
            conns = p.connections()
            if conns: 
                traits.append("NET_ACTIVE")
                self.log_communication_event(v[0], v[3], f"NET: {len(conns)} active sockets")
            
            # IPC/Cluster Communication Check
            if self.active_group and int(v[0]) in self.active_group:
                # Logic to 'prove' communication would go here
                traits.append("IPC_POTENTIAL")
                self.log_communication_event(v[0], v[3], "Cluster communication detected")
            
            if p.cpu_percent() > 15: traits.append("CPU_INTENSE")
            if p.memory_info().rss > 500 * 1024 * 1024: traits.append("MEM_HEAVY")
            
            if traits:
                self.manifest_display.insert(tk.END, f"Traits:   [{', '.join(traits)}]\n", "traits")
                self.manifest_display.tag_configure("traits", foreground="#ffa500")

            # 3. Server/Socket Detail
            if conns:
                self.manifest_display.insert(tk.END, f"Sockets:  {len(conns)} active\n")
                for c in conns[:3]:
                    status = c.status
                    raddr = f"{c.raddr.ip}:{c.raddr.port}" if c.raddr else "LISTENING"
                    self.manifest_display.insert(tk.END, f"  ↳ {status} | {raddr}\n")

            # 3.5 Behavioral Resolution
            for file_path, data in self.behavior_map.items():
                if data['pid'] == int(v[0]):
                    self.manifest_display.insert(tk.END, f"Behaviour: [Linked to {os.path.basename(file_path)}]\n", "behavior")
                    self.manifest_display.insert(tk.END, f"  ↳ {data['last_event'][:60]}...\n", "behavior")
                    self.manifest_display.tag_configure("behavior", foreground="#ae81ff")
            
            # 4. Source Trace (from cmdline)
            cmd = p.cmdline()
            if cmd:
                self.manifest_display.insert(tk.END, "-"*25 + "\n")
                for arg in cmd:
                    if arg.endswith(('.py', '.sh', '.js')) and os.path.exists(arg):
                        self.manifest_display.insert(tk.END, f"Source: {os.path.basename(arg)}\n", "source")
                        self.manifest_display.tag_configure("source", foreground="#00ff00")
                        break

        except Exception as e:
            self.manifest_display.insert(tk.END, f"Context Error: {e}\n")

    def view_daily_journal(self):
        """Immediately switch the log selector to today's communication journal."""
        today = f"comm_{datetime.now().strftime('%Y%m%d')}.log"
        if today in self.log_selector['values']:
            self.log_selector.set(today)
            self.on_log_selected(None)
            self.notebook.select(self.proc_frame) # Stay on monitor but update log view
        else:
            messagebox.showinfo("Journal", "No communication events recorded for today yet.")

    def deep_trace_process(self):
        """Perform an anatomical trace of the process and its file/thread lineage."""
        if not self.focused_pid: return
        self.cli_text.delete(1.0, tk.END)
        self.notebook.select(self.cli_frame)
        self.cli_text.insert(tk.END, f"--- Deep Tracing PID: {self.focused_pid} ---\n", "header")
        self.cli_text.tag_configure("header", foreground="#007acc", font=('Monospace', 10, 'bold'))
        
        try:
            import psutil
            p = psutil.Process(int(self.focused_pid))
            
            # Show expanding growth/tree in CLI
            self.visualize_growth(p)
            
            # File trajectory
            files = [f.path for f in p.open_files()]
            self.cli_text.insert(tk.END, f"\n[File Trajectories]\n")
            for f in files[:10]:
                self.cli_text.insert(tk.END, f" ↳ {f}\n")
                
            # Thread check
            self.cli_text.insert(tk.END, f"\n[Thread Snapshot]\n")
            for t in p.threads()[:5]:
                self.cli_text.insert(tk.END, f" ↳ ID: {t.id} | User: {t.user_time}s | System: {t.system_time}s\n")

        except Exception as e:
            self.cli_text.insert(tk.END, f"Trace Error: {e}\n")

    def visualize_growth(self, p, indent=""):
        """Recursive visualization of the process cluster growth."""
        self.cli_text.insert(tk.END, f"{indent}● {p.name()} ({p.pid})\n")
        try:
            children = p.children()
            for child in children:
                self.visualize_growth(child, indent + "  │ ")
        except: pass

    def group_related_processes(self):
        """Identify related processes and pin them to the top of the monitor."""
        if not self.focused_pid: return
        import psutil
        try:
            p = psutil.Process(int(self.focused_pid))
            self.active_group = {p.pid}
            if p.parent(): self.active_group.add(p.parent().pid)
            for child in p.children(recursive=True):
                self.active_group.add(child.pid)

            # Change UI state to reflect grouping
            self.target_label.config(text=f"CLUSTER FOCUS: {len(self.active_group)} PIDs", foreground="#00ff00")

            # Show a reset button if not already there
            if not hasattr(self, 'group_reset_btn'):
                self.group_reset_btn = ttk.Button(self.sk_f, text="Reset", width=6, command=self.reset_group_focus)
                self.group_reset_btn.pack(side=tk.LEFT, padx=1)

            # Update brain visualization with active group
            if hasattr(self, 'brain_viz'):
                self.brain_viz.set_active_group(self.active_group)

            self.update_proc_list()
        except: pass

    def reset_group_focus(self):
        """Clear the pinned cluster and restore standard sorting."""
        self.active_group = set()
        self.target_label.config(text="No selection", foreground=self.colors["fg"])
        if hasattr(self, 'group_reset_btn'):
            self.group_reset_btn.destroy()
            delattr(self, 'group_reset_btn')

        # Clear brain visualization active group
        if hasattr(self, 'brain_viz'):
            self.brain_viz.set_active_group(set())

        self.update_proc_list()

    def setup_brain_map_tab(self):
        """Initialize the 3D process brain map visualization using matplotlib."""
        logging.info("Initializing 3D Brain Map with matplotlib")

        # Get brain map config
        brain_cfg = self.prefs.get('brain_map', {})
        enable_debug = brain_cfg.get('enable_debug', False)

        logging.info(f"Brain Map debug mode: {enable_debug}")

        # Create the ProcessBrainVisualization widget
        self.brain_viz = ProcessBrainVisualization(self.brain_frame, get_category, enable_debug=enable_debug)
        self.brain_viz.pack(fill=tk.BOTH, expand=True)

        logging.info("Brain Map tab initialized successfully")

    def route_process_to_source(self):
        """Identify script in process cmdline and route to Editor/Hier."""
        if not self.focused_pid: return
        import psutil
        try:
            p = psutil.Process(int(self.focused_pid))
            for arg in p.cmdline():
                if arg.endswith(('.py', '.sh')) and os.path.exists(arg):
                    path = os.path.abspath(arg)
                    self.load_file_to_editor(path)
                    return
            messagebox.showinfo("Route", "No source script found in command line.")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def toggle_proc_monitor(self):
        """Toggle the active refresh loop for the process monitor with visual cue."""
        active = self.proc_active.get()
        if active:
            self.proc_active_cb.config(text="Active Monitor")
            logging.info("Process monitor refresh enabled.")
            # If unfreezing, clear the hierarchy snapshot
            if self.frozen_snapshot is not None:
                self.unfreeze_system()
            else:
                self.update_proc_list()
        else:
            self.proc_active_cb.config(text="Monitor FROZEN")
            logging.info("Process monitor refresh paused.")
            # When pausing, capture a snapshot
            if self.frozen_snapshot is None:
                self.freeze_system_snapshot()

        # Sync with Brain Map
        if hasattr(self, 'brain_viz'):
            self.brain_viz.frozen.set(not active)

    def sort_proc_tree(self, col):
        """Toggle sort order or column for the Monitor tree."""
        if self.proc_sort_col == col:
            self.proc_sort_desc = not self.proc_sort_desc
        else:
            self.proc_sort_col = col
            self.proc_sort_desc = (col in ('cpu', 'mem'))
        self.update_proc_list()

    def update_proc_list(self):
        """Fetch processes, apply priority colors, and sort per configuration."""
        import psutil
        from process_organizer import get_category, CM

        # 0. PERFORMANCE PROTECTION: Use existing snapshot if fresh (< 1s old)
        # This prevents double-capture when called from refresh_hierarchy
        if self.current_snapshot and not self.frozen_snapshot:
            # Check if current_snapshot was captured recently
            try:
                from datetime import datetime
                snap_time = datetime.strptime(self.current_snapshot.timestamp, "%Y-%m-%d %H:%M:%S.%f")
                if (datetime.now() - snap_time).total_seconds() < 1.0:
                    pass # Reuse current_snapshot
                else:
                    res_level = CM.config['user_prefs'].get('brain_map', {}).get('resource_level', 50)
                    self.current_snapshot = self.analyzer.capture_snapshot(resource_level=res_level)
            except:
                res_level = CM.config['user_prefs'].get('brain_map', {}).get('resource_level', 50)
                self.current_snapshot = self.analyzer.capture_snapshot(resource_level=res_level)
        elif not self.current_snapshot:
            res_level = CM.config['user_prefs'].get('brain_map', {}).get('resource_level', 50)
            self.current_snapshot = self.analyzer.capture_snapshot(resource_level=res_level)

        # Use frozen snapshot if available
        if self.frozen_snapshot:
            self.current_snapshot = self.frozen_snapshot

        # 1. Fetch current selection to restore it after refresh
        current_sel = self.proc_tree.selection()
        selected_pid = self.proc_tree.item(current_sel[0], 'values')[0] if current_sel else None

        # 2. Get filter config
        proc_cfg = CM.get('user_prefs.process_monitor', {})
        filters = proc_cfg.get('filters', {})
        show_categories = filters.get('show_categories', [])
        hide_categories = filters.get('hide_categories', [])
        hide_system_idle = filters.get('hide_system_idle', True)
        min_cpu = filters.get('min_cpu_threshold', 0.1)
        min_mem = filters.get('min_mem_threshold', 0.1)

        # 3. Get process data with filters
        procs = []
        for p in psutil.process_iter(['pid', 'cpu_percent', 'memory_percent', 'name', 'cmdline']):
            try:
                # Add priority/color data
                cat_name, cat_color, priority = get_category(p)
                p.info['category'] = cat_name
                p.info['cat_color'] = cat_color
                p.info['priority'] = priority

                # Apply filters
                # Filter by category (show_categories takes precedence)
                if show_categories and cat_name not in show_categories:
                    continue
                if hide_categories and cat_name in hide_categories:
                    continue

                # Filter system idle processes
                if hide_system_idle and "SYSTEM" in cat_name:
                    if p.info['cpu_percent'] < min_cpu and p.info['memory_percent'] < min_mem:
                        continue

                # Apply search filter if active
                if self.search_filter:
                    name_lower = p.info['name'].lower()
                    cmd_lower = " ".join(p.info['cmdline'] or []).lower()
                    if self.search_filter not in name_lower and self.search_filter not in cmd_lower:
                        continue

                procs.append(p.info)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

        # 3. Check for alerts
        alerts_cfg = proc_cfg.get('alerts', {})
        if alerts_cfg.get('enable_notifications', False):
            cpu_threshold = alerts_cfg.get('cpu_threshold', 80.0)
            mem_threshold = alerts_cfg.get('mem_threshold', 85.0)

            for p in procs:
                if p['cpu_percent'] > cpu_threshold:
                    logging.warning(f"CPU Alert: {p['name']} (PID {p['pid']}) using {p['cpu_percent']:.1f}% CPU")
                if p['memory_percent'] > mem_threshold:
                    logging.warning(f"Memory Alert: {p['name']} (PID {p['pid']}) using {p['memory_percent']:.1f}% memory")

        # 4. Sort logic with Cluster Affinity
        reverse = self.proc_sort_desc
        col = self.proc_sort_col

        # Primary key is whether the PID is in the active group (False < True, so we negate)
        def sort_key(x):
            is_grouped = x['pid'] in self.active_group
            if col == "pid": val = x['pid']
            elif col == "dom":
                val = 0
                if self.current_snapshot and x['pid'] in self.current_snapshot.all_nodes:
                    val = self.current_snapshot.all_nodes[x['pid']].dominance_score()
            elif col == "group": val = x['category'].lower()
            elif col == "cpu": val = x['cpu_percent']
            elif col == "mem": val = x['memory_percent']
            elif col == "name": val = x['name'].lower()
            else: val = (x['priority'], -x['cpu_percent'])
            return (not is_grouped, val)

        procs.sort(key=sort_key, reverse=reverse if col not in ("priority", "group") else False)

        # 5. Update UI
        self.proc_tree.delete(*self.proc_tree.get_children())
        
        # Dynamic Column Coordination
        total_width = self.proc_tree.winfo_width()
        if total_width > 200:
            # PID, DOM, CPU, MEM = ~50-60 each
            # Group = ~100
            # Name = ~120
            # Cmd = remainder
            fixed = 60 * 4 + 100 + 120
            rem = max(100, total_width - fixed - 20)
            self.proc_tree.column("pid", width=60)
            self.proc_tree.column("dom", width=60)
            self.proc_tree.column("cpu", width=60)
            self.proc_tree.column("mem", width=60)
            self.proc_tree.column("group", width=100)
            self.proc_tree.column("name", width=120)
            self.proc_tree.column("cmd", width=rem)

        # Map organizer colors to Tkinter-friendly hex (approximate)
        color_map = {
            "\033[92m": "#00ff00", # Green
            "\033[94m": "#4d96ff", # Blue
            "\033[95m": "#ae81ff", # Purple
            "\033[93m": "#ffd93d", # Yellow
            "\033[90m": "#858585", # Gray
            "\033[91m": "#ff0000"  # Red
        }

        for p in procs:
            pid = p['pid']
            group = p['category'].strip()
            cpu = p['cpu_percent']
            mem = p['memory_percent']
            name = p['name']
            cmd = " ".join(p['cmdline'] or [])

            # Get dominance
            dom = 0
            if self.current_snapshot and pid in self.current_snapshot.all_nodes:
                dom = int(self.current_snapshot.all_nodes[pid].dominance_score())

            # Enhanced ghost detection
            ghost_status = self._detect_ghost_status(pid, p, group)

            # Add tracking indicator to name if tracked
            display_name = name
            if pid in self.tracked_processes:
                display_name = f"★ {name}"

            # Define row tag for coloring
            tag = p['category']
            row_color = color_map.get(p['cat_color'], "#ffffff")
            self.proc_tree.tag_configure(tag, foreground=row_color)

            # Apply ghost tag if detected
            tags = (tag,)
            if ghost_status != "✓":
                self.proc_tree.tag_configure("ghost", foreground="#ff6b6b")
                tags = (tag, "ghost")

            # Apply tracked tag for bold emphasis
            if pid in self.tracked_processes:
                self.proc_tree.tag_configure("tracked", font=('Monospace', 9, 'bold'), foreground="#00ff00")
                tags = (tag, "tracked") if ghost_status == "✓" else (tag, "ghost", "tracked")

            item_id = self.proc_tree.insert('', 'end', values=(pid, dom, group, ghost_status, cpu, mem, display_name, cmd), tags=tags)
            
            # Restore selection
            if selected_pid and str(pid) == str(selected_pid):
                self.proc_tree.selection_set(item_id)

        # 6. Loop if active
        if self.proc_active.get():
            self.root.after(self.refresh_ms.get(), self.update_proc_list)

    def _detect_ghost_status(self, pid, proc_info, category):
        """
        Detect ghost status using 'lack of' method.
        Returns:
            "✓" - Fully traced
            "No Source" - Can't find source file
            "No Hier" - No hierarchy context
            "ACCESS" - Access denied (true ghost)
            "ZOMBIE" - Zombie process
            "UNKNOWN" - Multiple missing contexts
        """
        # Check if already marked as Ghost by get_category
        if "Ghost" in category or "ghost" in category.lower():
            return "ACCESS"

        missing = []

        # Check 1: Source file detection
        has_source = False
        if self.current_snapshot and pid in self.current_snapshot.all_nodes:
            node = self.current_snapshot.all_nodes[pid]
            if node.source_file:
                has_source = True

        if not has_source:
            # Try to detect from cmdline
            cmdline = proc_info.get('cmdline', [])
            for arg in cmdline:
                if isinstance(arg, str) and arg.endswith(('.py', '.rs', '.cpp', '.c', '.go', '.js', '.sh')):
                    if os.path.exists(arg):
                        has_source = True
                        break

        if not has_source:
            missing.append("source")

        # Check 2: Hierarchy context (parent/children)
        has_hier = False
        if self.current_snapshot and pid in self.current_snapshot.all_nodes:
            node = self.current_snapshot.all_nodes[pid]
            # Has hierarchy if it has parent or children or depth > 0
            if node.parent_pid or node.children_pids or node.depth > 0:
                has_hier = True

        if not has_hier:
            missing.append("hier")

        # Check 3: Code analysis (imports, classes, functions)
        has_code_context = False
        if self.current_snapshot and pid in self.current_snapshot.all_nodes:
            node = self.current_snapshot.all_nodes[pid]
            if node.imports or node.classes or node.functions:
                has_code_context = True

        if not has_code_context and has_source:
            # Has source but no code analysis (suspicious)
            missing.append("code")

        # Determine ghost status
        if not missing:
            return "✓"
        elif len(missing) == 1:
            if "source" in missing:
                return "No Source"
            elif "hier" in missing:
                return "No Hier"
            elif "code" in missing:
                return "No Code"
        elif len(missing) >= 2:
            return "UNKNOWN"

        return "?"

    def show_search_dialog(self):
        sw = tk.Toplevel(self.root)
        sw.title("Find")
        sw.geometry("300x100")
        ent = tk.Entry(sw)
        ent.pack(pady=10)
        def find():
            s = ent.get()
            pos = self.editor.search(s, "1.0", tk.END)
            if pos:
                self.editor.tag_add("sel", pos, f"{pos}+{len(s)}c")
                self.editor.see(pos)
        tk.Button(sw, text="Go", command=find).pack()

    def check_integrity(self):
        v, m = CM.verify_integrity()
        messagebox.showinfo("Integrity", f"{('OK' if v else 'FAIL')}\n{m}")

    def load_manifest(self): 
        """Load manifest.json and update the integrity summary display."""
        self.manifest_display.delete(1.0, tk.END)
        
        # 1. Check Integrity
        is_valid, msg = CM.verify_integrity()
        status = "SECURE" if is_valid else "MISMATCH"
        color = "#00ff00" if is_valid else "#ff0000"
        
        self.manifest_display.insert(tk.END, f"Integrity: {status}\n", ("status",))
        self.manifest_display.tag_configure("status", foreground=color, font=('Monospace', 9, 'bold'))
        self.manifest_display.insert(tk.END, f"Details: {msg}\n")
        self.manifest_display.insert(tk.END, "-"*25 + "\n")
        
        # 2. Load Manifest Summary
        if os.path.exists(self.manifest_path):
            try:
                with open(self.manifest_path, 'r') as f:
                    data = json.load(f)
                
                self.manifest_display.insert(tk.END, f"Last Scan: {data.get('last_updated', 'N/A')}\n")
                summary = data.get('scan_summary', [])
                self.manifest_display.insert(tk.END, f"Files Scanned: {len(summary)}\n")
                
                risks = [r for r in summary if r.get('score', 100) < 80]
                if risks:
                    self.manifest_display.insert(tk.END, f"Risks Found: {len(risks)}\n", ("risk",))
                    self.manifest_display.tag_configure("risk", foreground="#ffa500")
                else:
                    self.manifest_display.insert(tk.END, "Risks Found: 0\n")
            except Exception as e:
                self.manifest_display.insert(tk.END, f"Manifest Error: {e}\n")
        else:
            self.manifest_display.insert(tk.END, "Manifest: Not Found\n")

        # 3. Inject Performance Bugs
        if self.performance_bugs:
            self.manifest_display.insert(tk.END, "-"*25 + "\n")
            self.manifest_display.insert(tk.END, "🔴 RUNTIME ANOMALIES\n", "header")
            for bug in self.performance_bugs[-3:]: # Show last 3
                if bug['type'] == 'FPS_MISMATCH':
                    detail = f"FPS Delta: {bug['actual'] - bug['expected']}"
                else:
                    detail = bug.get('detail', 'Resource mismatch')
                
                bug_mark = f"#[Bug:{{type:'{bug['type']}', detail:'{detail}'}}]\n"
                self.manifest_display.insert(tk.END, bug_mark, "bug")
            
            self.manifest_display.tag_configure("bug", foreground="#ff6b6b", font=('Monospace', 8, 'italic'))

    def run_security_scan(self, rec=False):
        """Run the security scanner and stream output to the CLI panel."""
        self.cli_text.delete(1.0, tk.END)
        self.notebook.select(self.cli_frame)
        self.cli_text.insert(tk.END, f"--- Starting Security Scan: {self.current_dir} ---\n")
        
        def task():
            cmd = [sys.executable, "process_organizer.py", "--scan", self.current_dir]
            if rec: cmd.append("-r")
            
            # Pass unified session log to subprocess
            log_path = get_current_log_file()
            if log_path:
                cmd.extend(["--session-log", log_path])
            
            try:
                # Use Popen to stream stdout
                proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
                
                for line in proc.stdout:
                    self.root.after(0, lambda l=line: self.append_cli_text(l))
                
                proc.wait()
                self.root.after(0, lambda: self.append_cli_text("\n--- Scan Complete ---\n"))
                # Refresh manifest summary after scan
                self.root.after(0, self.load_manifest)
            except Exception as e:
                self.root.after(0, lambda: self.append_cli_text(f"Execution Error: {e}\n"))
                
        threading.Thread(target=task, daemon=True).start()

    def append_cli_text(self, text):
        """Append text to CLI display and auto-scroll."""
        self.cli_text.insert(tk.END, text)
        self.cli_text.see(tk.END)

    def open_directory(self):
        """Open a directory selection dialog."""
        p = filedialog.askdirectory()
        if p:
            self.current_dir = p
            self.refresh_file_tree()

    def view_crash_logs(self):
        """Find the latest GUI log containing an error and display it."""
        ls = sorted([f for f in os.listdir(LOG_DIR) if f.startswith('gui_')], reverse=True)
        for ln in ls:
            with open(os.path.join(LOG_DIR, ln), 'r') as f:
                if "ERROR" in f.read():
                    self.log_selector.set(ln)
                    self.on_log_selected(None)
                    return

    def inspect_current_file(self):
        """Analyze the currently open file in the editor and show it in Hier-View."""
        if self.current_file:
            self.visualize_code(self.current_file)
            self.notebook.select(self.hier_frame)

if __name__ == "__main__":

    try:

        root = tk.Tk()

        app = SecureViewApp(root)

        root.mainloop()

    except Exception as e:

        # 1. Log to FATAL_BOOT for immediate visibility

        with open("FATAL_BOOT.txt", "a") as f:

            f.write(f"=== {datetime.now()} ===\nCRASH: {e}\n{traceback.format_exc()}\n")

        

        # 2. Trigger the global exception hook for unified logging and popup

        sys.excepthook(*sys.exc_info())

        sys.exit(1)
