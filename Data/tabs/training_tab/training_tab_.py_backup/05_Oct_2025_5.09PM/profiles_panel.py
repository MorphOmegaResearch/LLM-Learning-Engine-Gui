"""
Profiles Panel - Training profile management
"""

import tkinter as tk
from tkinter import ttk, messagebox
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from config import save_profile, load_profile, list_profiles


class ProfilesPanel:
    """Panel for managing training profiles"""

    def __init__(self, parent, style, profile_vars, category_vars, subcategory_vars, config_vars, update_preview_callback, update_combobox_callback):
        self.parent = parent
        self.style = style
        self.profile_name_var = profile_vars['profile_name']
        self.selected_profile_var = profile_vars['selected_profile']
        self.category_vars = category_vars
        self.subcategory_vars = subcategory_vars
        self.config_vars = config_vars
        self.update_preview_callback = update_preview_callback
        self.update_combobox_callback = update_combobox_callback

    def create_ui(self):
        """Create the profiles panel UI"""
        section = ttk.LabelFrame(self.parent, text="💾 Training Profiles", style='TLabelframe')
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

    def load_profile_from_gui(self, event=None):
        """Loads selected profile and updates GUI elements"""
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
                var.set(False)
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

            self.update_preview_callback()
            messagebox.showinfo("Profile Loaded", f"Profile '{profile_name}' loaded successfully.")

        except FileNotFoundError:
            messagebox.showerror("Error", f"Profile '{profile_name}' not found.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load profile '{profile_name}': {e}")

    def save_profile_from_gui(self):
        """Saves current GUI configuration as a new profile"""
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
            self.profile_name_var.set("")
            self.update_combobox_callback()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save profile '{profile_name}': {e}")

    def update_profile_combobox(self):
        """Refreshes the list of profiles in the combobox"""
        profiles = list_profiles()
        self.profile_combobox['values'] = profiles
        if profiles and not self.selected_profile_var.get():
            self.selected_profile_var.set(profiles[0])
        elif not profiles:
            self.selected_profile_var.set("")
