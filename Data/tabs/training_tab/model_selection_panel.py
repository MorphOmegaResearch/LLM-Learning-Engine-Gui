# [SYSTEM: GUI | VERSION: 1.9f | STATUS: ACTIVE]
"""
Config Panel - Training configuration parameters
"""

import tkinter as tk
from tkinter import ttk


from tkinter import scrolledtext # New import for model info display
import logger_util # New import for logging
import tkinter.messagebox as messagebox
from config import get_model_skills # New import
from config import get_model_behavior_profile

class ModelSelectionPanel: # Renamed class
    """Panel for model selection and information display"""

    def __init__(self, parent, style, ollama_models, update_preview_callback, training_tab_instance):
        self.parent = parent
        self.style = style
        self.ollama_models = ollama_models
        self.update_preview_callback = update_preview_callback
        self.training_tab_instance = training_tab_instance
        
        self.base_model_var = tk.StringVar() # New tk.StringVar for selected model
        self.model_info_display = None # Will be scrolledtext widget

    def create_ui(self):
        """Create the model selection and information panel UI"""
        self.parent.columnconfigure(0, weight=1)
        self.parent.rowconfigure(1, weight=1) # Allow model info display to expand

        # Model Selection Section
        selection_section = ttk.LabelFrame(self.parent, text="🧠 Model Selection", style='TLabelframe')
        selection_section.grid(row=0, column=0, sticky=tk.EW, padx=10, pady=10)
        selection_section.columnconfigure(1, weight=1) # Allow combobox to expand

        ttk.Label(selection_section, text="Base Model:", style='Config.TLabel').grid(row=0, column=0, sticky=tk.W, padx=10, pady=5)
        
        model_combo = ttk.Combobox(selection_section, textvariable=self.base_model_var, values=self.ollama_models, state="readonly", width=40)
        model_combo.grid(row=0, column=1, sticky=tk.EW, padx=10, pady=5)
        model_combo.bind("<<ComboboxSelected>>", self.display_model_info) # Bind to new display method

        ttk.Button(selection_section, text="Send To Training", command=self.send_model_to_training, style='Action.TButton').grid(row=0, column=2, sticky=tk.E, padx=5)

        # Model Information Display
        info_section = ttk.LabelFrame(self.parent, text="📊 Model Information", style='TLabelframe')
        info_section.grid(row=1, column=0, sticky=tk.NSEW, padx=10, pady=10)
        info_section.columnconfigure(0, weight=1)
        info_section.rowconfigure(0, weight=1)

        self.model_info_display = scrolledtext.ScrolledText(
            info_section, wrap=tk.WORD, state=tk.DISABLED, font=("Courier", 9),
            bg="#1e1e1e", fg="#d4d4d4", relief='flat', padx=5, pady=5
        )
        self.model_info_display.grid(row=0, column=0, sticky='nsew')

        # Initial display of model info
        self.base_model_var.set(self.ollama_models[0] if self.ollama_models else "")
        self.display_model_info()

    def refresh_model_list(self, models: list):
        """Refresh the base model dropdown with a new list of models, preserving selection if possible."""
        try:
            current = self.base_model_var.get()
            # Find combobox
            combo = None
            for child in self.parent.winfo_children():
                # Locate the combobox by type
                if isinstance(child, ttk.LabelFrame) and child.cget('text').startswith('🧠'):
                    for sub in child.winfo_children():
                        if isinstance(sub, ttk.Combobox):
                            combo = sub
                            break
            if combo is None:
                return
            combo['values'] = models
            if current in models:
                combo.set(current)
            elif models:
                combo.set(models[0])
                self.base_model_var.set(models[0])
        except Exception:
            pass

    def on_model_selected(self):
        """Called when user selects a model from the dropdown."""
        # Update the preview
        self.update_preview_callback()

        # Update Runner panel's model display if available
        if self.training_tab_instance and hasattr(self.training_tab_instance, 'runner_panel'):
            self.training_tab_instance.runner_panel.update_training_model_display()

    def display_model_info(self, event=None):
        """Fetch and display detailed information similar to Models tab overview for trainable models."""
        from pathlib import Path
        from config import get_all_trained_models, load_training_stats
        import json as _json

        selected_model_name = self.base_model_var.get()
        logger_util.log_message(f"MODEL_SELECT: Displaying info for model: {selected_model_name}")

        # Find model metadata
        model_meta = None
        try:
            for m in get_all_trained_models():
                if m.get('name') == selected_model_name and m.get('type') in ('pytorch', 'trained'):
                    model_meta = m
                    break
        except Exception:
            model_meta = None

        lines = []
        lines.append(f"Name: {selected_model_name}")
        if model_meta:
            lines.append(f"Type: {'Trained' if model_meta.get('type')=='trained' else 'Base (PyTorch)'}")
            if model_meta.get('path'):
                lines.append(f"Path: {model_meta['path']}")
            if model_meta.get('size'):
                lines.append(f"Size: {model_meta['size']}")
            lines.append("")

            # Try to read config.json for arch details
            try:
                cfg_path = Path(model_meta['path']) / 'config.json'
                if cfg_path.exists():
                    with open(cfg_path, 'r') as f:
                        cfg = _json.load(f)
                    if cfg.get('model_type'):
                        lines.append(f"Architecture: {cfg['model_type']}")
                    # Core dims
                    if cfg.get('num_hidden_layers') is not None:
                        lines.append(f"Layers: {cfg['num_hidden_layers']}")
                    if cfg.get('hidden_size') is not None:
                        lines.append(f"Hidden Size: {cfg['hidden_size']}")
                    if cfg.get('num_attention_heads') is not None:
                        lines.append(f"Attention Heads: {cfg['num_attention_heads']}")
                    if cfg.get('intermediate_size') is not None:
                        lines.append(f"Intermediate Size: {cfg['intermediate_size']}")
                    if cfg.get('max_position_embeddings') is not None:
                        lines.append(f"Max Seq Length: {cfg['max_position_embeddings']}")
                    if cfg.get('vocab_size') is not None:
                        lines.append(f"Vocab Size: {cfg['vocab_size']:,}")
                    lines.append("")
            except Exception:
                pass

            # Training stats summary
            try:
                stats = load_training_stats(selected_model_name)
                runs = stats.get('training_runs', []) if isinstance(stats, dict) else []
                if runs:
                    last = runs[-1]
                    lines.append("📈 Latest Training Run:")
                    if last.get('epochs') is not None:
                        lines.append(f"  Epochs: {last.get('epochs')}")
                    if last.get('batch_size') is not None:
                        lines.append(f"  Batch Size: {last.get('batch_size')}")
                    if 'training_loss' in last:
                        try:
                            lines.append(f"  Training Loss: {float(last['training_loss']):.4f}")
                        except Exception:
                            lines.append(f"  Training Loss: {last['training_loss']}")
                    if 'train_runtime' in last:
                        try:
                            lines.append(f"  Runtime: {float(last['train_runtime']):.2f}s")
                        except Exception:
                            lines.append(f"  Runtime: {last['train_runtime']}")
                    if last.get('category'):
                        lines.append(f"  Category: {last['category']}")
                    lines.append("")
                else:
                    lines.append("📈 Training Stats: Unverified (no runs)")
                    lines.append("")
            except Exception:
                lines.append("📈 Training Stats: Unverified (failed to load)")
                lines.append("")

        # Skills summary
        try:
            from config import get_model_skills
            skills = get_model_skills(selected_model_name) or {}
            # Detect meaningful skills vs placeholder
            real_skills = {k: v for k, v in skills.items() if k != 'Overall Status'}
            lines.append("✨ Skills:")
            if real_skills:
                for skill_name, skill_data in sorted(real_skills.items()):
                    status = skill_data.get('status', 'Unknown')
                    icon = '✅' if status == 'Verified' else '⚠️' if status == 'Partial' else '❌'
                    details = skill_data.get('details', '')
                    lines.append(f"  {icon} {skill_name}: {status}{(' — ' + details) if details else ''}")
            else:
                lines.append("  Unverified")
        except Exception:
            lines.append("✨ Skills: Unverified (failed to load)")

        # Behavior profile summary
        try:
            prof = get_model_behavior_profile(selected_model_name) or {}
            if prof:
                lines.append("")
                lines.append("🧭 Behavior Profile:")
                if prof.get('overall'):
                    lines.append(f"  Overall: {prof.get('overall')}  Suite: {prof.get('suite')}")
                # Top tools (up to 3)
                pt = prof.get('per_tool') or {}
                if pt:
                    top = sorted(pt.items(), key=lambda kv: (kv[1].get('passed',0), kv[1].get('total',0)), reverse=True)[:3]
                    tops = [f"{k} {v.get('pass_rate_percent','')}" for k,v in top]
                    lines.append("  Top tools: " + ", ".join(tops))
                # Tags brief
                # Tags summary: always show all default tags with 0% fallback
                tagm = prof.get('per_tag') or {}
                all_tags = ["think_time", "adversarial", "paraphrasing", "workflows"]
                tags_s = ", ".join([f"{t}:{(tagm.get(t) or {}).get('pass_rate_percent','0.00%')}" for t in all_tags])
                lines.append(f"  Tags: {tags_s}")
        except Exception:
            pass

        info_text = "\n".join(lines) + "\n"
        self.model_info_display.config(state=tk.NORMAL)
        self.model_info_display.delete(1.0, tk.END)
        self.model_info_display.insert(tk.END, info_text)
        self.model_info_display.config(state=tk.DISABLED)

    def send_model_to_training(self):
        """Sets the selected model as the base model for training and updates the Runner display."""
        selected_model = self.base_model_var.get()
        if not selected_model:
            messagebox.showwarning("No Model Selected", "Please select a model to send to training.")
            return

        self.training_tab_instance.config_vars["base_model"].set(selected_model)
        self.training_tab_instance.runner_panel.update_training_model_display()
        logger_util.log_message(f"MODEL_SELECT: Model '{selected_model}' sent to training.")
        messagebox.showinfo("Model Set", f"Model '{selected_model}' has been set for training.")

    def get_config_params(self):
        """Get current configuration parameters"""
        return {
            "model_name": self.base_model_var.get() # Use the local base_model_var
        }

    def set_base_model(self, model_name: str):
        """Programmatically set the base model and refresh dependent displays."""
        try:
            if model_name:
                self.base_model_var.set(model_name)
                # Refresh info block
                self.display_model_info()
                # Update Runner panel label if available
                if getattr(self, 'training_tab_instance', None) and hasattr(self.training_tab_instance, 'runner_panel'):
                    self.training_tab_instance.runner_panel.update_training_model_display()
        except Exception as e:
            logger_util.log_message(f"MODEL_SELECT: set_base_model error: {e}")
