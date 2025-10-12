#!/usr/bin/env python3
"""
Interactive Training Launcher - Full GUI
Visual graphical interface for selecting training datasets
"""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import json
import subprocess
import threading
from pathlib import Path
from typing import Dict, Set

# Import config
from config import (
    get_category_info,
    get_training_data_files,
    DATA_DIR,
    TRAINER_ROOT,
    save_profile,
    load_profile,
    list_profiles,
    create_category_folder,
    create_subcategory_file,
    get_ollama_models,
    get_ollama_model_info,
    parse_ollama_model_info,
    save_model_note,
    load_model_note,
    list_model_notes,
    delete_model_note,
    load_training_stats,
    get_latest_training_stats
)


class TrainingGUI:
    """Full graphical training launcher"""

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("OpenCode Training Launcher")
        # self.root.geometry("900x700") # Removed fixed geometry

        # Set ttk theme and style
        self.style = ttk.Style()
        self.style.theme_use('clam') # Using 'clam' theme for a softer look

        # Configure general styles
        self.style.configure('.', font=('Arial', 10), background='#2b2b2b', foreground='#ffffff')
        self.style.configure('TFrame', background='#2b2b2b', borderwidth=0)
        self.style.configure('TLabel', background='#2b2b2b', foreground='#ffffff')
        self.style.configure('TCheckbutton', background='#363636', foreground='#ffffff', indicatoron=False, relief='flat', padding=5)
        self.style.map('TCheckbutton',
                       background=[('active', '#454545'), ('selected', '#61dafb')],
                       foreground=[('active', '#ffffff'), ('selected', '#1e1e1e')]) # Text color for selected checkbutton
        self.style.configure('TButton', font=('Arial', 10, 'bold'), relief='flat', borderwidth=0, padding=10)
        self.style.map('TButton',
                       background=[('active', '#454545')],
                       foreground=[('active', '#ffffff')])
        self.style.configure('TSpinbox', fieldbackground='#1e1e1e', foreground='#ffffff', background='#363636', arrowcolor='#61dafb')
        self.style.configure('TEntry', fieldbackground='#1e1e1e', foreground='#ffffff', insertcolor='#ffffff')
        self.style.configure('TLabelframe', background='#363636', foreground='#ffffff', relief='flat', borderwidth=0)
        self.style.configure('TLabelframe.Label', background='#363636', foreground='#ffffff', font=('Arial', 12, 'bold'))
        self.style.configure('TScrollbar', troughcolor='#2b2b2b', background='#61dafb', borderwidth=0, relief='flat')
        self.style.map('TScrollbar', background=[('active', '#454545')])


        # State
        self.category_vars = {}  # {category: BooleanVar}
        self.subcategory_vars = {}  # {(category, subcat): BooleanVar}
        # Get available Ollama models
        self.ollama_models = get_ollama_models()
        print(f"DEBUG: Detected Ollama models: {self.ollama_models}") # DEBUG PRINT
        default_model = "unsloth/Qwen2.5-Coder-1.5B-Instruct"
        if self.ollama_models and default_model not in self.ollama_models:
            default_model = self.ollama_models[0] # Use first available if default not present

        self.config_vars = {
            "training_runs": tk.IntVar(value=3),  # Renamed from epochs
            "batch_size": tk.IntVar(value=2),
            "learning_strength": tk.StringVar(value="2e-4"),  # Renamed from learning_rate
            "base_model": tk.StringVar(value=default_model) # Use dynamically set default
        }
        self.profile_name_var = tk.StringVar(value="") # New: For saving new profile
        self.selected_profile_var = tk.StringVar(value="") # New: For loading existing profile

        # Get category info
        self.category_info = get_category_info()

        # Build UI
        self.create_ui()
        self.update_profile_combobox() # New: Populate profile combobox on startup

    def create_ui(self):
        """Create the GUI layout with tabs"""

        # Header
        self.style.configure('Header.TFrame', background='#1e1e1e')
        header = ttk.Frame(self.root, height=80, style='Header.TFrame')
        header.pack(fill=tk.X, padx=0, pady=0)

        self.style.configure('Header.TLabel', font=("Arial", 24, "bold"), background='#1e1e1e', foreground='#61dafb')
        title_label = ttk.Label(
            header,
            text="🚀 OpenCode Training Launcher",
            style='Header.TLabel'
        )
        title_label.pack(pady=20)

        # Main content area - now a Notebook (tabs)
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10) # Added padding

        # --- Training Tab ---
        self.training_tab_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.training_tab_frame, text="⚙️ Training")

        # Layout within Training Tab (left and right panels)
        training_content_frame = ttk.Frame(self.training_tab_frame)
        training_content_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        left_panel = ttk.Frame(training_content_frame)
        left_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))
        self.create_category_panel(left_panel)

        right_panel = ttk.Frame(training_content_frame, width=350)
        right_panel.pack(side=tk.RIGHT, fill=tk.BOTH, padx=(10, 0))
        self.create_config_panel(right_panel)
        self.create_preview_panel(right_panel)

        # --- Models Tab ---
        self.models_tab_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.models_tab_frame, text="🧠 Models")
        self.create_models_tab(self.models_tab_frame) # New method to create models tab content

        # Bottom buttons
        button_frame = ttk.Frame(self.root, height=70)
        button_frame.pack(fill=tk.X, padx=20, pady=(0, 20))
        self.create_buttons(button_frame)

    def create_category_panel(self, parent):
        """Create category selection panel"""

        self.style.configure('CategoryPanel.TLabel', font=("Arial", 14, "bold"), background='#2b2b2b', foreground='#ffffff')
        label = ttk.Label(
            parent,
            text="📁 Select Training Categories",
            style='CategoryPanel.TLabel'
        )
        label.pack(anchor=tk.W, pady=(0, 10))

        # Scrollable frame for categories
        canvas = tk.Canvas(parent, bg="#2b2b2b", highlightthickness=0) # tk.Canvas is fine, but ensure styling
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        self.scrollable_frame = ttk.Frame(canvas) # Store reference to scrollable_frame

        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        # Store the canvas window ID to update its width dynamically
        self.canvas_window_id = canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        # Bind the canvas's <Configure> event to resize the window inside it
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(self.canvas_window_id, width=e.width))

        canvas.pack(side="left", fill="both", expand=True, padx=5, pady=5) # Add padding
        scrollbar.pack(side="right", fill="y")

        # Create category checkboxes
        for category in ["Tools", "App_Development", "Coding", "Semantic_States"]:
            self.create_category_section(self.scrollable_frame, category)

        # --- Category Management ---
        category_mgmt_frame = ttk.Frame(parent, style='Category.TFrame')
        category_mgmt_frame.pack(fill=tk.X, pady=(10, 5), padx=5)

        ttk.Label(category_mgmt_frame, text="New Category:", style='Config.TLabel').pack(side=tk.LEFT, padx=(0, 5))
        self.new_category_name_var = tk.StringVar()
        new_category_entry = ttk.Entry(category_mgmt_frame, textvariable=self.new_category_name_var, width=15, font=("Arial", 10))
        new_category_entry.pack(side=tk.LEFT, padx=(0, 5))
        create_cat_btn = ttk.Button(category_mgmt_frame, text="➕ Create", command=self.create_new_category, style='Select.TButton')
        create_cat_btn.pack(side=tk.LEFT)

        # --- Subcategory Management ---
        subcategory_mgmt_frame = ttk.Frame(parent, style='Category.TFrame')
        subcategory_mgmt_frame.pack(fill=tk.X, pady=(5, 10), padx=5)

        ttk.Label(subcategory_mgmt_frame, text="New Subcategory:", style='Config.TLabel').pack(side=tk.LEFT, padx=(0, 5))
        self.new_subcategory_name_var = tk.StringVar()
        new_subcategory_entry = ttk.Entry(subcategory_mgmt_frame, textvariable=self.new_subcategory_name_var, width=15, font=("Arial", 10))
        new_subcategory_entry.pack(side=tk.LEFT, padx=(0, 5))

        # Dropdown for selecting parent category for new subcategory
        self.parent_category_var = tk.StringVar(value="Tools") # Default to Tools
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

    def create_config_panel(self, parent):
        """Create training configuration panel"""

        self.style.configure('Config.TLabelframe', background='#363636', relief='flat', borderwidth=1, bordercolor='#454545')
        self.style.configure('Config.TLabelframe.Label', font=("Arial", 12, "bold"), background='#363636', foreground='#ffffff')
        config_frame = ttk.LabelFrame(
            parent,
            text="⚙️  Training Configuration",
            style='Config.TLabelframe'
        )
        config_frame.pack(fill=tk.X, pady=(0, 10), padx=5) # Added padx

        # --- Profile Management ---
        profile_frame = ttk.Frame(config_frame)
        profile_frame.grid(row=0, column=0, columnspan=3, sticky=tk.EW, padx=5, pady=5)

        ttk.Label(profile_frame, text="Load Profile:", style='Config.TLabel').pack(side=tk.LEFT, padx=(0, 5))
        self.profile_combobox = ttk.Combobox(
            profile_frame,
            textvariable=self.selected_profile_var,
            values=list_profiles(), # Populate with existing profiles
            state="readonly",
            width=20,
            font=("Arial", 10)
        )
        self.profile_combobox.pack(side=tk.LEFT, padx=(0, 10))
        self.profile_combobox.bind("<<ComboboxSelected>>", self.load_profile_from_gui)

        ttk.Label(profile_frame, text="Save As:", style='Config.TLabel').pack(side=tk.LEFT, padx=(0, 5))
        profile_name_entry = ttk.Entry(
            profile_frame,
            textvariable=self.profile_name_var,
            width=15,
            font=("Arial", 10)
        )
        profile_name_entry.pack(side=tk.LEFT, padx=(0, 5))

        save_profile_btn = ttk.Button(
            profile_frame,
            text="💾 Save",
            command=self.save_profile_from_gui,
            style='Select.TButton' # Reusing a button style
        )
        save_profile_btn.pack(side=tk.LEFT)

        # Separator
        ttk.Separator(config_frame, orient=tk.HORIZONTAL).grid(row=1, column=0, columnspan=3, sticky=tk.EW, pady=10)


        # Training Runs (formerly Epochs) - now starts at row 2
        self.style.configure('Config.TLabel', font=("Arial", 10), background='#363636', foreground='#cccccc')
        ttk.Label(
            config_frame,
            text="Training Runs:",
            style='Config.TLabel'
        ).grid(row=2, column=0, sticky=tk.W, padx=10, pady=8)

        runs_spin = ttk.Spinbox(
            config_frame,
            from_=1,
            to=10,
            textvariable=self.config_vars["training_runs"],
            width=10,
            font=("Arial", 10),
            command=self.update_preview
        )
        runs_spin.grid(row=2, column=1, padx=10, pady=8)

        # Tooltip
        self.style.configure('Config.Tooltip.TLabel', font=("Arial", 8), background='#363636', foreground='#888888')
        ttk.Label(
            config_frame,
            text="(How many times to read all examples)",
            style='Config.Tooltip.TLabel'
        ).grid(row=2, column=2, sticky=tk.W, padx=5, pady=8)

        # Batch Size - now at row 3
        ttk.Label(
            config_frame,
            text="Batch Size:",
            style='Config.TLabel'
        ).grid(row=3, column=0, sticky=tk.W, padx=10, pady=8)

        batch_spin = ttk.Spinbox(
            config_frame,
            from_=1,
            to=16,
            textvariable=self.config_vars["batch_size"],
            width=10,
            font=("Arial", 10),
            command=self.update_preview
        )
        batch_spin.grid(row=3, column=1, padx=10, pady=8)

        # Tooltip
        ttk.Label(
            config_frame,
            text="(Examples per update - higher = faster)",
            style='Config.Tooltip.TLabel'
        ).grid(row=3, column=2, sticky=tk.W, padx=5, pady=8)

        # Learning Strength (formerly Learning Rate) - now at row 4
        ttk.Label(
            config_frame,
            text="Learning Strength:",
            style='Config.TLabel'
        ).grid(row=4, column=0, sticky=tk.W, padx=10, pady=8)

        strength_entry = ttk.Entry(
            config_frame,
            textvariable=self.config_vars["learning_strength"],
            width=12,
            font=("Arial", 10)
        )
        strength_entry.grid(row=4, column=1, padx=10, pady=8)
        strength_entry.bind("<KeyRelease>", lambda e: self.update_preview())

        # Tooltip
        ttk.Label(
            config_frame,
            text="(How much to learn per mistake - 2e-4 is good)",
            style='Config.Tooltip.TLabel'
        ).grid(row=4, column=2, sticky=tk.W, padx=5, pady=8)

        # --- Model Selection --- - now at row 5
        ttk.Label(
            config_frame,
            text="Base Model:",
            style='Config.TLabel'
        ).grid(row=5, column=0, sticky=tk.W, padx=10, pady=8)

        model_combobox = ttk.Combobox(
            config_frame,
            textvariable=self.config_vars["base_model"],
            values=self.ollama_models, # Use dynamically fetched models
            state="readonly", # Users can only select from the list
            width=30,
            font=("Arial", 10)
        )
        model_combobox.grid(row=5, column=1, columnspan=2, sticky=tk.W, padx=10, pady=8)
        model_combobox.bind("<<ComboboxSelected>>", lambda e: self.update_preview())

        # Tooltip - now at row 6
        ttk.Label(
            config_frame,
            text="(Select the base model for fine-tuning)",
            style='Config.Tooltip.TLabel'
        ).grid(row=6, column=0, columnspan=3, sticky=tk.W, padx=10, pady=0)

    def create_preview_panel(self, parent):
        """Create training preview panel"""

        self.style.configure('Preview.TLabelframe', background='#363636', relief='flat', borderwidth=1, bordercolor='#454545')
        self.style.configure('Preview.TLabelframe.Label', font=("Arial", 12, "bold"), background='#363636', foreground='#ffffff')
        preview_frame = ttk.LabelFrame(
            parent,
            text="📊 Training Summary",
            style='Preview.TLabelframe'
        )
        preview_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5) # Added padx and pady

        # Summary text
        # ScrolledText is not a ttk widget, so we style its internal text widget
        self.summary_text = scrolledtext.ScrolledText(
            preview_frame,
            width=40,
            height=15,
            font=("Courier", 9),
            wrap=tk.WORD,
            state=tk.DISABLED,
            relief='flat', # Make it flat
            borderwidth=0, # Remove border
            highlightthickness=0 # Remove highlight border
        )
        self.summary_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Configure the internal Text widget of ScrolledText
        self.summary_text.tag_configure('default', background='#1e1e1e', foreground='#61dafb')
        self.summary_text.config(background='#1e1e1e', foreground='#61dafb') # Fallback for some systems

        self.update_preview()

    def create_buttons(self, parent):
        """Create action buttons"""

        # Start Training button
        self.style.configure('Start.TButton', font=("Arial", 14, "bold"), background='#4CAF50', foreground='#ffffff', relief='flat', borderwidth=0)
        self.style.map('Start.TButton',
                       background=[('active', '#45a049')],
                       foreground=[('active', '#ffffff')])
        start_btn = ttk.Button(
            parent,
            text="🚀 Start Training",
            command=self.start_training,
            style='Start.TButton',
            cursor="hand2"
        )
        start_btn.pack(side=tk.RIGHT, padx=5, pady=5) # Added pady

        # Cancel button
        self.style.configure('Cancel.TButton', font=("Arial", 12), background='#f44336', foreground='#ffffff', relief='flat', borderwidth=0)
        self.style.map('Cancel.TButton',
                       background=[('active', '#da190b')],
                       foreground=[('active', '#ffffff')])
        cancel_btn = ttk.Button(
            parent,
            text="❌ Cancel",
            command=self.root.quit,
            style='Cancel.TButton',
            cursor="hand2"
        )
        cancel_btn.pack(side=tk.RIGHT, padx=5, pady=5) # Added pady

        # Select All button
        self.style.configure('Select.TButton', font=("Arial", 10), background='#2196F3', foreground='#ffffff', relief='flat', borderwidth=0)
        self.style.map('Select.TButton',
                       background=[('active', '#0b7dda')],
                       foreground=[('active', '#ffffff')])
        select_all_btn = ttk.Button(
            parent,
            text="☑️ Select All",
            command=self.select_all,
            style='Select.TButton',
            cursor="hand2"
        )
        select_all_btn.pack(side=tk.LEFT, padx=5, pady=5) # Added pady

        # Deselect All button
        self.style.configure('Deselect.TButton', font=("Arial", 10), background='#607D8B', foreground='#ffffff', relief='flat', borderwidth=0)
        self.style.map('Deselect.TButton',
                       background=[('active', '#455A64')],
                       foreground=[('active', '#ffffff')])
        deselect_all_btn = ttk.Button(
            parent,
            text="☐ Deselect All",
            command=self.deselect_all,
            style='Deselect.TButton',
            cursor="hand2"
        )
        deselect_all_btn.pack(side=tk.LEFT, padx=5, pady=5) # Added pady

    def create_models_tab(self, parent):
        """Create the content for the Models tab."""
        parent.columnconfigure(0, weight=1) # Model Info column
        parent.columnconfigure(1, weight=0) # Model List column
        parent.rowconfigure(0, weight=1)

        # Left side: Model Information Display
        model_info_frame = ttk.Frame(parent, style='Category.TFrame')
        model_info_frame.grid(row=0, column=0, sticky=tk.NSEW, padx=10, pady=10)
        model_info_frame.columnconfigure(0, weight=1)
        model_info_frame.rowconfigure(0, weight=1)

        ttk.Label(model_info_frame, text="🧠 Model Information", font=("Arial", 14, "bold"), style='CategoryPanel.TLabel').pack(pady=5)
        
        self.model_info_notebook = ttk.Notebook(model_info_frame)
        self.model_info_notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Overview Tab
        self.overview_tab_frame = ttk.Frame(self.model_info_notebook)
        self.model_info_notebook.add(self.overview_tab_frame, text="Overview")
        # Labels for parsed info will be created dynamically in display_model_info

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

        # Right side: Scrollable Model List
        model_list_frame = ttk.Frame(parent, style='Category.TFrame')
        model_list_frame.grid(row=0, column=1, sticky=tk.NSEW, padx=10, pady=10)
        model_list_frame.columnconfigure(0, weight=1)
        model_list_frame.rowconfigure(1, weight=1) # For the canvas

        ttk.Label(model_list_frame, text="Available Ollama Models", font=("Arial", 12, "bold"), style='CategoryPanel.TLabel').grid(row=0, column=0, pady=5)

        model_list_canvas = tk.Canvas(model_list_frame, bg="#2b2b2b", highlightthickness=0)
        model_list_scrollbar = ttk.Scrollbar(model_list_frame, orient="vertical", command=model_list_canvas.yview)
        self.model_buttons_frame = ttk.Frame(model_list_canvas) # Frame to hold model buttons

        self.model_buttons_frame.bind(
            "<Configure>",
            lambda e: model_list_canvas.configure(scrollregion=model_list_canvas.bbox("all"))
        )

        # Store the canvas window ID to update its width dynamically
        self.model_list_canvas_window_id = model_list_canvas.create_window((0, 0), window=self.model_buttons_frame, anchor="nw")
        model_list_canvas.configure(yscrollcommand=model_list_scrollbar.set)

        model_list_canvas.grid(row=1, column=0, sticky=tk.NSEW)
        model_list_scrollbar.grid(row=1, column=1, sticky=tk.NS)

        # Bind canvas resize to update internal window width using the stored ID
        model_list_canvas.bind("<Configure>", lambda e: model_list_canvas.itemconfig(self.model_list_canvas_window_id, width=e.width))

        self.populate_model_list() # Populate the list of models

    def populate_model_list(self):
        """Populates the scrollable frame with buttons for each Ollama model."""
        # Clear existing buttons
        for widget in self.model_buttons_frame.winfo_children():
            widget.destroy()

        if not self.ollama_models:
            ttk.Label(self.model_buttons_frame, text="No Ollama models found.", style='Config.TLabel').pack(pady=10)
            return

        for model_name in self.ollama_models:
            model_btn = ttk.Button(
                self.model_buttons_frame,
                text=model_name,
                command=lambda m=model_name: self.display_model_info(m),
                style='Select.TButton'
            )
            model_btn.pack(fill=tk.X, pady=2, padx=5)

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

    def create_stats_panel(self, parent):
        """Create the stats panel for model training statistics."""
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(0, weight=1)

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

        stats_canvas.grid(row=0, column=0, sticky=tk.NSEW, padx=10, pady=10)
        stats_scrollbar.grid(row=0, column=1, sticky=tk.NS)

        stats_canvas.bind("<Configure>", lambda e: stats_canvas.itemconfig(self.stats_canvas_window_id, width=e.width))

        # Initialize with placeholder
        ttk.Label(self.stats_content_frame, text="Select a model to view training statistics",
                 font=("Arial", 12), style='Config.TLabel').pack(pady=20)

        # Store current model name for stats
        self.current_model_for_stats = None

    def populate_stats_display(self):
        """Populate the stats display for the current model."""
        # Clear existing content
        for widget in self.stats_content_frame.winfo_children():
            widget.destroy()

        if not self.current_model_for_stats:
            ttk.Label(self.stats_content_frame, text="Select a model to view training statistics",
                     font=("Arial", 12), style='Config.TLabel').pack(pady=20)
            return

        # Load stats for current model
        stats = load_training_stats(self.current_model_for_stats)
        latest = get_latest_training_stats(self.current_model_for_stats)

        # Header
        header_frame = ttk.Frame(self.stats_content_frame, style='Category.TFrame')
        header_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(header_frame, text=f"📊 Training Statistics: {self.current_model_for_stats}",
                 font=("Arial", 14, "bold"), style='CategoryPanel.TLabel').pack(anchor=tk.W)

        if not stats["training_runs"]:
            ttk.Label(self.stats_content_frame, text="No training runs recorded yet",
                     font=("Arial", 11), style='Config.TLabel').pack(pady=20)
            ttk.Label(self.stats_content_frame,
                     text="Stats will appear here after training completes",
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
                if key != "timestamp":
                    ttk.Label(latest_frame, text=f"{key.replace('_', ' ').title()}:",
                             font=("Arial", 10, "bold"), style='Config.TLabel').grid(
                                 row=row, column=0, sticky=tk.W, padx=10, pady=2)
                    ttk.Label(latest_frame, text=str(value), font=("Arial", 10),
                             style='Config.TLabel').grid(row=row, column=1, sticky=tk.W, padx=10, pady=2)
                    row += 1

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

    def populate_notes_list(self):
        """Populate the notes list for the current model."""
        # Clear existing buttons
        for widget in self.notes_list_buttons_frame.winfo_children():
            widget.destroy()

        if not self.current_model_for_notes:
            ttk.Label(self.notes_list_buttons_frame, text="Select a model", style='Config.TLabel').pack(pady=10)
            return

        notes = list_model_notes(self.current_model_for_notes)

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
        if not self.current_model_for_notes:
            messagebox.showwarning("No Model Selected", "Please select a model first.")
            return

        note_name = self.note_name_var.get().strip()
        if not note_name:
            messagebox.showwarning("No Note Name", "Please enter a name for the note.")
            return

        content = self.notes_text.get(1.0, tk.END).strip()

        try:
            save_model_note(self.current_model_for_notes, note_name, content)
            messagebox.showinfo("Note Saved", f"Note '{note_name}' saved for {self.current_model_for_notes}")
            self.populate_notes_list()  # Refresh the notes list
        except Exception as e:
            messagebox.showerror("Save Error", f"Failed to save note: {e}")

    def load_note(self, note_name):
        """Load a specific note for the current model."""
        if not self.current_model_for_notes:
            return

        content = load_model_note(self.current_model_for_notes, note_name)
        self.note_name_var.set(note_name)
        self.notes_text.delete(1.0, tk.END)
        self.notes_text.insert(1.0, content)

    def delete_note(self):
        """Delete the current note."""
        if not self.current_model_for_notes:
            messagebox.showwarning("No Model Selected", "Please select a model first.")
            return

        note_name = self.note_name_var.get().strip()
        if not note_name:
            messagebox.showwarning("No Note Name", "Please enter the name of the note to delete.")
            return

        if messagebox.askyesno("Confirm Delete", f"Delete note '{note_name}'?"):
            if delete_model_note(self.current_model_for_notes, note_name):
                messagebox.showinfo("Note Deleted", f"Note '{note_name}' deleted.")
                self.notes_text.delete(1.0, tk.END)
                self.note_name_var.set("")
                self.populate_notes_list()  # Refresh the notes list
            else:
                messagebox.showwarning("Not Found", f"Note '{note_name}' not found.")

    def display_model_info(self, model_name):
        """Displays information for the selected model."""
        raw_info = get_ollama_model_info(model_name)
        parsed_info = parse_ollama_model_info(raw_info)

        # Update Raw Info Tab
        self.raw_model_info_text.config(state=tk.NORMAL)
        self.raw_model_info_text.delete(1.0, tk.END)
        self.raw_model_info_text.insert(1.0, raw_info)
        self.raw_model_info_text.config(state=tk.DISABLED)

        # Update Overview Tab
        # Clear previous overview content
        for widget in self.overview_tab_frame.winfo_children():
            widget.destroy()

        row_num = 0
        for key, value in parsed_info.items():
            ttk.Label(self.overview_tab_frame, text=f"{key.replace('_', ' ').title()}:", font=("Arial", 10, "bold"), style='Config.TLabel').grid(row=row_num, column=0, sticky=tk.W, padx=5, pady=2)
            ttk.Label(self.overview_tab_frame, text=value, font=("Arial", 10), style='Config.TLabel').grid(row=row_num, column=1, sticky=tk.W, padx=5, pady=2)
            row_num += 1

        # Update Notes Tab context
        self.current_model_for_notes = model_name
        self.notes_text.delete(1.0, tk.END)
        self.note_name_var.set("")
        self.populate_notes_list()  # Load notes list for this model

        # Update Stats Tab
        self.current_model_for_stats = model_name
        self.populate_stats_display()  # Load stats for this model

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

        # Cleanup
        if temp_file.exists():
            temp_file.unlink()

    def run(self):
        """Run the GUI"""
        self.root.mainloop()


def main():
    """Entry point"""
    app = TrainingGUI()
    app.run()


if __name__ == "__main__":
    main()
