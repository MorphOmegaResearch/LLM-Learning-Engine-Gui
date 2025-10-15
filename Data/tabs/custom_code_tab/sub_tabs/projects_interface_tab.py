"""
Projects Interface Tab - Project-aware chat with RAG toggle
"""

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, simpledialog
from pathlib import Path
import json
import random

from tabs.base_tab import BaseTab
from logger_util import log_message

from .chat_interface_tab import ChatInterfaceTab
from ..projects_manager import list_projects, list_conversations, ensure_project, save_conversation


class ProjectsInterfaceTab(ChatInterfaceTab):
    """Reuses Chat UI/logic; left tree shows Projects -> conversations; adds RAG toggle and Create Project."""

    def __init__(self, parent, root, style, parent_tab):
        super().__init__(parent, root, style, parent_tab)
        self.current_project = None
        self.rag_enabled = True  # default on per request
        self.auto_project = True # auto-create on first input if none

    def create_ui(self):
        log_message("PROJECTS_TAB: Creating UI...")
        # Reuse Chat layout
        super().create_ui()
        # Update left sidebar header
        try:
            for child in self.conv_sidebar.winfo_children():
                child.destroy()
        except Exception:
            pass
        self._build_projects_sidebar(self.conv_sidebar)

    def _build_projects_sidebar(self, parent):
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(2, weight=1)
        header = ttk.Frame(parent, style='Category.TFrame')
        header.grid(row=0, column=0, sticky=tk.EW, padx=8, pady=(8,4))
        ttk.Label(header, text='📁 Projects', style='CategoryPanel.TLabel').pack(side=tk.LEFT)
        ttk.Button(header, text='➕ Create', style='Action.TButton', command=self._create_project).pack(side=tk.RIGHT)

        # Tree
        tree_wrap = ttk.Frame(parent, style='Category.TFrame')
        tree_wrap.grid(row=1, column=0, sticky=tk.NSEW, padx=8, pady=(0,8))
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
        # Schedule delayed refresh to avoid startup race conditions
        try:
            self.root.after_idle(self._refresh_projects_tree)
            self.root.after(400, self._refresh_projects_tree)
        except Exception:
            pass
        # Try to load persisted index for current project
        try:
            if hasattr(self, 'rag_service') and self.rag_service and self.current_project:
                self.rag_service.load_project_index(self.current_project)
        except Exception:
            pass

        # Bottom actions
        actions = ttk.Frame(parent, style='Category.TFrame')
        actions.grid(row=2, column=0, sticky=tk.EW, padx=8, pady=(0,4))
        actions.columnconfigure(0, weight=1)
        actions.columnconfigure(1, weight=1)
        ttk.Button(actions, text='Open Chat', style='Action.TButton', command=self._open_selected_chat).grid(row=0, column=0, sticky=tk.EW, padx=(0,4))
        ttk.Button(actions, text='Delete Chat', style='Select.TButton', command=self._delete_selected_chat).grid(row=0, column=1, sticky=tk.EW, padx=(4,0))
        # Rename project under Open Chat
        ttk.Button(actions, text='Rename Project', style='Select.TButton', command=self._rename_selected_project).grid(row=1, column=0, columnspan=2, sticky=tk.EW, pady=(4,0))
        # Rename chat within selected project
        ttk.Button(actions, text='Rename Chat', style='Select.TButton', command=self._rename_selected_chat).grid(row=2, column=0, columnspan=2, sticky=tk.EW, pady=(4,0))

        # Panel-wide RAG controls for projects (🧠, 🧠+, 🧠++)
        rag_bar = ttk.Frame(parent, style='Category.TFrame')
        rag_bar.grid(row=3, column=0, sticky=tk.EW, padx=8, pady=(0,4))
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
        self._proj_rag_hint_label.grid(row=4, column=0, sticky=tk.W, padx=12, pady=(0,6))

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

    # Projects tree helpers
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

    def _create_project(self):
        name = simpledialog.askstring('Create Project', 'Enter project name:')
        if not name:
            return
        ensure_project(name)
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
        elif vals[0] == 'session':
            self.current_project = vals[1]

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
        meta = {
            "mode": getattr(self, 'current_mode', 'smart'),
            "temperature": self.session_temperature,
            "temp_mode": getattr(self, 'temp_mode', 'manual'),
            "system_prompt": getattr(self, 'current_system_prompt', 'default'),
            "tool_schema": getattr(self, 'current_tool_schema', 'default'),
            "rag_enabled": bool(self.rag_enabled),
        }
        if not self.current_project and self.auto_project:
            self.current_project = f"Project_{Path.cwd().name}_{random.randint(100,999)}"
            ensure_project(self.current_project)
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
                mk('🧠', 'Toggle RAG per project/chat', _toggle_rag)
                mk('🗂', 'Create Project', self._create_project)
        except Exception:
            pass

    # Add indicator for RAG and current project
    def _update_quick_indicators(self):
        # Suppress base RAG indicator to avoid duplicates while parent rebuilds
        try:
            self._suppress_base_rag_indicator = True
        except Exception:
            pass
        super()._update_quick_indicators()
        try:
            self._suppress_base_rag_indicator = False
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
