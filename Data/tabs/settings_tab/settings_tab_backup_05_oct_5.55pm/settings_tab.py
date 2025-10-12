"""
Settings Tab - Application configuration and preferences
Isolated module for settings-related functionality
"""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import json
from pathlib import Path
import os
import sys
import glob
import logger_util
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from tabs.base_tab import BaseTab
from config import TRAINER_ROOT, DATA_DIR, MODELS_DIR


class SettingsTab(BaseTab):
    """Application settings and configuration tab"""

    def __init__(self, parent, root, style, main_gui=None):
        super().__init__(parent, root, style)

        # Reference to main GUI (for accessing other tabs)
        self.main_gui = main_gui

        # Settings file
        self.settings_file = DATA_DIR / "settings.json"
        self.settings = self.load_settings()

        # Debug tab variables
        self.log_poll_job = None
        self.current_log_file = None
        self.last_read_position = 0
        self.log_file_paths = {}

    def create_ui(self):
        """Create the settings tab UI with side menu and sub-tabs"""
        self.parent.columnconfigure(0, weight=1)
        self.parent.columnconfigure(1, weight=0)
        self.parent.rowconfigure(0, weight=1)

        # Left side: Settings content with sub-tabs
        settings_content_frame = ttk.Frame(self.parent, style='Category.TFrame')
        settings_content_frame.grid(row=0, column=0, sticky=tk.NSEW, padx=10, pady=10)
        settings_content_frame.columnconfigure(0, weight=1)
        settings_content_frame.rowconfigure(1, weight=1)

        # Header with title and refresh buttons
        header_frame = ttk.Frame(settings_content_frame, style='Category.TFrame')
        header_frame.grid(row=0, column=0, sticky=tk.EW, pady=5)
        header_frame.columnconfigure(0, weight=1)

        ttk.Label(header_frame, text="⚙️ Settings",
                 font=("Arial", 14, "bold"), style='CategoryPanel.TLabel').pack(side=tk.LEFT, padx=(0, 10))

        # Quick Restart button
        ttk.Button(header_frame, text="🚀 Quick Restart",
                  command=self.quick_restart_application,
                  style='Action.TButton').pack(side=tk.RIGHT, padx=(5, 0))

        # Settings tab refresh button
        ttk.Button(header_frame, text="🔄 Refresh Settings",
                  command=self.refresh_settings_tab,
                  style='Select.TButton').pack(side=tk.RIGHT, padx=5)

        # Sub-tabs notebook
        self.settings_notebook = ttk.Notebook(settings_content_frame)
        self.settings_notebook.grid(row=1, column=0, sticky=tk.NSEW, padx=5, pady=5)

        # General Settings Tab
        self.general_tab_frame = ttk.Frame(self.settings_notebook)
        self.settings_notebook.add(self.general_tab_frame, text="General")
        self.create_general_settings(self.general_tab_frame)

        # Paths Tab
        self.paths_tab_frame = ttk.Frame(self.settings_notebook)
        self.settings_notebook.add(self.paths_tab_frame, text="Paths")
        self.create_path_settings(self.paths_tab_frame)

        # Training Defaults Tab
        self.training_tab_frame = ttk.Frame(self.settings_notebook)
        self.settings_notebook.add(self.training_tab_frame, text="Training Defaults")
        self.create_training_defaults(self.training_tab_frame)

        # Interface Tab
        self.interface_tab_frame = ttk.Frame(self.settings_notebook)
        self.settings_notebook.add(self.interface_tab_frame, text="Interface")
        self.create_ui_settings(self.interface_tab_frame)

        # Tab Manager Tab
        self.tab_manager_frame = ttk.Frame(self.settings_notebook)
        self.settings_notebook.add(self.tab_manager_frame, text="Tab Manager")
        self.create_tab_manager(self.tab_manager_frame)

        # Resources Tab
        self.resources_tab_frame = ttk.Frame(self.settings_notebook)
        self.settings_notebook.add(self.resources_tab_frame, text="Resources")
        self.create_resource_settings(self.resources_tab_frame)

        # Debug Tab
        self.debug_tab_frame = ttk.Frame(self.settings_notebook)
        self.settings_notebook.add(self.debug_tab_frame, text="Debug")
        self.create_debug_tab(self.debug_tab_frame)

        # Right side: Settings categories menu
        self.create_settings_menu(self.parent)

    def create_settings_menu(self, parent):
        """Create the Help Menu tree on the right."""
        menu_frame = ttk.Frame(parent, style='Category.TFrame')
        menu_frame.grid(row=0, column=1, sticky=tk.NSEW, padx=10, pady=10)
        menu_frame.columnconfigure(0, weight=1)
        menu_frame.rowconfigure(1, weight=1)

        ttk.Label(menu_frame, text="🆘 Help Menu",
                 font=("Arial", 11, "bold"), style='CategoryPanel.TLabel').grid(
            row=0, column=0, pady=5, sticky=tk.W, padx=5
        )

        # Tree view with scrollbar
        tree_container = ttk.Frame(menu_frame)
        tree_container.grid(row=1, column=0, sticky='nsew', padx=5, pady=5)
        tree_container.columnconfigure(0, weight=1)
        tree_container.rowconfigure(0, weight=1)

        tree_scroll = ttk.Scrollbar(tree_container, orient="vertical")
        tree_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.help_tree = ttk.Treeview(
            tree_container,
            yscrollcommand=tree_scroll.set,
            selectmode='browse',
            height=15
        )
        self.help_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tree_scroll.config(command=self.help_tree.yview)

        self.help_tree.heading('#0', text='Topic')
        self.help_tree.tag_configure('main_tab', font=('Arial', 10, 'bold'))
        
        self.populate_help_tree()

    def populate_help_tree(self):
        """Populate the help tree with application structure."""
        for item in self.help_tree.get_children():
            self.help_tree.delete(item)

        help_structure = {
            "Training Tab": [
                "Runner", "Categories", "Configuration", "Profiles", "Summary", "Scripts Sidebar"
            ],
            "Models Tab": [
                "Overview", "Raw Info", "Notes", "Stats", "Skills", "Model List Sidebar"
            ],
            "Settings Tab": [
                "General", "Paths", "Training Defaults", "Interface", "Tab Manager", "Resources", "Debug"
            ]
        }

        for main_tab, sub_tabs in help_structure.items():
            tab_node = self.help_tree.insert(
                '', 'end', text=main_tab, open=True, tags=('main_tab',)
            )
            for sub_tab in sub_tabs:
                self.help_tree.insert(tab_node, 'end', text=sub_tab)

    def create_general_settings(self, parent):
        """Create general settings section using the proven scrollable layout pattern."""
        # This pattern (Canvas + Scrollbar + pack) is known to work from other tabs.
        canvas = tk.Canvas(parent, bg="#2b2b2b", highlightthickness=0)
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        content_frame = ttk.Frame(canvas, style='Category.TFrame')

        content_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas_window = canvas.create_window((0, 0), window=content_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True, padx=5, pady=5)
        scrollbar.pack(side="right", fill="y")

        canvas.bind("<Configure>", lambda e: canvas.itemconfig(canvas_window, width=e.width))
        
        content_frame.columnconfigure(0, weight=1) # Allow sections to expand horizontally

        # --- Content goes into content_frame using grid ---
        current_row = 0

        # Application info
        info_section = ttk.LabelFrame(content_frame, text="ℹ️ Application Info", style='TLabelframe')
        info_section.grid(row=current_row, column=0, sticky='ew', padx=10, pady=10); current_row += 1
        info_section.columnconfigure(1, weight=1)
        ttk.Label(info_section, text="Application:", font=("Arial", 10, "bold"), style='Config.TLabel').grid(row=0, column=0, sticky=tk.W, padx=10, pady=5)
        ttk.Label(info_section, text="OpenCode Trainer", style='Config.TLabel').grid(row=0, column=1, sticky=tk.W, padx=10, pady=5)
        ttk.Label(info_section, text="Version:", font=("Arial", 10, "bold"), style='Config.TLabel').grid(row=1, column=0, sticky=tk.W, padx=10, pady=5)
        ttk.Label(info_section, text="1.3 (Debug Enhanced)", style='Config.TLabel').grid(row=1, column=1, sticky=tk.W, padx=10, pady=5)
        ttk.Label(info_section, text="Location:", font=("Arial", 10, "bold"), style='Config.TLabel').grid(row=2, column=0, sticky=tk.W, padx=10, pady=5)
        ttk.Label(info_section, text=str(TRAINER_ROOT), style='Config.TLabel', wraplength=400, justify=tk.LEFT).grid(row=2, column=1, sticky=tk.W, padx=10, pady=5)

        # Quick actions
        actions_section = ttk.LabelFrame(content_frame, text="⚡ Quick Actions", style='TLabelframe')
        actions_section.grid(row=current_row, column=0, sticky='ew', padx=10, pady=10); current_row += 1
        actions_section.columnconfigure(0, weight=1)
        ttk.Button(actions_section, text="🔄 Refresh Ollama Models", command=self.refresh_models, style='Select.TButton').grid(row=0, column=0, sticky=tk.EW, padx=10, pady=5)
        ttk.Button(actions_section, text="🗑️ Clear Training Cache", command=self.clear_cache, style='Select.TButton').grid(row=1, column=0, sticky=tk.EW, padx=10, pady=5)
        ttk.Button(actions_section, text="📊 View System Info", command=self.show_system_info, style='Select.TButton').grid(row=2, column=0, sticky=tk.EW, padx=10, pady=5)

        # Main Action Buttons
        button_frame = ttk.Frame(content_frame, style='Category.TFrame')
        button_frame.grid(row=current_row, column=0, sticky='ew', padx=10, pady=(20, 10)); current_row += 1
        button_frame.columnconfigure(0, weight=1)
        button_frame.columnconfigure(1, weight=1)
        ttk.Button(button_frame, text="💾 Save All Settings", command=self.save_settings_to_file, style='Action.TButton').grid(row=0, column=0, padx=(0, 5), sticky=tk.EW)
        ttk.Button(button_frame, text="⚠️ Reset All Settings", command=self.reset_all_settings_to_default, style='Select.TButton').grid(row=0, column=1, padx=(5, 0), sticky=tk.EW)

    def reset_all_settings_to_default(self):
        """Resets all settings in this tab to their hardcoded default values."""
        if not messagebox.askyesno("Confirm Reset", "Are you sure you want to reset ALL settings to their original defaults?\nThis cannot be undone."):
            return

        log_message("SETTINGS: User initiated reset of all settings to default.")

        try:
            # Reset Training Defaults
            if hasattr(self, 'default_epochs'): self.default_epochs.set(3)
            if hasattr(self, 'default_batch'): self.default_batch.set(2)
            if hasattr(self, 'default_lr'): self.default_lr.set("2e-4")

            # Reset Interface
            if hasattr(self, 'auto_refresh'): self.auto_refresh.set(True)
            if hasattr(self, 'show_debug'): self.show_debug.set(False)
            if hasattr(self, 'confirm_training'): self.confirm_training.set(True)

            # Reset Resources
            if hasattr(self, 'max_cpu_threads'): self.max_cpu_threads.set(2)
            if hasattr(self, 'max_ram_percent'): self.max_ram_percent.set(70)
            if hasattr(self, 'max_seq_length'): self.max_seq_length.set(256)
            if hasattr(self, 'gradient_accumulation'): self.gradient_accumulation.set(16)

            log_message("SETTINGS: All settings variables have been reset in the UI.")
            messagebox.showinfo("Reset Complete", "All settings have been reset to their defaults. Click 'Save All Settings' to make them permanent.")
        except Exception as e:
            log_message(f"SETTINGS ERROR: Failed to reset settings. Error: {e}")
            messagebox.showerror("Reset Failed", f"An error occurred while resetting settings: {e}")

    def refresh_models(self):
        """Refresh Ollama models list"""
        messagebox.showinfo("Refresh Models", "Models list will be refreshed on next restart.")

    def clear_cache(self):
        """Clear training cache files"""
        if messagebox.askyesno("Clear Cache", "Clear all temporary training files?"):
            try:
                temp_files = list(DATA_DIR.glob("temp_*.jsonl"))
                for f in temp_files:
                    f.unlink()
                messagebox.showinfo("Cache Cleared", f"Removed {len(temp_files)} temporary files.")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to clear cache: {e}")

    def show_system_info(self):
        """Show system information"""
        import platform
        info = f"""System Information:

OS: {platform.system()} {platform.release()}
Python: {platform.python_version()}
Machine: {platform.machine()}

Trainer Root: {TRAINER_ROOT}
Models Dir: {MODELS_DIR}
Data Dir: {DATA_DIR}
"""
        messagebox.showinfo("System Info", info)

    def create_path_settings(self, parent):
        """Create path configuration section"""
        section = ttk.LabelFrame(parent, text="📁 Paths", style='TLabelframe')
        section.pack(fill=tk.X, pady=10)

        # Models directory
        ttk.Label(section, text="Models Directory:", style='Config.TLabel').grid(
            row=0, column=0, sticky=tk.W, padx=10, pady=5
        )
        models_path = ttk.Label(section, text=str(MODELS_DIR), style='Config.TLabel')
        models_path.grid(row=0, column=1, sticky=tk.W, padx=10, pady=5)

        # Training data directory
        ttk.Label(section, text="Training Data:", style='Config.TLabel').grid(
            row=1, column=0, sticky=tk.W, padx=10, pady=5
        )
        data_path = ttk.Label(section, text=str(TRAINER_ROOT / "Training_Data-Sets"),
                              style='Config.TLabel')
        data_path.grid(row=1, column=1, sticky=tk.W, padx=10, pady=5)

    def create_training_defaults(self, parent):
        """Create default training parameters section"""
        section = ttk.LabelFrame(parent, text="🎯 Training Defaults", style='TLabelframe')
        section.pack(fill=tk.X, pady=10)

        # Default epochs
        ttk.Label(section, text="Default Training Runs:", style='Config.TLabel').grid(
            row=0, column=0, sticky=tk.W, padx=10, pady=5
        )
        self.default_epochs = tk.IntVar(value=self.settings.get('default_epochs', 3))
        epochs_spin = ttk.Spinbox(
            section,
            from_=1,
            to=100,
            textvariable=self.default_epochs,
            width=10
        )
        epochs_spin.grid(row=0, column=1, sticky=tk.W, padx=10, pady=5)

        # Default batch size
        ttk.Label(section, text="Default Batch Size:", style='Config.TLabel').grid(
            row=1, column=0, sticky=tk.W, padx=10, pady=5
        )
        self.default_batch = tk.IntVar(value=self.settings.get('default_batch', 2))
        batch_spin = ttk.Spinbox(
            section,
            from_=1,
            to=32,
            textvariable=self.default_batch,
            width=10
        )
        batch_spin.grid(row=1, column=1, sticky=tk.W, padx=10, pady=5)

        # Default learning rate
        ttk.Label(section, text="Default Learning Strength:", style='Config.TLabel').grid(
            row=2, column=0, sticky=tk.W, padx=10, pady=5
        )
        self.default_lr = tk.StringVar(value=self.settings.get('default_learning_rate', '2e-4'))
        lr_entry = ttk.Entry(section, textvariable=self.default_lr, width=15)
        lr_entry.grid(row=2, column=1, sticky=tk.W, padx=10, pady=5)

    def create_ui_settings(self, parent):
        """Create UI preferences section"""
        section = ttk.LabelFrame(parent, text="🎨 Interface", style='TLabelframe')
        section.pack(fill=tk.X, pady=10)

        # Auto-refresh models list
        self.auto_refresh = tk.BooleanVar(value=self.settings.get('auto_refresh_models', True))
        ttk.Checkbutton(
            section,
            text="Auto-refresh models list on startup",
            variable=self.auto_refresh,
            style='Category.TCheckbutton'
        ).grid(row=0, column=0, sticky=tk.W, padx=10, pady=5)

        # Show debug info
        self.show_debug = tk.BooleanVar(value=self.settings.get('show_debug', False))
        ttk.Checkbutton(
            section,
            text="Show debug information",
            variable=self.show_debug,
            style='Category.TCheckbutton'
        ).grid(row=1, column=0, sticky=tk.W, padx=10, pady=5)

        # Confirm before training
        self.confirm_training = tk.BooleanVar(value=self.settings.get('confirm_training', True))
        ttk.Checkbutton(
            section,
            text="Confirm before starting training",
            variable=self.confirm_training,
            style='Category.TCheckbutton'
        ).grid(row=2, column=0, sticky=tk.W, padx=10, pady=5)

    def create_tab_manager(self, parent):
        """Create tab manager interface for creating/managing custom tabs"""
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(0, weight=1)

        # Main container
        container = ttk.Frame(parent)
        container.grid(row=0, column=0, sticky=tk.NSEW, padx=10, pady=10)
        container.columnconfigure(0, weight=1)
        container.rowconfigure(1, weight=1)

        # Title
        ttk.Label(
            container,
            text="🗂️ Tab Manager - Create Custom Tabs",
            font=("Arial", 12, "bold"),
            style='CategoryPanel.TLabel'
        ).grid(row=0, column=0, pady=10, sticky=tk.W)

        # Create Tab Section
        create_frame = ttk.LabelFrame(container, text="➕ Create New Tab", style='TLabelframe')
        create_frame.grid(row=1, column=0, sticky=tk.EW, pady=10)

        # Tab name input
        name_frame = ttk.Frame(create_frame)
        name_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(name_frame, text="Tab Name:", style='Config.TLabel', width=15).pack(side=tk.LEFT, padx=(0, 10))
        self.new_tab_name = tk.StringVar()
        ttk.Entry(
            name_frame,
            textvariable=self.new_tab_name,
            font=("Arial", 10),
            width=30
        ).pack(side=tk.LEFT, fill=tk.X, expand=True)

        # Number of sub-tabs
        subtabs_frame = ttk.Frame(create_frame)
        subtabs_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Label(subtabs_frame, text="Sub-tabs:", style='Config.TLabel', width=15).pack(side=tk.LEFT, padx=(0, 10))
        self.num_subtabs = tk.IntVar(value=3)
        ttk.Spinbox(
            subtabs_frame,
            from_=1,
            to=10,
            textvariable=self.num_subtabs,
            width=10
        ).pack(side=tk.LEFT)

        # Side menu option
        options_frame = ttk.Frame(create_frame)
        options_frame.pack(fill=tk.X, padx=10, pady=10)

        self.has_side_menu = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            options_frame,
            text="Include side menu (like Model/Settings tabs)",
            variable=self.has_side_menu,
            style='Category.TCheckbutton'
        ).pack(anchor=tk.W)

        # Create button
        ttk.Button(
            create_frame,
            text="🚀 Create Tab",
            command=self.create_new_tab,
            style='Action.TButton'
        ).pack(pady=10, padx=10, fill=tk.X)

        # Existing Tabs Browser Section
        browser_frame = ttk.LabelFrame(container, text="📂 Tab Browser & Editor", style='TLabelframe')
        browser_frame.grid(row=2, column=0, sticky=tk.NSEW, pady=10)
        browser_frame.columnconfigure(0, weight=1)
        browser_frame.rowconfigure(0, weight=1)

        # Split into left (tree) and right (editor)
        browser_paned = ttk.PanedWindow(browser_frame, orient=tk.HORIZONTAL)
        browser_paned.grid(row=0, column=0, sticky=tk.NSEW, padx=5, pady=5)

        # Left: Tree view of tabs/panels
        tree_frame = ttk.Frame(browser_paned)
        browser_paned.add(tree_frame, weight=1)

        ttk.Label(
            tree_frame,
            text="Tabs & Panels",
            font=("Arial", 10, "bold"),
            style='CategoryPanel.TLabel'
        ).pack(pady=5)

        # Tree view with scrollbar
        tree_container = ttk.Frame(tree_frame)
        tree_container.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        tree_scroll = ttk.Scrollbar(tree_container, orient="vertical")
        tree_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.tabs_tree = ttk.Treeview(
            tree_container,
            yscrollcommand=tree_scroll.set,
            selectmode='browse',
            height=12
        )
        self.tabs_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tree_scroll.config(command=self.tabs_tree.yview)

        # Configure tree columns
        self.tabs_tree.heading('#0', text='Structure')

        # Style the treeview for better visibility
        style = ttk.Style()
        style.configure("Treeview",
                       background="#2b2b2b",
                       foreground="white",
                       fieldbackground="#2b2b2b",
                       borderwidth=0)
        style.map('Treeview',
                 background=[('selected', '#3d3d3d')],
                 foreground=[('selected', '#61dafb')])

        # Configure tree tags for different item types
        self.tabs_tree.tag_configure('tab', foreground='#61dafb', font=('Arial', 10, 'bold'))
        self.tabs_tree.tag_configure('file', foreground='#ffffff')
        self.tabs_tree.tag_configure('panel', foreground='#a8dadc')

        self.tabs_tree.bind('<<TreeviewSelect>>', self.on_tree_select)

        # Right: Panel editor/actions
        editor_frame = ttk.Frame(browser_paned)
        browser_paned.add(editor_frame, weight=2)

        ttk.Label(
            editor_frame,
            text="Panel Editor",
            font=("Arial", 10, "bold"),
            style='CategoryPanel.TLabel'
        ).pack(pady=5)

        # Selected item info
        self.selected_info_label = ttk.Label(
            editor_frame,
            text="Select a tab or panel from the tree",
            style='Config.TLabel'
        )
        self.selected_info_label.pack(pady=10)

        # Action buttons
        actions_frame = ttk.Frame(editor_frame)
        actions_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Button(
            actions_frame,
            text="➕ Add Panel",
            command=self.add_new_panel,
            style='Action.TButton'
        ).pack(fill=tk.X, pady=2)

        ttk.Button(
            actions_frame,
            text="✏️ Edit Panel",
            command=self.edit_selected_panel,
            style='Select.TButton'
        ).pack(fill=tk.X, pady=2)

        ttk.Button(
            actions_frame,
            text="🗑️ Delete Panel",
            command=self.delete_selected_panel,
            style='Select.TButton'
        ).pack(fill=tk.X, pady=2)

        ttk.Button(
            actions_frame,
            text="🔄 Refresh",
            command=self.refresh_tabs_tree,
            style='Select.TButton'
        ).pack(fill=tk.X, pady=2)

        # Populate tree
        self.refresh_tabs_tree()

        # Store selected item
        self.selected_tree_item = None

    def create_new_tab(self):
        """Create a new tab with user specifications"""
        from tab_generator import TabGenerator

        tab_name = self.new_tab_name.get().strip()
        if not tab_name:
            messagebox.showwarning("No Name", "Please enter a tab name.")
            return

        generator = TabGenerator(DATA_DIR)
        result = generator.create_tab(
            tab_name=tab_name,
            num_subtabs=self.num_subtabs.get(),
            has_side_menu=self.has_side_menu.get()
        )

        if result['success']:
            messagebox.showinfo(
                "Tab Created",
                f"✅ Tab '{tab_name}' created successfully!\n\n"
                f"Files created:\n" + '\n'.join([f"  • {Path(f).name}" for f in result['files']]) +
                f"\n\nRestart the application to see the new tab."
            )
            self.new_tab_name.set("")
            self.refresh_tabs_tree()
        else:
            messagebox.showerror("Creation Failed", result['error'])

    def refresh_tabs_tree(self):
        """Refresh the tree view of tabs and panels - includes ALL tabs"""
        # Clear existing tree
        for item in self.tabs_tree.get_children():
            self.tabs_tree.delete(item)

        tabs_dir = DATA_DIR / "tabs"
        if not tabs_dir.exists():
            return

        # Define built-in tabs with special handling
        built_in_tabs = {
            'training_tab': {
                'display': 'Training',
                'icon': '⚙️',
                'main_file': 'training_tab.py',
                'panels': [
                    'runner_panel.py',
                    'category_manager_panel.py',
                    'dataset_panel.py',
                    'config_panel.py',
                    'profiles_panel.py',
                    'summary_panel.py'
                ]
            },
            'models_tab': {
                'display': 'Models',
                'icon': '🤖',
                'main_file': 'models_tab.py',
                'panels': []  # Auto-detect panels
            },
            'settings_tab': {
                'display': 'Settings',
                'icon': '⚙️',
                'main_file': 'settings_tab.py',
                'panels': []  # Auto-detect panels
            }
        }

        # Iterate through all tab directories
        for tab_dir in sorted(tabs_dir.iterdir()):
            if not tab_dir.is_dir() or tab_dir.name.startswith('__'):
                continue

            # Check if it's a built-in tab
            if tab_dir.name in built_in_tabs:
                tab_info = built_in_tabs[tab_dir.name]
                tab_display_name = tab_info['display']
                icon = tab_info['icon']
            else:
                # Custom tab
                tab_display_name = tab_dir.name.replace('_tab', '').replace('_', ' ').title()
                icon = '📂'

            # Add tab as root node
            tab_node = self.tabs_tree.insert(
                '',
                'end',
                text=f"{icon} {tab_display_name}",
                values=(str(tab_dir), 'tab'),
                tags=('tab',)
            )

            # Find main tab file
            if tab_dir.name in built_in_tabs and built_in_tabs[tab_dir.name]['main_file']:
                main_file = tab_dir / built_in_tabs[tab_dir.name]['main_file']
            else:
                main_file = tab_dir / f"{tab_dir.name}.py"

            if main_file.exists():
                self.tabs_tree.insert(
                    tab_node,
                    'end',
                    text=f"📄 {main_file.name}",
                    values=(str(main_file), 'main_file'),
                    tags=('file',)
                )

            # Find all panel files
            if tab_dir.name in built_in_tabs and built_in_tabs[tab_dir.name]['panels']:
                # Use predefined panel list for built-in tabs
                panel_files = [tab_dir / p for p in built_in_tabs[tab_dir.name]['panels']
                              if (tab_dir / p).exists()]
            else:
                # Auto-detect panels for custom tabs and built-in tabs without predefined list
                panel_files = sorted([f for f in tab_dir.glob("*.py")
                                     if f.name not in ['__init__.py', main_file.name]])

            for panel_file in panel_files:
                # Determine panel type/label
                if 'panel' in panel_file.stem.lower():
                    icon = '🔧'
                else:
                    icon = '📦'

                self.tabs_tree.insert(
                    tab_node,
                    'end',
                    text=f"{icon} {panel_file.name}",
                    values=(str(panel_file), 'panel'),
                    tags=('panel',)
                )

            # Expand the tab node by default so panels are visible
            self.tabs_tree.item(tab_node, open=True)

    def on_tree_select(self, event):
        """Handle tree item selection"""
        selection = self.tabs_tree.selection()
        if not selection:
            return

        item = selection[0]
        values = self.tabs_tree.item(item, 'values')

        if not values:
            return

        file_path, item_type = values
        self.selected_tree_item = {'path': Path(file_path), 'type': item_type}

        # Update info label
        if item_type == 'tab':
            self.selected_info_label.config(
                text=f"Tab: {Path(file_path).name}"
            )
        elif item_type == 'panel':
            self.selected_info_label.config(
                text=f"Panel: {Path(file_path).name}"
            )
        elif item_type == 'main_file':
            self.selected_info_label.config(
                text=f"Main File: {Path(file_path).name}"
            )

    def add_new_panel(self):
        """Add a new panel to selected tab"""
        if not self.selected_tree_item or self.selected_tree_item['type'] != 'tab':
            messagebox.showwarning(
                "No Tab Selected",
                "Please select a tab from the tree to add a panel."
            )
            return

        from tkinter import simpledialog
        panel_name = simpledialog.askstring(
            "New Panel",
            "Enter panel name (e.g., 'analytics', 'settings'):"
        )

        if not panel_name:
            return

        # Sanitize panel name
        import re
        panel_name = re.sub(r'[^a-zA-Z0-9_]', '_', panel_name).lower()

        tab_dir = self.selected_tree_item['path']
        panel_file = tab_dir / f"{panel_name}.py"

        if panel_file.exists():
            messagebox.showerror("Error", f"Panel '{panel_name}.py' already exists!")
            return

        # Generate panel content
        class_name = ''.join(word.capitalize() for word in panel_name.split('_'))
        panel_content = f'''"""
{class_name} Panel
"""

import tkinter as tk
from tkinter import ttk


class {class_name}:
    """Panel for {panel_name}"""

    def __init__(self, parent, style):
        self.parent = parent
        self.style = style

    def create_ui(self):
        """Create the panel UI"""
        self.parent.columnconfigure(0, weight=1)
        self.parent.rowconfigure(0, weight=1)

        # Main container
        container = ttk.Frame(self.parent, style='Category.TFrame')
        container.grid(row=0, column=0, sticky=tk.NSEW, padx=10, pady=10)

        # Title
        ttk.Label(
            container,
            text="{class_name} Panel",
            font=("Arial", 12, "bold"),
            style='CategoryPanel.TLabel'
        ).pack(pady=10)

        # Content
        ttk.Label(
            container,
            text="Add your content here",
            style='Config.TLabel'
        ).pack(pady=20)
'''

        try:
            panel_file.write_text(panel_content)
            messagebox.showinfo(
                "Panel Created",
                f"✅ Panel '{panel_name}.py' created!\n\n"
                f"Remember to:\n"
                f"1. Import it in the main tab file\n"
                f"2. Add it to the notebook\n"
                f"3. Restart the application"
            )
            self.refresh_tabs_tree()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to create panel: {e}")

    def edit_selected_panel(self):
        """Open selected panel file in default editor"""
        if not self.selected_tree_item:
            messagebox.showwarning(
                "No Selection",
                "Please select a file from the tree to edit.\n\n"
                "You can edit:\n"
                "• Panel files (🔧)\n"
                "• Main tab files (📄)"
            )
            return

        if self.selected_tree_item['type'] not in ['panel', 'main_file']:
            messagebox.showwarning(
                "Invalid Selection",
                f"Cannot edit {self.selected_tree_item['type']}.\n\n"
                "Please select a panel file (🔧) or main file (📄)."
            )
            return

        file_path = self.selected_tree_item['path']

        if not file_path.exists():
            messagebox.showerror(
                "File Not Found",
                f"File does not exist:\n{file_path}"
            )
            return

        try:
            import subprocess
            subprocess.Popen(['xdg-open', str(file_path)])
            messagebox.showinfo(
                "Opening File",
                f"Opening in default editor:\n\n{file_path.name}\n\n"
                "The file should open shortly in your system's default Python editor."
            )
        except Exception as e:
            messagebox.showerror("Failed to Open", f"Failed to open file: {e}")

    def delete_selected_panel(self):
        """Delete selected panel file with strict confirmation"""
        if not self.selected_tree_item:
            messagebox.showwarning(
                "No Selection",
                "Please select a panel file from the tree to delete."
            )
            return

        if self.selected_tree_item['type'] != 'panel':
            messagebox.showwarning(
                "Invalid Selection",
                "You can only delete panel files.\n\n"
                f"Selected: {self.selected_tree_item['type']}\n\n"
                "Please select a panel file (🔧 icon)."
            )
            return

        file_path = self.selected_tree_item['path']
        file_name = file_path.name

        # Check if it's a built-in critical panel
        critical_panels = [
            'runner_panel.py', 'category_manager_panel.py',
            'dataset_panel.py', 'config_panel.py',
            'profiles_panel.py', 'summary_panel.py'
        ]

        if file_name in critical_panels:
            messagebox.showerror(
                "Cannot Delete Built-in Panel",
                f"'{file_name}' is a built-in panel and cannot be deleted.\n\n"
                "This panel is essential to the application's functionality."
            )
            return

        # First confirmation
        if not messagebox.askyesno(
            "⚠️ Confirm Delete - Step 1/2",
            f"Are you sure you want to delete:\n\n"
            f"    {file_name}\n\n"
            f"This action CANNOT be undone!"
        ):
            return

        # Second strict confirmation with typing requirement
        from tkinter import simpledialog
        confirmation = simpledialog.askstring(
            "⚠️ Confirm Delete - Step 2/2",
            f"To confirm deletion, type the panel name:\n\n"
            f"{file_name}\n\n"
            f"Type it exactly (case-sensitive):",
            parent=self.parent
        )

        if confirmation != file_name:
            messagebox.showinfo(
                "Deletion Cancelled",
                "Panel name did not match. Deletion cancelled."
            )
            return

        # Perform deletion
        try:
            file_path.unlink()
            messagebox.showinfo(
                "Panel Deleted",
                f"✅ Panel '{file_name}' has been deleted.\n\n"
                f"⚠️ IMPORTANT:\n"
                f"• Update the main tab file to remove imports\n"
                f"• Remove panel initialization code\n"
                f"• Restart the application"
            )
            self.refresh_tabs_tree()
            self.selected_tree_item = None
            self.selected_info_label.config(text="Panel deleted - select another item")
        except Exception as e:
            messagebox.showerror("Deletion Failed", f"Failed to delete panel: {e}")

    def load_settings(self):
        """Load settings from file"""
        if self.settings_file.exists():
            try:
                with open(self.settings_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                print(f"Error loading settings: {e}")
                return {}
        return {}

    def save_settings_to_file(self):
        """Save current settings to file, preserving other sections."""
        log_message("SETTINGS: Saving all settings to file.")
        try:
            # Read existing settings to preserve other sections (like runner_defaults)
            all_settings = {}
            if self.settings_file.exists():
                try:
                    with open(self.settings_file, 'r') as f:
                        all_settings = json.load(f)
                except (json.JSONDecodeError, IOError) as e:
                    log_message(f"SETTINGS ERROR: Could not read existing settings file for merge: {e}")

            # Update the settings managed by this tab
            all_settings.update({
                'default_epochs': self.default_epochs.get(),
                'default_batch': self.default_batch.get(),
                'default_learning_rate': self.default_lr.get(),
                'auto_refresh_models': self.auto_refresh.get(),
                'show_debug': self.show_debug.get(),
                'confirm_training': self.confirm_training.get(),
                'max_cpu_threads': self.max_cpu_threads.get(),
                'max_ram_percent': self.max_ram_percent.get(),
                'max_seq_length': self.max_seq_length.get(),
                'gradient_accumulation': self.gradient_accumulation.get()
            })

            with open(self.settings_file, 'w') as f:
                json.dump(all_settings, f, indent=2)

            log_message("SETTINGS: Settings saved successfully.")
            messagebox.showinfo("Settings Saved", "Settings have been saved successfully!")
            self.settings = all_settings
        except Exception as e:
            log_message(f"SETTINGS ERROR: Failed to save settings: {e}")
            messagebox.showerror("Save Error", f"Failed to save settings: {e}")

    def get_setting(self, key, default=None):
        """Get a setting value"""
        return self.settings.get(key, default)

    def create_resource_settings(self, parent):
        """Create resource limiting settings"""
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(0, weight=1)

        # Scrollable frame
        canvas = tk.Canvas(parent, bg="#2b2b2b", highlightthickness=0)
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        content_frame = ttk.Frame(canvas)

        content_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas_window = canvas.create_window((0, 0), window=content_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True, padx=5, pady=5)
        scrollbar.pack(side="right", fill="y")

        canvas.bind("<Configure>", lambda e: canvas.itemconfig(canvas_window, width=e.width))

        # CPU Settings
        cpu_section = ttk.LabelFrame(content_frame, text="💻 CPU Limits", style='TLabelframe')
        cpu_section.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(cpu_section, text="Max CPU Threads:", style='Config.TLabel').grid(
            row=0, column=0, sticky=tk.W, padx=10, pady=5
        )
        self.max_cpu_threads = tk.IntVar(value=self.settings.get('max_cpu_threads', 2))
        ttk.Spinbox(
            cpu_section,
            from_=1,
            to=32,
            textvariable=self.max_cpu_threads,
            width=10
        ).grid(row=0, column=1, sticky=tk.W, padx=10, pady=5)

        ttk.Label(
            cpu_section,
            text="Lower values prevent system freezing during training",
            font=("Arial", 8),
            foreground='#888888'
        ).grid(row=1, column=0, columnspan=2, sticky=tk.W, padx=10, pady=(0, 10))

        # Memory Settings
        mem_section = ttk.LabelFrame(content_frame, text="🧠 Memory Limits", style='TLabelframe')
        mem_section.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(mem_section, text="Max RAM Usage (%):", style='Config.TLabel').grid(
            row=0, column=0, sticky=tk.W, padx=10, pady=5
        )
        self.max_ram_percent = tk.IntVar(value=self.settings.get('max_ram_percent', 70))
        ttk.Spinbox(
            mem_section,
            from_=50,
            to=95,
            increment=5,
            textvariable=self.max_ram_percent,
            width=10
        ).grid(row=0, column=1, sticky=tk.W, padx=10, pady=5)

        ttk.Label(
            mem_section,
            text="Recommended: 70% for 8GB RAM, 80% for 16GB+",
            font=("Arial", 8),
            foreground='#888888'
        ).grid(row=1, column=0, columnspan=2, sticky=tk.W, padx=10, pady=(0, 10))

        # Training Memory Settings
        train_mem_section = ttk.LabelFrame(content_frame, text="⚙️ Training Memory", style='TLabelframe')
        train_mem_section.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(train_mem_section, text="Max Sequence Length:", style='Config.TLabel').grid(
            row=0, column=0, sticky=tk.W, padx=10, pady=5
        )
        self.max_seq_length = tk.IntVar(value=self.settings.get('max_seq_length', 256))
        seq_lengths = [128, 256, 512, 1024, 2048]
        seq_combo = ttk.Combobox(
            train_mem_section,
            textvariable=self.max_seq_length,
            values=seq_lengths,
            state="readonly",
            width=10
        )
        seq_combo.grid(row=0, column=1, sticky=tk.W, padx=10, pady=5)

        ttk.Label(train_mem_section, text="Gradient Accumulation:", style='Config.TLabel').grid(
            row=1, column=0, sticky=tk.W, padx=10, pady=5
        )
        self.gradient_accumulation = tk.IntVar(value=self.settings.get('gradient_accumulation', 16))
        ttk.Spinbox(
            train_mem_section,
            from_=1,
            to=32,
            textvariable=self.gradient_accumulation,
            width=10
        ).grid(row=1, column=1, sticky=tk.W, padx=10, pady=5)

        ttk.Label(
            train_mem_section,
            text="8GB RAM: Use 256 seq length + 16 accumulation\n16GB RAM: Use 512 seq length + 8 accumulation",
            font=("Arial", 8),
            foreground='#888888',
            justify=tk.LEFT
        ).grid(row=2, column=0, columnspan=2, sticky=tk.W, padx=10, pady=(0, 10))

        # Warning section
        warning_section = ttk.LabelFrame(content_frame, text="⚠️ Important Notes", style='TLabelframe')
        warning_section.pack(fill=tk.X, padx=10, pady=10)

        warning_text = """• Lower values = slower training but safer for your system
• If training crashes with OOM error, reduce sequence length
• If system freezes, reduce CPU threads
• These are DEFAULT values - you can override in Runner panel
• Changes take effect on next training session"""

        ttk.Label(
            warning_section,
            text=warning_text,
            font=("Arial", 9),
            foreground='#ffaa00',
            justify=tk.LEFT
        ).pack(padx=10, pady=10, anchor=tk.W)

    def refresh_settings_tab(self):
        """Refresh the settings tab - reloads settings from file."""
        # Reload settings from file
        self.settings = self.load_settings()

        # Update all variable values from reloaded settings
        if hasattr(self, 'max_cpu_threads'):
            self.max_cpu_threads.set(self.settings.get('max_cpu_threads', 2))
        if hasattr(self, 'max_ram_percent'):
            self.max_ram_percent.set(self.settings.get('max_ram_percent', 70))
        if hasattr(self, 'max_seq_length'):
            self.max_seq_length.set(self.settings.get('max_seq_length', 256))
        if hasattr(self, 'gradient_accumulation'):
            self.gradient_accumulation.set(self.settings.get('gradient_accumulation', 16))

        print("✓ Settings tab refreshed")

    def quick_restart_application(self):
        """Saves settings and restarts the application to apply code changes."""
        log_message("SETTINGS: User initiated Quick Restart.")
        try:
            # Call save_settings_to_file directly. It handles its own success/error messages.
            self.save_settings_to_file()
            
        except Exception as e:
            log_message(f"SETTINGS ERROR: Quick Restart failed to save settings: {e}")
            if not messagebox.askyesno("Restart Warning", f"Could not save settings before restart: {e}\nRestart anyway?"):
                return

        # --- RESTART LOGIC ---
        try:
            main_script_path = DATA_DIR / "interactive_trainer_gui_NEW.py"
            if not main_script_path.exists():
                main_script_path = Path(sys.argv[0])

            python_executable = sys.executable
            
            log_message(f"SETTINGS:   - Executable: {python_executable}")
            log_message(f"SETTINGS:   - Script: {main_script_path}")

            # Replace the current process with a new one
            os.execl(python_executable, python_executable, str(main_script_path))

        except Exception as e:
            messagebox.showerror("Restart Failed", f"Could not restart the application: {e}")
            log_message(f"SETTINGS ERROR: Restart failed: {e}")
        try:
            main_script_path = DATA_DIR / "interactive_trainer_gui_NEW.py"
            if not main_script_path.exists():
                main_script_path = Path(sys.argv[0])

            python_executable = sys.executable
            
            print(f"   - Executable: {python_executable}")
            print(f"   - Script: {main_script_path}")

            # Replace the current process with a new one
            os.execl(python_executable, python_executable, str(main_script_path))

        except Exception as e:
            messagebox.showerror("Restart Failed", f"Could not restart the application: {e}")
            print(f"❌ Restart failed: {e}")

    def create_debug_tab(self, parent):
        """Create the live debug feed tab with log history viewer."""
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(2, weight=1) # Row 0 for header, Row 1 for controls, Row 2 for log display

        # Header
        header = ttk.Frame(parent)
        header.grid(row=0, column=0, sticky=tk.EW, padx=10, pady=10)
        ttk.Label(header, text="🐞 Live Debug Log", font=("Arial", 12, "bold")).pack(side=tk.LEFT)

        # Log file selection controls
        controls_frame = ttk.Frame(parent)
        controls_frame.grid(row=1, column=0, sticky=tk.EW, padx=10, pady=5)
        controls_frame.columnconfigure(1, weight=1)

        ttk.Label(controls_frame, text="View Log History:", style='Config.TLabel').grid(row=0, column=0, sticky=tk.W, padx=(0, 5))
        
        self.log_file_var = tk.StringVar()
        self.log_file_combobox = ttk.Combobox(
            controls_frame,
            textvariable=self.log_file_var,
            state="readonly",
            width=50
        )
        self.log_file_combobox.grid(row=0, column=1, sticky=tk.EW, padx=(0, 5))
        self.log_file_combobox.bind("<<ComboboxSelected>>", self.on_log_file_selected)

        ttk.Button(controls_frame, text="Refresh List", command=self.populate_log_file_combobox, style='Select.TButton').grid(row=0, column=2, sticky=tk.E)

        # Log display
        self.debug_output = scrolledtext.ScrolledText(
            parent, wrap=tk.WORD, state=tk.DISABLED, font=("Courier", 9),
            bg="#1e1e1e", fg="#d4d4d4", relief='flat'
        )
        self.debug_output.grid(row=2, column=0, sticky='nsew', padx=10, pady=(0, 10))

        # Populate combobox and start polling
        self.populate_log_file_combobox()
        self.start_log_polling()

    def populate_log_file_combobox(self):
        """Populates the combobox with available log files, sorting them and labeling the current session's log as 'Live Log'."""
        log_dir = DATA_DIR / "DeBug"
        self.log_file_paths.clear() # Clear previous mappings

        if not log_dir.exists():
            self.log_file_combobox['values'] = []
            self.log_file_var.set("No logs found")
            return

        list_of_files = glob.glob(str(log_dir / 'debug_log_*.txt'))
        if not list_of_files:
            self.log_file_combobox['values'] = []
            self.log_file_var.set("No logs found")
            return

        list_of_files.sort(key=os.path.getctime, reverse=True)
        
        display_names = []
        current_session_log_path = logger_util.get_log_file_path() # Get the path of the current session's log

        for f_path in list_of_files:
            if str(f_path) == current_session_log_path:
                display_name = "Live Log"
            else:
                display_name = os.path.basename(f_path)
            display_names.append(display_name)
            self.log_file_paths[display_name] = str(f_path)

        self.log_file_combobox['values'] = display_names
        
        # Select 'Live Log' by default if it exists, otherwise the latest file
        if "Live Log" in display_names:
            self.log_file_var.set("Live Log")
        elif display_names:
            self.log_file_var.set(display_names[0])
        
        self.on_log_file_selected() # Load the selected log

    def on_log_file_selected(self, event=None):
        """Handles selection of a log file from the combobox, displaying its content and managing polling."""
        selected_display_name = self.log_file_var.get()
        if not selected_display_name or selected_display_name == "No logs found":
            return

        # Stop live polling initially
        self.stop_log_polling()

        selected_full_path = self.log_file_paths.get(selected_display_name)
        if not selected_full_path:
            self.debug_output.config(state=tk.NORMAL)
            self.debug_output.delete(1.0, tk.END)
            self.debug_output.insert(tk.END, f"Error: Log file path not found for: {selected_display_name}")
            self.debug_output.config(state=tk.DISABLED)
            return

        if not Path(selected_full_path).exists():
            self.debug_output.config(state=tk.NORMAL)
            self.debug_output.delete(1.0, tk.END)
            self.debug_output.insert(tk.END, f"Error: Log file not found on disk: {selected_full_path}")
            self.debug_output.config(state=tk.DISABLED)
            return

        self.current_log_file = selected_full_path
        self.last_read_position = 0

        self.debug_output.config(state=tk.NORMAL)
        self.debug_output.delete(1.0, tk.END)
        self.debug_output.insert(tk.END, f"--- Viewing log: {selected_display_name} ---\n\n")
        self.debug_output.config(state=tk.DISABLED)

        try:
            with open(self.current_log_file, 'r') as f:
                content = f.read()
                if content:
                    self.debug_output.config(state=tk.NORMAL)
                    self.debug_output.insert(tk.END, content)
                    self.debug_output.see(tk.END)
                    self.debug_output.config(state=tk.DISABLED)
                self.last_read_position = f.tell()
        except Exception as e:
            self.debug_output.config(state=tk.NORMAL)
            self.debug_output.insert(tk.END, f"\n--- ERROR READING LOG: {e} ---\n")
            self.debug_output.config(state=tk.DISABLED)

        # If the selected file is the current session's log, restart live polling
        if self.current_log_file == logger_util.get_log_file_path():
            self.start_log_polling() # Restart polling for the live log

    def start_log_polling(self):
        """Starts the periodic polling of the log file."""
        if self.log_poll_job:
            self.parent.after_cancel(self.log_poll_job)
        self.poll_log_file()

    def stop_log_polling(self):
        """Stops the periodic polling of the log file."""
        if self.log_poll_job:
            self.parent.after_cancel(self.log_poll_job)
            self.log_poll_job = None

    def poll_log_file(self):
        """Checks the current log file for new content and updates the display. Only polls if viewing the live log."""
        # Only poll if the currently viewed log is the live log
        if self.current_log_file != logger_util.get_log_file_path():
            self.log_poll_job = self.parent.after(2000, self.poll_log_file) # Keep scheduling to re-check if it becomes live
            return

        log_dir = DATA_DIR / "DeBug"
        list_of_files = glob.glob(str(log_dir / 'debug_log_*.txt'))
        if not list_of_files:
            self.debug_output.config(state=tk.NORMAL)
            self.debug_output.delete(1.0, tk.END)
            self.debug_output.insert(tk.END, "No log files found in DeBug directory.")
            self.debug_output.config(state=tk.DISABLED)
            self.log_poll_job = self.parent.after(2000, self.poll_log_file) # Keep polling
            return

        # Ensure we are always polling the actual latest file if 'Live Log' is selected
        actual_latest_file = max(list_of_files, key=os.path.getctime)
        if self.current_log_file != actual_latest_file:
            # This should ideally not happen if on_log_file_selected correctly sets current_log_file to the live one
            # But as a safeguard, if the live log file changes (e.g., app restart), update.
            self.current_log_file = actual_latest_file
            self.last_read_position = 0
            self.log_file_var.set("Live Log") # Ensure combobox shows Live Log
            self.debug_output.config(state=tk.NORMAL)
            self.debug_output.delete(1.0, tk.END)
            self.debug_output.insert(tk.END, f"--- Switched to live log: {os.path.basename(actual_latest_file)} ---\n\n")
            self.debug_output.config(state=tk.DISABLED)

        try:
            with open(self.current_log_file, 'r') as f:
                f.seek(self.last_read_position)
                new_content = f.read()
                if new_content:
                    self.debug_output.config(state=tk.NORMAL)
                    self.debug_output.insert(tk.END, new_content)
                    self.debug_output.see(tk.END)
                    self.debug_output.config(state=tk.DISABLED)
                self.last_read_position = f.tell()

        except Exception as e:
            self.debug_output.config(state=tk.NORMAL)
            self.debug_output.insert(tk.END, f"\n--- ERROR POLLING LOG: {e} ---\n")
            self.debug_output.config(state=tk.DISABLED)
        
        self.log_poll_job = self.parent.after(2000, self.poll_log_file) # Poll every 2 seconds
