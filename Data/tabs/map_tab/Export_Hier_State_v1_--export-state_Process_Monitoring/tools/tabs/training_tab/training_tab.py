# [SYSTEM: GUI | VERSION: 1.9f | STATUS: ACTIVE]
"""
Training Tab - Main coordinator for training-related functionality
Modular design with separated panel components
"""

import tkinter as tk
from tkinter import ttk, messagebox
import json
import subprocess
from pathlib import Path
from logger_util import get_tab_logger

log_message, log_error, log_exception = get_tab_logger('training')

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from tabs.base_tab import BaseTab
from functools import partial
from config import (
    get_category_info,
    get_training_data_files,
    DATA_DIR,
    get_ollama_models,
    get_all_available_models,
    get_all_trained_models,
    PROMPTS_DIR,
    SCHEMAS_DIR,
    TYPE_SCHEMAS_DIR,
    SEMANTIC_DATA_DIR,
    PROMPTBOX_DIR,
)
import config as cfg

# Import panel modules
from .runner_panel import RunnerPanel
from .category_manager_panel import CategoryManagerPanel
from .model_selection_panel import ModelSelectionPanel
from .profiles_panel import ProfilesPanel
from .summary_panel import SummaryPanel
from functools import partial


class TrainingTab(BaseTab):
    """Training configuration and dataset selection tab - Main coordinator"""

    def __init__(self, parent, root, style):
        super().__init__(parent, root, style)

        self._is_updating_selection = False
        # State variables
        self.category_vars = {}
        self.subcategory_vars = {}
        self.ollama_models = get_all_available_models()  # Now includes local PyTorch models
        # Build trainable models list (exclude Ollama and stats dir)
        self.trainable_models = [
            m['name'] for m in get_all_trained_models()
            if m.get('type') in ('pytorch', 'trained') and m.get('name') != 'training_stats'
        ]

        # Set default model - prefer local models if available
        default_model = "unsloth/Qwen2.5-Coder-1.5B-Instruct"
        if self.ollama_models:
            # Use first local model if available
            for model in self.ollama_models:
                if model.startswith("LOCAL: "):
                    default_model = model
                    break
            # Otherwise use first in list
            if not default_model.startswith("LOCAL: ") and default_model not in self.ollama_models:
                default_model = self.ollama_models[0]

        self.config_vars = {
            # "training_runs": tk.IntVar(value=3), # Moved to RunnerPanel
            # "batch_size": tk.IntVar(value=2), # Moved to RunnerPanel
            # "learning_strength": tk.StringVar(value="2e-4"), # Moved to RunnerPanel
            "base_model": tk.StringVar(value=default_model)
        }

        self.profile_name_var = tk.StringVar(value="")
        self.selected_profile_var = tk.StringVar(value="")
        # Prompt/Schema selections
        self.prompt_selected_var = tk.StringVar(value="")
        self.schema_selected_var = tk.StringVar(value="")
        # Type Schema selections
        self.type_schema_selected_var = tk.StringVar(value="")
        self.type_schema_vars = {}  # name -> BooleanVar (flat list by group)
        # Prompt/Schema multi-select state
        self.prompt_vars = {}  # name -> BooleanVar
        self.schema_vars = {}  # name -> BooleanVar
        self.category_info = get_category_info()

    def create_ui(self):
        """Create the training tab UI with side menu and sub-tabs"""
        self.parent.columnconfigure(0, weight=1)
        self.parent.columnconfigure(1, weight=0)
        self.parent.rowconfigure(0, weight=1)

        # Left side: Training content with sub-tabs
        training_content_frame = ttk.Frame(self.parent, style='Category.TFrame')
        training_content_frame.grid(row=0, column=0, sticky=tk.NSEW, padx=10, pady=10)
        training_content_frame.columnconfigure(0, weight=1)
        training_content_frame.rowconfigure(1, weight=1)

        # Header with title and refresh button
        header_frame = ttk.Frame(training_content_frame, style='Category.TFrame')
        header_frame.grid(row=0, column=0, sticky=tk.EW, pady=5)
        header_frame.columnconfigure(0, weight=1)

        ttk.Label(header_frame, text="⚙️ Training",
                 font=("Arial", 14, "bold"), style='CategoryPanel.TLabel').pack(side=tk.LEFT, padx=(0, 10))

        ttk.Button(header_frame, text="🔄 Refresh",
                  command=self.refresh_training_tab,
                  style='Select.TButton').pack(side=tk.RIGHT, padx=5)

        # Sub-tabs notebook
        self.training_notebook = ttk.Notebook(training_content_frame)
        self.training_notebook.grid(row=1, column=0, sticky=tk.NSEW, padx=5, pady=5)

        # Bind tab change event to update model display
        self.training_notebook.bind("<<NotebookTabChanged>>", self.on_tab_changed)

        # Training Runner Tab
        runner_frame = ttk.Frame(self.training_notebook)
        self.training_notebook.add(runner_frame, text="Runner")
        self.runner_panel = RunnerPanel(runner_frame, self.style, self)
        self.runner_panel.create_ui()

        # Category Manager Tab
        category_manager_frame = ttk.Frame(self.training_notebook)
        self.training_notebook.add(category_manager_frame, text="Script Manager")
        self.category_manager_panel = CategoryManagerPanel(
            category_manager_frame,
            self.style,
            refresh_callback=self.refresh_all_panels,
            training_tab_instance=self
        )
        self.category_manager_panel.create_ui()

        # Model Selection Tab (formerly Configuration)
        model_selection_frame = ttk.Frame(self.training_notebook)
        self.training_notebook.add(model_selection_frame, text="Model Selection")
        self.model_selection_panel = ModelSelectionPanel(
            model_selection_frame,
            self.style,
            # Only trainable models in this dropdown
            self.trainable_models,
            self.update_preview,
            training_tab_instance=self
        )
        self.model_selection_panel.create_ui()

        # Profiles Tab
        profiles_frame = ttk.Frame(self.training_notebook)
        self.training_notebook.add(profiles_frame, text="Profiles")
        profile_vars = {
            'profile_name': self.profile_name_var,
            'selected_profile': self.selected_profile_var
        }
        self.profiles_panel = ProfilesPanel(
            profiles_frame,
            self.style,
            profile_vars,
            self.category_vars,
            self.subcategory_vars,
            model_selection_panel=self.model_selection_panel,
            runner_panel=self.runner_panel,
            update_preview_callback=self.update_preview,
            update_combobox_callback=self.update_profile_combobox,
            training_tab_instance=self # Pass the TrainingTab instance
        )
        self.profiles_panel.create_ui()

        # Summary Tab
        summary_frame = ttk.Frame(self.training_notebook)
        self.training_notebook.add(summary_frame, text="Summary")
        self.summary_panel = SummaryPanel(
            summary_frame,
            self.style,
            self.category_vars,
            self.subcategory_vars,
            self.model_selection_panel,
            self.runner_panel, # Pass the runner_panel
            self.selected_profile_var
        )
        self.summary_panel.create_ui()

        # Right side: Training menu
        self.create_training_menu(self.parent)

        # Update profile list
        self.update_profile_combobox()

        # Initialize runner panel's model display now that model_selection_panel exists
        if hasattr(self, 'runner_panel'):
            self.runner_panel.update_training_model_display()

    def create_training_menu(self, parent):
        """Create category/script selector menu on the right"""
        menu_frame = ttk.Frame(parent, style='Category.TFrame')
        menu_frame.grid(row=0, column=1, sticky=tk.NSEW, padx=10, pady=10)
        menu_frame.columnconfigure(0, weight=1)
        # Do not expand Training Scripts content to avoid pushing Prompts/Schemas down
        try:
            menu_frame.rowconfigure(1, weight=0)
        except Exception:
            pass

        # Collapsible section: Training Scripts (default collapsed)
        self.ts_expanded = tk.BooleanVar(value=False)
        ts_header = ttk.Frame(menu_frame, style='Category.TFrame')
        ts_header.grid(row=0, column=0, pady=5, sticky=tk.EW, padx=5)
        ts_header.columnconfigure(1, weight=1)
        self.ts_toggle_btn = ttk.Button(ts_header, text="▶", width=2, style='Select.TButton', command=self._toggle_ts_section)
        self.ts_toggle_btn.pack(side=tk.LEFT, padx=(0,5))
        ttk.Label(ts_header, text="📋 Training Scripts", font=("Arial", 11, "bold"), style='CategoryPanel.TLabel').pack(side=tk.LEFT)
        self.selection_counter_label = ttk.Label(ts_header, text="", style='CategoryPanel.TLabel')
        self.selection_counter_label.pack(side=tk.LEFT, padx=5)

        # Select/Deselect All buttons (inside Training Scripts section)
        self.ts_content = ttk.Frame(menu_frame, style='Category.TFrame')
        # Place Training Scripts content directly under its header (row 1)
        self.ts_content.grid(row=1, column=0, sticky=tk.NSEW)
        # Default collapsed on launch
        try:
            if not self.ts_expanded.get():
                self.ts_content.grid_remove()
                self.ts_toggle_btn.config(text="▶")
        except Exception:
            pass
        self.ts_content.columnconfigure(0, weight=1)

        buttons_frame = ttk.Frame(self.ts_content)
        buttons_frame.grid(row=0, column=0, pady=5, padx=5, sticky=tk.EW)
        buttons_frame.columnconfigure(1, weight=1) # Give deselect button space

        self.select_all_var = tk.BooleanVar()
        select_all_cb = ttk.Checkbutton(
            buttons_frame,
            text="Select All",
            variable=self.select_all_var,
            command=self.toggle_select_all,
            style='Category.TCheckbutton'
        )
        select_all_cb.grid(row=0, column=0, pady=2, padx=2, sticky=tk.W)

        ttk.Button(
            buttons_frame,
            text="Deselect All",
            command=self.deselect_all_scripts,
            style='Select.TButton'
        ).grid(row=0, column=1, pady=2, padx=2, sticky=tk.EW)


        # Scrollable category tree inside Training Scripts section
        tree_canvas = tk.Canvas(self.ts_content, bg="#2b2b2b", highlightthickness=0, height=250)
        tree_scrollbar = ttk.Scrollbar(self.ts_content, orient="vertical", command=tree_canvas.yview)
        self.category_tree_frame = ttk.Frame(tree_canvas)

        self.category_tree_frame.bind(
            "<Configure>",
            lambda e: tree_canvas.configure(scrollregion=tree_canvas.bbox("all"))
        )

        tree_canvas_window = tree_canvas.create_window((0, 0), window=self.category_tree_frame, anchor="nw")
        tree_canvas.configure(yscrollcommand=tree_scrollbar.set)

        tree_canvas.grid(row=1, column=0, sticky=tk.EW, pady=5)
        tree_scrollbar.grid(row=1, column=1, sticky=tk.NS)

        tree_canvas.bind("<Configure>", lambda e: tree_canvas.itemconfig(tree_canvas_window, width=e.width))
        # Independent mousewheel binding for Training Scripts list
        tree_canvas.bind('<Enter>', lambda e: self._bind_wheel_to_canvas(tree_canvas))
        tree_canvas.bind('<Leave>', lambda e: self._unbind_wheel_from_canvas())

        # Store script and JSONL variables
        self.script_vars = {}  # {category: {script_name: BooleanVar}}
        self.jsonl_vars = {}   # {category: {jsonl_name: BooleanVar}}
        self.category_expanded = {}  # {category: BooleanVar}
        self.script_expanded = {}    # {category: {script: BooleanVar}}

        # Populate category tree
        self.populate_category_tree()
        # Append Prompts, Schemas, and Type Schemas sections (collapsible, as sibling sections)
        self._populate_prompts_and_schemas(menu_frame)
        self._populate_type_schemas(menu_frame)

        # Bind global runtime training events
        try:
            self.root.bind("<<RuntimeTrainingDataReady>>", self._on_runtime_training_data_ready)
            self.root.bind("<<StartVariantTraining>>", self._on_start_variant_training)
            self.root.bind("<<FocusTrainingTab>>", self._on_focus_training_tab)
            # Phase 6: Training progression event
            self.root.bind("<<SelectVariantForTraining>>", self._on_select_variant_request)
        except Exception:
            pass

    def _toggle_ts_section(self):
        try:
            if self.ts_expanded.get():
                self.ts_content.grid_remove()
                self.ts_toggle_btn.config(text="▶")
                self.ts_expanded.set(False)
            else:
                self.ts_content.grid()
                self.ts_toggle_btn.config(text="▼")
                self.ts_expanded.set(True)
        except Exception:
            pass

    def _populate_prompts_and_schemas(self, parent):
        from config import list_system_prompts, list_tool_schemas
        # Prompts section (collapsible) as sibling of Training Scripts
        # Default collapsed on launch
        self.prompts_expanded = tk.BooleanVar(value=False)
        prompts_header = ttk.Frame(parent, style='Category.TFrame')
        # Prompts header in row 2
        prompts_header.grid(row=2, column=0, sticky=tk.EW, padx=5, pady=(5,0))
        self.prompts_toggle_btn = ttk.Button(prompts_header, text="▶", width=2, style='Select.TButton', command=self._toggle_prompts_section)
        self.prompts_toggle_btn.pack(side=tk.LEFT, padx=(0,5))
        ttk.Label(prompts_header, text="🧠 Prompts", font=("Arial", 10, "bold"), foreground='#61dafb').pack(side=tk.LEFT)
        self.prompts_selected_count_label = ttk.Label(prompts_header, text="Selected: 0", style='Config.TLabel')
        self.prompts_selected_count_label.pack(side=tk.RIGHT)
        self.prompts_content = ttk.Frame(parent, style='Category.TFrame')
        # Prompts content in row 3
        self.prompts_content.grid(row=3, column=0, sticky=tk.EW)
        # Default collapsed on launch
        try:
            if not self.prompts_expanded.get():
                self.prompts_content.grid_remove()
                self.prompts_toggle_btn.config(text="▶")
        except Exception:
            pass

        # Prompts header row (within content)
        prompts_hdr = ttk.Frame(self.prompts_content)
        prompts_hdr.grid(row=0, column=0, sticky=tk.EW, padx=10, pady=(2, 4))
        prompts_hdr.columnconfigure(0, weight=1)
        ttk.Label(prompts_hdr, text="🧠 Prompts", font=("Arial", 10, "bold"), foreground='#61dafb').grid(row=0, column=0, sticky=tk.W)

        # Prompts scrollable list
        prom_canvas = tk.Canvas(self.prompts_content, bg="#2b2b2b", highlightthickness=0, height=150)
        prom_scroll = ttk.Scrollbar(self.prompts_content, orient='vertical', command=prom_canvas.yview)
        self.prompts_list_frame = ttk.Frame(prom_canvas)
        self.prompts_list_frame.bind("<Configure>", lambda e: prom_canvas.configure(scrollregion=prom_canvas.bbox("all")))
        prom_window = prom_canvas.create_window((0,0), window=self.prompts_list_frame, anchor='nw')
        prom_canvas.configure(yscrollcommand=prom_scroll.set)
        prom_canvas.grid(row=1, column=0, sticky=tk.EW, padx=10)
        prom_scroll.grid(row=1, column=1, sticky=tk.NS)
        self.prompts_list_frame.bind("<Configure>", lambda e: prom_canvas.itemconfig(prom_window, width=prom_canvas.winfo_width()))
        # Independent mousewheel binding
        prom_canvas.bind('<Enter>', lambda e: self._bind_wheel_to_canvas(prom_canvas))
        prom_canvas.bind('<Leave>', lambda e: self._unbind_wheel_from_canvas())
        self._refresh_prompts_list()

        # Schemas section (collapsible) as sibling
        # Default collapsed on launch
        self.schemas_expanded = tk.BooleanVar(value=False)
        schemas_header = ttk.Frame(parent, style='Category.TFrame')
        # Schemas header in row 4
        schemas_header.grid(row=4, column=0, sticky=tk.EW, padx=5, pady=(5,0))
        self.schemas_toggle_btn = ttk.Button(schemas_header, text="▶", width=2, style='Select.TButton', command=self._toggle_schemas_section)
        self.schemas_toggle_btn.pack(side=tk.LEFT, padx=(0,5))
        ttk.Label(schemas_header, text="🧩 Schemas", font=("Arial", 10, "bold"), foreground='#ffd43b').pack(side=tk.LEFT)
        self.schemas_selected_count_label = ttk.Label(schemas_header, text="Selected: 0", style='Config.TLabel')
        self.schemas_selected_count_label.pack(side=tk.RIGHT)
        self.schemas_content = ttk.Frame(parent, style='Category.TFrame')
        # Schemas content in row 5
        self.schemas_content.grid(row=5, column=0, sticky=tk.EW)
        # Default collapsed on launch
        try:
            if not self.schemas_expanded.get():
                self.schemas_content.grid_remove()
                self.schemas_toggle_btn.config(text="▶")
        except Exception:
            pass

        schemas_hdr = ttk.Frame(self.schemas_content)
        schemas_hdr.grid(row=0, column=0, sticky=tk.EW, padx=10, pady=(2,4))
        schemas_hdr.columnconfigure(0, weight=1)
        ttk.Label(schemas_hdr, text="🧩 Schemas", font=("Arial", 10, "bold"), foreground='#ffd43b').grid(row=0, column=0, sticky=tk.W)

        sch_canvas = tk.Canvas(self.schemas_content, bg="#2b2b2b", highlightthickness=0, height=150)
        sch_scroll = ttk.Scrollbar(self.schemas_content, orient='vertical', command=sch_canvas.yview)
        self.schemas_list_frame = ttk.Frame(sch_canvas)
        self.schemas_list_frame.bind("<Configure>", lambda e: sch_canvas.configure(scrollregion=sch_canvas.bbox("all")))
        sch_window = sch_canvas.create_window((0,0), window=self.schemas_list_frame, anchor='nw')
        sch_canvas.configure(yscrollcommand=sch_scroll.set)
        sch_canvas.grid(row=1, column=0, sticky=tk.EW, padx=10)
        sch_scroll.grid(row=1, column=1, sticky=tk.NS)
        self.schemas_list_frame.bind("<Configure>", lambda e: sch_canvas.itemconfig(sch_window, width=sch_canvas.winfo_width()))
        sch_canvas.bind('<Enter>', lambda e: self._bind_wheel_to_canvas(sch_canvas))
        sch_canvas.bind('<Leave>', lambda e: self._unbind_wheel_from_canvas())
        self._refresh_schemas_list()

    def _refresh_prompts_list(self):
        # Clear
        for w in self.prompts_list_frame.winfo_children():
            w.destroy()

        # Build grouped prompts: PromptBox, Semantic_States, and Prompts/<category>
        groups = {}
        # PromptBox (.txt)
        if PROMPTBOX_DIR.exists():
            names = sorted([p.stem for p in PROMPTBOX_DIR.glob('*.txt')])
            if names:
                groups['PromptBox'] = names
        # Semantic_States (system_prompt_*.json)
        if SEMANTIC_DATA_DIR.exists():
            ss_names = []
            for p in SEMANTIC_DATA_DIR.glob('system_prompt_*.json'):
                ss_names.append(p.stem.replace('system_prompt_', '', 1))
            if ss_names:
                groups['Semantic_States'] = sorted(ss_names)
        # Prompts categories (any .json under Prompts/)
        if PROMPTS_DIR.exists():
            cat_map = {}
            for p in PROMPTS_DIR.rglob('*.json'):
                rel = p.parent.relative_to(PROMPTS_DIR)
                cat = str(rel) if str(rel) != '.' else 'Prompts'
                cat_map.setdefault(cat, []).append(p.stem)
            for cat, lst in sorted(cat_map.items()):
                groups[f"Prompts/{cat}"] = sorted(lst)

        if not groups:
            ttk.Label(self.prompts_list_frame, text="No prompts found.", style='Config.TLabel').grid(row=0, column=0, sticky=tk.W, padx=5)
            return

        # Normalize selection state to existing names only (flat across groups)
        valid_names = {name for lst in groups.values() for name in lst}
        self.prompt_vars = {k: v for k, v in self.prompt_vars.items() if k in valid_names}

        # Build UI groups
        self._prompt_group_frames = {}
        row_idx = 0
        for group, names in groups.items():
            grp_frame = ttk.Frame(self.prompts_list_frame)
            grp_frame.grid(row=row_idx, column=0, sticky=tk.EW, pady=(4,1))
            row_idx += 1
            header = ttk.Frame(grp_frame)
            header.pack(fill=tk.X)
            btn = ttk.Button(header, text="▶", width=2, style='Select.TButton', command=lambda g=group: self._toggle_prompt_group(g))
            btn.pack(side=tk.LEFT, padx=(0,5))
            ttk.Label(header, text=group, font=("Arial", 10, "bold"), style='CategoryPanel.TLabel').pack(side=tk.LEFT)
            container = ttk.Frame(grp_frame)
            # Default collapsed on launch (do not pack)
            # Rows
            for name in names:
                row = ttk.Frame(container)
                row.pack(fill=tk.X, pady=1)
                var = self.prompt_vars.get(name)
                if var is None:
                    var = tk.BooleanVar(value=False)
                    self.prompt_vars[name] = var
                ttk.Checkbutton(row, text="", variable=var, style='Category.TCheckbutton', width=2,
                                command=lambda n=name, v=var: self._on_prompt_checkbox_toggle(n, v.get())).pack(side=tk.LEFT, padx=(0,4))
                ttk.Button(row, text=name, command=lambda n=name: self._on_prompt_click(n), style='Select.TButton').pack(side=tk.LEFT)
            self._prompt_group_frames[group] = { 'container': container, 'expand_button': btn }
        self._update_prompts_selected_count()

    def _refresh_schemas_list(self):
        # Clear
        for w in self.schemas_list_frame.winfo_children():
            w.destroy()

        # Build grouped schemas: Semantic_States and Schemas/<category>
        groups = {}
        # Semantic_States (tool_schema_*.json)
        if SEMANTIC_DATA_DIR.exists():
            ss_names = []
            for p in SEMANTIC_DATA_DIR.glob('tool_schema_*.json'):
                ss_names.append(p.stem.replace('tool_schema_', '', 1))
            if ss_names:
                groups['Semantic_States'] = sorted(ss_names)
        # Schemas categories (any .json under Schemas/)
        if SCHEMAS_DIR.exists():
            cat_map = {}
            for p in SCHEMAS_DIR.rglob('*.json'):
                rel = p.parent.relative_to(SCHEMAS_DIR)
                cat = str(rel) if str(rel) != '.' else 'Schemas'
                cat_map.setdefault(cat, []).append(p.stem)
            for cat, lst in sorted(cat_map.items()):
                groups[f"Schemas/{cat}"] = sorted(lst)

        if not groups:
            ttk.Label(self.schemas_list_frame, text="No schemas found.", style='Config.TLabel').grid(row=0, column=0, sticky=tk.W, padx=5)
            return

        # Normalize selection state
        valid_names = {name for lst in groups.values() for name in lst}
        self.schema_vars = {k: v for k, v in self.schema_vars.items() if k in valid_names}

        # Build UI groups
        self._schema_group_frames = {}
        row_idx = 0
        for group, names in groups.items():
            grp_frame = ttk.Frame(self.schemas_list_frame)
            grp_frame.grid(row=row_idx, column=0, sticky=tk.EW, pady=(4,1))
            row_idx += 1
            header = ttk.Frame(grp_frame)
            header.pack(fill=tk.X)
            btn = ttk.Button(header, text="▶", width=2, style='Select.TButton', command=lambda g=group: self._toggle_schema_group(g))
            btn.pack(side=tk.LEFT, padx=(0,5))
            ttk.Label(header, text=group, font=("Arial", 10, "bold"), style='CategoryPanel.TLabel').pack(side=tk.LEFT)
            container = ttk.Frame(grp_frame)
            # Default collapsed on launch (do not pack)
            # Rows
            for name in names:
                row = ttk.Frame(container)
                row.pack(fill=tk.X, pady=1)
                var = self.schema_vars.get(name)
                if var is None:
                    var = tk.BooleanVar(value=False)
                    self.schema_vars[name] = var
                ttk.Checkbutton(row, text="", variable=var, style='Category.TCheckbutton', width=2,
                                command=lambda n=name, v=var: self._on_schema_checkbox_toggle(n, v.get())).pack(side=tk.LEFT, padx=(0,4))
                ttk.Button(row, text=name, command=lambda n=name: self._on_schema_click(n), style='Select.TButton').pack(side=tk.LEFT)
            self._schema_group_frames[group] = { 'container': container, 'expand_button': btn }
        
        self._update_schemas_selected_count()

    def _populate_type_schemas(self, parent):
        """Add a collapsible section for Type Schemas in the right menu."""
        import config as C
        # Default collapsed on launch
        self.type_schemas_expanded = tk.BooleanVar(value=False)
        header = ttk.Frame(parent, style='Category.TFrame')
        header.grid(row=6, column=0, sticky=tk.EW, padx=5, pady=(5,0))
        self.type_schemas_toggle_btn = ttk.Button(header, text="▶", width=2, style='Select.TButton', command=self._toggle_type_schemas_section)
        self.type_schemas_toggle_btn.pack(side=tk.LEFT, padx=(0,5))
        ttk.Label(header, text="🧩 Type Schemas", font=("Arial", 10, "bold"), foreground='#61dafb').pack(side=tk.LEFT)
        self.type_schemas_selected_count_label = ttk.Label(header, text="Selected: 0", style='Config.TLabel')
        self.type_schemas_selected_count_label.pack(side=tk.RIGHT)

        self.type_schemas_content = ttk.Frame(parent, style='Category.TFrame')
        self.type_schemas_content.grid(row=7, column=0, sticky=tk.EW)
        try:
            if not self.type_schemas_expanded.get():
                self.type_schemas_content.grid_remove()
                self.type_schemas_toggle_btn.config(text="▶")
        except Exception:
            pass

        # Build grouped list by category (type id)
        self._type_schema_group_frames = {}
        groups = C.list_type_schemas()  # {category: [names]}
        for group, names in groups.items():
            grp_frame = ttk.Frame(self.type_schemas_content)
            grp_frame.pack(fill=tk.X, padx=8, pady=(4,2))
            header = ttk.Frame(grp_frame)
            header.pack(fill=tk.X)
            btn = ttk.Button(header, text="▶", width=2, style='Select.TButton', command=lambda g=group: self._toggle_type_schema_group(g))
            btn.pack(side=tk.LEFT, padx=(0,5))
            ttk.Label(header, text=group, font=("Arial", 10, "bold"), style='CategoryPanel.TLabel').pack(side=tk.LEFT)
            container = ttk.Frame(grp_frame)
            # Rows
            for name in names:
                row = ttk.Frame(container)
                row.pack(fill=tk.X, pady=1)
                var = self.type_schema_vars.get(name)
                if var is None:
                    var = tk.BooleanVar(value=False)
                    self.type_schema_vars[name] = var
                ttk.Checkbutton(row, text="", variable=var, style='Category.TCheckbutton', width=2,
                                command=lambda n=name, v=var: self._on_type_schema_checkbox_toggle(n, v.get())).pack(side=tk.LEFT, padx=(0,4))
                ttk.Button(row, text=name, command=lambda n=name, g=group: self._on_type_schema_click(n, g), style='Select.TButton').pack(side=tk.LEFT)
            self._type_schema_group_frames[group] = { 'container': container, 'expand_button': btn }

        self._update_type_schemas_selected_count()

    def _toggle_type_schemas_section(self):
        try:
            if self.type_schemas_expanded.get():
                self.type_schemas_content.grid_remove()
                self.type_schemas_toggle_btn.config(text="▶")
                self.type_schemas_expanded.set(False)
            else:
                self.type_schemas_content.grid()
                self.type_schemas_toggle_btn.config(text="▼")
                self.type_schemas_expanded.set(True)
        except Exception:
            pass

    def _toggle_type_schema_group(self, group: str):
        grp = getattr(self, '_type_schema_group_frames', {}).get(group)
        if not grp:
            return
        cont = grp['container']
        btn = grp['expand_button']
        try:
            if cont.winfo_ismapped():
                cont.pack_forget()
                btn.config(text='▶')
            else:
                cont.pack(fill=tk.X, padx=10)
                btn.config(text='▼')
        except Exception:
            pass

    def _on_type_schema_checkbox_toggle(self, name: str, state: bool):
        # Single-select semantics: only one type schema active at a time
        if state:
            for k, var in self.type_schema_vars.items():
                if k != name and var.get():
                    var.set(False)
            self.type_schema_selected_var.set(name)
        else:
            if self.type_schema_selected_var.get() == name:
                self.type_schema_selected_var.set("")
        self._update_type_schemas_selected_count()

    def _on_type_schema_click(self, name: str, group: str):
        # Toggle selection and open in manager if available
        var = self.type_schema_vars.get(name)
        if var:
            var.set(not var.get())
        self._on_type_schema_checkbox_toggle(name, self.type_schema_vars.get(name, tk.BooleanVar(value=False)).get())
        self._open_type_schema_in_manager(name)

    def _open_type_schema_in_manager(self, name: str):
        try:
            panel = getattr(self, 'category_manager_panel', None)
            if not panel:
                return
            if hasattr(panel, 'open_type_schema_by_name'):
                panel.open_type_schema_by_name(name)
        except Exception:
            pass

    def _update_type_schemas_selected_count(self):
        cnt = sum(1 for v in self.type_schema_vars.values() if v.get())
        try:
            self.type_schemas_selected_count_label.config(text=f"Selected: {cnt}")
        except Exception:
            pass

    def _toggle_prompts_section(self):
        try:
            if self.prompts_expanded.get():
                self.prompts_content.grid_remove()
                self.prompts_toggle_btn.config(text="▶")
                self.prompts_expanded.set(False)
            else:
                self.prompts_content.grid()
                self.prompts_toggle_btn.config(text="▼")
                self.prompts_expanded.set(True)
        except Exception:
            pass

    def _toggle_schemas_section(self):
        try:
            if self.schemas_expanded.get():
                self.schemas_content.grid_remove()
                self.schemas_toggle_btn.config(text="▶")
                self.schemas_expanded.set(False)
            else:
                self.schemas_content.grid()
                self.schemas_toggle_btn.config(text="▼")
                self.schemas_expanded.set(True)
        except Exception:
            pass

    def _toggle_prompt_group(self, group: str):
        grp = getattr(self, '_prompt_group_frames', {}).get(group)
        if not grp:
            return
        cont = grp['container']
        btn = grp['expand_button']
        try:
            if cont.winfo_ismapped():
                cont.pack_forget()
                btn.config(text='▶')
            else:
                cont.pack(fill=tk.X, padx=10)
                btn.config(text='▼')
        except Exception:
            pass

    def _toggle_schema_group(self, group: str):
        grp = getattr(self, '_schema_group_frames', {}).get(group)
        if not grp:
            return
        cont = grp['container']
        btn = grp['expand_button']
        try:
            if cont.winfo_ismapped():
                cont.pack_forget()
                btn.config(text='▶')
            else:
                cont.pack(fill=tk.X, padx=10)
                btn.config(text='▼')
        except Exception:
            pass

    def _open_prompt_in_manager(self, name: str, view: bool):
        try:
            panel = getattr(self, 'category_manager_panel', None)
            if not panel:
                return
            if hasattr(panel, 'prompts_combo') and name:
                panel.prompts_combo.set(name)
            panel._load_semantic_file('prompt', 'view' if view else 'edit', name=name)
        except Exception as e:
            log_error(f"ERROR opening prompt {name}: {e}")

    def _open_schema_in_manager(self, name: str, view: bool):
        try:
            panel = getattr(self, 'category_manager_panel', None)
            if not panel:
                return
            if hasattr(panel, 'schemas_combo') and name:
                panel.schemas_combo.set(name)
            panel._load_semantic_file('schema', 'view' if view else 'edit', name=name)
        except Exception as e:
            log_error(f"ERROR opening schema {name}: {e}")

    def _show_view_buttons(self):
        try:
            current_tab = self.training_notebook.select()
            tab_name = self.training_notebook.tab(current_tab, "text")
            return tab_name != "Runner"
        except Exception:
            return True

    def _bind_wheel_to_canvas(self, canvas: tk.Canvas):
        # Bind mouse wheel to this canvas only
        def _on_wheel(event):
            delta = 0
            if event.num == 4 or event.delta > 0:
                delta = -1
            elif event.num == 5 or event.delta < 0:
                delta = 1
            canvas.yview_scroll(delta, 'units')
            return 'break'
        self._wheel_binding = _on_wheel
        self.parent.bind_all('<MouseWheel>', _on_wheel)
        self.parent.bind_all('<Button-4>', _on_wheel)
        self.parent.bind_all('<Button-5>', _on_wheel)

    def _unbind_wheel_from_canvas(self):
        try:
            self.parent.unbind_all('<MouseWheel>')
            self.parent.unbind_all('<Button-4>')
            self.parent.unbind_all('<Button-5>')
        except Exception:
            pass

    def populate_category_tree(self):
        """Populate the collapsible category tree with script and JSONL checkboxes"""
        # Clear existing tree
        for widget in self.category_tree_frame.winfo_children():
            widget.destroy()

        self.script_vars.clear()
        self.jsonl_vars.clear()
        self.category_expanded.clear()
        self.script_expanded.clear()

        # Get categories
        training_data_path = DATA_DIR.parent / "Training_Data-Sets"
        if not training_data_path.exists():
            ttk.Label(
                self.category_tree_frame,
                text="No categories found",
                style='Config.TLabel'
            ).pack(padx=10, pady=10)
            return

        categories = [d for d in training_data_path.iterdir() if d.is_dir()]
        # Exclude prompt/schema stores from Training Scripts; they are managed in their own sections
        excluded = {"Semantic_States", "PromptBox", "Prompts", "Schemas"}
        categories = [d for d in categories if d.name not in excluded]

        # Initialize frame storage
        self.category_tree_frame.category_frames = {}
        self.category_tree_frame.script_frames = {}

        for category_dir in sorted(categories):
            category_name = category_dir.name
            self.script_vars[category_name] = {}
            self.jsonl_vars[category_name] = {}
            self.script_expanded[category_name] = {}
            self.category_expanded[category_name] = tk.BooleanVar(value=False)

            # Category frame
            category_frame = ttk.Frame(self.category_tree_frame)
            category_frame.pack(fill=tk.X, padx=5, pady=2)

            # Category header button (clickable to expand/collapse)
            header_frame = ttk.Frame(category_frame, style='Category.TFrame')
            header_frame.pack(fill=tk.X)

            expand_button = ttk.Button(
                header_frame,
                text="▶",
                command=lambda c=category_name: self.toggle_category(c),
                width=2,
                style='Select.TButton'
            )
            expand_button.pack(side=tk.LEFT, padx=(0, 5))

            ttk.Label(
                header_frame,
                text=f"📂 {category_name}",
                font=("Arial", 9, "bold"),
                foreground='#61dafb'
            ).pack(side=tk.LEFT)

            # Scripts/JSONL container (hidden by default)
            category_content = ttk.Frame(category_frame)
            self.category_tree_frame.category_frames[category_name] = {
                'container': category_content,
                'expand_button': expand_button
            }

            # Find all .py scripts in category
            script_files = list(category_dir.glob("*.py"))

            for script_file in sorted(script_files):
                script_name = script_file.name
                var = tk.BooleanVar(value=True)  # Default: all selected
                var.trace_add('write', self.update_selection_state) # Add trace
                self.script_vars[category_name][script_name] = var
                self.script_expanded[category_name][script_name] = tk.BooleanVar(value=False)

                # Script frame
                script_frame = ttk.Frame(category_content)
                script_frame.pack(fill=tk.X, pady=1)

                # Script checkbox with expand button
                script_header = ttk.Frame(script_frame)
                script_header.pack(fill=tk.X)

                script_expand_btn = ttk.Button(
                    script_header,
                    text="▶",
                    command=lambda c=category_name, s=script_name: self.toggle_script(c, s),
                    width=2,
                    style='Select.TButton'
                )
                script_expand_btn.pack(side=tk.LEFT, padx=(15, 2))

                # Separate selection (checkbox) from viewing (main clickable area)
                script_cb = ttk.Checkbutton(
                    script_header,
                    text="",
                    variable=var,
                    style='Category.TCheckbutton',
                    width=2,
                    command=lambda c=category_name, s=script_name, v=var: self.on_script_checkbox_toggle(c, s, v.get())
                )
                script_cb.pack(side=tk.LEFT, padx=(0,4))

                # Main clickable area: clicking filename loads script into viewer
                ttk.Button(
                    script_header,
                    text=f"🐍 {script_name}",
                    command=partial(self._open_script_in_manager, script_file),
                    style='Select.TButton'
                ).pack(side=tk.LEFT)

                # Open in Script Manager button
                ttk.Button(
                    script_header,
                    text="✏️",
                    command=partial(self._open_script_in_manager, script_file),
                    style='Select.TButton',
                    width=3
                ).pack(side=tk.RIGHT, padx=2)

                # JSONL files container (hidden by default)
                jsonl_container = ttk.Frame(script_frame)
                # Populate JSONL files under this script
                jsonl_files_local = list(category_dir.glob("*.jsonl"))
                show_view = self._show_view_buttons()
                for jsonl_file in sorted(jsonl_files_local):
                    jsonl_name = jsonl_file.name
                    var = self.jsonl_vars[category_name].get(jsonl_name)
                    if var is None:
                        var = tk.BooleanVar(value=True)
                        var.trace_add('write', self.update_selection_state)
                        self.jsonl_vars[category_name][jsonl_name] = var
                    row_frame = ttk.Frame(jsonl_container)
                    row_frame.pack(fill=tk.X)
                    # Separate selection (checkbox) from viewing (clickable filename)
                    jsonl_cb = ttk.Checkbutton(
                        row_frame,
                        text="",
                        variable=var,
                        style='Category.TCheckbutton',
                        width=2
                    )
                    jsonl_cb.pack(side=tk.LEFT, padx=(25, 4), pady=1)

                    ttk.Button(
                        row_frame,
                        text=f"📄 {jsonl_name}",
                        command=partial(self._open_jsonl_in_manager_view, jsonl_file),
                        style='Select.TButton'
                    ).pack(side=tk.LEFT)

                # Store script frame references
                key = f"{category_name}::{script_name}"
                self.category_tree_frame.script_frames[key] = {
                    'container': jsonl_container,
                    'expand_button': script_expand_btn
                }

            # Category-level JSONL listing removed; JSONL files are shown under each script's toggle

    def _open_script_in_manager(self, path: Path):
        try:
            if hasattr(self, 'category_manager_panel') and self.category_manager_panel:
                self.category_manager_panel.select_script_file(path)
        except Exception as e:
            log_error(f"ERROR: Failed to open script in manager: {e}")

    def _open_jsonl_in_manager_view(self, path: Path):
        try:
            if hasattr(self, 'category_manager_panel') and self.category_manager_panel:
                self.category_manager_panel.select_jsonl_file(path)
                self.category_manager_panel.view_jsonl_file()
        except Exception as e:
            log_error(f"ERROR: Failed to open JSONL in manager: {e}")
        
        self.update_selection_state() # Set initial state

    def on_script_checkbox_toggle(self, category_name, script_name, checked):
        """When a script is (un)checked, cascade the state to its nested JSONL files in that category."""
        try:
            jsonl_map = self.jsonl_vars.get(category_name, {})
            for name, jvar in jsonl_map.items():
                jvar.set(bool(checked))
        except Exception as e:
            log_error(f"ERROR: Failed cascading script checkbox to JSONL in {category_name}/{script_name}: {e}")

    def toggle_category(self, category_name):
        """Toggle category expansion"""
        is_expanded = self.category_expanded[category_name].get()
        frames = self.category_tree_frame.category_frames.get(category_name)

        if not frames:
            return

        if is_expanded:
            # Collapse
            frames['container'].pack_forget()
            frames['expand_button'].config(text="▶")
            self.category_expanded[category_name].set(False)
        else:
            # Expand
            frames['container'].pack(fill=tk.X, pady=(0, 5))
            frames['expand_button'].config(text="▼")
            self.category_expanded[category_name].set(True)

    def toggle_script(self, category_name, script_name):
        """Toggle script expansion to show/hide JSONL files"""
        key = f"{category_name}::{script_name}"
        is_expanded = self.script_expanded[category_name][script_name].get()
        frames = self.category_tree_frame.script_frames.get(key)

        if not frames:
            return

        if is_expanded:
            # Collapse
            frames['container'].pack_forget()
            frames['expand_button'].config(text="▶")
            self.script_expanded[category_name][script_name].set(False)
        else:
            # Expand
            frames['container'].pack(fill=tk.X, pady=(0, 5))
            frames['expand_button'].config(text="▼")
            self.script_expanded[category_name][script_name].set(True)

    def toggle_select_all(self):
        """Command for the 'Select All' checkbutton."""
        # Prevent recursive calls from trace
        if self._is_updating_selection:
            return
            
        if self.select_all_var.get():
            self.select_all_scripts()
        else:
            self.deselect_all_scripts()

    def update_selection_state(self, *args):
        """Update the 'Select All' checkbox and the selection counter."""
        self._is_updating_selection = True
        total_items = 0
        selected_items = 0
        selected_categories = set()

        # Combine all vars
        all_vars = []
        for cat_vars in self.script_vars.values():
            all_vars.extend(cat_vars.values())
        for cat_vars in self.jsonl_vars.values():
            all_vars.extend(cat_vars.values())
        
        total_items = len(all_vars)
        selected_items = sum(v.get() for v in all_vars)

        # Update counter label
        for cat, scripts in self.script_vars.items():
            for script, var in scripts.items():
                if var.get():
                    selected_categories.add(cat)
        
        num_selected_scripts = sum(v.get() for cat in self.script_vars.values() for v in cat.values())

        self.selection_counter_label.config(text=f"({num_selected_scripts} scripts in {len(selected_categories)} cats)")

        # Update 'Select All' checkbox state
        current_state = self.select_all_var.get()
        if selected_items == total_items and total_items > 0:
            if not current_state: self.select_all_var.set(True)
        else:
            if current_state: self.select_all_var.set(False)
        
        self._is_updating_selection = False

    def select_all_scripts(self):
        """Select all training scripts and JSONL files"""
        for category in self.script_vars.values():
            for var in category.values():
                var.set(True)
        for category in self.jsonl_vars.values():
            for var in category.values():
                var.set(True)

    def deselect_all_scripts(self):
        """Deselect all training scripts and JSONL files"""
        for category in self.script_vars.values():
            for var in category.values():
                var.set(False)
        for category in self.jsonl_vars.values():
            for var in category.values():
                var.set(False)

    def get_selected_scripts(self):
        """Get list of selected scripts and JSONL files for training"""
        selected = {
            'scripts': [],
            'jsonl_files': []
        }

        # Get selected scripts
        for category_name, scripts in self.script_vars.items():
            for script_name, var in scripts.items():
                if var.get():
                    script_path = DATA_DIR.parent / "Training_Data-Sets" / category_name / script_name
                    selected['scripts'].append({
                        'category': category_name,
                        'script': script_name,
                        'path': script_path
                    })

        # Get selected JSONL files
        for category_name, jsonl_files in self.jsonl_vars.items():
            for jsonl_name, var in jsonl_files.items():
                if var.get():
                    jsonl_path = DATA_DIR.parent / "Training_Data-Sets" / category_name / jsonl_name
                    selected['jsonl_files'].append({
                        'category': category_name,
                        'file': jsonl_name,
                        'path': jsonl_path
                    })

        return selected

    def select_jsonl_path(self, jsonl_path: str, selected: bool = True):
        """Tick the checkbox for a given JSONL path under Training_Data-Sets.
        Accepts absolute or relative path; no-op if not found in current UI.
        """
        try:
            if not jsonl_path:
                return
            p = Path(jsonl_path)
            # Normalize to repo-relative under Training_Data-Sets
            try:
                root = (DATA_DIR.parent / "Training_Data-Sets").resolve()
                p = p.resolve()
                if root in p.parents:
                    rel = p.relative_to(root)
                else:
                    # Allow passing already-relative like "Tools/file.jsonl"
                    rel = Path(jsonl_path)
            except Exception:
                rel = Path(jsonl_path)
            if len(rel.parts) < 2:
                return
            category = rel.parts[0]
            filename = rel.name
            varmap = self.jsonl_vars.get(category) or {}
            var = varmap.get(filename)
            if var is None:
                return
            var.set(bool(selected))
            # Update selection counter label
            if hasattr(self, 'update_selection_state'):
                self.update_selection_state()
        except Exception:
            pass

    def save_active_training_profile(self):
        """Persist current scripts/prompts/schemas and runner settings to this variant's Training Profile."""
        try:
            import config as cfg
            # Resolve active variant id
            vid = getattr(self, 'active_trainee_name', '') or ''
            if not vid and hasattr(self, 'model_selection_panel') and hasattr(self.model_selection_panel, 'get_variant'):
                try:
                    vid = self.model_selection_panel.get_variant() or ''
                except Exception:
                    vid = ''
            if not vid:
                return

            try:
                tp = cfg.load_training_profile(vid) or {}
            except Exception:
                tp = {}

            # Base model
            try:
                bm = ''
                if hasattr(self, 'model_selection_panel') and hasattr(self.model_selection_panel, 'base_model_var'):
                    bm = self.model_selection_panel.base_model_var.get()
                if bm:
                    tp['base_model'] = bm
            except Exception:
                pass

            # Selections
            sel = self.get_selected_scripts()
            script_paths = []
            try:
                for it in (sel.get('scripts') or []):
                    cat = it.get('category') or ''
                    name = it.get('script') or ''
                    if name:
                        script_paths.append(f"{cat}/{name}" if cat else name)
            except Exception:
                pass
            tp['selected_scripts'] = script_paths
            try:
                tp['selected_prompts'] = list(self.get_selected_prompts() or [])
            except Exception:
                tp['selected_prompts'] = tp.get('selected_prompts') or []
            try:
                tp['selected_schemas'] = list(self.get_selected_schemas() or [])
            except Exception:
                tp['selected_schemas'] = tp.get('selected_schemas') or []

            # Runner settings
            rs = dict(tp.get('runner_settings') or {})
            try:
                rp = getattr(self, 'runner_panel', None)
                if rp is not None:
                    rs.update({
                        'max_time': rp.max_time_var.get(),
                        'max_runs': rp.max_runs_var.get(),
                        'run_delay': rp.run_delay_var.get(),
                        'save_checkpoints': rp.save_checkpoints_var.get(),
                        'checkpoint_interval': rp.checkpoint_interval_var.get(),
                        'early_stop': rp.early_stop_var.get(),
                        'early_stop_patience': rp.early_stop_patience_var.get(),
                        'use_mixed_precision': rp.use_mixed_precision_var.get(),
                        'gradient_accumulation': rp.gradient_accumulation_var.get(),
                        'warmup_steps': rp.warmup_steps_var.get(),
                        'max_cpu_threads': rp.max_cpu_threads_var.get(),
                        'max_ram_percent': rp.max_ram_percent_var.get(),
                        'auto_restart': rp.auto_restart_var.get(),
                        'enable_baseline_tests': rp.enable_baseline_tests_var.get(),
                        'enable_stat_saving': rp.enable_stat_saving_var.get(),
                        # Core params
                        'num_epochs': rp.num_epochs_var.get(),
                        'batch_size': rp.batch_size_var.get(),
                        'learning_rate': rp.learning_rate_var.get(),
                        # Eval context toggles
                        'auto_eval_baseline': rp.auto_eval_baseline_var.get(),
                        'auto_eval_post': rp.auto_eval_post_var.get(),
                        'use_system_prompt': rp.use_prompt_for_eval_var.get(),
                        'use_tool_schema': rp.use_schema_for_eval_var.get(),
                        # Legacy-friendly aliases
                        'max_time_min': rp.max_time_var.get(),
                        'delay_sec': rp.run_delay_var.get(),
                        'mixed_precision': rp.use_mixed_precision_var.get(),
                        'gradient_accum': rp.gradient_accumulation_var.get(),
                        'enable_baseline_skill_tests': rp.enable_baseline_tests_var.get(),
                        'auto_run_pre_eval': rp.auto_eval_baseline_var.get(),
                        'auto_run_post_eval': rp.auto_eval_post_var.get(),
                    })
            except Exception:
                pass
            tp['runner_settings'] = rs

            # Persist
            cfg.save_training_profile(vid, tp)
        except Exception as e:
            log_error(f"[TrainingTab] save_active_training_profile error: {e}")

    def select_all(self):
        """Select all categories and subcategories"""
        for var in self.category_vars.values():
            var.set(True)
        for var in self.subcategory_vars.values():
            var.set(True)
        self.update_preview()

    def deselect_all(self):
        """Deselect all categories and subcategories"""
        for var in self.category_vars.values():
            var.set(False)
        for var in self.subcategory_vars.values():
            var.set(False)
        self.update_preview()

    def update_preview(self, event=None):
        """Update the training summary preview"""
        if hasattr(self, 'summary_panel'):
            self.summary_panel.update_preview()

    def update_profile_combobox(self):
        """Refreshes the list of profiles in the combobox"""
        if hasattr(self, 'profiles_panel'):
            self.profiles_panel.update_profile_combobox()

    # --- Runtime training event handlers ---------------------------------
    def _on_runtime_training_data_ready(self, event):
        try:
            import json as _json
            payload = _json.loads(getattr(event, 'data', '{}') or '{}')
            p = payload.get('path'); vid = payload.get('variant_id')
            if p:
                self.select_jsonl_path(p, selected=True)
                # Optionally set active trainee for subsequent start
                if vid:
                    self.active_trainee_name = vid
                # Persist selections + runner settings
                self.save_active_training_profile()
                # Refresh preview
                self.update_preview()
        except Exception as e:
            log_error(f"[TrainingTab] _on_runtime_training_data_ready error: {e}")

    def _on_start_variant_training(self, event):
        try:
            import json as _json
            payload = _json.loads(getattr(event, 'data', '{}') or '{}')
            vid = payload.get('variant_id')
            if vid:
                # Hydrate plan to ensure base + selections are in place
                self.apply_plan(variant_id=vid)
            if hasattr(self, 'runner_panel'):
                self.runner_panel.start_runner_training()
        except Exception as e:
            log_error(f"[TrainingTab] _on_start_variant_training error: {e}")

    def _on_focus_training_tab(self, event=None):
        try:
            # Select the Training tab in the main notebook if applicable
            # and switch to Runner sub-tab for live logs
            if hasattr(self, 'training_notebook'):
                # Runner tab is index 0
                self.training_notebook.select(0)
            # Attempt to raise window focus
            try:
                self.root.lift(); self.root.focus_force()
            except Exception:
                pass
        except Exception:
            pass

    def _on_select_variant_request(self, event):
        """
        Handle request to pre-select variant for training (Phase 6)
        Triggered by <<SelectVariantForTraining>> event from preview panel or models tab

        Args:
            event: Event with data containing variant_id
        """
        try:
            import json as _json
            payload = _json.loads(getattr(event, 'data', '{}') or '{}')
            variant_id = payload.get('variant_id')

            if not variant_id:
                log_error("[TrainingTab] _on_select_variant_request: No variant_id in payload")
                return

            log_message(f"[TrainingTab] Selecting variant for training: {variant_id}")

            # 1. Switch to training tab in the main app notebook
            # (This requires the main app to have a reference, but we'll focus the tab)
            self._on_focus_training_tab()

            # 2. Pre-select the variant using apply_plan
            # This hydrates the base model and other settings for the variant
            try:
                self.apply_plan(variant_id=variant_id)
                log_message(f"[TrainingTab] Applied plan for variant: {variant_id}")
            except Exception as e:
                log_error(f"[TrainingTab] Failed to apply plan for {variant_id}: {e}")

            # 3. Switch to Runner tab to show training options
            if hasattr(self, 'training_notebook'):
                self.training_notebook.select(0)  # Runner is index 0

            # 4. Update the preview to reflect the selections
            try:
                self.update_preview()
            except Exception as e:
                log_error(f"[TrainingTab] Failed to update preview: {e}")

            # 5. Set active trainee name for subsequent operations
            self.active_trainee_name = variant_id

            log_message(f"[TrainingTab] Successfully prepared training session for {variant_id}")

        except Exception as e:
            log_error(f"[TrainingTab] _on_select_variant_request error: {e}")

    def on_tab_changed(self, event=None):
        """Called when user switches between tabs."""
        # Update Runner panel's model display when switching to Runner tab
        current_tab = self.training_notebook.select()
        tab_name = self.training_notebook.tab(current_tab, "text")

        if tab_name == "Runner" and hasattr(self, 'runner_panel'):
            self.runner_panel.update_training_model_display()
        # No inline "+ New" buttons in right-side display anymore

    def refresh_training_tab(self):
        """Refresh the entire training tab - reloads models, categories, etc."""
        # Refresh available models
        self.ollama_models = get_all_available_models()
        self.trainable_models = [
            m['name'] for m in get_all_trained_models()
            if m.get('type') in ('pytorch', 'trained') and m.get('name') != 'training_stats'
        ]

        # Refresh model selection panel dropdown
        if hasattr(self, 'model_selection_panel'):
            self.model_selection_panel.refresh_model_list(self.trainable_models)

        # Refresh category tree
        if hasattr(self, 'populate_category_tree'):
            self.populate_category_tree()

        # Refresh Prompts and Schemas lists
        try:
            if hasattr(self, '_refresh_prompts_list'):
                self._refresh_prompts_list()
            if hasattr(self, '_refresh_schemas_list'):
                self._refresh_schemas_list()
        except Exception:
            pass

        # Refresh all panels
        self.refresh_all_panels()

        # Update runner model display
        if hasattr(self, 'runner_panel'):
            self.runner_panel.update_training_model_display()

        log_message("TRAINING_TAB: refreshed")

    def refresh_all_panels(self):
        """Refresh all panels that need category updates"""
        if hasattr(self, 'category_manager_panel'):
            self.category_manager_panel.refresh()
        # Recompute category info and repopulate the right-side Training Scripts tree
        self.category_info = get_category_info()
        try:
            if hasattr(self, 'populate_category_tree'):
                self.populate_category_tree()
        except Exception:
            pass
        # Also refresh Prompts/Schemas lists to keep everything in sync
        try:
            if hasattr(self, '_refresh_prompts_list'):
                self._refresh_prompts_list()
            if hasattr(self, '_refresh_schemas_list'):
                self._refresh_schemas_list()
        except Exception:
            pass
        self.update_preview()

    def start_training(self):
        """Start the training process"""
        # Get selected files
        selected_categories = [cat for cat, var in self.category_vars.items() if var.get()]

        if not selected_categories:
            messagebox.showwarning("No Selection", "Please select at least one category!")
            return

        selected_subcats = {}
        for (cat, subcat), var in self.subcategory_vars.items():
            if var.get():
                if cat not in selected_subcats:
                    selected_subcats[cat] = []
                selected_subcats[cat].append(subcat)

        files = get_training_data_files(selected_categories, selected_subcats if selected_subcats else None)

        if not files:
            messagebox.showwarning("No Data", "No training files found for selected categories!")
            return

        # Count files
        def count_file(file_path):
            try:
                with open(file_path) as f:
                    return sum(1 for _ in f)
            except:
                return 0

        # Confirm
        total = sum(count_file(f) for f in files)
        if not messagebox.askyesno(
            "Confirm Training",
            f"Start training with {total} examples?\n\nThis may take several minutes."
        ):
            return

        # Combine files
        temp_file = DATA_DIR / "temp_training_data.jsonl"
        with open(temp_file, 'w') as outfile:
            for file_path in files:
                with open(file_path) as infile:
                    for line in infile:
                        outfile.write(line)

        # Save config
        config = {
            "categories": selected_categories,
            "subcategories": selected_subcats,
            "training_runs": self.config_vars["training_runs"].get(),
            "epochs": self.config_vars["training_runs"].get(),
            "batch_size": self.config_vars["batch_size"].get(),
            "learning_rate": self.config_vars["learning_strength"].get(),
            "learning_strength": self.config_vars["learning_strength"].get(),
            "base_model": self.config_vars["base_model"].get(),
            "total_examples": total
        }

        config_file = DATA_DIR / "last_training_config.json"
        with open(config_file, 'w') as f:
            json.dump(config, f, indent=2)

        # Close GUI and launch training
        self.root.destroy()

        # Run training script
        import os
        env = os.environ.copy()
        env["TRAINING_DATA_FILE"] = str(temp_file)
        env["TRAINING_EPOCHS"] = str(config["epochs"])
        env["TRAINING_BATCH_SIZE"] = str(config["batch_size"])
        env["TRAINING_LEARNING_RATE"] = str(config["learning_rate"])
        env["BASE_MODEL"] = str(config["base_model"])

        subprocess.run(
            ["python3", str(DATA_DIR / "train_with_unsloth.py")],
            env=env,
            cwd=str(DATA_DIR)
        )

    def post_training_actions(self):
        """Perform actions after a training run completes."""
        log_message("TRAINING_TAB: Performing post-training actions...")
        # Example: Refresh the models tab if it exists
        # This assumes the main GUI has a way to access other tabs
        # For now, we'll just print a message.
        messagebox.showinfo("Training Complete", "Training process has finished. Check the Models tab for updates.")
        self._update_prompts_selected_count()
        self._update_schemas_selected_count()

    def _on_prompt_checkbox_toggle(self, name: str, checked: bool):
        try:
            self._update_prompts_selected_count()
        except Exception:
            pass

    def _on_schema_checkbox_toggle(self, name: str, checked: bool):
        try:
            self._update_schemas_selected_count()
        except Exception:
            pass

    def _update_prompts_selected_count(self):
        count = sum(1 for v in self.prompt_vars.values() if v.get())
        if hasattr(self, 'prompts_selected_count_label'):
            self.prompts_selected_count_label.config(text=f"Selected: {count}")

    def _update_schemas_selected_count(self):
        count = sum(1 for v in self.schema_vars.values() if v.get())
        if hasattr(self, 'schemas_selected_count_label'):
            self.schemas_selected_count_label.config(text=f"Selected: {count}")

    def _on_prompt_click(self, name: str):
        # Set primary selected name and open in viewer
        self.prompt_selected_var.set(name)
        try:
            if hasattr(self, 'category_manager_panel') and self.category_manager_panel:
                self.category_manager_panel._open_selected_prompt()
        except Exception as e:
            log_error(f"ERROR opening prompt in manager: {e}")

    def _on_schema_click(self, name: str):
        self.schema_selected_var.set(name)
        try:
            if hasattr(self, 'category_manager_panel') and self.category_manager_panel:
                self.category_manager_panel._open_selected_schema()
        except Exception as e:
            log_error(f"ERROR opening schema in manager: {e}")

    def get_selected_prompts(self):
        return [k for k, v in self.prompt_vars.items() if v.get()]

    def get_selected_schemas(self):
        return [k for k, v in self.schema_vars.items() if v.get()]



    def load_prompts(self, prompt_names: list[str]):
        """
        Tick prompt checkboxes by name.
        Expects self.prompt_vars: {name: tk.BooleanVar}
        """
        try:
            names = set(prompt_names or [])
            for name, var in getattr(self, "prompt_vars", {}).items():
                var.set(name in names)
            if hasattr(self, "_update_prompts_selected_count"):
                self._update_prompts_selected_count()
        except Exception:
            pass

    def load_schemas(self, schema_names: list[str]):
        """
        Tick schema checkboxes by name.
        Expects self.schema_vars: {name: tk.BooleanVar}
        """
        try:
            names = set(schema_names or [])
            for name, var in getattr(self, "schema_vars", {}).items():
                var.set(name in names)
            if hasattr(self, "_update_schemas_selected_count"):
                self._update_schemas_selected_count()
        except Exception:
            pass

    def apply_plan(self, variant_id: str | None = None, training_profile: dict | None = None):
        """
        Load Training Profile for variant_id (or use provided dict) and hydrate UI:
          - scripts/prompts/schemas selections
          - runner settings
          - select Profiles entry
        """
        try:
            tp = {}
            if training_profile:
                tp = training_profile
            elif variant_id:
                tp = cfg.load_training_profile(variant_id) or {}
            else:
                log_error("[TrainingTab] apply_plan called without variant_id/profile", auto_capture=False)
                return

            # 0) Base model -> Model Selection panel + Variant selection
            base_model_name = tp.get("base_model", "")
            try:
                if hasattr(self, "model_selection_panel") and hasattr(self.model_selection_panel, "set_base_model") and base_model_name:
                    self.model_selection_panel.set_base_model(base_model_name)
                elif hasattr(self, "config_vars") and "base_model" in self.config_vars and base_model_name:
                    # Fallback: set config var
                    self.config_vars["base_model"].set(base_model_name)
                    if hasattr(self, "runner_panel"):
                        self.runner_panel.update_training_model_display()
                # Variant combobox: select matching variant
                if hasattr(self, "model_selection_panel") and hasattr(self.model_selection_panel, "set_variant"):
                    self.model_selection_panel.populate_variant_list()
                    self.model_selection_panel.set_variant(variant_id or tp.get("trainee_name") or "")
            except Exception:
                pass

            # 1) Scripts
            scripts = tp.get("selected_scripts", [])
            if hasattr(self, "runner_panel") and hasattr(self.runner_panel, "load_scripts"):
                self.runner_panel.load_scripts(scripts)

            # 2) Prompts
            prompts = tp.get("selected_prompts", [])
            if hasattr(self, "load_prompts"):
                self.load_prompts(prompts)

            # 3) Schemas
            schemas = tp.get("selected_schemas", [])
            if hasattr(self, "load_schemas"):
                self.load_schemas(schemas)

            # 4) Runner settings
            if hasattr(self, "runner_panel") and hasattr(self.runner_panel, "load_settings"):
                self.runner_panel.load_settings(tp.get("runner_settings", {}))

            # 5) Profiles dropdown: select or create entry for variant
            try:
                self.active_trainee_name = variant_id or tp.get("trainee_name")
            except Exception:
                pass
            if hasattr(self, "profiles_panel") and hasattr(self.profiles_panel, "select_profile"):
                self.profiles_panel.select_profile(self.active_trainee_name)

            # 6) Refresh preview/summary if available
            if hasattr(self, "update_preview"):
                self.update_preview()

            log_message(f"[TrainingTab] Plan applied for {self.active_trainee_name}")
            # WO-6p: Fire VariantApplied for cross-tab refresh
            try:
                import json as _json
                base = base_model_name
                payload = _json.dumps({"variant_id": self.active_trainee_name, "base_model": base})
                # Fire on own widget so it can bubble
                self.parent.event_generate("<<VariantApplied>>", data=payload, when="tail")
            except Exception:
                pass
        except Exception as e:
            log_error(f"[TrainingTab] Error in apply_plan: {e}")
