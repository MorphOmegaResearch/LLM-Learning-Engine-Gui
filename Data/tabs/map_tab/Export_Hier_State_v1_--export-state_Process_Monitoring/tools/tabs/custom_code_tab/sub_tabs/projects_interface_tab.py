"""
Projects Interface Tab - Project-aware chat with RAG toggle
"""

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, simpledialog
from pathlib import Path
import json
import random

from tabs.base_tab import BaseTab
from logger_util import get_tab_logger

log_message, log_error, log_exception = get_tab_logger('custom_code')

from .chat_interface_tab import ChatInterfaceTab
from ..projects_manager import list_projects, list_conversations, ensure_project, save_conversation, delete_project
from config import get_project_todos_dir, get_project_working_dir, THE_SANDBOX_DIR

try:
    from debug_logger import get_logger, get_logger as get_debug_logger, debug_method, debug_ui_event
except ImportError:
    def get_logger(_name: str):
        return None
    def get_debug_logger(_name: str):
        return None
    def debug_method(_logger):
        def decorator(func):
            return func
        return decorator
    def debug_ui_event(_logger):
        def decorator(func):
            return func
        return decorator



class ProjectsInterfaceTab(ChatInterfaceTab):
    """Reuses Chat UI/logic; left tree shows Projects -> conversations; adds RAG toggle and Create Project."""

    # Initialize debug logger with safe fallback - ensure it's always defined
    # Safely initialize to avoid NameError during class definition
    _projects_interface_tab_debug_logger = None
    try:
        # Directly try to call get_debug_logger - it's defined in the except block above if import fails
        # This is more reliable than checking globals()
        _projects_interface_tab_debug_logger = get_debug_logger("projects_interface_tab")
    except (NameError, AttributeError, TypeError, Exception):
        # Keep as None if initialization fails for any reason
        _projects_interface_tab_debug_logger = None

    def __init__(self, parent, root, style, parent_tab):
        super().__init__(parent, root, style, parent_tab)
        self.is_tracker_active = False
        self.current_project = None
        self.rag_enabled = True  # default on per request
        self.auto_project = True # auto-create on first input if none
        try:
            self._projects_vector_default = bool(self.backend_settings.get('rag_vector_enabled_projects', True))
        except Exception:
            self._projects_vector_default = True
        self._bind_training_events()

    @debug_ui_event(_projects_interface_tab_debug_logger)
    def create_ui(self):
        log_message("PROJECTS_TAB: Creating UI...")
        # Reuse Chat layout
        super().create_ui()
        if hasattr(self, '_rag_scope_vector'):
            desired = bool(self.backend_settings.get('rag_vector_enabled_projects', self._projects_vector_default))
            if not self._vector_backend_available:
                desired = False
            self._rag_scope_vector.set(desired)
            self.rag_service.enable_vector_search(desired and self._vector_backend_available)
        # Update left sidebar header
        if hasattr(self, 'conv_sidebar'):
            try:
                for child in self.conv_sidebar.winfo_children():
                    child.destroy()
            except Exception as e:
                log_message(f"PROJECTS_TAB: Error clearing sidebar: {e}")
            self._build_projects_sidebar(self.conv_sidebar)
        else:
            log_message("PROJECTS_TAB: Warning - conv_sidebar not initialized by parent class")

    @debug_ui_event(_projects_interface_tab_debug_logger)
    def _build_projects_sidebar(self, parent):
        parent.columnconfigure(0, weight=1)
        # Make project tree (row 2) and training grounds tree (row 4) resizable
        try:
            parent.rowconfigure(2, weight=1)
            parent.rowconfigure(4, weight=1)
        except Exception:
            pass
        # Active Version Indicator (row 0)
        version_frame = ttk.Frame(parent, style='Category.TFrame')
        version_frame.grid(row=0, column=0, sticky=tk.EW, padx=8, pady=(8,2))
        self.active_version_label = ttk.Label(
            version_frame,
            text='Active: (loading...)',
            foreground='#888888'
        )
        self.active_version_label.pack(side=tk.LEFT, padx=(0,4))
        self._update_active_version_label()

        # Projects header (row 1)
        header = ttk.Frame(parent, style='Category.TFrame')
        header.grid(row=1, column=0, sticky=tk.EW, padx=8, pady=(2,4))
        ttk.Label(header, text='📁 Projects', style='CategoryPanel.TLabel').pack(side=tk.LEFT)
        ttk.Button(header, text='➕ Create', style='Action.TButton', command=self._create_project).pack(side=tk.RIGHT)

        # Tree (row 2)
        tree_wrap = ttk.Frame(parent, style='Category.TFrame')
        tree_wrap.grid(row=2, column=0, sticky=tk.NSEW, padx=8, pady=(0,8))
        tree_wrap.columnconfigure(0, weight=1)
        tree_wrap.rowconfigure(0, weight=1)
        sb = ttk.Scrollbar(tree_wrap, orient='vertical')
        sb.grid(row=0, column=1, sticky=tk.NS)
        self.proj_tree = ttk.Treeview(tree_wrap, yscrollcommand=sb.set, selectmode='browse')
        self.proj_tree.grid(row=0, column=0, sticky=tk.NSEW)
        sb.config(command=self.proj_tree.yview)
        self.proj_tree.heading('#0', text='Projects')
        self.proj_tree.bind('<<TreeviewSelect>>', self._on_proj_selected)
        self.proj_tree.bind('<Double-Button-1>', self._on_proj_open)
        self._refresh_projects_tree()
        # Try to load persisted index for current project
        try:
            if hasattr(self, 'rag_service') and self.rag_service and self.current_project:
                self.rag_service.load_project_index(self.current_project)
        except Exception:
            pass

        # Training Grounds header (row 3)
        tg_hdr = ttk.Frame(parent, style='Category.TFrame')
        tg_hdr.grid(row=3, column=0, sticky=tk.EW, padx=8, pady=(0,4))
        ttk.Label(tg_hdr, text='🎯 Training Grounds', style='CategoryPanel.TLabel').pack(side=tk.LEFT)

        # Training Grounds tree (row 4): Type -> Variant -> Chats
        tg_wrap = ttk.Frame(parent, style='Category.TFrame')
        tg_wrap.grid(row=4, column=0, sticky=tk.NSEW, padx=8, pady=(0,8))
        tg_wrap.columnconfigure(0, weight=1)
        tg_wrap.rowconfigure(0, weight=1)
        tg_sb = ttk.Scrollbar(tg_wrap, orient='vertical')
        tg_sb.grid(row=0, column=1, sticky=tk.NS)
        self.tg_tree = ttk.Treeview(tg_wrap, yscrollcommand=tg_sb.set, selectmode='browse')
        self.tg_tree.grid(row=0, column=0, sticky=tk.NSEW)
        tg_sb.config(command=self.tg_tree.yview)
        self.tg_tree.heading('#0', text='Types / Variants / Chats')
        self.tg_tree.bind('<<TreeviewSelect>>', self._on_tg_selected)
        self.tg_tree.bind('<Double-Button-1>', self._on_tg_open)
        self._refresh_training_grounds_tree()

        # Bottom actions (row 5)
        actions = ttk.Frame(parent, style='Category.TFrame')
        actions.grid(row=5, column=0, sticky=tk.EW, padx=8, pady=(0,4))
        for c in range(2):
            actions.columnconfigure(c, weight=1)
        # Row 0: Chat actions
        ttk.Button(actions, text='Open Chat', style='Action.TButton', command=self._open_selected_chat).grid(row=0, column=0, sticky=tk.EW, padx=(0,4))
        ttk.Button(actions, text='Delete Chat', style='Select.TButton', command=self._delete_selected_chat).grid(row=0, column=1, sticky=tk.EW, padx=(4,0))
        # Row 1: Project actions
        ttk.Button(actions, text='Delete Project', style='Select.TButton', command=self._delete_selected_project).grid(row=1, column=0, sticky=tk.EW, pady=(4,0))
        ttk.Button(actions, text='Rename Project', style='Select.TButton', command=self._rename_selected_project).grid(row=1, column=1, sticky=tk.EW, pady=(4,0))
        # Row 2: Chat rename
        ttk.Button(actions, text='Rename Chat', style='Select.TButton', command=self._rename_selected_chat).grid(row=2, column=0, columnspan=2, sticky=tk.EW, pady=(4,0))

        # Panel-wide RAG controls for projects (row 6) (🧠, 🧠+, 🧠++)
        rag_bar = ttk.Frame(parent, style='Category.TFrame')
        rag_bar.grid(row=6, column=0, sticky=tk.EW, padx=8, pady=(0,4))
        rag_bar.columnconfigure(0, weight=1)
        rag_bar.columnconfigure(1, weight=1)
        rag_bar.columnconfigure(2, weight=1)

        # Read persisted value
        try:
            self.panel_rag_level_projects = int(self.backend_settings.get('panel_rag_level_projects', 0))
        except Exception:
            self.panel_rag_level_projects = 0
        # Mirror to shared attribute used by Chat logic
        self.panel_rag_level = self.panel_rag_level_projects

        def _save_backend_setting(key: str, value):
            try:
                settings_file = Path(__file__).parent.parent / "custom_code_settings.json"
                data = {}
                if settings_file.exists():
                    try:
                        with open(settings_file, 'r') as f:
                            data = json.load(f) or {}
                    except Exception:
                        data = {}
                data[key] = value
                with open(settings_file, 'w') as f:
                    json.dump(data, f, indent=2)
            except Exception:
                pass

        def set_rag_level(level: int):
            cur = int(getattr(self, 'panel_rag_level_projects', 0) or 0)
            new_level = 0 if level == cur else level
            self.panel_rag_level_projects = new_level
            # Mirror for shared logic
            self.panel_rag_level = new_level
            _save_backend_setting('panel_rag_level_projects', new_level)
            _update_rag_buttons()
            try:
                self._update_quick_indicators()
            except Exception:
                pass

        def _btn_style(active: bool) -> str:
            return 'Action.TButton' if active else 'Select.TButton'

        self._proj_rag_btn_lvl1 = ttk.Button(rag_bar, text='🧠', style=_btn_style(False), command=lambda: set_rag_level(1))
        self._proj_rag_btn_lvl2 = ttk.Button(rag_bar, text='🧠+', style=_btn_style(False), command=lambda: set_rag_level(2))
        self._proj_rag_btn_lvl3 = ttk.Button(rag_bar, text='🧠++', style=_btn_style(False), command=lambda: set_rag_level(3))
        self._proj_rag_btn_lvl1.grid(row=0, column=0, sticky=tk.EW, padx=(0,4))
        self._proj_rag_btn_lvl2.grid(row=0, column=1, sticky=tk.EW, padx=4)
        self._proj_rag_btn_lvl3.grid(row=0, column=2, sticky=tk.EW, padx=(4,0))

        # Hint label for hover
        self._proj_rag_hint_label = ttk.Label(parent, text='', style='Config.TLabel')
        self._proj_rag_hint_label.grid(row=7, column=0, sticky=tk.W, padx=12, pady=(0,6))

        def _set_phint(text:str=''):
            try:
                self._proj_rag_hint_label.config(text=text)
            except Exception:
                pass

        def _update_rag_buttons():
            lvl = int(getattr(self, 'panel_rag_level_projects', 0) or 0)
            try:
                self._proj_rag_btn_lvl1.configure(style=_btn_style(lvl >= 1))
                self._proj_rag_btn_lvl2.configure(style=_btn_style(lvl >= 2))
                self._proj_rag_btn_lvl3.configure(style=_btn_style(lvl >= 3))
            except Exception:
                pass

        _update_rag_buttons()
        # Hover descriptions
        try:
            self._proj_rag_btn_lvl1.bind('<Enter>', lambda e: _set_phint('L1: Conservative retrieval (≈2 snippets, ~1200 chars). Click again to turn OFF.'))
            self._proj_rag_btn_lvl2.bind('<Enter>', lambda e: _set_phint('L2: Balanced retrieval (≈4 snippets, ~2400 chars).'))
            self._proj_rag_btn_lvl3.bind('<Enter>', lambda e: _set_phint('L3: Max retrieval (≈6 snippets, ~3600 chars).'))
            for b in (self._proj_rag_btn_lvl1, self._proj_rag_btn_lvl2, self._proj_rag_btn_lvl3):
                b.bind('<Leave>', lambda e: _set_phint(''))
        except Exception:
            pass

        # Vector toggle for projects
        vector_row = ttk.Frame(parent, style='Category.TFrame')
        vector_row.grid(row=6, column=0, sticky=tk.EW, padx=8, pady=(0,6))
        self._proj_rag_vector_var = tk.BooleanVar(
            value=self.backend_settings.get('rag_vector_enabled_projects', self._projects_vector_default)
        )

        @debug_ui_event(ProjectsInterfaceTab._projects_interface_tab_debug_logger)
        def _toggle_vector():
            val = bool(self._proj_rag_vector_var.get()) and self._vector_backend_available
            self._proj_rag_vector_var.set(val)
            _save_backend_setting('rag_vector_enabled_projects', val)
            if hasattr(self, '_rag_scope_vector'):
                self._rag_scope_vector.set(val)
            self.rag_service.enable_vector_search(val and self._vector_backend_available)
            try:
                self._update_quick_indicators()
            except Exception:
                pass

        ttk.Checkbutton(
            vector_row,
            text='Vector search',
            variable=self._proj_rag_vector_var,
            command=_toggle_vector,
            style='TCheckbutton'
        ).pack(side=tk.LEFT)
        if not self._vector_backend_available:
            try:
                self._proj_rag_vector_var.set(False)
                for child in vector_row.winfo_children():
                    child.configure(state=tk.DISABLED)
            except Exception:
                pass

    @debug_ui_event(_projects_interface_tab_debug_logger)
    def _refresh_training_grounds_tree(self):
        try:
            # Clear
            for it in self.tg_tree.get_children():
                self.tg_tree.delete(it)
            # Group variants by assigned_type
            import config as C
            items = C.list_model_profiles() or []
            grouped = {}
            for it in items:
                t = (it.get('assigned_type') or 'uncategorized')
                vid = it.get('variant_id') or ''
                if not vid:
                    continue
                grouped.setdefault(t, []).append(vid)
            # Build
            for t in sorted(grouped.keys()):
                t_id = self.tg_tree.insert('', 'end', text=t.title(), values=(f"type::{t}",), open=False)
                for vid in sorted(grouped[t]):
                    v_id = self.tg_tree.insert(t_id, 'end', text=vid, values=(f"variant::{vid}",), open=False)
                    # Saved chats for this variant via ChatHistoryManager
                    try:
                        chats = self.chat_history_manager.list_conversations(model_name=vid) if hasattr(self, 'chat_history_manager') else []
                    except Exception:
                        chats = []
                    for rec in chats:
                        sid = rec.get('session_id')
                        if not sid:
                            continue
                        label = f"{sid}  ({rec.get('message_count',0)} msgs)"
                        self.tg_tree.insert(v_id, 'end', text=label, values=(f"chat::{vid}::{sid}",), open=False)
        except Exception as e:
            log_message(f"PROJECTS_TAB: Training Grounds refresh error: {e}")

    def _on_tg_selected(self, _e=None):
        # No-op (double-click opens variant/chat)
        pass

    @debug_ui_event(_projects_interface_tab_debug_logger)
    def _on_tg_open(self, _e=None):
        try:
            sel = self.tg_tree.selection()
            if not sel:
                return
            node = sel[0]
            vals = self.tg_tree.item(node, 'values')
            if not vals:
                return
            meta = vals[0]
            if meta.startswith('variant::'):
                vid = meta.split('::', 1)[1]
                model_data = {'model_name': vid, 'is_local_gguf': False}
                self.select_model(model_data)
                try:
                    self.add_message('system', f"Variant selected: {vid}")
                except Exception:
                    pass
            elif meta.startswith('chat::'):
                _, vid, sid = meta.split('::', 2)
                rec = self.chat_history_manager.load_conversation(sid) if hasattr(self, 'chat_history_manager') else None
                if not rec:
                    messagebox.showinfo('Chat Missing', f'Chat session {sid} not found.')
                    return
                self.chat_history = rec.get('chat_history', [])
                self.redisplay_conversation()
                try:
                    self.add_message('system', f"Opened saved chat: {sid}")
                except Exception:
                    pass
        except Exception as e:
            log_message(f"PROJECTS_TAB: Training Grounds open error: {e}")

    # Projects tree helpers
    @debug_ui_event(_projects_interface_tab_debug_logger)
    def _refresh_projects_tree(self):
        try:
            for it in self.proj_tree.get_children():
                self.proj_tree.delete(it)
            projects = list_projects()
            log_message(f"PROJECTS_TAB: Found {len(projects)} projects")
            for pname in projects:
                pnode = self.proj_tree.insert('', 'end', text=pname, values=('project', pname), open=(pname==self.current_project))
                recs = list_conversations(pname)
                log_message(f"PROJECTS_TAB: {pname} has {len(recs)} conversations")
                for rec in recs:
                    self.proj_tree.insert(pnode, 'end', text=f"{rec.get('saved_at','')[5:16]}  {rec.get('session_id','')}", values=('session', pname, rec.get('session_id','')))
            if getattr(self, 'rag_enabled', False) and getattr(self, 'qa_indicators', None) and getattr(self, 'parent', None):
                pass
        except Exception as e:
            log_message(f"PROJECTS_TAB ERROR: Failed to refresh projects tree: {e}")

    # -- Training mode / support sync -----------------------------------

    def _bind_training_events(self):
        try:
            self.root.bind("<<TrainingModeChanged>>", self._on_training_mode_event, add="+")
        except Exception:
            pass
        try:
            self.root.bind("<<TrainingSupportChanged>>", self._on_training_support_event, add="+")
        except Exception:
            pass

    def _on_training_mode_event(self, event=None):
        try:
            payload = getattr(event, 'data', None)
            data = json.loads(payload) if payload else {}
        except Exception:
            data = {}
        if 'enabled' not in data and 'value' not in data:
            return
        enabled = bool(data.get('enabled', data.get('value', False)))
        previous = bool(getattr(self, 'training_mode_enabled', False))
        self.training_mode_enabled = enabled
        try:
            self.backend_settings['training_mode_enabled'] = enabled
        except Exception:
            pass
        if enabled != previous:
            try:
                self._qa_update_training_btn()
            except Exception:
                pass
            try:
                self._update_quick_indicators()
            except Exception:
                pass

    def _on_training_support_event(self, event=None):
        try:
            payload = getattr(event, 'data', None)
            data = json.loads(payload) if payload else {}
        except Exception:
            data = {}
        if 'enabled' not in data and 'value' not in data:
            return
        enabled = bool(data.get('enabled', data.get('value', False)))
        try:
            self.backend_settings['training_support_enabled'] = enabled
        except Exception:
            pass
        try:
            self._update_quick_indicators()
        except Exception:
            pass

    def _create_project(self):
        name = simpledialog.askstring('Create Project', 'Enter project name:')
        if not name:
            return
        ensure_project(name)
        # Create project todos directory
        try:
            get_project_todos_dir(name)
            log_message(f"PROJECTS_TAB: Created todos directory for project '{name}'")
        except Exception as e:
            log_message(f"PROJECTS_TAB: Error creating todos dir for '{name}': {e}")
        # Set Settings tab context to this project
        try:
            if hasattr(self.parent_tab, 'settings_interface') and self.parent_tab.settings_interface:
                self.parent_tab.settings_interface.current_project_context = name
        except Exception:
            pass
        # Set working directory to project's working_dir
        try:
            working_dir = get_project_working_dir(name)
            if hasattr(self, 'tool_executor') and self.tool_executor:
                self.tool_executor.set_working_directory(str(working_dir))
                log_message(f"PROJECTS_TAB: Set working directory to {working_dir}")
                self.add_message("system", f"📂 Working directory set to: {working_dir}")
        except Exception as e:
            log_message(f"PROJECTS_TAB: Error setting working dir for '{name}': {e}")
        self.current_project = name
        self._refresh_projects_tree()
        messagebox.showinfo('Project Created', f"Project '{name}' created and selected.")

    def _on_proj_selected(self, event=None):
        sel = self.proj_tree.selection()
        if not sel:
            return
        vals = self.proj_tree.item(sel[0], 'values')
        if not vals:
            return
        if vals[0] == 'project':
            self.current_project = vals[1]
            # Refresh project RAG index
            try:
                if hasattr(self, 'rag_service') and self.rag_service:
                    self.rag_service.refresh_index_project(self.current_project)
            except Exception:
                pass
            # Update Settings tab context to selected project
            try:
                if hasattr(self.parent_tab, 'settings_interface') and self.parent_tab.settings_interface:
                    self.parent_tab.settings_interface.current_project_context = self.current_project
            except Exception:
                pass
            # Auto-switch working directory to selected project's working_dir
            try:
                working_dir = get_project_working_dir(self.current_project)
                if hasattr(self, 'tool_executor') and self.tool_executor:
                    self.tool_executor.set_working_directory(str(working_dir))
                    log_message(f"PROJECTS_TAB: Switched working directory to {working_dir}")
            except Exception as e:
                log_message(f"PROJECTS_TAB: Error switching working dir: {e}")
            # Apply project-level agents default if defined
            try:
                cfg = Path('Data')/'projects'/self.current_project/'agents_default.json'
                if cfg.exists() and hasattr(self.root, 'set_active_agents') and callable(getattr(self.root, 'set_active_agents')):
                    roster = json.loads(cfg.read_text())
                    if isinstance(roster, list) and roster:
                        self.root.set_active_agents(roster)
            except Exception:
                pass
            # Show quick view popup for the selected project
            try:
                self._show_project_quick_view(self.current_project)
            except Exception:
                pass
        elif vals[0] == 'session':
            self.current_project = vals[1]

    @debug_ui_event(_projects_interface_tab_debug_logger)
    def _on_proj_open(self, event=None):
        sel = self.proj_tree.selection()
        if not sel:
            return
        vals = self.proj_tree.item(sel[0], 'values')
        if not vals or vals[0] != 'session':
            return
        _, project, sid = vals
        # Load project chat (reuse Chat loader mechanics)
        rec = list_conversations(project)
        # Directly call Chat loader by constructing id
        try:
            data = json.loads((Path('Data/projects')/project/f"{sid}.json").read_text())
        except Exception:
            return
        self.chat_history = data.get('chat_history') or []
        self.current_model = data.get('model_name')
        self.current_session_id = sid
        self.model_label.config(text=self.current_model or 'No model selected')
        self.redisplay_conversation()
        self.add_message('system', f"✓ Loaded project chat: {sid}")

    # Helper to open a specific project session id
    @debug_ui_event(_projects_interface_tab_debug_logger)
    def _open_project_session(self, project: str, session_id: str):
        try:
            p = Path('Data/projects')/project/f"{session_id}.json"
            if not p.exists():
                messagebox.showinfo('Missing', f'Chat not found: {session_id}')
                return
            data = json.loads(p.read_text())
            self.chat_history = data.get('chat_history') or []
            self.current_model = data.get('model_name')
            self.current_session_id = session_id
            self.model_label.config(text=self.current_model or 'No model selected')
            self.redisplay_conversation()
            self.add_message('system', f"✓ Loaded project chat: {session_id}")
        except Exception as e:
            log_message(f"PROJECTS_TAB: Open session error: {e}")

    # Quick view popup for a project: counts, per-model links/active/deactivated, and config summary
    @debug_ui_event(_projects_interface_tab_debug_logger)
    def _show_project_quick_view(self, project: str):
        try:
            recs = list_conversations(project)
        except Exception:
            recs = []
        win = tk.Toplevel(self.root)
        win.title(f"Project Quick View — {project}")
        f = ttk.Frame(win)
        f.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        ttk.Label(f, text=f"📁 {project}", font=("Arial", 12, "bold"), style='CategoryPanel.TLabel').grid(row=0, column=0, sticky=tk.W)
        ttk.Label(f, text=f"Chats: {len(recs)}", style='Config.TLabel').grid(row=1, column=0, sticky=tk.W, pady=(2,6))

        # Scrollable area
        canvas = tk.Canvas(f, bg="#2b2b2b", highlightthickness=0)
        sb = ttk.Scrollbar(f, orient='vertical', command=canvas.yview)
        body = ttk.Frame(canvas)
        body.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.create_window((0,0), window=body, anchor='nw')
        canvas.configure(yscrollcommand=sb.set)
        canvas.grid(row=2, column=0, sticky=tk.NSEW)
        sb.grid(row=2, column=1, sticky=tk.NS)
        f.rowconfigure(2, weight=1); f.columnconfigure(0, weight=1)

        # Group by model
        by_model = {}
        for r in recs:
            m = r.get('model_name') or 'unknown'
            by_model.setdefault(m, []).append(r)

        # Memory loader per variant
        def _load_mem(variant: str) -> set:
            try:
                p = Path('Data')/'projects'/variant/'memory.json'
                if p.exists():
                    j = json.loads(p.read_text())
                    return set(j.get('active_sessions', []))
            except Exception:
                pass
            return set()

        rowi = 0
        for model, lst in sorted(by_model.items()):
            variant_id = Path(model).name
            active_set = _load_mem(variant_id)
            total = len(lst); active = sum(1 for s in lst if s.get('session_id') in active_set); deact = total - active
            hdr = ttk.Frame(body); hdr.grid(row=rowi, column=0, sticky=tk.EW, pady=(6,2)); rowi += 1
            ttk.Label(hdr, text=f"{variant_id}: {total} Links | Active: {active} | Deactivated: {deact}", style='Config.TLabel').pack(side=tk.LEFT)
            # List chats under this model
            for rec in lst:
                sid = rec.get('session_id'); mc = rec.get('message_count', 0)
                row = ttk.Frame(body); row.grid(row=rowi, column=0, sticky=tk.EW)
                rowi += 1
                ttk.Label(row, text=f"• {sid}  ({mc} msgs)", style='Config.TLabel').pack(side=tk.LEFT)
                ttk.Button(row, text='Open', style='Select.TButton', command=lambda s=sid: self._open_project_session(project, s)).pack(side=tk.RIGHT)

        # Config summary (similar to Chat popup quick indicators)
        cfg = ttk.LabelFrame(f, text='Summary', style='TLabelframe')
        cfg.grid(row=3, column=0, sticky=tk.EW, pady=(8,0))
        try:
            wd = ''
            if hasattr(self, 'tool_executor') and self.tool_executor:
                wd = self.tool_executor.get_working_directory() or ''
            rag_count = self._get_project_rag_connected_chat_count()
            ttk.Label(cfg, text=f"Working Dir: {wd or '(not set)'}", style='Config.TLabel').pack(anchor=tk.W, padx=8, pady=2)
            ttk.Label(cfg, text=f"RAG-linked chats: {rag_count}", style='Config.TLabel').pack(anchor=tk.W, padx=8, pady=2)

            # Additional project signals: ToDos, Knowledge Bank, Tool Calls, Variants
            try:
                todos_dir = get_project_todos_dir(project)
            except Exception:
                todos_dir = None
            todo_count = 0
            if todos_dir and Path(todos_dir).exists():
                p = Path(todos_dir)
                todo_count = len([x for x in p.glob('**/*') if x.is_file() and x.suffix.lower() in ('.json', '.md', '.txt')])
            ttk.Label(cfg, text=f"ToDos: {todo_count}", style='Config.TLabel').pack(anchor=tk.W, padx=8, pady=2)

            kb_dir = Path('Data')/'projects'/project/'rag_index'
            kb_present = kb_dir.exists()
            kb_items = 0
            if kb_present:
                try:
                    kb_items = len([x for x in kb_dir.glob('**/*') if x.is_file()])
                except Exception:
                    kb_items = 0
            ttk.Label(cfg, text=f"Knowledge Bank: {'present' if kb_present else 'missing'} ({kb_items} files)", style='Config.TLabel').pack(anchor=tk.W, padx=8, pady=2)

            tc_dir = Path('Data')/'projects'/project/'tool_calls'
            tc_count = 0
            if tc_dir.exists():
                try:
                    tc_count = len([x for x in tc_dir.glob('**/*.jsonl')])
                    if tc_count == 0:
                        tc_count = len([x for x in tc_dir.glob('**/*.json')])
                except Exception:
                    tc_count = 0
            ttk.Label(cfg, text=f"Tool Calls: {tc_count}", style='Config.TLabel').pack(anchor=tk.W, padx=8, pady=2)

            variants = sorted({(r.get('model_name') or 'unknown') for r in recs})
            ttk.Label(cfg, text=f"Variants used: {len(variants)}", style='Config.TLabel').pack(anchor=tk.W, padx=8, pady=2)

            # Open buttons row for common folders
            opens = ttk.Frame(cfg)
            opens.pack(anchor=tk.W, padx=6, pady=(4,6))
            ttk.Button(opens, text='Open Working Dir', style='Select.TButton',
                       command=lambda p=wd: self._open_path(p)).pack(side=tk.LEFT, padx=4)
            if todos_dir:
                ttk.Button(opens, text='Open ToDos', style='Select.TButton',
                           command=lambda p=str(todos_dir): self._open_path(p)).pack(side=tk.LEFT, padx=4)
            ttk.Button(opens, text='Open KB', style='Select.TButton',
                       command=lambda p=str(kb_dir): self._open_path(p)).pack(side=tk.LEFT, padx=4)
            ttk.Button(opens, text='Open Tool Calls', style='Select.TButton',
                       command=lambda p=str(tc_dir): self._open_path(p)).pack(side=tk.LEFT, padx=4)
        except Exception:
            pass
        btns = ttk.Frame(f); btns.grid(row=4, column=0, sticky=tk.EW, pady=(8,0))
        # Left: save project agents default
        try:
            @debug_ui_event(ProjectsInterfaceTab._projects_interface_tab_debug_logger)
            def _save_agents_default():
                roster = []
                try:
                    if hasattr(self.root, 'get_active_agents') and callable(getattr(self.root, 'get_active_agents')):
                        roster = self.root.get_active_agents() or []
                except Exception:
                    roster = []
                p = Path('Data')/'projects'/project
                p.mkdir(parents=True, exist_ok=True)
                (p/'agents_default.json').write_text(json.dumps(roster, indent=2))
                try:
                    messagebox.showinfo('Saved', 'Saved current agents as project default.')
                except Exception:
                    pass
            left = ttk.Frame(btns); left.pack(side=tk.LEFT)
            ttk.Button(left, text='Save Agents Default', style='Select.TButton', command=_save_agents_default).pack(side=tk.LEFT)
        except Exception:
            pass
        # Right: close
        ttk.Button(btns, text='Close', command=win.destroy, style='Select.TButton').pack(side=tk.RIGHT)

    @debug_ui_event(_projects_interface_tab_debug_logger)
    def _open_path(self, path):
        try:
            if not path:
                return
            p = Path(path)
            if not p.exists():
                from tkinter import messagebox
                messagebox.showinfo('Open', f'Path not found:\n{p}')
                return
            import os, sys, subprocess
            if sys.platform.startswith('win'):
                os.startfile(str(p))  # noqa: P204
            elif sys.platform == 'darwin':
                subprocess.Popen(['open', str(p)])
            else:
                subprocess.Popen(['xdg-open', str(p)])
        except Exception as e:
            log_message(f"PROJECTS_TAB: Open path error: {e}")

    @debug_ui_event(_projects_interface_tab_debug_logger)
    def _open_selected_chat(self):
        self._on_proj_open()

    def _delete_selected_chat(self):
        sel = self.proj_tree.selection()
        if not sel:
            return
        vals = self.proj_tree.item(sel[0], 'values')
        if not vals or vals[0] != 'session':
            return
        _, project, sid = vals
        if not messagebox.askyesno('Confirm Delete', f"Delete conversation from project '{project}'?\n\n{sid}"):
            return
        p = Path('Data/projects')/project/f"{sid}.json"
        if p.exists():
            p.unlink()
            self._refresh_projects_tree()

    def _delete_selected_project(self):
        try:
            sel = self.proj_tree.selection()
            if not sel:
                messagebox.showinfo('Delete Project', 'Select a project to delete.')
                return
            vals = self.proj_tree.item(sel[0], 'values')
            if not vals:
                messagebox.showinfo('Delete Project', 'Select a project to delete.')
                return
            # If a session is selected, use its parent project
            if vals[0] == 'session':
                project = vals[1]
            else:
                project = vals[1]
            if not messagebox.askyesno('Confirm Delete', f"Delete entire project '{project}' and all its data? This cannot be undone."):
                return
            ok = delete_project(project)
            if not ok:
                messagebox.showerror('Delete Project', 'Failed to delete project.')
                return
            # Reset working directory if we deleted the current project
            if getattr(self, 'current_project', None) == project:
                self.current_project = None
                try:
                    if hasattr(self, 'tool_executor') and self.tool_executor:
                        self.tool_executor.set_working_directory(str(THE_SANDBOX_DIR))
                        self.add_message('system', f"📂 Working directory set to: {THE_SANDBOX_DIR}")
                except Exception:
                    pass
            self._refresh_projects_tree()
            messagebox.showinfo('Project Deleted', f"Project '{project}' has been deleted.")
        except Exception as e:
            log_message(f"PROJECTS_TAB: Error deleting project: {e}")
            try:
                messagebox.showerror('Delete Project', f'Error deleting project: {e}')
            except Exception:
                pass

    def _rename_selected_chat(self):
        try:
            from tkinter import simpledialog, messagebox
            sel = self.proj_tree.selection()
            if not sel:
                messagebox.showinfo('Rename Chat', 'Select a conversation to rename.')
                return
            vals = self.proj_tree.item(sel[0], 'values')
            if not vals or vals[0] != 'session':
                messagebox.showinfo('Rename Chat', 'Select a conversation (not a project) to rename.')
                return
            _, project, sid = vals
            new_name = simpledialog.askstring('Rename Chat', f"Rename '{sid}' in project '{project}' to:")
            if not new_name or new_name.strip() == sid:
                return
            root = Path('Data/projects')/project
            src = root / f"{sid}.json"
            dst = root / f"{new_name.strip()}.json"
            if not src.exists():
                messagebox.showerror('Rename Chat', 'Original session file not found.')
                return
            if dst.exists():
                messagebox.showerror('Rename Chat', 'A chat with that name already exists.')
                return
            # Update inside JSON
            try:
                data = json.loads(src.read_text())
                data['session_id'] = new_name.strip()
                dst.write_text(json.dumps(data, indent=2))
                src.unlink()
            except Exception as e:
                messagebox.showerror('Rename Chat', f'Failed to rename chat file: {e}')
                return
            if getattr(self, 'current_session_id', None) == sid:
                self.current_session_id = new_name.strip()
            self._refresh_projects_tree()
            self.add_message('system', f"✓ Renamed project chat to: {new_name.strip()}")
        except Exception:
            pass

    def _rename_selected_project(self):
        from tkinter import simpledialog, messagebox
        sel = self.proj_tree.selection()
        if not sel:
            return
        vals = self.proj_tree.item(sel[0], 'values')
        if not vals or vals[0] != 'project':
            messagebox.showinfo('Rename Project', 'Select a project to rename.')
            return
        old = vals[1]
        new = simpledialog.askstring('Rename Project', f"Rename project '{old}' to:")
        if not new or new == old:
            return
        try:
            from ..projects_manager import ensure_project, safe_name
            op = Path('Data/projects')/safe_name(old)
            np = Path('Data/projects')/safe_name(new)
            if np.exists():
                messagebox.showerror('Exists', 'A project with that name already exists.')
                return
            op.rename(np)
            self.current_project = new
            self._refresh_projects_tree()
        except Exception as e:
            messagebox.showerror('Rename Error', f'Failed to rename project: {e}')

    # Override autosave to store in project if selected
    def _auto_save_conversation(self):
        if not self.chat_history:
            return
        # Attach UID context (variant/lineage) so downstream link‑ups are reliable
        # Try to use the global model context bundle first
        variant_id = None
        lineage_id = None
        try:
            from model_context_bundle import get_context
            bundle = get_context().get_bundle()
            if bundle:
                variant_id = bundle.get('variant_id')
                lineage_id = bundle.get('lineage_id')
                print(f"[ProjectsInterface] Using global bundle: variant_id={variant_id}, lineage_id={lineage_id}")
        except Exception as e:
            print(f"[ProjectsInterface] No global bundle available, resolving from model: {e}")

        # Fallback: resolve from self.current_model if no bundle available
        if not variant_id:
            try:
                import config as C
                model_str = str(self.current_model or '')
                if model_str.endswith('.gguf'):
                    try:
                        m = C.list_assigned_local_by_variant() or {}
                        for vid, ggufs in m.items():
                            if model_str in (ggufs or []):
                                variant_id = vid; break
                    except Exception:
                        pass
                    if not variant_id:
                        from pathlib import Path as _P
                        variant_id = _P(model_str).stem
                else:
                    variant_id = model_str
                if variant_id:
                    try:
                        lineage_id = C.get_lineage_id(variant_id)
                    except Exception:
                        lineage_id = None
                print(f"[ProjectsInterface] Resolved from model: variant_id={variant_id}, lineage_id={lineage_id}")
            except Exception as e:
                print(f"[ProjectsInterface] Error resolving variant_id: {e}")

        meta = {
            "mode": getattr(self, 'current_mode', 'smart'),
            "temperature": self.session_temperature,
            "temp_mode": getattr(self, 'temp_mode', 'manual'),
            "system_prompt": getattr(self, 'current_system_prompt', 'default'),
            "tool_schema": getattr(self, 'current_tool_schema', 'default'),
            "rag_enabled": bool(self.rag_enabled),
            "variant_id": variant_id,
            "lineage_id": lineage_id,
        }
        if not self.current_project and self.auto_project:
            self.current_project = f"Project_{Path.cwd().name}_{random.randint(100,999)}"
            ensure_project(self.current_project)
            # Create project todos directory on auto-creation
            try:
                get_project_todos_dir(self.current_project)
                log_message(f"PROJECTS_TAB: Created todos directory for auto-created project '{self.current_project}'")
            except Exception as e:
                log_message(f"PROJECTS_TAB: Error creating todos dir for '{self.current_project}': {e}")
            # Ensure/set working directory for auto-created project
            try:
                working_dir = get_project_working_dir(self.current_project)
                if hasattr(self, 'tool_executor') and self.tool_executor:
                    self.tool_executor.set_working_directory(str(working_dir))
                    log_message(f"PROJECTS_TAB: Set working directory to {working_dir}")
                    self.add_message("system", f"📂 Working directory set to: {working_dir}")
            except Exception as e:
                log_message(f"PROJECTS_TAB: Error setting working dir for '{self.current_project}': {e}")
        if self.current_project:
            sid = save_conversation(self.current_project, self.current_model or 'unknown', self.chat_history, meta, self.current_session_id)
            self.current_session_id = sid
            self._refresh_projects_tree()
            log_message(f"PROJECTS_TAB: Auto-saved to project '{self.current_project}' as {sid}")
            # Update project RAG index
            try:
                if hasattr(self, 'rag_service') and self.rag_service:
                    self.rag_service.refresh_index_project(self.current_project)
            except Exception:
                pass
        else:
            super()._auto_save_conversation()

    # Quick Actions additions: RAG toggle and Create Project
    def _qa_show_main(self):
        super()._qa_show_main()
        # Append RAG and Create Project if body is available
        try:
            if hasattr(self, '_qa_body') and self._qa_body.winfo_exists():
                row = ttk.Frame(self._qa_body)
                row.pack(pady=4)
                def mk(text, desc, cmd):
                    b = ttk.Button(row, text=text, width=6, style='Action.TButton', command=cmd)
                    b.pack(side=tk.LEFT, padx=6)
                    b.bind('<Enter>', lambda e, t=desc: self._qa_desc.config(text=t))
                    b.bind('<Leave>', lambda e: self._qa_desc.config(text=''))
                    return b
                def _toggle_rag():
                    self.rag_enabled = not bool(self.rag_enabled)
                    try:
                        if getattr(self, 'chat_history', None):
                            self._auto_save_conversation()
                    except Exception:
                        pass
                    self._update_quick_indicators()
                def _open_project_todos():
                    if not self.current_project:
                        messagebox.showinfo('No Project Selected', 'Please select or create a project first.')
                        return
                    # Open the project-specific todo manager directly
                    try:
                        if hasattr(self.parent_tab, 'settings_interface') and self.parent_tab.settings_interface:
                            self.parent_tab.settings_interface.show_project_todo_popup(self.current_project)
                    except Exception as e:
                        log_message(f"PROJECTS_TAB: Error opening project todos: {e}")
                        messagebox.showerror('Error', f'Failed to open project todo list:\n{e}')
                mk('🧠', 'Toggle RAG per project/chat', _toggle_rag)
                mk('🗂', 'Create Project', self._create_project)
                mk('📝', 'Project Todo List', _open_project_todos)
                # Agent Events toggle parity with Chat
                @debug_ui_event(ProjectsInterfaceTab._projects_interface_tab_debug_logger)
                def _toggle_agent_events():
                    self.agent_events_logging_enabled = not bool(getattr(self, 'agent_events_logging_enabled', True))
                    try:
                        self._update_quick_indicators()
                    except Exception:
                        pass
                mk('🗒️', 'Toggle Agent Events in main log', _toggle_agent_events)
        except Exception:
            pass

    # Add indicator for RAG and current project
    @debug_ui_event(_projects_interface_tab_debug_logger)
    def _update_quick_indicators(self):
        # Suppress base RAG indicator to avoid duplicates while parent rebuilds
        try:
            self._suppress_base_rag_indicator = True
            self._suppress_base_workdir_indicator = True
        except Exception:
            pass
        super()._update_quick_indicators()
        try:
            self._suppress_base_rag_indicator = False
            self._suppress_base_workdir_indicator = False
        except Exception:
            pass
        # Only append our project indicators once per parent rebuild cycle
        parent_key = getattr(self, '_qa_state_key', None)
        if getattr(self, '_proj_parent_key_done', None) == parent_key:
            return
        self._proj_parent_key_done = parent_key
        # Append project-specific indicators
        try:
            # Show rag indicator if per-chat rag or panel-level rag is active
            lvl = int(getattr(self, 'panel_rag_level_projects', 0) or (1 if self.rag_enabled else 0))
            rag_active = bool(self.rag_enabled) or lvl > 0
            if rag_active and hasattr(self, 'qa_indicators'):
                try:
                    c = self._get_project_rag_connected_chat_count()
                except Exception:
                    c = 0
                self._make_indicator(self.qa_indicators, '🧠', lambda count=c, l=lvl: f"RAG: ON (L{l}) — Project chats: {count}")
            if self.current_project:
                self._make_indicator(self.qa_indicators, '🗂', lambda: f"Project: {self.current_project}")
            # Show single working directory indicator (short name) to avoid duplicate
            if hasattr(self, 'tool_executor') and self.tool_executor:
                try:
                    wd = self.tool_executor.get_working_directory()
                    if wd:
                        wd_short = Path(wd).name
                        self._make_indicator(self.qa_indicators, '📂', lambda d=wd_short: f"Working Dir: {d}")
                except Exception:
                    pass
        except Exception:
            pass

    def _get_project_rag_connected_chat_count(self) -> int:
        """Count rag-enabled conversations within the current project."""
        try:
            if not self.current_project:
                return 0
            convs = list_conversations(self.current_project)
            count = 0
            for rec in convs:
                meta = rec.get('metadata') or {}
                if bool(meta.get('rag_enabled', False)):
                    count += 1
            # If current unsaved session is RAG-enabled, include it
            try:
                cur_id = getattr(self, 'current_session_id', None)
                is_counted = False
                if cur_id:
                    for rec in convs:
                        if rec.get('session_id') == cur_id:
                            is_counted = bool((rec.get('metadata') or {}).get('rag_enabled', False))
                            break
                if getattr(self, 'rag_enabled', False) and not is_counted:
                    count += 1
            except Exception:
                pass
            return count
        except Exception:
            return 0

    # Override to use project-scoped retrieval in Chat's RAG
    def _rag_query_scope(self) -> str | None:
        try:
            return self.current_project or None
        except Exception:
            return None

    def _update_active_version_label(self):
        """Update active version indicator label"""
        try:
            # Import version_manager
            import sys
            from pathlib import Path
            launcher_path = Path(__file__).resolve().parent.parent.parent.parent.parent / "launcher"
            if str(launcher_path) not in sys.path:
                sys.path.insert(0, str(launcher_path))

            from version_manager import get_version_manager

            vm = get_version_manager()
            active = vm.get_active_version()

            if active:
                label_text = f"Active: {active.display_name or active.version_id}"
                color = '#00cc66'  # Green
            else:
                label_text = "Active: (not detected)"
                color = '#ffcc66'  # Yellow

            if hasattr(self, 'active_version_label'):
                self.active_version_label.config(text=label_text, foreground=color)
        except Exception as e:
            # Silently fail if version manager not available
            if hasattr(self, 'active_version_label'):
                self.active_version_label.config(
                    text="Active: (unavailable)",
                    foreground='#888888'
                )
