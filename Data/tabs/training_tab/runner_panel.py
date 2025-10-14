# [SYSTEM: GUI | VERSION: 1.9f | STATUS: ACTIVE]
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import subprocess
import threading
import os
import sys
from datetime import datetime
from pathlib import Path
import re

# Ensure the Data directory is in the Python path for module imports
script_dir = os.path.dirname(__file__)
data_dir = os.path.abspath(os.path.join(script_dir, '..', '..', '..', 'Data'))
if data_dir not in sys.path:
    sys.path.insert(0, data_dir)

from config import DATA_DIR
from evaluation_engine import EvaluationEngine
from config import (
    save_baseline_report,
    save_evaluation_report,
    load_baseline_report,
    load_profile,
    get_regression_policy,
    load_benchmarks_index,
    get_benchmarks_dir,
    update_model_baseline_index
)
from logger_util import log_message, get_log_file_path
import json

class RunnerPanel:
    """Panel for running training scripts with live output monitoring"""

    def __init__(self, parent, style, training_tab_instance):
        self.parent = parent
        self.style = style
        self.training_tab_instance = training_tab_instance
        self.process = None
        self.TRAINING_DATA_SETS_DIR = DATA_DIR.parent / "Training_Data-Sets"

        # Runner variables
        self.auto_restart_var = tk.BooleanVar(value=False)
        self.run_delay_var = tk.IntVar(value=0)
        self.max_runs_var = tk.IntVar(value=1) # Note: This is now superseded by the script queue
        self.max_time_var = tk.IntVar(value=120)
        self.save_checkpoints_var = tk.BooleanVar(value=True)
        self.checkpoint_interval_var = tk.IntVar(value=500)
        self.early_stop_var = tk.BooleanVar(value=False)
        self.early_stop_patience_var = tk.IntVar(value=3)
        self.use_mixed_precision_var = tk.BooleanVar(value=True)
        self.gradient_accumulation_var = tk.IntVar(value=16)
        self.warmup_steps_var = tk.IntVar(value=5)
        self.max_cpu_threads_var = tk.IntVar(value=2)
        self.max_ram_percent_var = tk.IntVar(value=70)
        self.enable_baseline_tests_var = tk.BooleanVar(value=True) # New: Control baseline skill tests
        self.enable_stat_saving_var = tk.BooleanVar(value=True) # New: Control whether to save training statistics
        # Evaluation automation
        self.auto_eval_baseline_var = tk.BooleanVar(value=False)
        self.auto_eval_post_var = tk.BooleanVar(value=False)
        # WO-6o: Type Plan overrides toggle
        self.use_plan_overrides_var = tk.BooleanVar(value=True)
        self._plan_settings = {}
            
        # Core Training Parameters (moved from ConfigPanel)
        self.num_epochs_var = tk.IntVar(value=3)
        self.batch_size_var = tk.IntVar(value=2)
        self.learning_rate_var = tk.StringVar(value="2e-4")

        # Sequential execution state
        self.script_queue = []
        self.total_scripts_in_queue = 0
        self.script_running = False

        self.load_runner_defaults(initial_load=True)

    def update_training_model_display(self):
        # Show the model that has been explicitly sent to training (via config_vars['base_model'])
        try:
            model_var = getattr(self.training_tab_instance, 'config_vars', {}).get('base_model')
            model_name = model_var.get() if model_var else "Not Set"
        except Exception:
            model_name = "Not Set"
        if model_name and model_name != "Not Set":
            display_name = model_name.split("/")[-1] if "/" in model_name else model_name
            self.training_model_label.config(text=display_name, foreground='#51cf66')
        else:
            self.training_model_label.config(text="Not Set", foreground='#ff6b6b')
        # Refresh baseline status label when model changes
        try:
            self._update_baseline_status_label()
        except Exception:
            pass

    def create_ui(self):
        # (UI creation code remains the same as the last version)
        log_message("RUNNER: create_ui called")
        self.parent.columnconfigure(0, weight=1)
        self.parent.rowconfigure(0, weight=1)

        # --- Left side: Script output display ---
        output_frame = ttk.Frame(self.parent, style='Category.TFrame')
        output_frame.grid(row=0, column=0, sticky=tk.NSEW, padx=10, pady=10)
        output_frame.columnconfigure(0, weight=1)
        output_frame.rowconfigure(1, weight=1)

        header_frame = ttk.Frame(output_frame, style='Category.TFrame')
        header_frame.grid(row=0, column=0, sticky=tk.EW, pady=5)
        ttk.Label(header_frame, text="📺 Training Output", font=("Arial", 12, "bold"), style='CategoryPanel.TLabel').pack(side=tk.LEFT, padx=(0, 20))
        model_display_frame = ttk.Frame(header_frame, style='Category.TFrame')
        model_display_frame.pack(side=tk.LEFT)
        ttk.Label(model_display_frame, text="Training Model:", font=("Arial", 10, "bold"), style='Config.TLabel').pack(side=tk.LEFT, padx=(0, 5))
        self.training_model_label = ttk.Label(model_display_frame, text="Not Set", font=("Arial", 10), style='Config.TLabel', foreground='#ff6b6b')
        self.training_model_label.pack(side=tk.LEFT)

        self.runner_output = scrolledtext.ScrolledText(output_frame, font=("Courier", 9), wrap=tk.WORD, state=tk.DISABLED, relief='flat', borderwidth=0, highlightthickness=0, bg='#1e1e1e', fg='#00ff00')
        self.runner_output.grid(row=1, column=0, sticky='nsew', padx=5, pady=5)

        # --- Right side: Runner controls (scrollable) ---
        controls_container = ttk.Frame(self.parent, style='Category.TFrame')
        controls_container.grid(row=0, column=1, sticky=tk.NSEW, padx=10, pady=10)
        controls_container.columnconfigure(0, weight=1)
        controls_container.rowconfigure(1, weight=1)

        controls_header = ttk.Frame(controls_container, style='Category.TFrame')
        controls_header.grid(row=0, column=0, columnspan=2, pady=5, sticky=tk.EW, padx=5)
        ttk.Label(controls_header, text="🎮 Controls", font=("Arial", 11, "bold"), style='CategoryPanel.TLabel').pack(side=tk.LEFT)
        ttk.Button(controls_header, text="Load Defaults", command=self.load_runner_defaults, style='Select.TButton').pack(side=tk.RIGHT, padx=2)
        ttk.Button(controls_header, text="Save Defaults", command=self.save_runner_defaults, style='Select.TButton').pack(side=tk.RIGHT, padx=2)

        self.controls_canvas = tk.Canvas(controls_container, bg="#2b2b2b", highlightthickness=0)
        self.controls_canvas.bind('<Enter>', self._bind_mousewheel)
        self.controls_canvas.bind('<Leave>', self._unbind_mousewheel)
        controls_scrollbar = ttk.Scrollbar(controls_container, orient="vertical", command=self.controls_canvas.yview)
        controls_frame = ttk.Frame(self.controls_canvas, style='Category.TFrame')
        controls_frame.columnconfigure(0, weight=1)
        controls_frame.bind("<Configure>", lambda e: self.controls_canvas.configure(scrollregion=self.controls_canvas.bbox("all")))
        canvas_window = self.controls_canvas.create_window((0, 0), window=controls_frame, anchor="nw")
        self.controls_canvas.configure(yscrollcommand=controls_scrollbar.set)
        self.controls_canvas.bind("<Configure>", lambda e: self.controls_canvas.itemconfig(canvas_window, width=e.width))
        self.controls_canvas.grid(row=1, column=0, sticky='nsew')
        controls_scrollbar.grid(row=1, column=1, sticky='ns')

        current_row = 0
        time_section = ttk.LabelFrame(controls_frame, text="⏱️ Time Limits", style='TLabelframe')
        time_section.grid(row=current_row, column=0, sticky=tk.EW, padx=5, pady=5); current_row += 1
        max_time_frame = ttk.Frame(time_section)
        max_time_frame.pack(fill=tk.X, padx=10, pady=5)
        ttk.Label(max_time_frame, text="Max Time (min):", style='Config.TLabel', width=15).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Spinbox(max_time_frame, from_=1, to=1440, textvariable=self.max_time_var, width=8).pack(side=tk.LEFT)
        
        # Max runs is deprecated by sequential execution, but we leave it for now.
        max_runs_frame = ttk.Frame(time_section)
        max_runs_frame.pack(fill=tk.X, padx=10, pady=5)
        ttk.Label(max_runs_frame, text="Max Runs (Legacy):", style='Config.TLabel', width=15).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Spinbox(max_runs_frame, from_=1, to=100, textvariable=self.max_runs_var, width=8).pack(side=tk.LEFT)

        delay_frame = ttk.Frame(time_section)
        delay_frame.pack(fill=tk.X, padx=10, pady=5)
        ttk.Label(delay_frame, text="Delay (sec):", style='Config.TLabel', width=15).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Spinbox(delay_frame, from_=0, to=300, textvariable=self.run_delay_var, width=8).pack(side=tk.LEFT)

        checkpoint_section = ttk.LabelFrame(controls_frame, text="💾 Checkpoints", style='TLabelframe')
        checkpoint_section.grid(row=current_row, column=0, sticky=tk.EW, padx=5, pady=5); current_row += 1
        ttk.Checkbutton(checkpoint_section, text="Save checkpoints", variable=self.save_checkpoints_var, style='Category.TCheckbutton').pack(padx=10, pady=5, anchor=tk.W)
        ttk.Checkbutton(checkpoint_section, text="Enable Stat Saving", variable=self.enable_stat_saving_var, style='Category.TCheckbutton').pack(padx=10, pady=5, anchor=tk.W)
        checkpoint_interval_frame = ttk.Frame(checkpoint_section)
        checkpoint_interval_frame.pack(fill=tk.X, padx=10, pady=5)
        ttk.Label(checkpoint_interval_frame, text="Interval (steps):", style='Config.TLabel', width=15).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Spinbox(checkpoint_interval_frame, from_=10, to=10000, increment=10, textvariable=self.checkpoint_interval_var, width=8).pack(side=tk.LEFT)

        optimization_section = ttk.LabelFrame(controls_frame, text="⚡ Optimization", style='TLabelframe')
        optimization_section.grid(row=current_row, column=0, sticky=tk.EW, padx=5, pady=5); current_row += 1
        ttk.Checkbutton(optimization_section, text="Mixed precision (FP16)", variable=self.use_mixed_precision_var, style='Category.TCheckbutton').pack(padx=10, pady=5, anchor=tk.W)
        grad_accum_frame = ttk.Frame(optimization_section)
        grad_accum_frame.pack(fill=tk.X, padx=10, pady=5)
        ttk.Label(grad_accum_frame, text="Gradient Accum:", style='Config.TLabel', width=15).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Spinbox(grad_accum_frame, from_=1, to=32, textvariable=self.gradient_accumulation_var, width=8).pack(side=tk.LEFT)
        warmup_frame = ttk.Frame(optimization_section)
        warmup_frame.pack(fill=tk.X, padx=10, pady=5)
        ttk.Label(warmup_frame, text="Warmup Steps:", style='Config.TLabel', width=15).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Spinbox(warmup_frame, from_=0, to=1000, increment=10, textvariable=self.warmup_steps_var, width=8).pack(side=tk.LEFT)

        # Baseline Skill Tests
        ttk.Checkbutton(optimization_section, text="Enable Baseline Skill Tests", variable=self.enable_baseline_tests_var, style='Category.TCheckbutton').pack(padx=10, pady=5, anchor=tk.W)

        # Evaluation Automation (scheduling)
        eval_section = ttk.LabelFrame(controls_frame, text="🧪 Evaluation Automation", style='TLabelframe')
        eval_section.grid(row=current_row, column=0, sticky=tk.EW, padx=5, pady=5); current_row += 1
        ttk.Checkbutton(eval_section, text="Auto-run Baseline Before Training", variable=self.auto_eval_baseline_var, style='Category.TCheckbutton').pack(padx=10, pady=5, anchor=tk.W)
        ttk.Checkbutton(eval_section, text="Auto-run Post-Training Evaluation", variable=self.auto_eval_post_var, style='Category.TCheckbutton').pack(padx=10, pady=(0,5), anchor=tk.W)

        # Evaluation Context (prompt/schema selectors for auto-eval)
        ctx_section = ttk.LabelFrame(controls_frame, text="🧩 Evaluation Context", style='TLabelframe')
        ctx_section.grid(row=current_row, column=0, sticky=tk.EW, padx=5, pady=5); current_row += 1
        self.use_prompt_for_eval_var = tk.BooleanVar(value=False)
        self.use_schema_for_eval_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(ctx_section, text="Use System Prompt", variable=self.use_prompt_for_eval_var, style='Category.TCheckbutton').pack(padx=10, pady=5, anchor=tk.W)
        ttk.Checkbutton(ctx_section, text="Use Tool Schema", variable=self.use_schema_for_eval_var, style='Category.TCheckbutton').pack(padx=10, pady=(0,5), anchor=tk.W)

        # Baseline Controls
        baseline_section = ttk.LabelFrame(controls_frame, text="📏 Baseline Controls", style='TLabelframe')
        baseline_section.grid(row=current_row, column=0, sticky=tk.EW, padx=5, pady=5); current_row += 1
        base_row = ttk.Frame(baseline_section)
        base_row.pack(fill=tk.X, padx=10, pady=5)
        ttk.Label(base_row, text="Baseline Source:", style='Config.TLabel', width=16).pack(side=tk.LEFT, padx=(0, 5))
        self.baseline_source_var = tk.StringVar(value="Auto")
        ttk.Combobox(base_row, textvariable=self.baseline_source_var, values=["Auto", "Base", "Level"], state='readonly', width=12).pack(side=tk.LEFT)
        ttk.Button(base_row, text="View Baselines", command=self._open_models_baselines_from_runner, style='Select.TButton').pack(side=tk.RIGHT)

        # Active baseline quick status + actions
        status_row = ttk.Frame(baseline_section)
        status_row.pack(fill=tk.X, padx=10, pady=(0,6))
        self.baseline_status_label = ttk.Label(status_row, text="Active baseline: None", style='Config.TLabel')
        self.baseline_status_label.pack(side=tk.LEFT, padx=(0,6))
        ttk.Button(status_row, text="View Active Baseline", command=self._view_active_baseline_summary, style='Select.TButton').pack(side=tk.RIGHT)

        # Core Training Parameters (moved from ConfigPanel)
        core_params_section = ttk.LabelFrame(controls_frame, text="⚙️ Core Training Parameters", style='TLabelframe')
        core_params_section.grid(row=current_row, column=0, sticky=tk.EW, padx=5, pady=5); current_row += 1

        # Num Epochs
        epochs_frame = ttk.Frame(core_params_section)
        epochs_frame.pack(fill=tk.X, padx=10, pady=5)
        ttk.Label(epochs_frame, text="Epochs:", style='Config.TLabel', width=15).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Spinbox(epochs_frame, from_=1, to=100, textvariable=self.num_epochs_var, width=8).pack(side=tk.LEFT)

        # Batch Size
        batch_frame = ttk.Frame(core_params_section)
        batch_frame.pack(fill=tk.X, padx=10, pady=5)
        ttk.Label(batch_frame, text="Batch Size:", style='Config.TLabel', width=15).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Spinbox(batch_frame, from_=1, to=32, textvariable=self.batch_size_var, width=8).pack(side=tk.LEFT)

        # Learning Rate
        lr_frame = ttk.Frame(core_params_section)
        lr_frame.pack(fill=tk.X, padx=10, pady=5)
        ttk.Label(lr_frame, text="Learning Rate:", style='Config.TLabel', width=15).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Entry(lr_frame, textvariable=self.learning_rate_var, width=10).pack(side=tk.LEFT)

        # Early Stopping (hidden/disabled if no GPU)
        show_early_stop = False
        try:
            import torch
            show_early_stop = bool(torch.cuda.is_available())
        except Exception:
            show_early_stop = False
        if show_early_stop:
            early_stop_section = ttk.LabelFrame(controls_frame, text="🛑 Early Stopping", style='TLabelframe')
            early_stop_section.grid(row=current_row, column=0, sticky=tk.EW, padx=5, pady=5); current_row += 1
            ttk.Checkbutton(early_stop_section, text="Enable early stopping", variable=self.early_stop_var, style='Category.TCheckbutton').pack(padx=10, pady=5, anchor=tk.W)
            patience_frame = ttk.Frame(early_stop_section)
            patience_frame.pack(fill=tk.X, padx=10, pady=5)
            ttk.Label(patience_frame, text="Patience (epochs):", style='Config.TLabel', width=15).pack(side=tk.LEFT, padx=(0, 5))
            ttk.Spinbox(patience_frame, from_=1, to=20, textvariable=self.early_stop_patience_var, width=8).pack(side=tk.LEFT)
            ttk.Label(early_stop_section, text="⚠️ Functionality depends on 'transformers' version.", font=("Arial", 8), foreground='#ffaa00', wraplength=200, justify=tk.LEFT).pack(padx=10, pady=(0, 5), anchor=tk.W)
        else:
            # Reserve a small note so users know why it's hidden
            note = ttk.Label(controls_frame, text="🛈 Early Stopping disabled (GPU required)", style='Config.TLabel')
            note.grid(row=current_row, column=0, sticky=tk.W, padx=10, pady=5); current_row += 1

        restart_section = ttk.LabelFrame(controls_frame, text="🔄 Auto-Restart", style='TLabelframe')
        restart_section.grid(row=current_row, column=0, sticky=tk.EW, padx=5, pady=5); current_row += 1
        ttk.Checkbutton(restart_section, text="Auto-restart on completion", variable=self.auto_restart_var, style='Category.TCheckbutton').pack(padx=10, pady=10, anchor=tk.W)

        actions_section = ttk.LabelFrame(controls_frame, text="🎮 Actions", style='TLabelframe')
        actions_section.grid(row=current_row, column=0, sticky=tk.EW, padx=5, pady=10); current_row += 1
        self.start_button = ttk.Button(actions_section, text="▶️ Start Training", command=self.start_runner_training, style='Action.TButton')
        self.start_button.pack(fill=tk.X, padx=10, pady=5)
        self.stop_button = ttk.Button(actions_section, text="⏹️ Stop Training", command=self.stop_runner_training, style='Select.TButton', state=tk.DISABLED)
        self.stop_button.pack(fill=tk.X, padx=10, pady=5)
        ttk.Button(actions_section, text="🗑️ Clear Output", command=self.clear_runner_output, style='Select.TButton').pack(fill=tk.X, padx=10, pady=5)

        # WO-6o: Type Plan overrides toggle
        plan_section = ttk.LabelFrame(controls_frame, text="🧩 Type Plan Overrides", style='TLabelframe')
        plan_section.grid(row=current_row, column=0, sticky=tk.EW, padx=5, pady=5); current_row += 1
        def _on_toggle():
            try:
                if self.use_plan_overrides_var.get() and self._plan_settings:
                    self.load_settings(self._plan_settings)
            except Exception:
                pass
        ttk.Checkbutton(plan_section, text="Use Type Plan overrides", variable=self.use_plan_overrides_var, style='Category.TCheckbutton', command=_on_toggle).pack(padx=10, pady=6, anchor=tk.W)

        status_section = ttk.LabelFrame(controls_frame, text="📊 Status", style='TLabelframe')
        status_section.grid(row=current_row, column=0, sticky=tk.EW, padx=5, pady=10); current_row += 1
        self.runner_status_label = ttk.Label(status_section, text="⚪ Idle", style='Config.TLabel')
        self.runner_status_label.pack(padx=10, pady=10)
        self.runner_progress_label = ttk.Label(status_section, text="Run 0 of 0", style='Config.TLabel')
        self.runner_progress_label.pack(padx=10, pady=(0, 10))

        self.update_training_model_display()
        # Also surface current baseline status on load
        try:
            self._update_baseline_status_label()
        except Exception:
            pass

    def _open_models_baselines_from_runner(self):
        try:
            # Select Models tab and open its Baselines sub-tab
            tabs = getattr(self.training_tab_instance, 'tab_instances', None)
            if not tabs or 'models_tab' not in tabs:
                return
            models_meta = tabs['models_tab']
            models_frame = models_meta.get('frame')
            models_inst = models_meta.get('instance')
            # Select the top-level tab
            nb = self.training_tab_instance.parent.master.master  # heuristic to get main notebook
            try:
                nb.select(models_frame)
            except Exception:
                pass
            # Select Baselines sub-tab
            if hasattr(models_inst, 'model_info_notebook') and hasattr(models_inst, 'baselines_tab_frame'):
                models_inst.model_info_notebook.select(models_inst.baselines_tab_frame)
                if hasattr(models_inst, '_refresh_baselines_panel'):
                    models_inst._refresh_baselines_panel()
        except Exception:
            pass

    def _get_selected_model_name(self) -> str:
        try:
            if hasattr(self.training_tab_instance, 'model_selection_panel'):
                params = self.training_tab_instance.model_selection_panel.get_config_params()
                return params.get("model_name") or ""
        except Exception:
            return ""
        return ""

    def _resolve_active_baseline_path(self, model_name: str) -> Path | None:
        """Find the active baseline JSON path for a model.

        Resolution order:
        1) Exact key match in index.json using cleaned name.
        2) Fuzzy match of model key in index.json (normalize/strip variants).
        3) Scan benchmarks dir for best matching files by name pattern.
        4) Canonical baseline path for cleaned model name.
        """
        try:
            def _clean(s: str) -> str:
                return s.replace('/', '_').replace(':', '_')

            def _norm(s: str) -> str:
                s = s.lower()
                # remove common suffixes
                s = s.replace('instruct', '').replace('coder', '')
                return re.sub(r'[^a-z0-9]+', '', s)

            clean = _clean(model_name)
            idx = load_benchmarks_index() or {}
            models = (idx.get('models') or {})

            # 1) Exact key
            active = (models.get(clean) or {}).get('active') or {}
            p = active.get('path')
            if p:
                bp = Path(p)
                if bp.exists():
                    return bp

            # 2) Fuzzy key match
            want = _norm(model_name)
            for key, rec in models.items():
                if not isinstance(rec, dict):
                    continue
                k = _norm(key)
                if k == want or k.startswith(want) or want.startswith(k):
                    ap = (rec.get('active') or {}).get('path')
                    if ap and Path(ap).exists():
                        return Path(ap)

            # 3) Scan directory for best matching files
            bdir = get_benchmarks_dir()
            if bdir.exists():
                cands = []
                for jf in bdir.glob("*.json"):
                    name = jf.stem  # without .json
                    norm_name = _norm(name)
                    if want in norm_name or norm_name in want:
                        cands.append(jf)
                if cands:
                    cands.sort(key=lambda p: p.stat().st_mtime, reverse=True)
                    return cands[0]

            # 4) Canonical path fallback
            canon = get_benchmarks_dir() / f"{clean}_baseline.json"
            return canon if canon.exists() else None
        except Exception:
            return None

    def _update_baseline_status_label(self):
        """Update the small baseline status label with active filename or None."""
        model_name = self._get_selected_model_name()
        if not model_name:
            self.baseline_status_label.config(text="Active baseline: None")
            return
        p = self._resolve_active_baseline_path(model_name)
        if p:
            self.baseline_status_label.config(text=f"Active baseline: {p.name}")
        else:
            self.baseline_status_label.config(text="Active baseline: None")

    def _basename(self, p: str) -> str:
        import os
        return os.path.basename(p or "")

    def load_scripts(self, script_paths: list[str]):
        """
        Tick script checkboxes by basename.
        Expects self.script_vars: {category: {basename: tk.BooleanVar}}
        """
        try:
            names = set(self._basename(p) for p in (script_paths or []))
            for cat, varmap in getattr(self, "script_vars", {}).items():
                for name, var in varmap.items():
                    var.set(name in names)
        except Exception:
            pass

    def load_settings(self, settings: dict):
        """
        Apply runner settings if the widget exposes .set(value).
        """
        try:
            st = settings or {}
            # Store plan settings for reapplication on toggle
            self._plan_settings = dict(st)
            if not self.use_plan_overrides_var.get():
                return
            for key, value in st.items():
                w = getattr(self, key, None)
                if hasattr(w, "set"):
                    try:
                        w.set(value)
                    except Exception:
                        pass
        except Exception:
            pass

    def _view_active_baseline_summary(self):
        """Dump a concise summary of the active baseline (overall + per-skill) into runner output."""
        model_name = self._get_selected_model_name()
        if not model_name:
            self.append_runner_output("No model selected.\n")
            return
        p = self._resolve_active_baseline_path(model_name)
        if not p:
            self.append_runner_output(f"No active baseline found for model '{model_name}'.\n")
            return
        try:
            with open(p, 'r') as f:
                rep = json.load(f)
        except Exception as e:
            self.append_runner_output(f"Failed to load baseline: {e}\n")
            return
        overall = rep.get('pass_rate_percent', 'N/A')
        self.append_runner_output(f"\nNOTE: baseline confirmed '{p.name}' — overall {overall}\n")
        per_skill = rep.get('per_skill') or {}
        if per_skill:
            parts = []
            # Keep concise: show up to first 10 skills
            for i, (sk, data) in enumerate(sorted(per_skill.items())):
                if i >= 10:
                    break
                parts.append(f"{sk} {data.get('pass_rate_percent', 'N/A')}")
            self.append_runner_output("Skills: " + ", ".join(parts) + "\n")
        else:
            self.append_runner_output("Skills: N/A\n")
        # Refresh label too
        try:
            self._update_baseline_status_label()
        except Exception:
            pass

    def start_runner_training(self):
        log_message("RUNNER: Start button clicked.")
        # If a profile is selected, confirm with the user before starting
        try:
            prof_var = getattr(self.training_tab_instance, 'selected_profile_var', None)
            profile_name = prof_var.get() if prof_var else ""
            if profile_name:
                # Build a brief summary from current UI (reflects profile-applied settings)
                summary_lines = [
                    f"Profile: {profile_name}",
                    f"Model: {self.training_tab_instance.model_selection_panel.base_model_var.get()}",
                    f"Epochs: {self.num_epochs_var.get()}, Batch: {self.batch_size_var.get()}, LR: {self.learning_rate_var.get()}",
                    f"Auto Baseline: {'On' if self.auto_eval_baseline_var.get() else 'Off'}",
                    f"Auto Post-Eval: {'On' if self.auto_eval_post_var.get() else 'Off'}",
                ]
                # Include right-side prompt/schema selections if present
                try:
                    prompt_name = getattr(self.training_tab_instance, 'prompt_selected_var', None)
                    schema_name = getattr(self.training_tab_instance, 'schema_selected_var', None)
                    if prompt_name and prompt_name.get():
                        summary_lines.append(f"Prompt: {prompt_name.get()}")
                    if schema_name and schema_name.get():
                        summary_lines.append(f"Schema: {schema_name.get()}")
                except Exception:
                    pass
                if not messagebox.askyesno(
                    "Confirm Training Profile",
                    "\n".join(summary_lines) + "\n\nProceed with this profile?"
                ):
                    self.append_runner_output("Training canceled by user at profile confirmation.\n")
                    return
        except Exception as e:
            log_message(f"RUNNER: Non-fatal error building profile confirmation: {e}")
        
        self.script_queue = []
        for category_name, scripts in self.training_tab_instance.script_vars.items():
            for script_name, var in scripts.items():
                if var.get():
                    self.script_queue.append((category_name, script_name))

        if not self.script_queue:
            self.log_output("❌ Error: Please select at least one training script from the right panel.\n", "error")
            return

        self.start_button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.NORMAL)
        self.runner_status_label.config(text="🟢 Running")
        self.script_running = True
        self.total_scripts_in_queue = len(self.script_queue)

        self.append_runner_output(f"--- STARTING SEQUENTIAL TRAINING: {self.total_scripts_in_queue} SCRIPT(S) ---\n")
        # Surface baseline context at start if available
        try:
            self._view_active_baseline_summary()
        except Exception:
            pass
        log_message(f"RUNNER: Starting sequential training with {self.total_scripts_in_queue} script(s) in queue.")
        
        self._run_next_script_in_queue()

    def _run_next_script_in_queue(self):
        if not self.script_running or not self.script_queue:
            log_message("RUNNER: Script queue finished or execution was stopped.")
            self.append_runner_output("\n--- SEQUENTIAL TRAINING SESSION FINISHED ---\n")
            self.start_button.config(state=tk.NORMAL)
            self.stop_button.config(state=tk.DISABLED)
            self.runner_status_label.config(text="✅ Complete")
            self.script_running = False
            return

        current_run_number = self.total_scripts_in_queue - len(self.script_queue) + 1
        self.runner_progress_label.config(text=f"Run {current_run_number} of {self.total_scripts_in_queue}")
        
        selected_category, selected_script = self.script_queue.pop(0)

        self.append_runner_output(f"\n{ '='*20 } RUN {current_run_number}: {selected_category}/{selected_script} { '='*20 }\n")
        log_message(f"RUNNER: Starting script {current_run_number}/{self.total_scripts_in_queue}: {selected_category}/{selected_script}")

        script_path = self.TRAINING_DATA_SETS_DIR / selected_category / selected_script
        if not script_path.exists():
            self.log_output(f"❌ Error: Training script not found at {script_path}\n", "error")
            log_message(f"RUNNER ERROR: Script not found at {script_path}. Skipping.")
            self.parent.after(100, self._run_next_script_in_queue) # Immediately try next
            return

        # Fetch model config from the Model Selection panel (replaces old config_panel)
        config_params = {}
        try:
            if hasattr(self.training_tab_instance, 'model_selection_panel'):
                config_params = self.training_tab_instance.model_selection_panel.get_config_params()
        except Exception as e:
            log_message(f"RUNNER ERROR: Could not retrieve model selection params: {e}")
            config_params = {}
        if not config_params:
            self.log_output("❌ Error: Could not retrieve training configuration parameters.\n", "error")
            log_message("RUNNER ERROR: Could not get config_params. Aborting session.")
            self.stop_runner_training(user_initiated=False)
            return

        selected_data = self.training_tab_instance.get_selected_scripts()
        selected_datasets = [str(item['path']) for item in selected_data.get('jsonl_files', [])]

        env_vars = os.environ.copy()
        env_vars["BASE_MODEL"] = config_params.get("model_name", "")
        # Core Training Parameters now from RunnerPanel's UI
        env_vars["TRAINING_EPOCHS"] = str(self.num_epochs_var.get())
        env_vars["TRAINING_BATCH_SIZE"] = str(self.batch_size_var.get())
        env_vars["TRAINING_LEARNING_RATE"] = str(self.learning_rate_var.get())
        env_vars["TRAINING_MAX_SEQ_LENGTH"] = str(config_params.get("max_seq_length", 2048))
        env_vars["TRAINING_LORA_R"] = str(config_params.get("lora_r", 16))
        env_vars["TRAINING_LORA_ALPHA"] = str(config_params.get("lora_alpha", 16))
        env_vars["TRAINING_DATA_FILES"] = ",".join(selected_datasets) if selected_datasets else ""
        env_vars["GEMINI_LOG_FILE"] = get_log_file_path()
        env_vars["RUNNER_MAX_TIME"] = str(self.max_time_var.get())
        env_vars["RUNNER_SAVE_CHECKPOINTS"] = str(self.save_checkpoints_var.get())
        env_vars["RUNNER_CHECKPOINT_INTERVAL"] = str(self.checkpoint_interval_var.get())
        env_vars["RUNNER_MIXED_PRECISION"] = str(self.use_mixed_precision_var.get())
        env_vars["RUNNER_GRADIENT_ACCUMULATION"] = str(self.gradient_accumulation_var.get())
        env_vars["RUNNER_WARMUP_STEPS"] = str(self.warmup_steps_var.get())
        env_vars["RUNNER_EARLY_STOPPING"] = str(self.early_stop_var.get())
        env_vars["RUNNER_EARLY_STOPPING_PATIENCE"] = str(self.early_stop_patience_var.get())
        env_vars["RUNNER_MAX_CPU_THREADS"] = str(self.max_cpu_threads_var.get())
        env_vars["RUNNER_MAX_RAM_PERCENT"] = str(self.max_ram_percent_var.get())
        env_vars["RUNNER_ENABLE_BASELINE_TESTS"] = str(self.enable_baseline_tests_var.get())
        env_vars["RUNNER_ENABLE_STAT_SAVING"] = str(self.enable_stat_saving_var.get()) # New: Pass stat saving setting
        
        command = [sys.executable, str(script_path)]
        # Optionally run pre-training baseline
        try:
            if self.auto_eval_baseline_var.get():
                self.append_runner_output("\n=== Running Pre-Training Baseline (All suites) ===\n")
                self._auto_run_evaluation(as_baseline=True)
        except Exception as e:
            self.append_runner_output(f"Baseline evaluation failed: {e}\n")

        # Display a brief note about selected prompt/schema (from right-side selectors) before launching
        try:
            prompt_name = getattr(self.training_tab_instance, 'prompt_selected_var', None)
            schema_name = getattr(self.training_tab_instance, 'schema_selected_var', None)
            if self.use_prompt_for_eval_var.get() and prompt_name and prompt_name.get():
                self.append_runner_output(f"Using Prompt: {prompt_name.get()}\n")
            if self.use_schema_for_eval_var.get() and schema_name and schema_name.get():
                self.append_runner_output(f"Using Schema: {schema_name.get()}\n")
        except Exception:
            pass

        self.training_thread = threading.Thread(target=self._run_training_process, args=(command, env_vars))
        self.training_thread.daemon = True
        self.training_thread.start()

    def _run_training_process(self, command, env_vars):
        log_message(f"RUNNER: Launching subprocess with command: {command}")
        try:
            preexec_fn = os.setsid if 'linux' in sys.platform else None
            self.process = subprocess.Popen(
                command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                bufsize=1, universal_newlines=True, env=env_vars, preexec_fn=preexec_fn
            )
            log_message(f"RUNNER: Subprocess started with PID: {self.process.pid}")
            for line in self.process.stdout:
                log_message(f"STDOUT: {line.strip()}")
                self.log_output(line, "stdout")
            self.process.wait()
            log_message(f"RUNNER: Subprocess finished with return code: {self.process.returncode}")
            if self.process.returncode != 0:
                self.log_output(f"\n⚠️ Training process failed with exit code {self.process.returncode}.\n", "error")
            else:
                # Optionally run post-training evaluation
                try:
                    if self.auto_eval_post_var.get():
                        self.append_runner_output("\n=== Running Post-Training Evaluation (All suites) ===\n")
                        self._auto_run_evaluation(as_baseline=False)
                except Exception as e:
                    self.append_runner_output(f"Post-training evaluation failed: {e}\n")
        except Exception as e:
            log_message(f"RUNNER ERROR: Exception in _run_training_process: {e}")
            self.log_output(f"\n❌ Error running training process: {e}\n", "error")
        finally:
            self.process = None
            delay_ms = self.run_delay_var.get() * 1000
            if self.script_running and self.script_queue: # Only delay if there's a next script
                log_message(f"RUNNER: Script finished. Waiting {delay_ms}ms before next run.")
                if delay_ms > 0:
                    self.append_runner_output(f"\n--- Waiting {self.run_delay_var.get()} seconds before next run ---\n")
            self.parent.after(delay_ms, self._run_next_script_in_queue)

    def stop_runner_training(self, user_initiated=True):
        if user_initiated:
            log_message("RUNNER: Stop button clicked by user.")
        
        self.script_queue = [] # Clear any pending scripts
        self.script_running = False 
        
        if self.process and self.process.poll() is None:
            self.log_output("Attempting to stop training process...\n", "system")
            log_message(f"RUNNER: Attempting to terminate process group {self.process.pid}")
            try:
                if 'linux' in sys.platform:
                    os.killpg(os.getpgid(self.process.pid), subprocess.signal.SIGTERM)
                else:
                    self.process.terminate()
                self.process.wait(timeout=5)
                self.log_output("Training process stopped.\n", "system")
                log_message("RUNNER: Training process stopped successfully.")
            except Exception as e:
                self.log_output(f"Error stopping process: {e}\n", "error")
                log_message(f"RUNNER ERROR: Error stopping process: {e}")
            finally:
                self.process = None
        
        self.start_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)
        self.runner_status_label.config(text="🔴 Stopped")
        if user_initiated:
            self.append_runner_output("\n=== Training Session Halted by User ===\n")

    def clear_runner_output(self):
        self.runner_output.config(state=tk.NORMAL)
        self.runner_output.delete(1.0, tk.END)
        self.runner_output.config(state=tk.DISABLED)
        log_message("RUNNER: Output cleared.")

    def log_output(self, text, tag=None):
        self.runner_output.config(state=tk.NORMAL)
        self.runner_output.insert(tk.END, text, tag)
        self.runner_output.see(tk.END)
        self.runner_output.config(state=tk.DISABLED)

    def append_runner_output(self, text):
        self.log_output(text)

    def _auto_run_evaluation(self, as_baseline: bool):
        """Run evaluation engine against the selected model for All suites and save baseline/eval reports.

        Note: Uses Ollama chat API under the hood; ensure Ollama is running and model is available.
        """
        # Determine selected model name from Model Selection Panel
        model_name = None
        if hasattr(self.training_tab_instance, 'model_selection_panel'):
            params = self.training_tab_instance.model_selection_panel.get_config_params()
            model_name = params.get("model_name")
        if not model_name:
            self.append_runner_output("No model selected for evaluation. Skipping.\n")
            return

        # Resolve tests directory
        from config import TRAINING_DATA_DIR
        test_suite_dir = TRAINING_DATA_DIR / 'Test'
        engine = EvaluationEngine(tests_dir=test_suite_dir)

        # Determine which suites to run. Prefer suites matching trained categories.
        suites_available = sorted([d.name for d in test_suite_dir.iterdir() if d.is_dir()]) if test_suite_dir.exists() else []
        suites_to_run = []

        # Attempt to read profile for strategy and eval prefs
        system_prompt_name = None
        tool_schema_name = None
        try:
            prof_var = getattr(self.training_tab_instance, 'selected_profile_var', None)
            prof_name = prof_var.get() if prof_var else ""
            prof_cfg = load_profile(prof_name) if prof_name else {}
            eval_prefs = prof_cfg.get("evaluation_preferences", {})
            suite_strategy = eval_prefs.get("suite_strategy", "trained_categories")
            # Preferences from profile, else from Runner toggles + right-side selection
            if eval_prefs.get("use_system_prompt") and eval_prefs.get("system_prompt"):
                system_prompt_name = eval_prefs.get("system_prompt")
            elif self.use_prompt_for_eval_var.get() and hasattr(self.training_tab_instance, 'prompt_selected_var'):
                system_prompt_name = self.training_tab_instance.prompt_selected_var.get() or None
            if eval_prefs.get("use_tool_schema") and eval_prefs.get("tool_schema"):
                tool_schema_name = eval_prefs.get("tool_schema")
            elif self.use_schema_for_eval_var.get() and hasattr(self.training_tab_instance, 'schema_selected_var'):
                tool_schema_name = self.training_tab_instance.schema_selected_var.get() or None
        except Exception:
            suite_strategy = "trained_categories"

        if suite_strategy == "trained_categories":
            selected = self.training_tab_instance.get_selected_scripts() if hasattr(self.training_tab_instance, 'get_selected_scripts') else {"scripts": [], "jsonl_files": []}
            categories_used = sorted(set([x['category'] for x in (selected.get('scripts', []) + selected.get('jsonl_files', []))]))
            suites_to_run = [c for c in categories_used if c in suites_available]
        elif suite_strategy == "all":
            suites_to_run = suites_available
        else:
            suites_to_run = suites_available

        if not suites_to_run:
            # Fallback to All aggregator if nothing matches
            suites_to_run = ["All"]

        # Execute evaluation
        aggregated = {"results": [], "per_skill": {}, "pass_rate_percent": "0%", "passed": 0, "failed": 0, "total_tests": 0}
        if suites_to_run == ["All"]:
            results = engine.run_benchmark(model_name, "All", system_prompt_name, tool_schema_name)
            if "error" in results:
                self.append_runner_output(f"Evaluation error: {results['error']}\n")
                return
            aggregated = results
        else:
            for suite in suites_to_run:
                r = engine.run_benchmark(model_name, suite, system_prompt_name, tool_schema_name)
                if "error" in r:
                    self.append_runner_output(f"Suite '{suite}' error: {r['error']}\n")
                    continue
                aggregated["results"].extend(r.get("results", []))
            # Recompute aggregates
            passed_count = sum(1 for r in aggregated["results"] if r.get("passed"))
            total = len(aggregated["results"])
            aggregated["passed"] = passed_count
            aggregated["failed"] = total - passed_count
            aggregated["total_tests"] = total
            aggregated["pass_rate_percent"] = f"{(passed_count/total*100) if total else 0.0:.2f}%"
            # Per-skill
            per_skill = {}
            for r in aggregated["results"]:
                s = r.get("skill") or "Unknown"
                bucket = per_skill.setdefault(s, {"passed": 0, "total": 0, "pass_rate_percent": "0.00%"})
                bucket["total"] += 1
                if r.get("passed"):
                    bucket["passed"] += 1
            for s, v in per_skill.items():
                rate = (v["passed"] / v["total"] * 100) if v["total"] else 0.0
                v["pass_rate_percent"] = f"{rate:.2f}%"
            aggregated["per_skill"] = per_skill

        if as_baseline:
            # Save canonical baseline
            path = save_baseline_report(model_name, aggregated)
            # Ensure index has at least one active baseline for this model
            try:
                meta = aggregated.get('metadata', {}) or {}
                idx = load_benchmarks_index() or {}
                clean = model_name.replace('/', '_').replace(':', '_')
                active = ((idx.get('models') or {}).get(clean) or {}).get('active')
                if not active:
                    update_model_baseline_index(model_name, path, meta, set_active=True)
            except Exception:
                pass
            self.append_runner_output("Baseline saved.\n")
            # Show a one-line confirmation with skills
            try:
                self._view_active_baseline_summary()
            except Exception:
                pass
        else:
            save_evaluation_report(model_name, aggregated)
            self.append_runner_output("Evaluation report saved.\n")

            # If baseline exists, compare and summarize
            baseline = load_baseline_report(model_name)
            if baseline:
                policy = get_regression_policy()
                threshold = float(policy.get("alert_drop_percent", 5.0)) if policy.get("enabled", True) else 5.0
                comparison = engine.compare_models(baseline, aggregated, regression_threshold=threshold, improvement_threshold=threshold)
                overall = comparison.get("overall", {})
                deltas = overall.get("delta", "+0.00%")
                self.append_runner_output(f"Comparison Overall Δ: {deltas}\n")
                regs = comparison.get("regressions", [])
                if regs:
                    skills = ", ".join([r.get("skill", "") for r in regs])
                    self.append_runner_output(f"Regressions (>{threshold:.1f}% drop): {skills}\n")
                    if policy.get("enabled", True) and policy.get("strict_block", False):
                        self.append_runner_output("STRICT POLICY: Regressions detected. Consider rollback or retraining.\n")
                imps = comparison.get("improvements", [])
                if imps:
                    skills = ", ".join([r.get("skill", "") for r in imps])
                    self.append_runner_output(f"Improvements (>{threshold:.1f}% gain): {skills}\n")

    def save_runner_defaults(self):
        # (Code remains the same)
        settings_file = DATA_DIR / "settings.json"
        all_settings = {}
        if settings_file.exists():
            try:
                with open(settings_file, 'r') as f:
                    all_settings = json.load(f)
            except (json.JSONDecodeError, IOError): pass
        runner_settings = {
            "max_time": self.max_time_var.get(), "max_runs": self.max_runs_var.get(),
            "run_delay": self.run_delay_var.get(), "save_checkpoints": self.save_checkpoints_var.get(),
            "checkpoint_interval": self.checkpoint_interval_var.get(), "early_stop": self.early_stop_var.get(),
            "early_stop_patience": self.early_stop_patience_var.get(), "use_mixed_precision": self.use_mixed_precision_var.get(),
            "gradient_accumulation": self.gradient_accumulation_var.get(), "warmup_steps": self.warmup_steps_var.get(),
            "max_cpu_threads": self.max_cpu_threads_var.get(), "max_ram_percent": self.max_ram_percent_var.get(),
            "auto_restart": self.auto_restart_var.get(),
            "enable_baseline_tests": self.enable_baseline_tests_var.get(),
            "enable_stat_saving": self.enable_stat_saving_var.get(), # New: Save stat saving setting
            # Core Training Parameters
            "num_epochs": self.num_epochs_var.get(),
            "batch_size": self.batch_size_var.get(),
            "learning_rate": self.learning_rate_var.get()
        }
        all_settings["runner_defaults"] = runner_settings
        try:
            with open(settings_file, 'w') as f:
                json.dump(all_settings, f, indent=2)
            self.log_output("✅ Runner default settings saved.\n", "system")
            log_message("RUNNER: Runner default settings saved.")
        except Exception as e:
            self.log_output(f"❌ Error saving runner defaults: {e}\n", "error")
            log_message(f"RUNNER ERROR: Could not save runner defaults: {e}")

    def load_runner_defaults(self, initial_load=False):
        # (Code remains the same)
        log_message("RUNNER: Loading runner defaults.")
        settings_file = DATA_DIR / "settings.json"
        if not settings_file.exists():
            if not initial_load: self.log_output("ℹ️ No settings file found. Using current values.\n", "system")
            return
        try:
            with open(settings_file, 'r') as f:
                all_settings = json.load(f)
            runner_settings = all_settings.get("runner_defaults")
            if not runner_settings:
                if not initial_load: self.log_output("ℹ️ No runner defaults found in settings. Using current values.\n", "system")
                return
            self.max_time_var.set(runner_settings.get("max_time", self.max_time_var.get()))
            self.max_runs_var.set(runner_settings.get("max_runs", self.max_runs_var.get()))
            self.run_delay_var.set(runner_settings.get("run_delay", self.run_delay_var.get()))
            self.save_checkpoints_var.set(runner_settings.get("save_checkpoints", self.save_checkpoints_var.get()))
            self.checkpoint_interval_var.set(runner_settings.get("checkpoint_interval", self.checkpoint_interval_var.get()))
            self.early_stop_var.set(runner_settings.get("early_stop", self.early_stop_var.get()))
            self.early_stop_patience_var.set(runner_settings.get("early_stop_patience", self.early_stop_patience_var.get()))
            self.use_mixed_precision_var.set(runner_settings.get("use_mixed_precision", self.use_mixed_precision_var.get()))
            self.gradient_accumulation_var.set(runner_settings.get("gradient_accumulation", self.gradient_accumulation_var.get()))
            self.warmup_steps_var.set(runner_settings.get("warmup_steps", self.warmup_steps_var.get()))
            self.max_cpu_threads_var.set(runner_settings.get("max_cpu_threads", self.max_cpu_threads_var.get()))
            self.max_ram_percent_var.set(runner_settings.get("max_ram_percent", self.max_ram_percent_var.get()))
            self.auto_restart_var.set(runner_settings.get("auto_restart", self.auto_restart_var.get()))
            self.enable_baseline_tests_var.set(runner_settings.get("enable_baseline_tests", self.enable_baseline_tests_var.get()))
            self.enable_stat_saving_var.set(runner_settings.get("enable_stat_saving", self.enable_stat_saving_var.get())) # New: Load stat saving setting
            # Core Training Parameters
            self.num_epochs_var.set(runner_settings.get("num_epochs", self.num_epochs_var.get()))
            self.batch_size_var.set(runner_settings.get("batch_size", self.batch_size_var.get()))
            self.learning_rate_var.set(runner_settings.get("learning_rate", self.learning_rate_var.get()))
            
            if not initial_load: self.log_output("✅ Runner default settings loaded.\n", "system")
            log_message("RUNNER: Successfully loaded runner defaults.")
        except Exception as e:
            if not initial_load: self.log_output(f"❌ Error loading runner defaults: {e}\n", "error")
            log_message(f"RUNNER ERROR: Could not load runner defaults: {e}")

    def _on_mousewheel(self, event):
        if event.num == 5 or event.delta < 0:
            self.controls_canvas.yview_scroll(1, "units")
        elif event.num == 4 or event.delta > 0:
            self.controls_canvas.yview_scroll(-1, "units")

    def _bind_mousewheel(self, event):
        self.parent.bind_all("<MouseWheel>", self._on_mousewheel)
        self.parent.bind_all("<Button-4>", self._on_mousewheel)
        self.parent.bind_all("<Button-5>", self._on_mousewheel)

    def _unbind_mousewheel(self, event):
        self.parent.unbind_all("<MouseWheel>")
        self.parent.unbind_all("<Button-4>")
        self.parent.unbind_all("<Button-5>")
