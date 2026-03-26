"""
Category Manager Panel - Manage training categories and scripts
"""

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, simpledialog
import subprocess
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from config import DATA_DIR, get_category_info


class CategoryManagerPanel:
    """Panel for managing training categories and their scripts"""

    def __init__(self, parent, style, refresh_callback=None):
        super().__init__()
        # print(f"DEBUG: CategoryManagerPanel instance created with ID: {id(self)}") # Gated debug
        self.parent = parent
        self.style = style
        self.refresh_callback = refresh_callback

        # Category manager variables
        self.selected_category_for_edit = tk.StringVar()
        self.current_script_path = None
        self.current_file_path = None  # For tracking selected files
        self.current_file_type = None  # 'script' or 'jsonl'
        self.category_info = get_category_info()

    def create_ui(self):
        """Create the category manager panel UI"""
        self.parent.columnconfigure(0, weight=0)
        self.parent.columnconfigure(1, weight=1)
        self.parent.rowconfigure(0, weight=1)

        # Left side: JSONL file manager (smaller display)
        jsonl_manager_frame = ttk.Frame(self.parent, style='Category.TFrame')
        jsonl_manager_frame.grid(row=0, column=0, sticky=tk.NSEW, padx=10, pady=10)
        jsonl_manager_frame.columnconfigure(0, weight=1)
        jsonl_manager_frame.rowconfigure(1, weight=1)

        ttk.Label(jsonl_manager_frame, text="📄 Training Data Files",
                 font=("Arial", 12, "bold"), style='CategoryPanel.TLabel').grid(
            row=0, column=0, pady=5, sticky=tk.W, padx=5
        )

        # JSONL files list
        jsonl_canvas = tk.Canvas(jsonl_manager_frame, bg="#2b2b2b", highlightthickness=0, width=250)
        jsonl_scrollbar = ttk.Scrollbar(jsonl_manager_frame, orient="vertical", command=jsonl_canvas.yview)
        self.jsonl_list_frame = ttk.Frame(jsonl_canvas)

        self.jsonl_list_frame.bind(
            "<Configure>",
            lambda e: jsonl_canvas.configure(scrollregion=jsonl_canvas.bbox("all"))
        )

        jsonl_canvas_window = jsonl_canvas.create_window((0, 0), window=self.jsonl_list_frame, anchor="nw")
        jsonl_canvas.configure(yscrollcommand=jsonl_scrollbar.set)

        jsonl_canvas.grid(row=1, column=0, sticky=tk.NSEW, pady=5)
        jsonl_scrollbar.grid(row=1, column=1, sticky=tk.NS)

        jsonl_canvas.bind("<Configure>", lambda e: jsonl_canvas.itemconfig(jsonl_canvas_window, width=e.width))

        # JSONL file management buttons
        jsonl_buttons_frame = ttk.Frame(jsonl_manager_frame)
        jsonl_buttons_frame.grid(row=2, column=0, columnspan=2, sticky=tk.EW, padx=5, pady=10)

        ttk.Button(
            jsonl_buttons_frame,
            text="👁️ View",
            command=self.view_jsonl_file,
            style='Select.TButton'
        ).pack(fill=tk.X, pady=2)

        ttk.Button(
            jsonl_buttons_frame,
            text="✏️ Edit",
            command=self.edit_jsonl_file,
            style='Select.TButton'
        ).pack(fill=tk.X, pady=2)

        ttk.Button(
            jsonl_buttons_frame,
            text="➕ New JSONL",
            command=self.create_new_jsonl_dialog,
            style='Action.TButton'
        ).pack(fill=tk.X, pady=2)

        ttk.Button(
            jsonl_buttons_frame,
            text="🗑️ Delete",
            command=self.delete_jsonl_dialog,
            style='Select.TButton'
        ).pack(fill=tk.X, pady=2)

        # Right side: Category display and editor (larger display)
        editor_frame = ttk.Frame(self.parent, style='Category.TFrame')
        editor_frame.grid(row=0, column=1, sticky=tk.NSEW, padx=10, pady=10)
        editor_frame.columnconfigure(0, weight=1)
        editor_frame.rowconfigure(2, weight=1)

        # Category selector header
        header_frame = ttk.Frame(editor_frame)
        header_frame.grid(row=0, column=0, sticky=tk.EW, padx=5, pady=5)
        header_frame.columnconfigure(1, weight=1)

        ttk.Label(header_frame, text="📂 Category:",
                 font=("Arial", 11, "bold"), style='CategoryPanel.TLabel').grid(
            row=0, column=0, sticky=tk.W, padx=(0, 10)
        )

        # Category dropdown
        self.category_dropdown = ttk.Combobox(
            header_frame,
            textvariable=self.selected_category_for_edit,
            state='readonly',
            font=("Arial", 10),
            width=30
        )
        self.category_dropdown.grid(row=0, column=1, sticky=tk.W)
        self.category_dropdown.bind('<<ComboboxSelected>>', lambda e: self.on_category_selected())

        # Category management buttons
        cat_mgmt_frame = ttk.Frame(header_frame)
        cat_mgmt_frame.grid(row=0, column=2, sticky=tk.E, padx=(10, 0))

        ttk.Button(
            cat_mgmt_frame,
            text="➕ New Category",
            command=self.create_new_category_dialog,
            style='Action.TButton'
        ).pack(side=tk.LEFT, padx=2)

        ttk.Button(
            cat_mgmt_frame,
            text="📁 Open Folder",
            command=self.open_category_folder,
            style='Select.TButton'
        ).pack(side=tk.LEFT, padx=2)

        # Category info display
        info_frame = ttk.Frame(editor_frame)
        info_frame.grid(row=1, column=0, sticky=tk.EW, padx=5, pady=5)

        self.category_info_label = ttk.Label(
            info_frame,
            text="Select a category to view details",
            font=("Arial", 9),
            foreground='#888888'
        )
        self.category_info_label.pack(side=tk.LEFT)

        # File content viewer/editor
        viewer_label_frame = ttk.Frame(editor_frame)
        viewer_label_frame.grid(row=2, column=0, sticky=tk.EW, padx=5, pady=(10, 0))

        self.viewer_title_label = ttk.Label(
            viewer_label_frame,
            text="📝 File Viewer",
            font=("Arial", 11, "bold"),
            style='CategoryPanel.TLabel'
        )
        self.viewer_title_label.pack(side=tk.LEFT)

        self.file_name_label = ttk.Label(
            viewer_label_frame,
            text="",
            font=("Arial", 9),
            foreground='#61dafb'
        )
        self.file_name_label.pack(side=tk.LEFT, padx=(10, 0))

        # Content editor
        self.content_editor = scrolledtext.ScrolledText(
            editor_frame,
            font=("Courier", 9),
            wrap=tk.WORD,
            relief='flat',
            borderwidth=0,
            highlightthickness=0,
            bg='#1e1e1e',
            fg='#ffffff'
        )
        self.content_editor.grid(row=3, column=0, sticky=tk.NSEW, padx=5, pady=5)

        # Editor buttons
        editor_buttons_frame = ttk.Frame(editor_frame)
        editor_buttons_frame.grid(row=4, column=0, sticky=tk.EW, padx=5, pady=5)

        ttk.Button(
            editor_buttons_frame,
            text="💾 Save",
            command=self.save_content,
            style='Action.TButton'
        ).pack(side=tk.LEFT, padx=5)

        ttk.Button(
            editor_buttons_frame,
            text="🔄 Reload",
            command=self.reload_content,
            style='Select.TButton'
        ).pack(side=tk.LEFT, padx=5)

        ttk.Button(
            editor_buttons_frame,
            text="❌ Clear",
            command=lambda: self.content_editor.delete(1.0, tk.END),
            style='Select.TButton'
        ).pack(side=tk.LEFT, padx=5)

        # Variables to track current file
        self.current_file_path = None
        self.current_file_type = None  # 'jsonl' or 'script'

        # Now populate dropdown after all UI elements are created
        self.populate_category_dropdown()

    def populate_category_dropdown(self):
        """Populate the category dropdown"""
        categories = sorted(self.category_info.keys())
        self.category_dropdown['values'] = categories
        if categories:
            self.category_dropdown.current(0)
            self.on_category_selected()

    def on_category_selected(self):
        """Handle category selection"""
        category_name = self.selected_category_for_edit.get()
        if not category_name:
            return

        # Update category info display
        info = self.category_info.get(category_name, {})
        total = info.get("total_examples", 0)
        file_count = len(info.get("files", []))

        self.category_info_label.config(
            text=f"{total} examples across {file_count} JSONL file(s)"
        )

        # Populate file list
        self.populate_file_list(category_name)

        # Automatically select train.py if it exists (Gated debug)
        # category_path = DATA_DIR.parent / "Training_Data-Sets" / category_name
        # train_script_path = category_path / "train.py"
        # if train_script_path.exists():
        #     print(f"DEBUG: on_category_selected: Automatically selecting {train_script_path.name}")
        #     self.select_script_file(train_script_path)

    def populate_file_list(self, category_name):
        """Populate the file list for selected category with .jsonl and .py files"""
        # Clear existing list
        for widget in self.jsonl_list_frame.winfo_children():
            widget.destroy()

        # Get category folder
        category_path = DATA_DIR.parent / "Training_Data-Sets" / category_name

        if not category_path.exists():
            ttk.Label(
                self.jsonl_list_frame,
                text="Category folder not found",
                style='Config.TLabel'
            ).pack(padx=10, pady=10)
            return

        # Find all .py and .jsonl files in category
        script_files = list(category_path.glob("*.py"))
        jsonl_files = list(category_path.glob("*.jsonl"))

        all_files = sorted(script_files + jsonl_files)

        if not all_files:
            ttk.Label(
                self.jsonl_list_frame,
                text="No training files found\nClick ➕ New JSONL or create a .py script",
                style='Config.TLabel',
                justify=tk.CENTER
            ).pack(padx=10, pady=20)
            return

        # Add file buttons
        for file_path in all_files:
            btn_frame = ttk.Frame(self.jsonl_list_frame)
            btn_frame.pack(fill=tk.X, pady=2, padx=5)

            if file_path.suffix == '.py':
                print(f"DEBUG: populate_file_list: Creating .py button for {file_path.name}")
                btn = ttk.Button(
                    btn_frame,
                    text=f"🐍 {file_path.name}",
                    command=lambda f=file_path: self.select_script_file(f),
                    style='Select.TButton'
                )
            elif file_path.suffix == '.jsonl':
                # Count examples in file
                try:
                    with open(file_path, 'r') as f:
                        count = sum(1 for _ in f)
                except:
                    count = 0
                btn = ttk.Button(
                    btn_frame,
                    text=f"📄 {file_path.name}\n({count} examples)",
                    command=lambda f=file_path: self.select_jsonl_file(f),
                    style='Select.TButton'
                )
            else:
                continue # Skip other file types

            btn.pack(fill=tk.X)

    def select_script_file(self, script_path):
        print(f"DEBUG: select_script_file called with script_path={script_path} - BUTTON CLICK REGISTERED!")
        """Select a script file for viewing/editing"""
        self.current_file_path = script_path
        self.current_file_type = 'script'
        # Auto-select the category from the script path
        category_name = script_path.parent.name
        self.selected_category_for_edit.set(category_name)
        print(f"DEBUG: select_script_file: Set category='{category_name}', file_path={self.current_file_path}, type={self.current_file_type}")

        # Update label to show selection
        label_text = f"🐍 {script_path.name} ✅ SELECTED"
        self.file_name_label.config(text=label_text)
        # Optionally load content into editor immediately
        try:
            with open(self.current_file_path, 'r') as f:
                content = f.read()
            self.content_editor.config(state=tk.NORMAL)
            self.content_editor.delete(1.0, tk.END)
            self.content_editor.insert(1.0, content)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load script: {e}")

    def select_jsonl_file(self, jsonl_path):
        """Select a JSONL file for viewing/editing"""
        self.current_file_path = jsonl_path
        self.current_file_type = 'jsonl'
        self.file_name_label.config(text=f"📄 {jsonl_path.name}")

    def view_jsonl_file(self):
        """View the selected JSONL file (formatted)"""
        if not self.current_file_path or self.current_file_type != 'jsonl':
            messagebox.showwarning("No File", "Please select a JSONL file first.")
            return

        try:
            import json
            with open(self.current_file_path, 'r') as f:
                content = f.read()

            # Format as readable JSON
            formatted = ""
            for line_num, line in enumerate(content.strip().split('\n'), 1):
                if line.strip():
                    try:
                        data = json.loads(line)
                        formatted += f"=== Example {line_num} ===\n"
                        formatted += json.dumps(data, indent=2)
                        formatted += "\n\n"
                    except json.JSONDecodeError:
                        formatted += f"=== Example {line_num} (INVALID JSON) ===\n"
                        formatted += line + "\n\n"

            self.content_editor.delete(1.0, tk.END)
            self.content_editor.insert(1.0, formatted)
            self.content_editor.config(state=tk.DISABLED)  # Read-only for viewing

        except Exception as e:
            messagebox.showerror("Error", f"Failed to view file: {e}")

    def edit_jsonl_file(self):
        """Edit the selected JSONL file (raw)"""
        if not self.current_file_path or self.current_file_type != 'jsonl':
            messagebox.showwarning("No File", "Please select a JSONL file first.")
            return

        try:
            with open(self.current_file_path, 'r') as f:
                content = f.read()

            self.content_editor.config(state=tk.NORMAL)  # Enable editing
            self.content_editor.delete(1.0, tk.END)
            self.content_editor.insert(1.0, content)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load file: {e}")

    def save_content(self):
        """Save the current file content"""
        if not self.current_file_path:
            messagebox.showwarning("No File", "No file selected to save.")
            return

        content = self.content_editor.get(1.0, tk.END)

        try:
            # Validate JSONL format if it's a JSONL file
            if self.current_file_type == 'jsonl':
                import json
                for line_num, line in enumerate(content.strip().split('\n'), 1):
                    if line.strip():
                        try:
                            json.loads(line)
                        except json.JSONDecodeError as e:
                            if not messagebox.askyesno(
                                "Invalid JSON",
                                "Line {line_num} has invalid JSON:\n{str(e)}\n\nSave anyway?"
                            ):
                                return

            with open(self.current_file_path, 'w') as f:
                f.write(content)

            messagebox.showinfo("Saved", f"File saved: {self.current_file_path.name}")

            # Refresh the file list
            category_name = self.selected_category_for_edit.get()
            if category_name:
                self.populate_jsonl_list(category_name)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to save file: {e}")

    def reload_content(self):
        """Reload the current file from disk"""
        if not self.current_file_path:
            messagebox.showwarning("No File", "No file selected to reload.")
            return

        if self.current_file_type == 'jsonl':
            self.edit_jsonl_file()

    def create_new_jsonl_dialog(self):
        """Create a new JSONL training data file"""
        category_name = self.selected_category_for_edit.get()
        if not category_name:
            messagebox.showwarning("No Category", "Please select a category first.")
            return

        file_name = simpledialog.askstring(
            "New JSONL File",
            "Enter file name (without .jsonl):"
        )
        if not file_name:
            return

        # Add .jsonl extension if not present
        if not file_name.endswith('.jsonl'):
            file_name += '.jsonl'

        category_path = DATA_DIR.parent / "Training_Data-Sets" / category_name
        file_path = category_path / file_name

        if file_path.exists():
            messagebox.showerror("Error", f"File '{file_name}' already exists.")
            return

        try:
            # Create with example template
            example_content = '''{{"messages": [{{"role": "user", "content": "Example prompt"}}, {{"role": "assistant", "content": "Example response"}}], "scenario": "example"}}
'''
            category_path.mkdir(parents=True, exist_ok=True)
            with open(file_path, 'w') as f:
                f.write(example_content)

            messagebox.showinfo("Created", f"JSONL file '{file_name}' created with template.")
            self.populate_file_list(category_name)
            self.select_jsonl_file(file_path)
            self.edit_jsonl_file()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to create file: {e}")

    def delete_jsonl_dialog(self):
        """Delete the selected JSONL file"""
        if not self.current_file_path or self.current_file_type != 'jsonl':
            messagebox.showwarning("No File", "Please select a JSONL file to delete.")
            return

        file_name = self.current_file_path.name

        if messagebox.askyesno(
            "Confirm Delete",
            f"Delete '{file_name}'?\n\nThis cannot be undone!"
        ):
            try:
                self.current_file_path.unlink()
                self.current_file_path = None
                self.current_file_type = None
                self.content_editor.delete(1.0, tk.END)
                self.file_name_label.config(text="")

                category_name = self.selected_category_for_edit.get()
                if category_name:
                    self.populate_file_list(category_name)

            except Exception as e:
                messagebox.showerror("Error", f"Failed to delete file: {e}")

    def create_new_category_dialog(self):
        """Create a new category with dialog"""
        from config import create_category_folder

        category_name = simpledialog.askstring("New Category", "Enter category name:")
        if category_name:
            try:
                create_category_folder(category_name)
                messagebox.showinfo("Success", f"Category '{category_name}' created.")
                self.category_info = get_category_info()
                self.populate_category_dropdown()
                if self.refresh_callback:
                    self.refresh_callback()
            except FileExistsError:
                messagebox.showerror("Error", f"Category '{category_name}' already exists.")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to create category: {e}")

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

    def refresh(self):
        """Refresh category dropdown and list"""
        self.category_info = get_category_info()
        self.populate_category_dropdown()

    def get_selected_category(self):
        """Returns the currently selected category name."""
        category = self.selected_category_for_edit.get()
        print(f"DEBUG: get_selected_category returning: '{category}'")
        return category

    def get_selected_script(self):
        """Returns the name of the currently selected script file, if any."""
        script = ""
        if self.current_file_path and self.current_file_type == 'script':
            script = self.current_file_path.name
        print(f"DEBUG: get_selected_script returning: '{script}' (file_path={self.current_file_path}, type={self.current_file_type})")
        return script
