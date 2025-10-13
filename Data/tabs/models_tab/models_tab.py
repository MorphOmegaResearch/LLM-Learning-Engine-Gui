# [SYSTEM: GUI | VERSION: 1.9f | STATUS: ACTIVE]
"""
Models Tab - Model information, notes, and statistics
Isolated module for models-related functionality
"""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from pathlib import Path
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

        # Overview Tab
        self.overview_tab_frame = ttk.Frame(self.model_info_notebook)
        self.model_info_notebook.add(self.overview_tab_frame, text="Overview")
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
            print("[DEBUG] ModelsTab: TypesPanel instantiated")
            self.panel_types.set_context_getters(
                get_trainee=lambda: getattr(self, "current_model_for_stats", None),
                get_base_model=lambda: getattr(self, "current_model_info", {}).get("name")
            )
            print("[DEBUG] ModelsTab: set_context_getters called")
            # If TypesPanel packs itself, do nothing; otherwise:
            try:
                if hasattr(self.panel_types, "pack"):
                    print("[DEBUG] ModelsTab: Packing TypesPanel")
                    self.panel_types.pack(fill=tk.BOTH, expand=True, padx=10, pady=10) # Changed tk.X to tk.BOTH and added expand=True
            except Exception as e:
                print(f"[DEBUG] ModelsTab: Error packing TypesPanel: {e}")

            # Bind the event bridge (safe even if Training tab misses apply_plan)
            try:
                self.panel_types.bind("<<TypePlanApplied>>", self._on_type_plan_applied)
            except Exception:
                pass
        except Exception as _e:
            # Keep UI resilient if TypesPanel import fails
            print("[ModelsTab] TypesPanel unavailable:", _e)

        # Adapters Tab (New)
        self.adapters_tab_frame = ttk.Frame(self.model_info_notebook)
        self.model_info_notebook.add(self.adapters_tab_frame, text="🎯 Adapters")

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
        self.raw_model_info_text.config(background='#1e1e1e', foreground='#61dafb') # Fallback styling

        # Notes Tab
        self.notes_tab_frame = ttk.Frame(self.model_info_notebook)
        self.model_info_notebook.add(self.notes_tab_frame, text="Notes")
        self.create_notes_panel(self.notes_tab_frame)

        # Stats Tab
        self.stats_tab_frame = ttk.Frame(self.model_info_notebook)
        self.model_info_notebook.add(self.stats_tab_frame, text="Stats")
        self.create_stats_panel(self.stats_tab_frame)

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

        # Right side: Two scrollable lists (Base/Levels/Trained) and (Ollama)
        model_list_frame = ttk.Frame(parent, style='Category.TFrame')
        model_list_frame.grid(row=0, column=1, sticky=tk.NSEW, padx=10, pady=10)
        model_list_frame.columnconfigure(0, weight=1)
        model_list_frame.rowconfigure(3, weight=1)

        ttk.Label(model_list_frame, text="Available Models", font=("Arial", 12, "bold"), style='CategoryPanel.TLabel').grid(row=0, column=0, pady=5, sticky=tk.W)

        # Base/Levels/Trained canvas
        base_canvas = tk.Canvas(model_list_frame, bg="#2b2b2b", highlightthickness=0)
        base_scrollbar = ttk.Scrollbar(model_list_frame, orient="vertical", command=base_canvas.yview)
        self.base_buttons_frame = ttk.Frame(base_canvas)
        self.base_buttons_frame.bind("<Configure>", lambda e: base_canvas.configure(scrollregion=base_canvas.bbox("all")))
        self.base_canvas_window_id = base_canvas.create_window((0, 0), window=self.base_buttons_frame, anchor="nw")
        base_canvas.configure(yscrollcommand=base_scrollbar.set)
        base_canvas.grid(row=1, column=0, sticky=tk.NSEW)
        base_scrollbar.grid(row=1, column=1, sticky=tk.NS)
        base_canvas.bind("<Configure>", lambda e: base_canvas.itemconfig(self.base_canvas_window_id, width=e.width))

        # Enable mousewheel scrolling for base models list
        self.bind_mousewheel_to_canvas(base_canvas)

        # Ollama header
        ttk.Label(model_list_frame, text="🟡 Ollama Models (GGUF)", font=("Arial", 12, "bold"), style='CategoryPanel.TLabel').grid(row=2, column=0, pady=(10,5), sticky=tk.W)

        # Ollama canvas
        oll_canvas = tk.Canvas(model_list_frame, bg="#2b2b2b", highlightthickness=0)
        oll_scrollbar = ttk.Scrollbar(model_list_frame, orient="vertical", command=oll_canvas.yview)
        self.ollama_buttons_frame = ttk.Frame(oll_canvas)
        self.ollama_buttons_frame.bind("<Configure>", lambda e: oll_canvas.configure(scrollregion=oll_canvas.bbox("all")))
        self.ollama_canvas_window_id = oll_canvas.create_window((0, 0), window=self.ollama_buttons_frame, anchor="nw")
        oll_canvas.configure(yscrollcommand=oll_scrollbar.set)
        oll_canvas.grid(row=3, column=0, sticky=tk.NSEW)
        oll_scrollbar.grid(row=3, column=1, sticky=tk.NS)
        oll_canvas.bind("<Configure>", lambda e: oll_canvas.itemconfig(self.ollama_canvas_window_id, width=e.width))

        # --- WO-6b: Collections panel ---------------------------------------
        self.collections_section = ttk.LabelFrame(model_list_frame, text="Collections")
        self.collections_section.grid(row=4, column=0, columnspan=2, sticky=tk.NSEW, padx=4, pady=6) # Adjusted row and columnspan
        self.collections_section.columnconfigure(0, weight=1) # Allow listbox to expand

        # simple listbox for now
        self.collections_list = tk.Listbox(self.collections_section, height=8, exportselection=False)
        self.collections_list.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)

        # optional: little refresh button
        self.collections_refresh_btn = ttk.Button(self.collections_section, text="Refresh", command=self.refresh_collections_panel)
        self.collections_refresh_btn.pack(anchor="e", padx=6, pady=(0,6))

        self.collections_list.bind("<<ListboxSelect>>", self._on_collection_pick)
        # --------------------------------------------------------------------

        # Enable mousewheel scrolling for Ollama models list
        self.bind_mousewheel_to_canvas(oll_canvas)

        # Expanded state for Ollama groups
        self.ollama_expanded = {}
        self.ollama_ui = {}

        self.populate_model_list()
        self.refresh_collections_panel() # Call after UI is built

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

        print("✓ Models tab refreshed")

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
            print("[ModelsTab] TypePlanApplied missing variant_id; ignoring.")
            return

        # Relay to TrainingTab on the UI thread
        try:
            tt = self.get_training_tab()
            if tt and hasattr(tt, "apply_plan"):
                self.root.after(50, lambda: tt.apply_plan(variant_id=variant_id))
                print(f"[ModelsTab] Relayed TypePlan to TrainingTab (variant={variant_id}).")
            else:
                print("[ModelsTab] TrainingTab.apply_plan not found.")
        except Exception as e:
            print("[ModelsTab] Error relaying TypePlan:", e)

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

        # Populate Ollama grouped by base (using level manifests if available)
        if ollama_models:
            grouped = self._group_ollama_by_base([m['name'] for m in ollama_models])
            for base_name, names in grouped.items():
                # Header row with arrow
                row = ttk.Frame(self.ollama_buttons_frame)
                row.pack(fill=tk.X, padx=5, pady=2)
                self.ollama_expanded[base_name] = self.ollama_expanded.get(base_name, False)
                arrow_btn = ttk.Button(row, text=('▼' if self.ollama_expanded[base_name] else '▶'), width=2,
                                       command=lambda b=base_name: self._toggle_ollama_group(b), style='Select.TButton')
                arrow_btn.pack(side=tk.LEFT, padx=(0,5))
                ttk.Label(row, text=base_name, style='Config.TLabel', foreground='#61dafb').pack(side=tk.LEFT)
                cont = ttk.Frame(self.ollama_buttons_frame)
                self.ollama_ui[base_name] = { 'arrow': arrow_btn, 'container': cont }
                for n in names:
                    ttk.Button(cont, text=f"   🔶 {n} • inference-only", command=lambda name=n: self.display_model_info({'name':name,'type':'ollama'}), style='Select.TButton').pack(fill=tk.X, padx=25, pady=1)
                if self.ollama_expanded[base_name] and names:
                    cont.pack(fill=tk.X)

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

        # Selected Model Display
        self.selected_model_label_eval = ttk.Label(
            controls_frame,
            text="Selected Model: None",
            font=("Arial", 10, "bold"),
            style='Config.TLabel',
            foreground='#61dafb'
        )
        self.selected_model_label_eval.grid(row=0, column=0, columnspan=3, sticky=tk.W, padx=5, pady=5)

        # Source display (Ollama/PyTorch)
        self.eval_source_label = ttk.Label(
            controls_frame,
            text="Source: Unknown",
            font=("Arial", 9),
            style='Config.TLabel',
            foreground='#bbbbbb'
        )
        self.eval_source_label.grid(row=0, column=2, sticky=tk.E, padx=5, pady=5)

        # Test suite dropdown
        ttk.Label(controls_frame, text="Test Suite:", style='Config.TLabel').grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
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
        self.test_suite_combo.grid(row=1, column=1, sticky=tk.EW, padx=5, pady=5)
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
        ).grid(row=2, column=0, sticky=tk.W, padx=5, pady=5)

        self.system_prompt_var = tk.StringVar()
        self.system_prompt_combo = ttk.Combobox(
            controls_frame,
            textvariable=self.system_prompt_var,
            values=list_system_prompts(),
            state="readonly",
            width=20
        )
        self.system_prompt_combo.grid(row=2, column=1, sticky=tk.EW, padx=5, pady=5)
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
        ).grid(row=3, column=0, sticky=tk.W, padx=5, pady=5)

        self.tool_schema_var = tk.StringVar()
        self.tool_schema_combo = ttk.Combobox(
            controls_frame,
            textvariable=self.tool_schema_var,
            values=list_tool_schemas(),
            state="readonly",
            width=20
        )
        self.tool_schema_combo.grid(row=3, column=1, sticky=tk.EW, padx=5, pady=5)
        self.tool_schema_combo.set("None") # Default
        self.tool_schema_combo.config(state=tk.DISABLED) # Initially disabled

        # Baseline checkbox
        self.run_as_baseline_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            controls_frame,
            text="Run as Pre-Training Baseline",
            variable=self.run_as_baseline_var,
            style='Config.TCheckbutton'
        ).grid(row=4, column=0, sticky=tk.W, padx=5, pady=5)

        # Regression check toggle (compare vs baseline after run)
        self.eval_regression_check_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            controls_frame,
            text="Regression Check (compare vs baseline)",
            variable=self.eval_regression_check_var,
            style='Config.TCheckbutton'
        ).grid(row=5, column=0, sticky=tk.W, padx=5, pady=2)

        # Quick regression toggle (sampled subset for faster checks)
        self.eval_quick_regression_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            controls_frame,
            text="Quick Regression (sample ~20%)",
            variable=self.eval_quick_regression_var,
            style='Config.TCheckbutton'
        ).grid(row=6, column=0, sticky=tk.W, padx=5, pady=2)

        # Run button (row 4)
        self.run_eval_button = ttk.Button(
            controls_frame,
            text="▶️ Run Evaluation",
            command=self.run_evaluation,
            style='Action.TButton'
        )
        self.run_eval_button.grid(row=4, column=2, rowspan=3, sticky=tk.E, padx=10, pady=5)

        # Quick access: open Debug tab (manual only)
        ttk.Button(
            controls_frame,
            text="🐞 Debug",
            command=self._focus_settings_debug_tab,
            style='Select.TButton'
        ).grid(row=4, column=3, rowspan=3, sticky=tk.E, padx=(0,5), pady=5)

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
        # If schema-aware and selected model is trainable, ensure an inference (GGUF) model exists
        try:
            sel_type = (self.current_model_info or {}).get('type')
            if tool_schema_name and sel_type in ('pytorch', 'trained'):
                if not (self.ollama_models or []):
                    messagebox.showinfo(
                        "Export Required",
                        "No inference (GGUF) models are installed.\n"
                        "Export your base/level to GGUF first (Models → Levels: Export to GGUF), then run baseline."
                    )
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
        # Simple quant picker then spawn export thread
        win = tk.Toplevel(self.root); win.title('Export Base to GGUF')
        f = ttk.Frame(win); f.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        ttk.Label(f, text=f"Export base '{base_model_name}' to GGUF", style='Config.TLabel').grid(row=0, column=0, sticky=tk.W)
        ttk.Label(f, text="Quantization:", style='Config.TLabel').grid(row=1, column=0, sticky=tk.W, pady=(6,2))
        qvar = tk.StringVar(value='q4_k_m')
        combo = ttk.Combobox(f, textvariable=qvar, values=['q4_k_m','q5_k_m','q8_0'], state='readonly', width=12)
        combo.grid(row=1, column=1, sticky=tk.W)
        def go():
            win.destroy()
            self._run_export_base_to_gguf(base_model_path, qvar.get())
        ttk.Button(f, text='Start Export', command=go, style='Action.TButton').grid(row=2, column=1, sticky=tk.E, pady=(8,0))

    def _run_export_base_to_gguf(self, base_model_path, quant: str):
        # Spawn export_base_to_gguf.py in a thread
        self.append_runner_output(f"\n--- Exporting Base to GGUF ({quant}) ---\n")
        def worker():
            try:
                import subprocess, sys
                script = Path(__file__).parent.parent.parent / 'export_base_to_gguf.py'
                outdir = Path(__file__).parent.parent.parent / 'exports' / 'gguf'
                cmd = [sys.executable, str(script), '--base', str(base_model_path), '--output', str(outdir), '--quant', quant]
                proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
                while True:
                    line = proc.stdout.readline()
                    if line == '' and proc.poll() is not None:
                        break
                    if line:
                        self.root.after(0, self.append_runner_output, line)
                rc = proc.poll()
                if rc == 0:
                    # Attempt to create an Ollama model referencing the GGUF
                    try:
                        base_name = Path(str(base_model_path)).name
                        gguf_path = outdir / f"{base_name}.{quant}.gguf"
                        modelfile = outdir / f"{base_name}.Modelfile"
                        mf = f"FROM {gguf_path}\nTEMPLATE \"{{{{ .Prompt }}}}\"\n"
                        modelfile.write_text(mf)
                        model_tag = f"{base_name}:latest"
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
                                messagebox.showinfo('Export', f'Base GGUF export complete and Ollama model created: {model_tag}. Starting baseline evaluation...')
                                # Refresh Ollama list so it appears
                                self.ollama_models = get_ollama_models()
                                self.populate_model_list()
                                self.append_runner_output("\n--- Export complete. Starting baseline evaluation with created model ---\n")
                                self._resume_eval_with_override(model_tag)
                            self.root.after(0, _done)
                        else:
                            self.root.after(0, lambda: messagebox.showwarning('Ollama', 'GGUF export complete, but failed to create Ollama model. You can create it manually.'))
                    except Exception as e:
                        self.root.after(0, lambda: messagebox.showwarning('Ollama', f'GGUF export complete, but Ollama create failed: {e}'))
                else:
                    # Offer to pull a prebuilt base from Ollama registry as fallback (GPU-less env)
                    try:
                        base_name = Path(str(base_model_path)).name
                        tag = self._guess_ollama_tag_from_base_name(base_name)
                        if tag and messagebox.askyesno('Export Failed', f'Base GGUF export failed (likely no GPU).\n\nPull prebuilt base from Ollama registry and use that instead?\n\nModel: {tag}'):
                            self.root.after(0, self.append_runner_output, f"\n--- Pulling Ollama model {tag} ---\n")
                            p2 = subprocess.Popen(['ollama','pull',tag], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
                            while True:
                                l3 = p2.stdout.readline()
                                if l3 == '' and p2.poll() is not None:
                                    break
                                if l3:
                                    self.root.after(0, self.append_runner_output, l3)
                            prc = p2.poll()
                            if prc == 0:
                                def _done2():
                                    self.ollama_models = get_ollama_models(); self.populate_model_list()
                                    self.append_runner_output("\n--- Pull complete. Starting baseline evaluation with pulled model ---\n")
                                    self._resume_eval_with_override(tag)
                                self.root.after(0, _done2)
                            else:
                                self.root.after(0, lambda: messagebox.showerror('Ollama', f'Pull failed with code {prc}'))
                        else:
                            self.root.after(0, lambda: messagebox.showerror('Export Failed', f'Export failed with code {rc}'))
                    except Exception:
                        self.root.after(0, lambda: messagebox.showerror('Export Failed', f'Export failed with code {rc}'))
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror('Export Error', str(e)))
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
                messagebox.showinfo('Evaluation', f'Installed {tag}. Select it under Ollama Models to evaluate.')
                return
            self._eval_override_model_name = tag
            self.append_runner_output("\n--- Continuing evaluation with inference model: %s ---\n" % tag)
            t = threading.Thread(target=self._run_evaluation_thread,
                                 args=(ctx['model'], ctx['suite'], ctx['prompt'], ctx['schema'], ctx['baseline']))
            t.daemon = True
            t.start()
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
            if not hasattr(self, 'eval_suite_reco_suppressed'):
                self.eval_suite_reco_suppressed = {}
            if self.eval_suite_reco_suppressed.get(suite):
                return
            prompt, schema_options, default_schema = self._recommend_prompt_schema_for_suite(suite)
            if not prompt and not schema_options:
                return
            self._show_suite_recommendation_dialog(suite, prompt, schema_options, default_schema)
        except Exception:
            pass

    def _recommend_prompt_schema_for_suite(self, suite: str):
        # Return (prompt_name or None, [schema options], default_schema)
        suite_lower = suite.lower()
        prompt = None
        options = []
        default_schema = None
        # Recommend based on simple mapping
        if 'orchestration' in suite_lower:
            prompt = 'Revised_tools'
            options = ['think_time']
            default_schema = 'think_time'
        elif 'tools' in suite_lower:
            prompt = 'Revised_tools'
            options = ['json_calls_full', 'file_ops_compat', 'search_ops']
            default_schema = 'json_calls_full'
        elif 'errors' in suite_lower:
            prompt = 'Revised_tools'
            options = ['json_calls_full', 'file_ops_compat']
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
            test_suite_dir = Path(__file__).parent.parent.parent / "Training_Data-Sets" / "Test"
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
            test_suite_dir = Path(__file__).parent.parent.parent / "Training_Data-Sets" / "Test"
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
            test_suite_dir = Path(__file__).parent.parent.parent / "Training_Data-Sets" / "Test"
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

    def populate_skills_display(self):
        """Populate the skills display with real-time evaluation data."""
        # Clear existing content
        for widget in self.skills_content_frame.winfo_children():
            widget.destroy()

        model_name = self.current_model_for_stats
        if not model_name:
            ttk.Label(
                self.skills_content_frame,
                text="Select a model to view skills.",
                style='Config.TLabel'
            ).pack(pady=20)
            return

        # Get real-time scores from the chat interface
        scores = self.get_realtime_scores_for_model(model_name)

        if not scores:
            ttk.Label(
                self.skills_content_frame,
                text="No real-time skill data available for this model. Use the model in Custom Code tab with Training Mode enabled to collect data.",
                style='Config.TLabel',
                wraplength=600
            ).pack(pady=20, padx=20)
            return

        # Header
        header_frame = ttk.Frame(self.skills_content_frame, style='Category.TFrame')
        header_frame.pack(fill=tk.X, padx=10, pady=10)
        ttk.Label(
            header_frame,
            text=f"🛠️ Real-Time Tool Skills: {model_name}",
            font=("Arial", 14, "bold"),
            style='CategoryPanel.TLabel'
        ).pack(anchor=tk.W)

        # Display each skill
        for skill, data in sorted(scores.items()):
            success = data.get('success', 0)
            failure = data.get('failure', 0)
            total = success + failure
            success_rate = (success / total * 100) if total > 0 else 0

            # Determine status and color
            if success_rate >= 80:
                status = "Verified"
                color = "#00ff00"
            elif success_rate > 0:
                status = "Partial"
                color = "#ffff00"
            else:
                status = "Failed"
                color = "#ff0000"

            # Skill frame
            skill_frame = ttk.LabelFrame(
                self.skills_content_frame,
                text=f"{skill} ({status})",
                style='TLabelframe'
            )
            skill_frame.pack(fill=tk.X, padx=10, pady=5)

            # Success rate
            ttk.Label(
                skill_frame,
                text=f"Success Rate: {success_rate:.2f}%",
                foreground=color,
                font=("Arial", 10, "bold")
            ).grid(row=0, column=0, sticky=tk.W, padx=10, pady=2)

            # Success/failure counts
            ttk.Label(
                skill_frame,
                text=f"Successes: {success}"
            ).grid(row=1, column=0, sticky=tk.W, padx=10, pady=2)

            ttk.Label(
                skill_frame,
                text=f"Failures: {failure}"
            ).grid(row=2, column=0, sticky=tk.W, padx=10, pady=2)

            # Error details if any
            if data.get("errors"):
                import tkinter.scrolledtext as scrolledtext
                errors_str = "\n".join(data["errors"][:5])  # Limit to first 5 errors
                if len(data["errors"]) > 5:
                    errors_str += f"\n... and {len(data['errors']) - 5} more errors"

                error_details = scrolledtext.ScrolledText(
                    skill_frame,
                    height=3,
                    width=60,
                    wrap=tk.WORD,
                    font=("Courier", 8)
                )
                error_details.insert(tk.END, errors_str)
                error_details.config(state=tk.DISABLED)
                error_details.grid(row=3, column=0, sticky=tk.W, padx=10, pady=5)

    def get_realtime_scores_for_model(self, model_name):
        """Get real-time evaluation scores for a model from the chat interface."""
        # The parent of ModelsTab is the main notebook, we need to get the CustomCodeTab instance
        if self.tab_instances and 'custom_code_tab' in self.tab_instances:
            custom_code_tab = self.tab_instances['custom_code_tab']['instance']
            if hasattr(custom_code_tab, 'get_chat_interface_scores'):
                all_scores = custom_code_tab.get_chat_interface_scores()
                return all_scores.get(model_name, {})
        return {}

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

    def populate_stats_display(self):
        """Populate the stats display for the current model with category filtering."""
        # Clear existing content
        for widget in self.stats_content_frame.winfo_children():
            widget.destroy()

        if not self.current_model_for_stats:
            ttk.Label(self.stats_content_frame, text="Select a model to view training statistics",
                     font=("Arial", 12), style='Config.TLabel').pack(pady=20)
            return

        # Load stats for current model
        stats = load_training_stats(self.current_model_for_stats)
        all_runs = stats.get("training_runs", [])

        # Extract unique categories and update dropdown
        categories = sorted(set(run.get("category", "Unknown") for run in all_runs))
        category_options = ["All Categories"] + categories
        self.stats_category_dropdown["values"] = category_options

        # Filter by selected category
        selected_category = self.stats_category_filter_var.get()
        if selected_category != "All Categories":
            filtered_runs = [run for run in all_runs if run.get("category") == selected_category]
        else:
            filtered_runs = all_runs

        # Update stats dict with filtered runs
        stats["training_runs"] = filtered_runs
        latest = filtered_runs[-1] if filtered_runs else None

        # Header
        header_frame = ttk.Frame(self.stats_content_frame, style='Category.TFrame')
        header_frame.pack(fill=tk.X, padx=10, pady=10)

        header_text = f"📊 Training Statistics: {self.current_model_for_stats}"
        if selected_category != "All Categories":
            header_text += f" (Category: {selected_category})"

        ttk.Label(header_frame, text=header_text,
                 font=("Arial", 14, "bold"), style='CategoryPanel.TLabel').pack(anchor=tk.W)

        if not filtered_runs:
            if selected_category == "All Categories":
                ttk.Label(self.stats_content_frame, text="No training runs recorded yet",
                         font=("Arial", 11), style='Config.TLabel').pack(pady=20)
                ttk.Label(self.stats_content_frame,
                         text="Stats will appear here after training completes",
                         font=("Arial", 9), style='Config.TLabel').pack()
            else:
                ttk.Label(self.stats_content_frame, text=f"No training runs for category: {selected_category}",
                         font=("Arial", 11), style='Config.TLabel').pack(pady=20)
                ttk.Label(self.stats_content_frame,
                         text="Try selecting 'All Categories' or a different category",
                         font=("Arial", 9), style='Config.TLabel').pack()
            return

        # Summary section
        summary_frame = ttk.LabelFrame(self.stats_content_frame, text="Summary", style='TLabelframe')
        summary_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Label(summary_frame, text=f"Total Training Runs:", font=("Arial", 10, "bold"),
                 style='Config.TLabel').grid(row=0, column=0, sticky=tk.W, padx=10, pady=3)
        ttk.Label(summary_frame, text=f"{len(stats['training_runs'])}", font=("Arial", 10),
                 style='Config.TLabel').grid(row=0, column=1, sticky=tk.W, padx=10, pady=3)

        if stats.get("last_updated"):
            ttk.Label(summary_frame, text=f"Last Training:", font=("Arial", 10, "bold"),
                     style='Config.TLabel').grid(row=1, column=0, sticky=tk.W, padx=10, pady=3)
            ttk.Label(summary_frame, text=f"{stats['last_updated'][:19]}", font=("Arial", 10),
                     style='Config.TLabel').grid(row=1, column=1, sticky=tk.W, padx=10, pady=3)

        # Latest run details
        if latest:
            latest_frame = ttk.LabelFrame(self.stats_content_frame, text="Latest Training Run", style='TLabelframe')
            latest_frame.pack(fill=tk.X, padx=10, pady=5)

            row = 0
            for key, value in latest.items():
                if key not in ["timestamp", "eval_report_path"]:  # Exclude eval_report_path from direct display
                    ttk.Label(latest_frame, text=f"{key.replace('_', ' ').title()}:",
                              font=("Arial", 10, "bold"), style='Config.TLabel').grid(
                                  row=row, column=0, sticky=tk.W, padx=10, pady=2)
                    ttk.Label(latest_frame, text=str(value), font=("Arial", 10),
                              style='Config.TLabel').grid(row=row, column=1, sticky=tk.W, padx=10, pady=2)
                    row += 1

            # --- Evaluation and Comparison Summary ---
            eval_report_path = latest.get("eval_report_path")
            if eval_report_path and Path(eval_report_path).exists():
                try:
                    with open(eval_report_path, 'r') as f:
                        eval_report = json.load(f)

                    # Load active baseline for comparison
                    base_model_name = latest.get("base_model")
                    if base_model_name:
                        test_suite_dir = TRAINING_DATA_DIR / "Test"
                        eval_engine = EvaluationEngine(tests_dir=test_suite_dir)
                        baseline_report = load_baseline_report(base_model_name)

                        if baseline_report:
                            comparison = eval_engine.compare_models(baseline_report, eval_report)

                            # Display comparison summary
                            compare_frame = ttk.LabelFrame(latest_frame, text="Evaluation vs. Baseline", style='TLabelframe')
                            compare_frame.grid(row=row, column=0, columnspan=2, sticky=tk.EW, padx=5, pady=5)
                            compare_row = 0

                            overall_delta = comparison.get('overall', {}).get('delta', '+0.00%')
                            ttk.Label(compare_frame, text=f"Overall Pass Rate Delta: {overall_delta}",
                                      font=("Arial", 10, "bold"), style='Config.TLabel').grid(row=compare_row, column=0, sticky=tk.W, padx=5, pady=2)
                            compare_row += 1

                            regressions = comparison.get('regressions', [])
                            if regressions:
                                reg_text = ", ".join([r.get('skill', '') for r in regressions])
                                ttk.Label(compare_frame, text=f"⚠️ Regressions: {reg_text}",
                                          font=("Arial", 10, "bold"), foreground='red', style='Config.TLabel').grid(row=compare_row, column=0, sticky=tk.W, padx=5, pady=2)
                                compare_row += 1
                                # Add button for suggestions
                                ttk.Button(compare_frame, text="💡 Get Suggestions", style='Action.TButton',
                                           command=lambda br=baseline_report, nr=eval_report: self._show_suggestions_dialog(br, nr)).grid(row=compare_row, column=0, sticky=tk.W, padx=5, pady=2)
                                compare_row += 1

                            improvements = comparison.get('improvements', [])
                            if improvements:
                                imp_text = ", ".join([i.get('skill', '') for i in improvements])
                                ttk.Label(compare_frame, text=f"✅ Improvements: {imp_text}",
                                          font=("Arial", 10, "bold"), foreground='green', style='Config.TLabel').grid(row=compare_row, column=0, sticky=tk.W, padx=5, pady=2)
                                compare_row += 1
                            row += 1  # Increment main row counter for latest_frame

                        else:
                            ttk.Label(latest_frame, text="No active baseline found for comparison.",
                                      font=("Arial", 9), style='Config.TLabel').grid(row=row, column=0, columnspan=2, sticky=tk.W, padx=10, pady=2)
                            row += 1
                    else:
                        ttk.Label(latest_frame, text="Base model name not available for baseline lookup.",
                                  font=("Arial", 9), style='Config.TLabel').grid(row=row, column=0, columnspan=2, sticky=tk.W, padx=10, pady=2)
                        row += 1

                    # Display overall evaluation results
                    ttk.Label(latest_frame, text=f"Evaluation Pass Rate: {eval_report.get('pass_rate_percent', 'N/A')}",
                              font=("Arial", 10, "bold"), style='Config.TLabel').grid(row=row, column=0, sticky=tk.W, padx=10, pady=2)
                    row += 1
                    ttk.Label(latest_frame, text=f"Prompt: {eval_report.get('metadata', {}).get('prompt_name', 'N/A')}",
                              font=("Arial", 9), style='Config.TLabel').grid(row=row, column=0, sticky=tk.W, padx=10, pady=2)
                    row += 1
                    ttk.Label(latest_frame, text=f"Schema: {eval_report.get('metadata', {}).get('schema_name', 'N/A')}",
                              font=("Arial", 9), style='Config.TLabel').grid(row=row, column=0, sticky=tk.W, padx=10, pady=2)
                    row += 1

                except Exception as e:
                    ttk.Label(latest_frame, text=f"Error loading evaluation report: {e}",
                              font=("Arial", 9), foreground='red', style='Config.TLabel').grid(row=row, column=0, columnspan=2, sticky=tk.W, padx=10, pady=2)
                    row += 1
            else:
                ttk.Label(latest_frame, text="No evaluation report linked to this training run.",
                          font=("Arial", 9), style='Config.TLabel').grid(row=row, column=0, columnspan=2, sticky=tk.W, padx=10, pady=2)
                row += 1

            if latest.get("eval_loss") is not None:
                ttk.Label(latest_frame, text="Eval Loss:",
                          font=("Arial", 10, "bold"), style='Config.TLabel').grid(
                              row=row, column=0, sticky=tk.W, padx=10, pady=2)
                ttk.Label(latest_frame, text=f"{latest.get('eval_loss', 0.0):.4f}", font=("Arial", 10),
                          style='Config.TLabel').grid(row=row, column=1, sticky=tk.W, padx=10, pady=2)
                row += 1

            # Baseline Skills Results
            baseline_skills = latest.get("baseline_skills_results")
            if baseline_skills:
                skills_frame = ttk.LabelFrame(self.stats_content_frame, text="Baseline Skill Test Results", style='TLabelframe')
                skills_frame.pack(fill=tk.X, padx=10, pady=5)

                skill_row = 0
                for skill_name, skill_data in baseline_skills.items():
                    status_icon = "✅" if skill_data.get("passed") else "❌"
                    ttk.Label(skills_frame, text=f"{status_icon} {skill_name}:",
                              font=("Arial", 10, "bold"), style='Config.TLabel').grid(
                                  row=skill_row, column=0, sticky=tk.W, padx=10, pady=2)
                    ttk.Label(skills_frame, text=str(skill_data.get("passed")),
                              font=("Arial", 10), style='Config.TLabel').grid(
                                  row=skill_row, column=1, sticky=tk.W, padx=10, pady=2)
                    skill_row += 1

        # Training history
        if len(stats["training_runs"]) > 1:
            history_frame = ttk.LabelFrame(self.stats_content_frame, text="Training History", style='TLabelframe')
            history_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

            for idx, run in enumerate(reversed(stats["training_runs"]), 1):
                run_frame = ttk.Frame(history_frame, style='Category.TFrame')
                run_frame.pack(fill=tk.X, padx=5, pady=2)

                timestamp = run.get("timestamp", "Unknown")[:19]
                ttk.Label(run_frame, text=f"Run #{len(stats['training_runs']) - idx + 1} - {timestamp}",
                         font=("Arial", 9, "bold"), style='Config.TLabel').pack(anchor=tk.W)

                details = ", ".join([f"{k}: {v}" for k, v in run.items() if k != "timestamp"])
                ttk.Label(run_frame, text=details, font=("Arial", 8),
                         style='Config.TLabel').pack(anchor=tk.W, padx=10)

    def populate_skills_display(self):
        """Populate the skills display with runtime AND evaluation skills for comparison."""
        for widget in self.skills_content_frame.winfo_children():
            widget.destroy()

        model_name = self.current_model_for_stats
        if not model_name:
            ttk.Label(self.skills_content_frame, text="Select a model to view skills.", style='Config.TLabel').pack(pady=20)
            return

        # Get BOTH runtime skills (actual usage) AND evaluation skills (test results)
        try:
            from config import _get_runtime_skills, get_model_skills
            runtime_skills = _get_runtime_skills(model_name)
            eval_skills = get_model_skills(model_name)
        except Exception as e:
            log_message(f"MODELS_TAB ERROR: Failed to get skills: {e}")
            runtime_skills = {}
            eval_skills = {}

        # Merge runtime and evaluation skills
        all_skills = set(list(runtime_skills.keys()) + list(eval_skills.keys()))

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
            text=f"🛠️ Tool Skills: {model_name}",
            font=("Arial", 14, "bold"),
            style='CategoryPanel.TLabel'
        ).pack(anchor=tk.W, pady=(0, 5))

        ttk.Label(
            header_frame,
            text="Comparing Runtime (actual usage) vs Evaluation (test results)",
            font=("Arial", 9),
            style='Config.TLabel',
            foreground='#888888'
        ).pack(anchor=tk.W)

        # Categorize skills
        verified_runtime = []  # High runtime success
        unverified_eval = []  # Good eval but no/low runtime usage
        failed_runtime = []  # Poor runtime success
        no_data = []  # Skills with no meaningful data

        for skill in sorted(all_skills):
            runtime_data = runtime_skills.get(skill, {})
            eval_data = eval_skills.get(skill, {})

            runtime_rate = runtime_data.get('success_rate', 0)
            runtime_calls = runtime_data.get('total_calls', 0)
            eval_status = eval_data.get('status', 'Unknown')

            if runtime_calls >= 3:  # Has meaningful runtime data
                if runtime_rate >= 80:
                    verified_runtime.append((skill, runtime_data, eval_data))
                else:
                    failed_runtime.append((skill, runtime_data, eval_data))
            elif eval_status in ['Verified', 'Partial']:
                unverified_eval.append((skill, runtime_data, eval_data))
            else:
                no_data.append((skill, runtime_data, eval_data))

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

            for skill, runtime_data, eval_data in verified_runtime:
                self._create_skill_comparison_frame(skill, runtime_data, eval_data, "#00ff00", "✅")

        # Section 2: Claimed Skills (Yellow - Unverified)
        if unverified_eval:
            section_label = ttk.Label(
                self.skills_content_frame,
                text="⚠️ Claimed Skills (Evaluation Only - Not Verified in Runtime)",
                font=("Arial", 12, "bold"),
                foreground="#ffff00"
            )
            section_label.pack(anchor=tk.W, padx=10, pady=(10, 5))

            for skill, runtime_data, eval_data in unverified_eval:
                self._create_skill_comparison_frame(skill, runtime_data, eval_data, "#ffff00", "⚠️")

        # Section 3: Failed Runtime Skills (Red - Needs Training)
        if failed_runtime:
            section_label = ttk.Label(
                self.skills_content_frame,
                text="❌ Failed Skills (Runtime Success <80% - Needs Training)",
                font=("Arial", 12, "bold"),
                foreground="#ff6b6b"
            )
            section_label.pack(anchor=tk.W, padx=10, pady=(10, 5))

            for skill, runtime_data, eval_data in failed_runtime:
                self._create_skill_comparison_frame(skill, runtime_data, eval_data, "#ff6b6b", "❌")

    def _create_skill_comparison_frame(self, skill, runtime_data, eval_data, color, icon):
        """Create a frame showing both runtime and eval data for a skill"""
        skill_frame = ttk.LabelFrame(
            self.skills_content_frame,
            text=f"{icon} {skill}",
            style='TLabelframe'
        )
        skill_frame.pack(fill=tk.X, padx=10, pady=3)

        # Create two columns: Runtime (left) and Evaluation (right)
        left_frame = ttk.Frame(skill_frame, style='Category.TFrame')
        left_frame.grid(row=0, column=0, sticky=tk.W, padx=10, pady=5)

        right_frame = ttk.Frame(skill_frame, style='Category.TFrame')
        right_frame.grid(row=0, column=1, sticky=tk.W, padx=10, pady=5)

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

        # Right: Evaluation Data
        if eval_data and eval_data.get('status'):
            ttk.Label(
                right_frame,
                text="Evaluation:",
                font=("Arial", 9, "bold"),
                foreground="#61dafb"
            ).grid(row=0, column=0, sticky=tk.W, columnspan=2)

            eval_status = eval_data.get('status', 'Unknown')
            eval_color = "#00ff00" if eval_status == "Verified" else "#ffff00" if eval_status == "Partial" else "#888888"

            ttk.Label(
                right_frame,
                text=eval_status,
                foreground=eval_color,
                font=("Arial", 10)
            ).grid(row=1, column=0, sticky=tk.W)
        else:
            ttk.Label(
                right_frame,
                text="Evaluation: No data",
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
            error_label.grid(row=1, column=0, columnspan=2, sticky=tk.W, padx=10, pady=(0, 5))


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
            if hasattr(self, 'panel_types') and self.panel_types:
                self.panel_types.event_generate("<<ModelSelected>>", data=payload, when="tail")
            self.refresh_collections_panel() # Refresh collections after a type plan is applied
        except Exception:
            pass


        # --- Populate Overview Tab ---
        # Clear previous content
        for widget in self.overview_tab_frame.winfo_children():
            widget.destroy()

        # Load config.json if available
        model_config = {}
        config_file = Path(model_info["path"]) / "config.json"
        if config_file.exists():
            try:
                with open(config_file) as f:
                    model_config = json.load(f)
            except: pass

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
        try:
            from config import get_model_behavior_profile
            prof = get_model_behavior_profile(model_name) or {}
            beh = prof.get('behavior') or {}
            beh_frame = ttk.LabelFrame(self.overview_tab_frame, text="Behavior Indicators", style='TLabelframe')
            beh_frame.pack(fill=tk.X, padx=10, pady=6)
            def _badge(k: str) -> str:
                v = (beh.get(k) or '0.00%')
                return v
            ttk.Label(beh_frame, text=f"Compliance: {_badge('compliance')}", style='Config.TLabel').grid(row=0, column=0, sticky=tk.W, padx=10, pady=3)
            ttk.Label(beh_frame, text=f"Creativity: {_badge('creativity')}", style='Config.TLabel').grid(row=0, column=1, sticky=tk.W, padx=10, pady=3)
            ttk.Label(beh_frame, text=f"Coherence: {_badge('coherence')}", style='Config.TLabel').grid(row=0, column=2, sticky=tk.W, padx=10, pady=3)
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
        except Exception:
            pass

    def refresh_collections_panel(self):
        """Reload list from config.list_model_profiles() and show 'Base ▸ Variant (type)'."""
        try:
            from Data import config as C
            items = C.list_model_profiles() or []
            self._collections_cache = items
            self.collections_list.delete(0, tk.END)
            # group visually as "Base ▸ Variant   [type]"
            for it in items:
                label = f"{it.get('base_model','?')} ▸ {it.get('variant_id','?')}   [{it.get('assigned_type','')}]"
                self.collections_list.insert(tk.END, label)
        except Exception as e:
            print("[ModelsTab] refresh_collections_panel error:", e)

    def _on_collection_pick(self, _evt=None):
        """When a variant is picked, apply its training profile in Training tab."""
        try:
            sel = self.collections_list.curselection()
            if not sel: return
            idx = sel[0]
            it = (self._collections_cache or [])[idx]
            variant = it.get("variant_id")
            # Relay to TrainingTab
            tt = self.get_training_tab()
            if tt and hasattr(tt, "apply_plan"):
                self.root.after(50, lambda: tt.apply_plan(variant_id=variant))
                print(f"[ModelsTab] Applied collection variant to Training: {variant}")
        except Exception as e:
            print("[ModelsTab] _on_collection_pick error:", e)

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

            ttk.Label(adapter_frame, text=f"▶ {adapter_name}", font=("Arial", 10, "bold"), foreground="#51cf66").grid(row=0, column=col, sticky=tk.W, padx=5, pady=2)
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


    def _populate_history_tab(self, base_model_info):
        """Populate History → Runs and Levels for the selected base model without destroying the tab structure."""
        # Clear content areas only
        for frame in (self.history_runs_frame, self.history_levels_frame):
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
            with open(level_dir / 'manifest.json', 'w') as f:
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
                        with open(mf, 'r') as f:
                            data = json.load(f)
                        data['name'] = d.name
                        data['path'] = str(d)
                        levels.append(data)
                    except Exception:
                        continue
        except Exception:
            return []
        return levels

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
        # Clear previous overview content
        for widget in self.overview_tab_frame.winfo_children():
            widget.destroy()

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

        # Update Selected Model Label in Evaluation Tab
        if hasattr(self, 'selected_model_label_eval'):
            self.selected_model_label_eval.config(text=f"Selected Model: {model_name}")
        if hasattr(self, 'eval_source_label'):
            self.eval_source_label.config(text="Source: Ollama (GGUF)")

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
                    out = _sp.check_output([pth, '-c', 'import unsloth,sys;print(sys.executable)'], text=True, stderr=_sp.DEVNULL, timeout=3)
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
                        # Tag the Ollama model after adapter for uniqueness
                        model_tag = f"{adapter_name}:latest"
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

    def _copy_name_to_clipboard(self):
        """Copies the current model's name to the clipboard."""
        if not self.current_model_info:
            return
        try:
            model_name = self.current_model_info['name']
            self.root.clipboard_clear()
            self.root.clipboard_append(model_name)
            # Give subtle feedback without a disruptive messagebox
            print(f"Copied to clipboard: {model_name}")
        except Exception as e:
            print(f"Failed to copy model name to clipboard: {e}")

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

        except subprocess.CalledProcessError as e:
            error_msg = e.stderr if e.stderr else str(e)
            messagebox.showerror("Delete Failed", f"Failed to delete model:\n\n{error_msg}")
        except Exception as e:
            messagebox.showerror("Delete Failed", f"An error occurred:\n\n{str(e)}")
