# [SYSTEM: GUI | VERSION: 1.9f | STATUS: ACTIVE]
"""
Summary Panel - Training summary preview
"""

import tkinter as tk
from tkinter import ttk, scrolledtext
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from config import get_training_data_files, get_model_skills # New import


import logger_util # Add import for logging

class SummaryPanel:
    """Panel for displaying training summary"""

    def __init__(self, parent, style, category_vars, subcategory_vars, model_selection_panel, runner_panel, selected_profile_var):
        self.parent = parent
        self.style = style
        self.category_vars = category_vars
        self.subcategory_vars = subcategory_vars
        self.model_selection_panel = model_selection_panel
        self.runner_panel = runner_panel
        self.selected_profile_var = selected_profile_var

    def create_ui(self):
        """Create the summary panel UI"""
        # Summary text - full tab
        self.summary_text = scrolledtext.ScrolledText(
            self.parent,
            font=("Courier", 10),
            wrap=tk.WORD,
            state=tk.DISABLED,
            relief='flat',
            borderwidth=0,
            highlightthickness=0
        )
        self.summary_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Configure styling
        self.summary_text.tag_configure('default', background='#1e1e1e', foreground='#61dafb')
        self.summary_text.config(background='#1e1e1e', foreground='#61dafb')

        self.update_preview()

    def update_preview(self, event=None):
        logger_util.log_message("SUMMARY: Updating summary preview.")
        # Get selected files
        selected_categories = [cat for cat, var in self.category_vars.items() if var.get()]

        selected_subcats = {}
        for (cat, subcat), var in self.subcategory_vars.items():
            if var.get():
                if cat not in selected_subcats:
                    selected_subcats[cat] = []
                selected_subcats[cat].append(subcat)

        files = get_training_data_files(selected_categories, selected_subcats if selected_subcats else None)

        total_examples = sum(self.count_file(f) for f in files)
        
        # Get parameters from runner_panel
        training_runs = self.runner_panel.num_epochs_var.get()
        batch_size = self.runner_panel.batch_size_var.get()
        learning_strength = self.runner_panel.learning_rate_var.get()
        
        # Get base model from model_selection_panel
        config_params = self.model_selection_panel.get_config_params()
        base_model = config_params.get("model_name", "") if isinstance(config_params, dict) else ""

        # Fetch skills for the base model
        model_skills = get_model_skills(base_model)

        # Build summary text
        summary = []
        summary.append("=" * 40)
        summary.append("  TRAINING SUMMARY")
        summary.append("=" * 40)
        summary.append("")
        summary.append(f"📁 Categories: {len(selected_categories)}")
        for cat in sorted(selected_categories):
            summary.append(f"   ✓ {cat.replace('_', ' ')}")
            if cat in selected_subcats:
                for subcat in sorted(selected_subcats[cat]):
                    summary.append(f"      • {subcat.replace('_', ' ').title()}")
        summary.append("")
        summary.append(f"📊 Training Data:")
        summary.append(f"   Files: {len(files)}")
        summary.append(f"   Examples: {total_examples}")
        summary.append("")
        summary.append(f"⚙️  Configuration:")
        if self.selected_profile_var.get():
            summary.append(f"   Profile: {self.selected_profile_var.get()}")
        summary.append(f"   Training Runs: {training_runs}")
        summary.append(f"   Batch Size: {batch_size}")
        summary.append(f"   Learning Strength: {learning_strength}")
        summary.append(f"   Base Model: {base_model}")
        # Prompts/Schemas from Runner toggles and right-side selections
        try:
            use_prompt = getattr(self.runner_panel, 'use_prompt_for_eval_var', None)
            use_schema = getattr(self.runner_panel, 'use_schema_for_eval_var', None)
            prompt_sel = getattr(self.model_selection_panel, 'training_tab_instance', None).prompt_selected_var.get() if hasattr(self.model_selection_panel, 'training_tab_instance') else ""
            schema_sel = getattr(self.model_selection_panel, 'training_tab_instance', None).schema_selected_var.get() if hasattr(self.model_selection_panel, 'training_tab_instance') else ""
            if use_prompt is not None:
                summary.append(f"   Use Prompt: {'On' if use_prompt.get() else 'Off'}{(' (' + prompt_sel + ')') if use_prompt.get() and prompt_sel else ''}")
            if use_schema is not None:
                summary.append(f"   Use Schema: {'On' if use_schema.get() else 'Off'}{(' (' + schema_sel + ')') if use_schema.get() and schema_sel else ''}")
        except Exception:
            pass
        
        # Add skills summary
        if model_skills:
            summary.append("")
            summary.append("✨ Model Skills:")
            for skill_name, skill_data in sorted(model_skills.items()):
                status = skill_data.get("status", "Unknown")
                icon = "✅" if status == "Verified" else "⚠️" if status == "Partial" else "❌"
                summary.append(f"   {icon} {skill_name}: {status}")

        summary.append("")
        summary.append(f"⏱️  Estimated Time:")
        est_time = total_examples * training_runs * 0.5 / 60  # 0.5 sec per example
        summary.append(f"   ~{est_time:.1f} minutes")
        summary.append("")
        summary.append("=" * 40)

        # Update text widget
        self.summary_text.config(state=tk.NORMAL)
        self.summary_text.delete(1.0, tk.END)
        self.summary_text.insert(1.0, "\n".join(summary))
        self.summary_text.config(state=tk.DISABLED)

    def count_file(self, file_path):
        """Count examples in file"""
        try:
            with open(file_path) as f:
                return sum(1 for _ in f)
        except:
            return 0
