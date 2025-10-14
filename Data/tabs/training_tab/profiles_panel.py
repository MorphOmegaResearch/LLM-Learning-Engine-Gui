# [SYSTEM: GUI | VERSION: 1.9f | STATUS: ACTIVE]
"""
Profiles Panel - Training profile management
"""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from pathlib import Path
import json

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from config import save_profile, load_profile, list_profiles
from config import list_all_training_profiles


import logger_util # Add import for logging

class ProfilesPanel:
    """Panel for managing training profiles"""

    def __init__(self, parent, style, profile_vars, category_vars, subcategory_vars, model_selection_panel, runner_panel, update_preview_callback, update_combobox_callback, training_tab_instance):
        self.parent = parent
        self.style = style
        self.profile_name_var = profile_vars['profile_name']
        self.selected_profile_var = profile_vars['selected_profile']
        self.category_vars = category_vars
        self.subcategory_vars = subcategory_vars
        self.model_selection_panel = model_selection_panel
        self.runner_panel = runner_panel
        self.update_preview_callback = update_preview_callback
        self.update_combobox_callback = update_combobox_callback
        self.training_tab_instance = training_tab_instance # Store the TrainingTab instance
        
        self.profile_display = None # Will be scrolledtext widget
        self._suppress_next_popup = False # Prevent startup popup when auto-selecting a profile

    def create_ui(self):
        """Create the profiles panel UI with new buttons and display."""
        section = ttk.LabelFrame(self.parent, text="💾 Training Profiles", style='TLabelframe')
        section.pack(fill=tk.BOTH, expand=True, pady=10, padx=10)
        section.columnconfigure(0, weight=1) # Allow content to expand

        # Profile Selection and Load
        load_frame = ttk.Frame(section)
        load_frame.pack(fill=tk.X, padx=10, pady=5)
        load_frame.columnconfigure(1, weight=1)

        ttk.Label(load_frame, text="Select Profile:", style='Config.TLabel').grid(row=0, column=0, sticky=tk.W, padx=(0, 5))
        self.profile_combobox = ttk.Combobox(
            load_frame,
            textvariable=self.selected_profile_var,
            values=list_profiles(),
            state="readonly",
            width=25,
            font=("Arial", 10)
        )
        self.profile_combobox.grid(row=0, column=1, sticky=tk.EW, padx=(0, 10))
        self.profile_combobox.bind("<<ComboboxSelected>>", self.load_profile_from_gui)

        # Profile Action Buttons
        action_buttons_frame = ttk.Frame(section)
        action_buttons_frame.pack(fill=tk.X, padx=10, pady=5)
        action_buttons_frame.columnconfigure(0, weight=1)
        action_buttons_frame.columnconfigure(1, weight=1)
        action_buttons_frame.columnconfigure(2, weight=1)

        ttk.Button(action_buttons_frame, text="➕ Create New", command=self.create_new_profile, style='Action.TButton').grid(row=0, column=0, sticky=tk.EW, padx=2)
        self.overwrite_button = ttk.Button(action_buttons_frame, text="📝 Overwrite", command=self.overwrite_selected_profile, style='Select.TButton', state=tk.DISABLED)
        self.overwrite_button.grid(row=0, column=1, sticky=tk.EW, padx=2)
        self.delete_button = ttk.Button(action_buttons_frame, text="🗑️ Delete", command=self.delete_selected_profile, style='Select.TButton', state=tk.DISABLED)
        self.delete_button.grid(row=0, column=2, sticky=tk.EW, padx=2)

        # Save current settings to selected profile (explicit overwrite with confirm)
        ttk.Button(action_buttons_frame, text="💾 Save To Profile", command=self.save_to_selected_profile, style='Action.TButton').grid(row=1, column=0, columnspan=3, sticky=tk.EW, padx=2, pady=(6, 0))

        # Profile Name Entry (for Create New)
        create_frame = ttk.Frame(section)
        create_frame.pack(fill=tk.X, padx=10, pady=5)
        create_frame.columnconfigure(1, weight=1)

        ttk.Label(create_frame, text="New Profile Name:", style='Config.TLabel').grid(row=0, column=0, sticky=tk.W, padx=(0, 5))
        profile_name_entry = ttk.Entry(create_frame, textvariable=self.profile_name_var, width=25, font=("Arial", 10))
        profile_name_entry.grid(row=0, column=1, sticky=tk.EW, padx=(0, 10))

        # Profile Details Display
        profile_details_frame = ttk.LabelFrame(section, text="📊 Profile Details", style='TLabelframe')
        profile_details_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        profile_details_frame.columnconfigure(0, weight=1)
        profile_details_frame.rowconfigure(0, weight=1)

        self.profile_display = scrolledtext.ScrolledText(
            profile_details_frame, wrap=tk.WORD, state=tk.DISABLED, font=("Courier", 9),
            bg="#1e1e1e", fg="#d4d4d4", relief='flat', padx=5, pady=5
        )
        self.profile_display.grid(row=0, column=0, sticky='nsew')

        # Initial update of combobox and button states
        self.update_profile_combobox()
        # WO-6x: Refresh on ProfilesChanged
        try:
            self.parent.bind("<<ProfilesChanged>>", lambda e: self.update_profile_combobox())
        except Exception:
            pass

    def load_profile_from_gui(self, event=None):
        """Loads selected profile and updates GUI elements"""
        profile_name = self.selected_profile_var.get()
        if not profile_name:
            return

        try:
            profile_config = load_profile(profile_name)

            # Update config_vars
            self.runner_panel.num_epochs_var.set(profile_config.get("training_runs", 3))
            self.runner_panel.batch_size_var.set(profile_config.get("batch_size", 2))
            self.runner_panel.learning_rate_var.set(profile_config.get("learning_strength", "2e-4"))
            self.model_selection_panel.base_model_var.set(profile_config.get("base_model", "unsloth/Qwen2.5-Coder-1.5B-Instruct"))

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
            # Only show popup when user explicitly selects from the combobox
            if event is not None and not self._suppress_next_popup:
                messagebox.showinfo("Profile Loaded", f"Profile '{profile_name}' loaded successfully.")
            # Reset suppress flag after use
            self._suppress_next_popup = False
            
            # Update profile display
            self.profile_display.config(state=tk.NORMAL)
            self.profile_display.delete(1.0, tk.END)
            self.profile_display.insert(tk.END, json.dumps(profile_config, indent=2))
            self.profile_display.config(state=tk.DISABLED)

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
            "training_runs": self.runner_panel.num_epochs_var.get(),
            "batch_size": self.runner_panel.batch_size_var.get(),
            "learning_strength": self.runner_panel.learning_rate_var.get(),
            "base_model": self.model_selection_panel.base_model_var.get(),
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

    def load_profile_from_gui(self, event=None):
        """Loads selected profile and updates GUI elements (legacy) or applies plan (type)."""
        selected_label = self.selected_profile_var.get()
        if not selected_label or selected_label == "No profiles found":
            return

        try:
            # Determine record
            rec = getattr(self, '_profiles_lookup', {}).get(selected_label)
            if rec and rec.get('kind') == 'type':
                variant_id = rec.get('id')
                if hasattr(self, 'training_tab_instance') and hasattr(self.training_tab_instance, 'apply_plan'):
                    self.training_tab_instance.apply_plan(variant_id=variant_id)
                return
            # Fallback to legacy profile
            profile_name = rec.get('id') if rec else selected_label
            profile_config = load_profile(profile_name)

            # Update Runner Panel settings
            self.runner_panel.num_epochs_var.set(profile_config.get("training_runs", self.runner_panel.num_epochs_var.get()))
            self.runner_panel.batch_size_var.set(profile_config.get("batch_size", self.runner_panel.batch_size_var.get()))
            self.runner_panel.learning_rate_var.set(profile_config.get("learning_strength", self.runner_panel.learning_rate_var.get()))
            self.runner_panel.max_time_var.set(profile_config.get("runner_settings", {}).get("max_time", self.runner_panel.max_time_var.get()))
            self.runner_panel.run_delay_var.set(profile_config.get("runner_settings", {}).get("run_delay", self.runner_panel.run_delay_var.get()))
            self.runner_panel.save_checkpoints_var.set(profile_config.get("runner_settings", {}).get("save_checkpoints", self.runner_panel.save_checkpoints_var.get()))
            self.runner_panel.checkpoint_interval_var.set(profile_config.get("runner_settings", {}).get("checkpoint_interval", self.runner_panel.checkpoint_interval_var.get()))
            self.runner_panel.early_stop_var.set(profile_config.get("runner_settings", {}).get("early_stop", self.runner_panel.early_stop_var.get()))
            self.runner_panel.early_stop_patience_var.set(profile_config.get("runner_settings", {}).get("early_stop_patience", self.runner_panel.early_stop_patience_var.get()))
            self.runner_panel.use_mixed_precision_var.set(profile_config.get("runner_settings", {}).get("use_mixed_precision", self.runner_panel.use_mixed_precision_var.get()))
            self.runner_panel.gradient_accumulation_var.set(profile_config.get("runner_settings", {}).get("gradient_accumulation", self.runner_panel.gradient_accumulation_var.get()))
            self.runner_panel.warmup_steps_var.set(profile_config.get("runner_settings", {}).get("warmup_steps", self.runner_panel.warmup_steps_var.get()))
            self.runner_panel.max_cpu_threads_var.set(profile_config.get("runner_settings", {}).get("max_cpu_threads", self.runner_panel.max_cpu_threads_var.get()))
            self.runner_panel.max_ram_percent_var.set(profile_config.get("runner_settings", {}).get("max_ram_percent", self.runner_panel.max_ram_percent_var.get()))
            self.runner_panel.auto_restart_var.set(profile_config.get("runner_settings", {}).get("auto_restart", self.runner_panel.auto_restart_var.get()))
            # Evaluation automation toggles
            self.runner_panel.auto_eval_baseline_var.set(profile_config.get("runner_settings", {}).get("auto_eval_baseline", self.runner_panel.auto_eval_baseline_var.get()))
            self.runner_panel.auto_eval_post_var.set(profile_config.get("runner_settings", {}).get("auto_eval_post", self.runner_panel.auto_eval_post_var.get()))

            # Update Model Selection Panel settings
            self.model_selection_panel.base_model_var.set(profile_config.get("base_model", self.model_selection_panel.base_model_var.get()))
            self.model_selection_panel.display_model_info() # Refresh model info display

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

            # Apply evaluation preferences (prompts/schemas + toggles)
            eval_prefs = profile_config.get("evaluation_preferences", {})
            try:
                use_prompt = bool(eval_prefs.get("use_system_prompt", False))
                use_schema = bool(eval_prefs.get("use_tool_schema", False))
                # Set runner toggle states
                if hasattr(self.runner_panel, 'use_prompt_for_eval_var'):
                    self.runner_panel.use_prompt_for_eval_var.set(use_prompt)
                if hasattr(self.runner_panel, 'use_schema_for_eval_var'):
                    self.runner_panel.use_schema_for_eval_var.set(use_schema)
                # Set selected names on Training tab
                if hasattr(self.training_tab_instance, 'prompt_selected_var'):
                    sel_prompt = eval_prefs.get("system_prompt") or ""
                    self.training_tab_instance.prompt_selected_var.set(sel_prompt)
                if hasattr(self.training_tab_instance, 'schema_selected_var'):
                    sel_schema = eval_prefs.get("tool_schema") or ""
                    self.training_tab_instance.schema_selected_var.set(sel_schema)
                # Refresh right-side lists so UI reflects groups and selections
                if hasattr(self.training_tab_instance, '_refresh_prompts_list'):
                    self.training_tab_instance._refresh_prompts_list()
                if hasattr(self.training_tab_instance, '_refresh_schemas_list'):
                    self.training_tab_instance._refresh_schemas_list()
            except Exception:
                pass

            self.update_preview_callback()
            messagebox.showinfo("Profile Loaded", f"Profile '{profile_name}' loaded successfully.")
            
            # Display profile details
            self.profile_display.config(state=tk.NORMAL)
            self.profile_display.delete(1.0, tk.END)
            self.profile_display.insert(tk.END, json.dumps(profile_config, indent=2))
            self.profile_display.config(state=tk.DISABLED)

        except FileNotFoundError:
            messagebox.showerror("Error", f"Profile '{profile_name}' not found.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load profile '{profile_name}': {e}")

    def create_new_profile(self):
        """Creates a new profile with the current settings."""
        profile_name = self.profile_name_var.get().strip()
        if not profile_name:
            messagebox.showwarning("Input Error", "Please enter a name for the new profile.")
            return

        if profile_name in list_profiles():
            messagebox.showwarning("Profile Exists", f"Profile '{profile_name}' already exists. Use 'Overwrite' to update it.")
            return

        self._save_current_settings_to_profile(profile_name)
        logger_util.log_message(f"PROFILES: New profile '{profile_name}' created.")
        messagebox.showinfo("Profile Created", f"Profile '{profile_name}' created successfully.")
        self.profile_name_var.set("")
        self.update_profile_combobox()
        self.selected_profile_var.set(profile_name) # Select the newly created profile
        self.load_profile_from_gui() # Display its details

    def overwrite_selected_profile(self):
        """Overwrites the currently selected profile with the current settings."""
        profile_name = self.selected_profile_var.get()
        if not profile_name or profile_name == "No profiles found":
            messagebox.showwarning("No Profile Selected", "Please select a profile to overwrite.")
            return

        if not messagebox.askyesno("Confirm Overwrite", f"Are you sure you want to overwrite profile '{profile_name}' with current settings?"):
            return

        self._save_current_settings_to_profile(profile_name)
        logger_util.log_message(f"PROFILES: Profile '{profile_name}' overwritten.")
        messagebox.showinfo("Profile Overwritten", f"Profile '{profile_name}' overwritten successfully.")
        self.update_profile_combobox()
        self.load_profile_from_gui() # Refresh display

    def delete_selected_profile(self):
        """Deletes the currently selected profile."""
        profile_name = self.selected_profile_var.get()
        if not profile_name or profile_name == "No profiles found":
            messagebox.showwarning("No Profile Selected", "Please select a profile to delete.")
            return

        if not messagebox.askyesno("Confirm Delete", f"Are you sure you want to delete profile '{profile_name}'? This cannot be undone."):
            return

        try:
            profile_path = Path(DATA_DIR) / "profiles" / f"{profile_name}.json"
            if profile_path.exists():
                profile_path.unlink()
                logger_util.log_message(f"PROFILES: Profile '{profile_name}' deleted.")
                messagebox.showinfo("Profile Deleted", f"Profile '{profile_name}' deleted successfully.")
                self.update_profile_combobox()
                self.selected_profile_var.set("") # Clear selection
                self.profile_display.config(state=tk.NORMAL)
                self.profile_display.delete(1.0, tk.END)
                self.profile_display.config(state=tk.DISABLED)
            else:
                messagebox.showerror("Error", f"Profile '{profile_name}' not found on disk.")
        except Exception as e:
            logger_util.log_message(f"PROFILES ERROR: Failed to delete profile '{profile_name}': {e}")
            messagebox.showerror("Error", f"Failed to delete profile '{profile_name}': {e}")

    def _save_current_settings_to_profile(self, profile_name):
        """Helper to gather and save current settings to a profile."""
        current_config = self._build_current_settings_profile_dict()
        try:
            save_profile(profile_name, current_config)
        except Exception as e:
            logger_util.log_message(f"PROFILES ERROR: Failed to save profile '{profile_name}': {e}")
            messagebox.showerror("Error", f"Failed to save profile '{profile_name}': {e}")
            raise # Re-raise to be caught by calling function if needed

    def _build_current_settings_profile_dict(self):
        """Build a dict representing current UI settings suitable for saving as a profile."""
        # Get current selected scripts and JSONL files from the TrainingTab instance
        selected_scripts_data = self.training_tab_instance.get_selected_scripts()

        # Extract categories and subcategories from the selected data
        selected_categories_for_profile = list(set(item['category'] for item in selected_scripts_data['scripts'] + selected_scripts_data['jsonl_files']))
        selected_subcategories_for_profile = {}
        for item in selected_scripts_data['scripts'] + selected_scripts_data['jsonl_files']:
            cat = item['category']
            if cat not in selected_subcategories_for_profile:
                selected_subcategories_for_profile[cat] = []
            # Assuming script_name/file_name is the subcategory for simplicity in this context
            selected_subcategories_for_profile[cat].append(item.get('script', item.get('file')))

        # Gather current configuration
        current_config = {
            "training_runs": self.runner_panel.num_epochs_var.get(),
            "batch_size": self.runner_panel.batch_size_var.get(),
            "learning_strength": self.runner_panel.learning_rate_var.get(),
            "base_model": self.model_selection_panel.base_model_var.get(),
            "categories": selected_categories_for_profile,
            "subcategories": selected_subcategories_for_profile,
            # Add all runner panel settings
            "runner_settings": {
                "max_time": self.runner_panel.max_time_var.get(),
                "run_delay": self.runner_panel.run_delay_var.get(),
                "save_checkpoints": self.runner_panel.save_checkpoints_var.get(),
                "checkpoint_interval": self.runner_panel.checkpoint_interval_var.get(),
                "early_stop": self.runner_panel.early_stop_var.get(),
                "early_stop_patience": self.runner_panel.early_stop_patience_var.get(),
                "use_mixed_precision": self.runner_panel.use_mixed_precision_var.get(),
                "gradient_accumulation": self.runner_panel.gradient_accumulation_var.get(),
                "warmup_steps": self.runner_panel.warmup_steps_var.get(),
                "max_cpu_threads": self.runner_panel.max_cpu_threads_var.get(),
                "max_ram_percent": self.runner_panel.max_ram_percent_var.get(),
                "auto_restart": self.runner_panel.auto_restart_var.get(),
                # Evaluation automation toggles
                "auto_eval_baseline": self.runner_panel.auto_eval_baseline_var.get(),
                "auto_eval_post": self.runner_panel.auto_eval_post_var.get()
            },
            # Optional evaluation preferences (for future application in Models → Evaluation)
            "evaluation_preferences": {
                # Pull from Runner toggles and right-side selections where available
                "use_system_prompt": getattr(self.runner_panel, 'use_prompt_for_eval_var', tk.BooleanVar(value=False)).get() if hasattr(self, 'runner_panel') else False,
                "system_prompt": getattr(self.training_tab_instance, 'prompt_selected_var', tk.StringVar(value="")).get() if hasattr(self, 'training_tab_instance') else None,
                "use_tool_schema": getattr(self.runner_panel, 'use_schema_for_eval_var', tk.BooleanVar(value=False)).get() if hasattr(self, 'runner_panel') else False,
                "tool_schema": getattr(self.training_tab_instance, 'schema_selected_var', tk.StringVar(value="")).get() if hasattr(self, 'training_tab_instance') else None,
                "suite_strategy": "trained_categories"  # or "all"
            }
        }
        return current_config

    def update_profile_combobox(self):
        """Refresh the list with legacy + type profiles labeled accordingly."""
        try:
            records = list_all_training_profiles() or []
        except Exception:
            records = []
        self._profiles_lookup = {}
        labels = []
        for rec in records:
            pid = rec.get('id'); kind = rec.get('kind')
            label = f"{pid}  ({kind})"
            labels.append(label)
            self._profiles_lookup[label] = rec
        self.profile_combobox['values'] = labels

        current = self.selected_profile_var.get()
        if current in labels:
            self.profile_combobox.set(current)
            # Only legacy profiles can be overwritten directly here
            is_legacy = (self._profiles_lookup.get(current, {}).get('kind') == 'legacy')
            self.overwrite_button.config(state=(tk.NORMAL if is_legacy else tk.DISABLED))
            self.delete_button.config(state=tk.NORMAL)
        elif labels:
            self.selected_profile_var.set(labels[0])
            is_legacy = (self._profiles_lookup.get(labels[0], {}).get('kind') == 'legacy')
            self.overwrite_button.config(state=(tk.NORMAL if is_legacy else tk.DISABLED))
            self.delete_button.config(state=tk.NORMAL)
            self._suppress_next_popup = True
            self.load_profile_from_gui()
        else:
            self.selected_profile_var.set("No profiles found")
            self.overwrite_button.config(state=tk.DISABLED)
            self.delete_button.config(state=tk.DISABLED)
            self.profile_display.config(state=tk.NORMAL)
            self.profile_display.delete(1.0, tk.END)
            self.profile_display.config(state=tk.DISABLED)

    def save_to_selected_profile(self):
        """Saves current settings to the currently selected profile with confirmation."""
        profile_name = self.selected_profile_var.get()
        if not profile_name or profile_name == "No profiles found":
            messagebox.showwarning("No Profile Selected", "Please select a profile to save to.")
            return
        # Load existing profile and build new one for diff
        try:
            existing = load_profile(profile_name)
        except Exception:
            existing = {}
        updated = self._build_current_settings_profile_dict()

        # Summarize differences
        summary_lines = self._summarize_profile_changes(existing, updated)
        summary_text = "\n".join(summary_lines) if summary_lines else "No changes detected."
        confirm_text = (
            f"You are about to overwrite profile: '{profile_name}'.\n\n"
            f"Changes:\n{summary_text}\n\nProceed?"
        )
        if not messagebox.askyesno("Confirm Overwrite", confirm_text):
            return
        try:
            # Save
            save_profile(profile_name, updated)
            logger_util.log_message(f"PROFILES: Profile '{profile_name}' saved via Save To Profile.")
            messagebox.showinfo("Profile Saved", f"Profile '{profile_name}' updated successfully.")
            self.update_profile_combobox()
            self.load_profile_from_gui()  # Refresh display
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save profile '{profile_name}': {e}")

    def _summarize_profile_changes(self, old: dict, new: dict):
        lines = []
        def add(line):
            lines.append(f" • {line}")
        # Simple top-level fields
        for k in ("base_model", "training_runs", "batch_size", "learning_strength"):
            ov, nv = old.get(k), new.get(k)
            if ov != nv:
                add(f"{k}: {ov} → {nv}")
        # Categories
        old_c = set(old.get("categories", []) or [])
        new_c = set(new.get("categories", []) or [])
        added_c = sorted(list(new_c - old_c))
        removed_c = sorted(list(old_c - new_c))
        if added_c:
            add(f"categories: +{', '.join(added_c)}")
        if removed_c:
            add(f"categories: -{', '.join(removed_c)}")
        # Subcategories (summary per category)
        old_sc = old.get("subcategories", {}) or {}
        new_sc = new.get("subcategories", {}) or {}
        for cat in sorted(set(old_sc.keys()) | set(new_sc.keys())):
            old_set = set(old_sc.get(cat, []) or [])
            new_set = set(new_sc.get(cat, []) or [])
            add_sc = sorted(list(new_set - old_set))
            rem_sc = sorted(list(old_set - new_set))
            changes = []
            if add_sc:
                changes.append("+" + ", ".join(add_sc))
            if rem_sc:
                changes.append("-" + ", ".join(rem_sc))
            if changes:
                add(f"subcategories[{cat}]: {'; '.join(changes)}")
        # Runner settings
        old_rs = old.get("runner_settings", {}) or {}
        new_rs = new.get("runner_settings", {}) or {}
        changed_rs = [k for k in new_rs.keys() if old_rs.get(k) != new_rs.get(k)]
        if changed_rs:
            add(f"runner_settings changed: {', '.join(sorted(changed_rs))}")
        # Evaluation preferences
        old_ep = old.get("evaluation_preferences", {}) or {}
        new_ep = new.get("evaluation_preferences", {}) or {}
        changed_ep = [k for k in new_ep.keys() if old_ep.get(k) != new_ep.get(k)]
        if changed_ep:
            add(f"evaluation_preferences changed: {', '.join(sorted(changed_ep))}")
        return lines
