"""
Custom Code Tab - Main tab for OpenCode integration
Provides chat interface and tooling features
"""

import tkinter as tk
from tkinter import ttk
from pathlib import Path
import sys
import json

# Add parent directories to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from tabs.base_tab import BaseTab
from logger_util import log_message


class CustomCodeTab(BaseTab):
    """Custom Code tab with sub-tabs for chat, tools, and project management"""

    def __init__(self, parent, root, style):
        super().__init__(parent, root, style)
        self.tab_instances = None  # Will be set by main GUI
        self._open_projects = {}  # Registry of open ProjectTab instances

        # Set up close handler for auto-saving chat history
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def create_ui(self):
        """Create the custom code tab UI"""
        log_message("CUSTOM_CODE_TAB: Creating UI...")

        # Main layout: content area (left) and side panel (right)
        self.parent.columnconfigure(0, weight=1)  # Content area
        self.parent.columnconfigure(1, weight=0)  # Side panel
        self.parent.rowconfigure(0, weight=1)

        # Left side: Main content with sub-tabs
        content_frame = ttk.Frame(self.parent, style='Category.TFrame')
        content_frame.grid(row=0, column=0, sticky=tk.NSEW, padx=10, pady=10)
        content_frame.columnconfigure(0, weight=1)
        content_frame.rowconfigure(1, weight=1)

        # Header with title and refresh button
        header_frame = ttk.Frame(content_frame, style='Category.TFrame')
        header_frame.grid(row=0, column=0, sticky=tk.EW, pady=5)

        ttk.Label(
            header_frame,
            text="🤖 Custom Code",
            font=("Arial", 14, "bold"),
            style='CategoryPanel.TLabel'
        ).pack(side=tk.LEFT, padx=(0, 10))

        ttk.Button(
            header_frame,
            text="🔄 Refresh",
            command=self.refresh_tab,
            style='Select.TButton'
        ).pack(side=tk.RIGHT, padx=5)

        # Sub-tabs notebook
        self.sub_notebook = ttk.Notebook(content_frame)
        self.sub_notebook.grid(row=1, column=0, sticky=tk.NSEW, padx=5, pady=5)
        self.bind_sub_notebook(self.sub_notebook, label='Custom Code')

        # Chat Interface Sub-tab
        self.chat_tab_frame = ttk.Frame(self.sub_notebook)
        self.sub_notebook.add(self.chat_tab_frame, text="💬 Chat")
        self.create_chat_tab(self.chat_tab_frame)

        # History Sub-tab
        self.history_tab_frame = ttk.Frame(self.sub_notebook)
        self.sub_notebook.add(self.history_tab_frame, text="📚 History")
        self.create_history_tab(self.history_tab_frame)

        # Tools Sub-tab
        self.tools_tab_frame = ttk.Frame(self.sub_notebook)
        self.sub_notebook.add(self.tools_tab_frame, text="🔧 Tools")
        self.create_tools_tab(self.tools_tab_frame)

        # Projects Sub-tab (Project Factory hub)
        self.projects_tab_frame = ttk.Frame(self.sub_notebook)
        self.sub_notebook.add(self.projects_tab_frame, text="📡 Project")
        self.create_projects_hub(self.projects_tab_frame)

        # 3D Models Sub-tab
        self.models_3d_frame = ttk.Frame(self.sub_notebook)
        self.sub_notebook.add(self.models_3d_frame, text="🧊 3D Models")
        self.create_models_3d_tab(self.models_3d_frame)

        # Settings Sub-tab
        self.settings_tab_frame = ttk.Frame(self.sub_notebook)
        self.sub_notebook.add(self.settings_tab_frame, text="⚙️ Settings")
        self.create_settings_tab(self.settings_tab_frame)

        # IDE Sub-tab
        self.ide_tab_frame = ttk.Frame(self.sub_notebook)
        self.sub_notebook.add(self.ide_tab_frame, text="✏️ IDE")
        self.create_ide_tab(self.ide_tab_frame)

        # Inventory sub-tab (doc ingestion + stash management)
        from .sub_tabs.inventory_tab import InventoryTab
        inventory_frame = ttk.Frame(self.sub_notebook)
        self.sub_notebook.add(inventory_frame, text="📦 Inventory")
        self.inventory_interface = InventoryTab(inventory_frame, self.root, self.style, self)
        self.inventory_interface.safe_create()

        # Omega Console sub-tab (ThoughtMatrix live projector)
        from .sub_tabs.omega_console_tab import OmegaConsoleTab
        omega_console_frame = ttk.Frame(self.sub_notebook)
        self.sub_notebook.add(omega_console_frame, text="⚡ Ω Console")
        self.omega_console = OmegaConsoleTab(omega_console_frame, self.root, self.style, self)
        self.omega_console.safe_create()

        # Right side: Model selector (similar to Models tab)
        self.create_right_panel(self.parent)

        log_message("CUSTOM_CODE_TAB: UI created successfully")

    def create_chat_tab(self, parent):
        """Create the chat interface sub-tab"""
        # Import here to avoid circular dependencies
        from .sub_tabs.chat_interface_tab import ChatInterfaceTab

        self.chat_interface = ChatInterfaceTab(parent, self.root, self.style, self)
        self.chat_interface.safe_create()

    def create_tools_tab(self, parent):
        """Create the tools configuration sub-tab"""
        from .sub_tabs.tools_tab import ToolsTab

        self.tools_interface = ToolsTab(parent, self.root, self.style, self)
        self.tools_interface.safe_create()

    def create_settings_tab(self, parent):
        """Create the settings configuration sub-tab"""
        from .sub_tabs.settings_tab import CustomCodeSettingsTab

        self.settings_interface = CustomCodeSettingsTab(parent, self.root, self.style, self)
        self.settings_interface.safe_create()

    def create_ide_tab(self, parent):
        """Embed TextEnhanceAI as the IDE sub-tab."""
        from .TextEnhanceAI.text_enhance_tab import TextEnhanceTab
        self.ide_interface = TextEnhanceTab(parent, self.root, self.style, self)
        self.ide_interface.safe_create()

    def create_history_tab(self, parent):
        """Create the conversation history sub-tab"""
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(1, weight=1)

        # Header
        header_frame = ttk.Frame(parent, style='Category.TFrame')
        header_frame.grid(row=0, column=0, sticky=tk.EW, padx=10, pady=10)

        ttk.Label(
            header_frame,
            text="📚 Conversation History",
            font=("Arial", 12, "bold"),
            style='CategoryPanel.TLabel'
        ).pack(side=tk.LEFT, padx=(0, 10))

        ttk.Button(
            header_frame,
            text="🔄 Refresh",
            command=self.refresh_history,
            style='Select.TButton'
        ).pack(side=tk.RIGHT)

        # History list frame with scrollbar
        list_container = ttk.Frame(parent, style='Category.TFrame')
        list_container.grid(row=1, column=0, sticky=tk.NSEW, padx=10, pady=(0, 10))
        list_container.columnconfigure(0, weight=1)
        list_container.rowconfigure(0, weight=1)

        # Canvas for scrolling
        self.history_canvas = tk.Canvas(
            list_container,
            bg='#2b2b2b',
            highlightthickness=0
        )
        self.history_scrollbar = ttk.Scrollbar(
            list_container,
            orient="vertical",
            command=self.history_canvas.yview
        )
        self.history_scroll_frame = ttk.Frame(self.history_canvas, style='Category.TFrame')

        self.history_scroll_frame.bind(
            "<Configure>",
            lambda e: self.history_canvas.configure(scrollregion=self.history_canvas.bbox("all"))
        )

        self.history_canvas_window = self.history_canvas.create_window(
            (0, 0),
            window=self.history_scroll_frame,
            anchor="nw"
        )
        self.history_canvas.configure(yscrollcommand=self.history_scrollbar.set)

        self.history_canvas.bind(
            "<Configure>",
            lambda e: self.history_canvas.itemconfig(self.history_canvas_window, width=e.width)
        )

        self.history_canvas.grid(row=0, column=0, sticky=tk.NSEW)
        self.history_scrollbar.grid(row=0, column=1, sticky=tk.NS)

        # Enable mousewheel scrolling for history list
        self.bind_mousewheel_to_canvas(self.history_canvas)

        # Load history
        self.refresh_history()

    def refresh_history(self):
        """Refresh the conversation history list from persistent storage"""
        log_message("CUSTOM_CODE_TAB: Refreshing history from storage...")

        # Clear existing
        for widget in self.history_scroll_frame.winfo_children():
            widget.destroy()

        if not hasattr(self, 'chat_interface') or not self.chat_interface or not self.chat_interface.chat_history_manager:
            ttk.Label(
                self.history_scroll_frame,
                text="Chat history manager not initialized.",
                style='Config.TLabel'
            ).pack(pady=20, padx=10)
            return

        # Get conversation histories from ChatHistoryManager
        histories = self.chat_interface.chat_history_manager.list_conversations()

        if not histories:
            ttk.Label(
                self.history_scroll_frame,
                text="No saved conversation history found.",
                style='Config.TLabel'
            ).pack(pady=20, padx=10)
            return

        def show_config(cfg):
            import json
            config_win = tk.Toplevel(self.root)
            config_win.title("Session Configuration")
            config_win.geometry("600x400")
            text = tk.Text(config_win, wrap=tk.WORD, font=("Courier", 10))
            text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
            text.insert(tk.END, json.dumps(cfg, indent=2))
            text.config(state=tk.DISABLED)

        # Display each conversation
        for conv_summary in histories:
            session_id = conv_summary.get("session_id")
            model_name = conv_summary.get("model_name")
            msg_count = conv_summary.get("message_count")
            saved_at = conv_summary.get("saved_at")
            preview = conv_summary.get("preview")
            metadata = conv_summary.get("metadata", {})

            # Create frame for this session
            session_frame = ttk.LabelFrame(
                self.history_scroll_frame,
                text=f"📄 {session_id}",
                style='TLabelframe'
            )
            session_frame.pack(fill=tk.X, padx=5, pady=5)

            # Display info
            info_text = f"Model: {model_name} | Messages: {msg_count} | Saved: {saved_at}"
            ttk.Label(
                session_frame,
                text=info_text,
                style='Config.TLabel'
            ).pack(anchor=tk.W, padx=10, pady=(5, 2))

            ttk.Label(
                session_frame,
                text=f"Preview: {preview}",
                style='Config.TLabel'
            ).pack(anchor=tk.W, padx=10, pady=(0, 5))

            # Buttons
            btn_frame = ttk.Frame(session_frame, style='Category.TFrame')
            btn_frame.pack(fill=tk.X, padx=10, pady=(0, 5))

            ttk.Button(
                btn_frame,
                text="Load Conversation",
                command=lambda s=session_id: self.load_conversation(s),
                style='Action.TButton'
            ).pack(side=tk.LEFT, padx=(0, 5))

            ttk.Button(
                btn_frame,
                text="View Config",
                command=lambda m=metadata: show_config(m),
                style='Action.TButton'
            ).pack(side=tk.LEFT, padx=(0, 5))

            ttk.Button(
                btn_frame,
                text="Delete",
                command=lambda s=session_id: self.delete_conversation(s),
                style='Select.TButton'
            ).pack(side=tk.LEFT)

    def load_conversation(self, session_id):
        """Load a conversation from history by session_id"""
        log_message(f"CUSTOM_CODE_TAB: Loading conversation {session_id}")

        if not hasattr(self, 'chat_interface') or not self.chat_interface or not self.chat_interface.chat_history_manager:
            return

        conversation = self.chat_interface.chat_history_manager.load_conversation(session_id)
        if not conversation:
            from tkinter import messagebox
            messagebox.showerror("Error", f"Failed to load conversation: {session_id}")
            return

        # Switch to chat tab
        self.sub_notebook.select(self.chat_tab_frame)

        # Load the conversation into the chat interface
        self.chat_interface.chat_history = conversation.get("chat_history", [])
        self.chat_interface.current_model = conversation.get("model_name")
        self.chat_interface.current_session_id = session_id
        self.chat_interface.model_label.config(text=self.chat_interface.current_model)
        self.chat_interface.redisplay_conversation()
        self.chat_interface.add_message("system", f"✓ Loaded conversation: {session_id}")

    def delete_conversation(self, session_id):
        """Delete a conversation from history by session_id"""
        from tkinter import messagebox

        if not hasattr(self, 'chat_interface') or not self.chat_interface or not self.chat_interface.chat_history_manager:
            return

        if messagebox.askyesno(
            "Delete Conversation",
            f"Are you sure you want to delete this conversation?\n\n{session_id}"
        ):
            if self.chat_interface.chat_history_manager.delete_conversation(session_id):
                messagebox.showinfo("Deleted", "Conversation deleted successfully")
                self.refresh_history()
            else:
                messagebox.showerror("Error", "Failed to delete conversation")

    # ------------------------------------------------------------------
    # Projects Hub — Version Management + Custom Projects
    # ------------------------------------------------------------------

    # Tabs with hardware/system dependencies that cannot run in sandbox
    _CORE_TABS_NO_SANDBOX = frozenset({'training_tab', 'map_tab', 'models_tab', 'settings_tab'})

    def create_projects_hub(self, parent):
        """Create the Projects hub: version tree (left) + context panel (right)."""
        parent.rowconfigure(0, weight=1)
        parent.columnconfigure(0, weight=1)

        pane = ttk.PanedWindow(parent, orient=tk.HORIZONTAL)
        pane.grid(row=0, column=0, sticky=tk.NSEW, padx=5, pady=5)

        left = ttk.Frame(pane, width=300)
        pane.add(left, weight=2)
        self._build_version_tree(left)

        right = ttk.Frame(pane)
        pane.add(right, weight=3)
        self._build_context_panel(right)

    def _get_projects_path(self):
        """Return path to projects.json."""
        return Path(__file__).parent.parent / "plans" / "projects.json"

    def _load_projects(self):
        """Load projects from projects.json."""
        path = self._get_projects_path()
        if path.exists():
            try:
                return json.loads(path.read_text(encoding='utf-8'))
            except Exception as e:
                log_message(f"PROJECTS_HUB: Error loading projects.json: {e}")
        return {"projects": [], "next_seq": 1}

    def _save_projects(self, data):
        """Save projects data to projects.json."""
        path = self._get_projects_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2), encoding='utf-8')

    def _refresh_projects_list(self):
        """Refresh the version tree (replaces old card-based refresh)."""
        if hasattr(self, 'version_tree'):
            self._rebuild_version_tree()

    # ------------------------------------------------------------------
    # Version tree builders & event handlers
    # ------------------------------------------------------------------

    def _build_version_tree(self, parent):
        """Build the left Treeview: Tab Versions + Custom Projects sections."""
        parent.rowconfigure(1, weight=1)
        parent.columnconfigure(0, weight=1)

        # Header row
        hdr = ttk.Frame(parent, style='Category.TFrame')
        hdr.grid(row=0, column=0, columnspan=2, sticky=tk.EW, padx=5, pady=(5, 0))
        ttk.Label(hdr, text="📡 Projects & Versions",
                  font=("Arial", 11, "bold"),
                  style='CategoryPanel.TLabel').pack(side=tk.LEFT)
        ttk.Button(hdr, text="➕", command=self._show_new_project_dialog,
                   style='Action.TButton', width=3).pack(side=tk.RIGHT, padx=(2, 5))
        ttk.Button(hdr, text="🔄", command=self._rebuild_version_tree,
                   style='Select.TButton', width=3).pack(side=tk.RIGHT)

        # Treeview
        self.version_tree = ttk.Treeview(
            parent,
            columns=('status', 'count'),
            show='tree headings',
            selectmode='browse',
            height=20
        )
        self.version_tree.heading('#0', text='Item')
        self.version_tree.heading('status', text='Version')
        self.version_tree.heading('count', text='#')
        self.version_tree.column('#0', width=180, minwidth=140, stretch=True)
        self.version_tree.column('status', width=110, minwidth=90, stretch=True)
        self.version_tree.column('count', width=35, minwidth=30, stretch=False)

        vsb = ttk.Scrollbar(parent, orient='vertical', command=self.version_tree.yview)
        self.version_tree.configure(yscrollcommand=vsb.set)

        self.version_tree.grid(row=1, column=0, sticky=tk.NSEW, padx=(5, 0), pady=5)
        vsb.grid(row=1, column=1, sticky=tk.NS, pady=5, padx=(0, 5))

        self.version_tree.bind('<<TreeviewOpen>>', self._on_version_tree_open)
        self.version_tree.bind('<<TreeviewSelect>>', self._on_version_tree_select)

        self._rebuild_version_tree()

    def _rebuild_version_tree(self):
        """Clear and repopulate both sections of the version tree."""
        import logger_util
        tree = self.version_tree
        for iid in list(tree.get_children()):
            tree.delete(iid)

        # ── Section A: Tab Versions ───────────────────────────────────
        tree.insert('', 'end', iid='tab_versions',
                    text='🧪 Tab Versions', values=('', ''), open=True,
                    tags=('section',))

        known_tabs = sorted(logger_util.TAB_REGISTRY.keys()) if logger_util.TAB_REGISTRY else []
        for tab_name in known_tabs:
            reg = logger_util.TAB_REGISTRY.get(tab_name, {})
            if reg.get('status') in ('DISABLED', 'IGNORED'):
                continue
            pending_count = self._fast_pending_count(tab_name)
            active_v = self._fast_active_version(tab_name)
            ver_disp = active_v[:14] if active_v else '—'
            count_str = str(pending_count) if pending_count else ''
            tag = 'pending_tab' if pending_count else 'ok_tab'
            tree.insert('tab_versions', 'end',
                        iid=f'tab:{tab_name}',
                        text=f'📋 {tab_name}',
                        values=(ver_disp, count_str),
                        tags=(tag,),
                        open=False)
            # Placeholder so the expand arrow appears
            tree.insert(f'tab:{tab_name}', 'end',
                        iid=f'tab:{tab_name}:__placeholder__',
                        text='…', values=('', ''))

        if not known_tabs:
            tree.insert('tab_versions', 'end', iid='tab:_none',
                        text='  (no tabs loaded yet)', values=('', ''))

        # ── Section B: Custom Projects ────────────────────────────────
        tree.insert('', 'end', iid='custom_projects',
                    text='📡 Custom Projects', values=('', ''), open=True,
                    tags=('section',))

        data = self._load_projects()
        for proj in data.get('projects', []):
            pid = proj['project_id']
            is_open = pid in self._open_projects
            status_str = '[OPEN]' if is_open else proj.get('created', '?')[:10]
            tree.insert('custom_projects', 'end',
                        iid=f'proj:{pid}',
                        text=f'📂 {pid}',
                        values=(status_str, ''),
                        tags=('open_proj' if is_open else 'proj',))

        tree.insert('custom_projects', 'end',
                    iid='proj:__new__',
                    text='  ➕ New Project', values=('', ''),
                    tags=('action',))

        # Style tags
        try:
            tree.tag_configure('section',     foreground='#61dafb', font=('Arial', 9, 'bold'))
            tree.tag_configure('pending_tab', foreground='#ffaa55')
            tree.tag_configure('ok_tab',      foreground='#aaffaa')
            tree.tag_configure('open_proj',   foreground='#88ffaa')
            tree.tag_configure('proj',        foreground='#cccccc')
            tree.tag_configure('action',      foreground='#888888')
            tree.tag_configure('version_row', foreground='#ccccff')
            tree.tag_configure('pending_row', foreground='#ffaa55')
            tree.tag_configure('more_row',    foreground='#888888')
        except Exception:
            pass

    def _fast_pending_count(self, tab_name):
        """Quick count of pending_live_changes entries for this tab's source file."""
        try:
            import logger_util, os
            import recovery_util as ru
            manifest = ru.load_version_manifest()
            src_file = logger_util.TAB_REGISTRY.get(tab_name, {}).get('source_file', '')
            if not src_file:
                return 0
            src_base = os.path.basename(src_file)
            return sum(1 for k in manifest.get('pending_live_changes', {})
                       if os.path.basename(k) == src_base)
        except Exception:
            return 0

    def _fast_active_version(self, tab_name):
        """Return the most recent version timestamp touching this tab's source file."""
        try:
            import logger_util, os
            import recovery_util as ru
            manifest = ru.load_version_manifest()
            src_file = logger_util.TAB_REGISTRY.get(tab_name, {}).get('source_file', '')
            if not src_file:
                return None
            src_base = os.path.basename(src_file)
            matching = [ts for ts, v in manifest.get('versions', {}).items()
                        if any(os.path.basename(f) == src_base
                               for f in v.get('files_changed', []))]
            return max(matching) if matching else None
        except Exception:
            return None

    def _on_version_tree_open(self, event):
        """Lazy-load version children when a tab row is first expanded."""
        tree = self.version_tree
        iid = tree.focus()
        if not iid.startswith('tab:'):
            return
        tab_name = iid[4:]
        if ':' in tab_name:  # sub-rows don't trigger loading
            return
        # Remove all placeholder children
        for child in list(tree.get_children(iid)):
            tree.delete(child)
        try:
            import recovery_util as ru
            summary = ru.get_tab_version_summary(tab_name)
        except Exception as e:
            tree.insert(iid, 'end', text=f'Error: {e}', values=('', ''))
            return
        pending = summary.get('pending', {})
        versions = summary.get('versions', [])  # [(ts, vdict), …]
        if pending:
            tree.insert(iid, 'end',
                        iid=f'tab:{tab_name}:pending',
                        text=f'⏳ Pending  (+{len(pending)} files)',
                        values=(f'{len(pending)} events', str(len(pending))),
                        tags=('pending_row',))
        MAX_SHOW = 5
        for ts, vdict in versions[:MAX_SHOW]:
            name = vdict.get('name', '')
            label = f'> {ts[:14]}' + (f'  "{name}"' if name else '')
            n_files = len(vdict.get('files_changed', []))
            tree.insert(iid, 'end',
                        iid=f'tab:{tab_name}:v:{ts}',
                        text=label,
                        values=(vdict.get('status', '?'), str(n_files)),
                        tags=('version_row',))
        remaining = len(versions) - MAX_SHOW
        if remaining > 0:
            tree.insert(iid, 'end',
                        iid=f'tab:{tab_name}:more',
                        text=f'  > Show {remaining} more…',
                        values=('', ''), tags=('more_row',))
        if not pending and not versions:
            tree.insert(iid, 'end', text='  (no recorded versions)', values=('', ''))

    def _on_version_tree_select(self, event):
        """Dispatch to the appropriate context panel loader on tree selection."""
        iid = self.version_tree.focus()
        if not iid or iid in ('tab_versions', 'custom_projects', 'tab:_none'):
            return
        if iid == 'proj:__new__':
            self._show_new_project_dialog()
            return
        if iid.startswith('proj:'):
            self._load_project_context(iid[5:])
            return
        if iid.startswith('tab:') and '__placeholder__' in iid:
            return
        if iid.startswith('tab:'):
            raw = iid[4:]               # strip "tab:"
            parts = raw.split(':')
            tab_name = parts[0]
            if len(parts) == 1:
                self._load_tab_context(tab_name, ts=None)
            elif parts[1] == 'pending':
                self._load_tab_context(tab_name, ts=None, show_pending=True)
            elif parts[1] == 'v' and len(parts) == 3:
                self._load_tab_context(tab_name, ts=parts[2])
            elif parts[1] == 'more':
                self._expand_more_versions(tab_name)

    def _load_tab_context(self, tab_name, ts=None, show_pending=False):
        """Populate the right context panel for a tab version or pending state."""
        try:
            import recovery_util as ru
            summary = ru.get_tab_version_summary(tab_name)
        except Exception as e:
            self._set_context_hint(f"Error loading summary: {e}")
            return
        vdict = {}
        if ts is None and not show_pending and summary['versions']:
            ts = summary['versions'][0][0]
        if ts:
            for vts, vd in summary['versions']:
                if vts == ts:
                    vdict = vd
                    break
        src_base = (summary.get('source_file') or tab_name).split('/')[-1]
        if show_pending:
            header = f"📋 {tab_name}  —  PENDING CHANGES  [{src_base}]"
        elif ts:
            header = f"📋 {tab_name}  —  {ts[:16]}  [{src_base}]"
        else:
            header = f"📋 {tab_name}  —  (no versions recorded)"
        self._ctx_header_var.set(header)
        self._ctx_tab_name_current = tab_name
        self._ctx_version_ts_current = ts
        # Name field
        self._ctx_name_var.set(vdict.get('name', '') if vdict else '')
        entry_state = 'normal' if ts else 'disabled'
        self._ctx_name_entry.config(state=entry_state)
        self._ctx_save_name_btn.config(state=entry_state)
        # Files treeview
        for item in self._ctx_file_tree.get_children():
            self._ctx_file_tree.delete(item)
        if show_pending:
            for fpath in summary.get('pending', {}).keys():
                self._ctx_file_tree.insert('', 'end',
                                           text=fpath.split('/')[-1],
                                           values=('pending',))
        elif vdict:
            for fpath in vdict.get('files_changed', []):
                n_events = sum(1 for ch in summary['events'].values()
                               if fpath.endswith(ch.get('file', '').split('/')[-1]))
                self._ctx_file_tree.insert('', 'end', iid=f'file:{fpath}',
                                           text=fpath.split('/')[-1],
                                           values=(str(n_events),))
        # Diff preview
        self._ctx_diff_text.config(state='normal')
        self._ctx_diff_text.delete('1.0', 'end')
        if vdict and vdict.get('diffs'):
            self._ctx_diff_text.insert('1.0', '\n'.join(vdict['diffs'])[:4000])
        elif show_pending and summary.get('events'):
            sample = next(iter(summary['events'].values()))
            self._ctx_diff_text.insert('1.0',
                f"Most recent event:\nFile: {sample.get('file')}\n"
                f"Verb: {sample.get('verb')}  Risk: {sample.get('risk_level','?')}\n"
                f"+{sample.get('additions',0)} / -{sample.get('deletions',0)} lines\n")
        else:
            self._ctx_diff_text.insert('1.0', '(no diff data)')
        self._ctx_diff_text.config(state='disabled')
        # Buttons
        can_sandbox = tab_name not in self._CORE_TABS_NO_SANDBOX
        self._ctx_spawn_btn.config(
            state='normal' if (can_sandbox and ts) else 'disabled',
            text='⚡ Spawn Sandbox' if can_sandbox else '⛔ No Sandbox')
        self._ctx_undo_btn.config(state='normal' if ts else 'disabled')

    def _load_project_context(self, project_id):
        """Populate right panel for a custom project row."""
        self._ctx_header_var.set(f"📂 {project_id}")
        self._ctx_name_var.set('')
        self._ctx_name_entry.config(state='disabled')
        self._ctx_save_name_btn.config(state='disabled')
        self._ctx_tab_name_current = None
        self._ctx_version_ts_current = None
        for item in self._ctx_file_tree.get_children():
            self._ctx_file_tree.delete(item)
        data = self._load_projects()
        proj_info = next((p for p in data.get('projects', [])
                          if p['project_id'] == project_id), {})
        is_open = project_id in self._open_projects
        self._ctx_diff_text.config(state='normal')
        self._ctx_diff_text.delete('1.0', 'end')
        self._ctx_diff_text.insert('1.0',
            f"Project:  {project_id}\n"
            f"Created:  {proj_info.get('created', '?')}\n"
            f"Scan:     {proj_info.get('scan_target', 'local')}\n"
            f"Status:   {'OPEN' if is_open else 'closed'}")
        self._ctx_diff_text.config(state='disabled')
        action_lbl = 'Close Project' if is_open else 'Open Project'
        self._ctx_spawn_btn.config(
            text=action_lbl, state='normal',
            command=lambda pid=project_id, c=proj_info: (
                self._close_project(pid) if is_open else self._open_project(pid, c)))
        self._ctx_undo_btn.config(state='disabled')

    def _set_context_hint(self, msg='Select an item from the tree to view details.'):
        """Reset the context panel to a neutral hint state."""
        self._ctx_header_var.set(msg)
        self._ctx_name_var.set('')
        self._ctx_name_entry.config(state='disabled')
        self._ctx_save_name_btn.config(state='disabled')
        for item in self._ctx_file_tree.get_children():
            self._ctx_file_tree.delete(item)
        self._ctx_diff_text.config(state='normal')
        self._ctx_diff_text.delete('1.0', 'end')
        self._ctx_diff_text.config(state='disabled')

    def _expand_more_versions(self, tab_name):
        """Remove the 'Show N more' row and insert all remaining version rows."""
        tree = self.version_tree
        parent_iid = f'tab:{tab_name}'
        for child in list(tree.get_children(parent_iid)):
            if tree.tag_has('version_row', child) or tree.tag_has('more_row', child):
                tree.delete(child)
        try:
            import recovery_util as ru
            summary = ru.get_tab_version_summary(tab_name)
            for ts, vdict in summary.get('versions', []):
                iid = f'tab:{tab_name}:v:{ts}'
                if not tree.exists(iid):
                    name = vdict.get('name', '')
                    label = f'> {ts[:14]}' + (f'  "{name}"' if name else '')
                    tree.insert(parent_iid, 'end', iid=iid, text=label,
                                values=(vdict.get('status', '?'),
                                        str(len(vdict.get('files_changed', [])))),
                                tags=('version_row',))
        except Exception as e:
            tree.insert(parent_iid, 'end', text=f'Error: {e}', values=('', ''))

    def _spawn_sandbox(self, tab_name, version_ts):
        """Open a sandbox ProjectTab for a safe tab's pending version."""
        from tkinter import messagebox
        if not tab_name or not version_ts:
            return
        if tab_name in self._CORE_TABS_NO_SANDBOX:
            messagebox.showinfo(
                "Sandbox Blocked",
                f"'{tab_name}' has hardware or system dependencies and cannot run in sandbox.\n\n"
                "You can still view version history and diffs in the context panel.",
                parent=self.root)
            return
        from datetime import datetime as _dt
        sandbox_id = f"sandbox_{tab_name}_{version_ts[:8]}"
        config = {
            'scan_target': 'local',
            'type': 'sandbox',
            'tab_name': tab_name,
            'version_ts': version_ts,
            'created': _dt.now().strftime('%Y-%m-%d %H:%M'),
        }
        self._open_project(sandbox_id, config)
        log_message(f"PROJECTS_HUB: Sandbox spawned for {tab_name} v{version_ts}")

    def _save_version_name_ui(self):
        """Write the name typed in the name field to the version manifest."""
        ts = getattr(self, '_ctx_version_ts_current', None)
        name = self._ctx_name_var.get().strip()
        if not ts:
            return
        try:
            import recovery_util as ru
            ok = ru.save_version_name(ts, name)
            if ok:
                tab_name = getattr(self, '_ctx_tab_name_current', '')
                iid = f'tab:{tab_name}:v:{ts}'
                if hasattr(self, 'version_tree') and self.version_tree.exists(iid):
                    new_text = f'> {ts[:14]}' + (f'  "{name}"' if name else '')
                    self.version_tree.item(iid, text=new_text)
                log_message(f"PROJECTS_HUB: Version name saved: {ts} → '{name}'")
        except Exception as e:
            log_message(f"PROJECTS_HUB: save_version_name error: {e}")

    def _ctx_open_undo(self):
        """Open UndoChangesDialog for the most recent event in the current context."""
        tab_name = getattr(self, '_ctx_tab_name_current', None)
        if not tab_name:
            return
        try:
            import recovery_util as ru
            summary = ru.get_tab_version_summary(tab_name)
            events = summary.get('events', {})
            if not events:
                from tkinter import messagebox
                messagebox.showinfo("No Events", f"No recorded events for {tab_name}.")
                return
            latest_eid = max(events.keys())
            manifest = ru.load_version_manifest()
            import sys
            _data_dir = str(Path(__file__).parent.parent.parent)
            if _data_dir not in sys.path:
                sys.path.insert(0, _data_dir)
            from tabs.settings_tab.undo_changes import UndoChangesDialog
            UndoChangesDialog(self.parent, latest_eid, manifest)
        except Exception as e:
            from tkinter import messagebox
            messagebox.showerror("Error", f"Cannot open Undo dialog: {e}")

    def _build_context_panel(self, parent):
        """Build the right context panel: header, name, files tree, diff preview, actions."""
        from tkinter import scrolledtext
        parent.rowconfigure(2, weight=1)
        parent.columnconfigure(0, weight=1)

        # Header
        self._ctx_header_var = tk.StringVar(value='Select an item to view details.')
        self._ctx_tab_name_current = None
        self._ctx_version_ts_current = None
        ttk.Label(parent, textvariable=self._ctx_header_var,
                  font=('Arial', 10, 'bold'), style='CategoryPanel.TLabel',
                  wraplength=400, anchor='w'
                  ).grid(row=0, column=0, sticky=tk.EW, padx=10, pady=(8, 2))

        # Name field
        name_frame = ttk.Frame(parent, style='Category.TFrame')
        name_frame.grid(row=1, column=0, sticky=tk.EW, padx=10, pady=(0, 4))
        name_frame.columnconfigure(1, weight=1)
        ttk.Label(name_frame, text='Name:', style='Config.TLabel').grid(
            row=0, column=0, padx=(0, 5))
        self._ctx_name_var = tk.StringVar()
        self._ctx_name_entry = ttk.Entry(name_frame, textvariable=self._ctx_name_var,
                                         state='disabled')
        self._ctx_name_entry.grid(row=0, column=1, sticky=tk.EW)
        self._ctx_save_name_btn = ttk.Button(name_frame, text='Save',
                                             command=self._save_version_name_ui,
                                             state='disabled',
                                             style='Action.TButton', width=6)
        self._ctx_save_name_btn.grid(row=0, column=2, padx=(5, 0))

        # Files + Diff (vertical PanedWindow)
        inner_pane = ttk.PanedWindow(parent, orient=tk.VERTICAL)
        inner_pane.grid(row=2, column=0, sticky=tk.NSEW, padx=10, pady=5)

        # Changed files tree
        files_frame = ttk.LabelFrame(inner_pane, text='Changed Files')
        inner_pane.add(files_frame, weight=1)
        files_frame.rowconfigure(0, weight=1)
        files_frame.columnconfigure(0, weight=1)
        self._ctx_file_tree = ttk.Treeview(files_frame, columns=('events',),
                                            show='tree headings', height=4)
        self._ctx_file_tree.heading('#0', text='File')
        self._ctx_file_tree.heading('events', text='Events')
        self._ctx_file_tree.column('#0', stretch=True)
        self._ctx_file_tree.column('events', width=55, stretch=False)
        self._ctx_file_tree.grid(row=0, column=0, sticky=tk.NSEW)
        ftvsb = ttk.Scrollbar(files_frame, orient='vertical',
                               command=self._ctx_file_tree.yview)
        self._ctx_file_tree.configure(yscrollcommand=ftvsb.set)
        ftvsb.grid(row=0, column=1, sticky=tk.NS)

        # Diff preview
        diff_frame = ttk.LabelFrame(inner_pane, text='Diff Preview')
        inner_pane.add(diff_frame, weight=2)
        diff_frame.rowconfigure(0, weight=1)
        diff_frame.columnconfigure(0, weight=1)
        self._ctx_diff_text = scrolledtext.ScrolledText(
            diff_frame, wrap=tk.NONE, font=('Courier', 8),
            bg='#1e1e1e', fg='#cccccc', state='disabled', height=10)
        self._ctx_diff_text.grid(row=0, column=0, sticky=tk.NSEW)

        # Action buttons
        action_frame = ttk.Frame(parent, style='Category.TFrame')
        action_frame.grid(row=3, column=0, sticky=tk.EW, padx=10, pady=(0, 8))
        self._ctx_spawn_btn = ttk.Button(
            action_frame, text='⚡ Spawn Sandbox', state='disabled',
            style='Action.TButton',
            command=lambda: self._spawn_sandbox(
                getattr(self, '_ctx_tab_name_current', ''),
                getattr(self, '_ctx_version_ts_current', '')))
        self._ctx_spawn_btn.pack(side=tk.LEFT, padx=(0, 5))
        self._ctx_undo_btn = ttk.Button(
            action_frame, text='↶ Undo', state='disabled',
            style='Select.TButton',
            command=self._ctx_open_undo)
        self._ctx_undo_btn.pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(action_frame, text='🔄 Refresh Tree',
                   style='Select.TButton',
                   command=self._rebuild_version_tree).pack(side=tk.RIGHT)

    def _show_new_project_dialog(self):
        """Show dialog to create a new project."""
        data = self._load_projects()
        seq = data.get("next_seq", 1)
        default_name = f"Project_{seq:03d}"

        dialog = tk.Toplevel(self.root)
        dialog.title("New Project")
        dialog.geometry("400x250")
        dialog.transient(self.root)

        ttk.Label(dialog, text="Project Name:").pack(pady=(15, 5), padx=20, anchor=tk.W)
        name_var = tk.StringVar(value=default_name)
        name_entry = ttk.Entry(dialog, textvariable=name_var, width=30)
        name_entry.pack(padx=20, anchor=tk.W)

        ttk.Label(dialog, text="Scanner Scope:").pack(pady=(10, 5), padx=20, anchor=tk.W)
        scope_var = tk.StringVar(value="local")
        ttk.Radiobutton(
            dialog, text="Local (this tab only)", variable=scope_var, value="local"
        ).pack(padx=30, anchor=tk.W)
        ttk.Radiobutton(
            dialog, text="Global (whole app)", variable=scope_var, value="global"
        ).pack(padx=30, anchor=tk.W)

        def on_ok():
            pid = name_var.get().strip()
            if not pid:
                return
            existing = [p["project_id"] for p in data.get("projects", [])]
            if pid in existing:
                from tkinter import messagebox
                messagebox.showerror(
                    "Duplicate", f"Project '{pid}' already exists.", parent=dialog
                )
                return
            from datetime import datetime
            new_proj = {
                "project_id": pid,
                "created": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "scan_target": scope_var.get(),
                "model": None
            }
            data["projects"].append(new_proj)
            data["next_seq"] = seq + 1
            self._save_projects(data)
            dialog.destroy()
            self._open_project(pid, new_proj)
            self._refresh_projects_list()

        ttk.Button(dialog, text="OK", command=on_ok, style='Action.TButton').pack(pady=15)

    def _open_project(self, project_id, config):
        """Open a project as a new sub-tab."""
        if project_id in self._open_projects:
            tab_frame = self._open_projects[project_id]["frame"]
            self.sub_notebook.select(tab_frame)
            return

        tab_frame = ttk.Frame(self.sub_notebook)
        self.sub_notebook.add(tab_frame, text=f"📂 {project_id}")

        from .sub_tabs.project_tab import ProjectTab
        project_tab = ProjectTab(tab_frame, self.root, self.style, project_id, config)
        success = project_tab.safe_create()

        self._open_projects[project_id] = {
            "frame": tab_frame,
            "tab": project_tab,
            "config": config
        }
        self.sub_notebook.select(tab_frame)
        self._refresh_projects_list()
        log_message(f"PROJECTS_HUB: Opened {project_id} (success={success})")

    def _close_project(self, project_id):
        """Close a project sub-tab."""
        if project_id not in self._open_projects:
            return
        entry = self._open_projects.pop(project_id)
        tab_frame = entry["frame"]
        self.sub_notebook.forget(tab_frame)
        tab_frame.destroy()
        self._refresh_projects_list()
        log_message(f"PROJECTS_HUB: Closed {project_id}")

    # ------------------------------------------------------------------
    # 3D Models Tab
    # ------------------------------------------------------------------

    def create_models_3d_tab(self, parent):
        """Create the 3D Models sub-tab."""
        from .sub_tabs.models_3d_tab import Models3DTab
        self.models_3d_interface = Models3DTab(parent, self.root, self.style, self)
        self.models_3d_interface.safe_create()

    def create_placeholder_tab(self, parent, title):
        """Create a placeholder tab for future features"""
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(0, weight=1)

        container = ttk.Frame(parent, style='Category.TFrame')
        container.grid(row=0, column=0, sticky=tk.NSEW, padx=20, pady=20)

        ttk.Label(
            container,
            text=f"🚧 {title}",
            font=("Arial", 16, "bold"),
            style='CategoryPanel.TLabel'
        ).pack(pady=20)

        ttk.Label(
            container,
            text="This feature is planned for future development.",
            font=("Arial", 10),
            style='Config.TLabel'
        ).pack(pady=10)

    def create_right_panel(self, parent):
        """Create right side panel with model selector"""
        right_panel = ttk.Frame(parent, width=300, style='Category.TFrame')
        right_panel.grid(row=0, column=1, sticky=tk.NSEW, padx=(10, 10), pady=10)
        right_panel.grid_propagate(False)  # Maintain fixed width
        right_panel.columnconfigure(0, weight=1)
        right_panel.rowconfigure(1, weight=1)

        # Header
        header = ttk.Frame(right_panel, style='Category.TFrame')
        header.grid(row=0, column=0, sticky=tk.EW, pady=(0, 10))

        ttk.Label(
            header,
            text="🤖 Models",
            font=("Arial", 12, "bold"),
            style='CategoryPanel.TLabel'
        ).pack(side=tk.LEFT)

        ttk.Button(
            header,
            text="🔄",
            command=self.refresh_model_list,
            style='Select.TButton',
            width=3
        ).pack(side=tk.RIGHT)

        # Model list frame with scrollbar
        list_container = ttk.Frame(right_panel, style='Category.TFrame')
        list_container.grid(row=1, column=0, sticky=tk.NSEW)
        list_container.columnconfigure(0, weight=1)
        list_container.rowconfigure(0, weight=1)

        # Canvas for scrolling
        self.model_canvas = tk.Canvas(
            list_container,
            bg='#2b2b2b',
            highlightthickness=0
        )
        self.model_scrollbar = ttk.Scrollbar(
            list_container,
            orient="vertical",
            command=self.model_canvas.yview
        )
        self.model_scroll_frame = ttk.Frame(self.model_canvas, style='Category.TFrame')

        self.model_scroll_frame.bind(
            "<Configure>",
            lambda e: self.model_canvas.configure(scrollregion=self.model_canvas.bbox("all"))
        )

        self.model_canvas_window = self.model_canvas.create_window(
            (0, 0),
            window=self.model_scroll_frame,
            anchor="nw"
        )
        self.model_canvas.configure(yscrollcommand=self.model_scrollbar.set)

        # Bind resize to adjust canvas window width
        self.model_canvas.bind(
            "<Configure>",
            lambda e: self.model_canvas.itemconfig(self.model_canvas_window, width=e.width)
        )

        self.model_canvas.grid(row=0, column=0, sticky=tk.NSEW)
        self.model_scrollbar.grid(row=0, column=1, sticky=tk.NS)

        # Enable mousewheel scrolling for model list
        self.bind_mousewheel_to_canvas(self.model_canvas)

        # Load models
        self.refresh_model_list()

    def refresh_model_list(self):
        """Refresh model list — Ollama + local GGUF."""
        log_message("CUSTOM_CODE_TAB: Refreshing model list...")

        for widget in self.model_scroll_frame.winfo_children():
            widget.destroy()

        try:
            from config import get_all_trained_models
            all_models = get_all_trained_models()
        except Exception as e:
            log_message(f"CUSTOM_CODE_TAB ERROR: Failed to get models: {e}")
            all_models = []

        ollama_models = [m for m in all_models if m["type"] == "ollama"]
        gguf_models   = [m for m in all_models if m["type"] == "gguf"]

        if not ollama_models and not gguf_models:
            ttk.Label(self.model_scroll_frame, text="No models found",
                      style='Config.TLabel').pack(pady=20, padx=10)
            return

        if ollama_models:
            ttk.Label(self.model_scroll_frame, text="Ollama",
                      font=("Arial", 9, "bold"), foreground='#61dafb',
                      style='Config.TLabel').pack(anchor=tk.W, padx=6, pady=(8, 2))
            for m in ollama_models:
                info = {"name": m["name"], "type": "ollama", "path": None}
                ttk.Button(self.model_scroll_frame, text=m["name"],
                           command=lambda mi=info: self.select_model(mi),
                           style='Category.TButton').pack(fill=tk.X, padx=5, pady=2)

        if gguf_models:
            ttk.Label(self.model_scroll_frame, text="🟣 Local GGUF",
                      font=("Arial", 9, "bold"), foreground='#c792ea',
                      style='Config.TLabel').pack(anchor=tk.W, padx=6, pady=(8, 2))
            for m in gguf_models:
                label = f"{m['name']} ({m.get('size','?')})"
                ttk.Button(self.model_scroll_frame, text=label,
                           command=lambda mi=m: self.select_model(mi),
                           style='Category.TButton').pack(fill=tk.X, padx=5, pady=2)

        log_message(f"CUSTOM_CODE_TAB: {len(ollama_models)} ollama, {len(gguf_models)} gguf models")

    def select_model(self, model_info):
        """Handle model selection — accepts model_info dict or bare name string."""
        if isinstance(model_info, str):
            model_info = {"name": model_info, "type": "ollama", "path": None}
        log_message(f"CUSTOM_CODE_TAB: Model selected: {model_info['name']} [{model_info['type']}]")
        if hasattr(self, 'chat_interface') and self.chat_interface:
            self.chat_interface.set_model(model_info['name'], model_info=model_info)
        if hasattr(self, 'ide_interface') and self.ide_interface:
            self.ide_interface.set_model(model_info['name'], model_info=model_info)

    def get_chat_interface_scores(self):
        """Get the real-time evaluation scores from the chat interface"""
        if hasattr(self, 'chat_interface') and self.chat_interface:
            return self.chat_interface.get_realtime_eval_scores()
        return {}

    def set_training_mode(self, enabled):
        """Set the training mode for the chat interface"""
        if hasattr(self, 'chat_interface') and self.chat_interface:
            self.chat_interface.set_training_mode(enabled)

    def on_mode_changed(self, mode, params):
        """Handle mode changes from the settings tab"""
        if hasattr(self, 'chat_interface') and self.chat_interface:
            self.chat_interface.set_mode_parameters(mode, params)

    def on_closing(self):
        """Handle application close - save chat history"""
        log_message("CUSTOM_CODE_TAB: Application closing, saving chat history...")

        # Save chat history before closing
        if hasattr(self, 'chat_interface') and self.chat_interface:
            self.chat_interface.save_on_exit()

        # Close the application
        self.root.destroy()

    def refresh_tab(self):
        """Refresh the entire tab"""
        log_message("CUSTOM_CODE_TAB: Refreshing tab...")
        self.refresh_model_list()
        if hasattr(self, 'chat_interface') and self.chat_interface:
            self.chat_interface.refresh()
