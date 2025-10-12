"""
Training Tab - Dataset selection and training configuration
Isolated module for training-related functionality
"""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import json
import subprocess
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from tabs.base_tab import BaseTab
from config import (
    get_category_info,
    get_training_data_files,
    DATA_DIR,
    save_profile,
    load_profile,
    list_profiles,
    create_category_folder,
    create_subcategory_file,
    get_ollama_models
)


class TrainingTab(BaseTab):
    """Training configuration and dataset selection tab"""

    def __init__(self, parent, root, style):
        super().__init__(parent, root, style)

        # State variables
        self.category_vars = {}
        self.subcategory_vars = {}
        self.ollama_models = get_ollama_models()

        default_model = "unsloth/Qwen2.5-Coder-1.5B-Instruct"
        if self.ollama_models and default_model not in self.ollama_models:
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

        # UI variables
        self.new_category_name_var = tk.StringVar()
        self.new_subcategory_name_var = tk.StringVar()
        self.parent_category_var = tk.StringVar()

        # Runner variables
        self.selected_script_var = tk.StringVar()
        self.auto_restart_var = tk.BooleanVar(value=False)
        self.run_delay_var = tk.IntVar(value=0)
        self.max_runs_var = tk.IntVar(value=1)
        self.current_run_count = 0
        self.script_running = False

        # Category manager variables
        self.selected_category_for_edit = tk.StringVar()
        self.category_script_content = tk.StringVar()

    def create_ui(self):
        """Create the training tab UI with side menu and sub-tabs"""
        self.parent.columnconfigure(0, weight=1)
        self.parent.columnconfigure(1, weight=0)
        self.parent.rowconfigure(0, weight=1)

        # Left side: Training content with sub-tabs
        training_content_frame = ttk.Frame(self.parent, style='Category.TFrame')
        training_content_frame.grid(row=0, column=0, sticky=tk.NSEW, padx=10, pady=10)
        training_content_frame.columnconfigure(0, weight=1)
        training_content_frame.rowconfigure(0, weight=1)

        ttk.Label(training_content_frame, text="⚙️ Training",
                 font=("Arial", 14, "bold"), style='CategoryPanel.TLabel').pack(pady=5)

        # Sub-tabs notebook
        self.training_notebook = ttk.Notebook(training_content_frame)
        self.training_notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Training Runner Tab (First - for running scripts)
        self.runner_tab_frame = ttk.Frame(self.training_notebook)
        self.training_notebook.add(self.runner_tab_frame, text="Runner")
        self.create_runner_panel(self.runner_tab_frame)

        # Category Manager Tab
        self.category_manager_tab_frame = ttk.Frame(self.training_notebook)
        self.training_notebook.add(self.category_manager_tab_frame, text="Categories")
        self.create_category_manager_panel(self.category_manager_tab_frame)

        # Dataset Selection Tab
        self.dataset_tab_frame = ttk.Frame(self.training_notebook)
        self.training_notebook.add(self.dataset_tab_frame, text="Dataset")
        self.create_category_panel(self.dataset_tab_frame)

        # Configuration Tab
        self.config_tab_frame = ttk.Frame(self.training_notebook)
        self.training_notebook.add(self.config_tab_frame, text="Configuration")
        self.create_config_panel(self.config_tab_frame)

        # Profiles Tab
        self.profiles_tab_frame = ttk.Frame(self.training_notebook)
        self.training_notebook.add(self.profiles_tab_frame, text="Profiles")
        self.create_profiles_panel(self.profiles_tab_frame)

        # Summary Tab
        self.summary_tab_frame = ttk.Frame(self.training_notebook)
        self.training_notebook.add(self.summary_tab_frame, text="Summary")
        self.create_preview_panel(self.summary_tab_frame)

        # Right side: Training menu
        self.create_training_menu(self.parent)

        # Update profile list
        self.update_profile_combobox()


    def create_training_menu(self, parent):
        """Create training quick access menu on the right"""
        menu_frame = ttk.Frame(parent, style='Category.TFrame')
        menu_frame.grid(row=0, column=1, sticky=tk.NSEW, padx=10, pady=10)
        menu_frame.columnconfigure(0, weight=1)
        menu_frame.rowconfigure(1, weight=1)

        ttk.Label(menu_frame, text="📋 Quick Access",
                 font=("Arial", 11, "bold"), style='CategoryPanel.TLabel').grid(
            row=0, column=0, pady=5, sticky=tk.W, padx=5
        )

        # Scrollable menu
        menu_canvas = tk.Canvas(menu_frame, bg="#2b2b2b", highlightthickness=0)
        menu_scrollbar = ttk.Scrollbar(menu_frame, orient="vertical", command=menu_canvas.yview)
        menu_buttons_frame = ttk.Frame(menu_canvas)

        menu_buttons_frame.bind(
            "<Configure>",
            lambda e: menu_canvas.configure(scrollregion=menu_canvas.bbox("all"))
        )

        menu_canvas_window_id = menu_canvas.create_window((0, 0), window=menu_buttons_frame, anchor="nw")
        menu_canvas.configure(yscrollcommand=menu_scrollbar.set)

        menu_canvas.grid(row=1, column=0, sticky=tk.NSEW)
        menu_scrollbar.grid(row=1, column=1, sticky=tk.NS)

        menu_canvas.bind("<Configure>", lambda e: menu_canvas.itemconfig(menu_canvas_window_id, width=e.width))

        # Menu buttons
        menu_items = [
            ("Runner", 0, "▶️"),
            ("Categories", 1, "📂"),
            ("Dataset", 2, "📁"),
            ("Configuration", 3, "⚙️"),
            ("Profiles", 4, "💾"),
            ("Summary", 5, "📊"),
        ]

        for label, tab_index, icon in menu_items:
            btn = ttk.Button(
                menu_buttons_frame,
                text=f"{icon} {label}",
                command=lambda idx=tab_index: self.training_notebook.select(idx),
                style='Select.TButton'
            )
            btn.pack(fill=tk.X, pady=2, padx=5)

        # Action buttons
        ttk.Separator(menu_frame, orient=tk.HORIZONTAL).grid(row=2, column=0, columnspan=2, sticky=tk.EW, pady=10)

        # Select/Deselect All buttons
        ttk.Button(
            menu_frame,
            text="☑️ Select All",
            command=self.select_all,
            style='Select.TButton'
        ).grid(row=3, column=0, pady=2, padx=5, sticky=tk.EW)

        ttk.Button(
            menu_frame,
            text="☐ Deselect All",
            command=self.deselect_all,
            style='Select.TButton'
        ).grid(row=4, column=0, pady=2, padx=5, sticky=tk.EW)

        # Start Training button
        ttk.Button(
            menu_frame,
            text="🚀 Start Training",
            command=self.start_training,
            style='Action.TButton'
        ).grid(row=5, column=0, columnspan=2, pady=10, padx=5, sticky=tk.EW)

    def create_runner_panel(self, parent):
        """Create training script runner panel with output display and controls"""
        parent.columnconfigure(0, weight=1)
        parent.columnconfigure(1, weight=0)
        parent.rowconfigure(0, weight=1)

        # Left side: Script output display
        output_frame = ttk.Frame(parent, style='Category.TFrame')
        output_frame.grid(row=0, column=0, sticky=tk.NSEW, padx=10, pady=10)

        ttk.Label(output_frame, text="📺 Training Output",
                 font=("Arial", 12, "bold"), style='CategoryPanel.TLabel').pack(pady=5)

        # Output display
        self.runner_output = scrolledtext.ScrolledText(
            output_frame,
            font=("Courier", 9),
            wrap=tk.WORD,
            state=tk.DISABLED,
            relief='flat',
            borderwidth=0,
            highlightthickness=0,
            bg='#1e1e1e',
            fg='#00ff00'
        )
        self.runner_output.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Right side: Runner controls
        controls_frame = ttk.Frame(parent, style='Category.TFrame')
        controls_frame.grid(row=0, column=1, sticky=tk.NSEW, padx=10, pady=10)
        controls_frame.columnconfigure(0, weight=1)

        ttk.Label(controls_frame, text="🎮 Controls",
                 font=("Arial", 11, "bold"), style='CategoryPanel.TLabel').grid(
            row=0, column=0, pady=5, sticky=tk.W, padx=5
        )

        # Script selection
        script_section = ttk.LabelFrame(controls_frame, text="Script Selection", style='TLabelframe')
        script_section.grid(row=1, column=0, sticky=tk.EW, padx=5, pady=10)

        ttk.Label(script_section, text="Training Script:", style='Config.TLabel').pack(padx=10, pady=(10, 5), anchor=tk.W)

        script_options = ["train_with_unsloth.py", "Custom Script"]
        self.script_combo = ttk.Combobox(
            script_section,
            textvariable=self.selected_script_var,
            values=script_options,
            state="readonly",
            width=20
        )
        self.script_combo.pack(padx=10, pady=(0, 10), fill=tk.X)
        if script_options:
            self.selected_script_var.set(script_options[0])

        # Run settings
        settings_section = ttk.LabelFrame(controls_frame, text="Run Settings", style='TLabelframe')
        settings_section.grid(row=2, column=0, sticky=tk.EW, padx=5, pady=10)

        # Auto-restart checkbox
        ttk.Checkbutton(
            settings_section,
            text="Auto-restart on completion",
            variable=self.auto_restart_var,
            style='Category.TCheckbutton'
        ).pack(padx=10, pady=5, anchor=tk.W)

        # Max runs
        max_runs_frame = ttk.Frame(settings_section)
        max_runs_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Label(max_runs_frame, text="Max Runs:", style='Config.TLabel', width=12).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Spinbox(
            max_runs_frame,
            from_=1,
            to=100,
            textvariable=self.max_runs_var,
            width=8
        ).pack(side=tk.LEFT)

        # Delay between runs
        delay_frame = ttk.Frame(settings_section)
        delay_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Label(delay_frame, text="Delay (sec):", style='Config.TLabel', width=12).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Spinbox(
            delay_frame,
            from_=0,
            to=300,
            textvariable=self.run_delay_var,
            width=8
        ).pack(side=tk.LEFT)

        # Action buttons
        actions_section = ttk.LabelFrame(controls_frame, text="Actions", style='TLabelframe')
        actions_section.grid(row=3, column=0, sticky=tk.EW, padx=5, pady=10)

        ttk.Button(
            actions_section,
            text="▶️ Start Training",
            command=self.start_runner_training,
            style='Action.TButton'
        ).pack(fill=tk.X, padx=10, pady=5)

        ttk.Button(
            actions_section,
            text="⏹️ Stop Training",
            command=self.stop_runner_training,
            style='Select.TButton'
        ).pack(fill=tk.X, padx=10, pady=5)

        ttk.Button(
            actions_section,
            text="🗑️ Clear Output",
            command=self.clear_runner_output,
            style='Select.TButton'
        ).pack(fill=tk.X, padx=10, pady=5)

        # Status section
        status_section = ttk.LabelFrame(controls_frame, text="Status", style='TLabelframe')
        status_section.grid(row=4, column=0, sticky=tk.EW, padx=5, pady=10)

        self.runner_status_label = ttk.Label(
            status_section,
            text="⚪ Idle",
            style='Config.TLabel'
        )
        self.runner_status_label.pack(padx=10, pady=10)

        self.runner_progress_label = ttk.Label(
            status_section,
            text="Run 0 of 0",
            style='Config.TLabel'
        )
        self.runner_progress_label.pack(padx=10, pady=(0, 10))

    def create_category_manager_panel(self, parent):
        """Create category management panel for viewing/editing training categories and scripts"""
        parent.columnconfigure(0, weight=1)
        parent.columnconfigure(1, weight=0)
        parent.rowconfigure(0, weight=1)

        # Left side: Category script editor
        editor_frame = ttk.Frame(parent, style='Category.TFrame')
        editor_frame.grid(row=0, column=0, sticky=tk.NSEW, padx=10, pady=10)

        ttk.Label(editor_frame, text="📝 Category Script Editor",
                 font=("Arial", 12, "bold"), style='CategoryPanel.TLabel').pack(pady=5)

        # Category info display
        info_frame = ttk.Frame(editor_frame)
        info_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Label(info_frame, text="Category:", style='Config.TLabel').pack(side=tk.LEFT, padx=(0, 5))
        self.category_name_display = ttk.Label(info_frame, text="None selected",
                                               font=("Arial", 10, "bold"), foreground='#61dafb')
        self.category_name_display.pack(side=tk.LEFT)

        # Script editor
        self.category_script_editor = scrolledtext.ScrolledText(
            editor_frame,
            font=("Courier", 9),
            wrap=tk.NONE,
            relief='flat',
            borderwidth=0,
            highlightthickness=0,
            bg='#1e1e1e',
            fg='#ffffff'
        )
        self.category_script_editor.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Editor buttons
        editor_buttons_frame = ttk.Frame(editor_frame)
        editor_buttons_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Button(
            editor_buttons_frame,
            text="💾 Save Script",
            command=self.save_category_script,
            style='Action.TButton'
        ).pack(side=tk.LEFT, padx=5)

        ttk.Button(
            editor_buttons_frame,
            text="🔄 Reload",
            command=self.reload_category_script,
            style='Select.TButton'
        ).pack(side=tk.LEFT, padx=5)

        # Right side: Category list and manager
        manager_frame = ttk.Frame(parent, style='Category.TFrame')
        manager_frame.grid(row=0, column=1, sticky=tk.NSEW, padx=10, pady=10)
        manager_frame.columnconfigure(0, weight=1)
        manager_frame.rowconfigure(1, weight=1)

        ttk.Label(manager_frame, text="📂 Categories",
                 font=("Arial", 11, "bold"), style='CategoryPanel.TLabel').grid(
            row=0, column=0, pady=5, sticky=tk.W, padx=5
        )

        # Category list
        list_canvas = tk.Canvas(manager_frame, bg="#2b2b2b", highlightthickness=0, width=200)
        list_scrollbar = ttk.Scrollbar(manager_frame, orient="vertical", command=list_canvas.yview)
        self.category_list_frame = ttk.Frame(list_canvas)

        self.category_list_frame.bind(
            "<Configure>",
            lambda e: list_canvas.configure(scrollregion=list_canvas.bbox("all"))
        )

        list_canvas_window = list_canvas.create_window((0, 0), window=self.category_list_frame, anchor="nw")
        list_canvas.configure(yscrollcommand=list_scrollbar.set)

        list_canvas.grid(row=1, column=0, sticky=tk.NSEW)
        list_scrollbar.grid(row=1, column=1, sticky=tk.NS)

        list_canvas.bind("<Configure>", lambda e: list_canvas.itemconfig(list_canvas_window, width=e.width))

        # Populate category list
        self.populate_category_list()

        # Category management buttons
        mgmt_frame = ttk.Frame(manager_frame)
        mgmt_frame.grid(row=2, column=0, columnspan=2, sticky=tk.EW, padx=5, pady=10)

        ttk.Button(
            mgmt_frame,
            text="➕ New Category",
            command=self.create_new_category_dialog,
            style='Select.TButton'
        ).pack(fill=tk.X, pady=2)

        ttk.Button(
            mgmt_frame,
            text="🗑️ Delete Category",
            command=self.delete_category_dialog,
            style='Select.TButton'
        ).pack(fill=tk.X, pady=2)

        ttk.Button(
            mgmt_frame,
            text="📁 Open Folder",
            command=self.open_category_folder,
            style='Select.TButton'
        ).pack(fill=tk.X, pady=2)

    def populate_category_list(self):
        """Populate the category list in the manager"""
        # Clear existing list
        for widget in self.category_list_frame.winfo_children():
            widget.destroy()

        # Add categories
        for category in sorted(self.category_info.keys()):
            info = self.category_info[category]
            total = info["total_examples"]

            btn = ttk.Button(
                self.category_list_frame,
                text=f"{category}\n({total} examples)",
                command=lambda c=category: self.load_category_for_editing(c),
                style='Select.TButton'
            )
            btn.pack(fill=tk.X, pady=2, padx=5)

    def load_category_for_editing(self, category_name):
        """Load a category's training script for editing"""
        self.selected_category_for_edit.set(category_name)
        self.category_name_display.config(text=category_name)

        # Load script content (placeholder - would load actual script file)
        script_path = DATA_DIR.parent / "Training_Data-Sets" / category_name / "train.py"

        if script_path.exists():
            with open(script_path, 'r') as f:
                content = f.read()
        else:
            content = f"# Training script for {category_name}\n# Create your custom training logic here\n\n"

        self.category_script_editor.delete(1.0, tk.END)
        self.category_script_editor.insert(1.0, content)

    def save_category_script(self):
        """Save the edited category script"""
        category_name = self.selected_category_for_edit.get()
        if not category_name:
            messagebox.showwarning("No Category", "Please select a category first.")
            return

        script_path = DATA_DIR.parent / "Training_Data-Sets" / category_name / "train.py"
        script_path.parent.mkdir(parents=True, exist_ok=True)

        content = self.category_script_editor.get(1.0, tk.END)

        try:
            with open(script_path, 'w') as f:
                f.write(content)
            messagebox.showinfo("Saved", f"Script saved to {script_path}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save script: {e}")

    def reload_category_script(self):
        """Reload the category script from disk"""
        category_name = self.selected_category_for_edit.get()
        if category_name:
            self.load_category_for_editing(category_name)

    def create_new_category_dialog(self):
        """Create a new category with dialog"""
        # Reuse existing create_new_category functionality
        self.create_new_category()
        self.populate_category_list()

    def delete_category_dialog(self):
        """Delete selected category"""
        category_name = self.selected_category_for_edit.get()
        if not category_name:
            messagebox.showwarning("No Selection", "Please select a category to delete.")
            return

        if messagebox.askyesno("Confirm Delete",
                               f"Delete category '{category_name}' and all its data?\n\nThis cannot be undone!"):
            try:
                import shutil
                category_path = DATA_DIR.parent / "Training_Data-Sets" / category_name
                if category_path.exists():
                    shutil.rmtree(category_path)
                messagebox.showinfo("Deleted", f"Category '{category_name}' deleted.")
                self.selected_category_for_edit.set("")
                self.category_name_display.config(text="None selected")
                self.category_script_editor.delete(1.0, tk.END)
                self.category_info = get_category_info()
                self.populate_category_list()
                self.refresh_category_panel()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to delete category: {e}")

    def open_category_folder(self):
        """Open category folder in file manager"""
        category_name = self.selected_category_for_edit.get()
        if not category_name:
            messagebox.showwarning("No Selection", "Please select a category first.")
            return

        category_path = DATA_DIR.parent / "Training_Data-Sets" / category_name
        if category_path.exists():
            subprocess.run(["xdg-open", str(category_path)])
        else:
            messagebox.showerror("Not Found", f"Category folder not found: {category_path}")

    def start_runner_training(self):
        """Start training from runner"""
        self.runner_status_label.config(text="🟢 Running")
        self.current_run_count = 0
        self.script_running = True
        self.append_runner_output(f"=== Starting Training ===\n")
        self.append_runner_output(f"Script: {self.selected_script_var.get()}\n")
        self.append_runner_output(f"Max Runs: {self.max_runs_var.get()}\n")
        self.append_runner_output(f"Auto-restart: {self.auto_restart_var.get()}\n\n")

        # TODO: Implement actual training execution
        self.append_runner_output("Training execution not yet implemented.\n")
        self.append_runner_output("This will run the selected training script.\n")

    def stop_runner_training(self):
        """Stop running training"""
        self.script_running = False
        self.runner_status_label.config(text="🔴 Stopped")
        self.append_runner_output("\n=== Training Stopped ===\n")

    def clear_runner_output(self):
        """Clear the runner output display"""
        self.runner_output.config(state=tk.NORMAL)
        self.runner_output.delete(1.0, tk.END)
        self.runner_output.config(state=tk.DISABLED)

    def append_runner_output(self, text):
        """Append text to runner output"""
        self.runner_output.config(state=tk.NORMAL)
        self.runner_output.insert(tk.END, text)
        self.runner_output.see(tk.END)
        self.runner_output.config(state=tk.DISABLED)

    def create_category_panel(self, parent):
        """Create category selection panel"""
        # Scrollable frame for categories
        canvas = tk.Canvas(parent, bg="#2b2b2b", highlightthickness=0)
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        self.scrollable_frame = ttk.Frame(canvas)

        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        self.canvas_window_id = canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.bind("<Configure>", lambda e: canvas.itemconfig(self.canvas_window_id, width=e.width))

        canvas.pack(side="left", fill="both", expand=True, padx=5, pady=5)
        scrollbar.pack(side="right", fill="y")

        # Create category checkboxes
        for category in ["Tools", "App_Development", "Coding", "Semantic_States"]:
            self.create_category_section(self.scrollable_frame, category)

        # --- Category Management ---
        category_mgmt_frame = ttk.Frame(parent, style='Category.TFrame')
        category_mgmt_frame.pack(fill=tk.X, pady=(10, 5), padx=5)

        ttk.Label(category_mgmt_frame, text="New Category:", style='Config.TLabel').pack(side=tk.LEFT, padx=(0, 5))
        new_category_entry = ttk.Entry(category_mgmt_frame, textvariable=self.new_category_name_var, width=15, font=("Arial", 10))
        new_category_entry.pack(side=tk.LEFT, padx=(0, 5))
        create_cat_btn = ttk.Button(category_mgmt_frame, text="➕ Create", command=self.create_new_category, style='Select.TButton')
        create_cat_btn.pack(side=tk.LEFT)

        # --- Subcategory Management ---
        subcategory_mgmt_frame = ttk.Frame(parent, style='Category.TFrame')
        subcategory_mgmt_frame.pack(fill=tk.X, pady=(5, 10), padx=5)

        ttk.Label(subcategory_mgmt_frame, text="New Subcategory:", style='Config.TLabel').pack(side=tk.LEFT, padx=(0, 5))
        new_subcategory_entry = ttk.Entry(subcategory_mgmt_frame, textvariable=self.new_subcategory_name_var, width=15, font=("Arial", 10))
        new_subcategory_entry.pack(side=tk.LEFT, padx=(0, 5))

        # Dropdown for selecting parent category for new subcategory
        parent_category_options = [cat for cat in self.category_info.keys()]
        self.parent_category_combobox = ttk.Combobox(
            subcategory_mgmt_frame,
            textvariable=self.parent_category_var,
            values=parent_category_options,
            state="readonly",
            width=10,
            font=("Arial", 10)
        )
        self.parent_category_combobox.pack(side=tk.LEFT, padx=(0, 5))

        create_subcat_btn = ttk.Button(
            subcategory_mgmt_frame,
            text="➕ Create",
            command=self.create_new_subcategory,
            style='Select.TButton'
        )
        create_subcat_btn.pack(side=tk.LEFT)


    def create_category_section(self, parent, category):
        """Create expandable category section"""

        info = self.category_info[category]
        total = info["total_examples"]

        # Category frame
        self.style.configure('Category.TFrame', background='#363636', relief='flat', borderwidth=1, bordercolor='#454545')
        cat_frame = ttk.Frame(parent, style='Category.TFrame')
        cat_frame.pack(fill=tk.X, pady=5, padx=5)

        # Category checkbox
        var = tk.BooleanVar(value=True if total > 0 else False)
        self.category_vars[category] = var

        self.style.configure('Category.TCheckbutton', font=("Arial", 12, "bold"), background='#363636', foreground='#61dafb', padding=8)
        self.style.map('Category.TCheckbutton',
                       background=[('active', '#454545'), ('selected', '#61dafb')],
                       foreground=[('active', '#ffffff'), ('selected', '#1e1e1e')])
        cat_check = ttk.Checkbutton(
            cat_frame,
            text=f"{category.replace('_', ' ')} ({total} examples)",
            variable=var,
            style='Category.TCheckbutton',
            command=lambda c=category: self.toggle_category(c)
        )
        cat_check.pack(anchor=tk.W, padx=10, pady=0) # Adjusted pady

        # Subcategories frame (initially hidden if no subcats)
        if info["subcategories"]:
            self.style.configure('Subcategory.TFrame', background='#2b2b2b')
            subcat_frame = ttk.Frame(cat_frame, style='Subcategory.TFrame')
            subcat_frame.pack(fill=tk.X, padx=20, pady=(0, 8))

            for subcat_name, subcat_info in sorted(info["subcategories"].items()):
                count = subcat_info["count"]
                display_name = subcat_name.replace('_', ' ').title()

                var = tk.BooleanVar(value=True)
                self.subcategory_vars[(category, subcat_name)] = var

                self.style.configure('Subcategory.TCheckbutton', font=("Arial", 10), background='#2b2b2b', foreground='#cccccc', padding=2)
                self.style.map('Subcategory.TCheckbutton',
                               background=[('active', '#363636'), ('selected', '#61dafb')],
                               foreground=[('active', '#ffffff'), ('selected', '#1e1e1e')])
                sub_check = ttk.Checkbutton(
                    subcat_frame,
                    text=f"  {display_name} ({count})",
                    variable=var,
                    style='Subcategory.TCheckbutton',
                    command=self.update_preview
                )
                sub_check.pack(anchor=tk.W, pady=2)


    def toggle_category(self, category):
        """Toggle all subcategories when category is toggled"""
        enabled = self.category_vars[category].get()

        for (cat, subcat), var in self.subcategory_vars.items():
            if cat == category:
                var.set(enabled)

        self.update_preview()


    def create_profiles_panel(self, parent):
        """Create profiles management panel"""
        section = ttk.LabelFrame(parent, text="💾 Training Profiles", style='TLabelframe')
        section.pack(fill=tk.BOTH, expand=True, pady=10, padx=10)

        # Load Profile
        load_frame = ttk.Frame(section)
        load_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(load_frame, text="Load Profile:", style='Config.TLabel').pack(side=tk.LEFT, padx=(0, 5))
        self.profile_combobox = ttk.Combobox(
            load_frame,
            textvariable=self.selected_profile_var,
            values=list_profiles(),
            state="readonly",
            width=25,
            font=("Arial", 10)
        )
        self.profile_combobox.pack(side=tk.LEFT, padx=(0, 10))
        self.profile_combobox.bind("<<ComboboxSelected>>", self.load_profile_from_gui)

        ttk.Button(
            load_frame,
            text="📂 Load",
            command=lambda: self.load_profile_from_gui(),
            style='Select.TButton'
        ).pack(side=tk.LEFT)

        # Save Profile
        save_frame = ttk.Frame(section)
        save_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(save_frame, text="Save As:", style='Config.TLabel').pack(side=tk.LEFT, padx=(0, 5))
        profile_name_entry = ttk.Entry(
            save_frame,
            textvariable=self.profile_name_var,
            width=25,
            font=("Arial", 10)
        )
        profile_name_entry.pack(side=tk.LEFT, padx=(0, 10))

        ttk.Button(
            save_frame,
            text="💾 Save",
            command=self.save_profile_from_gui,
            style='Select.TButton'
        ).pack(side=tk.LEFT)

        # Profile info
        info_label = ttk.Label(
            section,
            text="Profiles save your current dataset selection and training parameters.",
            style='Config.TLabel',
            wraplength=400
        )
        info_label.pack(padx=10, pady=10)

    def create_config_panel(self, parent):
        """Create training configuration panel"""
        section = ttk.LabelFrame(parent, text="⚙️ Training Parameters", style='TLabelframe')
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
            command=self.update_preview
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
            command=self.update_preview
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
        strength_entry.bind("<KeyRelease>", lambda e: self.update_preview())
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
            state="readonly",
            width=35,
            font=("Arial", 10)
        )
        model_combobox.pack(side=tk.LEFT, padx=(0, 10))
        model_combobox.bind("<<ComboboxSelected>>", lambda e: self.update_preview())

        # Model tooltip on new line
        ttk.Label(section, text="Select the base model for fine-tuning",
                 font=("Arial", 8), foreground='#888888').pack(padx=10, pady=(0, 10))


    def create_preview_panel(self, parent):
        """Create training preview panel"""
        # Summary text - full tab
        self.summary_text = scrolledtext.ScrolledText(
            parent,
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


    def load_profile_from_gui(self, event=None):
        """Loads selected profile and updates GUI elements."""
        profile_name = self.selected_profile_var.get()
        if not profile_name:
            return

        try:
            profile_config = load_profile(profile_name)

            # Update config_vars
            self.config_vars["training_runs"].set(profile_config.get("training_runs", 3))
            self.config_vars["batch_size"].set(profile_config.get("batch_size", 2))
            self.config_vars["learning_strength"].set(profile_config.get("learning_strength", "2e-4"))
            self.config_vars["base_model"].set(profile_config.get("base_model", "unsloth/Qwen2.5-Coder-1.5B-Instruct"))

            # Update category checkboxes
            for cat, var in self.category_vars.items():
                var.set(False) # Deselect all first
            for (cat, subcat), var in self.subcategory_vars.items():
                var.set(False)

            selected_categories_in_profile = profile_config.get("categories", [])
            selected_subcategories_in_profile = profile_config.get("subcategories", {})

            for cat in selected_categories_in_profile:
                if cat in self.category_vars:
                    self.category_vars[cat].set(True)
                    for subcat in selected_subcategories_in_profile.get(cat, []):
                        if (cat, subcat) in self.subcategory_vars:
                            self.subcategory_vars[(cat, subcat)].set(True)

            self.update_preview()
            messagebox.showinfo("Profile Loaded", f"Profile '{profile_name}' loaded successfully.")

        except FileNotFoundError:
            messagebox.showerror("Error", f"Profile '{profile_name}' not found.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load profile '{profile_name}': {e}")


    def save_profile_from_gui(self):
        """Saves current GUI configuration as a new profile."""
        profile_name = self.profile_name_var.get().strip()
        if not profile_name:
            messagebox.showwarning("Input Error", "Please enter a name for the new profile.")
            return

        # Gather current configuration
        current_config = {
            "training_runs": self.config_vars["training_runs"].get(),
            "batch_size": self.config_vars["batch_size"].get(),
            "learning_strength": self.config_vars["learning_strength"].get(),
            "base_model": self.config_vars["base_model"].get(),
            "categories": [cat for cat, var in self.category_vars.items() if var.get()],
            "subcategories": {
                cat: [subcat for (c, subcat), var in self.subcategory_vars.items() if c == cat and var.get()]
                for cat in [cat for cat, var in self.category_vars.items() if var.get()]
            }
        }

        try:
            save_profile(profile_name, current_config)
            messagebox.showinfo("Profile Saved", f"Profile '{profile_name}' saved successfully.")
            self.profile_name_var.set("") # Clear entry
            self.update_profile_combobox() # Refresh combobox
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save profile '{profile_name}': {e}")


    def update_profile_combobox(self):
        """Refreshes the list of profiles in the combobox."""
        profiles = list_profiles()
        self.profile_combobox['values'] = profiles
        if profiles and not self.selected_profile_var.get():
            self.selected_profile_var.set(profiles[0]) # Select first profile by default
        elif not profiles:
            self.selected_profile_var.set("") # Clear if no profiles


    def create_new_category(self):
        """Creates a new category folder."""
        category_name = self.new_category_name_var.get().strip()
        if not category_name:
            messagebox.showwarning("Input Error", "Please enter a name for the new category.")
            return

        try:
            create_category_folder(category_name)
            messagebox.showinfo("Success", f"Category '{category_name}' created.")
            self.new_category_name_var.set("")
            self.refresh_category_panel()
        except FileExistsError:
            messagebox.showerror("Error", f"Category '{category_name}' already exists.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to create category '{category_name}': {e}")


    def create_new_subcategory(self):
        """Creates a new subcategory file within a selected category."""
        subcategory_name = self.new_subcategory_name_var.get().strip()
        parent_category = self.parent_category_var.get()

        if not subcategory_name:
            messagebox.showwarning("Input Error", "Please enter a name for the new subcategory.")
            return
        if not parent_category:
            messagebox.showwarning("Input Error", "Please select a parent category.")
            return

        try:
            create_subcategory_file(parent_category, subcategory_name)
            messagebox.showinfo("Success", f"Subcategory '{subcategory_name}.jsonl' created in '{parent_category}'.")
            self.new_subcategory_name_var.set("")
            self.refresh_category_panel()
        except FileNotFoundError:
            messagebox.showerror("Error", f"Parent category '{parent_category}' not found.")
        except FileExistsError:
            messagebox.showerror("Error", f"Subcategory '{subcategory_name}.jsonl' already exists in '{parent_category}'.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to create subcategory '{subcategory_name}': {e}")


    def refresh_category_panel(self):
        """Refreshes the category panel to show new categories/subcategories."""
        # Clear existing category panel content
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()

        # Re-fetch category info
        self.category_info = get_category_info()

        # Re-create category checkboxes
        for category in sorted(self.category_info.keys()): # Dynamically get categories
            self.create_category_section(self.scrollable_frame, category)

        # Update parent category combobox options
        self.parent_category_combobox['values'] = [cat for cat in self.category_info.keys()]
        if self.parent_category_var.get() not in self.category_info.keys():
            if self.category_info.keys():
                self.parent_category_var.set(list(self.category_info.keys())[0])
            else:
                self.parent_category_var.set("")

        self.update_preview()


    def update_preview(self, event=None):
        """Update the training summary preview"""

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
        training_runs = self.config_vars["training_runs"].get()

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
            summary.append(f"   Profile: {self.selected_profile_var.get()}") # Added profile name
        summary.append(f"   Training Runs: {training_runs}")
        summary.append(f"   Batch Size: {self.config_vars['batch_size'].get()}")
        summary.append(f"   Learning Strength: {self.config_vars['learning_strength'].get()}")
        summary.append(f"   Base Model: {self.config_vars['base_model'].get()}") # Added base model
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

        # Confirm
        total = sum(self.count_file(f) for f in files)
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
            "epochs": self.config_vars["training_runs"].get(),  # Keep for compatibility
            "batch_size": self.config_vars["batch_size"].get(),
            "learning_rate": self.config_vars["learning_strength"].get(),  # Keep for compatibility
            "learning_strength": self.config_vars["learning_strength"].get(),
            "base_model": self.config_vars["base_model"].get(), # Added base model to config
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
        env["BASE_MODEL"] = str(config["base_model"]) # Added BASE_MODEL env var

        subprocess.run(
            ["python3", str(DATA_DIR / "train_with_unsloth.py")],
            env=env,
            cwd=str(DATA_DIR)
        )

