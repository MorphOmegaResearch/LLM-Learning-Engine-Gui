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
import logger_util

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from tabs.base_tab import BaseTab
from config import get_category_info, get_training_data_files, DATA_DIR, get_ollama_models, get_all_available_models

# Import panel modules
from .runner_panel import RunnerPanel
from .category_manager_panel import CategoryManagerPanel
from .config_panel import ConfigPanel
from .profiles_panel import ProfilesPanel
from .summary_panel import SummaryPanel


class TrainingTab(BaseTab):
    """Training configuration and dataset selection tab - Main coordinator"""

    def __init__(self, parent, root, style):
        super().__init__(parent, root, style)

        self._is_updating_selection = False
        # State variables
        self.category_vars = {}
        self.subcategory_vars = {}
        self.ollama_models = get_all_available_models()  # Now includes local PyTorch models

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
            "training_runs": tk.IntVar(value=3),
            "batch_size": tk.IntVar(value=2),
            "learning_strength": tk.StringVar(value="2e-4"),
            "base_model": tk.StringVar(value=default_model)
        }

        self.profile_name_var = tk.StringVar(value="")
        self.selected_profile_var = tk.StringVar(value="")
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
            refresh_callback=self.refresh_all_panels
        )
        self.category_manager_panel.create_ui()

        # Configuration Tab
        config_frame = ttk.Frame(self.training_notebook)
        self.training_notebook.add(config_frame, text="Configuration")
        self.config_panel = ConfigPanel(
            config_frame,
            self.style,
            self.config_vars,
            self.ollama_models,
            self.update_preview,
            training_tab_instance=self
        )
        self.config_panel.create_ui()

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
            self.config_vars,
            self.update_preview,
            self.update_profile_combobox
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
            self.config_vars,
            self.selected_profile_var
        )
        self.summary_panel.create_ui()

        # Right side: Training menu
        self.create_training_menu(self.parent)

        # Update profile list
        self.update_profile_combobox()

        # Initialize runner panel's model display now that config_panel exists
        if hasattr(self, 'runner_panel'):
            self.runner_panel.update_training_model_display()

    def create_training_menu(self, parent):
        """Create category/script selector menu on the right"""
        menu_frame = ttk.Frame(parent, style='Category.TFrame')
        menu_frame.grid(row=0, column=1, sticky=tk.NSEW, padx=10, pady=10)
        menu_frame.columnconfigure(0, weight=1)
        menu_frame.rowconfigure(2, weight=1)

        # Header with title and counter
        header_frame = ttk.Frame(menu_frame, style='Category.TFrame')
        header_frame.grid(row=0, column=0, pady=5, sticky=tk.EW, padx=5)
        header_frame.columnconfigure(1, weight=1)

        ttk.Label(header_frame, text="📋 Training Scripts",
                 font=("Arial", 11, "bold"), style='CategoryPanel.TLabel').pack(side=tk.LEFT)

        self.selection_counter_label = ttk.Label(header_frame, text="", style='CategoryPanel.TLabel')
        self.selection_counter_label.pack(side=tk.LEFT, padx=5)

        # Select/Deselect All buttons
        buttons_frame = ttk.Frame(menu_frame)
        buttons_frame.grid(row=1, column=0, pady=5, padx=5, sticky=tk.EW)
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


        # Scrollable category tree
        tree_canvas = tk.Canvas(menu_frame, bg="#2b2b2b", highlightthickness=0)
        tree_scrollbar = ttk.Scrollbar(menu_frame, orient="vertical", command=tree_canvas.yview)
        self.category_tree_frame = ttk.Frame(tree_canvas)

        self.category_tree_frame.bind(
            "<Configure>",
            lambda e: tree_canvas.configure(scrollregion=tree_canvas.bbox("all"))
        )

        tree_canvas_window = tree_canvas.create_window((0, 0), window=self.category_tree_frame, anchor="nw")
        tree_canvas.configure(yscrollcommand=tree_scrollbar.set)

        tree_canvas.grid(row=2, column=0, sticky=tk.NSEW, pady=5)
        tree_scrollbar.grid(row=2, column=1, sticky=tk.NS)

        tree_canvas.bind("<Configure>", lambda e: tree_canvas.itemconfig(tree_canvas_window, width=e.width))

        # Store script and JSONL variables
        self.script_vars = {}  # {category: {script_name: BooleanVar}}
        self.jsonl_vars = {}   # {category: {jsonl_name: BooleanVar}}
        self.category_expanded = {}  # {category: BooleanVar}
        self.script_expanded = {}    # {category: {script: BooleanVar}}

        # Populate category tree
        self.populate_category_tree()

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

                script_cb = ttk.Checkbutton(
                    script_header,
                    text=f"🐍 {script_name}",
                    variable=var,
                    style='Category.TCheckbutton'
                )
                script_cb.pack(side=tk.LEFT)

                # JSONL files container (hidden by default)
                jsonl_container = ttk.Frame(script_frame)

                # Store script frame references
                key = f"{category_name}::{script_name}"
                self.category_tree_frame.script_frames[key] = {
                    'container': jsonl_container,
                    'expand_button': script_expand_btn
                }

            # Find all .jsonl files in category
            jsonl_files = list(category_dir.glob("*.jsonl"))

            for jsonl_file in sorted(jsonl_files):
                jsonl_name = jsonl_file.name
                var = tk.BooleanVar(value=True)  # Default: all selected
                var.trace_add('write', self.update_selection_state) # Add trace
                self.jsonl_vars[category_name][jsonl_name] = var

                # Add to appropriate script container or category level
                # For now, add to category_content as standalone items
                jsonl_cb = ttk.Checkbutton(
                    category_content,
                    text=f"  📄 {jsonl_name}",
                    variable=var,
                    style='Category.TCheckbutton'
                )
                jsonl_cb.pack(fill=tk.X, padx=(25, 5), pady=1, anchor=tk.W)
        
        self.update_selection_state() # Set initial state

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

    def on_tab_changed(self, event=None):
        """Called when user switches between tabs."""
        # Update Runner panel's model display when switching to Runner tab
        current_tab = self.training_notebook.select()
        tab_name = self.training_notebook.tab(current_tab, "text")

        if tab_name == "Runner" and hasattr(self, 'runner_panel'):
            self.runner_panel.update_training_model_display()

    def refresh_training_tab(self):
        """Refresh the entire training tab - reloads models, categories, etc."""
        # Refresh available models
        self.ollama_models = get_all_available_models()

        # Refresh config panel dropdown
        if hasattr(self, 'config_panel'):
            # Update the combobox values
            for widget in self.config_panel.parent.winfo_children():
                for child in widget.winfo_children():
                    if isinstance(child, ttk.Frame):
                        for subchild in child.winfo_children():
                            if isinstance(subchild, ttk.Combobox):
                                subchild['values'] = self.ollama_models

        # Refresh category tree
        if hasattr(self, 'populate_category_tree'):
            self.populate_category_tree()

        # Refresh all panels
        self.refresh_all_panels()

        # Update runner model display
        if hasattr(self, 'runner_panel'):
            self.runner_panel.update_training_model_display()

        print("✓ Training tab refreshed")

    def refresh_all_panels(self):
        """Refresh all panels that need category updates"""
        if hasattr(self, 'category_manager_panel'):
            self.category_manager_panel.refresh()
        self.category_info = get_category_info()
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
        print("Performing post-training actions...")
        # Example: Refresh the models tab if it exists
        # This assumes the main GUI has a way to access other tabs
        # For now, we'll just print a message.
        messagebox.showinfo("Training Complete", "Training process has finished. Check the Models tab for updates.")
