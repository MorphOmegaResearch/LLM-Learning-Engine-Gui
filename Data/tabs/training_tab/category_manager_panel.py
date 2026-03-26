"""
Category Manager Panel - Manage training categories and scripts
"""

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, simpledialog
import subprocess
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from config import DATA_DIR, get_category_info, SEMANTIC_DATA_DIR, create_subcategory_file, create_script_file, create_prompt_file, create_schema_file, PROMPTS_DIR, SCHEMAS_DIR, list_prompt_categories, list_schema_categories
from config import list_system_prompts, load_system_prompt, list_tool_schemas, load_tool_schema


class CategoryManagerPanel:
    """Panel for managing training categories, prompts, and schemas via sub-tabs"""

    def __init__(self, parent, style, refresh_callback=None, training_tab_instance=None):
        super().__init__()
        # print(f"DEBUG: CategoryManagerPanel instance created with ID: {id(self)}") # Gated debug
        self.parent = parent
        self.style = style
        self.refresh_callback = refresh_callback
        self.training_tab_instance = training_tab_instance

        # Category manager variables
        self.selected_category_for_edit = tk.StringVar()
        self.current_script_path = None
        self.current_file_path = None  # For tracking selected files
        self.current_file_type = None  # 'script' or 'jsonl'
        self.category_info = get_category_info()

    def create_ui(self):
        """Create the redesigned Script Manager with three sub-tabs: Scripts, Prompts, Schemas"""
        # Container
        container = ttk.Frame(self.parent, style='Category.TFrame')
        container.grid(row=0, column=0, sticky=tk.NSEW)
        container.columnconfigure(0, weight=1)
        container.rowconfigure(1, weight=1)

        # Sub-tab buttons at the top
        tabs_bar = ttk.Frame(container)
        tabs_bar.grid(row=0, column=0, sticky=tk.EW, padx=10, pady=(5, 0))
        self._active_subtab = tk.StringVar(value='scripts')
        btn_opts = dict(style='Select.TButton')
        self._btn_scripts = ttk.Button(tabs_bar, text='📜 Training Scripts', command=lambda: self._show_subtab('scripts'), **btn_opts)
        self._btn_prompts = ttk.Button(tabs_bar, text='🧠 Prompts', command=lambda: self._show_subtab('prompts'), **btn_opts)
        self._btn_schemas = ttk.Button(tabs_bar, text='🧩 Schemas', command=lambda: self._show_subtab('schemas'), **btn_opts)
        self._btn_scripts.pack(side=tk.LEFT, padx=(0,6))
        self._btn_prompts.pack(side=tk.LEFT, padx=6)
        self._btn_schemas.pack(side=tk.LEFT, padx=6)

        # Content area holds three frames
        content = ttk.Frame(container)
        content.grid(row=1, column=0, sticky=tk.NSEW)
        content.columnconfigure(0, weight=1)
        content.rowconfigure(0, weight=1)

        self.scripts_frame = ttk.Frame(content, style='Category.TFrame')
        self.prompts_frame = ttk.Frame(content, style='Category.TFrame')
        self.schemas_frame = ttk.Frame(content, style='Category.TFrame')
        for f in (self.scripts_frame, self.prompts_frame, self.schemas_frame):
            f.grid(row=0, column=0, sticky=tk.NSEW)

        # Build each subtab UI
        self._build_scripts_ui(self.scripts_frame)
        self._build_prompts_ui(self.prompts_frame)
        self._build_schemas_ui(self.schemas_frame)

        # Show default
        self._show_subtab('scripts')

        # Variables for tracking selected files
        self.current_file_path = None
        self.current_file_type = None

        # Keep category info updated
        self.populate_category_dropdown()

    def _show_subtab(self, name: str):
        self._active_subtab.set(name)
        self.scripts_frame.tkraise() if name == 'scripts' else None
        self.prompts_frame.tkraise() if name == 'prompts' else None
        self.schemas_frame.tkraise() if name == 'schemas' else None

    # --- SCRIPTS SUBTAB ---
    def _build_scripts_ui(self, parent):
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(1, weight=1)

        # Editor and bottom actions only; no left listing (use right-side Training tab selection)
        right = ttk.Frame(parent, style='Category.TFrame')
        right.grid(row=0, column=0, sticky=tk.NSEW, padx=10, pady=10)
        right.columnconfigure(0, weight=1)
        right.rowconfigure(1, weight=1)

        # Viewer header
        header = ttk.Frame(right)
        header.grid(row=0, column=0, sticky=tk.EW)
        self.viewer_title_label = ttk.Label(header, text="📝 File Viewer", font=("Arial", 11, "bold"), style='CategoryPanel.TLabel')
        self.viewer_title_label.pack(side=tk.LEFT)
        self.file_name_label = ttk.Label(header, text="", font=("Arial", 9), foreground='#61dafb')
        self.file_name_label.pack(side=tk.LEFT, padx=(10,0))

        # Editor
        self.content_editor = scrolledtext.ScrolledText(right, font=("Courier", 9), wrap=tk.WORD, relief='flat', borderwidth=0, highlightthickness=0, bg='#1e1e1e', fg='#ffffff')
        self.content_editor.grid(row=1, column=0, sticky=tk.NSEW, padx=5, pady=5)

        # Editor buttons
        eb = ttk.Frame(right)
        eb.grid(row=2, column=0, sticky=tk.EW)
        # This bar is now empty, but we keep it for layout consistency

        # Bottom actions
        bottom = ttk.Frame(parent)
        bottom.grid(row=2, column=0, sticky=tk.EW, padx=10, pady=(0,10))
        ttk.Button(bottom, text="➕ New JSONL", command=self.create_new_jsonl_dialog, style='Action.TButton').pack(side=tk.LEFT, padx=2)
        ttk.Button(bottom, text="🆕 New Script", command=self.create_new_script_dialog, style='Action.TButton').pack(side=tk.LEFT, padx=2)
        ttk.Button(bottom, text="📁 New Category", command=self._new_training_category_dialog, style='Action.TButton').pack(side=tk.LEFT, padx=2)
        ttk.Button(bottom, text="💾 Save", command=self.save_content, style='Action.TButton').pack(side=tk.LEFT, padx=8)
        ttk.Button(bottom, text="✏️ Rename", command=self.rename_current_file, style='Select.TButton').pack(side=tk.LEFT, padx=2)
        ttk.Button(bottom, text="🗑️ Delete File", command=self.delete_current_file, style='Select.TButton').pack(side=tk.LEFT, padx=2)
        ttk.Button(bottom, text="❌ Clear", command=lambda: self.content_editor.delete(1.0, tk.END), style='Select.TButton').pack(side=tk.RIGHT, padx=2)
        ttk.Button(bottom, text="📎 Copy", command=self._copy_to_clipboard, style='Select.TButton').pack(side=tk.RIGHT, padx=2)

    # --- PROMPTS SUBTAB ---
    def _build_prompts_ui(self, parent):
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(1, weight=1)
        ttk.Label(parent, text="🧠 System Prompts", font=("Arial", 12, "bold"), style='CategoryPanel.TLabel').grid(row=0, column=0, sticky=tk.W, padx=10, pady=(10,0))

        # Editor only; selection comes from right-side Prompts list (Training tab)
        self.prompts_editor = scrolledtext.ScrolledText(parent, font=("Courier", 9), wrap=tk.WORD, relief='flat', borderwidth=0, highlightthickness=0, bg='#1e1e1e', fg='#ffffff')
        self.prompts_editor.grid(row=1, column=0, sticky=tk.NSEW, padx=10, pady=10)

        # Bottom actions
        bottom = ttk.Frame(parent)
        bottom.grid(row=2, column=0, sticky=tk.EW, padx=10, pady=(0,10))
        ttk.Button(bottom, text="➕ New File", command=self._new_prompt_dialog, style='Action.TButton').pack(side=tk.LEFT, padx=2)
        ttk.Button(bottom, text="📁 New Category", command=self._new_prompt_category_dialog, style='Action.TButton').pack(side=tk.LEFT, padx=2)
        ttk.Button(bottom, text="💾 Save", command=self._save_prompt, style='Action.TButton').pack(side=tk.LEFT, padx=8)
        ttk.Button(bottom, text="✏️ Rename", command=self._rename_prompt_dialog, style='Select.TButton').pack(side=tk.LEFT, padx=2)
        ttk.Button(bottom, text="🗑️ Delete", command=self._delete_prompt_dialog, style='Select.TButton').pack(side=tk.LEFT, padx=2)
        ttk.Button(bottom, text="❌ Clear", command=lambda: self.prompts_editor.delete(1.0, tk.END), style='Select.TButton').pack(side=tk.RIGHT, padx=2)
        ttk.Button(bottom, text="📎 Copy", command=self._copy_to_clipboard, style='Select.TButton').pack(side=tk.RIGHT, padx=2)

    def _new_prompt_category_dialog(self):
        """Creates a new sub-folder inside the Prompts directory."""
        category_name = simpledialog.askstring("New Prompt Category", "Enter new category name:")
        if not category_name or not category_name.strip():
            return

        try:
            new_dir = PROMPTS_DIR / category_name.strip()
            if new_dir.exists():
                messagebox.showerror("Exists", f"A prompt category named '{category_name}' already exists.")
                return
            
            new_dir.mkdir(parents=True, exist_ok=True)
            messagebox.showinfo("Success", f"Prompt category '{category_name}' created.")

            if callable(self.refresh_callback):
                self.refresh_callback()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to create prompt category: {e}")



    def _open_selected_prompt(self):
        # Use the right-side Prompts selection from Training tab
        name = None
        if self.training_tab_instance and hasattr(self.training_tab_instance, 'prompt_selected_var'):
            name = self.training_tab_instance.prompt_selected_var.get()
        if not name:
            messagebox.showinfo("Select", "Choose a prompt in the Prompts list on the right.")
            return
        try:
            data = load_system_prompt(name)
            from json import dumps
            pretty = dumps(data, indent=2, ensure_ascii=False) if isinstance(data, dict) else str(data)
            self.prompts_editor.delete(1.0, tk.END)
            self.prompts_editor.insert(1.0, pretty)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open prompt: {e}")

    def _save_prompt(self):
        name = None
        if self.training_tab_instance and hasattr(self.training_tab_instance, 'prompt_selected_var'):
            name = self.training_tab_instance.prompt_selected_var.get()
        if not name:
            messagebox.showinfo("Select", "Choose a prompt to save.")
            return
        try:
            self._prompt_path(name).write_text(self.prompts_editor.get(1.0, tk.END))
            messagebox.showinfo("Saved", f"Prompt '{name}' saved.")
            if callable(self.refresh_callback):
                self.refresh_callback()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save: {e}")

    def _new_prompt_dialog(self):
        categories = list_prompt_categories()
        dialog = NewFileDialog(self.parent, title="Create New Prompt", header="Create a new prompt file", categories=categories)
        if dialog.result:
            category, name = dialog.result
            try:
                template_content = '{\n  "prompt": "Your new prompt here."\n}'
                create_prompt_file(name, category=category, content=template_content)

                if callable(self.refresh_callback):
                    self.refresh_callback()
                
                self.prompts_editor.delete(1.0, tk.END)
                self.prompts_editor.insert(1.0, template_content)
                
                if self.training_tab_instance and hasattr(self.training_tab_instance, 'prompt_selected_var'):
                    self.training_tab_instance.prompt_selected_var.set(name)

                messagebox.showinfo("Success", f"Prompt '{name}' created in category '{category or '(root)'}'.")

            except FileExistsError:
                messagebox.showerror("Exists", f"A prompt named '{name}' already exists in that category.")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to create prompt: {e}")

    def _copy_to_clipboard(self):
        """Copies the content of the currently active editor to the clipboard."""
        active_tab = self._active_subtab.get()
        content = ""
        try:
            if active_tab == 'scripts':
                content = self.content_editor.get(1.0, tk.END)
            elif active_tab == 'prompts':
                content = self.prompts_editor.get(1.0, tk.END)
            elif active_tab == 'schemas':
                content = self.schemas_editor.get(1.0, tk.END)

            if not content.strip():
                messagebox.showinfo("Clipboard", "Editor is empty. Nothing to copy.", parent=self.parent)
                return

            self.parent.clipboard_clear()
            self.parent.clipboard_append(content)
            messagebox.showinfo("Clipboard", "Editor content copied to clipboard!", parent=self.parent)
        except Exception as e:
            messagebox.showerror("Clipboard Error", f"Failed to copy to clipboard: {e}", parent=self.parent)

    def _new_training_category_dialog(self):
        """Creates a new category folder for training scripts."""
        from config import create_category_folder
        category_name = simpledialog.askstring("New Training Category", "Enter new category name:")
        if not category_name or not category_name.strip():
            return
        try:
            create_category_folder(category_name.strip())
            messagebox.showinfo("Success", f"Training category '{category_name}' created.")
            if callable(self.refresh_callback):
                self.refresh_callback()
        except FileExistsError:
            messagebox.showerror("Exists", f"A category named '{category_name}' already exists.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to create category: {e}")

    def _rename_prompt_dialog(self):
        old = None
        if self.training_tab_instance and hasattr(self.training_tab_instance, 'prompt_selected_var'):
            old = self.training_tab_instance.prompt_selected_var.get()
        if not old:
            messagebox.showinfo("Select", "Choose a prompt to rename.")
            return
        new = simpledialog.askstring("Rename Prompt", "New name:", initialvalue=old)
        if not new or new == old:
            return
        try:
            self._prompt_path(old).rename(self._prompt_path(new))
            if callable(self.refresh_callback):
                self.refresh_callback()
            if hasattr(self.training_tab_instance, 'prompt_selected_var'):
                self.training_tab_instance.prompt_selected_var.set(new)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to rename: {e}")

    def _delete_prompt_dialog(self):
        name = None
        if self.training_tab_instance and hasattr(self.training_tab_instance, 'prompt_selected_var'):
            name = self.training_tab_instance.prompt_selected_var.get()
        if not name:
            messagebox.showinfo("Select", "Choose a prompt to delete.")
            return
        if not messagebox.askyesno("Confirm", f"Delete prompt '{name}'?"):
            return
        try:
            self._prompt_path(name).unlink(missing_ok=True)
            self.prompts_editor.delete(1.0, tk.END)
            if hasattr(self.training_tab_instance, 'prompt_selected_var'):
                self.training_tab_instance.prompt_selected_var.set('')
            if callable(self.refresh_callback):
                self.refresh_callback()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to delete: {e}")

    # --- SCHEMAS SUBTAB ---
    def _build_schemas_ui(self, parent):
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(1, weight=1)
        ttk.Label(parent, text="🧩 Tool Schemas", font=("Arial", 12, "bold"), style='CategoryPanel.TLabel').grid(row=0, column=0, sticky=tk.W, padx=10, pady=(10,0))

        # Editor only; selection comes from right-side Schemas list (Training tab)
        self.schemas_editor = scrolledtext.ScrolledText(parent, font=("Courier", 9), wrap=tk.WORD, relief='flat', borderwidth=0, highlightthickness=0, bg='#1e1e1e', fg='#ffffff')
        self.schemas_editor.grid(row=1, column=0, sticky=tk.NSEW, padx=10, pady=10)

        # Bottom actions
        bottom = ttk.Frame(parent)
        bottom.grid(row=2, column=0, sticky=tk.EW, padx=10, pady=(0,10))
        ttk.Button(bottom, text="➕ New File", command=self._new_schema_dialog, style='Action.TButton').pack(side=tk.LEFT, padx=2)
        ttk.Button(bottom, text="📁 New Category", command=self._new_schema_category_dialog, style='Action.TButton').pack(side=tk.LEFT, padx=2)
        ttk.Button(bottom, text="💾 Save", command=self._save_schema, style='Action.TButton').pack(side=tk.LEFT, padx=8)
        ttk.Button(bottom, text="✏️ Rename", command=self._rename_schema_dialog, style='Select.TButton').pack(side=tk.LEFT, padx=2)
        ttk.Button(bottom, text="🗑️ Delete", command=self._delete_schema_dialog, style='Select.TButton').pack(side=tk.LEFT, padx=2)
        ttk.Button(bottom, text="❌ Clear", command=lambda: self.schemas_editor.delete(1.0, tk.END), style='Select.TButton').pack(side=tk.RIGHT, padx=2)
        ttk.Button(bottom, text="📎 Copy", command=self._copy_to_clipboard, style='Select.TButton').pack(side=tk.RIGHT, padx=2)

    def _new_schema_category_dialog(self):
        """Creates a new sub-folder inside the Schemas directory."""
        category_name = simpledialog.askstring("New Schema Category", "Enter new category name:")
        if not category_name or not category_name.strip():
            return

        try:
            new_dir = SCHEMAS_DIR / category_name.strip()
            if new_dir.exists():
                messagebox.showerror("Exists", f"A schema category named '{category_name}' already exists.")
                return
            
            new_dir.mkdir(parents=True, exist_ok=True)
            messagebox.showinfo("Success", f"Schema category '{category_name}' created.")

            if callable(self.refresh_callback):
                self.refresh_callback()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to create schema category: {e}")



    def _open_selected_schema(self):
        # Use the right-side Schemas selection from Training tab
        name = None
        if self.training_tab_instance and hasattr(self.training_tab_instance, 'schema_selected_var'):
            name = self.training_tab_instance.schema_selected_var.get()
        if not name:
            messagebox.showinfo("Select", "Choose a schema in the Schemas list on the right.")
            return
        try:
            data = load_tool_schema(name)
            from json import dumps
            pretty = dumps(data, indent=2, ensure_ascii=False) if isinstance(data, dict) else str(data)
            self.schemas_editor.delete(1.0, tk.END)
            self.schemas_editor.insert(1.0, pretty)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open schema: {e}")

    def _save_schema(self):
        name = None
        if self.training_tab_instance and hasattr(self.training_tab_instance, 'schema_selected_var'):
            name = self.training_tab_instance.schema_selected_var.get()
        if not name:
            messagebox.showinfo("Select", "Choose a schema to save.")
            return
        try:
            self._schema_path(name).write_text(self.schemas_editor.get(1.0, tk.END))
            messagebox.showinfo("Saved", f"Schema '{name}' saved.")
            if callable(self.refresh_callback):
                self.refresh_callback()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save: {e}")

    def _new_schema_dialog(self):
        categories = list_schema_categories()
        dialog = NewFileDialog(self.parent, title="Create New Schema", header="Create a new schema file", categories=categories)
        if dialog.result:
            category, name = dialog.result
            try:
                template_content = '{\n  "tools": []\n}'
                create_schema_file(name, category=category, content=template_content)

                if callable(self.refresh_callback):
                    self.refresh_callback()
                
                self.schemas_editor.delete(1.0, tk.END)
                self.schemas_editor.insert(1.0, template_content)

                if self.training_tab_instance and hasattr(self.training_tab_instance, 'schema_selected_var'):
                    self.training_tab_instance.schema_selected_var.set(name)

                messagebox.showinfo("Success", f"Schema '{name}' created in category '{category or '(root)'}'.")

            except FileExistsError:
                messagebox.showerror("Exists", f"A schema named '{name}' already exists in that category.")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to create schema: {e}")

    def _rename_schema_dialog(self):
        old = None
        if self.training_tab_instance and hasattr(self.training_tab_instance, 'schema_selected_var'):
            old = self.training_tab_instance.schema_selected_var.get()
        if not old:
            messagebox.showinfo("Select", "Choose a schema to rename.")
            return
        new = simpledialog.askstring("Rename Schema", "New name:", initialvalue=old)
        if not new or new == old:
            return
        try:
            self._schema_path(old).rename(self._schema_path(new))
            if callable(self.refresh_callback):
                self.refresh_callback()
            if hasattr(self.training_tab_instance, 'schema_selected_var'):
                self.training_tab_instance.schema_selected_var.set(new)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to rename: {e}")

    def _delete_schema_dialog(self):
        name = None
        if self.training_tab_instance and hasattr(self.training_tab_instance, 'schema_selected_var'):
            name = self.training_tab_instance.schema_selected_var.get()
        if not name:
            messagebox.showinfo("Select", "Choose a schema to delete.")
            return
        if not messagebox.askyesno("Confirm", f"Delete schema '{name}'?"):
            return
        try:
            self._schema_path(name).unlink(missing_ok=True)
            self.schemas_editor.delete(1.0, tk.END)
            if hasattr(self.training_tab_instance, 'schema_selected_var'):
                self.training_tab_instance.schema_selected_var.set('')
            if callable(self.refresh_callback):
                self.refresh_callback()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to delete: {e}")

    def populate_category_dropdown(self):
        """No-op: Category selection now comes from right-side Training Scripts panel."""
        # Keep category_info up to date for internal operations
        try:
            self.category_info = get_category_info()
        except Exception:
            pass

    def on_category_selected(self):
        """No-op: Category selection is driven by the right-side Training Scripts panel."""
        return

        # Automatically select train.py if it exists (Gated debug)
        # category_path = DATA_DIR.parent / "Training_Data-Sets" / category_name
        # train_script_path = category_path / "train.py"
        # if train_script_path.exists():
        #     print(f"DEBUG: on_category_selected: Automatically selecting {train_script_path.name}")
        #     self.select_script_file(train_script_path)

    def populate_file_list(self, category_name):
        """Populate the file list for selected category with .jsonl and .py files"""
        # No left-side listing anymore; safe no-op if list frame doesn't exist
        if not hasattr(self, 'jsonl_list_frame') or self.jsonl_list_frame is None:
            return

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
        """Select a script file for viewing/editing"""
        self.current_file_path = script_path
        self.current_file_type = 'script'
        # Auto-select the category from the script path
        category_name = script_path.parent.name
        self.selected_category_for_edit.set(category_name)

        # Update label to reflect live checkbox state from right-side selection
        selected = self._get_script_selected_state(category_name, script_path.name)
        suffix = " — ✅ Selected" if selected else " — ☐ Not selected"
        label_text = f"🐍 {script_path.name}{suffix}"
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
        # Reflect live checkbox state from right-side selection
        category_name = jsonl_path.parent.name
        selected = self._get_jsonl_selected_state(category_name, jsonl_path.name)
        suffix = " — ✅ Selected" if selected else " — ☐ Not selected"
        self.file_name_label.config(text=f"📄 {jsonl_path.name}{suffix}")

    def _get_script_selected_state(self, category: str, script_name: str) -> bool:
        """Returns current checkbox state for a script from Training tab selection."""
        try:
            if self.training_tab_instance and hasattr(self.training_tab_instance, 'script_vars'):
                var = self.training_tab_instance.script_vars.get(category, {}).get(script_name)
                return bool(var.get()) if var is not None else False
        except Exception:
            pass
        return False

    def _get_jsonl_selected_state(self, category: str, jsonl_name: str) -> bool:
        """Returns current checkbox state for a JSONL file from Training tab selection."""
        try:
            if self.training_tab_instance and hasattr(self.training_tab_instance, 'jsonl_vars'):
                var = self.training_tab_instance.jsonl_vars.get(category, {}).get(jsonl_name)
                return bool(var.get()) if var is not None else False
        except Exception:
            pass
        return False

    def open_from_selection(self):
        """Open the first selected script or JSONL from the right-side selection for editing/viewing."""
        if not self.training_tab_instance:
            messagebox.showwarning("Unavailable", "Training selection not available in this context.")
            return
        selected = self.training_tab_instance.get_selected_scripts() if hasattr(self.training_tab_instance, 'get_selected_scripts') else {"scripts": [], "jsonl_files": []}
        if selected.get('scripts'):
            self.select_script_file(selected['scripts'][0]['path'])
        elif selected.get('jsonl_files'):
            self.select_jsonl_file(selected['jsonl_files'][0]['path'])
            self.view_jsonl_file()
        else:
            messagebox.showinfo("No Selection", "Select a script or JSONL from the right-side Training Scripts panel.")

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

            # Ensure editor is writable before updating
            self.content_editor.config(state=tk.NORMAL)
            self.content_editor.delete(1.0, tk.END)
            self.content_editor.insert(1.0, formatted)

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
                self.populate_file_list(category_name)
            if callable(self.refresh_callback):
                self.refresh_callback()

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
        """Create a new JSONL training data file using the config function."""
        category_name = None
        # Prefer current file's category
        if self.current_file_path:
            category_name = self.current_file_path.parent.name
        # Next: derive from right-side selection
        if not category_name and self.training_tab_instance and hasattr(self.training_tab_instance, 'get_selected_scripts'):
            sel = self.training_tab_instance.get_selected_scripts()
            src = (sel.get('scripts') or sel.get('jsonl_files') or [])
            if src:
                category_name = Path(src[0]['path']).parent.name
        # Fallback: ask user
        if not category_name:
            category_name = simpledialog.askstring("Category", "Enter category name to create JSONL in:")
            if not category_name:
                return

        file_name_no_ext = simpledialog.askstring(
            "New JSONL File",
            "Enter file name (without .jsonl):"
        )
        if not file_name_no_ext:
            return

        try:
            # Create with example template using the config function
            example_content = '{"messages": [{"role": "user", "content": "Example prompt"}, {"role": "assistant", "content": "Example response"}], "scenario": "example"}\n'
            
            file_path = create_subcategory_file(
                category_name,
                file_name_no_ext,
                content=example_content
            )

            messagebox.showinfo("Created", f"JSONL file '{file_path.name}' created with template.")
            
            # Refresh the main Training Tab's right-side panel
            if callable(self.refresh_callback):
                self.refresh_callback()

            # Select and load the new file for editing
            self.select_jsonl_file(file_path)
            self.edit_jsonl_file()

        except FileExistsError:
            messagebox.showerror("Error", f"File '{file_name_no_ext}.jsonl' already exists in category '{category_name}'.")
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
                if callable(self.refresh_callback):
                    self.refresh_callback()

            except Exception as e:
                messagebox.showerror("Error", f"Failed to delete file: {e}")

    def delete_current_file(self):
        """Delete the currently loaded file (script or JSONL)."""
        if not self.current_file_path:
            messagebox.showwarning("No File", "No file selected to delete.")
            return
        fn = self.current_file_path.name
        if not messagebox.askyesno("Confirm Delete", f"Delete '{fn}'? This cannot be undone."):
            return
        try:
            cat = self.current_file_path.parent.name
            self.current_file_path.unlink()
            self.current_file_path = None
            self.current_file_type = None
            self.content_editor.config(state=tk.NORMAL)
            self.content_editor.delete(1.0, tk.END)
            self.file_name_label.config(text="")
            # Refresh listings
            self.populate_file_list(cat)
            if callable(self.refresh_callback):
                self.refresh_callback()
            messagebox.showinfo("Deleted", f"Deleted {fn}")
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
        category_name = None
        if self.current_file_path:
            category_name = self.current_file_path.parent.name
        if not category_name and self.training_tab_instance and hasattr(self.training_tab_instance, 'get_selected_scripts'):
            sel = self.training_tab_instance.get_selected_scripts()
            src = (sel.get('scripts') or sel.get('jsonl_files') or [])
            if src:
                category_name = Path(src[0]['path']).parent.name
        if not category_name:
            category_name = simpledialog.askstring("Open Folder", "Enter category name to open:")
            if not category_name:
                return

        category_path = DATA_DIR.parent / "Training_Data-Sets" / category_name
        if category_path.exists():
            subprocess.run(["xdg-open", str(category_path)])
        else:
            messagebox.showerror("Not Found", f"Category folder not found: {category_path}")

    def create_new_script_dialog(self):
        """Create a new Python training script using the config function."""
        category_name = None
        if self.current_file_path:
            category_name = self.current_file_path.parent.name
        if not category_name and self.training_tab_instance and hasattr(self.training_tab_instance, 'get_selected_scripts'):
            sel = self.training_tab_instance.get_selected_scripts()
            src = (sel.get('scripts') or sel.get('jsonl_files') or [])
            if src:
                category_name = Path(src[0]['path']).parent.name
        if not category_name:
            category_name = simpledialog.askstring("Category", "Enter category name to create script in:")
            if not category_name:
                return

        file_name = simpledialog.askstring("New Script", "Enter script file name (e.g., train.py):")
        if not file_name:
            return

        try:
            template = (
                "#!/usr/bin/env python3\n"
                "# Minimal training script template for category: {category}\n"
                "import os\n"
                "from pathlib import Path\n"
                "import sys\n\n"
                "# Add project root to path to allow imports like 'from config import ...'\n"
                "sys.path.insert(0, str(Path(__file__).parent.parent.parent))\n"
                "from Data.training_engine import TrainingEngine\n\n"
                "def main():\n"
                "    print(f'Starting training script for category: {category}')\n"
                "    # This script runs within the context of the Runner Panel.\n"
                "    # It receives all its configuration from environment variables set by the GUI.\n"
                "    # Example of how to use the TrainingEngine:\n"
                "    # engine = TrainingEngine()\n"
                "    # engine.run_full_training()\n"
                "    print('Training script finished.')\n\n"
                "if __name__ == '__main__':\n"
                "    main()\n"
            ).format(category=category_name)

            script_path = create_script_file(category_name, file_name, content=template)

            messagebox.showinfo("Created", f"Script '{script_path.name}' created.")
            
            if callable(self.refresh_callback):
                self.refresh_callback()

            self.select_script_file(script_path)

        except FileExistsError:
            messagebox.showerror("Error", f"Script '{file_name}' already exists in category '{category_name}'.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to create script: {e}")

    def rename_current_file(self):
        """Rename the currently loaded file (script or JSONL)."""
        if not self.current_file_path:
            messagebox.showwarning("No File", "No file selected to rename.")
            return
        new_name = simpledialog.askstring(
            "Rename",
            "Enter new filename (keep extension):",
            initialvalue=self.current_file_path.name
        )
        if not new_name:
            return
        dest = self.current_file_path.with_name(new_name)
        if dest.exists():
            messagebox.showerror("Error", f"File already exists: {new_name}")
            return
        try:
            old_cat = self.current_file_path.parent.name
            self.current_file_path.rename(dest)
            self.current_file_path = dest
            self.file_name_label.config(text=dest.name)
            self.populate_file_list(old_cat)
            if callable(self.refresh_callback):
                self.refresh_callback()
            messagebox.showinfo("Renamed", f"Renamed to {new_name}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to rename: {e}")

    # --- Semantic States Management ---
    def _create_semantic_states_panel(self):
        panel = ttk.LabelFrame(self.parent, text="🧠 Semantic States (Prompts & Tool Schemas)", style='TLabelframe')
        panel.grid(row=1, column=0, columnspan=2, sticky=tk.EW, padx=10, pady=(0,10))
        panel.columnconfigure(1, weight=1)

        # Prompts
        ttk.Label(panel, text="System Prompts:", style='Config.TLabel').grid(row=0, column=0, sticky=tk.W, padx=10)
        self.prompts_combo = ttk.Combobox(panel, state='readonly', width=30, values=list_system_prompts())
        self.prompts_combo.grid(row=0, column=1, sticky=tk.W, padx=5)
        ttk.Button(panel, text="View", command=lambda: self._load_semantic_file('prompt', 'view'), style='Select.TButton').grid(row=0, column=2, padx=5)
        ttk.Button(panel, text="Edit", command=lambda: self._load_semantic_file('prompt', 'edit'), style='Select.TButton').grid(row=0, column=3, padx=5)
        ttk.Button(panel, text="New", command=lambda: self._new_semantic_file('prompt'), style='Action.TButton').grid(row=0, column=4, padx=5)
        ttk.Button(panel, text="Delete", command=lambda: self._delete_semantic_file('prompt'), style='Select.TButton').grid(row=0, column=5, padx=5)

        # Schemas
        ttk.Label(panel, text="Tool Schemas:", style='Config.TLabel').grid(row=1, column=0, sticky=tk.W, padx=10)
        self.schemas_combo = ttk.Combobox(panel, state='readonly', width=30, values=list_tool_schemas())
        self.schemas_combo.grid(row=1, column=1, sticky=tk.W, padx=5)
        ttk.Button(panel, text="View", command=lambda: self._load_semantic_file('schema', 'view'), style='Select.TButton').grid(row=1, column=2, padx=5)
        ttk.Button(panel, text="Edit", command=lambda: self._load_semantic_file('schema', 'edit'), style='Select.TButton').grid(row=1, column=3, padx=5)
        ttk.Button(panel, text="New", command=lambda: self._new_semantic_file('schema'), style='Action.TButton').grid(row=1, column=4, padx=5)
        ttk.Button(panel, text="Delete", command=lambda: self._delete_semantic_file('schema'), style='Select.TButton').grid(row=1, column=5, padx=5)

    def _load_semantic_file(self, kind: str, mode: str, name: str = None):
        try:
            if kind == 'prompt':
                if not name and hasattr(self, 'prompts_combo'):
                    name = self.prompts_combo.get()
                if not name:
                    messagebox.showwarning("No Prompt", "Please select a system prompt.")
                    return
                data = load_system_prompt(name)
            else:
                if not name and hasattr(self, 'schemas_combo'):
                    name = self.schemas_combo.get()
                if not name:
                    messagebox.showwarning("No Schema", "Please select a tool schema.")
                    return
                data = load_tool_schema(name)
            import json
            text = json.dumps(data, indent=2)
            self.content_editor.config(state=tk.NORMAL if mode=='edit' else tk.DISABLED)
            self.content_editor.delete(1.0, tk.END)
            self.content_editor.insert(1.0, text)
            self.current_file_type = 'semantic'
            prefix = 'system_prompt_' if kind=='prompt' else 'tool_schema_'
            self.current_file_path = SEMANTIC_DATA_DIR / f"{prefix}{name}.json"
            self.file_name_label.config(text=f"🧠 {prefix}{name}.json")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load semantic file: {e}")

    def _new_semantic_file(self, kind: str):
        name = simpledialog.askstring("New Semantic File", f"Enter {('prompt' if kind=='prompt' else 'schema')} name:")
        if not name:
            return
        prefix = 'system_prompt_' if kind=='prompt' else 'tool_schema_'
        file_path = SEMANTIC_DATA_DIR / f"{prefix}{name}.json"
        if file_path.exists():
            messagebox.showerror("Error", f"File already exists: {file_path.name}")
            return
        try:
            SEMANTIC_DATA_DIR.mkdir(parents=True, exist_ok=True)
            template = {"name": name}
            if kind=='prompt':
                template["prompt"] = "You are a helpful assistant."
            else:
                template["tools"] = []
            import json
            with open(file_path, 'w') as f:
                json.dump(template, f, indent=2)
            messagebox.showinfo("Created", f"Created {file_path.name}")
            # Refresh combos
            self.prompts_combo['values'] = list_system_prompts()
            self.schemas_combo['values'] = list_tool_schemas()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to create file: {e}")

    def _delete_semantic_file(self, kind: str):
        name = self.prompts_combo.get() if kind=='prompt' else self.schemas_combo.get()
        if not name:
            messagebox.showwarning("No Selection", "Please select a file to delete.")
            return
        prefix = 'system_prompt_' if kind=='prompt' else 'tool_schema_'
        file_path = SEMANTIC_DATA_DIR / f"{prefix}{name}.json"
        if messagebox.askyesno("Confirm Delete", f"Delete {file_path.name}? This cannot be undone."):
            try:
                file_path.unlink()
                # Refresh combos
                self.prompts_combo['values'] = list_system_prompts()
                self.schemas_combo['values'] = list_tool_schemas()
                if kind=='prompt':
                    self.prompts_combo.set("")
                else:
                    self.schemas_combo.set("")
                messagebox.showinfo("Deleted", f"Deleted {file_path.name}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to delete file: {e}")

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
class NewFileDialog(tk.Toplevel):
    """A custom dialog for creating a new file with category selection."""
    def __init__(self, parent, title=None, header=None, categories=None):
        super().__init__(parent)
        self.transient(parent)
        if title:
            self.title(title)

        self.result = None
        self.body = ttk.Frame(self)
        self.body.pack(padx=10, pady=10)

        if header:
            ttk.Label(self.body, text=header, font=("Arial", 11, "bold")).grid(row=0, columnspan=2, pady=(0, 10))

        # Category
        ttk.Label(self.body, text="Category:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        self.category_var = tk.StringVar()
        self.category_combo = ttk.Combobox(self.body, textvariable=self.category_var, values=categories, width=30)
        if categories:
            self.category_combo.set(categories[0])
        self.category_combo.grid(row=1, column=1, sticky=tk.EW, padx=5, pady=5)

        # Filename
        ttk.Label(self.body, text="Filename:").grid(row=2, column=0, sticky=tk.W, padx=5, pady=5)
        self.name_var = tk.StringVar()
        self.name_entry = ttk.Entry(self.body, textvariable=self.name_var, width=32)
        self.name_entry.grid(row=2, column=1, sticky=tk.EW, padx=5, pady=5)

        # Buttons
        self.buttonbox = ttk.Frame(self)
        self.buttonbox.pack(pady=5)
        ttk.Button(self.buttonbox, text="OK", width=10, command=self.ok, default=tk.ACTIVE).pack(side=tk.LEFT, padx=5)
        ttk.Button(self.buttonbox, text="Cancel", width=10, command=self.cancel).pack(side=tk.LEFT, padx=5)

        self.bind("<Return>", self.ok)
        self.bind("<Escape>", self.cancel)

        self.initial_focus = self.name_entry
        self.initial_focus.focus_set()
        self.wait_window(self)

    def ok(self, event=None):
        name = self.name_var.get().strip()
        if not name:
            messagebox.showwarning("Input Error", "Please enter a filename.", parent=self)
            return
        
        self.result = (self.category_var.get(), name)
        self.destroy()

    def cancel(self, event=None):
        self.destroy()
