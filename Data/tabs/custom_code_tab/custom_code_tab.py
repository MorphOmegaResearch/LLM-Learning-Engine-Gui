"""
Custom Code Tab - Main tab for OpenCode integration
Provides chat interface and tooling features
"""

import tkinter as tk
from tkinter import ttk
from pathlib import Path
import sys

# Add parent directories to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from tabs.base_tab import BaseTab
from logger_util import log_message


class CustomCodeTab(BaseTab):
    """Custom Code tab with sub-tabs for chat, tools, and project management"""

    def __init__(self, parent, root, style):
        super().__init__(parent, root, style)
        self.tab_instances = None  # Will be set by main GUI

        # Set up close handler for auto-saving chat history
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

        # Backend settings (shared file with Chat)
        from pathlib import Path
        import json
        self._settings_path = Path(__file__).parent / 'custom_code_settings.json'
        try:
            self._backend_settings = json.loads(self._settings_path.read_text()) if self._settings_path.exists() else {}
        except Exception:
            self._backend_settings = {}
        # Use last saved width, and default to locked on launch
        self._right_panel_width = int(self._backend_settings.get('right_panel_width', 340))
        self._right_panel_locked = True
        self._backend_settings['right_panel_locked'] = True

    def create_ui(self):
        """Create the custom code tab UI"""
        log_message("CUSTOM_CODE_TAB: Creating UI...")

        # Main layout: Paned window with resizable left (content) and right (models)
        self.parent.columnconfigure(0, weight=1)
        self.parent.rowconfigure(0, weight=1)
        outer_pw = ttk.Panedwindow(self.parent, orient=tk.HORIZONTAL)
        outer_pw.grid(row=0, column=0, sticky=tk.NSEW)
        self._outer_pw = outer_pw

        # Left side pane: main content with sub-tabs
        content_frame = ttk.Frame(outer_pw, style='Category.TFrame')
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

        # Chat Interface Sub-tab
        self.chat_tab_frame = ttk.Frame(self.sub_notebook)
        self.sub_notebook.add(self.chat_tab_frame, text="💬 Chat")
        self.create_chat_tab(self.chat_tab_frame)
        # When user navigates to Chat tab, refresh conversations (bind once)
        try:
            def _on_subtab_changed(event=None):
                try:
                    current = self.sub_notebook.select()
                    if current == str(self.chat_tab_frame) and hasattr(self, 'chat_interface'):
                        if hasattr(self.chat_interface, '_refresh_conversations_list'):
                            self.chat_interface._refresh_conversations_list()
                except Exception:
                    pass
            self.sub_notebook.bind('<<NotebookTabChanged>>', _on_subtab_changed)
        except Exception:
            pass

        # History sub-tab removed (handled via Chat sidebar quick views)

        # Tools Sub-tab
        self.tools_tab_frame = ttk.Frame(self.sub_notebook)
        self.sub_notebook.add(self.tools_tab_frame, text="🔧 Tools")
        self.create_tools_tab(self.tools_tab_frame)

        # Projects Sub-tab (project-aware chat interface)
        self.projects_tab_frame = ttk.Frame(self.sub_notebook)
        self.sub_notebook.add(self.projects_tab_frame, text="📁 Projects")
        self.create_projects_tab(self.projects_tab_frame)

        # Settings Sub-tab
        self.settings_tab_frame = ttk.Frame(self.sub_notebook)
        self.sub_notebook.add(self.settings_tab_frame, text="⚙️ Settings")
        self.create_settings_tab(self.settings_tab_frame)

        # Right side pane: Model selector
        right_pane = ttk.Frame(outer_pw, style='Category.TFrame')
        right_pane.columnconfigure(0, weight=1)
        right_pane.rowconfigure(0, weight=1)
        self.create_right_panel(right_pane)

        outer_pw.add(content_frame, weight=1)
        outer_pw.add(right_pane, weight=0)
        try:
            # Enforce sensible minimum sizes so panes don't disappear
            outer_pw.paneconfigure(content_frame, minsize=500)
            outer_pw.paneconfigure(right_pane, minsize=260)
        except Exception:
            pass

        # Set default sash position after layout: leave ~360px for right pane
        try:
            def _set_outer_sash():
                try:
                    self.parent.update_idletasks()
                    pw_w = max(self._outer_pw.winfo_width(), 1000)
                    target_right = int(self._backend_settings.get('right_panel_width', self._right_panel_width or 340))
                    target_right = max(260, target_right)
                    # Compute sash position from desired right width, clamp to min sizes
                    pos = pw_w - target_right
                    pos = max(600, min(pos, pw_w - 260))
                    self._outer_pw.sashpos(0, pos)
                except Exception:
                    pass
            self.parent.after(150, _set_outer_sash)
        except Exception:
            pass

        # Enforce locked width on resize
        def _enforce_right_width(event=None):
            if not getattr(self, '_right_panel_locked', False):
                return
            try:
                pw_w = max(self._outer_pw.winfo_width(), 800)
                width = max(260, int(getattr(self, '_right_panel_width', 340)))
                pos = pw_w - width
                self._outer_pw.sashpos(0, max(500, min(pos, pw_w - 260)))
            except Exception:
                pass
        self._outer_pw.bind('<Configure>', _enforce_right_width)

        # Apply initial lock behavior (disable drag + arrow when locked)
        self._apply_right_lock_state()

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
        from .sub_tabs.settings_tab import SettingsTab

        self.settings_interface = SettingsTab(parent, self.root, self.style, self)
        self.settings_interface.safe_create()

    def create_projects_tab(self, parent):
        """Create the projects management sub-tab (project-aware chat)."""
        from .sub_tabs.projects_interface_tab import ProjectsInterfaceTab
        self.projects_interface = ProjectsInterfaceTab(parent, self.root, self.style, self)
        self.projects_interface.safe_create()

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
        right_panel = ttk.Frame(parent, width=360, style='Category.TFrame')
        right_panel.grid(row=0, column=0, sticky=tk.NSEW, padx=10, pady=10)
        # Maintain internal width to keep scrollbar visible
        right_panel.grid_propagate(False)
        right_panel.columnconfigure(0, weight=1)
        right_panel.rowconfigure(1, weight=1)
        # Keep a handle for width measurement when locking
        self._right_pane_widget = right_panel

        # Header
        header = ttk.Frame(right_panel, style='Category.TFrame')
        header.grid(row=0, column=0, sticky=tk.EW, pady=(0, 10))

        ttk.Label(
            header,
            text="🤖 Ollama Models",
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
        # Lock width toggle
        self._right_lock_btn = ttk.Button(
            header,
            text=("🔒" if self._right_panel_locked else "🔓"),
            command=self._toggle_right_panel_lock,
            style='Select.TButton',
            width=3
        )
        self._right_lock_btn.pack(side=tk.RIGHT, padx=(4,0))

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

        # UI state for expand/collapse
        # Default collapsed on launch
        self.cc_collections_expanded = False
        self.cc_unassigned_expanded = False
        self.cc_variant_expanded = {}
        # Load models
        self.refresh_model_list()

    def refresh_model_list(self):
        """Refresh the Ollama model list"""
        log_message("CUSTOM_CODE_TAB: Refreshing model list...")

        # Clear existing
        for widget in self.model_scroll_frame.winfo_children():
            widget.destroy()

        # Import config to get models and collections
        try:
            from config import (
                get_ollama_models,
                list_model_profiles,
                get_lineage_id,
                get_assigned_tags_by_lineage,
                load_ollama_assignments,
            )
            models = get_ollama_models() or []
            profiles = list_model_profiles() or []
            assignments = load_ollama_assignments() or {}
            tag_index = assignments.get('tag_index') or {}

            # Build assigned tags per variant using both v2 and legacy formats
            assigned_by_variant = {}
            for k, v in assignments.items():
                if k == 'tag_index':
                    continue
                if isinstance(v, dict):
                    tags = v.get('tags') or []
                else:
                    tags = v or []
                assigned_by_variant[k] = list(tags)
        except Exception as e:
            log_message(f"CUSTOM_CODE_TAB ERROR: Failed to get model/collection info: {e}")
            models, profiles, tag_index, assigned_by_variant = [], [], {}, {}

        # Collections section
        col_header = ttk.Frame(self.model_scroll_frame, style='Category.TFrame')
        col_header.pack(fill=tk.X, pady=(0,4))
        col_btn = ttk.Button(col_header, text=("▼" if self.cc_collections_expanded else "▶"), width=2, style='Select.TButton', command=self._toggle_cc_collections)
        col_btn.pack(side=tk.LEFT, padx=(0,5))
        ttk.Label(col_header, text="📚 Collections", font=("Arial", 11, "bold"), style='CategoryPanel.TLabel').pack(side=tk.LEFT)

        if self.cc_collections_expanded:
            # List variants with per-variant expand
            variants = sorted([it.get('variant_id') for it in profiles if it.get('variant_id')])
            if not variants:
                ttk.Label(self.model_scroll_frame, text="No variants found", style='Config.TLabel').pack(fill=tk.X, padx=10, pady=(0,6))
            for vid in variants:
                row = ttk.Frame(self.model_scroll_frame, style='Category.TFrame')
                row.pack(fill=tk.X)
                exp = self.cc_variant_expanded.get(vid, False)
                btn = ttk.Button(row, text=("▼" if exp else "▶"), width=2, style='Select.TButton', command=lambda v=vid: self._toggle_cc_variant(v))
                btn.pack(side=tk.LEFT, padx=(10,4))
                # Variant label colored by class level
                try:
                    from config import get_variant_class
                    cls = get_variant_class(vid)
                    color = {
                        'novice': '#51cf66', 'skilled': '#61dafb', 'expert': '#9b59b6', 'master': '#ffa94d', 'artifact': '#c92a2a'
                    }.get((cls or '').lower(), '#bbbbbb')
                    ttk.Label(row, text=vid, style='Config.TLabel', foreground=color).pack(side=tk.LEFT)
                except Exception:
                    ttk.Label(row, text=vid, style='Config.TLabel').pack(side=tk.LEFT)
                if exp:
                    # Assigned tags under this variant (prefer assignments mapping; then lineage; no ULID creation here)
                    tags = []
                    # v2/legacy by-variant mapping
                    tags = list(assigned_by_variant.get(vid) or [])
                    if not tags:
                        try:
                            lid = get_lineage_id(vid)
                            if lid:
                                tags = get_assigned_tags_by_lineage(lid) or []
                        except Exception:
                            tags = []
                    if tags:
                        for tg in tags:
                            trow = ttk.Frame(self.model_scroll_frame, style='Category.TFrame')
                            trow.pack(fill=tk.X)
                            ttk.Label(trow, text="Assigned:", style='Config.TLabel', foreground='#bbbbbb').pack(side=tk.LEFT, padx=(32,6))
                            # Color tag button by owning variant class color
                            try:
                                from tkinter import ttk as _ttk
                                st = _ttk.Style()
                                style_name = f"CCColorBtn_{color.replace('#','')}\.TButton"
                                try:
                                    st.lookup(style_name, 'foreground')
                                except Exception:
                                    st.configure(style_name, foreground=color)
                                btn_style = style_name
                            except Exception:
                                btn_style = 'Select.TButton'
                            ttk.Button(trow, text=tg, style=btn_style, command=lambda m=tg: self.select_model(m)).pack(side=tk.LEFT)
                    else:
                        ttk.Label(self.model_scroll_frame, text="Assigned: None", style='Config.TLabel', foreground='#bbbbbb').pack(fill=tk.X, padx=32)

        # Unassigned section
        un_header = ttk.Frame(self.model_scroll_frame, style='Category.TFrame')
        un_header.pack(fill=tk.X, pady=(10,4))
        un_btn = ttk.Button(un_header, text=("▼" if self.cc_unassigned_expanded else "▶"), width=2, style='Select.TButton', command=self._toggle_cc_unassigned)
        un_btn.pack(side=tk.LEFT, padx=(0,5))
        ttk.Label(un_header, text="🗂️ Unassigned", font=("Arial", 11, "bold"), style='CategoryPanel.TLabel').pack(side=tk.LEFT)

        if self.cc_unassigned_expanded:
            # Any model not assigned in either tag_index or assignments map is unassigned
            assigned_tags = set(tag_index.keys())
            for tags in assigned_by_variant.values():
                for t in (tags or []):
                    assigned_tags.add(t)
            unassigned = [m for m in models if m not in assigned_tags]
            if not unassigned:
                ttk.Label(self.model_scroll_frame, text="No unassigned models", style='Config.TLabel').pack(fill=tk.X, padx=10)
            else:
                for m in sorted(unassigned):
                    ttk.Button(self.model_scroll_frame, text=m, command=lambda mm=m: self.select_model(mm), style='Category.TButton').pack(fill=tk.X, padx=20, pady=1)

    def _toggle_cc_collections(self):
        self.cc_collections_expanded = not self.cc_collections_expanded
        self.refresh_model_list()

    def _toggle_right_panel_lock(self):
        try:
            self._right_panel_locked = not getattr(self, '_right_panel_locked', False)
            # Measure current width of the right pane area
            # Measure current right pane width reliably
            try:
                width = int(self._right_pane_widget.winfo_width()) if hasattr(self, '_right_pane_widget') else None
            except Exception:
                width = None
            if not width:
                try:
                    # Fallback: compute from total width minus sash position
                    pw_w = max(self._outer_pw.winfo_width(), 1)
                    sash = int(self._outer_pw.sashpos(0))
                    width = max(260, pw_w - sash)
                except Exception:
                    width = 340
            self._right_panel_width = int(width)
            if hasattr(self, '_right_lock_btn'):
                self._right_lock_btn.config(text=("🔒" if self._right_panel_locked else "🔓"))
            # Persist to backend settings
            self._backend_settings['right_panel_locked'] = bool(self._right_panel_locked)
            self._backend_settings['right_panel_width'] = int(self._right_panel_width)
            try:
                import json
                self._settings_path.write_text(json.dumps(self._backend_settings, indent=2))
            except Exception:
                pass
            # Apply behavior
            self._apply_right_lock_state()
        except Exception:
            pass

    def _apply_right_lock_state(self):
        try:
            if getattr(self, '_right_panel_locked', False):
                # Disable drag interactions and sash cursor
                try:
                    self._outer_pw.configure(cursor='arrow')
                except Exception:
                    pass
                def _block(event):
                    return 'break'
                # Bind block handlers
                for seq in ('<ButtonPress-1>', '<B1-Motion>', '<ButtonRelease-1>'):
                    self._outer_pw.bind(seq, _block)
                # Enforce current width immediately
                try:
                    pw_w = max(self._outer_pw.winfo_width(), 800)
                    width = max(260, int(getattr(self, '_right_panel_width', 340)))
                    pos = pw_w - width
                    self._outer_pw.sashpos(0, max(500, min(pos, pw_w - 260)))
                except Exception:
                    pass
            else:
                # Re-enable default behavior
                try:
                    self._outer_pw.configure(cursor='')
                except Exception:
                    pass
                for seq in ('<ButtonPress-1>', '<B1-Motion>', '<ButtonRelease-1>'):
                    try:
                        self._outer_pw.unbind(seq)
                    except Exception:
                        pass
        except Exception:
            pass

    def _toggle_cc_unassigned(self):
        self.cc_unassigned_expanded = not self.cc_unassigned_expanded
        self.refresh_model_list()

    def _toggle_cc_variant(self, vid: str):
        self.cc_variant_expanded[vid] = not self.cc_variant_expanded.get(vid, False)
        self.refresh_model_list()

    def select_model(self, model_name):
        """Handle model selection"""
        log_message(f"CUSTOM_CODE_TAB: Model selected: {model_name}")

        # Update chat interface with selected model
        if hasattr(self, 'chat_interface') and self.chat_interface:
            try:
                self.chat_interface.set_model(model_name)
                # Ensure UI reflects selection even if inner flow was bypassed
                if hasattr(self.chat_interface, '_set_model_label_with_class_color'):
                    self.chat_interface._set_model_label_with_class_color(model_name)
                if hasattr(self.chat_interface, '_update_mount_button_style'):
                    self.chat_interface._update_mount_button_style(mounted=False)
                if hasattr(self.chat_interface, 'mount_btn'):
                    self.chat_interface.mount_btn.config(state=tk.NORMAL)
            except Exception as e:
                log_message(f"CUSTOM_CODE_TAB ERROR: set_model failed: {e}")

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

        # Persist pane lock/width
        try:
            self._backend_settings['right_panel_locked'] = bool(self._right_panel_locked)
            self._backend_settings['right_panel_width'] = int(getattr(self, '_right_panel_width', 340))
            import json
            self._settings_path.write_text(json.dumps(self._backend_settings, indent=2))
        except Exception:
            pass

        # Close the application
        self.root.destroy()

    def refresh_tab(self):
        """Refresh the entire tab"""
        log_message("CUSTOM_CODE_TAB: Refreshing tab...")
        self.refresh_model_list()
        if hasattr(self, 'chat_interface') and self.chat_interface:
            self.chat_interface.refresh()
