# [SYSTEM: GUI | VERSION: 1.9f | STATUS: ACTIVE]
"""
Models Tab - Model information, notes, and statistics
Isolated module for models-related functionality
"""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from pathlib import Path
from typing import Optional
import subprocess
import shutil
import venv

import sys
import os
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from evaluation_engine import EvaluationEngine
import threading
import json

from tabs.base_tab import BaseTab
from tabs.models_tab.method_bank_tab import MethodBankTab
from tabs.custom_code_tab.chat_history_manager import ChatHistoryManager
from evaluation_engine import EvaluationEngine
from config import (
    get_ollama_models,
    get_ollama_model_info,
    parse_ollama_model_info,
    save_model_note,
    load_model_note,
    list_model_notes,
    load_training_stats,
    get_latest_training_stats,
    get_all_trained_models,
    delete_trained_model,
    get_model_skills,
    save_evaluation_report,
    get_test_suites,
    list_system_prompts,
    load_system_prompt,
    list_tool_schemas,
    load_tool_schema,
    save_baseline_report,
    load_baseline_report,
    load_latest_evaluation_report,
    get_all_trained_models,
    get_regression_policy,
    load_baseline_report,
    MODELS_DIR,
    TRAINING_DATA_DIR)
from logger_util import get_tab_logger

log_message, log_error, log_exception = get_tab_logger('models')


class ModelsTab(BaseTab):
    """Models information, notes, and statistics tab"""

    def __init__(self, parent, root, style):
        super().__init__(parent, root, style)

        # Get available models (all types)
        self.all_models = get_all_trained_models()
        self.ollama_models = get_ollama_models()  # Keep for backward compatibility

        # State variables
        self.current_model_for_stats = None
        self.current_model_info = None  # Store full model info dict
        self.tab_instances = getattr(self, 'tab_instances', None)
        self.trainee_name_var = tk.StringVar()
        self.base_model_var = tk.StringVar()
        # Adapters selection state
        self.adapters_select_mode = tk.BooleanVar(value=False)
        self.adapters_selection = {}  # path(str) -> BooleanVar
        self.adapters_estimate_btn = None
        self.adapters_levelup_btn = None
        
        # Levels expand/collapse state in model list
        self.levels_expanded = {}
        self.levels_ui = {}

        # Register for profile update notifications
        try:
            import config as C
            C.register_profile_update_callback(self._on_profile_updated)
        except Exception:
            pass

    def _on_profile_updated(self, variant_name: str):
        """Callback when a model profile is updated."""
        # Only refresh if the updated variant is currently displayed
        if self.current_model_for_stats == variant_name:
            # Schedule refresh on main thread
            try:
                self.root.after(100, self._refresh_current_model_display)
            except Exception:
                pass

    def _refresh_current_model_display(self):
        """Refresh the currently displayed model's statistics."""
        if self.current_model_for_stats:
            # Refresh stats display
            self.populate_stats_display()

    def create_ui(self):
        """Create the models tab UI"""
        parent = self.parent
        parent.columnconfigure(0, weight=1) # Model Info column
        parent.columnconfigure(1, weight=0) # Model List column
        parent.rowconfigure(0, weight=1)

        # Left side: Model Information Display
        model_info_frame = ttk.Frame(parent, style='Category.TFrame')
        model_info_frame.grid(row=0, column=0, sticky=tk.NSEW, padx=10, pady=10)
        model_info_frame.columnconfigure(0, weight=1)
        model_info_frame.rowconfigure(1, weight=1)

        # Header with title and refresh button
        header_frame = ttk.Frame(model_info_frame, style='Category.TFrame')
        header_frame.pack(fill=tk.X, pady=5)

        ttk.Label(header_frame, text="🧠 Model Information", font=("Arial", 14, "bold"), style='CategoryPanel.TLabel').pack(side=tk.LEFT, padx=(0, 10))

        ttk.Button(header_frame, text="🔄 Refresh",
                  command=self.refresh_models_tab,
                  style='Select.TButton').pack(side=tk.RIGHT, padx=5)
        
        self.model_info_notebook = ttk.Notebook(model_info_frame)
        self.model_info_notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Overview Tab (scrollable)
        self.overview_tab_outer = ttk.Frame(self.model_info_notebook)
        self.model_info_notebook.add(self.overview_tab_outer, text="Overview")

        # Create canvas and scrollbar for Overview tab
        self.overview_canvas = tk.Canvas(self.overview_tab_outer, bg="#2b2b2b", highlightthickness=0)
        self.overview_scrollbar = ttk.Scrollbar(self.overview_tab_outer, orient="vertical", command=self.overview_canvas.yview)
        self.overview_tab_frame = ttk.Frame(self.overview_canvas, style='Category.TFrame')

        # Configure canvas
        self.overview_tab_frame.bind(
            "<Configure>",
            lambda e: self.overview_canvas.configure(scrollregion=self.overview_canvas.bbox("all"))
        )
        self.overview_canvas.create_window((0, 0), window=self.overview_tab_frame, anchor="nw")
        self.overview_canvas.configure(yscrollcommand=self.overview_scrollbar.set)

        # Pack canvas and scrollbar
        self.overview_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.overview_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Mouse wheel scrolling on hover
        def _on_mousewheel(event):
            self.overview_canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        def _bind_mousewheel(event):
            self.overview_canvas.bind_all("<MouseWheel>", _on_mousewheel)
        def _unbind_mousewheel(event):
            self.overview_canvas.unbind_all("<MouseWheel>")
        self.overview_canvas.bind("<Enter>", _bind_mousewheel)
        self.overview_canvas.bind("<Leave>", _unbind_mousewheel)

        # WO-6z: Active Variant indicator (top of Overview)
        try:
            self.active_variant_var = tk.StringVar(value="")
            banner = ttk.Label(self.overview_tab_frame, textvariable=self.active_variant_var, style='Config.TLabel', foreground='#ffd43b')
            banner.pack(anchor=tk.W, padx=6, pady=4)
        except Exception:
            pass
        # Labels for parsed info will be created dynamically in display_model_info

        # --- Types Tab (must be visible next to Overview) ---
        try:
            from tabs.models_tab.types_panel import TypesPanel
            self.types_tab_frame = ttk.Frame(self.model_info_notebook)
            self.model_info_notebook.add(self.types_tab_frame, text="Types")

            # Shared state already created earlier:
            #   self.trainee_name_var, self.base_model_var
            self.panel_types = TypesPanel(
                self.types_tab_frame,
                trainee_name_var=self.trainee_name_var,
                base_model_var=self.base_model_var,
            )
            log_message("[DEBUG] ModelsTab: TypesPanel instantiated")
            self.panel_types.set_context_getters(
                get_trainee=lambda: getattr(self, "current_model_for_stats", None),
                get_base_model=lambda: getattr(self, "current_model_info", {}).get("name")
            )
            log_message("[DEBUG] ModelsTab: set_context_getters called")
            # If TypesPanel packs itself, do nothing; otherwise:
            try:
                if hasattr(self.panel_types, "pack"):
                    log_message("[DEBUG] ModelsTab: Packing TypesPanel")
                    self.panel_types.pack(fill=tk.BOTH, expand=True, padx=10, pady=10) # Changed tk.X to tk.BOTH and added expand=True
            except Exception as e:
                log_message(f"[DEBUG] ModelsTab: Error packing TypesPanel: {e}")

            # Bind the event bridge (safe even if Training tab misses apply_plan)
            try:
                self.panel_types.bind("<<TypePlanApplied>>", self._on_type_plan_applied)
            except Exception:
                pass
            # WO-6p/6x: Listen for global profile/variant events
            try:
                self.bind("<<VariantApplied>>", self._on_variant_applied)
                self.bind("<<ProfilesChanged>>", lambda _e: self.refresh_collections_panel())
                # Phase 1.2: Listen for training/conversation events to auto-refresh skills
                self.bind("<<ConversationSaved>>", self._on_conversation_saved)
                self.bind("<<TrainingModeChanged>>", self._on_training_activity)
            except Exception:
                pass
        except Exception as _e:
            # Keep UI resilient if TypesPanel import fails
            log_message("[ModelsTab] TypesPanel unavailable:", _e)

        # Adapters Tab (New)
        self.adapters_tab_frame = ttk.Frame(self.model_info_notebook)
        self.model_info_notebook.add(self.adapters_tab_frame, text="🎯 Adapters")

        # Visualization Tab (System Map)
        self.viz_tab_frame = ttk.Frame(self.model_info_notebook)
        self.model_info_notebook.add(self.viz_tab_frame, text="🧠 Visualization")
        self._create_visualization_tab(self.viz_tab_frame)

        # Training History Tab (New)
        self.history_tab_frame = ttk.Frame(self.model_info_notebook)
        self.model_info_notebook.add(self.history_tab_frame, text="📈 History")
        # Sub-tabs inside History: Runs and Levels
        self.history_notebook = ttk.Notebook(self.history_tab_frame)
        self.history_notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.history_runs_frame = ttk.Frame(self.history_notebook)
        self.history_levels_frame = ttk.Frame(self.history_notebook)
        self.history_notebook.add(self.history_runs_frame, text="Runs")
        self.history_notebook.add(self.history_levels_frame, text="Levels")
        # Chats sub-tab (RAG link tree)
        self.history_chats_frame = ttk.Frame(self.history_notebook)
        self.history_notebook.add(self.history_chats_frame, text="Chats")
        # Events sub-tab (variant lifecycle events)
        self.history_events_frame = ttk.Frame(self.history_notebook)
        self.history_notebook.add(self.history_events_frame, text="Events")
        self._history_chat_vars = {}
        self._history_chat_mgr = None
        self._history_chat_mgr_error = None
        try:
            log_message("[ModelsTab] Initializing ChatHistoryManager...")
            self._history_chat_mgr = ChatHistoryManager()
            log_message(f"[ModelsTab] ✓ ChatHistoryManager initialized: {self._history_chat_mgr.history_dir}")
        except Exception as e:
            self._history_chat_mgr_error = str(e)
            log_message(f"[ModelsTab] ✗ ChatHistoryManager initialization failed: {e}")
            import traceback
            traceback.print_exc()

        # Show initial placeholder in Chats tab
        self._show_history_chats_placeholder()

        # Raw Info Tab
        self.raw_info_tab_frame = ttk.Frame(self.model_info_notebook)
        self.model_info_notebook.add(self.raw_info_tab_frame, text="Raw Info")
        self.raw_model_info_text = scrolledtext.ScrolledText(
            self.raw_info_tab_frame,
            width=60,
            height=20,
            font=("Courier", 10),
            wrap=tk.WORD,
            state=tk.DISABLED,
            relief='flat',
            borderwidth=0,
            highlightthickness=0
        )
        self.raw_model_info_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Method Bank Tab
        self.method_bank_frame = MethodBankTab(self.model_info_notebook, self.root)
        self.model_info_notebook.add(self.method_bank_frame, text="Method Bank")
        self.raw_model_info_text.config(background='#1e1e1e', foreground='#61dafb') # Fallback styling

        # Notes Tab
        self.notes_tab_frame = ttk.Frame(self.model_info_notebook)
        self.model_info_notebook.add(self.notes_tab_frame, text="Notes")
        self.create_notes_panel(self.notes_tab_frame)

        # Stats Tab
        self.stats_tab_frame = ttk.Frame(self.model_info_notebook)
        self.model_info_notebook.add(self.stats_tab_frame, text="Stats")
        self.create_stats_panel(self.stats_tab_frame)

        # Collections Tab
        self.collections_tab_frame = ttk.Frame(self.model_info_notebook)
        self.model_info_notebook.add(self.collections_tab_frame, text="📦 Collections")
        self.create_collections_panel(self.collections_tab_frame)

        # Class Tab (progression tree)
        self.class_tab_outer = ttk.Frame(self.model_info_notebook)
        self.model_info_notebook.add(self.class_tab_outer, text="🎓 Class")
        self.create_class_tree_panel(self.class_tab_outer)

        # Skills Tab
        self.skills_tab_frame = ttk.Frame(self.model_info_notebook)
        self.model_info_notebook.add(self.skills_tab_frame, text="Skills")
        self.create_skills_panel(self.skills_tab_frame)

        # Evaluation Tab
        self.evaluation_tab_frame = ttk.Frame(self.model_info_notebook)
        self.model_info_notebook.add(self.evaluation_tab_frame, text="🧪 Evaluation")
        self.create_evaluation_panel(self.evaluation_tab_frame)

        # Baselines Tab
        self.baselines_tab_frame = ttk.Frame(self.model_info_notebook)
        self.model_info_notebook.add(self.baselines_tab_frame, text="Baselines")
        self.create_baselines_panel(self.baselines_tab_frame)

        # Compare Tab
        self.compare_tab_frame = ttk.Frame(self.model_info_notebook)
        self.model_info_notebook.add(self.compare_tab_frame, text="Compare")
        self.create_compare_panel(self.compare_tab_frame)

        # Find Models Tab (New - HuggingFace model search and download)
        self.find_models_tab_frame = ttk.Frame(self.model_info_notebook)
        self.model_info_notebook.add(self.find_models_tab_frame, text="🔍 Find Models")
        self.create_find_models_panel(self.find_models_tab_frame)

        # Right side: Unified scroll container with a draggable resizer gutter
        # Insert a thin resizer between left (col 0) and right pane
        self._resizer = ttk.Frame(parent, width=6, cursor='sb_h_double_arrow', style='Category.TFrame')
        self._resizer.grid(row=0, column=1, sticky=tk.NS)
        # Canvas and scrollbar for right pane move to columns 2 and 3
        self.right_canvas = tk.Canvas(parent, bg="#2b2b2b", highlightthickness=0)
        self.right_scrollbar = ttk.Scrollbar(parent, orient="vertical", command=self.right_canvas.yview)
        self.right_frame = ttk.Frame(self.right_canvas, style='Category.TFrame')
        self.right_canvas_window_id = self.right_canvas.create_window((0, 0), window=self.right_frame, anchor="nw")
        self.right_canvas.configure(yscrollcommand=self.right_scrollbar.set)
        self.right_pane_width = 360
        try:
            self.right_canvas.config(width=self.right_pane_width)
        except Exception:
            pass
        self.right_canvas.grid(row=0, column=2, sticky=tk.NSEW, padx=(6,10), pady=10)
        self.right_scrollbar.grid(row=0, column=3, sticky=tk.NS, pady=10)
        self.right_canvas.bind("<Configure>", lambda e: self.right_canvas.itemconfig(self.right_canvas_window_id, width=e.width))
        self.right_frame.bind("<Configure>", lambda e: self.right_canvas.configure(scrollregion=self.right_canvas.bbox("all")))
        # Resizer drag behavior
        self._resizer.bind("<ButtonPress-1>", self._on_resizer_press)
        self._resizer.bind("<B1-Motion>", self._on_resizer_drag)

        # Inside the unified right column, we keep existing sections
        model_list_frame = ttk.Frame(self.right_frame, style='Category.TFrame')
        model_list_frame.grid(row=0, column=0, sticky=tk.NSEW)
        model_list_frame.columnconfigure(0, weight=1)
        model_list_frame.rowconfigure(1, weight=1) # For Base/Levels/Trained canvas
        model_list_frame.rowconfigure(3, weight=1) # For Ollama canvas

        ttk.Label(model_list_frame, text="Available Models", font=("Arial", 12, "bold"), style='CategoryPanel.TLabel').grid(row=0, column=0, pady=5, sticky=tk.W)

        # Base/Levels/Trained section (no inner scrollbar; outer right pane scrolls)
        self.base_buttons_frame = ttk.Frame(model_list_frame)
        self.base_buttons_frame.grid(row=1, column=0, sticky=tk.NSEW)

        # Ollama header
        ttk.Label(model_list_frame, text="🟡 Assigned Models (GGUF + Local)", font=("Arial", 12, "bold"), style='CategoryPanel.TLabel').grid(row=2, column=0, pady=(10,5), sticky=tk.W)

        # Ollama section (no inner scrollbar; outer right pane scrolls)
        self.ollama_buttons_frame = ttk.Frame(model_list_frame)
        self.ollama_buttons_frame.grid(row=3, column=0, sticky=tk.NSEW)

        # --- WO-6b: Collections panel ---------------------------------------
        collections_section_frame = ttk.Frame(model_list_frame, style='Category.TFrame')
        collections_section_frame.grid(row=4, column=0, sticky=tk.NSEW, pady=(10,5))
        collections_section_frame.columnconfigure(0, weight=1)
        # Reserve rows: 0=header, 1=toggle, 2=canvas
        collections_section_frame.rowconfigure(2, weight=1) # For Collections canvas within this section

        # Header for Collections (now within collections_section_frame)
        ttk.Label(collections_section_frame, text="📚 Collections", font=("Arial", 12, "bold"), style='CategoryPanel.TLabel').grid(row=0, column=0, sticky=tk.W)

        # Toggle button for Collections (now within collections_section_frame)
        collections_toggle_frame = ttk.Frame(collections_section_frame)
        collections_toggle_frame.grid(row=1, column=0, sticky=tk.EW, padx=5)
        collections_toggle_frame.columnconfigure(0, weight=1)

        self.collections_expanded = tk.BooleanVar(value=False) # Default to collapsed
        self.collections_toggle_btn = ttk.Button(collections_toggle_frame, text="▶", width=2, style='Select.TButton', command=self._toggle_collections_group)
        self.collections_toggle_btn.pack(side=tk.LEFT, padx=(0,5))
        ttk.Label(collections_toggle_frame, text="Type Assigned Models", style='Config.TLabel').pack(side=tk.LEFT) # Placeholder for now

        # (Filter UI removed by request)

        # Collections canvas (now within collections_section_frame)
        self.collections_canvas = tk.Canvas(collections_section_frame, bg="#2b2b2b", highlightthickness=0)
        self.collections_scrollbar = ttk.Scrollbar(collections_section_frame, orient="vertical", command=self.collections_canvas.yview)
        self.collections_buttons_frame = ttk.Frame(self.collections_canvas)
        self.collections_buttons_frame.bind("<Configure>", lambda e: self.collections_canvas.configure(scrollregion=self.collections_canvas.bbox("all")))
        self.collections_canvas_window_id = self.collections_canvas.create_window((0, 0), window=self.collections_buttons_frame, anchor="nw")
        self.collections_canvas.configure(yscrollcommand=self.collections_scrollbar.set)
        # Conditional initial grid for canvas (row 2)
        if self.collections_expanded.get(): # This is False initially
            self.collections_canvas.grid(row=2, column=0, sticky=tk.NSEW)
            self.collections_scrollbar.grid(row=2, column=1, sticky=tk.NS)
        self.collections_canvas.bind("<Configure>", lambda e: self.collections_canvas.itemconfig(self.collections_canvas_window_id, width=e.width))

        # --------------------------------------------------------------------

        # Bind mousewheel to the unified right scroll on hover only
        try:
            self.bind_mousewheel_to_canvas(self.right_canvas)
        except Exception:
            pass

        # Expanded state for Ollama groups
        self.ollama_expanded = {}
        self.ollama_ui = {}

        self.populate_model_list()
        # Ensure default collapsed layout on launch
        if bool(self.collections_expanded.get()):
            self._toggle_collections_group()
        try:
            from logger_util import log_message as dbg
            dbg("COLLECTIONS_TRIGGER: Initial refresh_collections_panel from __init__")
        except Exception:
            pass
        self.refresh_collections_panel() # Call after UI is built
        # Bind auto-export event from Custom Code
        try:
            self.root.bind("<<RequestAutoExportReEval>>", self._on_request_auto_export_reeval)
        except Exception:
            pass

        # If a variant is already active on load, populate History → Chats
        try:
            vid = getattr(self, '_active_variant_id', '') or ''
            if vid:
                self._populate_history_chats(vid)
        except Exception:
            pass

    def refresh_models_tab(self):
        """Refresh the models tab - reloads all models and updates display."""
        # Refresh model lists
        self.all_models = get_all_trained_models()
        self.ollama_models = get_ollama_models()

        # Refresh the model list display
        self.populate_model_list()

        # Refresh current model display if one is selected
        if self.current_model_info:
            # Find the current model in the refreshed list
            for model in self.all_models:
                if model['name'] == self.current_model_info['name']:
                    self.display_model_info_from_dict(model)
                    break

        log_message("✓ Models tab refreshed")

    def _on_type_plan_applied(self, event=None):
        import json
        variant_id = None
        base_model = None
        type_id = None

        # tk>=8.6 can surface event.data; else we set .details above
        if event is not None:
            try:
                if hasattr(event, "data") and event.data:
                    d = json.loads(event.data)
                    variant_id = d.get("variant_id")
                    base_model = d.get("base_model")
                    type_id = d.get("type_id")
            except Exception:
                pass
            if not variant_id and hasattr(event, "details"):
                d = getattr(event, "details", {}) or {}
                variant_id = d.get("variant_id")
                base_model = d.get("base_model")
                type_id = d.get("type_id")

        if not variant_id:
            log_message("[ModelsTab] TypePlanApplied missing variant_id; ignoring.")
            return

        # Relay to TrainingTab on the UI thread
        try:
            tt = self.get_training_tab()
            if tt and hasattr(tt, "apply_plan"):
                self.root.after(50, lambda: tt.apply_plan(variant_id=variant_id))
                log_message(f"[ModelsTab] Relayed TypePlan to TrainingTab (variant={variant_id}).")
            else:
                log_message("[ModelsTab] TrainingTab.apply_plan not found.")
        except Exception as e:
            log_message("[ModelsTab] Error relaying TypePlan:", e)

    def populate_model_list(self):
        """Populates the scrollable frame with buttons for each model (all types)."""
        # Clear existing buttons
        for widget in self.base_buttons_frame.winfo_children():
            widget.destroy()
        for widget in self.ollama_buttons_frame.winfo_children():
            widget.destroy()

        # Refresh model list
        self.all_models = get_all_trained_models()

        if not self.all_models:
            ttk.Label(self.base_buttons_frame, text="No models found.", style='Config.TLabel').pack(pady=10)
            return

        # Group models by type
        pytorch_models = [m for m in self.all_models if m["type"] == "pytorch"]
        trained_models = [m for m in self.all_models if m["type"] == "trained"]
        ollama_models = [m for m in self.all_models if m["type"] == "ollama"]

        # Display PyTorch models (base models) - Trainable
        if pytorch_models:
            ttk.Label(self.base_buttons_frame, text="🔵 Base Models (PyTorch)",
                     font=("Arial", 10, "bold"), foreground='#61dafb').pack(anchor=tk.W, padx=5, pady=(10, 5))

            for model_info in pytorch_models:
                # Row frame for arrow + base model button
                row = ttk.Frame(self.base_buttons_frame)
                row.pack(fill=tk.X, padx=5, pady=2)
                base_name = model_info['name']
                self.levels_expanded[base_name] = self.levels_expanded.get(base_name, False)

                # Arrow button (integrated left of base model button)
                arrow_btn = ttk.Button(row, text=('▼' if self.levels_expanded[base_name] else '▶'), width=2,
                                       command=lambda b=base_name: self._toggle_levels(b), style='Select.TButton')
                arrow_btn.pack(side=tk.LEFT, padx=(0,5))

                # Base model button
                icon = "📦"
                size_text = f" • {model_info['size']}" if model_info.get("size") else ""
                btn_text = f"{icon} {base_name}{size_text} • trainable"
                ttk.Button(row, text=btn_text, command=lambda m=model_info: self.display_model_info_from_dict(m), style='Select.TButton').pack(side=tk.LEFT, fill=tk.X, expand=True)

                # Levels container (created but only packed when expanded)
                container = ttk.Frame(self.base_buttons_frame)
                # Populate level buttons
                levels = []
                try:
                    levels = self._discover_levels_for_base(base_name)
                except Exception:
                    levels = []
                # Clear previous UI record
                self.levels_ui[base_name] = { 'arrow': arrow_btn, 'container': container }
                if levels:
                    for level in sorted(levels, key=lambda d: d.get('created',''), reverse=True):
                        ttk.Button(container, text=f"   • {level.get('name','(unnamed)')}",
                                   command=lambda b=base_name, lv=level: self.display_level_info(b, lv),
                                   style='Select.TButton').pack(fill=tk.X, padx=25, pady=1)
                # Show container only if expanded
                if self.levels_expanded[base_name] and levels:
                    container.pack(fill=tk.X)

        # Populate Assigned Models strictly from unified registry; Unassigned from Ollama list
        if ollama_models:
            # Assigned (unified)
            key = 'Assigned'
            self.ollama_expanded[key] = self.ollama_expanded.get(key, False)
            assigned_section = ttk.Frame(self.ollama_buttons_frame)
            assigned_section.pack(fill=tk.X)
            row = ttk.Frame(assigned_section)
            row.pack(fill=tk.X, padx=5, pady=2)
            arrow_btn = ttk.Button(row, text=('▼' if self.ollama_expanded[key] else '▶'), width=2,
                                   command=lambda b=key: self._toggle_ollama_group(b), style='Select.TButton')
            arrow_btn.pack(side=tk.LEFT, padx=(0,5))
            ttk.Label(row, text='Assigned', style='Config.TLabel', foreground='#51cf66').pack(side=tk.LEFT)
            cont = ttk.Frame(assigned_section)
            self.ollama_ui[key] = { 'arrow': arrow_btn, 'container': cont, 'section': assigned_section }
            try:
                from config import load_unified_assignments, get_active_artifact
                uni = load_unified_assignments() or {}
                # Support both flat {variant_id: {...}} and nested {variants: {variant_id: {...}}}
                variants_map = uni.get('variants') or uni  # flat structure uses uni directly
                # Render each variant's artifacts
                for vid in sorted(variants_map.keys()):
                    v = variants_map.get(vid) or {}
                    arts = v.get('artifacts') or []
                    active = get_active_artifact(vid) or {}
                    for a in arts:
                        backend = (a.get('backend') or '').lower()
                        is_tag = (backend == 'ollama') and (a.get('kind') == 'tag') and a.get('id')
                        is_local = (backend == 'llama_server') and (a.get('gguf') is not None)
                        if not (is_tag or is_local):
                            continue
                        rowf = ttk.Frame(cont)
                        rowf.pack(fill=tk.X, padx=10, pady=1)
                        # Color chip by variant
                        try:
                            color = self._get_variant_color_for_gguf(vid) or '#51cf66'
                        except Exception:
                            color = '#51cf66'
                        try:
                            chip = tk.Label(rowf, text='  ', bg=color)
                            chip.pack(side=tk.LEFT, padx=(15,6), pady=2)
                        except Exception:
                            pass
                        if is_tag:
                            tag = a.get('id')
                            is_active = (active.get('backend') == 'ollama' and active.get('id') == tag)
                            label = f"{'✅ ' if is_active else ''}🔶 {tag} • tag"
                            ttk.Button(rowf, text=label,
                                       command=lambda t=tag, v=vid: self._select_ollama_tag(v, t),
                                       style='Select.TButton').pack(side=tk.LEFT, fill=tk.X, expand=True)
                            if not is_active:
                                ttk.Button(rowf, text='Set Active', style='Action.TButton',
                                           command=lambda v=vid, t=tag: self._set_active_tag(v, t)).pack(side=tk.LEFT, padx=6)
                            # Minimal capability chips for Ollama
                            try:
                                ttk.Label(rowf, text='🔧', style='Config.TLabel').pack(side=tk.LEFT, padx=2)
                                ttk.Label(rowf, text='📡', style='Config.TLabel').pack(side=tk.LEFT, padx=2)
                                ttk.Label(rowf, text='📄', style='Config.TLabel').pack(side=tk.LEFT, padx=2)
                            except Exception:
                                pass
                        else:
                            p = str(a.get('gguf'))
                            is_active = (active.get('backend') == 'llama_server' and active.get('id') == p)
                            label = f"{'✅ ' if is_active else ''}🟩 {Path(p).name} • local"
                            ttk.Button(rowf, text=label,
                                       command=lambda gp=p: self.display_local_gguf(gp),
                                       style='Select.TButton').pack(side=tk.LEFT, fill=tk.X, expand=True)
                            if not is_active:
                                ttk.Button(rowf, text='Set Active', style='Action.TButton',
                                           command=lambda v=vid, gp=p: self._set_active_local(v, gp)).pack(side=tk.LEFT, padx=6)
                            # Minimal capability chips for local gguf via llama_server
                            try:
                                ttk.Label(rowf, text='⚡', style='Config.TLabel').pack(side=tk.LEFT, padx=2)
                                ttk.Label(rowf, text='🔧', style='Config.TLabel').pack(side=tk.LEFT, padx=2)
                                ttk.Label(rowf, text='📡', style='Config.TLabel').pack(side=tk.LEFT, padx=2)
                                ttk.Label(rowf, text='📄', style='Config.TLabel').pack(side=tk.LEFT, padx=2)
                            except Exception:
                                pass
            except Exception:
                pass
            if self.ollama_expanded[key]:
                cont.pack(fill=tk.X)

            # Unassigned (Ollama list minus assigned tags)
            key2 = 'Unassigned'
            self.ollama_expanded[key2] = self.ollama_expanded.get(key2, False)
            unassigned_section = ttk.Frame(self.ollama_buttons_frame)
            unassigned_section.pack(fill=tk.X)
            row2 = ttk.Frame(unassigned_section)
            row2.pack(fill=tk.X, padx=5, pady=2)
            arrow_btn2 = ttk.Button(row2, text=('▼' if self.ollama_expanded[key2] else '▶'), width=2,
                                    command=lambda b=key2: self._toggle_ollama_group(b), style='Select.TButton')
            arrow_btn2.pack(side=tk.LEFT, padx=(0,5))
            ttk.Label(row2, text='Unassigned', style='Config.TLabel', foreground='#61dafb').pack(side=tk.LEFT)
            cont2 = ttk.Frame(unassigned_section)
            self.ollama_ui[key2] = { 'arrow': arrow_btn2, 'container': cont2, 'section': unassigned_section }
            try:
                from config import load_unified_assignments
                uni = load_unified_assignments() or {}
                assigned_tags = set()
                # Support both flat and nested structure
                variants_map = uni.get('variants') or uni
                for v in variants_map.values():
                    for a in (v.get('artifacts') or []):
                        if (a.get('backend') == 'ollama') and (a.get('kind') == 'tag') and a.get('id'):
                            assigned_tags.add(a.get('id'))
            except Exception:
                assigned_tags = set()
            all_names = [m['name'] if isinstance(m, dict) else m for m in ollama_models]
            unassigned_names = [n for n in all_names if n not in assigned_tags]
            for n in sorted(unassigned_names):
                ttk.Button(cont2, text=f"   🔶 {n} • inference-only",
                           command=lambda name=n: self._select_ollama_tag('(unassigned)', name),
                           style='Select.TButton').pack(fill=tk.X, padx=25, pady=1)
            if self.ollama_expanded[key2] and unassigned_names:
                cont2.pack(fill=tk.X)

        # (Local GGUF section no longer needed separately; unified under Assigned)

    def display_local_gguf(self, gguf_path: str):
        """Display minimal info for a local GGUF and set evaluation context."""
        try:
            # Clear variant context
            self._active_variant_id = ''
            if hasattr(self, 'active_variant_var'):
                self.active_variant_var.set('')
        except Exception:
            pass
        # Raw Info Tab
        try:
            self.raw_model_info_text.config(state=tk.NORMAL)
            self.raw_model_info_text.delete(1.0, tk.END)
            self.raw_model_info_text.insert(1.0, f"Local GGUF:\n{gguf_path}")
            self.raw_model_info_text.config(state=tk.DISABLED)
        except Exception:
            pass
        # Overview basics
        for widget in self.overview_tab_frame.winfo_children():
            widget.destroy()
        pane = ttk.LabelFrame(self.overview_tab_frame, text="Local GGUF", style='TLabelframe')
        pane.grid(row=0, column=0, sticky=tk.EW, padx=5, pady=10)
        ttk.Label(pane, text=str(gguf_path), style='Config.TLabel').grid(row=0, column=0, sticky=tk.W, padx=8, pady=6)
        # Evaluation context
        try:
            self._eval_override_model_name = gguf_path
            if hasattr(self, 'selected_model_label_eval'):
                self.selected_model_label_eval.config(text=f"Selected Model: {Path(gguf_path).name}")
            if hasattr(self, 'eval_source_label'):
                self.eval_source_label.config(text="Source: Local GGUF")
            # Fire a ModelSelected event so other panels (e.g., Chat) can react
            try:
                import json as _json
                payload = _json.dumps({
                    "model_name": Path(gguf_path).name,
                    "model_type": "local_gguf",
                    "is_local_gguf": True,
                    "path": str(gguf_path)
                })
                if hasattr(self, 'panel_types') and self.panel_types:
                    self.panel_types.event_generate("<<ModelSelected>>", data=payload, when="tail")
            except Exception:
                pass
        except Exception:
            pass

    def _set_active_local(self, variant_id: str, gguf_path: str):
        try:
            from config import set_active_assignment
            set_active_assignment(variant_id, 'llama_server', gguf_path)
            self.populate_model_list()
            try:
                self.add_message_to_overview = getattr(self, 'add_message_to_overview', None)
            except Exception:
                pass
        except Exception as e:
            try:
                messagebox.showerror('Active Artifact', f'Failed to set active: {e}')
            except Exception:
                pass

    def _set_active_tag(self, variant_id: str, tag: str):
        try:
            from config import set_active_assignment
            set_active_assignment(variant_id, 'ollama', tag)
            self.populate_model_list()
        except Exception as e:
            try:
                messagebox.showerror('Active Artifact', f'Failed to set active: {e}')
            except Exception:
                pass

    def _select_ollama_tag(self, variant_id: str, tag: str):
        """Select an Ollama tag in the UI and notify other panels (Chat)."""
        try:
            # Update Evaluation panel selection label context
            if hasattr(self, 'selected_model_label_eval'):
                if variant_id and variant_id != '(unassigned)':
                    self.selected_model_label_eval.config(text=f"Selected Model: {variant_id} → tag:{tag}")
                else:
                    self.selected_model_label_eval.config(text=f"Selected Model: {tag}")
        except Exception:
            pass
        # Fire ModelSelected event for Chat to switch backend/model
        try:
            import json as _json
            payload = _json.dumps({
                'backend': 'ollama',
                'kind': 'tag',
                'id': tag
            })
            try:
                self.event_generate('<<ModelSelected>>', data=payload, when='tail')
            except Exception:
                # Fallback for panel nesting: relay through Types panel if present
                if hasattr(self, 'panel_types'):
                    self.panel_types.event_generate('<<ModelSelected>>', data=payload, when='tail')
        except Exception:
            pass

    def create_notes_panel(self, parent):
        """Create the notes panel for model-specific notes."""
        parent.columnconfigure(0, weight=3)  # Editor column
        parent.columnconfigure(1, weight=1)  # Notes list column
        parent.rowconfigure(1, weight=1)

        # Top controls
        controls_frame = ttk.Frame(parent)
        controls_frame.grid(row=0, column=0, sticky=tk.EW, padx=5, pady=5)

        ttk.Label(controls_frame, text="Note Name:", style='Config.TLabel').pack(side=tk.LEFT, padx=5)

        self.note_name_var = tk.StringVar()
        note_name_entry = ttk.Entry(controls_frame, textvariable=self.note_name_var, width=30)
        note_name_entry.pack(side=tk.LEFT, padx=5)

        ttk.Button(controls_frame, text="💾 Save", command=self.save_note, style='Action.TButton').pack(side=tk.LEFT, padx=2)
        ttk.Button(controls_frame, text="🗑️ Delete", command=self.delete_note, style='Action.TButton').pack(side=tk.LEFT, padx=2)

        # Notes text area (left side)
        self.notes_text = scrolledtext.ScrolledText(
            parent,
            width=60,
            height=20,
            font=("Arial", 10),
            wrap=tk.WORD,
            relief='flat',
            borderwidth=0,
            highlightthickness=0
        )
        self.notes_text.grid(row=1, column=0, sticky=tk.NSEW, padx=5, pady=5)
        self.notes_text.config(background='#1e1e1e', foreground='#ffffff', insertbackground='#61dafb')

        # Notes list panel (right side)
        notes_list_frame = ttk.Frame(parent, style='Category.TFrame')
        notes_list_frame.grid(row=0, column=1, rowspan=2, sticky=tk.NSEW, padx=5, pady=5)
        notes_list_frame.columnconfigure(0, weight=1)
        notes_list_frame.rowconfigure(1, weight=1)

        ttk.Label(notes_list_frame, text="📝 Saved Notes", font=("Arial", 11, "bold"), style='CategoryPanel.TLabel').grid(row=0, column=0, pady=5, sticky=tk.W, padx=5)

        # Scrollable list of notes
        notes_list_canvas = tk.Canvas(notes_list_frame, bg="#2b2b2b", highlightthickness=0)
        notes_list_scrollbar = ttk.Scrollbar(notes_list_frame, orient="vertical", command=notes_list_canvas.yview)
        self.notes_list_buttons_frame = ttk.Frame(notes_list_canvas)

        self.notes_list_buttons_frame.bind(
            "<Configure>",
            lambda e: notes_list_canvas.configure(scrollregion=notes_list_canvas.bbox("all"))
        )

        self.notes_list_canvas_window_id = notes_list_canvas.create_window((0, 0), window=self.notes_list_buttons_frame, anchor="nw")
        notes_list_canvas.configure(yscrollcommand=notes_list_scrollbar.set)

        notes_list_canvas.grid(row=1, column=0, sticky=tk.NSEW)
        notes_list_scrollbar.grid(row=1, column=1, sticky=tk.NS)

        notes_list_canvas.bind("<Configure>", lambda e: notes_list_canvas.itemconfig(self.notes_list_canvas_window_id, width=e.width))

        # Store current model name for notes
        self.current_model_for_notes = None

    def create_evaluation_panel(self, parent):
        """Create the evaluation panel for running benchmarks."""
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(1, weight=1) # Row 1 for the output text area

        # --- Controls Frame ---
        controls_frame = ttk.Frame(parent, style='Category.TFrame')
        controls_frame.grid(row=0, column=0, sticky=tk.EW, padx=10, pady=10)
        controls_frame.columnconfigure(1, weight=1)

        # Parent Base Display (above Selected Model)
        self.eval_parent_label = ttk.Label(
            controls_frame,
            text="Base-Model: unavailable",
            font=("Arial", 9, "bold"),
            style='Config.TLabel',
            foreground='#cccccc'
        )
        self.eval_parent_label.grid(row=0, column=0, columnspan=3, sticky=tk.W, padx=5, pady=(0,0))

        # Lineage label (under parent)
        self.eval_lineage_label = ttk.Label(
            controls_frame,
            text="Lineage: unavailable",
            font=("Arial", 8),
            style='Config.TLabel',
            foreground='#aaaaaa'
        )
        self.eval_lineage_label.grid(row=1, column=0, columnspan=3, sticky=tk.W, padx=5, pady=(0,4))

        # Selected Model Display
        self.selected_model_label_eval = ttk.Label(
            controls_frame,
            text="Selected Model: None",
            font=("Arial", 10, "bold"),
            style='Config.TLabel',
            foreground='#61dafb'
        )
        self.selected_model_label_eval.grid(row=2, column=0, columnspan=3, sticky=tk.W, padx=5, pady=5)

        # Class color chip next to Selected model
        try:
            self.eval_class_chip = tk.Label(controls_frame, text='  ', bg='#444444')
            self.eval_class_chip.grid(row=2, column=3, sticky=tk.W, padx=(0,6))
        except Exception:
            self.eval_class_chip = None

        # Source display (Ollama/PyTorch)
        self.eval_source_label = ttk.Label(
            controls_frame,
            text="Source: Unknown",
            font=("Arial", 9),
            style='Config.TLabel',
            foreground='#bbbbbb'
        )
        self.eval_source_label.grid(row=2, column=2, sticky=tk.E, padx=5, pady=5)

        # Test suite dropdown
        ttk.Label(controls_frame, text="Test Suite:", style='Config.TLabel').grid(row=3, column=0, sticky=tk.W, padx=5, pady=5)
        self.test_suite_var = tk.StringVar()
        
        available_suites = get_test_suites()
        all_options = ["All"] + available_suites if available_suites else ["All"]

        self.test_suite_combo = ttk.Combobox(
            controls_frame,
            textvariable=self.test_suite_var,
            values=all_options,
            state="readonly",
            width=20
        )
        self.test_suite_combo.grid(row=3, column=1, sticky=tk.EW, padx=5, pady=5)
        self.test_suite_combo.bind('<<ComboboxSelected>>', self._on_suite_changed)
        
        if available_suites:
            self.test_suite_combo.set(available_suites[0])
        else:
            self.test_suite_combo.set("All")

        # System Prompt controls
        self.use_system_prompt_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            controls_frame,
            text="Use System Prompt",
            variable=self.use_system_prompt_var,
            command=self._toggle_system_prompt_controls,
            style='Config.TCheckbutton'
        ).grid(row=4, column=0, sticky=tk.W, padx=5, pady=5)

        self.system_prompt_var = tk.StringVar()
        self.system_prompt_combo = ttk.Combobox(
            controls_frame,
            textvariable=self.system_prompt_var,
            values=list_system_prompts(),
            state="readonly",
            width=20
        )
        self.system_prompt_combo.grid(row=4, column=1, sticky=tk.EW, padx=5, pady=5)
        self.system_prompt_combo.set("None") # Default
        self.system_prompt_combo.config(state=tk.DISABLED) # Initially disabled

        # Tool Schema controls
        self.use_tool_schema_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            controls_frame,
            text="Use Tool Schema",
            variable=self.use_tool_schema_var,
            command=self._toggle_tool_schema_controls,
            style='Config.TCheckbutton'
        ).grid(row=5, column=0, sticky=tk.W, padx=5, pady=5)

        self.tool_schema_var = tk.StringVar()
        self.tool_schema_combo = ttk.Combobox(
            controls_frame,
            textvariable=self.tool_schema_var,
            values=list_tool_schemas(),
            state="readonly",
            width=20
        )
        self.tool_schema_combo.grid(row=5, column=1, sticky=tk.EW, padx=5, pady=5)
        self.tool_schema_combo.set("None") # Default
        self.tool_schema_combo.config(state=tk.DISABLED) # Initially disabled

        # Baseline checkbox
        self.run_as_baseline_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            controls_frame,
            text="Run as Pre-Training Baseline",
            variable=self.run_as_baseline_var,
            style='Config.TCheckbutton'
        ).grid(row=6, column=0, sticky=tk.W, padx=5, pady=5)

        # Regression check toggle (compare vs baseline after run)
        self.eval_regression_check_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            controls_frame,
            text="Regression Check (compare vs baseline)",
            variable=self.eval_regression_check_var,
            style='Config.TCheckbutton'
        ).grid(row=7, column=0, sticky=tk.W, padx=5, pady=2)

        # Quick regression toggle (sampled subset for faster checks)
        self.eval_quick_regression_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            controls_frame,
            text="Quick Regression (sample ~20%)",
            variable=self.eval_quick_regression_var,
            style='Config.TCheckbutton'
        ).grid(row=8, column=0, sticky=tk.W, padx=5, pady=2)

        # Run button (row 4)
        self.run_eval_button = ttk.Button(
            controls_frame,
            text="▶️ Run Evaluation",
            command=self.run_evaluation,
            style='Action.TButton'
        )
        self.run_eval_button.grid(row=6, column=2, rowspan=3, sticky=tk.E, padx=10, pady=5)

        # Quick access: open Debug tab (manual only)
        ttk.Button(
            controls_frame,
            text="🐞 Debug",
            command=self._focus_settings_debug_tab,
            style='Select.TButton'
        ).grid(row=6, column=3, rowspan=3, sticky=tk.E, padx=(0,5), pady=5)

        # Auto pipeline toggles and data generation
        gen_frame = ttk.LabelFrame(controls_frame, text="🧪→📚 Auto Pipeline", style='TLabelframe')
        gen_frame.grid(row=9, column=0, columnspan=4, sticky=tk.EW, padx=5, pady=6)
        self.auto_train_after_gen_var = tk.BooleanVar(value=False)
        self.auto_export_after_train_var = tk.BooleanVar(value=False)
        self.auto_reeval_after_export_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(gen_frame, text="Auto‑Train after Generate", variable=self.auto_train_after_gen_var, style='Category.TCheckbutton').pack(side=tk.LEFT, padx=8, pady=4)
        ttk.Checkbutton(gen_frame, text="Auto‑Export (GGUF)", variable=self.auto_export_after_train_var, style='Category.TCheckbutton').pack(side=tk.LEFT, padx=8, pady=4)
        ttk.Checkbutton(gen_frame, text="Auto‑Re‑Eval", variable=self.auto_reeval_after_export_var, style='Category.TCheckbutton').pack(side=tk.LEFT, padx=8, pady=4)

        ttk.Button(gen_frame, text="📚 Generate Training Set from Last Eval", command=self._generate_training_from_eval_strict, style='Action.TButton').pack(side=tk.RIGHT, padx=8)

        # --- Output Frame ---
        output_frame = ttk.LabelFrame(parent, text="Live Output", style='TLabelframe')
        output_frame.grid(row=1, column=0, sticky=tk.NSEW, padx=10, pady=(0, 10))
        output_frame.columnconfigure(0, weight=1)
        output_frame.rowconfigure(0, weight=1)

        self.eval_output_text = scrolledtext.ScrolledText(
            output_frame,
            wrap=tk.WORD,
            state=tk.DISABLED,
            font=("Courier", 9),
            bg="#1e1e1e",
            fg="#d4d4d4"
        )
        self.eval_output_text.grid(row=0, column=0, sticky=tk.NSEW)

        # Initialize from Training tab selections if available
        try:
            tinst = self.get_training_tab()
            if tinst:
                # Mirror toggles
                if hasattr(tinst, 'runner_panel'):
                    self.use_system_prompt_var.set(bool(tinst.runner_panel.use_prompt_for_eval_var.get()))
                    self.use_tool_schema_var.set(bool(tinst.runner_panel.use_schema_for_eval_var.get()))
                # Mirror selected names
                psel = getattr(tinst, 'prompt_selected_var', None)
                ssel = getattr(tinst, 'schema_selected_var', None)
                if psel and psel.get():
                    self.system_prompt_combo.config(state='readonly')
                    self.system_prompt_combo.set(psel.get())
                if ssel and ssel.get():
                    self.tool_schema_combo.config(state='readonly')
                    self.tool_schema_combo.set(ssel.get())
        except Exception:
            pass

    def _toggle_system_prompt_controls(self):
        """Enables/disables the system prompt combobox based on checkbox state."""
        if self.use_system_prompt_var.get():
            self.system_prompt_combo.config(state="readonly")
            if not self.system_prompt_var.get() or self.system_prompt_var.get() == "None":
                available_prompts = list_system_prompts()
                if available_prompts:
                    self.system_prompt_combo.set(available_prompts[0])
                else:
                    self.system_prompt_combo.set("No prompts available")
        else:
            self.system_prompt_combo.config(state=tk.DISABLED)
            self.system_prompt_combo.set("None")

    def _toggle_tool_schema_controls(self):
        """Enables/disables the tool schema combobox based on checkbox state."""
        if self.use_tool_schema_var.get():
            self.tool_schema_combo.config(state="readonly")
            if not self.tool_schema_var.get() or self.tool_schema_var.get() == "None":
                available_schemas = list_tool_schemas()
                if available_schemas:
                    self.tool_schema_combo.set(available_schemas[0])
                else:
                    self.tool_schema_combo.set("No schemas available")
        else:
            self.tool_schema_combo.config(state=tk.DISABLED)
            self.tool_schema_combo.set("None")

    def run_evaluation(self):
        """
        Starts the evaluation process in a new thread to keep the GUI responsive.
        """
        suite = self.test_suite_var.get()
        # Prefer explicit selection for eval; fall back to current_model_info
        model = self.current_model_for_stats or ((self.current_model_info or {}).get('name'))
        # Resolve from own combos; if empty and toggles on, fall back to Training tab selections
        system_prompt_name = self.system_prompt_var.get() if self.use_system_prompt_var.get() else None
        tool_schema_name = self.tool_schema_var.get() if self.use_tool_schema_var.get() else None
        try:
            tinst = self.get_training_tab()
            if tinst:
                if self.use_system_prompt_var.get() and (not system_prompt_name or system_prompt_name == 'None'):
                    system_prompt_name = tinst.prompt_selected_var.get() or None
                if self.use_tool_schema_var.get() and (not tool_schema_name or tool_schema_name == 'None'):
                    tool_schema_name = tinst.schema_selected_var.get() or None
        except Exception:
            pass

        if not model:
            messagebox.showwarning("No Model Selected", "Please select a model from the list before running an evaluation.")
            return

        self.run_eval_button.config(state=tk.DISABLED)

        self.eval_output_text.config(state=tk.NORMAL)
        self.eval_output_text.delete(1.0, tk.END)
        self.eval_output_text.insert(tk.END, f"Starting evaluation for model: {model}\n")
        self.eval_output_text.insert(tk.END, f"Test Suite: {suite}\n")
        if system_prompt_name:
            self.eval_output_text.insert(tk.END, f"System Prompt: {system_prompt_name}\n")
        if tool_schema_name:
            self.eval_output_text.insert(tk.END, f"Tool Schema: {tool_schema_name}\n")
        self.eval_output_text.insert(tk.END, f"Scoring: {'schema-aware' if bool(tool_schema_name) else 'basic'}\n")
        if self.eval_regression_check_var.get():
            self.eval_output_text.insert(tk.END, "Regression Check: ON (will compare to baseline if available)\n")
        if self.eval_quick_regression_var.get():
            self.eval_output_text.insert(tk.END, "Quick Regression: ON (sampling ~20% of tests)\n")
        self.eval_output_text.insert(tk.END, "----------------------------------------\n")
        self.eval_output_text.config(state=tk.DISABLED)

        # Preflight: backend availability + inference model presence
        if not self._preflight_eval_backend(tool_schema_name):
            # Re-enable button on early exit
            try:
                self.run_eval_button.config(state=tk.NORMAL)
            except Exception:
                pass
            return

        # Ensure we have an inference (GGUF) model if evaluating a trainable base/level
        try:
            sel_type = (self.current_model_info or {}).get('type')
            if tool_schema_name and sel_type in ('pytorch', 'trained'):
                if not self._ensure_inference_model_for_eval(model):
                    # User cancelled or no compatible model selected/created; re-enable
                    try:
                        self.run_eval_button.config(state=tk.NORMAL)
                    except Exception:
                        pass
                    return
        except Exception:
            pass

        # Baseline conformer: if baseline selected, confirm before run
        baseline_flag = bool(self.run_as_baseline_var.get())
        if baseline_flag:
            if not self._confirm_baseline_creation(model, suite, system_prompt_name, tool_schema_name):
                baseline_flag = False

        # Stash context for potential auto-resume (e.g., after GGUF pull/create)
        try:
            self._last_eval_context = {
                'model': model,
                'suite': suite,
                'prompt': system_prompt_name,
                'schema': tool_schema_name,
                'baseline': baseline_flag,
            }
        except Exception:
            pass

        thread = threading.Thread(
            target=self._run_evaluation_thread,
            args=(model, suite, system_prompt_name, tool_schema_name, baseline_flag)
        )
        thread.daemon = True
        thread.start()

    def _preflight_eval_backend(self, tool_schema_name: str) -> bool:
        """Check that Ollama API is reachable and that an inference model exists when needed."""
        # Check Ollama API is reachable
        try:
            import requests
            r = requests.get("http://localhost:11434/api/version", timeout=2)
            if r.status_code != 200:
                raise RuntimeError(f"status {r.status_code}")
        except Exception:
            messagebox.showwarning(
                "Backend Unavailable",
                "Ollama API is not reachable at http://localhost:11434.\n"
                "Start it with 'ollama serve' or 'sudo systemctl start ollama', then retry."
            )
            return False
        # Ensure an inference (GGUF) model exists when evaluating non-Ollama targets
        try:
            # Refresh available Ollama tags
            try:
                self.ollama_models = get_ollama_models()
            except Exception:
                pass

            # Determine selected target name
            model_name = self.current_model_for_stats or ((self.current_model_info or {}).get('name') or '')

            # Build a flat set of known Ollama tags/names
            known = set()
            try:
                for m in (self.ollama_models or []):
                    if isinstance(m, dict) and m.get('name'):
                        known.add(m.get('name'))
                    elif isinstance(m, str):
                        known.add(m)
            except Exception:
                known = set()

            # If target is not an Ollama tag and no override has been chosen, prompt to select one
            if model_name and (model_name not in known) and not getattr(self, '_eval_override_model_name', None):
                if not self._ensure_inference_model_for_eval(model_name):
                    return False
        except Exception:
            pass
        return True

    def _ensure_inference_model_for_eval(self, base_model_name: str) -> bool:
        """If evaluating a trainable model, ensure a GGUF (Ollama) model is available.
        If none compatible is found, offer to (1) create first baseline GGUF via Level export, or (2) pick an existing GGUF.
        If compatible GGUFs exist, prompt to select which to use; set override for this run.
        """
        # Refresh available Ollama models
        try:
            self.ollama_models = get_ollama_models()
        except Exception:
            pass
        # Build list of compatible GGUF names
        compat = []
        try:
            for m in (self.ollama_models or []):
                name = ''
                if isinstance(m, dict):
                    name = m.get('name') or ''
                elif isinstance(m, str):
                    name = m
                base = name.split(':', 1)[0].lower()
                bsel = base_model_name.lower().split(':', 1)[0]
                if (bsel in base) or (base in base_model_name.lower()):
                    compat.append(name)
        except Exception:
            compat = []

        if compat:
            # Let user pick which GGUF to use
            win = tk.Toplevel(self.root); win.title('Select Inference Model')
            frame = ttk.Frame(win); frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
            ttk.Label(frame, text=f"Select GGUF model for evaluation of base '{base_model_name}':", style='Config.TLabel').grid(row=0, column=0, sticky=tk.W)
            var = tk.StringVar(value=compat[0])
            combo = ttk.Combobox(frame, textvariable=var, values=compat, state='readonly', width=50)
            combo.grid(row=1, column=0, sticky=tk.EW, pady=6)
            decision = {"ok": False}
            def do_ok():
                self._eval_override_model_name = var.get()
                decision["ok"] = True
                win.destroy()
            def do_cancel():
                win.destroy()
            btns = ttk.Frame(frame); btns.grid(row=2, column=0, sticky=tk.E, pady=(6,0))
            ttk.Button(btns, text='Cancel', command=do_cancel, style='Select.TButton').pack(side=tk.RIGHT, padx=5)
            ttk.Button(btns, text='Use This Model', command=do_ok, style='Action.TButton').pack(side=tk.RIGHT)
            win.grab_set(); win.wait_window()
            return bool(decision["ok"])  # proceed only if selected

        # No compatible GGUF; offer to create
        win = tk.Toplevel(self.root); win.title('No Export Detected')
        fr = ttk.Frame(win); fr.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        msg = (
            f"No inference (GGUF) export detected for base '{base_model_name}'.\n\n"
            "Create First Baseline GGUF now? This exports a Level to GGUF for evaluation.\n"
            "Alternatively, you can pick an existing GGUF model (if any) to evaluate."
        )
        txt = tk.Text(fr, height=6, width=64, bg='#ffffff', fg='#000000', font=('Arial', 9))
        txt.insert(1.0, msg); txt.config(state=tk.DISABLED)
        txt.grid(row=0, column=0, columnspan=3, sticky=tk.EW)
        decision = {"create": False, "pick": False}
        def do_create():
            decision["create"] = True; win.destroy()
        def do_pick():
            decision["pick"] = True; win.destroy()
        def do_cancel():
            win.destroy()
        btns = ttk.Frame(fr); btns.grid(row=1, column=0, columnspan=3, sticky=tk.E, pady=(8,0))
        ttk.Button(btns, text='Cancel', command=do_cancel, style='Select.TButton').pack(side=tk.RIGHT, padx=5)
        ttk.Button(btns, text='Pick Existing', command=do_pick, style='Select.TButton').pack(side=tk.RIGHT, padx=5)
        ttk.Button(btns, text='Create Baseline GGUF', command=do_create, style='Action.TButton').pack(side=tk.RIGHT)
        win.grab_set(); win.wait_window()

        if decision["pick"]:
            # Re-run compat detection (in case user added during session) and show dialog even if empty
            # Here, simply inform user to install GGUF via Ollama or Export Levels.
            messagebox.showinfo("Select GGUF", "Install or export a GGUF model, then select it under 'Ollama Models (GGUF)' to evaluate.")
            return False

        if decision["create"]:
            # Export BASE model to GGUF for first baseline
            try:
                base_path = self._find_base_path(base_model_name)
                if not base_path:
                    messagebox.showerror("Export Error", "Base model path not found.")
                    return False
                self._export_base_to_gguf_dialog(base_model_name, base_path)
                return False
            except Exception as e:
                messagebox.showerror("Export Error", f"Could not start baseline export: {e}")
                return False
        return False

    def _export_base_to_gguf_dialog(self, base_model_name: str, base_model_path):
        # Quant picker then prompt target (Local vs Ollama) before export
        win = tk.Toplevel(self.root); win.title('Export Base to GGUF')
        f = ttk.Frame(win); f.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        ttk.Label(f, text=f"Export base '{base_model_name}' to GGUF", style='Config.TLabel').grid(row=0, column=0, sticky=tk.W)
        ttk.Label(f, text="Quantization:", style='Config.TLabel').grid(row=1, column=0, sticky=tk.W, pady=(6,2))
        qvar = tk.StringVar(value='q4_k_m')
        combo = ttk.Combobox(f, textvariable=qvar, values=['q4_k_m','q5_k_m','q8_0'], state='readonly', width=12)
        combo.grid(row=1, column=1, sticky=tk.W)
        def go():
            win.destroy()
            target, outdir = self._prompt_export_target()
            if not target:
                return
            self._run_export_base_to_gguf(base_model_path, qvar.get(), target=target, outdir_override=outdir)
        ttk.Button(f, text='Start Export', command=go, style='Action.TButton').grid(row=2, column=1, sticky=tk.E, pady=(8,0))

    def _run_export_base_to_gguf(self, base_model_path, quant: str, *, model_tag_override: str = None, target: str = 'ollama', outdir_override: str = ''):
        # Spawn export_base_to_gguf.py in a thread and show live logs in a popup
        self._open_export_log_window(title=f"GGUF Export ({quant}) → {'Ollama' if (target or 'ollama')=='ollama' else 'Local'}")
        self._export_log_append(f"\n--- Exporting Base to GGUF ({quant}) ---\n")
        def worker():
            try:
                import subprocess, sys, os
                try:
                    from logger_util import log_message as dbg
                except Exception:
                    def dbg(_m):
                        pass
                dbg(f"GGUF_EXPORT: begin base={base_model_path} quant={quant} target={target} outdir_override={outdir_override} model_tag_override={model_tag_override}")
                script = Path(__file__).parent.parent.parent / 'export_base_to_gguf.py'
                outdir = Path(outdir_override) if (outdir_override or '').strip() else (Path(__file__).parent.parent.parent / 'exports' / 'gguf')
                try:
                    outdir.mkdir(parents=True, exist_ok=True)
                except Exception:
                    pass
                cmd = [sys.executable, str(script), '--base', str(base_model_path), '--output', str(outdir), '--quant', quant]
                dbg("GGUF_EXPORT: running command: " + " ".join(cmd))
                env = os.environ.copy()
                env.setdefault('HF_HUB_OFFLINE', '1')
                env.setdefault('CUDA_VISIBLE_DEVICES', '')
                proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=env)
                while True:
                    line = proc.stdout.readline()
                    if line == '' and proc.poll() is not None:
                        break
                    if line:
                        self.root.after(0, self._export_log_append, line)
                        try:
                            dbg("GGUF_EXPORT_OUT: " + line.rstrip())
                        except Exception:
                            pass
                rc = proc.poll()
                dbg(f"GGUF_EXPORT: export rc={rc}")
                if rc == 0:
                    # Compose Modelfile and either create Ollama model or save local GGUF
                    try:
                        base_name = Path(str(base_model_path)).name
                        tag_name = model_tag_override or base_name
                        # Resolve GGUF path with quant casing tolerance
                        q_upper = (quant or '').upper()
                        cand1 = (outdir / f"{base_name}.{quant}.gguf").resolve()
                        cand2 = (outdir / f"{base_name}.{q_upper}.gguf").resolve()
                        gguf_abs = cand1 if cand1.exists() else (cand2 if cand2.exists() else None)
                        # Validate GGUF path
                        if not gguf_abs:
                            try:
                                matches = sorted(outdir.glob(f"{base_name}.*.gguf"), key=lambda p: p.stat().st_mtime, reverse=True)
                                gguf_abs = matches[0].resolve() if matches else None
                            except Exception:
                                gguf_abs = None
                        if not gguf_abs or not gguf_abs.exists():
                            self.root.after(0, self._export_log_append, f"ERROR: GGUF not found at {gguf_abs}\n")
                            try:
                                dbg(f"GGUF_EXPORT: gguf not found gguf_abs={gguf_abs}")
                            except Exception:
                                pass
                            self.root.after(0, lambda: messagebox.showerror('Export', f'GGUF not found at {gguf_abs}'))
                            return
                        modelfile = outdir / f"{tag_name}.Modelfile"
                        mf = f"FROM {gguf_abs}\nTEMPLATE \"{{{{ .Prompt }}}}\"\n"
                        modelfile.write_text(mf)
                        model_tag = f"{tag_name}:latest"
                        if (target or 'ollama') != 'ollama':
                            try:
                                dbg(f"GGUF_EXPORT: target=local gguf={gguf_abs}")
                            except Exception:
                                pass
                            # Normalize filename for variant exports and write sidecar metadata
                            if model_tag_override:
                                try:
                                    import json as _json
                                    from config import load_model_profile, ensure_lineage_id
                                    # normalize filename {variant}.{quant}.gguf
                                    dest = (outdir / f"{model_tag_override}.{(quant or 'q4_k_m')}.gguf").resolve()
                                    if str(gguf_abs) != str(dest):
                                        try:
                                            os.replace(str(gguf_abs), str(dest))
                                            gguf_abs = dest
                                        except Exception:
                                            gguf_abs = dest
                                    # sidecar metadata
                                    try:
                                        mp = load_model_profile(model_tag_override) or {}
                                        meta = {
                                            'variant_id': model_tag_override,
                                            'lineage_id': ensure_lineage_id(model_tag_override),
                                            'assigned_type': mp.get('assigned_type') or '',
                                            'class_level': mp.get('class_level') or 'novice',
                                            'base_model': mp.get('base_model') or '',
                                            'quant': quant or 'q4_k_m',
                                            'created_at': __import__('datetime').datetime.now().isoformat()
                                        }
                                        (outdir / f"{model_tag_override}.variant.json").write_text(_json.dumps(meta, indent=2))
                                    except Exception:
                                        pass
                                except Exception:
                                    pass
                            # Record unified assignment when variant id known
                            if model_tag_override:
                                try:
                                    from config import add_local_assignment
                                    add_local_assignment(model_tag_override, str(gguf_abs), quant)
                                except Exception:
                                    pass
                            self.root.after(0, lambda: messagebox.showinfo('Export Complete', f'Local GGUF exported to:\n{gguf_abs}'))
                            # Refresh UI panels
                            try:
                                from logger_util import log_message as dbg
                                dbg(f"COLLECTIONS_TRIGGER: Refreshing after local GGUF export variant={model_tag_override} gguf={gguf_abs}")
                            except Exception:
                                pass
                            try:
                                self.populate_model_list()
                                self.refresh_collections_panel()
                            except Exception:
                                pass
                            return
                        # If tag already exists, treat as success and assign
                        try:
                            import subprocess
                            pre = subprocess.run(['ollama','list'], capture_output=True, text=True)
                            if pre.returncode == 0 and (model_tag.split(':')[0] in pre.stdout):
                                def _exists_done():
                                    try:
                                        if model_tag_override:
                                            from config import add_ollama_assignment
                                            add_ollama_assignment(model_tag_override, model_tag)
                                    except Exception:
                                        pass
                                    self.ollama_models = get_ollama_models(); self.populate_model_list()
                                self.root.after(0, _exists_done)
                                return
                        except Exception:
                            pass
                        # Ensure Ollama service is running (target=ollama path)
                        try:
                            dbg(f"GGUF_EXPORT: target=ollama tag={model_tag}")
                        except Exception:
                            pass
                        # Ensure Ollama service is running
                        try:
                            if not self._ensure_ollama_running():
                                # Try to start it in the background
                                import subprocess, time
                                self.root.after(0, self._export_log_append, "\n--- Starting Ollama service ---\n")
                                if 'linux' in sys.platform:
                                    subprocess.Popen(['ollama','serve'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, preexec_fn=os.setsid)
                                else:
                                    subprocess.Popen(['ollama','serve'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                                # Poll up to ~15s
                                for _ in range(30):
                                    time.sleep(0.5)
                                    if self._ensure_ollama_running():
                                        break
                        except Exception:
                            pass
                        # Create tag with captured output for diagnostics
                        create_cmd = ['ollama', 'create', model_tag, '-f', str(modelfile)]
                        self.root.after(0, self._export_log_append, f"\n--- Creating Ollama model {model_tag} ---\n")
                        cproc = subprocess.run(create_cmd, capture_output=True, text=True)
                        # stream outputs to UI
                        if cproc.stdout:
                            self.root.after(0, self._export_log_append, cproc.stdout)
                        if cproc.stderr:
                            self.root.after(0, self._export_log_append, cproc.stderr)
                        crc = cproc.returncode
                        if crc == 0:
                            def _done():
                                # Silent success; no modal interrupt
                                # Record assignment if tagged to a variant
                                try:
                                    if model_tag_override:
                                        from config import add_ollama_assignment
                                        add_ollama_assignment(model_tag_override, model_tag)
                                except Exception:
                                    pass
                                # Refresh Ollama list so it appears under Assigned
                                self.ollama_models = get_ollama_models()
                                self.populate_model_list()
                                self._export_log_append(f"\n✓ Ollama model created: {model_tag}\n")
                                # Auto re-evaluate if enabled and context exists
                                try:
                                    if hasattr(self, 'auto_reeval_after_export_var') and bool(self.auto_reeval_after_export_var.get()):
                                        self._resume_eval_with_override(model_tag)
                                except Exception:
                                    pass
                                self._close_export_log_window()
                            self.root.after(0, _done)
                        else:
                            # As a last resort, try one more time after a brief delay if service just came up
                            def _retry_create():
                                try:
                                    c2 = subprocess.run(['ollama','create', model_tag, '-f', str(modelfile)], capture_output=True, text=True)
                                    if c2.returncode == 0:
                                        try:
                                            if model_tag_override:
                                                from config import add_ollama_assignment
                                                add_ollama_assignment(model_tag_override, model_tag)
                                        except Exception:
                                            pass
                                        self.ollama_models = get_ollama_models(); self.populate_model_list()
                                    else:
                                        # Append diagnostic output
                                        if c2.stdout:
                                            self._export_log_append(c2.stdout)
                                        if c2.stderr:
                                            self._export_log_append(c2.stderr)
                                        messagebox.showwarning('Ollama', 'GGUF export complete, but failed to create Ollama model. You can create it manually.')
                                        self._export_log_append("\n⚠️ Failed to create Ollama model. See above logs.\n")
                                except Exception:
                                    messagebox.showwarning('Ollama', 'GGUF export complete, but failed to create Ollama model. You can create it manually.')
                            self.root.after(500, _retry_create)
                    except Exception as e:
                        self.root.after(0, lambda: messagebox.showwarning('Ollama', f'GGUF export complete, but Ollama create failed: {e}'))
                else:
                    # No fallback: surface the failure clearly and keep logs visible
                    try:
                        self.root.after(0, lambda: messagebox.showerror('Export Failed', f'Export failed with code {rc}.\nSee the export log for details.'))
                        self._export_log_append(f"\n❌ Export failed with code {rc}\n")
                        try:
                            dbg(f"GGUF_EXPORT: export failed rc={rc}")
                        except Exception:
                            pass
                    except Exception:
                        pass
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror('Export Error', str(e)))
                self.root.after(0, self._export_log_append, f"\n❌ Export Error: {e}\n")
                try:
                    dbg(f"GGUF_EXPORT: exception {e}")
                except Exception:
                    pass
        t = threading.Thread(target=worker); t.daemon=True; t.start()

    def _guess_ollama_tag_from_base_name(self, base_name: str) -> str:
        try:
            lower = base_name.lower()
            # Heuristic for Qwen2.5-Xb[-instruct]
            if 'qwen2.5' in lower:
                import re
                m = re.search(r'(\d+(?:\.\d+)?b)', lower)
                size = m.group(1) if m else None
                if size:
                    return f"qwen2.5:{size}"
                return 'qwen2.5:0.5b'
            return ''
        except Exception:
            return ''

    def _ensure_ollama_running(self) -> bool:
        """Return True if Ollama API responds; False otherwise."""
        try:
            import requests
            r = requests.get("http://localhost:11434/api/tags", timeout=1.5)
            return r.status_code == 200
        except Exception:
            return False

    # --- Export Log Window helpers -----------------------------------------
    def _open_export_log_window(self, title: str = "GGUF Export"):
        try:
            import tkinter as tk
            from tkinter import ttk, scrolledtext
            if getattr(self, '_export_log_win', None) and tk.Toplevel.winfo_exists(self._export_log_win):
                self._export_log_win.lift(); return
            win = tk.Toplevel(self.root); win.title(title)
            frame = ttk.Frame(win); frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
            txt = scrolledtext.ScrolledText(frame, wrap=tk.WORD, font=("Courier", 9))
            txt.pack(fill=tk.BOTH, expand=True)
            txt.insert(tk.END, f"{title}\n")
            txt.config(state=tk.DISABLED)
            self._export_log_win = win
            self._export_log_text = txt
        except Exception:
            self._export_log_win = None
            self._export_log_text = None

    def _export_log_append(self, text: str):
        try:
            if not text: return
            if getattr(self, '_export_log_text', None):
                self._export_log_text.config(state=tk.NORMAL)
                self._export_log_text.insert(tk.END, text)
                self._export_log_text.see(tk.END)
                self._export_log_text.config(state=tk.DISABLED)
            try:
                self.append_runner_output(text)
            except Exception:
                pass
        except Exception:
            pass

    def _close_export_log_window(self):
        try:
            if getattr(self, '_export_log_win', None):
                self._export_log_win.destroy()
        except Exception:
            pass
        finally:
            self._export_log_win = None
            self._export_log_text = None

    def _focus_settings_debug_tab(self):
        try:
            tabs = getattr(self, 'tab_instances', None)
            if not tabs or 'settings_tab' not in tabs:
                return
            settings_meta = tabs['settings_tab']
            settings_frame = settings_meta.get('frame')
            settings_inst = settings_meta.get('instance')
            if settings_frame and settings_frame.master:
                # Select the main Settings tab in the top-level notebook
                nb = settings_frame.master
                try:
                    nb.select(settings_frame)
                except Exception:
                    pass
            if settings_inst and hasattr(settings_inst, 'settings_notebook') and hasattr(settings_inst, 'debug_tab_frame'):
                try:
                    settings_inst.settings_notebook.select(settings_inst.debug_tab_frame)
                    # Ensure the debug combobox/poller shows Live Log
                    if hasattr(settings_inst, 'populate_log_file_combobox'):
                        settings_inst.populate_log_file_combobox()
                    if hasattr(settings_inst, 'start_log_polling'):
                        settings_inst.start_log_polling()
                except Exception:
                    pass
        except Exception:
            pass

    def _compute_skills_from_results(self, results: dict) -> dict:
        try:
            per = {}
            for r in results.get('results', []):
                s = r.get('skill') or 'Unknown'
                b = per.setdefault(s, {'passed': 0, 'total': 0})
                b['total'] += 1
                if r.get('passed'):
                    b['passed'] += 1
            if not per:
                return {}
            out = {}
            for s, c in per.items():
                passed = c['passed']; total = c['total']
                if passed == total:
                    status = 'Verified'
                elif passed > 0:
                    status = 'Partial'
                else:
                    status = 'Failed'
                out[s] = {'status': status, 'details': f'Passed {passed}/{total} tests.'}
            return out
        except Exception:
            return {}

    def _run_evaluation_thread(self, model_name, suite_name, system_prompt_name, tool_schema_name, baseline_flag):
        """
        This function runs in a background thread.
        """
        try:
            test_suite_dir = TRAINING_DATA_DIR / 'Test'
            engine = EvaluationEngine(tests_dir=test_suite_dir)
            sample_fraction = 0.2 if self.eval_quick_regression_var.get() else None
            # Call run_benchmark with optional sampling (backwards compatible signature)
            try:
                inference_override = getattr(self, '_eval_override_model_name', None)
                results = engine.run_benchmark(model_name, suite_name, system_prompt_name, tool_schema_name, sample_fraction=sample_fraction, inference_override=inference_override)
            except TypeError:
                # Older engine signature: fallback to full run
                results = engine.run_benchmark(model_name, suite_name, system_prompt_name, tool_schema_name)

            # Save the report (baseline or evaluation)
            if "error" not in results:
                if baseline_flag:
                    mode = getattr(self, '_baseline_mode', 'overwrite')
                    delete_old = bool(getattr(self, '_baseline_delete_old', False))
                    try:
                        import time
                        from config import (
                            get_baseline_report_path,
                            update_model_baseline_index,
                            save_evaluation_report,
                            get_benchmarks_dir,
                        )
                        meta = results.get('metadata', {})
                        meta = {**meta, "timestamp": int(time.time())}
                        if mode == 'new':
                            # Save as a new timestamped baseline under benchmarks dir
                            bdir = get_benchmarks_dir()
                            clean = model_name.replace('/', '_').replace(':', '_')
                            ts = time.strftime('%Y%m%d_%H%M%S')
                            new_path = bdir / f"{clean}_baseline_{ts}.json"
                            # Reuse evaluation saver to get a proper JSON file
                            # (We want exact contents of results)
                            with open(new_path, 'w') as f:
                                import json as _json
                                _json.dump(results, f, indent=2)
                            # Optionally delete old canonical baseline
                            if delete_old:
                                try:
                                    oldp = get_baseline_report_path(model_name)
                                    if oldp.exists():
                                        oldp.unlink()
                                except Exception:
                                    pass
                            update_model_baseline_index(model_name, new_path, meta, set_active=True)
                        else:
                            # Overwrite canonical baseline path
                            from config import save_baseline_report
                            path = save_baseline_report(model_name, results)
                            update_model_baseline_index(model_name, path, meta, set_active=True)
                    except Exception:
                        pass
                else:
                    save_evaluation_report(model_name, results)
            
            # Optional regression comparison summary
            compare_summary = None
            try:
                if (not self.run_as_baseline_var.get()) and self.eval_regression_check_var.get():
                    baseline = load_baseline_report(model_name)
                    if baseline:
                        from config import get_regression_policy
                        policy = get_regression_policy() or {}
                        threshold = float(policy.get('alert_drop_percent', 5.0))
                        cmp = engine.compare_models(baseline, results, regression_threshold=threshold, improvement_threshold=threshold)
                        overall = cmp.get('overall', {})
                        delta = overall.get('delta', '+0.00%')
                        regs = ", ".join([r.get('skill','') for r in cmp.get('regressions', [])]) or 'None'
                        imps = ", ".join([r.get('skill','') for r in cmp.get('improvements', [])]) or 'None'
                        compare_summary = (
                            "\n--- Regression Check Summary ---\n"
                            f"Overall Δ vs baseline: {delta}\n"
                            f"Regressions (>{threshold:.1f}%): {regs}\n"
                            f"Improvements (>{threshold:.1f}%): {imps}\n"
                        )
            except Exception:
                pass

            # Persist skills summary
            try:
                from config import save_skills_file
                skills = self._compute_skills_from_results(results)
                meta = (results or {}).get('metadata', {})
                if skills:
                    save_skills_file(model_name, skills, meta)
            except Exception:
                pass

            # Schedule the UI update on the main thread
            self.root.after(0, self._update_ui_with_results, results)
            if compare_summary:
                self.root.after(0, self._append_eval_summary, compare_summary)
        except Exception as e:
            error_results = {"error": f"An unexpected error occurred in the evaluation thread: {e}"}
            self.root.after(0, self._update_ui_with_results, error_results)

    def _resume_eval_with_override(self, tag: str):
        try:
            ctx = getattr(self, '_last_eval_context', None)
            if not ctx:
                # Fallback: compose context from variant/type
                self._start_eval_with_fallback(tag)
                return
            self._eval_override_model_name = tag
            self.append_runner_output("\n--- Continuing evaluation with inference model: %s ---\n" % tag)
            t = threading.Thread(target=self._run_evaluation_thread,
                                 args=(ctx['model'], ctx['suite'], ctx['prompt'], ctx['schema'], ctx['baseline']))
            t.daemon = True
            t.start()
        except Exception:
            pass

    def _start_eval_with_fallback(self, tag: str):
        try:
            import config as C
            # Resolve variant from tag
            vid = getattr(self, '_active_variant_id', '') or ''
            try:
                if not vid:
                    lid = C.get_lineage_for_tag(tag)
                    if lid:
                        for rec in (C.list_model_profiles() or []):
                            if rec.get('lineage_id') == lid:
                                vid = rec.get('variant_id')
                                break
            except Exception:
                pass
            # Determine type and default suite/prompt/schema
            type_id = 'tools'
            try:
                if vid:
                    mp = C.load_model_profile(vid) or {}
                    at = mp.get('assigned_type'); at = at[0] if isinstance(at, list) else at
                    type_id = (at or 'tools').lower()
            except Exception:
                pass
            mapping = {
                'coder': ('CoderNovice', 'Tools_JSON_Calls_Conformer', 'json_calls_full'),
                'tools': ('Tools', 'Tools_JSON_Calls_Conformer', 'json_calls_full'),
                'researcher': ('ResearcherNovice', 'Tools_JSON_Calls_Conformer', 'json_calls_full'),
                'workflows': ('Workflows', 'Tools_JSON_Calls_Conformer', 'json_calls_full'),
                'orchestration': ('ThinkTime', 'Revised_tools', 'think_time'),
                'thinktime': ('ThinkTime', 'Revised_tools', 'think_time'),
            }
            suite, prompt, schema = mapping.get(type_id, ('CoderNovice', 'Tools_JSON_Calls_Conformer', 'json_calls_full'))
            # Turn on prompt/schema use for this run
            try:
                self.use_system_prompt_var.set(True)
                self.system_prompt_var.set(prompt)
            except Exception:
                pass
            try:
                self.use_tool_schema_var.set(True)
                self.tool_schema_var.set(schema)
            except Exception:
                pass
            # Auto set Re‑Eval toggle for this run
            try:
                self.auto_reeval_after_export_var.set(True)
            except Exception:
                pass
            # Kick off eval with override to tag
            self._eval_override_model_name = tag
            t = threading.Thread(target=self._run_evaluation_thread,
                                 args=(tag, suite, prompt, schema, False))
            t.daemon = True
            t.start()
            self.append_runner_output(f"\n--- Running fallback evaluation ({suite}) using {prompt}/{schema} with inference {tag} ---\n")
        except Exception as e:
            try:
                messagebox.showinfo('Evaluation', f'Installed {tag}. Select it under Ollama Models to evaluate. ({e})')
            except Exception:
                pass

    def _update_ui_with_results(self, results):
        """
        This function is called by the main thread to safely update the UI.
        """
        self.eval_output_text.config(state=tk.NORMAL)
        results_str = json.dumps(results, indent=2)
        self.eval_output_text.insert(tk.END, "\n--- Benchmark Complete ---\n")
        self.eval_output_text.insert(tk.END, results_str)
        self.eval_output_text.see(tk.END)
        self.eval_output_text.config(state=tk.DISABLED)
        self.run_eval_button.config(state=tk.NORMAL)

        # Refresh Skills/Baselines/Compare lists for the current model so the user sees updates immediately
        try:
            if self.current_model_for_stats:
                self.populate_skills_display()
                self._refresh_baselines_panel()
                self._refresh_compare_lists()
        except Exception:
            pass

        # On errors, offer to open the Debug tab (no auto-routing)
        try:
            if isinstance(results, dict) and results.get('error'):
                if messagebox.askyesno("Open Debug?", "Evaluation reported an error. Open Debug tab to view live logs?"):
                    self._focus_settings_debug_tab()
        except Exception:
            pass
        
    def _append_eval_summary(self, text: str):
        try:
            self.eval_output_text.config(state=tk.NORMAL)
            self.eval_output_text.insert(tk.END, text)
            self.eval_output_text.see(tk.END)
            self.eval_output_text.config(state=tk.DISABLED)
        except Exception:
            pass

    # --- Baselines: UI and conformer ---
    def _confirm_baseline_creation(self, model_name: str, suite: str, prompt: str, schema: str) -> bool:
        try:
            import json
            from config import get_baseline_report_path
            path = get_baseline_report_path(model_name)
            exists = path.exists()
            win = tk.Toplevel(self.root)
            win.title("Baseline Options")
            frame = ttk.Frame(win)
            frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
            lines = [
                f"Model: {model_name}",
                f"Suite: {suite}",
                f"Schema: {schema or 'None'}",
                f"Prompt: {prompt or 'None'}",
                f"Sampling: {'ON' if self.eval_quick_regression_var.get() else 'OFF'}",
                "",
                ("A baseline already exists. You can overwrite it, or create a new one side-by-side and set it active." if exists else "This will create a new baseline for regression comparisons."),
                "Recommendation: Baselines should use full suites (no sampling)."
            ]
            txt = tk.Text(frame, height=8, width=60, bg='#ffffff', fg='#000000', font=('Arial', 9))
            txt.insert(1.0, "\n".join(lines))
            txt.config(state=tk.DISABLED)
            txt.grid(row=0, column=0, columnspan=2, sticky=tk.EW)

            # Options: Overwrite vs Create New, plus optional delete old
            mode_var = tk.StringVar(value=('overwrite' if exists else 'new'))
            opt_row = ttk.Frame(frame); opt_row.grid(row=1, column=0, columnspan=2, sticky=tk.W, pady=(8,4))
            ttk.Radiobutton(opt_row, text='Overwrite existing baseline', value='overwrite', variable=mode_var).pack(side=tk.LEFT, padx=(0,12))
            ttk.Radiobutton(opt_row, text='Create new baseline (keep previous)', value='new', variable=mode_var).pack(side=tk.LEFT)
            del_var = tk.BooleanVar(value=False)
            if exists:
                del_row = ttk.Frame(frame); del_row.grid(row=2, column=0, columnspan=2, sticky=tk.W)
                ttk.Checkbutton(del_row, text='Also delete the old baseline file', variable=del_var).pack(side=tk.LEFT)

            decision = {"ok": False}
            def do_overwrite():
                mode_var.set('overwrite'); decision["ok"] = True; win.destroy()
            def do_create_new():
                mode_var.set('new'); decision["ok"] = True; win.destroy()
            def do_cancel():
                win.destroy()
            btns = ttk.Frame(frame)
            btns.grid(row=3, column=0, columnspan=2, sticky=tk.E, pady=(8,0))
            ttk.Button(btns, text='Cancel', command=do_cancel, style='Select.TButton').pack(side=tk.RIGHT, padx=5)
            ttk.Button(btns, text='Create New', command=do_create_new, style='Select.TButton').pack(side=tk.RIGHT, padx=5)
            ttk.Button(btns, text='Overwrite', command=do_overwrite, style='Action.TButton').pack(side=tk.RIGHT)
            win.grab_set()
            win.wait_window()
            if decision["ok"]:
                # Persist choice for the evaluation thread
                try:
                    self._baseline_mode = mode_var.get()  # 'overwrite' or 'new'
                    self._baseline_delete_old = bool(del_var.get()) if exists else False
                except Exception:
                    self._baseline_mode = 'overwrite'; self._baseline_delete_old = False
                return True
            return False
        except Exception:
            # On error, fail safe: do not create baseline automatically
            return False

    def create_baselines_panel(self, parent):
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(1, weight=1)
        header = ttk.Frame(parent)
        header.grid(row=0, column=0, sticky=tk.EW, padx=10, pady=10)
        ttk.Label(header, text="Baselines Manager", font=("Arial", 12, "bold"), style='CategoryPanel.TLabel').pack(side=tk.LEFT)
        ttk.Button(header, text="🔄 Refresh", command=self._refresh_baselines_panel, style='Select.TButton').pack(side=tk.RIGHT)

        # Table area
        self.baselines_canvas = tk.Canvas(parent, bg="#2b2b2b", highlightthickness=0)
        self.baselines_scrollbar = ttk.Scrollbar(parent, orient="vertical", command=self.baselines_canvas.yview)
        self.baselines_content = ttk.Frame(self.baselines_canvas, style='Category.TFrame')
        self.baselines_content.bind("<Configure>", lambda e: self.baselines_canvas.configure(scrollregion=self.baselines_canvas.bbox("all")))
        self._bl_canvas_win = self.baselines_canvas.create_window((0, 0), window=self.baselines_content, anchor="nw")
        self.baselines_canvas.configure(yscrollcommand=self.baselines_scrollbar.set)
        self.baselines_canvas.grid(row=1, column=0, sticky=tk.NSEW, padx=10, pady=(0,10))
        self.baselines_scrollbar.grid(row=1, column=1, sticky=tk.NS)
        self.baselines_canvas.bind("<Configure>", lambda e: self.baselines_canvas.itemconfig(self._bl_canvas_win, width=e.width))
        self._refresh_baselines_panel()

    def _refresh_baselines_panel(self):
        for w in self.baselines_content.winfo_children():
            w.destroy()
        # Load index
        try:
            from config import load_benchmarks_index
            idx = load_benchmarks_index() or {}
        except Exception:
            idx = {}
        model_name = self.current_model_for_stats or (self.current_model_info or {}).get('name')
        # Try exact, then tolerant match on key variants
        def _slug(s: str):
            import re
            return re.sub(r'[^a-z0-9]+', '', (s or '').lower())
        clean = (model_name or '').replace('/', '_').replace(':', '_')
        models_idx = (idx.get('models') or {})
        matched_keys = []
        if model_name:
            want = _slug(model_name)
            for k in models_idx.keys():
                if want in _slug(k) or _slug(k) in want:
                    matched_keys.append(k)
        # Aggregate entries across all matched keys
        aggregate_entries = []
        active_entry = None
        for k in matched_keys or [clean]:
            md = models_idx.get(k) or {}
            for e in (md.get('entries') or []):
                aggregate_entries.append(e)
            if not active_entry and md.get('active'):
                active_entry = md.get('active')
        # Filter out entries that no longer exist on disk
        try:
            from pathlib import Path as _P
            aggregate_entries = [e for e in aggregate_entries if e.get('path') and _P(e.get('path')).exists()]
            if active_entry and (not active_entry.get('path') or not _P(active_entry.get('path')).exists()):
                active_entry = None
        except Exception:
            pass
        m = { 'entries': aggregate_entries, 'active': active_entry }
        matched_key = matched_keys[0] if matched_keys else clean
        row = 0
        header_txt = f"Model: {model_name or 'None selected'}"
        if m and matched_key != clean:
            header_txt += f"  (showing baselines saved under '{matched_key}')"
        ttk.Label(self.baselines_content, text=header_txt, style='Config.TLabel', font=("Arial", 10, "bold")).grid(row=row, column=0, sticky=tk.W, padx=5, pady=(5,3))
        row += 1
        if not m or not (m.get('entries') or m.get('active')):
            ttk.Label(self.baselines_content, text="No baselines found.", style='Config.TLabel').grid(row=row, column=0, sticky=tk.W, padx=10, pady=5)
            return
        # Auto-select the best baseline as active (highest pass_rate_percent)
        try:
            import json as _json
            from pathlib import Path as _P
            from config import save_benchmarks_index
            def _pct(v):
                try:
                    return float(str(v or '0').replace('%',''))
                except Exception:
                    return 0.0
            entries = m.get('entries') or []
            best = None; best_score = -1.0
            for e in entries:
                p = e.get('path');
                if not p or not _P(p).exists():
                    continue
                try:
                    with open(p,'r') as f:
                        data = _json.load(f)
                    score = _pct(data.get('pass_rate_percent'))
                    if score > best_score:
                        best_score = score; best = e
                except Exception:
                    continue
            active = m.get('active') or {}
            active_score = 0.0
            try:
                ap = active.get('path')
                if ap and _P(ap).exists():
                    with open(ap,'r') as f:
                        ad = _json.load(f)
                    active_score = _pct(ad.get('pass_rate_percent'))
            except Exception:
                pass
            # If best exists and is better than current active (or no active), set it active
            if best and (best_score > active_score or not active):
                m['active'] = best
                save_benchmarks_index(idx)
        except Exception:
            pass
        active = m.get('active') or {}
        ttk.Label(self.baselines_content, text=f"Active: suite={active.get('suite')} schema={active.get('schema')} prompt={active.get('prompt')}\n{active.get('path', '')}", style='Config.TLabel').grid(row=row, column=0, sticky=tk.W, padx=10, pady=(0,8))
        row += 1
        for entry in (m.get('entries') or []):
            f = ttk.Frame(self.baselines_content, style='Category.TFrame')
            f.grid(row=row, column=0, sticky=tk.EW, padx=10, pady=2)
            ttk.Label(f, text=f"suite={entry.get('suite')} schema={entry.get('schema')} prompt={entry.get('prompt')}", style='Config.TLabel').pack(side=tk.LEFT)
            ttk.Button(f, text="View", style='Select.TButton', command=lambda p=entry.get('path'): self._view_json_file(p)).pack(side=tk.RIGHT, padx=3)
            ttk.Button(f, text="Set Active", style='Action.TButton', command=lambda e=entry, k=matched_key: self._set_active_baseline(k, e)).pack(side=tk.RIGHT, padx=3)
            row += 1

    def _set_active_baseline(self, clean_name: str, entry: dict):
        try:
            from config import load_benchmarks_index, save_benchmarks_index
            idx = load_benchmarks_index()
            m = idx.setdefault('models', {}).setdefault(clean_name, {"entries": [], "active": None})
            m['active'] = entry
            save_benchmarks_index(idx)
            self._refresh_baselines_panel()
            # Refresh skills to reflect new active baseline
            self.populate_skills_display()
        except Exception:
            pass

    def _view_json_file(self, path: str):
        try:
            import json
            p = Path(path)
            if not p.exists():
                messagebox.showerror("View", f"File not found: {path}")
                return
            with open(p, 'r') as f:
                data = json.load(f)
            self._show_json_window(f"Baseline: {p.name}", data)
        except Exception as e:
            messagebox.showerror("View", f"Failed to open: {e}")

    # --- Suite recommendation conformer ---
    def _on_suite_changed(self, *_):
        try:
            suite = self.test_suite_var.get()
            if not suite or suite == 'All':
                return
            # Auto-apply strict suite→prompt/schema mapping (no dialog)
            prompt, schema_options, default_schema = self._recommend_prompt_schema_for_suite(suite)
            if prompt:
                self.use_system_prompt_var.set(True)
                self.system_prompt_combo.config(state='readonly')
                from config import list_system_prompts
                if prompt in list_system_prompts():
                    self.system_prompt_combo.set(prompt)
            if schema_options:
                pick = default_schema or schema_options[0]
                from config import list_tool_schemas
                if pick in list_tool_schemas():
                    self.use_tool_schema_var.set(True)
                    self.tool_schema_combo.config(state='readonly')
                    self.tool_schema_combo.set(pick)
        except Exception:
            pass

    def _recommend_prompt_schema_for_suite(self, suite: str):
        # Return (prompt_name or None, [schema options], default_schema)
        suite_lower = suite.lower()
        prompt = None
        options = []
        default_schema = None
        # Recommend based on simple mapping
        if 'orchestration' in suite_lower or 'thinktime' in suite_lower:
            # ThinkTime/Orchestration suites expect the think_time tool
            prompt = 'Revised_tools'  # strict, non-Translator prompt
            options = ['think_time']
            default_schema = 'think_time'
        elif 'tools' in suite_lower or 'codernovice' in suite_lower or 'researchernovice' in suite_lower or 'workflows' in suite_lower:
            # Strict JSON call regime using conformer
            prompt = 'Tools_JSON_Calls_Conformer'
            options = ['json_calls_full']
            default_schema = 'json_calls_full'
        elif 'errors' in suite_lower:
            prompt = 'Tools_JSON_Calls_Conformer'
            options = ['json_calls_full']
            default_schema = 'json_calls_full'
        return (prompt, options, default_schema)

    def _show_suite_recommendation_dialog(self, suite: str, prompt: str, schema_options: list, default_schema: str):
        win = tk.Toplevel(self.root)
        win.title('Apply Recommended Prompt/Schema?')
        frame = ttk.Frame(win)
        frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        msg = f"This suite has recommended settings:\n\nSuite: {suite}\n"
        if prompt:
            msg += f"Prompt: '{prompt}'\n"
        if schema_options:
            msg += f"Schema: {', '.join(schema_options)}\n\nApply these for this evaluation?"
        else:
            msg += "\nApply the recommended prompt?"
        info = tk.Text(frame, height=5, width=60, bg='#ffffff', fg='#000000', font=('Arial', 9))
        info.insert(1.0, msg)
        info.config(state=tk.DISABLED)
        info.grid(row=0, column=0, columnspan=3, sticky=tk.EW)

        chosen_schema = tk.StringVar(value=default_schema or (schema_options[0] if schema_options else ''))
        if schema_options and len(schema_options) > 1:
            ttk.Label(frame, text='Schema:', font=('Arial', 9)).grid(row=1, column=0, sticky=tk.W, pady=(6,2))
            schema_combo = ttk.Combobox(frame, textvariable=chosen_schema, values=schema_options, state='readonly', width=24)
            schema_combo.grid(row=1, column=1, sticky=tk.W, pady=(6,2))

        def apply_and_close():
            try:
                # Apply prompt
                if prompt:
                    self.use_system_prompt_var.set(True)
                    self.system_prompt_combo.config(state='readonly')
                    # Verify prompt exists; fall back silently if not
                    from config import list_system_prompts
                    if prompt in list_system_prompts():
                        self.system_prompt_combo.set(prompt)
                # Apply schema
                if schema_options:
                    pick = chosen_schema.get() or default_schema or schema_options[0]
                    from config import list_tool_schemas
                    if pick in list_tool_schemas():
                        self.use_tool_schema_var.set(True)
                        self.tool_schema_combo.config(state='readonly')
                        self.tool_schema_combo.set(pick)
            except Exception:
                pass
            win.destroy()

        def dismiss():
            win.destroy()

        def dont_ask():
            if not hasattr(self, 'eval_suite_reco_suppressed'):
                self.eval_suite_reco_suppressed = {}
            self.eval_suite_reco_suppressed[suite] = True
            win.destroy()

        btns = ttk.Frame(frame)
        btns.grid(row=2, column=0, columnspan=3, sticky=tk.E, pady=(8,0))
        ttk.Button(btns, text='Don\'t ask again', command=dont_ask, style='Select.TButton').pack(side=tk.RIGHT, padx=5)
        ttk.Button(btns, text='Skip', command=dismiss, style='Select.TButton').pack(side=tk.RIGHT, padx=5)
        ttk.Button(btns, text='Apply', command=apply_and_close, style='Action.TButton').pack(side=tk.RIGHT)

    def get_training_tab(self):
        try:
            tabs = getattr(self, 'tab_instances', None)
            if tabs and 'training_tab' in tabs:
                return tabs['training_tab']['instance']
        except Exception:
            pass
        return None

    def create_compare_panel(self, parent):
        """Create the comparison panel for comparing two models' latest evaluations."""
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(2, weight=1)

        # Controls
        controls = ttk.Frame(parent, style='Category.TFrame')
        controls.grid(row=0, column=0, sticky=tk.EW, padx=10, pady=10)
        controls.columnconfigure(1, weight=1)

        ttk.Label(controls, text="Parent Model:", style='Config.TLabel').grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        ttk.Label(controls, text="Advanced: Other Model (latest eval)", style='Config.TLabel').grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)

        self.compare_model_a_var = tk.StringVar()
        self.compare_model_b_var = tk.StringVar()

        # Populate only models that have at least one evaluation report or a baseline
        names = self._filtered_models_for_compare()

        self.compare_model_a_combo = ttk.Combobox(controls, textvariable=self.compare_model_a_var, values=names, state="readonly", width=40)
        self.compare_model_b_combo = ttk.Combobox(controls, textvariable=self.compare_model_b_var, values=names, state="readonly", width=40)
        self.compare_model_a_combo.grid(row=0, column=1, sticky=tk.EW, padx=5, pady=5)
        self.compare_model_b_combo.grid(row=1, column=1, sticky=tk.EW, padx=5, pady=5)

        self.compare_other_btn = ttk.Button(controls, text="🔍 Compare (Other Model)", command=self.run_compare_models, style='Action.TButton')
        self.compare_other_btn.grid(row=0, column=2, rowspan=2, sticky=tk.E, padx=10, pady=5)
        ttk.Button(controls, text="🔄 Refresh", command=self._refresh_compare_lists, style='Select.TButton').grid(row=0, column=3, rowspan=2, sticky=tk.E, padx=5, pady=5)

        # Baseline compare (Latest vs Baseline)
        baseline_frame = ttk.Frame(parent, style='Category.TFrame')
        baseline_frame.grid(row=1, column=0, sticky=tk.EW, padx=10, pady=(0,8))
        ttk.Label(baseline_frame, text="Reference Baseline (Parent):", style='Config.TLabel').pack(side=tk.LEFT, padx=5)
        self.compare_baseline_var = tk.StringVar()
        self.compare_baseline_combo = ttk.Combobox(baseline_frame, textvariable=self.compare_baseline_var, values=[], state='readonly', width=50)
        self.compare_baseline_combo.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        ttk.Button(baseline_frame, text="Compare Latest Eval vs Reference", command=self.run_compare_latest_vs_baseline, style='Select.TButton').pack(side=tk.RIGHT, padx=5)

        # Update baseline list when Parent changes
        self.compare_model_a_combo.bind('<<ComboboxSelected>>', self._populate_compare_baselines)
        self.compare_model_a_combo.bind('<<ComboboxSelected>>', self._populate_compare_baseline_pairs)
        # Update Other Model compare button enabled/disabled
        self.compare_model_a_combo.bind('<<ComboboxSelected>>', self._update_compare_other_state)
        self.compare_model_b_combo.bind('<<ComboboxSelected>>', self._update_compare_other_state)

        # Baseline vs Baseline (same parent: Model A)
        bb_frame = ttk.Frame(parent, style='Category.TFrame')
        bb_frame.grid(row=2, column=0, sticky=tk.EW, padx=10, pady=(0,8))
        ttk.Label(bb_frame, text="Reference vs Target (Parent Baselines):", style='Config.TLabel').grid(row=0, column=0, sticky=tk.W, padx=5)
        self.compare_baseline_a_var = tk.StringVar()
        self.compare_baseline_b_var = tk.StringVar()
        self.compare_baseline_a_combo = ttk.Combobox(bb_frame, textvariable=self.compare_baseline_a_var, values=[], state='readonly', width=45)
        self.compare_baseline_b_combo = ttk.Combobox(bb_frame, textvariable=self.compare_baseline_b_var, values=[], state='readonly', width=45)
        self.compare_baseline_a_combo.grid(row=0, column=1, sticky=tk.EW, padx=5)
        self.compare_baseline_b_combo.grid(row=0, column=2, sticky=tk.EW, padx=5)
        ttk.Button(bb_frame, text="Compare Baselines", command=self.run_compare_baseline_vs_baseline, style='Select.TButton').grid(row=0, column=3, sticky=tk.E, padx=5)
        # (bindings added above)

        # Output
        output_frame = ttk.LabelFrame(parent, text="Comparison Result", style='TLabelframe')
        output_frame.grid(row=3, column=0, sticky=tk.NSEW, padx=10, pady=(0, 10))
        output_frame.columnconfigure(0, weight=1)
        output_frame.rowconfigure(0, weight=1)

        self.compare_output_text = scrolledtext.ScrolledText(
            output_frame,
            wrap=tk.WORD,
            state=tk.DISABLED,
            font=("Courier", 9),
            bg="#1e1e1e",
            fg="#d4d4d4"
        )
        self.compare_output_text.grid(row=0, column=0, sticky=tk.NSEW)

        # Initialize Parent selection and baseline lists on open
        try:
            preferred = (self.current_model_info or {}).get('name')
            if preferred and preferred in names:
                self.compare_model_a_var.set(preferred)
                self.compare_model_a_combo.set(preferred)
            elif names:
                self.compare_model_a_var.set(names[0])
                self.compare_model_a_combo.set(names[0])
            self._populate_compare_baselines()
            self._populate_compare_baseline_pairs()
            self._update_compare_other_state()
        except Exception:
            pass

        # Actions row under output: generate suggestions / save examples
        actions_row = ttk.Frame(parent, style='Category.TFrame')
        actions_row.grid(row=4, column=0, sticky=tk.EW, padx=10, pady=(0,10))
        ttk.Button(actions_row, text='🧠 Generate Training Suggestions', command=self._compare_generate_suggestions, style='Select.TButton').pack(side=tk.LEFT)
        ttk.Button(actions_row, text='💾 Save Example Stubs', command=self._compare_save_examples, style='Select.TButton').pack(side=tk.LEFT, padx=6)

    def _update_compare_other_state(self, *_):
        """Enable 'Compare (Other Model)' only when both selections have a latest evaluation report."""
        try:
            from config import load_latest_evaluation_report
            a = self.compare_model_a_var.get() or ''
            b = self.compare_model_b_var.get() or ''
            has_a = bool(load_latest_evaluation_report(a))
            has_b = bool(load_latest_evaluation_report(b))
            state = tk.NORMAL if (has_a and has_b) else tk.DISABLED
            self.compare_other_btn.config(state=state)
        except Exception:
            try:
                self.compare_other_btn.config(state=tk.DISABLED)
            except Exception:
                pass

    def _refresh_compare_lists(self):
        try:
            names = self._filtered_models_for_compare()
            self.compare_model_a_combo['values'] = names
            self.compare_model_b_combo['values'] = names
            # Reset baseline list for Model A based on any new baselines
            self._populate_compare_baselines()
        except Exception:
            pass

    def _filtered_models_for_compare(self):
        try:
            from config import list_evaluation_reports, load_baseline_report
            names = []
            for m in get_all_trained_models():
                name = m.get('name')
                if not name:
                    continue
                # Only list trainable parents (pytorch/trained) to avoid Ollama tag duplicates
                if (m.get('type') not in ('pytorch', 'trained')):
                    continue
                has_eval = bool(list_evaluation_reports(name))
                has_base = bool(load_baseline_report(name))
                if has_eval or has_base:
                    names.append(name)
            # Deduplicate by case/format variations
            seen = set(); out = []
            for n in names:
                key = n.lower().replace(':','_')
                if key not in seen:
                    seen.add(key); out.append(n)
            return sorted(out)
        except Exception:
            # Fallback to previous behavior if filtering fails
            return [m["name"] for m in get_all_trained_models()]

    def _collect_parent_baselines(self, parent_name: str):
        """Return human‑readable labels for all baselines belonging to the parent (tolerant of name variants)."""
        try:
            import re
            from config import load_benchmarks_index
            idx = load_benchmarks_index() or {}
            models = (idx.get('models') or {})
            def slug(s: str):
                return re.sub(r'[^a-z0-9]+', '', (s or '').lower())
            pslug = slug(parent_name)
            labels = []
            for key, data in models.items():
                if not isinstance(data, dict):
                    continue
                kslug = slug(key)
                if pslug and (pslug == kslug or pslug in kslug or kslug in pslug):
                    for e in (data.get('entries') or []):
                        labels.append(self._format_baseline_label(e))
            return labels
        except Exception:
            return []

    def _format_baseline_label(self, entry: dict) -> str:
        """Build a readable label: YYYY‑MM‑DD HH:MM | pass 50.00% | suite | schema | prompt -> path"""
        try:
            import json, time
            p = entry.get('path','')
            ts = entry.get('timestamp')
            dt = time.strftime('%Y-%m-%d %H:%M', time.localtime(ts)) if ts else 'Unknown time'
            pr = 'n/a'
            if p:
                from pathlib import Path
                fp = Path(p)
                if fp.exists():
                    with open(fp,'r') as f:
                        data = json.load(f)
                        pr = data.get('pass_rate_percent') or 'n/a'
            suite = entry.get('suite') or 'All'
            schema = entry.get('schema') or 'None'
            prompt = entry.get('prompt') or 'None'
            return f"{dt} | pass {pr} | {suite} | {schema} | {prompt} -> {p}"
        except Exception:
            return f"{entry.get('suite') or 'All'} | {entry.get('schema') or 'None'} | {entry.get('prompt') or 'None'} -> {entry.get('path','')}"

    def run_compare_models(self):
        a = self.compare_model_a_var.get()
        b = self.compare_model_b_var.get()
        if not a or not b:
            messagebox.showwarning("Select Models", "Please select both Model A and Model B.")
            return

        a_report = load_latest_evaluation_report(a)
        b_report = load_latest_evaluation_report(b)
        if not a_report or not b_report:
            messagebox.showwarning("Missing Reports", "One or both models lack evaluation reports.")
            return

        # Use engine's compare to compute diffs
        try:
            test_suite_dir = TRAINING_DATA_DIR / "Test"
            engine = EvaluationEngine(tests_dir=test_suite_dir)
            comparison = engine.compare_models(a_report, b_report)
            # Store context for suggestions
            self._last_comparison_ctx = {'baseline': a_report, 'new': b_report, 'comparison': comparison}
            self.compare_output_text.config(state=tk.NORMAL)
            self.compare_output_text.delete(1.0, tk.END)
            self.compare_output_text.insert(tk.END, json.dumps(comparison, indent=2))
            self.compare_output_text.config(state=tk.DISABLED)
        except Exception as e:
            messagebox.showerror("Compare Error", f"Failed to compare: {e}")

    def _populate_compare_baselines(self, *_):
        try:
            mname = self.compare_model_a_var.get()
            labels = self._collect_parent_baselines(mname)
            # Build mapping label -> path for reliable resolution
            self._baseline_label_map = {}
            for lab in labels:
                try:
                    path = lab.split('->',1)[1].strip()
                except Exception:
                    path = ''
                self._baseline_label_map[lab] = path
            self.compare_baseline_combo['values'] = labels
            if labels:
                self.compare_baseline_combo.set(labels[0])
            else:
                self.compare_baseline_combo.set('')
        except Exception:
            self.compare_baseline_combo['values'] = []
            self.compare_baseline_combo.set('')

    def _populate_compare_baseline_pairs(self, *_):
        try:
            mname = self.compare_model_a_var.get()
            labels = self._collect_parent_baselines(mname)
            # Build mapping label -> path for reliable resolution
            self._baseline_pair_label_map = {}
            for lab in labels:
                try:
                    path = lab.split('->',1)[1].strip()
                except Exception:
                    path = ''
                self._baseline_pair_label_map[lab] = path
            self.compare_baseline_a_combo['values'] = labels
            self.compare_baseline_b_combo['values'] = labels
            # Preselect two different entries if available
            if len(labels) >= 1:
                self.compare_baseline_a_combo.set(labels[0])
            if len(labels) >= 2:
                self.compare_baseline_b_combo.set(labels[1])
        except Exception:
            self.compare_baseline_a_combo['values'] = []
            self.compare_baseline_b_combo['values'] = []
            self.compare_baseline_a_combo.set('')
            self.compare_baseline_b_combo.set('')

    def run_compare_latest_vs_baseline(self):
        a = self.compare_model_a_var.get()
        if not a:
            messagebox.showwarning("Select Model", "Please select Model A.")
            return
        label = self.compare_baseline_var.get()
        if not label:
            messagebox.showwarning("Select Baseline", "Please select a baseline entry for Model A.")
            return
        # Resolve via mapping (fallback to split)
        path = ''
        try:
            path = (self._baseline_label_map or {}).get(label, '')
        except Exception:
            path = ''
        if not path and '->' in label:
            path = label.split('->',1)[1].strip()
        try:
            import json
            from pathlib import Path
            from config import load_latest_evaluation_report
            latest = load_latest_evaluation_report(a)
            if not latest:
                messagebox.showwarning("Missing Report", "Model A has no latest evaluation report.")
                return
            p = Path(path)
            if not p.exists():
                messagebox.showwarning("Missing Baseline", "Selected baseline file not found on disk.")
                return
            with open(p, 'r') as f:
                baseline = json.load(f)
            test_suite_dir = TRAINING_DATA_DIR / "Test"
            engine = EvaluationEngine(tests_dir=test_suite_dir)
            comparison = engine.compare_models(baseline, latest)
            self._last_comparison_ctx = {'baseline': baseline, 'new': latest, 'comparison': comparison}
            self.compare_output_text.config(state=tk.NORMAL)
            self.compare_output_text.delete(1.0, tk.END)
            self.compare_output_text.insert(tk.END, json.dumps(comparison, indent=2))
            self.compare_output_text.config(state=tk.DISABLED)
            # Offer to save latest eval as new baseline if better
            try:
                def _pct(s):
                    try: return float((s or '0').replace('%',''))
                    except: return 0.0
                b_overall = _pct((baseline or {}).get('pass_rate_percent'))
                n_overall = _pct((latest or {}).get('pass_rate_percent'))
                if n_overall > b_overall and messagebox.askyesno('Set Active Baseline?', f'Latest evaluation ({n_overall:.2f}%) is higher than the reference baseline ({b_overall:.2f}%).\n\nSave latest eval as a new baseline and set it active?'):
                    from config import save_baseline_report, update_model_baseline_index
                    import time
                    model_name = self.compare_model_a_var.get()
                    path = save_baseline_report(model_name, latest)
                    meta = (latest.get('metadata') or {})
                    meta = {**meta, 'timestamp': int(time.time())}
                    update_model_baseline_index(model_name, path, meta, set_active=True)
                    self._refresh_baselines_panel()
            except Exception:
                pass
        except Exception as e:
            messagebox.showerror("Compare Error", f"Failed to compare: {e}")

    def run_compare_baseline_vs_baseline(self):
        a = self.compare_model_a_var.get()
        if not a:
            messagebox.showwarning("Select Model", "Please select Model A.")
            return
        la = self.compare_baseline_a_var.get() or ''
        lb = self.compare_baseline_b_var.get() or ''
        if not la or not lb:
            messagebox.showwarning("Select Baselines", "Please select two baseline entries for Model A.")
            return
        # Resolve via mapping (fallback to split)
        pa = (getattr(self, '_baseline_pair_label_map', {}) or {}).get(la, '')
        pb = (getattr(self, '_baseline_pair_label_map', {}) or {}).get(lb, '')
        if (not pa and '->' in la): pa = la.split('->',1)[1].strip()
        if (not pb and '->' in lb): pb = lb.split('->',1)[1].strip()
        try:
            import json
            from pathlib import Path
            pa = Path(pa); pb = Path(pb)
            if not pa.exists() or not pb.exists():
                messagebox.showwarning("Missing Baseline", "One or both selected baseline files were not found.")
                return
            with open(pa,'r') as fa: ba = json.load(fa)
            with open(pb,'r') as fb: bb = json.load(fb)
            test_suite_dir = TRAINING_DATA_DIR / "Test"
            engine = EvaluationEngine(tests_dir=test_suite_dir)
            comparison = engine.compare_models(ba, bb)
            self._last_comparison_ctx = {'baseline': ba, 'new': bb, 'comparison': comparison}
            self.compare_output_text.config(state=tk.NORMAL)
            self.compare_output_text.delete(1.0, tk.END)
            self.compare_output_text.insert(tk.END, json.dumps(comparison, indent=2))
            self.compare_output_text.config(state=tk.DISABLED)
            # Offer to set Target baseline active if better
            try:
                def _pct(s):
                    try: return float((s or '0').replace('%',''))
                    except: return 0.0
                b_overall = _pct((ba or {}).get('pass_rate_percent'))
                n_overall = _pct((bb or {}).get('pass_rate_percent'))
                if n_overall > b_overall:
                    parent = self.compare_model_a_var.get() or ''
                    if messagebox.askyesno('Set Active Baseline?', f'Target baseline ({n_overall:.2f}%) is higher than Reference ({b_overall:.2f}%).\n\nSet Target as active for {parent}?'):
                        from config import load_benchmarks_index, save_benchmarks_index
                        clean = parent.replace('/','_').replace(':','_')
                        idx = load_benchmarks_index()
                        m = idx.setdefault('models', {}).setdefault(clean, { 'entries': [], 'active': None })
                        # find target entry by path
                        target_entry = None
                        for e in (m.get('entries') or []):
                            if e.get('path') == str(pb):
                                target_entry = e; break
                        if target_entry:
                            m['active'] = target_entry
                            save_benchmarks_index(idx)
                            self._refresh_baselines_panel()
            except Exception:
                pass
        except Exception as e:
            messagebox.showerror("Compare Error", f"Failed to compare baselines: {e}")

    def _compare_generate_suggestions(self):
        try:
            ctx = getattr(self, '_last_comparison_ctx', None)
            if not ctx:
                messagebox.showinfo('Suggestions', 'Run a comparison first.'); return
            test_suite_dir = TRAINING_DATA_DIR / 'Test'
            engine = EvaluationEngine(tests_dir=test_suite_dir)
            s = engine.generate_training_suggestions(ctx.get('baseline') or {}, ctx.get('new') or {})
            # Render into a new window
            win = tk.Toplevel(self.root); win.title('Training Suggestions')
            txt = scrolledtext.ScrolledText(win, wrap=tk.WORD, font=("Courier", 9), bg="#1e1e1e", fg="#d4d4d4")
            txt.pack(fill=tk.BOTH, expand=True)
            txt.insert(1.0, json.dumps(s, indent=2))
            txt.config(state=tk.DISABLED)
            # Save on the side
            self._last_suggestions = s
        except Exception as e:
            messagebox.showerror('Suggestions', f'Failed to generate suggestions: {e}')

    def _compare_save_examples(self):
        """Save example training stubs from comparison results"""
        try:
            # Check if we have suggestions to save
            suggestions = getattr(self, '_last_suggestions', None)
            if not suggestions:
                # Try to generate suggestions first
                ctx = getattr(self, '_last_comparison_ctx', None)
                if not ctx:
                    messagebox.showinfo('Save Examples', 'Run a comparison and generate suggestions first.')
                    return

                # Generate suggestions
                test_suite_dir = TRAINING_DATA_DIR / 'Test'
                engine = EvaluationEngine(tests_dir=test_suite_dir)
                suggestions = engine.generate_training_suggestions(ctx.get('baseline') or {}, ctx.get('new') or {})
                self._last_suggestions = suggestions

            # Check if suggestions have examples
            examples_jsonl = suggestions.get('examples_jsonl', '')
            if not examples_jsonl:
                messagebox.showinfo('Save Examples', 'No example stubs available in the suggestions.')
                return

            # Ask user for save location
            from tkinter import filedialog
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            default_filename = f"training_examples_{timestamp}.jsonl"

            filepath = filedialog.asksaveasfilename(
                title="Save Training Examples",
                defaultextension=".jsonl",
                filetypes=[("JSONL files", "*.jsonl"), ("All files", "*.*")],
                initialfile=default_filename,
                initialdir=str(TRAINING_DATA_DIR / 'Training')
            )

            if not filepath:
                return  # User cancelled

            # Write examples to file
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(examples_jsonl)

            messagebox.showinfo(
                'Save Examples',
                f'Training examples saved successfully!\n\nLocation: {filepath}\n\nYou can now use these examples for fine-tuning.'
            )

        except Exception as e:
            messagebox.showerror('Save Examples', f'Failed to save examples: {e}')

    def create_skills_panel(self, parent):
        """Create the skills panel for verified model skills."""
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(0, weight=1)

        # Scrollable skills area
        skills_canvas = tk.Canvas(parent, bg="#2b2b2b", highlightthickness=0)
        skills_scrollbar = ttk.Scrollbar(parent, orient="vertical", command=skills_canvas.yview)
        self.skills_content_frame = ttk.Frame(skills_canvas, style='Category.TFrame')

        self.skills_content_frame.bind(
            "<Configure>",
            lambda e: skills_canvas.configure(scrollregion=skills_canvas.bbox("all"))
        )

        self.skills_canvas_window_id = skills_canvas.create_window((0, 0), window=self.skills_content_frame, anchor="nw")
        skills_canvas.configure(yscrollcommand=skills_scrollbar.set)

        skills_canvas.grid(row=0, column=0, sticky=tk.NSEW, padx=10, pady=10)
        skills_scrollbar.grid(row=0, column=1, sticky=tk.NS)

        skills_canvas.bind("<Configure>", lambda e: skills_canvas.itemconfig(self.skills_canvas_window_id, width=e.width))

        # Initialize with placeholder
        ttk.Label(self.skills_content_frame, text="Select a model to view verified skills",
                 font=("Arial", 12), style='Config.TLabel').pack(pady=20)

        # Store current model name for skills
        self.current_model_for_skills = None

    # Phase 1.3: OLD populate_skills_display() removed - using NEW comprehensive version at line ~3000

    def _load_skills_with_lineage_fallback(self, model_name: str):
        """
        Phase 3.1: Load skills with lineage-aware fallback.

        Tries to load skills from:
        1. Direct variant match
        2. Lineage/parent models (if no direct data)

        Returns:
            (runtime_skills, eval_skills, tool_prof, inherited_from)
            where inherited_from is None if direct match, or parent variant_id if inherited
        """
        from config import _get_runtime_skills, get_model_skills, load_model_profile, get_lineage_id, list_model_profiles

        # Try direct load first
        runtime_skills = _get_runtime_skills(model_name)
        eval_skills = get_model_skills(model_name)
        mp = load_model_profile(model_name) or {}
        tool_prof = mp.get('tool_proficiency') or {}

        # If we have any data, use it directly
        if runtime_skills or eval_skills or tool_prof:
            return (runtime_skills, eval_skills, tool_prof, None)

        # No direct data - try lineage fallback
        try:
            lineage_id = get_lineage_id(model_name)
            if not lineage_id:
                return ({}, {}, {}, None)

            # Find other variants in the same lineage
            profiles = list_model_profiles() or []
            siblings = []
            for p in profiles:
                vid = p.get('variant_id')
                lid = p.get('lineage_id')
                if vid and vid != model_name and lid == lineage_id:
                    siblings.append(vid)

            # Try loading from siblings (prefer base/parent variants)
            for sibling in siblings:
                sibling_runtime = _get_runtime_skills(sibling)
                sibling_eval = get_model_skills(sibling)
                sibling_mp = load_model_profile(sibling) or {}
                sibling_prof = sibling_mp.get('tool_proficiency') or {}

                if sibling_runtime or sibling_eval or sibling_prof:
                    log_message(f"[ModelsTab] Using skills inherited from {sibling} (same lineage)")
                    return (sibling_runtime, sibling_eval, sibling_prof, sibling)

        except Exception as e:
            log_message(f"[ModelsTab] Lineage fallback failed: {e}")

        return ({}, {}, {}, None)

    def create_stats_panel(self, parent):
        """Create the stats panel for model training statistics."""
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(1, weight=1)

        # Category filter dropdown
        filter_frame = ttk.Frame(parent, style='Category.TFrame')
        filter_frame.grid(row=0, column=0, sticky=tk.EW, padx=10, pady=5)

        ttk.Label(filter_frame, text="Filter by Category:", font=("Arial", 10, "bold"),
                 style='Config.TLabel').pack(side=tk.LEFT, padx=5)

        self.stats_category_filter_var = tk.StringVar(value="All Categories")
        self.stats_category_dropdown = ttk.Combobox(
            filter_frame,
            textvariable=self.stats_category_filter_var,
            values=["All Categories"],
            state="readonly",
            width=25
        )
        self.stats_category_dropdown.pack(side=tk.LEFT, padx=5)
        self.stats_category_dropdown.bind("<<ComboboxSelected>>", lambda e: self.populate_stats_display())

        # Scrollable stats area
        stats_canvas = tk.Canvas(parent, bg="#2b2b2b", highlightthickness=0)
        stats_scrollbar = ttk.Scrollbar(parent, orient="vertical", command=stats_canvas.yview)
        self.stats_content_frame = ttk.Frame(stats_canvas, style='Category.TFrame')

        self.stats_content_frame.bind(
            "<Configure>",
            lambda e: stats_canvas.configure(scrollregion=stats_canvas.bbox("all"))
        )

        self.stats_canvas_window_id = stats_canvas.create_window((0, 0), window=self.stats_content_frame, anchor="nw")
        stats_canvas.configure(yscrollcommand=stats_scrollbar.set)

        stats_canvas.grid(row=1, column=0, sticky=tk.NSEW, padx=10, pady=10)
        stats_scrollbar.grid(row=1, column=1, sticky=tk.NS)

        stats_canvas.bind("<Configure>", lambda e: stats_canvas.itemconfig(self.stats_canvas_window_id, width=e.width))

        # Initialize with placeholder
        ttk.Label(self.stats_content_frame, text="Select a model to view training statistics",
                 font=("Arial", 12), style='Config.TLabel').pack(pady=20)

        # Store current model name for stats
        self.current_model_for_stats = None

    def create_collections_panel(self, parent):
        """Create the Collections panel for browsing archived lineages."""
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(1, weight=1)

        # Toolbar
        toolbar = ttk.Frame(parent, style='Category.TFrame')
        toolbar.grid(row=0, column=0, sticky=tk.EW, padx=10, pady=5)

        ttk.Label(toolbar, text="Archived Lineages", font=("Arial", 12, "bold"),
                 style='Config.TLabel').pack(side=tk.LEFT, padx=5)

        ttk.Button(toolbar, text="🔄 Refresh", style='Action.TButton',
                  command=self.refresh_collections_list).pack(side=tk.RIGHT, padx=5)

        ttk.Button(toolbar, text="📥 Import Archive", style='Action.TButton',
                  command=self._import_archive_from_file).pack(side=tk.RIGHT, padx=5)

        # Search/filter frame
        filter_frame = ttk.Frame(parent, style='Category.TFrame')
        filter_frame.grid(row=1, column=0, sticky=tk.EW, padx=10, pady=5)

        ttk.Label(filter_frame, text="Search:", font=("Arial", 10),
                 style='Config.TLabel').pack(side=tk.LEFT, padx=5)

        self.collections_search_var = tk.StringVar()
        self.collections_search_var.trace('w', lambda *args: self.refresh_collections_list())
        search_entry = ttk.Entry(filter_frame, textvariable=self.collections_search_var, width=30)
        search_entry.pack(side=tk.LEFT, padx=5)

        # Scrollable list area
        list_canvas = tk.Canvas(parent, bg="#2b2b2b", highlightthickness=0)
        list_scrollbar = ttk.Scrollbar(parent, orient="vertical", command=list_canvas.yview)
        self.collections_content_frame = ttk.Frame(list_canvas, style='Category.TFrame')

        self.collections_content_frame.bind(
            "<Configure>",
            lambda e: list_canvas.configure(scrollregion=list_canvas.bbox("all"))
        )

        self.collections_canvas_window_id = list_canvas.create_window((0, 0), window=self.collections_content_frame, anchor="nw")
        list_canvas.configure(yscrollcommand=list_scrollbar.set)

        list_canvas.grid(row=2, column=0, sticky=tk.NSEW, padx=10, pady=10)
        list_scrollbar.grid(row=2, column=1, sticky=tk.NS)

        list_canvas.bind("<Configure>", lambda e: list_canvas.itemconfig(self.collections_canvas_window_id, width=e.width))

        # Load initial collections
        self.refresh_collections_list()

    def refresh_collections_list(self):
        """Refresh the list of archived lineages."""
        try:
            # Clear existing widgets
            for widget in self.collections_content_frame.winfo_children():
                widget.destroy()

            import config as C
            archives = C.list_archived_lineages()

            # Filter by search term
            search_term = self.collections_search_var.get().lower() if hasattr(self, 'collections_search_var') else ''
            if search_term:
                archives = [a for a in archives if
                           search_term in a.get('base_model', '').lower() or
                           search_term in a.get('archive_name', '').lower() or
                           search_term in a.get('lineage_id', '').lower()]

            if not archives:
                ttk.Label(self.collections_content_frame,
                         text="No archived lineages found.\n\nUse the '📦 Archive Lineage' button to archive a lineage.",
                         font=("Arial", 11), style='Config.TLabel', justify=tk.CENTER).pack(pady=40)
                return

            # Display each archive
            for archive_meta in archives:
                self._create_archive_entry(archive_meta)

        except Exception as e:
            log_error(f"Error refreshing collections: {e}")
            ttk.Label(self.collections_content_frame, text=f"Error loading archives: {e}",
                     font=("Arial", 10), foreground='red', style='Config.TLabel').pack(pady=20)

    def _create_archive_entry(self, archive_meta):
        """Create a UI entry for an archived lineage."""
        entry_frame = ttk.LabelFrame(self.collections_content_frame, text="", style='TLabelframe')
        entry_frame.pack(fill=tk.X, padx=5, pady=5)

        # Header row with key info
        header = ttk.Frame(entry_frame)
        header.pack(fill=tk.X, padx=10, pady=5)

        lineage_id = archive_meta.get('lineage_id', 'Unknown')[:12]
        base_model = archive_meta.get('base_model', 'Unknown')
        archive_date = archive_meta.get('archive_date', '')[:10]  # Just the date part
        variant_count = archive_meta.get('total_variants', 0)
        size_mb = archive_meta.get('archive_size_mb', 0)

        ttk.Label(header, text=f"🔖 {lineage_id}...", font=("Arial", 11, "bold"),
                 style='Config.TLabel').pack(side=tk.LEFT, padx=5)
        ttk.Label(header, text=f"Base: {base_model}", font=("Arial", 10),
                 style='Config.TLabel').pack(side=tk.LEFT, padx=10)
        ttk.Label(header, text=f"📅 {archive_date}", font=("Arial", 9),
                 style='Config.TLabel').pack(side=tk.LEFT, padx=5)
        ttk.Label(header, text=f"{variant_count} variants", font=("Arial", 9),
                 style='Config.TLabel').pack(side=tk.LEFT, padx=5)
        ttk.Label(header, text=f"{size_mb} MB", font=("Arial", 9),
                 style='Config.TLabel').pack(side=tk.LEFT, padx=5)

        # Action buttons row
        actions = ttk.Frame(entry_frame)
        actions.pack(fill=tk.X, padx=10, pady=5)

        archive_path = archive_meta.get('archive_path', '')

        ttk.Button(actions, text="📋 View Details", style='Action.TButton',
                  command=lambda p=archive_path: self._view_archive_details(p)).pack(side=tk.LEFT, padx=2)

        ttk.Button(actions, text="♻️ Restore", style='Action.TButton',
                  command=lambda p=archive_path: self._restore_archive(p)).pack(side=tk.LEFT, padx=2)

        ttk.Button(actions, text="🌱 Spawn Variant", style='Action.TButton',
                  command=lambda p=archive_path: self._spawn_variant_from_archive(p)).pack(side=tk.LEFT, padx=2)

        ttk.Button(actions, text="🗑️ Delete Archive", style='Select.TButton',
                  command=lambda p=archive_path, m=archive_meta: self._delete_archive(p, m)).pack(side=tk.RIGHT, padx=2)

    def _view_archive_details(self, archive_path):
        """Show detailed information about an archive."""
        try:
            from pathlib import Path
            import config as C

            archive_path = Path(archive_path)
            metadata_file = archive_path / "metadata.json"
            if not metadata_file.exists():
                messagebox.showerror('View Details', 'Archive metadata not found.')
                return

            with open(metadata_file, 'r') as f:
                metadata = json.load(f)

            # Create details dialog
            dialog = tk.Toplevel(self.root)
            dialog.title(f"Archive Details: {archive_path.name}")
            dialog.geometry("600x500")
            dialog.transient(self.root)

            # Display metadata
            details_text = scrolledtext.ScrolledText(dialog, wrap=tk.WORD, font=("Courier", 10))
            details_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

            details_content = f"Archive: {metadata.get('archive_name', 'Unknown')}\n"
            details_content += f"Lineage ID: {metadata.get('lineage_id', 'Unknown')}\n"
            details_content += f"Base Model: {metadata.get('base_model', 'Unknown')}\n"
            details_content += f"Archive Date: {metadata.get('archive_date', 'Unknown')}\n"
            details_content += f"Total Variants: {metadata.get('total_variants', 0)}\n"
            details_content += f"Total Size: {metadata.get('archive_size_mb', 0)} MB\n\n"
            details_content += "Variants:\n"
            for vid in metadata.get('variant_list', []):
                details_content += f"  - {vid}\n"

            details_text.insert('1.0', details_content)
            details_text.config(state=tk.DISABLED)

            ttk.Button(dialog, text="Close", command=dialog.destroy).pack(pady=10)

        except Exception as e:
            log_error(f"Error viewing archive details: {e}")
            messagebox.showerror('View Details', str(e))

    def _restore_archive(self, archive_path):
        """Restore an archived lineage with new lineage ID."""
        try:
            from pathlib import Path
            import config as C

            if not messagebox.askyesno('Restore Archive',
                                      'Restore this lineage with a new lineage ID?\n\n'
                                      'This will copy all data back to active profiles.'):
                return

            restored_variants = C.restore_archived_lineage(Path(archive_path))

            self.refresh_collections_panel()
            messagebox.showinfo('Restore Complete',
                              f'Successfully restored {len(restored_variants)} variants!')

        except Exception as e:
            log_error(f"Error restoring archive: {e}")
            messagebox.showerror('Restore Archive', str(e))

    def _spawn_variant_from_archive(self, archive_path):
        """Spawn a single variant from an archive."""
        try:
            from pathlib import Path
            import config as C

            # Load archive metadata
            archive_path = Path(archive_path)
            metadata_file = archive_path / "metadata.json"
            if not metadata_file.exists():
                messagebox.showerror('Spawn Variant', 'Archive metadata not found.')
                return

            with open(metadata_file, 'r') as f:
                metadata = json.load(f)

            variants = metadata.get('variant_list', [])
            if not variants:
                messagebox.showwarning('Spawn Variant', 'No variants found in archive.')
                return

            # Let user select which variant to spawn
            selection_dialog = tk.Toplevel(self.root)
            selection_dialog.title("Select Variant to Spawn")
            selection_dialog.geometry("400x300")
            selection_dialog.transient(self.root)
            selection_dialog.grab_set()

            ttk.Label(selection_dialog, text="Select a variant to spawn:",
                     font=("Arial", 11), style='Config.TLabel').pack(padx=10, pady=10)

            listbox = tk.Listbox(selection_dialog, selectmode=tk.SINGLE)
            scrollbar = ttk.Scrollbar(selection_dialog, command=listbox.yview)
            listbox.config(yscrollcommand=scrollbar.set)

            for variant in variants:
                listbox.insert(tk.END, variant)

            listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(10, 0), pady=10)
            scrollbar.pack(side=tk.LEFT, fill=tk.Y, pady=10, padx=(0, 10))

            selected_variant = [None]

            def on_spawn():
                selection = listbox.curselection()
                if not selection:
                    messagebox.showwarning('Select Variant', 'Please select a variant.')
                    return
                selected_variant[0] = listbox.get(selection[0])
                selection_dialog.destroy()

            ttk.Button(selection_dialog, text="Spawn", style='Action.TButton',
                      command=on_spawn).pack(pady=10)

            selection_dialog.wait_window()

            if not selected_variant[0]:
                return

            # Spawn the selected variant (simplified restore for single variant)
            variant_id = selected_variant[0]
            new_lineage_id = C.generate_ulid()

            # Restore just this variant's profile with new lineage ID and reset stats
            mp_src = archive_path / "profiles" / f"{variant_id}.json"
            if mp_src.exists():
                profile = json.loads(mp_src.read_text())
                profile['lineage_id'] = new_lineage_id
                profile['xp'] = {'total': 0, 'history': []}
                profile['latest_eval_score'] = 0.0
                profile['class_level'] = 'novice'
                profile['stats'] = {}
                profile['skills'] = {}
                profile['badges'] = []
                C.save_model_profile(variant_id, profile)

            self.refresh_collections_panel()
            messagebox.showinfo('Spawn Complete',
                              f'Spawned variant: {variant_id}\nNew lineage ID: {new_lineage_id[:8]}...')

        except Exception as e:
            log_error(f"Error spawning variant: {e}")
            messagebox.showerror('Spawn Variant', str(e))

    def _delete_archive(self, archive_path, archive_meta):
        """Delete an archived lineage."""
        try:
            from pathlib import Path
            import config as C

            archive_name = archive_meta.get('archive_name', 'Unknown')
            if not messagebox.askyesno('Delete Archive',
                                      f'Permanently delete archive "{archive_name}"?\n\n'
                                      f'This cannot be undone.'):
                return

            C.delete_archived_lineage(Path(archive_path))
            self.refresh_collections_list()
            messagebox.showinfo('Delete Archive', 'Archive deleted successfully.')

        except Exception as e:
            log_error(f"Error deleting archive: {e}")
            messagebox.showerror('Delete Archive', str(e))

    def _import_archive_from_file(self):
        """Import an archive from an external zip or directory."""
        messagebox.showinfo('Import Archive', 'Archive import feature coming soon!\n\n'
                           'For now, you can manually copy archive directories to:\n'
                           'Data/collections/archived_lineages/')

    # --- Class Tree Panel ---------------------------------------------------
    def create_class_tree_panel(self, parent):
        """Create the Class progression tree panel with scrollbar."""
        # Create canvas and scrollbar for Class tab
        self.class_canvas = tk.Canvas(parent, bg="#2b2b2b", highlightthickness=0)
        self.class_scrollbar = ttk.Scrollbar(parent, orient="vertical", command=self.class_canvas.yview)
        self.class_content_frame = ttk.Frame(self.class_canvas, style='Category.TFrame')

        # Configure canvas
        self.class_content_frame.bind(
            "<Configure>",
            lambda e: self.class_canvas.configure(scrollregion=self.class_canvas.bbox("all"))
        )
        self.class_canvas.create_window((0, 0), window=self.class_content_frame, anchor="nw")
        self.class_canvas.configure(yscrollcommand=self.class_scrollbar.set)

        # Pack canvas and scrollbar
        self.class_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.class_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Mouse wheel scrolling on hover
        def _on_mousewheel(event):
            self.class_canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        def _bind_mousewheel(event):
            self.class_canvas.bind_all("<MouseWheel>", _on_mousewheel)
        def _unbind_mousewheel(event):
            self.class_canvas.unbind_all("<MouseWheel>")
        self.class_canvas.bind("<Enter>", _bind_mousewheel)
        self.class_canvas.bind("<Leave>", _unbind_mousewheel)

        # Initial message
        ttk.Label(
            self.class_content_frame,
            text="Select a variant to view class progression tree",
            style='Config.TLabel',
            font=("Arial", 12),
            foreground="#888888"
        ).pack(pady=50)

    def populate_class_tree_display(self, variant_id: str):
        """Populate the class tree display for the selected variant."""
        try:
            # Clear existing content
            for widget in self.class_content_frame.winfo_children():
                widget.destroy()

            if not variant_id:
                ttk.Label(
                    self.class_content_frame,
                    text="Select a variant to view class progression tree",
                    style='Config.TLabel',
                    font=("Arial", 12),
                    foreground="#888888"
                ).pack(pady=50)
                return

            import config as C
            from pathlib import Path
            import json

            # Load variant profile
            profile = C.load_model_profile(variant_id)
            if not profile:
                ttk.Label(
                    self.class_content_frame,
                    text=f"Profile not found for {variant_id}",
                    style='Config.TLabel',
                    foreground="#ff6b6b"
                ).pack(pady=20)
                return

            # Get current class and assigned type
            current_class = profile.get('class_level', 'novice')
            assigned_type = profile.get('assigned_type', 'unassigned')

            # Handle empty or invalid assigned_type
            if not assigned_type or assigned_type in ('', '[]', 'None', 'unassigned'):
                # Try to get from bundle
                try:
                    from registry.bundle_loader import find_bundle_by_name
                    base_model = profile.get('base_model', '')
                    if base_model:
                        bundle = find_bundle_by_name(base_model)
                        if bundle:
                            for v in bundle.get('variants', []):
                                if v.get('variant_id') == variant_id:
                                    assigned_type = v.get('assigned_type', 'unassigned')
                                    break
                except Exception:
                    pass

            # Final fallback
            if not assigned_type or assigned_type in ('', '[]', 'None', 'unassigned'):
                assigned_type = 'unassigned'

            # Header
            header_frame = ttk.Frame(self.class_content_frame, style='Category.TFrame')
            header_frame.pack(fill=tk.X, padx=10, pady=10)

            ttk.Label(
                header_frame,
                text=f"🎓 Class Progression: {variant_id}",
                font=("Arial", 14, "bold"),
                style='CategoryPanel.TLabel'
            ).pack(anchor=tk.W, pady=(0, 5))

            ttk.Label(
                header_frame,
                text=f"Current Class: {current_class.title()} | Type: {assigned_type.title()}",
                font=("Arial", 10),
                style='Config.TLabel',
                foreground='#61dafb'
            ).pack(anchor=tk.W)

            # Show warning if type is unassigned
            if assigned_type == 'unassigned':
                ttk.Label(
                    self.class_content_frame,
                    text="⚠️ No type assigned to this variant",
                    style='Config.TLabel',
                    foreground="#ffaa00",
                    font=("Arial", 11, "bold")
                ).pack(pady=10, padx=20)
                ttk.Label(
                    self.class_content_frame,
                    text="Assign a type in the Types tab to view class progression tree",
                    style='Config.TLabel',
                    foreground="#888888"
                ).pack(pady=5, padx=20)
                return

            # Load type catalog v2 (contains all class definitions for all types)
            type_catalog_path = Path("Data/type_catalog_v2.json")

            if not type_catalog_path.exists():
                ttk.Label(
                    self.class_content_frame,
                    text="Type catalog not found (type_catalog_v2.json)",
                    style='Config.TLabel',
                    foreground="#ffaa00"
                ).pack(pady=20, padx=20)
                return

            # Load catalog and find the type definition
            with open(type_catalog_path, 'r') as f:
                type_catalog = json.load(f)

            # Find the type definition in the catalog
            type_definition = None
            for type_def in type_catalog.get('types', []):
                if type_def.get('id') == assigned_type:
                    type_definition = type_def
                    break

            if not type_definition:
                ttk.Label(
                    self.class_content_frame,
                    text=f"Type '{assigned_type}' not found in type catalog",
                    style='Config.TLabel',
                    foreground="#ffaa00"
                ).pack(pady=20, padx=20)
                return

            # Get class definitions from type
            class_data = type_definition.get('classes', {})

            # Define class progression order (matches type_catalog_v2.json structure)
            class_order = ['novice', 'skilled', 'adept', 'expert', 'master', 'grand_master']

            # Get current class index
            try:
                current_index = class_order.index(current_class.lower())
            except ValueError:
                current_index = 0

            # Display progression tree
            tree_frame = ttk.Frame(self.class_content_frame, style='Category.TFrame')
            tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

            for idx, class_name in enumerate(class_order):
                class_info = class_data.get(class_name, {})

                # Determine if class is unlocked, current, or locked
                if idx < current_index:
                    status = "unlocked"
                    color = "#00ff00"  # Green - completed
                    icon = "✅"
                elif idx == current_index:
                    status = "current"
                    color = "#61dafb"  # Cyan - current
                    icon = "🎯"
                else:
                    status = "locked"
                    color = "#888888"  # Gray - locked
                    icon = "🔒"

                # Create class entry frame
                # Format class name nicely (handle grand_master -> Grand Master)
                display_name = class_name.replace('_', ' ').title()
                class_entry = ttk.LabelFrame(
                    tree_frame,
                    text=f"{icon} {display_name}",
                    style='TLabelframe'
                )
                class_entry.pack(fill=tk.X, pady=5)

                # Class info summary (XP, eval requirements)
                info_parts = []
                min_xp = class_info.get('min_xp', 0)
                min_eval = class_info.get('min_eval', 0.0)

                if min_xp > 0:
                    info_parts.append(f"Min XP: {min_xp:,}")
                if min_eval > 0:
                    info_parts.append(f"Min Eval: {min_eval:.2f}")

                if info_parts:
                    ttk.Label(
                        class_entry,
                        text=" | ".join(info_parts),
                        style='Config.TLabel',
                        foreground=color,
                        font=("Arial", 9)
                    ).pack(anchor=tk.W, padx=10, pady=(5, 2))

                # Required skills for this class
                required_skills = class_info.get('required_skills', [])
                if required_skills:
                    skills_frame = ttk.Frame(class_entry)
                    skills_frame.pack(fill=tk.X, padx=10, pady=5)

                    ttk.Label(
                        skills_frame,
                        text="📚 Required Skills:",
                        style='Config.TLabel',
                        font=("Arial", 9, "bold")
                    ).pack(anchor=tk.W)

                    for skill in required_skills:
                        ttk.Label(
                            skills_frame,
                            text=f"  • {skill}",
                            style='Config.TLabel',
                            foreground=color if status != "locked" else "#666666"
                        ).pack(anchor=tk.W, padx=10)

                # Tool Proficiency requirements for this class
                tool_proficiency = class_info.get('tool_proficiency', {})
                if tool_proficiency:
                    tools_frame = ttk.Frame(class_entry)
                    tools_frame.pack(fill=tk.X, padx=10, pady=5)

                    ttk.Label(
                        tools_frame,
                        text="🔧 Tool Proficiency Requirements:",
                        style='Config.TLabel',
                        font=("Arial", 9, "bold")
                    ).pack(anchor=tk.W)

                    for tool_name, grade in tool_proficiency.items():
                        # Format tool name nicely
                        display_tool = tool_name.replace('_', ' ').title()
                        grade_text = f"Grade {grade}+" if grade != "all_tools" else "All Tools"

                        ttk.Label(
                            tools_frame,
                            text=f"  • {display_tool}: {grade_text}",
                            style='Config.TLabel',
                            foreground=color if status != "locked" else "#666666"
                        ).pack(anchor=tk.W, padx=10)

                # Requirements for next class (only show for current class)
                if status == "current" and idx < len(class_order) - 1:
                    next_class_info = class_data.get(class_order[idx + 1], {})
                    # Extract requirements from next class info
                    requirements = {}

                    # Add XP requirement
                    min_xp = next_class_info.get('min_xp', 0)
                    if min_xp > 0:
                        requirements['Min XP'] = f"{min_xp:,}"

                    # Add eval requirement
                    min_eval = next_class_info.get('min_eval', 0.0)
                    if min_eval > 0:
                        requirements['Min Eval Score'] = f"{min_eval:.2f}"

                    # Add required skills
                    required_skills = next_class_info.get('required_skills', [])
                    if required_skills:
                        requirements['Required Skills'] = ', '.join(required_skills)

                    if requirements:
                        req_frame = ttk.LabelFrame(class_entry, text="Requirements for Next Class", style='TLabelframe')
                        req_frame.pack(fill=tk.X, padx=10, pady=5)

                        for req_type, req_value in requirements.items():
                            ttk.Label(
                                req_frame,
                                text=f"  • {req_type}: {req_value}",
                                style='Config.TLabel',
                                foreground='#ffaa00'
                            ).pack(anchor=tk.W, padx=10, pady=2)

            log_message(f"[ModelsTab] Populated class tree for {variant_id}")

        except Exception as e:
            log_error(f"Error populating class tree: {e}")
            import traceback
            traceback.print_exc()
            ttk.Label(
                self.class_content_frame,
                text=f"Error loading class tree: {str(e)}",
                style='Config.TLabel',
                foreground="#ff6b6b"
            ).pack(pady=20, padx=20)

    def populate_stats_display(self):
        """Populate the stats display for the current model with hierarchical stats from profile."""
        # Clear existing content
        for widget in self.stats_content_frame.winfo_children():
            widget.destroy()

        if not self.current_model_for_stats:
            ttk.Label(self.stats_content_frame, text="Select a model to view statistics",
                     font=("Arial", 12), style='Config.TLabel').pack(pady=20)
            return

        # Load profile stats for current model (unified with Preview Panel)
        from config import load_model_profile
        profile = load_model_profile(self.current_model_for_stats) or {}
        stats = profile.get('stats', {})

        # Header
        header_frame = ttk.Frame(self.stats_content_frame, style='Category.TFrame')
        header_frame.pack(fill=tk.X, padx=10, pady=10)

        header_text = f"📊 Model Statistics: {self.current_model_for_stats}"
        ttk.Label(header_frame, text=header_text,
                 font=("Arial", 14, "bold"), style='CategoryPanel.TLabel').pack(anchor=tk.W)

        # Display hierarchical stats (same as Preview Panel)
        if not stats:
            ttk.Label(self.stats_content_frame, text="No statistics recorded yet",
                     font=("Arial", 11), style='Config.TLabel').pack(pady=20)
            ttk.Label(self.stats_content_frame,
                     text="Stats will appear after training, evaluation, or tool usage",
                     font=("Arial", 9), style='Config.TLabel').pack()
            return

        # Profile Summary
        summary_frame = ttk.LabelFrame(self.stats_content_frame, text="Profile Summary", style='TLabelframe')
        summary_frame.pack(fill=tk.X, padx=10, pady=5)

        # XP and Level - use safe extraction for modern dict format
        from config import get_xp_value
        xp_total = get_xp_value(profile)
        class_level = profile.get('class_level', 'novice')
        ttk.Label(summary_frame, text=f"Level:", font=("Arial", 10, "bold"),
                 style='Config.TLabel').grid(row=0, column=0, sticky=tk.W, padx=10, pady=3)
        ttk.Label(summary_frame, text=f"{class_level.title()}", font=("Arial", 10),
                 style='Config.TLabel').grid(row=0, column=1, sticky=tk.W, padx=10, pady=3)

        ttk.Label(summary_frame, text=f"XP:", font=("Arial", 10, "bold"),
                 style='Config.TLabel').grid(row=1, column=0, sticky=tk.W, padx=10, pady=3)
        ttk.Label(summary_frame, text=f"{xp_total:,}", font=("Arial", 10),
                 style='Config.TLabel').grid(row=1, column=1, sticky=tk.W, padx=10, pady=3)

        # Eval Score
        eval_score = profile.get('latest_eval_score', 0.0)
        ttk.Label(summary_frame, text=f"Latest Eval:", font=("Arial", 10, "bold"),
                 style='Config.TLabel').grid(row=2, column=0, sticky=tk.W, padx=10, pady=3)
        ttk.Label(summary_frame, text=f"{eval_score:.1%}", font=("Arial", 10),
                 style='Config.TLabel').grid(row=2, column=1, sticky=tk.W, padx=10, pady=3)

        # Hierarchical Stats Display (4-layer architecture)
        # Layer 1: Raw Metrics
        raw_metrics = stats.get('raw_metrics', {})
        if raw_metrics:
            raw_frame = ttk.LabelFrame(self.stats_content_frame, text="📊 Raw Metrics", style='TLabelframe')
            raw_frame.pack(fill=tk.X, padx=10, pady=5)

            row = 0
            # Token counts
            token_counts = raw_metrics.get('token_counts', {})
            if token_counts:
                ttk.Label(raw_frame, text="Token Counts:",
                         font=("Arial", 10, "bold"), style='Config.TLabel').grid(
                             row=row, column=0, sticky=tk.W, padx=10, pady=2)
                row += 1
                for key, val in token_counts.items():
                    ttk.Label(raw_frame, text=f"  {key.title()}:",
                             font=("Arial", 9), style='Config.TLabel').grid(
                                 row=row, column=0, sticky=tk.W, padx=20, pady=1)
                    ttk.Label(raw_frame, text=f"{val:,}",
                             font=("Arial", 9), style='Config.TLabel').grid(
                                 row=row, column=1, sticky=tk.W, padx=10, pady=1)
                    row += 1

            # Timing
            timing_ms = raw_metrics.get('timing_ms', {})
            if timing_ms:
                ttk.Label(raw_frame, text="Timing (ms):",
                         font=("Arial", 10, "bold"), style='Config.TLabel').grid(
                             row=row, column=0, sticky=tk.W, padx=10, pady=2)
                row += 1
                for key, val in timing_ms.items():
                    ttk.Label(raw_frame, text=f"  {key.title()}:",
                             font=("Arial", 9), style='Config.TLabel').grid(
                                 row=row, column=0, sticky=tk.W, padx=20, pady=1)
                    ttk.Label(raw_frame, text=f"{val:,}",
                             font=("Arial", 9), style='Config.TLabel').grid(
                                 row=row, column=1, sticky=tk.W, padx=10, pady=1)
                    row += 1

            # Tool usage
            tool_usage = raw_metrics.get('tool_usage', {})
            if tool_usage:
                ttk.Label(raw_frame, text="Tool Usage:",
                         font=("Arial", 10, "bold"), style='Config.TLabel').grid(
                             row=row, column=0, sticky=tk.W, padx=10, pady=2)
                row += 1
                for key, val in sorted(tool_usage.items()):
                    ttk.Label(raw_frame, text=f"  {key}:",
                             font=("Arial", 9), style='Config.TLabel').grid(
                                 row=row, column=0, sticky=tk.W, padx=20, pady=1)
                    ttk.Label(raw_frame, text=str(val),
                             font=("Arial", 9), style='Config.TLabel').grid(
                                 row=row, column=1, sticky=tk.W, padx=10, pady=1)
                    row += 1

        # Layer 2: Performance Stats
        performance = stats.get('performance', {})
        if performance:
            perf_frame = ttk.LabelFrame(self.stats_content_frame, text="⚡ Performance", style='TLabelframe')
            perf_frame.pack(fill=tk.X, padx=10, pady=5)

            row = 0
            # Speed metrics
            speed = performance.get('speed', {})
            if speed:
                ttk.Label(perf_frame, text="Speed:",
                         font=("Arial", 10, "bold"), style='Config.TLabel').grid(
                             row=row, column=0, sticky=tk.W, padx=10, pady=2)
                row += 1

                tokens_per_ms = speed.get('tokens_per_ms')
                if tokens_per_ms is not None:
                    tokens_per_sec = tokens_per_ms * 1000
                    ttk.Label(perf_frame, text="  Tokens/sec:",
                             font=("Arial", 9), style='Config.TLabel').grid(
                                 row=row, column=0, sticky=tk.W, padx=20, pady=1)
                    ttk.Label(perf_frame, text=f"{tokens_per_sec:.2f}",
                             font=("Arial", 9), style='Config.TLabel').grid(
                                 row=row, column=1, sticky=tk.W, padx=10, pady=1)
                    row += 1

                tokens_per_ms_ema = speed.get('tokens_per_ms_ema')
                if tokens_per_ms_ema is not None:
                    tokens_per_sec_ema = tokens_per_ms_ema * 1000
                    ttk.Label(perf_frame, text="  Tokens/sec (EMA):",
                             font=("Arial", 9), style='Config.TLabel').grid(
                                 row=row, column=0, sticky=tk.W, padx=20, pady=1)
                    ttk.Label(perf_frame, text=f"{tokens_per_sec_ema:.2f}",
                             font=("Arial", 9), style='Config.TLabel').grid(
                                 row=row, column=1, sticky=tk.W, padx=10, pady=1)
                    row += 1

            # Accuracy metrics
            accuracy = performance.get('accuracy', {})
            if accuracy:
                ttk.Label(perf_frame, text="Accuracy:",
                         font=("Arial", 10, "bold"), style='Config.TLabel').grid(
                             row=row, column=0, sticky=tk.W, padx=10, pady=2)
                row += 1
                for key, val in accuracy.items():
                    display_key = key.replace('_', ' ').title()
                    ttk.Label(perf_frame, text=f"  {display_key}:",
                             font=("Arial", 9), style='Config.TLabel').grid(
                                 row=row, column=0, sticky=tk.W, padx=20, pady=1)
                    if isinstance(val, float):
                        ttk.Label(perf_frame, text=f"{val:.3f}",
                                 font=("Arial", 9), style='Config.TLabel').grid(
                                     row=row, column=1, sticky=tk.W, padx=10, pady=1)
                    else:
                        ttk.Label(perf_frame, text=str(val),
                                 font=("Arial", 9), style='Config.TLabel').grid(
                                     row=row, column=1, sticky=tk.W, padx=10, pady=1)
                    row += 1

            # Efficiency metrics
            efficiency = performance.get('efficiency', {})
            if efficiency:
                ttk.Label(perf_frame, text="Efficiency:",
                         font=("Arial", 10, "bold"), style='Config.TLabel').grid(
                             row=row, column=0, sticky=tk.W, padx=10, pady=2)
                row += 1
                for key, val in efficiency.items():
                    display_key = key.replace('_', ' ').title()
                    ttk.Label(perf_frame, text=f"  {display_key}:",
                             font=("Arial", 9), style='Config.TLabel').grid(
                                 row=row, column=0, sticky=tk.W, padx=20, pady=1)
                    if isinstance(val, float):
                        ttk.Label(perf_frame, text=f"{val:.3f}",
                                 font=("Arial", 9), style='Config.TLabel').grid(
                                     row=row, column=1, sticky=tk.W, padx=10, pady=1)
                    else:
                        ttk.Label(perf_frame, text=str(val),
                                 font=("Arial", 9), style='Config.TLabel').grid(
                                     row=row, column=1, sticky=tk.W, padx=10, pady=1)
                    row += 1

        # Layer 3: Quality Stats
        quality = stats.get('quality', {})
        if quality:
            quality_frame = ttk.LabelFrame(self.stats_content_frame, text="✨ Quality", style='TLabelframe')
            quality_frame.pack(fill=tk.X, padx=10, pady=5)

            row = 0
            for category, metrics in quality.items():
                if isinstance(metrics, dict):
                    ttk.Label(quality_frame, text=f"{category.replace('_', ' ').title()}:",
                             font=("Arial", 10, "bold"), style='Config.TLabel').grid(
                                 row=row, column=0, sticky=tk.W, padx=10, pady=2)
                    row += 1
                    for key, val in metrics.items():
                        display_key = key.replace('_', ' ').title()
                        ttk.Label(quality_frame, text=f"  {display_key}:",
                                 font=("Arial", 9), style='Config.TLabel').grid(
                                     row=row, column=0, sticky=tk.W, padx=20, pady=1)
                        if isinstance(val, float):
                            ttk.Label(quality_frame, text=f"{val:.3f}",
                                     font=("Arial", 9), style='Config.TLabel').grid(
                                         row=row, column=1, sticky=tk.W, padx=10, pady=1)
                        else:
                            ttk.Label(quality_frame, text=str(val),
                                     font=("Arial", 9), style='Config.TLabel').grid(
                                         row=row, column=1, sticky=tk.W, padx=10, pady=1)
                        row += 1

        # Layer 4: Composite Stats
        composite = stats.get('composite', {})
        if composite:
            composite_frame = ttk.LabelFrame(self.stats_content_frame, text="🎯 Composite Metrics", style='TLabelframe')
            composite_frame.pack(fill=tk.X, padx=10, pady=5)

            row = 0
            for key, val in composite.items():
                display_key = key.replace('_', ' ').title()
                ttk.Label(composite_frame, text=f"{display_key}:",
                         font=("Arial", 10, "bold"), style='Config.TLabel').grid(
                             row=row, column=0, sticky=tk.W, padx=10, pady=2)
                if isinstance(val, float):
                    ttk.Label(composite_frame, text=f"{val:.3f}",
                             font=("Arial", 10), style='Config.TLabel').grid(
                                 row=row, column=1, sticky=tk.W, padx=10, pady=2)
                else:
                    ttk.Label(composite_frame, text=str(val),
                             font=("Arial", 10), style='Config.TLabel').grid(
                                 row=row, column=1, sticky=tk.W, padx=10, pady=2)
                row += 1

        # Skills and Badges
        skills = profile.get('skills', [])
        badges = profile.get('badges', [])
        if skills or badges:
            extras_frame = ttk.LabelFrame(self.stats_content_frame, text="🏆 Skills & Badges", style='TLabelframe')
            extras_frame.pack(fill=tk.X, padx=10, pady=5)

            if skills:
                ttk.Label(extras_frame, text=f"Skills: {', '.join(skills)}",
                         font=("Arial", 9), style='Config.TLabel').pack(anchor=tk.W, padx=10, pady=2)

            if badges:
                ttk.Label(extras_frame, text=f"Badges: {', '.join(badges)}",
                         font=("Arial", 9), style='Config.TLabel').pack(anchor=tk.W, padx=10, pady=2)

    def populate_skills_display(self):
        """Populate the skills display with runtime AND evaluation skills for comparison."""
        for widget in self.skills_content_frame.winfo_children():
            widget.destroy()

        model_name = self.current_model_for_stats
        if not model_name:
            ttk.Label(self.skills_content_frame, text="Select a model to view skills.", style='Config.TLabel').pack(pady=20)
            return

        # Load comprehensive variant data using unified loader for consistency
        try:
            from config import load_complete_variant_data
            variant_data = load_complete_variant_data(model_name)

            runtime_skills = variant_data["skills"]["runtime"]
            eval_skills = variant_data["skills"]["evaluation"]
            tool_prof = variant_data["tool_proficiency"]
            inherited_from = variant_data["lineage"]["inherited_from"]

            log_message(f"[ModelsTab] Loaded complete data for {model_name} - Runtime: {len(runtime_skills)}, Eval: {len(eval_skills)}, Prof: {len(tool_prof)}")
        except Exception as e:
            log_message(f"MODELS_TAB ERROR: Failed to get skills: {e}")
            runtime_skills = {}
            eval_skills = {}
            tool_prof = {}
            inherited_from = None

        # Merge runtime, evaluation, and proficiency skills
        all_skills = set(list(runtime_skills.keys()) + list(eval_skills.keys()) + list(tool_prof.keys()))

        # If no skills at all, show message
        if not all_skills:
            ttk.Label(
                self.skills_content_frame,
                text="No skill data available.\n\nUse the model in Custom Code tab with Training Mode enabled to collect runtime data,\nor run evaluations in the Evaluation tab.",
                style='Config.TLabel',
                wraplength=600
            ).pack(pady=20, padx=20)
            return

        # Header
        header_frame = ttk.Frame(self.skills_content_frame, style='Category.TFrame')
        header_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(
            header_frame,
            text=f"🛠️ Skills & Proficiency: {model_name}",
            font=("Arial", 14, "bold"),
            style='CategoryPanel.TLabel'
        ).pack(anchor=tk.W, pady=(0, 5))

        ttk.Label(
            header_frame,
            text="Runtime (actual usage) | Evaluation (test results) | Proficiency (F-AAA grades)",
            font=("Arial", 9),
            style='Config.TLabel',
            foreground='#888888'
        ).pack(anchor=tk.W)

        # Phase 3.1: Show inheritance indicator if skills are inherited
        if inherited_from:
            ttk.Label(
                header_frame,
                text=f"🔗 Skills inherited from: {inherited_from} (same lineage)",
                font=("Arial", 9, "italic"),
                style='Config.TLabel',
                foreground='#61dafb'
            ).pack(anchor=tk.W, pady=(5, 0))

        # NEW: Show class-level required skills
        self._show_class_skills_section(model_name)

        # Categorize skills
        verified_runtime = []  # High runtime success
        unverified_eval = []  # Good eval but no/low runtime usage
        failed_runtime = []  # Poor runtime success
        no_data = []  # Skills with no meaningful data

        for skill in sorted(all_skills):
            runtime_data = runtime_skills.get(skill, {})
            eval_data = eval_skills.get(skill, {})
            prof_data = tool_prof.get(skill, {})  # Phase 2.1: Add proficiency data

            runtime_rate = runtime_data.get('success_rate', 0)
            runtime_calls = runtime_data.get('total_calls', 0)
            eval_status = eval_data.get('status', 'Unknown')

            if runtime_calls >= 3:  # Has meaningful runtime data
                if runtime_rate >= 80:
                    verified_runtime.append((skill, runtime_data, eval_data, prof_data))
                else:
                    failed_runtime.append((skill, runtime_data, eval_data, prof_data))
            elif eval_status in ['Verified', 'Partial']:
                unverified_eval.append((skill, runtime_data, eval_data, prof_data))
            else:
                no_data.append((skill, runtime_data, eval_data, prof_data))

        # Summary
        summary_frame = ttk.Frame(self.skills_content_frame, style='Category.TFrame')
        summary_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Label(
            summary_frame,
            text=f"✅ Verified (Runtime): {len(verified_runtime)} | ⚠️ Claimed (Eval only): {len(unverified_eval)} | ❌ Failed (Runtime): {len(failed_runtime)}",
            font=("Arial", 10),
            style='Config.TLabel'
        ).pack(anchor=tk.W)

        # Section 1: Verified Runtime Skills (Green - High Confidence)
        if verified_runtime:
            section_label = ttk.Label(
                self.skills_content_frame,
                text="✅ Verified Skills (Runtime Success ≥80%)",
                font=("Arial", 12, "bold"),
                foreground="#00ff00"
            )
            section_label.pack(anchor=tk.W, padx=10, pady=(10, 5))

            for skill, runtime_data, eval_data, prof_data in verified_runtime:
                self._create_skill_comparison_frame(skill, runtime_data, eval_data, prof_data, "#00ff00", "✅")

        # Section 2: Claimed Skills (Yellow - Unverified)
        if unverified_eval:
            section_label = ttk.Label(
                self.skills_content_frame,
                text="⚠️ Claimed Skills (Evaluation Only - Not Verified in Runtime)",
                font=("Arial", 12, "bold"),
                foreground="#ffff00"
            )
            section_label.pack(anchor=tk.W, padx=10, pady=(10, 5))

            for skill, runtime_data, eval_data, prof_data in unverified_eval:
                self._create_skill_comparison_frame(skill, runtime_data, eval_data, prof_data, "#ffff00", "⚠️")

        # Section 3: Failed Runtime Skills (Red - Needs Training)
        if failed_runtime:
            section_label = ttk.Label(
                self.skills_content_frame,
                text="❌ Failed Skills (Runtime Success <80% - Needs Training)",
                font=("Arial", 12, "bold"),
                foreground="#ff6b6b"
            )
            section_label.pack(anchor=tk.W, padx=10, pady=(10, 5))

            for skill, runtime_data, eval_data, prof_data in failed_runtime:
                self._create_skill_comparison_frame(skill, runtime_data, eval_data, prof_data, "#ff6b6b", "❌")

    def _show_class_skills_section(self, model_name: str):
        """Show required skills for current class level and progression to next"""
        try:
            from config import load_model_profile
            import json
            from pathlib import Path

            profile = load_model_profile(model_name)
            if not profile:
                return

            assigned_type = profile.get('assigned_type', '')
            current_class = profile.get('class_level', 'novice')

            if not assigned_type or assigned_type == 'unassigned':
                return

            # Load type catalog
            catalog_path = Path(__file__).parent.parent.parent / "type_catalog_v2.json"
            if not catalog_path.exists():
                return

            with open(catalog_path, 'r') as f:
                type_catalog = json.load(f)

            # Find type definition
            type_def = None
            for t in type_catalog.get('types', []):
                if t.get('id') == assigned_type:
                    type_def = t
                    break

            if not type_def:
                return

            classes = type_def.get('classes', {})
            current_class_info = classes.get(current_class, {})
            required_skills = current_class_info.get('required_skills', [])

            if not required_skills:
                return

            # Create class skills section
            class_section = ttk.LabelFrame(
                self.skills_content_frame,
                text=f"📚 Class Skills: {current_class.replace('_', ' ').title()} ({assigned_type.title()})",
                style='TLabelframe'
            )
            class_section.pack(fill=tk.X, padx=10, pady=(10, 5))

            desc_frame = ttk.Frame(class_section, style='Category.TFrame')
            desc_frame.pack(fill=tk.X, padx=10, pady=5)

            ttk.Label(
                desc_frame,
                text=f"Required skills for current class level:",
                font=("Arial", 9),
                style='Config.TLabel',
                foreground='#888888'
            ).pack(anchor=tk.W)

            # Show required skills with status indicators
            for skill in required_skills:
                skill_row = ttk.Frame(desc_frame, style='Category.TFrame')
                skill_row.pack(fill=tk.X, pady=2)

                # Check if skill is verified in tool proficiency
                tool_prof = profile.get('tool_proficiency', {})
                skill_prof = tool_prof.get(skill, {})
                grade = skill_prof.get('grade', 'F')
                score = skill_prof.get('score', 0.0)

                # Status icon based on grade
                if grade in ['AAA', 'AA', 'A']:
                    icon = "✅"
                    status_color = "#00ff00"
                    status_text = "Mastered"
                elif grade in ['B', 'C']:
                    icon = "⚠️"
                    status_color = "#ffaa00"
                    status_text = "In Progress"
                else:
                    icon = "○"
                    status_color = "#888888"
                    status_text = "Not Started"

                ttk.Label(
                    skill_row,
                    text=f"{icon} {skill}",
                    font=("Arial", 10),
                    style='Config.TLabel',
                    width=25
                ).pack(side=tk.LEFT, padx=(10, 5))

                # Progress bar
                progress_canvas = tk.Canvas(skill_row, width=150, height=15, bg='#2b2b2b', highlightthickness=0)
                progress_canvas.pack(side=tk.LEFT, padx=5)

                # Draw progress bar background
                progress_canvas.create_rectangle(0, 0, 150, 15, fill='#444444', outline='#666666')

                # Draw progress fill
                fill_width = int(150 * score)
                if fill_width > 0:
                    fill_color = "#00ff00" if grade in ['AAA', 'AA', 'A'] else "#ffaa00" if grade in ['B', 'C'] else "#666666"
                    progress_canvas.create_rectangle(0, 0, fill_width, 15, fill=fill_color, outline='')

                # Draw percentage text
                progress_canvas.create_text(75, 7, text=f"{score:.0%}", fill='white', font=("Arial", 8, "bold"))

                ttk.Label(
                    skill_row,
                    text=f"[{grade}] {status_text}",
                    font=("Arial", 9),
                    foreground=status_color
                ).pack(side=tk.LEFT, padx=5)

            # Show next class requirements
            class_order = ['novice', 'skilled', 'adept', 'expert', 'master', 'grand_master']
            if current_class in class_order:
                current_idx = class_order.index(current_class)
                if current_idx < len(class_order) - 1:
                    next_class = class_order[current_idx + 1]
                    next_class_info = classes.get(next_class, {})
                    next_skills = next_class_info.get('required_skills', [])

                    if next_skills:
                        next_section = ttk.Frame(class_section, style='Category.TFrame')
                        next_section.pack(fill=tk.X, padx=10, pady=(10, 5))

                        ttk.Label(
                            next_section,
                            text=f"🎯 Next Class: {next_class.replace('_', ' ').title()}",
                            font=("Arial", 10, "bold"),
                            style='Config.TLabel',
                            foreground='#61dafb'
                        ).pack(anchor=tk.W)

                        new_skills = [s for s in next_skills if s not in required_skills]
                        if new_skills:
                            ttk.Label(
                                next_section,
                                text=f"Additional skills required: {', '.join(new_skills)}",
                                font=("Arial", 9),
                                style='Config.TLabel',
                                foreground='#888888'
                            ).pack(anchor=tk.W, padx=15)

        except Exception as e:
            log_message(f"[ModelsTab._show_class_skills_section] Error: {e}")

    def _create_skill_comparison_frame(self, skill, runtime_data, eval_data, prof_data, color, icon):
        """Phase 2.1: Create a frame showing runtime, eval, AND proficiency data (F-AAA grades)"""
        skill_frame = ttk.LabelFrame(
            self.skills_content_frame,
            text=f"{icon} {skill}",
            style='TLabelframe'
        )
        skill_frame.pack(fill=tk.X, padx=10, pady=3)

        # Create THREE columns: Runtime (left), Evaluation (middle), Proficiency (right)
        left_frame = ttk.Frame(skill_frame, style='Category.TFrame')
        left_frame.grid(row=0, column=0, sticky=tk.W, padx=10, pady=5)

        middle_frame = ttk.Frame(skill_frame, style='Category.TFrame')
        middle_frame.grid(row=0, column=1, sticky=tk.W, padx=10, pady=5)

        right_frame = ttk.Frame(skill_frame, style='Category.TFrame')
        right_frame.grid(row=0, column=2, sticky=tk.W, padx=10, pady=5)

        # Left: Runtime Data
        if runtime_data and runtime_data.get('total_calls', 0) > 0:
            ttk.Label(
                left_frame,
                text="Runtime Usage:",
                font=("Arial", 9, "bold"),
                foreground="#61dafb"
            ).grid(row=0, column=0, sticky=tk.W, columnspan=2)

            success_rate = runtime_data.get('success_rate', 0)
            ttk.Label(
                left_frame,
                text=f"{success_rate:.1f}% success",
                foreground=color,
                font=("Arial", 10, "bold")
            ).grid(row=1, column=0, sticky=tk.W, padx=(0, 10))

            ttk.Label(
                left_frame,
                text=f"({runtime_data.get('success_count', 0)}/{runtime_data.get('total_calls', 0)} calls)",
                style='Config.TLabel'
            ).grid(row=1, column=1, sticky=tk.W)
        else:
            ttk.Label(
                left_frame,
                text="Runtime: No usage data",
                font=("Arial", 9),
                foreground="#888888"
            ).grid(row=0, column=0, sticky=tk.W)

        # Middle: Evaluation Data
        if eval_data and eval_data.get('status'):
            ttk.Label(
                middle_frame,
                text="Evaluation:",
                font=("Arial", 9, "bold"),
                foreground="#61dafb"
            ).grid(row=0, column=0, sticky=tk.W, columnspan=2)

            eval_status = eval_data.get('status', 'Unknown')
            eval_color = "#00ff00" if eval_status == "Verified" else "#ffff00" if eval_status == "Partial" else "#888888"

            ttk.Label(
                middle_frame,
                text=eval_status,
                foreground=eval_color,
                font=("Arial", 10)
            ).grid(row=1, column=0, sticky=tk.W)
        else:
            ttk.Label(
                middle_frame,
                text="Evaluation: No data",
                font=("Arial", 9),
                foreground="#888888"
            ).grid(row=0, column=0, sticky=tk.W)

        # Right: Proficiency Grade (F-AAA)
        if prof_data:
            ttk.Label(
                right_frame,
                text="Proficiency:",
                font=("Arial", 9, "bold"),
                foreground="#61dafb"
            ).grid(row=0, column=0, sticky=tk.W, columnspan=2)

            grade = prof_data.get('grade', 'F')
            score = prof_data.get('score', 0.0)
            attempts = prof_data.get('attempts', 0)

            # Grade color helper (copied from custom_code_tab)
            def grade_color(g: str) -> str:
                colors = {
                    'AAA': '#00ff00',  # Green
                    'AA': '#7fff00',   # Yellow-green
                    'A': '#ffff00',    # Yellow
                    'B': '#ffa500',    # Orange
                    'C': '#ff6347',    # Red-orange
                    'F': '#ff0000'     # Red
                }
                return colors.get(g, '#888888')

            # Grade badge
            grade_frame = ttk.Frame(right_frame, style='Category.TFrame')
            grade_frame.grid(row=1, column=0, sticky=tk.W)

            ttk.Label(
                grade_frame,
                text=f"[{grade}]",
                foreground=grade_color(grade),
                font=("Arial", 12, "bold")
            ).pack(side=tk.LEFT, padx=(0, 10))

            # Progress bar
            progress_canvas = tk.Canvas(grade_frame, width=100, height=12, bg='#2b2b2b', highlightthickness=0)
            progress_canvas.pack(side=tk.LEFT)

            # Draw background
            progress_canvas.create_rectangle(0, 0, 100, 12, fill='#444444', outline='#666666')

            # Draw fill
            fill_width = int(100 * score)
            if fill_width > 0:
                progress_canvas.create_rectangle(0, 0, fill_width, 12, fill=grade_color(grade), outline='')

            # Score and attempts
            ttk.Label(
                right_frame,
                text=f"{score:.1%} success ({attempts} tests)",
                font=("Arial", 9),
                style='Config.TLabel'
            ).grid(row=2, column=0, sticky=tk.W)
        else:
            ttk.Label(
                right_frame,
                text="Grade: Not assessed",
                font=("Arial", 9),
                foreground="#888888"
            ).grid(row=0, column=0, sticky=tk.W)

        # Show errors if available
        errors = runtime_data.get("errors", [])
        if errors:
            error_text = "\n".join(errors[:3])  # Show max 3 errors
            error_label = ttk.Label(
                skill_frame,
                text=f"Recent errors: {error_text}",
                font=("Courier", 8),
                foreground="#ff6b6b",
                wraplength=600
            )
            error_label.grid(row=1, column=0, columnspan=3, sticky=tk.W, padx=10, pady=(0, 5))


    def populate_notes_list(self):
        """Populate the notes list for the current model."""
        for widget in self.notes_list_buttons_frame.winfo_children():
            widget.destroy()

        if not self.current_model_info:
            ttk.Label(self.notes_list_buttons_frame, text="Select a model", style='Config.TLabel').pack(pady=10)
            return

        notes = list_model_notes(self.current_model_info)

        if not notes:
            ttk.Label(self.notes_list_buttons_frame, text="No notes yet", style='Config.TLabel').pack(pady=10)
            return

        for note_name in notes:
            note_btn = ttk.Button(
                self.notes_list_buttons_frame,
                text=note_name,
                command=lambda n=note_name: self.load_note(n),
                style='Select.TButton'
            )
            note_btn.pack(fill=tk.X, pady=2, padx=5)

    def load_model_notes(self, variant_id: str):
        """Load notes for the selected variant and refresh the notes UI safely."""
        if not variant_id:
            return

        try:
            # Ensure we have model info for this variant
            info = self.current_model_info or {}
            if not info or info.get('variant_id') != variant_id:
                info = {
                    'name': variant_id,
                    'variant_id': variant_id,
                    'type': info.get('type', 'variant') if info else 'variant',
                    'profile': info.get('profile', {}) if info else {}
                }
                self.current_model_info = info

            info.setdefault('name', variant_id)
            info.setdefault('type', 'variant')

            self.current_model_for_notes = variant_id

            # Refresh list and, if present, load the first note into the editor
            self.populate_notes_list()
            notes = list_model_notes(info)
            if notes:
                first_note = notes[0]
                content = load_model_note(info, first_note)
                self.note_name_var.set(first_note)
                self.notes_text.delete(1.0, tk.END)
                self.notes_text.insert(1.0, content)
            else:
                self.note_name_var.set("")
                self.notes_text.delete(1.0, tk.END)
        except Exception as exc:
            log_message(f"[ModelsTab] load_model_notes error: {exc}")

    def save_note(self):
        """Save the current note for the selected model."""
        if not self.current_model_info:
            messagebox.showwarning("No Model Selected", "Please select a model first.")
            return

        note_name = self.note_name_var.get().strip()
        if not note_name:
            messagebox.showwarning("No Note Name", "Please enter a name for the note.")
            return

        content = self.notes_text.get(1.0, tk.END).strip()

        try:
            save_model_note(self.current_model_info, note_name, content)
            messagebox.showinfo("Note Saved", f"Note '{note_name}' saved for {self.current_model_info['name']}")
            self.populate_notes_list()
        except Exception as e:
            messagebox.showerror("Save Error", f"Failed to save note: {e}")

    def load_note(self, note_name):
        """Load a specific note for the current model."""
        if not self.current_model_info:
            return

        content = load_model_note(self.current_model_info, note_name)
        self.note_name_var.set(note_name)
        self.notes_text.delete(1.0, tk.END)
        self.notes_text.insert(1.0, content)

    def delete_note(self):
        """Delete the current note."""
        if not self.current_model_info:
            messagebox.showwarning("No Model Selected", "Please select a model first.")
            return

        note_name = self.note_name_var.get().strip()
        if not note_name:
            messagebox.showwarning("No Note Name", "Please enter the name of the note to delete.")
            return

        if messagebox.askyesno("Confirm Delete", f"Delete note '{note_name}'?"):
            if delete_model_note(self.current_model_info, note_name):
                messagebox.showinfo("Note Deleted", f"Note '{note_name}' deleted.")
                self.notes_text.delete(1.0, tk.END)
                self.note_name_var.set("")
                self.populate_notes_list()
            else:
                messagebox.showwarning("Not Found", f"Note '{note_name}' not found.")

    def display_model_info_from_dict(self, model_info):
        """Display model information for PyTorch/Trained models and populate the adapters tab."""
        self.current_model_info = model_info
        model_name = model_info["name"]
        model_type = model_info["type"]

        # Emit event for other panels to react to model selection
        try:
            import json
            payload = json.dumps({
                "model_name": model_name,
                "model_type": model_type,
                "is_ollama": False,
            })
            if hasattr(self, 'panel_types') and self.panel_types:
                self.panel_types.event_generate("<<ModelSelected>>", data=payload, when="tail")
            # Keep Collections fresh so new variants appear promptly
            self.refresh_collections_panel()
        except Exception:
            pass


        # --- Populate Overview Tab ---
        # When selecting a base model, clear any active variant context
        try:
            self._active_variant_id = ''
            if hasattr(self, 'active_variant_var'):
                self.active_variant_var.set('')
        except Exception:
            pass
        # Clear previous content
        for widget in self.overview_tab_frame.winfo_children():
            widget.destroy()
        # Do NOT build variant header/actions for base models

        # Load config.json if available
        model_config = {}
        config_file = Path(model_info["path"]) / "config.json"
        if config_file.exists():
            try:
                with open(config_file) as f:
                    model_config = json.load(f)
            except: pass

        # Add parent model lineage management actions at the TOP (only for PyTorch models)
        if model_type == 'pytorch':
            try:
                self._build_parent_model_actions(model_name)
            except Exception as e:
                log_message(f"[ModelsTab.display_model_info_from_dict] Error building parent actions: {e}")

        info_frame = ttk.LabelFrame(self.overview_tab_frame, text="Base Model Information", style='TLabelframe')
        info_frame.pack(fill=tk.X, padx=10, pady=10)
        info_frame.columnconfigure(1, weight=1)

        # Display base model info
        row = 0
        ttk.Label(info_frame, text="Name:", font=("Arial", 10, "bold"), style='Config.TLabel').grid(row=row, column=0, sticky=tk.W, padx=10, pady=5)
        name_frame = ttk.Frame(info_frame)
        name_frame.grid(row=row, column=1, sticky=tk.W, padx=5, pady=5)
        ttk.Label(name_frame, text=model_name, font=("Arial", 10), style='Config.TLabel', foreground='#61dafb').pack(side=tk.LEFT)
        ttk.Button(name_frame, text="📎", command=self._copy_name_to_clipboard, style='Select.TButton', width=2).pack(side=tk.LEFT, padx=5)
        row += 1
        ttk.Label(info_frame, text="Type:", font=("Arial", 10, "bold"), style='Config.TLabel').grid(row=row, column=0, sticky=tk.W, padx=10, pady=5)
        ttk.Label(info_frame, text=("Trained" if model_type == 'trained' else "Base (PyTorch)"), font=("Arial", 10), style='Config.TLabel').grid(row=row, column=1, sticky=tk.W, padx=5, pady=5); row += 1
        if model_info.get('path'):
            ttk.Label(info_frame, text="Path:", font=("Arial", 10, "bold"), style='Config.TLabel').grid(row=row, column=0, sticky=tk.W, padx=10, pady=5)
            ttk.Label(info_frame, text=str(model_info['path']), font=("Arial", 9), style='Config.TLabel').grid(row=row, column=1, sticky=tk.W, padx=5, pady=5); row += 1
        if model_info.get('size'):
            ttk.Label(info_frame, text="Size:", font=("Arial", 10, "bold"), style='Config.TLabel').grid(row=row, column=0, sticky=tk.W, padx=10, pady=5)
            ttk.Label(info_frame, text=str(model_info['size']), font=("Arial", 10), style='Config.TLabel').grid(row=row, column=1, sticky=tk.W, padx=5, pady=5); row += 1

        # Architecture details from config.json
        if model_config:
            arch_rows = []
            if model_config.get('model_type'):
                arch_rows.append(("Architecture", model_config['model_type']))
            if model_config.get('num_hidden_layers') is not None:
                arch_rows.append(("Layers", model_config['num_hidden_layers']))
            if model_config.get('hidden_size') is not None:
                arch_rows.append(("Hidden Size", model_config['hidden_size']))
            if model_config.get('num_attention_heads') is not None:
                arch_rows.append(("Attention Heads", model_config['num_attention_heads']))
            if model_config.get('intermediate_size') is not None:
                arch_rows.append(("Intermediate Size", model_config['intermediate_size']))
            if model_config.get('max_position_embeddings') is not None:
                arch_rows.append(("Max Seq Length", model_config['max_position_embeddings']))
            if model_config.get('vocab_size') is not None:
                arch_rows.append(("Vocab Size", f"{model_config['vocab_size']:,}"))
            for k,v in arch_rows:
                ttk.Label(info_frame, text=f"{k}:", font=("Arial", 10, "bold"), style='Config.TLabel').grid(row=row, column=0, sticky=tk.W, padx=10, pady=2)
                ttk.Label(info_frame, text=str(v), font=("Arial", 10), style='Config.TLabel').grid(row=row, column=1, sticky=tk.W, padx=5, pady=2)
                row += 1

        # Behavior indicators (Compliance/Creativity/Coherence)
        # For PyTorch parents: aggregate from child variants; For variants: use own profile
        try:
            beh = {}
            variant_count = 0

            if model_type == 'pytorch':
                # Parent model - aggregate behavior from all child variants
                import config as C
                items = C.list_model_profiles() or []
                variants = [it.get('variant_id') for it in items if (it.get('base_model') or '') == model_name]

                # Collect behavior metrics from all variants
                compliance_vals = []
                creativity_vals = []
                coherence_vals = []

                for vid in variants:
                    prof = C.get_model_behavior_profile(vid) or {}
                    v_beh = prof.get('behavior') or {}

                    # Extract numeric values from percentage strings
                    try:
                        comp = v_beh.get('compliance', '')
                        if comp and isinstance(comp, str):
                            comp_val = float(comp.replace('%', '').strip())
                            compliance_vals.append(comp_val)
                    except: pass

                    try:
                        creat = v_beh.get('creativity', '')
                        if creat and isinstance(creat, str):
                            creat_val = float(creat.replace('%', '').strip())
                            creativity_vals.append(creat_val)
                    except: pass

                    try:
                        coher = v_beh.get('coherence', '')
                        if coher and isinstance(coher, str):
                            coher_val = float(coher.replace('%', '').strip())
                            coherence_vals.append(coher_val)
                    except: pass

                # Calculate averages
                if compliance_vals:
                    beh['compliance'] = f"{sum(compliance_vals) / len(compliance_vals):.2f}%"
                if creativity_vals:
                    beh['creativity'] = f"{sum(creativity_vals) / len(creativity_vals):.2f}%"
                if coherence_vals:
                    beh['coherence'] = f"{sum(coherence_vals) / len(coherence_vals):.2f}%"

                variant_count = len(variants)
            else:
                # Variant or trained model - use own profile
                from config import get_model_behavior_profile
                prof = get_model_behavior_profile(model_name) or {}
                beh = prof.get('behavior') or {}

            # Display behavior indicators if we have data
            if beh:
                beh_frame = ttk.LabelFrame(self.overview_tab_frame, text="Behavior Indicators" + (f" (avg of {variant_count} variants)" if model_type == 'pytorch' and variant_count > 0 else ""), style='TLabelframe')
                beh_frame.pack(fill=tk.X, padx=10, pady=6)
                def _badge(k: str) -> str:
                    v = (beh.get(k) or '0.00%')
                    return v
                ttk.Label(beh_frame, text=f"Compliance: {_badge('compliance')}", style='Config.TLabel').grid(row=0, column=0, sticky=tk.W, padx=10, pady=3)
                ttk.Label(beh_frame, text=f"Creativity: {_badge('creativity')}", style='Config.TLabel').grid(row=0, column=1, sticky=tk.W, padx=10, pady=3)
                ttk.Label(beh_frame, text=f"Coherence: {_badge('coherence')}", style='Config.TLabel').grid(row=0, column=2, sticky=tk.W, padx=10, pady=3)
        except Exception as e:
            log_message(f"[ModelsTab] Error displaying behavior indicators: {e}")

        # Performance indicators (Token-Speed)
        # For PyTorch parents: aggregate from child variants; For variants: use own stats
        try:
            tokps = None
            perf_variant_count = 0

            if model_type == 'pytorch':
                # Parent model - aggregate performance from all child variants
                import config as C
                items = C.list_model_profiles() or []
                variants = [it.get('variant_id') for it in items if (it.get('base_model') or '') == model_name]

                # Collect token speed from all variants
                speed_vals = []
                for vid in variants:
                    mp = C.load_model_profile(vid) or {}
                    stats = mp.get('stats') or {}
                    speed = stats.get('token_speed_ema_tok_per_s')
                    if speed is not None:
                        try:
                            speed_vals.append(float(speed))
                        except: pass

                # Calculate average
                if speed_vals:
                    tokps = sum(speed_vals) / len(speed_vals)
                    perf_variant_count = len(speed_vals)
            else:
                # Variant or trained model - use own stats
                from config import load_model_profile
                mp = load_model_profile(model_name) or {}
                stats = mp.get('stats') or {}
                tokps = stats.get('token_speed_ema_tok_per_s')

            perf_frame = ttk.LabelFrame(self.overview_tab_frame, text="Performance Indicators" + (f" (avg of {perf_variant_count} variants)" if model_type == 'pytorch' and perf_variant_count > 0 else ""), style='TLabelframe')
            perf_frame.pack(fill=tk.X, padx=10, pady=6)
            if tokps is not None:
                ttk.Label(perf_frame, text=f"Token Speed (EMA): {float(tokps):.2f} tok/s", style='Config.TLabel').grid(row=0, column=0, sticky=tk.W, padx=10, pady=3)
            else:
                ttk.Label(perf_frame, text="Token Speed (EMA): No data yet", style='Config.TLabel', foreground='#888888').grid(row=0, column=0, sticky=tk.W, padx=10, pady=3)
        except Exception as e:
            log_message(f"[ModelsTab] Error displaying performance indicators: {e}")

        # Promotion alert for any eligible variants under this base
        try:
            import config as C
            items = C.list_model_profiles() or []
            elig = []
            for it in items:
                if (it.get('base_model') or '') == model_name:
                    vid = it.get('variant_id')
                    ok, _tip = self._check_promotion_eligibility(vid)
                    if ok:
                        elig.append(vid)
            if elig:
                if not hasattr(self, '_promo_alerted_bases'):
                    self._promo_alerted_bases = set()
                if model_name not in self._promo_alerted_bases:
                    messagebox.showinfo('Promotion Unlocked', f"The following variants have earned a promotion to <Skilled>:\n\n- " + "\n- ".join(elig) + "\n\nHybrid Available: <NO>")
                    self._promo_alerted_bases.add(model_name)
        except Exception:
            pass

        # Lineage: Variants and assigned GGUFs for this base
        try:
            self._build_lineage_variants_section(model_name, parent_frame=self.overview_tab_frame)
        except Exception:
            pass

        # --- Populate Adapters Tab ---
        self._populate_adapters_tab(model_info)

        # --- Populate History Tab ---
        self._populate_history_tab(model_info)

        # --- Populate Other Tabs ---
        # Ensure skills/stats context reflects this selection
        self.current_model_for_stats = model_name
        self.raw_model_info_text.config(state=tk.NORMAL)
        self.raw_model_info_text.delete(1.0, tk.END)
        if model_config:
            self.raw_model_info_text.insert(1.0, f"Config.json:\n{'='*60}\n{json.dumps(model_config, indent=2)}")
        else:
            self.raw_model_info_text.insert(1.0, "No config.json found.")
        self.raw_model_info_text.config(state=tk.DISABLED)

        self.notes_text.delete(1.0, tk.END)
        self.note_name_var.set("")
        self.populate_notes_list()
        self.populate_stats_display()
        self.populate_skills_display()
        try:
            self._refresh_baselines_panel()
        except Exception:
            pass

        if hasattr(self, 'selected_model_label_eval'):
            self.selected_model_label_eval.config(text=f"Selected Model: {model_name}")
        if hasattr(self, 'eval_source_label'):
            src = "Trainable (PyTorch)"
            self.eval_source_label.config(text=f"Source: {src}")
        if hasattr(self, 'eval_parent_label'):
            if model_type == 'pytorch':
                self.eval_parent_label.config(text=f"Base-Model: {model_name}")
            else:
                self.eval_parent_label.config(text="Base-Model: unavailable")

    def display_level_info(self, base_model_name: str, level_data: dict):
        """Display Level overview: base info, adapters in level, eval/skill deltas, and export status."""
        # Clear overview
        for w in self.overview_tab_frame.winfo_children():
            w.destroy()
        info = ttk.LabelFrame(self.overview_tab_frame, text="Level Overview", style='TLabelframe')
        info.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        info.columnconfigure(1, weight=1)

        row = 0
        ttk.Label(info, text="Level Name:", font=("Arial", 10, "bold"), style='Config.TLabel').grid(row=row, column=0, sticky=tk.W, padx=10, pady=5)
        ttk.Label(info, text=level_data.get('name','(unnamed)'), style='Config.TLabel').grid(row=row, column=1, sticky=tk.W, padx=5, pady=5); row+=1
        ttk.Label(info, text="Base Model:", font=("Arial", 10, "bold"), style='Config.TLabel').grid(row=row, column=0, sticky=tk.W, padx=10, pady=5)
        ttk.Label(info, text=base_model_name, style='Config.TLabel', foreground='#61dafb').grid(row=row, column=1, sticky=tk.W, padx=5, pady=5); row+=1
        ttk.Label(info, text="Created:", font=("Arial", 10, "bold"), style='Config.TLabel').grid(row=row, column=0, sticky=tk.W, padx=10, pady=5)
        ttk.Label(info, text=level_data.get('created',''), style='Config.TLabel').grid(row=row, column=1, sticky=tk.W, padx=5, pady=5); row+=1
        # Adapters list
        adapters = [a.get('name') for a in (level_data.get('adapters') or []) if a.get('name')]
        ttk.Label(info, text="Adapters:", font=("Arial", 10, "bold"), style='Config.TLabel').grid(row=row, column=0, sticky=tk.W, padx=10, pady=5)
        ttk.Label(info, text=(', '.join(adapters) if adapters else 'None'), style='Config.TLabel').grid(row=row, column=1, sticky=tk.W, padx=5, pady=5); row+=1
        # Evaluation summary for primary adapter (first)
        primary = adapters[0] if adapters else None
        summary = "Unverified"
        if primary:
            try:
                baseline = load_baseline_report(base_model_name) or {}
                latest = load_latest_evaluation_report(primary) or {}
                if latest and baseline:
                    engine = EvaluationEngine(tests_dir=TRAINING_DATA_DIR / 'Test')
                    policy = get_regression_policy() or {}
                    threshold = float(policy.get('alert_drop_percent', 5.0))
                    cmp = engine.compare_models(baseline, latest, regression_threshold=threshold, improvement_threshold=threshold)
                    overall = cmp.get('overall', {})
                    summary = f"Overall: {overall.get('new','N/A')} (Δ {overall.get('delta','+0.00%')})"
            except Exception:
                pass
        ttk.Label(info, text="Evaluation:", font=("Arial", 10, "bold"), style='Config.TLabel').grid(row=row, column=0, sticky=tk.W, padx=10, pady=5)
        ttk.Label(info, text=summary, style='Config.TLabel').grid(row=row, column=1, sticky=tk.W, padx=5, pady=5); row+=1
        # Status (Ollama installed?)
        status = "Archived only"
        try:
            exports = level_data.get('exports') or []
            if exports:
                status = "Ollama: installed"
        except Exception:
            pass
        ttk.Label(info, text="Status:", font=("Arial", 10, "bold"), style='Config.TLabel').grid(row=row, column=0, sticky=tk.W, padx=10, pady=5)
        ttk.Label(info, text=status, style='Config.TLabel').grid(row=row, column=1, sticky=tk.W, padx=5, pady=5); row+=1
        # Actions
        act = ttk.Frame(info)
        act.grid(row=row, column=0, columnspan=2, sticky=tk.W, padx=8, pady=8)
        ttk.Button(act, text="Export to GGUF", style='Action.TButton', command=lambda b=base_model_name, lv=level_data: self._levels_export_to_gguf({"name":b, "path": self._find_base_path(b)}, lv)).pack(side=tk.LEFT, padx=5)
        ttk.Button(act, text="Open Level Folder", style='Select.TButton', command=lambda b=base_model_name, n=level_data.get('name',''): self._levels_open_folder(b, n)).pack(side=tk.LEFT, padx=5)

    def _find_base_path(self, base_model_name: str):
        # Helper to locate base model path from self.all_models
        try:
            for m in self.all_models:
                if m.get('name') == base_model_name and m.get('type') == 'pytorch':
                    return m.get('path')
        except Exception:
            pass
        return None

    def _toggle_levels(self, base_name: str):
        """Expand/collapse the levels list for a base in the right-side model list."""
        try:
            ui = self.levels_ui.get(base_name)
            if not ui:
                return
            container = ui['container']
            arrow = ui['arrow']
            expanded = bool(container.winfo_ismapped())
            if expanded:
                container.pack_forget()
                arrow.config(text='▶')
            else:
                container.pack(fill=tk.X)
                arrow.config(text='▼')
            self.levels_expanded[base_name] = not expanded
        except Exception:
            pass

    def _group_ollama_by_base(self, ollama_names: list) -> dict:
        """Group Ollama model names under base models if discoverable via level manifests; others under 'Unassigned'."""
        grouping = {}
        # Seed with Unassigned
        grouping['Unassigned'] = []
        try:
            # Map export names to base by scanning all bases' levels
            base_names = [m['name'] for m in self.all_models if m.get('type') == 'pytorch']
            export_to_base = {}
            for b in base_names:
                levels = self._discover_levels_for_base(b)
                for lv in levels:
                    for exp in (lv.get('exports') or []):
                        name = exp.get('name')
                        if name:
                            export_to_base[name] = b
            # Group ollama names
            for name in ollama_names:
                base = export_to_base.get(name)
                if base:
                    grouping.setdefault(base, []).append(name)
                else:
                    grouping['Unassigned'].append(name)
            # Remove Unassigned if empty
            if not grouping['Unassigned']:
                grouping.pop('Unassigned', None)
        except Exception:
            # Fallback: put all under Unassigned
            grouping = {'Unassigned': ollama_names}
        return grouping

    def _toggle_ollama_group(self, base_name: str):
        try:
            ui = self.ollama_ui.get(base_name)
            if not ui: return
            cont = ui['container']; arrow = ui['arrow']
            expanded = bool(cont.winfo_ismapped())
            if expanded:
                cont.pack_forget(); arrow.config(text='▶')
            else:
                cont.pack(fill=tk.X); arrow.config(text='▼')
            self.ollama_expanded[base_name] = not expanded
            # Update right pane scrollregion for smooth dynamic repositioning
            if hasattr(self, 'right_canvas'):
                self.right_frame.update_idletasks()
                self.right_canvas.configure(scrollregion=self.right_canvas.bbox("all"))
        except Exception:
            pass

    def _toggle_collections_group(self):
        """Expand/collapse the Collections panel."""
        try:
            if self.collections_expanded.get():
                self.collections_canvas.grid_remove()
                self.collections_scrollbar.grid_remove()
                self.collections_toggle_btn.config(text="▶")
                self.collections_expanded.set(False)
            else:
                self.collections_canvas.grid(row=2, column=0, sticky=tk.NSEW)
                self.collections_scrollbar.grid(row=2, column=1, sticky=tk.NS)
                self.collections_toggle_btn.config(text="▼")
                self.collections_expanded.set(True)
            # Update the outer scrollregion after layout change
            if hasattr(self, 'right_canvas'):
                self._update_right_scrollregion()
        except Exception:
            pass

    def _update_right_scrollregion(self):
        try:
            self.root.after_idle(lambda: self.right_canvas.configure(scrollregion=self.right_canvas.bbox("all")))
        except Exception:
            pass

    def _generate_training_from_eval_strict(self):
        """Generate strict JSONL training examples from the latest eval report and link them to the variant/lineage."""
        try:
            import time
            import config as C
            # Determine variant id (prefer active variant; else resolve owner from GGUF)
            vid = getattr(self, '_active_variant_id', '') or (self.current_model_for_stats or '')
            if not vid:
                messagebox.showwarning('Generate', 'No active variant. Select a variant first.')
                return
            # Load latest eval report for this variant
            report = C.load_latest_evaluation_report(vid) or {}
            if not report:
                messagebox.showwarning('Generate', f'No evaluation report found for {vid}. Run an evaluation first.')
                return
            suite = report.get('metadata', {}).get('suite') or 'UnknownSuite'
            results = report.get('results') or []
            if not results:
                messagebox.showwarning('Generate', 'Evaluation report contains no results.')
                return
            # Build JSONL examples for failed cases only
            lines = []
            fail_count = 0
            for r in results:
                if r.get('passed') is True:
                    continue
                tc = (r.get('test_case_obj') or {})
                user_input = tc.get('input') or r.get('test_case') or ''
                expected_tool = (r.get('expected') or {}).get('tool') or tc.get('expected_tool')
                expected_args = (r.get('expected') or {}).get('args') or tc.get('expected_args') or {}
                if not expected_tool or not isinstance(expected_args, dict):
                    continue
                tool_json = {"type": "tool_call", "name": expected_tool, "args": expected_args}
                # Assemble messages in strict format (assistant content is JSON string)
                entry = {
                    "messages": [
                        {"role": "user", "content": user_input},
                        {"role": "assistant", "content": json.dumps(tool_json, ensure_ascii=False)}
                    ],
                    "scenario": f"auto_from_eval::{suite}::{(r.get('skill') or 'unknown')}"
                }
                lines.append(json.dumps(entry, ensure_ascii=False))
                fail_count += 1
            if not lines:
                messagebox.showinfo('Generate', 'No failed cases to convert into training data. Great job!')
                return
            # Write under Tools category so Training UI picks it up
            ts = time.strftime('%Y%m%d_%H%M%S')
            fname = f"auto_{vid}_{suite}_{ts}.jsonl".replace(' ', '_')
            out_path = TRAINING_DATA_DIR / 'Tools' / fname
            out_path.write_text("\n".join(lines), encoding='utf-8')
            # Link to Model Profile
            try:
                mp = C.load_model_profile(vid) or {}
                ads = list(mp.get('auto_datasets') or [])
                if str(out_path) not in ads:
                    ads.append(str(out_path))
                mp['auto_datasets'] = ads
                C.save_model_profile(vid, mp)
            except Exception:
                pass
            # Refresh Training UI so it sees the new dataset (defaults to selected)
            try:
                tt = self.get_training_tab()
                if tt and hasattr(tt, 'refresh_all_panels'):
                    tt.refresh_all_panels()
                    # Auto-select the newly generated dataset in Training tab
                    try:
                        if hasattr(tt, 'select_jsonl_path'):
                            tt.select_jsonl_path(str(out_path), selected=True)
                    except Exception:
                        pass
                    # Persist selections/settings to Training Profile
                    try:
                        if hasattr(tt, 'save_active_training_profile'):
                            tt.save_active_training_profile()
                    except Exception:
                        pass
            except Exception:
                pass
            # Notify
            messagebox.showinfo('Generate', f'Created {fail_count} training examples -> {out_path}')
            # Auto pipeline (best-effort)
            if bool(getattr(self, 'auto_train_after_gen_var', tk.BooleanVar(value=False)).get()):
                try:
                    tt = self.get_training_tab()
                    if tt and hasattr(tt, 'runner_panel'):
                        tt.runner_panel.start_runner_training()
                except Exception:
                    pass
        except Exception as e:
            messagebox.showerror('Generate', f'Failed to generate training set: {e}')

    # --- Lineage variants summary -------------------------------------------
    def _build_lineage_variants_section(self, base_name: str, parent_frame=None):
        try:
            import config as C
            items = C.list_model_profiles() or []
            variants = [it.get('variant_id') for it in items if (it.get('base_model') or '') == base_name]
            if not variants:
                return
            frame = ttk.LabelFrame(parent_frame or self.overview_tab_frame, text="Lineage", style='TLabelframe')
            # Use pack by default in base/trained overview; caller may grid if needed
            try:
                frame.pack(fill=tk.X, padx=10, pady=6)
            except Exception:
                frame.grid(row=0, column=0, columnspan=2, sticky=tk.EW, padx=5, pady=6)
            row = 0
            ttk.Label(frame, text="Variants (Collections):", style='Config.TLabel', font=("Arial", 10, "bold")).grid(row=row, column=0, sticky=tk.W, padx=8, pady=(6,2)); row+=1
            for vid in sorted(variants):
                # Ensure lineage id exists (legacy backfill)
                try:
                    C.ensure_lineage_id(vid)
                except Exception:
                    pass
                # Class chip and clickable variant button
                try:
                    cls = C.get_variant_class(vid)
                    vrow = ttk.Frame(frame); vrow.grid(row=row, column=0, sticky=tk.W)
                    chip = tk.Label(vrow, text='  ', bg=self._class_to_color(cls))
                    chip.pack(side=tk.LEFT, padx=(16,6))
                    btn = ttk.Button(vrow, text=f"{vid}", style='Select.TButton', command=lambda v=vid: self._open_variant_from_lineage(v))
                    btn.pack(side=tk.LEFT)
                except Exception:
                    ttk.Label(frame, text=f" • {vid}", style='Config.TLabel').grid(row=row, column=0, sticky=tk.W, padx=16, pady=1)
                row += 1
                # Assigned artifacts for THIS SPECIFIC VARIANT ONLY (Ollama tags + Local GGUFs)
                tags = []
                local_artifacts = []
                try:
                    # Get artifacts for this variant only (not entire lineage)
                    local_artifacts = C.get_local_artifacts_by_variant(vid) or []

                    # Get Ollama tags for this variant only
                    data = C.load_ollama_assignments() or {}
                    entry = data.get(vid)
                    if isinstance(entry, dict):
                        tags = entry.get('tags') or []
                    elif isinstance(entry, list):
                        tags = entry
                except Exception:
                    tags = []
                    local_artifacts = []
                # Display Ollama tags
                if tags:
                    for tg in tags:
                        trow = ttk.Frame(frame); trow.grid(row=row, column=0, sticky=tk.W)
                        ttk.Label(trow, text=f"🔶 Assigned:", style='Config.TLabel', foreground='#bbbbbb').pack(side=tk.LEFT, padx=(22,6))
                        ttk.Button(trow, text=tg, style='Select.TButton', command=lambda tag=tg: self.display_model_info({'name':tag,'type':'ollama'})).pack(side=tk.LEFT)
                        row += 1
                # Display Local GGUFs
                if local_artifacts:
                    for art in local_artifacts:
                        gguf_path = art.get('gguf', '')
                        quant = art.get('quant', '')
                        if gguf_path:
                            grow = ttk.Frame(frame); grow.grid(row=row, column=0, sticky=tk.W)
                            ttk.Label(grow, text=f"🟩 Assigned:", style='Config.TLabel', foreground='#bbbbbb').pack(side=tk.LEFT, padx=(22,6))
                            gguf_name = Path(gguf_path).name
                            ttk.Button(grow, text=f"{gguf_name} ({quant})", style='Select.TButton', command=lambda p=gguf_path: self.display_local_gguf(p)).pack(side=tk.LEFT)
                            row += 1
                # Show "None" only if no assignments at all
                if not tags and not local_artifacts:
                    ttk.Label(frame, text=f"    Assigned: None", style='Config.TLabel', foreground='#bbbbbb').grid(row=row, column=0, sticky=tk.W, padx=22, pady=(0,4)); row+=1
        except Exception as e:
            try:
                log_message(f"MODELS_TAB: Lineage variants section error: {e}")
            except Exception:
                pass

    def _open_variant_from_lineage(self, variant_id: str):
        try:
            import config as C
            mp = C.load_model_profile(variant_id) or {}
            item = {"variant_id": variant_id, "base_model": mp.get('base_model'), "assigned_type": mp.get('assigned_type')}
            self._on_collection_pick(item)
        except Exception:
            pass

    # --- Overview Header & Variant Actions ----------------------------------
    def _build_overview_header(self):
        try:
            # Only render header/actions if a Variant is active
            vid = getattr(self, '_active_variant_id', '') or ''
            if not vid:
                return
            header = ttk.Frame(self.overview_tab_frame)
            header.pack(fill=tk.X, padx=10, pady=(6, 0))
            # Active Variant banner (left) with class chip
            if not hasattr(self, 'active_variant_var'):
                self.active_variant_var = tk.StringVar(value="")
            try:
                import config as C
                cls = C.get_variant_class(vid)
                chip = tk.Label(header, text='  ', bg=self._class_to_color(cls))
                chip.pack(side=tk.LEFT, padx=(0,6))
            except Exception:
                pass
            ttk.Label(header, textvariable=self.active_variant_var, style='Config.TLabel', foreground='#ffd43b').pack(side=tk.LEFT)

            # XP and Class Progress (Section 1: XP/Grades/Promotions)
            try:
                from xp_calculator import get_current_xp, get_xp_to_next_class
                current_xp = get_current_xp(vid)
                xp_info = get_xp_to_next_class(vid)

                # XP badge
                xp_text = f"XP: {current_xp:,}"
                if xp_info.get('xp_required', 0) > 0:
                    xp_text += f" / {xp_info.get('xp_required', 0):,}"

                xp_label = ttk.Label(header, text=xp_text, style='Config.TLabel', foreground='#00d4ff')
                xp_label.pack(side=tk.LEFT, padx=(10,0))

                # Progress percentage
                progress_pct = xp_info.get('progress_percent', 0.0)
                if progress_pct < 100:
                    prog_label = ttk.Label(
                        header,
                        text=f"({progress_pct:.1f}%)",
                        style='Config.TLabel',
                        foreground='#aaaaaa'
                    )
                    prog_label.pack(side=tk.LEFT, padx=(4,0))
            except Exception as e:
                # Silently skip if XP system not available
                pass

            # Parent base summary (center)
            try:
                from config import load_model_profile
                mp = load_model_profile(vid) or {}
                base = mp.get('base_model') or ''
                if base:
                    ttk.Label(header, text=f"  • Parent: {base}", style='Config.TLabel').pack(side=tk.LEFT, padx=(10,0))
            except Exception:
                pass

            # Actions (right)
            act = ttk.Frame(header)
            act.pack(side=tk.RIGHT)
            self.btn_create_gguf = ttk.Button(act, text="Create GGUF for Variant", style='Action.TButton', command=self._create_gguf_for_active_variant)
            self.btn_create_gguf.pack(side=tk.LEFT, padx=(0,6))
            self.btn_delete_variant = ttk.Button(act, text="Delete Variant", style='Select.TButton', command=self._delete_active_variant)
            self.btn_delete_variant.pack(side=tk.LEFT)

            # Evolution Options button (opens comprehensive dialog)
            self.btn_evolution = ttk.Button(act, text="Evolution Options", style='Action.TButton', command=self._open_evolution_options)
            self.btn_evolution.pack(side=tk.LEFT, padx=(6,0))

            # Brain Map button (visualize system as neural network)
            self.btn_brain_map = ttk.Button(act, text="🧠 Brain Map", style='Action.TButton', command=self._open_brain_map)
            self.btn_brain_map.pack(side=tk.LEFT, padx=(6,0))
            self._refresh_overview_actions_state()
            # Attach a simple tooltip on hover explaining why Create is disabled
            try:
                self._attach_simple_tooltip(self.btn_create_gguf, lambda: getattr(self, '_create_gguf_tooltip_text', '') or '')
            except Exception:
                pass
            # Tooltip for evolution guidance
            try:
                self._attach_simple_tooltip(self.btn_evolution, lambda: getattr(self, '_evolution_tooltip_text', 'View promotion eligibility, hybrid creation, and parameter expansion options'))
            except Exception as e:
                log_message(f"[ModelsTab._build_overview_header] Error attaching evolution tooltip: {e}")
        except Exception as e:
            log_message(f"[ModelsTab._build_overview_header] Error building overview header: {e}")
            import traceback
            traceback.print_exc()

    def _refresh_overview_actions_state(self):
        try:
            vid = getattr(self, '_active_variant_id', '') or ''
            # default states
            state_create = tk.DISABLED
            state_delete = tk.DISABLED
            state_evolution = tk.DISABLED
            if vid:
                state_delete = tk.NORMAL
                # Always allow Create; provide informative tooltip if an assignment exists
                state_create = tk.NORMAL
                # Always enable Evolution Options (eligibility shown inside dialog)
                state_evolution = tk.NORMAL
                try:
                    import config as C
                    lid = C.get_lineage_id(vid) or C.ensure_lineage_id(vid)
                    tags = C.get_assigned_tags_by_lineage(lid)
                    if tags:
                        self._create_gguf_tooltip_text = (
                            f"Existing tag(s): {', '.join(tags)}. You will be prompted to replace it or save a Local GGUF."
                        )
                    else:
                        self._create_gguf_tooltip_text = ''
                except Exception:
                    self._create_gguf_tooltip_text = ''
            if hasattr(self, 'btn_create_gguf'):
                self.btn_create_gguf.config(state=state_create)
            if hasattr(self, 'btn_delete_variant'):
                self.btn_delete_variant.config(state=state_delete)
            if hasattr(self, 'btn_evolution'):
                self.btn_evolution.config(state=state_evolution)
        except Exception:
            pass

    def _build_parent_model_actions(self, base_model_name: str):
        """
        Build action bar with lineage management buttons for PyTorch parent models.
        Shows buttons for ALL PyTorch models (enables lineage management even if no variants exist yet).

        Args:
            base_model_name: Name of the parent base model
        """
        try:
            from registry.bundle_loader import find_bundle_by_name

            # Get bundle for this parent (if exists)
            bundle = find_bundle_by_name(base_model_name)
            variant_count = 0

            if bundle:
                bundle_variants = bundle.get('variants', [])
                variant_ids = [v.get('variant_id') for v in bundle_variants if v.get('variant_id')]
                variant_count = len(variant_ids)
                log_message(f"[ModelsTab._build_parent_model_actions] Creating actions for parent {base_model_name} with {variant_count} variants from bundle")
            else:
                log_message(f"[ModelsTab._build_parent_model_actions] Creating actions for parent {base_model_name} (no bundle yet)")

            # Store parent model name for button callbacks
            self._active_parent_model = base_model_name

            # Create header frame for parent model actions AT THE TOP
            header = ttk.Frame(self.overview_tab_frame)
            header.pack(fill=tk.X, padx=10, pady=(10, 6))

            # Left side - Parent model name
            ttk.Label(
                header,
                text=f"Parent Model: {base_model_name}",
                style='Config.TLabel',
                foreground='#ffd43b',
                font=("Arial", 11, "bold")
            ).pack(side=tk.LEFT)

            # Right side - Actions
            act = ttk.Frame(header)
            act.pack(side=tk.RIGHT)

            # Delete Parent + Lineage button
            self.btn_parent_delete = ttk.Button(
                act,
                text="🗑️ Delete Parent + Lineage",
                style='Select.TButton',
                command=lambda: self._delete_parent_and_lineage_for_parent(base_model_name)
            )
            self.btn_parent_delete.pack(side=tk.LEFT, padx=(0, 6))

            # Reset-Lineage button
            self.btn_parent_reset = ttk.Button(
                act,
                text="🔄 Reset Lineage",
                style='Action.TButton',
                command=lambda: self._reset_lineage_for_parent(base_model_name)
            )
            self.btn_parent_reset.pack(side=tk.LEFT, padx=(0, 6))

            # Archive-Lineage button
            self.btn_parent_archive = ttk.Button(
                act,
                text="📦 Archive Lineage",
                style='Action.TButton',
                command=lambda: self._archive_lineage_for_parent(base_model_name)
            )
            self.btn_parent_archive.pack(side=tk.LEFT)

            log_message(f"[ModelsTab._build_parent_model_actions] Created lineage management buttons for parent {base_model_name}")

        except Exception as e:
            log_message(f"[ModelsTab._build_parent_model_actions] Error: {e}")
            import traceback
            traceback.print_exc()

    # --- Minimal tooltip helper ---------------------------------------------
    def _attach_simple_tooltip(self, widget, text_getter):
        tw = {'win': None}
        def show_tooltip(event=None):
            try:
                txt = text_getter() if callable(text_getter) else str(text_getter)
            except Exception:
                txt = ''
            # Only show when disabled and text present
            try:
                if str(widget['state']) != 'disabled' or not txt:
                    return
            except Exception:
                if not txt:
                    return
            if tw['win'] is not None:
                return
            x = widget.winfo_rootx() + 10
            y = widget.winfo_rooty() + widget.winfo_height() + 6
            win = tk.Toplevel(widget)
            win.wm_overrideredirect(True)
            win.wm_geometry(f"+{x}+{y}")
            lbl = tk.Label(win, text=txt, bg="#333333", fg="#ffffff", padx=6, pady=3, relief='solid', borderwidth=1, justify=tk.LEFT)
            lbl.pack()
            tw['win'] = win
        def hide_tooltip(event=None):
            if tw['win'] is not None:
                try:
                    tw['win'].destroy()
                except Exception:
                    pass
                tw['win'] = None
        widget.bind("<Enter>", show_tooltip)
        widget.bind("<Leave>", hide_tooltip)
        widget.bind("<Button-1>", hide_tooltip)

    # --- Evolution Options (Section 1: XP/Grades/Promotions) ----------------
    def _open_evolution_options(self):
        """Open Evolution Options dialog for active variant."""
        try:
            vid = getattr(self, '_active_variant_id', '') or ''
            if not vid:
                messagebox.showwarning('Evolution Options', 'Select a variant from Collections first.')
                return

            # Log dialog opening
            try:
                from logger_util import log_promotion_event
                log_promotion_event(vid, 'evolution_dialog_opened', {'variant_id': vid})
            except Exception:
                pass

            # Import and show evolution dialog
            from Data.dialogs.evolution_options_dialog import EvolutionOptionsDialog
            dialog = EvolutionOptionsDialog(self.root, vid)
            result = dialog.show()

            # Handle dialog result
            if result and result.get('action') == 'promote':
                new_class = result.get('new_class', 'unknown')

                # Log promotion success
                try:
                    from logger_util import log_promotion_event
                    log_promotion_event(vid, 'promotion_completed', {
                        'variant_id': vid,
                        'new_class': new_class,
                        'method': 'evolution_dialog'
                    })
                except Exception:
                    pass

                # Comprehensive refresh: collections, header, overview
                try:
                    log_message(f"[ModelsTab._open_evolution_options] Refreshing UI after promotion to {new_class}")

                    # Refresh collections to show updated class badge
                    self.refresh_collections_panel()

                    # Rebuild header to show updated XP and class
                    self._build_overview_header()

                    # Refresh overview with updated promotion readiness
                    self._render_variant_overview()

                    log_message(f"[ModelsTab._open_evolution_options] UI refresh complete")
                except Exception as e:
                    log_message(f"[ModelsTab._open_evolution_options] Error during refresh: {e}")
                    import traceback
                    traceback.print_exc()

                messagebox.showinfo(
                    'Promotion Complete',
                    f"Successfully promoted to {new_class.title()}!\n\n"
                    "The variant has been updated and is ready for continued training.\n\n"
                    f"Your variant is now class: {new_class.title()}"
                )
            elif result and result.get('action') == 'hybrid_created':
                # Handle hybrid creation
                hybrid_id = result.get('hybrid_id', '')
                try:
                    from logger_util import log_promotion_event
                    log_promotion_event(vid, 'hybrid_created', {
                        'parent_id': vid,
                        'hybrid_id': hybrid_id
                    })
                except Exception:
                    pass

                # Refresh collections to show new hybrid
                try:
                    self.refresh_collections_panel()
                except Exception:
                    pass

                messagebox.showinfo(
                    'Hybrid Created',
                    f"Successfully created hybrid variant!\n\n"
                    f"Hybrid ID: {hybrid_id}"
                )

        except Exception as e:
            messagebox.showerror('Evolution Options', f"Error opening evolution dialog: {e}")

    # --- Old Promotion Methods (Deprecated - keeping for backward compatibility) ---
    def _check_promotion_eligibility(self, variant_id: str) -> tuple[bool, str]:
        """Return (eligible, tooltip_text) based on latest eval vs baseline and simple thresholds."""
        try:
            from config import load_baseline_report, load_latest_evaluation_report, get_regression_policy
            baseline = load_baseline_report(variant_id) or {}
            latest = load_latest_evaluation_report(variant_id) or {}
            if not baseline or not latest:
                return (False, "Run a baseline and an evaluation to unlock promotions.")
            eng = EvaluationEngine(tests_dir=TRAINING_DATA_DIR / 'Test')
            pol = get_regression_policy() or {}
            thr = float(pol.get('alert_drop_percent', 5.0))
            cmp = eng.compare_models(baseline, latest, regression_threshold=thr, improvement_threshold=thr)
            overall_delta = float(cmp.get('overall', {}).get('delta', '+0.00%').replace('%',''))
            regressions = cmp.get('regressions') or []
            try:
                jvr = float((latest.get('metrics', {}) or {}).get('json_valid_rate', '0%').replace('%',''))
            except Exception:
                jvr = 0.0
            try:
                svr = float((latest.get('metrics', {}) or {}).get('schema_valid_rate', '0%').replace('%',''))
            except Exception:
                svr = 0.0
            eligible = (overall_delta >= 5.0 and jvr >= 95.0 and svr >= 95.0 and len(regressions) == 0)
            tip = (
                f"Overall Δ: {overall_delta:+.2f}% • JSON: {jvr:.1f}% • Schema: {svr:.1f}%\n"
                + ("No regressions detected." if not regressions else f"Regressions: {len(regressions)}")
            )
            return (eligible, tip)
        except Exception:
            return (False, "Run a baseline and an evaluation to unlock promotions.")

    def _promote_variant(self):
        """Create a new Skilled variant from the active variant (novice) when eligibility is met."""
        try:
            vid = getattr(self, '_active_variant_id', '') or ''
            if not vid:
                return
            import config as C
            mp = C.load_model_profile(vid) or {}
            base = mp.get('base_model') or ''
            t_id = mp.get('assigned_type') or ''
            if not base or not t_id:
                messagebox.showwarning('Promotion', 'Variant profile missing base_model or assigned_type.')
                return
            # Derive new skilled variant id
            base_stub = C.derive_variant_name(base, t_id)  # e.g., Qwen2.5-0.5b_coder
            skilled_id = f"{base_stub}_skilled"
            # Avoid collision: append numeric suffix if needed
            existing = [it.get('variant_id') for it in (C.list_model_profiles() or [])]
            if skilled_id in existing:
                i = 2
                while f"{skilled_id}{i}" in existing:
                    i += 1
                skilled_id = f"{skilled_id}{i}"
            # Build model profile
            mp_new = {
                'trainee_name': skilled_id,
                'base_model': base,
                'assigned_type': t_id,
                'class_level': 'skilled',
                'parent_variant_id': vid,
            }
            C.save_model_profile(skilled_id, mp_new)
            # Ensure lineage id (ULID)
            C.ensure_lineage_id(skilled_id)
            # Build training profile by copying stickies from source
            try:
                tp_src = C.load_training_profile(vid) or {}
            except Exception:
                tp_src = {}
            tp_new = C.build_training_profile_from_type(skilled_id, base, t_id)
            # Copy sticky fields
            try:
                sp = tp_src.get('selected_prompts') or []
                ss = tp_src.get('selected_schemas') or []
                if sp:
                    tp_new['selected_prompts'] = sp
                if ss:
                    tp_new['selected_schemas'] = ss
            except Exception:
                pass
            C.save_training_profile(skilled_id, tp_new)
            # Refresh Collections and notify
            try:
                self.refresh_collections_panel()
            except Exception:
                pass
            messagebox.showinfo('Promotion', f"Skilled variant created: {skilled_id}\n\nYou can export a Skilled GGUF via Levels or Create GGUF when ready.")
        except Exception as e:
            messagebox.showerror('Promotion', f"Failed to create Skilled variant: {e}")

    def _create_gguf_for_active_variant(self):
        try:
            vid = getattr(self, '_active_variant_id', '') or ''
            if not vid:
                messagebox.showwarning('Create GGUF', 'Select a Variant from Collections first.')
                return
            from config import load_model_profile
            mp = load_model_profile(vid) or {}
            base_name = mp.get('base_model')
            if not base_name:
                messagebox.showerror('Create GGUF', 'Variant profile missing base_model.')
                return
            base_path = self._find_base_path(base_name)
            if not base_path:
                messagebox.showerror('Create GGUF', f"Base model path not found for '{base_name}'.")
                return
            # Ask quant and export
            self._export_base_to_gguf_dialog_for_variant(base_name, base_path, vid)
        except Exception as e:
            messagebox.showerror('Create GGUF', str(e))

    def _on_request_auto_export_reeval(self, event):
        """Handle request to export GGUF for a variant and then re-evaluate automatically."""
        try:
            import json as _json, config as C
            payload = _json.loads(getattr(event, 'data', '{}') or '{}')
            vid = payload.get('variant_id') or ''
            if not vid:
                return
            mp = C.load_model_profile(vid) or {}
            base_name = mp.get('base_model')
            if not base_name:
                messagebox.showwarning('Auto Export', 'Variant profile missing base_model. Aborting export.')
                return
            base_path = self._find_base_path(base_name)
            if not base_path:
                messagebox.showwarning('Auto Export', f"Base path not found for '{base_name}'.")
                return
            # Select active variant for consistency and enable auto re-eval
            self._active_variant_id = vid
            try:
                self.auto_reeval_after_export_var.set(True)
            except Exception:
                pass
            # Start export with a sane default quant
            self._run_export_base_to_gguf(base_path, 'q4_k_m', model_tag_override=vid)
        except Exception as e:
            log_message('[ModelsTab] _on_request_auto_export_reeval error:', e)
    def _export_base_to_gguf_dialog_for_variant(self, base_model_name: str, base_model_path, variant_id: str):
        win = tk.Toplevel(self.root); win.title('Export Base to GGUF (Variant)')
        f = ttk.Frame(win); f.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        ttk.Label(f, text=f"Export base '{base_model_name}' to GGUF for variant '{variant_id}'", style='Config.TLabel').grid(row=0, column=0, sticky=tk.W)
        ttk.Label(f, text="Quantization:", style='Config.TLabel').grid(row=1, column=0, sticky=tk.W, pady=(6,2))
        qvar = tk.StringVar(value='q4_k_m')
        combo = ttk.Combobox(f, textvariable=qvar, values=['q4_k_m','q5_k_m','q8_0'], state='readonly', width=12)
        combo.grid(row=1, column=1, sticky=tk.W)
        def go():
            win.destroy()
            target, outdir = self._prompt_export_target()
            if not target:
                return
            self._run_export_base_to_gguf(base_model_path, qvar.get(), model_tag_override=variant_id, target=target, outdir_override=outdir)
        ttk.Button(f, text='Start Export', command=go, style='Action.TButton').grid(row=2, column=1, sticky=tk.E, pady=(8,0))

    def _delete_active_variant(self):
        try:
            vid = getattr(self, '_active_variant_id', '') or ''
            if not vid:
                return
            if not messagebox.askyesno('Delete Variant', f"Delete variant '{vid}' and its training profile?"):
                return
            # Remove profiles and stats; keep models intact
            from config import _mp_path as _mppath, _tp_path as _tppath
            try:
                p = _mppath(vid)
                if p.exists(): p.unlink()
            except Exception: pass
            try:
                p2 = _tppath(vid)
                if p2.exists(): p2.unlink()
            except Exception: pass
            # Clear stats if present
            try:
                from config import DATA_DIR
                sp = (DATA_DIR / 'Stats' / f'{vid}.json')
                if sp.exists(): sp.unlink()
            except Exception: pass
            # Remove assignment mapping if present
            try:
                from config import load_ollama_assignments, save_ollama_assignments
                d = load_ollama_assignments() or {}
                if vid in d:
                    d.pop(vid, None)
                    save_ollama_assignments(d)
            except Exception: pass
            # Refresh UI
            self._active_variant_id = ''
            self.active_variant_var.set('')
            self.refresh_collections_panel()
            self._refresh_overview_actions_state()
            messagebox.showinfo('Delete Variant', 'Variant deleted.')
        except Exception as e:
            messagebox.showerror('Delete Variant', str(e))

    def _delete_parent_and_lineage(self):
        """Delete parent base model and all variants in the lineage (full wipe)."""
        try:
            vid = getattr(self, '_active_variant_id', '') or ''
            if not vid:
                return

            # Load variant to get base model and lineage
            import config as C
            profile = C.load_model_profile(vid)
            if not profile:
                messagebox.showwarning('Delete Parent + Lineage', 'Could not load variant profile.')
                return

            base_model = profile.get('base_model', '')
            lineage_id = profile.get('lineage_id', '')

            # Get all variants in lineage
            variants = []
            if lineage_id:
                variants = C.get_lineage_variants(lineage_id)
            if not variants and base_model:
                # Fallback to base model matching
                variants = C.get_base_model_variants(base_model)

            if not variants:
                messagebox.showwarning('Delete Parent + Lineage', 'No variants found to delete.')
                return

            # Confirm deletion with count
            msg = f"Delete parent '{base_model}' and ALL {len(variants)} variant(s) in lineage?\n\n"
            msg += "This will permanently delete:\n"
            msg += "• All model profiles\n"
            msg += "• All training profiles and stats\n"
            msg += "• All adapter directories\n"
            msg += "• All GGUF files\n"
            msg += "• All training ground data\n\n"
            msg += f"Variants: {', '.join(variants[:5])}"
            if len(variants) > 5:
                msg += f", ... and {len(variants) - 5} more"

            if not messagebox.askyesno('Delete Parent + Lineage', msg, icon='warning'):
                return

            # Delete all variants
            deleted_count = 0
            for variant_id in variants:
                try:
                    C.delete_variant_files(variant_id, include_models=True)
                    deleted_count += 1
                except Exception as e:
                    log_error(f"Error deleting variant {variant_id}: {e}")

            # Remove from ollama assignments
            try:
                d = C.load_ollama_assignments() or {}
                for variant_id in variants:
                    d.pop(variant_id, None)
                C.save_ollama_assignments(d)
            except Exception:
                pass

            # Remove from unified assignments
            try:
                assignments = C.load_unified_assignments() or {}
                for variant_id in variants:
                    assignments.pop(variant_id, None)
                C.save_unified_assignments(assignments)
            except Exception:
                pass

            # Delete parent base model directory if exists
            if base_model:
                try:
                    base_dir = C.MODELS_DIR / base_model
                    if base_dir.exists():
                        import shutil
                        shutil.rmtree(base_dir)
                except Exception as e:
                    log_error(f"Error deleting base model directory: {e}")

            # Refresh UI
            self._active_variant_id = ''
            self.active_variant_var.set('')
            self.refresh_collections_panel()
            self._refresh_overview_actions_state()

            messagebox.showinfo('Delete Parent + Lineage',
                              f'Successfully deleted {deleted_count} variant(s) and parent model.')
        except Exception as e:
            log_error(f"Error in _delete_parent_and_lineage: {e}")
            messagebox.showerror('Delete Parent + Lineage', str(e))

    def _reset_lineage(self):
        """Reset lineage: wipe stats, delete adapters/training grounds, generate new ULIDs, keep GGUFs."""
        try:
            vid = getattr(self, '_active_variant_id', '') or ''
            if not vid:
                return

            # Load variant to get lineage
            import config as C
            profile = C.load_model_profile(vid)
            if not profile:
                messagebox.showwarning('Reset Lineage', 'Could not load variant profile.')
                return

            lineage_id = profile.get('lineage_id', '')
            base_model = profile.get('base_model', '')

            # Get all variants in lineage
            variants = []
            if lineage_id:
                variants = C.get_lineage_variants(lineage_id)
            if not variants and base_model:
                # Fallback to base model matching
                variants = C.get_base_model_variants(base_model)

            if not variants:
                messagebox.showwarning('Reset Lineage', 'No variants found to reset.')
                return

            # Confirm reset with warning
            msg = f"Reset lineage for ALL {len(variants)} variant(s)?\n\n"
            msg += "This will:\n"
            msg += "• Delete all adapter directories\n"
            msg += "• Delete all training ground data\n"
            msg += "• Delete all stats files\n"
            msg += "• Generate new lineage IDs (ULIDs)\n"
            msg += "• Reset XP, scores, badges to zero\n"
            msg += "• Reset class level to Novice\n\n"
            msg += "PRESERVED:\n"
            msg += "• Model profiles (structure)\n"
            msg += "• GGUF files\n"
            msg += "• Base model assignments\n\n"
            msg += f"Variants: {', '.join(variants[:5])}"
            if len(variants) > 5:
                msg += f", ... and {len(variants) - 5} more"

            if not messagebox.askyesno('Reset Lineage', msg, icon='warning'):
                return

            # Generate new master lineage ID for entire family
            new_lineage_id = C.generate_ulid()

            # Generate new bundle ULID for the parent base model
            new_bundle_ulid = C.generate_ulid()

            log_message(f"MODELS_TAB: Resetting lineage - new lineage_id={new_lineage_id}, new bundle_ulid={new_bundle_ulid}")

            reset_count = 0
            for variant_id in variants:
                try:
                    # Delete adapter directories
                    variant_profile = C.load_model_profile(variant_id)
                    if variant_profile:
                        base = variant_profile.get('base_model', '')
                        if base:
                            base_dir = C.MODELS_DIR / base
                            if base_dir.exists():
                                import shutil
                                for adapter_dir in base_dir.glob("training_*"):
                                    sidecar = adapter_dir / ".variant.json"
                                    if sidecar.exists():
                                        try:
                                            data = json.loads(sidecar.read_text())
                                            if data.get('variant_id') == variant_id:
                                                shutil.rmtree(adapter_dir)
                                        except Exception:
                                            pass

                    # Delete training grounds
                    tg = C.MODEL_PROFILES_DIR / variant_id / "training_grounds"
                    if tg.exists():
                        import shutil
                        try:
                            shutil.rmtree(tg)
                        except Exception:
                            pass

                    # Delete stats files
                    stats = C.DATA_DIR / "Stats" / f"{variant_id}.json"
                    if stats.exists():
                        stats.unlink()

                    ts = C.MODELS_DIR / "training_stats" / f"{variant_id}_stats.json"
                    if ts.exists():
                        ts.unlink()

                    # Reset profile fields
                    if variant_profile:
                        variant_profile["lineage_id"] = new_lineage_id
                        variant_profile["xp"] = {'total': 0, 'history': []}
                        variant_profile["latest_eval_score"] = 0.0
                        variant_profile["stats"] = {}
                        variant_profile["skills"] = {}
                        variant_profile["badges"] = []
                        variant_profile["evolution_metadata"] = {}
                        variant_profile["class_level"] = "novice"

                        # Preserve: base_model, assigned_type, parameter_size_b, trainee_name
                        C.save_model_profile(variant_id, variant_profile)

                    # Archive old evaluation and baseline data
                    try:
                        from pathlib import Path
                        import shutil
                        from datetime import datetime

                        # Archive evaluations
                        evals_dir = C.MODELS_DIR / "evaluations"
                        if evals_dir.exists():
                            archive_dir = evals_dir / "archived" / datetime.now().strftime("%Y%m%d_%H%M%S")
                            archive_dir.mkdir(parents=True, exist_ok=True)

                            # Move all eval files for this variant
                            for eval_file in evals_dir.glob(f"*{variant_id}*.json"):
                                try:
                                    shutil.move(str(eval_file), str(archive_dir / eval_file.name))
                                    log_message(f"MODELS_TAB: Archived eval file: {eval_file.name}")
                                except Exception as e:
                                    log_message(f"MODELS_TAB: Failed to archive {eval_file.name}: {e}")

                        # Archive baselines
                        benchmarks_dir = C.MODELS_DIR / "benchmarks"
                        if benchmarks_dir.exists():
                            archive_dir = benchmarks_dir / "archived" / datetime.now().strftime("%Y%m%d_%H%M%S")
                            archive_dir.mkdir(parents=True, exist_ok=True)

                            # Move all baseline files for this variant
                            for baseline_file in benchmarks_dir.glob(f"*{variant_id}*.json"):
                                try:
                                    shutil.move(str(baseline_file), str(archive_dir / baseline_file.name))
                                    log_message(f"MODELS_TAB: Archived baseline file: {baseline_file.name}")
                                except Exception as e:
                                    log_message(f"MODELS_TAB: Failed to archive {baseline_file.name}: {e}")

                    except Exception as e:
                        log_message(f"MODELS_TAB: Error archiving eval/baseline data for {variant_id}: {e}")

                    # Update training profile lineage_id if exists
                    try:
                        tp = C.load_training_profile(variant_id)
                        if tp:
                            tp["lineage_id"] = new_lineage_id
                            C.save_training_profile(variant_id, tp)
                    except Exception:
                        pass

                    reset_count += 1
                except Exception as e:
                    log_error(f"Error resetting variant {variant_id}: {e}")

            # Update unified assignments with new lineage_id
            try:
                assignments = C.load_unified_assignments() or {}
                for variant_id in variants:
                    if variant_id in assignments:
                        assignments[variant_id]['lineage_id'] = new_lineage_id
                C.save_unified_assignments(assignments)
            except Exception:
                pass

            # Update or create bundle in registry with new ULIDs
            try:
                from registry.bundle_loader import BUNDLES_DIR
                from datetime import datetime

                # Find existing bundle for this base_model or create new one
                bundle_file = BUNDLES_DIR / f"{base_model}.json"

                if bundle_file.exists():
                    # Load existing bundle and update it
                    bundle = json.loads(bundle_file.read_text())
                    log_message(f"MODELS_TAB: Updating existing bundle for {base_model}")
                else:
                    # Create new bundle structure
                    bundle = {
                        "name": base_model,
                        "base_model": base_model,
                        "lineage_root": True,
                        "created_at": datetime.now().isoformat(),
                        "base_variant": {
                            "backend": "pytorch",
                            "model_path": f"Models/{base_model}",
                            "type": "base"
                        },
                        "variants": []
                    }
                    log_message(f"MODELS_TAB: Creating new bundle for {base_model}")

                # Update bundle with new ULID and lineage
                bundle["bundle_ulid"] = new_bundle_ulid
                bundle["updated_at"] = datetime.now().isoformat()

                # Update or create variant entries in bundle with new lineage_id
                existing_variant_ids = {v.get("variant_id") for v in bundle.get("variants", [])}

                for variant_entry in bundle.get("variants", []):
                    if variant_entry.get("variant_id") in variants:
                        variant_id = variant_entry.get("variant_id")
                        variant_entry["lineage_id"] = new_lineage_id
                        variant_entry["class_level"] = "novice"
                        variant_entry["skills"] = []
                        variant_entry["updated_at"] = datetime.now().isoformat()

                        # Ensure available_backends is populated with GGUF info
                        if "available_backends" not in variant_entry or not variant_entry["available_backends"].get("gguf"):
                            available_backends = variant_entry.get("available_backends", {})
                            gguf_files = list(C.GGUF_EXPORT_DIR.glob(f"{variant_id}*.gguf"))
                            if gguf_files:
                                gguf_path = gguf_files[0]
                                quant = "unknown"
                                for q in ["q4_k_m", "q4_k_s", "q5_k_m", "q5_k_s", "q8_0", "f16", "f32"]:
                                    if q in gguf_path.name.lower():
                                        quant = q
                                        break

                                available_backends["gguf"] = {
                                    "available": True,
                                    "path": str(gguf_path.relative_to(C.DATA_DIR.parent)),
                                    "quant": quant,
                                    "size_mb": gguf_path.stat().st_size // (1024 * 1024)
                                }
                                variant_entry["available_backends"] = available_backends

                        log_message(f"MODELS_TAB: Updated bundle entry for {variant_entry['variant_id']}")

                # Create entries for variants not in bundle
                for variant_id in variants:
                    if variant_id not in existing_variant_ids:
                        # Load profile to get variant details
                        vprofile = C.load_model_profile(variant_id)
                        if vprofile:
                            # Check for GGUF files for this variant
                            available_backends = {}
                            gguf_files = list(C.GGUF_EXPORT_DIR.glob(f"{variant_id}*.gguf"))
                            if gguf_files:
                                # Use the first GGUF found
                                gguf_path = gguf_files[0]
                                quant = "unknown"
                                # Try to extract quantization from filename
                                for q in ["q4_k_m", "q4_k_s", "q5_k_m", "q5_k_s", "q8_0", "f16", "f32"]:
                                    if q in gguf_path.name.lower():
                                        quant = q
                                        break

                                available_backends["gguf"] = {
                                    "available": True,
                                    "path": str(gguf_path.relative_to(C.DATA_DIR.parent)),
                                    "quant": quant,
                                    "size_mb": gguf_path.stat().st_size // (1024 * 1024)
                                }

                            new_entry = {
                                "variant_id": variant_id,
                                "lineage_id": new_lineage_id,
                                "assigned_type": vprofile.get("assigned_type", "unassigned"),
                                "backend": "ollama",
                                "tag": variant_id,
                                "class_level": "novice",
                                "skills": [],
                                "created_at": datetime.now().isoformat(),
                                "updated_at": datetime.now().isoformat(),
                                "metadata_ref": {
                                    "model_profile": f"Data/profiles/Models/{variant_id}.json",
                                    "training_profile": f"Data/profiles/Training/{variant_id}.json"
                                },
                                "available_backends": available_backends
                            }
                            bundle.setdefault("variants", []).append(new_entry)
                            log_message(f"MODELS_TAB: Created new bundle entry for {variant_id} with {len(available_backends)} backends")

                # Save updated bundle
                bundle_file.write_text(json.dumps(bundle, indent=2))
                log_message(f"MODELS_TAB: Saved bundle to {bundle_file}")

            except Exception as e:
                log_error(f"MODELS_TAB: Failed to update bundle registry: {e}")
                import traceback
                traceback.print_exc()

            # Refresh UI
            self.refresh_collections_panel()
            self._refresh_overview_actions_state()

            # Notify all registered callbacks that profiles were updated
            for variant_id in variants:
                C._notify_profile_updated(variant_id)

            # Close any open Model Preview popups to force refresh on next open
            try:
                # Try multiple ways to access custom_code_tab
                custom_code_tab = None

                # Method 1: via tab_instances (set by main app)
                if hasattr(self, 'tab_instances') and self.tab_instances:
                    custom_code_tab = self.tab_instances.get('custom_code_tab')

                # Method 2: via main_app
                if not custom_code_tab and hasattr(self, 'main_app') and self.main_app:
                    custom_code_tab = getattr(self.main_app, 'custom_code_tab', None)

                # Method 3: Search through root widget tree
                if not custom_code_tab:
                    try:
                        # Find custom_code_tab through widget hierarchy
                        for child in self.root.winfo_children():
                            if hasattr(child, 'custom_code_tab'):
                                custom_code_tab = child.custom_code_tab
                                break
                    except Exception:
                        pass

                # Close popup if found
                if custom_code_tab and hasattr(custom_code_tab, '_current_model_popup'):
                    popup = custom_code_tab._current_model_popup
                    if popup and popup.winfo_exists():
                        log_message(f"MODELS_TAB: Closing Model Preview popup after lineage reset")
                        popup.destroy()
                        custom_code_tab._current_model_popup = None
                else:
                    log_message(f"MODELS_TAB: Could not find custom_code_tab to close popup")

            except Exception as e:
                log_message(f"MODELS_TAB: Error closing popup after lineage reset: {e}")

            messagebox.showinfo('Reset Lineage',
                              f'Successfully reset {reset_count} variant(s).\nNew lineage ID: {new_lineage_id[:8]}...')
        except Exception as e:
            log_error(f"Error in _reset_lineage: {e}")
            messagebox.showerror('Reset Lineage', str(e))

    def _archive_lineage(self):
        """Archive entire lineage to collections directory."""
        try:
            vid = getattr(self, '_active_variant_id', '') or ''
            if not vid:
                return

            # Load variant to get lineage
            import config as C
            profile = C.load_model_profile(vid)
            if not profile:
                messagebox.showwarning('Archive Lineage', 'Could not load variant profile.')
                return

            lineage_id = profile.get('lineage_id', '')
            base_model = profile.get('base_model', '')

            # Get all variants in lineage
            variants = []
            if lineage_id:
                variants = C.get_lineage_variants(lineage_id)
            if not variants and base_model:
                # Fallback to base model matching
                variants = C.get_base_model_variants(base_model)

            if not variants:
                messagebox.showwarning('Archive Lineage', 'No variants found to archive.')
                return

            # Prompt for optional archive name
            archive_name = tk.simpledialog.askstring(
                'Archive Lineage',
                f'Archive {len(variants)} variant(s) from lineage?\n\n'
                f'Optional archive name (leave blank for auto-generated):',
                parent=self.root
            )

            if archive_name is None:  # User clicked Cancel
                return

            # Show progress message
            progress_msg = f"Archiving {len(variants)} variants...\n"
            progress_msg += "This may take a moment for large lineages."

            # Create progress dialog
            progress_dialog = tk.Toplevel(self.root)
            progress_dialog.title("Archiving Lineage")
            progress_dialog.geometry("400x150")
            progress_dialog.transient(self.root)
            progress_dialog.grab_set()

            ttk.Label(progress_dialog, text=progress_msg, style='Config.TLabel').pack(padx=20, pady=20)
            progress_bar = ttk.Progressbar(progress_dialog, mode='indeterminate')
            progress_bar.pack(padx=20, pady=10, fill=tk.X)
            progress_bar.start()

            # Archive in background (use after to avoid blocking)
            def do_archive():
                try:
                    archive_dir = C.archive_lineage(
                        lineage_id=lineage_id,
                        base_model=base_model,
                        variants=variants,
                        archive_name=archive_name if archive_name.strip() else None
                    )

                    progress_dialog.destroy()

                    # Ask if user wants to delete active lineage after archiving
                    msg = f"Archive created successfully!\n\n"
                    msg += f"Location: {archive_dir.name}\n"
                    msg += f"Variants: {len(variants)}\n\n"
                    msg += "Would you like to delete the active lineage data now?\n"
                    msg += "(The archive will be preserved in Collections)"

                    if messagebox.askyesno('Archive Complete', msg):
                        # Delete active lineage using the same logic as Delete Parent
                        deleted_count = 0
                        for variant_id in variants:
                            try:
                                C.delete_variant_files(variant_id, include_models=True)
                                deleted_count += 1
                            except Exception as e:
                                log_error(f"Error deleting variant {variant_id}: {e}")

                        # Remove from assignments
                        try:
                            d = C.load_ollama_assignments() or {}
                            for variant_id in variants:
                                d.pop(variant_id, None)
                            C.save_ollama_assignments(d)
                        except Exception:
                            pass

                        try:
                            assignments = C.load_unified_assignments() or {}
                            for variant_id in variants:
                                assignments.pop(variant_id, None)
                            C.save_unified_assignments(assignments)
                        except Exception:
                            pass

                        # Delete parent base model directory
                        if base_model:
                            try:
                                base_dir = C.MODELS_DIR / base_model
                                if base_dir.exists():
                                    import shutil
                                    shutil.rmtree(base_dir)
                            except Exception:
                                pass

                        # Refresh UI
                        self._active_variant_id = ''
                        self.active_variant_var.set('')
                        self.refresh_collections_panel()
                        self._refresh_overview_actions_state()

                        messagebox.showinfo('Lineage Archived & Deleted',
                                          f'Archived and deleted {deleted_count} variants.')
                    else:
                        messagebox.showinfo('Archive Complete',
                                          'Lineage archived successfully. Active data preserved.')

                except Exception as e:
                    progress_dialog.destroy()
                    log_error(f"Error archiving lineage: {e}")
                    messagebox.showerror('Archive Lineage', f'Error: {str(e)}')

            # Start archive after a short delay
            self.root.after(100, do_archive)

        except Exception as e:
            log_error(f"Error in _archive_lineage: {e}")
            messagebox.showerror('Archive Lineage', str(e))

    # --- Parent Model Lineage Management (wrappers for parent context) ---

    def _delete_parent_and_lineage_for_parent(self, base_model_name: str):
        """Delete parent model and all variants - uses bundle registry with fallback."""
        try:
            import config as C
            from registry.bundle_loader import find_bundle_by_name

            # Try to get bundle for this parent (authoritative source)
            bundle = find_bundle_by_name(base_model_name)
            variant_ids = []

            if bundle:
                # Get variants from bundle (safe, explicit list)
                bundle_variants = bundle.get('variants', [])
                variant_ids = [v.get('variant_id') for v in bundle_variants if v.get('variant_id')]
                log_message(f"[ModelsTab] Found {len(variant_ids)} variants in bundle for parent {base_model_name}")

            # Fallback: check for variants via base_model matching
            if not variant_ids:
                variant_ids = C.get_base_model_variants(base_model_name)
                if variant_ids:
                    log_message(f"[ModelsTab] Found {len(variant_ids)} variants via base_model matching for {base_model_name}")

            if not variant_ids:
                messagebox.showinfo('Delete Parent + Lineage', f'No variants found for parent {base_model_name}.\n\nNothing to delete.')
                return

            log_message(f"[ModelsTab] Deleting parent {base_model_name} with {len(variant_ids)} variants")

            # Set first variant as active (required by the existing function)
            self._active_variant_id = variant_ids[0]

            # Call existing function (it will operate on the lineage)
            self._delete_parent_and_lineage()

        except Exception as e:
            log_error(f"Error in _delete_parent_and_lineage_for_parent: {e}")
            messagebox.showerror('Delete Parent + Lineage', str(e))

    def _reset_lineage_for_parent(self, base_model_name: str):
        """Reset lineage for parent model - uses bundle registry with fallback."""
        try:
            import config as C
            from registry.bundle_loader import find_bundle_by_name

            # Try to get bundle for this parent (authoritative source)
            bundle = find_bundle_by_name(base_model_name)
            variant_ids = []

            if bundle:
                # Get variants from bundle (safe, explicit list)
                bundle_variants = bundle.get('variants', [])
                variant_ids = [v.get('variant_id') for v in bundle_variants if v.get('variant_id')]
                log_message(f"[ModelsTab] Found {len(variant_ids)} variants in bundle for parent {base_model_name}")

            # Fallback: check for variants via base_model matching
            if not variant_ids:
                variant_ids = C.get_base_model_variants(base_model_name)
                if variant_ids:
                    log_message(f"[ModelsTab] Found {len(variant_ids)} variants via base_model matching for {base_model_name}")

            if not variant_ids:
                messagebox.showinfo('Reset Lineage', f'No variants found for parent {base_model_name}.\n\nCreate variants first before resetting lineage.')
                return

            log_message(f"[ModelsTab] Resetting lineage for parent {base_model_name} with {len(variant_ids)} variants")

            # Set first variant as active (required by the existing function)
            self._active_variant_id = variant_ids[0]

            # Call existing function
            self._reset_lineage()

        except Exception as e:
            log_error(f"Error in _reset_lineage_for_parent: {e}")
            messagebox.showerror('Reset Lineage', str(e))

    def _archive_lineage_for_parent(self, base_model_name: str):
        """Archive lineage for parent model - uses bundle registry with fallback."""
        try:
            import config as C
            from registry.bundle_loader import find_bundle_by_name

            # Try to get bundle for this parent (authoritative source)
            bundle = find_bundle_by_name(base_model_name)
            variant_ids = []

            if bundle:
                # Get variants from bundle (safe, explicit list)
                bundle_variants = bundle.get('variants', [])
                variant_ids = [v.get('variant_id') for v in bundle_variants if v.get('variant_id')]
                log_message(f"[ModelsTab] Found {len(variant_ids)} variants in bundle for parent {base_model_name}")

            # Fallback: check for variants via base_model matching
            if not variant_ids:
                variant_ids = C.get_base_model_variants(base_model_name)
                if variant_ids:
                    log_message(f"[ModelsTab] Found {len(variant_ids)} variants via base_model matching for {base_model_name}")

            if not variant_ids:
                messagebox.showinfo('Archive Lineage', f'No variants found for parent {base_model_name}.\n\nNothing to archive.')
                return

            log_message(f"[ModelsTab] Archiving lineage for parent {base_model_name} with {len(variant_ids)} variants")

            # Set first variant as active (required by the existing function)
            self._active_variant_id = variant_ids[0]

            # Call existing function
            self._archive_lineage()

        except Exception as e:
            log_error(f"Error in _archive_lineage_for_parent: {e}")
            messagebox.showerror('Archive Lineage', str(e))

    def _render_variant_overview(self):
        try:
            vid = getattr(self, '_active_variant_id', '') or ''
            log_message(f"[ModelsTab._render_variant_overview] Rendering overview for variant: {vid}")

            # Clear current overview and rebuild header
            for w in self.overview_tab_frame.winfo_children():
                w.destroy()
            self._build_overview_header()

            if not vid:
                log_message("[ModelsTab._render_variant_overview] No variant_id, showing placeholder")
                return

            from config import load_model_profile
            mp = load_model_profile(vid) or {}
            base_name = mp.get('base_model') or ''
            log_message(f"[ModelsTab._render_variant_overview] Model profile: base_model={base_name}")

            base = None
            try:
                for m in (self.all_models or []):
                    if m.get('name') == base_name and m.get('type') == 'pytorch':
                        base = m
                        break
            except Exception as e:
                log_message(f"[ModelsTab._render_variant_overview] Error finding base model: {e}")
                base = None

            pane = ttk.LabelFrame(self.overview_tab_frame, text="Parent Base Overview", style='TLabelframe')
            pane.pack(fill=tk.X, padx=10, pady=10)

            if not base:
                log_message(f"[ModelsTab._render_variant_overview] Base model '{base_name}' not found in all_models")
                ttk.Label(pane, text=f"Base model '{base_name}' not found.", style='Config.TLabel').grid(row=0, column=0, sticky=tk.W, padx=10, pady=5)

                # Show variant info even if base is missing
                info_pane = ttk.LabelFrame(self.overview_tab_frame, text="Variant Information", style='TLabelframe')
                info_pane.pack(fill=tk.X, padx=10, pady=10)
                info_pane.columnconfigure(1, weight=1)
                r = 0
                ttk.Label(info_pane, text="Variant ID:", font=("Arial", 10, "bold"), style='Config.TLabel').grid(row=r, column=0, sticky=tk.W, padx=10, pady=4)
                ttk.Label(info_pane, text=vid, style='Config.TLabel', foreground='#61dafb').grid(row=r, column=1, sticky=tk.W, padx=5, pady=4); r+=1
                if mp.get('assigned_type'):
                    ttk.Label(info_pane, text="Type:", font=("Arial", 10, "bold"), style='Config.TLabel').grid(row=r, column=0, sticky=tk.W, padx=10, pady=4)
                    ttk.Label(info_pane, text=mp.get('assigned_type'), style='Config.TLabel').grid(row=r, column=1, sticky=tk.W, padx=5, pady=4); r+=1
                if mp.get('class_level'):
                    ttk.Label(info_pane, text="Class:", font=("Arial", 10, "bold"), style='Config.TLabel').grid(row=r, column=0, sticky=tk.W, padx=10, pady=4)
                    ttk.Label(info_pane, text=mp.get('class_level'), style='Config.TLabel').grid(row=r, column=1, sticky=tk.W, padx=5, pady=4); r+=1
                log_message(f"[ModelsTab._render_variant_overview] Displayed variant info panel")
                return

            pane.columnconfigure(1, weight=1)
            r = 0
            ttk.Label(pane, text="Name:", font=("Arial", 10, "bold"), style='Config.TLabel').grid(row=r, column=0, sticky=tk.W, padx=10, pady=4)
            ttk.Label(pane, text=base.get('name',''), style='Config.TLabel', foreground='#61dafb').grid(row=r, column=1, sticky=tk.W, padx=5, pady=4); r+=1
            if base.get('size'):
                ttk.Label(pane, text="Size:", font=("Arial", 10, "bold"), style='Config.TLabel').grid(row=r, column=0, sticky=tk.W, padx=10, pady=4)
                ttk.Label(pane, text=str(base.get('size')), style='Config.TLabel').grid(row=r, column=1, sticky=tk.W, padx=5, pady=4); r+=1
            if base.get('path'):
                ttk.Label(pane, text="Path:", font=("Arial", 10, "bold"), style='Config.TLabel').grid(row=r, column=0, sticky=tk.W, padx=10, pady=4)
                ttk.Label(pane, text=str(base.get('path')), style='Config.TLabel').grid(row=r, column=1, sticky=tk.W, padx=5, pady=4); r+=1

            log_message(f"[ModelsTab._render_variant_overview] Displayed parent base overview for: {base_name}")

            # Add Promotion Readiness section (Section 1: XP/Grades/Promotions)
            self._render_promotion_readiness_panel(vid, mp)

        except Exception as e:
            log_message(f"[ModelsTab._render_variant_overview] Error: {e}")
            import traceback
            traceback.print_exc()

    def _render_promotion_readiness_panel(self, variant_id: str, profile: dict):
        """Render promotion readiness panel showing stat gates and XP progress."""
        try:
            from class_progression import check_promotion_eligibility
            from xp_calculator import get_current_xp, get_xp_to_next_class

            # Get promotion eligibility
            eligibility = check_promotion_eligibility(variant_id)

            # Create promotion readiness panel
            promo_pane = ttk.LabelFrame(self.overview_tab_frame, text="Promotion Readiness", style='TLabelframe')
            promo_pane.pack(fill=tk.X, padx=10, pady=10)
            promo_pane.columnconfigure(1, weight=1)

            current_class = profile.get('class_level', 'novice')
            next_class = eligibility.get('next_class')
            eligible = eligibility.get('eligible', False)

            r = 0

            # Current class
            ttk.Label(promo_pane, text="Current Class:", font=("Arial", 10, "bold"), style='Config.TLabel').grid(row=r, column=0, sticky=tk.W, padx=10, pady=4)
            ttk.Label(promo_pane, text=current_class.title(), style='Config.TLabel', foreground='#61dafb').grid(row=r, column=1, sticky=tk.W, padx=5, pady=4)
            r += 1

            # Next class
            if next_class:
                ttk.Label(promo_pane, text="Next Class:", font=("Arial", 10, "bold"), style='Config.TLabel').grid(row=r, column=0, sticky=tk.W, padx=10, pady=4)
                ttk.Label(promo_pane, text=next_class.title(), style='Config.TLabel', foreground='#00d4ff').grid(row=r, column=1, sticky=tk.W, padx=5, pady=4)
                r += 1

            # XP Progress
            xp_info = get_xp_to_next_class(variant_id)
            current_xp = xp_info.get('current_xp', 0)
            xp_required = xp_info.get('xp_required', 0)
            xp_progress = xp_info.get('progress_percent', 0.0)

            ttk.Label(promo_pane, text="XP Progress:", font=("Arial", 10, "bold"), style='Config.TLabel').grid(row=r, column=0, sticky=tk.W, padx=10, pady=4)
            xp_frame = ttk.Frame(promo_pane)
            xp_frame.grid(row=r, column=1, sticky=tk.EW, padx=5, pady=4)

            # XP progress bar
            import tkinter.ttk as ttk_widgets
            xp_bar = ttk_widgets.Progressbar(xp_frame, length=200, mode='determinate', maximum=100)
            xp_bar.pack(side=tk.LEFT, padx=(0, 10))
            xp_bar['value'] = min(100, xp_progress)

            # XP text
            xp_color = '#00ff00' if xp_progress >= 100 else '#ffaa00' if xp_progress >= 75 else '#aaaaaa'
            xp_text = f"{current_xp:,} / {xp_required:,} ({xp_progress:.1f}%)"
            ttk.Label(xp_frame, text=xp_text, style='Config.TLabel', foreground=xp_color).pack(side=tk.LEFT)
            r += 1

            # Stat Gates Progress
            stat_gate_progress = eligibility.get('stat_gate_progress', 0.0)
            stat_gates_met = eligibility.get('stat_gates_met', [])
            stat_gates_missing = eligibility.get('stat_gates_missing', [])

            ttk.Label(promo_pane, text="Stat Gates:", font=("Arial", 10, "bold"), style='Config.TLabel').grid(row=r, column=0, sticky=tk.W, padx=10, pady=4)
            gate_frame = ttk.Frame(promo_pane)
            gate_frame.grid(row=r, column=1, sticky=tk.EW, padx=5, pady=4)

            # Stat gate progress bar
            gate_bar = ttk_widgets.Progressbar(gate_frame, length=200, mode='determinate', maximum=100)
            gate_bar.pack(side=tk.LEFT, padx=(0, 10))
            gate_bar['value'] = min(100, stat_gate_progress * 100)

            # Stat gate text
            gate_color = '#00ff00' if stat_gate_progress >= 1.0 else '#ffaa00' if stat_gate_progress >= 0.75 else '#aaaaaa'
            gates_total = len(stat_gates_met) + len(stat_gates_missing)
            gate_text = f"{len(stat_gates_met)} / {gates_total} gates ({stat_gate_progress * 100:.0f}%)"
            ttk.Label(gate_frame, text=gate_text, style='Config.TLabel', foreground=gate_color).pack(side=tk.LEFT)
            r += 1

            # Evolution safety
            evolution_safe = eligibility.get('evolution_safe', True)
            regression_score = eligibility.get('regression_score', 0.0)
            capacity_level = eligibility.get('capacity_level', 'green')

            ttk.Label(promo_pane, text="Evolution Safety:", font=("Arial", 10, "bold"), style='Config.TLabel').grid(row=r, column=0, sticky=tk.W, padx=10, pady=4)
            safety_frame = ttk.Frame(promo_pane)
            safety_frame.grid(row=r, column=1, sticky=tk.EW, padx=5, pady=4)

            # Safety indicator
            if evolution_safe:
                safety_icon = "✓"
                safety_text = "Safe to evolve"
                safety_color = "#00ff00"
            else:
                safety_icon = "⚠"
                safety_text = f"Capacity: {capacity_level.upper()}"
                safety_color = "#ffaa00" if capacity_level == 'yellow' else '#ff4444' if capacity_level == 'red' else '#aaaaaa'

            ttk.Label(safety_frame, text=f"{safety_icon} {safety_text}", style='Config.TLabel', foreground=safety_color).pack(side=tk.LEFT)
            r += 1

            # Eligibility status
            ttk.Label(promo_pane, text="Status:", font=("Arial", 10, "bold"), style='Config.TLabel').grid(row=r, column=0, sticky=tk.W, padx=10, pady=4)

            if eligible:
                status_text = f"✓ Ready for promotion to {next_class.title()}"
                status_color = "#00ff00"
            else:
                blockers = eligibility.get('blockers', [])
                if blockers:
                    status_text = f"✗ Blocked: {', '.join(blockers[:2])}"
                else:
                    status_text = "⏳ In progress..."
                status_color = "#ffaa00"

            ttk.Label(promo_pane, text=status_text, style='Config.TLabel', foreground=status_color).grid(row=r, column=1, sticky=tk.W, padx=5, pady=4)
            r += 1

            # Show missing stat gates if any
            if stat_gates_missing:
                ttk.Label(promo_pane, text="Missing Gates:", font=("Arial", 9), style='Config.TLabel', foreground='#888888').grid(row=r, column=0, sticky=tk.W, padx=10, pady=(0, 4))
                missing_text = ', '.join(stat_gates_missing[:3])
                if len(stat_gates_missing) > 3:
                    missing_text += f" (+{len(stat_gates_missing) - 3} more)"
                ttk.Label(promo_pane, text=missing_text, style='Config.TLabel', foreground='#888888', font=("Arial", 9)).grid(row=r, column=1, sticky=tk.W, padx=5, pady=(0, 4))
                r += 1

            log_message(f"[ModelsTab._render_promotion_readiness_panel] Displayed readiness for {variant_id}: eligible={eligible}")

        except Exception as e:
            log_message(f"[ModelsTab._render_promotion_readiness_panel] Error: {e}")
            import traceback
            traceback.print_exc()

    # --- Resizer logic -------------------------------------------------------
    def _on_resizer_press(self, event):
        try:
            self._resizer_drag_start_x = event.x_root
            # Cache current width
            self._resizer_start_width = int(self.right_canvas.winfo_width())
        except Exception:
            self._resizer_drag_start_x = None
            self._resizer_start_width = None

    def _on_resizer_drag(self, event):
        try:
            if self._resizer_drag_start_x is None or self._resizer_start_width is None:
                return
            dx = event.x_root - self._resizer_drag_start_x
            # Invert direction so dragging right widens the right pane
            new_w = max(240, min(700, self._resizer_start_width - dx))
            self.right_pane_width = new_w
            self.right_canvas.config(width=new_w)
            self._update_right_scrollregion()
        except Exception:
            pass

    def refresh_collections_panel(self):
        """Reload list from config.list_model_profiles() and show grouped, filtered entries."""
        try:
            import config as C
            try:
                from logger_util import log_message as dbg
            except Exception:
                def dbg(_m): pass

            dbg("COLLECTIONS_REFRESH: Starting refresh_collections_panel")
            items = C.list_model_profiles() or []
            dbg(f"COLLECTIONS_REFRESH: Found {len(items)} model profiles")
            for it in items:
                dbg(f"COLLECTIONS_REFRESH:   - {it.get('variant_id')}: base={it.get('base_model')} type={it.get('assigned_type')}")

            # Backfill missing lineage_id for legacy profiles
            try:
                for it in items:
                    vid = it.get('variant_id')
                    if vid:
                        C.ensure_lineage_id(vid)
            except Exception:
                pass
            # Group by type category (assigned_type), then by base
            grouped_by_type = {}
            for it in items:
                t = (it.get('assigned_type') or 'uncategorized')
                grouped_by_type.setdefault(t, []).append(it)
            dbg(f"COLLECTIONS_REFRESH: Grouped into {len(grouped_by_type)} types: {list(grouped_by_type.keys())}")
            self._collections_cache = items

            # Clear existing buttons
            for widget in self.collections_buttons_frame.winfo_children():
                widget.destroy()

            if not items:
                ttk.Label(self.collections_buttons_frame, text="No collections found.", style='Config.TLabel').pack(pady=10)
                return

            # Maintain per-type expand state and UI refs
            if not hasattr(self, 'collections_type_expanded'):
                self.collections_type_expanded = {}
            self.collections_type_ui = {}

            # Build grouped UI with Type headers and per-variant rows
            for type_id in sorted(grouped_by_type.keys()):
                # Header row with toggle
                hdr = ttk.Frame(self.collections_buttons_frame)
                hdr.pack(fill=tk.X, padx=5, pady=(8,2))
                expanded = bool(self.collections_type_expanded.get(type_id, False))
                arrow = ttk.Button(hdr, text=('▼' if expanded else '▶'), width=2,
                                   command=lambda t=type_id: self._toggle_collection_type_group(t), style='Select.TButton')
                arrow.pack(side=tk.LEFT, padx=(0,5))
                ttk.Label(hdr, text=type_id.title(), style='Config.TLabel').pack(side=tk.LEFT)

                cont = ttk.Frame(self.collections_buttons_frame)
                for it in sorted(grouped_by_type[type_id], key=lambda x: (x.get('base_model',''), x.get('variant_id',''))):
                    try:
                        cls = C.get_variant_class(it.get('variant_id',''))
                    except Exception:
                        cls = "novice"
                    base = it.get('base_model','?')
                    # Row with color chip and label button
                    rowv = ttk.Frame(cont)
                    rowv.pack(fill=tk.X, padx=10, pady=1)
                    try:
                        color = self._class_to_color(cls)
                        chip = tk.Label(rowv, text='  ', bg=color)
                        chip.pack(side=tk.LEFT, padx=(6,6), pady=2)
                    except Exception:
                        spacer = tk.Label(rowv, text='')
                        spacer.pack(side=tk.LEFT, padx=(6,6))
                    label = f"{base}-{type_id.title()}<{cls.title()}>"
                    btn = ttk.Button(rowv, text=label, style='Select.TButton', command=lambda item=it: self._on_collection_pick(item))
                    btn.pack(side=tk.LEFT, fill=tk.X, expand=True)
                    btn.bind("<Button-3>", lambda e, item=it: self._open_collections_menu(e, item))
                    # Info button [I] to show model preview popup
                    info_btn = ttk.Button(rowv, text='I', width=2, style='Select.TButton', command=lambda item=it: self._on_collection_info(item))
                    info_btn.pack(side=tk.LEFT, padx=(6,0))
                    # Hybrid button [H] to create hybrid variants (requires Skilled+)
                    if cls.lower() in ['skilled', 'adept', 'expert', 'master', 'grand_master']:
                        hybrid_btn = ttk.Button(rowv, text='🧬', width=2, style='Select.TButton', command=lambda item=it: self._open_inheritance_dialog(item))
                        hybrid_btn.pack(side=tk.LEFT, padx=(3,0))
                    # Show assigned artifacts (Ollama tags + Local GGUFs) under variant
                    vid = it.get('variant_id', '')
                    if vid:
                        try:
                            dbg(f"COLLECTIONS_ARTIFACTS: Checking artifacts for variant={vid}")
                            # Get Ollama tags for THIS VARIANT ONLY (not entire lineage)
                            ollama_tags = []
                            data = C.load_ollama_assignments() or {}
                            entry = data.get(vid)
                            if isinstance(entry, dict):
                                ollama_tags = entry.get('tags') or []
                            elif isinstance(entry, list):
                                ollama_tags = entry
                            dbg(f"COLLECTIONS_ARTIFACTS:   ollama_tags={ollama_tags}")
                            # Get Local GGUF artifacts for THIS VARIANT ONLY
                            local_artifacts = C.get_local_artifacts_by_variant(vid) or []
                            dbg(f"COLLECTIONS_ARTIFACTS:   local_artifacts count={len(local_artifacts)}")
                            for art in local_artifacts:
                                dbg(f"COLLECTIONS_ARTIFACTS:     - gguf={art.get('gguf')} quant={art.get('quant')}")
                            # Display Ollama tags
                            for tag in ollama_tags:
                                tag_row = ttk.Frame(cont)
                                tag_row.pack(fill=tk.X, padx=26, pady=1)
                                ttk.Label(tag_row, text="  🔶", style='Config.TLabel').pack(side=tk.LEFT, padx=(0,4))
                                ttk.Button(tag_row, text=tag, style='Select.TButton', command=lambda t=tag: self.display_model_info({'name':t,'type':'ollama'})).pack(side=tk.LEFT)
                                dbg(f"COLLECTIONS_ARTIFACTS:   Displayed Ollama tag: {tag}")
                            # Display Local GGUFs
                            for art in local_artifacts:
                                gguf_path = art.get('gguf', '')
                                quant = art.get('quant', '')
                                if gguf_path:
                                    gguf_row = ttk.Frame(cont)
                                    gguf_row.pack(fill=tk.X, padx=26, pady=1)
                                    ttk.Label(gguf_row, text="  🟩", style='Config.TLabel').pack(side=tk.LEFT, padx=(0,4))
                                    gguf_name = Path(gguf_path).name
                                    ttk.Button(gguf_row, text=f"{gguf_name} ({quant})", style='Select.TButton', command=lambda p=gguf_path: self.display_local_gguf(p)).pack(side=tk.LEFT)
                                    dbg(f"COLLECTIONS_ARTIFACTS:   Displayed Local GGUF: {gguf_name}")
                        except Exception as e:
                            dbg(f"COLLECTIONS_ARTIFACTS: Exception for variant {vid}: {e}")
                            pass
                # Always pack container first, then hide if collapsed
                try:
                    cont.pack(fill=tk.X, after=hdr)
                except Exception:
                    cont.pack(fill=tk.X)

                if not expanded:
                    # Start collapsed - hide the container but keep it in the layout
                    cont.pack_forget()
                    dbg(f"COLLECTIONS_REFRESH: Type '{type_id}' packed then hidden (expanded=False)")
                else:
                    dbg(f"COLLECTIONS_REFRESH: Type '{type_id}' packed and visible (expanded=True)")

                # Keep references including the header for ordered toggling
                self.collections_type_ui[type_id] = {'arrow': arrow, 'container': cont, 'header': hdr}
            dbg("COLLECTIONS_REFRESH: Completed successfully")
        except Exception as e:
            try:
                dbg(f"COLLECTIONS_REFRESH: ERROR - {e}")
                import traceback
                dbg(f"COLLECTIONS_REFRESH: Traceback - {traceback.format_exc()}")
            except Exception:
                pass
            log_message("[ModelsTab] refresh_collections_panel error:", e)

    def _open_brain_map(self):
        """Open brain map visualizer with selected model."""
        try:
            from Data.tabs.brain_map_visualizer import show_brain_map

            # Create brain map window
            brain_map = show_brain_map(self, self.style, self.root)

            # If a model is selected, load it into brain map
            variant_id = getattr(self, '_active_variant_id', None)
            if variant_id:
                import config as C
                model_data = C.load_model_profile(variant_id)
                if model_data:
                    brain_map.load_model(model_data)

        except Exception as e:
            messagebox.showerror("Brain Map", f"Error opening brain map: {e}")

    def _open_inheritance_dialog(self, item: dict):
        """Open inheritance dialog to create hybrid variant."""
        try:
            from Data.tabs.models_tab.inheritance_dialog import show_inheritance_dialog

            variant_id = item.get('variant_id')
            if not variant_id:
                return

            # Show dialog (modal)
            show_inheritance_dialog(self, self.root, self.style, variant_id)

            # Refresh collections after dialog closes
            self.refresh_collections_panel()

        except Exception as e:
            messagebox.showerror("Inheritance Dialog", f"Error opening inheritance dialog: {e}")

    def _on_collection_info(self, item: dict):
        """Open an info popup for this variant; if Custom Code popup is available, reuse it."""
        try:
            vid = item.get('variant_id') or ''
            if not vid:
                return
            # Try to reuse Custom Code popup if available via tab_instances mapping
            cc = None
            try:
                ti = getattr(self, 'tab_instances', None)
                if isinstance(ti, dict):
                    cc = (ti.get('custom_code_tab') or {}).get('instance')
            except Exception:
                cc = None
            if cc and hasattr(cc, '_show_model_popup'):
                model_data = {'variant_name': vid, 'model_name': vid}
                try:
                    cc._show_model_popup(model_data)
                    return
                except Exception:
                    pass
            # Fallback simple popup
            win = tk.Toplevel(self.root); win.title(f'Variant: {vid}')
            frm = ttk.Frame(win, style='Category.TFrame'); frm.pack(fill=tk.BOTH, expand=True, padx=12, pady=10)
            ttk.Label(frm, text=f"Variant: {vid}", style='CategoryPanel.TLabel').pack(anchor=tk.W)
            try:
                import config as C
                mp = C.load_model_profile(vid) or {}
                t = mp.get('assigned_type', '—'); cl = mp.get('class_level', 'novice')
                ttk.Label(frm, text=f"Type: {t}    Class: {cl}", style='Config.TLabel').pack(anchor=tk.W, pady=(6,0))
            except Exception:
                pass
            ttk.Button(frm, text='Close', style='Select.TButton', command=win.destroy).pack(anchor=tk.E, pady=(10,0))
        except Exception as e:
            log_message("[ModelsTab] _on_collection_info error:", e)

    def _open_collections_menu(self, event, item: dict):
        try:
            if not hasattr(self, 'collections_menu') or self.collections_menu is None:
                self.collections_menu = tk.Menu(self.parent, tearoff=0)
                self.collections_menu.add_command(label="Open in Training", command=lambda: self._on_collection_pick(self._collections_ctx_item))
                self.collections_menu.add_separator()
                self.collections_menu.add_command(label="Rename…", command=lambda: self._collections_rename(self._collections_ctx_item))
                self.collections_menu.add_command(label="Duplicate…", command=lambda: self._collections_duplicate(self._collections_ctx_item))
                self.collections_menu.add_command(label="Delete", command=lambda: self._collections_delete(self._collections_ctx_item))
                # WO-6s: Badges/Color editor
                self.collections_menu.add_separator()
                self.collections_menu.add_command(label="Edit Badges/Color…", command=lambda: self._collections_edit_visuals(self._collections_ctx_item))
            self._collections_ctx_item = item
            self.collections_menu.tk_popup(event.x_root, event.y_root)
        finally:
            try:
                self.collections_menu.grab_release()
            except Exception:
                pass

    def _toggle_collection_type_group(self, type_id: str):
        try:
            ui = (getattr(self, 'collections_type_ui', {}) or {}).get(type_id) or {}
            cont = ui.get('container'); arrow = ui.get('arrow'); hdr = ui.get('header')
            if not cont or not arrow:
                return
            expanded = bool(self.collections_type_expanded.get(type_id, False))
            if expanded:
                cont.pack_forget(); arrow.config(text='▶')
            else:
                try:
                    cont.pack(fill=tk.X, after=hdr)
                except Exception:
                    cont.pack(fill=tk.X)
                arrow.config(text='▼')
            self.collections_type_expanded[type_id] = not expanded
            self._update_right_scrollregion()
        except Exception:
            pass
    def _collections_rename(self, item: dict):
        try:
            from tkinter import simpledialog
            old = item.get('variant_id')
            if not old:
                return
            new = simpledialog.askstring("Rename Variant", f"New name for '{old}':", parent=self.root)
            if not new:
                return
            import config as C
            C.rename_variant(old, new)
            self.refresh_collections_panel()
        except Exception as e:
            log_message("[ModelsTab] rename error:", e)

    def _collections_duplicate(self, item: dict):
        try:
            from tkinter import simpledialog
            src = item.get('variant_id')
            if not src:
                return
            dst = simpledialog.askstring("Duplicate Variant", f"Duplicate '{src}' to:", parent=self.root)
            if not dst:
                return
            import config as C
            C.duplicate_variant(src, dst)
            self.refresh_collections_panel()
        except Exception as e:
            log_message("[ModelsTab] duplicate error:", e)

    def _collections_delete(self, item: dict):
        try:
            from tkinter import messagebox
            v = item.get('variant_id')
            if not v:
                return
            if not messagebox.askyesno("Delete Variant", f"Delete '{v}' (model+training profile)?"):
                return
            import config as C
            C.delete_variant(v)
            self.refresh_collections_panel()
        except Exception as e:
            log_message("[ModelsTab] delete error:", e)

    def _collections_edit_visuals(self, item: dict):
        try:
            from tkinter import simpledialog
            v = item.get('variant_id')
            if not v:
                return
            badges_str = simpledialog.askstring("Edit Badges", "Comma-separated badges:", parent=self.root)
            color_str = simpledialog.askstring("Edit Color", "Hex color (e.g., #ffaa00):", parent=self.root)
            if badges_str is None and color_str is None:
                return
            badges = []
            if badges_str:
                badges = [b.strip() for b in badges_str.split(',') if b.strip()]
            import config as C
            C.update_variant_visuals(v, badges, color_str or "")
            self.refresh_collections_panel()
        except Exception as e:
            log_message("[ModelsTab] edit visuals error:", e)

    def refresh_variant_stats(self, variant_id: str):
        """Best-effort: load variant sidecar stats if present and trigger any dependent refresh."""
        try:
            import json, os
            p = os.path.join('Data', 'Stats', f'{variant_id}.json')
            if os.path.exists(p):
                with open(p, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                # Placeholder: hook into skills/stats panels if available
                log_message(f"[ModelsTab] Loaded stats for {variant_id}: keys={list((data.get('summary') or {}).keys())}")
        except Exception as e:
            log_message("[ModelsTab] refresh_variant_stats error:", e)

    # --- Helpers: Variant ⇄ GGUF assignment & eval defaults ------------------
    def _find_assigned_gguf_for_variant(self, variant_id: str) -> str | None:
        """Return the first assigned Ollama tag for a variant, if any."""
        try:
            from config import load_ollama_assignments
            d = load_ollama_assignments() or {}
            lst = d.get(variant_id) or []
            return (lst[0] if lst else None)
        except Exception:
            return None

    def _find_variant_for_gguf(self, tag: str) -> str | None:
        """Reverse lookup: find a variant that owns this GGUF tag (first match)."""
        try:
            from config import load_ollama_assignments
            d = load_ollama_assignments() or {}
            for vid, entry in d.items():
                if vid == 'tag_index':
                    continue
                if isinstance(entry, dict):
                    tags = entry.get('tags') or []
                else:
                    tags = entry or []
                if tag in tags:
                    return vid
        except Exception:
            pass
        return None

    def _class_to_color(self, level: str) -> str:
        """Map class level to UI color hex (matches type_catalog_v2.json structure)."""
        lvl = (level or '').strip().lower()
        return {
            'novice': '#51cf66',      # green
            'skilled': '#61dafb',     # blue
            'adept': '#8b9dc3',       # light purple
            'expert': '#9b59b6',      # purple
            'master': '#ffa94d',      # orange
            'grand_master': '#c92a2a',# deep red
            'artifact': '#ffcc00',    # gold (special)
        }.get(lvl, '#bbbbbb')

    def _get_variant_color_for_gguf(self, tag: str) -> str | None:
        """Return the class color for the variant that owns this GGUF tag, if any."""
        try:
            owner = self._find_variant_for_gguf(tag)
            if not owner:
                return None
            import config as C
            level = C.get_variant_class(owner)
            return self._class_to_color(level)
        except Exception:
            return None

    def _apply_type_driven_eval_defaults(self, variant_id: str):
        """Populate Evaluation tab controls based on variant's type and training profile."""
        try:
            import config as C
            # 1) Suite selection from assigned_type
            t_id = None
            try:
                mp = C.load_model_profile(variant_id) or {}
                t_id = (mp.get('assigned_type') or '').lower()
            except Exception:
                t_id = None
            mapping = {
                'coder': 'CoderNovice',
                'researcher': 'ResearcherNovice',
            }
            preferred = mapping.get(t_id, 'Tools')
            if hasattr(self, 'test_suite_combo') and hasattr(self, 'test_suite_var'):
                opts = list(self.test_suite_combo['values']) if isinstance(self.test_suite_combo['values'], tuple) else (self.test_suite_combo['values'] or [])
                if preferred in opts:
                    self.test_suite_combo.set(preferred)
                elif opts:
                    self.test_suite_combo.set(opts[0])

            # 2) Prompt/Schema toggles and selections from Training Profile
            try:
                tp = C.load_training_profile(variant_id) or {}
            except Exception:
                tp = {}
            try:
                rs = (tp.get('runner_settings') or {})
                if hasattr(self, 'use_system_prompt_var'):
                    self.use_system_prompt_var.set(bool(rs.get('use_system_prompt', False)))
                    self._toggle_system_prompt_controls()
                if hasattr(self, 'use_tool_schema_var'):
                    self.use_tool_schema_var.set(bool(rs.get('use_tool_schema', False)))
                    self._toggle_tool_schema_controls()
            except Exception:
                pass
            try:
                sp = tp.get('selected_prompts') or []
                if sp and hasattr(self, 'system_prompt_combo'):
                    self.system_prompt_combo.config(state='readonly')
                    self.system_prompt_combo.set(sp[0])
            except Exception:
                pass
            try:
                ss = tp.get('selected_schemas') or []
                if ss and hasattr(self, 'tool_schema_combo'):
                    self.tool_schema_combo.config(state='readonly')
                    self.tool_schema_combo.set(ss[0])
            except Exception:
                pass
        except Exception:
            pass

    def _on_collection_pick(self, item: dict):
        """When a variant is picked, apply its training profile in Training tab."""
        try:
            variant = item.get("variant_id")
            # Update active banner
            try:
                if hasattr(self, 'active_variant_var'):
                    self.active_variant_var.set(f"Active Variant: {variant}")
            except Exception:
                pass
            # Render variant overview (parent summary + actions)
            try:
                self._active_variant_id = variant
                self._render_variant_overview()
            except Exception:
                pass
            # Update Class Tree tab
            try:
                self.populate_class_tree_display(variant)
            except Exception as e:
                log_message(f"[ModelsTab] Error updating class tree: {e}")
            # Reflect selection in Evaluation tab context
            try:
                # Determine assigned GGUF and parent base
                gguf = self._find_assigned_gguf_for_variant(variant)
                # If multiple assigned tags exist (legacy), let user choose
                try:
                    import config as C
                    lid = C.get_lineage_id(variant)
                    tags = C.get_assigned_tags_by_lineage(lid) if lid else ([] if not gguf else [gguf])
                    if tags and len(tags) > 1:
                        choice = self._choose_gguf_dialog(tags, title=f"Select GGUF for {variant}")
                        if choice:
                            gguf = choice
                except Exception:
                    pass
                base_name = None
                try:
                    import config as C
                    mp = C.load_model_profile(variant) or {}
                    base_name = mp.get('base_model') or None
                except Exception:
                    base_name = None

                # Labels: parent above, then selected model shows variant → gguf
                if hasattr(self, 'eval_parent_label'):
                    self.eval_parent_label.config(text=f"Base-Model: {base_name}" if base_name else "Base-Model: unavailable")
                if hasattr(self, 'selected_model_label_eval'):
                    if gguf:
                        self.selected_model_label_eval.config(text=f"Selected Model: {variant} → gguf:{gguf}")
                    else:
                        self.selected_model_label_eval.config(text=f"Selected Model: {variant}")
                if hasattr(self, 'eval_source_label'):
                    if gguf:
                        self.eval_source_label.config(text=f"Source: Variant → GGUF ({gguf})")
                        # Use the GGUF for evaluation
                        self._eval_override_model_name = gguf
                    else:
                        self.eval_source_label.config(text="Source: Variant (Profile)")
                        # Clear any previous override
                        if hasattr(self, '_eval_override_model_name'):
                            try:
                                delattr(self, '_eval_override_model_name')
                            except Exception:
                                pass
                # Use variant as logical selection context
                self.current_model_for_stats = variant
                # Update class chip based on variant class
                try:
                    import config as C
                    cls = C.get_variant_class(variant)
                    if getattr(self, 'eval_class_chip', None) is not None:
                        self.eval_class_chip.config(bg=self._class_to_color(cls))
                except Exception:
                    pass
                # Update lineage label
                try:
                    import config as C
                    lid = C.get_lineage_id(variant)
                    short = (lid[:10] + '…') if (lid and len(lid) > 10) else (lid or 'unavailable')
                    if hasattr(self, 'eval_lineage_label'):
                        self.eval_lineage_label.config(text=f"Lineage: {short}")
                except Exception:
                    pass
                # Promotion alert if eligible
                try:
                    eligible, _t = self._check_promotion_eligibility(variant)
                    if eligible:
                        if not hasattr(self, '_promo_alerted_variants'):
                            self._promo_alerted_variants = set()
                        if variant not in self._promo_alerted_variants:
                            messagebox.showinfo('Promotion Unlocked', f"{variant} has earned a promotion.\nClass Available: <Skilled>\nHybrid Available: <NO>")
                            self._promo_alerted_variants.add(variant)
                except Exception:
                    pass
                # Auto-toggle baseline for fresh variants and select type-specific suite
                try:
                    from config import load_latest_evaluation_report, get_baseline_report_path, load_model_profile
                    is_fresh = True
                    try:
                        rep = load_latest_evaluation_report(variant) or {}
                        if rep:
                            is_fresh = False
                    except Exception:
                        is_fresh = True
                    if is_fresh:
                        # No eval report; also check canonical baseline path existence
                        try:
                            p = get_baseline_report_path(variant)
                            if p.exists():
                                is_fresh = False
                        except Exception:
                            pass
                    if is_fresh and hasattr(self, 'run_as_baseline_var'):
                        self.run_as_baseline_var.set(True)
                    # Choose an evaluation suite based on type (fallback to 'Tools')
                    t_id = None
                    try:
                        mp = load_model_profile(variant) or {}
                        t_id = (mp.get('assigned_type') or '').lower()
                    except Exception:
                        pass
                    mapping = {
                        'coder': 'CoderNovice',
                        'researcher': 'ResearcherNovice',
                    }
                    preferred = mapping.get(t_id, 'Tools')
                    if hasattr(self, 'test_suite_combo') and hasattr(self, 'test_suite_var'):
                        opts = list(self.test_suite_combo['values']) if isinstance(self.test_suite_combo['values'], tuple) else (self.test_suite_combo['values'] or [])
                        if preferred in opts:
                            self.test_suite_combo.set(preferred)
                        elif opts:
                            self.test_suite_combo.set(opts[0])
                        # Update lineage label after suite set as well
                        try:
                            if hasattr(self, 'eval_lineage_label'):
                                short = ( (lid[:10] + '…') if (lid and len(lid) > 10) else (lid or 'unavailable') )
                                self.eval_lineage_label.config(text=f"Lineage: {short}")
                        except Exception:
                            pass
                except Exception:
                    pass
            except Exception:
                pass
            # Also apply any type-driven defaults (suite, prompt/schema) from the variant
            try:
                self._apply_type_driven_eval_defaults(variant)
            except Exception:
                pass
            # Relay to TrainingTab
            tt = self.get_training_tab()
            if tt and hasattr(tt, "apply_plan"):
                self.root.after(50, lambda: tt.apply_plan(variant_id=variant))
                log_message(f"[ModelsTab] Applied collection variant to Training: {variant}")
            # Refresh variant-linked stats/skills if available
            try:
                self.refresh_variant_stats(variant)
            except Exception:
                pass
        except Exception as e:
            log_message("[ModelsTab] _on_collection_pick error:", e)

        # Set current_model_for_stats so Skills and Stats tabs populate
        try:
            variant_id = item.get('variant_id', '')
            if variant_id:
                self.current_model_for_stats = variant_id
                self.current_model_for_notes = variant_id
                log_message(f"[ModelsTab] Set current_model_for_stats and notes to: {variant_id}")

                # Set current_model_info for Raw Info tab
                import config as C
                mp = C.load_model_profile(variant_id) or {}
                self.current_model_info = {
                    'name': variant_id,
                    'variant_id': variant_id,
                    'type': 'variant',
                    'profile': mp
                }

                # Refresh Skills tab
                try:
                    self.populate_skills_display()
                    log_message(f"[ModelsTab] Refreshed Skills tab for variant: {variant_id}")
                except Exception as e:
                    log_message(f"[ModelsTab] Error refreshing Skills tab: {e}")

                # Refresh Stats tab
                try:
                    self.populate_stats_display()
                    log_message(f"[ModelsTab] Refreshed Stats tab for variant: {variant_id}")
                except Exception as e:
                    log_message(f"[ModelsTab] Error refreshing Stats tab: {e}")

                # Load notes for variant
                try:
                    self.load_model_notes(variant_id)
                    log_message(f"[ModelsTab] Loaded notes for variant: {variant_id}")
                except Exception as e:
                    log_message(f"[ModelsTab] Error loading notes: {e}")

                # Populate Raw Info tab
                try:
                    self.raw_model_info_text.config(state=tk.NORMAL)
                    self.raw_model_info_text.delete(1.0, tk.END)
                    self.raw_model_info_text.insert(1.0, json.dumps(mp, indent=2))
                    self.raw_model_info_text.config(state=tk.DISABLED)
                    log_message(f"[ModelsTab] Populated Raw Info for variant: {variant_id}")
                except Exception as e:
                    log_message(f"[ModelsTab] Error populating raw info: {e}")

                # Update brain visualization with selected model
                try:
                    if hasattr(self, 'brain_viz_3d') and self.brain_viz_3d:
                        self.brain_viz_3d.load_model_kernel(mp)
                        log_message(f"[ModelsTab] Loaded model into brain visualization: {variant_id}")
                except Exception as e:
                    log_message(f"[ModelsTab] Error updating brain visualization: {e}")
        except Exception as e:
            log_message(f"[ModelsTab] Error setting current_model_for_stats: {e}")

        # CREATE AND EMIT MODEL CONTEXT BUNDLE - unified data for all tabs
        bundle = None
        try:
            from model_context_bundle import set_model_context_from_variant, get_context
            variant_id = item.get('variant_id', '')
            if variant_id:
                log_message(f"[ModelsTab] Creating bundle for variant: {variant_id}")
                bundle = set_model_context_from_variant(variant_id, source="models_tab_collection", root_widget=self.root)
                log_message(f"[ModelsTab] Bundle created: variant_id={bundle.get('variant_id')}, lineage_id={bundle.get('lineage_id')}")
        except Exception as e:
            log_message(f"[ModelsTab] Model context bundle error: {e}")
            import traceback
            traceback.print_exc()

        # Populate History → Chats with the bundle
        try:
            if bundle:
                log_message(f"[ModelsTab] Populating history chats with bundle for variant: {bundle.get('variant_id')}")
                self._populate_history_chats(bundle)
            else:
                log_message(f"[ModelsTab] No bundle available, populating with variant_id only")
                self._populate_history_chats(item.get('variant_id', ''))
        except Exception as e:
            log_message(f"[ModelsTab] Error populating history chats: {e}")
            import traceback
            traceback.print_exc()

    def _choose_gguf_dialog(self, tags: list[str], title: str = "Select GGUF") -> str | None:
        try:
            win = tk.Toplevel(self.root)
            win.title(title)
            f = ttk.Frame(win)
            f.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
            ttk.Label(f, text="Choose assigned GGUF:", style='Config.TLabel').grid(row=0, column=0, sticky=tk.W)
            var = tk.StringVar(value=(tags[0] if tags else ''))
            combo = ttk.Combobox(f, textvariable=var, values=tags, state='readonly', width=50)
            combo.grid(row=1, column=0, sticky=tk.EW, pady=(6,0))
            btns = ttk.Frame(f)
            btns.grid(row=2, column=0, sticky=tk.E, pady=(10,0))
            result = {'v': None}
            def ok():
                result['v'] = var.get()
                win.destroy()
            def cancel():
                win.destroy()
            ttk.Button(btns, text='Cancel', command=cancel, style='Select.TButton').pack(side=tk.RIGHT, padx=5)
            ttk.Button(btns, text='Use', command=ok, style='Action.TButton').pack(side=tk.RIGHT)
            win.grab_set(); win.wait_window()
            return result['v']
        except Exception:
            return None

    def _on_variant_applied(self, evt):
        try:
            import json
            data = json.loads(getattr(evt, 'data', '{}') or '{}')
            vid = data.get('variant_id')
            if vid and hasattr(self, 'active_variant_var'):
                self.active_variant_var.set(f"Active Variant: {vid}")
                try:
                    self.refresh_variant_stats(vid)
                except Exception:
                    pass
                # Also update Evaluation tab labels
                try:
                    # Determine assigned GGUF and parent base
                    gguf = self._find_assigned_gguf_for_variant(vid)
                    base_name = None
                    try:
                        import config as C
                        mp = C.load_model_profile(vid) or {}
                        base_name = mp.get('base_model') or None
                    except Exception:
                        base_name = None
                    if hasattr(self, 'eval_parent_label'):
                        self.eval_parent_label.config(text=f"Base-Model: {base_name}" if base_name else "Base-Model: unavailable")
                    if hasattr(self, 'selected_model_label_eval'):
                        if gguf:
                            self.selected_model_label_eval.config(text=f"Selected Model: {vid} → gguf:{gguf}")
                        else:
                            self.selected_model_label_eval.config(text=f"Selected Model: {vid}")
                    if hasattr(self, 'eval_source_label'):
                        if gguf:
                            self.eval_source_label.config(text=f"Source: Variant → GGUF ({gguf})")
                        else:
                            self.eval_source_label.config(text="Source: Variant (Profile)")
                    self.current_model_for_stats = vid
                    # Update class chip based on variant class
                    try:
                        cls = C.get_variant_class(vid)
                        if getattr(self, 'eval_class_chip', None) is not None:
                            self.eval_class_chip.config(bg=self._class_to_color(cls))
                    except Exception:
                        pass
                    self._active_variant_id = vid
                    self._refresh_overview_actions_state()
                    self._render_variant_overview()
                    # Populate History → Chats for this variant
                    try:
                        self._populate_history_chats(vid)
                    except Exception:
                        pass
                    # Auto-toggle baseline and pick suite for fresh variants too
                    try:
                        from config import load_latest_evaluation_report, get_baseline_report_path, load_model_profile
                        is_fresh = True
                        try:
                            rep = load_latest_evaluation_report(vid) or {}
                            if rep:
                                is_fresh = False
                        except Exception:
                            is_fresh = True
                        if is_fresh:
                            try:
                                p = get_baseline_report_path(vid)
                                if p.exists():
                                    is_fresh = False
                            except Exception:
                                pass
                        if is_fresh and hasattr(self, 'run_as_baseline_var'):
                            self.run_as_baseline_var.set(True)
                        # Pick suite
                        t_id = None
                        try:
                            mp = load_model_profile(vid) or {}
                            t_id = (mp.get('assigned_type') or '').lower()
                        except Exception:
                            pass
                        mapping = {
                            'coder': 'CoderNovice',
                            'researcher': 'ResearcherNovice',
                        }
                        preferred = mapping.get(t_id, 'Tools')
                        if hasattr(self, 'test_suite_combo') and hasattr(self, 'test_suite_var'):
                            opts = list(self.test_suite_combo['values']) if isinstance(self.test_suite_combo['values'], tuple) else (self.test_suite_combo['values'] or [])
                            if preferred in opts:
                                self.test_suite_combo.set(preferred)
                            elif opts:
                                self.test_suite_combo.set(opts[0])
                        # Also apply prompt/schema defaults from Training Profile
                        try:
                            self._apply_type_driven_eval_defaults(vid)
                        except Exception:
                            pass
                    except Exception:
                        pass
                except Exception:
                    pass
        except Exception:
            pass

    def _on_conversation_saved(self, evt):
        """
        Phase 1.2: Handler for <<ConversationSaved>> event from Chat interface.
        Refreshes skills display if the saved conversation is for the currently selected variant.
        """
        try:
            import json
            data = json.loads(getattr(evt, 'data', '{}') or '{}')
            saved_variant = data.get('variant_id')
            training_mode = data.get('training_mode', False)

            # Only refresh if this is the currently displayed model AND training was enabled
            if saved_variant and saved_variant == self.current_model_for_stats and training_mode:
                log_message(f"[ModelsTab] Conversation saved for {saved_variant} with training ON - refreshing skills")
                try:
                    self.populate_skills_display()
                except Exception as e:
                    log_message(f"[ModelsTab] Error refreshing skills after conversation save: {e}")
        except Exception as e:
            log_message(f"[ModelsTab] Error in _on_conversation_saved: {e}")

    def _on_training_activity(self, evt):
        """
        Phase 1.2: Handler for <<TrainingModeChanged>> event from Chat interface.
        Could be used to show a live indicator or update status.
        """
        try:
            import json
            data = json.loads(getattr(evt, 'data', '{}') or '{}')
            enabled = data.get('enabled', False)
            log_message(f"[ModelsTab] Training mode changed: {'ON' if enabled else 'OFF'}")
            # Optional: Add a visual indicator in ModelsTab that training is active
            # For now, just log it
        except Exception as e:
            log_message(f"[ModelsTab] Error in _on_training_activity: {e}")

    def _populate_adapters_tab(self, base_model_info):
        """Scans for and displays all adapters trained from the given base model."""
        for widget in self.adapters_tab_frame.winfo_children():
            widget.destroy()

        base_model_name = base_model_info["name"]
        base_dir = Path(base_model_info["path"]).parent
        all_training_dirs = list(base_dir.glob("training_*"))

        # Header controls
        header = ttk.Frame(self.adapters_tab_frame)
        header.pack(fill=tk.X, padx=8, pady=(6, 2))
        ttk.Checkbutton(header, text="Select Mode", variable=self.adapters_select_mode, style='Category.TCheckbutton',
                        command=lambda: self._toggle_adapters_select_mode(base_model_info)).pack(side=tk.LEFT)
        ttk.Button(header, text="Select All", style='Select.TButton',
                   command=lambda: self._adapters_select_all(True)).pack(side=tk.LEFT, padx=(8, 2))
        ttk.Button(header, text="Clear", style='Select.TButton',
                   command=lambda: self._adapters_select_all(False)).pack(side=tk.LEFT, padx=(2, 8))
        self.adapters_estimate_btn = ttk.Button(header, text="Estimate Size", style='Select.TButton',
                                                command=self._adapters_estimate_size)
        self.adapters_estimate_btn.pack(side=tk.RIGHT)
        self.adapters_levelup_btn = ttk.Button(header, text="Level Up 🚀", style='Action.TButton',
                                               command=lambda: self._adapters_level_up_selected(base_model_info))
        self.adapters_levelup_btn.pack(side=tk.RIGHT, padx=(0, 6))
        # Save as Level button
        self.adapters_save_level_btn = ttk.Button(header, text="Save as Level", style='Select.TButton',
                                                  command=lambda: self._adapters_save_as_level(base_model_info))
        self.adapters_save_level_btn.pack(side=tk.RIGHT, padx=(0, 6))

        found_adapters = []
        for adapter_dir in all_training_dirs:
            try:
                adapter_config_path = adapter_dir / 'adapter_config.json'
                if adapter_config_path.exists():
                    with open(adapter_config_path, 'r') as f:
                        adapter_config = json.load(f)
                    # Match by exact base name or contains cleaned base name
                    base_field = (adapter_config.get('base_model_name_or_path') or '')
                    clean_base = base_model_name.replace('/', '_').replace(':', '_')
                    alt_clean = clean_base.replace('-Instruct', '')
                    if base_field == base_model_name or clean_base in adapter_dir.name or alt_clean in adapter_dir.name:
                        found_adapters.append(adapter_dir)
                    continue
                # Fallback: infer by directory naming pattern if adapter_config.json missing
                clean_base = base_model_name.replace('/', '_').replace(':', '_')
                alt_clean = clean_base.replace('-Instruct', '')
                if clean_base in adapter_dir.name or alt_clean in adapter_dir.name:
                    found_adapters.append(adapter_dir)
            except Exception:
                continue # Ignore folders that can't be read

        if not found_adapters:
            ttk.Label(self.adapters_tab_frame, text="No adapters have been trained from this base model yet.", style='Config.TLabel').pack(padx=10, pady=10)
            return

        canvas = tk.Canvas(self.adapters_tab_frame, bg="#2b2b2b", highlightthickness=0)
        scrollbar = ttk.Scrollbar(self.adapters_tab_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        scrollable_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True, padx=5, pady=5)
        scrollbar.pack(side="right", fill="y")

        for adapter_path in sorted(found_adapters, key=lambda p: p.stat().st_mtime, reverse=True):
            adapter_name = adapter_path.name
            adapter_frame = ttk.Frame(scrollable_frame, style='Category.TFrame', borderwidth=1, relief="solid")
            adapter_frame.pack(fill=tk.X, padx=5, pady=5, expand=True)
            adapter_frame.columnconfigure(1, weight=1)

            col = 0
            if self.adapters_select_mode.get():
                var = self.adapters_selection.get(str(adapter_path))
                if var is None:
                    var = tk.BooleanVar(value=False)
                    self.adapters_selection[str(adapter_path)] = var
                ttk.Checkbutton(adapter_frame, text="", variable=var, style='Category.TCheckbutton', width=2,
                                command=self._adapters_update_actions_state).grid(row=0, column=col, sticky=tk.W, padx=5)
                col += 1

            # Try to show linked variant id from sidecar
            variant_note = ""
            class_level = None
            try:
                sidecar = Path(str(adapter_path) + ".variant.json")
                if sidecar.exists():
                    with open(sidecar, 'r', encoding='utf-8') as f:
                        vmeta = json.load(f)
                    vid = vmeta.get('variant_id')
                    if vid:
                        variant_note = f"  [{vid}]"
                    class_level = vmeta.get('class_level')
                    if not class_level and vid:
                        try:
                            import config as C
                            class_level = C.get_variant_class(vid)
                        except Exception:
                            class_level = None
            except Exception:
                pass

            # Class chip
            try:
                if class_level:
                    chip = tk.Label(adapter_frame, text='  ', bg=self._class_to_color(class_level))
                    chip.grid(row=0, column=col, sticky=tk.W, padx=(6,2), pady=2)
                    col += 1
            except Exception:
                pass
            ttk.Label(adapter_frame, text=f"▶ {adapter_name}{variant_note}", font=("Arial", 10, "bold"), foreground="#51cf66").grid(row=0, column=col, sticky=tk.W, padx=5, pady=2)
            col += 1
            # Readiness pill
            status_label = ttk.Label(adapter_frame, text="", font=("Arial", 8), style='Config.TLabel')
            status_label.grid(row=0, column=col, sticky=tk.W, padx=5)
            readiness = self._compute_adapter_readiness(adapter_name, base_model_name)
            pill_text = readiness.get('status', 'Unverified')
            pill_color = '#51cf66' if pill_text == 'Ready' else ('#ffd43b' if pill_text in ('Needs Eval', 'Unverified') else '#ff6b6b')
            status_label.config(text=pill_text, foreground=pill_color)

            stats = get_latest_training_stats(adapter_name)
            if stats:
                stats_text = f"Epochs: {stats.get('epochs', 'N/A')} | Loss: {stats.get('training_loss', 0.0):.4f} | Runtime: {stats.get('train_runtime', 0):.1f}s"
                span = 3 if self.adapters_select_mode.get() else 2
                ttk.Label(adapter_frame, text=stats_text, font=("Arial", 8), style='Config.TLabel').grid(row=1, column=0, columnspan=span, sticky=tk.W, padx=15)

            button_frame = ttk.Frame(adapter_frame)
            span = 3 if self.adapters_select_mode.get() else 2
            button_frame.grid(row=2, column=0, columnspan=span, sticky=tk.W, padx=15, pady=5)
            ttk.Button(button_frame, text="Archive", command=lambda ap=adapter_path: self._archive_adapter(ap), style='Select.TButton').pack(side=tk.LEFT, padx=5)
            ttk.Button(button_frame, text="Delete", command=lambda ap=adapter_path: self._delete_adapter(ap), style='Select.TButton').pack(side=tk.LEFT, padx=5)

        # Update header button states
        self._adapters_update_actions_state()

    def _compute_adapter_readiness(self, adapter_name: str, base_model_name: str) -> dict:
        """Return readiness info for an adapter based on baseline/evaluation comparison.
        Structure: {status, delta_overall(float), regressions(list[str]), issues(list[str])}
        """
        info = {"status": "Unverified", "delta_overall": None, "regressions": [], "issues": []}
        try:
            baseline = load_baseline_report(base_model_name) or {}
            latest_eval = load_latest_evaluation_report(adapter_name) or {}
            if not latest_eval:
                info["status"] = "Needs Eval"
                info["issues"].append("No evaluation report found for adapter.")
                if not baseline:
                    info["issues"].append("No baseline report found for base model.")
                return info
            if not baseline:
                info["status"] = "Unverified"
                info["issues"].append("No baseline report found for base model.")
                return info

            # Compare
            try:
                test_suite_dir = TRAINING_DATA_DIR / 'Test'
                engine = EvaluationEngine(tests_dir=test_suite_dir)
                policy = get_regression_policy() or {}
                threshold = float(policy.get("alert_drop_percent", 5.0))
                cmp = engine.compare_models(baseline, latest_eval, regression_threshold=threshold, improvement_threshold=threshold)
                delta_str = cmp.get('overall', {}).get('delta', '+0.00%').replace('%', '')
                delta = float(delta_str) if delta_str else 0.0
                info["delta_overall"] = delta
                regs = [r.get('skill') for r in (cmp.get('regressions') or [])]
                info["regressions"] = regs

                if delta >= threshold and not regs:
                    info["status"] = "Ready"
                elif regs:
                    info["status"] = "Regression Detected"
                    info["issues"].append(f"Regressions: {', '.join(regs)}")
                else:
                    info["status"] = "Unverified"
                    info["issues"].append(f"Overall delta below threshold ({delta:.2f}% < {threshold:.2f}%)")
            except Exception as e:
                info["issues"].append(f"Comparison failed: {e}")
        except Exception as e:
            info["issues"].append(f"Readiness check error: {e}")
        return info

    # --- History → Chats (RAG link-tree) ---
    def _show_history_chats_placeholder(self):
        """Show placeholder message in History → Chats tab."""
        try:
            for w in self.history_chats_frame.winfo_children():
                w.destroy()
        except Exception:
            pass

        frame = ttk.Frame(self.history_chats_frame)
        frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        if self._history_chat_mgr_error:
            # Show error if ChatHistoryManager failed to initialize
            ttk.Label(
                frame,
                text="⚠ Chat History Manager Error",
                font=("Arial", 12, "bold"),
                style='CategoryPanel.TLabel'
            ).pack(pady=(0, 10))
            ttk.Label(
                frame,
                text=f"Failed to initialize chat history:\n{self._history_chat_mgr_error}",
                style='Config.TLabel',
                wraplength=400
            ).pack()
        elif not self._history_chat_mgr:
            # Manager is None but no error recorded
            ttk.Label(
                frame,
                text="⚠ Chat History Not Available",
                font=("Arial", 12, "bold"),
                style='CategoryPanel.TLabel'
            ).pack(pady=(0, 10))
            ttk.Label(
                frame,
                text="ChatHistoryManager could not be initialized.",
                style='Config.TLabel'
            ).pack()
        else:
            # Manager exists, show "select a variant" message
            ttk.Label(
                frame,
                text="📋 Chat History",
                font=("Arial", 12, "bold"),
                style='CategoryPanel.TLabel'
            ).pack(pady=(0, 10))
            ttk.Label(
                frame,
                text="Select a variant from Collections to view its saved chats.",
                style='Config.TLabel',
                wraplength=400
            ).pack()

    def _variant_memory_path(self, variant_id: str) -> Path:
        try:
            root = Path('Data') / 'projects' / variant_id
            root.mkdir(parents=True, exist_ok=True)
            return root / 'memory.json'
        except Exception:
            return Path('Data') / 'projects' / variant_id / 'memory.json'

    def _load_variant_memory_set(self, variant_id: str) -> set:
        try:
            p = self._variant_memory_path(variant_id)
            if p.exists():
                data = json.loads(p.read_text())
                return set(data.get('active_sessions', []))
        except Exception:
            pass
        return set()

    def _save_variant_memory_set(self, variant_id: str, s: set):
        try:
            p = self._variant_memory_path(variant_id)
            p.write_text(json.dumps({'variant_id': variant_id, 'active_sessions': sorted(list(s))}, indent=2))
        except Exception:
            pass

    def _load_all_chats_with_sources(self, variant_id: str, lineage_id: Optional[str]) -> list:
        """
        Load all chats for a variant from both Chat tab and Project directories.
        Returns list of dicts with added 'source_type' and 'source_name' keys.
        """
        all_chats = []

        # Helper to check if a chat matches the variant
        def _match(rec: dict) -> bool:
            try:
                md = rec.get('metadata') or {}
                model_name = rec.get('model_name', '')

                # Priority 1: metadata.variant_id exact match
                if md.get('variant_id') == variant_id:
                    return True

                # Priority 2: metadata.lineage_id match
                if lineage_id and md.get('lineage_id') == lineage_id:
                    return True

                # Priority 3: model_name exact match
                if model_name == variant_id:
                    return True

                # Priority 4: model_name stem match (for GGUF paths)
                from pathlib import Path as _P
                if _P(model_name).stem == variant_id:
                    return True

                # Priority 5: substring match
                if variant_id in model_name:
                    return True

                return False
            except Exception:
                return False

        # 1. Load from Chat tab (ChatHistories)
        try:
            mgr = getattr(self, '_history_chat_mgr', None)
            if mgr:
                chat_tab_chats = mgr.list_conversations(model_name=None) or []
                log_message(f"[ModelsTab._load_all_chats] Loaded {len(chat_tab_chats)} chats from Chat tab")
                for rec in chat_tab_chats:
                    if _match(rec):
                        rec['source_type'] = 'chat'
                        rec['source_name'] = 'Single Chat'
                        all_chats.append(rec)
        except Exception as e:
            log_message(f"[ModelsTab._load_all_chats] Error loading from Chat tab: {e}")

        # 2. Load from Projects
        try:
            projects_dir = Path('Data/projects')
            if projects_dir.exists():
                for project_dir in projects_dir.iterdir():
                    if not project_dir.is_dir():
                        continue
                    project_name = project_dir.name

                    # Skip non-project directories
                    if project_name in ['__pycache__']:
                        continue

                    # Scan for chat JSON files in this project
                    for chat_file in project_dir.glob('*.json'):
                        # Skip system files
                        if chat_file.name in ['rag_index.json', 'memory.json', 'chat_index.json']:
                            continue

                        try:
                            data = json.loads(chat_file.read_text())
                            # Verify it's a chat file (has required keys)
                            if 'session_id' in data and 'chat_history' in data:
                                if _match(data):
                                    data['source_type'] = 'project'
                                    data['source_name'] = project_name
                                    all_chats.append(data)
                        except Exception as e:
                            log_message(f"[ModelsTab._load_all_chats] Error reading {chat_file}: {e}")

                log_message(f"[ModelsTab._load_all_chats] Loaded {sum(1 for c in all_chats if c.get('source_type') == 'project')} chats from Projects")
        except Exception as e:
            log_message(f"[ModelsTab._load_all_chats] Error loading from Projects: {e}")

        log_message(f"[ModelsTab._load_all_chats] Total chats found: {len(all_chats)} (Chat: {sum(1 for c in all_chats if c.get('source_type') == 'chat')}, Projects: {sum(1 for c in all_chats if c.get('source_type') == 'project')})")
        return all_chats

    def _populate_history_chats(self, variant_or_bundle):
        """
        Populate History → Chats tab with conversations for a variant.

        Args:
            variant_or_bundle: Either a variant_id string or a model context bundle dict
        """
        # Extract variant_id and lineage_id from input
        if isinstance(variant_or_bundle, dict):
            # It's a bundle
            variant_id = variant_or_bundle.get('variant_id', '')
            lineage_id = variant_or_bundle.get('lineage_id')
            log_message(f"[ModelsTab._populate_history_chats] Using bundle: variant_id={variant_id}, lineage_id={lineage_id}")
        else:
            # It's a string variant_id
            variant_id = str(variant_or_bundle or '')
            lineage_id = None
            # Try to get lineage_id
            try:
                import config as C
                lineage_id = C.get_lineage_id(variant_id)
            except Exception:
                pass
            log_message(f"[ModelsTab._populate_history_chats] Using variant_id string: {variant_id}, resolved lineage_id={lineage_id}")

        if not variant_id:
            log_message("[ModelsTab._populate_history_chats] No variant_id provided, aborting")
            return

        try:
            for w in self.history_chats_frame.winfo_children():
                w.destroy()
        except Exception:
            pass
        header = ttk.Frame(self.history_chats_frame)
        header.pack(fill=tk.X, padx=10, pady=(8, 4))
        ttk.Label(header, text=f"Saved Chats for: {variant_id}", font=("Arial", 12, "bold"), style='CategoryPanel.TLabel').pack(side=tk.LEFT)
        ttk.Button(header, text="🔄 Refresh", command=lambda v=variant_id: self._populate_history_chats(v), style='Select.TButton').pack(side=tk.RIGHT)

        canvas = tk.Canvas(self.history_chats_frame, bg="#2b2b2b", highlightthickness=0)
        sb = ttk.Scrollbar(self.history_chats_frame, orient='vertical', command=canvas.yview)
        body = ttk.Frame(canvas)
        body.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=body, anchor='nw')
        canvas.configure(yscrollcommand=sb.set)
        canvas.pack(side='left', fill='both', expand=True, padx=6, pady=6)
        sb.pack(side='right', fill='y', pady=6)

        # Load chats from both Chat tab and Projects
        chats = []
        error_msg = None
        try:
            chats = self._load_all_chats_with_sources(variant_id, lineage_id)
            log_message(f"[ModelsTab._populate_history_chats] Loaded {len(chats)} total chats")
        except Exception as e:
            error_msg = str(e)
            log_message(f"[ModelsTab._populate_history_chats] Error loading chats: {e}")
            import traceback
            traceback.print_exc()
            chats = []

        # Show error message in UI if there was a problem
        if error_msg:
            err_frame = ttk.Frame(body)
            err_frame.pack(fill=tk.X, padx=8, pady=8)
            ttk.Label(
                err_frame,
                text=f"⚠ Error loading chat history:\n{error_msg}",
                style='Config.TLabel',
                wraplength=400
            ).pack()
            return

        active_set = self._load_variant_memory_set(variant_id)
        self._history_chat_vars = {}

        sum_frame = ttk.Frame(body)
        sum_frame.pack(fill=tk.X, padx=6, pady=(2, 6))
        sum_var = tk.StringVar(value=f"0 / {len(chats)} linked")
        ttk.Label(sum_frame, textvariable=sum_var, style='Config.TLabel').pack(side=tk.LEFT)

        def _recompute():
            try:
                linked = sum(1 for _sid, var in self._history_chat_vars.items() if var.get())
                sum_var.set(f"{linked} / {len(chats)} linked")
            except Exception:
                pass

        if not chats:
            ttk.Label(body, text="No saved chats found for this variant.", style='Config.TLabel').pack(padx=8, pady=8)
        else:
            for rec in chats:
                sid = rec.get('session_id'); mc = rec.get('message_count', 0)
                row = ttk.Frame(body)
                row.pack(fill=tk.X, padx=8, pady=2)
                var = tk.BooleanVar(value=(sid in active_set))
                self._history_chat_vars[sid] = var
                def make_cb(s=sid, v=var):
                    def _on():
                        if v.get():
                            active_set.add(s)
                        else:
                            active_set.discard(s)
                        self._save_variant_memory_set(variant_id, active_set)
                        _recompute()
                    return _on
                ttk.Checkbutton(row, text='', variable=var, command=make_cb(), style='Category.TCheckbutton').pack(side=tk.LEFT)

                # Get source from the record (added by _load_all_chats_with_sources)
                source_type = rec.get('source_type', 'chat')
                source_name = rec.get('source_name', 'Single Chat')

                # Set icon and text based on source
                if source_type == 'project':
                    source_icon = "📁"
                    source_text = f"Project: {source_name}"
                else:
                    source_icon = "💬"
                    source_text = "Single Chat"

                # Show session ID with source indicator
                ttk.Label(row, text=source_icon, style='Config.TLabel').pack(side=tk.LEFT, padx=(2, 4))
                ttk.Label(row, text=sid, style='Config.TLabel').pack(side=tk.LEFT, padx=(0, 8))
                ttk.Label(row, text=f"{mc} msgs", style='Config.TLabel').pack(side=tk.LEFT)
                ttk.Label(row, text=f"[{source_text}]", style='Config.TLabel', foreground='#888888').pack(side=tk.LEFT, padx=(8, 0))
        _recompute()


    def _populate_history_tab(self, base_model_info):
        """Populate History → Runs, Levels, and Events for the selected base model without destroying the tab structure."""
        # Clear content areas only
        for frame in (self.history_runs_frame, self.history_levels_frame, self.history_events_frame):
            for w in frame.winfo_children():
                w.destroy()

        # --- Runs sub-tab ---
        runs_header = ttk.Frame(self.history_runs_frame)
        runs_header.pack(fill=tk.X, padx=10, pady=(8, 4))
        ttk.Label(runs_header, text="Training Runs", font=("Arial", 12, "bold"), style='CategoryPanel.TLabel').pack(side=tk.LEFT)
        ttk.Button(runs_header, text="🔄 Refresh", command=lambda: self._populate_history_tab(base_model_info), style='Select.TButton').pack(side=tk.RIGHT)

        base_model_name = base_model_info["name"]
        base_dir = Path(base_model_info["path"]).parent
        all_training_dirs = list(base_dir.glob("training_*"))

        found = []
        for adapter_dir in all_training_dirs:
            try:
                acfg = adapter_dir / 'adapter_config.json'
                if acfg.exists():
                    with open(acfg, 'r') as f:
                        cfg = json.load(f)
                    if cfg.get('base_model_name_or_path') == base_model_name:
                        found.append(adapter_dir)
            except Exception:
                continue

        if not found:
            ttk.Label(self.history_runs_frame, text="No training history for this base model yet.", style='Config.TLabel').pack(padx=10, pady=10)
        else:
            found = sorted(found, key=lambda p: p.stat().st_mtime, reverse=True)
            canvas = tk.Canvas(self.history_runs_frame, bg="#2b2b2b", highlightthickness=0)
            scrollbar = ttk.Scrollbar(self.history_runs_frame, orient="vertical", command=canvas.yview)
            list_frame = ttk.Frame(canvas)
            list_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
            canvas.create_window((0, 0), window=list_frame, anchor="nw")
            canvas.configure(yscrollcommand=scrollbar.set)
            canvas.pack(side="left", fill="both", expand=True, padx=5, pady=5)
            scrollbar.pack(side="right", fill="y")

            for adapter_dir in found:
                adapter_name = adapter_dir.name
                row = ttk.Frame(list_frame, style='Category.TFrame', borderwidth=1)
                row.pack(fill=tk.X, padx=8, pady=3)
                ttk.Label(row, text=f"🎯 {adapter_name}", font=("Arial", 10, "bold"), style='Config.TLabel').grid(row=0, column=0, sticky=tk.W, padx=6, pady=(4, 2))
                # Stats summary
                summary = "Unverified"
                try:
                    stats = get_latest_training_stats(adapter_name)
                    if stats:
                        parts = []
                        if stats.get('epochs') is not None:
                            parts.append(f"Epochs: {stats.get('epochs')}")
                        if 'training_loss' in stats:
                            try:
                                parts.append(f"Loss: {float(stats['training_loss']):.4f}")
                            except Exception:
                                parts.append(f"Loss: {stats['training_loss']}")
                        if 'train_runtime' in stats:
                            try:
                                parts.append(f"Time: {float(stats['train_runtime']):.1f}s")
                            except Exception:
                                parts.append(f"Time: {stats['train_runtime']}")
                        if stats.get('timestamp'):
                            parts.append(f"When: {stats.get('timestamp').split('T')[0]}")
                        summary = " | ".join(parts) if parts else summary
                except Exception:
                    pass
                ttk.Label(row, text=summary, font=("Arial", 9), style='Config.TLabel').grid(row=1, column=0, sticky=tk.W, padx=20, pady=(0, 2))

                # Evaluation summary and actions
                eval_line = "Evaluation: Unverified"
                try:
                    base_name = base_model_name
                    baseline = load_baseline_report(base_name) or {}
                    latest = load_latest_evaluation_report(adapter_name) or {}
                    if latest and baseline:
                        engine = EvaluationEngine(tests_dir=TRAINING_DATA_DIR / 'Test')
                        policy = get_regression_policy() or {}
                        threshold = float(policy.get('alert_drop_percent', 5.0))
                        cmp = engine.compare_models(baseline, latest, regression_threshold=threshold, improvement_threshold=threshold)
                        overall = cmp.get('overall', {})
                        new = overall.get('new','N/A'); delta = overall.get('delta','+0.00%')
                        eval_line = f"Evaluation: {new} (Δ {delta})"
                except Exception:
                    pass
                ttk.Label(row, text=eval_line, font=("Arial", 9), style='Config.TLabel').grid(row=2, column=0, sticky=tk.W, padx=20, pady=(0, 6))

                # Action buttons
                actions = ttk.Frame(row)
                actions.grid(row=3, column=0, sticky=tk.W, padx=20, pady=(0,8))
                ttk.Button(actions, text="View Report", style='Select.TButton',
                           command=lambda n=adapter_name: self._history_view_report(n)).pack(side=tk.LEFT, padx=3)
                ttk.Button(actions, text="Compare", style='Select.TButton',
                           command=lambda b=base_model_name, n=adapter_name: self._history_compare_baseline(b, n)).pack(side=tk.LEFT, padx=3)
                ttk.Button(actions, text="Open Folder", style='Select.TButton',
                           command=lambda p=adapter_dir: self._open_folder(p)).pack(side=tk.LEFT, padx=3)

        # Phase 5: Add training session management
        # Add separator
        ttk.Separator(self.history_runs_frame, orient='horizontal').pack(fill=tk.X, padx=10, pady=10)

        # Training session controls
        session_header = ttk.Frame(self.history_runs_frame)
        session_header.pack(fill=tk.X, padx=10, pady=(8, 4))
        ttk.Label(session_header, text="Training Sessions", font=("Arial", 12, "bold"), style='CategoryPanel.TLabel').pack(side=tk.LEFT)
        ttk.Button(
            session_header,
            text="➕ Start New Training Session",
            style='Action.TButton',
            command=lambda: self._start_training_session(base_model_info)
        ).pack(side=tk.RIGHT, padx=3)

        # Display training sessions from lineage tracker
        self._display_training_sessions(base_model_info)

        # --- Levels sub-tab ---
        levels_header = ttk.Frame(self.history_levels_frame)
        levels_header.pack(fill=tk.X, padx=10, pady=(8, 4))
        ttk.Label(levels_header, text="Levels (Archived Sets)", font=("Arial", 12, "bold"), style='CategoryPanel.TLabel').pack(side=tk.LEFT)
        ttk.Button(levels_header, text="🔄 Refresh", command=lambda: self._populate_history_tab(base_model_info), style='Select.TButton').pack(side=tk.RIGHT)

        levels_list_frame = ttk.Frame(self.history_levels_frame)
        levels_list_frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=6)
        levels = self._discover_levels_for_base(base_model_name)
        if not levels:
            ttk.Label(levels_list_frame, text="No levels archived for this base model.", style='Config.TLabel').pack(padx=10, pady=10)
        else:
            for level in sorted(levels, key=lambda d: d.get('created',''), reverse=True):
                lf = ttk.LabelFrame(levels_list_frame, text=level.get('name','(unnamed)'), style='TLabelframe')
                lf.pack(fill=tk.X, padx=5, pady=5)
                ttk.Label(lf, text=f"Created: {level.get('created','')}", style='Config.TLabel').pack(anchor=tk.W, padx=10)
                ttk.Label(lf, text=f"Adapters: {', '.join(a.get('name','') for a in level.get('adapters',[]))}", style='Config.TLabel').pack(anchor=tk.W, padx=10, pady=(0,4))
                btnrow = ttk.Frame(lf)
                btnrow.pack(fill=tk.X, padx=8, pady=4)
                ttk.Button(btnrow, text="Export to GGUF", style='Action.TButton', command=lambda lv=level: self._levels_export_to_gguf(base_model_info, lv)).pack(side=tk.LEFT, padx=4)
                ttk.Button(btnrow, text="Open Folder", style='Select.TButton', command=lambda lv=level: self._levels_open_folder(base_model_name, lv.get('name',''))).pack(side=tk.LEFT, padx=4)

        # --- Events sub-tab ---
        self._populate_events_tab(base_model_name)

    def _populate_events_tab(self, variant_id: str):
        """Populate Events sub-tab with variant lifecycle events."""
        from Data.config import get_variant_events, get_event_types_with_icons, format_event_summary

        # Header with filter and refresh
        events_header = ttk.Frame(self.history_events_frame)
        events_header.pack(fill=tk.X, padx=10, pady=(8, 4))
        ttk.Label(events_header, text="Lifecycle Events", font=("Arial", 12, "bold"), style='CategoryPanel.TLabel').pack(side=tk.LEFT)

        # Event type filter
        filter_frame = ttk.Frame(events_header)
        filter_frame.pack(side=tk.LEFT, padx=20)
        ttk.Label(filter_frame, text="Filter:", style='Config.TLabel').pack(side=tk.LEFT, padx=(0, 5))

        event_types = get_event_types_with_icons()
        filter_var = tk.StringVar(value="all")
        filter_combo = ttk.Combobox(filter_frame, textvariable=filter_var,
                                     values=["all"] + list(event_types.keys()),
                                     state="readonly", width=20)
        filter_combo.pack(side=tk.LEFT)
        filter_combo.bind("<<ComboboxSelected>>", lambda e: self._populate_events_tab(variant_id))

        ttk.Button(events_header, text="🔄 Refresh",
                   command=lambda: self._populate_events_tab(variant_id),
                   style='Select.TButton').pack(side=tk.RIGHT)

        # Get events with optional filter
        event_type_filter = filter_var.get() if filter_var.get() != "all" else None
        events = get_variant_events(variant_id, event_type=event_type_filter, limit=50)

        if not events:
            ttk.Label(self.history_events_frame,
                      text="No events recorded for this variant yet.",
                      style='Config.TLabel').pack(padx=10, pady=10)
        else:
            # Create scrollable canvas
            canvas = tk.Canvas(self.history_events_frame, bg="#2b2b2b", highlightthickness=0)
            scrollbar = ttk.Scrollbar(self.history_events_frame, orient="vertical", command=canvas.yview)
            events_list_frame = ttk.Frame(canvas)
            events_list_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
            canvas.create_window((0, 0), window=events_list_frame, anchor="nw")
            canvas.configure(yscrollcommand=scrollbar.set)
            canvas.pack(side="left", fill="both", expand=True, padx=5, pady=5)
            scrollbar.pack(side="right", fill="y")

            # Display each event
            for event in events:
                event_type = event.get('event_type', 'unknown')
                event_meta = event_types.get(event_type, {'icon': '📋', 'description': event_type.title(), 'color': '#888888'})

                event_frame = ttk.Frame(events_list_frame, style='Category.TFrame', borderwidth=1)
                event_frame.pack(fill=tk.X, padx=8, pady=3)

                # Header with icon and type
                header = ttk.Frame(event_frame)
                header.pack(fill=tk.X, padx=6, pady=(4, 2))
                icon_label = ttk.Label(header, text=event_meta['icon'], font=("Arial", 12))
                icon_label.pack(side=tk.LEFT)
                ttk.Label(header, text=event_meta['description'],
                          font=("Arial", 10, "bold"),
                          style='Config.TLabel',
                          foreground=event_meta['color']).pack(side=tk.LEFT, padx=(5, 0))

                # Timestamp
                timestamp = event.get('iso_timestamp', event.get('timestamp', 'Unknown'))
                ttk.Label(header, text=timestamp,
                          font=("Arial", 8),
                          style='Config.TLabel',
                          foreground='#888888').pack(side=tk.RIGHT)

                # Event summary
                summary = format_event_summary(event)
                ttk.Label(event_frame, text=summary,
                          font=("Arial", 9),
                          style='Config.TLabel',
                          wraplength=600).pack(anchor=tk.W, padx=20, pady=(0, 2))

                # Action buttons for specific event types
                if event_type in ['stat_gate_check', 'bug_detected', 'training_completed']:
                    actions = ttk.Frame(event_frame)
                    actions.pack(anchor=tk.W, padx=20, pady=(2, 6))
                    ttk.Button(actions, text="🤖 Ask AI for Help",
                               style='Select.TButton',
                               command=lambda e=event: self._show_ask_ai_dialog(variant_id, e)).pack(side=tk.LEFT, padx=3)

                    # Additional context buttons
                    if event_type == 'stat_gate_check' and not event.get('data', {}).get('result') == 'passed':
                        ttk.Button(actions, text="View Missing Gates",
                                   style='Select.TButton',
                                   command=lambda e=event: self._show_event_details(e)).pack(side=tk.LEFT, padx=3)

    def _show_event_details(self, event):
        """Show detailed event information in a dialog."""
        import tkinter.messagebox as messagebox
        event_data = event.get('data', {})
        details = json.dumps(event_data, indent=2)
        messagebox.showinfo("Event Details", details)

    def _show_ask_ai_dialog(self, variant_id: str, event: dict):
        """Show Ask AI dialog for event assistance."""
        from Data.dialogs.ask_ai_dialog import show_ask_ai_dialog
        from Data.config import log_variant_event

        result = show_ask_ai_dialog(
            self.root,
            variant_id,
            event,
            PROFILES_DIR
        )

        if result:
            # Log AI assistance event
            log_variant_event(
                variant_id,
                'ai_assistance_used',
                {
                    'assistant_variant': result['trainer'],
                    'task': event.get('event_type', 'unknown'),
                    'outcome': 'session_started',
                    'tools_granted': result['tools'],
                    'working_dir': result['working_dir']
                }
            )

            # TODO: Launch actual AI assistance session
            # This would spawn the Trainer variant with the given permissions
            # and allow it to analyze and propose solutions
            import tkinter.messagebox as messagebox
            messagebox.showinfo(
                "AI Session Started",
                f"Trainer '{result['trainer']}' will now help with this issue.\n\n"
                f"Tools granted: {', '.join([k for k, v in result['tools'].items() if v])}\n"
                f"Working directory: {result['working_dir']}\n\n"
                f"The Trainer will analyze the problem and propose solutions."
            )

    def _toggle_adapters_select_mode(self, base_model_info):
        # Re-render adapters list to show/hide checkboxes
        self._populate_adapters_tab(base_model_info)

    def _get_selected_adapters(self):
        try:
            return [Path(p) for p, v in self.adapters_selection.items() if v.get()]
        except Exception:
            return []

    def _adapters_select_all(self, state: bool):
        for var in self.adapters_selection.values():
            var.set(bool(state))
        self._adapters_update_actions_state()

    def _adapters_update_actions_state(self):
        selected = self._get_selected_adapters()
        if self.adapters_estimate_btn:
            try:
                self.adapters_estimate_btn.config(state=(tk.NORMAL if selected else tk.DISABLED))
            except Exception:
                pass
        if self.adapters_levelup_btn:
            try:
                self.adapters_levelup_btn.config(state=(tk.NORMAL if len(selected) == 1 else tk.DISABLED))
            except Exception:
                pass
        if hasattr(self, 'adapters_save_level_btn') and self.adapters_save_level_btn:
            try:
                self.adapters_save_level_btn.config(state=(tk.NORMAL if selected else tk.DISABLED))
            except Exception:
                pass

    def _adapters_estimate_size(self):
        selected = self._get_selected_adapters()
        if not selected:
            messagebox.showinfo("Estimate", "Select at least one adapter in Select Mode.")
            return
        # Rough estimate based on base model disk size
        try:
            base_path = Path(self.current_model_info["path"]) if self.current_model_info else None
            base_bytes = 0
            if base_path and base_path.exists():
                for f in base_path.rglob('*'):
                    if f.is_file():
                        base_bytes += f.stat().st_size
            gb = base_bytes / (1024*1024*1024) if base_bytes else 0
            msg = [
                "Parameter count: Same as base (merging LoRA does not add parameters).",
                f"Base HF model size: ~{gb:.2f} GB" if gb else "Base size: unknown",
                "GGUF size estimates (rough):",
                " - q4_k_m: ~30–50% of FP16",
                " - q5_k_m: ~40–60% of FP16",
                " - q8_0: ~70–90% of FP16",
                f"Selected: {', '.join(p.name for p in selected)}",
            ]
            messagebox.showinfo("Estimate", "\n".join(msg))
        except Exception as e:
            messagebox.showerror("Estimate Error", f"Failed to estimate: {e}")

    def _adapters_level_up_selected(self, base_model_info):
        selected = self._get_selected_adapters()
        if len(selected) != 1:
            messagebox.showwarning("Level Up", "Select exactly one adapter in Select Mode to level up.")
            return
        adapter_path = selected[0]
        base_path = base_model_info["path"]
        # Compute readiness and open unified confirm + quant dialog
        readiness = self._compute_adapter_readiness(adapter_path.name, base_model_info["name"])
        self._confirm_quant_and_export(base_model_info["name"], base_path, adapter_path, readiness)

    def _adapters_save_as_level(self, base_model_info):
        from tkinter import simpledialog
        sels = self._get_selected_adapters()
        if not sels:
            messagebox.showinfo("Save as Level", "Select one or more adapters in Select Mode.")
            return
        level_name = simpledialog.askstring("Save as Level", "Enter a level name:")
        if not level_name:
            return
        notes = simpledialog.askstring("Save as Level", "Optional notes:") or ""
        try:
            clean_base = base_model_info["name"].replace('/','_').replace(':','_')
            level_dir = MODELS_DIR / 'archive' / 'levels' / clean_base / level_name
            level_dir.mkdir(parents=True, exist_ok=True)
            manifest = {
                "name": level_name,
                "base_model": base_model_info["name"],
                "created": __import__('datetime').datetime.now().isoformat(),
                "adapters": [{"name": p.name} for p in sels],
                "notes": notes,
            }
            # Enrich with lineage/variant/type/class if derivable from adapter sidecars
            try:
                base_dir = Path(base_model_info["path"]).parent
                vset, lset, tset, cset = set(), set(), set(), set()
                for p in sels:
                    sc = Path(str(p) + ".variant.json")
                    if (base_dir / sc.name).exists():
                        sc_path = base_dir / sc.name
                    else:
                        sc_path = Path(str(base_dir / p.name) + ".variant.json")
                    if sc_path.exists():
                        with open(sc_path, 'r', encoding='utf-8') as sf:
                            meta = json.load(sf)
                        if meta.get('variant_id'):
                            vset.add(meta.get('variant_id'))
                        if meta.get('lineage_id'):
                            lset.add(meta.get('lineage_id'))
                        if meta.get('assigned_type'):
                            tset.add(meta.get('assigned_type'))
                        if meta.get('class_level'):
                            cset.add(meta.get('class_level'))
                if len(vset) == 1:
                    manifest['variant_id'] = list(vset)[0]
                if len(lset) == 1:
                    manifest['lineage_id'] = list(lset)[0]
                if len(tset) == 1:
                    manifest['assigned_type'] = list(tset)[0]
                if len(cset) == 1:
                    manifest['class_level'] = list(cset)[0]
            except Exception:
                pass
            with open(level_dir / 'manifest.json', 'w', encoding='utf-8') as f:
                json.dump(manifest, f, indent=2)
            messagebox.showinfo("Saved", f"Level '{level_name}' saved.")
            self._populate_history_tab(base_model_info)
        except Exception as e:
            messagebox.showerror("Save Failed", f"Could not save level: {e}")

    def _discover_levels_for_base(self, base_model_name: str):
        levels = []
        try:
            clean_base = base_model_name.replace('/','_').replace(':','_')
            base_levels_dir = MODELS_DIR / 'archive' / 'levels' / clean_base
            if not base_levels_dir.exists():
                return []
            for d in base_levels_dir.iterdir():
                if not d.is_dir():
                    continue
                mf = d / 'manifest.json'
                if mf.exists():
                    try:
                        with open(mf, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                        # Backfill lineage/variant/type/class if missing
                        self._backfill_level_manifest(base_model_name, d, data)
                        data['name'] = d.name
                        data['path'] = str(d)
                        levels.append(data)
                    except Exception:
                        continue
        except Exception:
            return []
        return levels

    def _backfill_level_manifest(self, base_model_name: str, level_dir: Path, data: dict):
        """If a Level manifest lacks lineage/variant/type/class, derive from adapter sidecars and persist back."""
        try:
            needs = []
            for key in ('variant_id','lineage_id','assigned_type','class_level'):
                if not data.get(key):
                    needs.append(key)
            if not needs:
                return
            # Locate base dir to find adapter sidecars
            base_path = self._find_base_path(base_model_name)
            if not base_path:
                return
            base_dir = Path(base_path).parent
            sels = [a.get('name') for a in (data.get('adapters') or []) if a.get('name')]
            if not sels:
                return
            vset, lset, tset, cset = set(), set(), set(), set()
            for an in sels:
                sc_path = Path(str(base_dir / an) + ".variant.json")
                if sc_path.exists():
                    try:
                        meta = json.loads(sc_path.read_text())
                        if meta.get('variant_id'):
                            vset.add(meta.get('variant_id'))
                        if meta.get('lineage_id'):
                            lset.add(meta.get('lineage_id'))
                        if meta.get('assigned_type'):
                            tset.add(meta.get('assigned_type'))
                        if meta.get('class_level'):
                            cset.add(meta.get('class_level'))
                    except Exception:
                        continue
            changed = False
            if 'variant_id' in needs and len(vset) == 1:
                data['variant_id'] = list(vset)[0]; changed = True
            if 'lineage_id' in needs and len(lset) == 1:
                data['lineage_id'] = list(lset)[0]; changed = True
            if 'assigned_type' in needs and len(tset) == 1:
                data['assigned_type'] = list(tset)[0]; changed = True
            if 'class_level' in needs and len(cset) == 1:
                data['class_level'] = list(cset)[0]; changed = True
            if changed:
                mf = level_dir / 'manifest.json'
                with open(mf, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2)
        except Exception:
            pass

    def _levels_open_folder(self, base_model_name: str, level_name: str):
        try:
            clean_base = base_model_name.replace('/','_').replace(':','_')
            path = MODELS_DIR / 'archive' / 'levels' / clean_base / level_name
            if path.exists():
                __import__('subprocess').run(["xdg-open", str(path)])
        except Exception:
            pass

    def _levels_export_to_gguf(self, base_model_info, level_data: dict):
        adapters = [a.get('name') for a in (level_data.get('adapters') or []) if a.get('name')]
        if not adapters:
            messagebox.showinfo("Export", "No adapters listed in this level.")
            return
        adapter_name = adapters[0]
        if len(adapters) > 1:
            if not messagebox.askyesno("Export", f"Multiple adapters in level. Proceed exporting the first: {adapter_name}?"):
                return
        base_dir = Path(base_model_info["path"]).parent
        adapter_path = base_dir / adapter_name
        if not adapter_path.exists():
            messagebox.showerror("Export", f"Adapter folder not found: {adapter_path}")
            return
        readiness = self._compute_adapter_readiness(adapter_name, base_model_info["name"])
        self._confirm_quant_and_export(base_model_info["name"], base_model_info["path"], adapter_path, readiness, level_name=level_data.get('name'))

    def _confirm_quant_and_export(self, base_model_name: str, base_model_path, adapter_path, readiness: dict, level_name: str = None):
        """Single dialog to show readiness/warnings and let user pick quant with size estimate, then export."""
        try:
            win = tk.Toplevel(self.root)
            win.title("Level Up: Confirm & Export")
            wrapper = ttk.Frame(win)
            wrapper.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

            # Info box (small font, black on white for readability)
            info = scrolledtext.ScrolledText(wrapper, wrap=tk.WORD, font=("Arial", 9), bg="#ffffff", fg="#000000", height=10)
            info.grid(row=0, column=0, columnspan=2, sticky=tk.NSEW)
            wrapper.rowconfigure(0, weight=1)
            wrapper.columnconfigure(1, weight=1)
            # Compose message
            lines = []
            lines.append(f"Adapter: {adapter_path.name}")
            status = readiness.get('status', 'Unverified')
            lines.append(f"Status: {status}")
            delta = readiness.get('delta_overall')
            lines.append(f"Overall Δ: {delta:.2f}%" if delta is not None else "Overall Δ: N/A")
            issues = readiness.get('issues') or []
            if issues:
                lines.append("Issues:")
                for it in issues:
                    lines.append(f" - {it}")
            lines.append("")
            # Base size + quant notes
            base_est = self._estimate_gguf_size_gb(base_model_path, 'q4_k_m')
            if base_est is not None:
                lines.append(f"Base HF size approx: ~{(base_est/0.4):.2f} GB")
            lines.append("Quantization affects size and quality:")
            lines.append(" - q4_k_m ≈ 30–50% of FP16")
            lines.append(" - q5_k_m ≈ 40–60% of FP16")
            lines.append(" - q8_0  ≈ 70–90% of FP16")
            lines.append("")
            info.insert(1.0, "\n".join(lines))
            info.config(state=tk.DISABLED)

            # Quant picker + live estimate (small black font)
            ttk.Label(wrapper, text="Quantization:", font=("Arial", 9), foreground="#000000").grid(row=1, column=0, sticky=tk.W, padx=(0,6), pady=(8,4))
            quant_var = tk.StringVar(value="q4_k_m")
            combo = ttk.Combobox(wrapper, textvariable=quant_var, values=["q4_k_m","q5_k_m","q8_0"], state='readonly', width=12)
            combo.grid(row=1, column=1, sticky=tk.W, pady=(8,4))
            est_size = ttk.Label(wrapper, text="", font=("Arial", 9), foreground="#000000")
            est_size.grid(row=2, column=0, columnspan=2, sticky=tk.W)
            est_more = ttk.Label(wrapper, text="", font=("Arial", 9), foreground="#000000", justify=tk.LEFT)
            est_more.grid(row=3, column=0, columnspan=2, sticky=tk.W)
            est_perf = ttk.Label(wrapper, text="", font=("Arial", 9), foreground="#000000")
            est_perf.grid(row=4, column=0, columnspan=2, sticky=tk.W)

            def update_est(*_):
                q = quant_var.get()
                g = self._estimate_gguf_size_gb(base_model_path, q)
                if g is not None:
                    est_size.config(text=f"Estimated GGUF size for {q}: ~{g:.2f} GB")
                    # Simple heuristics for runtime RAM and disk needs
                    load_ram = g * 1.2  # ~20% overhead
                    disk_need = g * 2.0 # export temp + headroom
                    quality_notes = {
                        'q4_k_m': 'Smallest, fastest; noticeable quality drop vs q5/q8',
                        'q5_k_m': 'Balanced size/quality; good default if RAM allows',
                        'q8_0':   'Largest; closest to FP16 quality'
                    }
                    note = quality_notes.get(q, 'Quantized weights; quality vs size trade-off')
                    more = (
                        f"Runtime RAM (load) ≈ {load_ram:.2f} GB\n"
                        f"Disk free recommended ≈ {disk_need:.2f} GB during export\n"
                        f"Parameters unchanged; weights quantized to {q.split('_')[0][1:]}-bit"
                        f"\nQuality: {note}"
                    )
                    est_more.config(text=more)
                    # Tokens/sec estimate (CPU)
                    low, high, cores = self._estimate_tokens_per_sec(g, q)
                    if low is not None:
                        est_perf.config(text=f"Estimated tokens/sec (CPU, ~{cores} threads): ~{low:.1f}–{high:.1f} tok/s")
                    else:
                        est_perf.config(text="")
                else:
                    est_size.config(text=f"Estimated GGUF size for {q}: unknown")
                    est_more.config(text="")
                    est_perf.config(text="")
            combo.bind('<<ComboboxSelected>>', update_est)
            update_est()

            # Buttons
            btns = ttk.Frame(wrapper)
            btns.grid(row=5, column=0, columnspan=2, sticky=tk.E, pady=(10,0))
            ttk.Button(btns, text="Cancel", style='Select.TButton', command=win.destroy).pack(side=tk.RIGHT, padx=5)
            def do_export():
                q = quant_var.get()
                win.destroy()
                self._run_merge_and_export(base_model_path, adapter_path, q, base_model_name=base_model_name, level_name=level_name)
            ttk.Button(btns, text="Export", style='Action.TButton', command=do_export).pack(side=tk.RIGHT)
        except Exception as e:
            messagebox.showerror("Export", f"Could not open export dialog: {e}")

    def _estimate_gguf_size_gb(self, base_model_path, quant: str):
        ratios = {"q4_k_m": 0.4, "q5_k_m": 0.5, "q8_0": 0.8}
        ratio = ratios.get(quant, 0.5)
        try:
            base_path = Path(base_model_path)
            total = 0
            if base_path and base_path.exists():
                for f in base_path.rglob('*'):
                    if f.is_file():
                        total += f.stat().st_size
            if total == 0:
                return None
            gb = total / (1024*1024*1024)
            return gb * ratio
        except Exception:
            return None

    def _estimate_tokens_per_sec(self, gguf_size_gb: float, quant: str):
        """Rough CPU tokens/sec estimate based on GGUF size, quant, and CPU cores.
        Returns (low, high, cores) where low/high define a range.
        Heuristic assumes llama.cpp-like threading and AVX2-class CPU.
        """
        try:
            if gguf_size_gb is None or gguf_size_gb <= 0:
                return (None, None, os.cpu_count() or 4)
            # Baseline: for q4_k_m on a 4-core CPU, ~20 tok/s per GB inverse
            # e.g., 0.5 GB -> ~40 tok/s, 4 GB -> ~5 tok/s
            base_per_gb = 20.0
            quant_scale = { 'q4_k_m': 1.0, 'q5_k_m': 0.85, 'q8_0': 0.60 }.get(quant, 0.80)
            cores = os.cpu_count() or 4
            # Scale with threads up to 16 cores with diminishing returns
            core_scale = min(max(1, cores), 16) / 4.0
            est = (base_per_gb / gguf_size_gb) * quant_scale * core_scale
            low = est * 0.7
            high = est * 1.3
            return (low, high, int(cores))
        except Exception:
            return (None, None, os.cpu_count() or 4)

    # --- History helpers ---
    def _history_view_report(self, adapter_name: str):
        """Open a window showing the latest evaluation report for an adapter."""
        try:
            report = load_latest_evaluation_report(adapter_name) or {}
            self._show_json_window(f"Latest Eval: {adapter_name}", report)
        except Exception as e:
            messagebox.showerror("View Report", f"Failed to load report: {e}")

    def _history_compare_baseline(self, base_model_name: str, adapter_name: str):
        try:
            baseline = load_baseline_report(base_model_name) or {}
            latest = load_latest_evaluation_report(adapter_name) or {}
            if not latest or not baseline:
                messagebox.showinfo("Compare", "Missing baseline or evaluation report.")
                return
            engine = EvaluationEngine(tests_dir=TRAINING_DATA_DIR / 'Test')
            policy = get_regression_policy() or {}
            threshold = float(policy.get('alert_drop_percent', 5.0))
            cmp = engine.compare_models(baseline, latest, regression_threshold=threshold, improvement_threshold=threshold)
            self._show_json_window(f"Compare: {adapter_name} vs baseline", cmp)
        except Exception as e:
            messagebox.showerror("Compare", f"Failed to compare: {e}")

    def _open_folder(self, path: Path):
        try:
            __import__('subprocess').run(["xdg-open", str(path)])
        except Exception:
            pass

    def _start_training_session(self, base_model_info: dict):
        """
        Start a new training session for the selected model (Phase 5)

        Args:
            base_model_info: Model info dict with 'name' key
        """
        try:
            variant_id = base_model_info.get('name', 'Unknown')
            log_message(f"MODELS_TAB: Starting training session for {variant_id}")

            # Generate event for training tab to handle
            # Import json at top if not already imported
            import json
            self.root.event_generate(
                "<<SelectVariantForTraining>>",
                data=json.dumps({'variant_id': variant_id}),
                when="tail"
            )

            log_message(f"MODELS_TAB: Generated SelectVariantForTraining event for {variant_id}")

        except Exception as e:
            log_message(f"MODELS_TAB: Error starting training session: {e}")
            messagebox.showerror("Training Session", f"Failed to start training session: {e}")

    def _display_training_sessions(self, base_model_info: dict):
        """
        Display training sessions from lineage tracker (Phase 5)

        Args:
            base_model_info: Model info dict with 'name' key
        """
        try:
            variant_id = base_model_info.get('name', 'Unknown')

            # Import lineage tracker
            from tabs.custom_code_tab.lineage_tracker import get_tracker

            tracker = get_tracker()

            # Get all lineage records for this variant
            lineage_record = tracker.get_lineage_record(variant_id)

            if not lineage_record:
                ttk.Label(
                    self.history_runs_frame,
                    text="No training session history tracked yet.",
                    style='Config.TLabel'
                ).pack(padx=10, pady=10)
                return

            # Display training session info
            info_frame = ttk.Frame(self.history_runs_frame, style='Category.TFrame', borderwidth=1, relief='ridge')
            info_frame.pack(fill=tk.X, padx=10, pady=5)

            # Training date
            training_date = lineage_record.get('training_date', 'Unknown')
            if training_date != 'Unknown':
                try:
                    # Parse ISO format date
                    from datetime import datetime
                    dt = datetime.fromisoformat(training_date)
                    training_date = dt.strftime('%Y-%m-%d %H:%M')
                except Exception:
                    pass

            ttk.Label(
                info_frame,
                text=f"📅 Last Training: {training_date}",
                font=("Arial", 10),
                style='Config.TLabel'
            ).pack(anchor=tk.W, padx=10, pady=2)

            # Base model
            base_model = lineage_record.get('base_model', 'Unknown')
            ttk.Label(
                info_frame,
                text=f"🏗️  Base Model: {base_model}",
                font=("Arial", 10),
                style='Config.TLabel'
            ).pack(anchor=tk.W, padx=10, pady=2)

            # Training method
            training_method = lineage_record.get('training_method', 'fine-tune')
            ttk.Label(
                info_frame,
                text=f"⚙️  Method: {training_method}",
                font=("Arial", 10),
                style='Config.TLabel'
            ).pack(anchor=tk.W, padx=10, pady=2)

            # Training data source
            data_source = lineage_record.get('training_data_source', 'Unknown')
            if data_source and data_source != 'Unknown':
                ttk.Label(
                    info_frame,
                    text=f"📊 Data: {data_source}",
                    font=("Arial", 10),
                    style='Config.TLabel'
                ).pack(anchor=tk.W, padx=10, pady=2)

            # Metadata (if any)
            metadata = lineage_record.get('metadata', {})
            if metadata:
                metadata_text = ", ".join([f"{k}: {v}" for k, v in metadata.items()])
                ttk.Label(
                    info_frame,
                    text=f"ℹ️  Details: {metadata_text}",
                    font=("Arial", 9),
                    style='Config.TLabel',
                    wraplength=600
                ).pack(anchor=tk.W, padx=10, pady=(2, 6))

        except Exception as e:
            log_message(f"MODELS_TAB: Error displaying training sessions: {e}")

    def _show_json_window(self, title: str, data: dict):
        """Utility: Show a JSON object in a scrollable window for inspection."""
        try:
            win = tk.Toplevel(self.root)
            win.title(title or 'JSON')
            txt = scrolledtext.ScrolledText(win, wrap=tk.WORD, font=("Courier", 9), bg="#1e1e1e", fg="#d4d4d4")
            txt.pack(fill=tk.BOTH, expand=True)
            try:
                payload = json.dumps(data, indent=2)
            except Exception:
                payload = str(data)
            txt.insert(1.0, payload)
            txt.config(state=tk.DISABLED)
        except Exception:
            try:
                messagebox.showerror('View', 'Failed to render JSON window.')
            except Exception:
                pass

    def _show_suggestions_dialog(self, baseline_report: dict, new_report: dict):
        """Displays training suggestions in a new window."""
        try:
            test_suite_dir = TRAINING_DATA_DIR / "Test"
            eval_engine = EvaluationEngine(tests_dir=test_suite_dir)
            suggestions = eval_engine.generate_training_suggestions(baseline_report, new_report)

            win = tk.Toplevel(self.root)
            win.title("Training Suggestions")
            win.transient(self.root) # Make it appear on top of the main window
            win.grab_set() # Make it modal

            frame = ttk.Frame(win)
            frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

            ttk.Label(frame, text="💡 Training Suggestions", font=("Arial", 14, "bold"), style='CategoryPanel.TLabel').pack(anchor=tk.W, pady=(0, 10))

            if suggestions.get('error'):
                ttk.Label(frame, text=f"Error generating suggestions: {suggestions['error']}", foreground='red', style='Config.TLabel').pack(anchor=tk.W)
                return

            # Summary
            summary_frame = ttk.LabelFrame(frame, text="Summary", style='TLabelframe')
            summary_frame.pack(fill=tk.X, pady=5)
            for k, v in suggestions.get('summary', {}).items():
                ttk.Label(summary_frame, text=f"{k.replace('_', ' ').title()}: {v}", style='Config.TLabel').pack(anchor=tk.W, padx=5)

            # Reason Counts
            if suggestions.get('reason_counts'):
                reasons_frame = ttk.LabelFrame(frame, text="Failure Reasons", style='TLabelframe')
                reasons_frame.pack(fill=tk.X, pady=5)
                for k, v in suggestions['reason_counts'].items():
                    ttk.Label(reasons_frame, text=f"{k.replace('_', ' ').title()}: {v}", style='Config.TLabel').pack(anchor=tk.W, padx=5)

            # Top Failures
            if suggestions.get('top_failures'):
                failures_frame = ttk.LabelFrame(frame, text="Top Failing Test Cases", style='TLabelframe')
                failures_frame.pack(fill=tk.X, pady=5)
                for tf in suggestions['top_failures']:
                    ttk.Label(failures_frame, text=f"- {tf.get('test_case')} (Reason: {tf.get('reason')})", style='Config.TLabel').pack(anchor=tk.W, padx=5)

            # Example Stubs (JSONL)
            if suggestions.get('examples_jsonl'):
                ttk.Label(frame, text="\nExample JSONL Stubs for Retraining:", font=("Arial", 10, "bold"), style='Config.TLabel').pack(anchor=tk.W, pady=(10, 5))
                jsonl_text = scrolledtext.ScrolledText(
                    frame,
                    wrap=tk.WORD,
                    height=10,
                    font=("Courier", 9),
                    bg="#1e1e1e",
                    fg="#d4d4d4"
                )
                jsonl_text.insert(tk.END, suggestions['examples_jsonl'])
                jsonl_text.config(state=tk.DISABLED)
                jsonl_text.pack(fill=tk.BOTH, expand=True)

            ttk.Button(frame, text="Close", command=win.destroy, style='Select.TButton').pack(pady=10)

            self.root.wait_window(win) # Wait for the dialog to close

        except Exception as e:
            messagebox.showerror("Suggestions Error", f"Failed to generate or display suggestions: {e}")
    def display_model_info(self, model_info):
        """Displays information for the selected Ollama model."""
        self.current_model_info = model_info
        model_name = model_info["name"]
        raw_info = get_ollama_model_info(model_name)
        parsed_info = parse_ollama_model_info(raw_info)

        # Emit event for other panels to react to model selection
        try:
            import json
            payload = json.dumps({
                "model_name": model_name,
                "model_type": model_info.get("type", "ollama"),
                "is_ollama": True,
            })
            if hasattr(self, 'panel_types') and self.panel_types:
                self.panel_types.event_generate("<<ModelSelected>>", data=payload, when="tail")
        except Exception:
            pass


        # Update Raw Info Tab
        self.raw_model_info_text.config(state=tk.NORMAL)
        self.raw_model_info_text.delete(1.0, tk.END)
        self.raw_model_info_text.insert(1.0, raw_info)
        self.raw_model_info_text.config(state=tk.DISABLED)

        # Update Overview Tab
        # Selecting an Ollama model clears active variant context
        try:
            self._active_variant_id = ''
            if hasattr(self, 'active_variant_var'):
                self.active_variant_var.set('')
        except Exception:
            pass
        # Clear previous overview content
        for widget in self.overview_tab_frame.winfo_children():
            widget.destroy()
        # Do NOT build variant header/actions for unassigned Ollama models

        # Model Rename Section at the top
        rename_frame = ttk.LabelFrame(self.overview_tab_frame, text="🏷️ Rename Model", style='TLabelframe')
        rename_frame.grid(row=0, column=0, columnspan=2, sticky=tk.EW, padx=5, pady=10)
        rename_frame.columnconfigure(1, weight=1)

        ttk.Label(rename_frame, text="Current Name:", font=("Arial", 10, "bold"), style='Config.TLabel').grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        name_frame = ttk.Frame(rename_frame)
        name_frame.grid(row=0, column=1, sticky=tk.W, padx=5, pady=5)
        ttk.Label(name_frame, text=model_name, font=("Arial", 10), style='Config.TLabel', foreground='#61dafb').pack(side=tk.LEFT)
        ttk.Button(name_frame, text="📎", command=self._copy_name_to_clipboard, style='Select.TButton', width=2).pack(side=tk.LEFT, padx=5)

        ttk.Label(rename_frame, text="New Name:", font=("Arial", 10, "bold"), style='Config.TLabel').grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)

        self.rename_entry_var = tk.StringVar()
        rename_entry = ttk.Entry(rename_frame, textvariable=self.rename_entry_var, width=40)
        rename_entry.grid(row=1, column=1, sticky=tk.EW, padx=5, pady=5)

        # Validation label
        self.rename_validation_label = ttk.Label(rename_frame, text="", font=("Arial", 9), style='Config.TLabel')
        self.rename_validation_label.grid(row=2, column=0, columnspan=2, sticky=tk.W, padx=5, pady=2)

        # Buttons
        button_frame = ttk.Frame(rename_frame)
        button_frame.grid(row=3, column=0, columnspan=2, pady=5)

        ttk.Button(button_frame, text="✓ Validate Name", command=self.validate_model_name, style='Action.TButton').pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="🔄 Rename Model", command=self.rename_model, style='Action.TButton').pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="🗑️ Delete Model", command=self.delete_model, style='Action.TButton').pack(side=tk.LEFT, padx=5)

        # Info text
        info_text = "HuggingFace naming rules:\n• Alphanumeric chars, '-', '_', '.' only\n• Cannot start/end with '-' or '.'\n• Max 96 characters\n• No colons (:) or slashes (/)\n\nNote: Ollama will add ':latest' tag automatically.\nThis is normal - it will be stripped during training."
        ttk.Label(rename_frame, text=info_text, font=("Arial", 8), style='Config.TLabel', foreground='#888888').grid(
            row=4, column=0, columnspan=2, sticky=tk.W, padx=5, pady=5)

        # Separator
        ttk.Separator(self.overview_tab_frame, orient='horizontal').grid(row=1, column=0, columnspan=2, sticky=tk.EW, padx=5, pady=10)

        # Training Capability Notice
        cap_frame = ttk.LabelFrame(self.overview_tab_frame, text="Capability", style='TLabelframe')
        cap_frame.grid(row=2, column=0, columnspan=2, sticky=tk.EW, padx=5, pady=5)
        ttk.Label(cap_frame, text="Training Capability:", font=("Arial", 10, "bold"), style='Config.TLabel').grid(row=0, column=0, sticky=tk.W, padx=10, pady=5)
        ttk.Label(cap_frame, text="Inference-only (GGUF via Ollama) — not trainable here. Evaluations supported.", font=("Arial", 10), style='Config.TLabel').grid(row=0, column=1, sticky=tk.W, padx=10, pady=5)

        # Bump subsequent content rows
        next_row_base = 3

        # Model Info
        row_num = next_row_base
        for key, value in parsed_info.items():
            ttk.Label(self.overview_tab_frame, text=f"{key.replace('_', ' ').title()}:", font=("Arial", 10, "bold"), style='Config.TLabel').grid(row=row_num, column=0, sticky=tk.W, padx=5, pady=2)
            ttk.Label(self.overview_tab_frame, text=value, font=("Arial", 10), style='Config.TLabel').grid(row=row_num, column=1, sticky=tk.W, padx=5, pady=2)
            row_num += 1

        # Lineage - Try LineageTracker first, then fall back to old method
        lineage_record = None
        lineage_chain = []
        found = None

        # Try new LineageTracker
        try:
            import sys
            from pathlib import Path
            sys.path.insert(0, str(Path(__file__).parent.parent / "tabs" / "custom_code_tab"))
            from lineage_tracker import get_tracker

            tracker = get_tracker()
            if tracker.has_lineage(model_name):
                lineage_record = tracker.get_lineage_record(model_name)
                lineage_chain = tracker.get_lineage_chain(model_name)
        except Exception as e:
            log_message(f"MODELS_TAB: LineageTracker not available: {e}")

        # Fall back to old method if LineageTracker didn't find anything
        if not lineage_record:
            try:
                from config import MODELS_DIR
                base_names = [m['name'] for m in (self.all_models or []) if m.get('type') == 'pytorch']
                for b in base_names:
                    clean_base = b.replace('/','_').replace(':','_')
                    base_levels_dir = MODELS_DIR / 'archive' / 'levels' / clean_base
                    if not base_levels_dir.exists():
                        continue
                    for d in base_levels_dir.iterdir():
                        mf = d / 'manifest.json'
                        if mf.exists():
                            try:
                                with open(mf,'r') as f:
                                    data = json.load(f)
                                for ex in (data.get('exports') or []):
                                    if (ex.get('name') or '') == model_name:
                                        found = { 'base': b, 'level': d.name, 'adapters': [a.get('name') for a in (data.get('adapters') or []) if a.get('name')] }
                                        raise StopIteration
                            except Exception:
                                continue
            except StopIteration:
                pass
            except Exception:
                found = None

        # Display lineage information (from either source)
        if lineage_record or found:
            lin = ttk.LabelFrame(self.overview_tab_frame, text="🧬 Model Lineage", style='TLabelframe')
            lin.grid(row=row_num, column=0, columnspan=2, sticky=tk.EW, padx=5, pady=6)

            if lineage_record:
                # Display from LineageTracker
                current_row = 0

                # Base model info
                ttk.Label(
                    lin,
                    text=f"Base Model: {lineage_record.get('base_model', 'Unknown')}",
                    font=("Arial", 10, "bold"),
                    style='Config.TLabel'
                ).grid(row=current_row, column=0, sticky=tk.W, padx=8, pady=2)

                ttk.Label(
                    lin,
                    text=f"Training Method: {lineage_record.get('training_method', 'Unknown')}",
                    style='Config.TLabel'
                ).grid(row=current_row, column=1, sticky=tk.W, padx=8, pady=2)
                current_row += 1

                # Training date
                training_date = lineage_record.get('training_date', '')
                if training_date:
                    try:
                        from datetime import datetime
                        dt = datetime.fromisoformat(training_date)
                        formatted_date = dt.strftime('%Y-%m-%d %H:%M')
                    except:
                        formatted_date = training_date
                    ttk.Label(
                        lin,
                        text=f"Trained: {formatted_date}",
                        style='Config.TLabel'
                    ).grid(row=current_row, column=0, sticky=tk.W, padx=8, pady=2)
                    current_row += 1

                # Training data source
                data_source = lineage_record.get('training_data_source')
                if data_source:
                    ttk.Label(
                        lin,
                        text=f"Training Data: {data_source}",
                        style='Config.TLabel'
                    ).grid(row=current_row, column=0, columnspan=2, sticky=tk.W, padx=8, pady=2)
                    current_row += 1

                # Lineage chain (ancestry)
                if len(lineage_chain) > 1:
                    chain_text = " → ".join([r.get('model_name', 'Unknown') for r in lineage_chain])
                    ttk.Label(
                        lin,
                        text=f"Ancestry: {chain_text}",
                        style='Config.TLabel',
                        wraplength=500
                    ).grid(row=current_row, column=0, columnspan=2, sticky=tk.W, padx=8, pady=2)
                    current_row += 1

                # Metadata (if any)
                metadata = lineage_record.get('metadata', {})
                if metadata:
                    metadata_str = ", ".join([f"{k}: {v}" for k, v in metadata.items()])
                    ttk.Label(
                        lin,
                        text=f"Metadata: {metadata_str}",
                        style='Config.TLabel',
                        wraplength=500
                    ).grid(row=current_row, column=0, columnspan=2, sticky=tk.W, padx=8, pady=2)

            elif found:
                # Display from old method
                ttk.Label(lin, text=f"Parent Base: {found['base']}", style='Config.TLabel').grid(row=0, column=0, sticky=tk.W, padx=8, pady=2)
                ttk.Label(lin, text=f"Level: {found['level']}", style='Config.TLabel').grid(row=0, column=1, sticky=tk.W, padx=8, pady=2)
                ttk.Label(lin, text=f"Adapters: {', '.join(found['adapters']) if found['adapters'] else 'None'}", style='Config.TLabel').grid(row=1, column=0, columnspan=2, sticky=tk.W, padx=8, pady=2)

                # Parent baseline and primary adapter evaluation snapshots
                try:
                    from config import load_baseline_report, load_latest_evaluation_report
                    base_bl = load_baseline_report(found['base']) or {}
                    if base_bl:
                        ttk.Label(lin, text=f"Parent Baseline Overall: {base_bl.get('pass_rate_percent','N/A')}", style='Config.TLabel').grid(row=2, column=0, sticky=tk.W, padx=8, pady=2)
                    if found['adapters']:
                        primary = found['adapters'][0]
                        lad = load_latest_evaluation_report(primary) or {}
                        if lad:
                            ttk.Label(lin, text=f"Primary Adapter Eval Overall: {lad.get('pass_rate_percent','N/A')}", style='Config.TLabel').grid(row=2, column=1, sticky=tk.W, padx=8, pady=2)
                except Exception:
                    pass

            row_num += 1

        # Update Notes Tab context
        self.notes_text.delete(1.0, tk.END)
        self.note_name_var.set("")
        self.populate_notes_list()  # Load notes list for this model

        # Update Stats Tab
        self.current_model_for_stats = model_name
        self.populate_stats_display()  # Load stats for this model

        # Lineage (Variants & Assignments) for this model's parent base (if determinable)
        try:
            base_for_variants = parent_base or ''
            if base_for_variants:
                self._build_lineage_variants_section(base_for_variants, parent_frame=self.overview_tab_frame)
        except Exception:
            pass

        # Behavior indicators for GGUF (if evaluated)
        try:
            from config import get_model_behavior_profile
            prof = get_model_behavior_profile(model_name) or {}
            beh = prof.get('behavior') or {}
            beh_frame = ttk.LabelFrame(self.overview_tab_frame, text="Behavior Indicators", style='TLabelframe')
            beh_frame.grid(row=row_num, column=0, columnspan=2, sticky=tk.EW, padx=5, pady=10)
            ttk.Label(beh_frame, text=f"Compliance: {(beh.get('compliance') or '0.00%')}", style='Config.TLabel').grid(row=0, column=0, sticky=tk.W, padx=10, pady=3)
            ttk.Label(beh_frame, text=f"Creativity: {(beh.get('creativity') or '0.00%')}", style='Config.TLabel').grid(row=0, column=1, sticky=tk.W, padx=10, pady=3)
            ttk.Label(beh_frame, text=f"Coherence: {(beh.get('coherence') or '0.00%')}", style='Config.TLabel').grid(row=0, column=2, sticky=tk.W, padx=10, pady=3)
        except Exception:
            pass

        # Update Selected Model + Parent Labels in Evaluation Tab
        owner_variant = None
        try:
            owner_variant = self._find_variant_for_gguf(model_name)
        except Exception:
            owner_variant = None
        # Parent base derivation via owner variant (if any)
        parent_base = None
        if owner_variant:
            try:
                import config as C
                mp = C.load_model_profile(owner_variant) or {}
                parent_base = mp.get('base_model') or None
            except Exception:
                parent_base = None
        if hasattr(self, 'eval_parent_label'):
            self.eval_parent_label.config(text=f"Base-Model: {parent_base}" if parent_base else "Base-Model: unavailable")
        if hasattr(self, 'selected_model_label_eval'):
            if owner_variant:
                self.selected_model_label_eval.config(text=f"Selected Model: {owner_variant} → gguf:{model_name}")
            else:
                self.selected_model_label_eval.config(text=f"Selected Model: {model_name}")
        if hasattr(self, 'eval_source_label'):
            self.eval_source_label.config(text="Source: Ollama (GGUF)")

        # Class chip: derive from owner variant if present
        try:
            if owner_variant and getattr(self, 'eval_class_chip', None) is not None:
                import config as C
                cls = C.get_variant_class(owner_variant)
                self.eval_class_chip.config(bg=self._class_to_color(cls))
        except Exception:
            pass
        # Lineage label
        try:
            import config as C
            lid = None
            if owner_variant:
                lid = C.get_lineage_id(owner_variant)
            if not lid:
                lid = C.get_lineage_for_tag(model_name)
            short = (lid[:10] + '…') if (lid and len(lid) > 10) else (lid or 'unavailable')
            if hasattr(self, 'eval_lineage_label'):
                self.eval_lineage_label.config(text=f"Lineage: {short}")
        except Exception:
            pass

        # If this GGUF is assigned to a variant, use that variant to prefill per-type eval settings
        try:
            if owner_variant:
                # Populate suite + prompt/schema defaults similar to selecting from Collections
                self._apply_type_driven_eval_defaults(owner_variant)
                # Explicit GGUF selection: ensure no stale override
                if hasattr(self, '_eval_override_model_name'):
                    try:
                        delattr(self, '_eval_override_model_name')
                    except Exception:
                        pass
        except Exception:
            pass

    def validate_model_name(self):
        """Validate the proposed model name against HuggingFace rules."""
        new_name = self.rename_entry_var.get().strip()

        if not new_name:
            self.rename_validation_label.config(text="⚠️ Please enter a model name", foreground='#ff6b6b')
            return False

        # HuggingFace validation rules
        import re

        # Check length
        if len(new_name) > 96:
            self.rename_validation_label.config(text="❌ Name too long (max 96 characters)", foreground='#ff6b6b')
            return False

        # Check for forbidden characters
        if not re.match(r'^[a-zA-Z0-9._-]+$', new_name):
            self.rename_validation_label.config(text="❌ Only alphanumeric, '-', '_', '.' allowed", foreground='#ff6b6b')
            return False

        # Check for colons (common mistake from Ollama names)
        if ':' in new_name:
            self.rename_validation_label.config(text="❌ Colons (:) not allowed - remove ':latest' or version tags", foreground='#ff6b6b')
            return False

        # Check for slashes
        if '/' in new_name:
            self.rename_validation_label.config(text="❌ Slashes (/) not allowed - use '-' or '_' instead", foreground='#ff6b6b')
            return False

        # Check for forbidden patterns
        if new_name.startswith('-') or new_name.startswith('.'):
            self.rename_validation_label.config(text="❌ Cannot start with '-' or '.'", foreground='#ff6b6b')
            return False

        if new_name.endswith('-') or new_name.endswith('.'):
            self.rename_validation_label.config(text="❌ Cannot end with '-' or '.'", foreground='#ff6b6b')
            return False

        if '--' in new_name or '..' in new_name:
            self.rename_validation_label.config(text="❌ Cannot contain '--' or '..'", foreground='#ff6b6b')
            return False

        # All checks passed
        self.rename_validation_label.config(text="✅ Valid HuggingFace model name", foreground='#51cf66')
        return True

    def rename_model(self):
        """Rename the selected Ollama model."""
        if not hasattr(self, 'current_model_for_notes') or not self.current_model_for_notes:
            messagebox.showwarning("No Model Selected", "Please select a model first.")
            return

        # Validate name first
        if not self.validate_model_name():
            messagebox.showerror("Invalid Name", "Please fix the validation errors before renaming.")
            return

        old_name = self.current_model_for_notes
        new_name = self.rename_entry_var.get().strip()

        if old_name == new_name:
            messagebox.showinfo("No Change", "New name is the same as the current name.")
            return

        # Confirm with user
        confirm_msg = f"Rename model:\n\nFrom: {old_name}\nTo:   {new_name}\n\nThis will create a copy with the new name. Continue?"
        if not messagebox.askyesno("Confirm Rename", confirm_msg):
            return

        try:
            import subprocess
            import tempfile
            import os

            # Create a Modelfile that references the original model
            # This approach should prevent Ollama from auto-adding :latest
            with tempfile.NamedTemporaryFile(mode='w', suffix='.modelfile', delete=False) as f:
                f.write(f"FROM {old_name}\n")
                modelfile_path = f.name

            try:
                # Create the new model using ollama create with explicit name (no tag)
                result = subprocess.run(
                    ["ollama", "create", new_name, "-f", modelfile_path],
                    capture_output=True,
                    text=True,
                    check=True
                )

                # Clean up the temporary Modelfile
                os.unlink(modelfile_path)

                # Verify what was actually created
                updated_models = get_ollama_models()
                actual_new_name = None

                # Look for the new model (check if :latest was added)
                for model in updated_models:
                    if model == new_name:
                        actual_new_name = new_name
                        break
                    elif model.startswith(f"{new_name}:"):
                        actual_new_name = model
                        break

                if not actual_new_name:
                    # Couldn't find the model, something went wrong
                    messagebox.showerror("Rename Failed", f"Model was created but couldn't be found in model list.\n\nOutput: {result.stdout}\nError: {result.stderr}")
                    return

                if actual_new_name != new_name:
                    # Ollama added :latest (this is expected and OK)
                    messagebox.showinfo(
                        "Rename Successful",
                        f"✅ Model renamed successfully!\n\nOld: {old_name}\nNew: {actual_new_name}\n\nℹ️ Note: Ollama automatically adds ':latest' tag to all models. This is normal behavior and won't affect training - the tag will be automatically stripped when using the model for HuggingFace training.\n\nOriginal model '{old_name}' still exists. You can delete it using the Delete button if needed."
                    )
                else:
                    messagebox.showinfo(
                        "Rename Successful",
                        f"✅ Model renamed successfully!\n\nOld: {old_name}\nNew: {new_name}\n\nNote: Original model '{old_name}' still exists. You can delete it using the Delete button if needed."
                    )

                # Refresh model list
                self.ollama_models = get_ollama_models()
                self.populate_model_list()

                # Clear rename field
                self.rename_entry_var.set("")
                self.rename_validation_label.config(text="")

                # Display the new model
                if actual_new_name in self.ollama_models:
                    self.display_model_info(actual_new_name)

            except subprocess.CalledProcessError as e:
                # Clean up the temporary file
                if os.path.exists(modelfile_path):
                    os.unlink(modelfile_path)
                error_msg = e.stderr if e.stderr else str(e)
                messagebox.showerror("Rename Failed", f"Failed to create model:\n\n{error_msg}")
            except Exception as e:
                # Clean up the temporary file
                if os.path.exists(modelfile_path):
                    os.unlink(modelfile_path)
                raise

        except Exception as e:
            messagebox.showerror("Rename Failed", f"An error occurred:\n\n{str(e)}")

    def delete_trained_model_action(self):
        """Delete the currently selected trained model."""
        if not self.current_model_info or self.current_model_info["type"] != "trained":
            messagebox.showwarning("Invalid Model", "Can only delete trained models.")
            return

        model_name = self.current_model_info["name"]
        model_path = self.current_model_info["path"]

        # Confirm deletion
        confirm_msg = f"⚠️ DELETE TRAINED MODEL?\n\nModel: {model_name}\nPath: {model_path}\n\nThis will permanently delete:\n• The trained model directory\n• All model files\n• Associated training statistics\n\nThis action cannot be undone!\n\nContinue?"
        if not messagebox.askyesno("Confirm Delete", confirm_msg):
            return

        try:
            # Delete the trained model
            if delete_trained_model(model_path):
                messagebox.showinfo("Delete Successful", f"Trained model '{model_name}' has been deleted.")

                # Refresh model list
                self.all_models = get_all_trained_models()
                self.populate_model_list()

                # Clear the overview tab
                for widget in self.overview_tab_frame.winfo_children():
                    widget.destroy()

                ttk.Label(self.overview_tab_frame, text="Select a model to view details",
                         font=("Arial", 12), style='Config.TLabel').pack(pady=20)

                # Clear other tabs
                self.current_model_for_notes = None
                self.current_model_for_stats = None
                self.current_model_info = None
                self.notes_text.delete(1.0, tk.END)
                self.note_name_var.set("")
                self.populate_notes_list()
                self.populate_stats_display()
            else:
                messagebox.showerror("Delete Failed", f"Failed to delete model '{model_name}'.")

        except Exception as e:
            messagebox.showerror("Delete Failed", f"An error occurred:\n\n{str(e)}")

    def _run_merge_and_export(self, base_model_path, adapter_path, quant: str = None, *, base_model_name: str = None, level_name: str = None):
        """Runs the merge_and_export.py script in a separate thread."""
        if not messagebox.askyesno("Confirm Export", f"This will start the GGUF export process for:\n\nAdapter: {adapter_path.name}\n\nThis can take several minutes and consume significant RAM. Continue?"):
            return

        # Find the button to disable it - this is a bit complex
        # For now, we just run the process.

        self.append_runner_output(f"\n--- Starting GGUF Export for {adapter_path.name} ---\n")

        def _find_python_with_unsloth(candidates=None):
            """Search existing interpreters for Unsloth; do not install anything automatically."""
            import subprocess as _sp
            paths = candidates or []
            paths += [sys.executable, shutil.which('python3') or '', shutil.which('python') or '']
            # Common locations for venv/conda
            for root in [str(Path.home() / 'miniconda3' / 'envs'), str(Path.home() / '.pyenv' / 'versions')]:
                p = Path(root)
                if p.exists():
                    for d in p.iterdir():
                        cand = d / 'bin' / 'python'
                        if cand.exists():
                            paths.append(str(cand))
            tested = []
            for pth in [p for p in paths if p]:
                if pth in tested:
                    continue
                tested.append(pth)
                try:
                    out = _sp.check_output([pth, '-c', 'import unsloth,sys;log_message(sys.executable)'], text=True, stderr=_sp.DEVNULL, timeout=3)
                    return out.strip()
                except Exception:
                    continue
            return None

        def export_thread():
            try:
                # __file__ is Data/tabs/models_tab/models_tab.py; parent.parent.parent is Data/
                script_path = Path(__file__).parent.parent.parent / "merge_and_export.py"
                py_for_unsloth = _find_python_with_unsloth()
                py_exec = py_for_unsloth or sys.executable
                command = [py_exec, str(script_path), "--base", str(base_model_path), "--adapter", str(adapter_path)]
                if quant:
                    command += ["--quant", quant]
                env = os.environ.copy()
                if py_for_unsloth and py_for_unsloth != sys.executable:
                    env["UNSLOTH_PYTHON"] = py_for_unsloth
                process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=env)
                
                gguf_path_emitted = None
                output_buffer = []
                while True:
                    output = process.stdout.readline()
                    if output == '' and process.poll() is not None:
                        break
                    if output:
                        output_buffer.append(output)
                        # Try to capture GGUF_PATH line
                        if output.startswith('GGUF_PATH:'):
                            try:
                                gguf_path_emitted = output.split(':',1)[1].strip()
                            except Exception:
                                gguf_path_emitted = None
                        self.root.after(0, self.append_runner_output, output)
                
                rc = process.poll()
                if rc == 0:
                    # Create an Ollama model referencing the GGUF
                    try:
                        outdir = Path(gguf_path_emitted).parent if gguf_path_emitted else (Path(__file__).parent.parent.parent / 'exports' / 'gguf')
                        adapter_name = Path(str(adapter_path)).name
                        # Prefer manifest lineage/variant for tag naming when level_name present
                        variant_id_for_export = None
                        lineage_id_for_export = None
                        if base_model_name and level_name:
                            try:
                                clean_base = base_model_name.replace('/','_').replace(':','_')
                                mfpath = MODELS_DIR / 'archive' / 'levels' / clean_base / level_name / 'manifest.json'
                                if mfpath.exists():
                                    mdata = json.loads(mfpath.read_text())
                                    variant_id_for_export = mdata.get('variant_id')
                                    lineage_id_for_export = mdata.get('lineage_id')
                            except Exception:
                                pass
                        # Enforce one-GGUF per lineage: if lineage has assigned tags, ask to replace
                        if lineage_id_for_export:
                            try:
                                import config as C
                                existing_tags = C.get_assigned_tags_by_lineage(lineage_id_for_export)
                                if existing_tags:
                                    def _ask_replace():
                                        return messagebox.askyesno('Assigned Exists', f"A GGUF is already assigned for this variant lineage:\n{', '.join(existing_tags)}\n\nReplace with new export?")
                                    # Must query UI thread
                                    ans = []
                                    self.root.after(0, lambda: ans.append(_ask_replace()))
                                    while not ans:
                                        time.sleep(0.05)
                                    if not ans[0]:
                                        return
                            except Exception:
                                pass
                        # Tag policy
                        model_tag = f"{adapter_name}:latest"
                        if variant_id_for_export:
                            model_tag = f"{variant_id_for_export}:{(quant or 'q4_k_m')}"
                        modelfile = outdir / f"{adapter_name}.Modelfile"
                        gguf_path = gguf_path_emitted or str(outdir / f"{Path(base_model_path).name}-merged-{adapter_name}.{quant or 'q4_k_m'}.gguf")
                        mf = f"FROM {gguf_path}\nTEMPLATE \"{{{{ .Prompt }}}}\"\n"
                        Path(modelfile).write_text(mf)
                        create_cmd = ['ollama', 'create', model_tag, '-f', str(modelfile)]
                        self.root.after(0, self.append_runner_output, f"\n--- Creating Ollama model {model_tag} ---\n")
                        cproc = subprocess.Popen(create_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
                        while True:
                            l2 = cproc.stdout.readline()
                            if l2 == '' and cproc.poll() is not None:
                                break
                            if l2:
                                self.root.after(0, self.append_runner_output, l2)
                        crc = cproc.poll()
                        if crc == 0:
                            def _done():
                                # Update level manifest with export lineage
                                try:
                                    if base_model_name and level_name:
                                        clean_base = base_model_name.replace('/','_').replace(':','_')
                                        mfpath = MODELS_DIR / 'archive' / 'levels' / clean_base / level_name / 'manifest.json'
                                        if mfpath.exists():
                                            import json as _json
                                            with open(mfpath, 'r') as f:
                                                man = _json.load(f)
                                            ex = man.setdefault('exports', [])
                                            from datetime import datetime
                                            ex.append({
                                                'name': model_tag,
                                                'created': datetime.now().isoformat(),
                                                'gguf_path': gguf_path
                                            })
                                            with open(mfpath, 'w') as f:
                                                _json.dump(man, f, indent=2)
                                except Exception:
                                    pass
                                # Assignment update for variant lineage
                                try:
                                    if variant_id_for_export:
                                        import config as C
                                        C.add_ollama_assignment(variant_id_for_export, model_tag)
                                except Exception:
                                    pass
                                try:
                                    self.ollama_models = get_ollama_models()
                                    self.populate_model_list()
                                except Exception:
                                    pass
                                # Notify success
                                messagebox.showinfo("Export Complete", f"GGUF export finished and Ollama model created: {model_tag}")
                                # Prompt for rename of Ollama tag
                                try:
                                    from tkinter import simpledialog
                                    new_tag = simpledialog.askstring(
                                        "Rename Model",
                                        "Enter a new Ollama model tag (optional):",
                                        initialvalue=model_tag
                                    )
                                    if new_tag and new_tag.strip() and new_tag.strip() != model_tag:
                                        nt = new_tag.strip()
                                        # Try fast copy-rename; fallback to recreate from Modelfile
                                        try:
                                            rcp = subprocess.run(['ollama', 'cp', model_tag, nt], text=True, capture_output=True)
                                            if rcp.returncode == 0:
                                                subprocess.run(['ollama', 'rm', model_tag], text=True)
                                                # Update manifest export name
                                                try:
                                                    if base_model_name and level_name:
                                                        clean_base2 = base_model_name.replace('/','_').replace(':','_')
                                                        mfpath2 = MODELS_DIR / 'archive' / 'levels' / clean_base2 / level_name / 'manifest.json'
                                                        if mfpath2.exists():
                                                            import json as _json
                                                            with open(mfpath2, 'r') as f:
                                                                man2 = _json.load(f)
                                                            for it in (man2.get('exports') or []):
                                                                if it.get('name') == model_tag:
                                                                    it['name'] = nt
                                                            with open(mfpath2, 'w') as f:
                                                                _json.dump(man2, f, indent=2)
                                                except Exception:
                                                    pass
                                                messagebox.showinfo("Model Renamed", f"Ollama model renamed to: {nt}")
                                            else:
                                                # Fallback: recreate
                                                try:
                                                    subprocess.run(['ollama', 'create', nt, '-f', str(modelfile)], check=True, text=True)
                                                    subprocess.run(['ollama', 'rm', model_tag], text=True)
                                                    messagebox.showinfo("Model Renamed", f"Ollama model renamed to: {nt}")
                                                except Exception as re:
                                                    messagebox.showwarning("Rename Failed", f"Could not rename model: {re}")
                                        except Exception as re:
                                            messagebox.showwarning("Rename Failed", f"Could not rename model: {re}")
                                except Exception:
                                    pass
                            self.root.after(0, _done)
                        else:
                            self.root.after(0, lambda: messagebox.showwarning('Ollama', 'GGUF export complete, but failed to create Ollama model.'))
                    except Exception as e:
                        msg = f"GGUF export complete, but Ollama create failed: {e}"
                        self.root.after(0, lambda m=msg: messagebox.showwarning('Ollama', m))
                else:
                    # Provide clearer error if Unsloth was missing
                    combined = "".join(output_buffer)
                    # Persist full export log for troubleshooting
                    try:
                        from datetime import datetime
                        # __file__ is Data/tabs/models_tab/models_tab.py; parent.parent.parent is Data/
                        log_dir = Path(__file__).parent.parent.parent / 'DeBug'
                        log_dir.mkdir(parents=True, exist_ok=True)
                        log_path = log_dir / f"gguf_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
                        log_path.write_text(combined)
                    except Exception:
                        log_path = None
                    if "Unsloth is required for GGUF export" in combined:
                        self.root.after(0, lambda: messagebox.showerror(
                            "Export Failed",
                            "Unsloth is required for GGUF export.\n\nInstall Unsloth or export via another machine with GPU/Unsloth, or use a prebuilt GGUF from Ollama."
                        ))
                    else:
                        tail = combined.splitlines()[-10:]
                        msg = f"GGUF export failed with exit code {rc}.\n\n" + ("\n".join(tail) if tail else "(no output)")
                        if log_path:
                            msg += f"\n\nFull log: {log_path}"
                        self.root.after(0, lambda m=msg: messagebox.showerror("Export Failed", m))

            except Exception as e:
                msg = f"An error occurred: {e}"
                self.root.after(0, lambda m=msg: messagebox.showerror("Export Error", m))

        thread = threading.Thread(target=export_thread)
        thread.daemon = True
        thread.start()

    def _archive_adapter(self, adapter_path: Path):
        """Moves an adapter and its stats to the archive directory."""
        if not messagebox.askyesno("Confirm Archive", f"Archive the adapter '{adapter_path.name}'?"):
            return
        try:
            archive_dir = Path(self.current_model_info["path"]).parent.parent / "archive"
            archive_dir.mkdir(exist_ok=True)

            # Move adapter directory
            adapter_path.rename(archive_dir / adapter_path.name)

            # Move stats file
            stats_file = Path(self.current_model_info["path"]).parent / "training_stats" / f"{adapter_path.name}_stats.json"
            if stats_file.exists():
                stats_file.rename(archive_dir / stats_file.name)

            messagebox.showinfo("Archived", f"Adapter '{adapter_path.name}' has been archived.")
            self.refresh_models_tab()
        except Exception as e:
            messagebox.showerror("Archive Failed", f"Could not archive adapter: {e}")

    def _delete_adapter(self, adapter_path: Path):
        """Deletes an adapter and its stats permanently."""
        if not messagebox.askyesno("⚠️ CONFIRM DELETE ⚠️", f"PERMANENTLY DELETE the adapter '{adapter_path.name}' and its stats?\n\nThis action cannot be undone."):
            return
        try:
            import shutil
            # Delete adapter directory
            shutil.rmtree(adapter_path)

            # Delete stats file
            stats_file = Path(self.current_model_info["path"]).parent / "training_stats" / f"{adapter_path.name}_stats.json"
            if stats_file.exists():
                stats_file.unlink()

            messagebox.showinfo("Deleted", f"Adapter '{adapter_path.name}' has been permanently deleted.")
            self.refresh_models_tab()
        except Exception as e:
            messagebox.showerror("Delete Failed", f"Could not delete adapter: {e}")

    def append_runner_output(self, text):
        """Appends text to the evaluation output console for feedback."""
        self.eval_output_text.config(state=tk.NORMAL)
        self.eval_output_text.insert(tk.END, text)
        self.eval_output_text.see(tk.END)
        self.eval_output_text.config(state=tk.DISABLED)

    # Prompt: choose export target (Local GGUF vs Ollama)
    def _prompt_export_target(self):
        try:
            win = tk.Toplevel(self.root)
            win.title('Export Target')
            wrapper = ttk.Frame(win); wrapper.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
            ttk.Label(wrapper, text='Choose export target', style='Config.TLabel').grid(row=0, column=0, sticky=tk.W, columnspan=3)
            tgt = tk.StringVar(value='ollama')
            ttk.Radiobutton(wrapper, text='Create Ollama model', value='ollama', variable=tgt).grid(row=1, column=0, sticky=tk.W, pady=(6,2))
            ttk.Radiobutton(wrapper, text='Save Local GGUF', value='local', variable=tgt).grid(row=1, column=1, sticky=tk.W, pady=(6,2))
            # Local dir
            ttk.Label(wrapper, text='Local GGUF dir:', style='Config.TLabel').grid(row=2, column=0, sticky=tk.W, pady=(6,2))
            def _default_local_dir():
                here = Path(__file__).resolve()
                cands = [
                    here.parent.parent.parent / 'Models' / 'Local_gguf',
                    here.parent.parent.parent / 'exports' / 'gguf',
                ]
                for p in cands:
                    try:
                        if p.exists():
                            return str(p)
                    except Exception:
                        continue
                return str(cands[-1])
            out_var = tk.StringVar(value=_default_local_dir())
            ent = ttk.Entry(wrapper, textvariable=out_var, width=50)
            ent.grid(row=2, column=1, sticky=tk.EW)
            def browse():
                from tkinter import filedialog
                d = filedialog.askdirectory(title='Select Local GGUF Folder')
                if d:
                    out_var.set(d)
            ttk.Button(wrapper, text='Browse…', command=browse, style='Select.TButton').grid(row=2, column=2, sticky=tk.W, padx=(6,0))

            result = {'ok': False}
            def ok():
                result['ok'] = True
                win.destroy()
            def cancel():
                win.destroy()
            btns = ttk.Frame(wrapper); btns.grid(row=3, column=0, columnspan=3, sticky=tk.E, pady=(10,0))
            ttk.Button(btns, text='Cancel', style='Select.TButton', command=cancel).pack(side=tk.RIGHT, padx=6)
            ttk.Button(btns, text='OK', style='Action.TButton', command=ok).pack(side=tk.RIGHT)

            win.transient(self.root); win.grab_set(); win.focus_force()
            self.root.wait_window(win)
            if not result['ok']:
                return (None, None)
            return (tgt.get(), out_var.get())
        except Exception:
            return ('ollama', '')

    def _copy_name_to_clipboard(self):
        """Copies the current model's name to the clipboard."""
        if not self.current_model_info:
            return
        try:
            model_name = self.current_model_info['name']
            self.root.clipboard_clear()
            self.root.clipboard_append(model_name)
            # Give subtle feedback without a disruptive messagebox
            log_message(f"Copied to clipboard: {model_name}")
        except Exception as e:
            log_message(f"Failed to copy model name to clipboard: {e}")

    def rename_trained_model_action(self):
        """Renames a trained model folder and all its associated data files."""
        if not self.current_model_info or self.current_model_info["type"] != "trained":
            messagebox.showwarning("Invalid Model", "Can only rename trained models.")
            return

        old_path = Path(self.current_model_info["path"])
        old_name = old_path.name
        new_name = self.trained_rename_entry_var.get().strip()

        if not new_name or new_name == old_name:
            messagebox.showinfo("No Change", "New name is invalid or the same as the current name.")
            return

        new_path = old_path.with_name(new_name)
        if new_path.exists():
            messagebox.showerror("Exists", f"A directory named '{new_name}' already exists.")
            return

        confirm_msg = f"Rename trained model:\n\nFrom: {old_name}\nTo:   {new_name}\n\nThis will rename the folder and all associated data (stats, notes, evals). Continue?"
        if not messagebox.askyesno("Confirm Rename", confirm_msg):
            return

        try:
            # 1. Rename model directory
            old_path.rename(new_path)

            # 2. Rename stats file
            old_stats_file = Path(self.current_model_info["path"]).parent / "training_stats" / f"{old_name}_stats.json"
            if old_stats_file.exists():
                new_stats_file = old_stats_file.with_name(f"{new_name}_stats.json")
                old_stats_file.rename(new_stats_file)

            # 3. Rename notes directory
            old_notes_dir = Path(self.current_model_info["path"]).parent.parent / "model_notes" / old_name
            if old_notes_dir.exists():
                new_notes_dir = old_notes_dir.with_name(new_name)
                old_notes_dir.rename(new_notes_dir)

            # 4. Rename evaluation reports
            evals_dir = Path(self.current_model_info["path"]).parent / "evaluations"
            for report in evals_dir.glob(f"{old_name}_eval_*.json"):
                new_report_name = report.name.replace(old_name, new_name)
                report.rename(report.with_name(new_report_name))

            # 5. Rename baseline report
            baseline_report = Path(self.current_model_info["path"]).parent / "benchmarks" / f"{old_name}_baseline.json"
            if baseline_report.exists():
                new_baseline_name = baseline_report.name.replace(old_name, new_name)
                baseline_report.rename(baseline_report.with_name(new_baseline_name))

            messagebox.showinfo("Rename Successful", f"Model renamed to '{new_name}'.")
            self.refresh_models_tab()

        except Exception as e:
            messagebox.showerror("Rename Failed", f"An error occurred during rename: {e}")
            # Attempt to rollback if something failed mid-way
            if new_path.exists() and not old_path.exists():
                new_path.rename(old_path)
            self.refresh_models_tab()

    def delete_model(self):
        """Delete the selected Ollama model."""
        if not hasattr(self, 'current_model_for_notes') or not self.current_model_for_notes:
            messagebox.showwarning("No Model Selected", "Please select a model first.")
            return

        model_name = self.current_model_for_notes

        # Confirm deletion
        confirm_msg = f"⚠️ DELETE MODEL?\n\nModel: {model_name}\n\nThis will permanently delete the model from Ollama.\n\nThis action cannot be undone!\n\nContinue?"
        if not messagebox.askyesno("Confirm Delete", confirm_msg):
            return

        try:
            import subprocess
            result = subprocess.run(
                ["ollama", "rm", model_name],
                capture_output=True,
                text=True,
                check=True
            )

            messagebox.showinfo("Delete Successful", f"Model '{model_name}' has been deleted.")

            # If this tag was assigned to a variant lineage, remove the assignment
            try:
                import config as C
                lid = C.get_lineage_for_tag(model_name)
                if lid:
                    # Update tag_index by removing this tag
                    data = C.load_ollama_assignments() or {}
                    ti = data.get('tag_index') or {}
                    if model_name in ti:
                        ti.pop(model_name, None)
                        data['tag_index'] = ti
                        # Also remove from any variant entry that lists it
                        for k, v in list(data.items()):
                            if k == 'tag_index':
                                continue
                            if isinstance(v, dict):
                                tags = set(v.get('tags') or [])
                                if model_name in tags:
                                    tags.discard(model_name)
                                    v['tags'] = sorted(tags)
                                    data[k] = v
                            else:
                                lst = set(v or [])
                                if model_name in lst:
                                    lst.discard(model_name)
                                    data[k] = sorted(lst)
                        C.save_ollama_assignments(data)
            except Exception:
                pass

            # Refresh model list
            self.ollama_models = get_ollama_models()
            self.populate_model_list()

            # Clear the overview tab
            for widget in self.overview_tab_frame.winfo_children():
                widget.destroy()

            ttk.Label(self.overview_tab_frame, text="Select a model to view details",
                     font=("Arial", 12), style='Config.TLabel').pack(pady=20)

            # Clear other tabs
            self.current_model_for_notes = None
            self.current_model_for_stats = None
            self.notes_text.delete(1.0, tk.END)
            self.note_name_var.set("")
            self.populate_notes_list()
            self.populate_stats_display()
            # If a Variant was active, refresh its actions state (may re‑enable Create GGUF)
            try:
                self._refresh_overview_actions_state()
            except Exception:
                pass

        except subprocess.CalledProcessError as e:
            error_msg = e.stderr if e.stderr else str(e)
            messagebox.showerror("Delete Failed", f"Failed to delete model:\n\n{error_msg}")
        except Exception as e:
            messagebox.showerror("Delete Failed", f"An error occurred:\n\n{str(e)}")

    def _create_visualization_tab(self, parent):
        """Create integrated 2D+3D brain visualization (always-visible 2D tree + 3D view)."""
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(1, weight=1)

        # Control bar at top
        control_frame = ttk.Frame(parent)
        control_frame.grid(row=0, column=0, sticky=tk.EW, padx=5, pady=5)

        ttk.Label(
            control_frame,
            text="🧠 System Visualization",
            font=("Arial", 12, "bold"),
            style='CategoryPanel.TLabel'
        ).pack(side=tk.LEFT, padx=(5, 15))

        # Container for visualization content
        self.viz_container = ttk.Frame(parent)
        self.viz_container.grid(row=1, column=0, sticky=tk.NSEW, padx=5, pady=5)
        self.viz_container.columnconfigure(0, weight=1)
        self.viz_container.rowconfigure(0, weight=1)

        # Create integrated 2D+3D view
        self._create_3d_brain_view()

    def _switch_viz_mode(self):
        """Legacy shim (no-op): integrated view is always active."""
        # Clear and recreate integrated view if needed
        for widget in self.viz_container.winfo_children():
            widget.destroy()
        self._create_3d_brain_view()

    def _create_2d_tree_view(self):
        """Legacy 2D view (deprecated): integrated 2D tree exists inside 3D view."""
        # For backward compatibility, redirect to integrated view
        for widget in self.viz_container.winfo_children():
            widget.destroy()
        self._create_3d_brain_view()

    def _build_system_tree(self, parent):
        """Deprecated: replaced by integrated Treeview in brain_viz_3d."""
        ttk.Label(parent, text="Integrated 2D tree is now part of the 3D Brain view.",
                  style='Config.TLabel').grid(row=0, column=0, sticky=tk.W, padx=10, pady=10)

    def _on_tree_item_click(self, item_name):
        """Handle click on tree item"""
        messagebox.showinfo("Component", f"Selected: {item_name}\n\nComponent details and navigation will be implemented here.")

    def _create_3d_brain_view(self):
        """Create 3D neural network brain visualization"""
        try:
            from tabs.models_tab.brain_viz_3d import Brain3DVisualization

            # Create 3D brain visualization
            self.brain_viz_3d = Brain3DVisualization(self.viz_container, self.style)
            # Provide optional callbacks for opening files / navigating tabs
            try:
                self.brain_viz_3d.open_file_callback = self._open_source_file_from_brain
                self.brain_viz_3d.open_tab_callback = self._open_related_tab_from_brain
            except Exception:
                pass
            self.brain_viz_3d.grid(row=0, column=0, sticky=tk.NSEW)

            # If a model is currently selected, load it into the brain
            if hasattr(self, 'current_model_for_stats') and self.current_model_for_stats:
                try:
                    import Data.config as config
                    model_data = config.load_model_profile(self.current_model_for_stats)
                    if model_data:
                        self.brain_viz_3d.load_model_kernel(model_data)
                except Exception as e:
                    log_message(f"Could not load model into brain: {e}")

        except Exception as e:
            log_message(f"Error creating 3D brain visualization: {e}")
            import traceback
            traceback.print_exc()

            # Fallback to error message
            error_label = ttk.Label(
                self.viz_container,
                text=f"3D visualization unavailable: {e}\n\nPlease ensure matplotlib is installed.",
                style='Config.TLabel'
            )
            error_label.grid(row=0, column=0, padx=20, pady=20)

    def _open_source_file_from_brain(self, rel_path: str):
        """Open a source file from Brain viz (show in-app viewer if available or OS)."""
        try:
            import os, subprocess, sys
            # If there is a central file viewer, wire it here (future enhancement)
            # Fallback: OS default
            base = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
            abs_path = os.path.abspath(os.path.join(base, rel_path))
            if sys.platform.startswith('win'):
                os.startfile(abs_path)  # noqa: P204
            elif sys.platform == 'darwin':
                subprocess.Popen(['open', abs_path])
            else:
                subprocess.Popen(['xdg-open', abs_path])
        except Exception as e:
            log_message(f"Open source file failed: {e}")

    def _open_related_tab_from_brain(self, region_name: str):
        """Best-effort navigation from Brain viz to relevant tab/section."""
        try:
            name = (region_name or '').lower()
            # Heuristics: open appropriate tab for region
            # Available tabs within this class are not all accessible here;
            # for now, show a message and leave a hook for future integration.
            import tkinter.messagebox as messagebox
            messagebox.showinfo("Navigation", f"Navigate to related tab for: {region_name}")
        except Exception as e:
            log_message(f"Open related tab failed: {e}")

    def create_find_models_panel(self, parent):
        """Create the Find Models panel for searching and downloading models from HuggingFace"""
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(2, weight=1)

        # Header
        header_frame = ttk.Frame(parent, style='Category.TFrame')
        header_frame.grid(row=0, column=0, sticky=tk.EW, padx=10, pady=10)

        ttk.Label(
            header_frame,
            text="🔍 Find and Download Models",
            font=("Arial", 14, "bold"),
            style='CategoryPanel.TLabel'
        ).pack(side=tk.LEFT)

        ttk.Label(
            header_frame,
            text="Search HuggingFace for PyTorch models to download",
            style='Config.TLabel'
        ).pack(side=tk.LEFT, padx=20)

        # Search frame
        search_frame = ttk.LabelFrame(parent, text="Search", padding=10, style='Category.TFrame')
        search_frame.grid(row=1, column=0, sticky=tk.EW, padx=10, pady=(0, 10))
        search_frame.columnconfigure(1, weight=1)

        ttk.Label(search_frame, text="Search Query:", style='Config.TLabel').grid(row=0, column=0, sticky=tk.W, padx=(0, 10))
        self.find_search_var = tk.StringVar()
        search_entry = ttk.Entry(search_frame, textvariable=self.find_search_var, width=40)
        search_entry.grid(row=0, column=1, sticky=tk.EW, padx=(0, 10))
        search_entry.bind('<Return>', lambda e: self._search_huggingface_models())

        ttk.Button(
            search_frame,
            text="🔍 Search",
            command=self._search_huggingface_models,
            style='Action.TButton'
        ).grid(row=0, column=2, padx=5)

        # Filters
        ttk.Label(search_frame, text="Task:", style='Config.TLabel').grid(row=1, column=0, sticky=tk.W, padx=(0, 10), pady=(10, 0))
        self.find_task_var = tk.StringVar(value="text-generation")
        task_combo = ttk.Combobox(
            search_frame,
            textvariable=self.find_task_var,
            values=["text-generation", "text-classification", "token-classification",
                    "question-answering", "summarization", "translation", "conversational", "all"],
            state="readonly",
            width=25
        )
        task_combo.grid(row=1, column=1, sticky=tk.W, pady=(10, 0))

        ttk.Label(search_frame, text="Sort:", style='Config.TLabel').grid(row=1, column=2, sticky=tk.W, padx=(20, 10), pady=(10, 0))
        self.find_sort_var = tk.StringVar(value="downloads")
        sort_combo = ttk.Combobox(
            search_frame,
            textvariable=self.find_sort_var,
            values=["downloads", "likes", "updated", "created"],
            state="readonly",
            width=15
        )
        sort_combo.grid(row=1, column=3, sticky=tk.W, pady=(10, 0))

        # Results frame
        results_frame = ttk.LabelFrame(parent, text="Search Results", padding=10, style='Category.TFrame')
        results_frame.grid(row=2, column=0, sticky=tk.NSEW, padx=10, pady=(0, 10))
        results_frame.columnconfigure(0, weight=1)
        results_frame.rowconfigure(0, weight=1)

        # Treeview for results
        tree_frame = ttk.Frame(results_frame)
        tree_frame.grid(row=0, column=0, sticky=tk.NSEW)
        tree_frame.columnconfigure(0, weight=1)
        tree_frame.rowconfigure(0, weight=1)

        tree_scroll = ttk.Scrollbar(tree_frame, orient="vertical")
        tree_scroll.grid(row=0, column=1, sticky=tk.NS)

        self.find_models_tree = ttk.Treeview(
            tree_frame,
            columns=("model_id", "downloads", "likes", "updated", "size"),
            show="tree headings",
            yscrollcommand=tree_scroll.set,
            height=15
        )
        self.find_models_tree.grid(row=0, column=0, sticky=tk.NSEW)
        tree_scroll.config(command=self.find_models_tree.yview)

        # Configure columns
        self.find_models_tree.heading("#0", text="Model Name", anchor=tk.W)
        self.find_models_tree.heading("model_id", text="Model ID", anchor=tk.W)
        self.find_models_tree.heading("downloads", text="Downloads", anchor=tk.E)
        self.find_models_tree.heading("likes", text="Likes", anchor=tk.E)
        self.find_models_tree.heading("updated", text="Updated", anchor=tk.W)
        self.find_models_tree.heading("size", text="Size", anchor=tk.E)

        self.find_models_tree.column("#0", width=250, minwidth=150)
        self.find_models_tree.column("model_id", width=250, minwidth=150)
        self.find_models_tree.column("downloads", width=100, minwidth=80, anchor=tk.E)
        self.find_models_tree.column("likes", width=80, minwidth=60, anchor=tk.E)
        self.find_models_tree.column("updated", width=120, minwidth=100)
        self.find_models_tree.column("size", width=100, minwidth=80, anchor=tk.E)

        # Bind selection
        self.find_models_tree.bind('<<TreeviewSelect>>', self._on_model_select)

        # Details frame
        details_frame = ttk.LabelFrame(results_frame, text="Model Details", padding=10, style='Category.TFrame')
        details_frame.grid(row=1, column=0, sticky=tk.EW, pady=(10, 0))
        details_frame.columnconfigure(0, weight=1)

        self.find_details_text = scrolledtext.ScrolledText(
            details_frame,
            height=8,
            wrap=tk.WORD,
            bg="#1e1e1e",
            fg="#d4d4d4",
            insertbackground="#d4d4d4",
            font=("Consolas", 10)
        )
        self.find_details_text.grid(row=0, column=0, sticky=tk.NSEW)

        # Action buttons
        action_frame = ttk.Frame(results_frame)
        action_frame.grid(row=2, column=0, sticky=tk.EW, pady=(10, 0))

        ttk.Button(
            action_frame,
            text="📥 Download Model",
            command=self._download_selected_model,
            style='Action.TButton'
        ).pack(side=tk.LEFT, padx=5)

        ttk.Button(
            action_frame,
            text="🌐 Open on HuggingFace",
            command=self._open_model_on_huggingface,
            style='Select.TButton'
        ).pack(side=tk.LEFT, padx=5)

        # Progress frame (hidden by default)
        self.find_progress_frame = ttk.Frame(results_frame)
        self.find_progress_label = ttk.Label(self.find_progress_frame, text="", style='Config.TLabel')
        self.find_progress_label.pack(side=tk.LEFT, padx=10)
        self.find_progress_bar = ttk.Progressbar(self.find_progress_frame, mode='determinate', length=400)
        self.find_progress_bar.pack(side=tk.LEFT, padx=10)
        self.find_progress_bytes = ttk.Label(self.find_progress_frame, text="", style='Config.TLabel')
        self.find_progress_bytes.pack(side=tk.LEFT, padx=10)

        # Initialize state
        self.find_selected_model = None
        self.find_search_results = []

    def _search_huggingface_models(self):
        """Search HuggingFace for models matching query"""
        try:
            query = self.find_search_var.get().strip()
            task = self.find_task_var.get()
            sort = self.find_sort_var.get()

            if not query and task == "all":
                messagebox.showwarning("Search Required", "Please enter a search query or select a specific task")
                return

            # Clear previous results
            for item in self.find_models_tree.get_children():
                self.find_models_tree.delete(item)
            self.find_details_text.delete(1.0, tk.END)
            self.find_selected_model = None

            # Show progress
            self.find_progress_frame.grid(row=3, column=0, sticky=tk.EW, pady=(10, 0))
            self.find_progress_label.config(text="Searching HuggingFace...")
            self.find_progress_bar.start(10)

            # Run search in background thread
            def search_thread():
                try:
                    from huggingface_hub import HfApi
                    api = HfApi()

                    # Build search kwargs
                    search_kwargs = {
                        "sort": sort,
                        "direction": -1,
                        "limit": 50
                    }
                    if query:
                        search_kwargs["search"] = query
                    if task != "all":
                        search_kwargs["filter"] = task

                    models = list(api.list_models(**search_kwargs))
                    self.find_search_results = models

                    # Update UI in main thread
                    self.root.after(0, lambda: self._display_search_results(models))
                except Exception as e:
                    self.root.after(0, lambda: self._search_error(str(e)))

            threading.Thread(target=search_thread, daemon=True).start()

        except Exception as e:
            log_message(f"MODELS_TAB: Search error: {e}")
            messagebox.showerror("Search Error", f"Failed to search models: {e}")

    def _display_search_results(self, models):
        """Display search results in treeview"""
        try:
            # Stop progress
            self.find_progress_bar.stop()
            self.find_progress_frame.grid_forget()

            if not models:
                self.find_details_text.insert(tk.END, "No models found. Try a different search query or task.")
                return

            # Populate treeview
            for model in models:
                model_id = model.modelId or "Unknown"
                downloads = f"{model.downloads:,}" if model.downloads else "0"
                likes = f"{model.likes:,}" if model.likes else "0"
                updated = model.lastModified.strftime("%Y-%m-%d") if model.lastModified else "Unknown"

                # Estimate size from siblings if available
                size = "Unknown"
                if hasattr(model, 'siblings') and model.siblings:
                    total_size = sum(s.size for s in model.siblings if hasattr(s, 'size') and s.size)
                    if total_size > 0:
                        size = self._format_size(total_size)

                # Extract display name
                display_name = model_id.split('/')[-1] if '/' in model_id else model_id

                self.find_models_tree.insert(
                    "",
                    tk.END,
                    text=display_name,
                    values=(model_id, downloads, likes, updated, size),
                    tags=(model_id,)
                )

            self.find_details_text.insert(tk.END, f"Found {len(models)} models. Select a model to view details.")
            log_message(f"MODELS_TAB: Found {len(models)} models")

        except Exception as e:
            log_message(f"MODELS_TAB: Display results error: {e}")
            self.find_details_text.insert(tk.END, f"Error displaying results: {e}")

    def _search_error(self, error_msg):
        """Handle search error"""
        self.find_progress_bar.stop()
        self.find_progress_frame.grid_forget()
        self.find_details_text.delete(1.0, tk.END)
        self.find_details_text.insert(tk.END, f"Search failed: {error_msg}\n\nMake sure you have internet connection and huggingface_hub is installed.")
        log_message(f"MODELS_TAB: Search error: {error_msg}")

    def _format_size(self, bytes_size):
        """Format bytes to human readable size"""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if bytes_size < 1024.0:
                return f"{bytes_size:.1f} {unit}"
            bytes_size /= 1024.0
        return f"{bytes_size:.1f} PB"

    def _on_model_select(self, event):
        """Handle model selection in treeview"""
        try:
            selection = self.find_models_tree.selection()
            if not selection:
                return

            item = selection[0]
            model_id = self.find_models_tree.item(item)['values'][0]

            # Find model in results
            model = next((m for m in self.find_search_results if m.modelId == model_id), None)
            if not model:
                return

            self.find_selected_model = model

            # Display details
            self.find_details_text.delete(1.0, tk.END)
            self.find_details_text.insert(tk.END, f"Model ID: {model.modelId}\n")
            self.find_details_text.insert(tk.END, f"Author: {model.author or 'Unknown'}\n")
            self.find_details_text.insert(tk.END, f"Downloads: {model.downloads:,}\n")
            self.find_details_text.insert(tk.END, f"Likes: {model.likes:,}\n")
            if model.lastModified:
                self.find_details_text.insert(tk.END, f"Last Modified: {model.lastModified.strftime('%Y-%m-%d %H:%M:%S')}\n")
            if hasattr(model, 'pipeline_tag') and model.pipeline_tag:
                self.find_details_text.insert(tk.END, f"Pipeline: {model.pipeline_tag}\n")
            if hasattr(model, 'tags') and model.tags:
                self.find_details_text.insert(tk.END, f"Tags: {', '.join(model.tags[:10])}\n")
            self.find_details_text.insert(tk.END, f"\nURL: https://huggingface.co/{model.modelId}\n")

        except Exception as e:
            log_message(f"MODELS_TAB: Model select error: {e}")

    def _open_model_on_huggingface(self):
        """Open selected model page on HuggingFace"""
        try:
            if not self.find_selected_model:
                messagebox.showwarning("No Selection", "Please select a model first")
                return

            import webbrowser
            url = f"https://huggingface.co/{self.find_selected_model.modelId}"
            webbrowser.open(url)

        except Exception as e:
            log_message(f"MODELS_TAB: Open HF error: {e}")
            messagebox.showerror("Error", f"Failed to open browser: {e}")

    def _download_selected_model(self):
        """Download selected model from HuggingFace"""
        try:
            if not self.find_selected_model:
                messagebox.showwarning("No Selection", "Please select a model to download")
                return

            model_id = self.find_selected_model.modelId

            # Confirm download
            confirm = messagebox.askyesno(
                "Download Model",
                f"Download model: {model_id}\n\n"
                f"This will download the model files to your local system.\n"
                f"The model will be added to your available models list.\n\n"
                f"Continue?"
            )

            if not confirm:
                return

            # Show progress
            self.find_progress_frame.grid(row=3, column=0, sticky=tk.EW, pady=(10, 0))
            self.find_progress_label.config(text=f"Downloading {model_id}...")
            self.find_progress_bar['value'] = 0
            self.find_progress_bytes.config(text="Preparing...")

            # Run download in background
            def download_thread():
                try:
                    from huggingface_hub import snapshot_download
                    import uuid
                    import os
                    import time

                    # Download to Models directory
                    models_dir = MODELS_DIR
                    model_name = model_id.split('/')[-1]
                    local_dir = models_dir / model_name

                    log_message(f"MODELS_TAB: Downloading {model_id} to {local_dir}")

                    # Start progress monitoring thread
                    download_active = [True]  # Using list so inner function can modify

                    def monitor_progress():
                        """Monitor download progress by checking directory size"""
                        last_size = 0
                        stall_count = 0
                        while download_active[0]:
                            try:
                                # Calculate directory size
                                if os.path.exists(local_dir):
                                    total_size = 0
                                    for dirpath, dirnames, filenames in os.walk(local_dir):
                                        for f in filenames:
                                            fp = os.path.join(dirpath, f)
                                            if os.path.exists(fp):
                                                total_size += os.path.getsize(fp)

                                    # Update UI
                                    size_mb = total_size / (1024 * 1024)
                                    size_gb = total_size / (1024 * 1024 * 1024)

                                    if size_gb >= 1:
                                        size_str = f"{size_gb:.2f} GB"
                                    else:
                                        size_str = f"{size_mb:.1f} MB"

                                    self.root.after(0, lambda s=size_str: self.find_progress_bytes.config(text=s))

                                    # Check if download is progressing
                                    if total_size > last_size:
                                        stall_count = 0
                                        last_size = total_size
                                    else:
                                        stall_count += 1

                                    # If stalled for too long, might be done or stuck
                                    if stall_count > 10:  # 10 seconds with no change
                                        pass  # Continue monitoring until download_active set to False

                            except Exception as e:
                                log_message(f"MODELS_TAB: Progress monitor error: {e}")

                            time.sleep(1)  # Check every second

                    # Start monitoring in separate thread
                    monitor_thread = threading.Thread(target=monitor_progress, daemon=True)
                    monitor_thread.start()

                    # Update progress label with file count
                    def update_progress(filename):
                        try:
                            self.root.after(0, lambda: self.find_progress_label.config(
                                text=f"Downloading {model_id}... ({filename})"
                            ))
                        except:
                            pass

                    # Download model with progress callback
                    # Check if model requires authentication
                    log_message(f"MODELS_TAB: Starting download of {model_id}")

                    snapshot_download(
                        repo_id=model_id,
                        local_dir=str(local_dir),
                        local_dir_use_symlinks=False,
                        resume_download=True,
                        max_workers=4,
                        token=True  # Use cached HF token if available
                    )

                    log_message(f"MODELS_TAB: Download completed for {model_id}")

                    # Stop progress monitoring
                    download_active[0] = False

                    # Update to show completion
                    self.root.after(0, lambda: self.find_progress_label.config(
                        text=f"Finalizing {model_id}..."
                    ))

                    # Create proper model profile with lineage_id
                    profile = {
                        "trainee_name": model_name,
                        "base_model": model_id,  # HF model ID as base
                        "assigned_type": "unassigned",
                        "class_level": "novice",
                        "xp": 0,
                        "latest_eval_score": 0.0,
                        "stats": {},
                        "skills": {},
                        "badges": [],
                        "source": "huggingface",
                        "local_path": str(local_dir),
                        "hf_metadata": {
                            "model_id": model_id,
                            "downloads": self.find_selected_model.downloads,
                            "likes": self.find_selected_model.likes,
                            "tags": getattr(self.find_selected_model, 'tags', []),
                            "author": self.find_selected_model.author,
                            "pipeline_tag": getattr(self.find_selected_model, 'pipeline_tag', None),
                            "last_modified": self.find_selected_model.lastModified.isoformat() if self.find_selected_model.lastModified else None
                        },
                        "downloaded_at": __import__('datetime').datetime.now().isoformat(),
                        "evolution_metadata": {
                            "capacity_score": 0.0,
                            "capacity_level": "green",
                            "safe_to_train": True,
                            "regression_score": 0.0
                        }
                    }

                    # Save using proper helper (automatically assigns lineage_id)
                    config.save_model_profile(model_name, profile)
                    model_uid = config.ensure_lineage_id(model_name)

                    log_message(f"MODELS_TAB: Downloaded {model_id} successfully")

                    # Sync Bundle Registry with new HF download
                    try:
                        from registry.bundle_loader import sync_bundles_from_profiles
                        log_message(f"MODELS_TAB: Syncing bundle registry after HF download: {model_name}")
                        sync_result = sync_bundles_from_profiles(verbose=False)
                        if sync_result and sync_result.get('errors'):
                            log_message(f"MODELS_TAB: Bundle sync warnings: {sync_result.get('errors')}")
                        elif sync_result:
                            log_message(f"MODELS_TAB: Bundle sync complete - created={sync_result.get('bundles_created', 0)}")
                    except Exception as exc:
                        log_message(f"MODELS_TAB: Failed to sync bundles after HF download: {exc}")

                    # Update UI in main thread
                    self.root.after(0, lambda: self._download_complete(model_name, model_uid))

                except Exception as e:
                    # Stop progress monitoring
                    download_active[0] = False

                    error_msg = str(e)
                    log_message(f"MODELS_TAB: Download error: {e}")

                    # Check for specific error types
                    if "401" in error_msg or "authentication" in error_msg.lower() or "gated" in error_msg.lower():
                        error_msg = (
                            f"Authentication required for {model_id}\n\n"
                            "This is a gated model. To download:\n"
                            "1. Go to https://huggingface.co and create an account\n"
                            "2. Accept the model's license agreement\n"
                            "3. Generate an access token at: https://huggingface.co/settings/tokens\n"
                            "4. Run in terminal: huggingface-cli login\n"
                            "5. Paste your token when prompted\n\n"
                            f"Original error: {error_msg}"
                        )

                    self.root.after(0, lambda: self._download_error(error_msg))

            threading.Thread(target=download_thread, daemon=True).start()

        except Exception as e:
            log_message(f"MODELS_TAB: Download setup error: {e}")
            messagebox.showerror("Download Error", f"Failed to start download: {e}")

    def _download_complete(self, model_name, model_uid):
        """Handle successful download"""
        try:
            self.find_progress_bar.stop()
            self.find_progress_frame.grid_forget()

            messagebox.showinfo(
                "Download Complete",
                f"Model '{model_name}' downloaded successfully!\n\n"
                f"UID: {model_uid}\n\n"
                f"The model has been added to your available models."
            )

            # Refresh models list
            self.refresh_models_tab()

        except Exception as e:
            log_message(f"MODELS_TAB: Download complete error: {e}")

    def _download_error(self, error_msg):
        """Handle download error"""
        self.find_progress_bar.stop()
        self.find_progress_frame.grid_forget()
        messagebox.showerror(
            "Download Failed",
            f"Failed to download model:\n\n{error_msg}"
        )
        log_message(f"MODELS_TAB: Download failed: {error_msg}")
