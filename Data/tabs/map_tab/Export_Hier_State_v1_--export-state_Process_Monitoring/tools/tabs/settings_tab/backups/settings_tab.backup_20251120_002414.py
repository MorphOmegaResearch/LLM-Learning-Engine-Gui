# [SYSTEM: GUI | VERSION: 1.9f | STATUS: ACTIVE]
"""
Settings Sub-Tab - Backend configuration for Custom Code features
Controls working directory, tool execution, chat behavior, and project settings
Uses unified Tool Profile system for persistence.
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
import json
import sys
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
    TOOL_PROFILES_DIR
)


class SettingsTab(BaseTab):
    """Settings configuration interface for Custom Code tab"""


    _settings_tab.backup_20251120_002414_debug_logger = get_debug_logger("settings_tab.backup_20251120_002414")

    def __init__(self, parent, root, style, parent_tab):
        super().__init__(parent, root, style)
        self.parent_tab = parent_tab

        # Unified Tool Profile integration
        self.current_profile_name = tk.StringVar(value="Default")
        self.profile = self.load_profile()
        self.settings = self.extract_settings_from_profile()
        # Shared Training Mode var across views
        try:
            cur_tm = False
            if hasattr(parent_tab, 'chat_interface') and parent_tab.chat_interface:
                cur_tm = bool(parent_tab.chat_interface.training_mode_enabled)
            else:
                cur_tm = bool(self.settings.get('training_mode_enabled', False))
        except Exception:
            cur_tm = bool(self.settings.get('training_mode_enabled', False))
        self.training_mode_var = tk.BooleanVar(value=cur_tm)
        self._tm_event_bound = False
        self._ts_event_bound = False

    def create_ui(self):
        """Create the settings interface UI with nested tabs"""
        log_message("CC_SETTINGS: Creating UI...")

        self.parent.columnconfigure(0, weight=1)
        self.parent.rowconfigure(0, weight=1)

        # Create notebook for sub-sub-tabs
        self.settings_notebook = ttk.Notebook(self.parent)
        self.settings_notebook.grid(row=0, column=0, sticky=tk.NSEW, padx=5, pady=5)

        # Basic Settings Sub-Sub-Tab
        self.basic_frame = ttk.Frame(self.settings_notebook)
        self.settings_notebook.add(self.basic_frame, text="⚙️ Basic")
        self.create_basic_settings(self.basic_frame)

        # Mode Selector Sub-Sub-Tab (positioned between Basic and Advanced)
        self.mode_frame = ttk.Frame(self.settings_notebook)
        self.settings_notebook.add(self.mode_frame, text="🎯 Mode")
        self.create_mode_selector(self.mode_frame)

        # Training Settings Sub-Sub-Tab (between Mode and Advanced)
        self.training_frame = ttk.Frame(self.settings_notebook)
        self.settings_notebook.add(self.training_frame, text="🏋️ Training")
        self.create_training_settings(self.training_frame)

        # Advanced Settings Sub-Sub-Tab
        self.advanced_frame = ttk.Frame(self.settings_notebook)
        self.settings_notebook.add(self.advanced_frame, text="🔧 Advanced")
        self.create_advanced_settings(self.advanced_frame)

        # Bind tab change event to refresh Advanced tab when switched to
        self.settings_notebook.bind("<<NotebookTabChanged>>", self._on_settings_tab_changed)

        log_message("CC_SETTINGS: UI created successfully")

    def _on_settings_tab_changed(self, event=None):
        """Called when user switches between Basic/Mode/Advanced tabs"""
        try:
            # Get currently selected tab
            current_tab_index = self.settings_notebook.index(self.settings_notebook.select())

            # Advanced tab is index 3 (Basic=0, Mode=1, Training=2, Advanced=3)
            if current_tab_index == 3:
                # User switched to Advanced tab - refresh to show current mode
                if hasattr(self, 'advanced_settings_interface') and self.advanced_settings_interface:
                    if hasattr(self.advanced_settings_interface, 'refresh'):
                        log_message("CC_SETTINGS: Refreshing Advanced tab after tab switch")
                        self.advanced_settings_interface.refresh()
        except Exception as e:
            log_message(f"CC_SETTINGS ERROR: Failed to handle tab change: {e}")

    def create_basic_settings(self, parent):
        """Create basic settings content"""
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(0, weight=0)  # Profile picker
        parent.rowconfigure(1, weight=0)  # Header
        parent.rowconfigure(2, weight=1)  # Scrollable content
        parent.rowconfigure(3, weight=0)  # Buttons

        # Profile Picker
        self.create_profile_picker(parent, row=0)

        # Header
        header_frame = ttk.Frame(parent, style='Category.TFrame')
        header_frame.grid(row=1, column=0, sticky=tk.EW, padx=10, pady=10)

        ttk.Label(
            header_frame,
            text="⚙️ Basic Settings",
            font=("Arial", 12, "bold"),
            style='CategoryPanel.TLabel'
        ).pack(side=tk.LEFT, padx=(0, 10))

        ttk.Button(
            header_frame,
            text="🔄 Reset to Defaults",
            command=self.reset_to_defaults,
            style='Select.TButton'
        ).pack(side=tk.RIGHT)

        # Scrollable content area
        self.create_scrollable_content(parent, row=2)

        # Bottom buttons
        self.create_button_bar(parent, row=3)

    def create_mode_selector(self, parent):
        """Create mode selector sub-sub-tab"""
        from .mode_selector_tab import ModeSelectorTab

        self.mode_selector_interface = ModeSelectorTab(parent, self.root, self.style, self.parent_tab)
        self.mode_selector_interface.safe_create()

    def create_training_settings(self, parent):
        """Create training automation settings sub-tab"""
        parent.columnconfigure(0, weight=1)
        # Section 1: Automation
        section = ttk.LabelFrame(parent, text="🤖 Training Automation", style='TLabelframe')
        section.grid(row=0, column=0, sticky=tk.EW, padx=10, pady=10)

        # Auto-start training when runtime dataset is created
        self.auto_start_training_var = tk.BooleanVar(value=self.settings.get('auto_start_training_on_runtime_dataset', False))
        ttk.Checkbutton(
            section,
            text="Auto-start training when runtime dataset is created (no confirmation)",
            variable=self.auto_start_training_var,
            style='TCheckbutton'
        ).grid(row=0, column=0, sticky=tk.W, padx=10, pady=(8,4))

        # Auto export + re-eval after training completes
        self.auto_export_reeval_var = tk.BooleanVar(value=self.settings.get('auto_export_reeval_after_training', True))
        ttk.Checkbutton(
            section,
            text="Auto-export GGUF and re-evaluate after training completes",
            variable=self.auto_export_reeval_var,
            style='TCheckbutton'
        ).grid(row=1, column=0, sticky=tk.W, padx=10, pady=(4,10))

        # Section 2: Data Collection & Support
        coll = ttk.LabelFrame(parent, text="📊 Training Data Collection", style='TLabelframe')
        coll.grid(row=1, column=0, sticky=tk.EW, padx=10, pady=10)
        # Training Mode
        ttk.Checkbutton(
            coll,
            text="Enable Training Mode (logs tool calls as datasets)",
            variable=self.training_mode_var,
            style='TCheckbutton',
            command=self.on_training_mode_toggled_session
        ).grid(row=0, column=0, sticky=tk.W, padx=10, pady=(8,4))
        # Training Support toggle
        self.training_support_var = tk.BooleanVar(value=self.settings.get('training_support_enabled', False))
        ttk.Checkbutton(
            coll,
            text="Training Support (auto‑pipeline + extractive verification when Training Mode is ON)",
            variable=self.training_support_var,
            style='TCheckbutton',
            command=self.on_training_support_toggled
        ).grid(row=1, column=0, sticky=tk.W, padx=10, pady=(4,10))

        # Save-as-default (always visible; disabled when Training Mode is OFF)
        self.training_default_save_var2 = tk.BooleanVar(value=False)
        self._default_row2 = ttk.Frame(coll)
        self._default_row2.grid(row=2, column=0, sticky=tk.W, padx=6, pady=(0, 8))
        self.training_default_save_btn2 = ttk.Button(
            self._default_row2,
            text="💾 Save as Default",
            style='Action.TButton',
            command=self.on_training_default_save_toggled
        )
        self.training_default_save_btn2.pack(side=tk.LEFT, padx=4)
        # Add a live note showing what will be saved as defaults
        self._default_note_lbl = ttk.Label(self._default_row2, text="", style='Config.TLabel')
        self._default_note_lbl.pack(side=tk.LEFT, padx=8)
        self._update_default_note()
        try:
            self.training_default_save_btn2.configure(state=('normal' if self.training_mode_var.get() else 'disabled'))
        except Exception:
            pass
        # Listen for Quick Actions per‑chat flips (bind once)
        self._bind_training_events_once()

    def create_advanced_settings(self, parent):
        """Create advanced settings sub-sub-tab"""
        from .advanced_settings_tab import AdvancedSettingsTab

        self.advanced_settings_interface = AdvancedSettingsTab(parent, self.root, self.style, self.parent_tab)
        self.advanced_settings_interface.safe_create()

        # RAG Retrieval parameters + Index preview
        try:
            rag_frame = ttk.LabelFrame(parent, text="🧠 RAG Retrieval", style='TLabelframe')
            rag_frame.grid(row=99, column=0, sticky=tk.EW, padx=10, pady=(6,10))
            for i in range(3):
                rag_frame.columnconfigure(i, weight=0)
            # k1
            ttk.Label(rag_frame, text="BM25 k1:", style='Config.TLabel').grid(row=0, column=0, sticky=tk.W, padx=10, pady=(8,2))
            self.rag_k1_var = tk.StringVar(value=str(self.settings.get('rag_k1', 1.2)))
            ttk.Entry(rag_frame, textvariable=self.rag_k1_var, width=10).grid(row=0, column=1, sticky=tk.W)
            # b
            ttk.Label(rag_frame, text="BM25 b (0-1):", style='Config.TLabel').grid(row=1, column=0, sticky=tk.W, padx=10, pady=2)
            self.rag_b_var = tk.StringVar(value=str(self.settings.get('rag_b', 0.75)))
            ttk.Entry(rag_frame, textvariable=self.rag_b_var, width=10).grid(row=1, column=1, sticky=tk.W)
            # decay days
            ttk.Label(rag_frame, text="Time Decay (days):", style='Config.TLabel').grid(row=2, column=0, sticky=tk.W, padx=10, pady=2)
            self.rag_decay_var = tk.StringVar(value=str(self.settings.get('rag_decay_days', 3)))
            ttk.Entry(rag_frame, textvariable=self.rag_decay_var, width=10).grid(row=2, column=1, sticky=tk.W)

            btns = ttk.Frame(rag_frame)
            btns.grid(row=0, column=2, rowspan=3, sticky=tk.NSEW, padx=10)
            ttk.Button(btns, text='🔍 Preview RAG Index', style='Select.TButton', command=self.preview_rag_index).pack(side=tk.TOP, padx=4, pady=(8,4))
            ttk.Button(btns, text='⚡ Apply Now', style='Action.TButton', command=self.apply_rag_params_live).pack(side=tk.TOP, padx=4, pady=4)

            # Auto-training trigger settings
            auto_frame = ttk.LabelFrame(parent, text="🤖 RAG Auto-Training Trigger", style='TLabelframe')
            auto_frame.grid(row=100, column=0, sticky=tk.EW, padx=10, pady=(0,10))
            self.rag_autotrain_enabled_var = tk.BooleanVar(value=self.settings.get('rag_autotrain_enabled', False))
            ttk.Checkbutton(auto_frame, text='Enable Auto-Training Trigger (uses Training Mode)', variable=self.rag_autotrain_enabled_var, style='TCheckbutton').grid(row=0, column=0, sticky=tk.W, padx=10, pady=(8,2))
            ttk.Label(auto_frame, text='Window (turns):', style='Config.TLabel').grid(row=1, column=0, sticky=tk.W, padx=10)
            self.rag_autotrain_window_var = tk.StringVar(value=str(self.settings.get('rag_autotrain_window', 5)))
            ttk.Entry(auto_frame, textvariable=self.rag_autotrain_window_var, width=10).grid(row=1, column=1, sticky=tk.W)
            ttk.Label(auto_frame, text='Avg Top-1 Score Threshold (0-1):', style='Config.TLabel').grid(row=2, column=0, sticky=tk.W, padx=10, pady=(2,8))
            self.rag_autotrain_threshold_var = tk.StringVar(value=str(self.settings.get('rag_autotrain_threshold', 0.7)))
            ttk.Entry(auto_frame, textvariable=self.rag_autotrain_threshold_var, width=10).grid(row=2, column=1, sticky=tk.W)
            # Promotion gate and override
            self.rag_autotrain_require_promotion_gate_var = tk.BooleanVar(value=self.settings.get('rag_autotrain_require_promotion_gate', True))
            ttk.Checkbutton(auto_frame, text='Require Class Promotion Gate', variable=self.rag_autotrain_require_promotion_gate_var, style='TCheckbutton').grid(row=3, column=0, sticky=tk.W, padx=10, pady=(2,2))
            self.rag_autotrain_backend_override_var = tk.BooleanVar(value=self.settings.get('rag_autotrain_backend_override', False))
            ttk.Checkbutton(auto_frame, text='Allow Backend Override', variable=self.rag_autotrain_backend_override_var, style='TCheckbutton').grid(row=3, column=1, sticky=tk.W, padx=10, pady=(2,2))
            self.class_promotion_earned_var = tk.BooleanVar(value=self.settings.get('class_promotion_earned', False))
            ttk.Checkbutton(auto_frame, text='Class Promotion Earned (manual)', variable=self.class_promotion_earned_var, style='TCheckbutton').grid(row=4, column=0, sticky=tk.W, padx=10, pady=(2,8))
        except Exception:
            pass

    def preview_rag_index(self):
        try:
            # Access rag_service via chat interface
            chat = getattr(self.parent_tab, 'chat_interface', None)
            if not chat or not hasattr(chat, 'rag_service') or not chat.rag_service:
                messagebox.showinfo('RAG Index', 'Chat interface or RAG service not available.')
                return
            svc = chat.rag_service
            # Refresh and compute basic stats
            svc.refresh_index_global()
            docs = getattr(svc, '_global_index', [])
            sessions = len({d.session_id for d in docs})
            chunks = len(docs)
            # Dialog
            dlg = tk.Toplevel(self.root)
            dlg.title('RAG Index Preview')
            dlg.geometry('480x240')
            frm = ttk.Frame(dlg, padding=10)
            frm.pack(fill=tk.BOTH, expand=True)
            ttk.Label(frm, text=f"Global Sessions: {sessions}", style='Config.TLabel').pack(anchor=tk.W)
            ttk.Label(frm, text=f"Global Chunks: {chunks}", style='Config.TLabel').pack(anchor=tk.W)
            # Show top 5 session counts
            from collections import Counter
            cnt = Counter([d.session_id for d in docs])
            top = cnt.most_common(5)
            if top:
                ttk.Label(frm, text="Top Sessions:", style='Config.TLabel').pack(anchor=tk.W, pady=(8,2))
                for sid, n in top:
                    ttk.Label(frm, text=f"• {sid} — {n} chunks", style='Config.TLabel').pack(anchor=tk.W)
            ttk.Button(frm, text='Close', style='Select.TButton', command=dlg.destroy).pack(anchor=tk.E, pady=(12,0))
        except Exception as e:
            messagebox.showerror('RAG Index', f'Failed to preview index: {e}')

    def on_mode_changed(self, new_mode):
        """Called when mode changes - notify advanced settings tab"""
        if hasattr(self, 'advanced_settings_interface') and self.advanced_settings_interface:
            if hasattr(self.advanced_settings_interface, 'on_mode_changed'):
                self.advanced_settings_interface.on_mode_changed(new_mode)

    def create_profile_picker(self, parent, row=0):
        """Create profile picker UI at the top"""
        picker_frame = ttk.LabelFrame(
            parent,
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

    def create_scrollable_content(self, parent, row=1):
        """Create scrollable content area with all settings"""
        container = ttk.Frame(parent, style='Category.TFrame')
        container.grid(row=row, column=0, sticky=tk.NSEW, padx=10, pady=(0, 10))
        container.columnconfigure(0, weight=1)
        container.rowconfigure(0, weight=1)

        # Canvas for scrolling
        canvas = tk.Canvas(
            container,
            bg='#2b2b2b',
            highlightthickness=0
        )
        scrollbar = ttk.Scrollbar(
            container,
            orient="vertical",
            command=canvas.yview
        )
        self.scroll_frame = ttk.Frame(canvas, style='Category.TFrame')

        self.scroll_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas_window = canvas.create_window(
            (0, 0),
            window=self.scroll_frame,
            anchor="nw"
        )
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.bind(
            "<Configure>",
            lambda e: canvas.itemconfig(canvas_window, width=e.width)
        )

        canvas.grid(row=0, column=0, sticky=tk.NSEW)
        scrollbar.grid(row=0, column=1, sticky=tk.NS)

        # Enable mousewheel scrolling
        self.bind_mousewheel_to_canvas(canvas)

        # Add all settings sections (Training Data Collection moved to Training tab)
        self.create_working_directory_section()
        self.create_tool_execution_section()
        self.create_chat_behavior_section()
        self.create_project_settings_section()
        self.create_advanced_settings_section()

    def create_working_directory_section(self):
        """Working Directory Management"""
        frame = ttk.LabelFrame(
            self.scroll_frame,
            text="📁 Working Directory",
            style='TLabelframe'
        )
        frame.pack(fill=tk.X, padx=10, pady=10)

        # Current working directory display
        ttk.Label(
            frame,
            text="Current Working Directory:",
            style='Config.TLabel',
            font=("Arial", 9, "bold")
        ).grid(row=0, column=0, sticky=tk.W, padx=10, pady=(10, 5))

        wd_frame = ttk.Frame(frame, style='Category.TFrame')
        wd_frame.grid(row=1, column=0, sticky=tk.EW, padx=10, pady=(0, 5))
        wd_frame.columnconfigure(0, weight=1)

        self.working_dir_var = tk.StringVar(value=self.settings.get('working_directory', str(Path.cwd())))
        working_dir_entry = ttk.Entry(
            wd_frame,
            textvariable=self.working_dir_var,
            font=("Arial", 9),
            state='readonly'
        )
        working_dir_entry.grid(row=0, column=0, sticky=tk.EW, padx=(0, 5))

        ttk.Button(
            wd_frame,
            text="Browse...",
            command=self.browse_working_directory,
            style='Action.TButton'
        ).grid(row=0, column=1)

        # Auto-update working directory
        self.auto_update_wd_var = tk.BooleanVar(value=self.settings.get('auto_update_working_dir', False))
        ttk.Checkbutton(
            frame,
            text="Automatically update working directory when changing projects",
            variable=self.auto_update_wd_var,
            style='TCheckbutton'
        ).grid(row=2, column=0, sticky=tk.W, padx=10, pady=(0, 10))

    def create_tool_execution_section(self):
        """Tool Execution Preferences"""
        frame = ttk.LabelFrame(
            self.scroll_frame,
            text="🔧 Tool Execution",
            style='TLabelframe'
        )
        frame.pack(fill=tk.X, padx=10, pady=10)

        # Confirmation gates
        ttk.Label(
            frame,
            text="Confirmation Requirements:",
            style='Config.TLabel',
            font=("Arial", 9, "bold")
        ).grid(row=0, column=0, sticky=tk.W, padx=10, pady=(10, 5))

        self.confirm_high_risk_var = tk.BooleanVar(value=self.settings.get('confirm_high_risk_tools', True))
        ttk.Checkbutton(
            frame,
            text="Require confirmation for HIGH risk tools (file_delete, etc.)",
            variable=self.confirm_high_risk_var,
            style='TCheckbutton'
        ).grid(row=1, column=0, sticky=tk.W, padx=20, pady=2)

        self.confirm_critical_var = tk.BooleanVar(value=self.settings.get('confirm_critical_tools', True))
        ttk.Checkbutton(
            frame,
            text="Require confirmation for CRITICAL risk tools (bash_execute)",
            variable=self.confirm_critical_var,
            style='TCheckbutton'
        ).grid(row=2, column=0, sticky=tk.W, padx=20, pady=2)

        # Tool timeouts
        ttk.Label(
            frame,
            text="Tool Execution Timeout (seconds):",
            style='Config.TLabel',
            font=("Arial", 9)
        ).grid(row=3, column=0, sticky=tk.W, padx=10, pady=(10, 5))

        self.tool_timeout_var = tk.StringVar(value=str(self.settings.get('tool_timeout', 30)))
        ttk.Entry(
            frame,
            textvariable=self.tool_timeout_var,
            font=("Arial", 9),
            width=10
        ).grid(row=4, column=0, sticky=tk.W, padx=20, pady=(0, 5))

        # Logging
        self.log_tool_execution_var = tk.BooleanVar(value=self.settings.get('log_tool_execution', True))
        ttk.Checkbutton(
            frame,
            text="Log all tool executions to file",
            variable=self.log_tool_execution_var,
            style='TCheckbutton'
        ).grid(row=5, column=0, sticky=tk.W, padx=10, pady=(5, 10))

    

        # Save-as-default (always visible; disabled when Training Mode is OFF)
        self.training_default_save_var = tk.BooleanVar(value=False)
        self._default_row = ttk.Frame(frame)
        self._default_row.grid(row=4, column=0, sticky=tk.W, padx=6, pady=(0, 8))
        self.training_default_save_btn = ttk.Button(
            self._default_row,
            text="💾 Save as Default",
            style='Action.TButton',
            command=self.on_training_default_save_toggled
        )
        self.training_default_save_btn.pack(side=tk.LEFT, padx=4)
        try:
            self.training_default_save_btn.configure(state=('normal' if self.training_mode_var.get() else 'disabled'))
        except Exception:
            pass
        # Listen for Quick Actions per‑chat Training Mode flips (bind once)
        self._bind_training_events_once()

    def on_training_mode_toggled_session(self):
        """Handle per‑chat Training Mode toggle (Training sub‑tab)."""
        enabled = self.training_mode_var.get()
        log_message(f"CC_SETTINGS: Session Training Mode {'enabled' if enabled else 'disabled'}")
        # Flip current chat state; default is persisted only via the Save-as-default control
        self.settings['training_mode_enabled'] = bool(enabled)
        if hasattr(self.parent_tab, 'set_training_mode'):
            self.parent_tab.set_training_mode(enabled)
        self.update_training_status_label()
        self._update_default_save_state()
        # Mirror visibility for the Training sub-tab save row if present
        try:
            if hasattr(self, '_default_row2'):
                if hasattr(self, 'training_default_save_btn2') and self.training_default_save_btn2:
                    self.training_default_save_btn2.configure(state=('normal' if enabled else 'disabled'))
        except Exception:
            pass

    def on_training_mode_toggled_default(self):
        """Handle default Training Mode toggle (Basic page) — does NOT flip current chat."""
        enabled = self.training_mode_var.get()
        log_message(f"CC_SETTINGS: Default Training Mode {'enabled' if enabled else 'disabled'}")
        self.settings['training_mode_enabled'] = bool(enabled)
        self.update_training_status_label()
        self._update_default_save_state()

    def on_training_support_toggled(self):
        enabled = self.training_support_var.get()
        log_message(f"CC_SETTINGS: Training support {'enabled' if enabled else 'disabled'}")
        # Gate: Support only allowed when Training Mode is ON
        if not self.training_mode_var.get():
            try:
                self.training_support_var.set(False)
                messagebox.showinfo('Training Support', 'Enable Training Mode to use Training Support.')
            except Exception:
                pass
            return
        self.settings['training_support_enabled'] = bool(enabled)
        if hasattr(self.parent_tab, 'set_training_support'):
            self.parent_tab.set_training_support(enabled)

    @debug_ui_event(_settings_tab.backup_20251120_002414_debug_logger)
    def update_training_status_label(self):
        """Update training mode status label (if present in this view)."""
        try:
            lbl = getattr(self, 'training_status_label', None)
            if not lbl:
                return
            if self.training_mode_var.get():
                lbl.config(text="Status: ✅ Active - Logging tool calls", foreground='#00ff00')
            else:
                lbl.config(text="Status: ⭕ Disabled", foreground='#888888')
        except Exception:
            pass

    def _update_default_note(self):
        """Update the inline note showing intended default state."""
        try:
            mode_txt = 'On' if self.training_mode_var.get() else 'Off'
            sup_on = False
            try:
                sup_on = bool(self.training_support_var.get())
            except Exception:
                sup_on = False
            sup_txt = 'On' if sup_on else 'Off'
            if hasattr(self, '_default_note_lbl') and self._default_note_lbl:
                self._default_note_lbl.config(text=f"[Default: Mode {mode_txt} | Support {sup_txt}]")
        except Exception:
            pass

    def _on_training_mode_changed_event(self, event=None):
        """Sync checkbox and controls when Quick Actions toggles Training Mode."""
        try:
            import json as _json
            if event and getattr(event, 'data', None):
                payload = _json.loads(event.data)
                enabled = bool(payload.get('enabled', False))
                self.training_mode_var.set(enabled)
                self.update_training_status_label()
                self._update_default_note()
                try:
                    if hasattr(self, 'training_default_save_btn2') and self.training_default_save_btn2:
                        # If TM turned off, also force Support OFF in UI
                        if not enabled and hasattr(self, 'training_support_var') and self.training_support_var.get():
                            self.training_support_var.set(False)
                except Exception:
                    pass
        except Exception:
            pass

    def _on_training_support_changed_event(self, event=None):
        """Sync Support toggle when emitted from Chat/Controller."""
        try:
            import json as _json

from debug_logger import get_debug_logger, debug_method, debug_ui_event

            if event and getattr(event, 'data', None):
                payload = _json.loads(event.data)
                enabled = bool(payload.get('enabled', False))
                try:
                    self.training_support_var.set(enabled)
                except Exception:
                    pass
                self._update_default_save_state()
        except Exception:
            pass

    def _bind_training_events_once(self):
        """Bind TrainingMode/Support change events once."""
        try:
            if not getattr(self, '_tm_event_bound', False):
                self.root.bind("<<TrainingModeChanged>>", self._on_training_mode_changed_event)
                self._tm_event_bound = True
        except Exception:
            pass
        try:
            if not getattr(self, '_ts_event_bound', False):
                self.root.bind("<<TrainingSupportChanged>>", self._on_training_support_changed_event)
                self._ts_event_bound = True
        except Exception:
            pass

    def on_training_default_save_toggled(self):
        """Persist current Training Mode/Support as default for re-launch (one‑shot)."""
        try:
            # Save current toggles as defaults regardless of checkbutton vars (invoked by button)
            backend_path = Path(__file__).parent.parent / "custom_code_settings.json"
            cur = {}
            if backend_path.exists():
                with open(backend_path, 'r') as bf:
                    cur = json.load(bf) or {}
            cur['training_mode_enabled'] = bool(self.training_mode_var.get())
            cur['training_support_enabled'] = bool(self.training_support_var.get())
            with open(backend_path, 'w') as wf:
                json.dump(cur, wf, indent=2)
            try:
                messagebox.showinfo('Saved', 'Default Training settings saved for new chats and relaunch.')
            except Exception:
                pass
        except Exception:
            pass
        finally:
            try:
                if hasattr(self, 'training_default_save_var'):
                    self.training_default_save_var.set(False)
                if hasattr(self, 'training_default_save_var2'):
                    self.training_default_save_var2.set(False)
            except Exception:
                pass

    def create_chat_behavior_section(self):
        """Chat Behavior Settings"""
        frame = ttk.LabelFrame(
            self.scroll_frame,
            text="💬 Chat Behavior",
            style='TLabelframe'
        )
        frame.pack(fill=tk.X, padx=10, pady=10)

        # Auto-mount
        self.auto_mount_var = tk.BooleanVar(value=self.settings.get('auto_mount_model', False))
        ttk.Checkbutton(
            frame,
            text="Automatically mount model when selected",
            variable=self.auto_mount_var,
            style='TCheckbutton'
        ).grid(row=0, column=0, sticky=tk.W, padx=10, pady=(10, 5))

        # Auto-save history
        self.auto_save_history_var = tk.BooleanVar(value=self.settings.get('auto_save_history', True))
        ttk.Checkbutton(
            frame,
            text="Automatically save conversation history",
            variable=self.auto_save_history_var,
            style='TCheckbutton'
        ).grid(row=1, column=0, sticky=tk.W, padx=10, pady=5)

        # Model popup preview toggle
        self.model_popup_enabled_var = tk.BooleanVar(value=self.settings.get('model_popup_enabled', False))
        popup_cb = ttk.Checkbutton(
            frame,
            text="Enable Model Popup Preview (Experimental - S7)",
            variable=self.model_popup_enabled_var,
            style='TCheckbutton'
        )
        popup_cb.grid(row=1, column=1, sticky=tk.W, padx=10, pady=5)

        # Add tooltip/description
        ttk.Label(
            frame,
            text="When enabled: single-click shows popup, double-click sets active\nWhen disabled: single-click sets active, double-click mounts",
            style='Config.TLabel',
            font=("Arial", 8),
            foreground='#888888'
        ).grid(row=2, column=1, sticky=tk.W, padx=20, pady=(0, 5))

        # History retention
        ttk.Label(
            frame,
            text="History Retention (days, 0 = forever):",
            style='Config.TLabel',
            font=("Arial", 9)
        ).grid(row=2, column=0, sticky=tk.W, padx=10, pady=(10, 5))

        self.history_retention_var = tk.StringVar(value=str(self.settings.get('history_retention_days', 0)))
        ttk.Entry(
            frame,
            textvariable=self.history_retention_var,
            font=("Arial", 9),
            width=10
        ).grid(row=3, column=0, sticky=tk.W, padx=20, pady=(0, 5))

        # Max message length
        ttk.Label(
            frame,
            text="Max Message Length (characters, 0 = unlimited):",
            style='Config.TLabel',
            font=("Arial", 9)
        ).grid(row=4, column=0, sticky=tk.W, padx=10, pady=(10, 5))

        self.max_message_length_var = tk.StringVar(value=str(self.settings.get('max_message_length', 0)))
        ttk.Entry(
            frame,
            textvariable=self.max_message_length_var,
            font=("Arial", 9),
            width=10
        ).grid(row=5, column=0, sticky=tk.W, padx=20, pady=(0, 10))

        # GPU Layers for Llama Server
        ttk.Label(
            frame,
            text="Llama Server GPU Layers (-1 = all, 0 = CPU only, 1-99 = partial):",
            style='Config.TLabel',
            font=("Arial", 9)
        ).grid(row=5, column=1, sticky=tk.W, padx=10, pady=(10, 5))

        self.gpu_layers_var = tk.IntVar(value=self.settings.get('llama_server_gpu_layers', -1))
        ttk.Spinbox(
            frame,
            from_=-1,
            to=99,
            textvariable=self.gpu_layers_var,
            font=("Arial", 9),
            width=8
        ).grid(row=6, column=1, sticky=tk.W, padx=20, pady=(0, 10))

        # Temperature control
        temp_frame = ttk.Frame(frame, style='Category.TFrame')
        temp_frame.grid(row=7, column=0, columnspan=2, sticky=tk.EW, padx=10, pady=(10, 5))
        temp_frame.columnconfigure(1, weight=1)

        self.temp_label = ttk.Label(
            temp_frame,
            text=f"Temperature: {self.settings.get('temperature', 0.8):.1f}",
            style='Config.TLabel',
            font=("Arial", 9, "bold")
        )
        self.temp_label.grid(row=0, column=0, sticky=tk.W)

        self.temperature_var = tk.DoubleVar(value=self.settings.get('temperature', 0.8))
        temp_scale = ttk.Scale(
            temp_frame,
            from_=0.0,
            to=2.0,
            orient=tk.HORIZONTAL,
            variable=self.temperature_var,
            command=self.update_temp_label
        )
        temp_scale.grid(row=0, column=1, sticky=tk.EW, padx=(10, 0))

        # RAG DEBUG toggle
        self.rag_debug_var = tk.BooleanVar(value=self.settings.get('rag_debug', False))
        ttk.Checkbutton(
            frame,
            text="RAG DEBUG (log retrieval provenance to chat)",
            variable=self.rag_debug_var,
            style='TCheckbutton'
        ).grid(row=7, column=0, sticky=tk.W, padx=10, pady=(5, 10))

    def update_temp_label(self, value):
        self.temp_label.config(text=f"Temperature: {float(value):.1f}")

    def create_project_settings_section(self):
        """Project Workspace Settings"""
        frame = ttk.LabelFrame(
            self.scroll_frame,
            text="📁 Project Settings",
            style='TLabelframe'
        )
        frame.pack(fill=tk.X, padx=10, pady=10)

        # Default project directory
        ttk.Label(
            frame,
            text="Default Project Directory:",
            style='Config.TLabel',
            font=("Arial", 9, "bold")
        ).grid(row=0, column=0, sticky=tk.W, padx=10, pady=(10, 5))

        proj_frame = ttk.Frame(frame, style='Category.TFrame')
        proj_frame.grid(row=1, column=0, sticky=tk.EW, padx=10, pady=(0, 5))
        proj_frame.columnconfigure(0, weight=1)

        self.project_dir_var = tk.StringVar(value=self.settings.get('default_project_dir', str(Path.home() / "Projects")))
        ttk.Entry(
            proj_frame,
            textvariable=self.project_dir_var,
            font=("Arial", 9),
            state='readonly'
        ).grid(row=0, column=0, sticky=tk.EW, padx=(0, 5))

        ttk.Button(
            proj_frame,
            text="Browse...",
            command=self.browse_project_directory,
            style='Action.TButton'
        ).grid(row=0, column=1)

        # Auto-load last project
        self.auto_load_project_var = tk.BooleanVar(value=self.settings.get('auto_load_last_project', False))
        ttk.Checkbutton(
            frame,
            text="Automatically load last opened project on startup",
            variable=self.auto_load_project_var,
            style='TCheckbutton'
        ).grid(row=2, column=0, sticky=tk.W, padx=10, pady=(5, 10))

        # Project RAG Adapters (per-project connectors)
        adapters = ttk.LabelFrame(frame, text="🧠 Project RAG Adapters (used as modular context sources)", style='TLabelframe')
        adapters.grid(row=3, column=0, sticky=tk.EW, padx=10, pady=(0,10))
        self.project_adapter_vars = {}
        try:
            projects_root = Path('Data/projects')
            project_names = sorted([p.name for p in projects_root.iterdir() if p.is_dir()]) if projects_root.exists() else []
            enabled = []
            try:
                enabled = list(self.settings.get('rag_project_adapters', []))
            except Exception:
                enabled = []
            col = 0; row = 0
            for name in project_names:
                var = tk.BooleanVar(value=(name in enabled))
                cb = ttk.Checkbutton(adapters, text=name, variable=var, style='TCheckbutton')
                cb.grid(row=row, column=col, sticky=tk.W, padx=8, pady=2)
                self.project_adapter_vars[name] = var
                col += 1
                if col >= 3:
                    col = 0; row += 1
            if not project_names:
                ttk.Label(adapters, text="No projects found.", style='Config.TLabel').grid(row=0, column=0, sticky=tk.W, padx=8, pady=4)
        except Exception:
            ttk.Label(adapters, text="Failed to list projects.", style='Config.TLabel').grid(row=0, column=0, sticky=tk.W, padx=8, pady=4)

    def create_advanced_settings_section(self):
        """Advanced Settings"""
        frame = ttk.LabelFrame(
            self.scroll_frame,
            text="⚡ Advanced Settings",
            style='TLabelframe'
        )
        frame.pack(fill=tk.X, padx=10, pady=10)

        # Enable debug logging
        self.debug_logging_var = tk.BooleanVar(value=self.settings.get('enable_debug_logging', False))
        ttk.Checkbutton(
            frame,
            text="Enable debug logging for Custom Code features",
            variable=self.debug_logging_var,
            style='TCheckbutton'
        ).grid(row=0, column=0, sticky=tk.W, padx=10, pady=(10, 5))

        # Show tool call details
        self.show_tool_details_var = tk.BooleanVar(value=self.settings.get('show_tool_call_details', True))
        ttk.Checkbutton(
            frame,
            text="Show detailed tool call information in chat",
            variable=self.show_tool_details_var,
            style='TCheckbutton'
        ).grid(row=1, column=0, sticky=tk.W, padx=10, pady=5)

        # Enable experimental features
        self.experimental_var = tk.BooleanVar(value=self.settings.get('enable_experimental', False))
        ttk.Checkbutton(
            frame,
            text="Enable experimental features (may be unstable)",
            variable=self.experimental_var,
            style='TCheckbutton'
        ).grid(row=2, column=0, sticky=tk.W, padx=10, pady=(5, 10))

    def create_button_bar(self, parent, row=2):
        """Create bottom button bar"""
        button_frame = ttk.Frame(parent, style='Category.TFrame')
        button_frame.grid(row=row, column=0, sticky=tk.EW, padx=10, pady=(0, 10))

        ttk.Button(
            button_frame,
            text="💾 Save Settings",
            command=self.save_settings,
            style='Action.TButton'
        ).pack(side=tk.LEFT, padx=5)

        ttk.Button(
            button_frame,
            text="↺ Reload",
            command=self.reload_settings,
            style='Select.TButton'
        ).pack(side=tk.LEFT, padx=5)

        self.profile_status_label = ttk.Label(
            button_frame,
            text=f"Profile: {self.current_profile_name.get()}",
            style='Config.TLabel',
            font=("Arial", 8)
        )
        self.profile_status_label.pack(side=tk.RIGHT, padx=5)

    def browse_working_directory(self):
        """Browse for working directory"""
        directory = filedialog.askdirectory(
            title="Select Working Directory",
            initialdir=self.working_dir_var.get()
        )
        if directory:
            self.working_dir_var.set(directory)
            log_message(f"CC_SETTINGS: Working directory set to {directory}")

    def browse_project_directory(self):
        """Browse for default project directory"""
        directory = filedialog.askdirectory(
            title="Select Default Project Directory",
            initialdir=self.project_dir_var.get()
        )
        if directory:
            self.project_dir_var.set(directory)
            log_message(f"CC_SETTINGS: Project directory set to {directory}")

    def load_profile(self):
        """Load Tool Profile from unified system"""
        try:
            profile_name = self.current_profile_name.get()
            profile = get_unified_tool_profile(profile_name, migrate=True)
            log_message(f"CC_SETTINGS: Loaded profile '{profile_name}'")
            return profile
        except Exception as e:
            log_message(f"CC_SETTINGS ERROR: Failed to load profile: {e}")
            # Return minimal default profile
            return {
                "profile_name": "Default",
                "version": "1.0",
                "tools": {"enabled_tools": {}},
                "execution": {
                    "working_directory": str(Path.cwd()),
                    "auto_update_working_dir": False,
                    "default_project_dir": str(Path.home() / "Projects")
                },
                "chat": {
                    "auto_mount_model": False,
                    "auto_save_history": True,
                    "history_retention_days": 0,
                    "max_message_length": 0,
                    "llama_server_gpu_layers": -1
                },
                "orchestrator": {},
                "notes": ""
            }

    def extract_settings_from_profile(self):
        """Extract settings dict from unified profile for UI binding"""
        try:
            # Map profile sections to legacy settings format for UI compatibility
            execution = self.profile.get("execution", {})
            chat = self.profile.get("chat", {})
            tools = self.profile.get("tools", {})
            tools_logging = tools.get("logging", {})
            confirmation = tools.get("confirmation_policy", {})
            timeouts = tools.get("timeouts_sec", {})

            settings = {
                # Execution section
                'working_directory': execution.get('working_directory', str(Path.cwd())),
                'auto_update_working_dir': execution.get('auto_update_working_dir', False),
                'default_project_dir': execution.get('default_project_dir', str(Path.home() / "Projects")),

                # Chat section
                'auto_mount_model': chat.get('auto_mount_model', False),
                'auto_save_history': chat.get('auto_save_history', True),
                'history_retention_days': chat.get('history_retention_days', 0),
                'max_message_length': chat.get('max_message_length', 0),
                'llama_server_gpu_layers': chat.get('llama_server_gpu_layers', -1),
                'temperature': chat.get('temperature', 0.8),
                # Local-only RAG debug flag
                'rag_debug': bool(self.profile.get('rag_debug', False)),

                # Tools section
                'confirm_high_risk_tools': confirmation.get('default_minimum_risk_to_confirm', 'high') in ['high', 'critical'],
                'confirm_critical_tools': confirmation.get('default_minimum_risk_to_confirm', 'critical') == 'critical',
                'tool_timeout': timeouts.get('default', 30),
                'log_tool_execution': tools_logging.get('tool_calls', True),

                # Local-only settings (not in profile)
                'training_mode_enabled': False,
                'auto_load_last_project': False,
                'enable_debug_logging': False,
                'show_tool_call_details': True,
                'enable_experimental': False,
                # Training automation flags (from chat section if present)
                'auto_start_training_on_runtime_dataset': chat.get('auto_start_training_on_runtime_dataset', False),
                'auto_export_reeval_after_training': chat.get('auto_export_reeval_after_training', True)
            }

            # Supplement local-only flags from backend settings file
            try:
                backend_path = Path(__file__).parent.parent / "custom_code_settings.json"
                if backend_path.exists():
                    with open(backend_path, 'r') as bf:
                        bset = json.load(bf) or {}
                    if 'rag_debug' in bset:
                        settings['rag_debug'] = bool(bset.get('rag_debug', False))
                    # Persisted Training toggles (session defaults)
                    if 'training_mode_enabled' in bset:
                        settings['training_mode_enabled'] = bool(bset.get('training_mode_enabled', False))
                    if 'training_support_enabled' in bset:
                        settings['training_support_enabled'] = bool(bset.get('training_support_enabled', False))
            except Exception:
                pass

            log_message("CC_SETTINGS: Extracted settings from profile")
            # Supplement local-only flags/params from backend settings file (continued)
            try:
                backend_path = Path(__file__).parent.parent / "custom_code_settings.json"
                if backend_path.exists():
                    with open(backend_path, 'r') as bf:
                        bset = json.load(bf) or {}
                    if 'rag_debug' in bset:
                        settings['rag_debug'] = bool(bset.get('rag_debug', False))
                    if 'rag_k1' in bset:
                        settings['rag_k1'] = float(bset.get('rag_k1', 1.2))
                    if 'rag_b' in bset:
                        settings['rag_b'] = float(bset.get('rag_b', 0.75))
                    if 'rag_decay_days' in bset:
                        settings['rag_decay_days'] = float(bset.get('rag_decay_days', 3))
                    if 'rag_autotrain_enabled' in bset:
                        settings['rag_autotrain_enabled'] = bool(bset.get('rag_autotrain_enabled', False))
                    if 'rag_autotrain_window' in bset:
                        settings['rag_autotrain_window'] = int(bset.get('rag_autotrain_window', 5))
                    if 'rag_autotrain_threshold' in bset:
                        settings['rag_autotrain_threshold'] = float(bset.get('rag_autotrain_threshold', 0.7))
                    if 'rag_project_adapters' in bset:
                        settings['rag_project_adapters'] = list(bset.get('rag_project_adapters', []))
                    if 'rag_autotrain_require_promotion_gate' in bset:
                        settings['rag_autotrain_require_promotion_gate'] = bool(bset.get('rag_autotrain_require_promotion_gate', True))
                    if 'rag_autotrain_backend_override' in bset:
                        settings['rag_autotrain_backend_override'] = bool(bset.get('rag_autotrain_backend_override', False))
                    if 'class_promotion_earned' in bset:
                        settings['class_promotion_earned'] = bool(bset.get('class_promotion_earned', False))
            except Exception:
                pass
            return settings

        except Exception as e:
            log_message(f"CC_SETTINGS ERROR: Failed to extract settings: {e}")
            return self.get_default_settings()

    def get_default_settings(self):
        """Get default settings"""
        return {
            'working_directory': str(Path.cwd()),
            'auto_update_working_dir': False,
            'confirm_high_risk_tools': True,
            'confirm_critical_tools': True,
            'tool_timeout': 30,
            'log_tool_execution': True,
            'training_mode_enabled': False,
            'auto_mount_model': False,
            'auto_save_history': True,
            'history_retention_days': 0,
            'max_message_length': 0,
            'llama_server_gpu_layers': -1,
            'temperature': 0.8,
            'rag_debug': False,
            'default_project_dir': str(Path.home() / "Projects"),
            'auto_load_last_project': False,
            'enable_debug_logging': False,
            'show_tool_call_details': True,
            'enable_experimental': False,
            'auto_start_training_on_runtime_dataset': False,
            'auto_export_reeval_after_training': True,
            'rag_k1': 1.2,
            'rag_b': 0.75,
            'rag_decay_days': 3,
            'rag_autotrain_enabled': False,
            'rag_autotrain_window': 5,
            'rag_autotrain_threshold': 0.7,
            'rag_project_adapters': [],
            'rag_autotrain_require_promotion_gate': True,
            'rag_autotrain_backend_override': False,
            'class_promotion_earned': False,
        }

    def save_settings(self):
        """Save settings to unified Tool Profile"""
        try:
            # Update profile sections from UI
            profile_name = self.current_profile_name.get()

            # Update execution section
            self.profile.setdefault("execution", {})
            self.profile["execution"]["working_directory"] = self.working_dir_var.get()
            self.profile["execution"]["auto_update_working_dir"] = self.auto_update_wd_var.get()
            self.profile["execution"]["default_project_dir"] = self.project_dir_var.get()

            # Update chat section
            self.profile.setdefault("chat", {})
            self.profile["chat"]["auto_mount_model"] = self.auto_mount_var.get()
            self.profile["chat"]["auto_save_history"] = self.auto_save_history_var.get()
            self.profile["chat"]["history_retention_days"] = int(self.history_retention_var.get())
            self.profile["chat"]["max_message_length"] = int(self.max_message_length_var.get())
            self.profile["chat"]["llama_server_gpu_layers"] = int(self.gpu_layers_var.get())
            self.profile["chat"]["temperature"] = round(self.temperature_var.get(), 1)
            # Training automation flags persisted under chat
            self.profile["chat"]["auto_start_training_on_runtime_dataset"] = bool(self.auto_start_training_var.get())
            self.profile["chat"]["auto_export_reeval_after_training"] = bool(self.auto_export_reeval_var.get())

            # Update tools section
            self.profile.setdefault("tools", {})
            self.profile["tools"].setdefault("confirmation_policy", {})
            self.profile["tools"].setdefault("timeouts_sec", {})
            self.profile["tools"].setdefault("logging", {})

            # Map confirmation checkboxes to risk levels
            if self.confirm_critical_var.get():
                risk_level = "critical"
            elif self.confirm_high_risk_var.get():
                risk_level = "high"
            else:
                risk_level = "none"
            self.profile["tools"]["confirmation_policy"]["default_minimum_risk_to_confirm"] = risk_level

            self.profile["tools"]["timeouts_sec"]["default"] = int(self.tool_timeout_var.get())
            self.profile["tools"]["logging"]["tool_calls"] = self.log_tool_execution_var.get()

            # Update metadata
            self.profile["profile_name"] = profile_name
            self.profile["updated_at"] = datetime.utcnow().isoformat() + "Z"

            # Save via unified API (atomic write + backup)
            save_tool_profile(profile_name, self.profile)

            # Also dump minimal backend settings for ChatInterfaceTab consumption
            try:
                backend = {
                    'working_directory': self.working_dir_var.get(),
                    'auto_mount_model': self.auto_mount_var.get(),
                    'auto_save_history': self.auto_save_history_var.get(),
                    'model_popup_enabled': self.model_popup_enabled_var.get(),
                    'llama_server_gpu_layers': int(self.gpu_layers_var.get()),
                    'show_tool_call_details': self.show_tool_details_var.get(),
                    'tool_timeout': int(self.tool_timeout_var.get()),
                    # Training toggles persisted for session default on reload
                    'training_mode_enabled': bool(self.training_mode_var.get()),
                    'training_support_enabled': bool(self.training_support_var.get()),
                    'auto_start_training_on_runtime_dataset': bool(self.auto_start_training_var.get()),
                    'auto_export_reeval_after_training': bool(self.auto_export_reeval_var.get()),
                    'rag_debug': bool(self.rag_debug_var.get()),
                    'rag_k1': float(self.rag_k1_var.get()) if hasattr(self, 'rag_k1_var') else 1.2,
                    'rag_b': float(self.rag_b_var.get()) if hasattr(self, 'rag_b_var') else 0.75,
                    'rag_decay_days': float(self.rag_decay_var.get()) if hasattr(self, 'rag_decay_var') else 3.0,
                    'rag_autotrain_enabled': bool(self.rag_autotrain_enabled_var.get()) if hasattr(self, 'rag_autotrain_enabled_var') else False,
                    'rag_autotrain_window': int(self.rag_autotrain_window_var.get()) if hasattr(self, 'rag_autotrain_window_var') else 5,
                    'rag_autotrain_threshold': float(self.rag_autotrain_threshold_var.get()) if hasattr(self, 'rag_autotrain_threshold_var') else 0.7,
                    'rag_autotrain_require_promotion_gate': bool(self.rag_autotrain_require_promotion_gate_var.get()) if hasattr(self, 'rag_autotrain_require_promotion_gate_var') else True,
                    'rag_autotrain_backend_override': bool(self.rag_autotrain_backend_override_var.get()) if hasattr(self, 'rag_autotrain_backend_override_var') else False,
                    'class_promotion_earned': bool(self.class_promotion_earned_var.get()) if hasattr(self, 'class_promotion_earned_var') else False,
                    'rag_project_adapters': [name for name, var in getattr(self, 'project_adapter_vars', {}).items() if var.get()],
                }
                settings_file = Path(__file__).parent.parent / "custom_code_settings.json"
                with open(settings_file, 'w') as f:
                    json.dump(backend, f, indent=2)
            except Exception as e:
                log_message(f"CC_SETTINGS: Failed to persist backend settings: {e}")

            # Update local settings cache
            self.settings = self.extract_settings_from_profile()

            log_message(f"CC_SETTINGS: Profile '{profile_name}' saved successfully")
            messagebox.showinfo("Profile Saved", f"Tool Profile '{profile_name}' has been saved successfully!")

            # Update parent_tab's popup feature flag immediately (no restart needed)
            if hasattr(self.parent_tab, '_popup_feature_enabled'):
                self.parent_tab._popup_feature_enabled = self.model_popup_enabled_var.get()
                log_message(f"CC_SETTINGS: Updated popup feature flag to {self.model_popup_enabled_var.get()}")

            # Update tool executor working directory if needed
            if hasattr(self.parent_tab, 'chat_interface') and self.parent_tab.chat_interface:
                if hasattr(self.parent_tab.chat_interface, 'tool_executor'):
                    if self.parent_tab.chat_interface.tool_executor:
                        self.parent_tab.chat_interface.tool_executor.set_working_directory(
                            self.profile["execution"]["working_directory"]
                        )

            # Update status label
            self.profile_status_label.config(text=f"Profile: {profile_name} (saved)")

        except Exception as e:
            error_msg = f"Failed to save profile: {str(e)}"
            log_message(f"CC_SETTINGS ERROR: {error_msg}")
            messagebox.showerror("Save Error", error_msg)

    def reload_settings(self):
        """Reload settings from unified profile"""
        self.profile = self.load_profile()
        self.settings = self.extract_settings_from_profile()

        # Update all UI elements
        self.working_dir_var.set(self.settings.get('working_directory', str(Path.cwd())))
        self.auto_update_wd_var.set(self.settings.get('auto_update_working_dir', False))
        self.confirm_high_risk_var.set(self.settings.get('confirm_high_risk_tools', True))
        self.confirm_critical_var.set(self.settings.get('confirm_critical_tools', True))
        self.tool_timeout_var.set(str(self.settings.get('tool_timeout', 30)))
        self.log_tool_execution_var.set(self.settings.get('log_tool_execution', True))
        self.training_mode_var.set(self.settings.get('training_mode_enabled', False))
        self.update_training_status_label()
        self.auto_mount_var.set(self.settings.get('auto_mount_model', False))
        self.auto_save_history_var.set(self.settings.get('auto_save_history', True))
        self.history_retention_var.set(str(self.settings.get('history_retention_days', 0)))
        self.max_message_length_var.set(str(self.settings.get('max_message_length', 0)))
        self.gpu_layers_var.set(self.settings.get('llama_server_gpu_layers', -1))
        self.temperature_var.set(self.settings.get('temperature', 0.8))
        self.update_temp_label(self.temperature_var.get())
        self.project_dir_var.set(self.settings.get('default_project_dir', str(Path.home() / "Projects")))
        self.auto_load_project_var.set(self.settings.get('auto_load_last_project', False))
        self.debug_logging_var.set(self.settings.get('enable_debug_logging', False))
        self.show_tool_details_var.set(self.settings.get('show_tool_call_details', True))
        self.experimental_var.set(self.settings.get('enable_experimental', False))
        # RAG debug and params
        if hasattr(self, 'rag_debug_var'):
            self.rag_debug_var.set(self.settings.get('rag_debug', False))
        if hasattr(self, 'rag_k1_var'):
            try: self.rag_k1_var.set(str(self.settings.get('rag_k1', 1.2)))
            except Exception: pass
        if hasattr(self, 'rag_b_var'):
            try: self.rag_b_var.set(str(self.settings.get('rag_b', 0.75)))
            except Exception: pass
        if hasattr(self, 'rag_decay_var'):
            try: self.rag_decay_var.set(str(self.settings.get('rag_decay_days', 3)))
            except Exception: pass
        if hasattr(self, 'rag_autotrain_enabled_var'):
            try: self.rag_autotrain_enabled_var.set(self.settings.get('rag_autotrain_enabled', False))
            except Exception: pass
        if hasattr(self, 'rag_autotrain_window_var'):
            try: self.rag_autotrain_window_var.set(str(self.settings.get('rag_autotrain_window', 5)))
            except Exception: pass
        if hasattr(self, 'rag_autotrain_threshold_var'):
            try: self.rag_autotrain_threshold_var.set(str(self.settings.get('rag_autotrain_threshold', 0.7)))
            except Exception: pass
        # Training automation toggles
        if hasattr(self, 'auto_start_training_var'):
            self.auto_start_training_var.set(self.settings.get('auto_start_training_on_runtime_dataset', False))
        if hasattr(self, 'auto_export_reeval_var'):
            self.auto_export_reeval_var.set(self.settings.get('auto_export_reeval_after_training', True))

        log_message(f"CC_SETTINGS: Profile '{self.current_profile_name.get()}' reloaded")
        messagebox.showinfo("Profile Reloaded", f"Profile '{self.current_profile_name.get()}' has been reloaded")

    def reset_to_defaults(self):
        """Reset current profile to default values"""
        if messagebox.askyesno(
            "Reset to Defaults",
            f"Are you sure you want to reset profile '{self.current_profile_name.get()}' to default values?"
        ):
            # Get default settings and map to profile structure
            defaults = self.get_default_settings()
            profile_name = self.current_profile_name.get()

            # Create fresh profile with defaults
            self.profile = {
                "profile_name": profile_name,
                "version": "1.0",
                "created_at": self.profile.get("created_at", datetime.utcnow().isoformat() + "Z"),
                "updated_at": datetime.utcnow().isoformat() + "Z",
                "execution": {
                    "working_directory": defaults['working_directory'],
                    "auto_update_working_dir": defaults['auto_update_working_dir'],
                    "default_project_dir": defaults['default_project_dir']
                },
                "chat": {
                    "auto_mount_model": defaults['auto_mount_model'],
                    "auto_save_history": defaults['auto_save_history'],
                    "history_retention_days": defaults['history_retention_days'],
                    "max_message_length": defaults['max_message_length'],
                    "llama_server_gpu_layers": defaults['llama_server_gpu_layers'],
                    "temperature": defaults['temperature']
                },
                "tools": {
                    "enabled_tools": self.profile.get("tools", {}).get("enabled_tools", {}),  # Preserve tool selections
                    "confirmation_policy": {
                        "default_minimum_risk_to_confirm": "high" if defaults['confirm_high_risk_tools'] else "none"
                    },
                    "timeouts_sec": {"default": defaults['tool_timeout']},
                    "logging": {"tool_calls": defaults['log_tool_execution']}
                },
                "orchestrator": self.profile.get("orchestrator", {}),
                "notes": ""
            }

            # Save and reload
            save_tool_profile(profile_name, self.profile)
            self.reload_settings()

            log_message(f"CC_SETTINGS: Profile '{profile_name}' reset to defaults")
            messagebox.showinfo("Reset Complete", f"Profile '{profile_name}' has been reset to defaults")

    def on_profile_changed(self, event=None):
        """Handle profile selection change"""
        new_profile = self.current_profile_name.get()
        log_message(f"CC_SETTINGS: Switching to profile '{new_profile}'")

        # Reload from new profile
        self.profile = self.load_profile()
        self.reload_settings()

        # Update status label
        self.profile_status_label.config(text=f"Profile: {new_profile}")

    def create_profile(self):
        """Create a new profile by cloning current or from defaults"""
        # Simple dialog to get new profile name
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
                new_profile = self.profile.copy()
                new_profile["profile_name"] = new_name
                new_profile["created_at"] = datetime.utcnow().isoformat() + "Z"
                new_profile["updated_at"] = datetime.utcnow().isoformat() + "Z"

                save_tool_profile(new_name, new_profile)

                # Update combo and switch to new profile
                self.profile_combo['values'] = list_tool_profiles()
                self.current_profile_name.set(new_name)
                self.on_profile_changed()

                log_message(f"CC_SETTINGS: Created new profile '{new_name}'")
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

        # Simple dialog to get new name
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

                log_message(f"CC_SETTINGS: Renamed profile '{current_name}' → '{new_name}'")
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

                log_message(f"CC_SETTINGS: Deleted profile '{current_name}' (backed up to {backup_path.name})")
                messagebox.showinfo("Profile Deleted", f"Profile '{current_name}' deleted (backup: {backup_path.name})")

        except Exception as e:
            messagebox.showerror("Delete Error", f"Failed to delete profile: {e}")

    def refresh(self):
        """Refresh the settings tab"""
        log_message("CC_SETTINGS: Refreshing...")
        self.reload_settings()
