"""
Config Panel - Training configuration parameters
"""

import tkinter as tk
from tkinter import ttk


class ConfigPanel:
    """Panel for training configuration parameters"""

    def __init__(self, parent, style, config_vars, ollama_models, update_preview_callback, training_tab_instance=None):
        self.parent = parent
        self.style = style
        self.config_vars = config_vars
        self.ollama_models = ollama_models
        self.update_preview_callback = update_preview_callback
        self.training_tab_instance = training_tab_instance

    def create_ui(self):
        """Create the configuration panel UI"""
        section = ttk.LabelFrame(self.parent, text="⚙️ Training Parameters", style='TLabelframe')
        section.pack(fill=tk.X, pady=10, padx=10)

        # Training Runs
        runs_frame = ttk.Frame(section)
        runs_frame.pack(fill=tk.X, padx=10, pady=8)

        ttk.Label(runs_frame, text="Training Runs:", style='Config.TLabel', width=20).pack(side=tk.LEFT, padx=(0, 5))
        runs_spin = ttk.Spinbox(
            runs_frame,
            from_=1,
            to=10,
            textvariable=self.config_vars["training_runs"],
            width=10,
            font=("Arial", 10),
            command=self.update_preview_callback
        )
        runs_spin.pack(side=tk.LEFT, padx=(0, 10))
        ttk.Label(runs_frame, text="(How many times to read all examples)",
                 font=("Arial", 8), foreground='#888888').pack(side=tk.LEFT)

        # Batch Size
        batch_frame = ttk.Frame(section)
        batch_frame.pack(fill=tk.X, padx=10, pady=8)

        ttk.Label(batch_frame, text="Batch Size:", style='Config.TLabel', width=20).pack(side=tk.LEFT, padx=(0, 5))
        batch_spin = ttk.Spinbox(
            batch_frame,
            from_=1,
            to=16,
            textvariable=self.config_vars["batch_size"],
            width=10,
            font=("Arial", 10),
            command=self.update_preview_callback
        )
        batch_spin.pack(side=tk.LEFT, padx=(0, 10))
        ttk.Label(batch_frame, text="(Examples per update - higher = faster)",
                 font=("Arial", 8), foreground='#888888').pack(side=tk.LEFT)

        # Learning Strength
        lr_frame = ttk.Frame(section)
        lr_frame.pack(fill=tk.X, padx=10, pady=8)

        ttk.Label(lr_frame, text="Learning Strength:", style='Config.TLabel', width=20).pack(side=tk.LEFT, padx=(0, 5))
        strength_entry = ttk.Entry(
            lr_frame,
            textvariable=self.config_vars["learning_strength"],
            width=12,
            font=("Arial", 10)
        )
        strength_entry.pack(side=tk.LEFT, padx=(0, 10))
        strength_entry.bind("<KeyRelease>", lambda e: self.update_preview_callback())
        ttk.Label(lr_frame, text="(How much to learn per mistake - 2e-4 is good)",
                 font=("Arial", 8), foreground='#888888').pack(side=tk.LEFT)

        # Base Model
        model_frame = ttk.Frame(section)
        model_frame.pack(fill=tk.X, padx=10, pady=8)

        ttk.Label(model_frame, text="Base Model:", style='Config.TLabel', width=20).pack(side=tk.LEFT, padx=(0, 5))
        model_combobox = ttk.Combobox(
            model_frame,
            textvariable=self.config_vars["base_model"],
            values=self.ollama_models,
            state="normal",  # Allow typing custom paths
            width=50,
            font=("Arial", 10)
        )
        model_combobox.pack(side=tk.LEFT, padx=(0, 10))
        model_combobox.bind("<<ComboboxSelected>>", lambda e: self.on_model_selected())

        # Model tooltip
        ttk.Label(section, text="Select a LOCAL model for training, or enter a HuggingFace model name/path",
                 font=("Arial", 8), foreground='#888888').pack(padx=10, pady=(0, 10))

    def on_model_selected(self):
        """Called when user selects a model from the dropdown."""
        # Update the preview
        self.update_preview_callback()

        # Update Runner panel's model display if available
        if self.training_tab_instance and hasattr(self.training_tab_instance, 'runner_panel'):
            self.training_tab_instance.runner_panel.update_training_model_display()

    def get_config_params(self):
        """Returns a dictionary of the current configuration parameters."""
        # Extract actual model path from dropdown selection
        raw_model = self.config_vars["base_model"].get()

        # If format is "LOCAL: name (path)", extract the path
        if raw_model.startswith("LOCAL: ") and "(" in raw_model:
            model_name = raw_model.split("(")[1].rstrip(")")
        # If format is "OLLAMA: name (...)", skip it (not trainable)
        elif raw_model.startswith("OLLAMA: "):
            model_name = raw_model  # Will show error later
        else:
            # Direct path or HuggingFace name
            model_name = raw_model

        return {
            "num_epochs": self.config_vars["training_runs"].get(),
            "batch_size": self.config_vars["batch_size"].get(),
            "learning_rate": float(self.config_vars["learning_strength"].get()),
            "model_name": model_name,
            # Add other parameters as needed by the training engine
            "max_seq_length": 2048, # Default value, can be made configurable
            "lora_r": 16,           # Default value, can be made configurable
            "lora_alpha": 16        # Default value, can be made configurable
        }
