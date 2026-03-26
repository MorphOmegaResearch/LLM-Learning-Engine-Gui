import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import os
import json
import datetime
from pathlib import Path
import subprocess
import sys
import difflib
import threading
from queue import Queue
import hashlib

# Import Ag Knowledge Linker
try:
    from ag_utils import AgKnowledgeLinker
except ImportError:
    try:
        from ..ag_utils import AgKnowledgeLinker
    except ImportError:
        AgKnowledgeLinker = None

# Trainer logger integration — lazy so PlannerSuite works standalone too
try:
    import sys as _sys
    # Walk up from tabs/ag_forge_tab/modules/quick_clip/tabs/ → Trainer/Data/
    _data_root = str(Path(__file__).parents[5])
    if _data_root not in _sys.path:
        _sys.path.insert(0, _data_root)
    import logger_util as _trainer_log
    _TRAINER_LOG_AVAILABLE = True
except Exception:
    _trainer_log = None
    _TRAINER_LOG_AVAILABLE = False

# Os_Toolkit path for Generate Report integration
_OS_TOOLKIT_PATH = Path(__file__).parents[5] / "tabs" / "action_panel_tab" / "Os_Toolkit.py"
_LATEST_RUNNING = False  # Guard: prevent concurrent Os_Toolkit latest processes
_SYNC_RUNNING = False    # Guard: prevent concurrent sync_todos runs

# AoE vector config — loaded once at module import
_AOE_CONFIG_PATH = Path(__file__).parents[5] / "plans" / "aoe_vector_config.json"
_AOE_CONFIG = None
try:
    with open(_AOE_CONFIG_PATH, 'r', encoding='utf-8') as _f:
        _AOE_CONFIG = json.load(_f)
except Exception:
    pass

class PlannerSuite(tk.Frame):
    def __init__(self, parent, app_ref, base_path=None):
        super().__init__(parent)
        self.parent = parent
        self.app = app_ref # Reference to the main ClipboardAssistant app
        self.base_path = base_path or os.path.expanduser("~/PlannerSuite")
        self.marked_files = []
        self.current_context = {}
        self.diff_history = []

        # Project editor state
        self._active_project_path = None   # Path to active epic .md
        self._active_project_id = None     # e.g., "Digital_Kingdom_001"
        self._current_edit_mode = "epic"   # "epic" | "task_context"
        self._current_edit_tid = None      # task_id when edit_mode=task_context
        self._ctx_edit_source_path = None  # path to task_context json being edited
        self._ctx_cache = {}               # {tid: ctx_dict} fast lookup cache
        self._tooltip_win = None           # hover tooltip Toplevel
        self._live_refresh_pending = False # guard for live branch auto-refresh

        # Load persisted active project from config
        try:
            _cfg = json.loads(Path(self.base_path).joinpath("config.json").read_text(encoding="utf-8"))
            self._active_project_id = _cfg.get("active_project_id")
            _ap = _cfg.get("active_project_path")
            self._active_project_path = Path(_ap) if _ap else None
        except Exception:
            pass

        # Initialize Ag Knowledge Linker
        self.ag_linker = AgKnowledgeLinker() if AgKnowledgeLinker else None
        
        # Create directory structure if it doesn't exist
        self.setup_directories()
        
        # Setup UI
        self.setup_ui()
        self._load_active_project_epic()  # after setup_ui so status_bar exists
        self._restore_active_project_indicator()
        self.load_directory_structure()
        # Populate live branch shortly after board loads (don't wait 30s)
        self.after(1500, self._refresh_live_branch)

    def _load_active_project_epic(self):
        """
        Scans for the project epic in plans/Epics/ and loads it.
        Currently loads the first .md file found.
        """
        epics_dir = Path(self.base_path) / "Epics"
        if not epics_dir.exists():
            self.status_bar.config(text="Epics directory not found.")
            return

        epic_files = list(epics_dir.glob("*.md"))
        if epic_files:
            # If a project is already persisted, load that specific epic — not just [0]
            target_epic = None
            if self._active_project_path and Path(self._active_project_path).exists():
                target_epic = Path(self._active_project_path)
            elif self._active_project_id:
                # Try to find by project_id stem match
                for ef in epic_files:
                    if self._active_project_id.lower() in ef.stem.lower():
                        target_epic = ef
                        break
            if target_epic is None:
                target_epic = epic_files[0]

            self.open_file(str(target_epic))
            self.status_bar.config(text=f"Loaded Epic: {target_epic.name}")
            # Auto-set active project on first load if not already set
            if not self._active_project_id:
                self._set_active_project(target_epic)
            if _TRAINER_LOG_AVAILABLE:
                _trainer_log.log_ux_event(
                    "ag_knowledge", "LOAD_EPIC", "board_load_epic_button",
                    outcome="success",
                    detail=f"Loaded {target_epic.name}",
                    wherein="PlannerSuite::_load_active_project_epic"
                )
        else:
            self.status_bar.config(text="No active project epic found.")
        
    def setup_directories(self):
        """Create the standard directory structure"""
        directories = [
            "Epics",
            "Plans", 
            "Phases",
            "Tasks",
            "Milestones",
            "Diffs",
            "Refs"
        ]
        
        for directory in directories:
            path = os.path.join(self.base_path, directory)
            os.makedirs(path, exist_ok=True)
            
        # Create config file if it doesn't exist
        config_path = os.path.join(self.base_path, "config.json")
        if not os.path.exists(config_path):
            with open(config_path, 'w') as f:
                json.dump({
                    "file_browser": "thunar",
                    "default_editor": "xdg-open",
                    "recent_files": [],
                    "settings": {}
                }, f, indent=2)
    
    def setup_ui(self):
        """Setup the main UI layout"""
        # Bottom panel - Controls (Created first so children can use status_bar during init)
        self.bottom_panel = tk.Frame(self, relief=tk.RAISED, borderwidth=1)
        self.bottom_panel.pack(fill=tk.X, side=tk.BOTTOM)
        
        # Status bar
        self.status_bar = tk.Label(self.bottom_panel, text="Initializing...", bd=1, relief=tk.SUNKEN, anchor=tk.W)
        self.status_bar.pack(fill=tk.X, side=tk.BOTTOM)

        # Main container
        main_container = tk.PanedWindow(self, orient=tk.HORIZONTAL, sashwidth=5)
        main_container.pack(fill=tk.BOTH, expand=True)
        
        # Left panel - Document display
        self.left_frame = tk.Frame(main_container, bg='white', relief=tk.SUNKEN, borderwidth=2)
        main_container.add(self.left_frame, width=600)
        
        # Current file path indicator
        self.file_path_label = tk.Label(
            self.left_frame, text="No file open", anchor='w',
            font=('Consolas', 8), fg='#555555', bg='#f0f0f0',
            relief=tk.FLAT, padx=4
        )
        self.file_path_label.pack(fill=tk.X, side=tk.TOP)

        # Project selector bar
        self._setup_project_bar(self.left_frame)

        # Document display area
        self.doc_display = scrolledtext.ScrolledText(
            self.left_frame,
            wrap=tk.WORD,
            font=('Consolas', 10),
            undo=True
        )
        self.doc_display.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Color tags for context-aware editing
        self.doc_display.tag_configure("field_filled",  foreground="#27ae60")
        self.doc_display.tag_configure("field_partial",  foreground="#e67e22")
        self.doc_display.tag_configure("field_missing",  foreground="#c0392b")
        self.doc_display.tag_configure("sec_header", foreground="#2980b9",
                                        font=('Consolas', 10, 'bold'))
        self.doc_display.tag_configure("hint_link",  foreground="#9b59b6", underline=True)
        self.doc_display.tag_configure("ctx_key",    foreground="#7f8c8d")
        self.doc_display.tag_configure("ctx_val_null", foreground="#c0392b")
        self.doc_display.bind("<Motion>", self._on_doc_hover)
        self.doc_display.bind("<Leave>",  lambda e: self._hide_tooltip())

        # Document controls
        doc_controls = tk.Frame(self.left_frame)
        doc_controls.pack(fill=tk.X, padx=5, pady=5)
        
        tk.Button(doc_controls, text="Save", command=self._on_doc_save_with_refresh).pack(side=tk.LEFT, padx=2)
        tk.Button(doc_controls, text="New", command=self.new_document).pack(side=tk.LEFT, padx=2)
        tk.Button(doc_controls, text="Clear", command=self.clear_document).pack(side=tk.LEFT, padx=2)
        
        # Right panel - Directory structure
        self.right_panel = tk.Frame(main_container)
        main_container.add(self.right_panel, width=300)
        
        # Create notebook for right panel tabs
        self.right_notebook = ttk.Notebook(self.right_panel)
        self.right_notebook.pack(fill=tk.BOTH, expand=True)
        
        # Directory structure tab
        self.dir_frame = tk.Frame(self.right_notebook)
        self.right_notebook.add(self.dir_frame, text="Structure")
        
        # Create treeview for directory structure
        self.tree_frame = tk.Frame(self.dir_frame)
        self.tree_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Add scrollbars
        tree_scroll_y = tk.Scrollbar(self.tree_frame)
        tree_scroll_y.pack(side=tk.RIGHT, fill=tk.Y)
        
        tree_scroll_x = tk.Scrollbar(self.tree_frame, orient=tk.HORIZONTAL)
        tree_scroll_x.pack(side=tk.BOTTOM, fill=tk.X)
        
        # Create treeview
        self.tree = ttk.Treeview(
            self.tree_frame,
            yscrollcommand=tree_scroll_y.set,
            xscrollcommand=tree_scroll_x.set,
            selectmode='browse'
        )
        self.tree.pack(fill=tk.BOTH, expand=True)
        
        tree_scroll_y.config(command=self.tree.yview)
        tree_scroll_x.config(command=self.tree.xview)
        
        # Configure tree columns
        self.tree["columns"] = ("type", "size", "full_path")
        self.tree.column("#0", width=200, minwidth=100)
        self.tree.column("type", width=60, minwidth=50)
        self.tree.column("size", width=80, minwidth=60)
        self.tree.column("full_path", width=0, stretch=tk.NO) # Hidden column
        
        self.tree.heading("#0", text="Name", anchor=tk.W)
        self.tree.heading("type", text="Type", anchor=tk.W)
        self.tree.heading("size", text="Size", anchor=tk.W)
        
        # Bind tree events
        self.tree.bind("<Double-1>", self.on_tree_double_click)
        self.tree.bind("<<TreeviewSelect>>", self.on_tree_select)
        self.tree.bind("<<TreeviewOpen>>", self._on_tree_open)
        self.tree.bind("<<TreeviewClose>>", self._on_tree_close)
        
        # Directory controls frame
        dir_controls = tk.Frame(self.dir_frame)
        dir_controls.pack(fill=tk.X, padx=5, pady=5)
        
        # Buttons for each directory — dynamically discover all subdirs in base_path
        self.dir_buttons = {}
        try:
            directories = sorted([
                d for d in os.listdir(self.base_path)
                if os.path.isdir(os.path.join(self.base_path, d)) and not d.startswith(".")
            ])
        except Exception:
            directories = ["Epics", "Plans", "Phases", "Tasks", "Milestones", "Diffs", "Refs"]
        
        for i, dir_name in enumerate(directories):
            btn_frame = tk.Frame(dir_controls)
            btn_frame.grid(row=i//2, column=i%2, sticky="ew", padx=2, pady=2)
            
            # Open in file browser button
            open_btn = tk.Button(
                btn_frame, 
                text=f"📂 {dir_name}",
                command=lambda d=dir_name: self.open_in_file_browser(d),
                width=15
            )
            open_btn.pack(side=tk.LEFT, padx=2)
            
            # Toggle button
            toggle_btn = tk.Button(
                btn_frame,
                text="▶",
                command=lambda d=dir_name: self.toggle_directory(d),
                width=3
            )
            toggle_btn.pack(side=tk.RIGHT, padx=2)
            self.dir_buttons[dir_name] = toggle_btn
        
        # Checklist tab (formerly "Marked Files")
        self.marked_frame = tk.Frame(self.right_notebook)
        self.right_notebook.add(self.marked_frame, text="✓ Checklist")
        
        # Ag Knowledge tab
        self.ag_frame = tk.Frame(self.right_notebook)
        self.right_notebook.add(self.ag_frame, text="Ag Knowledge")
        self.setup_ag_knowledge_ui()

        # Task Board tab — P0/P1/P2 task list with Mark Complete
        self.board_frame = tk.Frame(self.right_notebook)
        self.right_notebook.add(self.board_frame, text="📋 Tasks")
        self.setup_task_board_ui()

        # Latest Report tab — shows plans/Refs/latest_sync.json + Os_Toolkit latest
        self.latest_frame = tk.Frame(self.right_notebook)
        self.right_notebook.add(self.latest_frame, text="📊 Latest")
        self.setup_latest_report_ui()
        
        # ── Checklist: PanedWindow (tree top, detail bottom) ──
        cl_paned = tk.PanedWindow(self.marked_frame, orient=tk.VERTICAL, sashwidth=4)
        cl_paned.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)

        # Top: treeview + scroll
        cl_tree_frame = tk.Frame(cl_paned)
        cl_paned.add(cl_tree_frame, minsize=80)

        cl_cols = ("checked", "file", "type", "task_id", "project", "status", "changes")
        self.checklist_tree = ttk.Treeview(cl_tree_frame, columns=cl_cols, show="headings", height=10)
        _cl_heads = {"checked": "✓", "file": "File", "type": "Type", "task_id": "Task ID",
                      "project": "Project", "status": "Status", "changes": "🔗 Changes"}
        for col, w, anchor in [("checked", 38, "center"), ("file", 140, "w"),
                                ("type", 55, "center"), ("task_id", 75, "w"),
                                ("project", 90, "w"),
                                ("status", 70, "center"), ("changes", 55, "center")]:
            self.checklist_tree.heading(col, text=_cl_heads[col])
            self.checklist_tree.column(col, width=w, anchor=anchor, stretch=(col == "file"))
        cl_scroll = ttk.Scrollbar(cl_tree_frame, orient="vertical", command=self.checklist_tree.yview)
        self.checklist_tree.configure(yscrollcommand=cl_scroll.set)
        self.checklist_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        cl_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.checklist_tree.bind("<Double-1>", self._on_checklist_double_click)
        self.checklist_tree.bind("<<TreeviewSelect>>", self._on_checklist_select)
        self.checklist_tree.tag_configure("done", foreground="#27ae60")
        self.checklist_tree.tag_configure("confirmed", foreground="#27ae60", font=('Consolas', 9, 'bold'))
        self.checklist_tree.tag_configure("denied", foreground="#c0392b")
        self.checklist_tree.tag_configure("alert", foreground="#e67e22")
        self.checklist_tree.tag_configure("linked", foreground="#2980b9")
        self.checklist_tree.tag_configure("check", foreground="#9b59b6", font=('Consolas', 9, 'bold'))
        self.checklist_tree.tag_configure("test_pass", foreground="#27ae60", font=('Consolas', 9, 'bold'))
        self.checklist_tree.tag_configure("test_fail", foreground="#e74c3c")
        self.checklist_tree.tag_configure("test_pending", foreground="#3498db")

        # Control buttons
        cl_ctrl = tk.Frame(cl_tree_frame)
        cl_ctrl.pack(fill=tk.X, padx=2, pady=(2, 0))
        tk.Button(cl_ctrl, text="☑ Check", command=self._checklist_toggle_check, font=('Consolas', 8)).pack(side=tk.LEFT, padx=1)
        tk.Button(cl_ctrl, text="🔗 Link Task", command=self._checklist_link_task, font=('Consolas', 8)).pack(side=tk.LEFT, padx=1)
        tk.Button(cl_ctrl, text="✅ Confirm", command=self._checklist_confirm, font=('Consolas', 8)).pack(side=tk.LEFT, padx=1)
        tk.Button(cl_ctrl, text="❌ Deny", command=self._checklist_deny, font=('Consolas', 8)).pack(side=tk.LEFT, padx=1)
        tk.Button(cl_ctrl, text="📎 Link Plan", command=self._checklist_link_plan, font=('Consolas', 8)).pack(side=tk.LEFT, padx=1)
        tk.Button(cl_ctrl, text="+ Add", command=self._checklist_add_file, font=('Consolas', 8)).pack(side=tk.LEFT, padx=1)
        tk.Button(cl_ctrl, text="🗑", command=self._checklist_remove, font=('Consolas', 8)).pack(side=tk.LEFT, padx=1)
        tk.Button(cl_ctrl, text="🔄", command=self._refresh_checklist_tab, font=('Consolas', 8)).pack(side=tk.LEFT, padx=1)
        # CLI menu (right side)
        cli_menu = tk.Menubutton(cl_ctrl, text="⚡ CLI", relief=tk.RAISED, font=('Consolas', 8))
        cli_menu.pack(side=tk.RIGHT, padx=2)
        _cli_m = tk.Menu(cli_menu, tearoff=0)
        cli_menu["menu"] = _cli_m
        _cli_m.add_command(label="Sync Marks", command=self._cli_sync_marks)
        _cli_m.add_command(label="Sync All Todos", command=self._cli_sync_all_todos)
        _cli_m.add_command(label="Consolidate Plans", command=self._cli_consolidate_plans)
        _cli_m.add_command(label="View Latest Report", command=self._cli_latest_report)

        # Bottom: detail panel
        cl_detail_frame = tk.Frame(cl_paned)
        cl_paned.add(cl_detail_frame, minsize=60)

        # Navigation buttons bar
        self._cl_nav_frame = tk.Frame(cl_detail_frame)
        self._cl_nav_frame.pack(fill=tk.X, padx=2, pady=(2, 0))
        self._cl_nav_open_btn = tk.Button(self._cl_nav_frame, text="📄 Open Plan", command=self._checklist_open_plan,
                                          font=('Consolas', 8), state=tk.DISABLED)
        self._cl_nav_open_btn.pack(side=tk.LEFT, padx=2)
        self._cl_nav_goto_btn = tk.Button(self._cl_nav_frame, text="📋 Go to Task", command=self._checklist_goto_task,
                                          font=('Consolas', 8), state=tk.DISABLED)
        self._cl_nav_goto_btn.pack(side=tk.LEFT, padx=2)
        tk.Label(self._cl_nav_frame, text="Item Details", font=('Consolas', 8, 'bold'), fg='#555').pack(side=tk.LEFT, padx=6)

        self.cl_detail_text = tk.Text(cl_detail_frame, height=6, wrap=tk.WORD, state='disabled',
                                       font=('Consolas', 9), bg='#1e1e1e', fg='#d4d4d4',
                                       insertbackground='white', selectbackground='#264f78')
        self.cl_detail_text.pack(fill=tk.BOTH, expand=True, padx=2, pady=(0, 2))

        self._checklist_full_data = {}
        self._cl_selected_plan_doc = None
        self._cl_selected_task_id = None
        self.after(400, self._refresh_checklist_tab)
        
        # Context controls
        context_frame = tk.LabelFrame(self.bottom_panel, text="Context & Tasking", padx=5, pady=5)
        context_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # Global Search (Os_Toolkit) - Right side of Context Frame
        search_frame = tk.Frame(context_frame)
        search_frame.pack(side=tk.RIGHT, padx=5)
        tk.Label(search_frame, text="🔍 Search Knowledge:").pack(side=tk.LEFT)
        self.global_search_entry = tk.Entry(search_frame, width=20)
        self.global_search_entry.pack(side=tk.LEFT, padx=5)
        self.global_search_entry.bind("<Return>", self._on_global_search)
        tk.Button(search_frame, text="Go", command=self._on_global_search).pack(side=tk.LEFT)

        # Context entry
        tk.Label(context_frame, text="Context:").pack(side=tk.LEFT, padx=2)
        self.context_entry = tk.Entry(context_frame, width=40)
        self.context_entry.pack(side=tk.LEFT, padx=2, fill=tk.X, expand=True)
        
        tk.Button(context_frame, text="Add to Task", command=self.add_to_task).pack(side=tk.LEFT, padx=2)
        tk.Button(context_frame, text="Compile Summary", command=self.compile_summary).pack(side=tk.LEFT, padx=2)
        
        # Diff controls
        diff_frame = tk.LabelFrame(self.bottom_panel, text="Diff Controls", padx=5, pady=5)
        diff_frame.pack(fill=tk.X, padx=5, pady=5)
        
        tk.Label(diff_frame, text="Add lines to diff:").pack(side=tk.LEFT, padx=2)
        self.diff_entry = tk.Entry(diff_frame, width=50)
        self.diff_entry.pack(side=tk.LEFT, padx=2, fill=tk.X, expand=True)
        
        tk.Button(diff_frame, text="Add Diff", command=self.add_diff_lines).pack(side=tk.LEFT, padx=2)
        tk.Button(diff_frame, text="Scroll Marked", command=self.scroll_marked_files).pack(side=tk.LEFT, padx=2)
        
        # Task watcher controls
        watcher_frame = tk.Frame(self.bottom_panel)
        watcher_frame.pack(fill=tk.X, padx=5, pady=5)
        
        _watcher_on = self._load_planner_state().get("task_watcher", True)
        self.watcher_var = tk.BooleanVar(value=_watcher_on)
        tk.Checkbutton(watcher_frame, text="Task Watcher", variable=self.watcher_var,
                      command=self.toggle_watcher).pack(side=tk.LEFT, padx=5)
        
        tk.Button(watcher_frame, text="Check Completion", command=self.check_completion).pack(side=tk.LEFT, padx=5)
        tk.Button(watcher_frame, text="Generate Report", command=self.generate_report).pack(side=tk.LEFT, padx=5)
        tk.Button(watcher_frame, text="🔄 Sync Todos", command=self.sync_todos).pack(side=tk.LEFT, padx=5)
        tk.Button(watcher_frame, text="📦 Consolidate Plans", command=self.consolidate_plans).pack(side=tk.LEFT, padx=5)
        
        self.status_bar.config(text="Ready")
        # Auto-start Task Watcher if saved state was ON (or default ON on first launch)
        if self.watcher_var.get():
            self.after(500, self.start_watcher)

    def send_to_editor(self):
        """Gather content from marked files and send to the Edit & Process tab."""
        if not self.marked_files:
            messagebox.showwarning("No Files", "No files are marked. Please mark one or more files to send to the editor.")
            return

        full_content = []
        for file_path in self.marked_files:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                full_content.append(f"--- START OF FILE: {os.path.basename(file_path)} ---\n\n{content}\n\n--- END OF FILE: {os.path.basename(file_path)} ---")
            except Exception as e:
                full_content.append(f"--- ERROR READING FILE: {os.path.basename(file_path)} ---\n\n{str(e)}\n\n--- END OF FILE: {os.path.basename(file_path)} ---")
        
        combined_content = "\n\n".join(full_content)
        
        # Use the app reference to access the other tab
        self.app.edit_text.delete('1.0', tk.END)
        self.app.edit_text.insert('1.0', combined_content)
        self.app.notebook.select(self.app.edit_frame) # Switch to the edit tab

    def load_directory_structure(self):
        """Load the directory structure into the treeview with lazy-expand support."""
        for item in self.tree.get_children():
            self.tree.delete(item)

        root = self.tree.insert("", "end", text=os.path.basename(self.base_path),
                               values=("Folder", "", self.base_path), open=True)

        try:
            all_entries = sorted(os.listdir(self.base_path))
        except Exception:
            all_entries = []
        for entry in all_entries:
            dir_path = os.path.join(self.base_path, entry)
            if not os.path.isdir(dir_path) or entry.startswith("."):
                continue
            try:
                count = len(os.listdir(dir_path))
            except Exception:
                count = 0
            size_hint = f"{count} items" if count else "empty"
            node = self.tree.insert(root, "end", text=entry,
                                    values=("Folder", size_hint, dir_path))
            # Virtual child so the ▶ expand arrow appears
            if count:
                self.tree.insert(node, "end", text="__loading__", values=("", "", ""))
    
    def toggle_directory(self, dir_name):
        """Expand or collapse a directory in the tree"""
        dir_path = os.path.join(self.base_path, dir_name)
        
        # Find the directory item in the tree
        for item in self.tree.get_children(self.tree.get_children()[0]): # Search under the root node
            if self.tree.item(item, "text") == dir_name:
                if self.tree.item(item, "open"):
                    # Clear children before closing
                    for child in self.tree.get_children(item):
                        self.tree.delete(child)
                    self.tree.item(item, open=False)
                    self.dir_buttons[dir_name].config(text="▶")
                else:
                    self.expand_directory(item, dir_path)
                    self.dir_buttons[dir_name].config(text="▼")
                break
    
    def _on_tree_open(self, event):
        """Lazy-load children when a tree node is expanded via the treeview arrow."""
        node = self.tree.focus()
        if not node:
            return
        children = self.tree.get_children(node)
        # Replace virtual __loading__ child with real contents
        if len(children) == 1 and self.tree.item(children[0], "text") == "__loading__":
            self.tree.delete(children[0])
            vals = self.tree.item(node, "values")
            if vals and len(vals) > 2 and vals[2] and os.path.isdir(vals[2]):
                self.expand_directory(node, vals[2])
                # Sync toggle button if this is a top-level plans dir
                dir_name = self.tree.item(node, "text")
                if dir_name in self.dir_buttons:
                    self.dir_buttons[dir_name].config(text="▼")

    def _on_tree_close(self, event):
        """Collapse handler — replace children with virtual placeholder."""
        node = self.tree.focus()
        if not node:
            return
        dir_name = self.tree.item(node, "text")
        vals = self.tree.item(node, "values")
        if vals and len(vals) > 2 and vals[2] and os.path.isdir(vals[2]):
            for child in self.tree.get_children(node):
                self.tree.delete(child)
            # Restore virtual child so it can be re-expanded
            self.tree.insert(node, "end", text="__loading__", values=("", "", ""))
            if dir_name in self.dir_buttons:
                self.dir_buttons[dir_name].config(text="▶")

    def expand_directory(self, parent_id, dir_path):
        """Expand a directory to show its contents (files + subdirs)."""
        try:
            entries = sorted(os.listdir(dir_path))
            # Subdirectories first, then files
            for item_name in entries:
                item_path = os.path.join(dir_path, item_name)
                if os.path.isdir(item_path):
                    count = len(os.listdir(item_path))
                    sub_node = self.tree.insert(parent_id, "end", text=f"📁 {item_name}",
                                                values=("Folder", f"{count} items", item_path))
                    if count:
                        self.tree.insert(sub_node, "end", text="__loading__", values=("", "", ""))
            for item_name in entries:
                item_path = os.path.join(dir_path, item_name)
                if os.path.isfile(item_path):
                    size = os.path.getsize(item_path)
                    size_str = f"{size/1024:.1f}KB" if size > 1024 else f"{size}B"
                    if item_name.endswith('.json'):
                        file_type = "JSON"
                    elif item_name.endswith('.md'):
                        file_type = "Markdown"
                    elif item_name.endswith('.txt'):
                        file_type = "Text"
                    elif item_name.endswith('.py'):
                        file_type = "Python"
                    else:
                        file_type = "File"
                    self.tree.insert(parent_id, "end", text=item_name,
                                     values=(file_type, size_str, item_path))
            self.tree.item(parent_id, open=True)
        except Exception as e:
            messagebox.showerror("Error", f"Could not load directory: {e}")
    
    def on_tree_double_click(self, event):
        """Handle double-click on tree items"""
        if not self.tree.selection():
            return
        item_id = self.tree.selection()[0]
        item_values = self.tree.item(item_id, "values")
        
        # The full_path is the 3rd value (index 2)
        if item_values and len(item_values) > 2 and item_values[2]:
            path = item_values[2]
            if os.path.isfile(path):
                self.open_file(path)
    
    def on_tree_select(self, event):
        """Handle selection in tree — opens file on single-click."""
        if not self.tree.selection():
            return
        item_id = self.tree.selection()[0]
        item_values = self.tree.item(item_id, "values")

        if item_values and len(item_values) > 2 and item_values[2]:
            path = item_values[2]
            if os.path.isfile(path):
                self.open_file(path)
            else:
                self.status_bar.config(text=f"📁 {os.path.basename(path)}")
    
    def open_file(self, file_path):
        """Open a file in the document display"""
        try:
            with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read()

            self.doc_display.delete(1.0, tk.END)
            self.doc_display.insert(1.0, content)

            # Update Ag Knowledge links
            self.update_ag_knowledge_links(content)

            # Store current file info
            self.current_file = file_path

            # Update path indicator label
            rel = os.path.relpath(file_path, self.base_path)
            size_kb = os.path.getsize(file_path) / 1024
            lines = content.count('\n')
            self.file_path_label.config(text=f"📄 {rel}  ({size_kb:.1f} KB, {lines} lines)")

            self.status_bar.config(text=f"Opened: {os.path.basename(file_path)}")

            # Set edit mode based on file type
            self._current_edit_mode = "task_context" if file_path.endswith(".json") and "task_context" in os.path.basename(file_path) else "epic"
            self._current_edit_tid = None
            # Colorize content for known file types
            if file_path.endswith(".md"):
                self.after(50, self._colorize_epic_display)

            if _TRAINER_LOG_AVAILABLE:
                _trainer_log.log_ux_event(
                    "ag_knowledge", "OPEN_FILE", "planner_tree",
                    outcome="success",
                    detail=f"Opened: {rel} ({lines} lines)",
                    wherein="PlannerSuite::open_file"
                )
        except Exception as e:
            self.status_bar.config(text=f"Error opening file: {e}")
            messagebox.showerror("Error", f"Could not open file: {e}")
    
    def save_document(self):
        """Save the current document"""
        if hasattr(self, 'current_file'):
            content = self.doc_display.get(1.0, tk.END)
            try:
                with open(self.current_file, 'w') as f:
                    f.write(content)
                self.status_bar.config(text=f"Saved: {os.path.basename(self.current_file)}")
            except Exception as e:
                messagebox.showerror("Error", f"Could not save file: {e}")
        else:
            # Save as new file
            self.save_as_document()
    
    def save_as_document(self):
        """Save document as new file"""
        file_types = [
            ("Text files", "*.txt"),
            ("Markdown files", "*.md"),
            ("JSON files", "*.json"),
            ("Python files", "*.py"),
            ("All files", "*.*")
        ]
        
        file_path = filedialog.asksaveasfilename(
            initialdir=self.base_path,
            defaultextension=".txt",
            filetypes=file_types
        )
        
        if file_path:
            content = self.doc_display.get(1.0, tk.END)
            try:
                with open(file_path, 'w') as f:
                    f.write(content)
                
                self.current_file = file_path
                self.status_bar.config(text=f"Saved as: {os.path.basename(file_path)}")
                
                # Refresh tree if in our structure
                if self.base_path in file_path:
                    self.load_directory_structure()
            except Exception as e:
                messagebox.showerror("Error", f"Could not save file: {e}")
    
    def new_document(self):
        """Create a new document"""
        self.doc_display.delete(1.0, tk.END)
        self.current_file = None
        self.status_bar.config(text="New document")
    
    def clear_document(self):
        """Clear the document display"""
        if messagebox.askyesno("Clear", "Clear current document?"):
            self.doc_display.delete(1.0, tk.END)
    
    def open_in_file_browser(self, dir_name):
        """Open directory in native file browser"""
        dir_path = os.path.join(self.base_path, dir_name)
        
        try:
            # Try thunar first, then xdg-open as fallback
            subprocess.Popen(['thunar', dir_path])
        except:
            try:
                subprocess.Popen(['xdg-open', dir_path])
            except Exception as e:
                messagebox.showerror("Error", f"Could not open file browser: {e}")
    
    def mark_files(self):
        """Mark files for diff analysis"""
        file_types = [
            ("Python files", "*.py"),
            ("Text files", "*.txt"),
            ("Markdown files", "*.md"),
            ("All files", "*.*")
        ]
        
        files = filedialog.askopenfilenames(
            title="Select files to mark",
            filetypes=file_types
        )
        
        for file_path in files:
            if file_path not in self.marked_files:
                self.marked_files.append(file_path)
                if hasattr(self, 'checklist_tree'):
                    iid = f"watch_{hashlib.md5(file_path.encode()).hexdigest()[:8]}"
                    if not self.checklist_tree.exists(iid):
                        self.checklist_tree.insert("", "end", iid=iid,
                            values=("☐", os.path.basename(file_path), "WATCH", "", "", "PENDING", ""))
        
        self.status_bar.config(text=f"Marked {len(files)} files")
    
    def remove_marked(self):
        """Remove selected files from marked list"""
        self._checklist_remove()

    # ── Checklist tab helpers ──────────────────────────────────────────────────

    def _load_checklist_items(self):
        """Load items from checklist.json + task_context_*.json (checklist_candidate=True).
        Includes 'changes' count from enriched_changes task_ids back-links."""
        items = {}

        # Pre-load enriched_changes for task_ids back-link counts
        _ec_by_task = {}  # {task_id: count of linked enriched_change events}
        try:
            _data_root = Path(__file__).parents[5]
            _mp = _data_root / "backup" / "version_manifest.json"
            if _mp.exists():
                with open(_mp, encoding="utf-8") as _f:
                    _vm = json.load(_f)
                for _eid, _ch in _vm.get("enriched_changes", {}).items():
                    for _tid in _ch.get("task_ids", []):
                        _ec_by_task[_tid] = _ec_by_task.get(_tid, 0) + 1
        except Exception:
            pass

        # 1. checklist.json
        cl_path = Path(self.base_path) / "checklist.json"
        try:
            if cl_path.exists():
                with open(cl_path, encoding="utf-8") as f:
                    cl = json.load(f)
                for section_key, section in cl.items():
                    if not isinstance(section, dict):
                        continue
                    for item in section.get("items", []):
                        iid = str(item.get("id") or item.get("title", "")[:30])
                        if not iid:
                            continue
                        wherein = item.get("wherein", "")
                        items[iid] = {
                            "id": iid,
                            "file": os.path.basename(wherein) if wherein else "",
                            "type": "MODIFY" if wherein else "NEW",
                            "task_id": iid,
                            "status": item.get("status", "PENDING"),
                            "checked": item.get("status") in ("COMPLETE", "RESOLVED", "DONE"),
                            "changes": _ec_by_task.get(iid, 0),
                            # Full data for detail panel
                            "title": item.get("title", ""),
                            "what": item.get("what", ""),
                            "description": item.get("description", ""),
                            "acceptance": item.get("acceptance", ""),
                            "wherein": wherein,
                            "plan_doc": item.get("plan_doc", ""),
                            "project_id": item.get("project_id", ""),
                            "project_ref": item.get("project_ref", ""),
                            "test_expectations": item.get("test_expectations", []),
                            "effort": item.get("effort", ""),
                            "priority": item.get("priority", ""),
                            "source": f"checklist:{section_key}",
                        }
        except Exception:
            pass

        # 2. aoe_inbox alerts from checklist.json (D3 live-watcher notifications)
        #    Grouped by task_id to avoid flooding the tree with 200+ individual rows
        # Pre-load project_ids from latest_sync for cross-referencing aoe_inbox
        _task_projects = {}  # {task_id: project_id}
        try:
            _ls_path = Path(self.base_path) / "Refs" / "latest_sync.json"
            if _ls_path.exists():
                with open(_ls_path, encoding="utf-8") as _f:
                    _ls = json.load(_f)
                for _t in _ls.get("tasks", []):
                    _pid = _t.get("project_id", "")
                    if _pid and _t.get("id"):
                        _task_projects[_t["id"]] = _pid
        except Exception:
            pass
        try:
            if cl_path.exists():
                with open(cl_path, encoding="utf-8") as f:
                    cl_aoe = json.load(f)
                _inbox_by_task = {}  # {task_id: [entries]}
                for entry in cl_aoe.get("aoe_inbox", []):
                    tid = entry.get("task_id", "") or "unlinked"
                    _inbox_by_task.setdefault(tid, []).append(entry)
                for tid, entries in _inbox_by_task.items():
                    iid = f"aoe_summary_{tid}"
                    if iid not in items:
                        risk_counts = {}
                        for e in entries:
                            rl = e.get("risk_level", "LOW")
                            risk_counts[rl] = risk_counts.get(rl, 0) + 1
                        risk_str = ", ".join(f"{v} {k}" for k, v in sorted(risk_counts.items()))
                        items[iid] = {
                            "id": iid,
                            "file": f"{len(entries)} changes",
                            "type": "ALERT",
                            "task_id": tid,
                            "project_id": _task_projects.get(tid, ""),
                            "status": "ALERT",
                            "checked": False,
                            "changes": len(entries),
                            "title": f"{len(entries)} file changes for {tid} ({risk_str})",
                            "_inbox_entries": entries,  # Preserve for detail panel
                        }
        except Exception:
            pass

        # 3. task_context_*.json (watcher alert candidates)
        tasks_dir = Path(self.base_path) / "Tasks"
        if tasks_dir.exists():
            for ctx_file in sorted(tasks_dir.glob("task_context_*.json"), reverse=True)[:50]:
                try:
                    with open(ctx_file, encoding="utf-8") as f:
                        ctx = json.load(f)
                    if not ctx.get("checklist_candidate"):
                        continue
                    iid = ctx_file.stem
                    if iid not in items:
                        wherein = ctx.get("wherein", "")
                        items[iid] = {
                            "id": iid,
                            "file": os.path.basename(wherein) if wherein else ctx.get("event_type", ""),
                            "type": "WATCH",
                            "task_id": "",
                            "status": ctx.get("status", "OPEN"),
                            "checked": ctx.get("status") in ("RESOLVED", "DONE"),
                            "changes": _ec_by_task.get(iid, 0),
                        }
                except Exception:
                    pass

        # 3b. Per-expectation TEST rows from task_context test_expectations
        if tasks_dir.exists():
            for _ctx_file in sorted(tasks_dir.glob("task_context_*.json"), reverse=True)[:50]:
                try:
                    with open(_ctx_file, encoding="utf-8") as _f_te:
                        _ctx_te = json.load(_f_te)
                except Exception:
                    continue
                _texp = _ctx_te.get("test_expectations", [])
                if not _texp:
                    continue
                _meta_te = _ctx_te.get("_meta", {})
                _tid_te = _meta_te.get("task_id", _ctx_file.stem)
                _tresults = {r.get("test", ""): r.get("result", "pending")
                             for r in _ctx_te.get("test_results", [])
                             if isinstance(r, dict)}
                for _i_te, _exp in enumerate(_texp):
                    _test_iid = f"test_{_tid_te}_{_i_te}"
                    if _test_iid in items:
                        continue
                    _exp_result = _tresults.get(_exp, "pending")
                    _st_te = ("COMPLETE" if _exp_result == "PASS"
                              else "DENIED" if _exp_result == "FAIL"
                              else "PENDING")
                    items[_test_iid] = {
                        "id": _test_iid,
                        "file": f"○ {_exp[:55]}" if _st_te == "PENDING" else f"✓ {_exp[:55]}",
                        "type": "TEST",
                        "task_id": _tid_te,
                        "project_id": _ctx_te.get("project_ref", ""),
                        "status": _st_te,
                        "checked": _exp_result == "PASS",
                        "changes": 0,
                        "plan_doc": _ctx_te.get("plan_doc", ""),
                        "test_expectation": _exp,
                        "parent_task": _tid_te,
                        "wherein": _meta_te.get("wherein", ""),
                    }

        # 4. Dynamic system check row (always first)
        _check_msgs = []
        try:
            _cfg_path = Path(self.base_path) / "config.json"
            if _cfg_path.exists():
                _cfg = json.loads(_cfg_path.read_text(encoding="utf-8"))
                _atid = _cfg.get("active_task_id", "")
                _lat = _cfg.get("last_activity_at", "")
                if _atid and _lat:
                    _delta = (datetime.datetime.now() - datetime.datetime.fromisoformat(_lat)).total_seconds() / 3600
                    if _delta > 2:
                        _check_msgs.append(f"Task {_atid} idle {_delta:.0f}h")
            # Unresolved probes
            _mp_chk = Path(__file__).parents[5] / "backup" / "version_manifest.json"
            if _mp_chk.exists():
                with open(_mp_chk, encoding="utf-8") as _f_chk:
                    _vm_chk = json.load(_f_chk)
                _unresp = sum(1 for ch in _vm_chk.get("enriched_changes", {}).values()
                              if ch.get("probe_status") == "FAIL" and not ch.get("resolved_by"))
                if _unresp:
                    _check_msgs.append(f"{_unresp} probe FAIL")
        except Exception:
            pass
        if _check_msgs:
            items["_system_check"] = {
                "id": "_system_check",
                "file": " | ".join(_check_msgs),
                "type": "CHECK",
                "task_id": "",
                "project_id": "",
                "status": "REVIEW",
                "checked": False,
                "changes": 0,
                "title": f"System: {' | '.join(_check_msgs)}",
            }

        return list(items.values())

    def _refresh_checklist_tab(self):
        """Reload checklist treeview from checklist.json + watcher task_context files."""
        if not hasattr(self, 'checklist_tree'):
            return
        for row in self.checklist_tree.get_children():
            self.checklist_tree.delete(row)
        self._checklist_full_data = {}
        for it in self._load_checklist_items():
            self._checklist_full_data[it["id"]] = it
            chk = "☑" if it.get("checked") else "☐"
            fname = it.get("file", "")
            n_ch = it.get("changes", 0)
            ch_disp = str(n_ch) if n_ch else ""
            # Determine tag
            status = it.get("status", "")
            if it.get("checked") or status == "COMPLETE":
                tags = ("done",)
            elif status == "CONFIRMED":
                tags = ("confirmed",)
            elif status == "DENIED":
                tags = ("denied",)
            elif it.get("type") == "ALERT":
                tags = ("alert",)
            elif it.get("type") == "CHECK":
                tags = ("check",)
            elif it.get("type") == "TEST":
                tags = ("test_pass",) if status == "COMPLETE" else ("test_fail",) if status == "DENIED" else ("test_pending",)
            elif it.get("plan_doc"):
                tags = ("linked",)
            else:
                tags = ()
            proj = it.get("project_id", "")
            self.checklist_tree.insert("", "end", iid=it["id"],
                values=(chk, fname, it.get("type", ""), it.get("task_id", ""),
                        proj, status, ch_disp), tags=tags)

    def _checklist_toggle_check(self):
        """Toggle checked state of selected checklist rows; persist to checklist.json."""
        if not hasattr(self, 'checklist_tree'):
            return
        for iid in self.checklist_tree.selection():
            vals = list(self.checklist_tree.item(iid, "values"))
            is_checked = vals[0] == "☑"
            new_checked = not is_checked
            vals[0] = "☑" if new_checked else "☐"
            new_status = "COMPLETE" if new_checked else "PENDING"
            vals[5] = new_status  # status column (index: checked=0, file=1, type=2, task_id=3, project=4, status=5, changes=6)
            self.checklist_tree.item(iid, values=vals, tags=("done",) if new_checked else ())
            task_id = vals[3]
            if task_id:
                self._update_checklist_task(task_id, new_status)

    def _checklist_link_task(self):
        """Prompt for a task_id and link it to the selected checklist row."""
        if not hasattr(self, 'checklist_tree'):
            return
        sel = self.checklist_tree.selection()
        if not sel:
            messagebox.showinfo("Link Task", "Select a checklist row first.")
            return
        iid = sel[0]
        dlg = tk.Toplevel(self)
        dlg.title("Link Task ID")
        dlg.geometry("320x90")
        dlg.resizable(False, False)
        tk.Label(dlg, text="Task ID to link:").pack(pady=(10, 2))
        entry = tk.Entry(dlg, width=30)
        entry.pack(pady=2)
        entry.focus()
        def _do_link():
            tid = entry.get().strip()
            if tid:
                vals = list(self.checklist_tree.item(iid, "values"))
                vals[3] = tid
                self.checklist_tree.item(iid, values=vals)
            dlg.destroy()
        tk.Button(dlg, text="Link", command=_do_link).pack(pady=5)
        dlg.bind("<Return>", lambda e: _do_link())

    def _checklist_add_file(self):
        """Open file dialog and add file to checklist as a WATCH item (also marks for watcher)."""
        paths = filedialog.askopenfilenames(title="Add File to Checklist")
        for fpath in paths:
            basename = os.path.basename(fpath)
            iid = f"watch_{hashlib.md5(fpath.encode()).hexdigest()[:8]}"
            if hasattr(self, 'checklist_tree') and not self.checklist_tree.exists(iid):
                self.checklist_tree.insert("", "end", iid=iid,
                    values=("☐", basename, "WATCH", "", "", "PENDING", ""))
            if fpath not in self.marked_files:
                self.marked_files.append(fpath)

    def _checklist_remove(self):
        """Remove selected rows from checklist treeview."""
        if not hasattr(self, 'checklist_tree'):
            return
        for iid in self.checklist_tree.selection():
            self.checklist_tree.delete(iid)

    def _on_checklist_double_click(self, event):
        """Toggle check on double-click; if click is on the '🔗 Changes' column, open UndoChangesDialog."""
        if not hasattr(self, 'checklist_tree'):
            return
        col = self.checklist_tree.identify_column(event.x)
        # column #6 = "changes" (1-indexed in ttk)
        if col == "#6":
            sel = self.checklist_tree.selection()
            if not sel:
                return
            iid = sel[0]
            vals = self.checklist_tree.item(iid, "values")
            task_id = vals[3] if vals and len(vals) > 3 else ""
            file_name = vals[1] if vals and len(vals) > 1 else ""
            if not task_id and not file_name:
                return
            try:
                import sys as _sys, os as _os2
                _here2 = _os2.path.dirname(__file__)
                _sys.path.insert(0, _os2.join(_here2, "..", "..", "..", "..", ".."))
                from tabs.settings_tab.undo_changes import UndoChangesDialog
                import recovery_util as _ru2
                _manifest2 = _ru2.load_version_manifest()
                _ec2 = _manifest2.get("enriched_changes", {})
                # Find most recent event linked to this task_id or file
                matching = [
                    eid for eid, ch in _ec2.items()
                    if (task_id and task_id in ch.get("task_ids", []))
                    or (file_name and _os2.path.basename(ch.get("file", "")) == file_name)
                ]
                if not matching:
                    self.status_bar.config(text=f"No linked changes found for {task_id or file_name}")
                    return
                latest = max(matching, key=lambda x: x)
                UndoChangesDialog(self.parent, latest, _manifest2, initial_tab="blame_risk")
            except Exception as _e:
                self.status_bar.config(text=f"Cannot open dialog: {_e}")
            return
        # Default: toggle check
        self._checklist_toggle_check()

    def _checklist_append_row(self, file="", ftype="WATCH", status="PENDING", task_id=""):
        """Append a new row to the checklist treeview (safe to call from watcher via self.after)."""
        if not hasattr(self, 'checklist_tree'):
            return
        basename = os.path.basename(file) if file else ""
        iid = f"watch_{hashlib.md5(file.encode()).hexdigest()[:8]}" if file else \
              f"watch_{datetime.datetime.now().strftime('%H%M%S%f')}"
        if not self.checklist_tree.exists(iid):
            self.checklist_tree.insert("", "end", iid=iid,
                values=("☐", basename, ftype, task_id, "", status, ""))
        self.status_bar.config(text=f"Watcher: change detected in {basename}")

    # ── Checklist Detail Panel + Confirm/Deny/Link/Navigate ──────────────────

    def _on_checklist_select(self, event=None):
        """Show full item details in the detail panel when a checklist row is selected."""
        if not hasattr(self, 'checklist_tree') or not hasattr(self, 'cl_detail_text'):
            return
        sel = self.checklist_tree.selection()
        if not sel:
            return
        iid = sel[0]
        full = getattr(self, '_checklist_full_data', {}).get(iid, {})

        # If not cached, try to look up from checklist.json / todos.json
        if not full.get("title") and not full.get("what"):
            full = self._lookup_item_detail(iid) or full

        # Build detail text
        lines = []
        title = full.get("title") or iid
        lines.append(f"{'─'*50}")
        lines.append(f"  {title}")
        lines.append(f"{'─'*50}")

        # Show individual aoe_inbox entries for ALERT summary rows
        _inbox_entries = full.get("_inbox_entries", [])
        if _inbox_entries:
            lines.append(f"\nChange Events ({len(_inbox_entries)}):")
            for _ie in sorted(_inbox_entries, key=lambda x: x.get('timestamp', ''), reverse=True)[:10]:
                _ts = _ie.get('timestamp', '')[:16]
                _verb = _ie.get('verb', '?')
                _risk = _ie.get('risk_level', '?')
                _fname = os.path.basename(_ie.get('file', '?'))
                _eid = _ie.get('event_id', '')
                _gap = " [ATTRIBUTION_GAP]" if _ie.get('status') == 'ATTRIBUTION_GAP' else ""
                lines.append(f"  {_ts} | {_verb:8s} | {_risk:8s} | {_fname} {_eid}{_gap}")
            if len(_inbox_entries) > 10:
                lines.append(f"  ... +{len(_inbox_entries) - 10} more")
            lines.append("")

        if full.get("priority"):
            lines.append(f"Priority:    {full['priority']}    Effort: {full.get('effort', '?')}")
        if full.get("status"):
            lines.append(f"Status:      {full['status']}")
        if full.get("wherein"):
            lines.append(f"Wherein:     {full['wherein']}")
        if full.get("source"):
            lines.append(f"Source:      {full['source']}")
        if full.get("what"):
            lines.append(f"\nWhat:\n  {full['what']}")
        if full.get("description"):
            lines.append(f"\nDescription:\n  {full['description']}")
        if full.get("acceptance"):
            lines.append(f"\nAcceptance:\n  {full['acceptance']}")
        if full.get("plan_doc"):
            lines.append(f"\nPlan Doc:    {full['plan_doc']}")
        if full.get("project_id"):
            lines.append(f"Project:     {full['project_id']}")
        if full.get("project_ref"):
            lines.append(f"Project Ref: {full['project_ref']}")
        if full.get("test_expectations"):
            te = full["test_expectations"]
            if isinstance(te, list):
                lines.append(f"\nTest Expectations ({len(te)}):")
                for t in te:
                    lines.append(f"  • {t}")
        n_changes = full.get("changes", 0)
        if n_changes:
            lines.append(f"\nLinked Changes: {n_changes}")

        # Check for task_context file
        ctx_path = Path(self.base_path) / "Tasks" / f"task_context_{iid}.json"
        if ctx_path.exists():
            try:
                ctx = json.loads(ctx_path.read_text(encoding="utf-8"))
                if ctx.get("expected_diffs"):
                    lines.append(f"\nExpected Diffs ({len(ctx['expected_diffs'])}):")
                    for d in ctx["expected_diffs"][:5]:
                        lines.append(f"  {d.get('type','?')} {d.get('file','?')}")
                if ctx.get("blame"):
                    lines.append(f"\nBlame Entries: {len(ctx['blame'])}")
            except Exception:
                pass

        # Update detail text
        self._show_detail("\n".join(lines))

        # Update nav buttons
        self._cl_selected_plan_doc = full.get("plan_doc") or None
        self._cl_selected_task_id = full.get("task_id") or iid
        if hasattr(self, '_cl_nav_open_btn'):
            self._cl_nav_open_btn.config(state=tk.NORMAL if self._cl_selected_plan_doc else tk.DISABLED)
        if hasattr(self, '_cl_nav_goto_btn'):
            self._cl_nav_goto_btn.config(state=tk.NORMAL if self._cl_selected_task_id else tk.DISABLED)

    def _show_detail(self, text):
        """Update the detail panel text."""
        if not hasattr(self, 'cl_detail_text'):
            return
        self.cl_detail_text.config(state='normal')
        self.cl_detail_text.delete('1.0', tk.END)
        self.cl_detail_text.insert('1.0', text)
        self.cl_detail_text.config(state='disabled')

    def _lookup_item_detail(self, iid):
        """Look up full item data from checklist.json and todos.json by id."""
        # 1. checklist.json
        cl_path = Path(self.base_path) / "checklist.json"
        try:
            if cl_path.exists():
                cl = json.loads(cl_path.read_text(encoding="utf-8"))
                for section_key, section in cl.items():
                    if not isinstance(section, dict):
                        continue
                    for item in section.get("items", []):
                        if str(item.get("id")) == str(iid):
                            item["source"] = f"checklist:{section_key}"
                            return item
        except Exception:
            pass

        # 2. todos.json (phase-dict format)
        todos_path = Path(self.base_path) / "todos.json"
        try:
            if todos_path.exists():
                todos = json.loads(todos_path.read_text(encoding="utf-8"))
                if isinstance(todos, dict):
                    for phase_key, phase in todos.items():
                        if not isinstance(phase, dict):
                            continue
                        for tid, task in phase.items():
                            if isinstance(task, dict) and str(task.get("id", tid)) == str(iid):
                                task["source"] = f"todos:{phase_key}"
                                return task
        except Exception:
            pass
        return None

    def _checklist_confirm(self):
        """Mark selected checklist items as CONFIRMED."""
        if not hasattr(self, 'checklist_tree'):
            return
        for iid in self.checklist_tree.selection():
            vals = list(self.checklist_tree.item(iid, "values"))
            vals[4] = "CONFIRMED"
            self.checklist_tree.item(iid, values=vals, tags=("confirmed",))
            self._persist_checklist_item(iid, {
                "status": "CONFIRMED",
                "confirmed_at": datetime.datetime.now().isoformat()
            })
        self.status_bar.config(text=f"Confirmed {len(self.checklist_tree.selection())} item(s)")

    def _checklist_deny(self):
        """Mark selected checklist items as DENIED, with optional reason."""
        if not hasattr(self, 'checklist_tree'):
            return
        sel = self.checklist_tree.selection()
        if not sel:
            return
        # Prompt for reason
        reason = ""
        dlg = tk.Toplevel(self)
        dlg.title("Deny Reason")
        dlg.geometry("350x100")
        dlg.resizable(False, False)
        tk.Label(dlg, text="Reason (optional):").pack(pady=(8, 2))
        entry = tk.Entry(dlg, width=40)
        entry.pack(pady=2)
        entry.focus()
        _result = {"done": False}

        def _do_deny():
            _result["reason"] = entry.get().strip()
            _result["done"] = True
            dlg.destroy()

        tk.Button(dlg, text="Deny", command=_do_deny, bg="#c0392b", fg="white").pack(pady=5)
        dlg.bind("<Return>", lambda e: _do_deny())
        dlg.transient(self)
        dlg.grab_set()
        self.wait_window(dlg)

        if not _result.get("done"):
            return
        reason = _result.get("reason", "")

        for iid in sel:
            vals = list(self.checklist_tree.item(iid, "values"))
            vals[4] = "DENIED"
            self.checklist_tree.item(iid, values=vals, tags=("denied",))
            self._persist_checklist_item(iid, {
                "status": "DENIED",
                "denied_at": datetime.datetime.now().isoformat(),
                "denied_reason": reason
            })
        self.status_bar.config(text=f"Denied {len(sel)} item(s)")

    def _checklist_link_plan(self):
        """Open file browser to link a plan document to the selected checklist item."""
        if not hasattr(self, 'checklist_tree'):
            return
        sel = self.checklist_tree.selection()
        if not sel:
            messagebox.showinfo("Link Plan", "Select a checklist row first.")
            return
        plans_dir = str(Path(self.base_path))
        fpath = filedialog.askopenfilename(
            title="Select Plan Document",
            initialdir=plans_dir,
            filetypes=[("Markdown", "*.md"), ("All files", "*.*")]
        )
        if not fpath:
            return
        for iid in sel:
            self._persist_checklist_item(iid, {"plan_doc": fpath})
            # Update cached data
            if iid in self._checklist_full_data:
                self._checklist_full_data[iid]["plan_doc"] = fpath
            # Update tree tag
            vals = list(self.checklist_tree.item(iid, "values"))
            current_tags = self.checklist_tree.item(iid, "tags")
            if "linked" not in current_tags:
                self.checklist_tree.item(iid, tags=("linked",))
        self.status_bar.config(text=f"Linked plan: {os.path.basename(fpath)}")
        # Refresh detail if same item selected
        self._on_checklist_select()

    def _persist_checklist_item(self, iid, updates):
        """Update item fields in checklist.json by id. Also updates todos.json if task_id matches."""
        cl_path = Path(self.base_path) / "checklist.json"
        updated = False
        try:
            if cl_path.exists():
                cl = json.loads(cl_path.read_text(encoding="utf-8"))
                for section_key, section in cl.items():
                    if not isinstance(section, dict):
                        continue
                    for item in section.get("items", []):
                        if str(item.get("id")) == str(iid):
                            item.update(updates)
                            updated = True
                            break
                    if updated:
                        break
                if updated:
                    cl_path.write_text(json.dumps(cl, indent=2), encoding="utf-8")
        except Exception:
            pass

        # Also update in todos.json if matching task_id
        todos_path = Path(self.base_path) / "todos.json"
        try:
            if todos_path.exists():
                todos = json.loads(todos_path.read_text(encoding="utf-8"))
                if isinstance(todos, dict):
                    for phase_key, phase in todos.items():
                        if not isinstance(phase, dict):
                            continue
                        for tid, task in phase.items():
                            if isinstance(task, dict) and str(task.get("id", tid)) == str(iid):
                                task.update(updates)
                                todos_path.write_text(json.dumps(todos, indent=2), encoding="utf-8")
                                return
        except Exception:
            pass

    def _checklist_open_plan(self):
        """Open the linked plan document in the default editor."""
        plan_doc = getattr(self, '_cl_selected_plan_doc', None)
        if not plan_doc:
            return
        try:
            cfg_path = Path(self.base_path) / "config.json"
            editor = "xdg-open"
            if cfg_path.exists():
                cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
                editor = cfg.get("default_editor", "xdg-open")
            import subprocess as _sp
            _sp.Popen([editor, plan_doc])
            self.status_bar.config(text=f"Opened: {os.path.basename(plan_doc)}")
        except Exception as e:
            self.status_bar.config(text=f"Cannot open plan: {e}")

    def _checklist_goto_task(self):
        """Switch to Tasks tab and select the matching task in board_tree."""
        task_id = getattr(self, '_cl_selected_task_id', None)
        if not task_id or not hasattr(self, 'board_tree'):
            return
        # Switch to Tasks tab
        if hasattr(self, 'right_notebook') and hasattr(self, 'board_frame'):
            self.right_notebook.select(self.board_frame)
        # Find and select in board_tree
        for iid in self.board_tree.get_children():
            item_text = self.board_tree.item(iid, "text")
            if task_id in str(item_text):
                self.board_tree.selection_set(iid)
                self.board_tree.see(iid)
                self.board_tree.focus(iid)
                self.status_bar.config(text=f"Jumped to task: {task_id}")
                return
            # Check children
            for child in self.board_tree.get_children(iid):
                child_text = self.board_tree.item(child, "text")
                if task_id in str(child_text):
                    self.board_tree.item(iid, open=True)
                    self.board_tree.selection_set(child)
                    self.board_tree.see(child)
                    self.board_tree.focus(child)
                    self.status_bar.config(text=f"Jumped to task: {task_id}")
                    return
        self.status_bar.config(text=f"Task {task_id} not found in board")

    # ── CLI Integration ──────────────────────────────────────────────────────

    def _run_cli_command(self, *cmd_args):
        """Run Os_Toolkit CLI command in background thread, show output in detail panel."""
        import threading
        display = " ".join(cmd_args)
        self._show_detail(f"Running: Os_Toolkit.py {display} ...")
        self.status_bar.config(text=f"CLI: running {display}...")

        def _worker():
            try:
                toolkit_path = Path(__file__).parents[5] / "tabs" / "action_panel_tab" / "Os_Toolkit.py"
                result = subprocess.run(
                    [sys.executable, str(toolkit_path)] + list(cmd_args),
                    capture_output=True, text=True, timeout=30,
                    cwd=str(toolkit_path.parent)
                )
                output = (result.stdout or "") + (result.stderr or "")
            except subprocess.TimeoutExpired:
                output = f"Timeout: {display} took > 30s"
            except Exception as e:
                output = f"Error: {e}"
            self.after(0, lambda: self._show_cli_output(display, output))

        threading.Thread(target=_worker, daemon=True).start()

    def _show_cli_output(self, action, output):
        """Display CLI command output in detail panel and refresh checklist."""
        self._show_detail(f"=== Os_Toolkit.py {action} ===\n\n{output}")
        self.status_bar.config(text=f"CLI: {action} complete")
        # Auto-refresh checklist after sync commands
        if "sync" in action or "consolidate" in action:
            self.after(500, self._refresh_checklist_tab)

    def _cli_sync_marks(self):
        self._run_cli_command("actions", "--run", "sync_marks")

    def _cli_sync_all_todos(self):
        self._run_cli_command("actions", "--run", "sync_all_todos")

    def _cli_consolidate_plans(self):
        self._run_cli_command("actions", "--run", "consolidate_plans")

    def _cli_latest_report(self):
        self._run_cli_command("latest")

    def run_diff_analysis(self):
        """Run diff analysis on marked files"""
        if len(self.marked_files) < 2:
            messagebox.showwarning("Diff", "Need at least 2 files for diff")
            return
        
        # Create diff window
        diff_window = tk.Toplevel(self)
        diff_window.title("Diff Analysis")
        diff_window.geometry("800x600")
        
        # Diff text area
        diff_text = scrolledtext.ScrolledText(diff_window, wrap=tk.NONE)
        diff_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Compare first two files
        try:
            with open(self.marked_files[0], 'r') as f1, open(self.marked_files[1], 'r') as f2:
                lines1 = f1.readlines()
                lines2 = f2.readlines()
            
            diff = difflib.unified_diff(
                lines1, lines2,
                fromfile=os.path.basename(self.marked_files[0]),
                tofile=os.path.basename(self.marked_files[1]),
                lineterm=''
            )
            
            diff_text.insert(1.0, '\n'.join(diff))
            
            # Store diff
            diff_content = '\n'.join(diff)
            self.save_diff_to_file(diff_content, self.marked_files[0], self.marked_files[1])
            
        except Exception as e:
            messagebox.showerror("Diff Error", f"Could not compute diff: {e}")
    
    def save_diff_to_file(self, diff_content, file1, file2):
        """Save diff to file in Diffs directory"""
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        diff_file = os.path.join(self.base_path, "Diffs", f"diff_{timestamp}.txt")
        
        with open(diff_file, 'w') as f:
            f.write(f"Diff between:\n{file1}\n{file2}\n\n")
            f.write(diff_content)
        
        self.diff_history.append({
            'timestamp': timestamp,
            'file1': file1,
            'file2': file2,
            'diff_file': diff_file
        })
        
        # Refresh tree
        self.load_directory_structure()
    
    def add_to_task(self):
        """Add context to current task"""
        context = self.context_entry.get()
        if context:
            task_file = os.path.join(self.base_path, "Tasks", "context_tasks.txt")
            
            with open(task_file, 'a') as f:
                timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                f.write(f"\n[{timestamp}] {context}\n")
            
            # Update Ag Knowledge links
            self.update_ag_knowledge_links(context)
            
            self.status_bar.config(text="Context added to task")
            self.context_entry.delete(0, tk.END)
    
    def compile_summary(self):
        """Compile a summary from marked files and context"""
        if not self.marked_files:
            messagebox.showwarning("Summary", "No marked files to compile")
            return
        
        summary_window = tk.Toplevel(self)
        summary_window.title("Compiled Summary")
        summary_window.geometry("600x400")
        
        summary_text = scrolledtext.ScrolledText(summary_window, wrap=tk.WORD)
        summary_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        summary = f"Summary compiled: {datetime.datetime.now()}\n"
        summary += "=" * 50 + "\n\n"
        summary += f"Marked files ({len(self.marked_files)}):\n"
        
        for i, file_path in enumerate(self.marked_files, 1):
            summary += f"{i}. {file_path}\n"
            
            try:
                with open(file_path, 'r') as f:
                    lines = f.readlines()[:10]  # First 10 lines
                    summary += "   Preview:\n"
                    for line in lines[:5]:
                        summary += f"   {line}"
                    if len(lines) > 5:
                        summary += "   ...\n"
            except:
                summary += "   [Could not read file]\n"
            
            summary += "\n"
        
        summary_text.insert(1.0, summary)
        
        # Save summary
        summary_file = os.path.join(self.base_path, "Refs", f"summary_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.txt")
        with open(summary_file, 'w') as f:
            f.write(summary)
        
        self.load_directory_structure()
    
    def add_diff_lines(self):
        """Add lines to diff tracking"""
        lines = self.diff_entry.get()
        if lines:
            diff_file = os.path.join(self.base_path, "Diffs", "manual_diffs.txt")
            
            with open(diff_file, 'a') as f:
                timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                f.write(f"\n[{timestamp}]\n")
                f.write(lines + "\n")
                f.write("-" * 40 + "\n")
            
            self.diff_entry.delete(0, tk.END)
            self.status_bar.config(text="Diff lines added")
    
    def scroll_marked_files(self):
        """Scroll through marked files in document display"""
        if not self.marked_files:
            messagebox.showinfo("Marked Files", "No marked files to scroll through")
            return
        
        # Create a simple viewer
        viewer_window = tk.Toplevel(self)
        viewer_window.title("Marked Files Viewer")
        viewer_window.geometry("800x500")
        
        notebook = ttk.Notebook(viewer_window)
        notebook.pack(fill=tk.BOTH, expand=True)
        
        for file_path in self.marked_files:
            frame = tk.Frame(notebook)
            notebook.add(frame, text=os.path.basename(file_path))
            
            text_widget = scrolledtext.ScrolledText(frame, wrap=tk.WORD)
            text_widget.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
            
            try:
                with open(file_path, 'r') as f:
                    content = f.read()
                text_widget.insert(1.0, content)
            except Exception as e:
                text_widget.insert(1.0, f"Error reading file: {e}")
    
    # ── Planner state persistence ──────────────────────────────────────────────

    def _load_planner_state(self):
        """Load persisted UI state from plans/config.json."""
        cfg = Path(self.base_path) / "config.json"
        try:
            return json.loads(cfg.read_text(encoding="utf-8")) if cfg.exists() else {}
        except Exception:
            return {}

    def _save_planner_state(self):
        """Persist current UI state to plans/config.json."""
        cfg = Path(self.base_path) / "config.json"
        state = self._load_planner_state()
        state["task_watcher"] = self.watcher_var.get()
        try:
            cfg.write_text(json.dumps(state, indent=2), encoding="utf-8")
        except Exception:
            pass

    def toggle_watcher(self):
        """Toggle task completion watcher"""
        state = self.watcher_var.get()
        if state:
            self.status_bar.config(text="Task watcher: ON")
            self.start_watcher()
        else:
            self.status_bar.config(text="Task watcher: OFF")
        self._save_planner_state()
        if _TRAINER_LOG_AVAILABLE:
            _trainer_log.log_ux_event(
                "ag_knowledge", "WATCHER_TOGGLE", "watcher_checkbutton",
                outcome="on" if state else "off",
                detail=f"Task Watcher {'enabled' if state else 'disabled'} — watching {len(self.marked_files)} marked files",
                wherein="PlannerSuite::toggle_watcher"
            )

    def start_watcher(self):
        """Start file watcher thread + UX_EVENT_LOG monitor.

        File watcher: detects hash changes in marked_files, emits log_ux_event.
        Event monitor: polls UX_EVENT_LOG for new WARN/ERROR/RISK events and writes
                       plans/Tasks/task_context_{timestamp}.json for each new alert.
        """
        _last_ux_seen = [0]  # mutable closure cell for event monitor

        def _monitor_ux_events():
            """Poll UX_EVENT_LOG for new error/warn events → write task context files."""
            if not (_TRAINER_LOG_AVAILABLE and hasattr(_trainer_log, 'UX_EVENT_LOG')):
                return
            tasks_dir = Path(self.base_path) / "Tasks"
            tasks_dir.mkdir(exist_ok=True)
            current_log = _trainer_log.UX_EVENT_LOG
            new_idx = _last_ux_seen[0]
            new_events = current_log[new_idx:]
            _last_ux_seen[0] = len(current_log)
            alert_outcomes = {"error", "warn", "WARN", "ERROR", "risk", "RISK"}
            for e in new_events:
                if e.get("outcome", "") in alert_outcomes or e.get("event_type", "").startswith("WARN"):
                    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:19]
                    ctx = {
                        "timestamp": e.get("timestamp"),
                        "event_type": e.get("event_type"),
                        "tab": e.get("tab"),
                        "widget": e.get("widget"),
                        "outcome": e.get("outcome"),
                        "detail": e.get("detail"),
                        "wherein": e.get("wherein"),
                        "status": "OPEN",
                        "checklist_candidate": True,
                    }
                    ctx_file = tasks_dir / f"task_context_{ts}.json"
                    try:
                        with open(ctx_file, 'w', encoding='utf-8') as f:
                            json.dump(ctx, f, indent=2)
                    except Exception:
                        pass
                if (e.get("event_type") == "VERSION_GATE_CHOICE"
                        and e.get("choice") in ("save", "save_default")):
                    _tids = e.get("active_task_ids", [])
                    if _tids:
                        self.after(0, lambda t=_tids: self._prompt_version_gate_tasks(t))

        def watch_files():
            last_hashes = {}
            while self.watcher_var.get():
                _monitor_ux_events()
                for file_path in self.marked_files:
                    try:
                        with open(file_path, 'rb') as f:
                            file_hash = hashlib.md5(f.read()).hexdigest()

                        if file_path in last_hashes:
                            if last_hashes[file_path] != file_hash:
                                fname = os.path.basename(file_path)
                                if _TRAINER_LOG_AVAILABLE:
                                    _trainer_log.log_ux_event(
                                        "ag_knowledge", "FILE_CHANGED", fname,
                                        outcome="detected",
                                        detail=f"Watcher: {file_path}",
                                        wherein="PlannerSuite::_watcher_thread"
                                    )
                                else:
                                    print(f"File changed: {file_path}")
                                # Append live row to Checklist tab on main thread
                                self.after(0, lambda fp=file_path: self._checklist_append_row(
                                    file=fp, ftype="WATCH", status="PENDING"))
                                # Fire watcher inference on main thread
                                self.after(0, lambda fp=file_path: self._on_watcher_file_change(fp))
                                last_hashes[file_path] = file_hash
                        else:
                            last_hashes[file_path] = file_hash
                    except:
                        pass
                
                import time
                time.sleep(5)  # Check every 5 seconds
        
        thread = threading.Thread(target=watch_files, daemon=True)
        thread.start()
    
    # ── Task Board ────────────────────────────────────────────────────────────

    def setup_task_board_ui(self):
        """Build the Task Board tab — live lifecycle view with right-click controls."""
        ctrl = tk.Frame(self.board_frame)
        ctrl.pack(fill=tk.X, padx=4, pady=3)

        tk.Button(ctrl, text="🔄 Refresh", command=self._sync_and_refresh).pack(side=tk.LEFT, padx=2)
        tk.Button(ctrl, text="➕ New Task", command=self._show_new_task_dialog,
                  font=('Consolas', 9), fg='#2ecc71').pack(side=tk.LEFT, padx=2)
        tk.Button(ctrl, text="✓ Complete", command=self._complete_selected_task,
                  font=('Consolas', 8), fg='#27ae60').pack(side=tk.LEFT, padx=2)
        tk.Button(ctrl, text="▶ In Progress", command=self.mark_task_in_progress).pack(side=tk.LEFT, padx=2)
        tk.Button(ctrl, text="📄 Open", command=self._board_open_file).pack(side=tk.LEFT, padx=2)
        tk.Button(ctrl, text="📌 Load Epic", command=self._load_active_project_epic).pack(side=tk.LEFT, padx=2)
        tk.Button(ctrl, text="🔬 Debug AoE", command=self._debug_aoe_context,
                  font=('Consolas', 8), fg='#666').pack(side=tk.LEFT, padx=2)
        tk.Button(ctrl, text="📝 Edit Attr", command=self._show_attribution_editor,
                  font=('Consolas', 8), fg='#666').pack(side=tk.LEFT, padx=2)
        tk.Button(ctrl, text="🎯 Activate", command=self._activate_selected_task,
                  font=('Consolas', 8), fg='#2980b9').pack(side=tk.LEFT, padx=2)
        tk.Button(ctrl, text="⟳ Next", command=self._cycle_active_task,
                  font=('Consolas', 8), fg='#2980b9').pack(side=tk.LEFT, padx=2)
        self._active_label = tk.Label(ctrl, text="", font=('Consolas', 8), fg='#e67e22')
        self._active_label.pack(side=tk.LEFT, padx=6)
        # _active_task_id is set later at line ~1254; pre-init to avoid AttributeError
        if not hasattr(self, '_active_task_id'):
            self._active_task_id = None
        self._refresh_active_label()

        # Sort/filter row
        filt = tk.Frame(self.board_frame)
        filt.pack(fill=tk.X, padx=4, pady=1)

        tk.Label(filt, text="Show:").pack(side=tk.LEFT)
        self.board_filter_var = tk.StringVar(value="READY+IN_PROGRESS")
        for label, val in [("All", "ALL"), ("Active", "READY+IN_PROGRESS"), ("Done", "COMPLETE")]:
            tk.Radiobutton(filt, text=label, variable=self.board_filter_var,
                           value=val, command=self.refresh_task_board).pack(side=tk.LEFT, padx=2)

        # File filter indicator + clear button (hidden when no filter active)
        self.board_filter_label = tk.Label(filt, text="", fg='#e67e22', font=('Consolas', 8))
        self.board_filter_label.pack(side=tk.LEFT, padx=(6, 0))
        self.board_filter_clear_btn = tk.Button(
            filt, text="✕ Clear Filter", font=('Consolas', 8), fg='#e67e22',
            command=self._clear_board_file_filter, relief=tk.FLAT, pady=0
        )
        # btn packed only when filter active — see show_tasks_for_file

        tk.Label(filt, text="  Sort:").pack(side=tk.LEFT, padx=(8, 0))
        # "Current State" — IN_PROGRESS + BUG + reactive warnings at top (default ON)
        self.board_sort_current_state = tk.BooleanVar(value=True)
        tk.Checkbutton(filt, text="Current State", variable=self.board_sort_current_state,
                       command=self.refresh_task_board).pack(side=tk.LEFT, padx=2)
        # Calendar sort — group by recency/age of task
        self.board_sort_calendar = tk.BooleanVar(value=False)
        tk.Checkbutton(filt, text="Calendar", variable=self.board_sort_calendar,
                       command=self.refresh_task_board).pack(side=tk.LEFT, padx=2)

        # Status bar
        self.board_status = tk.Label(self.board_frame, text="", anchor='w',
                                     font=('Consolas', 8), fg='#555')
        self.board_status.pack(fill=tk.X, padx=4)

        # Treeview
        tree_frame = tk.Frame(self.board_frame)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=4, pady=2)

        vsb = tk.Scrollbar(tree_frame)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        hsb = tk.Scrollbar(tree_frame, orient=tk.HORIZONTAL)
        hsb.pack(side=tk.BOTTOM, fill=tk.X)

        self._file_filter = None  # set by show_tasks_for_file(); None = no filter
        self.board_tree = ttk.Treeview(
            tree_frame, columns=("status", "wherein", "source", "who", "type", "created", "project", "gaps"),
            yscrollcommand=vsb.set, xscrollcommand=hsb.set, selectmode='extended'
        )
        vsb.config(command=self.board_tree.yview)
        hsb.config(command=self.board_tree.xview)

        # Keyboard shortcuts
        self.board_tree.bind("<Control-z>", self._on_ctrl_z)
        self.bind_all("<Control-z>", self._on_ctrl_z) # Global within tab

        # Column sort state: col → 0=default, 1=asc, 2=desc
        self._board_sort_state = {"#0": 0, "status": 0, "wherein": 0, "source": 0, "who": 0, "type": 0, "created": 0, "project": 0, "gaps": 0}
        self._board_sort_col = None

        for col, label, width in [
            ("#0",       "Task / Title ⇅", 250),
            ("status",   "Status ⇅",        70),
            ("wherein",  "∈ File ⇅",       120),
            ("source",   "Source ⇅",        70),
            ("who",      "Who ⇅",           50),
            ("type",     "Type ⇅",          90),
            ("created",  "📅 Created ⇅",   100),
            ("project",  "Project ⇅",       90),
            ("gaps",     "Gaps ⇅",          45),
        ]:
            self.board_tree.heading(col, text=label, anchor=tk.W,
                                    command=lambda c=col: self._board_sort_by(c))
            self.board_tree.column(col, width=width,
                                   minwidth=max(60, width // 2))

        self.board_tree.tag_configure("p0",    foreground="#c0392b")
        self.board_tree.tag_configure("p1",    foreground="#d35400")
        self.board_tree.tag_configure("p2",    foreground="#2980b9")
        self.board_tree.tag_configure("done",  foreground="#27ae60")
        self.board_tree.tag_configure("inprog",foreground="#8e44ad")
        self.board_tree.tag_configure("bug",   foreground="#c0392b", font=('Consolas', 9, 'bold'))
        self.board_tree.tag_configure("reactive", foreground="#e67e22")
        self.board_tree.tag_configure("group", font=('Consolas', 9, 'bold'))
        self.board_tree.tag_configure("test_inprog", foreground="#f39c12")   # yellow — test:in_progress
        self.board_tree.tag_configure("test_passed", foreground="#27ae60")   # green — test:passed
        self.board_tree.tag_configure("has_gaps",    foreground="#c0392b")   # red   — missing attributes
        self.board_tree.tag_configure("proj_rel",    foreground="#16a085")   # teal  — active project relevant
        self.board_tree.tag_configure("inferred",     foreground="#8e44ad")   # purple — inferred from epic file refs

        self.board_tree.pack(fill=tk.BOTH, expand=True)
        self.board_tree.bind("<<TreeviewSelect>>", self._on_board_select)
        self.board_tree.bind("<Double-1>",         self._on_board_double_click)
        self.board_tree.bind("<Button-3>",         self._on_board_right_click)
        self.board_tree.bind("<<TreeviewOpen>>",   self._on_board_expand)

        self._board_tasks = {}
        self._board_lazy_ctx = {}  # {task_node_iid: (tid, t, enriched_changes, fs_manifest)}
        self._board_cycle_idx = 0   # for live watcher cycling
        self._active_task_id = self._load_planner_state().get("active_task_id")
        self.refresh_task_board()

    def _sync_and_refresh(self):
        """Refresh button handler: syncs first if latest_sync.json is stale (>5 min), then re-renders."""
        import time
        latest_sync = Path(self.base_path) / "Refs" / "latest_sync.json"
        stale = True
        if latest_sync.exists():
            age_seconds = time.time() - latest_sync.stat().st_mtime
            stale = age_seconds > 300  # 5-minute freshness window
        if stale:
            self.sync_todos()  # sync_todos() calls refresh_task_board() on completion
        else:
            self.refresh_task_board()

    def refresh_task_board(self):
        """Load tasks from latest_sync.json + quieten resolved reactive test tasks.
        Nests child nodes for deep context (Temporal AoE, DNA, Tool Profiles, Logs).
        """
        for item in self.board_tree.get_children():
            self.board_tree.delete(item)
        self._board_tasks = {}
        self._board_lazy_ctx = {}

        # ── 1. Load Multi-System Context Data ──
        enriched_changes = {}
        filesync_manifest = {}
        try:
            root_data = Path(__file__).parents[5]
            manifest_path = root_data / "backup" / "version_manifest.json"
            if manifest_path.exists():
                with open(manifest_path, 'r') as f:
                    v_manifest = json.load(f)
                enriched_changes = v_manifest.get("enriched_changes", {})
            
            # Filesync Timeline Data (Temporal Inference)
            fs_dir = root_data / "tabs" / "action_panel_tab" / "babel_data" / "timeline" / "manifests"
            if fs_dir.exists():
                # Try history_temporal_manifest first (generated by latest), then legacy manifest_* pattern
                _htm = fs_dir / "history_temporal_manifest.json"
                if _htm.exists():
                    with open(_htm, 'r') as f:
                        filesync_manifest = json.load(f)
                else:
                    fs_manifests = sorted(fs_dir.glob("manifest_*.json"))
                    if fs_manifests:
                        with open(fs_manifests[-1], 'r') as f:
                            filesync_manifest = json.load(f)
        except Exception:
            pass

        # ── 2. Load Todos ──
        latest_sync = Path(self.base_path) / "Refs" / "latest_sync.json"
        if not latest_sync.exists():
            self.board_status.config(text="No data — press Sync Todos first")
            return

        try:
            with open(latest_sync, encoding='utf-8') as f:
                data = json.load(f)
        except Exception as e:
            self.board_status.config(text=f"Load error: {e}")
            return

        tasks = data.get("tasks", {})

        # Reactive quietening
        fired_events = set()
        if _TRAINER_LOG_AVAILABLE and hasattr(_trainer_log, 'UX_EVENT_LOG'):
            fired_events = {e.get("event_type") for e in _trainer_log.UX_EVENT_LOG
                           if e.get("outcome") in ("fired", "success", "primed")}
            tasks_dir = Path(self.base_path) / "Tasks"
            if tasks_dir.exists():
                for ctx_file in tasks_dir.glob("task_context_*.json"):
                    try:
                        with open(ctx_file, encoding='utf-8') as f:
                            ctx = json.load(f)
                        if ctx.get("status") == "OPEN" and ctx.get("event_type") in fired_events:
                            ctx["status"] = "RESOLVED"
                            with open(ctx_file, 'w', encoding='utf-8') as f:
                                json.dump(ctx, f, indent=2)
                    except Exception:
                        pass

        # Group by priority (case-insensitive status matching)
        filt = self.board_filter_var.get()
        shown_statuses = None
        if filt == "READY+IN_PROGRESS":
            shown_statuses = {"READY", "IN_PROGRESS", "PROTOTYPE_READY", "DESIGN",
                              "PENDING", "PENDING_TEST", "DESIGN_READY",
                              "READY_FOR_TESTING", "READY_TO_EXECUTE", "READY_TO_IMPLEMENT"}
        elif filt == "COMPLETE":
            shown_statuses = {"COMPLETE", "COMPLETED", "RESOLVED", "DONE"}

        groups = {"P0": [], "P1": [], "P2": [], "P3": [], "Other": []}
        for tid, t in tasks.items():
            pri = t.get("priority", "").upper()
            status = t.get("status", "").upper()
            if shown_statuses and status not in shown_statuses:
                continue
            if pri in groups:
                groups[pri].append((tid, t))
            else:
                groups["Other"].append((tid, t))

        # ── Live polling branch (pinned at top) ──
        try:
            _all_task_items = list(tasks.items()) if isinstance(tasks, dict) else [(t.get("id",""), t) for t in tasks]
            _live_tasks = [(tid, t) for tid, t in _all_task_items
                           if str(t.get("status", "")).lower().replace("-", "_") in ("in_progress", "inprogress")]
            _live_iid = "§live"
            self.board_tree.insert("", 0, iid=_live_iid,
                text=f"🔴  LIVE — {len(_live_tasks)} in progress",
                tags=("group",), open=True)
            for _lt_id, _lt in _live_tasks[:10]:
                _lt_title = str(_lt.get("title", ""))[:45]
                _lt_where = _lt.get("wherein", "") or ""
                _lt_proj, _lt_gaps = self._get_task_meta_quick(_lt_id)
                _tags = ("inprog",) + (("has_gaps",) if _lt_gaps > 0 else ())
                self.board_tree.insert(_live_iid, "end", iid=f"§live_{_lt_id}",
                    text=f"  {_lt_title}",
                    values=(_lt.get("status",""), _lt_where[:35], _lt.get("source",""),
                            "", "", "", _lt_proj, str(_lt_gaps) if _lt_gaps else ""),
                    tags=_tags)
        except Exception:
            pass

        # ── Inferred Tasks branch ─────────────────────────────────────────────
        _infer_iid = "§inferred"
        if not self.board_tree.exists(_infer_iid):
            self.board_tree.insert("", 1, iid=_infer_iid,
                text="🔍  INFERRED — tasks matched via project file refs",
                tags=("group_header",))
        else:
            # Clear stale inferred entries
            for ch in self.board_tree.get_children(_infer_iid):
                self.board_tree.delete(ch)

        # Populate inferred: tasks with wherein matching any epic's file refs but no project_ref
        try:
            _epic_file_map = self._get_all_epic_file_refs()
            _inferred_count = 0
            _seen_infer = set()
            _all_task_pairs = list(tasks.items()) if isinstance(tasks, dict) else [(t.get("id", ""), t) for t in tasks]
            for _tid, _t in _all_task_pairs:
                _wherein = os.path.basename(str(_t.get("wherein", "") or ""))
                if not _wherein:
                    continue
                _matched_proj = _epic_file_map.get(_wherein)
                if not _matched_proj:
                    continue
                # Only show if no project_ref already linked
                _ctx_proj, _gaps = self._get_task_meta_quick(_tid)
                if _ctx_proj:
                    continue
                if _tid in _seen_infer:
                    continue
                _seen_infer.add(_tid)
                _status = str(_t.get("status", "")).upper()
                _title = str(_t.get("title", _tid))[:55]
                _iid = f"§inf_{_tid}"
                if not self.board_tree.exists(_iid):
                    self.board_tree.insert(_infer_iid, "end", iid=_iid,
                        text=f"  ⟳ {_title}",
                        values=(_status, _t.get("priority", ""), _wherein,
                                _matched_proj, "", _gaps, "", ""),
                        tags=("inferred",))
                    _inferred_count += 1
            self.board_tree.item(_infer_iid,
                text=f"🔍  INFERRED — {_inferred_count} tasks matched via file refs")
        except Exception:
            pass

        # ── Attribution Gap Detection ──
        # Find enriched_change events with no matching task wherein.
        gap_eids = []
        try:
            import recovery_util as _ru
            gap_eids = _ru.find_unattributed_changes(enriched_changes, tasks)
        except Exception:
            pass

        if gap_eids and not self._file_filter:
            gap_group = self.board_tree.insert(
                "", "end",
                text=f"── ⚠ Attribution Gaps  ({len(gap_eids)} changes, no task attributed)",
                values=("BUG", "", "enriched_changes", "system", "gap", "", "", ""), open=True, tags=("p0",)
            )
            self._board_tasks[gap_group] = {"type": "group", "group": "attribution_gaps"}
            for gap_eid in gap_eids:
                ch = enriched_changes.get(gap_eid, {})
                ch_file = ch.get("file", "{unknown}").split("/")[-1]
                ch_verb = ch.get("verb", "?")
                ch_risk = ch.get("risk_level", "LOW")
                risk_tag = "diff_node" if ch_risk in ("HIGH", "CRITICAL") else "p0"
                gap_row = self.board_tree.insert(
                    gap_group, "end",
                    text=f"  [BUG] {gap_eid} — {ch_verb} ∈ {ch_file} — no task attributed",
                    values=("BUG", ch_file, "enriched_changes", "system", "gap", ch.get("timestamp", "")[:16], "", ""),
                    tags=(risk_tag,)
                )
                self._board_tasks[gap_row] = {
                    "type": "attribution_gap",
                    "eid": gap_eid,
                    **ch
                }

        total_shown = 0
        for pri_label in ["P0", "P1", "P2", "P3", "Other"]:
            items = groups[pri_label]
            if not items: continue
            
            ready_count = sum(1 for _, t in items if t.get("status") in
                              ("READY", "IN_PROGRESS", "PROTOTYPE_READY"))
            group_node = self.board_tree.insert(
                "", "end",
                text=f"── {pri_label}  ({len(items)} tasks, {ready_count} active)",
                values=("", "", "", "", "", "", "", ""), open=(pri_label in ("P0", "P1")), tags=("group",)
            )
            
            for tid, t in items:
                status, wherein, source, title = t.get("status", "?"), t.get("wherein", ""), t.get("source", ""), t.get("title", tid)
                display_wh = wherein.split("/")[-1] if wherein else ""
                
                tag = "p0" if pri_label == "P0" else "p1" if pri_label == "P1" else "p2"
                if status in ("COMPLETE", "RESOLVED", "DONE"): tag = "done"
                elif status == "IN_PROGRESS": tag = "inprog"
                # Override with test_status color if present
                _test_st = t.get("test_status", "")
                if _test_st == "test:in_progress": tag = "test_inprog"
                elif _test_st == "test:passed": tag = "test_passed"

                # Task type badge — inferred from wherein + enriched_changes verb
                _wh_base = os.path.basename(wherein) if wherein else ""
                if not _wh_base:
                    _type_badge = "[NEW]"
                else:
                    _ec_verb = next(
                        (ch.get("verb", "").upper()
                         for _, ch in enriched_changes.items()
                         if os.path.basename(ch.get("file", "")) == _wh_base),
                        None
                    )
                    _type_badge = {"CREATE": "[NEW]", "ADD": "[NEW]",
                                   "DELETE": "[REM]", "REMOVE": "[REM]"}.get(_ec_verb, "[MOD]")

                # File filter — skip tasks not matching active filter
                if self._file_filter and display_wh and self._file_filter not in display_wh:
                    continue

                # Populate datetime_created from task timestamp
                created = t.get("created_at", t.get("timestamp", ""))
                created = created[:16] if created else ""
                # Infer who from source if not explicitly set
                who = t.get("who", "")
                if not who:
                    _src = t.get("source", "")
                    if _src.startswith("claude:"):
                        who = "claude"
                    elif _src == "checklist.json":
                        who = "user"
                    elif _src == "todos.json":
                        who = "system"
                # Shorten task_type for display (strip phase_ prefix)
                task_type = t.get("task_type", "")
                if task_type.startswith("phase_"):
                    task_type = task_type[6:]
                if not task_type:
                    task_type = "<unknown>"
                # Infer created from enriched_changes timestamps if missing
                if not created and display_wh:
                    for _eid, _ch in enriched_changes.items():
                        if os.path.basename(_ch.get("file", "")) == display_wh:
                            _ts = _ch.get("timestamp", "")
                            if _ts:
                                created = _ts[:16]
                                break

                _proj, _gaps = self._get_task_meta_quick(tid)
                _gaps_str = str(_gaps) if _gaps else ""
                _task_tags = (tag,) + (("has_gaps",) if _gaps > 0 else ())
                task_node = self.board_tree.insert(group_node, "end", text=f"{_type_badge} {tid}: {title[:55]}", values=(status, display_wh, source, who, task_type, created, _proj, _gaps_str), tags=_task_tags)
                self._board_tasks[task_node] = {"tid": tid, "type": "task", **t}
                total_shown += 1

                # ── 3. Lazy-load layer header sentinels ──
                # Each layer gets a header node with a sentinel child so Treeview shows the ▶ expand arrow.
                # Actual vector population happens in _on_board_expand when the layer is opened.
                self._board_lazy_ctx[task_node] = (tid, t, enriched_changes, filesync_manifest)
                layers = _AOE_CONFIG.get("layers", []) if _AOE_CONFIG else []
                for layer in layers:
                    layer_id   = layer["id"]
                    layer_icon = layer.get("icon", "▶")
                    layer_disp = layer["display"]
                    n_vectors  = len(layer.get("vectors", []))
                    layer_node = self.board_tree.insert(
                        task_node, "end",
                        text=f"  {layer_icon} {layer_disp}  ({n_vectors} vectors)",
                        values=("", "", layer.get("source", ""), "", "", "", "", ""),
                        tags=("group",), open=False
                    )
                    self._board_tasks[layer_node] = {
                        "type": "layer_header",
                        "layer_id": layer_id,
                        "task_node": task_node,
                        "populated": False
                    }
                    # Sentinel child — makes the ▶ expand arrow appear
                    sentinel = self.board_tree.insert(
                        layer_node, "end",
                        text=f"    ○ {layer_disp} — click ▶ to load vectors",
                        values=("", "", "", "", "", "", "", ""), tags=("group",)
                    )
                    self._board_tasks[sentinel] = {"type": "sentinel", "layer_node": layer_node}

        ts = data.get("timestamp", "")[:16]
        gap_note = f"  ⚠ {len(gap_eids)} unattributed changes" if gap_eids and not self._file_filter else ""
        self.board_status.config(text=f"{total_shown} tasks shown  |  synced {ts}{gap_note}")

        if _TRAINER_LOG_AVAILABLE:
            _trainer_log.log_ux_event(
                "ag_knowledge", "TASK_BOARD_REFRESH", "board_refresh_button",
                outcome="success", detail=f"shown={total_shown}",
                wherein="PlannerSuite::refresh_task_board"
            )

    def _on_ctrl_z(self, event=None):
        """Handle Ctrl+Z — triggers undo for the latest change."""
        try:
            import recovery_util
            manifest = recovery_util.load_version_manifest()
            enriched = manifest.get("enriched_changes", {})
            if not enriched:
                self.status_bar.config(text="No recent changes to undo.")
                return
            
            # Find latest event ID
            latest_eid = sorted(enriched.keys())[-1]
            self._open_undo_dialog(latest_eid)
        except Exception as e:
            self.status_bar.config(text=f"Undo error: {e}")

    def _open_undo_dialog(self, event_id):
        """Open the Unified Undo Dialog for a specific event."""
        try:
            import recovery_util
            import sys
            # Ensure path to undo_changes.py is available
            _tab_root = str(Path(__file__).parents[5] / "tabs" / "settings_tab")
            if _tab_root not in sys.path:
                sys.path.insert(0, _tab_root)
            from undo_changes import UndoChangesDialog
            
            manifest = recovery_util.load_version_manifest()
            UndoChangesDialog(self.winfo_toplevel(), event_id, manifest)
            self.refresh_task_board()
        except Exception as e:
            messagebox.showerror("Undo Error", f"Could not open undo dialog: {e}")
            if _TRAINER_LOG_AVAILABLE:
                _trainer_log.log_message(f"PLANNER: {{warn}} Undo dialog error: {e}")

    def _on_board_right_click(self, event):
        """Enhanced context menu for tasks and attributions."""
        item_id = self.board_tree.identify_row(event.y)
        if not item_id:
            return
        
        # If right-clicking a non-selected item, select it exclusively.
        # Otherwise, keep existing multi-selection.
        current_sel = self.board_tree.selection()
        if item_id not in current_sel:
            self.board_tree.selection_set(item_id)
            current_sel = (item_id,)
        
        # Determine types in selection — walk up to parent task if a child node is clicked
        selected_tasks = []
        selected_attributions = []
        for iid in current_sel:
            data = self._board_tasks.get(iid, {})
            node_type = data.get("type", "")
            if node_type == "task":
                selected_tasks.append(iid)
            elif node_type == "attribution":
                selected_attributions.append(iid)
            else:
                # Any node (registered child types OR unregistered placeholders/group headers)
                # Walk up to find nearest task ancestor
                parent = self.board_tree.parent(iid)
                while parent:
                    p_data = self._board_tasks.get(parent, {})
                    if p_data.get("type") == "task":
                        if parent not in selected_tasks:
                            selected_tasks.append(parent)
                        break
                    parent = self.board_tree.parent(parent)

        # Detect if the clicked node itself is a layer_header or vector (for layer-aware copy)
        clicked_data = self._board_tasks.get(item_id, {})
        clicked_type = clicked_data.get("type", "")

        menu = tk.Menu(self, tearoff=0)

        if clicked_type == "layer_header":
            layer_id   = clicked_data.get("layer_id", "?")
            layer_iid  = item_id
            menu.add_command(
                label=f"📋 Copy '{layer_id}' Layer",
                command=lambda iid=layer_iid: self.copy_babel_context_block(start_iid=iid)
            )
            menu.add_separator()

        if clicked_type == "vector":
            disp = clicked_data.get("display", "field")
            vec_iid = item_id
            menu.add_command(
                label=f"📋 Copy Field: {disp}",
                command=lambda iid=vec_iid: self.copy_babel_context_block(start_iid=iid)
            )
            menu.add_separator()

        if selected_tasks and not selected_attributions:
            menu.add_command(label="📋 Copy Babel Context Block", command=self.copy_babel_context_block)
            menu.add_separator()
            menu.add_command(label="✅ Complete", command=self.mark_task_complete)
            menu.add_command(label="▶ In Progress", command=self.mark_task_in_progress)
            menu.add_command(label="🎯 Activate (set as current)", command=self._activate_selected_task)
            menu.add_separator()
            menu.add_command(label="📄 Open Primary File", command=self._board_open_file)
            task_id = self._board_tasks.get(selected_tasks[0], {}).get("tid", "")
            menu.add_separator()
            menu.add_command(label="📄 Open Context in Editor",
                command=lambda tid=task_id: self._render_task_context_in_editor(tid))
            menu.add_command(label="🔗 Set Project ID",
                command=lambda tid=task_id: self._quick_set_project(tid))

        if selected_attributions:
            label = "↶ Undo Selected Change" if len(selected_attributions) == 1 else f"↶ Undo {len(selected_attributions)} Changes"
            menu.add_command(label=label, command=self._undo_selected_attributions)
            menu.add_command(label="🔍 View Attribution Details", command=self._view_selected_attribution)

        if selected_tasks:
            menu.add_separator()
            menu.add_command(label="🔬 Debug: View Raw AoE Data", command=self._debug_aoe_context)

        menu.add_separator()
        menu.add_command(label="🔄 Refresh Board", command=self.refresh_task_board)

        def _dismiss(e=None):
            try: menu.unpost()
            except Exception: pass
        toplevel = self.winfo_toplevel()
        toplevel.bind("<Button-1>", _dismiss, add="+")
        toplevel.bind("<Button-3>", _dismiss, add="+")
        toplevel.bind("<FocusOut>", _dismiss, add="+")
        menu.post(event.x_root, event.y_root)

    def _undo_selected_attributions(self):
        """Undo all selected change events."""
        sel = self.board_tree.selection()
        to_undo = []
        for iid in sel:
            data = self._board_tasks.get(iid, {})
            if data.get("type") == "attribution" and "eid" in data:
                to_undo.append(data["eid"])
        
        if not to_undo: return
        
        if messagebox.askyesno("Undo Changes", f"Undo {len(to_undo)} changes?"):
            import recovery_util
            success_count = 0
            for eid in to_undo:
                ok, _ = recovery_util.undo_single_change(eid)
                if ok: success_count += 1
            
            messagebox.showinfo("Undo Results", f"Successfully undid {success_count}/{len(to_undo)} changes.")
            self.refresh_task_board()

    def _view_selected_attribution(self):
        """Open undo dialog for the first selected attribution."""
        sel = self.board_tree.selection()
        for iid in sel:
            data = self._board_tasks.get(iid, {})
            if data.get("type") == "attribution" and "eid" in data:
                self._open_undo_dialog(data["eid"])
                break

    # ── Lazy-Load Tree: Expand / Populate / Collect ──────────────────────────

    def _on_board_expand(self, event=None):
        """Fired by <<TreeviewOpen>>. If the opened node is a layer_header with a sentinel child,
        populate it with real vector nodes from _populate_layer."""
        try:
            self._on_board_expand_inner(event)
        except Exception as e:
            try:
                self.board_status.config(text=f"Expand error: {e}")
            except Exception:
                pass

    def _on_board_expand_inner(self, event=None):
        opened = self.board_tree.focus()
        if not opened:
            return
        data = self._board_tasks.get(opened, {})
        # Fallback: if focus() didn't land on a layer_header, try identify_row
        # (some Tkinter versions set focus to parent when clicking the ▶ glyph)
        if data.get("type") != "layer_header" and event:
            item = self.board_tree.identify_row(event.y)
            if item and item != opened:
                opened = item
                data = self._board_tasks.get(opened, {})
        if data.get("type") != "layer_header" or data.get("populated"):
            return
        # Check for sentinel child
        children = self.board_tree.get_children(opened)
        if not children:
            return
        first_child_data = self._board_tasks.get(children[0], {})
        if first_child_data.get("type") != "sentinel":
            return
        # Remove sentinel
        self.board_tree.delete(children[0])
        del self._board_tasks[children[0]]
        # Mark as populated before inserting (prevents double-fire)
        self._board_tasks[opened]["populated"] = True
        # Populate the layer
        task_node = data.get("task_node")
        layer_id  = data.get("layer_id", "")
        ctx_tuple = self._board_lazy_ctx.get(task_node)
        if ctx_tuple:
            # Handle both old format (t, enriched, fs) and new format (tid, t, enriched, fs)
            if len(ctx_tuple) == 4:
                tid, t, enriched_changes, fs_manifest = ctx_tuple
                ctx_data = self._get_task_aoe_context(t, enriched_changes, fs_manifest, task_id=tid)
            else:
                t, enriched_changes, fs_manifest = ctx_tuple
                ctx_data = self._get_task_aoe_context(t, enriched_changes, fs_manifest)
            self._populate_layer(opened, layer_id, t, ctx_data)
        else:
            self.board_tree.insert(opened, "end",
                text="  ❓ context data unavailable (refresh board)",
                values=("", "", "", "", "", "", "", ""), tags=("group",))

    def _populate_layer(self, layer_node, layer_id, task, ctx_data):
        """Insert vector nodes for one layer into the given layer_node.
        Uses _AOE_CONFIG for vector definitions; populates from ctx_data where wired."""
        if not _AOE_CONFIG:
            self.board_tree.insert(layer_node, "end",
                text="  ○ aoe_vector_config.json not loaded",
                values=("", "", "", "", "", "", "", ""), tags=("group",))
            return

        layer_cfg = next((l for l in _AOE_CONFIG.get("layers", []) if l["id"] == layer_id), None)
        if not layer_cfg:
            return

        vectors = layer_cfg.get("vectors", [])

        # Attribution layer: show one sub-group per enriched_change entry
        if layer_id == "attribution":
            changes = ctx_data.get("changes", [])
            if not changes:
                self.board_tree.insert(layer_node, "end",
                    text="    ❓ no enriched_changes matched this task file",
                    values=("", "", "", "", "", "", "", ""), tags=("group",))
                self._insert_vectors_for_source(layer_node, vectors, {}, layer_id)
                return
            for eid, ch in changes:
                risk = ch.get("risk_level", "LOW")
                verb = ch.get("verb", "?")
                fname = ch.get("file", "{unknown}").split("/")[-1]
                risk_tag = "diff_node" if risk in ("HIGH", "CRITICAL") else "history_node"
                # Test result sidecar
                test_status = ch.get("test_status", "")
                test_icon = {"PASS": "✓", "FAIL": "⚠", "ATTRIBUTION_GAP": "❗"}.get(test_status, "·")
                version_ts = ch.get("version_ts", "")
                v_suffix = f" @{version_ts[4:8]+'-'+version_ts[9:11]+'-'+version_ts[11:13]}" if len(version_ts) >= 13 else ""
                change_group = self.board_tree.insert(layer_node, "end",
                    text=f"    Δ {eid}: {verb} [{risk}] ∈ {fname}  {test_icon}{v_suffix}",
                    values=("", "", "", "", "", "", "", ""), tags=(risk_tag,))
                self._board_tasks[change_group] = {
                    "type": "attribution",
                    "eid": eid,
                    "layer_id": layer_id,
                    **ch
                }
                src_data = {**ch, "event_id": eid}
                self._insert_vectors_for_source(change_group, vectors, src_data, layer_id)
                # Show test errors as child nodes when FAIL
                if test_status == "FAIL" or test_status == "ATTRIBUTION_GAP":
                    for err in ch.get("test_errors", []):
                        self.board_tree.insert(change_group, "end",
                            text=f"        ❗ {err[:100]}",
                            values=("", "", "", "", "", "", "", ""), tags=("diff_node",))
            # ── D4: Expected Diffs sub-section ──────────────────────────────
            expected_diffs = ctx_data.get("expected_diffs", [])
            if expected_diffs:
                self.board_tree.insert(layer_node, "end",
                    text="    ── Expected (from project.md </Diffs>) ──",
                    values=("", "", "", "", "", "", "", ""), tags=("group",))
                actual_files = {ch.get("file", "").split("/")[-1] for _, ch in changes}
                for ed in expected_diffs:
                    ef = ed.get("file", "?")
                    etype = ed.get("type", "MODIFY")
                    matched = "✓" if ef in actual_files else "○"
                    tag = "history_node" if matched == "✓" else "group"
                    self.board_tree.insert(layer_node, "end",
                        text=f"      📋 {etype}: {ef}  ← {matched}",
                        values=("", "", "", "", "", "", "", ""), tags=(tag,))
            return

        # All other layers: single source dict
        src_data = self._resolve_layer_source(layer_id, ctx_data)
        self._insert_vectors_for_source(layer_node, vectors, src_data, layer_id)

    def _insert_vectors_for_source(self, parent_node, vectors, src_data, layer_id):
        """Helper: insert vector leaf nodes into parent_node from src_data dict."""
        for vec in vectors:
            vid   = vec["id"]
            disp  = vec["display"]
            field = vec["field"]
            wired = vec.get("wired", False)
            phase = vec.get("phase", "?")
            is_risk  = vec.get("risk_field", False)

            value = src_data.get(field) if src_data else None
            # Handle list fields
            if isinstance(value, list):
                value = ", ".join(str(v) for v in value[:5]) if value else None

            if not wired:
                icon = "○"
                text = f"      {icon} {disp}: (unwired — Phase {phase})"
                tag  = "group"
            elif value:
                icon = "⚠️" if is_risk and str(value).upper() not in ("LOW", "") else ("🔴" if is_risk else "📌")
                text = f"      {icon} {disp}: {str(value)[:80]}"
                tag  = "diff_node" if is_risk else "history_node"
            else:
                icon = "❓"
                text = f"      {icon} {disp}: {{unknown}}"
                tag  = "group"

            node = self.board_tree.insert(parent_node, "end", text=text,
                                          values=("", "", "", "", "", "", "", ""), tags=(tag,))
            self._board_tasks[node] = {
                "type": "vector",
                "vector_id": vid,
                "display": disp,
                "value": value,
                "wired": wired,
                "layer_id": layer_id
            }

    def _resolve_layer_source(self, layer_id, ctx_data):
        """Map layer_id to a flat dict of field→value from ctx_data.
        Returns None if no data available for this layer."""
        if layer_id == "attribution":
            # First change in ctx_data['changes'] if any
            if ctx_data.get("changes"):
                eid, ch = ctx_data["changes"][0]
                return {
                    **ch, 
                    "event_id": eid,
                    # Phase B mappings
                    "lines_changed": ch.get("lines_changed", 0),
                    "diff_hash": eid, # Proxy using event ID
                    "timestamp": ch.get("timestamp", "")
                }
            return {}
        elif layer_id == "version_health":
            # First blame entry — return simple keys (no "blame." prefix)
            # aoe_vector_config.json version_health fields use: target, file, line, modified_this_version
            if ctx_data.get("blame"):
                b = ctx_data["blame"][0]
                return {
                    "target":               b.get("target"),
                    "file":                 b.get("file"),
                    "line":                 b.get("line"),
                    "modified_this_version": b.get("modified_this_version"),
                }
            return {}
        elif layer_id == "ux_baseline":
            # Most recent UX event
            if ctx_data.get("ux_events"):
                evt = ctx_data["ux_events"][-1]
                return evt
            return {}
        elif layer_id == "temporal_aoe":
            # Phase B: Temporal AoE
            res = {}
            # Peers
            if ctx_data.get("peers"):
                p = ctx_data["peers"][0]
                res["peer_file"] = p.get("name")
                res["peer_category"] = p.get("cat")
            
            # Cluster/Time (from Filesync manifest)
            res["cluster_id"] = ctx_data.get("cluster_id", "{unknown}")
            res["time_delta_min"] = ctx_data.get("time_delta_min", 0)
            
            return res

        elif layer_id == "code_profile":
            # Phase C: py_manifest data
            cp = ctx_data.get("code_profile")
            if cp:
                # Calculate complexity metric (sum of cyclomatic complexity of all functions/classes if available)
                c_score = 0
                for f in cp.get("functions", []):
                    c_score += f.get("complexity", 1)
                for c in cp.get("classes", []):
                    c_score += c.get("complexity", 1)
                
                # Extract simple lists
                cls_names = [c.get("name") for c in cp.get("classes", [])]
                fn_names  = [f.get("name") for f in cp.get("functions", [])]
                imps      = [i.get("module") for i in cp.get("imports", []) if i.get("module")]

                # Compute diff_gaps from enriched_changes with FAIL/ATTRIBUTION_GAP status
                _dg = []
                for _eid, _ch in ctx_data.get("changes", []):
                    _ts = _ch.get("test_status", "")
                    if _ts in ("FAIL", "ATTRIBUTION_GAP"):
                        _dg.append(f"{_eid}: {_ts}")

                # Build call_graph summary from ctx_data
                _cg_data = ctx_data.get("call_graph_data", {})
                _cg_summary = []
                if _cg_data:
                    # Show import dependencies
                    for _imp_dep in _cg_data.get("imports", []):
                        _cg_summary.append(f"→ {_imp_dep}")
                    # Show reverse dependencies (who imports us)
                    for _importer in _cg_data.get("importers", []):
                        _cg_summary.append(f"← {_importer}")
                    # Show top call edges (func→target)
                    for _edge in _cg_data.get("edges", [])[:10]:
                        _cg_summary.append(_edge)
                    _total = _cg_data.get("edge_count", 0)
                    if _total > 10:
                        _cg_summary.append(f"... +{_total - 10} more edges")

                return {
                    "file": cp.get("file_path", "").split("/")[-1],
                    "classes": cls_names,
                    "functions": fn_names,
                    "imports": imps,
                    "verb_category": cp.get("_verb", "mixed"),
                    "complexity": c_score,
                    "diff_gaps": _dg,
                    "call_graph": _cg_summary,
                    "runtime_events": [],
                    "docstring": (cp.get("docstring") or "")[:50],
                    "line_count": cp.get("loc") or cp.get("line_count") or cp.get("lines") or "?"
                }
            return {}
        elif layer_id == "query_weights":
            # G2: GapAnalyzer 5W1H metastate — populated in _do_sync from task title/description
            return ctx_data.get("query_weights_data", {})
        elif layer_id == "morph_opinion":
            # G3: Morph grounding opinion — populated in _do_sync from OsToolkitGroundingBridge
            return ctx_data.get("morph_opinion_data", {})
        elif layer_id == "business_domain":
            # N_ctx2: domain classification from TemporalNarrativeEngine (_temporal written in _do_sync)
            temporal = ctx_data.get("_temporal", {})
            return {
                "dominant_domain":   temporal.get("dominant_domain", "{unknown}"),
                "domain_confidence": temporal.get("domain_confidence", 0.0),
                "phase_name":        temporal.get("phase_name", "{unknown}"),
                "files_touched":     temporal.get("files_touched_count", 0),
            }
        elif layer_id == "temporal_aoe":
            # O3a: extend with session_history sub-fields from ChatHistoryManager + lineage_tracker
            _ta = {
                "peer_file":         ctx_data.get("peer_file", "{unknown}"),
                "peer_category":     ctx_data.get("peer_category", "{unknown}"),
                "cluster_id":        ctx_data.get("cluster_id", "{none}"),
                "time_delta_min":    ctx_data.get("time_delta_min", 0),
            }
            try:
                import sys as _sys_ta
                _chat_dir = str(Path(__file__).parents[5] / "custom_code_tab")
                if _chat_dir not in _sys_ta.path:
                    _sys_ta.path.insert(0, _chat_dir)
                from chat_history_manager import ChatHistoryManager as _CHM
                _chm = _CHM()
                _convs = _chm.list_conversations()
                if _convs:
                    _latest = _convs[0]
                    _ta["session_history_recent_id"] = _latest.get("session_id", "{none}")
                    _ta["session_history_provider"]  = _latest.get("metadata", {}).get("provider", "ollama")
                else:
                    _ta["session_history_recent_id"] = "{none}"
                    _ta["session_history_provider"]  = "{none}"
            except Exception:
                _ta["session_history_recent_id"] = "{unavailable}"
                _ta["session_history_provider"]  = "{unavailable}"
            try:
                from lineage_tracker import get_tracker as _get_lt_ta
                _lt_ta = _get_lt_ta()
                _all_m = _lt_ta.get_morph_interactions()
                _acc_m = _lt_ta.get_morph_interactions(accepted_only=True)
                _ta["session_history_accepted_ratio"] = (
                    f"{len(_acc_m)}/{len(_all_m)}" if _all_m else "0/0"
                )
            except Exception:
                _ta["session_history_accepted_ratio"] = "{unavailable}"
            return _ta
        elif layer_id == "graph_topology":
            # O3b: biosphere_manifest.json → ecosystem layer; fallback to pymanifest/state.json
            try:
                _bio_path = Path(__file__).parents[5] / "map_tab" / "biosphere_manifest.json"
                if _bio_path.exists():
                    import json as _jbio
                    _bio = _jbio.loads(_bio_path.read_text(encoding="utf-8"))
                    _entities = _bio.get("entities", [])
                    return {
                        "ecosystem_layer": _bio.get("ecosystem_summary", "{unknown}"),
                        "entity_count":    len(_entities),
                        "top_node":        _entities[0].get("name", "{none}") if _entities else "{none}",
                        "biosphere_phase": "F",
                    }
            except Exception:
                pass
            # Fallback: pymanifest/state.json call_graph topology
            try:
                _state_path = Path(__file__).parents[5].parent / "pymanifest" / "state.json"
                if _state_path.exists():
                    import json as _jst
                    _state = _jst.loads(_state_path.read_text(encoding="utf-8"))
                    _cg = _state.get("call_graph", {})
                    return {
                        "ecosystem_layer":  "pymanifest_callgraph",
                        "crash_points":     len(_cg.get("crash_points", [])),
                        "suspicious_paths": len(_cg.get("suspicious_paths", {})),
                        "graph_sha":        _cg.get("graph_sha", "{none}"),
                    }
            except Exception:
                pass
            return {"ecosystem_layer": "{biosphere_not_loaded}"}
        # Other layers not yet wired — return empty so all show ○ (unwired)
        return {}

    def show_tasks_for_file(self, rel_file):
        """Filter the task board to show only tasks whose wherein matches rel_file.
        Called by _tab_action_tasks() in the main GUI when 'Tasks for Tab' is clicked."""
        import os as _os
        self._file_filter = _os.path.basename(rel_file) if rel_file else None
        # Switch right_notebook to the Tasks tab (index 0)
        try:
            self.right_notebook.select(0)
        except Exception:
            pass
        self.refresh_task_board()
        if self._file_filter:
            self.board_filter_label.config(text=f"Filter: {self._file_filter}")
            self.board_filter_label.pack(side=tk.LEFT, padx=(6, 0))
            self.board_filter_clear_btn.pack(side=tk.LEFT, padx=(2, 0))
        else:
            self.board_filter_label.pack_forget()
            self.board_filter_clear_btn.pack_forget()

    def _clear_board_file_filter(self):
        """Remove the active file filter and reload the full task board."""
        self._file_filter = None
        self.board_filter_label.pack_forget()
        self.board_filter_clear_btn.pack_forget()
        self.refresh_task_board()

    def _show_new_task_dialog(self):
        """Dialog to create a new task and append it to plans/todos.json.
        #[Mark:D2-NEW-TASK-DIALOG]
        """
        dialog = tk.Toplevel(self)
        dialog.title("New Task")
        dialog.geometry("560x620")
        dialog.resizable(False, False)
        dialog.transient(self.winfo_toplevel())
        dialog.grab_set()

        pad = dict(padx=8, pady=4)

        tk.Label(dialog, text="Title *", anchor="w").grid(row=0, column=0, sticky="w", **pad)
        title_var = tk.StringVar()
        tk.Entry(dialog, textvariable=title_var, width=48).grid(row=0, column=1, sticky="ew", **pad)

        tk.Label(dialog, text="Priority", anchor="w").grid(row=1, column=0, sticky="w", **pad)
        priority_var = tk.StringVar(value="P1")
        tk.OptionMenu(dialog, priority_var, "P0", "P1", "P2", "P3").grid(row=1, column=1, sticky="w", **pad)

        tk.Label(dialog, text="Wherein\n(file or Class::method)", anchor="w", justify="left").grid(row=2, column=0, sticky="w", **pad)
        wherein_var = tk.StringVar()
        tk.Entry(dialog, textvariable=wherein_var, width=48).grid(row=2, column=1, sticky="ew", **pad)

        tk.Label(dialog, text="Project ID", anchor="w").grid(row=3, column=0, sticky="w", **pad)
        project_var = tk.StringVar()
        tk.Entry(dialog, textvariable=project_var, width=48).grid(row=3, column=1, sticky="ew", **pad)

        tk.Label(dialog, text="Description", anchor="w").grid(row=4, column=0, sticky="nw", **pad)
        desc_text = tk.Text(dialog, width=48, height=6, wrap=tk.WORD)
        desc_text.grid(row=4, column=1, sticky="ew", **pad)

        # ── Extended fields (Big Bang Layer 1A + 3B) ──
        tk.Label(dialog, text="Plan Doc", anchor="w").grid(row=5, column=0, sticky="w", **pad)
        plan_doc_frame = tk.Frame(dialog)
        plan_doc_frame.grid(row=5, column=1, sticky="ew", **pad)
        plan_doc_var = tk.StringVar()
        tk.Entry(plan_doc_frame, textvariable=plan_doc_var, width=40).pack(side=tk.LEFT, fill=tk.X, expand=True)
        def _browse_plan():
            f = filedialog.askopenfilename(
                initialdir=str(Path(self.base_path)),
                filetypes=[("Markdown", "*.md"), ("All", "*.*")])
            if f:
                try:
                    plan_doc_var.set(str(Path(f).relative_to(Path(self.base_path).parent)))
                except ValueError:
                    plan_doc_var.set(f)
        tk.Button(plan_doc_frame, text="...", command=_browse_plan, width=3).pack(side=tk.LEFT, padx=2)

        tk.Label(dialog, text="Project Ref", anchor="w").grid(row=6, column=0, sticky="w", **pad)
        project_ref_var = tk.StringVar()
        _proj_choices = []
        try:
            _proj_path = Path(self.base_path) / "projects.json"
            if _proj_path.exists():
                _pdata = json.loads(_proj_path.read_text(encoding="utf-8"))
                _proj_choices = [p.get("project_id", "") for p in _pdata.get("projects", []) if p.get("project_id")]
        except Exception:
            pass
        if _proj_choices:
            tk.OptionMenu(dialog, project_ref_var, "", *_proj_choices).grid(row=6, column=1, sticky="w", **pad)
        else:
            tk.Entry(dialog, textvariable=project_ref_var, width=48).grid(row=6, column=1, sticky="ew", **pad)

        tk.Label(dialog, text="Test Expectations\n(one per line)", anchor="w", justify="left").grid(row=7, column=0, sticky="nw", **pad)
        test_exp_text = tk.Text(dialog, width=48, height=4, wrap=tk.WORD)
        test_exp_text.grid(row=7, column=1, sticky="ew", **pad)

        tk.Label(dialog, text="Marks\n(comma-sep)", anchor="w", justify="left").grid(row=8, column=0, sticky="w", **pad)
        marks_var = tk.StringVar()
        tk.Entry(dialog, textvariable=marks_var, width=48).grid(row=8, column=1, sticky="ew", **pad)

        status_lbl = tk.Label(dialog, text="", fg="red", anchor="w")
        status_lbl.grid(row=9, column=0, columnspan=2, sticky="w", **pad)

        dialog.columnconfigure(1, weight=1)

        def _submit():
            title = title_var.get().strip()
            if not title:
                status_lbl.config(text="Title is required.")
                return
            priority = priority_var.get()
            wherein = wherein_var.get().strip()
            project_id = project_var.get().strip()
            description = desc_text.get("1.0", tk.END).strip()
            plan_doc = plan_doc_var.get().strip()
            project_ref = project_ref_var.get().strip()
            test_expectations = [line.strip() for line in test_exp_text.get("1.0", tk.END).strip().splitlines() if line.strip()]
            marks = [m.strip() for m in marks_var.get().split(",") if m.strip()]

            # Generate task ID: task_{YYMM}_{seq}
            now = datetime.datetime.now()
            date_part = now.strftime("%y%m")
            todos_path = Path(self.base_path) / "todos.json"
            seq = 1
            try:
                if todos_path.exists():
                    with open(todos_path, encoding="utf-8") as f:
                        todos_data = json.load(f)
                    import re as _re_nt
                    for val in todos_data.values():
                        if isinstance(val, dict):
                            for k in val:
                                m = _re_nt.match(r"task_(\d{4})_(\d+)", k)
                                if m and m.group(1) == date_part:
                                    seq = max(seq, int(m.group(2)) + 1)
            except Exception:
                pass

            task_id = f"task_{date_part}_{seq}"
            iso_now = now.isoformat()
            new_task = {
                "id": task_id,
                "title": title,
                "status": "pending",
                "priority": priority,
                "wherein": wherein,
                "project_id": project_id,
                "description": description,
                "plan_doc": plan_doc,
                "project_ref": project_ref,
                "test_expectations": test_expectations,
                "marks": marks,
                "test_status": "pending",
                "created_at": iso_now,
                "updated_at": iso_now,
                "task_ids": [],
                "meta_links": [f"{plan_doc}#task-{task_id}"] if plan_doc else []
            }

            # Append to todos.json
            try:
                todos_data = {}
                if todos_path.exists():
                    with open(todos_path, encoding="utf-8") as f:
                        todos_data = json.load(f)
                phase_key = f"phase_new_{date_part}"
                if phase_key not in todos_data:
                    todos_data[phase_key] = {}
                todos_data[phase_key][task_id] = new_task
                with open(todos_path, "w", encoding="utf-8") as f:
                    json.dump(todos_data, f, indent=2)
            except Exception as e:
                status_lbl.config(text=f"Error saving: {e}")
                return

            # Write seed task_context file
            try:
                tasks_dir = Path(self.base_path) / "Tasks"
                tasks_dir.mkdir(exist_ok=True)
                enriched_changes_fresh = {}
                try:
                    import recovery_util as _ru_nt
                    _vm_nt = _ru_nt.load_version_manifest()
                    enriched_changes_fresh = _vm_nt.get("enriched_changes", {})
                except Exception:
                    pass
                ctx = self._get_task_aoe_context(new_task, enriched_changes_fresh, {}, task_id=task_id)
                ctx_serial = dict(ctx)
                ctx_serial["changes"] = [
                    {"eid": eid, **{k: v for k, v in ch.items()}}
                    for eid, ch in ctx.get("changes", [])
                ]
                ctx_serial["expected_diffs"] = self._parse_expected_diffs(
                    project_id, wherein, Path(self.base_path)
                )
                ctx_serial["_meta"] = {
                    "task_id": task_id, "title": title,
                    "wherein": wherein, "generated": iso_now, "source": "new_task_dialog"
                }
                ctx_serial["plan_doc"] = plan_doc
                ctx_serial["project_ref"] = project_ref
                ctx_serial["test_expectations"] = test_expectations
                ctx_serial["test_status"] = "pending"
                ctx_serial["test_results"] = []
                ctx_path = tasks_dir / f"task_context_{task_id}.json"
                with open(ctx_path, "w", encoding="utf-8") as f:
                    json.dump(ctx_serial, f, indent=2, default=str)
            except Exception:
                pass

            dialog.destroy()
            self.status_bar.config(text=f"Created {task_id}: {title}")
            self.sync_todos()  # full pipeline: todos.json → latest_sync.json → refresh board

        btn_frame = tk.Frame(dialog)
        btn_frame.grid(row=10, column=0, columnspan=2, pady=8)
        tk.Button(btn_frame, text="Create Task", command=_submit,
                  bg="#2ecc71", fg="white", padx=12).pack(side=tk.LEFT, padx=6)
        tk.Button(btn_frame, text="Cancel", command=dialog.destroy, padx=12).pack(side=tk.LEFT, padx=6)

    def _collect_context_block(self, start_iid=None):
        """Walk the task subtree collecting all vector nodes.
        Returns a formatted multi-line string (the full AoE context block).
        If start_iid is a layer header, collect only that layer.
        If start_iid is a vector node, return just that field.
        If start_iid is a task node (or None → use selection), collect all layers.
        """
        # Resolve the anchor node
        if start_iid is None:
            sel = self.board_tree.selection()
            if not sel:
                return "(no task selected)"
            start_iid = sel[0]

        data = self._board_tasks.get(start_iid, {})
        node_type = data.get("type", "")

        # Walk up to task if needed
        task_node = None
        if node_type == "task":
            task_node = start_iid
        elif node_type in ("layer_header", "vector", "sentinel", "peer", "ux_ref",
                           "blame", "attribution"):
            parent = self.board_tree.parent(start_iid)
            while parent:
                p_data = self._board_tasks.get(parent, {})
                if p_data.get("type") == "task":
                    task_node = parent
                    break
                parent = self.board_tree.parent(parent)
        else:
            # Walk up for any unregistered node
            parent = self.board_tree.parent(start_iid)
            while parent:
                p_data = self._board_tasks.get(parent, {})
                if p_data.get("type") == "task":
                    task_node = parent
                    break
                parent = self.board_tree.parent(parent)

        if not task_node:
            return "(could not resolve task)"

        task_data = self._board_tasks.get(task_node, {})
        tid   = task_data.get("tid", "?")
        title = task_data.get("title", "?")
        wherein = task_data.get("wherein", "{unknown}")

        lines = [
            f"# AoE Context Block — {tid}",
            f"# {title}",
            f"# wherein: {wherein}",
            f"# generated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}",
            "",
        ]

        # If single layer requested
        target_layer_id = None
        if node_type == "layer_header":
            target_layer_id = data.get("layer_id")
        elif node_type == "vector":
            # Single field copy
            vid = data.get("display", data.get("vector_id", "?"))
            val = data.get("value") or "{unknown}"
            return f"{tid} | {vid}: {val}"

        # Auto-compute context data for unpopulated layers (instead of "expand to populate")
        _ctx_data = None
        ctx_tuple = self._board_lazy_ctx.get(task_node)
        if ctx_tuple:
            if len(ctx_tuple) == 4:
                _c_tid, _c_t, _c_ec, _c_fs = ctx_tuple
                _ctx_data = self._get_task_aoe_context(_c_t, _c_ec, _c_fs, task_id=_c_tid)
            else:
                _c_t, _c_ec, _c_fs = ctx_tuple
                _ctx_data = self._get_task_aoe_context(_c_t, _c_ec, _c_fs)
        if not _ctx_data:
            # Fallback: load from task_context file
            try:
                _tc_path = Path(self.base_path) / "Tasks" / f"task_context_{tid}.json"
                if _tc_path.exists():
                    with open(_tc_path, 'r') as f:
                        _ctx_data = json.load(f)
                    # Reconstruct changes tuples from serialized format
                    _ctx_data['changes'] = [
                        (c.get('eid', '?'), c) for c in _ctx_data.get('changes', [])
                    ]
            except Exception:
                pass

        # Walk task's children (layer headers)
        for layer_node in self.board_tree.get_children(task_node):
            l_data = self._board_tasks.get(layer_node, {})
            if l_data.get("type") != "layer_header":
                continue
            lid = l_data.get("layer_id", "")
            if target_layer_id and lid != target_layer_id:
                continue
            layer_cfg = next(
                (l for l in (_AOE_CONFIG or {}).get("layers", []) if l["id"] == lid), {}
            )
            lines.append(f"## {layer_cfg.get('icon','▶')} {layer_cfg.get('display', lid)}")

            if l_data.get("populated"):
                # Layer is expanded in treeview — read from tree nodes
                self._collect_layer_from_tree(layer_node, lines)
            elif _ctx_data:
                # Layer not expanded — compute from context data directly
                self._collect_layer_from_ctx(lid, layer_cfg, _ctx_data, lines)
            else:
                lines.append("  (no context data available)")
            lines.append("")

        return "\n".join(lines)

    def _collect_layer_from_tree(self, layer_node, lines):
        """Collect vector data from expanded treeview layer nodes."""
        for vec_node in self.board_tree.get_children(layer_node):
            vd = self._board_tasks.get(vec_node, {})
            if vd.get("type") == "vector":
                disp = vd.get("display", "?")
                val  = vd.get("value") or "{unknown}"
                wired = vd.get("wired", False)
                prefix = "📌" if wired and val != "{unknown}" else ("❓" if wired else "○")
                lines.append(f"  {prefix} {disp}: {val}")
            elif vd.get("type") == "attribution":
                eid = vd.get("eid", "?")
                verb = vd.get("verb", "?")
                risk = vd.get("risk_level", "?")
                fname = vd.get("file", "?").split("/")[-1]
                lines.append(f"  Δ {eid}: {verb} [{risk}] {fname}")
                for sub_node in self.board_tree.get_children(vec_node):
                    sd = self._board_tasks.get(sub_node, {})
                    if sd.get("type") == "vector":
                        s_disp = sd.get("display", "?")
                        s_val  = sd.get("value") or "{unknown}"
                        s_wired = sd.get("wired", False)
                        s_prefix = "📌" if s_wired and s_val != "{unknown}" else ("❓" if s_wired else "○")
                        lines.append(f"    {s_prefix} {s_disp}: {s_val}")

    def _collect_layer_from_ctx(self, layer_id, layer_cfg, ctx_data, lines):
        """Collect vector data directly from computed context (for unexpanded layers)."""
        vectors = layer_cfg.get("vectors", [])

        # Attribution layer: show change groups with their vectors
        if layer_id == "attribution":
            changes = ctx_data.get("changes", [])
            if not changes:
                lines.append("  (no enriched_changes matched this task file)")
                return
            for eid_or_tuple in changes:
                if isinstance(eid_or_tuple, (list, tuple)) and len(eid_or_tuple) == 2:
                    eid, ch = eid_or_tuple
                else:
                    ch = eid_or_tuple if isinstance(eid_or_tuple, dict) else {}
                    eid = ch.get("eid", "?")
                risk = ch.get("risk_level", "LOW")
                verb = ch.get("verb", "?")
                fname = ch.get("file", "{unknown}").split("/")[-1]
                lines.append(f"  Δ {eid}: {verb} [{risk}] {fname}")
                src_data = {**ch, "event_id": eid}
                for vec in vectors:
                    disp, field, wired = vec["display"], vec["field"], vec.get("wired", False)
                    value = src_data.get(field)
                    if isinstance(value, list):
                        value = ", ".join(str(v) for v in value[:5]) if value else None
                    if not wired:
                        lines.append(f"    ○ {disp}: (unwired — Phase {vec.get('phase','?')})")
                    elif value:
                        is_risk = vec.get("risk_field", False)
                        icon = "⚠️" if is_risk and str(value).upper() not in ("LOW", "") else "📌"
                        lines.append(f"    {icon} {disp}: {str(value)[:80]}")
                    else:
                        lines.append(f"    ❓ {disp}: {{unknown}}")
            return

        # All other layers: resolve source data and show vectors
        src_data = self._resolve_layer_source(layer_id, ctx_data)
        for vec in vectors:
            disp  = vec["display"]
            field = vec["field"]
            wired = vec.get("wired", False)
            phase = vec.get("phase", "?")
            is_risk = vec.get("risk_field", False)
            value = src_data.get(field) if src_data else None
            if isinstance(value, list):
                value = ", ".join(str(v) for v in value[:5]) if value else None
            if not wired:
                lines.append(f"  ○ {disp}: (unwired — Phase {phase})")
            elif value:
                icon = "⚠️" if is_risk and str(value).upper() not in ("LOW", "") else "📌"
                lines.append(f"  {icon} {disp}: {str(value)[:80]}")
            else:
                lines.append(f"  ❓ {disp}: {{unknown}}")

    def _debug_aoe_context(self):
        """Open a debug popup showing the raw _get_task_aoe_context output for the selected task.
        Useful for verifying data flow through the 78-vector attribution system.
        #[Mark:DEBUG-AOE]
        """
        try:
            self._debug_aoe_context_inner()
        except Exception as e:
            try:
                self.status_bar.config(text=f"Debug AoE error: {e}")
            except Exception:
                pass
            if _TRAINER_LOG_AVAILABLE:
                import traceback
                _trainer_log.log_message(f"PLANNER: {{warn}} Debug AoE error: {e}\n{traceback.format_exc()[:500]}")

    def _debug_aoe_context_inner(self):
        sel = self.board_tree.selection()
        anchor = sel[0] if sel else None
        if not anchor:
            self.status_bar.config(text="Select a task or child node first.")
            return

        # Walk up to find the task node
        task_node = None
        d = self._board_tasks.get(anchor, {})
        if d.get("type") == "task":
            task_node = anchor
        else:
            parent = self.board_tree.parent(anchor)
            while parent:
                pd = self._board_tasks.get(parent, {})
                if pd.get("type") == "task":
                    task_node = parent
                    break
                parent = self.board_tree.parent(parent)

        if not task_node:
            self.status_bar.config(text="Could not resolve parent task.")
            return

        t_data = self._board_tasks.get(task_node, {})
        ctx_tuple = self._board_lazy_ctx.get(task_node)
        if not ctx_tuple:
            self.status_bar.config(text="No context tuple found — try Refresh Board first.")
            return

        if len(ctx_tuple) == 4:
            tid, t, enriched_changes, fs_manifest = ctx_tuple
            ctx = self._get_task_aoe_context(t, enriched_changes, fs_manifest, task_id=tid)
        else:
            t, enriched_changes, fs_manifest = ctx_tuple
            ctx = self._get_task_aoe_context(t, enriched_changes, fs_manifest)

        # Format the debug output
        lines = [
            f"=== AoE Debug: {t_data.get('tid', '?')} ===",
            f"title:       {t_data.get('title', '?')}",
            f"wherein:     {t_data.get('wherein', '{none}')}",
            f"status:      {t_data.get('status', '?')}",
            "",
            f"--- CHANGES ({len(ctx.get('changes', []))}) ---",
        ]
        for eid, ch in ctx.get("changes", []):
            lines.append(f"  {eid}: {ch.get('verb','?')} [{ch.get('risk_level','?')}]"
                         f"  file={ch.get('file','?')}"
                         f"  classes={ch.get('classes',[])}"
                         f"  methods={ch.get('methods',[])} ")
        lines += [
            "",
            f"--- BLAME ({len(ctx.get('blame', []))}) ---",
        ]
        for b in ctx.get("blame", []):
            lines.append(f"  target={b.get('target','?')}  file={b.get('file','?')}"
                         f"  line={b.get('line','?')}  modified={b.get('modified_this_version','?')}")
        lines += [
            "",
            f"--- UX_EVENTS ({len(ctx.get('ux_events', []))}) ---",
        ]
        for evt in ctx.get("ux_events", [])[-10:]:
            lines.append(f"  [{evt.get('tab','?')}] {evt.get('event_type','?')}"
                         f"  outcome={evt.get('outcome','?')}"
                         f"  wherein={evt.get('wherein','?')}")
        lines += [
            "",
            f"--- PEERS ({len(ctx.get('peers', []))}) ---",
        ]
        for p in ctx.get("peers", []):
            lines.append(f"  {p.get('name','?')} ({p.get('cat','?')})")
        lines += [
            "",
            f"--- DNA: {ctx.get('dna', '{none}')} ---",
            f"--- TOOL PROFILE: {ctx.get('tool_profile', '{none}')} ---",
            "",
            f"enriched_changes keys in manifest: {len(enriched_changes)}",
            f"filesync manifest loaded: {bool(fs_manifest)}",
        ]

        # Launch popup
        popup = tk.Toplevel(self)
        popup.title(f"🔬 AoE Debug — {t_data.get('tid', '?')}")
        popup.geometry("760x520")
        txt = scrolledtext.ScrolledText(popup, wrap=tk.WORD, font=("Consolas", 9))
        txt.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)
        txt.insert("1.0", "\n".join(lines))
        txt.config(state=tk.DISABLED)
        tk.Button(popup, text="Close", command=popup.destroy).pack(pady=4)
        popup.transient(self.winfo_toplevel())
        popup.grab_set()

    def _show_attribution_editor(self, task_id=None):
        """Dialog to edit task_context attribution data.
        #[Mark:ATTRIBUTION-EDITOR]
        """
        if not task_id:
            sel = self.board_tree.selection()
            if not sel:
                self.status_bar.config(text="Select a task first.")
                return
            anchor = sel[0]
            d = self._board_tasks.get(anchor, {})
            if d.get("type") == "task":
                task_id = d.get("tid", "")
            else:
                parent = self.board_tree.parent(anchor)
                while parent:
                    pd = self._board_tasks.get(parent, {})
                    if pd.get("type") == "task":
                        task_id = pd.get("tid", "")
                        break
                    parent = self.board_tree.parent(parent)

        if not task_id:
            self.status_bar.config(text="Could not resolve task ID.")
            return

        ctx_path = Path(self.base_path) / "Tasks" / f"task_context_{task_id}.json"
        ctx_data = {}
        if ctx_path.exists():
            try:
                ctx_data = json.loads(ctx_path.read_text(encoding="utf-8"))
            except Exception:
                pass

        # Also load from todos.json
        todo_data = {}
        todos_path = Path(self.base_path) / "todos.json"
        if todos_path.exists():
            try:
                _all_todos = json.loads(todos_path.read_text(encoding="utf-8"))
                for phase, tasks in _all_todos.items():
                    if isinstance(tasks, dict) and task_id in tasks:
                        todo_data = tasks[task_id]
                        break
            except Exception:
                pass

        dialog = tk.Toplevel(self)
        dialog.title(f"Edit Attribution: {task_id}")
        dialog.geometry("580x520")
        dialog.transient(self.winfo_toplevel())
        dialog.grab_set()
        pad = dict(padx=8, pady=3)

        tk.Label(dialog, text=f"Task: {task_id}", font=("Consolas", 11, "bold")).grid(row=0, column=0, columnspan=3, sticky="w", **pad)

        tk.Label(dialog, text="Plan Doc:", anchor="w").grid(row=1, column=0, sticky="w", **pad)
        plan_var = tk.StringVar(value=todo_data.get("plan_doc", ctx_data.get("plan_doc", "")))
        plan_entry = tk.Entry(dialog, textvariable=plan_var, width=44)
        plan_entry.grid(row=1, column=1, sticky="ew", **pad)
        def _browse():
            f = filedialog.askopenfilename(initialdir=str(Path(self.base_path)), filetypes=[("Markdown", "*.md")])
            if f:
                try:
                    plan_var.set(str(Path(f).relative_to(Path(self.base_path).parent)))
                except ValueError:
                    plan_var.set(f)
        tk.Button(dialog, text="...", command=_browse, width=3).grid(row=1, column=2, **pad)

        tk.Label(dialog, text="Project Ref:", anchor="w").grid(row=2, column=0, sticky="w", **pad)
        pref_var = tk.StringVar(value=todo_data.get("project_ref", ctx_data.get("project_ref", "")))
        tk.Entry(dialog, textvariable=pref_var, width=44).grid(row=2, column=1, sticky="ew", **pad)

        tk.Label(dialog, text="Test Expectations:", anchor="w").grid(row=3, column=0, sticky="nw", **pad)
        texp_text = tk.Text(dialog, width=44, height=4, wrap=tk.WORD)
        texp_text.grid(row=3, column=1, columnspan=2, sticky="ew", **pad)
        _existing_exp = todo_data.get("test_expectations", ctx_data.get("test_expectations", []))
        if _existing_exp:
            texp_text.insert("1.0", "\n".join(_existing_exp))

        tk.Label(dialog, text="Marks:", anchor="w").grid(row=4, column=0, sticky="w", **pad)
        marks_var_ed = tk.StringVar(value=", ".join(todo_data.get("marks", ctx_data.get("marks", []))))
        tk.Entry(dialog, textvariable=marks_var_ed, width=44).grid(row=4, column=1, sticky="ew", **pad)

        tk.Label(dialog, text="Test Status:", anchor="w").grid(row=5, column=0, sticky="w", **pad)
        tstat_var = tk.StringVar(value=todo_data.get("test_status", ctx_data.get("test_status", "pending")))
        tk.OptionMenu(dialog, tstat_var, "pending", "in_progress", "deferred", "passed", "failed").grid(row=5, column=1, sticky="w", **pad)

        # Associated Events display
        tk.Label(dialog, text="Events:", anchor="w").grid(row=6, column=0, sticky="nw", **pad)
        ev_frame = tk.Frame(dialog)
        ev_frame.grid(row=6, column=1, columnspan=2, sticky="ew", **pad)
        ev_listbox = tk.Listbox(ev_frame, height=5, width=50)
        ev_listbox.pack(fill=tk.BOTH, expand=True)
        _events = todo_data.get("task_ids", ctx_data.get("task_ids", []))
        for ev in _events:
            ev_listbox.insert(tk.END, ev)

        dialog.columnconfigure(1, weight=1)

        def _save():
            new_plan = plan_var.get().strip()
            new_pref = pref_var.get().strip()
            new_texp = [l.strip() for l in texp_text.get("1.0", tk.END).strip().splitlines() if l.strip()]
            new_marks = [m.strip() for m in marks_var_ed.get().split(",") if m.strip()]
            new_tstat = tstat_var.get()

            # Update task_context
            ctx_data["plan_doc"] = new_plan
            ctx_data["project_ref"] = new_pref
            ctx_data["test_expectations"] = new_texp
            ctx_data["marks"] = new_marks
            ctx_data["test_status"] = new_tstat
            try:
                ctx_path.parent.mkdir(exist_ok=True)
                ctx_path.write_text(json.dumps(ctx_data, indent=2, default=str), encoding="utf-8")
            except Exception as e:
                self.status_bar.config(text=f"Save ctx error: {e}")

            # Update todos.json
            if todos_path.exists():
                try:
                    _all = json.loads(todos_path.read_text(encoding="utf-8"))
                    for phase, tasks in _all.items():
                        if isinstance(tasks, dict) and task_id in tasks:
                            tasks[task_id]["plan_doc"] = new_plan
                            tasks[task_id]["project_ref"] = new_pref
                            tasks[task_id]["test_expectations"] = new_texp
                            tasks[task_id]["marks"] = new_marks
                            tasks[task_id]["test_status"] = new_tstat
                            break
                    todos_path.write_text(json.dumps(_all, indent=2), encoding="utf-8")
                except Exception:
                    pass

            dialog.destroy()
            self.status_bar.config(text=f"Attribution updated for {task_id}")

        btn_f = tk.Frame(dialog)
        btn_f.grid(row=7, column=0, columnspan=3, pady=8)
        tk.Button(btn_f, text="Save", command=_save, bg="#2ecc71", fg="white", padx=12).pack(side=tk.LEFT, padx=6)
        tk.Button(btn_f, text="Cancel", command=dialog.destroy, padx=12).pack(side=tk.LEFT, padx=6)

    def _parse_expected_diffs(self, project_id, wherein, plans_path):
        """Parse </Diffs> block from Epics/, Plans/, *_project/ dirs for expected file changes.
        Returns list of {file, type, mark} dicts. #[Mark:D4-EXPECTED-DIFFS]
        """
        results = []
        try:
            # Search multiple directories for plan docs with Diffs blocks
            # E3: Include Morph-generated plans (plans/Morph/*.md)
            search_dirs = [plans_path / "Epics", plans_path / "Plans", plans_path / "Morph"]
            for d in plans_path.iterdir():
                if d.is_dir() and (d.name.endswith("_project") or d.name.endswith("_development")):
                    search_dirs.append(d)

            md_files = []
            for sd in search_dirs:
                if sd.exists():
                    md_files.extend(sd.rglob("*.md"))

            target_file = None
            if project_id:
                _pid = project_id.replace(" ", "_").lower()
                for md in md_files:
                    if _pid in md.stem.lower() or md.stem.lower() in _pid:
                        target_file = md
                        break
            # Fallback: match by wherein filename in doc content
            if target_file is None and wherein:
                _wf = Path(wherein).stem.lower()
                for md in md_files:
                    try:
                        _peek = md.read_text(encoding="utf-8", errors="replace")[:2000]
                        if _wf in _peek.lower() and "</Diffs>" in _peek:
                            target_file = md
                            break
                    except Exception:
                        pass
            if target_file is None:
                # Fall back to first file that has a Diffs block
                for md in md_files:
                    try:
                        if "</Diffs>" in md.read_text(encoding="utf-8", errors="replace")[:2000]:
                            target_file = md
                            break
                    except Exception:
                        pass
            if target_file is None:
                return results

            import re as _re
            text = target_file.read_text(encoding="utf-8", errors="replace")
            # Extract between </Diffs>: and <Diffs/>
            diffs_match = _re.search(r'</Diffs>.*?\n(.*?)<Diffs/>', text, _re.DOTALL)
            if not diffs_match:
                return results
            block = diffs_match.group(1)
            # Parse file path lines and associated Mark/Event lines
            current_file = None
            for line in block.splitlines():
                line = line.strip()
                path_match = _re.match(r'^-?(/[\w/._-]+\.\w+)', line)
                if path_match:
                    current_file = path_match.group(1)
                    # Determine type from context (New/Modify/Remove hints)
                    diff_type = "MODIFY"
                    if "new" in line.lower():
                        diff_type = "NEW"
                    elif "remove" in line.lower():
                        diff_type = "REMOVE"
                    results.append({"file": current_file.split("/")[-1], "full_path": current_file, "type": diff_type, "marks": []})
                mark_match = _re.search(r'#\[(Mark|Event):[^\]]+\]', line)
                if mark_match and results:
                    results[-1].setdefault("marks", []).append(mark_match.group(0))
        except Exception:
            pass
        return results

    def _get_task_aoe_context(self, task, enriched_changes, fs_manifest, task_id=None):
        """Pool context from multi-system manifests for a single task.
        #[Mark:P2-AoE-Context]
        """
        ctx = {
            'peers': [], 'dna': None, 'changes': [], 'ux_events': [],
            'tool_profile': None, 'blame': [], 'code_profile': None,
            'cluster_id': None, 'time_delta_min': 0
        }
        wherein = task.get('wherein', '')
        task_file = wherein.split('/')[-1] if wherein else ""

        # ── 0. Code Profile (py_manifest + enriched_changes fallback) ──
        if task_file:
            try:
                _data_root = Path(__file__).parents[5]
                _pm_path = _data_root / "pymanifest" / "py_manifest_augmented.json"
                if not _pm_path.exists():
                    _pm_path = _data_root / "pymanifest" / "py_manifest.json"

                if _pm_path.exists():
                    with open(_pm_path, 'r') as f:
                        _pm = json.load(f)

                    # Search for file match by basename, preferring non-backup paths
                    _candidates = []
                    for fpath, info in _pm.get("files", {}).items():
                        if fpath.endswith(f"/{task_file}") or fpath == task_file:
                            _is_backup = "/backup/" in fpath or "/history/" in fpath or "/archive/" in fpath
                            _candidates.append((fpath, info, _is_backup))
                    # Prefer non-backup paths
                    _candidates.sort(key=lambda x: (x[2], len(x[0])))
                    if _candidates:
                        ctx['code_profile'] = _candidates[0][1]
                    # Stem-only fallback if exact match missed
                    if not ctx['code_profile']:
                        _stem = Path(task_file).stem
                        for fpath, info in _pm.get("files", {}).items():
                            if Path(fpath).stem == _stem and "/backup/" not in fpath and "/history/" not in fpath:
                                ctx['code_profile'] = info
                                break
            except Exception:
                pass

            # Fallback: synthesize code_profile from enriched_changes if manifest miss
            if not ctx['code_profile'] and enriched_changes:
                _ec_matches = [ch for ch in enriched_changes.values()
                               if ch.get("file", "").endswith(task_file)]
                if _ec_matches:
                    _latest = max(_ec_matches, key=lambda c: c.get("timestamp", ""))
                    _all_classes = []
                    _all_methods = []
                    _all_imports = []
                    for ch in _ec_matches:
                        _all_classes.extend(ch.get("classes", []))
                        _all_methods.extend(ch.get("methods", []))
                        _all_imports.extend(ch.get("imports_added", []))
                    ctx['code_profile'] = {
                        "file_path": _latest.get("file", task_file),
                        "classes": [{"name": c} for c in set(_all_classes) if c],
                        "functions": [{"name": m} for m in set(_all_methods) if m],
                        "imports": [{"module": i} for i in set(_all_imports) if i],
                        "loc": _latest.get("lines_changed", "?"),
                        "line_count": _latest.get("lines_changed", "?"),
                        "_source": "enriched_changes",
                        "_verb": _latest.get("verb", "mixed"),
                    }

        # ── 0b. Call Graph Extraction (from py_manifest dependencies + calls) ──
        if task_file and ctx.get('code_profile'):
            try:
                _data_root_cg = Path(__file__).parents[5]
                _pm_cg_path = _data_root_cg / "pymanifest" / "py_manifest_augmented.json"
                if not _pm_cg_path.exists():
                    _pm_cg_path = _data_root_cg / "pymanifest" / "py_manifest.json"

                if _pm_cg_path.exists():
                    with open(_pm_cg_path, 'r') as f:
                        _pm_cg = json.load(f)

                    _pm_files = _pm_cg.get("files", {})
                    _cg_edges = []        # outgoing call edges
                    _cg_imports = []      # import dependencies (this file → imported files)
                    _cg_importers = []    # reverse dependencies (files that import this one)
                    _matched_path = None

                    # Find the full path for task_file
                    for fpath in _pm_files:
                        if fpath.endswith(f"/{task_file}") or fpath == task_file:
                            if "/backup/" not in fpath and "/history/" not in fpath:
                                _matched_path = fpath
                                break

                    if _matched_path:
                        _file_info = _pm_files[_matched_path]

                        # 1. Import dependencies (this file depends on)
                        for dep in _file_info.get("dependencies", []):
                            _dep_name = dep.split("/")[-1] if "/" in dep else dep
                            _cg_imports.append(_dep_name)

                        # 2. Function call edges (function → called_function @ line)
                        for fn in _file_info.get("functions", []):
                            for call_target, call_line in fn.get("calls", []):
                                _cg_edges.append(f"{fn.get('name', '?')}→{call_target}:{call_line}")
                        for cls in _file_info.get("classes", []):
                            for method in cls.get("methods", []):
                                for call_target, call_line in method.get("calls", []):
                                    _cg_edges.append(f"{cls.get('name','?')}.{method.get('name','?')}→{call_target}:{call_line}")

                        # 3. Reverse dependencies (who imports this file?)
                        for fpath2, info2 in _pm_files.items():
                            if fpath2 == _matched_path:
                                continue
                            if "/backup/" in fpath2 or "/history/" in fpath2 or "/archive/" in fpath2:
                                continue
                            _imp_bn = fpath2.split("/")[-1]
                            if ".backup_" in _imp_bn or _imp_bn.startswith("LEGACY"):
                                continue
                            for dep2 in info2.get("dependencies", []):
                                if dep2 == _matched_path:
                                    _importer_name = fpath2.split("/")[-1]
                                    _cg_importers.append(_importer_name)
                                    break

                    # Store in context — cap edges to prevent bloat
                    ctx['call_graph_data'] = {
                        "edges": _cg_edges[:50],
                        "imports": _cg_imports,
                        "importers": _cg_importers,
                        "edge_count": len(_cg_edges),
                        "matched_path": _matched_path or "",
                    }
            except Exception:
                pass

        # ── 1. Temporal Inference (Filesync) ──
        if fs_manifest:
            # Phase B: Cluster ID & Time Delta
            ctx['cluster_id'] = fs_manifest.get('metadata', {}).get('session_id', '{unknown}')
            try:
                gen_ts = fs_manifest.get('metadata', {}).get('generated')
                if gen_ts:
                    # Parse ISO timestamp (simple version)
                    # 2026-02-05T23:37:57.465837
                    dt_gen = datetime.datetime.fromisoformat(gen_ts)
                    dt_now = datetime.datetime.now()
                    delta = dt_now - dt_gen
                    ctx['time_delta_min'] = int(delta.total_seconds() / 60)
            except Exception:
                pass

            files_data = fs_manifest.get('files', {}) if task_file else {}
            for fid, info in files_data.items():
                if info.get('original_name') == task_file or task_file in info.get('original_path', ''):
                    proj_id = info.get('project_association')
                    if proj_id and proj_id in fs_manifest.get('projects', {}):
                        proj = fs_manifest['projects'][proj_id]
                        for rel_id in proj.get('file_ids', []):
                            if rel_id != fid and rel_id in files_data:
                                rf = files_data[rel_id]
                                ctx['peers'].append({
                                    'name': rf.get('original_name', 'unknown'),
                                    'path': rf.get('original_path', 'unknown'),
                                    'cat': rf.get('category', 'unknown')
                                })
                    break

        # ── 1b. Temporal fallback from enriched_changes (when no Filesync) ──
        if (not ctx['cluster_id'] or ctx['cluster_id'] == '{unknown}') and task_file and enriched_changes:
            _ec_temporal = [(eid, ch) for eid, ch in enriched_changes.items()
                           if ch.get("file", "").endswith(task_file)]
            if _ec_temporal:
                _ts_list = sorted([ch.get("timestamp", "") for _, ch in _ec_temporal])
                ctx['cluster_id'] = f"ec_{task_file[:20]}"
                if len(_ts_list) >= 2:
                    try:
                        _t0 = datetime.datetime.fromisoformat(_ts_list[0])
                        _t1 = datetime.datetime.fromisoformat(_ts_list[-1])
                        ctx['time_delta_min'] = int((_t1 - _t0).total_seconds() / 60)
                    except Exception:
                        pass
            # Peers: other files in enriched_changes (co-changed files)
            if not ctx['peers'] and enriched_changes:
                _seen = set()
                for _eid, _ch in enriched_changes.items():
                    _other = _ch.get("file", "").split("/")[-1]
                    if _other and _other != task_file and _other not in _seen:
                        ctx['peers'].append({'name': _other, 'cat': _ch.get("verb", "?")})
                        _seen.add(_other)
                    if len(ctx['peers']) >= 5:
                        break

        # ── 1c. Temporal from history_temporal_manifest.json (ALWAYS augment) ──
        if task_file:
            try:
                _tm_path = (Path(__file__).parents[5] / "tabs" / "action_panel_tab"
                           / "babel_data" / "timeline" / "manifests" / "history_temporal_manifest.json")
                if _tm_path.exists():
                    with open(_tm_path, 'r') as f:
                        _tm = json.load(f)
                    _tf_stem = Path(task_file).stem.lower()
                    for _hname, _hprof in _tm.get("profiles", {}).items():
                        if _tf_stem in _hname.lower():
                            # Augment: prefer history data when current is empty/zero
                            if not ctx['cluster_id'] or ctx['cluster_id'] == '{unknown}':
                                ctx['cluster_id'] = f"hist_{_hname[:30]}"
                            if not ctx['time_delta_min'] or ctx['time_delta_min'] == '{unknown}':
                                ctx['time_delta_min'] = int(_hprof.get("span_days", 0) * 24 * 60)
                            ctx['_temporal'] = {
                                "backup_count": _hprof.get("backup_count", 0),
                                "first_seen": _hprof.get("first_seen", ""),
                                "last_seen": _hprof.get("last_seen", ""),
                                "activity_score": _hprof.get("activity_score", 0),
                            }
                            break
            except Exception:
                pass

        # ── 2. System DNA (Os_Toolkit) ──
        if wherein:
            dna_patterns = {
                '/etc/passwd': 'User account management',
                '/etc/hosts': 'Static hostname resolution',
                '/var/log/syslog': 'General system event logging',
                'systemd': 'System and service manager'
            }
            for pattern, desc in dna_patterns.items():
                if pattern in wherein:
                    ctx['dna'] = desc
                    break

        # ── 3. Tool Profile (Onboarder) ──
        if wherein:
            try:
                babel_root = Path(__file__).parents[5] / "tabs" / "action_panel_tab"
                menu_file = babel_root / "babel_data" / "inventory" / "consolidated_menu.json"
                if menu_file.exists():
                    with open(menu_file, 'r') as f:
                        menu_data = json.load(f)
                    _tf_stem = Path(task_file).stem.lower() if task_file else ""
                    for tool in menu_data.get('tools', []):
                        # Match by source_path, command, name, or display_name
                        _tp = (tool.get('source_path') or '').lower()
                        _tn = (tool.get('name') or tool.get('display_name') or '').lower()
                        _tc = (tool.get('command') or '').lower()
                        if ((_tp and task_file and task_file.lower() in _tp)
                                or (_tf_stem and (_tf_stem in _tn or _tf_stem in _tc))):
                            ctx['tool_profile'] = f"{tool.get('display_name')} ({tool.get('category')})"
                            if tool.get('source_path'):
                                ctx['tool_profile'] += f" [{tool['source_path']}]"
                            break
            except Exception: pass

        # ── 4. Changes (Enriched Attribution) ──
        # Combine explicit task_ids AND file-based matching (tasks own their file's events)
        if not task_id:
            task_id = task.get('id', '')

        _seen_eids = set()

        # Pass 1: explicit task_ids field
        if task_id:
            for eid, ch in enriched_changes.items():
                _tids = ch.get('task_ids') or []
                if task_id in _tids:
                    ctx['changes'].append((eid, ch))
                    _seen_eids.add(eid)

        # Pass 2: file-based matching (ALWAYS runs — tasks own all events for their file)
        if task_file:
            task_base = os.path.basename(task_file) if task_file else ""
            for eid, ch in enriched_changes.items():
                if eid in _seen_eids:
                    continue
                ch_file = ch.get('file', '')
                ch_base = os.path.basename(ch_file) if ch_file else ""
                if task_base and ch_base == task_base:
                    ctx['changes'].append((eid, ch))
                    _seen_eids.add(eid)
                elif task_file and ch_file.endswith(task_file):
                    ctx['changes'].append((eid, ch))
                    _seen_eids.add(eid)

        # Pass 3: event ID mentioned in task title/description
        if not ctx['changes']:
            for eid, ch in enriched_changes.items():
                if eid in task.get('title', '') or eid in str(task.get('description', '')):
                    ctx['changes'].append((eid, ch))

        # ── 5. UX Baseline (Logs) ──
        if _TRAINER_LOG_AVAILABLE and hasattr(_trainer_log, 'UX_EVENT_LOG'):
            task_stem = task_file.replace('.py', '') if task_file else ''
            for evt in _trainer_log.UX_EVENT_LOG[-50:]:
                tab_name = evt.get('tab', '')
                ev_wherein = evt.get('wherein', '')
                if task_file and (
                    task_file in tab_name or
                    (task_stem and task_stem in tab_name) or
                    (ev_wherein and task_file in ev_wherein)
                ):
                    ctx['ux_events'].append(evt)
            # UX fallback: if no specific match, use most recent event as baseline
            if not ctx['ux_events'] and _trainer_log.UX_EVENT_LOG:
                latest_evt = _trainer_log.UX_EVENT_LOG[-1]
                ctx['ux_events'].append({
                    **latest_evt,
                    '_fallback': True,
                    'detail': f"(no direct UX events for {task_file}; showing latest system event)"
                })

        # ── 6. Blame (version_manifest versions + enriched_changes fallback) ──
        try:
            vm_path = Path(__file__).parents[5] / "backup" / "version_manifest.json"
            if vm_path.exists():
                with open(vm_path, 'r') as f:
                    vm = json.load(f)
                for ts, ver in list(vm.get('versions', {}).items())[-20:]:
                    for b in ver.get('blame', []):
                        if task_file and task_file in b.get('file', ''):
                            ctx['blame'].append({
                                'version': ts,
                                'target': b.get('target', '{unknown}'),
                                'file': b.get('file', ''),
                                'line': b.get('line', '?'),
                                'modified_this_version': b.get('modified_this_version', False)
                            })
                # Fallback: synthesize blame from enriched_changes if no formal blame
                if not ctx['blame'] and ctx.get('changes'):
                    for eid, ch in ctx['changes'][:5]:
                        _methods = ch.get('methods', [])
                        _target = f"{ch.get('file','').split('/')[-1]}::{_methods[0]}" if _methods else ch.get('file','').split('/')[-1]
                        ctx['blame'].append({
                            'version': ch.get('version_ts', ch.get('timestamp', '')[:15]),
                            'target': _target,
                            'file': ch.get('file', ''),
                            'line': ch.get('lines_changed', '?'),
                            'modified_this_version': True
                        })
        except Exception:
            pass

        # ── 6b. Plan & Project Context (Big Bang Layer 1C) ──
        plan_doc = task.get("plan_doc", "")
        if plan_doc:
            _plan_path = Path(self.base_path) / plan_doc.replace("plans/", "")
            if not _plan_path.exists():
                _plan_path = Path(self.base_path).parent / plan_doc
            if _plan_path.exists():
                try:
                    _plan_content = _plan_path.read_text(encoding='utf-8')[:2000]
                    ctx['plan_summary'] = _plan_content[:500]
                    ctx['plan_doc'] = plan_doc
                except Exception:
                    pass

        project_ref = task.get("project_ref", "")
        if project_ref:
            _proj_path = Path(self.base_path) / "projects.json"
            if _proj_path.exists():
                try:
                    _projs = json.loads(_proj_path.read_text(encoding='utf-8'))
                    _proj = next((p for p in _projs.get("projects", [])
                                 if p.get("project_id") == project_ref), None)
                    if _proj:
                        ctx['project_context'] = _proj
                except Exception:
                    pass

        # ── 7. Temporal Fallback (DeBug logs when filesync is empty) ──
        if not ctx['peers'] and task_file:
            try:
                debug_dir = Path(__file__).parents[6] / "DeBug"
                if debug_dir.exists():
                    import re as _re
                    attribution_pattern = _re.compile(
                        r'CHANGE ATTRIBUTION.*?Event:\s*\[?(#\[Event:\d+\])\]?.*?'
                        r'File:\s*(.+?)\n.*?Risk:\s*(\w+)',
                        _re.DOTALL
                    )
                    logs = sorted(debug_dir.glob("debug_log_*.txt"))[-3:]
                    seen = set()
                    for log_path in logs:
                        try:
                            text = log_path.read_text(errors='ignore')
                            for m in attribution_pattern.finditer(text):
                                eid, fpath, risk = m.group(1), m.group(2).strip(), m.group(3).strip()
                                peer_name = fpath.split('/')[-1]
                                if peer_name != task_file and peer_name not in seen:
                                    seen.add(peer_name)
                                    ctx['peers'].append({
                                        'name': peer_name,
                                        'path': fpath,
                                        'cat': f'log-{risk}',
                                        'eid': eid
                                    })
                        except Exception:
                            pass
            except Exception:
                pass

        # ── 8. Similarity Scoring from PyManifest (Big Bang Layer 4C) ──
        if ctx.get('code_profile') and task_file:
            try:
                _data_root_sim = Path(__file__).parents[5]
                _pm_sim_path = _data_root_sim / "pymanifest" / "py_manifest_augmented.json"
                if not _pm_sim_path.exists():
                    _pm_sim_path = _data_root_sim / "pymanifest" / "py_manifest.json"
                if _pm_sim_path.exists():
                    with open(_pm_sim_path, 'r') as f:
                        _pm_sim = json.load(f)
                    _task_fns = set(fn.get("name", "") for fn in ctx['code_profile'].get("functions", []) if fn.get("name"))
                    if _task_fns:
                        _similar = []
                        for fpath, info in _pm_sim.get("files", {}).items():
                            if fpath.endswith(task_file):
                                continue
                            _other_fns = set(fn.get("name", "") for fn in info.get("functions", []) if fn.get("name"))
                            _overlap = _task_fns & _other_fns
                            if _overlap:
                                _similar.append({"file": fpath, "shared_functions": list(_overlap),
                                                "confidence": len(_overlap) / max(len(_task_fns), 1)})
                        ctx['similar_files'] = sorted(_similar, key=lambda x: x['confidence'], reverse=True)[:5]
            except Exception:
                pass

        # ── G2: Load query_weights_data + morph_opinion_data from stored task_context ──
        # During sync these are written fresh; during display we load from the persisted file.
        if task_id and not ctx.get('query_weights_data'):
            try:
                _tc_path = Path(self.base_path) / "Tasks" / f"task_context_{task_id}.json"
                if _tc_path.exists():
                    with open(_tc_path, encoding='utf-8') as _tcf:
                        _tc_stored = json.load(_tcf)
                    if _tc_stored.get('query_weights_data'):
                        ctx['query_weights_data'] = _tc_stored['query_weights_data']
                    if _tc_stored.get('morph_opinion_data'):
                        ctx['morph_opinion_data'] = _tc_stored['morph_opinion_data']
            except Exception:
                pass

        return ctx

    def copy_babel_context_block(self, start_iid=None):
        """Copy the AoE context block to clipboard using lazy-load tree state.
        #[Mark:BABEL_CONTEXT_CLIPBOARD]
        start_iid: if None, use current selection. Pass a layer_node iid for layer-only copy.
        """
        try:
            self._copy_babel_context_block_inner(start_iid)
        except Exception as e:
            try:
                self.status_bar.config(text=f"Clipboard error: {e}")
            except Exception:
                pass

    def _copy_babel_context_block_inner(self, start_iid=None):
        block = self._collect_context_block(start_iid)
        if not block or block.startswith("("):
            messagebox.showinfo("Context", block or "No context available.")
            return

        # Use tkinter's built-in clipboard (works on X11/Wayland without xclip/xsel).
        # Falls back to pyperclip only if tkinter clipboard raises.
        copied = False
        try:
            self.winfo_toplevel().clipboard_clear()
            self.winfo_toplevel().clipboard_append(block)
            copied = True
        except Exception:
            pass
        if not copied:
            try:
                import pyperclip
                pyperclip.copy(block)
                copied = True
            except Exception as e:
                messagebox.showerror("Clipboard Error",
                    f"Could not copy to clipboard:\n{e}\n\nInstall xclip: sudo apt install xclip")
                return
        # Status feedback
        if start_iid:
            d = self._board_tasks.get(start_iid, {})
            if d.get("type") == "layer_header":
                lid = d.get("layer_id", "?")
                self.status_bar.config(text=f"📋 Layer '{lid}' context copied to clipboard.")
                return
        sel = self.board_tree.selection()
        if sel:
            d = self._board_tasks.get(sel[0], {})
            tid = d.get("tid", "?")
            self.status_bar.config(text=f"📋 Babel Context for {tid} copied to clipboard.")

    def _on_board_select(self, event):
        """Show task details in status bar on single-click."""
        sel = self.board_tree.selection()
        if not sel:
            return
        t = self._board_tasks.get(sel[0])
        if t:
            wh = t.get("wherein", "")
            self.status_bar.config(text=f"[{t.get('status','')}] {t.get('tid','')} ∈ {wh}")

    def _on_board_double_click(self, event):
        """Open wherein file on double-click, or UndoChangesDialog for attribution/gap rows."""
        sel = self.board_tree.selection()
        if sel:
            d = self._board_tasks.get(sel[0], {})
            if d.get("type") in ("attribution_gap", "attribution"):
                eid = d.get("eid")
                if eid:
                    try:
                        import sys, os as _os
                        _here = _os.path.dirname(__file__)
                        sys.path.insert(0, _os.path.join(_here, "..", "..", "..", "..", ".."))
                        from tabs.settings_tab.undo_changes import UndoChangesDialog
                        import recovery_util as _ru
                        manifest = _ru.load_version_manifest()
                        UndoChangesDialog(self.parent, eid, manifest, initial_tab="blame_risk")
                    except Exception as _e:
                        self.status_bar.config(text=f"Cannot open dialog: {_e}")
                return
        self._board_open_file()

    def _board_open_file(self):
        """Open the wherein file of the selected task in the left doc viewer."""
        sel = self.board_tree.selection()
        if not sel:
            return
        t = self._board_tasks.get(sel[0])
        if not t:
            return
        wherein = t.get("wherein", "")
        if not wherein:
            self.status_bar.config(text="No file path for this task")
            return
        # Try resolving relative to Trainer/Data/
        _data_root = Path(__file__).parents[5]
        candidate = _data_root / wherein.lstrip("/")
        if candidate.exists():
            self.open_file(str(candidate))
        else:
            self.status_bar.config(text=f"File not found: {wherein}")

    def _update_checklist_task(self, tid, new_status):
        """Update a task's status in plans/checklist.json by task id."""
        checklist_path = Path(self.base_path) / "checklist.json"
        if not checklist_path.exists():
            return False
        try:
            with open(checklist_path, encoding='utf-8') as f:
                cl = json.load(f)
            updated = False
            for section in cl.values():
                if isinstance(section, dict):
                    for item in section.get("items", []):
                        if isinstance(item, dict) and item.get("id") == tid:
                            item["status"] = new_status
                            updated = True
            if updated:
                with open(checklist_path, 'w', encoding='utf-8') as f:
                    json.dump(cl, f, indent=2)
            return updated
        except Exception as e:
            self.status_bar.config(text=f"checklist update error: {e}")
            return False

    def mark_task_complete(self):
        """Mark selected task as COMPLETE in checklist.json + refresh board."""
        sel = self.board_tree.selection()
        if not sel:
            return
        t = self._board_tasks.get(sel[0])
        if not t:
            return
        tid = t.get("tid", "")
        ok = self._update_checklist_task(tid, "COMPLETE")
        if ok:
            self.status_bar.config(text=f"✅ {tid} marked COMPLETE")
            if _TRAINER_LOG_AVAILABLE:
                _trainer_log.log_ux_event(
                    "ag_knowledge", "MARK_COMPLETE", "board_mark_complete_button",
                    outcome="success", detail=f"tid={tid}",
                    wherein="PlannerSuite::mark_task_complete"
                )
            # Refresh board + sync latest
            self.sync_todos()
        else:
            self.status_bar.config(text=f"Task {tid} not found in checklist.json (todos.json source — edit manually)")

    def _prompt_version_gate_tasks(self, task_ids):
        """Prompt user to mark tasks complete after a stable version save.
        Called directly from InteractiveTrainerGUI._do_choice() when choice=save/save_default.
        task_ids: list of task IDs active during the session.
        """
        open_tasks = [
            _t for _t in self._board_tasks.values()
            if _t.get("tid") in task_ids
            and _t.get("status", "").upper() not in ("COMPLETE", "DONE", "CLOSED")
        ]
        if not open_tasks:
            return

        dlg = tk.Toplevel(self)
        dlg.title("Version Saved — Complete Related Tasks?")
        dlg.geometry("500x340")
        dlg.transient(self.winfo_toplevel())
        # Non-blocking: no grab_set() so shutdown can proceed

        tk.Label(dlg, text="✅ Version marked stable. Mark related tasks complete?",
                 font=("Consolas", 10, "bold")).pack(pady=(14, 6))

        _vars = {}
        for _t in open_tasks[:10]:
            _tid = _t.get("tid", "?")
            _v = tk.BooleanVar(value=False)
            _vars[_tid] = _v
            tk.Checkbutton(dlg, text=f"[{_tid}] {_t.get('title', _tid)[:65]}",
                           variable=_v, anchor="w").pack(fill=tk.X, padx=20, pady=1)

        def _confirm():
            for _tid, _v in _vars.items():
                if _v.get():
                    self._update_checklist_task(_tid, "COMPLETE")
                    if _TRAINER_LOG_AVAILABLE:
                        _trainer_log.log_ux_event(
                            "version_gate", "MARK_COMPLETE", "version_gate_task_prompt",
                            outcome="success", detail=f"tid={_tid}",
                            wherein="PlannerSuite::_prompt_version_gate_tasks"
                        )
            self.sync_todos()
            dlg.destroy()

        _btn = tk.Frame(dlg)
        _btn.pack(pady=14)
        tk.Button(_btn, text="Mark Selected Complete", command=_confirm,
                  bg="#2ecc71", fg="white", padx=12).pack(side=tk.LEFT, padx=6)
        tk.Button(_btn, text="Skip", command=dlg.destroy, padx=12).pack(side=tk.LEFT)

    def _complete_selected_task(self):
        """Completion gate: check test_expectations before marking complete."""
        sel = self.board_tree.selection()
        if not sel:
            return
        t = self._board_tasks.get(sel[0])
        if not t or t.get("type") != "task":
            return
        tid = t.get("tid", "")
        title = t.get("title", tid)

        # Load test_expectations from todos.json
        expectations = []
        try:
            _todos_path = Path(self.base_path) / "todos.json"
            if _todos_path.exists():
                _todos = json.loads(_todos_path.read_text(encoding="utf-8"))
                if isinstance(_todos, dict):
                    for _phase, _tblock in _todos.items():
                        if isinstance(_tblock, dict) and tid in _tblock:
                            expectations = _tblock[tid].get("test_expectations", [])
                            break
                elif isinstance(_todos, list):
                    for _t in _todos:
                        if _t.get("id") == tid:
                            expectations = _t.get("test_expectations", [])
                            break
        except Exception:
            pass

        if not expectations:
            # No expectations — simple confirmation
            if messagebox.askyesno("Complete Task",
                    f"Mark '{title}' as complete?\n\nNo test expectations defined."):
                self.mark_task_complete()
            return

        # Show checklist dialog with expectations
        gate_dlg = tk.Toplevel(self)
        gate_dlg.title(f"Verify: {tid}")
        gate_dlg.geometry("480x360")
        gate_dlg.transient(self)

        tk.Label(gate_dlg, text=f"Test Expectations for {tid}",
                 font=('Consolas', 10, 'bold')).pack(pady=(10, 5))
        tk.Label(gate_dlg, text=title, fg='#555').pack(pady=(0, 10))

        check_vars = []
        checks_frame = tk.Frame(gate_dlg)
        checks_frame.pack(fill=tk.BOTH, expand=True, padx=15)

        for exp in expectations:
            var = tk.BooleanVar(value=False)
            check_vars.append(var)
            tk.Checkbutton(checks_frame, text=exp, variable=var,
                           anchor='w', wraplength=420,
                           font=('Consolas', 9)).pack(fill=tk.X, pady=2)

        def _on_confirm():
            passed = sum(1 for v in check_vars if v.get())
            total = len(check_vars)

            if passed == total:
                # All passed — complete
                gate_dlg.destroy()
                self.mark_task_complete()
                self.status_bar.config(text=f"✅ {tid} complete ({passed}/{total} passed)")
            elif passed == 0:
                messagebox.showwarning("No Tests Passed",
                    f"0/{total} expectations checked.\nCannot mark complete.", parent=gate_dlg)
            else:
                # Partial — ask or set test:in_progress
                if messagebox.askyesno("Partial Pass",
                        f"{passed}/{total} expectations passed.\nMark as complete anyway?",
                        parent=gate_dlg):
                    gate_dlg.destroy()
                    self.mark_task_complete()
                else:
                    gate_dlg.destroy()
                    # Set test:in_progress status
                    self._update_checklist_task(tid, "IN_PROGRESS")
                    # Write test_status to todos.json
                    try:
                        _todos_path = Path(self.base_path) / "todos.json"
                        if _todos_path.exists():
                            _todos = json.loads(_todos_path.read_text(encoding="utf-8"))
                            _updated = False
                            if isinstance(_todos, dict):
                                for _phase, _tblock in _todos.items():
                                    if isinstance(_tblock, dict) and tid in _tblock:
                                        _tblock[tid]["test_status"] = "test:in_progress"
                                        _tblock[tid]["updated_at"] = datetime.datetime.now().isoformat()
                                        _updated = True
                                        break
                            if _updated:
                                _todos_path.write_text(json.dumps(_todos, indent=2), encoding="utf-8")
                    except Exception:
                        pass
                    self.status_bar.config(text=f"⏳ {tid} → test:in_progress ({passed}/{total})")
                    self.refresh_task_board()

        btn_frame = tk.Frame(gate_dlg)
        btn_frame.pack(fill=tk.X, padx=15, pady=10)
        tk.Button(btn_frame, text="Cancel", command=gate_dlg.destroy).pack(side=tk.RIGHT, padx=5)
        tk.Button(btn_frame, text="✓ Confirm", command=_on_confirm,
                  fg='#27ae60', font=('Consolas', 9, 'bold')).pack(side=tk.RIGHT, padx=5)

    def mark_task_in_progress(self):
        """Mark selected task as IN_PROGRESS in checklist.json + refresh board."""
        sel = self.board_tree.selection()
        if not sel:
            return
        t = self._board_tasks.get(sel[0])
        if not t:
            return
        tid = t.get("tid", "")
        ok = self._update_checklist_task(tid, "IN_PROGRESS")
        if ok:
            self.status_bar.config(text=f"▶ {tid} marked IN_PROGRESS")
            self.sync_todos()
        else:
            self.status_bar.config(text=f"{tid} not in checklist.json")

    def _activate_selected_task(self):
        """Set the selected task as the active task (currently-working-on pointer)."""
        sel = self.board_tree.selection()
        if not sel:
            return
        t = self._board_tasks.get(sel[0])
        if not t or t.get("type") != "task":
            return
        tid = t.get("tid", "")
        wherein = t.get("task", {}).get("wherein", "")

        # Mark IN_PROGRESS if not already
        task_data = t.get("task", {})
        if task_data.get("status") not in ("IN_PROGRESS", "COMPLETE"):
            self._update_checklist_task(tid, "IN_PROGRESS")

        # Set active and persist
        self._active_task_id = tid
        state = self._load_planner_state()
        state["active_task_id"] = tid
        state["active_task_wherein"] = wherein
        state["activated_at"] = datetime.datetime.now().isoformat()
        cfg = Path(self.base_path) / "config.json"
        try:
            cfg.write_text(json.dumps(state, indent=2), encoding="utf-8")
        except Exception:
            pass
        self._refresh_active_label()
        self.status_bar.config(text=f"🎯 Active: {tid} — {wherein}")
        if _TRAINER_LOG_AVAILABLE:
            _trainer_log.log_ux_event(
                "ag_knowledge", "TASK_ACTIVATE", tid,
                outcome="activated", detail=f"wherein={wherein}",
                wherein="PlannerSuite::_activate_selected_task"
            )

    def _cycle_active_task(self):
        """Cycle through IN_PROGRESS tasks in board order."""
        in_progress = []
        for iid in self.board_tree.get_children():
            t = self._board_tasks.get(iid, {})
            task_data = t.get("task", {})
            if task_data.get("status") in ("IN_PROGRESS", "READY"):
                in_progress.append(iid)
        if not in_progress:
            self.status_bar.config(text="No active/ready tasks to cycle")
            return
        self._board_cycle_idx = (self._board_cycle_idx + 1) % len(in_progress)
        next_iid = in_progress[self._board_cycle_idx]
        self.board_tree.selection_set(next_iid)
        self.board_tree.see(next_iid)
        # Activate it
        self._activate_selected_task()

    def _refresh_active_label(self):
        """Update the active task label in toolbar."""
        if hasattr(self, '_active_label'):
            if self._active_task_id:
                self._active_label.config(text=f"Active: {self._active_task_id}")
            else:
                self._active_label.config(text="")

    def _board_sort_by(self, col):
        """Sort task board rows by the clicked column header."""
        col_map = {"status": 0, "wherein": 1, "source": 2, "who": 3, "type": 4, "created": 5, "project": 6, "gaps": 7}
        col_idx = col_map.get(col)
        if col_idx is None:
            return
        # Toggle sort direction
        if not hasattr(self, '_board_sort_reverse'):
            self._board_sort_reverse = {}
        reverse = self._board_sort_reverse.get(col, False)
        self._board_sort_reverse[col] = not reverse
        # Gather top-level children (groups) and sort their task children
        for group_node in self.board_tree.get_children():
            children = list(self.board_tree.get_children(group_node))
            if not children:
                continue
            # Sort by column value
            def sort_key(iid):
                vals = self.board_tree.item(iid, "values")
                if col_idx < len(vals):
                    return str(vals[col_idx]).lower()
                return ""
            children.sort(key=sort_key, reverse=reverse)
            for idx, child in enumerate(children):
                self.board_tree.move(child, group_node, idx)
        arrow = "▼" if reverse else "▲"
        self.status_bar.config(text=f"Sorted by {col} {arrow}")

    # ── Check Completion (enhanced) ───────────────────────────────────────────

    def check_completion(self):
        """Check task completion status"""
        completion_window = tk.Toplevel(self)
        completion_window.title("Task Completion Check")
        completion_window.geometry("400x300")
        
        # Simple completion check
        text_widget = scrolledtext.ScrolledText(completion_window, wrap=tk.WORD)
        text_widget.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        report = "Task Completion Check\n"
        report += "=" * 30 + "\n\n"
        
        # Check for TODO/FIXME comments in marked Python files
        todo_count = 0
        for file_path in self.marked_files:
            if file_path.endswith('.py'):
                try:
                    with open(file_path, 'r') as f:
                        lines = f.readlines()
                    
                    for i, line in enumerate(lines, 1):
                        if 'TODO' in line or 'FIXME' in line:
                            todo_count += 1
                            report += f"{os.path.basename(file_path)}:{i}: {line.strip()}\n"
                except:
                    pass
        
        report += f"\nTotal TODO/FIXME items: {todo_count}\n"

        # --- Runtime bugs from logger_util {warn} pipeline ---
        try:
            bugs_path = Path(__file__).parents[5] / "plans" / "runtime_bugs.json"
            if bugs_path.exists():
                with open(bugs_path, 'r') as _bf:
                    bugs = json.load(_bf)
                open_bugs = [b for b in bugs if b.get("status") == "OPEN"]
                report += f"\n{'='*30}\nRuntime Warns ({len(open_bugs)} open):\n"
                for bug in open_bugs[-10:]:  # Show last 10
                    report += f"  [{bug.get('type','BUG')}] {bug.get('timestamp','')} — {bug.get('message','')[:120]}\n"
        except Exception:
            pass

        text_widget.insert(1.0, report)
    
    def _build_ag_dropdown_values(self):
        """Build sectioned dropdown values for Ag Knowledge combobox."""
        values = []
        # --- Recent Files from enriched_changes ---
        try:
            _data_root = Path(__file__).parents[5]
            vm_path = _data_root / "backup" / "version_manifest.json"
            if vm_path.exists():
                vm = json.loads(vm_path.read_text(encoding="utf-8"))
                ec = vm.get("enriched_changes", {})
                # Sort by timestamp desc, take unique filenames
                sorted_ec = sorted(ec.values(), key=lambda e: e.get("timestamp", ""), reverse=True)
                seen = set()
                for e in sorted_ec:
                    fn = Path(e.get("file", "")).name
                    if fn and fn not in seen and fn.endswith(".py"):
                        seen.add(fn)
                        if len(seen) <= 10:
                            values.append(fn)
        except Exception:
            pass

        values.append("--- Commands ---")
        values.extend([
            "latest", "todo view", "todo complete --id <task_id> -z",
            "actions --list", "plan show", "stats", "suggest"
        ])

        # --- Active Task ---
        try:
            _cfg_path = Path(self.base_path) / "config.json"
            if _cfg_path.exists():
                _cfg = json.loads(_cfg_path.read_text(encoding="utf-8"))
                _atid = _cfg.get("active_task_id", "")
                _atwh = _cfg.get("active_task_wherein", "")
                if _atid:
                    values.append("--- Active Task ---")
                    values.append(f"{_atid}: {_atwh}" if _atwh else _atid)
        except Exception:
            pass

        return values

    def setup_ag_knowledge_ui(self):
        """Setup UI for Ag Knowledge tab with Query Router & Suggestions."""
        # Top: Query Target + Search Bar  #[Mark:UNIVERSAL_CATALOG_QUERY_ROUTER]
        search_frame = tk.Frame(self.ag_frame)
        search_frame.pack(fill=tk.X, padx=5, pady=5)

        # Query target dropdown (Query Router)
        tk.Label(search_frame, text="Target:").pack(side=tk.LEFT, padx=(0, 3))
        self._query_target_var = tk.StringVar(value="Os_Toolkit")
        self._query_target = ttk.Combobox(
            search_frame, textvariable=self._query_target_var,
            values=["Os_Toolkit", "Knowledge Forge", "Taxonomic Catalog", "Brain / Financial"],
            state='readonly', width=18
        )
        self._query_target.pack(side=tk.LEFT, padx=(0, 8))

        tk.Label(search_frame, text="🔍").pack(side=tk.LEFT, padx=(0, 5))
        self.ag_search_var = tk.StringVar()
        self.ag_search_entry = ttk.Combobox(
            search_frame, textvariable=self.ag_search_var,
            font=('Consolas', 10), width=40
        )
        self.ag_search_entry['values'] = self._build_ag_dropdown_values()
        self.ag_search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.ag_search_entry.bind("<Return>", self._on_ag_search)
        self.ag_search_entry.bind("<FocusIn>", self._on_ag_focus)
        self.ag_search_entry.bind("<<ComboboxSelected>>", self._on_ag_combo_selected)

        tk.Button(search_frame, text="Go", command=self._on_ag_search).pack(side=tk.LEFT, padx=5)

        # Middle: Results Display
        self.ag_display = scrolledtext.ScrolledText(
            self.ag_frame, wrap=tk.WORD, font=('Consolas', 9), bg='#f8f9fa', height=20
        )
        self.ag_display.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Configure text tags for 6W1H highlighting
        self.ag_display.tag_configure("section_header", font=('Consolas', 10, 'bold'), foreground='#2c3e50')
        self.ag_display.tag_configure("change_event", foreground='#e74c3c')
        self.ag_display.tag_configure("ast_profile", foreground='#2980b9')
        self.ag_display.tag_configure("task_assoc", foreground='#27ae60')
        self.ag_display.tag_configure("temporal", foreground='#8e44ad')
        self.ag_display.tag_configure("narrative", foreground='#b8860b', font=('Consolas', 10, 'italic'))

        # Bottom: Suggestions Area
        self.ag_suggestions_frame = tk.LabelFrame(self.ag_frame, text="💡 Actions", padx=5, pady=5)
        self.ag_suggestions_frame.pack(fill=tk.X, padx=5, pady=5)
        self.ag_suggestions_lbl = tk.Label(self.ag_suggestions_frame, text="Run a search to see actions.", fg="#777")
        self.ag_suggestions_lbl.pack(anchor="w")

        # Initial help text
        self.ag_display.insert(tk.END, "Query Router — select a target and search.\n\n", "section_header")
        self.ag_display.insert(tk.END, "Targets:\n", "section_header")
        self.ag_display.insert(tk.END, "  Os_Toolkit        — 6W1H query, latest, suggest, stats\n")
        self.ag_display.insert(tk.END, "  Knowledge Forge   — Search entities (species, animals, plants)\n")
        self.ag_display.insert(tk.END, "  Taxonomic Catalog — Search Catalogue of Life (143K+ species)\n")
        self.ag_display.insert(tk.END, "  Brain / Financial — Financial project & session data\n\n")
        self.ag_display.insert(tk.END, "Os_Toolkit commands:\n", "section_header")
        self.ag_display.insert(tk.END, "  latest          — Full system state report\n")
        self.ag_display.insert(tk.END, "  todo view        — List all tasks\n")
        self.ag_display.insert(tk.END, "  suggest <file>   — Get suggestions for a file\n\n")
        self.ag_display.insert(tk.END, "Or type a search term and press Go.\n")
        self.ag_display.config(state=tk.DISABLED)

    def _on_ag_focus(self, event=None):
        """Show help when combobox is focused with no text."""
        if not self.ag_search_var.get().strip():
            # Refresh dropdown values
            self.ag_search_entry['values'] = self._build_ag_dropdown_values()

    def _on_ag_combo_selected(self, event=None):
        """Handle combobox selection — skip separator lines."""
        val = self.ag_search_var.get().strip()
        if val.startswith("---"):
            self.ag_search_var.set("")
            return
        # Auto-run on selection
        self._on_ag_search()

    def _run_os_toolkit(self, cmd, args):
        """Run Os_Toolkit.py subcommand and return stdout (text) or None on error."""
        if not _OS_TOOLKIT_PATH.exists():
            return None
        try:
            # cwd=map_tab to ensure consistent relative paths if needed
            _map_tab = Path(__file__).parents[5] / "tabs" / "map_tab"
            full_cmd = [sys.executable, str(_OS_TOOLKIT_PATH), cmd] + args
            proc = subprocess.run(
                full_cmd, capture_output=True, text=True, timeout=30, cwd=str(_map_tab)
            )
            return (proc.stdout or "") + (proc.stderr or "")
        except FileNotFoundError as e:
            return f"[Os_Toolkit not found: {e}]"
        except Exception as e:
            return f"[Error running Os_Toolkit: {e}]"

    def _on_global_search(self, event=None):
        """Handle search from the bottom global search bar."""
        query = self.global_search_entry.get().strip()
        if not query:
            return
            
        # Switch to Ag Knowledge tab (Index 2)
        # Note: Index might vary if tabs are reordered, but currently it's 3rd.
        # Structure: Structure(0), Checklist(1), Ag Knowledge(2), Tasks(3), Latest(4)
        # Wait, setup order is: Structure, Checklist, Ag Knowledge, Tasks, Latest. So index 2.
        try:
            self.right_notebook.select(2)
        except Exception:
            pass
            
        # Set inner search var and trigger
        if hasattr(self, 'ag_search_var'):
            self.ag_search_var.set(query)
            self._on_ag_search()
            
        # Clear global entry to indicate handoff
        self.global_search_entry.delete(0, tk.END)

    def _on_ag_search(self, event=None):
        """Execute query via Query Router — dispatches to selected backend."""
        query = self.ag_search_var.get().strip()
        if not query or query.startswith("---"):
            return

        # Strip task prefix from active task selections (e.g. "task_28_1: planner_tab.py")
        if ": " in query and query.split(":")[0].startswith("task_"):
            query = query.split(": ", 1)[1].strip()
            self.ag_search_var.set(query)

        target = self._query_target_var.get() if hasattr(self, '_query_target_var') else "Os_Toolkit"
        self.status_bar.config(text=f"Searching [{target}] for: {query}...")
        self.ag_display.config(state=tk.NORMAL)
        self.ag_display.delete(1.0, tk.END)
        self.ag_display.insert(tk.END, f"⏳ [{target}] Querying: {query}...\n")
        self.update_idletasks()

        # Route to selected backend  #[Mark:UNIVERSAL_CATALOG_QUERY_ROUTER]
        if target == "Knowledge Forge":
            self._query_knowledge_forge(query)
            return
        elif target == "Taxonomic Catalog":
            self._query_taxonomy(query)
            return
        elif target == "Brain / Financial":
            self._query_brain(query)
            return

        # Default: Os_Toolkit (existing behavior)
        _direct_commands = ("latest", "todo", "actions", "plan", "stats", "suggest", "explain")
        _is_direct = any(query.lower().startswith(cmd) for cmd in _direct_commands)

        # Auto-detect date/phase queries → route to explain
        _explain_triggers = ("yesterday", "last 24h", "last 48h", "phase-", "since ", "today")
        _is_explain_trigger = (not _is_direct and
                               any(query.lower().startswith(k) for k in _explain_triggers))

        def _do_search():
            if _is_explain_trigger:
                q_out = self._run_os_toolkit("explain", ["--since", query, "--format", "text"])
                s_out = None
            elif _is_direct:
                parts = query.split(None, 1)
                cmd = parts[0]
                args = parts[1].split() if len(parts) > 1 else []
                q_out = self._run_os_toolkit(cmd, args)
                s_out = None
            else:
                q_out = self._run_os_toolkit("query", [query])
                s_out = self._run_os_toolkit("suggest", [query])
            
            def _update_ui():
                # Display Query Results with 6W1H section highlighting
                self.ag_display.delete(1.0, tk.END)
                if q_out:
                    _section_tags = {
                        "6W1H Breakdown": "section_header",
                        "[CHANGE EVENT]": "change_event",
                        "[CHANGE EVENTS]": "change_event",
                        "[AST PROFILE]": "ast_profile",
                        "[AST DATA]": "ast_profile",
                        "[TASK ASSOCIATIONS]": "task_assoc",
                        "[TASK LINKS]": "task_assoc",
                        "[TEMPORAL PROFILE]": "temporal",
                        "[TEMPORAL DATA]": "temporal",
                        "[COLD-START]": "section_header",
                        "[ENRICHMENT]": "section_header",
                        # Explain / narrative markers (gold italic)
                        "[Phase": "narrative",
                        "Period:": "narrative",
                        "file(s) touched": "narrative",
                        "task(s) active": "narrative",
                        "Session highlights": "narrative",
                        "[No activity": "narrative",
                    }
                    for line in q_out.splitlines():
                        stripped = line.strip()
                        tag = None
                        for marker, t in _section_tags.items():
                            if marker in stripped:
                                tag = t
                                break
                        if tag:
                            self.ag_display.insert(tk.END, line + "\n", tag)
                        else:
                            self.ag_display.insert(tk.END, line + "\n")
                else:
                    self.ag_display.insert(tk.END, "[No output from query]")
                self.ag_display.config(state=tk.DISABLED)
                
                # Update Suggestions
                for widget in self.ag_suggestions_frame.winfo_children():
                    widget.destroy()
                
                suggestions = []
                try:
                    # Parse JSON output from suggest (it might have log noise before/after)
                    # Simple heuristic: find [ and ]
                    if s_out:
                        start = s_out.find("[")
                        end = s_out.rfind("]")
                        if start != -1 and end != -1:
                            json_str = s_out[start:end+1]
                            suggestions = json.loads(json_str)
                except Exception:
                    pass

                if suggestions:
                    for sg in suggestions:
                        label = sg.get("label", "?")
                        cmd = sg.get("command", "")
                        btn = tk.Button(
                            self.ag_suggestions_frame,
                            text=label,
                            command=lambda c=cmd: self._on_suggestion_click(c),
                            anchor="w", justify="left"
                        )
                        btn.pack(fill=tk.X, pady=1)
                else:
                    # Default "Explain now" button when no suggestions available
                    tk.Button(
                        self.ag_suggestions_frame,
                        text="📖 Explain last 24h",
                        command=lambda: (
                            self.ag_search_var.set("explain"),
                            self._on_ag_search()
                        ),
                        anchor="w", fg="#b8860b"
                    ).pack(fill=tk.X, pady=1)
                    tk.Label(self.ag_suggestions_frame, text="No search-specific actions.", fg="#aaa").pack(anchor="w")

                self.status_bar.config(text=f"Search complete: {query}")

            self.after(0, _update_ui)

        threading.Thread(target=_do_search, daemon=True).start()

    def _on_suggestion_click(self, command):
        """Handle clicking a suggestion action."""
        if not command: return
        
        if command.startswith("echo "):
            msg = command[5:].strip("'\"")
            messagebox.showinfo("Action", msg)
            return
            
        if command.startswith("nano ") or "Edit" in command:
            # Open in internal editor or system editor?
            # For now, just show the file path
            path = command.split()[-1].strip("'\"")
            if os.path.exists(path):
                self.open_file(path)
                return

        # For other commands, confirm execution
        _ALLOWED_PREFIXES = ("python3 ", "python ", sys.executable, "Os_Toolkit", "os_toolkit")
        if not any(command.startswith(p) for p in _ALLOWED_PREFIXES):
            messagebox.showwarning("Blocked", f"Command not in allowed prefixes:\n{command[:120]}")
            return
        if messagebox.askyesno("Execute Action", f"Run this command?\n\n{command}"):
            def _run():
                try:
                    import shlex as _shlex
                    args_list = _shlex.split(command)
                    # Replace bare python3/python with sys.executable for portability
                    if args_list and args_list[0] in ("python3", "python"):
                        args_list[0] = sys.executable
                    proc = subprocess.run(args_list, shell=False, capture_output=True, text=True, timeout=30)
                    out = (proc.stdout or "") + (proc.stderr or "")
                    self.after(0, lambda: messagebox.showinfo("Result", out[-2000:]))
                except Exception as e:
                    self.after(0, lambda: messagebox.showerror("Error", str(e)))
            threading.Thread(target=_run, daemon=True).start()

    # ── Query Router backends ────────────────────────────────────────────────
    #[Mark:UNIVERSAL_CATALOG_QUERY_ROUTER]

    def _query_knowledge_forge(self, query):
        """Search KnowledgeForgeApp entities and display results."""
        kf = getattr(self.app, 'knowledge_forge', None) if self.app else None
        self.ag_display.config(state=tk.NORMAL)
        self.ag_display.delete(1.0, tk.END)

        if not kf:
            self.ag_display.insert(tk.END, "[Knowledge Forge not available]\n")
            self.ag_display.insert(tk.END, "KnowledgeForgeApp was not loaded on startup.\n")
            self.ag_display.config(state=tk.DISABLED)
            self.status_bar.config(text="Knowledge Forge unavailable")
            return

        results = kf.search_entities(query)
        if not results:
            self.ag_display.insert(tk.END, f"No entities matching '{query}'.\n\n")
            self.ag_display.insert(tk.END, f"Total entities in store: {len(kf.entities)}\n")
            self.ag_display.insert(tk.END, "Use the Collections tab to create entities or import from taxonomy.\n")
        else:
            self.ag_display.insert(tk.END, f"Found {len(results)} entities for '{query}':\n\n", "section_header")
            for entity in results[:50]:  # cap at 50
                etype = entity.type.value if hasattr(entity.type, 'value') else str(entity.type)
                health = entity.health_status.value if hasattr(entity.health_status, 'value') else str(entity.health_status)
                self.ag_display.insert(tk.END, f"  [{etype}] ", "change_event")
                self.ag_display.insert(tk.END, f"{entity.name}")
                if entity.species:
                    self.ag_display.insert(tk.END, f" | Species: {entity.species}", "ast_profile")
                if health:
                    self.ag_display.insert(tk.END, f" | Health: {health}", "task_assoc")
                if entity.location:
                    self.ag_display.insert(tk.END, f" | Location: {entity.location}")
                self.ag_display.insert(tk.END, "\n")
                if entity.tags:
                    self.ag_display.insert(tk.END, f"    Tags: {', '.join(entity.tags)}\n", "temporal")

        self.ag_display.config(state=tk.DISABLED)
        # Clear suggestions for non-Os_Toolkit routes
        for w in self.ag_suggestions_frame.winfo_children():
            w.destroy()
        tk.Label(self.ag_suggestions_frame, text=f"Knowledge Forge: {len(results)} results", fg="#27ae60").pack(anchor="w")
        self.status_bar.config(text=f"Knowledge Forge: {len(results)} entities found")

    def _query_taxonomy(self, query):
        """Search seed_pack VernacularName.tsv in a thread."""
        self.ag_display.config(state=tk.NORMAL)
        self.ag_display.delete(1.0, tk.END)
        self.ag_display.insert(tk.END, f"⏳ Searching Catalogue of Life for '{query}'...\n")
        self.ag_display.config(state=tk.DISABLED)

        _seed_pack = Path(__file__).parents[3] / "modules" / "Imports" / "seed_pack"
        _vn_path = _seed_pack / "VernacularName.tsv"

        if not _vn_path.exists():
            self.ag_display.config(state=tk.NORMAL)
            self.ag_display.delete(1.0, tk.END)
            self.ag_display.insert(tk.END, f"[Seed pack not found at {_seed_pack}]\n")
            self.ag_display.config(state=tk.DISABLED)
            self.status_bar.config(text="Taxonomic catalog: seed_pack not found")
            return

        def _do_search():
            try:
                from modules.ag_importer import stream_tsv_file
            except ImportError:
                def _err():
                    self.ag_display.config(state=tk.NORMAL)
                    self.ag_display.delete(1.0, tk.END)
                    self.ag_display.insert(tk.END, "[ag_importer module not available]\n")
                    self.ag_display.config(state=tk.DISABLED)
                self.after(0, _err)
                return

            matches = []
            q_lower = query.lower()
            for row in stream_tsv_file(_vn_path):
                name = row.get('col:name', '').lower()
                country = row.get('col:country', '').lower()
                lang = row.get('col:language', '').lower()
                if q_lower in name or q_lower in country:
                    matches.append(row)
                    if len(matches) >= 200:  # cap results
                        break

            def _update():
                self.ag_display.config(state=tk.NORMAL)
                self.ag_display.delete(1.0, tk.END)
                if not matches:
                    self.ag_display.insert(tk.END, f"No vernacular names matching '{query}'.\n")
                else:
                    cap_note = " (capped at 200)" if len(matches) >= 200 else ""
                    self.ag_display.insert(tk.END,
                        f"Catalogue of Life: {len(matches)} matches{cap_note}\n\n", "section_header")
                    self.ag_display.insert(tk.END,
                        f"{'TaxonID':<10} {'Common Name':<35} {'Language':<12} {'Country':<15}\n", "section_header")
                    self.ag_display.insert(tk.END, "-" * 75 + "\n")
                    for row in matches:
                        tid = row.get('col:taxonID', '?')[:9]
                        name = row.get('col:name', '?')[:34]
                        lang = row.get('col:language', '')[:11]
                        country = row.get('col:country', '')[:14]
                        self.ag_display.insert(tk.END, f"{tid:<10} {name:<35} {lang:<12} {country:<15}\n")
                self.ag_display.config(state=tk.DISABLED)
                for w in self.ag_suggestions_frame.winfo_children():
                    w.destroy()
                tk.Label(self.ag_suggestions_frame, text=f"Taxonomy: {len(matches)} vernacular names", fg="#2980b9").pack(anchor="w")
                self.status_bar.config(text=f"Taxonomy search complete: {len(matches)} results")

            self.after(0, _update)

        threading.Thread(target=_do_search, daemon=True).start()

    def _query_brain(self, query):  #[Mark:UNIVERSAL_CATALOG_BRAIN_ROUTE]
        """Query brain.py financial planner data."""
        self.ag_display.config(state=tk.NORMAL)
        self.ag_display.delete(1.0, tk.END)

        try:
            from modules.brain import ConfigManager, SessionManager
            _brain_base = Path(__file__).parents[3] / "modules"
            # Try to load brain config and sessions
            config = ConfigManager()
            sessions = SessionManager(config)

            self.ag_display.insert(tk.END, f"Brain / Financial — query: '{query}'\n\n", "section_header")

            # Show available workflows
            self.ag_display.insert(tk.END, "Available Workflows:\n", "section_header")
            for wf in ["Financial Analysis", "Portfolio Management", "Loan Analysis", "Business Planning", "Custom Workflow"]:
                self.ag_display.insert(tk.END, f"  - {wf}\n")

            # Show session data if available
            self.ag_display.insert(tk.END, f"\nSession Data:\n", "section_header")
            try:
                session_list = sessions.list_sessions()
                if session_list:
                    for sid in session_list[:10]:
                        self.ag_display.insert(tk.END, f"  Session: {sid}\n", "temporal")
                else:
                    self.ag_display.insert(tk.END, "  No sessions found.\n")
            except Exception:
                self.ag_display.insert(tk.END, "  Session listing not available.\n")

            # Show config
            self.ag_display.insert(tk.END, f"\nConfig:\n", "section_header")
            try:
                if hasattr(config, 'config') and config.config:
                    for section, values in config.config.items():
                        self.ag_display.insert(tk.END, f"  [{section}]\n", "ast_profile")
                        if isinstance(values, dict):
                            for k, v in values.items():
                                if query.lower() in str(k).lower() or query.lower() in str(v).lower():
                                    self.ag_display.insert(tk.END, f"    {k}: {v}\n", "task_assoc")
                                else:
                                    self.ag_display.insert(tk.END, f"    {k}: {v}\n")
                else:
                    self.ag_display.insert(tk.END, "  No config loaded.\n")
            except Exception as e:
                self.ag_display.insert(tk.END, f"  Config error: {e}\n")

        except ImportError:
            self.ag_display.insert(tk.END, "[Brain module not available]\n")
            self.ag_display.insert(tk.END, "The modules.brain module could not be imported.\n")
        except Exception as e:
            self.ag_display.insert(tk.END, f"[Brain query error: {e}]\n")

        self.ag_display.config(state=tk.DISABLED)
        for w in self.ag_suggestions_frame.winfo_children():
            w.destroy()
        tk.Label(self.ag_suggestions_frame, text="Brain / Financial query complete", fg="#8e44ad").pack(anchor="w")
        self.status_bar.config(text=f"Brain search complete: {query}")

    def setup_latest_report_ui(self):
        """Setup the Latest Report tab — shows latest_sync.json + Os_Toolkit latest output."""
        ctrl_frame = tk.Frame(self.latest_frame)
        ctrl_frame.pack(fill=tk.X, padx=5, pady=3)

        tk.Button(ctrl_frame, text="🔄 Refresh", command=self.refresh_latest_report).pack(side=tk.LEFT, padx=3)
        tk.Button(ctrl_frame, text="🔄 Sync Todos", command=self.sync_todos).pack(side=tk.LEFT, padx=3)
        self.latest_source_label = tk.Label(ctrl_frame, text="", fg="#666666", anchor='w')
        self.latest_source_label.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)

        self.latest_display = scrolledtext.ScrolledText(
            self.latest_frame, wrap=tk.WORD, font=('Consolas', 9), bg='#1e1e2e', fg='#cdd6f4'
        )
        self.latest_display.pack(fill=tk.BOTH, expand=True, padx=5, pady=3)

        # Auto-load on tab switch
        self.right_notebook.bind("<<NotebookTabChanged>>", self._on_right_tab_changed)
        self.refresh_latest_report()

    def refresh_latest_report(self):
        """Pool latest state from local sources + Os_Toolkit latest in background.

        Fast path (immediate):
          1. plans/Refs/latest_sync.json  (todo sync results)
          2. backup/version_manifest.json  (enriched_changes last 20)
          3. logger_util.UX_EVENT_LOG      (in-process events, last 20)
          4. DeBug/debug_log_*.txt         (latest log file tail, 40 lines)
        Slow path (background thread, 30s timeout):
          5. Os_Toolkit.py latest          ([SECTION] structured output)
        Result saved to plans/Refs/latest_state.json.
        """
        self.latest_display.config(state=tk.NORMAL)
        self.latest_display.delete(1.0, tk.END)

        output = []
        source_parts = []
        _data_root = Path(__file__).parents[5]

        # --- 1. latest_sync.json ---
        latest_sync_path = Path(self.base_path) / "Refs" / "latest_sync.json"
        sync_data = {}
        if latest_sync_path.exists():
            try:
                with open(latest_sync_path, encoding='utf-8') as f:
                    sync_data = json.load(f)
                ts = sync_data.get("timestamp", "unknown")
                count = sync_data.get("task_count", 0)
                err = sync_data.get("error")
                srcs = sync_data.get("sources", [])
                output.append(f"=== Todo Sync — {ts} ===")
                if srcs:
                    output.append(f"  Sources: {', '.join(srcs)}")
                if err:
                    output.append(f"  ERROR: {err}")
                else:
                    output.append(f"  {count} tasks")
                    output.append("")
                    for tid, t in list(sync_data.get("tasks", {}).items())[:40]:
                        pri = f"[{t.get('priority','')}]" if t.get("priority") else ""
                        st = f"{t.get('status','?'):14}"
                        wh = f"  ∈ {t['wherein']}" if t.get("wherein") else ""
                        src = f"  ({t.get('source','')})" if t.get("source") else ""
                        output.append(f"  {st}{pri} {tid}: {t.get('title','')}{wh}{src}")
                source_parts.append(f"sync:{ts[11:16]}")
            except Exception as e:
                output.append(f"[latest_sync.json parse error: {e}]")
        else:
            output.append("[No latest_sync.json — press 🔄 Sync Todos first]")

        output.append("")

        # --- 2. version_manifest.json enriched_changes ---
        vm_path = _data_root / "backup" / "version_manifest.json"
        ec_count = 0
        if vm_path.exists():
            try:
                with open(vm_path, encoding='utf-8') as f:
                    vm = json.load(f)
                ec = vm.get("enriched_changes", {})
                ec_count = len(ec)
                recent = list(ec.items())[-20:]
                output.append(f"=== Recent Changes ({ec_count} total, showing last {len(recent)}) ===")
                for eid, e in recent:
                    fn = Path(e.get("file", "?")).name
                    verb = e.get("verb", "?")
                    risk = e.get("risk_level", "")
                    wherein = e.get("wherein", "")
                    classes = e.get("classes", [])
                    wh_str = f"  ∈ {wherein}" if wherein else (f"  ∈ {classes[0]}" if classes else "")
                    risk_str = f" [{risk}]" if risk else ""
                    adds = e.get("additions", 0)
                    dels = e.get("deletions", 0)
                    output.append(f"  {eid}  {verb:8} {fn}{risk_str}  +{adds}/-{dels}{wh_str}")
                source_parts.append("vm:ok")
            except Exception as e:
                output.append(f"[version_manifest error: {e}]")
                source_parts.append("vm:err")
        else:
            output.append("[backup/version_manifest.json not found]")

        output.append("")

        # --- 2b. aoe_inbox alerts from checklist.json ---
        _cl_path = Path(self.base_path) / "checklist.json"
        if _cl_path.exists():
            try:
                _cl = json.loads(_cl_path.read_text(encoding='utf-8'))
                _inbox = _cl.get("aoe_inbox", [])
                if _inbox:
                    output.append(f"=== AoE Inbox Alerts ({len(_inbox)}) ===")
                    for _alert in _inbox[-10:]:
                        _eid = _alert.get("event_id", "")
                        _tid = _alert.get("task_id", "")
                        _risk = _alert.get("risk_level", "")
                        _msg = _alert.get("message", _alert.get("file", ""))
                        _risk_icon = "🔴" if _risk == "CRITICAL" else "🟡" if _risk == "HIGH" else "🔵"
                        output.append(f"  {_risk_icon} {_eid} → {_tid}  {_msg}")
                    source_parts.append(f"alerts:{len(_inbox)}")
            except Exception:
                pass

        output.append("")

        # --- 3. UX_EVENT_LOG (in-process) ---
        if _TRAINER_LOG_AVAILABLE and hasattr(_trainer_log, 'UX_EVENT_LOG'):
            log = _trainer_log.UX_EVENT_LOG[-20:]
            total = len(_trainer_log.UX_EVENT_LOG)
            output.append(f"=== UX Events ({total} total, last {len(log)}) ===")
            for e in log:
                wh = f"  ∈ {e['wherein']}" if e.get("wherein") else ""
                output.append(f"  {e['timestamp']} [{e['event_type']:20}] {e['tab']}.{e['widget']} → {e['outcome']}{wh}")
            source_parts.append(f"ux:{total}")
        else:
            output.append("[UX_EVENT_LOG — logger not loaded in this process]")

        output.append("")

        # --- 4. Latest DeBug log tail ---
        debug_dir = _data_root / "DeBug"
        latest_log_name = None
        if debug_dir.exists():
            txt_logs = sorted(debug_dir.glob("debug_log_*.txt"),
                              key=lambda p: p.stat().st_mtime, reverse=True)
            if txt_logs:
                latest_log = txt_logs[0]
                latest_log_name = latest_log.name
                try:
                    with open(latest_log, encoding='utf-8', errors='replace') as f:
                        lines = f.readlines()
                    tail = lines[-40:]
                    output.append(f"=== Debug Log: {latest_log.name} (last {len(tail)} of {len(lines)} lines) ===")
                    output.extend([l.rstrip() for l in tail])
                    source_parts.append(f"log:{latest_log.name[10:18]}")
                except Exception as e:
                    output.append(f"[DeBug log error: {e}]")

        self.latest_display.insert(tk.END, "\n".join(output))
        self.latest_display.config(state=tk.DISABLED)
        self.latest_source_label.config(text=" | ".join(source_parts))

        # Save latest_state.json to Refs/ (replaces stale issue)
        def _save():
            try:
                refs_dir = Path(self.base_path) / "Refs"
                refs_dir.mkdir(exist_ok=True)
                state = {
                    "timestamp": datetime.datetime.now().isoformat(),
                    "sources": source_parts,
                    "todo_task_count": sync_data.get("task_count", 0),
                    "enriched_change_count": ec_count,
                    "ux_event_count": len(_trainer_log.UX_EVENT_LOG) if _TRAINER_LOG_AVAILABLE and hasattr(_trainer_log, 'UX_EVENT_LOG') else 0,
                    "debug_log": latest_log_name,
                }
                with open(refs_dir / "latest_state.json", 'w', encoding='utf-8') as f:
                    json.dump(state, f, indent=2)
            except Exception:
                pass
        threading.Thread(target=_save, daemon=True).start()

        if _TRAINER_LOG_AVAILABLE:
            _trainer_log.log_ux_event(
                "ag_knowledge", "LATEST_REPORT", "refresh_button",
                outcome="success",
                detail=f"tasks={sync_data.get('task_count',0)} changes={ec_count} sources={source_parts}",
                wherein="PlannerSuite::refresh_latest_report"
            )

        # --- 5. Os_Toolkit latest in background (30s) — appended when ready ---
        global _LATEST_RUNNING
        if _OS_TOOLKIT_PATH.exists() and not _LATEST_RUNNING:
            _LATEST_RUNNING = True
            self.latest_display.config(state=tk.NORMAL)
            self.latest_display.insert(tk.END, "\n\n=== Os_Toolkit latest — loading... ===\n")
            self.latest_display.config(state=tk.DISABLED)

            def _load_ostoolkit():
                global _LATEST_RUNNING
                try:
                    # cwd=map_tab/ so Os_Toolkit finds forekit_data/sessions/
                    _map_tab = Path(__file__).parents[5] / "tabs" / "map_tab"
                    proc = subprocess.run(
                        [sys.executable, str(_OS_TOOLKIT_PATH), "latest"],
                        capture_output=True, text=True, timeout=180,
                        cwd=str(_map_tab)
                    )
                    if proc.returncode != 0:
                        out = f"[Os_Toolkit exited {proc.returncode}]\n{proc.stderr or proc.stdout or ''}"
                    else:
                        out = (proc.stdout or proc.stderr or "[no output]").strip()
                    # Save manifest output to Refs/
                    refs_dir = Path(self.base_path) / "Refs"
                    refs_dir.mkdir(exist_ok=True)
                    try:
                        with open(refs_dir / "ostoolkit_latest.txt", 'w', encoding='utf-8') as f:
                            f.write(out)
                    except Exception:
                        pass
                    # Parse sections from Os_Toolkit output
                    _raw_lines = out.splitlines()
                    _sections = {}
                    _cur_sec = "PREAMBLE"
                    for _rl in _raw_lines:
                        _stripped = _rl.strip()
                        if _stripped.startswith("[") and _stripped.endswith("]") and len(_stripped) < 60:
                            _cur_sec = _stripped[1:-1]
                            _sections[_cur_sec] = []
                        else:
                            _sections.setdefault(_cur_sec, []).append(_rl)
                    # Build labeled output with key sections, capped per section
                    lines = []
                    _show_sections = ["TODO SYNC", "CHANGE DELTA", "MANIFEST SYNC",
                                      "CONFORMITY CHECK", "SECURITY & HEALTH", "RECENT FILE CHANGES & WORKFLOW VALIDATION"]
                    for _sec in _show_sections:
                        if _sec in _sections:
                            lines.append(f"\n--- Os_Toolkit: {_sec} ---")
                            lines.extend(_sections[_sec][:15])
                    # Include any remaining sections not in the show list (truncated)
                    for _sec, _sl in _sections.items():
                        if _sec not in _show_sections and _sec != "PREAMBLE" and _sl:
                            lines.append(f"\n--- Os_Toolkit: {_sec} ---")
                            lines.extend(_sl[:8])
                    if not lines:
                        lines = _raw_lines[:150]  # Fallback: raw dump
                    ok_label = "ostoolkit:ok"
                    # Read suggested_actions.json from Os_Toolkit babel_data
                    _ap_tab = Path(__file__).parents[5] / "tabs" / "action_panel_tab"
                    actions_path = _ap_tab / "babel_data" / "profile" / "suggested_actions.json"
                    if actions_path.exists():
                        try:
                            with open(actions_path, encoding='utf-8') as f:
                                actions = json.load(f)
                            lines.append("")
                            lines.append("=== Suggested Actions ===")
                            for a in (actions if isinstance(actions, list) else
                                      actions.get("actions", []))[:10]:
                                conf = a.get("confidence", 0)
                                desc = a.get("description", a.get("action", str(a)))[:80]
                                lines.append(f"  [{conf:.2f}] {desc}")
                        except Exception:
                            pass
                except subprocess.TimeoutExpired:
                    lines = ["[Os_Toolkit latest timed out after 180s]"]
                    ok_label = "ostoolkit:timeout"
                    if _TRAINER_LOG_AVAILABLE:
                        _trainer_log.log_message("PLANNER: {warn} Os_Toolkit latest timed out (180s)")
                except Exception as e:
                    lines = [f"[Os_Toolkit error: {e}]"]
                    ok_label = "ostoolkit:err"
                    if _TRAINER_LOG_AVAILABLE:
                        _trainer_log.log_message(f"PLANNER: {{warn}} Os_Toolkit latest error: {e}")

                def _append():
                    global _LATEST_RUNNING
                    _LATEST_RUNNING = False
                    self.latest_display.config(state=tk.NORMAL)
                    content = self.latest_display.get(1.0, tk.END)
                    marker = "=== Os_Toolkit latest — loading... ==="
                    if marker in content:
                        idx = content.index(marker)
                        line_num = content[:idx].count('\n') + 1
                        self.latest_display.delete(f"{line_num}.0", tk.END)
                        self.latest_display.insert(tk.END, "=== Os_Toolkit latest ===\n")
                        self.latest_display.insert(tk.END, "\n".join(lines))
                    self.latest_display.config(state=tk.DISABLED)
                    self.latest_source_label.config(
                        text=" | ".join(source_parts + [ok_label])
                    )
                self.after(0, _append)

            threading.Thread(target=_load_ostoolkit, daemon=True).start()
        elif _LATEST_RUNNING:
            # Already running — skip duplicate spawn
            if _TRAINER_LOG_AVAILABLE:
                _trainer_log.log_message("PLANNER: Os_Toolkit latest already running, skipping duplicate")

    def _on_right_tab_changed(self, event):
        """Auto-refresh Task Board on tab switch. Latest only refreshes on button press."""
        try:
            selected = self.right_notebook.tab(self.right_notebook.select(), "text")
            if "Tasks" in selected:
                self.refresh_task_board()
            # Latest tab: don't auto-trigger Os_Toolkit — user presses Refresh when ready
        except Exception:
            pass

    def refresh_ag_links(self):
        """Manually refresh Ag Knowledge links based on current document content"""
        content = self.doc_display.get(1.0, tk.END)
        self.update_ag_knowledge_links(content)

    def update_ag_knowledge_links(self, text):
        """Scan text and update the Ag Knowledge display with hierarchical associations"""
        if not self.ag_linker:
            return

        found = self.ag_linker.scan_text(text)
        
        self.ag_display.config(state=tk.NORMAL)
        self.ag_display.delete(1.0, tk.END)
        
        if not found["entities"] and not found["diseases"] and not found["terms"]:
            self.ag_display.insert(tk.END, "No specific Ag Knowledge links found in current selection.\n\n")
            self.ag_display.insert(tk.END, "Tip: Use entity names like 'Bella' or 'Daisy' in your tasks.")
        else:
            if found["entities"]:
                self.ag_display.insert(tk.END, "--- Linked Entities ---\n", "heading")
                for entity in found["entities"]:
                    hierarchy = self.ag_linker.get_hierarchy(entity)
                    assoc = self.ag_linker.get_full_associations(entity)
                    
                    self.ag_display.insert(tk.END, f"• {entity['name']}\n", "link")
                    self.ag_display.insert(tk.END, f"  Hierarchy: {hierarchy}\n")
                    self.ag_display.insert(tk.END, f"  Health: {entity.get('health_status', 'Unknown')}\n")
                    
                    if assoc["parent"]:
                        self.ag_display.insert(tk.END, f"  Parent: {assoc['parent'].get('name', 'Unknown')}\n")
                    
                    if assoc["offspring"]:
                        off_names = ", ".join([o.get('name', 'Unknown') for o in assoc["offspring"]])
                        self.ag_display.insert(tk.END, f"  Offspring: {off_names}\n")
                    
                    if assoc["diseases"]:
                        dis_names = ", ".join([d.get('name', 'Unknown') for d in assoc["diseases"]])
                        self.ag_display.insert(tk.END, f"  History: {dis_names}\n", "error_link")

                    self.ag_display.insert(tk.END, f"  Desc: {entity.get('description', '')[:100]}...\n\n")
            
            if found["diseases"]:
                self.ag_display.insert(tk.END, "\n--- Linked Diseases ---\n", "heading")
                for disease in found["diseases"]:
                    self.ag_display.insert(tk.END, f"• {disease['name']}\n", "error_link")
                    self.ag_display.insert(tk.END, f"  Scientific: {disease.get('scientific_name', '')}\n")
                    self.ag_display.insert(tk.END, f"  Severity: {disease.get('severity', '')}\n\n")

            if found["terms"]:
                self.ag_display.insert(tk.END, "\n--- Related Terms ---\n", "heading")
                for term in found["terms"]:
                    self.ag_display.insert(tk.END, f"• {term}\n")

        # Configure tags
        self.ag_display.tag_config("heading", font=('Arial', 10, 'bold'))
        self.ag_display.tag_config("link", foreground="blue", underline=True)
        self.ag_display.tag_config("error_link", foreground="red", underline=True)
        
        self.ag_display.config(state=tk.DISABLED)

    def generate_report(self):
        """Generate a comprehensive report.
        Appends Os_Toolkit 'latest' system state if action_panel_tab is present.
        Logs result via logger_util so live log and runtime_bugs.json are updated.
        """
        report_file = os.path.join(self.base_path, "Refs", f"report_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.txt")

        report = "Planner Suite Report\n"
        report += "=" * 50 + "\n"
        report += f"Generated: {datetime.datetime.now()}\n\n"
        report += f"Base Path: {self.base_path}\n"
        report += f"Marked Files: {len(self.marked_files)}\n"
        report += f"Diff History Entries: {len(self.diff_history)}\n\n"

        # Directory contents summary
        report += "Directory Structure:\n"
        try:
            _dir_names = sorted([
                d for d in os.listdir(self.base_path)
                if os.path.isdir(os.path.join(self.base_path, d)) and not d.startswith(".")
            ])
        except Exception:
            _dir_names = ["Epics", "Plans", "Phases", "Tasks", "Milestones", "Diffs", "Refs"]
        for dir_name in _dir_names:
            dir_path = os.path.join(self.base_path, dir_name)
            try:
                count = len([f for f in os.listdir(dir_path) if os.path.isfile(os.path.join(dir_path, f))])
                report += f"  {dir_name}: {count} files\n"
            except Exception:
                report += f"  {dir_name}: Error accessing\n"

        # --- Os_Toolkit 'latest' system state (no zenity) ---
        os_toolkit_output = ""
        if _OS_TOOLKIT_PATH.exists():
            try:
                result = subprocess.run(
                    [sys.executable, str(_OS_TOOLKIT_PATH), "latest"],
                    capture_output=True, text=True, timeout=20
                )
                if result.returncode != 0:
                    os_toolkit_output = f"[Os_Toolkit exited {result.returncode}]\n{result.stderr or result.stdout or ''}"
                else:
                    os_toolkit_output = result.stdout or result.stderr or ""
                if os_toolkit_output:
                    report += "\n" + "=" * 50 + "\n"
                    report += "System State (Os_Toolkit latest):\n"
                    report += "=" * 50 + "\n"
                    report += os_toolkit_output
            except Exception as e:
                os_toolkit_output = f"[Os_Toolkit error: {e}]"
                report += f"\n{os_toolkit_output}\n"

        with open(report_file, 'w') as f:
            f.write(report)

        line_count = len(report.splitlines())
        self.status_bar.config(text=f"Report: {os.path.basename(report_file)} ({line_count} lines)")
        self.load_directory_structure()

        if _TRAINER_LOG_AVAILABLE:
            _trainer_log.log_ux_event(
                "ag_knowledge", "GENERATE_REPORT", "generate_report_button",
                outcome="success",
                detail=f"Report saved: {report_file} — {line_count} lines — Os_Toolkit: {'yes' if os_toolkit_output else 'not found'}",
                wherein="PlannerSuite::generate_report"
            )

    def sync_todos(self):
        """Merge Claude tasks + plans/todos.json + plans/checklist.json into latest_sync.json.
        Triggers 'Os_Toolkit.py actions --run sync_all_todos' for bidirectional reconciliation.
        """
        global _SYNC_RUNNING
        if _SYNC_RUNNING:
            self.status_bar.config(text="Sync already in progress...")
            return
        _SYNC_RUNNING = True
        self.status_bar.config(text="Syncing todos & reconciling system state...")
        self.update_idletasks()

        def _do_sync():
            global _SYNC_RUNNING
            # 1. Trigger Os_Toolkit bidirectional sync (P1-TodoSync)
            try:
                _os_cwd = str(Path(_OS_TOOLKIT_PATH).parent)
                result = subprocess.run(
                    [sys.executable, str(_OS_TOOLKIT_PATH), "actions", "--run", "sync_all_todos"],
                    capture_output=True, text=True, timeout=60, cwd=_os_cwd
                )
                if result.returncode != 0:
                    _sync_os_out = f"[sync_all_todos exited {result.returncode}] {result.stderr or result.stdout or ''}"
                else:
                    _sync_os_out = (result.stdout or "") + (result.stderr or "")
            except Exception as _e:
                _sync_os_out = str(_e)

            tasks = {}
            sources = []
            error = None

            # --- 1. plans/checklist.json → P0/P1 immediate_ready items ---
            checklist_path = Path(self.base_path) / "checklist.json"
            if checklist_path.exists():
                try:
                    with open(checklist_path, encoding='utf-8') as f:
                        cl = json.load(f)
                    count = 0
                    for section_key, section in cl.items():
                        if isinstance(section, dict):
                            for item in section.get("items", []):
                                if isinstance(item, dict) and "id" in item:
                                    tasks[item["id"]] = {
                                        "title": item.get("title", ""),
                                        "status": item.get("status", ""),
                                        "priority": item.get("priority", ""),
                                        "wherein": item.get("file", ""),
                                        "source": "checklist.json",
                                        "created_at": item.get("created_at", ""),
                                        "who": "user",
                                        "task_type": section_key,
                                        "effort": item.get("effort", ""),
                                        "description": item.get("what", item.get("description", "")),
                                    }
                                    count += 1
                    sources.append(f"checklist({count})")
                except Exception as e:
                    sources.append(f"checklist(err:{e})")

            # --- 1b. aoe_inbox → ATTRIBUTION_GAP + probe FAIL alerts as tasks ---
            if checklist_path.exists():
                try:
                    with open(checklist_path, encoding='utf-8') as f:
                        cl_inbox = json.load(f)
                    _inbox_items = cl_inbox.get("aoe_inbox", [])
                    _inbox_count = 0
                    for _item in _inbox_items:
                        if not isinstance(_item, dict):
                            continue
                        _eid = _item.get("event_id", "")
                        _status = _item.get("status", "")
                        _tid = _item.get("task_id", "")
                        # Create tasks from ATTRIBUTION_GAP entries (probe failures)
                        if _status == "ATTRIBUTION_GAP" and _eid:
                            _inbox_tid = f"probe_{_eid}"
                            if _inbox_tid not in tasks:
                                tasks[_inbox_tid] = {
                                    "title": _item.get("message", f"Probe FAIL: {_eid}"),
                                    "status": "OPEN",
                                    "priority": "P0",
                                    "wherein": _item.get("file", ""),
                                    "source": "aoe_inbox",
                                    "created_at": _item.get("timestamp", ""),
                                    "who": "auto_test",
                                    "task_type": "probe_failure",
                                    "description": f"Auto-detected probe failure for {_eid}. "
                                                   f"Risk: {_item.get('risk_level', 'UNKNOWN')}. "
                                                   f"Verb: {_item.get('verb', '')}",
                                }
                                _inbox_count += 1
                        # Also pull regular aoe_inbox alerts linked to tasks
                        elif _tid and _eid and _tid not in tasks:
                            tasks[f"aoe_{_eid}_{_tid}"] = {
                                "title": _item.get("message", f"Change alert: {_eid}"),
                                "status": "OPEN",
                                "priority": _item.get("risk_level", "P2") if _item.get("risk_level") in ("P0", "P1", "P2") else "P1",
                                "wherein": _item.get("file", ""),
                                "source": "aoe_inbox",
                                "created_at": _item.get("timestamp", ""),
                                "who": "live_watcher",
                                "task_type": "change_alert",
                            }
                            _inbox_count += 1
                    if _inbox_count:
                        sources.append(f"aoe_inbox({_inbox_count})")
                except Exception:
                    pass

            # --- 2. plans/todos.json → progress_notes phases ---
            todos_path = Path(self.base_path) / "todos.json"
            if todos_path.exists():
                try:
                    with open(todos_path, encoding='utf-8') as f:
                        todos = json.load(f)
                    count = 0
                    for phase_key, phase_val in todos.items():
                        if isinstance(phase_val, dict):
                            for task_id, task_val in phase_val.items():
                                if isinstance(task_val, dict) and "title" in task_val:
                                    if task_id not in tasks:
                                        # Infer who: sync-created = system, user-created phases = user
                                        _who = "system" if task_val.get("_source") == "sync" or phase_key == "phase_sync_2602" else "user"
                                        tasks[task_id] = {
                                            "title": task_val.get("title", ""),
                                            "status": task_val.get("status", ""),
                                            "priority": task_val.get("priority", ""),
                                            "wherein": task_val.get("wherein", ""),
                                            "source": "todos.json",
                                            "created_at": task_val.get("created_at", ""),
                                            "who": _who,
                                            "task_type": phase_key,
                                            "description": task_val.get("description", ""),
                                        }
                                    count += 1
                    sources.append(f"todos({count})")
                except Exception as e:
                    sources.append(f"todos(err:{e})")

            # --- 3. ~/.claude/tasks/ latest session ---
            claude_dir = Path.home() / ".claude" / "tasks"
            if claude_dir.exists():
                try:
                    sessions = sorted(
                        [p for p in claude_dir.iterdir() if p.is_dir()],
                        key=lambda p: p.stat().st_mtime, reverse=True
                    )
                    if sessions:
                        sess = sessions[0]
                        count = 0
                        for tf in sess.glob("*.json"):
                            try:
                                with open(tf, encoding='utf-8') as f:
                                    t = json.load(f)
                                tid = t.get("id") or tf.stem
                                if tid not in tasks:
                                    tasks[tid] = {
                                        "title": t.get("subject", t.get("title", "")),
                                        "status": t.get("status", ""),
                                        "wherein": t.get("wherein", ""),
                                        "source": f"claude:{sess.name}",
                                        "created_at": t.get("created_at", ""),
                                        "who": "claude",
                                        "task_type": t.get("metadata", {}).get("type", "") if isinstance(t.get("metadata"), dict) else "",
                                        "description": t.get("description", ""),
                                    }
                                count += 1
                            except Exception:
                                pass
                        sources.append(f"claude:{sess.name}({count})")
                except Exception as e:
                    sources.append(f"claude(err:{e})")

            result = {
                "timestamp": datetime.datetime.now().isoformat(),
                "task_count": len(tasks),
                "sources": sources,
                "tasks": tasks,
                "error": error
            }

            # ── Project Resolution: match tasks to Plans/ and Epics/ by wherein ──
            try:
                import re as _re_proj
                _plans_root = Path(self.base_path)
                _project_dirs = {}   # {filename: project_id}
                _plan_docs = {}      # {filename: plan_doc_path}

                # Scan Plans/Project_*/ for .py file references
                _plans_dir = _plans_root / "Plans"
                if _plans_dir.exists():
                    for _pdir in _plans_dir.iterdir():
                        if _pdir.is_dir():
                            _pid = _pdir.name
                            for _md in _pdir.rglob("*.md"):
                                try:
                                    _content = _md.read_text(encoding="utf-8", errors="ignore")[:2000]
                                    _refs = set(_re_proj.findall(r'[\w]+\.py', _content))
                                    for _ref in _refs:
                                        _project_dirs[_ref] = _pid
                                        _plan_docs[_ref] = str(_md.relative_to(_plans_root))
                                except Exception:
                                    pass

                # Also scan Epics/
                _epics_dir = _plans_root / "Epics"
                if _epics_dir.exists():
                    for _epic in _epics_dir.rglob("*.md"):
                        try:
                            _content = _epic.read_text(encoding="utf-8", errors="ignore")[:2000]
                            _refs = set(_re_proj.findall(r'[\w]+\.py', _content))
                            _pid = _epic.stem
                            for _ref in _refs:
                                if _ref not in _project_dirs:
                                    _project_dirs[_ref] = _pid
                                    _plan_docs[_ref] = str(_epic.relative_to(_plans_root))
                        except Exception:
                            pass

                # Apply to tasks
                _resolved_count = 0
                for tid, t in tasks.items():
                    _wh = (t.get("wherein") or "").split("/")[-1]
                    if _wh and _wh in _project_dirs:
                        t["project_id"] = _project_dirs[_wh]
                        t["plan_doc"] = _plan_docs.get(_wh, "")
                        _resolved_count += 1
                if _resolved_count:
                    sources.append(f"project_resolve({_resolved_count})")
            except Exception:
                pass

            refs_dir = Path(self.base_path) / "Refs"
            refs_dir.mkdir(exist_ok=True)
            tasks_dir = refs_dir / "tasks"
            tasks_dir.mkdir(exist_ok=True)

            try:
                with open(refs_dir / "latest_sync.json", 'w', encoding='utf-8') as f:
                    json.dump(result, f, indent=2)
            except Exception as e:
                result["error"] = f"save: {e}"

            # Save per-source breakdowns to Refs/tasks/
            try:
                cl_tasks = {k: v for k, v in tasks.items() if v.get("source") == "checklist.json"}
                td_tasks = {k: v for k, v in tasks.items() if v.get("source") == "todos.json"}
                cc_tasks = {k: v for k, v in tasks.items()
                            if v.get("source", "").startswith("claude:")}
                for name, subset in [("checklist_todos", cl_tasks),
                                     ("todos_json", td_tasks),
                                     ("claude_tasks", cc_tasks)]:
                    with open(tasks_dir / f"{name}.json", 'w', encoding='utf-8') as f:
                        json.dump({"timestamp": result["timestamp"],
                                   "count": len(subset), "tasks": subset}, f, indent=2)
            except Exception:
                pass

            # ── Task-ID back-link: write task_ids into enriched_changes ──
            # For each enriched_change whose file basename matches a task's wherein,
            # append the task_id to enriched_change['task_ids'] and persist the manifest.
            try:
                import recovery_util as _ru
                _manifest = _ru.load_version_manifest()
                _ec = _manifest.get("enriched_changes", {})
                _changed = False
                for _tid, _t in tasks.items():
                    _wh_base = os.path.basename(_t.get("wherein", "") or "")
                    if not _wh_base:
                        continue
                    for _eid, _ch in _ec.items():
                        if os.path.basename(_ch.get("file", "") or "") == _wh_base:
                            _ch.setdefault("task_ids", [])
                            if _tid not in _ch["task_ids"]:
                                _ch["task_ids"].append(_tid)
                                _changed = True
                if _changed:
                    _manifest["enriched_changes"] = _ec
                    _ru.save_version_manifest(_manifest)
            except Exception:
                pass

            # ── D1: Persist AoE context per task ──────────────────────────────
            try:
                tasks_dir = Path(self.base_path) / "Tasks"
                tasks_dir.mkdir(exist_ok=True)
                enriched_changes_fresh = {}
                try:
                    import recovery_util as _ru_ctx
                    _vm_ctx = _ru_ctx.load_version_manifest()
                    enriched_changes_fresh = _vm_ctx.get("enriched_changes", {})
                except Exception:
                    pass

                # G1 pre-load: GapAnalyzer + OsToolkitGroundingBridge (loaded once, reused per task)
                _ga_cached = None
                _grounded_cached = None
                try:
                    import sys as _sys_d1
                    _ga_dir_d1 = str(Path(__file__).parents[5] / "tabs" / "action_panel_tab" / "regex_project")
                    if _ga_dir_d1 not in _sys_d1.path:
                        _sys_d1.path.insert(0, _ga_dir_d1)
                    from gap_analyzer import GapAnalyzer as _GapAnalyzerD1
                    _ga_cached = _GapAnalyzerD1()
                except Exception:
                    pass
                try:
                    import sys as _sys_d1b
                    _mo_dir_d1 = str(Path(__file__).parents[5] / "tabs" / "action_panel_tab"
                                     / "regex_project" / "activities" / "tools" / "scripts")
                    if _mo_dir_d1 not in _sys_d1b.path:
                        _sys_d1b.path.insert(0, _mo_dir_d1)
                    from activity_integration_bridge import OsToolkitGroundingBridge as _OGB_D1
                    _babel_root_d1 = Path(__file__).parents[5] / "tabs" / "action_panel_tab" / "babel_data"
                    _grounded_cached = _OGB_D1(_babel_root_d1).load()
                except Exception:
                    pass
                # H2: UnifiedContextIndex pre-load (once per sync, cached)
                _unified_index = None
                try:
                    import sys as _sys_uci
                    _uci_dir = str(Path(__file__).parents[5] / "tabs" / "action_panel_tab"
                                   / "regex_project" / "activities" / "tools" / "scripts")
                    if _uci_dir not in _sys_uci.path:
                        _sys_uci.path.insert(0, _uci_dir)
                    from unified_context_index import get_index as _get_uci
                    _unified_index = _get_uci(Path(__file__).parents[5])
                except Exception:
                    pass

                # N0: pre-compute TNE narrative once per sync cycle (cached)
                _nar_cache = None
                try:
                    import sys as _sys_tne
                    _tne_dir = str(Path(__file__).parents[5] / "tabs" / "action_panel_tab"
                                   / "regex_project" / "activities" / "tools" / "scripts")
                    if _tne_dir not in _sys_tne.path:
                        _sys_tne.path.insert(0, _tne_dir)
                    from temporal_narrative_engine import TemporalNarrativeEngine as _TNE
                    _trainer_root = Path(__file__).parents[5]
                    _nar_cache = _TNE(_trainer_root).explain('last 24h')
                except Exception:
                    pass

                for tid, t in tasks.items():
                    try:
                        ctx = self._get_task_aoe_context(t, enriched_changes_fresh, {}, task_id=tid)
                        # Serialize changes list (contains (eid, ch) tuples)
                        ctx_serial = dict(ctx)
                        ctx_serial["changes"] = [
                            {"eid": eid, **{k: v for k, v in ch.items()}}
                            for eid, ch in ctx.get("changes", [])
                        ]
                        # Parse expected diffs from project epic file
                        _exp_diffs = self._parse_expected_diffs(
                            t.get("project_id", ""), t.get("wherein", ""),
                            Path(self.base_path)
                        )

                        # Fallback: infer expected_diffs from task's own changes
                        if not _exp_diffs and ctx.get("changes"):
                            _seen_files = {}
                            for eid, ch in ctx["changes"]:
                                _cf = (ch.get("file", "") or "").split("/")[-1]
                                if _cf and _cf not in _seen_files:
                                    _verb = (ch.get("verb", "modify") or "modify").upper()
                                    _methods = ch.get("methods_changed", [])[:5]
                                    _classes = ch.get("classes", [])[:3]
                                    _risk = ch.get("risk_level", "LOW")
                                    _seen_files[_cf] = True
                                    _entry = {
                                        "file": _cf,
                                        "type": _verb,
                                        "marks": [],
                                        "inferred": True,
                                        "methods": _methods,
                                        "classes": _classes,
                                        "risk": _risk,
                                        "event_ids": [eid],
                                    }
                                    if ch.get("probe_status") == "FAIL" and not ch.get("resolved_by"):
                                        _entry["probe_status"] = "FAIL"
                                    elif ch.get("probe_status") == "PASS" or ch.get("resolved_by"):
                                        _entry["probe_status"] = "PASS"
                                    _exp_diffs.append(_entry)

                        ctx_serial["expected_diffs"] = _exp_diffs

                        # Compute completion signals
                        _n_changes = len(ctx.get("changes", []))
                        _n_probes_ok = sum(1 for _, ch in ctx.get("changes", [])
                                           if ch.get("probe_status") in ("PASS",) or ch.get("resolved_by"))
                        _n_probes_fail = sum(1 for _, ch in ctx.get("changes", [])
                                             if ch.get("probe_status") == "FAIL" and not ch.get("resolved_by"))
                        _has_assess = bool(ctx.get("last_assess"))

                        ctx_serial["completion_signals"] = {
                            "changes_count": _n_changes,
                            "probes_passing": _n_probes_ok,
                            "probes_failing": _n_probes_fail,
                            "all_probes_green": _n_probes_fail == 0 and _n_probes_ok > 0,
                            "has_assess": _has_assess,
                            "has_blame": bool(ctx.get("blame")),
                            "inferred_status": "COMPLETABLE" if (_n_changes > 0 and _n_probes_fail == 0) else
                                               "BLOCKED" if _n_probes_fail > 0 else "NO_EVIDENCE",
                        }

                        ctx_serial["_meta"] = {
                            "task_id": tid,
                            "title": t.get("title", ""),
                            "wherein": t.get("wherein", ""),
                            "generated": datetime.datetime.now().isoformat(),
                            "source": t.get("source", ""),
                        }

                        # ── G1: GapAnalyzer metastate + 5W1H query_weights ──────
                        if _ga_cached is not None:
                            try:
                                _gap_text = f"{t.get('title', '')} {t.get('description', '')}"
                                _ga_analysis = _ga_cached.analyze_text(_gap_text)
                                _ga_weights  = _ga_cached.calculate_metastate_weights(_ga_analysis)
                                ctx_serial['metastate'] = {
                                    'gap_severity':      _ga_weights.gap_severity,
                                    'recommended_action': _ga_weights.recommended_action,
                                    'priority_pct':      round(_ga_weights.priority_pct, 3),
                                    'understanding_pct': round(_ga_weights.understanding_pct, 3),
                                    'category_weights':  {k: round(v, 3) for k, v in _ga_weights.category_weights.items()},
                                }
                                ctx_serial['query_weights_data'] = {
                                    'what':          (t.get('title') or '?')[:60],
                                    'who':           t.get('who', 'user'),
                                    'where':         (t.get('wherein') or '?').split('/')[-1],
                                    'when':          (t.get('created_at') or '?')[:19],
                                    'why':           (t.get('description') or '?')[:60],
                                    'how':           _ga_weights.recommended_action,
                                    'state':         _ga_weights.gap_severity,
                                    'signal':        f"{int(_ga_weights.understanding_pct * 100)}% understood",
                                    'priority_bias': f"{int(_ga_weights.priority_pct * 100)}%",
                                }
                            except Exception:
                                pass

                        # ── G1b: Morph opinion (uses pre-loaded grounded cache) ─
                        if _grounded_cached is not None:
                            try:
                                _wh_base    = (t.get('wherein') or '').split('/')[-1]
                                _t_changes  = [c for c in _grounded_cached.get('enriched_changes', [])
                                               if c.get('file', '').endswith(_wh_base)] if _wh_base else []
                                _probe_fails = sum(1 for c in _t_changes if c.get('probe_status') == 'FAIL')
                                _verb = _t_changes[0].get('verb', '?') if _t_changes else '?'
                                _gap_sev = ctx_serial.get('metastate', {}).get('gap_severity', '?')
                                ctx_serial['morph_opinion_data'] = {
                                    'activity_type':   _verb,
                                    'gap_severity':    _gap_sev,
                                    'grounded_reason': f"{len(_t_changes)} change(s) in {_wh_base or '?'}",
                                    'probe_failures':  str(_probe_fails),
                                    'suggested_action': ctx_serial.get('query_weights_data', {}).get('how', '?'),
                                }
                            except Exception:
                                pass

                        # ── H2: code_profile_data from UnifiedContextIndex ────────
                        if _unified_index is not None:
                            try:
                                _wherein = t.get('wherein', '')
                                _uci_ent = _unified_index.get(_wherein) if _wherein else {}
                                if _uci_ent:
                                    _cg_s = _uci_ent.get('call_graph_summary', {})
                                    ctx_serial['code_profile_data'] = {
                                        'file':         _uci_ent.get('file_path', '?').split('/')[-1],
                                        'classes':      ', '.join(_uci_ent.get('classes', [])[:5]),
                                        'functions':    str(len(_uci_ent.get('functions', []))),
                                        'imports':      ', '.join(_uci_ent.get('imports', [])[:5]),
                                        'complexity':   str(_uci_ent.get('loc', '?')),
                                        'call_graph':   f"{_cg_s.get('forward_count',0)} fwd / {_cg_s.get('unique_callees',0)} callees",
                                        'verb_category': _uci_ent.get('event_summary', {}).get('top_verb', '?'),
                                        'line_count':   str(_uci_ent.get('loc', '?')),
                                    }
                            except Exception:
                                pass

                        # N0: inject _temporal from TemporalNarrativeEngine (cached per sync)
                        if _nar_cache is not None:
                            ctx_serial['_temporal'] = {
                                'dominant_domain':     _nar_cache.get('dominant_domain', ''),
                                'domain_confidence':   _nar_cache.get('domain_confidence', 0.0),
                                'files_touched_count': len(_nar_cache.get('files_touched', [])),
                                'phase_name':          _nar_cache.get('phase_name', ''),
                            }

                        ctx_path = tasks_dir / f"task_context_{tid}.json"
                        with open(ctx_path, "w", encoding="utf-8") as f:
                            json.dump(ctx_serial, f, indent=2, default=str)
                    except Exception:
                        pass
            except Exception:
                pass

            # ── D6: Post project context to ~/.claude/plans/ for agent consumption ──
            try:
                _claude_plans = Path.home() / ".claude" / "plans"
                _claude_plans.mkdir(parents=True, exist_ok=True)

                # Build lightweight import graph from py_manifest (once)
                _dep_graph = {}   # basename → [files it imports]
                _rev_graph = {}   # basename → [files that import it]
                try:
                    _d6_root = Path(__file__).parents[5]
                    _d6_pm_path = _d6_root / "pymanifest" / "py_manifest.json"
                    if _d6_pm_path.exists():
                        with open(_d6_pm_path, 'r') as f:
                            _d6_pm = json.load(f)
                        for _fp, _info in _d6_pm.get("files", {}).items():
                            if "/backup/" in _fp or "/history/" in _fp or "/archive/" in _fp:
                                continue
                            _bn = _fp.split("/")[-1]
                            if ".backup_" in _bn or _bn.startswith("LEGACY"):
                                continue
                            _deps = [d.split("/")[-1] for d in _info.get("dependencies", [])]
                            if _deps:
                                _dep_graph[_bn] = _deps
                                for _d in _deps:
                                    _rev_graph.setdefault(_d, []).append(_bn)
                except Exception:
                    pass

                # Group tasks by project_id
                _by_project = {}
                for tid, t in tasks.items():
                    pid = t.get("project_id", "unlinked")
                    _by_project.setdefault(pid, []).append((tid, t))

                for pid, ptasks in _by_project.items():
                    if pid == "unlinked":
                        continue
                    _active = [(tid, t) for tid, t in ptasks
                               if t.get("status", "").upper() in ("READY", "IN_PROGRESS", "OPEN")]
                    if not _active:
                        continue

                    # Collect all files touched by this project's tasks
                    _project_files = set()
                    for tid, t in _active:
                        _wh = (t.get("wherein") or "").split("/")[-1]
                        if _wh:
                            _project_files.add(_wh)

                    # Build impact set: files affected by changes to project files
                    _impact_set = set()
                    for _pf in _project_files:
                        for _imp in _rev_graph.get(_pf, []):
                            _impact_set.add(_imp)
                        for _dep in _dep_graph.get(_pf, []):
                            _impact_set.add(_dep)
                    _impact_set -= _project_files  # exclude self-references

                    _summary = {
                        "project_id": pid,
                        "generated": datetime.datetime.now().isoformat(),
                        "active_tasks": len(_active),
                        "tasks": [
                            {
                                "id": tid,
                                "title": t.get("title", ""),
                                "status": t.get("status", ""),
                                "wherein": t.get("wherein", ""),
                                "plan_doc": t.get("plan_doc", ""),
                                "changes": sum(1 for eid, ch in enriched_changes_fresh.items()
                                               if tid in (ch.get("task_ids") or [])),
                                "imports": _dep_graph.get((t.get("wherein") or "").split("/")[-1], []),
                                "imported_by": _rev_graph.get((t.get("wherein") or "").split("/")[-1], []),
                            }
                            for tid, t in _active
                        ],
                        "impact_radius": sorted(_impact_set),
                    }
                    _out = _claude_plans / f"project_{pid}.json"
                    _out.write_text(json.dumps(_summary, indent=2), encoding="utf-8")
            except Exception:
                pass

            def _update_ui():
                if result.get("error"):
                    self.status_bar.config(text=f"Sync error: {result['error'][:70]}")
                else:
                    src = ", ".join(result.get("sources", []))
                    self.status_bar.config(
                        text=f"Synced {result['task_count']} tasks  [{src}]"
                    )
                if _TRAINER_LOG_AVAILABLE:
                    _trainer_log.log_ux_event(
                        "ag_knowledge", "SYNC_TODOS", "sync_todos_button",
                        outcome="error" if result.get("error") else "success",
                        detail=f"tasks={result['task_count']} sources={result.get('sources')}",
                        wherein="PlannerSuite::sync_todos"
                    )
                # Refresh Task Board only (don't cascade into Os_Toolkit latest)
                self.refresh_task_board()
                global _SYNC_RUNNING
                _SYNC_RUNNING = False
            self.after(0, _update_ui)

        threading.Thread(target=_do_sync, daemon=True).start()

    def consolidate_plans(self):
        """Discover scattered .md plan files with #[Mark:] annotations.

        Scans a user-chosen directory (or Trainer/Data/ by default).
        Shows a dialog to review found files. On confirm:
          1. Extracts #[Mark:] lines from each file
          2. Offers to copy (not move) docs into plans/Plans/
          3. New marks found → appended to plans/checklist.json as PENDING candidates
        """
        import re as _re

        # Let user pick root dir to scan (default: Trainer/Data/)
        _data_root = Path(__file__).parents[5]
        scan_root = filedialog.askdirectory(
            title="Select directory to scan for plans",
            initialdir=str(_data_root)
        )
        if not scan_root:
            self.status_bar.config(text="Consolidate cancelled.")
            return

        self.status_bar.config(text=f"Scanning {scan_root} for .md plans...")
        self.update_idletasks()

        # Scan for .md files containing #[Mark:] or template section tags
        scan_path = Path(scan_root)
        EXCLUDE = {"__pycache__", ".git", "backup", "venv", "node_modules"}
        found = []
        try:
            for md in scan_path.rglob("*.md"):
                # Skip if inside plans/ dir (already consolidated)
                if "plans" in md.parts and str(Path(self.base_path)) in str(md):
                    continue
                if any(part in EXCLUDE for part in md.parts):
                    continue
                try:
                    text = md.read_text(encoding='utf-8', errors='replace')
                    marks = _re.findall(r'#\[Mark:([^\]]+)\]', text)
                    has_sections = bool(_re.search(r'<\/[A-Z][A-Za-z_]+>', text))
                    if marks or has_sections:
                        found.append({
                            "path": str(md),
                            "location": str(md.relative_to(_data_root)),
                            "marks": marks,
                            "has_sections": has_sections,
                            "size": md.stat().st_size,
                        })
                except Exception:
                    continue
        except Exception as e:
            self.status_bar.config(text=f"Scan error: {e}")
            return

        if not found:
            self.status_bar.config(text="No plan .md files with marks found.")
            messagebox.showinfo("Consolidate Plans", "No .md files with #[Mark:] or section tags found.")
            return

        # Dialog
        dlg = tk.Toplevel(self)
        dlg.title(f"Consolidate Plans — {len(found)} found")
        dlg.geometry("800x500")

        tk.Label(dlg,
                 text=f"Found {len(found)} plan docs with #[Mark:] / section tags. Select to add marks → checklist.json:",
                 anchor='w').pack(fill=tk.X, padx=10, pady=5)

        cols = ("marks", "size", "location")
        tv = ttk.Treeview(dlg, columns=cols, selectmode=tk.EXTENDED, height=16)
        tv.heading("#0", text="File")
        tv.heading("marks", text="Marks found")
        tv.heading("size", text="Size")
        tv.heading("location", text="Path")
        tv.column("#0", width=180)
        tv.column("marks", width=200)
        tv.column("size", width=60)
        tv.column("location", width=300)

        vsb = tk.Scrollbar(dlg, command=tv.yview)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        tv.configure(yscrollcommand=vsb.set)
        tv.pack(fill=tk.BOTH, expand=True, padx=10, pady=3)

        for item in found:
            marks_str = ", ".join(item["marks"][:4]) + ("…" if len(item["marks"]) > 4 else "")
            size_str = f"{item['size']//1024}KB" if item['size'] > 1024 else f"{item['size']}B"
            tag = "sections" if item["has_sections"] else "marks"
            tv.insert("", "end",
                      text=Path(item["path"]).name,
                      values=(marks_str or "(sections only)", size_str, item["location"]),
                      tags=(tag,))
        tv.tag_configure("sections", foreground="#2980b9")
        tv.tag_configure("marks", foreground="#27ae60")

        # Select all by default — user can deselect
        tv.selection_set(tv.get_children())

        btn_frame = tk.Frame(dlg)
        btn_frame.pack(fill=tk.X, padx=10, pady=6)

        result_label = tk.Label(btn_frame, text="", anchor='w', fg='#555')
        result_label.pack(side=tk.BOTTOM, fill=tk.X)

        def _do_consolidate():
            selected_iids = tv.selection()
            if not selected_iids:
                return

            selected_items = [found[tv.get_children().index(iid)] for iid in selected_iids]
            all_marks = []
            errors = []
            for item in selected_items:
                all_marks.extend(item["marks"])
                # Copy into plans/Plans/ preserving filename (no destructive move)
                try:
                    import shutil as _sh
                    dest = Path(self.base_path) / "Plans" / Path(item["path"]).name
                    if not dest.exists():
                        _sh.copy2(item["path"], str(dest))
                except Exception as e:
                    errors.append(str(e))

            # Add new marks to checklist.json as PENDING candidates
            new_candidates = 0
            checklist_path = Path(self.base_path) / "checklist.json"
            if all_marks and checklist_path.exists():
                try:
                    with open(checklist_path, encoding='utf-8') as f:
                        cl = json.load(f)
                    existing_ids = set()
                    for sec in cl.values():
                        if isinstance(sec, dict):
                            for it in sec.get("items", []):
                                existing_ids.add(it.get("id", ""))
                    consolidated_sec = cl.setdefault("consolidated_marks", {
                        "title": "Consolidated from plan scan",
                        "items": []
                    })
                    for mark in set(all_marks):
                        cid = f"mark_{mark.lower().replace(':', '_')}"
                        if cid not in existing_ids:
                            consolidated_sec["items"].append({
                                "id": cid,
                                "title": f"[Mark] {mark}",
                                "status": "PENDING",
                                "priority": "P2",
                                "source": "consolidate_scan",
                            })
                            new_candidates += 1
                    with open(checklist_path, 'w', encoding='utf-8') as f:
                        json.dump(cl, f, indent=2)
                except Exception as e:
                    errors.append(f"checklist: {e}")

            dlg.destroy()
            msg = f"Consolidated {len(selected_items)} plans. {new_candidates} new marks → checklist.json."
            if errors:
                msg += f" Errors: {len(errors)}"
            self.status_bar.config(text=msg)
            self.load_directory_structure()
            self.sync_todos()   # Refresh task board with new candidates
            if _TRAINER_LOG_AVAILABLE:
                _trainer_log.log_ux_event(
                    "ag_knowledge", "CONSOLIDATE_PLANS", "consolidate_plans_button",
                    outcome="success" if not errors else "partial",
                    detail=f"files={len(selected_items)} marks={new_candidates} errors={len(errors)}",
                    wherein="PlannerSuite::consolidate_plans"
                )

        tk.Button(btn_frame, text="Add Marks → Checklist + Copy to Plans/",
                  command=_do_consolidate).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="Cancel", command=dlg.destroy).pack(side=tk.LEFT, padx=5)

    # ── Project Bar ───────────────────────────────────────────────────────────

    def _setup_project_bar(self, parent):
        """Build the project selector bar in the left panel."""
        bar = tk.Frame(parent, bg='#2c3e50', pady=2)
        bar.pack(fill=tk.X, side=tk.TOP)

        # Active project indicator
        self._proj_indicator = tk.Label(bar, text="○ no active project",
            font=('Consolas', 8), fg='#7f8c8d', bg='#2c3e50', padx=4)
        self._proj_indicator.pack(side=tk.LEFT)

        # Epic selector dropdown
        self._epic_var = tk.StringVar(value="— select epic —")
        self._epic_options = self._get_epic_options()
        self._epic_menu_btn = tk.OptionMenu(bar, self._epic_var,
            "— select epic —", *[p.name for p in self._epic_options])
        self._epic_menu_btn.config(font=('Consolas', 8), bg='#34495e', fg='white',
                                    activebackground='#2980b9', width=25, pady=0)
        self._epic_menu_btn.pack(side=tk.LEFT, padx=2)

        tk.Button(bar, text="Load", font=('Consolas', 8), bg='#2980b9', fg='white',
                  pady=0, command=self._load_selected_epic).pack(side=tk.LEFT, padx=1)
        tk.Button(bar, text="★ Active", font=('Consolas', 8), bg='#16a085', fg='white',
                  pady=0, command=self._activate_selected_epic).pack(side=tk.LEFT, padx=1)
        tk.Button(bar, text="✨ New", font=('Consolas', 8), bg='#8e44ad', fg='white',
                  pady=0, command=self._show_new_project_dialog).pack(side=tk.LEFT, padx=1)

    def _get_epic_options(self):
        """Return sorted list of Path objects for Epics/*.md."""
        epics_dir = Path(self.base_path) / "Epics"
        if not epics_dir.exists():
            return []
        return sorted(epics_dir.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)

    def _refresh_project_dropdown(self):
        """Re-populate the epic OptionMenu after adding a new project."""
        self._epic_options = self._get_epic_options()
        menu = self._epic_menu_btn["menu"]
        menu.delete(0, "end")
        menu.add_command(label="— select epic —",
                         command=lambda: self._epic_var.set("— select epic —"))
        for p in self._epic_options:
            menu.add_command(label=p.name,
                             command=lambda n=p.name: self._epic_var.set(n))

    def _load_selected_epic(self):
        """Load the currently selected epic into doc_display."""
        sel = self._epic_var.get()
        if sel == "— select epic —":
            return
        path = Path(self.base_path) / "Epics" / sel
        if path.exists():
            self.open_file(str(path))

    def _activate_selected_epic(self):
        """Set selected epic as the active project."""
        sel = self._epic_var.get()
        if sel == "— select epic —":
            return
        path = Path(self.base_path) / "Epics" / sel
        if path.exists():
            self._set_active_project(path)

    def _set_active_project(self, epic_path):
        """Mark an epic as the active project; persist to config; refresh board."""
        self._active_project_path = Path(epic_path)
        # Extract ID from filename (strip .md, use stem)
        self._active_project_id = self._active_project_path.stem
        # Update indicator label
        if hasattr(self, '_proj_indicator'):
            self._proj_indicator.config(
                text=f"◉ {self._active_project_id[:30]}",
                fg='#27ae60'
            )
        # Persist to config.json
        try:
            cfg_path = Path(self.base_path) / "config.json"
            cfg = json.loads(cfg_path.read_text(encoding="utf-8")) if cfg_path.exists() else {}
            cfg["active_project_id"] = self._active_project_id
            cfg["active_project_path"] = str(self._active_project_path)
            cfg_path.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
        except Exception:
            pass
        self.status_bar.config(text=f"Active project: {self._active_project_id}")

        # 2a. Write system-wide broadcast file
        _broadcast = {
            "project_id":   self._active_project_id,
            "epic_path":    str(self._active_project_path),
            "activated_at": datetime.datetime.now().isoformat(),
            "wherein_files": self._parse_target_files_from_epic(self._active_project_path),
        }
        try:
            (Path(self.base_path) / "active_project.json").write_text(
                json.dumps(_broadcast, indent=2), encoding="utf-8")
        except Exception:
            pass

        # 2b. Write to Os_Toolkit action_panel plans config
        _os_cfg_path = Path(self.base_path).parent / "tabs" / "action_panel_tab" / "plans" / "config.json"
        if _os_cfg_path.parent.exists():
            try:
                _os_cfg = json.loads(_os_cfg_path.read_text()) if _os_cfg_path.exists() else {}
                _os_cfg["active_project_id"] = self._active_project_id
                _os_cfg["active_project_path"] = str(self._active_project_path)
                _os_cfg["active_project_set_at"] = datetime.datetime.now().isoformat()
                _os_cfg_path.write_text(json.dumps(_os_cfg, indent=2))
            except Exception:
                pass

        # 2c. App-ref propagation
        if self.app and hasattr(self.app, "set_active_project"):
            try:
                self.app.set_active_project(self._active_project_id, str(self._active_project_path))
            except Exception:
                pass

        # Refresh board to float relevant tasks
        self.refresh_task_board()

    # ── Colorized Editor ──────────────────────────────────────────────────────

    def _colorize_epic_display(self):
        """Apply color tags to doc_display for .md epic files.
        Green=filled, Orange=partial, Red=placeholder/missing, Blue=section headers.
        """
        try:
            content = self.doc_display.get("1.0", tk.END)
            lines = content.split("\n")
            for i, line in enumerate(lines, 1):
                start = f"{i}.0"
                end = f"{i}.end"
                stripped = line.strip()
                # Section headers
                if stripped.startswith("</") and stripped.endswith(">:"):
                    self.doc_display.tag_add("sec_header", start, end)
                elif stripped.startswith("<") and stripped.endswith("/>"):
                    self.doc_display.tag_add("sec_header", start, end)
                # Placeholder bullets
                elif stripped.startswith("- [") and (
                    "bullet" in stripped.lower() or
                    stripped == "- [###]" or
                    stripped.endswith("[###]") or
                    (stripped.endswith("]") and len(stripped) < 20)
                ):
                    self.doc_display.tag_add("field_missing", start, end)
                elif stripped.startswith("-") and len(stripped) < 22 and stripped != "-":
                    self.doc_display.tag_add("field_partial", start, end)
                elif stripped.startswith("-") and len(stripped) >= 22:
                    self.doc_display.tag_add("field_filled", start, end)
                # Section template markers [File/Doc], [###]
                elif "[File/Doc]" in stripped or "[###]" in stripped:
                    self.doc_display.tag_add("field_missing", start, end)
        except Exception:
            pass

    def _render_task_context_in_editor(self, tid):
        """Load task_context_{tid}.json into doc_display with color coding."""
        ctx_path = Path(self.base_path) / "Tasks" / f"task_context_{tid}.json"
        if not ctx_path.exists():
            self.status_bar.config(text=f"No context file for task {tid}")
            return
        try:
            ctx = json.loads(ctx_path.read_text(encoding="utf-8"))
        except Exception as e:
            self.status_bar.config(text=f"Error loading context: {e}")
            return

        self._ctx_cache[tid] = ctx
        self._current_edit_mode = "task_context"
        self._current_edit_tid = tid
        self._ctx_edit_source_path = ctx_path

        meta = ctx.get("_meta", {})
        self.doc_display.config(state=tk.NORMAL)
        self.doc_display.delete("1.0", tk.END)

        def _ins(text, tag=None):
            start = self.doc_display.index(tk.INSERT)
            self.doc_display.insert(tk.END, text)
            if tag:
                end = self.doc_display.index(tk.INSERT)
                self.doc_display.tag_add(tag, start, end)

        _ins(f"# Task Context: {tid}\n", "sec_header")
        _ins(f"# {meta.get('title','(no title)')}\n\n", "sec_header")

        def _field(label, value, hint=""):
            """Insert a labeled field with appropriate color."""
            _ins(f"{label}: ", "ctx_key")
            if not value or value in ([], {}, None, ""):
                tag = "field_missing" if hint else "field_partial"
                display = f"(empty){' — ' + hint if hint else ''}"
                _ins(display + "\n", tag)
            else:
                val_str = str(value) if not isinstance(value, (list, dict)) else json.dumps(value)[:80]
                _ins(val_str[:100] + "\n", "field_filled")

        _ins("\n## Identity\n", "sec_header")
        _field("task_id",    meta.get("task_id"))
        _field("title",      meta.get("title"))
        _field("wherein",    meta.get("wherein"), "Add file path (e.g. planner_tab.py)")
        _field("source",     meta.get("source"))
        _field("project_ref", ctx.get("project_ref") or meta.get("project_ref"), "Set project_id via right-click → Set Project ID")

        _ins("\n## Change Attribution\n", "sec_header")
        changes = ctx.get("changes", [])
        _field("changes", changes if changes else None, "Run 'python3 Os_Toolkit.py latest' to link changes")
        _field("blame",   ctx.get("blame") or None)
        _field("expected_diffs", ctx.get("expected_diffs") or None, "Link an Epic via Set Project ID")

        _ins("\n## Code Context\n", "sec_header")
        _field("code_profile",     ctx.get("code_profile"))
        cg = ctx.get("call_graph_data", {})
        cg_edges = cg.get("edges", []) if cg else []
        _field("call_graph edges", cg_edges if cg_edges else None, "Call graph not populated yet")
        _field("cluster_id",       ctx.get("cluster_id"))

        _ins("\n## Activity\n", "sec_header")
        _field("ux_events",    ctx.get("ux_events") or None)
        _field("test_results", ctx.get("test_results") or None)

        self.file_path_label.config(text=f"📋 task_context_{tid}.json  (edit mode)")
        self.status_bar.config(text=f"Context loaded for task {tid} — edit & Save to persist")

    def _on_doc_hover(self, event):
        """Show tooltip for missing/hint-tagged regions in doc_display."""
        try:
            idx = self.doc_display.index(f"@{event.x},{event.y}")
            tags = self.doc_display.tag_names(idx)
            hint_text = None
            if "field_missing" in tags:
                # Find the line content to build a contextual hint
                line_start = self.doc_display.index(f"{idx} linestart")
                line_end = self.doc_display.index(f"{idx} lineend")
                line = self.doc_display.get(line_start, line_end)
                if "wherein" in line:
                    hint_text = "💡 Add: file path e.g. 'planner_tab.py'"
                elif "project_ref" in line or "project_id" in line:
                    hint_text = "💡 Right-click task → Set Project ID"
                elif "changes" in line:
                    hint_text = "💡 Run: python3 Os_Toolkit.py latest"
                elif "expected_diffs" in line:
                    hint_text = "💡 Link an Epic to populate expected diffs"
                elif "- [" in line or "[###]" in line or "bullet" in line.lower():
                    hint_text = "💡 Replace placeholder with actual content"
                else:
                    hint_text = "💡 Missing attribute — click to edit"
            if hint_text:
                self._show_tooltip(event.x_root + 12, event.y_root + 8, hint_text)
            else:
                self._hide_tooltip()
        except Exception:
            self._hide_tooltip()

    def _show_tooltip(self, x, y, text):
        """Display a floating tooltip at screen coordinates."""
        self._hide_tooltip()
        try:
            self._tooltip_win = tk.Toplevel(self)
            self._tooltip_win.wm_overrideredirect(True)
            self._tooltip_win.wm_geometry(f"+{x}+{y}")
            lbl = tk.Label(self._tooltip_win, text=text,
                           bg='#2c3e50', fg='#ecf0f1',
                           font=('Consolas', 8), padx=6, pady=3,
                           relief=tk.FLAT, borderwidth=1)
            lbl.pack()
            self._tooltip_win.attributes('-topmost', True)
        except Exception:
            pass

    def _hide_tooltip(self):
        """Destroy tooltip if visible."""
        if self._tooltip_win:
            try:
                self._tooltip_win.destroy()
            except Exception:
                pass
            self._tooltip_win = None

    def _on_doc_save_with_refresh(self):
        """Save doc, then refresh board if editing a task_context or epic."""
        self.save_document()  # existing save logic
        if self._current_edit_mode == "task_context" and self._current_edit_tid:
            # Parse the displayed content and write back to task_context JSON
            try:
                ctx_path = Path(self.base_path) / "Tasks" / f"task_context_{self._current_edit_tid}.json"
                if ctx_path.exists():
                    # Load existing JSON, keep structure intact
                    ctx = json.loads(ctx_path.read_text(encoding="utf-8"))
                    # Extract project_ref line from display
                    content = self.doc_display.get("1.0", tk.END)
                    for line in content.split("\n"):
                        if line.startswith("project_ref:") and "(empty)" not in line:
                            val = line.split(":", 1)[1].strip()
                            if val:
                                ctx.setdefault("_meta", {})["project_ref"] = val
                                ctx["project_ref"] = val
                        elif line.startswith("wherein:") and "(empty)" not in line:
                            val = line.split(":", 1)[1].strip()
                            if val:
                                ctx.setdefault("_meta", {})["wherein"] = val
                    ctx_path.write_text(json.dumps(ctx, indent=2), encoding="utf-8")
                    self._ctx_cache[self._current_edit_tid] = ctx
                    # Refresh just this row
                    self._refresh_single_board_row(self._current_edit_tid)
            except Exception:
                pass
            self.status_bar.config(text="✓ Context saved — board updated")
        elif self._current_edit_mode == "epic":
            self._refresh_project_dropdown()
            self.status_bar.config(text="✓ Epic saved — project list refreshed")

    def _get_task_meta_quick(self, tid):
        """Return (project_ref, gap_count) for a task from cached task_context."""
        if not tid:
            return ("", 0)
        if tid in self._ctx_cache:
            ctx = self._ctx_cache[tid]
        else:
            ctx_path = Path(self.base_path) / "Tasks" / f"task_context_{tid}.json"
            if not ctx_path.exists():
                return ("", 0)
            try:
                ctx = json.loads(ctx_path.read_text(encoding="utf-8"))
                self._ctx_cache[tid] = ctx
            except Exception:
                return ("", 0)
        meta = ctx.get("_meta", {})
        proj = ctx.get("project_ref") or meta.get("project_ref") or ""
        # Count critical gaps
        gaps = 0
        if not meta.get("wherein"):
            gaps += 1
        if not proj:
            gaps += 1
        if not ctx.get("changes"):
            gaps += 1
        if not ctx.get("expected_diffs"):
            gaps += 1
        return (proj[:20] if proj else "", gaps)

    def _refresh_single_board_row(self, tid):
        """Update the project/gaps columns for a single task row without full reload."""
        proj, gaps = self._get_task_meta_quick(tid)
        # Find the iid for this task in the board
        for iid in self.board_tree.get_children():
            self._update_row_if_match(iid, tid, proj, gaps)

    def _update_row_if_match(self, iid, tid, proj, gaps):
        """Recursively find and update a task row by tid."""
        try:
            vals = list(self.board_tree.item(iid, "values"))
            tags = list(self.board_tree.item(iid, "tags"))
            # Check if this iid corresponds to the task (stored in _board_tasks)
            if self._board_tasks.get(iid) == tid:
                # Update project and gaps columns (indices 6 and 7)
                while len(vals) < 8:
                    vals.append("")
                vals[6] = proj
                vals[7] = str(gaps) if gaps else ""
                if gaps > 0 and "has_gaps" not in tags:
                    tags.append("has_gaps")
                elif gaps == 0 and "has_gaps" in tags:
                    tags.remove("has_gaps")
                self.board_tree.item(iid, values=vals, tags=tags)
                return
            for child in self.board_tree.get_children(iid):
                self._update_row_if_match(child, tid, proj, gaps)
        except Exception:
            pass

    def _refresh_live_branch(self):
        """Auto-refresh the live polling branch every 30 seconds."""
        if not self._live_refresh_pending:
            return
        try:
            # Remove old live items
            if self.board_tree.exists("§live"):
                for child in self.board_tree.get_children("§live"):
                    self.board_tree.delete(child)
                # Reload active tasks
                sync_path = Path(self.base_path) / "Refs" / "latest_sync.json"
                if sync_path.exists():
                    data = json.loads(sync_path.read_text(encoding="utf-8"))
                    tasks = data if isinstance(data, list) else data.get("tasks", [])
                    live = [t for t in tasks
                            if str(t.get("status","")).lower().replace("-","_") in ("in_progress","inprogress")]
                    self.board_tree.item("§live", text=f"🔴  LIVE — {len(live)} in progress")
                    for lt in live[:10]:
                        lt_id = lt.get("id", "")
                        lt_proj, lt_gaps = self._get_task_meta_quick(lt_id)
                        _tags = ("inprog",) + (("has_gaps",) if lt_gaps > 0 else ())
                        try:
                            self.board_tree.insert("§live", "end",
                                iid=f"§live_{lt_id}_{id(lt)}",
                                text=f"  {str(lt.get('title',''))[:45]}",
                                values=(lt.get("status",""), lt.get("wherein","")[:35],
                                        lt.get("source",""), "", "", "", lt_proj,
                                        str(lt_gaps) if lt_gaps else ""),
                                tags=_tags)
                        except Exception:
                            pass
        except Exception:
            pass
        self.after(30_000, self._refresh_live_branch)

    def _quick_set_project(self, tid):
        """Quick dialog to set project_ref on a task_context."""
        epics = self._get_epic_options()
        if not epics:
            messagebox.showinfo("No Epics", "No Epic files found in plans/Epics/")
            return
        dlg = tk.Toplevel(self)
        dlg.title(f"Set Project for {tid}")
        dlg.geometry("340x120")
        dlg.transient(self)
        dlg.grab_set()
        tk.Label(dlg, text="Select project:", font=('Consolas', 9)).pack(pady=(10, 2))
        var = tk.StringVar(value=epics[0].stem)
        opts = [p.stem for p in epics]
        om = tk.OptionMenu(dlg, var, *opts)
        om.config(font=('Consolas', 9))
        om.pack(fill=tk.X, padx=20)
        def _apply():
            proj_id = var.get()
            ctx_path = Path(self.base_path) / "Tasks" / f"task_context_{tid}.json"
            try:
                ctx = json.loads(ctx_path.read_text()) if ctx_path.exists() else {"_meta": {}}
                ctx["project_ref"] = proj_id
                ctx.setdefault("_meta", {})["project_ref"] = proj_id
                ctx_path.write_text(json.dumps(ctx, indent=2))
                self._ctx_cache[tid] = ctx
                self._refresh_single_board_row(tid)
                self.status_bar.config(text=f"Project set: {proj_id} → task {tid}")
            except Exception as ex:
                messagebox.showerror("Error", str(ex))
            dlg.destroy()
        tk.Button(dlg, text="Set Project", command=_apply, bg='#2980b9', fg='white').pack(pady=8)

    # ── New Project Dialog ────────────────────────────────────────────────────

    def _show_new_project_dialog(self):
        """Full project creation dialog following Project_Template_1.md format."""
        dlg = tk.Toplevel(self)
        dlg.title("✨ New Project")
        dlg.geometry("700x750")
        dlg.transient(self)
        dlg.grab_set()
        dlg.resizable(True, True)

        nb = ttk.Notebook(dlg)
        nb.pack(fill=tk.BOTH, expand=True, padx=6, pady=4)

        # ── Tab 1: Core ──
        tab1 = tk.Frame(nb)
        nb.add(tab1, text="Core")

        top = tk.Frame(tab1)
        top.pack(fill=tk.X, padx=8, pady=6)
        tk.Label(top, text="Title:", font=('Consolas', 9, 'bold')).pack(side=tk.LEFT)
        title_var = tk.StringVar()
        tk.Entry(top, textvariable=title_var, font=('Consolas', 9), width=35).pack(side=tk.LEFT, padx=4)
        # Auto-generate ID
        try:
            pj_path = Path(self.base_path) / "projects.json"
            pj = json.loads(pj_path.read_text()) if pj_path.exists() else {"next_seq": 1}
            seq = pj.get("next_seq", 1)
        except Exception:
            seq = 1
        id_var = tk.StringVar(value=f"Project_{seq:03d}")
        tk.Label(top, text="ID:", font=('Consolas', 9)).pack(side=tk.LEFT, padx=(8,0))
        tk.Entry(top, textvariable=id_var, font=('Consolas', 9), width=14).pack(side=tk.LEFT, padx=2)

        sections = {}
        for section, label, height in [
            ("high_level", "High Level (abstract — what & why):", 5),
            ("mid_level",  "Mid Level (plan doc briefs — how):", 5),
            ("low_level",  "Low Level (insights & gotchas):", 5),
        ]:
            fr = tk.LabelFrame(tab1, text=label, font=('Consolas', 9))
            fr.pack(fill=tk.X, padx=8, pady=3)
            t = tk.Text(fr, height=height, font=('Consolas', 9), wrap=tk.WORD)
            t.pack(fill=tk.X, padx=4, pady=2)
            sections[section] = t

        # ── Tab 2: Targets & Provisions ──
        tab2 = tk.Frame(nb)
        nb.add(tab2, text="Targets")

        tf_fr = tk.LabelFrame(tab2, text="Target Files", font=('Consolas', 9))
        tf_fr.pack(fill=tk.BOTH, padx=8, pady=4, expand=True)
        tf_list = tk.Listbox(tf_fr, height=6, font=('Consolas', 9))
        tf_list.pack(fill=tk.BOTH, expand=True, padx=4, pady=2)
        tf_btns = tk.Frame(tf_fr)
        tf_btns.pack(fill=tk.X, padx=4)
        tf_entry = tk.Entry(tf_btns, font=('Consolas', 8), width=40)
        tf_entry.pack(side=tk.LEFT)
        def _add_file():
            v = tf_entry.get().strip()
            if v:
                tf_list.insert(tk.END, v)
                tf_entry.delete(0, tk.END)
        def _browse_file():
            p = filedialog.askopenfilename(initialdir=str(Path(self.base_path).parent))
            if p:
                rel = os.path.relpath(p, str(Path(self.base_path).parent))
                tf_list.insert(tk.END, rel)
        tk.Button(tf_btns, text="+ Add", command=_add_file).pack(side=tk.LEFT, padx=2)
        tk.Button(tf_btns, text="Browse", command=_browse_file).pack(side=tk.LEFT, padx=2)

        gf = tk.LabelFrame(tab2, text="Goals", font=('Consolas', 9))
        gf.pack(fill=tk.X, padx=8, pady=4)
        goals_text = tk.Text(gf, height=4, font=('Consolas', 9))
        goals_text.pack(fill=tk.X, padx=4, pady=2)

        pf = tk.LabelFrame(tab2, text="Provisions", font=('Consolas', 9))
        pf.pack(fill=tk.X, padx=8, pady=4)
        pf_inner = tk.Frame(pf)
        pf_inner.pack(fill=tk.X, padx=4, pady=2)
        tk.Label(pf_inner, text="Packages:", font=('Consolas', 8)).pack(side=tk.LEFT)
        pkg_entry = tk.Entry(pf_inner, font=('Consolas', 8), width=20)
        pkg_entry.pack(side=tk.LEFT, padx=2)
        pkg_list = tk.Listbox(pf, height=3, font=('Consolas', 8))
        pkg_list.pack(fill=tk.X, padx=4)
        def _add_pkg():
            v = pkg_entry.get().strip()
            if v:
                pkg_list.insert(tk.END, v)
                pkg_entry.delete(0, tk.END)
        tk.Button(pf_inner, text="+", command=_add_pkg).pack(side=tk.LEFT)

        # ── Tab 3: Meta Links / Call Graph ──
        tab3 = tk.Frame(nb)
        nb.add(tab3, text="Meta Links")

        cg_fr = tk.LabelFrame(tab3, text="Call Graph Builder", font=('Consolas', 9))
        cg_fr.pack(fill=tk.X, padx=8, pady=4)
        cg_row = tk.Frame(cg_fr)
        cg_row.pack(fill=tk.X, padx=4, pady=4)
        tk.Label(cg_row, text="File:", font=('Consolas', 8)).pack(side=tk.LEFT)
        cg_file_var = tk.StringVar(value="— select .py file —")
        # Gather python files from Data/tabs/
        _data_root_path = Path(self.base_path).parent
        _py_files = sorted([
            str(p.relative_to(_data_root_path))
            for p in _data_root_path.glob("tabs/**/*.py")
            if not any(x in str(p) for x in ['__pycache__', 'backup', 'archive'])
        ])[:80]
        cg_file_menu = tk.OptionMenu(cg_row, cg_file_var, "— select .py file —", *_py_files)
        cg_file_menu.config(font=('Consolas', 8), width=30)
        cg_file_menu.pack(side=tk.LEFT, padx=2)
        tk.Label(cg_row, text="Layer:", font=('Consolas', 8)).pack(side=tk.LEFT, padx=(6,0))
        cg_layer_var = tk.StringVar(value="imports")
        tk.OptionMenu(cg_row, cg_layer_var,
                      "imports", "importers", "classes", "functions", "call_edges").pack(side=tk.LEFT, padx=2)
        sugg_fr = tk.LabelFrame(tab3, text="Suggestions (multi-select)", font=('Consolas', 9))
        sugg_fr.pack(fill=tk.BOTH, padx=8, pady=4, expand=True)
        sugg_list = tk.Listbox(sugg_fr, height=7, selectmode=tk.MULTIPLE, font=('Consolas', 8))
        sugg_list.pack(fill=tk.BOTH, expand=True, padx=4, pady=2)
        def _fetch_cg():
            sugg_list.delete(0, tk.END)
            f = cg_file_var.get()
            if f == "— select .py file —":
                return
            layer = cg_layer_var.get()
            results = self._fetch_callgraph_suggestions(
                str(_data_root_path / f), layer)
            for r in results:
                sugg_list.insert(tk.END, r)
        tk.Button(cg_fr, text="🔍 Fetch Suggestions", command=_fetch_cg).pack(padx=4, pady=2)
        ml_fr = tk.LabelFrame(tab3, text="Meta Links (selected)", font=('Consolas', 9))
        ml_fr.pack(fill=tk.BOTH, padx=8, pady=4, expand=True)
        ml_list = tk.Listbox(ml_fr, height=5, font=('Consolas', 8))
        ml_list.pack(fill=tk.BOTH, expand=True, padx=4, pady=2)
        def _add_to_meta():
            for i in sugg_list.curselection():
                item = sugg_list.get(i)
                ml_list.insert(tk.END, f"- {item}")
        tk.Button(tab3, text="→ Add Selected to Meta Links", command=_add_to_meta).pack(pady=2)

        # ── Tab 4: Tasks ──
        tab4 = tk.Frame(nb)
        nb.add(tab4, text="Tasks")
        auto_tasks_var = tk.BooleanVar(value=True)
        tk.Checkbutton(tab4, text="Auto-generate linked tasks from template",
                       variable=auto_tasks_var, font=('Consolas', 9)).pack(anchor='w', padx=8, pady=8)
        task_count_fr = tk.Frame(tab4)
        task_count_fr.pack(anchor='w', padx=8)
        tk.Label(task_count_fr, text="Task count:", font=('Consolas', 9)).pack(side=tk.LEFT)
        task_count_var = tk.IntVar(value=3)
        tk.Spinbox(task_count_fr, from_=1, to=10, textvariable=task_count_var,
                   width=4, font=('Consolas', 9)).pack(side=tk.LEFT, padx=4)
        task_titles_fr = tk.LabelFrame(tab4, text="Task Titles (one per line)", font=('Consolas', 9))
        task_titles_fr.pack(fill=tk.BOTH, padx=8, pady=4, expand=True)
        task_titles_text = tk.Text(task_titles_fr, height=6, font=('Consolas', 9))
        task_titles_text.pack(fill=tk.BOTH, expand=True, padx=4, pady=2)
        task_titles_text.insert("1.0", "Implement core feature\nWrite tests\nUpdate documentation")

        # ── Bottom: Create / Cancel ──
        btn_fr = tk.Frame(dlg)
        btn_fr.pack(fill=tk.X, padx=8, pady=6)
        def _create():
            data = {
                "title": title_var.get().strip(),
                "project_id": id_var.get().strip(),
                "high_level": sections["high_level"].get("1.0", tk.END).strip(),
                "mid_level":  sections["mid_level"].get("1.0",  tk.END).strip(),
                "low_level":  sections["low_level"].get("1.0",  tk.END).strip(),
                "files": [tf_list.get(i) for i in range(tf_list.size())],
                "goals": goals_text.get("1.0", tk.END).strip(),
                "packages": [pkg_list.get(i) for i in range(pkg_list.size())],
                "meta_links": [ml_list.get(i) for i in range(ml_list.size())],
                "auto_tasks": auto_tasks_var.get(),
                "task_count": task_count_var.get(),
                "task_titles": [t.strip() for t in task_titles_text.get("1.0", tk.END).strip().split("\n") if t.strip()],
            }
            if not data["title"]:
                messagebox.showwarning("Missing Title", "Please enter a project title.")
                return
            self._create_project_from_dialog(data)
            dlg.destroy()
        tk.Button(btn_fr, text="✨ Create Project", command=_create,
                  bg='#8e44ad', fg='white', font=('Consolas', 10, 'bold'),
                  padx=10).pack(side=tk.LEFT, padx=4)
        tk.Button(btn_fr, text="Cancel", command=dlg.destroy).pack(side=tk.LEFT)

    def _fetch_callgraph_suggestions(self, file_path, layer):
        """Fetch call graph data from py_manifest_augmented.json for a file."""
        results = []
        try:
            manifest_path = Path(self.base_path).parent / "pymanifest" / "py_manifest_augmented.json"
            if not manifest_path.exists():
                # Try alternate location
                manifest_path = Path(self.base_path).parent / "backup" / "py_manifest_augmented.json"
            if not manifest_path.exists():
                return ["(py_manifest_augmented.json not found)"]
            data = json.loads(manifest_path.read_text(encoding="utf-8", errors="replace")[:2_000_000])
            # Find matching file entry
            target = os.path.normpath(file_path)
            entry = None
            for key, val in data.items() if isinstance(data, dict) else []:
                if isinstance(key, str) and os.path.normpath(key).endswith(os.path.normpath(file_path.split(os.sep)[-1])):
                    entry = val
                    break
            if not entry:
                return [f"(no entry found for {os.path.basename(file_path)})"]
            if layer == "imports":
                results = entry.get("imports", [])[:40]
            elif layer == "importers":
                results = entry.get("importers", [])[:40]
            elif layer == "classes":
                results = [c.get("name", "") for c in entry.get("classes", [])][:40]
            elif layer == "functions":
                results = [f.get("name", "") for f in entry.get("functions", [])][:40]
            elif layer == "call_edges":
                edges = entry.get("call_graph", {}).get("edges", [])
                results = [f"{e.get('from','')} → {e.get('to','')}" for e in edges[:20]]
        except Exception as ex:
            results = [f"(error: {ex})"]
        return [str(r) for r in results if r]

    def _create_project_from_dialog(self, data):
        """Create a new project: write epic .md, update projects.json, create tasks."""
        project_id = data["project_id"]
        title = data["title"]
        slug = title.lower().replace(" ", "_").replace("/", "_")[:30]
        epic_path = Path(self.base_path) / "Epics" / f"{project_id}_{slug}.md"

        # Build template content
        def _bullets(text, count=5):
            lines = [l.strip() for l in text.split("\n") if l.strip()]
            while len(lines) < count:
                lines.append("[to be defined]")
            return "\n".join(f"- {l}" for l in lines[:count])

        files_bullets = "\n".join(f"- {f}" for f in data["files"]) or "- [no files specified]"
        goals_bullets = _bullets(data["goals"])
        meta_links_txt = "\n".join(data["meta_links"]) or "- [none]"
        packages_txt = "\n".join(f"- {p}" for p in data["packages"]) or "- [none]"

        content = f"""</PROJECT_TEMPLATE_001>
###
</High_Level>:
{_bullets(data['high_level'])}

<High_Level/>. |
##
</Mid_Level>:
{_bullets(data['mid_level'])}

<Mid_Level/>. |
##
</Low_Level>:
{_bullets(data['low_level'])}

<Low_Level/>. |
##
</Meta_Links>:
{meta_links_txt}

<Meta_Links/>. |
##
</Provisions>:
#
[Packages]
{packages_txt}

<Provisions/>. |
##
</Current_Targets>:

[Files]:
{files_bullets}

[Goal(s)]:
{goals_bullets}

<Current_Targets/>. |
##
</Diffs>: (New/Modify/Remove)
#
[File/Doc] - [###]
-/path/###.#
 -Lines
  -#
  +#
-#[Mark:###] - [###]

<Diffs/>. |
#
</Plans_manifested>:
- [5 bullets — ref plan docs]

<Plans_Manifested>. |
#
</Current_Todos>:
- [auto-generated tasks below]

<Current_Todos>. |
"""
        try:
            epic_path.write_text(content, encoding="utf-8")
        except Exception as e:
            messagebox.showerror("Error", f"Could not write epic file: {e}")
            return

        # Update projects.json
        try:
            pj_path = Path(self.base_path) / "projects.json"
            pj = json.loads(pj_path.read_text()) if pj_path.exists() else {"projects": [], "next_seq": 1}
            pj["projects"].append({
                "project_id": project_id,
                "title": title,
                "epic_path": str(epic_path),
                "created": datetime.datetime.now().isoformat()[:16],
                "scan_target": "local",
                "model": None
            })
            pj["next_seq"] = pj.get("next_seq", 1) + 1
            pj_path.write_text(json.dumps(pj, indent=2))
        except Exception:
            pass

        # Create linked tasks if requested
        if data.get("auto_tasks"):
            task_titles = data.get("task_titles", [])
            task_count = data.get("task_count", 3)
            import datetime as _dt
            yymm = _dt.datetime.now().strftime("%y%m")
            try:
                todos_path = Path(self.base_path) / "todos.json"
                todos = json.loads(todos_path.read_text()) if todos_path.exists() else []
                if isinstance(todos, list):
                    existing_ids = {t.get("id") for t in todos}
                else:
                    existing_ids = set()
                    todos = []
                phase_key = f"phase_new_{yymm}"
                seq = sum(1 for t in todos if str(t.get("id","")).startswith(f"task_{yymm}")) + 1
                created_tids = []
                for i in range(min(task_count, max(len(task_titles), task_count))):
                    t_title = task_titles[i] if i < len(task_titles) else f"{title} — Task {i+1}"
                    tid = f"task_{yymm}_{seq + i}"
                    task_entry = {
                        "id": tid,
                        "title": t_title,
                        "status": "pending",
                        "project_id": project_id,
                        "wherein": data["files"][0] if data["files"] else "",
                        "created_at": _dt.datetime.now().isoformat()
                    }
                    todos.append(task_entry)
                    created_tids.append(tid)
                    # Write seed task_context
                    ctx_path = Path(self.base_path) / "Tasks" / f"task_context_{tid}.json"
                    seed_ctx = {
                        "peers": [], "dna": None, "changes": [], "ux_events": [],
                        "tool_profile": None, "blame": [], "code_profile": None,
                        "cluster_id": None, "time_delta_min": 0, "expected_diffs": [],
                        "project_ref": project_id,
                        "call_graph_data": {"edges":[],"imports":[],"importers":[],"edge_count":0,"matched_path":""},
                        "_meta": {
                            "task_id": tid, "title": t_title,
                            "wherein": data["files"][0] if data["files"] else "",
                            "project_ref": project_id,
                            "generated": _dt.datetime.now().isoformat(),
                            "source": "new_project_dialog"
                        }
                    }
                    ctx_path.write_text(json.dumps(seed_ctx, indent=2))
                todos_path.write_text(json.dumps(todos, indent=2))
            except Exception as ex:
                self.status_bar.config(text=f"Warning: task creation failed: {ex}")

        # Refresh UI
        self._refresh_project_dropdown()
        self.refresh_task_board()
        self.open_file(str(epic_path))
        self._set_active_project(epic_path)
        self.status_bar.config(text=f"✨ Project created: {project_id} — {len(data.get('task_titles',[]))} tasks")

    # ── Active Project Propagation & Watcher Inference ───────────────────────

    def _parse_target_files_from_epic(self, epic_path):
        """Extract [Files]: bullets from </Current_Targets>: section of an epic."""
        files = []
        try:
            content = Path(epic_path).read_text(encoding="utf-8", errors="replace")
            in_targets = False
            in_files = False
            for line in content.split("\n"):
                if "</Current_Targets>:" in line:
                    in_targets = True
                elif in_targets and "<Current_Targets/>" in line:
                    break
                elif in_targets and "[Files]:" in line:
                    in_files = True
                elif in_targets and in_files and line.strip().startswith("-"):
                    f = line.strip().lstrip("- ").strip()
                    if f and "[" not in f:
                        files.append(os.path.basename(f))
                elif in_targets and in_files and line.strip() and not line.strip().startswith("-"):
                    in_files = False
        except Exception:
            pass
        return files

    def _get_all_epic_file_refs(self):
        """Returns {basename: project_id} map from all epics' Current_Targets sections."""
        file_to_proj = {}
        epics_dir = Path(self.base_path) / "Epics"
        if not epics_dir.exists():
            return file_to_proj
        for epic_path in epics_dir.glob("*.md"):
            proj_id = epic_path.stem
            files = self._parse_target_files_from_epic(epic_path)
            for f in files:
                if f not in file_to_proj:  # first epic wins
                    file_to_proj[f] = proj_id
        return file_to_proj

    def _restore_active_project_indicator(self):
        """Sync _proj_indicator to match _active_project_id loaded from config."""
        if not hasattr(self, '_proj_indicator'):
            return
        if self._active_project_id:
            self._proj_indicator.config(
                text=f"◉ {self._active_project_id[:30]}", fg='#27ae60')
        else:
            self._proj_indicator.config(text="○ no active project", fg='#7f8c8d')

    def _check_recent_probe_for_file(self, basename):
        """Check most recent probe result for a given file from debug logs.
        Returns 'PASS', 'FAIL', or None.
        probe_status: SKIP + test_status: PASS is treated as PASS (GUI files can't exec headlessly).
        """
        try:
            debug_dir = Path(self.base_path).parent / "DeBug"
            if not debug_dir.exists():
                debug_dir = Path(self.base_path).parent.parent / "DeBug"
            if not debug_dir.exists():
                return None
            logs = sorted(debug_dir.glob("debug_log_*.txt"), reverse=True)[:3]
            for log_path in logs:
                content = log_path.read_text(encoding="utf-8", errors="replace")
                lines = content.split("\n")
                for line in reversed(lines[-200:]):
                    if basename in line:
                        ll = line.lower()
                        if ("pass" in ll and "probe" in ll) or "exec_ok" in ll or "test_status.*pass" in ll:
                            return "PASS"
                        if "test_status" in ll and "pass" in ll:
                            return "PASS"
                        if "py_compile" in ll and ("ok" in ll or "pass" in ll):
                            return "PASS"
                        if ("fail" in ll and "probe" in ll) or "probe_fail" in ll or "exec_fail" in ll:
                            return "FAIL"
        except Exception:
            pass
        return None

    def _infer_tasks_for_change(self, basename):
        """Return list of task_ids likely relevant to the changed file."""
        relevant = []
        active_files = []
        if self._active_project_path:
            active_files = self._parse_target_files_from_epic(self._active_project_path)

        sync_path = Path(self.base_path) / "Refs" / "latest_sync.json"
        if not sync_path.exists():
            return relevant
        try:
            data = json.loads(sync_path.read_text(encoding="utf-8"))
            raw = data.get("tasks", {}) if isinstance(data, dict) else data
            # Normalize: dict-keyed {tid: {...}} OR list [{id:..., ...}]
            if isinstance(raw, dict):
                task_pairs = [(tid, td) for tid, td in raw.items() if isinstance(td, dict)]
            else:
                task_pairs = [(t.get("id", ""), t) for t in raw if isinstance(t, dict)]
        except Exception:
            return relevant

        in_progress_matches = []
        ready_matches = []
        project_matches = []
        _active_statuses = {"in_progress", "ready", "pending", "design_ready", "prototype_ready"}
        for tid, t in task_pairs:
            wherein = os.path.basename(str(t.get("wherein", "") or ""))
            status = str(t.get("status", "")).lower().replace("-", "_").replace(" ", "_")
            proj, _ = self._get_task_meta_quick(tid)
            is_project_task = (proj == self._active_project_id) if self._active_project_id else False
            file_matches = (basename in wherein) or (wherein and wherein in basename)

            if file_matches and status == "in_progress":
                in_progress_matches.append(tid)
            elif file_matches and status in _active_statuses:
                ready_matches.append(tid)
            elif file_matches and is_project_task:
                project_matches.append(tid)
            elif is_project_task and basename in active_files:
                project_matches.append(tid)

        seen = set()
        for tid in in_progress_matches + ready_matches + project_matches:
            if tid not in seen:
                seen.add(tid)
                relevant.append(tid)
        return relevant[:5]

    def _promote_tasks_in_live_branch(self, task_ids):
        """Move inferred tasks to the top of the §live branch, tagged proj_rel."""
        if not hasattr(self, 'board_tree') or not self.board_tree.exists("§live"):
            return
        for tid in task_ids:
            iid = f"§infer_{tid}"
            if self.board_tree.exists(iid):
                self.board_tree.delete(iid)
            task_text = ""
            task_vals = ("", "", "", "", "", "", "", "")
            for node_iid, node_tid in list(self._board_tasks.items()):
                if node_tid == tid or (isinstance(node_tid, dict) and node_tid.get("tid") == tid):
                    try:
                        task_text = self.board_tree.item(node_iid, "text")
                        task_vals = self.board_tree.item(node_iid, "values")
                    except Exception:
                        pass
                    break
            if not task_text:
                task_text = f"  ⟳ {tid}"
            try:
                self.board_tree.insert("§live", 0, iid=iid,
                    text=f"  ↑ {task_text.strip()[:45]}",
                    values=task_vals,
                    tags=("proj_rel", "inprog"))
            except Exception:
                pass

    def _on_watcher_file_change(self, changed_file_path):
        """Fired on main thread when watcher detects a hash change."""
        basename = os.path.basename(str(changed_file_path))

        matching_tids = self._infer_tasks_for_change(basename)

        if matching_tids:
            self._promote_tasks_in_live_branch(matching_tids)

        probe_result = self._check_recent_probe_for_file(basename)

        if matching_tids:
            tid = matching_tids[0]
            td = self._board_tasks.get(tid)
            task_title = td.get("title", tid) if isinstance(td, dict) else str(tid)
            if probe_result == "PASS":
                if hasattr(self, 'status_bar'):
                    self.status_bar.config(
                        text=f"💡 {basename} changed + probe PASS → '{task_title[:40]}' may be complete — ✓ Complete?",
                        fg='#27ae60')
                if hasattr(self, 'board_status'):
                    self.board_status.config(
                        text=f"🔔 Completion candidate: {tid} ({basename})", fg='#27ae60')
            elif probe_result == "FAIL":
                if hasattr(self, 'status_bar'):
                    self.status_bar.config(
                        text=f"⚠ {basename} changed but probe FAIL → task '{task_title[:35]}' blocked",
                        fg='#e74c3c')
            else:
                if hasattr(self, 'status_bar'):
                    self.status_bar.config(
                        text=f"👁 {basename} changed → relevant task: '{task_title[:40]}'",
                        fg='#e67e22')
