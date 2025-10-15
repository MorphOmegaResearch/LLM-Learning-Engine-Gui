# [SYSTEM: GUI | VERSION: 1.9f | STATUS: ACTIVE]
"""
Chat Interface Tab - Interactive chat with Ollama models
Provides a simple chat interface to test and interact with models
"""

import tkinter as tk
from tkinter import ttk, scrolledtext
import subprocess
import re
import random
import json
import threading
from pathlib import Path
import sys
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from tabs.base_tab import BaseTab
from logger_util import log_message
from tabs.custom_code_tab.rag_service import RagService


class ChatInterfaceTab(BaseTab):
    """Chat interface for interacting with Ollama models"""

    def __init__(self, parent, root, style, parent_tab):
        super().__init__(parent, root, style)
        self.parent_tab = parent_tab
        self.current_model = None
        self.chat_history = []
        self.is_generating = False
        self.is_mounted = False
        self.is_standard_mode = False
        self.training_mode_enabled = False
        self.realtime_eval_scores = {}
        self.conversation_histories = {}  # {model_name: [chat_history]}
        self.last_user_message = ""  # Track for tool call validation

        # Ephemeral ThinkTime for next input (seconds)
        self._think_next_min = None
        self._think_next_max = None
        # Quick indicators internal state
        self._qa_state_key = None
        self._tooltip_active = False
        # Show Thoughts (streaming preview) toggle
        self.show_thoughts = False
        # RAG per chat (default OFF) and save-per-session flag
        self.rag_enabled = False
        self.rag_save_session = False
        # Track QA settings changes to prompt on exit/switch
        self._qa_settings_dirty = False
        # Track if chat content changed (unsaved)
        self._chat_dirty = False

        # Load backend settings first
        self.backend_settings = self.load_backend_settings()

        # Session temperature
        self.session_temperature = self.backend_settings.get('temperature', 0.8)
        # Temperature mode (manual/auto)
        try:
            self.temp_mode = str(self.backend_settings.get('temp_mode', 'manual')).lower()
            if self.temp_mode not in ('manual', 'auto'):
                self.temp_mode = 'manual'
        except Exception:
            self.temp_mode = 'manual'

        # Panel-wide RAG level (0=OFF, 1=standard, 2=+, 3=++)
        try:
            self.panel_rag_level = int(self.backend_settings.get('panel_rag_level_chat', 0))
        except Exception:
            self.panel_rag_level = 0

        # Current mode (persisted in mode_settings.json)
        self.current_mode = 'smart'
        try:
            mode_settings_file = Path(__file__).parent.parent / "mode_settings.json"
            if mode_settings_file.exists():
                with open(mode_settings_file, 'r') as _f:
                    _m = json.load(_f)
                self.current_mode = _m.get('current_mode', 'smart')
        except Exception:
            self.current_mode = 'smart'

        # Tool execution
        self.tool_executor = None
        self.initialize_tool_executor()

        # Tool call logging and detection
        self.tool_call_logger = None
        self.tool_call_detector = None
        self.initialize_tool_logging()

        # Chat history management
        self.chat_history_manager = None
        self.current_session_id = None
        self.initialize_history_manager()
        # RAG service and debug
        try:
            self.rag_service = RagService(self.chat_history_manager, None)
            # Apply retrieval params from backend settings
            try:
                rk1 = float(self.backend_settings.get('rag_k1', 1.2))
                rb = float(self.backend_settings.get('rag_b', 0.75))
                rdd = float(self.backend_settings.get('rag_decay_days', 3.0))
                self.rag_service.set_params(k1=rk1, b=rb, decay_days=rdd)
            except Exception:
                pass
            # Try to load persisted global index (non-fatal)
            self.rag_service.load_global_index()
        except Exception:
            self.rag_service = RagService()
        # Auto-training trigger state
        try:
            self.rag_autotrain_enabled = bool(self.backend_settings.get('rag_autotrain_enabled', False))
            self.rag_autotrain_window = int(self.backend_settings.get('rag_autotrain_window', 5))
            self.rag_autotrain_threshold = float(self.backend_settings.get('rag_autotrain_threshold', 0.7))
            self.rag_autotrain_require_promotion_gate = bool(self.backend_settings.get('rag_autotrain_require_promotion_gate', True))
            self.rag_autotrain_backend_override = bool(self.backend_settings.get('rag_autotrain_backend_override', False))
            self.class_promotion_earned = bool(self.backend_settings.get('class_promotion_earned', False))
            self.rag_project_adapters = list(self.backend_settings.get('rag_project_adapters', []))
        except Exception:
            self.rag_autotrain_enabled = False
            self.rag_autotrain_window = 5
            self.rag_autotrain_threshold = 0.7
            self.rag_autotrain_require_promotion_gate = True
            self.rag_autotrain_backend_override = False
            self.class_promotion_earned = False
            self.rag_project_adapters = []
        self._rag_recent_scores = []
        self._rag_last_trigger_ts = 0
        try:
            self.rag_debug_enabled = bool(self.backend_settings.get('rag_debug', False))
        except Exception:
            self.rag_debug_enabled = False

        # Load advanced settings
        self.advanced_settings = self.load_advanced_settings()

        # System Prompt and Tool Schema management
        self.current_system_prompt = "default"
        self.current_tool_schema = "default"
        self.system_prompts_dir = Path(__file__).parent.parent / "system_prompts"
        self.tool_schemas_dir = Path(__file__).parent.parent / "tool_schemas_configs"
        self._ensure_prompt_schema_dirs()

        # Initialize advanced components (all based on settings)
        self.initialize_advanced_components()
        # Wire optional context scorer to RAG service and prime index
        try:
            if hasattr(self, 'context_scorer') and self.context_scorer:
                self.rag_service.set_context_scorer(self.context_scorer)
            self.rag_service.refresh_index_global()
        except Exception:
            pass

    def update_session_temp_label(self, value):
        self.session_temperature = round(float(value), 1)
        try:
            if getattr(self, 'session_temp_label', None):
                self.session_temp_label.config(text=f"Temp: {self.session_temperature:.1f}")
        except Exception:
            pass
        # Persist when manual mode
        if getattr(self, 'temp_mode', 'manual') == 'manual':
            try:
                self._save_backend_setting('temperature', float(self.session_temperature))
            except Exception:
                pass

    def create_ui(self):
        """Create the chat interface UI"""
        log_message("CHAT_INTERFACE: Creating UI...")

        # Use a PanedWindow to allow left conversations list and right chat area to be resizable
        pw = ttk.Panedwindow(self.parent, orient=tk.HORIZONTAL)
        pw.grid(row=0, column=0, sticky=tk.NSEW)
        self._chat_pane = pw
        self.parent.columnconfigure(0, weight=1)
        self.parent.rowconfigure(0, weight=1)

        # Left: Conversations list sidebar
        self.conv_sidebar = ttk.Frame(pw, width=240, style='Category.TFrame')
        self.conv_sidebar.columnconfigure(0, weight=1)
        self.conv_sidebar.rowconfigure(1, weight=1)
        self._build_conversations_sidebar(self.conv_sidebar)

        # Right: Chat main container
        self.chat_container = ttk.Frame(pw, style='Category.TFrame')
        self.chat_container.columnconfigure(0, weight=1)
        self.chat_container.rowconfigure(1, weight=1)

        # Top controls in chat_container
        self.create_top_controls(self.chat_container)
        # Middle chat display
        self.create_chat_display(self.chat_container)
        # Bottom input
        self.create_input_area(self.chat_container)

        pw.add(self.conv_sidebar, weight=0)
        pw.add(self.chat_container, weight=1)
        try:
            pw.paneconfigure(self.conv_sidebar, minsize=160)
            pw.paneconfigure(self.chat_container, minsize=400)
        except Exception:
            pass
        # Default sidebar width ~240px or last saved width
        try:
            def _set_inner_sash():
                try:
                    self.parent.update_idletasks()
                    try:
                        w = int(self.backend_settings.get('conv_width', 240))
                    except Exception:
                        w = 240
                    self._chat_pane.sashpos(0, max(160, min(360, w)))
                except Exception:
                    pass
            self.root.after(50, _set_inner_sash)
        except Exception:
            pass
        # Keep locked width on parent resizes
        pw.bind('<Configure>', self._enforce_conv_width)
        # Apply initial lock behavior (disable drag + arrow when locked)
        self._apply_conv_lock_state()

        log_message("CHAT_INTERFACE: UI created successfully")
        # Listen for training lifecycle to show simple status popups
        try:
            self.root.bind("<<TrainingSessionStarted>>", self._on_training_started)
            self.root.bind("<<TrainingSessionComplete>>", self._on_training_complete)
            self.root.bind("<<TrainingProgressUpdate>>", self._on_training_progress)
        except Exception:
            pass

    def create_top_controls(self, parent):
        """Create top control bar with model info and actions"""
        controls_frame = ttk.Frame(parent, style='Category.TFrame')
        controls_frame.grid(row=0, column=0, sticky=tk.EW, padx=10, pady=(10, 5))
        controls_frame.columnconfigure(1, weight=1)

        # Model label
        ttk.Label(
            controls_frame,
            text="Active Model:",
            style='Config.TLabel',
            font=("Arial", 10, "bold")
        ).grid(row=0, column=0, sticky=tk.W, padx=(5, 10))

        # Model name display (with color indicator for mount status)
        self.model_label = tk.Label(
            controls_frame,
            text="No model selected",
            font=("Arial", 10),
            bg='#2b2b2b',
            fg='#ffffff'
        )
        self.model_label.grid(row=0, column=1, sticky=tk.W, padx=(0, 10))

        # Temperature controls moved to Quick Actions; header indicators removed.
        self.session_temp_label = None
        self.session_temperature_var = tk.DoubleVar(value=self.backend_settings.get('temperature', 0.8))
        self.session_temp_scale = None

        # (Prompt/Schema, Change Dir and Mode moved to Quick Actions gear)
        # Top action buttons (Mount/Dismount/New Chat/Delete Chat) + Quick Actions + indicators
        # Place inside the controls row so they're vertically centered between borders
        top_actions = ttk.Frame(controls_frame, style='Category.TFrame')
        top_actions.grid(row=0, column=4, sticky=tk.E, padx=(0, 10))
        self.mount_btn = ttk.Button(top_actions, text="📌 Mount", command=self.mount_model, style='Action.TButton', state=tk.DISABLED)
        self.mount_btn.pack(side=tk.LEFT, padx=(0,5))
        self.dismount_btn = ttk.Button(top_actions, text="📍 Dismount", command=self.dismount_model, style='Select.TButton', state=tk.DISABLED)
        self.dismount_btn.pack(side=tk.LEFT, padx=(0,5))
        ttk.Button(top_actions, text="🆕 New Chat", command=self.new_chat, style='Action.TButton').pack(side=tk.LEFT, padx=(0,5))
        ttk.Button(top_actions, text="🗑 Delete Chat", command=self.delete_current_chat, style='Select.TButton').pack(side=tk.LEFT, padx=(0,5))

    def open_todo_list(self):
        """Open the Settings tab ToDo popup from Chat quick actions."""
        try:
            # Access settings tab instance via parent_tab.tab_instances
            tab_map = getattr(self.parent_tab, 'tab_instances', None)
            if not tab_map and hasattr(self.parent_tab, 'parent'):
                tab_map = getattr(self.parent_tab.parent, 'tab_instances', None)
            settings_meta = None
            if isinstance(tab_map, dict):
                settings_meta = tab_map.get('settings_tab')
            settings_inst = settings_meta.get('instance') if settings_meta else None
            if settings_inst and hasattr(settings_inst, 'show_todo_popup'):
                settings_inst.show_todo_popup()
            else:
                # Graceful fallback: no settings instance available
                from tkinter import messagebox
                messagebox.showinfo("ToDo List", "Settings tab is not available.")
        except Exception:
            try:
                from tkinter import messagebox
                messagebox.showerror("ToDo Error", "Failed to open ToDo list.")
            except Exception:
                pass

    def open_temp_mode_selector(self):
        try:
            win = tk.Toplevel(self.root)
            win.title('Temperature Mode')
            win.resizable(False, False)
            container = ttk.Frame(win, padding=8)
            container.pack(fill=tk.BOTH, expand=True)

            body = ttk.Frame(container)
            body.pack(fill=tk.BOTH, expand=True)

            def show_select():
                for w in body.winfo_children():
                    w.destroy()
                ttk.Label(body, text='Select Temperature Mode', style='CategoryPanel.TLabel').grid(row=0, column=0, columnspan=2, pady=(0,6))
                ttk.Button(body, text='Manual', style='Action.TButton', command=show_manual).grid(row=1, column=0, padx=6, pady=6, sticky=tk.EW)
                def set_auto():
                    self.temp_mode = 'auto'
                    try:
                        self._save_backend_setting('temp_mode', 'auto')
                    except Exception:
                        pass
                    self._apply_temp_mode_visibility()
                    self._apply_auto_temperature_adjustment(source='mode_switch')
                    try:
                        self._update_quick_indicators()
                    except Exception:
                        pass
                    win.destroy()
                ttk.Button(body, text='Auto', style='Action.TButton', command=set_auto).grid(row=1, column=1, padx=6, pady=6, sticky=tk.EW)

            def show_manual():
                for w in body.winfo_children():
                    w.destroy()
                ttk.Label(body, text='Manual Temperature', style='CategoryPanel.TLabel').grid(row=0, column=0, columnspan=2, pady=(0,6))
                # Slider
                temp_var = tk.DoubleVar(value=float(self.session_temperature))
                scale = ttk.Scale(body, from_=0.0, to=2.0, orient=tk.HORIZONTAL, variable=temp_var, length=220)
                scale.grid(row=1, column=0, columnspan=2, sticky=tk.EW, padx=6, pady=6)
                val_lbl = ttk.Label(body, text=f"{float(self.session_temperature):.1f}", style='Config.TLabel')
                val_lbl.grid(row=2, column=0, sticky=tk.W, padx=6)
                def on_change(_=None):
                    try: val_lbl.config(text=f"{float(temp_var.get()):.1f}")
                    except Exception: pass
                try:
                    scale.configure(command=lambda v: on_change())
                except Exception:
                    pass
                # Buttons
                def apply_manual():
                    try:
                        self.temp_mode = 'manual'
                        self.session_temperature = round(float(temp_var.get()), 1)
                        self.session_temperature_var.set(self.session_temperature)
                        self.session_temp_label.config(text=f"Temp: {self.session_temperature:.1f}")
                        self._save_backend_setting('temp_mode', 'manual')
                        self._save_backend_setting('temperature', float(self.session_temperature))
                        try:
                            self._update_quick_indicators()
                        except Exception:
                            pass
                    except Exception:
                        pass
                    win.destroy()
                ttk.Button(body, text='Set Temp', style='Action.TButton', command=apply_manual).grid(row=3, column=0, padx=6, pady=6, sticky=tk.W)
                ttk.Button(body, text='Back', style='Select.TButton', command=show_select).grid(row=3, column=1, padx=6, pady=6, sticky=tk.E)

            show_select()
            try:
                win.transient(self.root); win.lift(); win.attributes('-topmost', True); self.root.after(300, lambda: win.attributes('-topmost', False))
            except Exception:
                pass
        except Exception:
            pass

    def _apply_temp_mode_visibility(self):
        try:
            # Always hide header slider; we use popup for manual
            if hasattr(self, 'session_temp_scale') and self.session_temp_scale:
                try:
                    self.session_temp_scale.grid_remove()
                except Exception:
                    pass
        except Exception:
            pass

    def _apply_auto_temperature_adjustment(self, source='auto'):
        try:
            if getattr(self, 'temp_mode', 'manual') != 'auto':
                return
            model = (self.current_model or '').strip()
            success = 0; failure = 0
            stats = self.realtime_eval_scores.get(model, {}) if hasattr(self, 'realtime_eval_scores') else {}
            for s in stats.values():
                success += int(s.get('success', 0)); failure += int(s.get('failure', 0))
            total = success + failure
            rec = 0.8
            if total >= 5:
                ratio = success / max(1, total)
                if ratio < 0.5:
                    rec = 0.4
                elif ratio < 0.7:
                    rec = 0.6
                elif ratio > 0.85:
                    rec = 1.0
                else:
                    rec = 0.8
            self.session_temperature = round(rec, 1)
            try:
                self.session_temperature_var.set(self.session_temperature)
            except Exception:
                pass
            self.session_temp_label.config(text=f"Temp: {self.session_temperature:.1f}")
            log_message(f"CHAT_INTERFACE: Auto temperature set to {self.session_temperature:.1f} (source={source}, stats={success}/{total})")
        except Exception:
            pass

    def create_chat_display(self, parent):
        """Create the chat message display area"""
        display_frame = ttk.Frame(parent, style='Category.TFrame')
        display_frame.grid(row=1, column=0, sticky=tk.NSEW, padx=10, pady=5)
        display_frame.columnconfigure(0, weight=1)
        display_frame.rowconfigure(0, weight=1)

        # Scrolled text widget for chat
        self.chat_display = scrolledtext.ScrolledText(
            display_frame,
            wrap=tk.WORD,
            font=("Arial", 10),
            state=tk.DISABLED,
            relief='flat',
            borderwidth=0,
            highlightthickness=1,
            highlightbackground='#454545',
            bg='#1e1e1e',
            fg='#ffffff',
            insertbackground='#61dafb'
        )
        self.chat_display.grid(row=0, column=0, sticky=tk.NSEW)
        # Thought tag for streaming preview
        try:
            self.chat_display.tag_config('thought', foreground='#bbbbbb', font=("Arial", 9, "italic"))
        except Exception:
            pass

    def _build_conversations_sidebar(self, parent):
        header = ttk.Frame(parent, style='Category.TFrame')
        header.grid(row=0, column=0, sticky=tk.EW, padx=8, pady=(8,4))
        ttk.Label(header, text='📚 Conversations', style='CategoryPanel.TLabel').pack(side=tk.LEFT)
        ttk.Button(header, text='↻', width=3, style='Select.TButton', command=self._refresh_conversations_list).pack(side=tk.RIGHT)
        self._conv_lock_btn = ttk.Button(header, text=('🔒' if self.backend_settings.get('conv_locked', False) else '🔓'), width=3, style='Select.TButton', command=self._toggle_conv_lock)
        self._conv_lock_btn.pack(side=tk.RIGHT, padx=(4,0))

        # Treeview + scrollbar (categorized by time)
        list_frame = ttk.Frame(parent, style='Category.TFrame')
        list_frame.grid(row=1, column=0, sticky=tk.NSEW, padx=8, pady=(0,8))
        list_frame.columnconfigure(0, weight=1)
        list_frame.rowconfigure(0, weight=1)
        sb = ttk.Scrollbar(list_frame, orient='vertical')
        sb.grid(row=0, column=1, sticky=tk.NS)
        self.conv_tree = ttk.Treeview(list_frame, yscrollcommand=sb.set, selectmode='browse')
        self.conv_tree.grid(row=0, column=0, sticky=tk.NSEW)
        sb.config(command=self.conv_tree.yview)
        self.conv_tree.heading('#0', text='Structure')
        # Styling
        try:
            st = ttk.Style()
            st.configure('Treeview', background='#2b2b2b', fieldbackground='#2b2b2b', foreground='#ffffff')
            st.map('Treeview', background=[('selected','#3a3a3a')], foreground=[('selected','#61dafb')])
        except Exception:
            pass
        self.conv_tree.bind('<Double-Button-1>', self._on_open_selected_conversation)
        self.conv_tree.bind('<<TreeviewSelect>>', self._on_conv_selected)

        # Bottom action buttons
        actions = ttk.Frame(parent, style='Category.TFrame')
        actions.grid(row=2, column=0, sticky=tk.EW, padx=8, pady=(0,4))
        actions.columnconfigure(0, weight=1)
        actions.columnconfigure(1, weight=1)
        ttk.Button(actions, text='Open Chat', style='Action.TButton', command=self._open_selected_chat).grid(row=0, column=0, sticky=tk.EW, padx=(0,4))
        ttk.Button(actions, text='Delete Chat', style='Select.TButton', command=self._delete_selected_chat).grid(row=0, column=1, sticky=tk.EW, padx=(4,0))
        # New: Rename Chat button (prompts for new name for selected session)
        try:
            ttk.Button(actions, text='Rename Chat', style='Select.TButton', command=self._rename_selected_chat).grid(row=1, column=0, columnspan=2, sticky=tk.EW, pady=(4,0))
        except Exception:
            pass

        # Panel-wide RAG controls (incremental: 🧠, 🧠+, 🧠++)
        rag_bar = ttk.Frame(parent, style='Category.TFrame')
        rag_bar.grid(row=3, column=0, sticky=tk.EW, padx=8, pady=(0,4))
        rag_bar.columnconfigure(0, weight=1)
        rag_bar.columnconfigure(1, weight=1)
        rag_bar.columnconfigure(2, weight=1)

        def set_rag_level(level: int):
            try:
                cur = int(getattr(self, 'panel_rag_level', 0))
            except Exception:
                cur = 0
            # Toggle behavior: clicking current highest level turns OFF
            if level == cur:
                new_level = 0
            else:
                new_level = level
            self.panel_rag_level = new_level
            # Persist to backend settings
            try:
                self._save_backend_setting('panel_rag_level_chat', new_level)
            except Exception:
                pass
            # Update button styles and indicators
            _update_rag_buttons()
            try:
                self._update_quick_indicators()
            except Exception:
                pass

        def _btn_style(active: bool) -> str:
            return 'Action.TButton' if active else 'Select.TButton'

        self._rag_btn_lvl1 = ttk.Button(rag_bar, text='🧠', style=_btn_style(False), command=lambda: set_rag_level(1))
        self._rag_btn_lvl2 = ttk.Button(rag_bar, text='🧠+', style=_btn_style(False), command=lambda: set_rag_level(2))
        self._rag_btn_lvl3 = ttk.Button(rag_bar, text='🧠++', style=_btn_style(False), command=lambda: set_rag_level(3))
        self._rag_btn_lvl1.grid(row=0, column=0, sticky=tk.EW, padx=(0,4))
        self._rag_btn_lvl2.grid(row=0, column=1, sticky=tk.EW, padx=4)
        self._rag_btn_lvl3.grid(row=0, column=2, sticky=tk.EW, padx=(4,0))

        # Hint label for hover
        self._rag_hint_label = ttk.Label(parent, text='', style='Config.TLabel')
        self._rag_hint_label.grid(row=4, column=0, sticky=tk.W, padx=12, pady=(0,6))

        def _set_hint(text:str=''):
            try:
                self._rag_hint_label.config(text=text)
            except Exception:
                pass

        def _update_rag_buttons():
            lvl = int(getattr(self, 'panel_rag_level', 0) or 0)
            try:
                self._rag_btn_lvl1.configure(style=_btn_style(lvl >= 1))
                self._rag_btn_lvl2.configure(style=_btn_style(lvl >= 2))
                self._rag_btn_lvl3.configure(style=_btn_style(lvl >= 3))
            except Exception:
                pass

        _update_rag_buttons()
        # Hover descriptions
        try:
            self._rag_btn_lvl1.bind('<Enter>', lambda e: _set_hint('L1: Conservative retrieval (≈2 snippets, ~1200 chars). Click again to turn OFF.'))
            self._rag_btn_lvl2.bind('<Enter>', lambda e: _set_hint('L2: Balanced retrieval (≈4 snippets, ~2400 chars).'))
            self._rag_btn_lvl3.bind('<Enter>', lambda e: _set_hint('L3: Max retrieval (≈6 snippets, ~3600 chars).'))
            for b in (self._rag_btn_lvl1, self._rag_btn_lvl2, self._rag_btn_lvl3):
                b.bind('<Leave>', lambda e: _set_hint(''))
        except Exception:
            pass

        # Optional quick toggle for RAG DEBUG
        try:
            cur_dbg = bool(getattr(self, 'rag_debug_enabled', False))
        except Exception:
            cur_dbg = False
        self._rag_debug_var = tk.BooleanVar(value=cur_dbg)
        def _toggle_rag_debug():
            try:
                self.rag_debug_enabled = bool(self._rag_debug_var.get())
                self._save_backend_setting('rag_debug', self.rag_debug_enabled)
            except Exception:
                pass
        dbg_row = ttk.Frame(parent, style='Category.TFrame')
        dbg_row.grid(row=5, column=0, sticky=tk.EW, padx=8, pady=(0,8))
        ttk.Checkbutton(dbg_row, text='RAG DEBUG', variable=self._rag_debug_var, command=_toggle_rag_debug, style='TCheckbutton').pack(side=tk.LEFT)
        # RAG Details button (opens preview dialog)
        ttk.Button(dbg_row, text='🔍 RAG Details', style='Select.TButton', command=self._open_rag_details).pack(side=tk.RIGHT)

    def _open_rag_details(self):
        try:
            dlg = tk.Toplevel(self.root)
            dlg.title('RAG Details')
            dlg.geometry('800x520')
            dlg.transient(self.root)
            container = ttk.Frame(dlg, padding=8)
            container.pack(fill=tk.BOTH, expand=True)

            top = ttk.Frame(container)
            top.pack(fill=tk.X)
            ttk.Label(top, text='Query:', style='Config.TLabel').pack(side=tk.LEFT)
            qvar = tk.StringVar(value=self.last_user_message or '')
            qent = ttk.Entry(top, textvariable=qvar, width=80)
            qent.pack(side=tk.LEFT, padx=6)
            scope_var = tk.BooleanVar(value=bool(getattr(self, 'current_project', None)))
            ttk.Checkbutton(top, text='Use Project Scope', variable=scope_var, style='TCheckbutton').pack(side=tk.LEFT, padx=6)
            out = scrolledtext.ScrolledText(container, wrap=tk.WORD, font=("Courier", 9), bg='#1e1e1e', fg='#ffffff')
            out.pack(fill=tk.BOTH, expand=True, pady=(8,0))

            def run_query():
                try:
                    query = qvar.get().strip()
                    out.config(state=tk.NORMAL)
                    out.delete(1.0, tk.END)
                    if not query:
                        out.insert(tk.END, 'Enter a query above.')
                        out.config(state=tk.DISABLED)
                        return
                    # Ensure indexes ready
                    if scope_var.get() and getattr(self, 'current_project', None):
                        self.rag_service.refresh_index_project(self.current_project)
                        results = self.rag_service.query(query, top_k=6, scope=self.current_project)
                    else:
                        self.rag_service.refresh_index_global()
                        results = self.rag_service.query(query, top_k=6, scope=None)
                    if not results:
                        out.insert(tk.END, 'No results.')
                        out.config(state=tk.DISABLED)
                        return
                    for i, (doc, score) in enumerate(results, 1):
                        out.insert(tk.END, f"[{i}] session={doc.session_id} role={doc.role} idx={doc.index} score={score:.3f}\n")
                        out.insert(tk.END, (doc.text or '')[:600] + '\n\n')
                    out.config(state=tk.DISABLED)
                except Exception:
                    try:
                        out.insert(tk.END, 'Error during retrieval.')
                        out.config(state=tk.DISABLED)
                    except Exception:
                        pass
            btns = ttk.Frame(container)
            btns.pack(fill=tk.X, pady=(6,0))
            ttk.Button(btns, text='Run', style='Action.TButton', command=run_query).pack(side=tk.LEFT)
            ttk.Button(btns, text='Close', style='Select.TButton', command=dlg.destroy).pack(side=tk.RIGHT)
            # Autofocus and initial run
            qent.focus_set()
            run_query()
        except Exception:
            pass

        self._refresh_conversations_list()
        # Schedule refreshes to avoid startup race conditions
        try:
            self.root.after_idle(self._refresh_conversations_list)
            self.root.after(400, self._refresh_conversations_list)
        except Exception:
            pass

    def _refresh_conversations_list(self):
        try:
            if not self.chat_history_manager:
                log_message("CHAT_INTERFACE: No ChatHistoryManager; conversations cannot be listed.")
                return
            from datetime import datetime, timedelta
            items = self.chat_history_manager.list_conversations()
            self._conv_items = items
            try:
                hist_dir = getattr(self.chat_history_manager, 'history_dir', None)
                log_message(f"CHAT_INTERFACE: Loaded {len(items)} conversations from {hist_dir}")
                if getattr(self, 'rag_debug_enabled', False):
                    try:
                        self.add_message('system', f"🧠 RAG DEBUG: Conversations loaded = {len(items)}\nPath: {hist_dir}")
                    except Exception:
                        pass
            except Exception:
                pass
            # Clear tree
            for it in self.conv_tree.get_children():
                self.conv_tree.delete(it)
            now = datetime.now()
            def parse_dt(s):
                try:
                    return datetime.fromisoformat(s)
                except Exception:
                    return None
            # Buckets
            latest_today = []
            week = []
            month = []
            year = []
            for rec in items:
                dt = parse_dt(rec.get('saved_at',''))
                if not dt:
                    continue
                age = now - dt
                if dt.date() == now.date():
                    latest_today.append(rec)
                elif age <= timedelta(days=7):
                    week.append(rec)
                elif age <= timedelta(days=30):
                    month.append(rec)
                elif age <= timedelta(days=365):
                    year.append(rec)
            # Year
            year_node = self.conv_tree.insert('', 'end', text=f"Year ({len(year)})", open=False, values=('category','year'))
            for rec in year:
                self.conv_tree.insert(year_node, 'end', text=f"{rec.get('saved_at','')[:16]}  {rec.get('session_id','')}", values=('session',rec.get('session_id','')))
            # Month
            month_node = self.conv_tree.insert('', 'end', text=f"Month ({len(month)})", open=False, values=('category','month'))
            for rec in month:
                self.conv_tree.insert(month_node, 'end', text=f"{rec.get('saved_at','')[:16]}  {rec.get('session_id','')}", values=('session',rec.get('session_id','')))
            # Week
            week_node = self.conv_tree.insert('', 'end', text=f"Week ({len(week)})", open=False, values=('category','week'))
            for rec in week:
                self.conv_tree.insert(week_node, 'end', text=f"{rec.get('saved_at','')[:16]}  {rec.get('session_id','')}", values=('session',rec.get('session_id','')))
            # Latest (days of week)
            latest_node = self.conv_tree.insert('', 'end', text="Latest", open=True, values=('category','latest'))
            # Build days starting with today
            weekdays = ['Mon','Tue','Wed','Thu','Fri','Sat','Sun']
            today_idx = now.weekday() # 0=Mon
            ordered = [weekdays[today_idx]] + [w for i,w in enumerate(weekdays) if i!=today_idx]
            # Map recs by weekday name
            def dow_name(dt):
                return weekdays[dt.weekday()]
            by_day = {w: [] for w in weekdays}
            for rec in latest_today:
                dt = parse_dt(rec.get('saved_at',''))
                if dt:
                    by_day[dow_name(dt)].append(rec)
            # Limit current day to latest 15
            for w in ordered:
                label = w + (' (Today)' if w == weekdays[today_idx] else '')
                recs = by_day.get(w, [])
                if w == weekdays[today_idx]:
                    recs = recs[:15]
                node = self.conv_tree.insert(latest_node, 'end', text=f"{label} ({len(recs)})", open=(w==weekdays[today_idx]), values=('subcategory','latest_day'))
                for rec in recs:
                    self.conv_tree.insert(node, 'end', text=f"{rec.get('saved_at','')[11:16]}  {rec.get('session_id','')}", values=('session',rec.get('session_id','')))
            if len(items) == 0:
                # Friendly placeholder when no history yet
                self.conv_tree.insert(latest_node, 'end', text="(No conversations found)", values=('info',))
            # Expand top categories by default
            self.conv_tree.item(latest_node, open=True)
            # Highlight current session if present
            if self.current_session_id:
                for cat in self.conv_tree.get_children(''):
                    for sub in self.conv_tree.get_children(cat):
                        for leaf in self.conv_tree.get_children(sub):
                            sid = self.conv_tree.item(leaf,'values')
                            if isinstance(sid, (list,tuple)) and len(sid)>1 and sid[1]==self.current_session_id:
                                self.conv_tree.selection_set(leaf)
                                self.conv_tree.see(leaf)
                                raise StopIteration
        except Exception as e:
            log_message(f"CHAT_INTERFACE ERROR: Failed to refresh conversations: {e}")
            try:
                if getattr(self, 'rag_debug_enabled', False):
                    self.add_message('error', f"Conversations refresh failed: {e}")
            except Exception:
                pass

    def _open_selected_chat(self):
        try:
            sel = self.conv_tree.selection()
            if not sel:
                return
            vals = self.conv_tree.item(sel[0], 'values')
            if not vals or vals[0] != 'session':
                return
            session_id = vals[1]
            # simulate double-click open
            self._load_conversation_by_id(session_id)
        except Exception:
            pass

    def _rename_selected_chat(self):
        try:
            from tkinter import simpledialog, messagebox
            sel = self.conv_tree.selection()
            if not sel:
                messagebox.showinfo('Rename Chat', 'Select a conversation to rename.')
                return
            vals = self.conv_tree.item(sel[0], 'values')
            if not vals or vals[0] != 'session':
                messagebox.showinfo('Rename Chat', 'Select a conversation (not a category) to rename.')
                return
            session_id = vals[1]
            new_name = simpledialog.askstring('Rename Chat', f'Rename "{session_id}" to:')
            if not new_name or new_name.strip() == session_id:
                return
            ok = False
            try:
                ok = self.chat_history_manager.rename_conversation(session_id, new_name.strip())
            except Exception as e:
                messagebox.showerror('Rename Chat', f'Failed to rename: {e}')
                return
            if ok:
                # Update current session id if needed
                if getattr(self, 'current_session_id', None) == session_id:
                    self.current_session_id = new_name.strip()
                # Refresh list and notify
                try:
                    self._refresh_conversations_list()
                except Exception:
                    pass
                self.add_message('system', f'✓ Renamed chat to: {new_name.strip()}')
            else:
                messagebox.showerror('Rename Chat', 'Rename operation failed.')
        except Exception:
            pass

    def _load_conversation_by_id(self, session_id: str):
        """Load a conversation by id and update UI consistently."""
        try:
            if not self.chat_history_manager:
                return
            data = self.chat_history_manager.load_conversation(session_id)
            if not data:
                return
            # Restore per-session tool overrides if available
            try:
                meta = data.get('metadata') or {}
                sess = meta.get('session_tools')
                if isinstance(sess, dict):
                    self.session_enabled_tools = sess
            except Exception:
                pass
            # Confirm/reflect model
            model = (data.get('model_name') or '').strip()
            switched = False
            if model and model != (self.current_model or ''):
                chosen = self._confirm_switch_model(model)
                if chosen:
                    try:
                        if hasattr(self.parent_tab, 'select_model'):
                            self.parent_tab.select_model(chosen)
                        else:
                            self.set_model(chosen)
                    except Exception:
                        self.set_model(chosen)
                    switched = True
            if not switched and model:
                try:
                    self.current_model = model
                    self._set_model_label_with_class_color(model)
                    self._update_mount_button_style(mounted=False)
                    self.mount_btn.config(state=tk.NORMAL)
                except Exception:
                    pass
            # Load chat history and update UI
            self.chat_history = data.get('chat_history') or []
            self.current_session_id = session_id
            self.redisplay_conversation()
            self.add_message('system', f"✓ Loaded conversation: {session_id}")
        except Exception:
            pass

    def _delete_selected_chat(self):
        from tkinter import messagebox
        try:
            sel = self.conv_tree.selection()
            if not sel:
                return
            vals = self.conv_tree.item(sel[0], 'values')
            if not vals or vals[0] != 'session':
                return
            session_id = vals[1]
            if not messagebox.askyesno('Confirm Delete', f'Delete conversation?\n\n{session_id}'):
                return
            ok = self.chat_history_manager.delete_conversation(session_id)
            if ok:
                messagebox.showinfo('Deleted', 'Conversation deleted successfully')
                self._refresh_conversations_list()
            else:
                messagebox.showerror('Error', 'Failed to delete conversation')
        except Exception:
            pass

    def _on_conv_selected(self, event=None):
        try:
            sel = self.conv_tree.selection()
            if not sel:
                return
            vals = self.conv_tree.item(sel[0], 'values')
            if not vals or vals[0] != 'session':
                return
            session_id = vals[1]
            self._show_conv_quickview(session_id)
        except Exception:
            pass

    def _show_conv_quickview(self, session_id: str):
        # Destroy previous quickview
        try:
            if hasattr(self, '_conv_quickview') and self._conv_quickview and self._conv_quickview.winfo_exists():
                self._conv_quickview.destroy()
        except Exception:
            pass
        try:
            data = self.chat_history_manager.load_conversation(session_id)
            if not data:
                return
            top = tk.Toplevel(self.root)
            self._conv_quickview = top
            top.title('Chat Quick View')
            top.resizable(False, False)
            # Position near tree
            try:
                tx = self.conv_tree.winfo_rootx() + self.conv_tree.winfo_width() + 16
                ty = self.conv_tree.winfo_rooty() + 40
                top.geometry(f"460x380+{tx}+{ty}")
            except Exception:
                pass
            frm = ttk.Frame(top, padding=8)
            frm.pack(fill=tk.BOTH, expand=True)
            frm.columnconfigure(0, weight=1)
            # Header: Model color-coded and Parent Model line
            model = (data.get('model_name') or 'unknown').strip()
            parent_text, class_label, color = self._resolve_parent_and_class(model)
            header = f"{model}  <{class_label.capitalize()}>"
            ttk.Label(frm, text=header, font=('Arial', 11, 'bold'), foreground=color, style='CategoryPanel.TLabel').grid(row=0, column=0, sticky=tk.W)
            ttk.Label(frm, text=f"Parent Model: {parent_text}", style='Config.TLabel').grid(row=1, column=0, sticky=tk.W, pady=(0,6))
            # Last two user/assistant pairs
            hist = data.get('chat_history') or []
            pairs = []
            cur_user = None
            for msg in reversed(hist):
                role = msg.get('role')
                if role == 'assistant' and cur_user is not None:
                    pairs.append((cur_user, msg.get('content','')))
                    cur_user = None
                    if len(pairs) >= 2:
                        break
                elif role == 'user':
                    cur_user = msg.get('content','')
            box = scrolledtext.ScrolledText(frm, height=10, wrap=tk.WORD, font=('Arial', 9), bg='#1e1e1e', fg='#dcdcdc')
            box.grid(row=2, column=0, sticky=tk.EW)
            def _write_pair(u,a):
                box.insert(tk.END, 'You: ', 'u'); box.insert(tk.END, (u or '') + '\n')
                box.insert(tk.END, 'Model: ', 'a'); box.insert(tk.END, (a or '') + '\n\n')
            try:
                box.tag_config('u', foreground='#61dafb'); box.tag_config('a', foreground='#98c379')
            except Exception:
                pass
            for u,a in reversed(pairs):
                _write_pair(u,a)
            # Configuration
            meta = data.get('metadata') or {}
            cfg_lines = [
                f"Mode: {meta.get('mode','unknown')}",
                f"Temp: {meta.get('temperature','?')}",
                f"Temp Mode: {meta.get('temp_mode','manual')}",
                f"Prompt: {meta.get('system_prompt','default')}",
                f"Schema: {meta.get('tool_schema','default')}",
                f"Working Dir: {meta.get('working_directory','unknown')}",
                f"Training Mode: {bool(meta.get('training_data_collection', False))}",
                f"Session Tools: {len((meta.get('session_tools') or {})) if isinstance(meta.get('session_tools'), dict) else 'default'}",
            ]
            ttk.Label(frm, text='Configuration', font=('Arial', 10, 'bold'), style='CategoryPanel.TLabel').grid(row=3, column=0, sticky=tk.W, pady=(6,0))
            ttk.Label(frm, text='\n'.join(cfg_lines), style='Config.TLabel', justify=tk.LEFT).grid(row=4, column=0, sticky=tk.W)
            # Auto-dismiss on click-away
            def _maybe_close(e=None):
                """Close quickview on focus-out but keep current selection intact so Open Chat works."""
                try:
                    f = self.root.focus_get()
                    if not f or not str(f).startswith(str(top)):
                        top.destroy()
                except Exception:
                    pass
            top.bind('<FocusOut>', _maybe_close)
        except Exception:
            pass

    def _get_model_class_color(self, model_tag: str) -> str:
        try:
            import config as C
            color = '#bbbbbb'
            try:
                lid = C.get_lineage_for_tag(model_tag)
            except Exception:
                lid = None
            if lid:
                try:
                    for rec in (C.list_model_profiles() or []):
                        if rec.get('lineage_id') == lid:
                            cls = rec.get('type') or rec.get('class') or ''
                            # Map common classes to colors
                            cmap = {'coder':'#c792ea','researcher':'#82aaff'}
                            color = cmap.get(cls, '#61dafb')
                            break
                except Exception:
                    pass
            return color
        except Exception:
            return '#bbbbbb'

    def _resolve_parent_and_class(self, model_tag: str) -> tuple[str,str,str]:
        """Return (parent_model, class_label, color) for a model tag or variant id."""
        try:
            import config as C
            # 1) Direct variant profile
            try:
                mp = C.load_model_profile(model_tag)
                parent = mp.get('base_model') or ''
                class_label = (mp.get('class_level') or mp.get('class') or 'unassigned')
                return (parent or 'unknown', class_label, self._get_model_class_color(model_tag))
            except Exception:
                pass
            # 2) If tag -> lineage -> find variant
            try:
                lid = C.get_lineage_for_tag(model_tag)
                if lid:
                    for rec in (C.list_model_profiles() or []):
                        vid = rec.get('variant_id') or ''
                        if C.get_lineage_id(vid) == lid:
                            parent = rec.get('base_model') or 'unknown'
                            class_label = C.get_variant_class(vid) or 'unassigned'
                            return (parent, class_label, self._get_model_class_color(vid))
            except Exception:
                pass
        except Exception:
            pass
        return ('unknown', 'unassigned', '#bbbbbb')

    def _toggle_conv_lock(self):
        try:
            locked = bool(self.backend_settings.get('conv_locked', False))
            locked = not locked
            self.backend_settings['conv_locked'] = locked
            # Capture current width
            try:
                w = max(160, min(360, int(self.conv_sidebar.winfo_width())))
            except Exception:
                w = 240
            self.backend_settings['conv_width'] = w
            if hasattr(self, '_conv_lock_btn'):
                self._conv_lock_btn.config(text=('🔒' if locked else '🔓'))
            self._save_backend_settings()
            self._apply_conv_lock_state()
        except Exception:
            pass

    def _enforce_conv_width(self, event=None):
        try:
            if not bool(self.backend_settings.get('conv_locked', False)):
                return
            w = max(160, min(360, int(self.backend_settings.get('conv_width', 240))))
            try:
                # adjust sash to keep left pane at w
                self._chat_pane.sashpos(0, w)
            except Exception:
                pass
        except Exception:
            pass

    def _apply_conv_lock_state(self):
        try:
            if bool(self.backend_settings.get('conv_locked', False)):
                # Disable sash drag and cursor
                try:
                    self._chat_pane.configure(cursor='arrow')
                except Exception:
                    pass
                def _block(event):
                    return 'break'
                for seq in ('<ButtonPress-1>', '<B1-Motion>', '<ButtonRelease-1>'):
                    self._chat_pane.bind(seq, _block)
                # Enforce saved width
                self._enforce_conv_width()
            else:
                try:
                    self._chat_pane.configure(cursor='')
                except Exception:
                    pass
                for seq in ('<ButtonPress-1>', '<B1-Motion>', '<ButtonRelease-1>'):
                    try:
                        self._chat_pane.unbind(seq)
                    except Exception:
                        pass
        except Exception:
            pass

    def _save_backend_settings(self):
        try:
            from pathlib import Path
            import json
            settings_file = Path(__file__).parent.parent / 'custom_code_settings.json'
            existing = {}
            if settings_file.exists():
                try:
                    existing = json.loads(settings_file.read_text())
                except Exception:
                    existing = {}
            existing.update(self.backend_settings or {})
            settings_file.write_text(json.dumps(existing, indent=2))
        except Exception:
            pass

    def _on_open_selected_conversation(self, event=None):
        try:
            # Save QA settings per session if changed
            self._maybe_prompt_save_qa_settings('opening another chat')
            sel = self.conv_tree.selection() if hasattr(self, 'conv_tree') else []
            if not sel:
                return
            item = sel[0]
            vals = self.conv_tree.item(item, 'values')
            if not vals or vals[0] != 'session':
                return
            session_id = vals[1]
            data = self.chat_history_manager.load_conversation(session_id)
            if not data:
                return
            # Restore per-session tool overrides if available
            try:
                meta = data.get('metadata') or {}
                sess = meta.get('session_tools')
                if isinstance(sess, dict):
                    self.session_enabled_tools = sess
            except Exception:
                pass
            # Check model availability and confirm switch
            model = (data.get('model_name') or '').strip()
            switched = False
            if model and model != (self.current_model or ''):
                chosen = self._confirm_switch_model(model)
                if chosen:
                    # Route through parent to keep other panels in sync
                    try:
                        if hasattr(self.parent_tab, 'select_model'):
                            self.parent_tab.select_model(chosen)
                        else:
                            self.set_model(chosen)
                    except Exception:
                        self.set_model(chosen)
                    switched = True
            # If not switched (user cancelled or model unavailable), still reflect session model in UI
            if not switched and model:
                try:
                    self.current_model = model
                    self._set_model_label_with_class_color(model)
                    self._update_mount_button_style(mounted=False)
                    self.mount_btn.config(state=tk.NORMAL)
                except Exception:
                    pass
            # Load chat history
            self.chat_history = data.get('chat_history') or []
            self.redisplay_conversation()
            self.add_message('system', f"Loaded conversation: {session_id}")
        except Exception:
            pass

    def _confirm_switch_model(self, target_model: str) -> str | bool:
        from tkinter import messagebox
        try:
            def _base(name: str) -> str:
                name = (name or '').strip()
                # Split on last colon to remove tag (handles names with embedded colons)
                return name.rsplit(':', 1)[0] if ':' in name else name
            available = []
            try:
                from config import get_ollama_models
                available = get_ollama_models() or []
            except Exception:
                available = []
            # Try exact match, else match by base name
            if target_model in available:
                return target_model if messagebox.askyesno('Switch Model', f'Switching to "{target_model}" for the selected conversation. Continue?') else False
            base_target = _base(target_model)
            candidates = [m for m in available if _base(m) == base_target]
            if candidates:
                choice = candidates[0]
                return choice if messagebox.askyesno('Switch Model', f'Switching to "{choice}" for the selected conversation. Continue?') else False
            else:
                messagebox.showwarning('Model Not Available', f'Warning: "{target_model}" is no longer available.')
                return False
        except Exception:
            return target_model

        # Configure tags for styling
        self.chat_display.tag_config('user', foreground='#61dafb', font=("Arial", 10, "bold"))
        self.chat_display.tag_config('assistant', foreground='#98c379', font=("Arial", 10, "bold"))
        self.chat_display.tag_config('system', foreground='#e06c75', font=("Arial", 9, "italic"))
        self.chat_display.tag_config('error', foreground='#ff6b6b', font=("Arial", 9))

    def create_input_area(self, parent):
        """Create the message input area"""
        input_frame = ttk.Frame(parent, style='Category.TFrame')
        input_frame.grid(row=2, column=0, sticky=tk.EW, padx=10, pady=(5, 10))
        input_frame.columnconfigure(0, weight=1)

        # Quick Actions gear (replaces Load Chat) - placed later near top actions

        # Quick Actions and indicators bar (bottom-left between display and input)
        qa_bar = ttk.Frame(input_frame, style='Category.TFrame')
        qa_bar.grid(row=0, column=0, columnspan=2, sticky=tk.W, pady=(0,4))
        self.quick_actions_btn = ttk.Button(qa_bar, text="⚙️", command=self._open_quick_actions, style='Action.TButton', width=4)
        self.quick_actions_btn.pack(side=tk.LEFT)
        self.qa_indicators = ttk.Frame(qa_bar, style='Category.TFrame')
        self.qa_indicators.pack(side=tk.LEFT, padx=(8,0))
        self._tooltip_win = None
        self._update_quick_indicators()
        try:
            self._indicators_job = self.root.after(2000, self._poll_indicators)
        except Exception:
            self._indicators_job = None

        # Text input
        self.input_text = tk.Text(
            input_frame,
            height=3,
            wrap=tk.WORD,
            font=("Arial", 10),
            relief='flat',
            borderwidth=1,
            highlightthickness=1,
            highlightbackground='#454545',
            bg='#1e1e1e',
            fg='#ffffff',
            insertbackground='#61dafb'
        )
        self.input_text.grid(row=1, column=0, sticky=tk.EW, padx=(0, 5))

        # Bind Enter key (Shift+Enter for new line)
        self.input_text.bind('<Return>', self.on_enter_key)

        # Button container (Send/Stop buttons on the right side of input)
        button_container = ttk.Frame(input_frame, style='Category.TFrame')
        button_container.grid(row=1, column=1, sticky=tk.NS)

        # Send button
        self.send_btn = ttk.Button(
            button_container,
            text="Send ➤",
            command=self.send_message,
            style='Action.TButton',
            state=tk.DISABLED
        )
        self.send_btn.pack(side=tk.TOP, fill=tk.X, pady=(0, 2))

        # Stop button (moved here)
        self.stop_btn = ttk.Button(
            button_container,
            text="⏹️ Stop",
            command=self.stop_generation,
            style='Select.TButton',
            state=tk.DISABLED
        )
        self.stop_btn.pack(side=tk.TOP, fill=tk.X)

        # Instructions
        ttk.Label(
            input_frame,
            text="Press Enter to send • Shift+Enter for new line",
            style='Config.TLabel',
            font=("Arial", 8)
        ).grid(row=2, column=0, columnspan=2, sticky=tk.W, pady=(2, 0))

        # Indicator strip moved to top actions; no duplicate setup here

    def on_enter_key(self, event):
        """Handle Enter key press"""
        # If Shift is held, insert newline (default behavior)
        if event.state & 0x1:  # Shift key
            return None  # Allow default behavior
        else:
            # Otherwise, send message
            self.send_message()
            return "break"  # Prevent newline insertion

    def set_model(self, model_name):
        """Set the active model for chat"""
        # Auto-save current conversation if switching models
        if self.current_model and self.chat_history:
            self.conversation_histories[self.current_model] = self.chat_history.copy()
            # Auto-save to persistent storage if enabled
            if self.backend_settings.get('auto_save_history', True):
                self._auto_save_conversation()

            # Persist real-time scores for the previous model
            if self.training_mode_enabled and self.current_model in self.realtime_eval_scores:
                self.persist_realtime_scores(self.current_model)

        self.current_model = model_name
        self.is_mounted = False

        # Update label color based on variant class color
        self._set_model_label_with_class_color(model_name)

        # Enable mount button (style red for not mounted), disable send and dismount
        self._update_mount_button_style(mounted=False)
        self.dismount_btn.config(state=tk.DISABLED)
        self.send_btn.config(state=tk.DISABLED)

        log_message(f"CHAT_INTERFACE: Model set to {model_name}")

        # Load conversation history for this model if exists
        if model_name in self.conversation_histories:
            self.chat_history = self.conversation_histories[model_name].copy()
            # Redisplay the conversation
            self.redisplay_conversation()
            self.add_message("system", f"Model switched to: {model_name} (conversation restored)")
        else:
            self.chat_history = []
            self.clear_chat()
            self.add_message("system", f"Model switched to: {model_name} (new conversation)")

        # Auto-mount if enabled in settings
        if self.backend_settings.get('auto_mount_model', False):
            log_message(f"CHAT_INTERFACE: Auto-mounting {model_name}")
            self.mount_model()

        # Reset session temperature
        self.session_temperature = self.backend_settings.get('temperature', 0.8)
        self.session_temperature_var.set(self.session_temperature)
        self.update_session_temp_label(self.session_temperature)
        # Ensure mount button enabled after model selection
        try:
            self.mount_btn.config(state=tk.NORMAL)
        except Exception:
            pass

    def mount_model(self):
        """Mount the selected model in Ollama"""
        # Resolve active model: prefer internal state; fallback to label text
        model_name = (self.current_model or '').strip()
        if not model_name:
            try:
                lbl = str(self.model_label.cget('text') or '').strip()
            except Exception:
                lbl = ''
            if lbl and lbl.lower() != 'no model selected':
                model_name = lbl
                self.current_model = model_name
                try:
                    self.add_message('system', f"Using active model: {model_name}")
                except Exception:
                    pass
        if not model_name:
            try:
                self.add_message("error", "No model selected. Pick a model from the right panel.")
            except Exception:
                pass
            return

        log_message(f"CHAT_INTERFACE: Mounting model {model_name}...")
        try:
            self.add_message("system", f"Mounting {model_name}...")
        except Exception:
            pass

        def mount_thread():
            try:
                # Basic preflight: ensure 'ollama' is available
                try:
                    import shutil
                    if not shutil.which('ollama'):
                        self.root.after(0, lambda: self._on_mount_error("Mount failed: 'ollama' command not found."))
                        return
                except Exception:
                    pass
                # Call Ollama to load the model
                result = subprocess.run(
                    ["ollama", "run", model_name, "--verbose"],
                    input="",  # Empty input to just load the model
                    capture_output=True,
                    text=True,
                    timeout=30
                )

                if result.returncode == 0 or "success" in (result.stderr or '').lower():
                    self.root.after(0, self._on_mount_success)
                else:
                    err = (result.stderr or '').strip()
                    out = (result.stdout or '').strip()
                    error_msg = f"Mount failed: {err or out or 'unknown error'}"
                    self.root.after(0, lambda: self._on_mount_error(error_msg))

            except subprocess.TimeoutExpired:
                self.root.after(0, self._on_mount_success)  # Timeout often means it loaded
            except Exception as e:
                error_msg = f"Mount error: {str(e)}"
                self.root.after(0, lambda: self._on_mount_error(error_msg))

        threading.Thread(target=mount_thread, daemon=True).start()

    # --- Quick Actions gear popup ---------------------------------------
    def _open_quick_actions(self):
        try:
            # If already open, focus it
            if hasattr(self, '_qa_win') and self._qa_win and self._qa_win.winfo_exists():
                try:
                    self._qa_win.lift(); self._qa_win.focus_force()
                except Exception:
                    pass
                return
            win = tk.Toplevel(self.root)
            self._qa_win = win
            win.title('Quick Actions')
            win.resizable(True, True)
            try:
                # Small dialog near the gear button
                w, h = 420, 220
                bx = self.quick_actions_btn.winfo_rootx()
                by = self.quick_actions_btn.winfo_rooty()
                ax = bx
                ay = max(0, by - h - 8)
                self._qa_anchor = (ax, ay)
                win.geometry(f"{w}x{h}+{ax}+{ay}")
            except Exception:
                pass
            container = ttk.Frame(win, padding=8)
            container.pack(fill=tk.BOTH, expand=True)
            # Header with close button
            hdr = ttk.Frame(container)
            hdr.pack(fill=tk.X)
            ttk.Label(hdr, text='Quick Actions', style='CategoryPanel.TLabel').pack(side=tk.LEFT)
            ttk.Button(hdr, text='✕', width=3, style='Select.TButton', command=win.destroy).pack(side=tk.RIGHT)
            # Description/tooltip area
            self._qa_desc = ttk.Label(container, text='', style='Config.TLabel')
            self._qa_desc.pack(fill=tk.X, padx=2)

            self._qa_body = ttk.Frame(container)
            self._qa_body.pack(fill=tk.BOTH, expand=True, pady=(6,0))
            self._qa_show_main()

            # Auto-hide when clicking away if on main view
            def _maybe_hide(_e=None):
                try:
                    if getattr(self, '_qa_view', 'main') == 'main':
                        # Delay slightly to allow focusing internal widgets
                        def _check():
                            try:
                                f = self.root.focus_get()
                                if f is None or not str(f).startswith(str(self._qa_win)):
                                    if self._qa_win and self._qa_win.winfo_exists():
                                        self._qa_win.destroy()
                            except Exception:
                                pass
                        self.root.after(120, _check)
                except Exception:
                    pass
            try:
                win.bind('<FocusOut>', _maybe_hide)
            except Exception:
                pass
        except Exception:
            pass

    def _qa_show_main(self):
        try:
            for w in self._qa_body.winfo_children():
                w.destroy()
            try:
                if hasattr(self, '_qa_win') and self._qa_win:
                    self._qa_win.resizable(True, True)
                    w, h = 420, 220
                    ax, ay = getattr(self, '_qa_anchor', (self._qa_win.winfo_x(), self._qa_win.winfo_y()))
                    self._qa_win.geometry(f"{w}x{h}+{ax}+{ay}")
            except Exception:
                pass
            # Grid of icon-only buttons (wrap to rows of 4)
            grid = ttk.Frame(self._qa_body)
            grid.pack(pady=8, fill=tk.BOTH, expand=True)
            for i in range(4):
                grid.columnconfigure(i, weight=1)

            def mk_at(index, btn_text, desc, cmd, style='Action.TButton'):
                r = index // 4
                c = index % 4
                b = ttk.Button(grid, text=btn_text, width=6, style=style, command=cmd)
                b.grid(row=r, column=c, padx=6, pady=6, sticky=tk.EW)
                b.bind('<Enter>', lambda e, t=desc: self._qa_desc.config(text=t))
                b.bind('<Leave>', lambda e: self._qa_desc.config(text=''))
                return b

            i = 0
            mk_at(i, '📂', 'Change Working Directory', self.change_working_directory); i += 1
            mk_at(i, '🔧', 'Manage Tools', self._qa_show_tools); i += 1
            mk_at(i, '⏱', 'Think Time (next input)', self.open_think_time_dialog); i += 1
            mk_at(i, '⚡', 'Select Mode', self.open_mode_selector); i += 1
            mk_at(i, '📝', 'System Prompt / Tool Schema', self.open_prompt_schema_manager); i += 1
            # Temperature mode selector
            mk_at(i, '🌡️', 'Temperature Mode (Auto/Manual)', self.open_temp_mode_selector); i += 1
            # Create Project (save current chat to a new project and switch panel)
            mk_at(i, '🗂', 'Create Project from this chat', self._qa_create_project); i += 1
            # Show Thoughts toggle (👁 preferred; fallback 🧠)
            def _toggle_thoughts():
                self.show_thoughts = not bool(self.show_thoughts)
                try:
                    self._update_quick_indicators()
                except Exception:
                    pass
                # Update style to reflect state
                try:
                    btn = self._qa_thoughts_btn
                    btn.configure(style=('QA.Green.TButton' if self.show_thoughts else 'Select.TButton'))
                except Exception:
                    pass
            self._qa_thoughts_btn = mk_at(i, '👁', 'Toggle Show Thoughts (preview during generation)', _toggle_thoughts, style='Select.TButton'); i += 1
            # RAG toggle (chat-only) — enabling disables is immediate and persisted if possible
            def _toggle_rag():
                self.rag_enabled = not bool(self.rag_enabled)
                try:
                    if getattr(self, 'current_session_id', None) and self.chat_history_manager:
                        self._auto_save_conversation()
                except Exception:
                    pass
                self._update_quick_indicators()
            mk_at(i, '🧠', 'Toggle RAG (per chat)', _toggle_rag); i += 1
            # Removed redundant "Save RAG" action; RAG setting persists via autosave when toggled
            mk_at(i, '🗒', 'ToDo List', self.open_todo_list); i += 1
            # Training toggle (🏋️) with colored state
            self._qa_train_btn = mk_at(i, '🏋️', 'Training Mode', self._qa_toggle_training)
            self._qa_update_training_btn()
            # Mark current QA view
            self._qa_view = 'main'
        except Exception:
            pass

    # --- Indicator helpers ---------------------------------------------
    def _poll_indicators(self):
        try:
            # Avoid refreshing while tooltip is shown to prevent flicker
            if not getattr(self, '_tooltip_active', False):
                self._update_quick_indicators()
        except Exception:
            pass
        try:
            self._indicators_job = self.root.after(2000, self._poll_indicators)
        except Exception:
            pass

    def _update_quick_indicators(self):
        # Build a fingerprint of current indicator state; only rebuild when changed
        wd = None
        try:
            if self.tool_executor:
                wd = self.tool_executor.get_working_directory()
            if not wd:
                wd = self.backend_settings.get('working_directory')
        except Exception:
            wd = None
        tools_list = []
        try:
            if hasattr(self, 'session_enabled_tools') and isinstance(self.session_enabled_tools, dict) and self.session_enabled_tools:
                tools_list = sorted([k for k, v in self.session_enabled_tools.items() if v])
            elif hasattr(self.parent_tab, 'tools_interface') and self.parent_tab.tools_interface:
                ti = self.parent_tab.tools_interface
                tools_list = sorted([k for k, v in (getattr(ti, 'tool_vars', {}) or {}).items() if v.get()])
        except Exception:
            tools_list = []
        todo_active = False
        try:
            tab_map = getattr(self.parent_tab, 'tab_instances', None)
            settings_inst = tab_map.get('settings_tab', {}).get('instance') if isinstance(tab_map, dict) else None
            todo_active = bool(settings_inst is not None and getattr(settings_inst, 'todo_popup_active', False))
        except Exception:
            todo_active = False

        state_key = (
            int(self._think_next_min or 0),
            int(self._think_next_max or 0),
            str(wd or ''),
            tuple(tools_list),
            todo_active,
            str(self.current_mode or ''),
            int(1 if self.show_thoughts else 0),
            int(1 if getattr(self, 'rag_enabled', False) else 0),
            str(getattr(self, 'temp_mode', 'manual')),
            int(round(float(getattr(self, 'session_temperature', 0.8)) * 10)),
        )
        if state_key == getattr(self, '_qa_state_key', None):
            return
        self._qa_state_key = state_key

        # Clear previous icons
        try:
            for w in self.qa_indicators.winfo_children():
                w.destroy()
        except Exception:
            return

        # ThinkTime pending
        if (self._think_next_min or self._think_next_max):
            self._make_indicator(self.qa_indicators, '⏱', lambda: f"ThinkTime pending: min={int(self._think_next_min or 0)}s, max={int(self._think_next_max or 0)}s")

        # Working directory
        if wd:
            self._make_indicator(self.qa_indicators, '📂', lambda wdir=wd: f"Working dir: {wdir}")

        # Enabled tools
        if tools_list:
            self._make_indicator(self.qa_indicators, '🔧', lambda lst=tools_list: "Enabled tools:\n" + ", ".join(lst))

        # ToDo popup active
        if todo_active:
            self._make_indicator(self.qa_indicators, '🗒', lambda: "ToDo popup is open")

        # Mode indicator
        try:
            mode_name = (self.current_mode or 'smart').capitalize()
            self._make_indicator(self.qa_indicators, '⚡', lambda m=mode_name: f"Mode: {m}")
        except Exception:
            pass

        # Prompt/Schema indicator
        try:
            pr = self.current_system_prompt or 'default'
            sc = self.current_tool_schema or 'default'
            self._make_indicator(self.qa_indicators, '📝', lambda p=pr, s=sc: f"Prompt: {p}\nSchema: {s}")
        except Exception:
            pass
        # Show Thoughts indicator
        if bool(self.show_thoughts):
            self._make_indicator(self.qa_indicators, '👁', lambda: "Show Thoughts: ON (streaming preview)")
        # Temperature indicator
        try:
            tmode = (getattr(self, 'temp_mode', 'manual') or 'manual').capitalize()
            val = float(getattr(self, 'session_temperature', 0.8))
            self._make_indicator(self.qa_indicators, '🌡️', lambda tm=tmode, v=val: f"Temp: {v:.1f} ({tm})")
        except Exception:
            pass
        # RAG indicator with dynamic connected chat count and level
        if not getattr(self, '_suppress_base_rag_indicator', False) and self._is_rag_active():
            try:
                count = self._get_rag_connected_chat_count()
            except Exception:
                count = 0
            lvl = int(getattr(self, 'panel_rag_level', 0) or (1 if getattr(self, 'rag_enabled', False) else 0))
            self._make_indicator(self.qa_indicators, '🧠', lambda c=count, l=lvl: f"RAG: ON (L{l}) — Connected chats: {c}")

    def _get_rag_connected_chat_count(self) -> int:
        """Count conversations contributing to unified RAG (rag_enabled=True).

        Includes persisted conversations marked rag_enabled and, if applicable,
        the current in-memory session if toggled but not yet saved.
        """
        count = 0
        try:
            if not self.chat_history_manager:
                return 1 if getattr(self, 'rag_enabled', False) else 0
            convs = self.chat_history_manager.list_conversations()
            for rec in convs:
                meta = rec.get('metadata') or {}
                if bool(meta.get('rag_enabled', False)):
                    count += 1
            # If current session is RAG-enabled but not yet reflected in storage, include it
            try:
                current_id = getattr(self, 'current_session_id', None)
                is_current_counted = False
                if current_id:
                    for rec in convs:
                        if rec.get('session_id') == current_id:
                            is_current_counted = bool((rec.get('metadata') or {}).get('rag_enabled', False))
                            break
                if getattr(self, 'rag_enabled', False) and not is_current_counted:
                    count += 1
            except Exception:
                pass
        except Exception:
            pass
        return count

    def _is_rag_active(self) -> bool:
        """True if per-chat RAG is on or panel-level RAG level > 0."""
        try:
            return bool(getattr(self, 'rag_enabled', False)) or int(getattr(self, 'panel_rag_level', 0) or 0) > 0
        except Exception:
            return bool(getattr(self, 'rag_enabled', False))

    def _rag_query_scope(self) -> str | None:
        """Override in Projects tab to return current project name for scoped retrieval."""
        return None

    def _build_rag_context(self, user_message: str, max_chars: int = 1800, per_snippet_max: int = 600, top_k: int = 3) -> str:
        """Assemble retrieval context from rag-enabled chats.

        - Scores saved conversations by simple lexical overlap with the user message.
        - Pulls most relevant snippets and caps total characters for safety.
        - In Projects tab, prefers current project's rag-enabled chats.
        """
        try:
            um = (user_message or '').lower()
            if not um:
                return ''

            # Tokenize user message (very simple split)
            query_terms = [w for w in re.split(r"[^a-zA-Z0-9]+", um) if len(w) > 2]
            if not query_terms:
                query_terms = um.split()

            candidates = []  # list of (score, when, snippet)

            def summarize_chat(chat_history: list[dict]) -> str:
                # Prefer recent assistant outputs and user inputs
                texts = []
                for msg in chat_history[-12:]:  # last ~12 messages
                    role = msg.get('role'); content = (msg.get('content') or '').strip()
                    if not content:
                        continue
                    if role in ('assistant', 'user', 'system'):
                        texts.append(f"[{role}] {content}")
                return "\n".join(texts)

            def score_text(text: str) -> int:
                tl = text.lower()
                score = 0
                for t in query_terms:
                    if t and t in tl:
                        score += tl.count(t)
                return score

            # Helper to collect from a conversation record
            def consider_conv(record: dict, chat_history: list[dict]):
                meta = record.get('metadata') or {}
                if not bool(meta.get('rag_enabled', False)):
                    return
                summary = summarize_chat(chat_history)
                if not summary:
                    return
                s = score_text(summary)
                if s <= 0:
                    return
                when = record.get('saved_at') or ''
                snippet = summary[:per_snippet_max]
                candidates.append((s, when, snippet))

            import re, json as _json
            from datetime import datetime as _dt

            # If Projects tab with a current project: collect from project store
            try:
                if hasattr(self, 'current_project') and self.current_project:
                    from ..projects_manager import list_conversations as _plist
                    root = Path('Data/projects')/self.current_project
                    for rec in _plist(self.current_project):
                        sid = rec.get('session_id');
                        p = root / f"{sid}.json"
                        try:
                            data = _json.loads(p.read_text())
                            consider_conv(data, data.get('chat_history') or [])
                        except Exception:
                            continue
                else:
                    # Global: use ChatHistoryManager
                    if not self.chat_history_manager:
                        return ''
                    summaries = self.chat_history_manager.list_conversations()
                    for rec in summaries:
                        data = self.chat_history_manager.load_conversation(rec.get('session_id','')) or {}
                        consider_conv(data, data.get('chat_history') or [])
            except Exception:
                pass

            # Rank candidates by score desc then recency
            candidates.sort(key=lambda x: (x[0], x[1]), reverse=True)
            chosen = candidates[:top_k]
            buf = []
            total = 0
            for idx, (_score, _when, snip) in enumerate(chosen, 1):
                part = f"[Context {idx}]\n{snip}".strip()
                if total + len(part) + 2 > max_chars:
                    break
                buf.append(part)
                total += len(part) + 2
            return "\n\n".join(buf)
        except Exception:
            return ''

    def _save_backend_setting(self, key: str, value):
        """Persist a backend setting into custom_code_settings.json."""
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
        except Exception as e:
            log_message(f"CHAT_INTERFACE: Failed to save backend setting {key}: {e}")

    def _log_rag_training_example(self, query: str):
        """Append a JSONL record with RAG retrieval details to training dataset when Training Mode is ON."""
        try:
            lvl = int(getattr(self, 'panel_rag_level', 0) or 0)
            if lvl <= 0 and getattr(self, 'rag_enabled', False):
                lvl = 1
            scope = None
            try:
                scope = self._rag_query_scope()
            except Exception:
                scope = None
            # Ensure index is ready
            try:
                if scope:
                    self.rag_service.refresh_index_project(scope)
                else:
                    self.rag_service.refresh_index_global()
            except Exception:
                pass
            # Use a fixed top_k for logging, independent of injection caps
            results = self.rag_service.query(query, top_k=6, scope=scope)
            rec = {
                'timestamp': datetime.now().isoformat(),
                'session_id': getattr(self, 'current_session_id', ''),
                'model_name': getattr(self, 'current_model', ''),
                'project': getattr(self, 'current_project', None),
                'rag_level': lvl,
                'scope': (scope or 'global'),
                'query': query,
                'results': [
                    {
                        'session_id': doc.session_id,
                        'role': doc.role,
                        'index': doc.index,
                        'score': float(score),
                        'preview': (doc.text or '')[:240]
                    } for (doc, score) in results
                ]
            }
            out_dir = Path('Training_Data-Sets') / 'Tools'
            out_dir.mkdir(parents=True, exist_ok=True)
            out_path = out_dir / 'rag_retrievals.jsonl'
            with open(out_path, 'a', encoding='utf-8') as f:
                f.write(json.dumps(rec) + '\n')
        except Exception:
            pass

    # --- Unified System Prompt / Tool Schema manager --------------------
    def open_prompt_schema_manager(self):
        """Open a combined manager with tabs for System Prompt and Tool Schema."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Prompt / Tool Schema Manager")
        dialog.geometry("1000x720")
        dialog.configure(bg='#2b2b2b')
        try:
            dialog.transient(self.root)
            dialog.lift(); dialog.attributes('-topmost', True); self.root.after(400, lambda: dialog.attributes('-topmost', False))
        except Exception:
            pass

        # Top toggle buttons
        header = ttk.Frame(dialog)
        header.pack(fill=tk.X, padx=10, pady=(10, 0))
        body = ttk.Frame(dialog)
        body.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Track which view is active
        active = {'tab': 'prompt'}

        def show_prompt():
            active['tab'] = 'prompt'
            for w in body.winfo_children():
                w.destroy()
            try:
                self._build_prompt_manager_ui(body, dialog)
            except Exception:
                pass
            try:
                btn_prompt.configure(style='Action.TButton')
                btn_schema.configure(style='Select.TButton')
            except Exception:
                pass

        def show_schema():
            active['tab'] = 'schema'
            for w in body.winfo_children():
                w.destroy()
            try:
                self._build_schema_manager_ui(body, dialog)
            except Exception:
                pass
            try:
                btn_prompt.configure(style='Select.TButton')
                btn_schema.configure(style='Action.TButton')
            except Exception:
                pass

        btn_prompt = ttk.Button(header, text='System Prompt', style='Action.TButton', command=show_prompt)
        btn_schema = ttk.Button(header, text='Tool Schema', style='Select.TButton', command=show_schema)
        btn_prompt.pack(side=tk.LEFT, padx=(0,6))
        btn_schema.pack(side=tk.LEFT)

        # Default to prompt view
        show_prompt()

    def _build_prompt_manager_ui(self, parent, dialog):
        """Build the System Prompt manager UI into parent frame."""
        parent.columnconfigure(0, weight=0)
        parent.columnconfigure(1, weight=1)
        parent.rowconfigure(0, weight=1)

        # Left list
        left = ttk.Frame(parent, style='Category.TFrame')
        left.grid(row=0, column=0, sticky=tk.NSEW, padx=(0,6))
        ttk.Label(left, text='Available Prompts', font=("Arial", 12, 'bold'), style='CategoryPanel.TLabel').pack(anchor=tk.W, pady=(0,6))
        lf = ttk.Frame(left)
        lf.pack(fill=tk.BOTH, expand=True)
        sb = ttk.Scrollbar(lf)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        lst = tk.Listbox(lf, yscrollcommand=sb.set, bg='#1e1e1e', fg='#ffffff', selectbackground='#61dafb', width=26)
        lst.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb.config(command=lst.yview)
        prompts = sorted([f.stem for f in self.system_prompts_dir.glob('*.txt')])
        for i, name in enumerate(prompts):
            lst.insert(tk.END, name)
            if name == (self.current_system_prompt or 'default'):
                lst.selection_set(i)

        # Right editor
        right = ttk.Frame(parent, style='Category.TFrame')
        right.grid(row=0, column=1, sticky=tk.NSEW)
        right.columnconfigure(0, weight=1)
        right.rowconfigure(1, weight=1)
        title = ttk.Label(right, text='Select a prompt to view/edit', font=("Arial", 12, 'bold'), style='CategoryPanel.TLabel')
        title.grid(row=0, column=0, sticky=tk.W, pady=(0,6))
        ed = scrolledtext.ScrolledText(right, wrap=tk.WORD, font=("Courier", 10), bg='#1e1e1e', fg='#ffffff', insertbackground='#61dafb')
        ed.grid(row=1, column=0, sticky=tk.NSEW)

        current = {'name': None, 'modified': False}

        def load_selected(_e=None):
            if not lst.curselection():
                return
            name = lst.get(lst.curselection()[0])
            current['name'] = name
            try:
                content = (self.system_prompts_dir / f"{name}.txt").read_text()
            except Exception:
                content = ''
            ed.delete(1.0, tk.END)
            ed.insert(tk.END, content)
            current['modified'] = False
            title.config(text=f"Editing: {name}")

        def on_modified(_e=None):
            current['modified'] = True

        ed.bind('<<Modified>>', on_modified)
        load_selected()
        lst.bind('<<ListboxSelect>>', load_selected)

        # Bottom buttons
        btns = ttk.Frame(parent)
        btns.grid(row=1, column=0, columnspan=2, sticky=tk.EW, pady=(6,0))
        for i in range(4):
            btns.columnconfigure(i, weight=1)

        def save_cb():
            name = current.get('name')
            if not name:
                return
            (self.system_prompts_dir / f"{name}.txt").write_text(ed.get(1.0, tk.END))
            current['modified'] = False

        def new_cb():
            from tkinter import simpledialog, messagebox
            name = simpledialog.askstring('New Prompt', 'Enter prompt name:')
            if not name:
                return
            p = self.system_prompts_dir / f"{name}.txt"
            if p.exists():
                messagebox.showerror('Exists', 'A prompt with that name already exists.')
                return
            p.write_text('')
            lst.insert(tk.END, name)
            lst.selection_clear(0, tk.END)
            lst.selection_set(tk.END)
            load_selected()

        def del_cb():
            from tkinter import messagebox
            name = current.get('name')
            if not name:
                return
            if name == 'default':
                messagebox.showerror('Cannot Delete', 'Cannot delete the default prompt')
                return
            if not messagebox.askyesno('Confirm', f"Delete prompt '{name}'?"):
                return
            (self.system_prompts_dir / f"{name}.txt").unlink(missing_ok=True)
            # refresh list
            sel = lst.curselection()
            if sel:
                lst.delete(sel[0])
            current['name'] = None
            ed.delete(1.0, tk.END)
            title.config(text='Select a prompt to view/edit')

        def apply_cb():
            name = current.get('name')
            if not name:
                return
            if current.get('modified'):
                save_cb()
            self.current_system_prompt = name
            try:
                self.add_message('system', f"✓ Loaded system prompt: {name}")
            except Exception:
                pass
            try:
                self._update_quick_indicators()
            except Exception:
                pass
            if self.is_mounted:
                self.dismount_model(); self.root.after(500, self.mount_model)

        ttk.Button(btns, text='💾 Save', style='Action.TButton', command=save_cb).grid(row=0, column=0, padx=4, sticky=tk.EW)
        ttk.Button(btns, text='➕ New', style='Action.TButton', command=new_cb).grid(row=0, column=1, padx=4, sticky=tk.EW)
        ttk.Button(btns, text='🗑 Delete', style='Select.TButton', command=del_cb).grid(row=0, column=2, padx=4, sticky=tk.EW)
        ttk.Button(btns, text='✓ Select & Apply', style='Action.TButton', command=apply_cb).grid(row=0, column=3, padx=4, sticky=tk.EW)

    def _build_schema_manager_ui(self, parent, dialog):
        """Build the Tool Schema manager UI into parent frame."""
        parent.columnconfigure(0, weight=0)
        parent.columnconfigure(1, weight=1)
        parent.rowconfigure(0, weight=1)

        left = ttk.Frame(parent, style='Category.TFrame')
        left.grid(row=0, column=0, sticky=tk.NSEW, padx=(0,6))
        ttk.Label(left, text='Available Schemas', font=("Arial", 12, 'bold'), style='CategoryPanel.TLabel').pack(anchor=tk.W, pady=(0,6))
        lf = ttk.Frame(left)
        lf.pack(fill=tk.BOTH, expand=True)
        sb = ttk.Scrollbar(lf)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        lst = tk.Listbox(lf, yscrollcommand=sb.set, bg='#1e1e1e', fg='#ffffff', selectbackground='#61dafb', width=26)
        lst.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb.config(command=lst.yview)
        schemas = sorted([f.stem for f in self.tool_schemas_dir.glob('*.json')])
        for i, name in enumerate(schemas):
            lst.insert(tk.END, name)
            if name == (self.current_tool_schema or 'default'):
                lst.selection_set(i)

        right = ttk.Frame(parent, style='Category.TFrame')
        right.grid(row=0, column=1, sticky=tk.NSEW)
        right.columnconfigure(0, weight=1)
        right.rowconfigure(1, weight=1)
        title = ttk.Label(right, text='Select a schema to view/edit', font=("Arial", 12, 'bold'), style='CategoryPanel.TLabel')
        title.grid(row=0, column=0, sticky=tk.W, pady=(0,6))
        ed = scrolledtext.ScrolledText(right, wrap=tk.WORD, font=("Courier", 10), bg='#1e1e1e', fg='#ffffff', insertbackground='#61dafb')
        ed.grid(row=1, column=0, sticky=tk.NSEW)

        current = {'name': None, 'modified': False}

        def load_selected(_e=None):
            if not lst.curselection():
                return
            name = lst.get(lst.curselection()[0])
            current['name'] = name
            try:
                content = (self.tool_schemas_dir / f"{name}.json").read_text()
            except Exception:
                content = '{\n  "enabled_tools": "all"\n}'
            ed.delete(1.0, tk.END)
            ed.insert(tk.END, content)
            current['modified'] = False
            title.config(text=f"Editing: {name}")

        def on_modified(_e=None):
            current['modified'] = True
        ed.bind('<<Modified>>', on_modified)
        load_selected(); lst.bind('<<ListboxSelect>>', load_selected)

        btns = ttk.Frame(parent)
        btns.grid(row=1, column=0, columnspan=2, sticky=tk.EW, pady=(6,0))
        for i in range(4):
            btns.columnconfigure(i, weight=1)

        def save_cb():
            name = current.get('name')
            if not name:
                return
            (self.tool_schemas_dir / f"{name}.json").write_text(ed.get(1.0, tk.END))
            current['modified'] = False

        def new_cb():
            from tkinter import simpledialog, messagebox
            name = simpledialog.askstring('New Schema', 'Enter schema name:')
            if not name:
                return
            p = self.tool_schemas_dir / f"{name}.json"
            if p.exists():
                messagebox.showerror('Exists', 'A schema with that name already exists.')
                return
            p.write_text('{\n  "enabled_tools": "all",\n  "description": "Default"\n}')
            lst.insert(tk.END, name)
            lst.selection_clear(0, tk.END)
            lst.selection_set(tk.END)
            load_selected()

        def del_cb():
            from tkinter import messagebox
            name = current.get('name')
            if not name:
                return
            if name == 'default':
                messagebox.showerror('Cannot Delete', 'Cannot delete the default schema')
                return
            if not messagebox.askyesno('Confirm', f"Delete schema '{name}'?"):
                return
            (self.tool_schemas_dir / f"{name}.json").unlink(missing_ok=True)
            sel = lst.curselection();
            if sel: lst.delete(sel[0])
            current['name'] = None
            ed.delete(1.0, tk.END); title.config(text='Select a schema to view/edit')

        def apply_cb():
            name = current.get('name')
            if not name:
                return
            if current.get('modified'):
                save_cb()
            self.current_tool_schema = name
            try:
                self.add_message('system', f"✓ Loaded tool schema: {name}")
            except Exception:
                pass
            try:
                self._update_quick_indicators()
            except Exception:
                pass
            if self.is_mounted:
                self.dismount_model(); self.root.after(500, self.mount_model)

        ttk.Button(btns, text='💾 Save', style='Action.TButton', command=save_cb).grid(row=0, column=0, padx=4, sticky=tk.EW)
        ttk.Button(btns, text='➕ New', style='Action.TButton', command=new_cb).grid(row=0, column=1, padx=4, sticky=tk.EW)
        ttk.Button(btns, text='🗑 Delete', style='Select.TButton', command=del_cb).grid(row=0, column=2, padx=4, sticky=tk.EW)
        ttk.Button(btns, text='✓ Select & Apply', style='Action.TButton', command=apply_cb).grid(row=0, column=3, padx=4, sticky=tk.EW)

    def _make_indicator(self, parent, icon_text, tooltip_provider):
        lbl = ttk.Label(parent, text=icon_text, style='CategoryPanel.TLabel')
        lbl.pack(side=tk.LEFT, padx=4)
        def _enter(e):
            # Debounce tooltip to avoid flicker
            try:
                if hasattr(self, '_tooltip_after_id') and self._tooltip_after_id:
                    self.root.after_cancel(self._tooltip_after_id)
            except Exception:
                pass
            self._tooltip_after_id = self.root.after(200, lambda w=e.widget: self._show_tooltip(w, tooltip_provider()))
        def _leave(e):
            # Cancel pending tooltip and hide any visible one
            try:
                if hasattr(self, '_tooltip_after_id') and self._tooltip_after_id:
                    self.root.after_cancel(self._tooltip_after_id)
            except Exception:
                pass
            self._tooltip_after_id = None
            self._hide_tooltip()
        lbl.bind('<Enter>', _enter)
        lbl.bind('<Leave>', _leave)
        return lbl

    def _show_tooltip(self, widget, text):
        try:
            self._hide_tooltip()
            tip = tk.Toplevel(self.root)
            tip.wm_overrideredirect(True)
            # Place tooltip below and to the right to avoid overlapping the source widget
            x = widget.winfo_rootx() + int(widget.winfo_width() * 0.3)
            y = widget.winfo_rooty() + widget.winfo_height() + 8
            tip.wm_geometry(f"+{x}+{y}")
            frm = ttk.Frame(tip, padding=4, relief='solid', borderwidth=1)
            frm.pack()
            ttk.Label(frm, text=text, style='Config.TLabel').pack()
            self._tooltip_win = tip
            self._tooltip_active = True
            try:
                tip.attributes('-topmost', True)
            except Exception:
                pass
        except Exception:
            pass

    def _hide_tooltip(self):
        try:
            if self._tooltip_win and self._tooltip_win.winfo_exists():
                self._tooltip_win.destroy()
        except Exception:
            pass
        self._tooltip_win = None
        self._tooltip_active = False

    def _qa_create_project(self):
        """Create a new project from current chat and switch to Projects panel."""
        from tkinter import simpledialog, messagebox
        try:
            name = simpledialog.askstring('Create Project', 'Enter project name:')
            if not name:
                return
            if not messagebox.askyesno('Create Project', f"Create project '{name}' and save this chat to it?\nYou will be switched to the Projects panel."):
                return
            # Save current chat to project (if any)
            try:
                from ..projects_manager import ensure_project, save_conversation
                ensure_project(name)
                meta = {
                    'mode': getattr(self, 'current_mode', 'smart'),
                    'temperature': self.session_temperature,
                    'system_prompt': getattr(self, 'current_system_prompt', 'default'),
                    'tool_schema': getattr(self, 'current_tool_schema', 'default'),
                    'working_directory': self.tool_executor.get_working_directory() if hasattr(self, 'tool_executor') and self.tool_executor else 'unknown',
                    'rag_enabled': bool(getattr(self, 'rag_enabled', False)),
                }
                if self.chat_history:
                    sid = save_conversation(name, self.current_model or 'unknown', self.chat_history, meta, self.current_session_id)
                else:
                    sid = save_conversation(name, self.current_model or 'unknown', [], meta)
            except Exception as e:
                messagebox.showerror('Project Error', f'Failed to save to project: {e}')
                return
            # Switch to Projects tab and select project
            try:
                nb = getattr(self.parent_tab, 'sub_notebook', None)
                if nb and hasattr(self.parent_tab, 'projects_tab_frame'):
                    nb.select(self.parent_tab.projects_tab_frame)
                pif = getattr(self.parent_tab, 'projects_interface', None)
                if pif:
                    pif.current_project = name
                    pif._refresh_projects_tree()
            except Exception:
                pass
        except Exception:
            pass

    def _qa_update_training_btn(self):
        try:
            from tkinter import ttk as _ttk
            st = _ttk.Style()
            gstyle, rstyle = 'QA.Green.TButton', 'QA.Red.TButton'
            try:
                st.configure(gstyle, foreground='#51cf66')
                st.configure(rstyle, foreground='#ff6b6b')
            except Exception:
                pass
            if hasattr(self, '_qa_train_btn') and self._qa_train_btn:
                self._qa_train_btn.config(style=(gstyle if self.training_mode_enabled else rstyle))
        except Exception:
            pass

    def _qa_toggle_training(self):
        try:
            enabled = not bool(self.training_mode_enabled)
            self.set_training_mode(enabled)
            self._qa_update_training_btn()
        except Exception:
            pass

    def _qa_show_tools(self):
        try:
            for w in self._qa_body.winfo_children():
                w.destroy()
            try:
                if hasattr(self, '_qa_win') and self._qa_win:
                    self._qa_win.resizable(True, True)
                    self._qa_win.geometry('520x420')
            except Exception:
                pass
            top = ttk.Frame(self._qa_body)
            top.pack(fill=tk.X)
            # Back button
            ttk.Button(top, text='⬅', width=3, style='Select.TButton', command=self._qa_show_main).pack(side=tk.LEFT)
            ttk.Label(top, text='Tools', style='CategoryPanel.TLabel').pack(side=tk.LEFT, padx=6)
            # Scrollable tools list with checkboxes
            wrap = ttk.Frame(self._qa_body)
            wrap.pack(fill=tk.BOTH, expand=True, pady=(6,0))
            wrap.columnconfigure(0, weight=1)
            wrap.rowconfigure(0, weight=1)
            cv = tk.Canvas(wrap, bg='#2b2b2b', highlightthickness=0)
            sb = ttk.Scrollbar(wrap, orient='vertical', command=cv.yview)
            body = ttk.Frame(cv, style='Category.TFrame')
            body.bind('<Configure>', lambda e: cv.configure(scrollregion=cv.bbox('all')))
            win_id = cv.create_window((0,0), window=body, anchor='nw')
            cv.configure(yscrollcommand=sb.set)
            def _sync_width(event):
                try:
                    cv.itemconfigure(win_id, width=cv.winfo_width())
                except Exception:
                    pass
            cv.bind('<Configure>', _sync_width)
            cv.grid(row=0, column=0, sticky=tk.NSEW)
            sb.grid(row=0, column=1, sticky=tk.NS)
            # Mousewheel scrolling on hover
            cv.bind('<Enter>', lambda e: self._qa_bind_wheel(cv))
            cv.bind('<Leave>', lambda e: self._qa_unbind_wheel())
            # Mark subview so focus-out does not auto-hide
            self._qa_view = 'tools'
            # Build tools list from Tools tab state when available; else fallback
            tools = []
            enabled = {}
            try:
                if hasattr(self.parent_tab, 'tools_interface') and self.parent_tab.tools_interface:
                    ti = self.parent_tab.tools_interface
                    for _, mp in getattr(ti, 'AVAILABLE_TOOLS', {}).items():
                        tools.extend(list(mp.keys()))
                    enabled = {k: bool(v.get()) for k, v in (getattr(ti, 'tool_vars', {}) or {}).items()}
            except Exception:
                pass
            if not tools:
                tools = ['file_read','file_write','file_edit','file_search','directory_list','grep_search','bash_execute']
            if not enabled:
                enabled = self.load_enabled_tools() or {}
            self._qa_tool_vars = {}
            for name in tools:
                var = tk.BooleanVar(value=bool(enabled.get(name, True)) if enabled else True)
                self._qa_tool_vars[name] = var
                ttk.Checkbutton(body, text=name, variable=var, style='Category.TCheckbutton').pack(anchor=tk.W)
            # Save row
            def save_tools():
                try:
                    # Build override map
                    session_map = {k: bool(v.get()) for k, v in self._qa_tool_vars.items()}
                    # Determine defaults to compare against
                    defaults = {}
                    try:
                        if hasattr(self.parent_tab, 'tools_interface') and self.parent_tab.tools_interface:
                            ti = self.parent_tab.tools_interface
                            defaults = {k: bool(v.get()) for k, v in (getattr(ti, 'tool_vars', {}) or {}).items()}
                    except Exception:
                        defaults = {}
                    if not defaults:
                        defaults = self.load_enabled_tools() or {}

                    # Compute diffs
                    enabled_now = sorted([k for k, v in session_map.items() if v])
                    disabled_now = sorted([k for k, v in session_map.items() if not v])
                    changed = sorted([k for k, v in session_map.items() if v != bool(defaults.get(k, True))])
                    plus = sorted([k for k in changed if session_map.get(k) is True])
                    minus = sorted([k for k in changed if session_map.get(k) is False])

                    # Persist per-chat override
                    self.session_enabled_tools = session_map
                    self._qa_desc.config(text='Saved tool settings for this chat (overrides defaults)')

                    # Announce summary in chat
                    try:
                        parts = []
                        if plus:
                            parts.append("+" + ", ".join(plus))
                        if minus:
                            parts.append("-" + ", ".join(minus))
                        diff_line = ("; Changes: " + " | ".join(parts)) if parts else "; No changes vs defaults"
                        msg = (
                            "Quick Tools: overrides saved.\n"
                            f"Enabled: {', '.join(enabled_now) or '—'}\n"
                            f"Disabled: {', '.join(disabled_now) or '—'}" + diff_line
                        )
                        self.add_message('system', msg)
                    except Exception:
                        pass
                except Exception as e:
                    try:
                        self._qa_desc.config(text=f"Error saving: {e}")
                    except Exception:
                        pass
            ttk.Button(self._qa_body, text='Save', style='Action.TButton', command=save_tools).pack(pady=6)
        except Exception:
            pass

    # Mousewheel helpers for Quick Actions scrollable views
    def _qa_bind_wheel(self, canvas: tk.Canvas):
        try:
            def _on_wheel(event):
                delta = 0
                try:
                    if event.num == 4 or event.delta > 0:
                        delta = -1
                    elif event.num == 5 or event.delta < 0:
                        delta = 1
                except Exception:
                    delta = 0
                canvas.yview_scroll(delta, 'units')
                return 'break'
            self._qa_wheel_handler = _on_wheel
            # Bind for Windows/Mac and Linux
            self.root.bind_all('<MouseWheel>', _on_wheel)
            self.root.bind_all('<Button-4>', _on_wheel)
            self.root.bind_all('<Button-5>', _on_wheel)
        except Exception:
            pass

    def _qa_unbind_wheel(self):
        try:
            self.root.unbind_all('<MouseWheel>')
            self.root.unbind_all('<Button-4>')
            self.root.unbind_all('<Button-5>')
        except Exception:
            pass

    def _on_mount_success(self):
        """Handle successful model mount"""
        self.is_mounted = True
        # Keep class color on label; mount button goes green
        self._update_mount_button_style(mounted=True)
        self.mount_btn.config(state=tk.DISABLED)
        self.dismount_btn.config(state=tk.NORMAL)
        self.send_btn.config(state=tk.NORMAL)
        self.add_message("system", f"{self.current_model} mounted successfully ✓")
        log_message(f"CHAT_INTERFACE: Model {self.current_model} mounted")

    def _on_mount_error(self, error_msg):
        """Handle model mount error"""
        self.add_message("error", error_msg)
        log_message(f"CHAT_INTERFACE ERROR: {error_msg}")

    def dismount_model(self):
        """Dismount the current model"""
        if not self.current_model:
            return

        log_message(f"CHAT_INTERFACE: Dismounting model {self.current_model}...")
        self.is_mounted = False

        # Update UI immediately
        self._update_mount_button_style(mounted=False)
        self.mount_btn.config(state=tk.NORMAL)
        self.dismount_btn.config(state=tk.DISABLED)
        self.send_btn.config(state=tk.DISABLED)

        self.add_message("system", f"{self.current_model} dismounted")
        log_message(f"CHAT_INTERFACE: Model {self.current_model} dismounted")

    def _set_model_label_with_class_color(self, model_tag: str):
        try:
            import config as C
            color = '#bbbbbb'
            vid = None
            model_tag = (model_tag or '').strip()
            try:
                lid = C.get_lineage_for_tag(model_tag)
            except Exception:
                lid = None
            if lid:
                try:
                    for rec in (C.list_model_profiles() or []):
                        if rec.get('lineage_id') == lid:
                            vid = rec.get('variant_id')
                            break
                except Exception:
                    pass
            if not vid:
                # Fallback: try variant id from tag prefix
                base_tag = (model_tag or '').split(':')[0]
                try:
                    for rec in (C.list_model_profiles() or []):
                        if rec.get('variant_id') == base_tag:
                            vid = base_tag
                            break
                except Exception:
                    pass
            if vid:
                try:
                    cls = C.get_variant_class(vid) or 'novice'
                    color = {
                        'novice': '#51cf66', 'skilled': '#61dafb', 'expert': '#9b59b6', 'master': '#ffa94d', 'artifact': '#c92a2a'
                    }.get(str(cls).lower(), '#bbbbbb')
                except Exception:
                    pass
            self.model_label.config(text=model_tag, fg=color)
        except Exception:
            self.model_label.config(text=model_tag, fg='#bbbbbb')

    def _update_mount_button_style(self, mounted: bool):
        try:
            from tkinter import ttk as _ttk
            st = _ttk.Style()
            gstyle = 'MountGreen.TButton'; rstyle = 'MountRed.TButton'
            try:
                st.configure(gstyle, foreground='#00c853')
                st.configure(rstyle, foreground='#ff6b6b')
            except Exception:
                pass
            self.mount_btn.config(style=(gstyle if mounted else rstyle))
        except Exception:
            pass

    def _toggle_training_mode(self):
        try:
            enabled = not bool(self.training_mode_enabled)
            self.set_training_mode(enabled)
            if hasattr(self, 'training_state_label'):
                self.training_state_label.config(text=('On' if enabled else 'Off'))
            # Persist to backend settings for other tabs and emit event
            try:
                from pathlib import Path
                import json
                self.backend_settings['training_mode_enabled'] = bool(enabled)
                settings_file = Path(__file__).parent.parent / 'custom_code_settings.json'
                try:
                    data = {}
                    if settings_file.exists():
                        data = json.loads(settings_file.read_text())
                    data.update(self.backend_settings)
                    settings_file.write_text(json.dumps(data, indent=2))
                except Exception:
                    pass
                # Notify Settings tab to reflect the toggle
                payload = json.dumps({"enabled": bool(enabled)})
                self.root.event_generate("<<TrainingModeChanged>>", data=payload, when='tail')
            except Exception:
                pass
        except Exception:
            pass

        # Note: Ollama doesn't have a specific "unload" command
        # Models are automatically unloaded after inactivity

    def change_working_directory(self):
        """Open dialog to change working directory for tool execution"""
        from tkinter import filedialog, messagebox

        # Get current working directory
        current_dir = str(Path.cwd())
        if self.tool_executor:
            current_dir = self.tool_executor.get_working_directory()

        # Open directory selection dialog
        new_dir = filedialog.askdirectory(
            title="Select Working Directory for Tool Execution",
            initialdir=current_dir
        )

        if new_dir:
            # Update tool executor
            if self.tool_executor:
                success = self.tool_executor.set_working_directory(new_dir)
                if success:
                    # Update backend settings
                    self.backend_settings['working_directory'] = new_dir

                    # Save to settings file
                    settings_file = Path(__file__).parent.parent / "custom_code_settings.json"
                    try:
                        with open(settings_file, 'r') as f:
                            settings = json.load(f)
                        settings['working_directory'] = new_dir
                        with open(settings_file, 'w') as f:
                            json.dump(settings, f, indent=2)

                        log_message(f"CHAT_INTERFACE: Working directory changed to {new_dir}")
                        self.add_message("system", f"Working directory changed to: {new_dir}")
                        messagebox.showinfo("Directory Changed", f"Working directory set to:\n{new_dir}")
                    except Exception as e:
                        log_message(f"CHAT_INTERFACE ERROR: Failed to save working directory: {e}")
                        messagebox.showerror("Save Error", f"Directory changed but failed to save to settings:\n{str(e)}")
                else:
                    log_message(f"CHAT_INTERFACE ERROR: Failed to change working directory to {new_dir}")
                    messagebox.showerror("Directory Error", f"Failed to change working directory:\n{new_dir}\n\nDirectory may not exist or be inaccessible.")
            else:
                log_message("CHAT_INTERFACE ERROR: Tool executor not initialized")
                messagebox.showerror("Error", "Tool executor not initialized")

    def clear_chat(self):
        """Clear chat history and renews the session"""
        # Save the current conversation before clearing, if not empty
        if self.chat_history and self.backend_settings.get('auto_save_history', True) and not getattr(self, '_skip_autosave_once', False):
            self._auto_save_conversation()

        # Reset chat buffers and UI
        self.chat_history = []
        self.current_session_id = None  # New session begins only when user sends a message
        self.chat_display.config(state=tk.NORMAL)
        self.chat_display.delete(1.0, tk.END)
        self.chat_display.config(state=tk.DISABLED)
        # Clear active model and disable mount/send
        self.current_model = None
        self.is_mounted = False
        try:
            self.model_label.config(text="No model selected", fg='#ffffff')
            self.mount_btn.config(state=tk.DISABLED)
            self.dismount_btn.config(state=tk.DISABLED)
            self.send_btn.config(state=tk.DISABLED)
        except Exception:
            pass
        self.add_message("system", "Chat cleared. Select a model to begin a new session.")
        log_message("CHAT_INTERFACE: Chat cleared; model unset and session idle")

        # Reset session temperature
        self.session_temperature = self.backend_settings.get('temperature', 0.8)
        self.session_temperature_var.set(self.session_temperature)
        self.update_session_temp_label(self.session_temperature)

    def new_chat(self):
        """Start a new chat: save current if any, then clear and show summary."""
        from tkinter import messagebox
        # Offer to save QA settings per session if requested
        self._maybe_prompt_save_qa_settings('New Chat')
        had_chat = bool(self.chat_history) and bool(self._chat_dirty)
        model = self.current_model or 'none'
        mode = getattr(self, 'current_mode', 'smart')
        prompt = getattr(self, 'current_system_prompt', 'default')
        schema = getattr(self, 'current_tool_schema', 'default')
        if had_chat and self.backend_settings.get('auto_save_history', True):
            self._auto_save_conversation()
            msg = f"Chat: Saved with model '{model}' and settings [mode={mode}, prompt={prompt}, schema={schema}]\n\nSettings cleared: Starting new chat with default settings."
        else:
            msg = "Settings cleared: Starting new chat with default settings."
        self._skip_autosave_once = True
        try:
            self.clear_chat()
        finally:
            self._skip_autosave_once = False
        messagebox.showinfo("New Chat", msg)

    def delete_current_chat(self):
        """Delete current chat from history if saved; or discard unsaved chat."""
        from tkinter import messagebox
        if not self.chat_history_manager:
            messagebox.showerror("Error", "Chat history manager not initialized")
            return
        sid = self.current_session_id
        if sid:
            if not messagebox.askyesno("Delete Chat", f"Delete current chat from history?\n\nID: {sid}"):
                return
            ok = self.chat_history_manager.delete_conversation(sid)
            if ok:
                messagebox.showinfo("Deleted", "Conversation deleted from history")
                self._skip_autosave_once = True
                try:
                    self.clear_chat()
                finally:
                    self._skip_autosave_once = False
                if hasattr(self.parent_tab, 'refresh_history'):
                    try:
                        self.parent_tab.refresh_history()
                    except Exception:
                        pass
            else:
                messagebox.showerror("Error", "Failed to delete conversation")
        else:
            if not self.chat_history:
                messagebox.showinfo("Delete Chat", "No chat to delete.")
                return
            if messagebox.askyesno("Discard Unsaved Chat", "This chat has not been saved. Discard it?"):
                self._skip_autosave_once = True
                try:
                    self.clear_chat()
                finally:
                    self._skip_autosave_once = False

    def get_mode_parameters(self, mode):
        """Get default parameters for a specific mode"""
        mode_configs = {
            'standard': {
                'Resource Usage': 'Default',
                'Max Context Tokens': '4096',
                'Generation Step': '24 tokens',
                'CPU Threads': 'Default',
                'Token Caps (Reasoning)': '300',
                'Token Caps (Standard)': '200',
                'Token Caps (Structured)': '150',
                'Quality Mode': 'Standard',
                'Description': 'Standard settings for general use, without resource profiles.'
            },
            'fast': {
                'Resource Usage': '25% (conservative)',
                'Max Context Tokens': '3072',
                'Generation Step': '16 tokens',
                'CPU Threads': 'Minimal (1-2)',
                'Token Caps (Reasoning)': '200',
                'Token Caps (Standard)': '120',
                'Token Caps (Structured)': '90',
                'Quality Mode': 'Fast',
                'Description': 'Quick responses, minimal processing'
            },
            'smart': {
                'Resource Usage': '50% (balanced)',
                'Max Context Tokens': '5120',
                'Generation Step': '32 tokens',
                'CPU Threads': 'Half of available',
                'Token Caps (Reasoning)': '450',
                'Token Caps (Standard)': '300',
                'Token Caps (Structured)': '220',
                'Quality Mode': 'Auto/Smart',
                'Description': 'Balanced speed and intelligence'
            },
            'think': {
                'Resource Usage': '75% (aggressive)',
                'Max Context Tokens': '8192',
                'Generation Step': '48 tokens',
                'CPU Threads': 'Most available (n-2)',
                'Token Caps (Reasoning)': '900',
                'Token Caps (Standard)': '600',
                'Token Caps (Structured)': '350',
                'Quality Mode': 'Think (with verification)',
                'Think Time': 'Dynamic (configurable)',
                'Description': 'Deep reasoning, thorough analysis'
            }
        }
        return mode_configs.get(mode, mode_configs['smart'])

    def open_mode_selector(self):
        """Open quick mode selector dialog"""
        from tkinter import messagebox

        # Create dialog window
        dialog = tk.Toplevel(self.root)
        dialog.title("Quick Mode Selection")
        dialog.geometry("450x450")
        dialog.configure(bg='#2b2b2b')

        # Make modal
        dialog.transient(self.root)
        dialog.grab_set()

        # Center the dialog
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() // 2) - (450 // 2)
        y = (dialog.winfo_screenheight() // 2) - (450 // 2)
        dialog.geometry(f"450x450+{x}+{y}")

        # Main content
        content_frame = ttk.Frame(dialog, style='Category.TFrame')
        content_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        # Back bar and title
        backbar = ttk.Frame(content_frame)
        backbar.pack(fill=tk.X)
        ttk.Button(backbar, text='⬅', width=3, style='Select.TButton', command=dialog.destroy).pack(side=tk.LEFT)
        ttk.Label(backbar, text='⚡ Select Mode', font=("Arial", 14, "bold"), style='CategoryPanel.TLabel').pack(side=tk.LEFT, padx=6)
        ttk.Frame(content_frame, height=8).pack()  # small spacer

        # Load current mode from mode_settings.json (same as mode selector tab)
        mode_settings_file = Path(__file__).parent.parent / "mode_settings.json"
        try:
            with open(mode_settings_file, 'r') as f:
                settings = json.load(f)
            current_mode = settings.get('current_mode', 'smart')
        except Exception as e:
            log_message(f"CHAT_INTERFACE: Failed to load mode settings: {e}")
            current_mode = 'smart'

        # Mode buttons
        modes = [
            ('standard', '🔹 Standard', 'Balanced performance and capability'),
            ('fast', '⚡ Fast', 'Optimized for speed'),
            ('smart', '🧠 Smart', 'Enhanced reasoning and tools'),
            ('think', '💭 Think', 'Maximum capability and depth')
        ]

        selected_mode = tk.StringVar(value=current_mode)

        for mode_id, mode_name, mode_desc in modes:
            mode_frame = ttk.Frame(content_frame, style='Category.TFrame')
            mode_frame.pack(fill=tk.X, pady=5)

            rb = ttk.Radiobutton(
                mode_frame,
                text=mode_name,
                variable=selected_mode,
                value=mode_id,
                style='TRadiobutton'
            )
            rb.pack(anchor=tk.W)

            ttk.Label(
                mode_frame,
                text=mode_desc,
                font=("Arial", 8),
                style='Config.TLabel'
            ).pack(anchor=tk.W, padx=(25, 0))

        # Button frame
        btn_frame = ttk.Frame(content_frame, style='Category.TFrame')
        btn_frame.pack(pady=(20, 0))

        def apply_mode():
            """Apply the selected mode"""
            new_mode = selected_mode.get()
            try:
                # Load current settings
                with open(mode_settings_file, 'r') as f:
                    mode_settings = json.load(f)

                # Update mode
                mode_settings['current_mode'] = new_mode

                # Get default parameters for this mode
                mode_parameters = self.get_mode_parameters(new_mode)
                mode_settings['mode_parameters'] = mode_parameters

                # Save to mode_settings.json
                with open(mode_settings_file, 'w') as f:
                    json.dump(mode_settings, f, indent=2)

                log_message(f"CHAT_INTERFACE: Mode changed to {new_mode}")
                self.add_message("system", f"Mode changed to: {new_mode.upper()}")
                try:
                    self.current_mode = new_mode
                    self._update_quick_indicators()
                except Exception:
                    pass

                # Notify Advanced Settings tab about mode change
                if hasattr(self.parent_tab, 'settings_interface'):
                    if hasattr(self.parent_tab.settings_interface, 'on_mode_changed'):
                        self.parent_tab.settings_interface.on_mode_changed(new_mode)
                        log_message(f"CHAT_INTERFACE: Notified Advanced Settings of mode change to {new_mode}")

                # Apply mode to chat interface
                if hasattr(self, 'set_mode_parameters'):
                    self.set_mode_parameters(new_mode, mode_parameters)

                dialog.destroy()
            except Exception as e:
                log_message(f"CHAT_INTERFACE ERROR: Failed to save mode: {e}")
                messagebox.showerror("Error", f"Failed to save mode:\n{str(e)}")

        ok_btn = ttk.Button(
            btn_frame,
            text="✓ OK",
            command=apply_mode,
            style='Action.TButton',
            width=12
        )
        ok_btn.pack(side=tk.LEFT, padx=5)

        ttk.Button(
            btn_frame,
            text="✕ Cancel",
            command=dialog.destroy,
            style='Select.TButton',
            width=12
        ).pack(side=tk.LEFT, padx=5)

        # Bind Enter key to apply
        dialog.bind('<Return>', lambda e: apply_mode())
        dialog.bind('<Escape>', lambda e: dialog.destroy())

        # Focus the OK button
        ok_btn.focus_set()

    def redisplay_conversation(self):
        """Redisplay the entire conversation history"""
        self.chat_display.config(state=tk.NORMAL)
        self.chat_display.delete(1.0, tk.END)
        self.chat_display.config(state=tk.DISABLED)

        for msg in self.chat_history:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            self.add_message(role, content)

    def add_message(self, role, content):
        """Add a message to the chat display"""
        self.chat_display.config(state=tk.NORMAL)

        if role == "user":
            prefix = "You: "
            tag = "user"
        elif role == "assistant":
            prefix = f"{self.current_model}: "
            tag = "assistant"
        elif role == "system":
            prefix = "[System] "
            tag = "system"
        elif role == "error":
            prefix = "[Error] "
            tag = "error"
        else:
            prefix = ""
            tag = None

        # Add prefix with tag
        if tag:
            self.chat_display.insert(tk.END, prefix, tag)

        # Add content
        self.chat_display.insert(tk.END, content + "\n\n")

        # Auto-scroll to bottom
        self.chat_display.see(tk.END)
        self.chat_display.config(state=tk.DISABLED)

    def send_message(self):
        """Send message to Ollama model"""
        if not self.current_model:
            self.add_message("error", "Please select a model from the right panel first")
            return

        if self.is_generating:
            return

        # Get message text
        message = self.input_text.get(1.0, tk.END).strip()
        if not message:
            return

        # Clear input
        self.input_text.delete(1.0, tk.END)

        # If ThinkTime is set for next input, delay generation non-blockingly
        delay_secs = 0
        try:
            mn = self._think_next_min if isinstance(self._think_next_min, (int, float)) else None
            mx = self._think_next_max if isinstance(self._think_next_max, (int, float)) else None
            if mn is not None and mn < 0:
                mn = 0
            if mx is not None and mx < 0:
                mx = 0
            if mn is not None and mx is not None:
                if mx < mn:
                    mn, mx = mx, mn
                delay_secs = int(random.randint(int(mn), int(mx)))
            elif mn is not None:
                delay_secs = int(mn)
            elif mx is not None:
                delay_secs = int(mx)
        except Exception:
            delay_secs = 0

        if delay_secs and delay_secs > 0:
            try:
                self.add_message('system', f"⏱ Applying ThinkTime: waiting {delay_secs}s before sending…")
            except Exception:
                pass
            # Schedule send after delay, without losing the typed message
            self.send_btn.config(state=tk.DISABLED)
            self.stop_btn.config(state=tk.DISABLED)
            self.root.after(delay_secs * 1000, lambda m=message: self._start_generation(m))
        else:
            self._start_generation(message)

        # Clear one-shot ThinkTime
        self._think_next_min = None
        self._think_next_max = None
        try:
            self._update_quick_indicators()
        except Exception:
            pass

    def _start_generation(self, message: str):
        # Add user message to display
        self.add_message("user", message)

        # Add to history
        self.chat_history.append({"role": "user", "content": message})
        self._chat_dirty = True

        # Track for tool call validation
        self.last_user_message = message

        # Disable send button and enable stop button
        self.send_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        self.is_generating = True

        # Generate response in background thread
        threading.Thread(
            target=self.generate_response,
            args=(message,),
            daemon=True
        ).start()

    def open_think_time_dialog(self):
        """Popup to set ThinkTime min/max (seconds) for next input."""
        try:
            dlg = tk.Toplevel(self.root)
            dlg.title('Set Think Time (next input)')
            dlg.resizable(False, False)
            frm = ttk.Frame(dlg, padding=10)
            frm.pack(fill=tk.BOTH, expand=True)
            ttk.Label(frm, text='Min (seconds):', style='Config.TLabel').grid(row=0, column=0, sticky=tk.W, padx=(0,8), pady=4)
            min_var = tk.IntVar(value=int(self._think_next_min or 0))
            ttk.Spinbox(frm, from_=0, to=3600, textvariable=min_var, width=8).grid(row=0, column=1, sticky=tk.W, pady=4)
            ttk.Label(frm, text='Max (seconds):', style='Config.TLabel').grid(row=1, column=0, sticky=tk.W, padx=(0,8), pady=4)
            max_var = tk.IntVar(value=int(self._think_next_max or 0))
            ttk.Spinbox(frm, from_=0, to=7200, textvariable=max_var, width=8).grid(row=1, column=1, sticky=tk.W, pady=4)
            tip = ttk.Label(frm, text='Applies once to the next message. If both set, a random value in [min, max] is used.', style='Config.TLabel')
            tip.grid(row=2, column=0, columnspan=2, sticky=tk.W, pady=(4,8))
            btns = ttk.Frame(frm)
            btns.grid(row=3, column=0, columnspan=2, sticky=tk.EW)
            btns.columnconfigure(0, weight=1)
            btns.columnconfigure(1, weight=1)
            def _save():
                try:
                    a = int(min_var.get()); b = int(max_var.get())
                except Exception:
                    a, b = 0, 0
                self._think_next_min = max(0, a)
                self._think_next_max = max(0, b)
                try:
                    self.add_message('system', f"ThinkTime set for next input: min={self._think_next_min}s, max={self._think_next_max}s")
                except Exception:
                    pass
                try:
                    self._update_quick_indicators()
                except Exception:
                    pass
                dlg.destroy()
            ttk.Button(btns, text='Save', style='Action.TButton', command=_save).grid(row=0, column=0, padx=4, sticky=tk.EW)
            ttk.Button(btns, text='Cancel', style='Select.TButton', command=dlg.destroy).grid(row=0, column=1, padx=4, sticky=tk.EW)
            try:
                dlg.transient(self.root); dlg.lift(); dlg.attributes('-topmost', True); self.root.after(400, lambda: dlg.attributes('-topmost', False))
            except Exception:
                pass
        except Exception:
            pass

    # --- Training status popups (lightweight) ---------------------------
    def _on_training_started(self, event=None):
        try:
            import json as _json
            data = {}
            if event is not None and getattr(event, 'data', None):
                try:
                    data = _json.loads(event.data)
                except Exception:
                    data = {}
            vid = data.get('variant_id') or ''
            # Create popup
            self._training_popup = tk.Toplevel(self.root)
            self._training_popup.title('Training Progress')
            ttk.Label(self._training_popup, text=f"Variant: {vid or 'unknown'}", style='Config.TLabel').pack(padx=10, pady=(8,2))
            self._training_status_lbl = ttk.Label(self._training_popup, text="Training Status: Running…", style='Config.TLabel')
            self._training_status_lbl.pack(padx=10, pady=(0,8))
            # Progress bar
            self._training_progress = ttk.Progressbar(self._training_popup, mode='determinate', length=280)
            self._training_progress.pack(fill=tk.X, padx=10, pady=(0,8))
            btns = ttk.Frame(self._training_popup); btns.pack(fill=tk.X, padx=8, pady=(0,8))
            ttk.Button(btns, text='View Logs', style='Select.TButton', command=lambda: self.root.event_generate("<<FocusTrainingTab>>", when='tail')).pack(side=tk.LEFT)
            ttk.Button(btns, text='Hide', style='Select.TButton', command=self._training_popup.withdraw).pack(side=tk.RIGHT)
        except Exception:
            pass

    def _on_training_complete(self, event=None):
        try:
            if hasattr(self, '_training_status_lbl') and self._training_status_lbl:
                self._training_status_lbl.config(text='Training Status: Complete')
            if hasattr(self, '_training_progress') and self._training_progress:
                try:
                    self._training_progress['value'] = 100
                except Exception:
                    pass
            # Offer to Export + Re‑Eval (hands-free if enabled)
            import json as _json
            data = {}
            if event is not None and getattr(event, 'data', None):
                try:
                    data = _json.loads(event.data)
                except Exception:
                    data = {}
            vid = data.get('variant_id') or ''
            if self.backend_settings.get('auto_export_reeval_after_training', True):
                payload = _json.dumps({"variant_id": vid})
                self.root.event_generate("<<RequestAutoExportReEval>>", data=payload, when='tail')
        except Exception:
            pass

    def _on_training_progress(self, event=None):
        try:
            if not hasattr(self, '_training_progress') or self._training_progress is None:
                return
            import json as _json
            data = _json.loads(getattr(event, 'data', '{}') or '{}')
            cur = int(data.get('current', 0)); tot = int(data.get('total', 1) or 1)
            pct = max(0, min(100, int(cur * 100 / max(1, tot))))
            self._training_progress['value'] = pct
            if hasattr(self, '_training_status_lbl') and self._training_status_lbl:
                self._training_status_lbl.config(text=f'Training Status: Run {cur} of {tot} ({pct}%)')
        except Exception:
            pass

    def generate_response(self, message):
        """Generate response from Ollama with tool support (runs in background thread)"""
        try:
            log_message(f"CHAT_INTERFACE: Generating response for: {message[:50]}...")

            # Apply Intelligent Router (pre-process message)
            if self.router:
                try:
                    routing_result = self.router.route_intent(message)
                    if self.backend_settings.get('enable_debug_logging', False):
                        log_message(f"DEBUG: Router intent: {routing_result.get('intent', 'unknown')}, " +
                                   f"confidence: {routing_result.get('confidence', 0.0)}")
                except Exception as e:
                    if self.backend_settings.get('enable_debug_logging', False):
                        log_message(f"DEBUG: Router error: {e}")

            # Apply Pre-RAG Optimizer (optimize chat history)
            chat_history_to_use = self.chat_history
            if self.pre_rag_optimizer:
                try:
                    # Combine chat history into single string for optimization
                    history_text = "\n".join([f"{msg['role']}: {msg['content']}" for msg in self.chat_history])
                    optimized = self.pre_rag_optimizer.optimize_context(history_text)
                    if self.backend_settings.get('enable_debug_logging', False):
                        log_message(f"DEBUG: Pre-RAG compression ratio: {optimized.get('compression_ratio', 1.0)}")
                    # Note: For now we still use original history, full integration would reconstruct from optimized
                except Exception as e:
                    if self.backend_settings.get('enable_debug_logging', False):
                        log_message(f"DEBUG: Pre-RAG Optimizer error: {e}")

            # Apply Context Scorer (score context quality)
            if self.context_scorer:
                try:
                    score_result = self.context_scorer.score_context(chat_history_to_use)
                    if self.backend_settings.get('enable_debug_logging', False):
                        log_message(f"DEBUG: Context score: {score_result.get('final_score', 0.0)}, " +
                                   f"target_met: {score_result.get('target_met', False)}")
                except Exception as e:
                    if self.backend_settings.get('enable_debug_logging', False):
                        log_message(f"DEBUG: Context Scorer error: {e}")

            # Get enabled tool schemas (filtered by current schema config)
            tool_schemas = self.get_tool_schemas()
            schema_config = self.get_current_tool_schema_config()
            if schema_config.get("enabled_tools") != "all":
                enabled_list = schema_config.get("enabled_tools", [])
                tool_schemas = [t for t in tool_schemas if t['function']['name'] in enabled_list]

            # Inject system prompt and optional RAG context at the start of conversation
            system_prompt = self.get_current_system_prompt()
            messages_with_system = [{"role": "system", "content": system_prompt}]
            try:
                if self._is_rag_active():
                    lvl = int(getattr(self, 'panel_rag_level', 0) or 0)
                    if lvl <= 0 and getattr(self, 'rag_enabled', False):
                        lvl = 1
                    if lvl >= 3:
                        top_k, max_chars, per_snip = 6, 3600, 900
                    elif lvl == 2:
                        top_k, max_chars, per_snip = 4, 2400, 800
                    else:
                        top_k, max_chars, per_snip = 2, 1200, 600
                    # Refresh index and query (scoped to project if applicable)
                    scope = None
                    try:
                        scope = self._rag_query_scope()
                    except Exception:
                        scope = None
                    try:
                        if scope:
                            self.rag_service.refresh_index_project(scope)
                        else:
                            self.rag_service.refresh_index_global()
                    except Exception:
                        pass
                    results = self.rag_service.query(message, top_k=top_k, scope=scope)
                    # If in Chat (no project scope) and adapters configured, merge adapter project results
                    if not scope and getattr(self, 'rag_project_adapters', []):
                        merged = list(results)
                        for pname in self.rag_project_adapters:
                            try:
                                self.rag_service.refresh_index_project(pname)
                                merged.extend(self.rag_service.query(message, top_k=top_k, scope=pname))
                            except Exception:
                                continue
                        # Sort merged by score desc and unique by (session_id, index)
                        uniq = {}
                        for doc, score in merged:
                            key = (doc.session_id, int(getattr(doc, 'index', -1)))
                            if key not in uniq or score > uniq[key][1]:
                                uniq[key] = (doc, score)
                        results = sorted(uniq.values(), key=lambda x: x[1], reverse=True)[:top_k]
                    buf = []
                    dbg = []
                    total = 0
                    top1_score = None
                    for rank, (doc, score) in enumerate(results, 1):
                        snip = (doc.text or '')[:per_snip]
                        part = f"[Context {rank}] (session={doc.session_id}, score={score:.3f})\n{snip}"
                        if total + len(part) + 2 > max_chars:
                            break
                        buf.append(part)
                        total += len(part) + 2
                        if getattr(self, 'rag_debug_enabled', False):
                            dbg.append(f"{rank}. {doc.session_id} score={score:.3f}")
                        if top1_score is None:
                            top1_score = float(score)
                    rag_ctx = "\n\n".join(buf)
                    # Optional Pre-RAG optimization on context before injection
                    try:
                        if getattr(self, 'pre_rag_optimizer', None):
                            try:
                                # Prefer comprehensive optimizer if available
                                from opencode.pre_rag_optimizer import ContentType
                                maybe = self.pre_rag_optimizer.optimize_content_comprehensive(
                                    rag_ctx, ContentType.CONVERSATION, target_size=None, optimization_level="balanced"
                                )
                                # Handle coroutine or direct result
                                try:
                                    import asyncio
                                    if asyncio.iscoroutine(maybe):
                                        res = asyncio.get_event_loop().run_until_complete(maybe)
                                    else:
                                        res = maybe
                                    rag_ctx = getattr(res, 'optimized_content', rag_ctx) or rag_ctx
                                except Exception:
                                    pass
                            except Exception:
                                # Fallback: try a simple optimize_context if present
                                try:
                                    rag_ctx = self.pre_rag_optimizer.optimize_context(rag_ctx).get('optimized', rag_ctx)
                                except Exception:
                                    pass
                    except Exception:
                        pass
                    if rag_ctx:
                        messages_with_system.append({
                            "role": "system",
                            "content": f"RAG Context (from enabled chats):\n{rag_ctx}"
                        })
                        if getattr(self, 'rag_debug_enabled', False) and dbg:
                            try:
                                self.add_message('system', "🧠 RAG DEBUG:\n" + "\n".join(dbg))
                            except Exception:
                                pass
                    # Update auto-training window with top1 score
                    try:
                        if top1_score is not None:
                            self._rag_recent_scores.append(float(top1_score))
                            if len(self._rag_recent_scores) > max(1, int(self.rag_autotrain_window)):
                                self._rag_recent_scores = self._rag_recent_scores[-int(self.rag_autotrain_window):]
                    except Exception:
                        pass
            except Exception as e:
                log_message(f"CHAT_INTERFACE: RAG context build failed: {e}")
            messages_with_system += chat_history_to_use

            # Prepare the chat payload
            payload = {
                "model": self.current_model,
                "messages": messages_with_system,
                "stream": False,
                "options": {
                    "temperature": self.session_temperature
                }
            }

            # NOTE: We do NOT add tools to the payload using Ollama's native API
            # Instead, tool schemas are embedded in the system prompt, and the model
            # learns to output tool calls in text format which are detected by Format Translator
            # This approach works with ANY model, not just those supporting Ollama's tools API
            if tool_schemas:
                log_message(f"CHAT_INTERFACE: {len(tool_schemas)} tool schemas available (embedded in system prompt)")

            # Call Ollama API via HTTP (using curl as subprocess)
            import tempfile
            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
                json.dump(payload, f)
                payload_file = f.name

            try:
                if self.show_thoughts:
                    # Streaming mode: read JSONL lines and preview partial content
                    import subprocess as sp
                    cmd = [
                        "curl", "-s", "-N", "-X", "POST", "http://localhost:11434/api/chat",
                        "-H", "Content-Type: application/json",
                        "-d", f"@{payload_file}"
                    ]
                    # Force stream=true in runtime by patching payload file (simple replace)
                    try:
                        payload = json.loads(Path(payload_file).read_text())
                        payload["stream"] = True
                        Path(payload_file).write_text(json.dumps(payload))
                    except Exception:
                        pass
                    proc = sp.Popen(cmd, stdout=sp.PIPE, stderr=sp.PIPE, text=True, bufsize=1)
                    final_text_chunks = []
                    def _append_thought(txt):
                        try:
                            self.root.after(0, lambda t=txt: self.chat_display.config(state=tk.NORMAL) or self.chat_display.insert(tk.END, t, 'thought') or self.chat_display.see(tk.END) or self.chat_display.config(state=tk.DISABLED))
                        except Exception:
                            pass
                    for line in proc.stdout:
                        line = line.strip()
                        if not line:
                            continue
                        # Each line is JSON for stream event
                        try:
                            obj = json.loads(line)
                            msg = obj.get('message', {})
                            chunk = msg.get('content', '')
                            if chunk:
                                final_text_chunks.append(chunk)
                                _append_thought(chunk)
                            if obj.get('done', False):
                                break
                        except Exception:
                            # Fallback: append raw
                            final_text_chunks.append('')
                    stdout_full = "".join(final_text_chunks)
                    stderr_full = ''
                    class _Res:
                        returncode = 0
                        stdout = stdout_full
                        stderr = stderr_full
                    result = _Res()
                else:
                    result = subprocess.run(
                        ["curl", "-s", "-X", "POST", "http://localhost:11434/api/chat",
                         "-H", "Content-Type: application/json",
                         "-d", f"@{payload_file}"],
                        capture_output=True,
                        text=True,
                        timeout=120
                    )
            finally:
                Path(payload_file).unlink(missing_ok=True)

            if result.returncode != 0:
                error_msg = f"Ollama error: {getattr(result,'stderr','')}"
                log_message(f"CHAT_INTERFACE ERROR: {error_msg}")
                self.root.after(0, lambda: self.add_message("error", error_msg))
            else:
                # Log raw response for debugging
                log_message(f"CHAT_INTERFACE DEBUG: Raw Ollama response (first 1000 chars): {getattr(result,'stdout','')[:1000]}")

                # Parse response (with JSON Fixer if enabled)
                if self.json_fixer_enabled:
                    try:
                        response_data = self.smart_json_parse(getattr(result,'stdout',''))
                        if self.backend_settings.get('enable_debug_logging', False):
                            log_message("DEBUG: JSON Fixer used to parse response")
                    except Exception as e:
                        if self.backend_settings.get('enable_debug_logging', False):
                            log_message(f"DEBUG: JSON Fixer failed, falling back to standard JSON: {e}")
                        response_data = json.loads(getattr(result,'stdout',''))
                else:
                    response_data = json.loads(getattr(result,'stdout',''))

                # Check if Ollama returned an error
                if "error" in response_data:
                    error_msg = response_data["error"]
                    log_message(f"CHAT_INTERFACE ERROR: Ollama API error: {error_msg}")
                    self.root.after(0, lambda: self.add_message("error", f"Ollama error: {error_msg}"))
                    return

                message_data = response_data.get("message", {})

                # Training mode: log RAG retrieval record for dataset generation
                try:
                    if bool(getattr(self, 'training_mode_enabled', False)) and self._is_rag_active():
                        self._log_rag_training_example(query=message)
                        # Auto-training trigger
                        self._maybe_trigger_auto_training()
                except Exception:
                    pass

    

                # Apply Quality Assurance to response if enabled
                if self.quality_assurance:
                    try:
                        qa_result = self.quality_assurance.assess_quality(response_data)
                        if self.backend_settings.get('enable_debug_logging', False):
                            log_message(f"DEBUG: QA assessment score: {qa_result.get('score', 0.0)}, " +
                                       f"passed: {qa_result.get('passed', True)}")

                        # Auto-recovery if enabled and QA failed
                        if self.advanced_settings.get('quality_assurance', {}).get('auto_recovery', True):
                            if not qa_result.get('passed', True):
                                if self.backend_settings.get('enable_debug_logging', False):
                                    log_message(f"DEBUG: QA auto-recovery triggered due to low quality")
                                # Could implement retry logic here
                    except Exception as e:
                        if self.backend_settings.get('enable_debug_logging', False):
                            log_message(f"DEBUG: Quality Assurance error: {e}")

                # Apply Format Translator if enabled and no standard tool_calls
                tool_calls = message_data.get("tool_calls", [])
                if not tool_calls and self.format_translator:
                    try:
                        response_content = message_data.get("content", "")
                        translated = self.format_translator.translate(response_content)
                        if translated:
                            if self.backend_settings.get('enable_debug_logging', False):
                                log_message(f"DEBUG: Format Translator detected tool call: {translated.get('name', 'unknown')}")
                            # Convert to Ollama tool_call format
                            tool_calls = [{
                                "function": {
                                    "name": translated.get("name", ""),
                                    "arguments": translated.get("args", {})
                                }
                            }]
                    except Exception as e:
                        if self.backend_settings.get('enable_debug_logging', False):
                            log_message(f"DEBUG: Format Translator error: {e}")

                # Check for tool calls
                if tool_calls:
                    # Model wants to use tools
                    log_message(f"CHAT_INTERFACE: Model requested {len(tool_calls)} tool calls")
                    self.root.after(0, lambda: self.handle_tool_calls(tool_calls, message_data))
                else:
                    # Regular response
                    response_content = message_data.get("content", "")

                    # Check if response is empty
                    if not response_content or response_content.strip() == "":
                        log_message("CHAT_INTERFACE WARNING: Model returned empty response")
                        log_message(f"CHAT_INTERFACE DEBUG: Full response data: {response_data}")
                        response_content = "[Model returned empty response]"

                    # Add to history
                    self.chat_history.append({"role": "assistant", "content": response_content})
                    self._chat_dirty = True

                    # Display response
                    self.root.after(0, lambda: self.add_message("assistant", response_content))
                    log_message("CHAT_INTERFACE: Response generated successfully")

                    # Auto-save conversation
                    if self.backend_settings.get('auto_save_history', True):
                        self.root.after(0, self._auto_save_conversation)

        except subprocess.TimeoutExpired:
            error_msg = "Request timed out after 120 seconds"
            log_message(f"CHAT_INTERFACE ERROR: {error_msg}")
            self.root.after(0, lambda: self.add_message("error", error_msg))
        except Exception as e:
            error_msg = f"Error generating response: {str(e)}"
            log_message(f"CHAT_INTERFACE ERROR: {error_msg}")
            self.root.after(0, lambda: self.add_message("error", error_msg))
        finally:
            # Re-enable send button and disable stop button
            self.root.after(0, self.reset_buttons)

    def reset_buttons(self):
        """Reset button states after generation"""
        self.is_generating = False
        self.send_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)

    def _maybe_trigger_auto_training(self):
        try:
            if not bool(getattr(self, 'training_mode_enabled', False)):
                return
            if not bool(getattr(self, 'rag_autotrain_enabled', False)):
                return
            # Gate by class promotion unless backend override
            if bool(getattr(self, 'rag_autotrain_require_promotion_gate', True)):
                if not (bool(getattr(self, 'class_promotion_earned', False)) or bool(getattr(self, 'rag_autotrain_backend_override', False))):
                    return
            if not self._rag_recent_scores:
                return
            import time, json as _json
            avg = sum(self._rag_recent_scores) / max(1, len(self._rag_recent_scores))
            if avg < float(self.rag_autotrain_threshold):
                return
            # cooldown: 5 minutes
            now = int(time.time())
            if now - int(self._rag_last_trigger_ts) < 300:
                return
            self._rag_last_trigger_ts = now
            payload = _json.dumps({
                'model_name': (self.current_model or ''),
                'avg_rag_score': avg,
                'window': int(self.rag_autotrain_window)
            })
            try:
                self.root.event_generate("<<StartVariantTraining>>", data=payload, when='tail')
                self.add_message('system', f"🤖 Auto-Training Triggered (avg={avg:.3f} over {len(self._rag_recent_scores)}).")
            except Exception:
                pass
        except Exception:
            pass

    def stop_generation(self):
        """Stop ongoing generation (placeholder)"""
        # Note: subprocess doesn't easily support stopping mid-execution
        # This is a placeholder for future streaming implementation
        log_message("CHAT_INTERFACE: Stop requested (not fully implemented)")
        self.add_message("system", "Stop requested - waiting for current generation to complete")

    def handle_tool_calls(self, tool_calls, message_data):
        """Handle tool calls from model response"""
        log_message(f"CHAT_INTERFACE: Handling {len(tool_calls)} tool calls")

        # Add assistant message with tool calls to history
        self.chat_history.append(message_data)

        # Get enabled tools from Tools tab
        enabled_tools = []
        if hasattr(self.parent_tab, 'tools_interface') and self.parent_tab.tools_interface:
            enabled_tools = self.parent_tab.tools_interface.get_enabled_tools()
            log_message(f"CHAT_INTERFACE: {len(enabled_tools)} tools are enabled in Tools tab")
        else:
            log_message("CHAT_INTERFACE WARNING: Tools tab not available, allowing all tools")
            enabled_tools = None  # None means allow all

        # Display tool execution message
        self.add_message("system", f"🔧 Executing {len(tool_calls)} tool(s)...")

        # Execute each tool
        tool_results = []
        for tool_call in tool_calls:
            function_data = tool_call.get("function", {})
            tool_name = function_data.get("name")
            arguments = function_data.get("arguments", {})

            # Check if tool is enabled in Tools tab
            if enabled_tools is not None and tool_name not in enabled_tools:
                log_message(f"CHAT_INTERFACE: Tool '{tool_name}' is DISABLED in Tools tab, skipping")
                self.add_message("system", f"  ✗ {tool_name}: Tool is disabled in Tools tab")
                tool_results.append({
                    "role": "tool",
                    "content": json.dumps({"error": "Tool is disabled in settings"}),
                    "tool_call_id": tool_call.get("id", ""),
                    "name": tool_name
                })
                continue

            # Parse arguments if they're a JSON string (with JSON Fixer if enabled)
            if isinstance(arguments, str):
                try:
                    if self.json_fixer_enabled:
                        arguments = self.smart_json_parse(arguments)
                        if self.backend_settings.get('enable_debug_logging', False):
                            log_message(f"DEBUG: JSON Fixer parsed tool arguments")
                    else:
                        arguments = json.loads(arguments)
                except json.JSONDecodeError:
                    log_message(f"CHAT_INTERFACE ERROR: Failed to parse tool arguments: {arguments}")
                    arguments = {}

            # Apply Schema Validator if enabled
            if self.schema_validator:
                try:
                    validation_result = self.schema_validator.validate(tool_name, arguments)
                    if not validation_result.get('valid', True):
                        if self.backend_settings.get('enable_debug_logging', False):
                            log_message(f"DEBUG: Schema validation failed for {tool_name}: {validation_result.get('errors', [])}")
                        # Optionally skip invalid tool calls based on mode
                        if self.advanced_settings.get('schema_validation', {}).get('mode') == 'strict':
                            self.add_message("error", f"  ✗ {tool_name}: Schema validation failed")
                            continue
                    else:
                        if self.backend_settings.get('enable_debug_logging', False):
                            log_message(f"DEBUG: Schema validation passed for {tool_name}")
                except Exception as e:
                    if self.backend_settings.get('enable_debug_logging', False):
                        log_message(f"DEBUG: Schema Validator error: {e}")

            log_message(f"CHAT_INTERFACE: Executing tool: {tool_name} with args: {arguments}")

            # Show detailed tool call info if enabled in settings
            show_details = self.backend_settings.get('show_tool_call_details', True)
            if show_details:
                self.add_message("system", f"  → {tool_name}({', '.join(f'{k}={v}' for k, v in arguments.items())})")

            # Execute tool (via Orchestrator if enabled, otherwise direct)
            if self.tool_orchestrator:
                # Use Tool Orchestrator for intelligent execution
                try:
                    if self.backend_settings.get('enable_debug_logging', False):
                        log_message(f"DEBUG: Using Tool Orchestrator for {tool_name}")
                    # Orchestrator expects a chain of operations
                    # For now, create single-tool chain
                    orchestrator_result = self.tool_orchestrator.execute_tool_with_gates(
                        tool_name, arguments
                    )
                    result = {
                        'success': orchestrator_result.get('success', False),
                        'output': orchestrator_result.get('output', ''),
                        'error': orchestrator_result.get('error')
                    }
                except Exception as e:
                    if self.backend_settings.get('enable_debug_logging', False):
                        log_message(f"DEBUG: Tool Orchestrator error, falling back to direct execution: {e}")
                    # Fallback to direct execution
                    result = self.tool_executor.execute_tool_sync(tool_name, arguments)
            elif self.tool_executor:
                # Direct execution
                result = self.tool_executor.execute_tool_sync(tool_name, arguments)
            else:
                result = {'success': False, 'output': '', 'error': 'Tool executor not initialized'}

            # Apply Verification Engine to result if enabled
            if self.verification_engine and result['success']:
                try:
                    verification_result = self.verification_engine.verify_output(
                        tool_name, result['output']
                    )
                    if self.backend_settings.get('enable_debug_logging', False):
                        log_message(f"DEBUG: Verification result for {tool_name}: " +
                                   f"passed={verification_result.get('passed', True)}")

                    # Auto-fix if enabled and verification suggests fixes
                    if self.advanced_settings.get('verification', {}).get('auto_fix', True):
                        if verification_result.get('fixed_output'):
                            result['output'] = verification_result['fixed_output']
                            if self.backend_settings.get('enable_debug_logging', False):
                                log_message(f"DEBUG: Auto-fixed output for {tool_name}")
                except Exception as e:
                    if self.backend_settings.get('enable_debug_logging', False):
                        log_message(f"DEBUG: Verification Engine error: {e}")

            # Process result
            if result['success']:
                if show_details:
                    output_preview = result['output'][:200] if len(result['output']) > 200 else result['output']
                    self.add_message("system", f"  ✓ {tool_name}: {output_preview}")
                tool_results.append({
                    "role": "tool",
                    "content": result['output']
                })
            else:
                error_msg = result.get('error', 'Unknown error')
                self.add_message("error", f"  ✗ {tool_name}: {error_msg}")
                tool_results.append({
                    "role": "tool",
                    "content": f"Error: {error_msg}"
                })

        # Add tool results to history
        self.chat_history.extend(tool_results)

        # Log for training and real-time evaluation if enabled
        if self.training_mode_enabled:
            try:
                model_name = self.current_model

                # Use ToolCallLogger for training data logging
                if self.tool_call_logger:
                    self.tool_call_logger.log_training_example(self.chat_history.copy(), model_name)
                    self.tool_call_logger.log_batch_tool_calls(tool_calls, tool_results, model_name)
                    log_message(f"CHAT_INTERFACE: Logged tool calls via ToolCallLogger")

                # Perform real-time evaluation scoring
                if model_name not in self.realtime_eval_scores:
                    self.realtime_eval_scores[model_name] = {}

                for tool_call, res in zip(tool_calls, tool_results):
                    tool_name = tool_call.get("function", {}).get("name")
                    if tool_name not in self.realtime_eval_scores[model_name]:
                        self.realtime_eval_scores[model_name][tool_name] = {"success": 0, "failure": 0, "errors": []}

                    # Enhanced success validation
                    is_success, failure_reason = self._validate_tool_call_success(
                        tool_call, res, self.last_user_message
                    )

                    if is_success:
                        self.realtime_eval_scores[model_name][tool_name]["success"] += 1
                    else:
                        self.realtime_eval_scores[model_name][tool_name]["failure"] += 1
                        error_msg = f"{failure_reason}: {res['content'][:200]}"
                        self.realtime_eval_scores[model_name][tool_name]["errors"].append(error_msg)

                log_message(f"CHAT_INTERFACE: Updated real-time scores for {model_name}: {self.realtime_eval_scores[model_name]}")
                self.add_message("system", f"📈 Real-time score updated for {model_name}.")

            except Exception as e:
                log_message(f"CHAT_INTERFACE ERROR: Failed during training mode operation: {e}")
                self.add_message("error", f"Failed to process training data: {e}")

            # MVP: Generate strict runtime JSONL for failed calls and notify Training tab
            try:
                import json as _json
                import config as C
                from ..runtime_to_training import RuntimeToTrainingConverter as _RT

                # Resolve variant from mounted model tag (lineage-aware)
                tag = self.current_model or ""
                vid = None
                assigned_type = None
                try:
                    lid = C.get_lineage_for_tag(tag)
                except Exception:
                    lid = None
                if lid:
                    # First try assignments map
                    try:
                        data = C.load_ollama_assignments() or {}
                        for k, v in data.items():
                            if k == 'tag_index':
                                continue
                            if isinstance(v, dict) and v.get('lineage_id') == lid:
                                vid = k
                                break
                    except Exception:
                        pass
                    # Fallback: scan model profiles
                    if not vid:
                        try:
                            for rec in (C.list_model_profiles() or []):
                                if rec.get('lineage_id') == lid:
                                    vid = rec.get('variant_id')
                                    break
                        except Exception:
                            pass
                # Load assigned_type when variant resolved
                if vid:
                    try:
                        mp = C.load_model_profile(vid) or {}
                        at = mp.get('assigned_type')
                        assigned_type = at[0] if isinstance(at, list) else at
                    except Exception:
                        assigned_type = None

                # Build strict JSONL for failed tool calls only; if none, synthesize from refusal
                synth_calls = []
                synth_results = []
                if not tool_calls:
                    # Check refusal patterns in last assistant message
                    if self.chat_history and self.chat_history[-1].get('role') == 'assistant':
                        atext = (self.chat_history[-1].get('content') or '').lower()
                        refusal = any(ph in atext for ph in ["i can't", "i cannot", "i won'", "not allowed", "refuse", "unable to"]) or ('no ' in atext and 'permission' in atext)
                        if refusal:
                            guess = self._guess_tool_from_prompt(self.last_user_message)
                            synth_calls = [{"function": {"name": guess, "arguments": {}}}]
                            synth_results = [{"content": "Error: refusal"}]
                tcalls = tool_calls or synth_calls
                tresults = tool_results or synth_results
                out_path, wrote = _RT.write_strict_runtime_jsonl(
                    model_tag=tag,
                    variant_id=vid or (self.current_model or 'unknown'),
                    assigned_type=assigned_type or 'Unknown',
                    user_input=self.last_user_message or '',
                    tool_calls=tcalls,
                    tool_results=tresults,
                    include_success=False
                )
                if wrote > 0 and out_path:
                    self.add_message("system", f"📚 Generated runtime training set ({wrote}) → {out_path}")
                    # Notify Training tab to select and persist
                    try:
                        payload = _json.dumps({"variant_id": vid, "path": out_path})
                        self.root.event_generate("<<RuntimeTrainingDataReady>>", data=payload, when="tail")
                    except Exception:
                        pass
                    # Auto-start training if enabled; else prompt user
                    try:
                        if self.backend_settings.get('auto_start_training_on_runtime_dataset', False):
                            spayload = _json.dumps({"variant_id": vid})
                            self.root.event_generate("<<StartVariantTraining>>", data=spayload, when="tail")
                        else:
                            self._prompt_train_now(vid)
                    except Exception:
                        pass
            except Exception as e:
                log_message(f"CHAT_INTERFACE: strict runtime JSONL generation skipped ({e})")

    def _guess_tool_from_prompt(self, prompt: str) -> str:
        p = (prompt or '').lower()
        if any(k in p for k in ['read file', 'open file', 'view file', 'cat ', 'read ', 'contents of']):
            return 'file_read'
        if any(k in p for k in ['write file', 'save file', 'create file', 'append', 'overwrite']):
            return 'file_write'
        if any(k in p for k in ['search', 'find', 'grep', 'pattern']):
            return 'grep_search'
        if any(k in p for k in ['list files', 'ls', 'dir ']):
            return 'bash'
        if any(k in p for k in ['web', 'http', 'url', 'scrape']):
            return 'web_search'
        return 'file_read'

    def _prompt_train_now(self, variant_id: str | None):
        """Small confirm dialog to start training on the newly generated dataset."""
        from tkinter import messagebox
        try:
            if not variant_id:
                # Still allow user to go to Training tab manually
                if messagebox.askyesno("Training", "Training data created. Open Training tab?"):
                    # Fire a simple event that other parts can use to focus Training
                    self.root.event_generate("<<FocusTrainingTab>>", when="tail")
                return
            if messagebox.askyesno("Training", "Training data created. Start training now?"):
                import json as _json
                payload = _json.dumps({"variant_id": variant_id})
                # Ensure selection/persist happened before start
                self.root.event_generate("<<StartVariantTraining>>", data=payload, when="tail")
        except Exception:
            pass

        # Send tool results back to model for final response
        self.add_message("system", "📨 Sending tool results to model...")
        threading.Thread(
            target=self.generate_final_response_after_tools,
            daemon=True
        ).start()

    def generate_final_response_after_tools(self):
        """Generate final response after tool execution"""
        try:
            log_message("CHAT_INTERFACE: Generating final response after tool execution")

            # Prepare payload with tool results
            payload = {
                "model": self.current_model,
                "messages": self.chat_history,
                "stream": False,
                "options": {
                    "temperature": self.session_temperature
                }
            }

            # Call Ollama API
            import tempfile
            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
                json.dump(payload, f)
                payload_file = f.name

            try:
                result = subprocess.run(
                    ["curl", "-s", "-X", "POST", "http://localhost:11434/api/chat",
                     "-H", "Content-Type: application/json",
                     "-d", f"@{payload_file}"],
                    capture_output=True,
                    text=True,
                    timeout=120
                )
            finally:
                Path(payload_file).unlink(missing_ok=True)

            if result.returncode != 0:
                error_msg = f"Ollama error: {result.stderr}"
                log_message(f"CHAT_INTERFACE ERROR: {error_msg}")
                self.root.after(0, lambda: self.add_message("error", error_msg))
            else:
                # Parse final response
                response_data = json.loads(result.stdout)
                response_content = response_data.get("message", {}).get("content", "")

                # Add to history
                self.chat_history.append({"role": "assistant", "content": response_content})

                # Display response
                self.root.after(0, lambda: self.add_message("assistant", response_content))
                log_message("CHAT_INTERFACE: Final response generated successfully")

                # Auto-save conversation
                if self.backend_settings.get('auto_save_history', True):
                    self.root.after(0, self._auto_save_conversation)

        except Exception as e:
            error_msg = f"Error generating final response: {str(e)}"
            log_message(f"CHAT_INTERFACE ERROR: {error_msg}")
            self.root.after(0, lambda: self.add_message("error", error_msg))
        finally:
            self.root.after(0, self.reset_buttons)

    def initialize_tool_executor(self):
        """Initialize the tool executor"""
        try:
            sys.path.insert(0, str(Path(__file__).parent.parent))
            from tool_executor import ToolExecutor

            # Get working directory from settings if available
            working_dir = None
            if hasattr(self, 'backend_settings'):
                working_dir_str = self.backend_settings.get('working_directory')
                if working_dir_str:
                    working_dir = Path(working_dir_str)

            self.tool_executor = ToolExecutor(working_dir=working_dir)
            log_message(f"CHAT_INTERFACE: Tool executor initialized with working dir: {self.tool_executor.working_dir}")
        except Exception as e:
            log_message(f"CHAT_INTERFACE ERROR: Failed to initialize tool executor: {e}")
            self.tool_executor = None

    def initialize_tool_logging(self):
        """Initialize tool call logger and detector"""
        try:
            sys.path.insert(0, str(Path(__file__).parent.parent))
            from tool_call_logger import ToolCallLogger
            from tool_call_detector import ToolCallDetector

            self.tool_call_logger = ToolCallLogger()
            self.tool_call_detector = ToolCallDetector()
            log_message("CHAT_INTERFACE: Tool call logger and detector initialized")
        except Exception as e:
            log_message(f"CHAT_INTERFACE ERROR: Failed to initialize tool logging: {e}")
            self.tool_call_logger = None
            self.tool_call_detector = None

    def initialize_history_manager(self):
        """Initialize chat history manager"""
        try:
            sys.path.insert(0, str(Path(__file__).parent.parent))
            from chat_history_manager import ChatHistoryManager

            self.chat_history_manager = ChatHistoryManager()
            log_message("CHAT_INTERFACE: Chat history manager initialized")
        except Exception as e:
            log_message(f"CHAT_INTERFACE ERROR: Failed to initialize history manager: {e}")
            self.chat_history_manager = None

    def load_enabled_tools(self):
        """Load enabled tools from settings"""
        tool_settings_file = Path(__file__).parent.parent / "tool_settings.json"

        if tool_settings_file.exists():
            try:
                with open(tool_settings_file, 'r') as f:
                    settings = json.load(f)
                return settings.get('enabled_tools', {})
            except Exception as e:
                log_message(f"CHAT_INTERFACE ERROR: Failed to load tool settings: {e}")

        # Default: all safe tools enabled
        return {}

    def get_tool_schemas(self):
        """Get Ollama tool schemas for enabled tools"""
        try:
            from tool_schemas import get_enabled_tool_schemas
            # Prefer session overrides if present
            enabled_tools = getattr(self, 'session_enabled_tools', None)
            if not enabled_tools:
                enabled_tools = self.load_enabled_tools()
            schemas = get_enabled_tool_schemas(enabled_tools)

            log_message(f"CHAT_INTERFACE: Loaded {len(schemas)} enabled tool schemas")
            return schemas

        except Exception as e:
            log_message(f"CHAT_INTERFACE ERROR: Failed to load tool schemas: {e}")
            return []

    def _list_all_tools(self):
        try:
            sys.path.insert(0, str(Path(__file__).parent.parent / 'site-packages'))
            from opencode.tools import ToolManager
            from opencode.config import ToolsConfig
            cfg = ToolsConfig()
            tm = ToolManager(cfg)
            names = set()
            # Everything registered
            names.update(list(tm.tools.keys()))
            # Plus anything enabled in config defaults (some envs only register a subset)
            names.update(list(getattr(cfg, 'enabled', []) or []))
            # Ensure a representative superset in case registry is minimal
            if len(names) < 10:
                names.update([
                    'file_read','file_write','file_edit','file_copy','file_move','file_delete','file_create','file_fill',
                    'file_search','directory_list','grep_search','bash_execute','process_manage','git_operations',
                    'web_search','web_fetch','code_analyze','package_check','system_info','resource_request','change_directory'
                ])
            return sorted(list(names))
        except Exception:
            return sorted([
                'file_read','file_write','file_edit','file_copy','file_move','file_delete','file_create','file_fill',
                'file_search','directory_list','grep_search','bash_execute','process_manage','git_operations',
                'web_search','web_fetch','code_analyze','package_check','system_info','resource_request','change_directory'
            ])

    def load_backend_settings(self):
        """Load backend settings from custom_code_settings.json"""
        settings_file = Path(__file__).parent.parent / "custom_code_settings.json"

        if settings_file.exists():
            try:
                with open(settings_file, 'r') as f:
                    settings = json.load(f)
                    # Ensure left pane lock defaults to ON at launch
                    settings['conv_locked'] = True
                    log_message("CHAT_INTERFACE: Backend settings loaded")
                    return settings
            except Exception as e:
                log_message(f"CHAT_INTERFACE ERROR: Failed to load backend settings: {e}")

        # Return defaults
        return {
            'working_directory': str(Path.cwd()),
            'auto_mount_model': False,
            'auto_save_history': True,
            'show_tool_call_details': True,
            'tool_timeout': 30,
            'training_mode_enabled': False,
            'auto_start_training_on_runtime_dataset': False,
            'auto_export_reeval_after_training': True,
            'conv_locked': True,
            'conv_width': 240,
        }

    def load_advanced_settings(self):
        """Load advanced settings from advanced_settings.json"""
        settings_file = Path(__file__).parent.parent / "advanced_settings.json"

        if settings_file.exists():
            try:
                with open(settings_file, 'r') as f:
                    settings = json.load(f)
                    log_message("CHAT_INTERFACE: Advanced settings loaded")
                    return settings
            except Exception as e:
                log_message(f"CHAT_INTERFACE ERROR: Failed to load advanced settings: {e}")

        # Return defaults (all disabled)
        return {
            'format_translation': {'enabled': False},
            'json_repair': {'enabled': False},
            'schema_validation': {'enabled': False},
            'tool_orchestrator': {'enabled': False},
            'intelligent_routing': {'enabled': False},
            'resource_management': {'profile': 'balanced'},
            'time_slicing': {'enabled': False},
            'context_scoring': {'enabled': False},
            'pre_rag_optimizer': {'enabled': False},
            'verification': {'enabled': False},
            'quality_assurance': {'enabled': False}
        }

    def initialize_advanced_components(self):
        """Initialize advanced OpenCode components based on settings"""
        if self.is_standard_mode:
            log_message("CHAT_INTERFACE: Standard mode is active, bypassing advanced component initialization.")
            self.format_translator = None
            self.json_fixer_enabled = False
            self.schema_validator = None
            self.tool_orchestrator = None
            self.router = None
            self.time_slicer = None
            self.context_scorer = None
            self.pre_rag_optimizer = None
            self.verification_engine = None
            self.quality_assurance = None
            self.adaptive_workflow = None
            self.agentic_project = None
            self.workflow_optimizer = None
            self.project_store = None
            self.session_manager_adv = None
            self.master_quality = None
            self.quality_recovery = None
            self.performance_benchmark = None
            self.rag_feedback = None
            self.complexity_analyzer = None
            self.hardening_manager = None
            self.atomic_writer = None
            self.confirmation_gates_standalone = None
            self.model_optimizer = None
            self.model_selector = None
            self.quant_manager = None
            self.mvco_engine = None
            self.auto_policy = None
            self.command_policy = None
            self.mcp_integration = None
            self.mcp_server = None
            self.langchain_adapter = None
            self.instant_hooks = None
            self.version_manager = None
            self.ollama_direct = None
            return

        # Add path for OpenCode modules
        sys.path.insert(0, str(Path(__file__).parent.parent / "site-packages"))

        # Format Translator
        if self.advanced_settings.get('format_translation', {}).get('enabled', False):
            try:
                from opencode.format_translator import FormatTranslator
                self.format_translator = FormatTranslator()
                log_message("CHAT_INTERFACE: FormatTranslator initialized")
                if self.backend_settings.get('enable_debug_logging', False):
                    log_message("DEBUG: FormatTranslator enabled with settings: " +
                               json.dumps(self.advanced_settings.get('format_translation', {})))
            except Exception as e:
                log_message(f"CHAT_INTERFACE ERROR: Failed to initialize FormatTranslator: {e}")
                self.format_translator = None
        else:
            self.format_translator = None
            if self.backend_settings.get('enable_debug_logging', False):
                log_message("DEBUG: FormatTranslator disabled")

        # JSON Fixer
        if self.advanced_settings.get('json_repair', {}).get('enabled', False):
            try:
                from opencode.json_fixer import smart_json_parse, parse_partial_json
                self.json_fixer_enabled = True
                self.smart_json_parse = smart_json_parse
                self.parse_partial_json = parse_partial_json
                log_message("CHAT_INTERFACE: JSON Fixer initialized")
                if self.backend_settings.get('enable_debug_logging', False):
                    log_message("DEBUG: JSON Fixer enabled with aggressiveness: " +
                               self.advanced_settings.get('json_repair', {}).get('aggressiveness', 'medium'))
            except Exception as e:
                log_message(f"CHAT_INTERFACE ERROR: Failed to initialize JSON Fixer: {e}")
                self.json_fixer_enabled = False
        else:
            self.json_fixer_enabled = False
            if self.backend_settings.get('enable_debug_logging', False):
                log_message("DEBUG: JSON Fixer disabled")

        # Schema Validator
        if self.advanced_settings.get('schema_validation', {}).get('enabled', False):
            try:
                from opencode.tool_schema_validator import ToolSchemaValidator
                self.schema_validator = ToolSchemaValidator()
                log_message("CHAT_INTERFACE: Schema Validator initialized")
                if self.backend_settings.get('enable_debug_logging', False):
                    log_message("DEBUG: Schema Validator enabled with mode: " +
                               self.advanced_settings.get('schema_validation', {}).get('mode', 'permissive'))
            except Exception as e:
                log_message(f"CHAT_INTERFACE ERROR: Failed to initialize Schema Validator: {e}")
                self.schema_validator = None
        else:
            self.schema_validator = None
            if self.backend_settings.get('enable_debug_logging', False):
                log_message("DEBUG: Schema Validator disabled")

        # Tool Orchestrator
        if self.advanced_settings.get('tool_orchestrator', {}).get('enabled', False):
            try:
                from opencode.tool_orchestrator import AdvancedToolOrchestrator
                from opencode.config import Config
                config = Config()
                # Tool manager will be the tool_executor
                self.tool_orchestrator = AdvancedToolOrchestrator(self.tool_executor, config)
                log_message("CHAT_INTERFACE: Tool Orchestrator initialized")
                if self.backend_settings.get('enable_debug_logging', False):
                    log_message("DEBUG: Tool Orchestrator enabled with risk_assessment: " +
                               str(self.advanced_settings.get('tool_orchestrator', {}).get('risk_assessment', True)))
            except Exception as e:
                log_message(f"CHAT_INTERFACE ERROR: Failed to initialize Tool Orchestrator: {e}")
                self.tool_orchestrator = None
        else:
            self.tool_orchestrator = None
            if self.backend_settings.get('enable_debug_logging', False):
                log_message("DEBUG: Tool Orchestrator disabled")

        # Intelligent Router
        if self.advanced_settings.get('intelligent_routing', {}).get('enabled', False):
            try:
                from opencode.router import Router
                self.router = Router()
                log_message("CHAT_INTERFACE: Intelligent Router initialized")
                if self.backend_settings.get('enable_debug_logging', False):
                    log_message("DEBUG: Router enabled with confidence threshold: " +
                               str(self.advanced_settings.get('intelligent_routing', {}).get('confidence_threshold', 0.7)))
            except Exception as e:
                log_message(f"CHAT_INTERFACE ERROR: Failed to initialize Router: {e}")
                self.router = None
        else:
            self.router = None
            if self.backend_settings.get('enable_debug_logging', False):
                log_message("DEBUG: Intelligent Router disabled")

        # Resource Management (applied to tool executor)
        resource_profile = self.advanced_settings.get('resource_management', {}).get('profile', 'balanced')
        try:
            from opencode.runtime_profiles import resource_manager
            profile = resource_manager.get_profile_by_name(resource_profile)

            # Apply profile constraints to tool executor if it exists
            if self.tool_executor and hasattr(self.tool_executor, 'set_resource_limits'):
                limits = {
                    'num_threads': profile.num_threads,
                    'max_tokens': profile.max_tokens,
                    'memory_limit_mb': profile.memory_limit_mb if hasattr(profile, 'memory_limit_mb') else None
                }
                self.tool_executor.set_resource_limits(limits)
                if self.backend_settings.get('enable_debug_logging', False):
                    log_message(f"DEBUG: Applied resource profile '{resource_profile}' to tool executor: {limits}")
            else:
                if self.backend_settings.get('enable_debug_logging', False):
                    log_message(f"DEBUG: Resource profile '{resource_profile}' loaded but not applied (tool executor doesn't support limits)")
        except Exception as e:
            if self.backend_settings.get('enable_debug_logging', False):
                log_message(f"DEBUG: Failed to apply resource profile: {e}")

        # Time Slicer
        if self.advanced_settings.get('time_slicing', {}).get('enabled', False):
            try:
                from opencode.time_slicer import TimeSlicedGenerator, TimeBudget
                from opencode.runtime_profiles import resource_manager
                profile = resource_manager.get_profile_by_name(resource_profile)
                self.time_slicer = TimeSlicedGenerator(profile)
                log_message("CHAT_INTERFACE: Time Slicer initialized")
                if self.backend_settings.get('enable_debug_logging', False):
                    log_message("DEBUG: Time Slicer enabled with tokens_per_slice: " +
                               str(self.advanced_settings.get('time_slicing', {}).get('tokens_per_slice', 32)))
                    log_message("DEBUG: Note - Time Slicer requires streaming mode (stream=True) to function")
            except Exception as e:
                log_message(f"CHAT_INTERFACE ERROR: Failed to initialize Time Slicer: {e}")
                self.time_slicer = None
        else:
            self.time_slicer = None
            if self.backend_settings.get('enable_debug_logging', False):
                log_message("DEBUG: Time Slicer disabled")

        # Context Scorer
        if self.advanced_settings.get('context_scoring', {}).get('enabled', False):
            try:
                from opencode.context_scorer import AdaptiveContextScorer
                from opencode.config import Config
                config = Config()
                self.context_scorer = AdaptiveContextScorer(config)
                log_message("CHAT_INTERFACE: Context Scorer initialized")
                if self.backend_settings.get('enable_debug_logging', False):
                    log_message("DEBUG: Context Scorer enabled with memory_threshold: " +
                               str(self.advanced_settings.get('context_scoring', {}).get('memory_threshold_percent', 85)))
            except Exception as e:
                log_message(f"CHAT_INTERFACE ERROR: Failed to initialize Context Scorer: {e}")
                self.context_scorer = None
        else:
            self.context_scorer = None
            if self.backend_settings.get('enable_debug_logging', False):
                log_message("DEBUG: Context Scorer disabled")

        # Pre-RAG Optimizer
        if self.advanced_settings.get('pre_rag_optimizer', {}).get('enabled', False):
            try:
                from opencode.pre_rag_optimizer import PreRAGOptimizer
                from opencode.config import Config
                config = Config()
                self.pre_rag_optimizer = PreRAGOptimizer(config)
                log_message("CHAT_INTERFACE: Pre-RAG Optimizer initialized")
                if self.backend_settings.get('enable_debug_logging', False):
                    optimizations = self.advanced_settings.get('pre_rag_optimizer', {}).get('optimizations', {})
                    log_message("DEBUG: Pre-RAG Optimizer enabled with optimizations: " + json.dumps(optimizations))
            except Exception as e:
                log_message(f"CHAT_INTERFACE ERROR: Failed to initialize Pre-RAG Optimizer: {e}")
                self.pre_rag_optimizer = None
        else:
            self.pre_rag_optimizer = None
            if self.backend_settings.get('enable_debug_logging', False):
                log_message("DEBUG: Pre-RAG Optimizer disabled")

        # Verification Engine
        if self.advanced_settings.get('verification', {}).get('enabled', False):
            try:
                from opencode.verification_engine import VerificationEngine
                self.verification_engine = VerificationEngine()
                log_message("CHAT_INTERFACE: Verification Engine initialized")
                if self.backend_settings.get('enable_debug_logging', False):
                    log_message("DEBUG: Verification Engine enabled with strictness: " +
                               self.advanced_settings.get('verification', {}).get('strictness', 'medium'))
            except Exception as e:
                log_message(f"CHAT_INTERFACE ERROR: Failed to initialize Verification Engine: {e}")
                self.verification_engine = None
        else:
            self.verification_engine = None
            if self.backend_settings.get('enable_debug_logging', False):
                log_message("DEBUG: Verification Engine disabled")

        # Quality Assurance
        if self.advanced_settings.get('quality_assurance', {}).get('enabled', False):
            try:
                from opencode.quality_integration import QualityIntegration
                self.quality_assurance = QualityIntegration()
                log_message("CHAT_INTERFACE: Quality Assurance initialized")
                if self.backend_settings.get('enable_debug_logging', False):
                    log_message("DEBUG: Quality Assurance enabled with threshold: " +
                               str(self.advanced_settings.get('quality_assurance', {}).get('threshold', 0.8)))
            except Exception as e:
                log_message(f"CHAT_INTERFACE ERROR: Failed to initialize Quality Assurance: {e}")
                self.quality_assurance = None
        else:
            self.quality_assurance = None
            if self.backend_settings.get('enable_debug_logging', False):
                log_message("DEBUG: Quality Assurance disabled")

        # ========== Additional 26 Systems ==========

        # Adaptive Workflow Engine
        if self.advanced_settings.get('adaptive_workflow', {}).get('enabled', False):
            try:
                from opencode.adaptive_workflow_engine import AdaptiveWorkflowEngine
                self.adaptive_workflow = AdaptiveWorkflowEngine()
                log_message("CHAT_INTERFACE: Adaptive Workflow Engine initialized")
                if self.backend_settings.get('enable_debug_logging', False):
                    log_message(f"DEBUG: Adaptive Workflow enabled")
            except Exception as e:
                log_message(f"CHAT_INTERFACE ERROR: Failed to initialize Adaptive Workflow: {e}")
                self.adaptive_workflow = None
        else:
            self.adaptive_workflow = None

        # Agentic Project System
        if self.advanced_settings.get('agentic_project', {}).get('enabled', False):
            try:
                from opencode.agentic_project_system import AgenticProjectSystem
                self.agentic_project = AgenticProjectSystem()
                log_message("CHAT_INTERFACE: Agentic Project System initialized")
                if self.backend_settings.get('enable_debug_logging', False):
                    log_message(f"DEBUG: Agentic Project enabled")
            except Exception as e:
                log_message(f"CHAT_INTERFACE ERROR: Failed to initialize Agentic Project: {e}")
                self.agentic_project = None
        else:
            self.agentic_project = None

        # Workflow Optimizer
        if self.advanced_settings.get('workflow_optimizer', {}).get('enabled', False):
            try:
                from opencode.workflow_optimizer import WorkflowOptimizer
                self.workflow_optimizer = WorkflowOptimizer()
                log_message("CHAT_INTERFACE: Workflow Optimizer initialized")
                if self.backend_settings.get('enable_debug_logging', False):
                    log_message(f"DEBUG: Workflow Optimizer enabled")
            except Exception as e:
                log_message(f"CHAT_INTERFACE ERROR: Failed to initialize Workflow Optimizer: {e}")
                self.workflow_optimizer = None
        else:
            self.workflow_optimizer = None

        # Project Store
        if self.advanced_settings.get('project_store', {}).get('enabled', False):
            try:
                from opencode.project_store import ProjectStore
                self.project_store = ProjectStore()
                log_message("CHAT_INTERFACE: Project Store initialized")
                if self.backend_settings.get('enable_debug_logging', False):
                    log_message(f"DEBUG: Project Store enabled")
            except Exception as e:
                log_message(f"CHAT_INTERFACE ERROR: Failed to initialize Project Store: {e}")
                self.project_store = None
        else:
            self.project_store = None

        # Session Manager
        if self.advanced_settings.get('session_manager', {}).get('enabled', False):
            try:
                from opencode.session_manager import SessionManager
                self.session_manager_adv = SessionManager()
                log_message("CHAT_INTERFACE: Session Manager initialized")
                if self.backend_settings.get('enable_debug_logging', False):
                    log_message(f"DEBUG: Session Manager enabled")
            except Exception as e:
                log_message(f"CHAT_INTERFACE ERROR: Failed to initialize Session Manager: {e}")
                self.session_manager_adv = None
        else:
            self.session_manager_adv = None

        # Master Quality System
        if self.advanced_settings.get('master_quality', {}).get('enabled', False):
            try:
                from opencode.master_quality_system import MasterQualitySystem
                self.master_quality = MasterQualitySystem()
                log_message("CHAT_INTERFACE: Master Quality System initialized")
                if self.backend_settings.get('enable_debug_logging', False):
                    log_message(f"DEBUG: Master Quality System enabled")
            except Exception as e:
                log_message(f"CHAT_INTERFACE ERROR: Failed to initialize Master Quality: {e}")
                self.master_quality = None
        else:
            self.master_quality = None

        # Quality Recovery Engine
        if self.advanced_settings.get('quality_recovery', {}).get('enabled', False):
            try:
                from opencode.quality_recovery_engine import QualityRecoveryEngine
                self.quality_recovery = QualityRecoveryEngine()
                log_message("CHAT_INTERFACE: Quality Recovery Engine initialized")
                if self.backend_settings.get('enable_debug_logging', False):
                    log_message(f"DEBUG: Quality Recovery enabled")
            except Exception as e:
                log_message(f"CHAT_INTERFACE ERROR: Failed to initialize Quality Recovery: {e}")
                self.quality_recovery = None
        else:
            self.quality_recovery = None

        # Performance Benchmark
        if self.advanced_settings.get('performance_benchmark', {}).get('enabled', False):
            try:
                from opencode.performance_benchmark_system import PerformanceBenchmarkSystem
                self.performance_benchmark = PerformanceBenchmarkSystem()
                log_message("CHAT_INTERFACE: Performance Benchmark initialized")
                if self.backend_settings.get('enable_debug_logging', False):
                    log_message(f"DEBUG: Performance Benchmark enabled")
            except Exception as e:
                log_message(f"CHAT_INTERFACE ERROR: Failed to initialize Performance Benchmark: {e}")
                self.performance_benchmark = None
        else:
            self.performance_benchmark = None

        # RAG Feedback Engine
        if self.advanced_settings.get('rag_feedback', {}).get('enabled', False):
            try:
                from opencode.rag_feedback_engine import RAGFeedbackEngine
                self.rag_feedback = RAGFeedbackEngine()
                log_message("CHAT_INTERFACE: RAG Feedback Engine initialized")
                if self.backend_settings.get('enable_debug_logging', False):
                    log_message(f"DEBUG: RAG Feedback enabled")
            except Exception as e:
                log_message(f"CHAT_INTERFACE ERROR: Failed to initialize RAG Feedback: {e}")
                self.rag_feedback = None
        else:
            self.rag_feedback = None

        # Complexity Analyzer
        if self.advanced_settings.get('complexity_analyzer', {}).get('enabled', False):
            try:
                from opencode.complexity_analyzer import ComplexityAnalyzer
                self.complexity_analyzer = ComplexityAnalyzer()
                log_message("CHAT_INTERFACE: Complexity Analyzer initialized")
                if self.backend_settings.get('enable_debug_logging', False):
                    log_message(f"DEBUG: Complexity Analyzer enabled")
            except Exception as e:
                log_message(f"CHAT_INTERFACE ERROR: Failed to initialize Complexity Analyzer: {e}")
                self.complexity_analyzer = None
        else:
            self.complexity_analyzer = None

        # Hardening Manager
        if self.advanced_settings.get('hardening_manager', {}).get('enabled', False):
            try:
                from opencode.hardening_manager import HardeningManager
                self.hardening_manager = HardeningManager()
                log_message("CHAT_INTERFACE: Hardening Manager initialized")
                if self.backend_settings.get('enable_debug_logging', False):
                    log_message(f"DEBUG: Hardening Manager enabled")
            except Exception as e:
                log_message(f"CHAT_INTERFACE ERROR: Failed to initialize Hardening Manager: {e}")
                self.hardening_manager = None
        else:
            self.hardening_manager = None

        # Atomic Writer
        if self.advanced_settings.get('atomic_writer', {}).get('enabled', False):
            try:
                from opencode.atomic_writer import AtomicWriter
                self.atomic_writer = AtomicWriter()
                log_message("CHAT_INTERFACE: Atomic Writer initialized")
                if self.backend_settings.get('enable_debug_logging', False):
                    log_message(f"DEBUG: Atomic Writer enabled")
            except Exception as e:
                log_message(f"CHAT_INTERFACE ERROR: Failed to initialize Atomic Writer: {e}")
                self.atomic_writer = None
        else:
            self.atomic_writer = None

        # Confirmation Gates (standalone)
        if self.advanced_settings.get('confirmation_gates', {}).get('enabled', False):
            try:
                from opencode.confirmation_gates import ConfirmationGates
                self.confirmation_gates_standalone = ConfirmationGates()
                log_message("CHAT_INTERFACE: Confirmation Gates initialized")
                if self.backend_settings.get('enable_debug_logging', False):
                    log_message(f"DEBUG: Confirmation Gates enabled")
            except Exception as e:
                log_message(f"CHAT_INTERFACE ERROR: Failed to initialize Confirmation Gates: {e}")
                self.confirmation_gates_standalone = None
        else:
            self.confirmation_gates_standalone = None

        # Model Optimizer
        if self.advanced_settings.get('model_optimizer', {}).get('enabled', False):
            try:
                from opencode.model_optimizer import ModelOptimizer
                self.model_optimizer = ModelOptimizer()
                log_message("CHAT_INTERFACE: Model Optimizer initialized")
                if self.backend_settings.get('enable_debug_logging', False):
                    log_message(f"DEBUG: Model Optimizer enabled")
            except Exception as e:
                log_message(f"CHAT_INTERFACE ERROR: Failed to initialize Model Optimizer: {e}")
                self.model_optimizer = None
        else:
            self.model_optimizer = None

        # Model Selector
        if self.advanced_settings.get('model_selector', {}).get('enabled', False):
            try:
                from opencode.model_selector import ModelSelector
                self.model_selector = ModelSelector()
                log_message("CHAT_INTERFACE: Model Selector initialized")
                if self.backend_settings.get('enable_debug_logging', False):
                    log_message(f"DEBUG: Model Selector enabled")
            except Exception as e:
                log_message(f"CHAT_INTERFACE ERROR: Failed to initialize Model Selector: {e}")
                self.model_selector = None
        else:
            self.model_selector = None

        # Quant Manager
        if self.advanced_settings.get('quant_manager', {}).get('enabled', False):
            try:
                from opencode.quant_manager import QuantManager
                self.quant_manager = QuantManager()
                log_message("CHAT_INTERFACE: Quant Manager initialized")
                if self.backend_settings.get('enable_debug_logging', False):
                    log_message(f"DEBUG: Quant Manager enabled")
            except Exception as e:
                log_message(f"CHAT_INTERFACE ERROR: Failed to initialize Quant Manager: {e}")
                self.quant_manager = None
        else:
            self.quant_manager = None

        # MVCO Engine
        if self.advanced_settings.get('mvco_engine', {}).get('enabled', False):
            try:
                from opencode.mvco_engine import MVCOEngine
                self.mvco_engine = MVCOEngine()
                log_message("CHAT_INTERFACE: MVCO Engine initialized")
                if self.backend_settings.get('enable_debug_logging', False):
                    log_message(f"DEBUG: MVCO Engine enabled")
            except Exception as e:
                log_message(f"CHAT_INTERFACE ERROR: Failed to initialize MVCO Engine: {e}")
                self.mvco_engine = None
        else:
            self.mvco_engine = None

        # Auto Policy
        if self.advanced_settings.get('auto_policy', {}).get('enabled', False):
            try:
                from opencode.auto_policy import AutoPolicy
                self.auto_policy = AutoPolicy()
                log_message("CHAT_INTERFACE: Auto Policy initialized")
                if self.backend_settings.get('enable_debug_logging', False):
                    log_message(f"DEBUG: Auto Policy enabled")
            except Exception as e:
                log_message(f"CHAT_INTERFACE ERROR: Failed to initialize Auto Policy: {e}")
                self.auto_policy = None
        else:
            self.auto_policy = None

        # Command Policy
        if self.advanced_settings.get('command_policy', {}).get('enabled', False):
            try:
                from opencode.command_policy import CommandPolicy
                self.command_policy = CommandPolicy()
                log_message("CHAT_INTERFACE: Command Policy initialized")
                if self.backend_settings.get('enable_debug_logging', False):
                    log_message(f"DEBUG: Command Policy enabled")
            except Exception as e:
                log_message(f"CHAT_INTERFACE ERROR: Failed to initialize Command Policy: {e}")
                self.command_policy = None
        else:
            self.command_policy = None

        # MCP Integration
        if self.advanced_settings.get('mcp_integration', {}).get('enabled', False):
            try:
                from opencode.mcp_integration import MCPIntegration
                self.mcp_integration = MCPIntegration()
                log_message("CHAT_INTERFACE: MCP Integration initialized")
                if self.backend_settings.get('enable_debug_logging', False):
                    log_message(f"DEBUG: MCP Integration enabled")
            except Exception as e:
                log_message(f"CHAT_INTERFACE ERROR: Failed to initialize MCP Integration: {e}")
                self.mcp_integration = None
        else:
            self.mcp_integration = None

        # MCP Server
        if self.advanced_settings.get('mcp_server', {}).get('enabled', False):
            try:
                from opencode.mcp_server_wrapper import MCPServerWrapper
                self.mcp_server = MCPServerWrapper()
                log_message("CHAT_INTERFACE: MCP Server initialized")
                if self.backend_settings.get('enable_debug_logging', False):
                    log_message(f"DEBUG: MCP Server enabled")
            except Exception as e:
                log_message(f"CHAT_INTERFACE ERROR: Failed to initialize MCP Server: {e}")
                self.mcp_server = None
        else:
            self.mcp_server = None

        # LangChain Adapter
        if self.advanced_settings.get('langchain_adapter', {}).get('enabled', False):
            try:
                adapter_type = self.advanced_settings.get('langchain_adapter', {}).get('adapter_type', 'simple')
                if adapter_type == 'simple':
                    from opencode.langchain_adapter_simple import LangChainAdapterSimple
                    self.langchain_adapter = LangChainAdapterSimple()
                else:
                    from opencode.langchain_adapter import LangChainAdapter
                    self.langchain_adapter = LangChainAdapter()
                log_message(f"CHAT_INTERFACE: LangChain Adapter ({adapter_type}) initialized")
                if self.backend_settings.get('enable_debug_logging', False):
                    log_message(f"DEBUG: LangChain Adapter enabled")
            except Exception as e:
                log_message(f"CHAT_INTERFACE ERROR: Failed to initialize LangChain Adapter: {e}")
                self.langchain_adapter = None
        else:
            self.langchain_adapter = None

        # Instant Hooks Engine
        if self.advanced_settings.get('instant_hooks', {}).get('enabled', False):
            try:
                from opencode.instant_hook_engine import InstantHookEngine
                self.instant_hooks = InstantHookEngine()
                log_message("CHAT_INTERFACE: Instant Hook Engine initialized")
                if self.backend_settings.get('enable_debug_logging', False):
                    log_message(f"DEBUG: Instant Hooks enabled")
            except Exception as e:
                log_message(f"CHAT_INTERFACE ERROR: Failed to initialize Instant Hooks: {e}")
                self.instant_hooks = None
        else:
            self.instant_hooks = None

        # Version Manager
        if self.advanced_settings.get('version_manager', {}).get('enabled', False):
            try:
                from opencode.version_manager import VersionManager
                self.version_manager = VersionManager()
                log_message("CHAT_INTERFACE: Version Manager initialized")
                if self.backend_settings.get('enable_debug_logging', False):
                    log_message(f"DEBUG: Version Manager enabled")
            except Exception as e:
                log_message(f"CHAT_INTERFACE ERROR: Failed to initialize Version Manager: {e}")
                self.version_manager = None
        else:
            self.version_manager = None

        # Ollama Direct Client
        if self.advanced_settings.get('ollama_direct', {}).get('enabled', False):
            try:
                from opencode.ollama_client import OllamaClient
                self.ollama_direct = OllamaClient()
                log_message("CHAT_INTERFACE: Ollama Direct Client initialized")
                if self.backend_settings.get('enable_debug_logging', False):
                    log_message(f"DEBUG: Ollama Direct Client enabled")
            except Exception as e:
                log_message(f"CHAT_INTERFACE ERROR: Failed to initialize Ollama Direct: {e}")
                self.ollama_direct = None
        else:
            self.ollama_direct = None

    def _ensure_prompt_schema_dirs(self):
        """Ensure system_prompts and tool_schemas_configs directories exist"""
        self.system_prompts_dir.mkdir(exist_ok=True)
        self.tool_schemas_dir.mkdir(exist_ok=True)

        # Create default system prompt if doesn't exist
        default_prompt_file = self.system_prompts_dir / "default.txt"
        if not default_prompt_file.exists():
            with open(default_prompt_file, 'w') as f:
                f.write("You are a helpful AI assistant with access to various tools. Use them when appropriate to help the user.")

        # Create default tool schema config if doesn't exist
        default_schema_file = self.tool_schemas_dir / "default.json"
        if not default_schema_file.exists():
            with open(default_schema_file, 'w') as f:
                json.dump({"enabled_tools": "all", "description": "Default - All tools enabled"}, f, indent=2)

    def select_system_prompt(self):
        """Open dialog to select and edit system prompt"""
        from tkinter import messagebox

        # Create dialog window
        dialog = tk.Toplevel(self.root)
        dialog.title("System Prompt Manager")
        dialog.geometry("900x700")
        dialog.configure(bg='#2b2b2b')

        # Make modal
        dialog.transient(self.root)
        dialog.grab_set()

        # Main layout
        dialog.columnconfigure(0, weight=0)  # List on left
        dialog.columnconfigure(1, weight=1)  # Editor on right
        dialog.rowconfigure(0, weight=1)
        dialog.rowconfigure(1, weight=0)

        # Left panel - Prompt list
        left_frame = ttk.Frame(dialog, style='Category.TFrame')
        left_frame.grid(row=0, column=0, sticky=tk.NSEW, padx=(10, 5), pady=10)

        ttk.Label(
            left_frame,
            text="Available Prompts",
            font=("Arial", 12, "bold"),
            style='CategoryPanel.TLabel'
        ).pack(pady=(0, 5))

        # Listbox for prompts
        list_frame = ttk.Frame(left_frame, style='Category.TFrame')
        list_frame.pack(fill=tk.BOTH, expand=True)

        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        prompt_listbox = tk.Listbox(
            list_frame,
            yscrollcommand=scrollbar.set,
            bg='#1e1e1e',
            fg='#ffffff',
            selectbackground='#61dafb',
            font=("Arial", 10),
            width=25
        )
        prompt_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=prompt_listbox.yview)

        # Load prompts
        prompts = sorted([f.stem for f in self.system_prompts_dir.glob("*.txt")])
        for prompt in prompts:
            prompt_listbox.insert(tk.END, prompt)
            if prompt == self.current_system_prompt:
                prompt_listbox.selection_set(prompts.index(prompt))

        # Right panel - Editor
        right_frame = ttk.Frame(dialog, style='Category.TFrame')
        right_frame.grid(row=0, column=1, sticky=tk.NSEW, padx=(5, 10), pady=10)
        right_frame.columnconfigure(0, weight=1)
        right_frame.rowconfigure(1, weight=1)

        # Editor header
        header_frame = ttk.Frame(right_frame, style='Category.TFrame')
        header_frame.grid(row=0, column=0, sticky=tk.EW, pady=(0, 5))
        header_frame.columnconfigure(0, weight=1)

        prompt_name_label = ttk.Label(
            header_frame,
            text="Select a prompt to view/edit",
            font=("Arial", 12, "bold"),
            style='CategoryPanel.TLabel'
        )
        prompt_name_label.grid(row=0, column=0, sticky=tk.W)

        # Text editor
        editor = scrolledtext.ScrolledText(
            right_frame,
            wrap=tk.WORD,
            font=("Courier", 10),
            bg='#1e1e1e',
            fg='#ffffff',
            insertbackground='#61dafb'
        )
        editor.grid(row=1, column=0, sticky=tk.NSEW)

        # Track current selection
        current_prompt_name = [None]
        modified = [False]

        def load_prompt(event=None):
            """Load selected prompt into editor"""
            selection = prompt_listbox.curselection()
            if not selection:
                return

            # Check if current prompt was modified
            if modified[0] and current_prompt_name[0]:
                if messagebox.askyesno(
                    "Unsaved Changes",
                    f"You have unsaved changes to '{current_prompt_name[0]}'.\n\nSave before switching?"
                ):
                    save_prompt()

            prompt_name = prompt_listbox.get(selection[0])
            current_prompt_name[0] = prompt_name
            modified[0] = False

            prompt_file = self.system_prompts_dir / f"{prompt_name}.txt"
            if prompt_file.exists():
                with open(prompt_file, 'r') as f:
                    content = f.read()
                editor.delete(1.0, tk.END)
                editor.insert(1.0, content)
                prompt_name_label.config(text=f"📝 {prompt_name}")

        def on_text_change(event=None):
            """Mark as modified when text changes"""
            modified[0] = True
            if current_prompt_name[0]:
                prompt_name_label.config(text=f"📝 {current_prompt_name[0]} *")

        editor.bind('<KeyRelease>', on_text_change)
        prompt_listbox.bind('<<ListboxSelect>>', load_prompt)

        # Load initially selected prompt
        if prompt_listbox.curselection():
            load_prompt()

        # Bottom buttons
        button_frame = ttk.Frame(dialog, style='Category.TFrame')
        button_frame.grid(row=1, column=0, columnspan=2, sticky=tk.EW, padx=10, pady=(0, 10))

        def save_prompt():
            """Save current prompt"""
            if not current_prompt_name[0]:
                messagebox.showwarning("No Selection", "Please select a prompt first")
                return

            content = editor.get(1.0, tk.END).strip()
            if not content:
                messagebox.showwarning("Empty Content", "Prompt content cannot be empty")
                return

            prompt_file = self.system_prompts_dir / f"{current_prompt_name[0]}.txt"
            with open(prompt_file, 'w') as f:
                f.write(content)

            modified[0] = False
            prompt_name_label.config(text=f"📝 {current_prompt_name[0]}")
            messagebox.showinfo("Saved", f"Prompt '{current_prompt_name[0]}' saved successfully")

        def new_prompt():
            """Create new prompt"""
            from tkinter import simpledialog
            name = simpledialog.askstring("New Prompt", "Enter prompt name:")
            if name:
                # Clean name
                name = "".join(c for c in name if c.isalnum() or c in ('_', '-'))
                if not name:
                    messagebox.showerror("Invalid Name", "Prompt name must contain alphanumeric characters")
                    return

                prompt_file = self.system_prompts_dir / f"{name}.txt"
                if prompt_file.exists():
                    messagebox.showerror("Exists", f"Prompt '{name}' already exists")
                    return

                # Create empty prompt
                with open(prompt_file, 'w') as f:
                    f.write("You are a helpful AI assistant.")

                # Reload list
                prompt_listbox.insert(tk.END, name)
                prompt_listbox.selection_clear(0, tk.END)
                prompt_listbox.selection_set(tk.END)
                load_prompt()

        def delete_prompt():
            """Delete selected prompt"""
            if not current_prompt_name[0]:
                messagebox.showwarning("No Selection", "Please select a prompt first")
                return

            if current_prompt_name[0] == "default":
                messagebox.showerror("Cannot Delete", "Cannot delete the default prompt")
                return

            if messagebox.askyesno(
                "Confirm Delete",
                f"Are you sure you want to delete '{current_prompt_name[0]}'?"
            ):
                prompt_file = self.system_prompts_dir / f"{current_prompt_name[0]}.txt"
                prompt_file.unlink(missing_ok=True)

                # Reload list
                selection = prompt_listbox.curselection()
                prompt_listbox.delete(selection[0])
                current_prompt_name[0] = None
                modified[0] = False
                editor.delete(1.0, tk.END)
                prompt_name_label.config(text="Select a prompt to view/edit")

        def select_and_apply():
            """Select prompt and apply it"""
            if not current_prompt_name[0]:
                messagebox.showwarning("No Selection", "Please select a prompt first")
                return

            # Save if modified
            if modified[0]:
                save_prompt()

            self.current_system_prompt = current_prompt_name[0]
            self.add_message("system", f"✓ Loaded system prompt: {current_prompt_name[0]}")
            log_message(f"CHAT_INTERFACE: Loaded system prompt: {current_prompt_name[0]}")

            # Remount model to apply new prompt
            if self.is_mounted:
                self.dismount_model()
                self.root.after(500, self.mount_model)

            dialog.destroy()

        # Buttons
        ttk.Button(
            button_frame,
            text="💾 Save",
            command=save_prompt,
            style='Action.TButton'
        ).pack(side=tk.LEFT, padx=5)

        ttk.Button(
            button_frame,
            text="➕ New",
            command=new_prompt,
            style='Action.TButton'
        ).pack(side=tk.LEFT, padx=5)

        ttk.Button(
            button_frame,
            text="🗑️ Delete",
            command=delete_prompt,
            style='Select.TButton'
        ).pack(side=tk.LEFT, padx=5)

        ttk.Button(
            button_frame,
            text="✓ Select & Apply",
            command=select_and_apply,
            style='Action.TButton'
        ).pack(side=tk.RIGHT, padx=5)

        ttk.Button(
            button_frame,
            text="Cancel",
            command=dialog.destroy,
            style='Select.TButton'
        ).pack(side=tk.RIGHT, padx=5)

    def select_tool_schema(self):
        """Open dialog to select and edit tool schema configuration"""
        from tkinter import messagebox

        # Create dialog window
        dialog = tk.Toplevel(self.root)
        dialog.title("Tool Schema Manager")
        dialog.geometry("900x700")
        dialog.configure(bg='#2b2b2b')

        # Make modal
        dialog.transient(self.root)
        dialog.grab_set()

        # Main layout
        dialog.columnconfigure(0, weight=0)  # List on left
        dialog.columnconfigure(1, weight=1)  # Editor on right
        dialog.rowconfigure(0, weight=1)
        dialog.rowconfigure(1, weight=0)

        # Left panel - Schema list
        left_frame = ttk.Frame(dialog, style='Category.TFrame')
        left_frame.grid(row=0, column=0, sticky=tk.NSEW, padx=(10, 5), pady=10)

        ttk.Label(
            left_frame,
            text="Available Schemas",
            font=("Arial", 12, "bold"),
            style='CategoryPanel.TLabel'
        ).pack(pady=(0, 5))

        # Listbox for schemas
        list_frame = ttk.Frame(left_frame, style='Category.TFrame')
        list_frame.pack(fill=tk.BOTH, expand=True)

        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        schema_listbox = tk.Listbox(
            list_frame,
            yscrollcommand=scrollbar.set,
            bg='#1e1e1e',
            fg='#ffffff',
            selectbackground='#61dafb',
            font=("Arial", 10),
            width=25
        )
        schema_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=schema_listbox.yview)

        # Load schemas
        schemas = sorted([f.stem for f in self.tool_schemas_dir.glob("*.json")])
        for schema in schemas:
            schema_listbox.insert(tk.END, schema)
            if schema == self.current_tool_schema:
                schema_listbox.selection_set(schemas.index(schema))

        # Right panel - Editor
        right_frame = ttk.Frame(dialog, style='Category.TFrame')
        right_frame.grid(row=0, column=1, sticky=tk.NSEW, padx=(5, 10), pady=10)
        right_frame.columnconfigure(0, weight=1)
        right_frame.rowconfigure(1, weight=1)

        # Editor header
        header_frame = ttk.Frame(right_frame, style='Category.TFrame')
        header_frame.grid(row=0, column=0, sticky=tk.EW, pady=(0, 5))
        header_frame.columnconfigure(0, weight=1)

        schema_name_label = ttk.Label(
            header_frame,
            text="Select a schema to view/edit",
            font=("Arial", 12, "bold"),
            style='CategoryPanel.TLabel'
        )
        schema_name_label.grid(row=0, column=0, sticky=tk.W)

        # Text editor
        editor = scrolledtext.ScrolledText(
            right_frame,
            wrap=tk.WORD,
            font=("Courier", 10),
            bg='#1e1e1e',
            fg='#ffffff',
            insertbackground='#61dafb'
        )
        editor.grid(row=1, column=0, sticky=tk.NSEW)

        # Track current selection
        current_schema_name = [None]
        modified = [False]

        def load_schema(event=None):
            """Load selected schema into editor"""
            selection = schema_listbox.curselection()
            if not selection:
                return

            # Check if current schema was modified
            if modified[0] and current_schema_name[0]:
                if messagebox.askyesno(
                    "Unsaved Changes",
                    f"You have unsaved changes to '{current_schema_name[0]}'.\n\nSave before switching?"
                ):
                    save_schema()

            schema_name = schema_listbox.get(selection[0])
            current_schema_name[0] = schema_name
            modified[0] = False

            schema_file = self.tool_schemas_dir / f"{schema_name}.json"
            if schema_file.exists():
                with open(schema_file, 'r') as f:
                    content = f.read()
                editor.delete(1.0, tk.END)
                editor.insert(1.0, content)
                schema_name_label.config(text=f"🔧 {schema_name}")

        def on_text_change(event=None):
            """Mark as modified when text changes"""
            modified[0] = True
            if current_schema_name[0]:
                schema_name_label.config(text=f"🔧 {current_schema_name[0]} *")

        editor.bind('<KeyRelease>', on_text_change)
        schema_listbox.bind('<<ListboxSelect>>', load_schema)

        # Load initially selected schema
        if schema_listbox.curselection():
            load_schema()

        # Bottom buttons
        button_frame = ttk.Frame(dialog, style='Category.TFrame')
        button_frame.grid(row=1, column=0, columnspan=2, sticky=tk.EW, padx=10, pady=(0, 10))

        def save_schema():
            """Save current schema"""
            if not current_schema_name[0]:
                messagebox.showwarning("No Selection", "Please select a schema first")
                return

            content = editor.get(1.0, tk.END).strip()
            if not content:
                messagebox.showwarning("Empty Content", "Schema content cannot be empty")
                return

            # Validate JSON
            try:
                schema_data = json.loads(content)
            except json.JSONDecodeError as e:
                messagebox.showerror("Invalid JSON", f"JSON validation failed:\n{str(e)}")
                return

            # Validate schema structure
            if "enabled_tools" not in schema_data:
                messagebox.showerror("Invalid Schema", "Schema must contain 'enabled_tools' field")
                return

            schema_file = self.tool_schemas_dir / f"{current_schema_name[0]}.json"
            with open(schema_file, 'w') as f:
                json.dump(schema_data, f, indent=2)

            modified[0] = False
            schema_name_label.config(text=f"🔧 {current_schema_name[0]}")
            messagebox.showinfo("Saved", f"Schema '{current_schema_name[0]}' saved successfully")

        def new_schema():
            """Create new schema"""
            from tkinter import simpledialog
            name = simpledialog.askstring("New Schema", "Enter schema name:")
            if name:
                # Clean name
                name = "".join(c for c in name if c.isalnum() or c in ('_', '-'))
                if not name:
                    messagebox.showerror("Invalid Name", "Schema name must contain alphanumeric characters")
                    return

                schema_file = self.tool_schemas_dir / f"{name}.json"
                if schema_file.exists():
                    messagebox.showerror("Exists", f"Schema '{name}' already exists")
                    return

                # Create default schema
                default_schema = {
                    "enabled_tools": "all",
                    "description": f"Custom schema: {name}"
                }
                with open(schema_file, 'w') as f:
                    json.dump(default_schema, f, indent=2)

                # Reload list
                schema_listbox.insert(tk.END, name)
                schema_listbox.selection_clear(0, tk.END)
                schema_listbox.selection_set(tk.END)
                load_schema()

        def delete_schema():
            """Delete selected schema"""
            if not current_schema_name[0]:
                messagebox.showwarning("No Selection", "Please select a schema first")
                return

            if current_schema_name[0] == "default":
                messagebox.showerror("Cannot Delete", "Cannot delete the default schema")
                return

            if messagebox.askyesno(
                "Confirm Delete",
                f"Are you sure you want to delete '{current_schema_name[0]}'?"
            ):
                schema_file = self.tool_schemas_dir / f"{current_schema_name[0]}.json"
                schema_file.unlink(missing_ok=True)

                # Reload list
                selection = schema_listbox.curselection()
                schema_listbox.delete(selection[0])
                current_schema_name[0] = None
                modified[0] = False
                editor.delete(1.0, tk.END)
                schema_name_label.config(text="Select a schema to view/edit")

        def select_and_apply():
            """Select schema and apply it"""
            if not current_schema_name[0]:
                messagebox.showwarning("No Selection", "Please select a schema first")
                return

            # Save if modified
            if modified[0]:
                save_schema()

            self.current_tool_schema = current_schema_name[0]
            self.add_message("system", f"✓ Loaded tool schema: {current_schema_name[0]}")
            log_message(f"CHAT_INTERFACE: Loaded tool schema: {current_schema_name[0]}")

            # Reload tool schemas
            self.tool_executor.initialize_tools()

            # Remount model to apply new schema
            if self.is_mounted:
                self.dismount_model()
                self.root.after(500, self.mount_model)

            dialog.destroy()

        # Buttons
        ttk.Button(
            button_frame,
            text="💾 Save",
            command=save_schema,
            style='Action.TButton'
        ).pack(side=tk.LEFT, padx=5)

        ttk.Button(
            button_frame,
            text="➕ New",
            command=new_schema,
            style='Action.TButton'
        ).pack(side=tk.LEFT, padx=5)

        ttk.Button(
            button_frame,
            text="🗑️ Delete",
            command=delete_schema,
            style='Select.TButton'
        ).pack(side=tk.LEFT, padx=5)

        ttk.Button(
            button_frame,
            text="✓ Select & Apply",
            command=select_and_apply,
            style='Action.TButton'
        ).pack(side=tk.RIGHT, padx=5)

        ttk.Button(
            button_frame,
            text="Cancel",
            command=dialog.destroy,
            style='Select.TButton'
        ).pack(side=tk.RIGHT, padx=5)

    def get_current_system_prompt(self):
        """Get the current system prompt content"""
        prompt_file = self.system_prompts_dir / f"{self.current_system_prompt}.txt"
        if prompt_file.exists():
            with open(prompt_file, 'r') as f:
                return f.read()
        return "You are a helpful AI assistant."

    def get_current_tool_schema_config(self):
        """Get the current tool schema configuration"""
        schema_file = self.tool_schemas_dir / f"{self.current_tool_schema}.json"
        if schema_file.exists():
            with open(schema_file, 'r') as f:
                return json.load(f)
        return {"enabled_tools": "all"}

    def get_realtime_eval_scores(self):
        """Return the real-time evaluation scores"""
        return self.realtime_eval_scores

    def _validate_tool_call_success(self, tool_call, result, user_message):
        """
        Enhanced tool call validation beyond simple error string matching.

        Returns:
            Tuple[bool, str]: (is_success, failure_reason)
        """
        result_content = result.get('content', '')
        tool_name = tool_call.get('function', {}).get('name', 'unknown')

        # 1. Check for explicit error indicators
        error_indicators = ['Error:', 'error:', 'ERROR:', 'Exception:', 'Failed:', 'failed:']
        for indicator in error_indicators:
            if indicator in result_content:
                return False, "error_in_result"

        # 2. Check for empty or suspiciously short results for tools that should return data
        data_returning_tools = ['file_read', 'grep_search', 'list_directory', 'web_fetch', 'bash']
        if tool_name in data_returning_tools:
            if len(result_content.strip()) < 10:
                return False, "empty_result"

        # 3. Tool-specific validations
        if tool_name == 'file_read':
            # File read should not return "file not found" or similar
            if any(phrase in result_content.lower() for phrase in ['not found', 'does not exist', 'no such file']):
                return False, "file_not_found"

        elif tool_name == 'file_write':
            # File write should confirm success
            if not any(phrase in result_content.lower() for phrase in ['written', 'success', 'saved', 'created']):
                return False, "write_not_confirmed"

        elif tool_name == 'bash':
            # Bash commands with non-zero exit codes often indicate failure
            if 'exit code' in result_content.lower() and 'exit code 0' not in result_content.lower():
                return False, "non_zero_exit_code"

        elif tool_name == 'grep_search':
            # Grep with no matches might be valid, but if user asked for something specific, it's likely a failure
            if 'no matches found' in result_content.lower() or result_content.strip() == '':
                # Check if user was expecting specific content
                if user_message and any(word in user_message.lower() for word in ['find', 'search', 'where', 'show me']):
                    return False, "no_matches_found"

        # 4. Check result format makes sense (basic sanity check)
        # If result is just a stack trace or exception, it's likely a failure
        if result_content.count('\n') > 20 and 'Traceback' in result_content:
            return False, "exception_traceback"

        # If we got here, consider it a success
        return True, "success"

    def persist_realtime_scores(self, model_name=None):
        """Persist real-time scores to ToolCallLogger for permanent storage"""
        if not self.tool_call_logger:
            log_message("CHAT_INTERFACE: ToolCallLogger not available for persisting scores")
            return

        # If model_name not specified, persist all models' scores
        models_to_persist = [model_name] if model_name else list(self.realtime_eval_scores.keys())

        for model in models_to_persist:
            if model not in self.realtime_eval_scores:
                continue

            log_message(f"CHAT_INTERFACE: Persisting real-time scores for {model}")

            for tool_name, stats in self.realtime_eval_scores[model].items():
                success_count = stats.get('success', 0)
                failure_count = stats.get('failure', 0)

                # Log each success and failure to ToolCallLogger
                # This updates the persistent tool_realtime_data.jsonl file
                for _ in range(success_count):
                    self.tool_call_logger.log_tool_call(
                        tool_name=tool_name,
                        tool_args={},  # Args not tracked in realtime scores
                        result="Success (from realtime persistence)",
                        success=True,
                        model_name=model
                    )

                for error in stats.get('errors', [])[:failure_count]:
                    self.tool_call_logger.log_tool_call(
                        tool_name=tool_name,
                        tool_args={},
                        result=error,
                        success=False,
                        model_name=model
                    )

            log_message(f"CHAT_INTERFACE: ✓ Persisted real-time scores for {model}")

    def _auto_save_conversation(self):
        """Auto-save current conversation to persistent storage"""
        if not self.chat_history_manager or not self.current_model or not self.chat_history:
            return

        try:
            # Collect metadata
            current_mode = 'unknown'
            try:
                mode_settings_file = Path(__file__).parent.parent / "mode_settings.json"
                if mode_settings_file.exists():
                    with open(mode_settings_file, 'r') as f:
                        settings = json.load(f)
                    current_mode = settings.get('current_mode', 'unknown')
            except Exception:
                pass

            tool_settings = {}
            try:
                tool_settings_file = Path(__file__).parent.parent / "tool_settings.json"
                if tool_settings_file.exists():
                    with open(tool_settings_file, 'r') as f:
                        tool_settings = json.load(f)
            except Exception:
                pass

            metadata = {
                "mode": current_mode,
                "temperature": self.session_temperature,
                "temp_mode": getattr(self, 'temp_mode', 'manual'),
                "system_prompt": self.current_system_prompt,
                "tool_schema": self.current_tool_schema,
                "working_directory": self.tool_executor.get_working_directory() if self.tool_executor else 'unknown',
                "training_data_collection": self.training_mode_enabled,
                "model": self.current_model,
                "tool_settings": tool_settings,
                # Persist per-session tool overrides (if any)
                "session_tools": getattr(self, 'session_enabled_tools', None),
                # RAG per chat (if toggled)
                "rag_enabled": bool(getattr(self, 'rag_enabled', False)),
            }

            # Save conversation
            session_id = self.chat_history_manager.save_conversation(
                model_name=self.current_model,
                chat_history=self.chat_history,
                session_name=self.current_session_id,
                metadata=metadata
            )

            # Update current session ID
            if session_id:
                self.current_session_id = session_id
                log_message(f"CHAT_INTERFACE: Auto-saved conversation as {session_id}")
                self._chat_dirty = False

                # Refresh the history tab in the parent
                if hasattr(self.parent_tab, 'refresh_history'):
                    self.root.after(0, self.parent_tab.refresh_history)
                # Refresh conversation sidebar and highlight current session
                try:
                    self.root.after(0, self._refresh_conversations_list)
                except Exception:
                    pass
                # Update RAG index after save
                try:
                    self.rag_service.refresh_index_global()
                except Exception:
                    pass
        except Exception as e:
            log_message(f"CHAT_INTERFACE ERROR: Failed to auto-save conversation: {e}")

    def load_chat_history(self):
        """Open dialog to select and load a previous conversation"""
        from tkinter import messagebox

        if not self.chat_history_manager:
            messagebox.showerror("Error", "Chat history manager not initialized")
            return

        # Create dialog window
        dialog = tk.Toplevel(self.root)
        dialog.title("Load Chat History")
        dialog.geometry("800x600")
        dialog.configure(bg='#2b2b2b')

        # Make modal
        dialog.transient(self.root)
        dialog.grab_set()

        # Main layout
        dialog.columnconfigure(0, weight=1)
        dialog.rowconfigure(0, weight=0)  # Filter controls
        dialog.rowconfigure(1, weight=1)  # Chat list
        dialog.rowconfigure(2, weight=0)  # Buttons

        # Filter controls
        filter_frame = ttk.Frame(dialog, style='Category.TFrame')
        filter_frame.grid(row=0, column=0, sticky=tk.EW, padx=10, pady=10)
        filter_frame.columnconfigure(1, weight=1)

        ttk.Label(
            filter_frame,
            text="Filter by Model:",
            font=("Arial", 10),
            style='Config.TLabel'
        ).grid(row=0, column=0, sticky=tk.W, padx=(0, 10))

        model_filter_var = tk.StringVar(value="All Models")
        model_filter = ttk.Combobox(
            filter_frame,
            textvariable=model_filter_var,
            state='readonly',
            font=("Arial", 10)
        )
        model_filter.grid(row=0, column=1, sticky=tk.EW, padx=(0, 10))

        # Get all unique model names
        all_conversations = self.chat_history_manager.list_conversations()
        model_names = sorted(list(set(conv["model_name"] for conv in all_conversations)))
        model_filter['values'] = ["All Models"] + model_names

        # Chat list frame
        list_frame = ttk.Frame(dialog, style='Category.TFrame')
        list_frame.grid(row=1, column=0, sticky=tk.NSEW, padx=10, pady=(0, 10))
        list_frame.columnconfigure(0, weight=1)
        list_frame.rowconfigure(0, weight=1)

        # Create Treeview for chat list
        tree_scroll = ttk.Scrollbar(list_frame)
        tree_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        chat_tree = ttk.Treeview(
            list_frame,
            columns=("Model", "Messages", "Date", "Preview"),
            show='headings',
            yscrollcommand=tree_scroll.set,
            style='Treeview'
        )
        chat_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tree_scroll.config(command=chat_tree.yview)

        # Configure columns
        chat_tree.heading("Model", text="Model")
        chat_tree.heading("Messages", text="Messages")
        chat_tree.heading("Date", text="Date")
        chat_tree.heading("Preview", text="Preview")

        chat_tree.column("Model", width=150, anchor=tk.W)
        chat_tree.column("Messages", width=80, anchor=tk.CENTER)
        chat_tree.column("Date", width=150, anchor=tk.W)
        chat_tree.column("Preview", width=300, anchor=tk.W)

        # Configure Treeview style
        style = ttk.Style()
        style.configure('Treeview', background='#1e1e1e', foreground='#ffffff', fieldbackground='#1e1e1e')
        style.map('Treeview', background=[('selected', '#61dafb')])

        def populate_tree(filter_model=None):
            """Populate tree with conversations"""
            chat_tree.delete(*chat_tree.get_children())

            conversations = self.chat_history_manager.list_conversations(
                model_name=filter_model if filter_model != "All Models" else None
            )

            for conv in conversations:
                # Format date
                date_str = conv.get("saved_at", "")
                if date_str:
                    try:
                        date_obj = datetime.fromisoformat(date_str)
                        date_formatted = date_obj.strftime("%Y-%m-%d %H:%M")
                    except:
                        date_formatted = date_str[:16]
                else:
                    date_formatted = "Unknown"

                chat_tree.insert(
                    "",
                    tk.END,
                    values=(
                        conv.get("model_name", "Unknown"),
                        conv.get("message_count", 0),
                        date_formatted,
                        conv.get("preview", "")
                    ),
                    tags=(conv.get("session_id", ""),)
                )

        # Initial population
        populate_tree()

        def on_filter_change(event=None):
            """Handle filter change"""
            populate_tree(model_filter_var.get())

        model_filter.bind('<<ComboboxSelected>>', on_filter_change)

        # Button frame
        button_frame = ttk.Frame(dialog, style='Category.TFrame')
        button_frame.grid(row=2, column=0, sticky=tk.EW, padx=10, pady=(0, 10))

        def load_selected():
            """Load the selected conversation"""
            selection = chat_tree.selection()
            if not selection:
                messagebox.showwarning("No Selection", "Please select a conversation to load")
                return

            item = chat_tree.item(selection[0])
            session_id = item['tags'][0]

            # Load conversation
            conversation = self.chat_history_manager.load_conversation(session_id)
            if not conversation:
                messagebox.showerror("Error", f"Failed to load conversation: {session_id}")
                return

            # Check if we need to save current conversation
            if self.chat_history and self.backend_settings.get('auto_save_history', True):
                if messagebox.askyesno(
                    "Save Current Chat?",
                    "Do you want to save the current conversation before loading a new one?"
                ):
                    self._auto_save_conversation()

            # Load the conversation
            self.chat_history = conversation.get("chat_history", [])
            self.current_model = conversation.get("model_name")
            self.current_session_id = session_id

            # Update UI
            self.model_label.config(text=self.current_model)
            self.redisplay_conversation()
            self.add_message("system", f"✓ Loaded conversation: {session_id}")
            log_message(f"CHAT_INTERFACE: Loaded conversation {session_id}")

            dialog.destroy()

        def delete_selected():
            """Delete the selected conversation"""
            selection = chat_tree.selection()
            if not selection:
                messagebox.showwarning("No Selection", "Please select a conversation to delete")
                return

            item = chat_tree.item(selection[0])
            session_id = item['tags'][0]

            if messagebox.askyesno(
                "Confirm Delete",
                f"Are you sure you want to delete this conversation?\n\n{session_id}"
            ):
                if self.chat_history_manager.delete_conversation(session_id):
                    messagebox.showinfo("Deleted", "Conversation deleted successfully")
                    populate_tree(model_filter_var.get())
                else:
                    messagebox.showerror("Error", "Failed to delete conversation")

        def export_selected():
            """Export the selected conversation"""
            from tkinter import filedialog

            selection = chat_tree.selection()
            if not selection:
                messagebox.showwarning("No Selection", "Please select a conversation to export")
                return

            item = chat_tree.item(selection[0])
            session_id = item['tags'][0]

            # Ask for export format
            export_format = messagebox.askquestion(
                "Export Format",
                "Export as JSON?\n(No = Export as Text)",
                icon='question'
            )
            format_ext = "json" if export_format == "yes" else "txt"

            # Ask for save location
            export_path = filedialog.asksaveasfilename(
                title="Export Conversation",
                defaultextension=f".{format_ext}",
                filetypes=[(f"{format_ext.upper()} files", f"*.{format_ext}"), ("All files", "*.*")],
                initialfile=f"{session_id}.{format_ext}"
            )

            if export_path:
                if self.chat_history_manager.export_conversation(session_id, Path(export_path), format_ext):
                    messagebox.showinfo("Exported", f"Conversation exported to:\n{export_path}")
                else:
                    messagebox.showerror("Error", "Failed to export conversation")

        # Buttons
        ttk.Button(
            button_frame,
            text="✓ Load",
            command=load_selected,
            style='Action.TButton'
        ).pack(side=tk.LEFT, padx=5)

        ttk.Button(
            button_frame,
            text="🗑️ Delete",
            command=delete_selected,
            style='Select.TButton'
        ).pack(side=tk.LEFT, padx=5)

        ttk.Button(
            button_frame,
            text="📤 Export",
            command=export_selected,
            style='Action.TButton'
        ).pack(side=tk.LEFT, padx=5)

        ttk.Button(
            button_frame,
            text="Cancel",
            command=dialog.destroy,
            style='Select.TButton'
        ).pack(side=tk.RIGHT, padx=5)

    def save_on_exit(self):
        """Save conversation when application is closing"""
        if self.chat_history and self.backend_settings.get('auto_save_history', True):
            self._auto_save_conversation()
            log_message("CHAT_INTERFACE: Saved conversation on exit")

    def set_training_mode(self, enabled):
        """Enable or disable training mode"""
        # If disabling training mode, persist any accumulated scores
        if not enabled and self.training_mode_enabled and self.realtime_eval_scores:
            log_message("CHAT_INTERFACE: Training mode being disabled - persisting real-time scores")
            self.persist_realtime_scores()  # Persist all models
            self.add_message("system", "💾 Real-time scores persisted to permanent storage.")

        self.training_mode_enabled = enabled
        log_message(f"CHAT_INTERFACE: Training mode set to {enabled}")
        self.add_message("system", f"📚 Training mode has been {'enabled' if enabled else 'disabled'}.")

    def set_mode_parameters(self, mode, params):
        """Set mode-specific parameters from the mode selector"""
        log_message(f"CHAT_INTERFACE: Setting mode to '{mode}' with params: {params}")

        if mode == 'standard':
            self.is_standard_mode = True
            self.add_message("system", "⚙️ Mode updated to Standard. Advanced systems bypassed.")
            # We don't change advanced_settings.json in standard mode
            self.initialize_advanced_components() # Re-initialize to disable components
            return

        self.is_standard_mode = False
        # Map mode to resource profile
        profile_map = {
            'fast': 'conservative',
            'smart': 'balanced',
            'think': 'aggressive'
        }
        profile = profile_map.get(mode, 'balanced')

        # Update advanced settings
        if 'resource_management' not in self.advanced_settings:
            self.advanced_settings['resource_management'] = {}
        self.advanced_settings['resource_management']['profile'] = profile

        # Potentially map other parameters from params to advanced_settings here
        # For now, we just handle the main profile

        # Save the updated settings to file
        try:
            settings_file = Path(__file__).parent.parent / "advanced_settings.json"
            with open(settings_file, 'w') as f:
                json.dump(self.advanced_settings, f, indent=2)
            log_message(f"CHAT_INTERFACE: Saved updated advanced settings for mode '{mode}'")
        except Exception as e:
            log_message(f"CHAT_INTERFACE ERROR: Failed to save advanced_settings.json: {e}")

        # Re-initialize advanced components to apply new settings
        self.initialize_advanced_components()

        self.add_message("system", f"⚙️ Mode updated to '{mode.capitalize()}' ({profile} profile). Settings applied.")

    def refresh(self):
        """Refresh the chat interface"""
        log_message("CHAT_INTERFACE: Refreshing...")
        # Reload backend settings
        self.backend_settings = self.load_backend_settings()

        # Reload advanced settings
        self.advanced_settings = self.load_advanced_settings()

        # Reinitialize advanced components
        self.initialize_advanced_components()

        # Update tool executor working directory if changed
        if self.tool_executor:
            working_dir = self.backend_settings.get('working_directory', str(Path.cwd()))
            self.tool_executor.set_working_directory(working_dir)
