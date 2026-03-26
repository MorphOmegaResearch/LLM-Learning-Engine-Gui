# [SYSTEM: GUI | VERSION: 1.9f | STATUS: ACTIVE]
"""
Dataset Panel - Training dataset selection and management
"""

import tkinter as tk
from tkinter import ttk, messagebox
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from config import (
    get_category_info,
    create_category_folder,
    create_subcategory_file,
    TRAINING_DATA_DIR,
)


class DatasetPanel:
    """Panel for selecting training datasets"""

    def __init__(self, parent, style, category_vars, subcategory_vars, update_preview_callback, refresh_callback):
        self.parent = parent
        self.style = style
        self.category_vars = category_vars
        self.subcategory_vars = subcategory_vars
        self.update_preview_callback = update_preview_callback
        self.refresh_callback = refresh_callback

        self.category_info = get_category_info()
        self.new_category_name_var = tk.StringVar()
        self.new_subcategory_name_var = tk.StringVar()
        self.parent_category_var = tk.StringVar(value="Tools")

    def create_ui(self):
        """Create the dataset selection panel UI"""
        # Scrollable frame for categories
        canvas = tk.Canvas(self.parent, bg="#2b2b2b", highlightthickness=0)
        scrollbar = ttk.Scrollbar(self.parent, orient="vertical", command=canvas.yview)
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

        # Category Management
        category_mgmt_frame = ttk.Frame(self.parent, style='Category.TFrame')
        category_mgmt_frame.pack(fill=tk.X, pady=(10, 5), padx=5)

        ttk.Label(category_mgmt_frame, text="New Category:", style='Config.TLabel').pack(side=tk.LEFT, padx=(0, 5))
        new_category_entry = ttk.Entry(category_mgmt_frame, textvariable=self.new_category_name_var, width=15, font=("Arial", 10))
        new_category_entry.pack(side=tk.LEFT, padx=(0, 5))
        create_cat_btn = ttk.Button(category_mgmt_frame, text="➕ Create", command=self.create_new_category, style='Select.TButton')
        create_cat_btn.pack(side=tk.LEFT)

        # Subcategory Management
        subcategory_mgmt_frame = ttk.Frame(self.parent, style='Category.TFrame')
        subcategory_mgmt_frame.pack(fill=tk.X, pady=(5, 10), padx=5)

        ttk.Label(subcategory_mgmt_frame, text="New Subcategory:", style='Config.TLabel').pack(side=tk.LEFT, padx=(0, 5))
        new_subcategory_entry = ttk.Entry(subcategory_mgmt_frame, textvariable=self.new_subcategory_name_var, width=15, font=("Arial", 10))
        new_subcategory_entry.pack(side=tk.LEFT, padx=(0, 5))

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
        cat_frame = ttk.Frame(parent, style='Category.TFrame')
        cat_frame.pack(fill=tk.X, pady=5, padx=5)

        # Category checkbox
        var = tk.BooleanVar(value=True if total > 0 else False)
        self.category_vars[category] = var

        cat_check = ttk.Checkbutton(
            cat_frame,
            text=f"{category.replace('_', ' ')} ({total} examples)",
            variable=var,
            style='Category.TCheckbutton',
            command=lambda c=category: self.toggle_category(c)
        )
        cat_check.pack(anchor=tk.W, padx=10, pady=0)

        # Subcategories
        if info["subcategories"]:
            subcat_frame = ttk.Frame(cat_frame, style='Subcategory.TFrame')
            subcat_frame.pack(fill=tk.X, padx=20, pady=(0, 8))

            for subcat_name, subcat_info in sorted(info["subcategories"].items()):
                count = subcat_info["count"]
                display_name = subcat_name.replace('_', ' ').title()

                var = tk.BooleanVar(value=True)
                self.subcategory_vars[(category, subcat_name)] = var

                sub_check = ttk.Checkbutton(
                    subcat_frame,
                    text=f"  {display_name} ({count})",
                    variable=var,
                    style='Subcategory.TCheckbutton',
                    command=self.update_preview_callback
                )
                sub_check.pack(anchor=tk.W, pady=2)

    def toggle_category(self, category):
        """Toggle all subcategories when category is toggled"""
        enabled = self.category_vars[category].get()

        for (cat, subcat), var in self.subcategory_vars.items():
            if cat == category:
                var.set(enabled)

        self.update_preview_callback()

    def create_new_category(self):
        """Creates a new category folder"""
        category_name = self.new_category_name_var.get().strip()
        if not category_name:
            messagebox.showwarning("Input Error", "Please enter a name for the new category.")
            return

        try:
            create_category_folder(category_name)
            messagebox.showinfo("Success", f"Category '{category_name}' created.")
            self.new_category_name_var.set("")
            if self.refresh_callback:
                self.refresh_callback()
        except FileExistsError:
            messagebox.showerror("Error", f"Category '{category_name}' already exists.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to create category '{category_name}': {e}")

    def create_new_subcategory(self):
        """Creates a new subcategory file within a selected category"""
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
            if self.refresh_callback:
                self.refresh_callback()
        except FileNotFoundError:
            messagebox.showerror("Error", f"Parent category '{parent_category}' not found.")
        except FileExistsError:
            messagebox.showerror("Error", f"Subcategory '{subcategory_name}.jsonl' already exists in '{parent_category}'.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to create subcategory '{subcategory_name}': {e}")

    def refresh(self):
        """Refresh the dataset panel"""
        # Clear existing category panel content
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()

        # Re-fetch category info
        self.category_info = get_category_info()

        # Re-create category checkboxes
        for category in sorted(self.category_info.keys()):
            self.create_category_section(self.scrollable_frame, category)

        # Update parent category combobox options
        self.parent_category_combobox['values'] = [cat for cat in self.category_info.keys()]
        if self.parent_category_var.get() not in self.category_info.keys():
            if self.category_info.keys():
                self.parent_category_var.set(list(self.category_info.keys())[0])
        self.update_preview_callback()

    def get_selected_datasets(self):
        """Returns a list of absolute paths to selected .jsonl files."""
        selected_files = []
        training_data_root = TRAINING_DATA_DIR

        for category_name, category_var in self.category_vars.items():
            if category_var.get():
                # Check if any subcategories are selected within this category
                subcategories_selected_in_category = False
                for (cat, subcat_name), subcat_var in self.subcategory_vars.items():
                    if cat == category_name and subcat_var.get():
                        subcategories_selected_in_category = True
                        # Add specific selected subcategory file
                        file_path = training_data_root / category_name / f"{subcat_name}.jsonl"
                        if file_path.exists():
                            selected_files.append(str(file_path))
                
                # If category is selected but no specific subcategories are, include all .jsonl in category
                if not subcategories_selected_in_category:
                    category_dir = training_data_root / category_name
                    if category_dir.is_dir():
                        for jsonl_file in category_dir.glob("*.jsonl"):
                            selected_files.append(str(jsonl_file))
        return selected_files
