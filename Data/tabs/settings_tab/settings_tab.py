"""
Settings Tab - Application configuration and preferences
Isolated module for settings-related functionality
"""

import tkinter as tk
from tkinter import ttk, scrolledtext
import tkinter.messagebox as messagebox
import json
from pathlib import Path
import os
import sys
import glob
import logger_util
from logger_util import log_message
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from tabs.base_tab import BaseTab
from config import (TRAINER_ROOT, DATA_DIR, MODELS_DIR, TODOS_DIR,
                    create_todo_file, list_todo_files, read_todo_file,
                    update_todo_file, delete_todo_file, move_todo_to_completed,
                    get_project_todos_dir, create_project_todo_file, list_project_todo_files,
                    list_all_projects_with_todos, move_project_todo_to_completed)


class SettingsTab(BaseTab):
    """Application settings and configuration tab"""

    def __init__(self, parent, root, style, main_gui=None, tab_instances=None):
        super().__init__(parent, root, style)

        # Reference to main GUI (for accessing other tabs)
        self.main_gui = main_gui
        self.tab_instances = tab_instances

        # Debug tab variables
        self.log_poll_job = None
        self.current_log_file = None
        self.last_read_position = 0
        self.log_file_paths = {} # Corrected indentation
        self.tab_enabled_vars = {} # For managing tab visibility
        self.reorder_mode = tk.StringVar(value='static') # New setting for tab reordering
        # Settings file
        self.settings_file = DATA_DIR / "settings.json"
        self.settings = self.load_settings()
        # Lazy terminal init flag
        self.terminal_initialized = False
        # Internal flag to suppress reorder mode popups during programmatic changes
        self._suppress_reorder_popup = False
        # Internal mapping from (tab_name, panel_header_text) -> file path (if resolvable)
        self.panel_file_map = {}
        # Current project context for unified ToDo manager (set by Projects panel)
        self.current_project_context = None

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

        log_message("SETTINGS: Creating Quick Restart button.")
        # Quick Restart button
        quick_restart_btn = ttk.Button(header_frame, text="🚀 Quick Restart",
                  command=self.quick_restart_application,
                  style='Action.TButton')
        quick_restart_btn.pack(side=tk.RIGHT, padx=(5, 0))
        print(f"DEBUG: Quick Restart button created. Command bound to: {quick_restart_btn.cget('command')}")
        log_message(f"SETTINGS: Quick Restart button created. Command bound to: {quick_restart_btn.cget('command')}")

    # --- Plan Template Dialog (shared by Main/Project ToDo) ---
    def _open_plan_template_dialog(self, project_name: str | None = None):
        dlg = tk.Toplevel(self.root)
        dlg.title('New Plan')
        dlg.geometry('760x560')
        try:
            dlg.transient(self.root); dlg.grab_set()
        except Exception:
            pass

        # Scrollable body container
        container = ttk.Frame(dlg)
        container.pack(fill=tk.BOTH, expand=True)
        canvas = tk.Canvas(container, highlightthickness=0)
        vbar = ttk.Scrollbar(container, orient=tk.VERTICAL, command=canvas.yview)
        canvas.configure(yscrollcommand=vbar.set)
        canvas.grid(row=0, column=0, sticky=tk.NSEW)
        vbar.grid(row=0, column=1, sticky=tk.NS)
        container.columnconfigure(0, weight=1)
        container.rowconfigure(0, weight=1)
        body = ttk.Frame(canvas, padding=10)
        body_id = canvas.create_window((0,0), window=body, anchor='nw')

        def _on_body_config(_e=None):
            try:
                canvas.configure(scrollregion=canvas.bbox('all'))
            except Exception:
                pass
        def _on_container_resize(e):
            try:
                canvas.itemconfigure(body_id, width=e.width - vbar.winfo_width())
            except Exception:
                pass
        body.bind('<Configure>', _on_body_config)
        container.bind('<Configure>', _on_container_resize)

        f = body  # Alias for layout
        # Plan name
        ttk.Label(f, text='Plan Name', style='CategoryPanel.TLabel').grid(row=0, column=0, sticky=tk.W)
        name_var = tk.StringVar(); ttk.Entry(f, textvariable=name_var).grid(row=0, column=1, sticky=tk.EW)
        # Priority
        ttk.Label(f, text='Priority', style='CategoryPanel.TLabel').grid(row=1, column=0, sticky=tk.W)
        pvar = tk.StringVar(value='medium'); pr = ttk.Frame(f); pr.grid(row=1, column=1, sticky=tk.W)
        ttk.Radiobutton(pr, text='High', value='high', variable=pvar).pack(side=tk.LEFT, padx=4)
        ttk.Radiobutton(pr, text='Medium', value='medium', variable=pvar).pack(side=tk.LEFT, padx=4)
        ttk.Radiobutton(pr, text='Low', value='low', variable=pvar).pack(side=tk.LEFT, padx=4)
        # Helper: auto-resize text widget 1..3 lines and hide scrollbar
        def _mk_auto_text(parent, min_lines=1, max_lines=3):
            txt = scrolledtext.ScrolledText(parent, height=min_lines, wrap=tk.WORD, font=('Arial',9), bg='#1e1e1e', fg='#dcdcdc')
            # Hide the visible scrollbar by setting its width to 0; keep wheel working
            try:
                for child in txt.winfo_children():
                    if isinstance(child, tk.Scrollbar):
                        child.configure(width=0)
            except Exception:
                pass
            def _update_height(_e=None):
                try:
                    # Count visual lines (approximate by content lines)
                    text = txt.get('1.0', 'end-1c')
                    lines = max(min_lines, min(max_lines, max(1, text.count('\n') + 1)))
                    if int(txt.cget('height')) != lines:
                        txt.configure(height=lines)
                except Exception:
                    pass
                finally:
                    try:
                        txt.edit_modified(False)
                    except Exception:
                        pass
            try:
                txt.bind('<<Modified>>', _update_height)
            except Exception:
                pass
            return txt

        # Overview
        ttk.Label(f, text='Overview', style='CategoryPanel.TLabel').grid(row=2, column=0, sticky=tk.NW)
        ov = _mk_auto_text(f, 1, 3); ov.grid(row=2, column=1, sticky=tk.NSEW)
        # Objectives
        ttk.Label(f, text='Objectives', style='CategoryPanel.TLabel').grid(row=3, column=0, sticky=tk.NW)
        obj = _mk_auto_text(f, 1, 3); obj.grid(row=3, column=1, sticky=tk.NSEW)
        # Section builder: dynamic single-line entries with + / - controls
        def _mk_section(row_idx: int, label_text: str, examples: list[str]):
            ttk.Label(f, text=label_text, style='CategoryPanel.TLabel').grid(row=row_idx, column=0, sticky=tk.NW, pady=(6,0))
            wrap = ttk.Frame(f); wrap.grid(row=row_idx, column=1, sticky=tk.NSEW, pady=(6,0))
            wrap.columnconfigure(0, weight=1)

            # controls under header
            ctrl = ttk.Frame(wrap)
            ctrl.grid(row=0, column=0, sticky=tk.W)
            rows_frame = ttk.Frame(wrap)
            rows_frame.grid(row=1, column=0, sticky=tk.NSEW)
            rows = []

            def add_row(text: str = '', *, placeholder: bool = False):
                r = ttk.Frame(rows_frame)
                r.columnconfigure(0, weight=1)
                e = ttk.Entry(r)
                e.grid(row=0, column=0, sticky=tk.EW, padx=(0,6), pady=2)
                if text:
                    e.insert(0, text)
                if placeholder and text:
                    try:
                        e.configure(foreground='#888888')
                        e._placeholder = True
                    except Exception:
                        pass
                    def _clear_placeholder(_e):
                        try:
                            if getattr(e, '_placeholder', False):
                                e.delete(0, tk.END)
                                e.configure(foreground='#dcdcdc')
                                e._placeholder = False
                        except Exception:
                            pass
                    e.bind('<FocusIn>', _clear_placeholder, add='+')
                rows.append(e)
                r.pack(fill=tk.X)

            def remove_row():
                if rows:
                    e = rows.pop()
                    try:
                        e.master.destroy()
                    except Exception:
                        pass

            ttk.Button(ctrl, text='＋', width=3, command=lambda: add_row('')).pack(side=tk.LEFT, padx=(0,4))
            ttk.Button(ctrl, text='−', width=3, command=remove_row).pack(side=tk.LEFT)

            # Default three entries; first with example placeholder
            add_row(examples[0] if examples else '', placeholder=True)
            add_row('')
            add_row('')

            return rows

        # Build sections
        task_rows = _mk_section(4, 'Tasks', ['Add overview window when a model is selected'])
        wo_rows = _mk_section(5, 'Work Orders', ['Create Popup Window'])
        tests_rows = _mk_section(6, 'Tests', ['Selecting a model shows overview'])
        f.columnconfigure(1, weight=1); f.rowconfigure(6, weight=1)
        # Prefill examples
        try:
            ov.insert(tk.END, 'Example: Upgrade Chat interface to show model overview panel.')
            obj.insert(tk.END, '- Improve discoverability\n- Reduce clicks\n- Keep layout responsive')
        except Exception:
            pass
        # Create
        def create_plan():
            try:
                title = (name_var.get() or '').strip()
                if not title:
                    messagebox.showwarning('Missing Plan Name','Please enter a plan name.', parent=dlg); return
                prio = pvar.get()
                from config import create_todo_file, create_project_todo_file
                def mk(cat, text_):
                    if project_name:
                        return create_project_todo_file(project_name, cat, text_, prio, '', plan=title)
                    else:
                        return create_todo_file(cat, text_, prio, '', plan=title)
                # Plan body summary
                body_parts = [
                    'Overview:\n' + ov.get('1.0', tk.END).strip(),
                    'Objectives:\n' + obj.get('1.0', tk.END).strip(),
                ]
                # Collect non-empty rows; ignore placeholder examples
                def _collect(rows):
                    out = []
                    for e in rows:
                        try:
                            if getattr(e, '_placeholder', False):
                                continue
                        except Exception:
                            pass
                        val = (e.get() or '').strip()
                        if val:
                            out.append(val)
                    return out
                lines_tasks = _collect(task_rows)
                lines_wo = _collect(wo_rows)
                lines_tests = _collect(tests_rows)
                body_parts.append('Tasks:\n' + '\n'.join(f'- {t}' for t in lines_tasks) or 'Tasks:\n-')
                body_parts.append('Work Orders:\n' + '\n'.join(f'{i+1}. {w}' for i,w in enumerate(lines_wo)) or 'Work Orders:\n1.')
                body_parts.append('Tests:\n' + '\n'.join(f'- {t}' for t in lines_tests) or 'Tests:\n-')
                body = '\n\n'.join(body_parts)
                # Plan file
                if project_name:
                    create_project_todo_file(project_name, 'plans', f'Plan: {title}', prio, body, plan=title)
                else:
                    create_todo_file('plans', f'Plan: {title}', prio, body, plan=title)
                # Derived items
                for t in lines_tasks:
                    mk('tasks', f'Plan:{title} | Task: {t}')
                for i,w in enumerate(lines_wo, 1):
                    mk('work_orders', f'Plan:{title} | Work-Order {i}: {w}')
                for t in lines_tests:
                    mk('tests', f'Plan:{title} | Test: {t}')
                try:
                    # Refresh listings in active popup
                    self.refresh_todo_view()
                except Exception:
                    pass
                dlg.destroy()
            except Exception as e:
                log_message(f'SETTINGS: Error creating plan (dialog): {e}')
                messagebox.showerror('Error', f'Failed to create plan: {e}', parent=dlg)
        b = ttk.Frame(f); b.grid(row=7, column=1, sticky=tk.E, pady=(8,0))
        ttk.Button(b, text='Create Plan', style='Action.TButton', command=create_plan).pack(side=tk.LEFT, padx=4)
        ttk.Button(b, text='Cancel', style='Select.TButton', command=dlg.destroy).pack(side=tk.LEFT, padx=4)

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

        # Custom Code Tab
        self.custom_code_settings_frame = ttk.Frame(self.settings_notebook)
        self.settings_notebook.add(self.custom_code_settings_frame, text="Custom Code")
        self.create_custom_code_settings(self.custom_code_settings_frame)

        # Debug Tab
        self.debug_tab_frame = ttk.Frame(self.settings_notebook)
        self.settings_notebook.add(self.debug_tab_frame, text="Debug")
        self.create_debug_tab(self.debug_tab_frame)

        # System Blueprints Tab
        self.blueprints_tab_frame = ttk.Frame(self.settings_notebook)
        self.settings_notebook.add(self.blueprints_tab_frame, text="System Blueprints")
        self.create_blueprints_tab(self.blueprints_tab_frame)

        # Help & Guide Tab
        self.help_tab_frame = ttk.Frame(self.settings_notebook)
        self.settings_notebook.add(self.help_tab_frame, text="Help & Guide")
        self.create_help_tab(self.help_tab_frame)

        # Bind sub-tab change event
        self.settings_notebook.bind("<<NotebookTabChanged>>", self._on_sub_tab_changed)

        # Right side: Settings categories menu
        self.create_right_panel(self.parent)

    def _on_sub_tab_changed(self, event):
        """Switch between help menu and terminal based on selected sub-tab."""
        selected_tab_index = self.settings_notebook.index(self.settings_notebook.select())
        selected_tab_text = self.settings_notebook.tab(selected_tab_index, "text")

        # Auto-enable Arrow reordering when opening Tab Manager (without popups)
        if selected_tab_text == "Tab Manager":
            try:
                self._suppress_reorder_popup = True
                self.reorder_mode.set('arrow')
                self._on_reorder_mode_changed()
                # Ensure tree reflects live tab instances (panels) once Tab Manager is shown
                try:
                    self.refresh_tabs_tree()
                except Exception:
                    pass
            except Exception:
                pass
            finally:
                self._suppress_reorder_popup = False

        if selected_tab_text == "Debug":
            self.help_menu_frame.grid_remove()
            # Lazy-initialize terminal when Debug is selected
            if not self.terminal_initialized:
                self.create_terminal_ui(self.terminal_frame)
                self.terminal_initialized = True
            self.terminal_frame.grid()
        else:
            # Destroy terminal contents to stop background threads
            try:
                for child in self.terminal_frame.winfo_children():
                    child.destroy()
            except Exception:
                pass
            self.terminal_initialized = False
            self.terminal_frame.grid_remove()
            self.help_menu_frame.grid()

    def create_terminal_ui(self, parent):
        """Creates the terminal interface using tkterminal library."""
        try:
            from tkterminal import Terminal
        except ImportError:
            error_label = ttk.Label(
                parent,
                text="Error: 'tkterminal' library not found.\nPlease install it by running: pip install tkterminal",
                foreground="red",
                wraplength=300
            )
            error_label.pack(pady=20, padx=10)
            return

        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(1, weight=1)

        # Header with reset button
        header = ttk.Frame(parent)
        header.grid(row=0, column=0, sticky=tk.EW, padx=5, pady=5)
        ttk.Button(header, text="🔁 Reset Terminal", command=lambda: self.reset_terminal(parent), style='Select.TButton').pack(side=tk.LEFT)

        self.terminal = Terminal(parent, pady=5, padx=5)
        self.terminal.shell = True
        self.terminal_widget = self.terminal
        self.terminal_widget.grid(row=1, column=0, sticky='nsew')

        # Use main-thread safe scheduling for terminal commands
        try:
            self.root.after(0, lambda: self.terminal_widget.run_command(f"cd {DATA_DIR} && clear"))
            self.root.after(10, lambda: self.terminal_widget.run_command("echo 'Welcome to the in-house terminal!'"))
            self.root.after(20, lambda: self.terminal_widget.run_command(f"echo 'Working directory: $(pwd)'"))
        except Exception as e:
            log_message(f"SETTINGS: Terminal init scheduling error: {e}")

    def reset_terminal(self, parent):
        """Destroy and recreate the terminal widget to clear state and stop any background threads."""
        try:
            for child in parent.winfo_children():
                child.destroy()
        except Exception:
            pass
        # Recreate terminal UI
        self.create_terminal_ui(parent)



    def create_right_panel(self, parent):
        """Create the right-side panel which can contain either the help menu or the terminal."""
        self.right_panel = ttk.Frame(parent)
        self.right_panel.grid(row=0, column=1, sticky=tk.NSEW, padx=10, pady=10)
        self.right_panel.columnconfigure(0, weight=1)
        self.right_panel.rowconfigure(0, weight=1)

        # --- Help Menu Frame ---
        self.help_menu_frame = ttk.Frame(self.right_panel, style='Category.TFrame')
        self.help_menu_frame.grid(row=0, column=0, sticky='nsew')
        self.help_menu_frame.columnconfigure(0, weight=1)
        self.help_menu_frame.rowconfigure(1, weight=1)
        self.help_menu_frame.rowconfigure(2, weight=0)

        ttk.Label(self.help_menu_frame, text="🆘 Help Menu",
                 font=("Arial", 11, "bold"), style='CategoryPanel.TLabel').grid(
            row=0, column=0, pady=5, sticky=tk.W, padx=5
        )

        self.help_paned = ttk.PanedWindow(self.help_menu_frame, orient=tk.VERTICAL)
        self.help_paned.grid(row=1, column=0, sticky='nsew', padx=5, pady=5)

        tree_container = ttk.Frame(self.help_paned)
        self.help_paned.add(tree_container, weight=1)
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
        self.help_tree.bind('<<TreeviewSelect>>', self.on_help_topic_select)
        
        self.populate_help_tree()

        # Help text pane is created but not added until a topic is selected
        self.help_text_frame = ttk.Frame(self.help_paned, style='Category.TFrame')
        self.help_text_frame.columnconfigure(0, weight=1)
        self.help_text_frame.rowconfigure(0, weight=1)

        self.help_display = scrolledtext.ScrolledText(
            self.help_text_frame, wrap=tk.WORD, state=tk.DISABLED, font=("Arial", 9),
            bg="#1e1e1e", fg="#d4d4d4", relief='flat', padx=5, pady=5
        )
        self.help_display.grid(row=0, column=0, sticky='nsew')

        # --- ToDo List Section (as a pane under the help content) ---
        self.todo_section = ttk.Frame(self.help_paned, style='Category.TFrame')
        self.help_paned.add(self.todo_section, weight=1)
        self.todo_section.columnconfigure(0, weight=1)

        # Header with dynamic counts, centered
        # Todo header with separate lines for better layout
        self.todo_counts_var = tk.StringVar(value="Tasks: 0 | Bugs: 0 | Work-Orders: 0 | Notes: 0 | Completed: 0")
        self.todo_priority_var = tk.StringVar(value="Priority: High 0 | Medium 0 | Low 0")
        header_row = ttk.Frame(self.todo_section, style='Category.TFrame')
        header_row.grid(row=0, column=0, sticky=tk.EW, pady=(4, 0))
        header_row.columnconfigure(0, weight=0)
        header_row.columnconfigure(1, weight=1)

        # Show-on-launch checkbox (no label)
        self.todo_show_on_launch = tk.BooleanVar(value=self.settings.get('todo_show_on_launch', False))
        cb = ttk.Checkbutton(header_row, variable=self.todo_show_on_launch, command=self._on_todo_show_on_launch_changed)
        cb.grid(row=0, column=0, rowspan=2, sticky=tk.W, padx=(0,8))

        # Two-line header for better fit
        ttk.Label(header_row, textvariable=self.todo_counts_var, font=("Arial", 10, "bold"), style='CategoryPanel.TLabel', anchor='center').grid(row=0, column=1, sticky=tk.EW)
        ttk.Label(header_row, textvariable=self.todo_priority_var, font=("Arial", 9), style='CategoryPanel.TLabel', anchor='center').grid(row=1, column=1, sticky=tk.EW)

        # Action buttons row
        buttons_row = ttk.Frame(self.todo_section)
        buttons_row.grid(row=1, column=0, sticky=tk.EW, pady=(6, 6))
        buttons_row.columnconfigure(0, weight=1)
        buttons_row.columnconfigure(1, weight=1)
        buttons_row.columnconfigure(2, weight=1)
        buttons_row.columnconfigure(3, weight=1)
        self.todo_btn_create = ttk.Button(buttons_row, text="➕ Create Todo", command=self.todo_create, style='Action.TButton')
        self.todo_btn_create.grid(row=0, column=0, padx=3, sticky=tk.EW)
        self.todo_btn_mark = ttk.Button(buttons_row, text="✔ Mark Complete", command=self.todo_mark_complete, style='Select.TButton')
        self.todo_btn_mark.grid(row=0, column=1, padx=3, sticky=tk.EW)
        self.todo_btn_edit = ttk.Button(buttons_row, text="✏️ Edit Todo", command=self.todo_edit, style='Select.TButton')
        self.todo_btn_edit.grid(row=0, column=2, padx=3, sticky=tk.EW)
        self.todo_btn_delete = ttk.Button(buttons_row, text="🗑 Delete Todo", command=self.todo_delete, style='Select.TButton')
        self.todo_btn_delete.grid(row=0, column=3, padx=3, sticky=tk.EW)

        # Tree for Tasks/Bugs/Completed with checkbox-like glyphs
        tree_wrap = ttk.Frame(self.todo_section)
        tree_wrap.grid(row=2, column=0, sticky='nsew')
        self.todo_section.rowconfigure(2, weight=1)
        tree_scroll = ttk.Scrollbar(tree_wrap, orient="vertical")
        tree_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.todo_tree = ttk.Treeview(tree_wrap, columns=("done",), show='tree headings')
        self.todo_tree.heading('#0', text='Item')
        self.todo_tree.heading('done', text='Done')
        self.todo_tree.column('done', width=60, anchor=tk.CENTER, stretch=False)
        self.todo_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.todo_tree.configure(yscrollcommand=tree_scroll.set)
        tree_scroll.config(command=self.todo_tree.yview)
        # Styles for completed
        self.todo_tree.tag_configure('completed', foreground='#8a8a8a', font=('Arial', 9, 'italic'))
        # Bind click to toggle checkbox in 'done' column
        self.todo_tree.bind('<Button-1>', self._on_todo_click, add=True)

        # Initialize storage and populate
        if not hasattr(self, 'todos'):
            self.todos = { 'tasks': [], 'bugs': [], 'work_orders': [], 'notes': [], 'completed': [] }
        else:
            # Backfill new categories if missing
            self.todos.setdefault('work_orders', [])
            self.todos.setdefault('notes', [])
        self.todo_tree.bind('<<TreeviewSelect>>', self._on_todo_selection_changed)
        self._wire_todo_button_hover()
        self.refresh_todo_view()

        # --- Terminal Frame (created here, but hidden) ---
        self.terminal_frame = ttk.Frame(self.right_panel, style='Category.TFrame')
        self.terminal_frame.grid(row=0, column=0, sticky='nsew')
        # Do not initialize the terminal yet; wait until Debug tab is selected
        self.terminal_frame.grid_remove() # Hide it initially

    def populate_help_tree(self):
        """Populate the help tree with application structure and help text."""
        for item in self.help_tree.get_children():
            self.help_tree.delete(item)

        self.help_structure = {
            "Automation Guide": {
                "description": "How to drive common workflows with minimal clicks using Quick Actions, saved orders, and defaults.",
                "sub_tabs": {
                    "Quick Actions": "Use ⚙ at bottom-left in Chat to access: Working Dir, Tools, Think Time (one-shot), Mode, Prompt/Schema, Temperature (Manual/Auto), and ToDo. The icon grid wraps and auto-hides when clicking away.",
                    "Indicators": "Next to ⚙: ⏱ ThinkTime pending • 📂 Working dir (hover shows path) • 🔧 Enabled tools (hover lists) • 🌡 Temp (value + Manual/Auto) • 🗒 ToDo popup active • ⚡ Mode • 📝 Prompt/Schema.",
                    "Save Tab Order": "In Settings → Tab Manager, Arrow mode lets you reorder tabs/panels. Click 'Save Tab Order' to persist both main tabs and per-tab panel order.",
                    "Show ToDo on Launch": "Enable the checkbox left of the ToDo header under Help & Guide to display ToDo on startup. ToDo v2 supports categories (Tasks, Bugs, Work-Orders, Notes, Completed) and priorities (High/Medium/Low) with color coding.",
                }
            },
            "Manual Guide": {
                "description": "Detailed, step-by-step usage for manual workflows and training.",
                "sub_tabs": {
                    "System Prompt & Tool Schema": "From Quick Actions → 📝 open the unified manager. Top toggles switch between System Prompt and Tool Schema. 'Select & Apply' remounts the model if mounted.",
                    "Temperature": "Click 🌡 to choose Manual (adjust slider in popup and Save) or Auto (uses training stats). Mode and value persist per session and are shown in the bottom indicator.",
                    "Think Time": "From Quick Actions → ⏱ set min/max seconds for the next input only. A ⏱ indicator appears while pending.",
                    "Chat Sessions": "Use 🆕 New Chat; 🗑 Delete Chat; ✏️ Rename Chat (Chat tab and Projects). History supports load/export/delete.",
                }
            },
            "Project Blueprint v2": {
                "description": "High-level system plan and current state.",
                "sub_tabs": {
                    "Overview": "See extras/blueprints/Trainer_Blue_Print_v2.0.txt for the v2 plan, roadmap, dependencies, and acceptance for v2.1.",
                }
            },
            "Git & Branching": {
                "description": "Local Git workflow and branches used for docs/blueprints.",
                "sub_tabs": {
                    "START_HERE": "Read START_HERE.md for setup, branching (docs/blueprint-v2), and commit conventions.",
                }
            },
            "Beginner’s Guide": {
                "description": "A step‑by‑step path from a fresh PyTorch model to a verified skillset: datasets → baseline → training → export → evaluation → compare.",
                "sub_tabs": {
                    "Getting Started": "Install or prepare a local PyTorch base model under Models/. In Models → Overview, select the base to work with. Ensure Ollama is running for inference (/api/chat).",
                    "Datasets": "Place evaluation suites under Training_Data‑Sets/Test (e.g., Tools/). Put training JSONL under Training_Data‑Sets (Tools, Coding, etc.). You can use or extend the examples provided.",
                    "Run Baseline": "Models → 🧪 Evaluation: choose a suite (e.g., Tools), select Tool Schema 'json_calls_full', and System Prompt 'Tools_JSON_Calls_Conformer'. Check 'Run as Baseline'. If no GGUF exists, export/pull first; the baseline will auto‑resume with the created tag and be saved under Models/benchmarks, set active.",
                    "Train & Level Up": "Training → Runner: commit your base and scripts, then train. Create Level 1 from adapters. Export level to GGUF (pick quant).",
                    "Evaluate & Compare": "Evaluate the Level; Compare vs the parent’s active baseline. Review overall Δ and per‑skill changes. History, Skills, and Baselines tabs update automatically.",
                    "Tips": "For Tools suite, json_calls_full + Tools_JSON_Calls_Conformer improves accuracy. Keep baselines full (no sampling). Use 'Create New' baselines to preserve history; optionally delete old when prompted."
                }
            },
            "Training Tab": {
                "description": "Prepare, run, and validate training. Left: sub‑tabs (Runner, Script Manager, Model Selection, Profiles, Summary). Right: selectors (Training Scripts, Prompts, Schemas).",
                "sub_tabs": {
                    "Runner": "Run training with a live console. Supports sequential execution (queues selected scripts) and delay between runs. Start/Stop/Clear/Status are fixed at the bottom for quick access. Early Stopping is shown only when a GPU is available. Save/Load Defaults persists runner controls.\n\nEvaluation Automation (scheduling): Auto‑run Baseline and Auto‑run Post‑Training.\nEvaluation Context: enable 'Use System Prompt' / 'Use Tool Schema' for automation.\nBaseline Controls: select baseline source (Auto/Base/Level) and open the Baselines manager.\n\n**(NEW)** Post-training evaluation is now automatically triggered after a training run, generating a report linked to the run's stats.",
                    "Script Manager": "A self-contained manager with three sub-tabs: 'Training Scripts', 'Prompts', and 'Schemas'. Each tab features an editor and a consistent set of action buttons at the bottom: `[➕ New File(s)] [📁 New Category] [💾 Save] [✏️ Rename] [🗑️ Delete] [❌ Clear] [📎 Copy]`. Selections in the main right-side panel of the Training Tab will load the corresponding file into the editor here.",
                    "Model Selection": "Dropdown lists only trainable models (local PyTorch and trained). Selecting shows detailed info (architecture, core parameters, latest training stats, and skills). Click 'Send To Training' to commit the selection (Runner's 'Training Model' updates then). Missing data is shown as 'Unverified'.",
                    "Profiles": "Save/load full setups: runner controls, committed model, right‑side selections (scripts/jsonl) and evaluation preferences (Use Prompt/Schema + selected names). Loading re‑applies toggles and selections.",
                    "Summary": "Read‑only preview: categories/files, core params, base model, and Use Prompt/Schema state (with names when enabled)."
                }
            },
            "Models Tab": {
                "description": "Inspect models, run evaluations, and compare results.",
                "sub_tabs": {
                    "Overview": "Parsed model info (type, path, size) and, when available, architecture/stats.",
                    "Raw Info": "Raw metadata (e.g., config.json) or Ollama show output.",
                    "Notes": "Free‑form notes per model.",
                    "Stats": "Training runs with filtering.\n\n**(NEW)** Now displays detailed evaluation results for each training run, including comparison against the active baseline (overall delta, regressions, improvements). Offers training suggestions if regressions are found.",
                    "Skills": "Skills aggregated from the latest evaluation report (per‑skill pass/total and status). **(NEW)** Now also displays the System Prompt and Tool Schema used for the evaluation.",
                    "🧪 Evaluation": "Suites come from `Training_Data-Sets/Test/<suite>`. Toggle 'Use System Prompt' / 'Use Tool Schema'. When a Tool Schema is selected, scoring is schema‑aware: tool name and args must validate against the schema before applying the test's policy (exact/partial/subset/function_call). 'Run as Pre‑Training Baseline' opens a confirm dialog and saves to `Models/benchmarks/`; otherwise to `Models/evaluations/`.",
                    "Baselines": "Manage baselines per model. View JSON, Set Active. Catalog stored at `Models/benchmarks/index.json`. Active baseline is used for regression checks and quick comparisons.",
                    "Compare": "Parent‑centric compare with three modes: (1) Baseline vs Baseline (Parent), (2) Latest Eval vs Reference (Parent), and (3) Advanced: Other Model (latest eval). Baseline lists autoload for the selected Parent with readable labels (date | pass% | suite | schema | prompt). Buttons below the result: '🧠 Generate Training Suggestions' (reason breakdown + JSONL stubs) and '💾 Save Example Stubs' (writes to Training_Data‑Sets/Tools).",
                    "Model List Sidebar": "Groups into Base (PyTorch), Trained, and Ollama (inference‑only)."
                }
            },
            "Settings Tab": {
                "description": "Global preferences and developer tools.",
                "sub_tabs": {
                    "General": "Overview and quick actions (save/reset settings).",
                    "Paths": "Key directories used by the app.",
                    "Training Defaults": "Default epochs/batch/lr used by Runner when not overridden.",
                    "Interface": "Tab visibility/order and reordering mode (static/dnd).",
                    "Tab Manager": "Create/edit tabs and panels programmatically.",
                    "Resources": "CPU threads, RAM %, seq length, gradient accumulation (applied in training).",
                    "Debug": "Live log viewer with history and 'Copy to Clipboard'. Captures wrapper early logs.",
                    "Evaluation Policy": "Regression checks: enable, drop threshold (in %), strict notifications; auto‑rollback is reserved for future use."
                }
            }
        }

        for main_tab_name, main_tab_data in self.help_structure.items():
            tab_node = self.help_tree.insert(
                '', 'end', text=main_tab_name, open=True, tags=('main_tab',)
            )
            # Add description for main tab
            if "description" in main_tab_data:
                self.help_tree.insert(tab_node, 'end', text="Description", tags=('description',))

            for sub_tab_name in main_tab_data.get("sub_tabs", {}).keys():
                self.help_tree.insert(tab_node, 'end', text=sub_tab_name)

    def on_help_topic_select(self, event):
        """Displays the help text for the selected topic."""
        selection = self.help_tree.selection()
        if not selection:
            return

        item_id = selection[0]
        parent_id = self.help_tree.parent(item_id)
        
        help_text = "No help available for this topic."

        if parent_id: # It's a sub-tab or a description node
            main_tab_text = self.help_tree.item(parent_id, 'text')
            item_text = self.help_tree.item(item_id, 'text')
            
            if item_text == "Description":
                help_text = self.help_structure.get(main_tab_text, {}).get("description", help_text)
            else:
                help_text = self.help_structure.get(main_tab_text, {}).get("sub_tabs", {}).get(item_text, help_text)
        else: # It's a main tab
            main_tab_text = self.help_tree.item(item_id, 'text')
            help_text = self.help_structure.get(main_tab_text, {}).get("description", help_text)

        # Ensure help text pane is visible (add to paned if not already present)
        try:
            panes = [str(p) for p in getattr(self.help_paned, 'panes')()] if hasattr(self, 'help_paned') else []
            if hasattr(self, 'help_text_frame') and str(self.help_text_frame) not in panes:
                self.help_paned.insert(1, self.help_text_frame, weight=1)
        except Exception:
            pass

        self.help_display.config(state=tk.NORMAL)
        self.help_display.delete(1.0, tk.END)
        self.help_display.insert(tk.END, help_text)
        self.help_display.config(state=tk.DISABLED)

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

        # Scrollable root for entire Tab Manager panel
        scroll_root = ttk.Frame(parent)
        scroll_root.grid(row=0, column=0, sticky=tk.NSEW)
        scroll_root.columnconfigure(0, weight=1)
        scroll_root.rowconfigure(0, weight=1)

        canvas = tk.Canvas(scroll_root, borderwidth=0, highlightthickness=0)
        vscroll = ttk.Scrollbar(scroll_root, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=vscroll.set)
        canvas.grid(row=0, column=0, sticky=tk.NSEW)
        vscroll.grid(row=0, column=1, sticky=tk.NS)

        # Inner container that actually holds the content
        container = ttk.Frame(canvas)
        # Create window for inner frame
        canvas_window = canvas.create_window((0, 0), window=container, anchor="nw")

        # Configure resizing behavior
        def _on_container_configure(event=None):
            try:
                canvas.configure(scrollregion=canvas.bbox("all"))
                # Keep inner frame width synced to canvas width for nice layout
                canvas.itemconfigure(canvas_window, width=canvas.winfo_width())
            except Exception:
                pass

        container.bind("<Configure>", _on_container_configure)
        canvas.bind("<Configure>", _on_container_configure)

        # Mouse wheel on hover for the canvas area (bind_all only while hovering)
        try:
            self._bind_mousewheel_to_canvas_hover(canvas, hover_widgets=[canvas, container])
        except Exception:
            pass

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

        # Tab Visibility Section
        visibility_frame = ttk.LabelFrame(container, text="👁️ Tab Visibility", style='TLabelframe')
        visibility_frame.grid(row=2, column=0, sticky=tk.EW, pady=10)
        visibility_frame.columnconfigure(0, weight=1)

        # Populate with checkboxes for each tab
        self._populate_tab_visibility_controls(visibility_frame)

        # Existing Tabs Browser Section
        browser_frame = ttk.LabelFrame(container, text="📂 Tab Browser & Editor", style='TLabelframe')
        browser_frame.grid(row=3, column=0, sticky=tk.NSEW, pady=10) # Adjusted row
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

        # Mouse wheel on hover for the structure tree (bind to both tree and its container)
        try:
            self._bind_mousewheel_to_tree(self.tabs_tree, tree_container)
        except Exception:
            pass

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

        # Panel selector UI (appears when a tab is selected)
        self.panel_select_container = ttk.Frame(editor_frame)
        ttk.Label(self.panel_select_container, text="Select Panel:", style='Config.TLabel').pack(side=tk.LEFT, padx=(0,8))
        self.panel_selector = ttk.Combobox(self.panel_select_container, state='readonly', width=28)
        self.panel_selector.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.panel_selector.bind('<<ComboboxSelected>>', self._on_panel_combo_changed)
        # Initially hidden
        self.panel_select_container.pack_forget()
        # Panel selection indicator
        self.panel_selected_label = ttk.Label(editor_frame, text="", style='Config.TLabel')
        self.panel_selected_label.pack(pady=(4,10))
        # Track which tab drives the panel selector
        self.current_tab_for_panel_selector = None

        # Action buttons
        actions_frame = ttk.Frame(editor_frame)
        actions_frame.pack(fill=tk.X, padx=10, pady=10)

        self.move_left_button = ttk.Button(
            actions_frame,
            text="⬅️ Move Left",
            command=lambda: self.move_tab("left"),
            style='Action.TButton'
        )
        
        self.move_right_button = ttk.Button(
            actions_frame,
            text="➡️ Move Right",
            command=lambda: self.move_tab("right"),
            style='Action.TButton'
        )

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

        # Initially hide the move buttons
        self.move_left_button.pack_forget()
        self.move_right_button.pack_forget()

    def _bind_mousewheel_to_tree(self, tree_widget, container_widget=None):
        """Enable mouse wheel scrolling on hover for Treeview (Linux/Windows/Mac)."""
        import platform
        system = platform.system()

        targets = [tree_widget]
        if container_widget is not None:
            targets.append(container_widget)

        if system == "Linux":
            def _on_up(event):
                tree_widget.yview_scroll(-1, "units")
                return "break"
            def _on_down(event):
                tree_widget.yview_scroll(1, "units")
                return "break"
            for w in targets:
                w.bind("<Button-4>", _on_up, add=True)
                w.bind("<Button-5>", _on_down, add=True)
        else:
            def _on_wheel(event):
                try:
                    delta = int(-1 * (event.delta / 120))
                except Exception:
                    delta = -1
                tree_widget.yview_scroll(delta, "units")
                return "break"
            for w in targets:
                w.bind("<MouseWheel>", _on_wheel, add=True)

    def _bind_mousewheel_to_canvas_hover(self, canvas_widget, hover_widgets=None):
        """Enable scrolling the Tab Manager canvas with the mouse wheel while hovering.

        Uses bind_all only during hover to capture wheel events anywhere over the
        scrollable area (including inner child widgets), but allows inner widgets
        like the Treeview to consume events by returning "break" first.
        """
        import platform
        system = platform.system()

        if hover_widgets is None:
            hover_widgets = [canvas_widget]

        # Handlers that scroll the canvas
        if system == "Linux":
            def _wheel_up(event):
                canvas_widget.yview_scroll(-1, "units")
                return "break"
            def _wheel_down(event):
                canvas_widget.yview_scroll(1, "units")
                return "break"
            def _enable(_e=None):
                canvas_widget.bind_all("<Button-4>", _wheel_up)
                canvas_widget.bind_all("<Button-5>", _wheel_down)
            def _disable(_e=None):
                canvas_widget.unbind_all("<Button-4>")
                canvas_widget.unbind_all("<Button-5>")
        else:
            def _wheel_any(event):
                try:
                    delta = int(-1 * (event.delta / 120))
                except Exception:
                    delta = -1
                canvas_widget.yview_scroll(delta, "units")
                return "break"
            def _enable(_e=None):
                canvas_widget.bind_all("<MouseWheel>", _wheel_any)
            def _disable(_e=None):
                canvas_widget.unbind_all("<MouseWheel>")

        # Attach enter/leave to both the canvas and inner container
        for w in hover_widgets:
            w.bind("<Enter>", _enable, add=True)
            w.bind("<Leave>", _disable, add=True)

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
        log_message("SETTINGS: Refreshing tabs tree.")
        log_message(f"SETTINGS: Tab order from settings: {self.settings.get('tab_order')}")
        # Clear existing tree
        for item in self.tabs_tree.get_children():
            self.tabs_tree.delete(item)
        # Reset panel file mapping
        self.panel_file_map = {}

        tabs_dir = DATA_DIR / "tabs"
        if not tabs_dir.exists():
            return

        # Define built-in tabs with special handling
        built_in_tabs = {
            'settings_tab': {
                'display': 'Settings',
                'icon': '⚙️',
                'main_file': 'settings_tab.py',
                'panels': []
            },
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
                'icon': '🧠',
                'main_file': 'models_tab.py',
                'panels': []
            }
        }

        # Get the saved tab order
        saved_order = self.settings.get('tab_order', ['training_tab', 'models_tab', 'custom_code_tab', 'settings_tab'])
        
        # Get all tab directories
        all_tab_dirs = {tab_dir.name: tab_dir for tab_dir in sorted(tabs_dir.iterdir()) if tab_dir.is_dir() and not tab_dir.name.startswith('__')}
        
        processed_tabs = set()

        # Add tabs in the saved order
        for tab_dir_name in saved_order:
            if tab_dir_name in all_tab_dirs:
                self._add_tab_to_tree(all_tab_dirs[tab_dir_name], built_in_tabs)
                processed_tabs.add(tab_dir_name)

        # Add any remaining tabs that were not in the saved order
        for tab_dir_name, tab_dir in all_tab_dirs.items():
            if tab_dir_name not in processed_tabs:
                self._add_tab_to_tree(tab_dir, built_in_tabs)

    def _add_tab_to_tree(self, tab_dir, built_in_tabs):
        """Add a single tab node and its live panel headers, hiding raw files."""
        tab_name = tab_dir.name

        # Determine display name and icon
        if tab_name in built_in_tabs:
            tab_info = built_in_tabs[tab_name]
            tab_display_name = tab_info['display']
            icon = tab_info['icon']
        else:
            tab_display_name = tab_dir.name.replace('_tab', '').replace('_', ' ').title()
            icon = '📂'

        # Add tab as root node (store tab_name, not path)
        tab_node = self.tabs_tree.insert(
            '', 'end',
            text=f"{icon} {tab_display_name}",
            values=(tab_name, 'tab'),
            tags=('tab',)
        )

        # Add panel headers from the live notebook (if available)
        instance = None
        try:
            if self.tab_instances and tab_name in self.tab_instances:
                instance = self.tab_instances[tab_name]['instance']
        except Exception:
            instance = None

        notebook = None
        if instance is not None:
            # Known notebook attributes by tab
            for attr in (
                'training_notebook',    # TrainingTab
                'sub_notebook',         # CustomCodeTab
                'settings_notebook',    # SettingsTab
                'model_info_notebook',  # ModelsTab
                'models_notebook'       # Fallback (older naming)
            ):
                nb = getattr(instance, attr, None)
                if nb is not None:
                    notebook = nb
                    break

        if notebook is not None:
            try:
                tab_ids = notebook.tabs()
                for i, tid in enumerate(tab_ids):
                    try:
                        header = notebook.tab(tid, 'text')
                    except Exception:
                        header = f"Panel {i+1}"

                    # Record potential file mapping for known tabs
                    file_path = self._resolve_panel_file(tab_name, header, tab_dir)
                    if file_path:
                        self.panel_file_map[(tab_name, header)] = file_path

                    self.tabs_tree.insert(
                        tab_node,
                        'end',
                        text=f"🔧 {header}",
                        values=(f"{tab_name}|{header}", 'panel_header'),
                        tags=('panel',)
                    )
            except Exception:
                pass

        # Expand by default
        self.tabs_tree.item(tab_node, open=True)

    def _resolve_panel_file(self, tab_name, header_text, tab_dir):
        """Best-effort mapping from panel header to its source file for built-in tabs."""
        try:
            if tab_name == 'training_tab':
                mapping = {
                    'Runner': 'runner_panel.py',
                    'Script Manager': 'category_manager_panel.py',
                    'Model Selection': 'model_selection_panel.py',
                    'Profiles': 'profiles_panel.py',
                    'Summary': 'summary_panel.py',
                }
                fn = mapping.get(header_text)
                if fn:
                    p = tab_dir / fn
                    return p if p.exists() else None
            # Custom Code panels are all in custom_code_tab.py; skip mapping to file
        except Exception:
            pass
        return None

    def on_tree_select(self, event):
        """Handle tree item selection"""
        selection = self.tabs_tree.selection()
        if not selection:
            if hasattr(self, 'move_left_button'):
                self.move_left_button.config(state=tk.DISABLED)
                self.move_right_button.config(state=tk.DISABLED)
            # Hide panel selector
            self.panel_select_container.pack_forget()
            self.panel_selected_label.config(text="")
            return

        item = selection[0]
        values = self.tabs_tree.item(item, 'values')

        if not values:
            if hasattr(self, 'move_left_button'):
                self.move_left_button.config(state=tk.DISABLED)
                self.move_right_button.config(state=tk.DISABLED)
            return

        raw_key, item_type = values
        # Decode selection meta
        if item_type == 'tab':
            tab_name = raw_key
            self.selected_tree_item = {'type': 'tab', 'tab_name': tab_name, 'path': Path(DATA_DIR) / 'tabs' / tab_name}
        elif item_type == 'panel_header':
            # raw_key = "tab_name|header"
            try:
                tab_name, header = raw_key.split('|', 1)
            except ValueError:
                tab_name, header = raw_key, ''
            info = {'type': 'panel_header', 'tab_name': tab_name, 'panel_header': header}
            file_path = self.panel_file_map.get((tab_name, header))
            if file_path:
                info['path'] = file_path
            self.selected_tree_item = info
        else:
            # Fallback to previous behavior
            self.selected_tree_item = {'path': Path(raw_key), 'type': item_type}

        # Update info label and button states
        if item_type in ('tab', 'panel_header') and self.reorder_mode.get() == 'arrow':
            # Always persist Tab label at the top
            tab_name_for_label = self.selected_tree_item.get('tab_name') if item_type == 'panel_header' else self.selected_tree_item.get('tab_name')
            self.selected_info_label.config(text=f"Tab: {tab_name_for_label}")
            if hasattr(self, 'move_left_button'):
                self.move_left_button.config(state=tk.NORMAL)
                self.move_right_button.config(state=tk.NORMAL)
            # Show and sync panel selector
            if item_type == 'tab':
                self._show_panel_selector(self.selected_tree_item.get('tab_name'))
            else:
                header = self.selected_tree_item.get('panel_header')
                self._show_panel_selector(self.selected_tree_item.get('tab_name'), preselect=header)
                # Show panel indicator separately
                self.panel_selected_label.config(text=f"Panel: {header}")
        else:
            if hasattr(self, 'move_left_button'):
                self.move_left_button.config(state=tk.DISABLED)
                self.move_right_button.config(state=tk.DISABLED)
            if item_type == 'tab':
                self.selected_info_label.config(text=f"Tab: {self.selected_tree_item.get('tab_name')}")
                self._show_panel_selector(self.selected_tree_item.get('tab_name'))
            elif item_type == 'panel_header':
                # Persist Tab label and show panel indicator below
                self.selected_info_label.config(text=f"Tab: {self.selected_tree_item.get('tab_name')}")
                header = self.selected_tree_item.get('panel_header')
                self._show_panel_selector(self.selected_tree_item.get('tab_name'), preselect=header)
                self.panel_selected_label.config(text=f"Panel: {header}")

    def _get_tab_notebook(self, tab_name):
        """Return the ttk.Notebook for the given tab instance, if any."""
        try:
            if not self.tab_instances or tab_name not in self.tab_instances:
                return None
            instance = self.tab_instances[tab_name]['instance']
            for attr in (
                'training_notebook',
                'sub_notebook',
                'settings_notebook',
                'model_info_notebook',
                'models_notebook'
            ):
                nb = getattr(instance, attr, None)
                if nb is not None:
                    return nb
        except Exception:
            return None
        return None

    def _get_panel_headers(self, tab_name):
        """List of panel header texts for the tab's notebook."""
        nb = self._get_tab_notebook(tab_name)
        if nb is None:
            return []
        headers = []
        try:
            for tid in nb.tabs():
                try:
                    headers.append(nb.tab(tid, 'text'))
                except Exception:
                    headers.append('')
        except Exception:
            pass
        return headers

    def _show_panel_selector(self, tab_name, preselect=None):
        """Populate and show the panel selector for a given tab."""
        headers = [h for h in self._get_panel_headers(tab_name) if h]
        if not headers:
            self.panel_select_container.pack_forget()
            self.panel_selected_label.config(text="")
            self.current_tab_for_panel_selector = None
            return
        self.current_tab_for_panel_selector = tab_name
        # Update combobox values and selection
        try:
            self.panel_selector['values'] = headers
        except Exception:
            pass
        if preselect and preselect in headers:
            self.panel_selector.set(preselect)
            self.panel_selected_label.config(text=f"Panel: {preselect}")
        else:
            # No preselect: leave empty until user picks
            try:
                self.panel_selector.set("")
            except Exception:
                pass
            self.panel_selected_label.config(text="")
        # Show container
        self.panel_select_container.pack(fill=tk.X, padx=10)

        # Do not change selected_tree_item here unless preselect used
        if preselect and preselect in headers:
            selected_header = preselect
            info = {'type': 'panel_header', 'tab_name': tab_name, 'panel_header': selected_header}
            file_path = self.panel_file_map.get((tab_name, selected_header))
            if file_path:
                info['path'] = file_path
            self.selected_tree_item = info

    def _on_panel_combo_changed(self, event=None):
        """Handle selection change from the panel combobox."""
        tab_name = self.current_tab_for_panel_selector
        if not tab_name:
            return
        header = self.panel_selector.get()
        self.panel_selected_label.config(text=f"Panel: {header}")
        info = {'type': 'panel_header', 'tab_name': tab_name, 'panel_header': header}
        file_path = self.panel_file_map.get((tab_name, header))
        if file_path:
            info['path'] = file_path
        self.selected_tree_item = info

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
        """Open selected panel file in default editor (when resolvable)."""
        if not self.selected_tree_item:
            messagebox.showwarning(
                "No Selection",
                "Please select a file from the tree to edit.\n\n"
                "You can edit:\n"
                "• Panel files (🔧)\n"
                "• Main tab files (📄)"
            )
            return

        stype = self.selected_tree_item.get('type')
        if stype not in ['panel', 'main_file', 'panel_header']:
            messagebox.showwarning(
                "Invalid Selection",
                f"Cannot edit {stype}.\n\n"
                "Please select a panel file (🔧) or main file (📄)."
            )
            return

        # For panel_header, we may not have a file path
        file_path = self.selected_tree_item.get('path')
        if stype == 'panel_header' and not file_path:
            messagebox.showinfo(
                "Not Editable",
                "This panel does not map to a single source file."
            )
            return

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
        settings = {}
        if self.settings_file.exists():
            try:
                with open(self.settings_file, 'r') as f:
                    settings = json.load(f)
                logger_util.log_message("SETTINGS: Settings file loaded successfully.")
            except Exception as e:
                logger_util.log_message(f"SETTINGS ERROR: Error loading settings: {e}")
            
        # Load tab visibility settings into tk.BooleanVars
        for display_name, setting_key in [
            ("Training Tab", "training_tab_enabled"),
            ("Models Tab", "models_tab_enabled"),
            ("Settings Tab", "settings_tab_enabled"),
            ("Custom Code Tab", "custom_code_tab_enabled"),
        ]:
            # Initialize var if not already done (e.g., in __init__)
            if setting_key not in self.tab_enabled_vars:
                self.tab_enabled_vars[setting_key] = tk.BooleanVar()
            self.tab_enabled_vars[setting_key].set(settings.get(setting_key, True)) # Default to enabled

            self.reorder_mode.set(settings.get('reorder_mode', 'static')) # Default to static

        # Load ToDos
        try:
            self.todos = settings.get('todos', { 'tasks': [], 'bugs': [], 'completed': [] })
        except Exception:
            self.todos = { 'tasks': [], 'bugs': [], 'completed': [] }

        return settings

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
            
            # Save tab visibility settings
            for setting_key, var in self.tab_enabled_vars.items():
                all_settings[setting_key] = var.get()

            # Save tab reordering setting
            all_settings['reorder_mode'] = self.reorder_mode.get()

            # Ensure custom_code_tab is in tab_order if it's enabled
            tab_order = self.settings.get('tab_order', ['training_tab', 'models_tab', 'custom_code_tab', 'settings_tab'])
            if 'custom_code_tab' not in tab_order and self.tab_enabled_vars.get('custom_code_tab_enabled', tk.BooleanVar(value=False)).get():
                # Insert custom_code_tab before settings_tab if enabled
                if 'settings_tab' in tab_order:
                    idx = tab_order.index('settings_tab')
                    tab_order.insert(idx, 'custom_code_tab')
                else:
                    tab_order.append('custom_code_tab')
            all_settings['tab_order'] = tab_order

            # Save Regression Policy
            if not hasattr(self, 'policy_alert_drop'):
                # Initialize defaults if UI not visited
                self.policy_enabled = tk.BooleanVar(value=True)
                self.policy_alert_drop = tk.DoubleVar(value=5.0)
                self.policy_strict_block = tk.BooleanVar(value=False)
                self.policy_auto_rollback = tk.BooleanVar(value=False)
            all_settings['regression_policy'] = {
                'enabled': self.policy_enabled.get(),
                'alert_drop_percent': float(self.policy_alert_drop.get()),
                'strict_block': self.policy_strict_block.get(),
                'auto_rollback': self.policy_auto_rollback.get()
            }

            # If caller populated panel_orders in memory, persist it
            if 'panel_orders' in self.settings:
                all_settings['panel_orders'] = self.settings.get('panel_orders', {})

            # Persist ToDos
            try:
                all_settings['todos'] = getattr(self, 'todos', { 'tasks': [], 'bugs': [], 'completed': [] })
                all_settings['todo_show_on_launch'] = bool(self.todo_show_on_launch.get()) if hasattr(self, 'todo_show_on_launch') else False
            except Exception:
                pass

            with open(self.settings_file, 'w') as f:
                json.dump(all_settings, f, indent=2)

            log_message("SETTINGS: Settings saved successfully.")
            messagebox.showinfo("Settings Saved", "Settings have been saved successfully!")
            self.settings = all_settings
        except Exception as e:
            log_message(f"SETTINGS ERROR: Failed to save settings: {e}")
            messagebox.showerror("Save Error", f"Failed to save settings: {e}")

    # --- ToDo List: Handlers ---
    def refresh_todo_view(self):
        """Refresh main todo tree view from file-based storage."""
        # Clear tree
        for item in self.todo_tree.get_children():
            self.todo_tree.delete(item)

        # Roots
        tasks_root = self.todo_tree.insert('', 'end', text='🗒 Tasks', open=True)
        bugs_root = self.todo_tree.insert('', 'end', text='🐞 Bugs', open=True)
        work_root = self.todo_tree.insert('', 'end', text='📋 Work-Orders', open=True)
        notes_root = self.todo_tree.insert('', 'end', text='📝 Notes', open=True)
        completed_root = self.todo_tree.insert('', 'end', text='✅ Completed', open=True)

        # Priority tag styles
        try:
            self.todo_tree.tag_configure('prio_high', foreground='#ff5555')
            self.todo_tree.tag_configure('prio_med', foreground='#ff9900')
            self.todo_tree.tag_configure('prio_low', foreground='#ffd700')
            self.todo_tree.tag_configure('completed', foreground='#33cc33', font=('Arial', 9, 'italic'))
        except Exception:
            pass

        # Helper to sort by priority
        def _prio_key(item):
            p = (item or {}).get('priority', 'low').lower()
            return {'high': 0, 'medium': 1, 'low': 2}.get(p, 2)

        # Load from files and populate
        tcount = bcount = wcount = ncount = 0
        ph = pm = pl = 0

        # Tasks
        try:
            task_files = list_todo_files('tasks')
            tasks_data = [read_todo_file(f) for f in task_files]
            for todo in sorted(tasks_data, key=_prio_key):
                text = todo.get('title', '').strip() or 'Untitled Task'
                pr = (todo.get('priority', 'low') or 'low').lower()
                tag = ('prio_high',) if pr == 'high' else (('prio_med',) if pr == 'medium' else ('prio_low',))
                self.todo_tree.insert(tasks_root, 'end', iid=f'tasks:{todo["filename"]}', text=text, values=('☐',), tags=tag)
                tcount += 1
                if pr == 'high':
                    ph += 1
                elif pr == 'medium':
                    pm += 1
                else:
                    pl += 1
        except Exception as e:
            log_message(f"SETTINGS: Error loading tasks: {e}")

        # Bugs
        try:
            bug_files = list_todo_files('bugs')
            bugs_data = [read_todo_file(f) for f in bug_files]
            for todo in sorted(bugs_data, key=_prio_key):
                text = todo.get('title', '').strip() or 'Untitled Bug'
                pr = (todo.get('priority', 'low') or 'low').lower()
                tag = ('prio_high',) if pr == 'high' else (('prio_med',) if pr == 'medium' else ('prio_low',))
                self.todo_tree.insert(bugs_root, 'end', iid=f'bugs:{todo["filename"]}', text=text, values=('☐',), tags=tag)
                bcount += 1
                if pr == 'high':
                    ph += 1
                elif pr == 'medium':
                    pm += 1
                else:
                    pl += 1
        except Exception as e:
            log_message(f"SETTINGS: Error loading bugs: {e}")

        # Work Orders
        try:
            work_files = list_todo_files('work_orders')
            work_data = [read_todo_file(f) for f in work_files]
            for todo in sorted(work_data, key=_prio_key):
                text = todo.get('title', '').strip() or 'Untitled Work-Order'
                pr = (todo.get('priority', 'low') or 'low').lower()
                tag = ('prio_high',) if pr == 'high' else (('prio_med',) if pr == 'medium' else ('prio_low',))
                self.todo_tree.insert(work_root, 'end', iid=f'work_orders:{todo["filename"]}', text=text, values=('☐',), tags=tag)
                wcount += 1
                if pr == 'high':
                    ph += 1
                elif pr == 'medium':
                    pm += 1
                else:
                    pl += 1
        except Exception as e:
            log_message(f"SETTINGS: Error loading work orders: {e}")

        # Notes
        try:
            note_files = list_todo_files('notes')
            notes_data = [read_todo_file(f) for f in note_files]
            for todo in sorted(notes_data, key=_prio_key):
                text = todo.get('title', '').strip() or 'Untitled Note'
                pr = (todo.get('priority', 'low') or 'low').lower()
                tag = ('prio_high',) if pr == 'high' else (('prio_med',) if pr == 'medium' else ('prio_low',))
                self.todo_tree.insert(notes_root, 'end', iid=f'notes:{todo["filename"]}', text=text, values=('☐',), tags=tag)
                ncount += 1
                if pr == 'high':
                    ph += 1
                elif pr == 'medium':
                    pm += 1
                else:
                    pl += 1
        except Exception as e:
            log_message(f"SETTINGS: Error loading notes: {e}")

        # Completed
        ccount = 0
        try:
            completed_files = list_todo_files('completed')
            completed_data = [read_todo_file(f) for f in completed_files]
            for todo in completed_data:
                text = todo.get('title', '').strip() or 'Untitled Item'
                self.todo_tree.insert(completed_root, 'end', iid=f'completed:{todo["filename"]}', text=text, values=('☑',), tags=('completed',))
                ccount += 1
        except Exception as e:
            log_message(f"SETTINGS: Error loading completed: {e}")

        # Update header counts with priority totals (two-line layout)
        self.todo_counts_var.set(f"Tasks: {tcount} | Bugs: {bcount} | Work-Orders: {wcount} | Notes: {ncount} | Completed: {ccount}")
        self.todo_priority_var.set(f"Priority: High {ph} | Medium {pm} | Low {pl}")
        # Update buttons state
        self._apply_todo_button_states()

    def _on_todo_click(self, event):
        """Handle click on todo item - file-based storage doesn't use 'done' checkboxes."""
        # With file-based storage, items are either active or completed (in different folders)
        # No need for inline checkbox toggling
        pass

    def _get_selected_todo(self):
        """Get selected todo from tree - returns (category, filename)."""
        sel = self.todo_tree.selection()
        if not sel:
            return None
        item = sel[0]
        if ':' not in item:
            return None
        category, filename = item.split(':', 1)
        return category, filename

    def _is_todo_actionable(self, action):
        """Check if action is valid for selected todo."""
        sel = self._get_selected_todo()
        if not sel:
            return False
        category, filename = sel
        if action == 'mark':
            return category in ('tasks', 'bugs', 'work_orders', 'notes')
        if action == 'edit':
            return category in ('tasks', 'bugs', 'work_orders', 'notes')
        if action == 'delete':
            return category in ('tasks', 'bugs', 'work_orders', 'notes', 'completed')
        return True

    def _apply_todo_button_states(self):
        # Enable/disable buttons based on selection
        for action, btn in (
            ('mark', self.todo_btn_mark),
            ('edit', self.todo_btn_edit),
            ('delete', self.todo_btn_delete),
        ):
            actionable = self._is_todo_actionable(action)
            try:
                btn.state(['!disabled'] if actionable else ['disabled'])
            except Exception:
                pass

    def _on_todo_selection_changed(self, event=None):
        self._apply_todo_button_states()
        # Also refresh hover style immediately
        self._update_todo_button_hover_style()

    def _wire_todo_button_hover(self):
        # Bind hover events
        for action, btn in (
            ('mark', self.todo_btn_mark),
            ('edit', self.todo_btn_edit),
            ('delete', self.todo_btn_delete),
        ):
            btn.bind('<Enter>', lambda e, a=action: self._on_todo_btn_enter(a))
            btn.bind('<Leave>', lambda e, a=action: self._on_todo_btn_leave(a))

    def _on_todo_btn_enter(self, action):
        actionable = self._is_todo_actionable(action)
        btn = {
            'mark': self.todo_btn_mark,
            'edit': self.todo_btn_edit,
            'delete': self.todo_btn_delete,
        }.get(action)
        if not btn:
            return
        try:
            btn.configure(style='Action.TButton' if actionable else 'Select.TButton')
        except Exception:
            pass

    def _on_todo_btn_leave(self, action):
        # Revert to selection-based style
        self._update_todo_button_hover_style()

    def _update_todo_button_hover_style(self):
        for action, btn in (
            ('mark', self.todo_btn_mark),
            ('edit', self.todo_btn_edit),
            ('delete', self.todo_btn_delete),
        ):
            actionable = self._is_todo_actionable(action)
            try:
                btn.configure(style='Action.TButton' if actionable else 'Select.TButton')
            except Exception:
                pass

    def _on_todo_show_on_launch_changed(self):
        # Persist immediately
        try:
            self.save_settings_to_file()
        except Exception:
            pass

    # Optional popup on launch
    def show_todo_popup(self, project_name: str = None, prefer_project: bool = False):
        """Show main todo popup.

        If project_name is provided and prefer_project is True, open the Project ToDo view instead.
        """
        # Redirect to project view if requested
        try:
            ctx_project = project_name or getattr(self, 'current_project_context', None)
            if prefer_project and ctx_project:
                return self.show_project_todo_popup(ctx_project)
        except Exception:
            pass
        top = tk.Toplevel(self.root)
        top.title("ToDo List")
        try:
            geom = (self.settings or {}).get('todo_geometry_main')
            if isinstance(geom, str) and 'x' in geom:
                top.geometry(geom)
            else:
                top.geometry('820x560')
        except Exception:
            top.geometry('820x560')
        try:
            top.transient(self.root)
            top.lift()
            top.attributes('-topmost', True)
            # Drop always-on-top shortly after so normal stacking resumes
            self.root.after(500, lambda: top.attributes('-topmost', False))
            top.focus_force()
        except Exception:
            pass
        # Track active state so other tabs can show an indicator
        try:
            self.todo_popup_active = True
            def _on_close():
                # Persist window geometry silently
                try:
                    w = max(400, int(top.winfo_width()))
                    h = max(300, int(top.winfo_height()))
                    self.settings['todo_geometry_main'] = f"{w}x{h}"
                    # Merge minimal write
                    all_settings = {}
                    if self.settings_file.exists():
                        try:
                            with open(self.settings_file, 'r') as f:
                                all_settings = json.load(f)
                        except Exception:
                            all_settings = {}
                    all_settings['todo_geometry_main'] = self.settings['todo_geometry_main']
                    with open(self.settings_file, 'w') as f:
                        json.dump(all_settings, f, indent=2)
                except Exception:
                    pass
                try:
                    self.todo_popup_active = False
                except Exception:
                    pass
                try:
                    top.destroy()
                except Exception:
                    pass
            top.protocol('WM_DELETE_WINDOW', _on_close)
            top.bind('<Destroy>', lambda e: setattr(self, 'todo_popup_active', False))
        except Exception:
            pass
        frame = ttk.Frame(top)
        frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        frame.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=0)
        frame.rowconfigure(2, weight=1)

        # Toggle header: allow switching to Project list when context is provided
        def _open_project_from_main():
            try:
                top.destroy()
            except Exception:
                pass
            try:
                ctx = project_name or getattr(self, 'current_project_context', None)
                if ctx:
                    self.show_project_todo_popup(ctx)
            except Exception:
                pass

        log_message("TODO POPUP: Building header toggle row (Main)...")
        toggle = ttk.Frame(frame)
        toggle.grid(row=0, column=0, columnspan=2, sticky=tk.EW)
        try:
            for c in range(3):
                toggle.columnconfigure(c, weight=1)
            plan_btn = ttk.Button(toggle, text='＋ Plan', style='Action.TButton', command=lambda: self._open_plan_template_dialog(None))
            plan_btn.grid(row=0, column=0, sticky=tk.W, padx=(0,8))
            main_btn = ttk.Button(toggle, text='Main ToDo List', style='Action.TButton')
            main_btn.grid(row=0, column=1, sticky=tk.EW, padx=(0,4))
            ctx = project_name or getattr(self, 'current_project_context', None)
            if ctx:
                try:
                    get_project_todos_dir(ctx)
                except Exception:
                    pass
                proj_btn = ttk.Button(toggle, text='Project ToDo List', style='Select.TButton', command=_open_project_from_main)
                proj_btn.grid(row=0, column=2, sticky=tk.EW, padx=(4,0))
        except Exception as e:
            log_message(f"TODO POPUP: Header build error (Main): {e}")

        # Top right header buttons
        def open_system_trash():
            try:
                import platform, subprocess, os, shutil
                system = platform.system()
                if system == 'Linux':
                    if shutil.which('gio'):
                        subprocess.Popen(['gio', 'open', 'trash:///'])
                    elif shutil.which('xdg-open'):
                        subprocess.Popen(['xdg-open', os.path.expanduser('~/.local/share/Trash/files')])
                elif system == 'Darwin':
                    subprocess.Popen(['open', os.path.expanduser('~/.Trash')])
                elif system == 'Windows':
                    subprocess.Popen(['explorer', 'shell:RecycleBinFolder'])
            except Exception:
                pass

        try:
            trash_btn = ttk.Button(frame, text='🗑', width=3, command=open_system_trash)
            trash_btn.grid(row=0, column=1, sticky=tk.NE, padx=(6,0))
        except Exception:
            pass

        # Plan context (used to auto-link new todos to a selected plan)
        plan_context = {'name': None}

        # Two-line header for better fit
        try:
            ttk.Label(frame, textvariable=self.todo_counts_var, font=("Arial", 11, "bold"), style='CategoryPanel.TLabel', anchor='center').grid(row=1, column=0, sticky=tk.EW)
            ttk.Label(frame, textvariable=self.todo_priority_var, font=("Arial", 10), style='CategoryPanel.TLabel', anchor='center').grid(row=2, column=0, sticky=tk.EW, pady=(0,6))
        except Exception as e:
            log_message(f"TODO POPUP: Counts row error (Main): {e}")

        # Folder button to open todos directory in file manager
        def open_todos_folder():
            """Open the todos directory in system file manager."""
            try:
                import subprocess
                import platform

                todos_path = str(TODOS_DIR)
                log_message(f"SETTINGS: Opening todos folder: {todos_path}")

                system = platform.system()
                if system == 'Linux':
                    subprocess.Popen(['xdg-open', todos_path])
                elif system == 'Darwin':  # macOS
                    subprocess.Popen(['open', todos_path])
                elif system == 'Windows':
                    subprocess.Popen(['explorer', todos_path])
                else:
                    messagebox.showinfo("Unsupported OS", f"Please manually navigate to:\n{todos_path}", parent=top)
            except Exception as e:
                log_message(f"SETTINGS: Error opening todos folder: {e}")
                messagebox.showerror("Error", f"Failed to open folder:\n{e}\n\nPath: {TODOS_DIR}", parent=top)

        try:
            folder_btn = ttk.Button(frame, text="📁", command=open_todos_folder, width=3)
            folder_btn.grid(row=1, column=1, rowspan=2, sticky=tk.NE, padx=(6,0))
        except Exception as e:
            log_message(f"TODO POPUP: Folder button error (Main): {e}")
        # Tree
        log_message("TODO POPUP: Building body (tree) (Main)...")
        try:
            sub = ttk.Frame(frame)
            sub.grid(row=3, column=0, columnspan=2, sticky=tk.NSEW)
            sub.columnconfigure(0, weight=1)
            sub.rowconfigure(0, weight=1)
            scr = ttk.Scrollbar(sub, orient=tk.VERTICAL)
            scr.pack(side=tk.RIGHT, fill=tk.Y)
            pop_tree = ttk.Treeview(sub, columns=("done",), show='tree headings')
            pop_tree.heading('#0', text='Item')
            pop_tree.heading('done', text='Done')
            pop_tree.column('done', width=60, anchor=tk.CENTER, stretch=False)
            pop_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            pop_tree.configure(yscrollcommand=scr.set)
            scr.config(command=pop_tree.yview)
        except Exception as e:
            log_message(f"TODO POPUP: Tree build error (Main): {e}")
            # Fallback minimal tree
            try:
                ttk.Label(frame, text='[Tree build failed]', style='CategoryPanel.TLabel').grid(row=3, column=0, sticky=tk.W)
            except Exception:
                pass

        # Tag colors for priorities/completed in popup
        try:
            pop_tree.tag_configure('prio_high', foreground='#ff5555')
            pop_tree.tag_configure('prio_med', foreground='#ff9900')
            pop_tree.tag_configure('prio_low', foreground='#ffd700')
            pop_tree.tag_configure('completed', foreground='#33cc33', font=('Arial', 9, 'italic'))
        except Exception:
            pass

        # Details editor inside popup
        log_message("TODO POPUP: Building body (details) (Main)...")
        try:
            details = ttk.Frame(frame)
            details.grid(row=4, column=0, columnspan=2, sticky=tk.NSEW)
            frame.rowconfigure(3, weight=1)
            frame.rowconfigure(4, weight=1)
            details.columnconfigure(1, weight=1)
        except Exception as e:
            log_message(f"TODO POPUP: Details frame error (Main): {e}")
        ttk.Label(details, text='Priority', style='CategoryPanel.TLabel').grid(row=0, column=0, sticky=tk.W)
        pr_var = tk.StringVar(value='low')
        pr_btns = ttk.Frame(details)
        pr_btns.grid(row=0, column=1, sticky=tk.W, pady=(0,6))
        ttk.Radiobutton(pr_btns, text='High', value='high', variable=pr_var).pack(side=tk.LEFT, padx=2)
        ttk.Radiobutton(pr_btns, text='Medium', value='medium', variable=pr_var).pack(side=tk.LEFT, padx=2)
        ttk.Radiobutton(pr_btns, text='Low', value='low', variable=pr_var).pack(side=tk.LEFT, padx=2)
        ttk.Label(details, text='Title', style='CategoryPanel.TLabel').grid(row=1, column=0, sticky=tk.W)
        title_var = tk.StringVar(value='')
        title_entry = ttk.Entry(details, textvariable=title_var)
        title_entry.grid(row=1, column=1, sticky=tk.EW, pady=(0,6))
        ttk.Label(details, text='Details', style='CategoryPanel.TLabel').grid(row=2, column=0, sticky=tk.W)
        details_txt = scrolledtext.ScrolledText(details, height=8, wrap=tk.WORD, font=('Arial', 9), bg='#1e1e1e', fg='#dcdcdc')
        details_txt.grid(row=2, column=1, sticky=tk.NSEW)
        details.rowconfigure(2, weight=1)

        # Show helpful instructions on popup open
        try:
            details_txt.insert(tk.END, "📝 Quick Start:\n\n")
            details_txt.insert(tk.END, "1. To CREATE: Fill in Title & Details, set Priority, click 'Create Todo', then select category\n\n")
            details_txt.insert(tk.END, "2. To EDIT: Select an item from the list above, modify fields, click 'Save'\n\n")
            details_txt.insert(tk.END, "3. To VIEW: Click any item in the tree to view/edit its details here\n\n")
            details_txt.insert(tk.END, "Select an item above to get started!")
            log_message("SETTINGS: Quick Start instructions added to details pane")
        except Exception as e:
            log_message(f"SETTINGS: Error adding Quick Start instructions: {e}")

        # Populate from file-based storage
        def refresh_pop():
            log_message("SETTINGS: refresh_pop() START")
            try:
                for i in pop_tree.get_children():
                    pop_tree.delete(i)
                log_message("SETTINGS: Tree cleared successfully")
            except Exception as e:
                log_message(f"SETTINGS: Error clearing popup tree: {e}")
                return
            try:
                troot = pop_tree.insert('', 'end', text='🗒 Tasks', open=True)
                broot = pop_tree.insert('', 'end', text='🐞 Bugs', open=True)
                wroot = pop_tree.insert('', 'end', text='📋 Work-Orders', open=True)
                nroot = pop_tree.insert('', 'end', text='📝 Notes', open=True)
                croot = pop_tree.insert('', 'end', text='✅ Completed', open=True)
                log_message("SETTINGS: Tree roots created successfully")
            except Exception as e:
                log_message(f"SETTINGS: Error creating popup tree roots: {e}")
                return

            def _prio_key(todo_dict):
                p = (todo_dict or {}).get('priority','low').lower()
                return {'high':0, 'medium':1, 'low':2}.get(p, 2)

            # Load from files instead of JSON
            try:
                task_files = list_todo_files('tasks')
                log_message(f"SETTINGS: Found {len(task_files)} task files")
                tasks_data = [read_todo_file(f) for f in task_files]
                for todo in sorted(tasks_data, key=_prio_key):
                    pr = (todo.get('priority','low') or 'low').lower()
                    tag = ('prio_high',) if pr=='high' else (('prio_med',) if pr=='medium' else ('prio_low',))
                    # Use filename as stable iid
                    pop_tree.insert(troot, 'end', iid=f'tasks:{todo["filename"]}', text=todo.get('title',''), values=('☐',), tags=tag)
                log_message(f"SETTINGS: Populated {len(tasks_data)} tasks")
            except Exception as e:
                log_message(f"SETTINGS: Error populating tasks in popup: {e}")

            try:
                bug_files = list_todo_files('bugs')
                bugs_data = [read_todo_file(f) for f in bug_files]
                for todo in sorted(bugs_data, key=_prio_key):
                    pr = (todo.get('priority','low') or 'low').lower()
                    tag = ('prio_high',) if pr=='high' else (('prio_med',) if pr=='medium' else ('prio_low',))
                    pop_tree.insert(broot, 'end', iid=f'bugs:{todo["filename"]}', text=todo.get('title',''), values=('☐',), tags=tag)
            except Exception as e:
                log_message(f"SETTINGS: Error populating bugs in popup: {e}")

            try:
                wo_files = list_todo_files('work_orders')
                wo_data = [read_todo_file(f) for f in wo_files]
                for todo in sorted(wo_data, key=_prio_key):
                    pr = (todo.get('priority','low') or 'low').lower()
                    tag = ('prio_high',) if pr=='high' else (('prio_med',) if pr=='medium' else ('prio_low',))
                    pop_tree.insert(wroot, 'end', iid=f'work_orders:{todo["filename"]}', text=todo.get('title',''), values=('☐',), tags=tag)
            except Exception as e:
                log_message(f"SETTINGS: Error populating work-orders in popup: {e}")

            try:
                notes_files = list_todo_files('notes')
                notes_data = [read_todo_file(f) for f in notes_files]
                for todo in sorted(notes_data, key=_prio_key):
                    pr = (todo.get('priority','low') or 'low').lower()
                    tag = ('prio_high',) if pr=='high' else (('prio_med',) if pr=='medium' else ('prio_low',))
                    pop_tree.insert(nroot, 'end', iid=f'notes:{todo["filename"]}', text=todo.get('title',''), values=('☐',), tags=tag)
            except Exception as e:
                log_message(f"SETTINGS: Error populating notes in popup: {e}")

            try:
                completed_files = list_todo_files('completed')
                completed_data = [read_todo_file(f) for f in completed_files]
                for todo in completed_data:
                    pop_tree.insert(croot, 'end', iid=f'completed:{todo["filename"]}', text=todo.get('title',''), values=('☑',), tags=('completed',))
            except Exception as e:
                log_message(f"SETTINGS: Error populating completed in popup: {e}")

            # Plans and Tests (optional roots)
            try:
                plans_root = pop_tree.insert('', 'end', text='📐 Plans', open=True)
                plan_files = list_todo_files('plans')
                plans_data = [read_todo_file(f) for f in plan_files]
                for todo in plans_data:
                    pop_tree.insert(plans_root, 'end', iid=f'plans:{todo["filename"]}', text=todo.get('title',''), values=('☐',))
            except Exception as e:
                log_message(f"SETTINGS: Error populating plans in popup: {e}")
            try:
                tests_root = pop_tree.insert('', 'end', text='🧪 Tests', open=True)
                test_files = list_todo_files('tests')
                tests_data = [read_todo_file(f) for f in test_files]
                for todo in tests_data:
                    pop_tree.insert(tests_root, 'end', iid=f'tests:{todo["filename"]}', text=todo.get('title',''), values=('☐',))
            except Exception as e:
                log_message(f"SETTINGS: Error populating tests in popup: {e}")

        # Populate tree first, then bind events
        try:
            refresh_pop()
        except Exception as e:
            log_message(f"TODO POPUP: Initial populate error (Main): {e}")
        # Auto-refresh while popup is open to pick up external changes/restores
        last_sig = {'v': 0}
        def _tick_refresh():
            try:
                import os
                sig = 0
                base = get_project_todos_dir(project_name)
                for cat in ('tasks','bugs','work_orders','notes','completed'):
                    d = base / cat
                    if d.exists():
                        sig ^= int(d.stat().st_mtime)
                if sig != last_sig['v']:
                    last_sig['v'] = sig
                    refresh_pop()
            except Exception:
                pass
            try:
                if top.winfo_exists():
                    self.root.after(2000, _tick_refresh)
            except Exception:
                pass
        try:
            self.root.after(2000, _tick_refresh)
        except Exception:
            pass
        # Auto-refresh while popup is open to pick up external changes/restores
        last_sig = {'v': 0}
        def _tick_refresh():
            try:
                import os, time
                sig = 0
                for cat in ('tasks','bugs','work_orders','notes','completed'):
                    d = TODOS_DIR / cat
                    if d.exists():
                        sig ^= int(d.stat().st_mtime)
                if sig != last_sig['v']:
                    last_sig['v'] = sig
                    refresh_pop()
            except Exception:
                pass
            try:
                if top.winfo_exists():
                    self.root.after(2000, _tick_refresh)
            except Exception:
                pass
        try:
            self.root.after(2000, _tick_refresh)
        except Exception:
            pass

        # Action buttons use existing handlers but with selected item from popup
        try:
            btns = ttk.Frame(frame)
            btns.grid(row=5, column=0, columnspan=2, sticky=tk.EW, pady=(6,0))
        except Exception as e:
            log_message(f"TODO POPUP: Buttons row error (Main): {e}")
        for i in range(5):
            btns.columnconfigure(i, weight=1)

        def get_sel_from_pop():
            """Returns (category, filename) from selected tree item."""
            sel = pop_tree.selection()
            if not sel:
                return None
            item = sel[0]
            if ':' not in item:
                return None
            category, filename = item.split(':', 1)
            return category, filename

        def populate_details_from_sel():
            """Load todo file and populate detail fields."""
            log_message("SETTINGS: populate_details_from_sel() called")
            sel = get_sel_from_pop()

            # If nothing selected, don't clear the Quick Start instructions
            if not sel:
                log_message("SETTINGS: No selection, keeping Quick Start instructions")
                return

            # Reset fields when we have a selection
            try:
                pr_var.set('low')
                title_var.set('')
                details_txt.delete('1.0', tk.END)
                log_message(f"SETTINGS: Fields cleared for selection: {sel}")
            except Exception:
                pass
            category, filename = sel

            # Don't populate details for completed items (read-only)
            if category == 'completed':
                try:
                    title_var.set('[Completed - Read Only]')
                    details_txt.insert(tk.END, 'Completed items are read-only. Delete to remove or recreate as new todo.')
                except Exception:
                    pass
                return

            # Load from file
            try:
                from pathlib import Path
                todo_dir = TODOS_DIR / category
                filepath = todo_dir / filename
                if not filepath.exists():
                    return

                todo_data = read_todo_file(filepath)
                pr_var.set(todo_data.get('priority', 'low'))
                title_var.set(todo_data.get('title', ''))
                details_txt.insert(tk.END, todo_data.get('details', ''))
            except Exception as e:
                log_message(f"SETTINGS: Error loading todo file: {e}")
                pass

        try:
            pop_tree.bind('<<TreeviewSelect>>', lambda e: populate_details_from_sel())
        except Exception:
            pass
        # Populate details for initial selection if any
        try:
            populate_details_from_sel()
        except Exception:
            pass

        def create_cb():
            """Open a full create dialog to enter category, title, priority, and details."""
            dlg = tk.Toplevel(top)
            dlg.title('Create ToDo')
            dlg.geometry('640x420')
            try:
                dlg.transient(top); dlg.grab_set()
            except Exception:
                pass
            frm = ttk.Frame(dlg, padding=10)
            frm.pack(fill=tk.BOTH, expand=True)
            # Category
            ttk.Label(frm, text='Category', style='CategoryPanel.TLabel').grid(row=0, column=0, sticky=tk.W)
            cat_var = tk.StringVar(value='tasks')
            cats = [('Tasks','tasks'),('Bugs','bugs'),('Work-Orders','work_orders'),('Notes','notes')]
            cat_row = ttk.Frame(frm); cat_row.grid(row=0, column=1, sticky=tk.W)
            for label, val in cats:
                ttk.Radiobutton(cat_row, text=label, value=val, variable=cat_var).pack(side=tk.LEFT, padx=4)
            # Priority
            ttk.Label(frm, text='Priority', style='CategoryPanel.TLabel').grid(row=1, column=0, sticky=tk.W)
            pr_local = tk.StringVar(value='low')
            pr_row = ttk.Frame(frm); pr_row.grid(row=1, column=1, sticky=tk.W)
            ttk.Radiobutton(pr_row, text='High', value='high', variable=pr_local).pack(side=tk.LEFT, padx=4)
            ttk.Radiobutton(pr_row, text='Medium', value='medium', variable=pr_local).pack(side=tk.LEFT, padx=4)
            ttk.Radiobutton(pr_row, text='Low', value='low', variable=pr_local).pack(side=tk.LEFT, padx=4)
            # Title
            ttk.Label(frm, text='Title', style='CategoryPanel.TLabel').grid(row=2, column=0, sticky=tk.W)
            tvar = tk.StringVar()
            ttk.Entry(frm, textvariable=tvar).grid(row=2, column=1, sticky=tk.EW)
            # Details
            ttk.Label(frm, text='Details', style='CategoryPanel.TLabel').grid(row=3, column=0, sticky=tk.NW)
            txt = scrolledtext.ScrolledText(frm, height=10, wrap=tk.WORD, font=('Arial', 9), bg='#1e1e1e', fg='#dcdcdc')
            txt.grid(row=3, column=1, sticky=tk.NSEW)
            frm.columnconfigure(1, weight=1)
            frm.rowconfigure(3, weight=1)
            # Buttons
            def do_create():
                try:
                    title_text = (tvar.get() or '').strip()
                    if not title_text:
                        messagebox.showwarning('Missing Title', 'Please enter a title.', parent=dlg); return
                    plan_name = plan_context.get('name') if isinstance(plan_context, dict) else None
                    # Auto-label in title if linked to a plan
                    if plan_name and not title_text.lower().startswith(f"plan:{plan_name.lower()}"):
                        title_text = f"Plan:{plan_name} | {title_text}"
                    created = create_todo_file(cat_var.get(), title_text, pr_local.get(), txt.get('1.0', tk.END).strip(), plan=plan_name)
                    self.refresh_todo_view(); refresh_pop()
                    try:
                        import subprocess, platform
                        system = platform.system(); path = str(created)
                        if system == 'Linux': subprocess.Popen(['xdg-open', path])
                        elif system == 'Darwin': subprocess.Popen(['open', path])
                        elif system == 'Windows': subprocess.Popen(['explorer', path])
                    except Exception: pass
                    dlg.destroy()
                except Exception as e:
                    log_message(f'SETTINGS: Error creating todo (dialog): {e}')
                    messagebox.showerror('Error', f'Failed to create todo: {e}', parent=dlg)
            btns2 = ttk.Frame(frm); btns2.grid(row=4, column=1, sticky=tk.E)
            ttk.Button(btns2, text='Create', style='Action.TButton', command=do_create).pack(side=tk.LEFT, padx=4)
            ttk.Button(btns2, text='Cancel', style='Select.TButton', command=dlg.destroy).pack(side=tk.LEFT, padx=4)

        def mark_cb():
            """Move todo file to completed directory."""
            sel = get_sel_from_pop()
            if not sel:
                messagebox.showinfo("No Selection", "Please select a todo to mark complete.", parent=top)
                return
            category, filename = sel
            if category not in ('tasks', 'bugs', 'work_orders', 'notes', 'tests'):
                messagebox.showinfo("Invalid Selection", "Select a task, bug, work-order, or note to mark complete.", parent=top)
                return
            if not messagebox.askyesno("Mark Complete", "Mark this todo as complete?", parent=top):
                return
            try:
                # Move file to completed directory
                from pathlib import Path
                todo_dir = TODOS_DIR / category
                filepath = todo_dir / filename
                if filepath.exists():
                    move_todo_to_completed(filepath)

                self.refresh_todo_view()
                refresh_pop()
                # Clear details after marking complete
                try:
                    pr_var.set('low')
                    title_var.set('')
                    details_txt.delete('1.0', tk.END)
                except Exception:
                    pass
            except Exception as e:
                log_message(f"SETTINGS: Error in mark_cb: {e}")
                messagebox.showerror("Error", f"Failed to mark complete: {e}", parent=top)

        def edit_cb():
            """Open selected todo file in system editor."""
            sel = get_sel_from_pop()
            if not sel:
                messagebox.showinfo("No Selection", "Please select a todo to edit.", parent=top)
                return
            category, filename = sel
            if category not in ('tasks', 'bugs', 'work_orders', 'notes', 'completed'):
                messagebox.showinfo("Invalid Selection", "Select a valid todo to open.", parent=top)
                return
            try:
                from pathlib import Path
                todo_dir = TODOS_DIR / category
                filepath = todo_dir / filename
                if not filepath.exists():
                    messagebox.showerror("Error", "Todo file not found.", parent=top)
                    return
                import subprocess, platform
                system = platform.system()
                path = str(filepath)
                if system == 'Linux': subprocess.Popen(['xdg-open', path])
                elif system == 'Darwin': subprocess.Popen(['open', path])
                elif system == 'Windows': subprocess.Popen(['explorer', path])
            except Exception as e:
                log_message(f"SETTINGS: Error opening todo externally: {e}")
                messagebox.showerror("Error", f"Failed to open: {e}", parent=top)

        def _send_to_trash(path_str: str) -> bool:
            try:
                # Prefer send2trash if available
                try:
                    from send2trash import send2trash
                    send2trash(path_str)
                    return True
                except Exception:
                    pass
                import platform, subprocess, os, shutil
                system = platform.system()
                if system == 'Linux' and shutil.which('gio'):
                    subprocess.check_call(['gio', 'trash', path_str])
                    return True
                # Fallback: move to local app trash
                tdir = DATA_DIR / '.trash'
                tdir.mkdir(parents=True, exist_ok=True)
                import shutil as _sh
                _sh.move(path_str, tdir / Path(path_str).name)
                return True
            except Exception:
                return False

        def delete_cb():
            """Move todo file to system trash (recoverable)."""
            sel = get_sel_from_pop()
            if not sel:
                messagebox.showinfo("No Selection", "Please select a todo to delete.", parent=top)
                return
            category, filename = sel
            # Allow deleting from all categories including completed
            if category not in ('tasks', 'bugs', 'work_orders', 'notes', 'completed', 'plans', 'tests'):
                messagebox.showinfo("Invalid Selection", "Select an item to delete.", parent=top)
                return
            if not messagebox.askyesno("Confirm Delete", "Delete selected todo?", parent=top):
                return
            try:
                from pathlib import Path
                todo_dir = TODOS_DIR / category
                filepath = todo_dir / filename
                if filepath.exists():
                    _send_to_trash(str(filepath))

                self.refresh_todo_view()
                refresh_pop()
                # Clear details after delete
                try:
                    pr_var.set('low')
                    title_var.set('')
                    details_txt.delete('1.0', tk.END)
                except Exception:
                    pass
            except Exception as e:
                log_message(f"SETTINGS: Error in delete_cb: {e}")
                messagebox.showerror("Error", f"Failed to delete: {e}", parent=top)

        def save_cb():
            """Update todo file with changes from detail fields."""
            sel = get_sel_from_pop()
            if not sel:
                messagebox.showinfo("No Selection", "Please select a todo to save.", parent=top)
                return
            category, filename = sel
            if category == 'completed':
                messagebox.showinfo("Read Only", "Completed items are read-only. Delete or recreate to change.", parent=top)
                return
            try:
                # Get field values
                new_title = (title_var.get() or '').strip()
                new_priority = pr_var.get()
                new_details = details_txt.get('1.0', tk.END).strip()

                if not new_title:
                    messagebox.showwarning("Missing Title", "Title cannot be empty.", parent=top)
                    return

                # Update file (may rename if title changed)
                from pathlib import Path
                todo_dir = TODOS_DIR / category
                filepath = todo_dir / filename
                if not filepath.exists():
                    messagebox.showerror("Error", "Todo file not found.", parent=top)
                    return

                new_filepath = update_todo_file(filepath, new_title, new_priority, new_details)

                self.refresh_todo_view()
                refresh_pop()

                # Re-select the updated item (may have new filename if title changed)
                try:
                    new_filename = new_filepath.name
                    pop_tree.selection_set(f"{category}:{new_filename}")
                except Exception:
                    pass

                populate_details_from_sel()
            except Exception as e:
                log_message(f"SETTINGS: Error in save_cb: {e}")
                messagebox.showerror("Error", f"Failed to save: {e}", parent=top)

        ttk.Button(btns, text="➕ Create Todo", command=create_cb, style='Action.TButton').grid(row=0, column=0, padx=3, sticky=tk.EW)
        ttk.Button(btns, text="✔ Mark Complete", command=mark_cb, style='Select.TButton').grid(row=0, column=1, padx=3, sticky=tk.EW)
        ttk.Button(btns, text="✏️ Edit (Open)", command=edit_cb, style='Select.TButton').grid(row=0, column=2, padx=3, sticky=tk.EW)
        ttk.Button(btns, text="📄 Open File", command=edit_cb, style='Select.TButton').grid(row=0, column=3, padx=3, sticky=tk.EW)
        ttk.Button(btns, text="🗑 Delete Todo", command=delete_cb, style='Select.TButton').grid(row=0, column=4, padx=3, sticky=tk.EW)
        ttk.Button(btns, text="💾 Save (Title/Priority)", command=save_cb, style='Action.TButton').grid(row=0, column=5, padx=3, sticky=tk.EW)


    def show_project_todo_popup(self, project_name):
        """Show project-specific todo popup - completely separate from main todos."""
        if not project_name:
            messagebox.showerror("No Project", "Please select a project first.")
            return

        # Ensure project todos directory exists
        get_project_todos_dir(project_name)

        top = tk.Toplevel(self.root)
        top.title(f"Project ToDo List - {project_name}")
        try:
            geom = (self.settings or {}).get('todo_geometry_project')
            if isinstance(geom, str) and 'x' in geom:
                top.geometry(geom)
            else:
                top.geometry('820x560')
        except Exception:
            top.geometry('820x560')
        try:
            top.transient(self.root)
            top.lift()
            top.attributes('-topmost', True)
            self.root.after(500, lambda: top.attributes('-topmost', False))
            top.focus_force()
        except Exception:
            pass

        # Track active state
        try:
            def _on_close():
                # Persist project geometry silently
                try:
                    w = max(400, int(top.winfo_width()))
                    h = max(300, int(top.winfo_height()))
                    self.settings['todo_geometry_project'] = f"{w}x{h}"
                    all_settings = {}
                    if self.settings_file.exists():
                        try:
                            with open(self.settings_file, 'r') as f:
                                all_settings = json.load(f)
                        except Exception:
                            all_settings = {}
                    all_settings['todo_geometry_project'] = self.settings['todo_geometry_project']
                    with open(self.settings_file, 'w') as f:
                        json.dump(all_settings, f, indent=2)
                except Exception:
                    pass
                try:
                    top.destroy()
                except Exception:
                    pass
            top.protocol('WM_DELETE_WINDOW', _on_close)
        except Exception:
            pass

        frame = ttk.Frame(top)
        frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        frame.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=0)
        frame.rowconfigure(3, weight=1)

        # Toggle header: Project/Main buttons
        def _open_main_from_project():
            try:
                top.destroy()
            except Exception:
                pass
            try:
                self.show_todo_popup(project_name=project_name, prefer_project=False)
            except Exception:
                pass

        log_message("TODO POPUP: Building header toggle row (Project)...")
        toggle = ttk.Frame(frame)
        toggle.grid(row=0, column=0, columnspan=2, sticky=tk.EW)
        try:
            for c in range(3):
                toggle.columnconfigure(c, weight=1)
            plan_btn = ttk.Button(toggle, text='＋ Plan', style='Action.TButton', command=lambda: self._open_plan_template_dialog(project_name))
            plan_btn.grid(row=0, column=0, sticky=tk.W, padx=(0,8))
            proj_btn = ttk.Button(toggle, text='Project ToDo List', style='Action.TButton')
            proj_btn.grid(row=0, column=1, sticky=tk.EW, padx=(0,4))
            main_btn = ttk.Button(toggle, text='Main ToDo List', style='Select.TButton', command=_open_main_from_project)
            main_btn.grid(row=0, column=2, sticky=tk.EW, padx=(4,0))
        except Exception as e:
            log_message(f"TODO POPUP: Header build error (Project): {e}")

        # Project-specific header variables
        proj_counts_var = tk.StringVar(value="Tasks: 0 | Bugs: 0 | Work-Orders: 0 | Notes: 0 | Completed: 0")
        proj_priority_var = tk.StringVar(value="Priority: High 0 | Medium 0 | Low 0")

        # Two-line header
        ttk.Label(frame, textvariable=proj_counts_var, font=("Arial", 11, "bold"), style='CategoryPanel.TLabel', anchor='center').grid(row=1, column=0, sticky=tk.EW)
        ttk.Label(frame, textvariable=proj_priority_var, font=("Arial", 10), style='CategoryPanel.TLabel', anchor='center').grid(row=2, column=0, sticky=tk.EW, pady=(0,6))

        # Top right: Trash and Folder buttons
        def open_system_trash():
            try:
                import platform, subprocess, os, shutil
                system = platform.system()
                if system == 'Linux':
                    if shutil.which('gio'):
                        subprocess.Popen(['gio', 'open', 'trash:///'])
                    elif shutil.which('xdg-open'):
                        subprocess.Popen(['xdg-open', os.path.expanduser('~/.local/share/Trash/files')])
                elif system == 'Darwin':
                    subprocess.Popen(['open', os.path.expanduser('~/.Trash')])
                elif system == 'Windows':
                    subprocess.Popen(['explorer', 'shell:RecycleBinFolder'])
            except Exception:
                pass

        try:
            trash_btn = ttk.Button(frame, text='🗑', width=3, command=open_system_trash)
            trash_btn.grid(row=0, column=1, sticky=tk.NE, padx=(6,0))
        except Exception:
            pass

        # Folder button - opens project todos folder
        def open_project_todos_folder():
            try:
                import subprocess, platform
                todos_path = str(get_project_todos_dir(project_name))
                log_message(f"SETTINGS: Opening project todos folder: {todos_path}")
                system = platform.system()
                if system == 'Linux':
                    subprocess.Popen(['xdg-open', todos_path])
                elif system == 'Darwin':
                    subprocess.Popen(['open', todos_path])
                elif system == 'Windows':
                    subprocess.Popen(['explorer', todos_path])
                else:
                    messagebox.showinfo("Unsupported OS", f"Please manually navigate to:\n{todos_path}", parent=top)
            except Exception as e:
                log_message(f"SETTINGS: Error opening project todos folder: {e}")
                messagebox.showerror("Error", f"Failed to open folder:\n{e}", parent=top)

        folder_btn = ttk.Button(frame, text="📁", command=open_project_todos_folder, width=3)
        folder_btn.grid(row=1, column=1, rowspan=2, sticky=tk.NE, padx=(6,0))

        # Tree
        log_message("TODO POPUP: Building body (tree) (Project)...")
        try:
            sub = ttk.Frame(frame)
            sub.grid(row=3, column=0, columnspan=2, sticky=tk.NSEW)
            sub.columnconfigure(0, weight=1)
            sub.rowconfigure(0, weight=1)
            scr = ttk.Scrollbar(sub, orient=tk.VERTICAL)
            scr.pack(side=tk.RIGHT, fill=tk.Y)
            pop_tree = ttk.Treeview(sub, columns=("done",), show='tree headings')
            pop_tree.heading('#0', text='Item')
            pop_tree.heading('done', text='Done')
            pop_tree.column('done', width=60, anchor=tk.CENTER, stretch=False)
            pop_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            pop_tree.configure(yscrollcommand=scr.set)
            scr.config(command=pop_tree.yview)
        except Exception as e:
            log_message(f"TODO POPUP: Tree build error (Project): {e}")
            try:
                ttk.Label(frame, text='[Tree build failed]', style='CategoryPanel.TLabel').grid(row=3, column=0, sticky=tk.W)
            except Exception:
                pass

        # Tag colors
        try:
            pop_tree.tag_configure('prio_high', foreground='#ff5555')
            pop_tree.tag_configure('prio_med', foreground='#ff9900')
            pop_tree.tag_configure('prio_low', foreground='#ffd700')
            pop_tree.tag_configure('completed', foreground='#33cc33', font=('Arial', 9, 'italic'))
        except Exception:
            pass

        # Details viewer (read-only)
        log_message("TODO POPUP: Building body (details) (Project)...")
        try:
            details = ttk.Frame(frame)
            details.grid(row=4, column=0, columnspan=2, sticky=tk.NSEW)
            frame.rowconfigure(3, weight=1)
            frame.rowconfigure(4, weight=1)
            details.columnconfigure(1, weight=1)
        except Exception as e:
            log_message(f"TODO POPUP: Details frame error (Project): {e}")
        ttk.Label(details, text='Priority', style='CategoryPanel.TLabel').grid(row=0, column=0, sticky=tk.W)
        pr_var = tk.StringVar(value='low')
        pr_btns = ttk.Frame(details)
        pr_btns.grid(row=0, column=1, sticky=tk.W, pady=(0,6))
        ttk.Radiobutton(pr_btns, text='High', value='high', variable=pr_var).pack(side=tk.LEFT, padx=2)
        ttk.Radiobutton(pr_btns, text='Medium', value='medium', variable=pr_var).pack(side=tk.LEFT, padx=2)
        ttk.Radiobutton(pr_btns, text='Low', value='low', variable=pr_var).pack(side=tk.LEFT, padx=2)
        ttk.Label(details, text='Title', style='CategoryPanel.TLabel').grid(row=1, column=0, sticky=tk.W)
        title_var = tk.StringVar(value='')
        title_entry = ttk.Entry(details, textvariable=title_var)
        title_entry.grid(row=1, column=1, sticky=tk.EW, pady=(0,6))
        ttk.Label(details, text='Details (read-only preview)', style='CategoryPanel.TLabel').grid(row=2, column=0, sticky=tk.W)
        details_txt = scrolledtext.ScrolledText(details, height=8, wrap=tk.WORD, font=('Arial', 9), bg='#1e1e1e', fg='#dcdcdc')
        details_txt.grid(row=2, column=1, sticky=tk.NSEW)
        details.rowconfigure(2, weight=1)
        try:
            details_txt.configure(state='disabled')
        except Exception:
            pass

        # Quick Start instructions
        try:
            details_txt.configure(state='normal')
            details_txt.insert(tk.END, f"📝 Project: {project_name}\n\n")
            details_txt.insert(tk.END, "1. To CREATE: Enter Title and set Priority, click 'Create Todo', then edit the file in your editor (auto-opens).\n\n")
            details_txt.insert(tk.END, "2. To EDIT: Double-click an item or use 'Open File' to edit externally.\n\n")
            details_txt.insert(tk.END, "3. To UPDATE Title/Priority: Change fields above and click 'Save (Title/Priority)'.\n\n")
            details_txt.insert(tk.END, "This panel shows a read-only preview of the selected todo.")
            details_txt.configure(state='disabled')
            log_message(f"SETTINGS: Project todo popup opened for: {project_name}")
        except Exception as e:
            log_message(f"SETTINGS: Error adding Quick Start instructions: {e}")

        # Helper: set details preview safely in read-only widget
        def _set_details_text(text: str):
            try:
                details_txt.configure(state='normal')
                details_txt.delete('1.0', tk.END)
                details_txt.insert(tk.END, text or '')
                details_txt.configure(state='disabled')
            except Exception:
                pass

        # Populate from project-specific files
        def refresh_pop():
            log_message(f"SETTINGS: Refreshing project todos for: {project_name}")
            try:
                for i in pop_tree.get_children():
                    pop_tree.delete(i)
                log_message("SETTINGS: Project tree cleared successfully")
            except Exception as e:
                log_message(f"SETTINGS: Error clearing project popup tree: {e}")
                return
            try:
                troot = pop_tree.insert('', 'end', text='🗒 Tasks', open=True)
                broot = pop_tree.insert('', 'end', text='🐞 Bugs', open=True)
                wroot = pop_tree.insert('', 'end', text='📋 Work-Orders', open=True)
                nroot = pop_tree.insert('', 'end', text='📝 Notes', open=True)
                croot = pop_tree.insert('', 'end', text='✅ Completed', open=True)
                log_message("SETTINGS: Project tree roots created successfully")
            except Exception as e:
                log_message(f"SETTINGS: Error creating project popup tree roots: {e}")
                return

            def _prio_key(todo_dict):
                p = (todo_dict or {}).get('priority','low').lower()
                return {'high':0, 'medium':1, 'low':2}.get(p, 2)

            tcount = bcount = wcount = ncount = ccount = 0
            ph = pm = pl = 0

            # Load project-specific todos
            try:
                task_files = list_project_todo_files(project_name, 'tasks')
                log_message(f"SETTINGS: Found {len(task_files)} project task files")
                tasks_data = [read_todo_file(f) for f in task_files]
                for todo in sorted(tasks_data, key=_prio_key):
                    pr = (todo.get('priority','low') or 'low').lower()
                    tag = ('prio_high',) if pr=='high' else (('prio_med',) if pr=='medium' else ('prio_low',))
                    pop_tree.insert(troot, 'end', iid=f'tasks:{todo["filename"]}', text=todo.get('title',''), values=('☐',), tags=tag)
                    tcount += 1
                    if pr == 'high': ph += 1
                    elif pr == 'medium': pm += 1
                    else: pl += 1
                log_message(f"SETTINGS: Populated {len(tasks_data)} project tasks")
            except Exception as e:
                log_message(f"SETTINGS: Error populating project tasks in popup: {e}")

            try:
                bug_files = list_project_todo_files(project_name, 'bugs')
                bugs_data = [read_todo_file(f) for f in bug_files]
                for todo in sorted(bugs_data, key=_prio_key):
                    pr = (todo.get('priority','low') or 'low').lower()
                    tag = ('prio_high',) if pr=='high' else (('prio_med',) if pr=='medium' else ('prio_low',))
                    pop_tree.insert(broot, 'end', iid=f'bugs:{todo["filename"]}', text=todo.get('title',''), values=('☐',), tags=tag)
                    bcount += 1
                    if pr == 'high': ph += 1
                    elif pr == 'medium': pm += 1
                    else: pl += 1
            except Exception as e:
                log_message(f"SETTINGS: Error populating project bugs in popup: {e}")

            try:
                wo_files = list_project_todo_files(project_name, 'work_orders')
                wo_data = [read_todo_file(f) for f in wo_files]
                for todo in sorted(wo_data, key=_prio_key):
                    pr = (todo.get('priority','low') or 'low').lower()
                    tag = ('prio_high',) if pr=='high' else (('prio_med',) if pr=='medium' else ('prio_low',))
                    pop_tree.insert(wroot, 'end', iid=f'work_orders:{todo["filename"]}', text=todo.get('title',''), values=('☐',), tags=tag)
                    wcount += 1
                    if pr == 'high': ph += 1
                    elif pr == 'medium': pm += 1
                    else: pl += 1
            except Exception as e:
                log_message(f"SETTINGS: Error populating project work-orders in popup: {e}")

            try:
                notes_files = list_project_todo_files(project_name, 'notes')
                notes_data = [read_todo_file(f) for f in notes_files]
                for todo in sorted(notes_data, key=_prio_key):
                    pr = (todo.get('priority','low') or 'low').lower()
                    tag = ('prio_high',) if pr=='high' else (('prio_med',) if pr=='medium' else ('prio_low',))
                    pop_tree.insert(nroot, 'end', iid=f'notes:{todo["filename"]}', text=todo.get('title',''), values=('☐',), tags=tag)
                    ncount += 1
                    if pr == 'high': ph += 1
                    elif pr == 'medium': pm += 1
                    else: pl += 1
            except Exception as e:
                log_message(f"SETTINGS: Error populating project notes in popup: {e}")

            try:
                completed_files = list_project_todo_files(project_name, 'completed')
                completed_data = [read_todo_file(f) for f in completed_files]
                for todo in completed_data:
                    pop_tree.insert(croot, 'end', iid=f'completed:{todo["filename"]}', text=todo.get('title',''), values=('☑',), tags=('completed',))
                    ccount += 1
            except Exception as e:
                log_message(f"SETTINGS: Error populating project completed in popup: {e}")

            # Update counts
            proj_counts_var.set(f"Tasks: {tcount} | Bugs: {bcount} | Work-Orders: {wcount} | Notes: {ncount} | Completed: {ccount}")
            proj_priority_var.set(f"Priority: High {ph} | Medium {pm} | Low {pl}")

        refresh_pop()

        # Buttons and callbacks
        btns = ttk.Frame(frame)
        btns.grid(row=5, column=0, columnspan=2, sticky=tk.EW, pady=(6,0))
        for i in range(5):
            btns.columnconfigure(i, weight=1)

        def get_sel_from_pop():
            sel = pop_tree.selection()
            if not sel:
                return None
            item = sel[0]
            if ':' not in item:
                return None
            category, filename = item.split(':', 1)
            return category, filename

        def populate_details_from_sel():
            log_message("SETTINGS: Project populate_details_from_sel() called")
            sel = get_sel_from_pop()
            if not sel:
                log_message("SETTINGS: No selection, keeping Quick Start instructions")
                return
            try:
                pr_var.set('low')
                title_var.set('')
                _set_details_text('')
                log_message(f"SETTINGS: Fields cleared for selection: {sel}")
            except Exception:
                pass
            category, filename = sel
            if category == 'completed':
                try:
                    title_var.set('[Completed - Read Only]')
                    _set_details_text('Completed items are read-only. Delete to remove or recreate as new todo.')
                except Exception:
                    pass
                return
            try:
                from pathlib import Path
                todos_dir = get_project_todos_dir(project_name)
                todo_dir = todos_dir / category
                filepath = todo_dir / filename
                if not filepath.exists():
                    return
                todo_data = read_todo_file(filepath)
                pr_var.set(todo_data.get('priority', 'low'))
                title_var.set(todo_data.get('title', ''))
                _set_details_text(todo_data.get('details', ''))
            except Exception as e:
                log_message(f"SETTINGS: Error loading project todo file: {e}")

        try:
            pop_tree.bind('<<TreeviewSelect>>', lambda e: populate_details_from_sel())
        except Exception:
            pass
        try:
            populate_details_from_sel()
        except Exception:
            pass

        def create_cb():
            """Open full create dialog for a new project todo."""
            dlg = tk.Toplevel(top)
            dlg.title('Create Project ToDo')
            dlg.geometry('640x420')
            try:
                dlg.transient(top); dlg.grab_set()
            except Exception:
                pass
            frm = ttk.Frame(dlg, padding=10)
            frm.pack(fill=tk.BOTH, expand=True)
            # Category
            ttk.Label(frm, text='Category', style='CategoryPanel.TLabel').grid(row=0, column=0, sticky=tk.W)
            cat_var = tk.StringVar(value='tasks')
            cats = [('Tasks','tasks'),('Bugs','bugs'),('Work-Orders','work_orders'),('Notes','notes')]
            cat_row = ttk.Frame(frm); cat_row.grid(row=0, column=1, sticky=tk.W)
            for label, val in cats:
                ttk.Radiobutton(cat_row, text=label, value=val, variable=cat_var).pack(side=tk.LEFT, padx=4)
            # Priority
            ttk.Label(frm, text='Priority', style='CategoryPanel.TLabel').grid(row=1, column=0, sticky=tk.W)
            pr_local = tk.StringVar(value='low')
            pr_row = ttk.Frame(frm); pr_row.grid(row=1, column=1, sticky=tk.W)
            ttk.Radiobutton(pr_row, text='High', value='high', variable=pr_local).pack(side=tk.LEFT, padx=4)
            ttk.Radiobutton(pr_row, text='Medium', value='medium', variable=pr_local).pack(side=tk.LEFT, padx=4)
            ttk.Radiobutton(pr_row, text='Low', value='low', variable=pr_local).pack(side=tk.LEFT, padx=4)
            # Title
            ttk.Label(frm, text='Title', style='CategoryPanel.TLabel').grid(row=2, column=0, sticky=tk.W)
            tvar = tk.StringVar()
            ttk.Entry(frm, textvariable=tvar).grid(row=2, column=1, sticky=tk.EW)
            # Details
            ttk.Label(frm, text='Details', style='CategoryPanel.TLabel').grid(row=3, column=0, sticky=tk.NW)
            txt = scrolledtext.ScrolledText(frm, height=10, wrap=tk.WORD, font=('Arial', 9), bg='#1e1e1e', fg='#dcdcdc')
            txt.grid(row=3, column=1, sticky=tk.NSEW)
            frm.columnconfigure(1, weight=1)
            frm.rowconfigure(3, weight=1)
            # Buttons
            def do_create():
                try:
                    title_text = (tvar.get() or '').strip()
                    if not title_text:
                        messagebox.showwarning('Missing Title', 'Please enter a title.', parent=dlg); return
                    plan_name = plan_context.get('name') if isinstance(plan_context, dict) else None
                    if plan_name and not title_text.lower().startswith(f"plan:{plan_name.lower()}"):
                        title_text = f"Plan:{plan_name} | {title_text}"
                    created = create_project_todo_file(project_name, cat_var.get(), title_text, pr_local.get(), txt.get('1.0', tk.END).strip(), plan=plan_name)
                    refresh_pop()
                    try:
                        import subprocess, platform
                        system = platform.system(); path = str(created)
                        if system == 'Linux': subprocess.Popen(['xdg-open', path])
                        elif system == 'Darwin': subprocess.Popen(['open', path])
                        elif system == 'Windows': subprocess.Popen(['explorer', path])
                    except Exception: pass
                    dlg.destroy()
                except Exception as e:
                    log_message(f'SETTINGS: Error creating project todo (dialog): {e}')
                    messagebox.showerror('Error', f'Failed to create todo: {e}', parent=dlg)
            btns2 = ttk.Frame(frm); btns2.grid(row=4, column=1, sticky=tk.E)
            ttk.Button(btns2, text='Create', style='Action.TButton', command=do_create).pack(side=tk.LEFT, padx=4)
            ttk.Button(btns2, text='Cancel', style='Select.TButton', command=dlg.destroy).pack(side=tk.LEFT, padx=4)

        def mark_cb():
            sel = get_sel_from_pop()
            if not sel:
                messagebox.showinfo("No Selection", "Please select a todo to mark complete.", parent=top)
                return
            category, filename = sel
            if category not in ('tasks', 'bugs', 'work_orders', 'notes'):
                messagebox.showinfo("Invalid Selection", "Select a task, bug, work-order, or note to mark complete.", parent=top)
                return
            if not messagebox.askyesno("Mark Complete", "Mark this todo as complete?", parent=top):
                return
            try:
                from pathlib import Path
                todos_dir = get_project_todos_dir(project_name)
                todo_dir = todos_dir / category
                filepath = todo_dir / filename
                if filepath.exists():
                    move_project_todo_to_completed(project_name, filepath)
                refresh_pop()
                try:
                    pr_var.set('low')
                    title_var.set('')
                    _set_details_text('')
                except Exception:
                    pass
            except Exception as e:
                log_message(f"SETTINGS: Error in project mark_cb: {e}")
                messagebox.showerror("Error", f"Failed to mark complete: {e}", parent=top)

        def save_cb():
            sel = get_sel_from_pop()
            if not sel:
                messagebox.showinfo("No Selection", "Please select a todo to save.", parent=top)
                return
            category, filename = sel
            if category == 'completed':
                messagebox.showinfo("Read Only", "Completed items are read-only. Delete or recreate to change.", parent=top)
                return
            try:
                new_title = (title_var.get() or '').strip()
                new_priority = pr_var.get()
                # Preserve details; edit externally
                new_details = None
                if not new_title:
                    messagebox.showwarning("Missing Title", "Title cannot be empty.", parent=top)
                    return
                from pathlib import Path
                todos_dir = get_project_todos_dir(project_name)
                todo_dir = todos_dir / category
                filepath = todo_dir / filename
                if not filepath.exists():
                    messagebox.showerror("Error", "Todo file not found.", parent=top)
                    return
                new_filepath = update_todo_file(filepath, new_title, new_priority, new_details)
                refresh_pop()
                try:
                    new_filename = new_filepath.name
                    pop_tree.selection_set(f"{category}:{new_filename}")
                except Exception:
                    pass
                populate_details_from_sel()
            except Exception as e:
                log_message(f"SETTINGS: Error in project save_cb: {e}")
                messagebox.showerror("Error", f"Failed to save: {e}", parent=top)

        def _send_to_trash(path_str: str) -> bool:
            try:
                try:
                    from send2trash import send2trash
                    send2trash(path_str)
                    return True
                except Exception:
                    pass
                import platform, subprocess, os, shutil
                system = platform.system()
                if system == 'Linux' and shutil.which('gio'):
                    subprocess.check_call(['gio', 'trash', path_str])
                    return True
                tdir = get_project_todos_dir(project_name).parent / '.trash'
                tdir.mkdir(parents=True, exist_ok=True)
                import shutil as _sh
                _sh.move(path_str, tdir / Path(path_str).name)
                return True
            except Exception:
                return False

        def delete_cb():
            sel = get_sel_from_pop()
            if not sel:
                messagebox.showinfo("No Selection", "Please select a todo to delete.", parent=top)
                return
            category, filename = sel
            if category not in ('tasks', 'bugs', 'work_orders', 'notes', 'completed'):
                messagebox.showinfo("Invalid Selection", "Select an item to delete.", parent=top)
                return
            if not messagebox.askyesno("Confirm Delete", "Delete selected todo?", parent=top):
                return
            try:
                from pathlib import Path
                todos_dir = get_project_todos_dir(project_name)
                todo_dir = todos_dir / category
                filepath = todo_dir / filename
                if filepath.exists():
                    _send_to_trash(str(filepath))
                refresh_pop()
                try:
                    pr_var.set('low')
                    title_var.set('')
                    details_txt.delete('1.0', tk.END)
                except Exception:
                    pass
            except Exception as e:
                log_message(f"SETTINGS: Error in project delete_cb: {e}")
                messagebox.showerror("Error", f"Failed to delete: {e}", parent=top)

        def edit_cb():
            sel = get_sel_from_pop()
            if not sel:
                messagebox.showinfo("No Selection", "Please select a todo to edit.", parent=top)
                return
            category, filename = sel
            if category not in ('tasks', 'bugs', 'work_orders', 'notes', 'completed', 'plans', 'tests'):
                messagebox.showinfo("Invalid Selection", "Select a valid todo to open.", parent=top)
                return

            try:
                from pathlib import Path
                todos_dir = get_project_todos_dir(project_name)
                todo_dir = todos_dir / category
                filepath = todo_dir / filename
                if not filepath.exists():
                    messagebox.showerror("Error", "Todo file not found.", parent=top)
                    return
                import subprocess, platform
                system = platform.system()
                path = str(filepath)
                if system == 'Linux': subprocess.Popen(['xdg-open', path])
                elif system == 'Darwin': subprocess.Popen(['open', path])
                elif system == 'Windows': subprocess.Popen(['explorer', path])
            except Exception as e:
                log_message(f"SETTINGS: Error opening project todo externally: {e}")
                messagebox.showerror("Error", f"Failed to open: {e}", parent=top)

        # Action buttons (includes Open)
        for i in range(6):
            try:
                btns.columnconfigure(i, weight=1)
            except Exception:
                pass
        ttk.Button(btns, text="➕ Create Todo", command=create_cb, style='Action.TButton').grid(row=0, column=0, padx=3, sticky=tk.EW)
        ttk.Button(btns, text="✔ Mark Complete", command=mark_cb, style='Select.TButton').grid(row=0, column=1, padx=3, sticky=tk.EW)
        ttk.Button(btns, text="✏️ Edit (Open)", command=edit_cb, style='Select.TButton').grid(row=0, column=2, padx=3, sticky=tk.EW)
        ttk.Button(btns, text="📄 Open File", command=edit_cb, style='Select.TButton').grid(row=0, column=3, padx=3, sticky=tk.EW)
        ttk.Button(btns, text="🗑 Delete Todo", command=delete_cb, style='Select.TButton').grid(row=0, column=4, padx=3, sticky=tk.EW)
        ttk.Button(btns, text="💾 Save (Title/Priority)", command=save_cb, style='Action.TButton').grid(row=0, column=5, padx=3, sticky=tk.EW)

        # Double-click to open file
        try:
            pop_tree.bind('<Double-1>', lambda e: edit_cb())
        except Exception:
            pass

    def todo_create(self):
        # Step 1: Category selection popup
        top = tk.Toplevel(self.root); top.title('Create ToDo')
        frm = ttk.Frame(top, padding=8); frm.pack(fill=tk.BOTH, expand=True)
        ttk.Label(frm, text='Select Category', style='CategoryPanel.TLabel').grid(row=0, column=0, columnspan=5, pady=(0,6))
        choice = {'cat': None, 'prio': None, 'title': None, 'details': None}
        def pick(cat): choice['cat']=cat; pick_prio()
        for i,(label,cat) in enumerate((('Tasks','tasks'),('Bugs','bugs'),('Work-Orders','work_orders'),('Completed','completed'),('Notes','notes'))):
            ttk.Button(frm, text=label, style='Action.TButton', command=lambda c=cat: pick(c)).grid(row=1, column=i, padx=4, pady=4, sticky=tk.EW)
        def pick_prio():
            for w in frm.winfo_children(): w.destroy()
            if choice['cat']=='completed':
                choice['prio']='low'
                enter_title(); return
            ttk.Label(frm, text='Set Priority', style='CategoryPanel.TLabel').grid(row=0,column=0,columnspan=3,pady=(0,6))
            def setp(p): choice['prio']=p; enter_title()
            ttk.Button(frm, text='High', style='Action.TButton', command=lambda: setp('high')).grid(row=1,column=0,padx=4,pady=4,sticky=tk.EW)
            ttk.Button(frm, text='Medium', style='Action.TButton', command=lambda: setp('medium')).grid(row=1,column=1,padx=4,pady=4,sticky=tk.EW)
            ttk.Button(frm, text='Low', style='Action.TButton', command=lambda: setp('low')).grid(row=1,column=2,padx=4,pady=4,sticky=tk.EW)
        def enter_title():
            for w in frm.winfo_children(): w.destroy()
            ttk.Label(frm, text='Describe ToDo', style='CategoryPanel.TLabel').grid(row=0,column=0,sticky=tk.W)
            title_var = tk.StringVar()
            ent = ttk.Entry(frm, textvariable=title_var, width=48)
            ent.grid(row=1,column=0,sticky=tk.EW,pady=4)
            def next_details():
                choice['title'] = (title_var.get() or '').strip()
                if not choice['title']:
                    messagebox.showerror('Create ToDo','Please enter a description.'); return
                enter_details()
            ttk.Button(frm, text='Next', style='Action.TButton', command=next_details).grid(row=2,column=0,sticky=tk.E, pady=6)
            ent.focus_set()
        def enter_details():
            for w in frm.winfo_children(): w.destroy()
            ttk.Label(frm, text='Details', style='CategoryPanel.TLabel').grid(row=0,column=0,sticky=tk.W)
            txt = scrolledtext.ScrolledText(frm, height=12, wrap=tk.WORD, font=('Arial', 9), bg='#1e1e1e', fg='#dcdcdc')
            txt.grid(row=1,column=0,sticky=tk.NSEW)
            frm.rowconfigure(1, weight=1)
            def save_all():
                choice['details'] = txt.get('1.0', tk.END).strip()
                # Build entry and save
                if choice['cat'] == 'completed':
                    self.todos.setdefault('completed', []).append({ 'text': choice['title'], 'details': choice['details'], 'type': 'task', 'priority': 'low' })
                else:
                    self.todos.setdefault(choice['cat'], []).append({ 'text': choice['title'], 'details': choice['details'], 'priority': choice['prio'], 'done': False })
                self.save_settings_to_file(); self.refresh_todo_view(); top.destroy()
            ttk.Button(frm, text='OK', style='Action.TButton', command=save_all).grid(row=2,column=0,sticky=tk.E, pady=6)
        # Start flow
        try:
            top.transient(self.root); top.lift(); top.attributes('-topmost', True); self.root.after(400, lambda: top.attributes('-topmost', False))
        except Exception:
            pass
        # Initialize category selection view
        # (Callbacks proceed to next steps)

    def todo_mark_complete(self):
        """Move selected todo file to completed directory."""
        sel = self._get_selected_todo()
        if not sel:
            messagebox.showinfo("No Selection", "Please select a todo (task/bug) to mark complete.")
            return
        category, filename = sel
        if category not in ('tasks', 'bugs', 'work_orders', 'notes'):
            messagebox.showinfo("Invalid Selection", "Select a task or bug, not a category header.")
            return
        if not messagebox.askyesno("Mark Complete", "Mark this todo as complete?"):
            return
        try:
            from pathlib import Path
            todo_dir = TODOS_DIR / category
            filepath = todo_dir / filename
            if filepath.exists():
                move_todo_to_completed(filepath)
            self.refresh_todo_view()
        except Exception as e:
            log_message(f"SETTINGS: Error marking complete: {e}")
            messagebox.showerror("Error", f"Failed to mark complete: {e}")

    def todo_edit(self):
        """Open edit dialog for selected todo file."""
        sel = self._get_selected_todo()
        if not sel:
            messagebox.showinfo("No Selection", "Please select a todo to edit.")
            return
        category, filename = sel
        if category not in ('tasks', 'bugs', 'work_orders', 'notes'):
            messagebox.showinfo("Invalid Selection", "Select a task or bug to edit.")
            return
        try:
            from pathlib import Path
            todo_dir = TODOS_DIR / category
            filepath = todo_dir / filename
            if not filepath.exists():
                messagebox.showerror("Error", "Todo file not found.")
                return

            # Load todo from file
            todo_data = read_todo_file(filepath)

            # Edit popup with priority + title + details
            top = tk.Toplevel(self.root)
            top.title('Edit ToDo')
            frm = ttk.Frame(top, padding=8)
            frm.pack(fill=tk.BOTH, expand=True)

            ttk.Label(frm, text='Priority', style='CategoryPanel.TLabel').grid(row=0, column=0, sticky=tk.W)
            pr = tk.StringVar(value=todo_data.get('priority', 'low'))

            def setp(v):
                pr.set(v)

            btnf = ttk.Frame(frm)
            btnf.grid(row=0, column=1, sticky=tk.W)
            ttk.Button(btnf, text='High', style='Action.TButton', command=lambda: setp('high')).pack(side=tk.LEFT, padx=2)
            ttk.Button(btnf, text='Medium', style='Action.TButton', command=lambda: setp('medium')).pack(side=tk.LEFT, padx=2)
            ttk.Button(btnf, text='Low', style='Action.TButton', command=lambda: setp('low')).pack(side=tk.LEFT, padx=2)

            ttk.Label(frm, text='Title', style='CategoryPanel.TLabel').grid(row=1, column=0, sticky=tk.W, pady=(6, 0))
            title_var = tk.StringVar(value=todo_data.get('title', ''))
            ent = ttk.Entry(frm, textvariable=title_var, width=50)
            ent.grid(row=1, column=1, sticky=tk.EW, pady=(6, 0))

            ttk.Label(frm, text='Details', style='CategoryPanel.TLabel').grid(row=2, column=0, sticky=tk.W, pady=(6, 0))
            txt = scrolledtext.ScrolledText(frm, height=10, wrap=tk.WORD, font=('Arial', 9), bg='#1e1e1e', fg='#dcdcdc')
            txt.grid(row=2, column=1, sticky=tk.NSEW, pady=(6, 0))
            frm.columnconfigure(1, weight=1)
            frm.rowconfigure(2, weight=1)
            txt.insert(tk.END, todo_data.get('details', ''))

            def save_edits():
                try:
                    new_title = (title_var.get() or '').strip()
                    new_priority = pr.get()
                    new_details = txt.get('1.0', tk.END).strip()

                    if not new_title:
                        messagebox.showwarning("Missing Title", "Title cannot be empty.", parent=top)
                        return

                    # Update file (may rename if title changed)
                    update_todo_file(filepath, new_title, new_priority, new_details)

                    self.refresh_todo_view()
                    top.destroy()
                except Exception as e:
                    log_message(f"SETTINGS: Error saving edits: {e}")
                    messagebox.showerror("Error", f"Failed to save: {e}", parent=top)

            ttk.Button(frm, text='Save', style='Action.TButton', command=save_edits).grid(row=3, column=1, sticky=tk.E, pady=6)
        except Exception as e:
            log_message(f"SETTINGS: Error in todo_edit: {e}")
            messagebox.showerror("Error", f"Failed to open editor: {e}")

    def todo_delete(self):
        """Delete selected todo file."""
        sel = self._get_selected_todo()
        if not sel:
            messagebox.showinfo("No Selection", "Please select a todo to delete.")
            return
        category, filename = sel
        # Allow deleting from all categories including completed
        if category not in ('tasks', 'bugs', 'work_orders', 'notes', 'completed'):
            messagebox.showinfo("Invalid Selection", "Select an item to delete.")
            return
        if not messagebox.askyesno("Confirm Delete", "Delete selected todo?"):
            return
        try:
            from pathlib import Path
            todo_dir = TODOS_DIR / category
            filepath = todo_dir / filename
            if filepath.exists():
                delete_todo_file(filepath)
            self.refresh_todo_view()
        except Exception as e:
            log_message(f"SETTINGS: Error deleting todo: {e}")
            messagebox.showerror("Error", f"Failed to delete: {e}")

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

    def _populate_tab_visibility_controls(self, parent_frame):
        """Populates the 'Tab Visibility' section with checkboxes for each tab."""
        # Clear existing controls
        for widget in parent_frame.winfo_children():
            widget.destroy()

        # Get a list of all known tabs (main tabs)
        known_tabs = [
            ("Training Tab", "training_tab_enabled"),
            ("Models Tab", "models_tab_enabled"),
            ("Settings Tab", "settings_tab_enabled"),
            ("Custom Code Tab", "custom_code_tab_enabled"),
        ]

        for display_name, setting_key in known_tabs:
            var = tk.BooleanVar(value=self.settings.get(setting_key, True)) # Default to enabled
            self.tab_enabled_vars[setting_key] = var

            cb = ttk.Checkbutton(
                parent_frame,
                text=f"Show {display_name}",
                variable=var,
                command=self._on_tab_visibility_changed,
                style='Category.TCheckbutton'
            )
            cb.pack(fill=tk.X, padx=10, pady=2, anchor=tk.W)

        # --- Tab Reordering Mode ---
        reorder_frame = ttk.LabelFrame(parent_frame, text="Tab Reordering Mode", style='TLabelframe')
        reorder_frame.pack(fill=tk.X, padx=10, pady=10)

        modes = [
            ("D&D", "dnd"),
            ("Arrow Buttons", "arrow")
        ]

        for text, mode in modes:
            rb = ttk.Radiobutton(
                reorder_frame,
                text=text,
                variable=self.reorder_mode,
                value=mode,
                command=self._on_reorder_mode_changed,
                style='Category.TRadiobutton' # You might need to define this style
            )
            rb.pack(fill=tk.X, padx=10, pady=2, anchor=tk.W)

        # Save button to persist the current tab order
        ttk.Button(
            reorder_frame,
            text="💾 Save Tab Order",
            command=self.save_tab_order_now,
            style='Action.TButton'
        ).pack(fill=tk.X, padx=10, pady=(8, 4))

    def save_tab_order_now(self):
        """Capture current notebook tab order and persist to settings.json."""
        if not self.main_gui or not hasattr(self.main_gui, 'notebook') or not self.tab_instances:
            messagebox.showerror("Error", "Cannot save tab order. Internal components not found.")
            return

        notebook = self.main_gui.notebook
        # Build order from current notebook tabs
        new_tab_order = []
        for tab_id in notebook.tabs():
            for name, info in self.tab_instances.items():
                if str(info['frame']) == tab_id:
                    new_tab_order.append(name)
                    break

        if not new_tab_order:
            messagebox.showerror("Error", "Could not determine current tab order.")
            return

        # Also capture per-tab panel orders (headers)
        panel_orders = {}
        for tab_name, meta in self.tab_instances.items():
            nb = None
            inst = meta.get('instance')
            for attr in (
                'training_notebook',   # TrainingTab
                'sub_notebook',        # CustomCodeTab
                'settings_notebook',   # SettingsTab
                'model_info_notebook', # ModelsTab
                'models_notebook'      # Fallback
            ):
                nb = getattr(inst, attr, None) if inst is not None else None
                if nb is not None:
                    break
            if nb is None:
                continue
            headers = []
            try:
                for tid in nb.tabs():
                    try:
                        headers.append(nb.tab(tid, 'text'))
                    except Exception:
                        pass
            except Exception:
                pass
            if headers:
                panel_orders[tab_name] = headers

        # Update in-memory settings and persist
        self.settings['tab_order'] = new_tab_order
        if panel_orders:
            self.settings['panel_orders'] = panel_orders
        try:
            self.save_settings_to_file()
            messagebox.showinfo("Tab Order Saved", "Tab order saved. Use Quick Restart to apply.")
        except Exception as e:
            messagebox.showerror("Save Error", f"Failed to save tab order: {e}")

    def _on_tab_visibility_changed(self):
        """Callback when a tab visibility checkbox is toggled."""
        # Immediately save settings to persist the change
        self.save_settings_to_file()
        messagebox.showinfo("Tab Visibility Changed", "Tab visibility settings saved. Please Quick Restart the application to apply changes.")

    def _on_reorder_mode_changed(self):
        """Callback when the reorder mode is changed."""
        mode = self.reorder_mode.get()
        
        if mode == 'arrow':
            if hasattr(self, 'move_left_button'):
                self.move_left_button.pack(fill=tk.X, pady=2)
                self.move_right_button.pack(fill=tk.X, pady=2)
        else:
            if hasattr(self, 'move_left_button'):
                self.move_left_button.pack_forget()
                self.move_right_button.pack_forget()

        # Only show guidance when not programmatically toggled
        if not getattr(self, '_suppress_reorder_popup', False):
            if mode in ('arrow', 'dnd'):
                messagebox.showinfo(
                    "Reorder Mode",
                    f"Reorder mode set to '{mode}'.\n\nChanges are temporary until you click 'Save Tab Order'."
                )

    def move_tab(self, direction):
        """Move the selected tab left or right in the order, dynamically."""
        log_message(f"SETTINGS: move_tab called with direction: {direction}")
        if not self.selected_tree_item:
            log_message("SETTINGS: move_tab aborted - nothing selected.")
            messagebox.showwarning("No Selection", "Please select a tab or panel from the tree to move.")
            return

        if self.selected_tree_item.get('type') == 'panel_header':
            # Delegate to panel move within the tab's notebook
            return self._move_panel_within_tab(direction)

        if self.selected_tree_item.get('type') != 'tab':
            log_message("SETTINGS: move_tab aborted - selection is not a main tab.")
            messagebox.showwarning("Wrong Selection", "Select a main tab header to reorder tabs.")
            return

        selected_tab_dir_name = self.selected_tree_item.get('tab_name') or self.selected_tree_item['path'].name
        log_message(f"SETTINGS: Selected tab for move: {selected_tab_dir_name}")

        if not self.main_gui or not hasattr(self.main_gui, 'notebook') or not self.tab_instances:
            log_message("SETTINGS ERROR: Main GUI, notebook, or tab_instances not available.")
            messagebox.showerror("Error", "Cannot reorder tabs. Internal components not found.")
            return

        notebook = self.main_gui.notebook

        if selected_tab_dir_name not in self.tab_instances:
            log_message(f"SETTINGS ERROR: Selected tab '{selected_tab_dir_name}' not in tab_instances.")
            messagebox.showerror("Error", "Selected tab not found in the application's tab registry.")
            return
            
        tab_to_move_frame = self.tab_instances[selected_tab_dir_name]['frame']

        try:
            current_index = notebook.index(tab_to_move_frame)
        except tk.TclError:
            log_message(f"SETTINGS ERROR: Could not find tab '{selected_tab_dir_name}' in the notebook.")
            messagebox.showerror("Error", "Could not find the selected tab in the notebook.")
            return

        new_index = current_index
        if direction == "left":
            if current_index > 0:
                new_index = current_index - 1
            else:
                log_message("SETTINGS: Cannot move tab further left.")
                return
        elif direction == "right":
            if current_index < len(notebook.tabs()) - 1:
                new_index = current_index + 1
            else:
                log_message("SETTINGS: Cannot move tab further right.")
                return
        
        log_message(f"SETTINGS: Moving tab from index {current_index} to {new_index}.")
        
        # Move the tab in the notebook
        notebook.insert(new_index, tab_to_move_frame)

        # Update the tab_order in settings dictionary (without saving to file)
        new_tab_order = []
        for tab_id in notebook.tabs():
            for name, info in self.tab_instances.items():
                if str(info['frame']) == tab_id:
                    new_tab_order.append(name)
                    break
        
        self.settings['tab_order'] = new_tab_order
        log_message(f"SETTINGS: New tab order in memory: {new_tab_order}")

        # Refresh the tree to show the new order based on the in-memory settings
        self.refresh_tabs_tree()

    def _move_panel_within_tab(self, direction):
        """Move selected panel header left/right inside its parent tab's notebook."""
        try:
            tab_name = self.selected_tree_item.get('tab_name')
            header = self.selected_tree_item.get('panel_header')
            if not tab_name or not header:
                raise ValueError("Missing tab/panel selection")

            if not self.tab_instances or tab_name not in self.tab_instances:
                messagebox.showerror("Error", "Cannot reorder panels. Tab instance not found.")
                return

            instance = self.tab_instances[tab_name]['instance']
            notebook = None
            for attr in (
                'training_notebook',
                'sub_notebook',
                'settings_notebook',
                'model_info_notebook',
                'models_notebook'
            ):
                nb = getattr(instance, attr, None)
                if nb is not None:
                    notebook = nb
                    break
            if notebook is None:
                messagebox.showerror("Error", "Selected tab has no panels to reorder.")
                return

            tab_ids = notebook.tabs()
            current_index = None
            for idx, tid in enumerate(tab_ids):
                try:
                    if notebook.tab(tid, 'text') == header:
                        current_index = idx
                        break
                except Exception:
                    continue
            if current_index is None:
                messagebox.showerror("Error", "Could not locate selected panel in the tab.")
                return

            new_index = current_index
            if direction == 'left':
                if current_index > 0:
                    new_index = current_index - 1
                else:
                    return
            elif direction == 'right':
                if current_index < len(tab_ids) - 1:
                    new_index = current_index + 1
                else:
                    return

            tab_id = tab_ids[current_index]
            notebook.insert(new_index, tab_id)

            # Refresh the tree to reflect the new order
            self.refresh_tabs_tree()
        except Exception as e:
            log_message(f"SETTINGS ERROR: Panel move failed: {e}")
            messagebox.showerror("Error", f"Failed to reorder panel: {e}")

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

        log_message("SETTINGS: Settings tab refreshed.")

    def quick_restart_application(self):
        try:
            log_message("SETTINGS: User initiated Quick Restart. (Method entered)")
            # Call save_settings_to_file directly. It handles its own success/error messages.
            self.save_settings_to_file()
                
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

        except Exception as e:
            log_message(f"SETTINGS CRITICAL ERROR: Unhandled exception in quick_restart_application: {e}")
            import traceback
            log_message(f"SETTINGS CRITICAL TRACEBACK: {traceback.format_exc()}")
            messagebox.showerror("Critical Error", f"An unexpected error occurred during Quick Restart: {e}\nCheck debug log for details.")

    def copy_log_to_clipboard(self):
        """Copies the content of the currently displayed log to the clipboard."""
        try:
            log_content = self.debug_output.get(1.0, tk.END)
            if not log_content.strip():
                messagebox.showinfo("Clipboard", "Log is empty. Nothing to copy.")
                return

            self.root.clipboard_clear()
            self.root.clipboard_append(log_content)
            messagebox.showinfo("Clipboard", "Log content copied to clipboard!")
            log_message("SETTINGS: Log content copied to clipboard.")
        except Exception as e:
            messagebox.showerror("Clipboard Error", f"Failed to copy log to clipboard: {e}")
            log_message(f"SETTINGS ERROR: Failed to copy log to clipboard: {e}")

    def create_custom_code_settings(self, parent):
        """Create Custom Code feature settings"""
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

        # Tool Orchestrator Section
        orchestrator_section = ttk.LabelFrame(content_frame, text="🎯 Tool Orchestrator", style='TLabelframe')
        orchestrator_section.pack(fill=tk.X, padx=10, pady=10)

        self.enable_tool_orchestrator = tk.BooleanVar(
            value=self.settings.get('custom_code', {}).get('enable_tool_orchestrator', False)
        )
        ttk.Checkbutton(
            orchestrator_section,
            text="Enable Advanced Tool Orchestrator",
            variable=self.enable_tool_orchestrator,
            style='Category.TCheckbutton'
        ).pack(anchor=tk.W, padx=10, pady=5)

        ttk.Label(
            orchestrator_section,
            text="Enables intelligent tool chaining, confirmation gates, and risk assessment",
            font=("Arial", 8),
            foreground='#888888'
        ).pack(anchor=tk.W, padx=10, pady=(0, 10))

        # Format Translators Section
        translators_section = ttk.LabelFrame(content_frame, text="🔄 Format Translators", style='TLabelframe')
        translators_section.pack(fill=tk.X, padx=10, pady=10)

        self.enable_json_translator = tk.BooleanVar(
            value=self.settings.get('custom_code', {}).get('enable_json_translator', True)
        )
        ttk.Checkbutton(
            translators_section,
            text="JSON Format Translator",
            variable=self.enable_json_translator,
            style='Category.TCheckbutton'
        ).pack(anchor=tk.W, padx=10, pady=5)

        self.enable_yaml_translator = tk.BooleanVar(
            value=self.settings.get('custom_code', {}).get('enable_yaml_translator', False)
        )
        ttk.Checkbutton(
            translators_section,
            text="YAML Format Translator",
            variable=self.enable_yaml_translator,
            style='Category.TCheckbutton'
        ).pack(anchor=tk.W, padx=10, pady=5)

        # Parsers Section
        parsers_section = ttk.LabelFrame(content_frame, text="📋 Response Parsers", style='TLabelframe')
        parsers_section.pack(fill=tk.X, padx=10, pady=10)

        self.enable_structured_parser = tk.BooleanVar(
            value=self.settings.get('custom_code', {}).get('enable_structured_parser', True)
        )
        ttk.Checkbutton(
            parsers_section,
            text="Structured Output Parser",
            variable=self.enable_structured_parser,
            style='Category.TCheckbutton'
        ).pack(anchor=tk.W, padx=10, pady=5)

        self.enable_datetime_parser = tk.BooleanVar(
            value=self.settings.get('custom_code', {}).get('enable_datetime_parser', False)
        )
        ttk.Checkbutton(
            parsers_section,
            text="DateTime Parser",
            variable=self.enable_datetime_parser,
            style='Category.TCheckbutton'
        ).pack(anchor=tk.W, padx=10, pady=5)

        self.enable_regex_parser = tk.BooleanVar(
            value=self.settings.get('custom_code', {}).get('enable_regex_parser', False)
        )
        ttk.Checkbutton(
            parsers_section,
            text="Regex Pattern Parser",
            variable=self.enable_regex_parser,
            style='Category.TCheckbutton'
        ).pack(anchor=tk.W, padx=10, pady=5)

        # Advanced Features Section
        advanced_section = ttk.LabelFrame(content_frame, text="⚙️ Advanced Features", style='TLabelframe')
        advanced_section.pack(fill=tk.X, padx=10, pady=10)

        self.enable_context_scorer = tk.BooleanVar(
            value=self.settings.get('custom_code', {}).get('enable_context_scorer', False)
        )
        ttk.Checkbutton(
            advanced_section,
            text="Context Scoring (RAG optimization)",
            variable=self.enable_context_scorer,
            style='Category.TCheckbutton'
        ).pack(anchor=tk.W, padx=10, pady=5)

        self.enable_time_slicer = tk.BooleanVar(
            value=self.settings.get('custom_code', {}).get('enable_time_slicer', False)
        )
        ttk.Checkbutton(
            advanced_section,
            text="Time-Sliced Generation",
            variable=self.enable_time_slicer,
            style='Category.TCheckbutton'
        ).pack(anchor=tk.W, padx=10, pady=5)

        self.enable_verification_engine = tk.BooleanVar(
            value=self.settings.get('custom_code', {}).get('enable_verification_engine', False)
        )
        ttk.Checkbutton(
            advanced_section,
            text="Verification Engine (output validation)",
            variable=self.enable_verification_engine,
            style='Category.TCheckbutton'
        ).pack(anchor=tk.W, padx=10, pady=5)

        # Save button
        ttk.Button(
            content_frame,
            text="💾 Save Custom Code Settings",
            command=self.save_custom_code_settings,
            style='Action.TButton'
        ).pack(pady=20, padx=10, fill=tk.X)

    def save_custom_code_settings(self):
        """Save custom code settings"""
        try:
            # Read existing settings
            all_settings = {}
            if self.settings_file.exists():
                try:
                    with open(self.settings_file, 'r') as f:
                        all_settings = json.load(f)
                except Exception as e:
                    log_message(f"SETTINGS ERROR: Could not read settings: {e}")

            # Update custom_code section
            all_settings['custom_code'] = {
                'enable_tool_orchestrator': self.enable_tool_orchestrator.get(),
                'enable_json_translator': self.enable_json_translator.get(),
                'enable_yaml_translator': self.enable_yaml_translator.get(),
                'enable_structured_parser': self.enable_structured_parser.get(),
                'enable_datetime_parser': self.enable_datetime_parser.get(),
                'enable_regex_parser': self.enable_regex_parser.get(),
                'enable_context_scorer': self.enable_context_scorer.get(),
                'enable_time_slicer': self.enable_time_slicer.get(),
                'enable_verification_engine': self.enable_verification_engine.get(),
            }

            # Save
            with open(self.settings_file, 'w') as f:
                json.dump(all_settings, f, indent=2)

            log_message("SETTINGS: Custom Code settings saved successfully")
            messagebox.showinfo("Settings Saved", "Custom Code settings have been saved successfully!")

        except Exception as e:
            log_message(f"SETTINGS ERROR: Failed to save custom code settings: {e}")
            messagebox.showerror("Save Error", f"Failed to save settings: {e}")

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

        ttk.Button(controls_frame, text="🔄", command=self.populate_log_file_combobox, style='Select.TButton', width=4).grid(row=0, column=2, sticky=tk.E, padx=(0, 5))
        ttk.Button(controls_frame, text="📎", command=self.copy_log_to_clipboard, style='Select.TButton', width=4).grid(row=0, column=3, sticky=tk.E)

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

    # --- Evaluation Policy UI ---
    def _init_policy_vars(self):
        data = self.settings.get('regression_policy', {}) if hasattr(self, 'settings') else {}
        self.policy_enabled = tk.BooleanVar(value=data.get('enabled', True))
        self.policy_alert_drop = tk.DoubleVar(value=data.get('alert_drop_percent', 5.0))
        self.policy_strict_block = tk.BooleanVar(value=data.get('strict_block', False))
        self.policy_auto_rollback = tk.BooleanVar(value=data.get('auto_rollback', False))

    def create_policy_settings(self, parent):
        parent.columnconfigure(0, weight=1)
        container = ttk.Frame(parent, style='Category.TFrame')
        container.grid(row=0, column=0, sticky=tk.NSEW, padx=10, pady=10)
        if not hasattr(self, 'policy_enabled'):
            self._init_policy_vars()

        ttk.Label(container, text="Evaluation & Regression Policy", font=("Arial", 12, "bold"), style='CategoryPanel.TLabel').grid(row=0, column=0, sticky=tk.W, pady=(0, 10))
        ttk.Checkbutton(container, text="Enable Regression Policy", variable=self.policy_enabled, style='Category.TCheckbutton').grid(row=1, column=0, sticky=tk.W, pady=5)

        row_frame = ttk.Frame(container)
        row_frame.grid(row=2, column=0, sticky=tk.W)
        ttk.Label(row_frame, text="Alert if drop > %:", style='Config.TLabel').pack(side=tk.LEFT, padx=(0, 8))
        ttk.Spinbox(row_frame, from_=0.0, to=100.0, increment=0.5, textvariable=self.policy_alert_drop, width=8).pack(side=tk.LEFT)

        ttk.Checkbutton(container, text="Strict Mode: Flag training if regressions detected", variable=self.policy_strict_block, style='Category.TCheckbutton').grid(row=3, column=0, sticky=tk.W, pady=5)
        ttk.Checkbutton(container, text="Auto-Rollback (not implemented)", variable=self.policy_auto_rollback, style='Category.TCheckbutton').grid(row=4, column=0, sticky=tk.W, pady=5)
        ttk.Button(container, text="💾 Save Policy", command=self.save_settings_to_file, style='Action.TButton').grid(row=5, column=0, sticky=tk.W, pady=(10,0))

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

    def create_blueprints_tab(self, parent):
        """Create System Blueprints documentation tab"""
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

        # Header + Blueprint selector toolbar
        header_section = ttk.Frame(content_frame)
        header_section.pack(fill=tk.X, padx=10, pady=10)
        ttk.Label(
            header_section,
            text="🗺️ OpenCode Trainer System Architecture",
            font=("Arial", 14, "bold"),
            foreground='#4db8ff'
        ).grid(row=0, column=0, columnspan=4, sticky=tk.W)
        ttk.Label(
            header_section,
            text="Complete End-to-End Integrated Training Pipeline",
            font=("Arial", 10),
            foreground='#888888'
        ).grid(row=1, column=0, columnspan=4, sticky=tk.W, pady=(0,4))

        # Blueprint selector row
        header_section.columnconfigure(1, weight=1)
        ttk.Label(header_section, text='Blueprint:', style='CategoryPanel.TLabel').grid(row=2, column=0, sticky=tk.W, padx=(0,6))
        self.bp_select_var = tk.StringVar()
        self.bp_selector = ttk.Combobox(header_section, textvariable=self.bp_select_var, state='readonly')
        self.bp_selector.grid(row=2, column=1, sticky=tk.EW)
        ttk.Button(header_section, text='Update Blueprint', style='Select.TButton', command=lambda: self._clone_increment_blueprint()).grid(row=2, column=2, padx=6)
        ttk.Button(header_section, text='Edit', style='Action.TButton', command=lambda: self._open_blueprint_editor()).grid(row=2, column=3)

        # Blueprint preview area
        preview_frame = ttk.LabelFrame(content_frame, text='📄 Blueprint Preview', style='TLabelframe')
        preview_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0,10))
        preview_frame.columnconfigure(0, weight=1)
        preview_frame.rowconfigure(0, weight=1)
        self.bp_preview = scrolledtext.ScrolledText(preview_frame, wrap=tk.WORD, font=("Arial", 9), bg="#1e1e1e", fg="#dcdcdc")
        self.bp_preview.grid(row=0, column=0, sticky=tk.NSEW)

        # Helper methods for blueprints
        def _registry_path():
            return Path('extras/blueprints/blueprint_registry.txt')

        def _list_blueprints_from_fs():
            base = Path('extras/blueprints')
            files = []
            try:
                for p in sorted(base.glob('Trainer_Blue_Print_*.txt')):
                    files.append(p.name)
            except Exception:
                pass
            return files

        def _read_registry():
            rp = _registry_path()
            if rp.exists():
                try:
                    return [ln.strip() for ln in rp.read_text().splitlines() if ln.strip() and not ln.strip().startswith('#')]
                except Exception:
                    return []
            # bootstrap registry with FS scan
            return _list_blueprints_from_fs()

        def _write_registry(names):
            try:
                Path('extras/blueprints').mkdir(parents=True, exist_ok=True)
                _registry_path().write_text('\n'.join(names) + '\n')
            except Exception:
                pass

        def _set_preview(text):
            try:
                self.bp_preview.config(state=tk.NORMAL)
                self.bp_preview.delete('1.0', tk.END)
                self.bp_preview.insert(tk.END, text)
                self.bp_preview.config(state=tk.DISABLED)
            except Exception:
                pass

        def _load_selected_into_preview():
            sel = self.bp_select_var.get().strip()
            if not sel:
                _set_preview('')
                return
            path = Path('extras/blueprints')/sel
            try:
                txt = path.read_text()
            except Exception as e:
                txt = f"Failed to load {path}: {e}"
            _set_preview(txt)

        def _parse_version_from_name(name):
            import re
            m = re.search(r'v(\d+)\.(\d+)', name)
            if not m:
                return None
            return int(m.group(1)), int(m.group(2))

        def _bump_minor(v):
            if not v:
                return (2, 1)
            return (v[0], v[1] + 1)

        def _update_content_version(text, new_ver_tuple):
            new_ver = f"{new_ver_tuple[0]}.{new_ver_tuple[1]}"
            lines = text.splitlines()
            out = []
            from datetime import date
            today = date.today().isoformat()
            for ln in lines:
                if ln.strip().startswith('Version:'):
                    out.append(f"  Version: {new_ver}")
                elif 'Blueprint v' in ln:
                    # e.g., "OpenCode Trainer System - Blueprint v2.0"
                    import re
                    out.append(re.sub(r'Blueprint v\d+\.\d+', f'Blueprint v{new_ver}', ln))
                elif ln.strip().startswith('Date:'):
                    out.append(f"  Date: {today}")
                else:
                    out.append(ln)
            return '\n'.join(out) + ('\n' if text.endswith('\n') else '')

        def _ensure_registry_seeded():
            names = _read_registry()
            if not names:
                names = _list_blueprints_from_fs()
            if not names:
                # create seed with v2.0 if missing
                seed = 'Trainer_Blue_Print_v2.0.txt'
                if (Path('extras/blueprints')/seed).exists():
                    names = [seed]
            _write_registry(names)
            return names

        def _refresh_selector(select_name=None):
            names = _ensure_registry_seeded()
            self.bp_selector['values'] = names
            # default to last entry if none selected
            if select_name and select_name in names:
                self.bp_select_var.set(select_name)
            elif not self.bp_select_var.get() and names:
                self.bp_select_var.set(names[-1])
            _load_selected_into_preview()

        # Bind events and expose handlers on self
        self._refresh_blueprint_selector = _refresh_selector
        self._load_blueprint_into_preview = _load_selected_into_preview
        self._read_blueprint_registry = _read_registry
        self._write_blueprint_registry = _write_registry
        self._parse_bp_version = _parse_version_from_name
        self._bump_bp_minor = _bump_minor
        self._update_content_version = _update_content_version

        try:
            self.bp_selector.bind('<<ComboboxSelected>>', lambda e: _load_selected_into_preview())
        except Exception:
            pass

        # Public methods: clone/update and editor
        def _clone_increment_blueprint():
            names = _read_registry()
            sel = self.bp_select_var.get().strip() or (names[-1] if names else '')
            if not sel:
                messagebox.showinfo('Update Blueprint', 'No blueprint selected.')
                return
            src = Path('extras/blueprints')/sel
            if not src.exists():
                messagebox.showerror('Update Blueprint', f'Source file not found: {src}')
                return
            v = _parse_version_from_name(sel)
            new_v = _bump_minor(v)
            base = 'Trainer_Blue_Print'
            new_name = f"{base}_v{new_v[0]}.{new_v[1]}.txt"
            dst = Path('extras/blueprints')/new_name
            if dst.exists():
                messagebox.showerror('Update Blueprint', f'Target exists: {dst.name}')
                return
            try:
                text = src.read_text()
                updated = _update_content_version(text, new_v)
                dst.write_text(updated)
            except Exception as e:
                messagebox.showerror('Update Blueprint', f'Failed to clone: {e}')
                return
            # Update registry
            names.append(new_name)
            _write_registry(names)
            # Refresh selector and preview to new file
            _refresh_selector(select_name=new_name)
            messagebox.showinfo('Update Blueprint', f'Created {new_name}')

        def _open_blueprint_editor():
            sel = self.bp_select_var.get().strip()
            if not sel:
                messagebox.showinfo('Edit Blueprint', 'No blueprint selected.')
                return
            path = Path('extras/blueprints')/sel
            top = tk.Toplevel(self.root); top.title(f'Edit: {sel}')
            frm = ttk.Frame(top, padding=8); frm.pack(fill=tk.BOTH, expand=True)
            frm.columnconfigure(0, weight=1); frm.rowconfigure(0, weight=1)
            txt = scrolledtext.ScrolledText(frm, wrap=tk.WORD, font=("Arial", 9), bg='#1e1e1e', fg='#dcdcdc')
            txt.grid(row=0, column=0, sticky=tk.NSEW)
            btns = ttk.Frame(frm); btns.grid(row=1, column=0, sticky=tk.E)
            def _save():
                try:
                    path.write_text(txt.get('1.0', tk.END))
                    # refresh preview
                    _load_selected_into_preview()
                    messagebox.showinfo('Save', 'Blueprint saved.')
                except Exception as e:
                    messagebox.showerror('Save Failed', str(e))
            def _copy():
                try:
                    self.root.clipboard_clear()
                    self.root.clipboard_append(txt.get('1.0', tk.END))
                    messagebox.showinfo('Copied', 'Blueprint copied to clipboard.')
                except Exception:
                    pass
            ttk.Button(btns, text='Copy to Clipboard', style='Select.TButton', command=_copy).pack(side=tk.RIGHT, padx=4)
            ttk.Button(btns, text='Save', style='Action.TButton', command=_save).pack(side=tk.RIGHT, padx=4)
            try:
                txt.insert(tk.END, path.read_text())
            except Exception as e:
                txt.insert(tk.END, f'Failed to open {path}: {e}')

        # Attach methods to instance for button callbacks
        self._clone_increment_blueprint = _clone_increment_blueprint
        self._open_blueprint_editor = _open_blueprint_editor

        # Seed registry file if missing and load selector
        try:
            Path('extras/blueprints').mkdir(parents=True, exist_ok=True)
            # Ensure registry includes v2.0 at least
            reg = _ensure_registry_seeded()
            if not reg:
                # create registry pointing to v2.0 if exists
                if (Path('extras/blueprints')/'Trainer_Blue_Print_v2.0.txt').exists():
                    _write_registry(['Trainer_Blue_Print_v2.0.txt'])
            self._refresh_blueprint_selector()
        except Exception:
            pass

        # Overview Section
        overview_section = ttk.LabelFrame(content_frame, text="📋 System Overview", style='TLabelframe')
        overview_section.pack(fill=tk.X, padx=10, pady=10)

        overview_text = """The OpenCode Trainer integrates multiple subsystems to provide a complete model lifecycle management platform:

        ✓ Model Lineage Tracking - Track model genealogy from base to fine-tuned versions
        ✓ Dual Skill Verification - Runtime usage validation vs evaluation test results
        ✓ Automated Training Data Generation - Multiple sources for training data creation
        ✓ Regression Detection - Identify skill degradation with auto-correction
        ✓ Complete Workflow Integration - Seamless flow from download to deployment"""

        overview_label = ttk.Label(
            overview_section,
            text=overview_text,
            font=("Arial", 9),
            foreground='#cccccc',
            justify=tk.LEFT,
            wraplength=700
        )
        overview_label.pack(padx=10, pady=10, anchor=tk.W)

        # Integrated Workflow Section
        workflow_section = ttk.LabelFrame(content_frame, text="🔄 Complete Integrated Workflow", style='TLabelframe')
        workflow_section.pack(fill=tk.X, padx=10, pady=10)

        workflow_text = """STEP 1: Model Download & Initial Evaluation
        • Download base model (e.g., Qwen 0.5B) to Models directory
        • Convert to GGUF format
        • Run initial evaluation tests (Models Tab → Evaluate)
        • Baseline skills recorded (claimed skills from tests)

STEP 2: Runtime Validation & Data Collection
        • Enable "Training Mode" in Custom Code Chat Interface
        • Use the model with real tasks and tool calls
        • ToolCallLogger captures every tool invocation with success/failure
        • Real-time skill scoring updated (verified skills from actual usage)
        • ChatHistoryManager saves conversations for later extraction

STEP 3: Skill Verification & Gap Analysis
        • Models Tab displays DUAL skill view:
          - Verified (Runtime): ≥80% success rate, actual usage proof
          - Claimed (Evaluation): Test results, may be false positives
          - Failed: <80% success rate, needs training
        • Identify gaps: skills with good eval but poor runtime = false positives
        • Identify needs: skills with 0% runtime usage = untrained capabilities

STEP 4: Automated Training Data Generation
        Multiple sources automatically create training data:
        • Chat History Extraction: Extract successful tool usage patterns
        • Runtime Log Conversion: Convert tool call logs to training format
        • Corrective Data Generation: Auto-generate examples for failed skills
        All outputs saved to Training_Data-Sets/ directory

STEP 5: LoRA Fine-Tuning with Lineage Tracking
        • Select generated training data in Training Tab
        • Configure LoRA parameters (r=16, alpha=32, etc.)
        • TrainingEngine automatically:
          - Fine-tunes with adapters
          - Records lineage (base model → adapter → metadata)
          - Runs post-training evaluation
          - Saves results to Models directory

STEP 6: Regression Detection & Continuous Improvement
        • EvaluationEngine compares new eval to baseline
        • Detects regressions: skills that dropped >5% accuracy
        • Auto-generates corrective training data targeting failed skills
        • Provides re-training recommendations
        • Complete cycle: evaluate → identify issues → generate fixes → retrain"""

        workflow_label = ttk.Label(
            workflow_section,
            text=workflow_text,
            font=("Courier", 8),
            foreground='#aaaaaa',
            justify=tk.LEFT,
            wraplength=700
        )
        workflow_label.pack(padx=10, pady=10, anchor=tk.W)

        # System Integration Map
        integration_section = ttk.LabelFrame(content_frame, text="🔗 System Integration Map", style='TLabelframe')
        integration_section.pack(fill=tk.X, padx=10, pady=10)

        integration_text = """┌─────────────────────────────────────────────────────────────┐
│                    DATA FLOW INTEGRATION                    │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ToolCallLogger ──────┬──────> RuntimeToTrainingConverter  │
│      (JSONL logs)     │              ↓                      │
│                       │     Training Data (JSONL)           │
│                       │              ↓                      │
│  ChatHistoryManager ──┤──────> TrainingEngine               │
│      (conversations)  │         (LoRA fine-tune)            │
│                       │              ↓                      │
│  EvaluationEngine ────┤──────> LineageTracker              │
│      (test reports)   │         (model genealogy)           │
│                       │              ↓                      │
│  config.py ───────────┘──────> Models Tab Display          │
│  (_get_runtime_skills)           (dual verification)       │
│                                                             │
└─────────────────────────────────────────────────────────────┘

KEY INTEGRATION POINTS:
• ToolCallLogger → RuntimeSkills: Real-time scoring in config.py
• ChatHistoryManager → Training Data: Extract successful patterns
• EvaluationEngine → Baseline Comparison: Detect regressions
• TrainingEngine → LineageTracker: Record model genealogy
• Models Tab: Merge runtime + evaluation skills for display"""

        integration_label = ttk.Label(
            integration_section,
            text=integration_text,
            font=("Courier", 8),
            foreground='#88ff88',
            justify=tk.LEFT
        )
        integration_label.pack(padx=10, pady=10, anchor=tk.W)

        # Key Components Section
        components_section = ttk.LabelFrame(content_frame, text="⚙️ Key System Components", style='TLabelframe')
        components_section.pack(fill=tk.X, padx=10, pady=10)

        components_text = """LINEAGE TRACKER (tabs/custom_code_tab/lineage_tracker.py)
• Singleton pattern for model genealogy tracking
• Records: base model, adapter path, training date, metadata
• File: Training_Data-Sets/ModelLineage/lineage.json
• Integration: Called automatically by TrainingEngine after training

TOOL CALL LOGGER (tabs/custom_code_tab/tool_call_logger.py)
• JSONL-based persistent logging of all tool calls
• Tracks: tool name, arguments, result, success/failure, timestamp
• Enhanced validation: Multi-level success detection
• File: Training_Data-Sets/ToolCallLogs/{model_name}_calls.jsonl
• Integration: Chat interface logs every tool execution

RUNTIME TO TRAINING CONVERTER (tabs/custom_code_tab/runtime_to_training.py)
• Converts tool call logs to OpenAI training format
• Generates corrective training data from failures
• Creates proper message sequences: user → assistant → tool → assistant
• Output: Training_Data-Sets/Training/{model}_runtime_{timestamp}.jsonl

CHAT HISTORY MANAGER (tabs/custom_code_tab/chat_history_manager.py)
• Persistent conversation storage with training extraction
• Filters by tool usage count and success rate
• Extracts complete tool usage patterns
• File: Training_Data-Sets/ChatHistories/{session_id}.json

EVALUATION ENGINE (Data/evaluation_engine.py)
• Test suite execution with regression detection
• Compares current results to baseline (first eval)
• Auto-triggers corrective training on regression
• Reports: Training_Data-Sets/Evaluations/{model}_eval_report.json

TRAINING ENGINE (Data/training_engine.py)
• LoRA fine-tuning with Unsloth
• Automatic post-training evaluation
• Lineage recording after every training run
• Output: Models/{model_name}/ (adapter + merged model)

MODELS TAB (tabs/models_tab/models_tab.py)
• Dual skill verification display:
  - Verified Runtime: Green, ≥80% success
  - Unverified Eval: Yellow, low/no runtime usage
  - Failed Runtime: Red, <80% success
• Merges _get_runtime_skills() + get_model_skills()
• Shows skill source: (Runtime/Eval/Both)"""

        components_label = ttk.Label(
            components_section,
            text=components_text,
            font=("Courier", 8),
            foreground='#ffaa88',
            justify=tk.LEFT
        )
        components_label.pack(padx=10, pady=10, anchor=tk.W)

        # Data Flow Section
        dataflow_section = ttk.LabelFrame(content_frame, text="📊 Data Persistence & Storage", style='TLabelframe')
        dataflow_section.pack(fill=tk.X, padx=10, pady=10)

        dataflow_text = """Training_Data-Sets/
├── ChatHistories/           # Saved conversations
│   ├── {session_id}.json
│   └── chat_index.json
├── ToolCallLogs/            # Runtime tool execution logs
│   └── {model_name}_calls.jsonl
├── ModelLineage/            # Model genealogy tracking
│   └── lineage.json
├── Evaluations/             # Test results and baselines
│   └── {model_name}_eval_report.json
└── Training/                # Generated training data
    ├── {model}_runtime_{timestamp}.jsonl
    ├── {model}_corrective_{timestamp}.jsonl
    └── chat_extracted_{model}_{timestamp}.jsonl

Models/
└── {model_name}/
    ├── adapter_model.safetensors  # LoRA adapter weights
    ├── adapter_config.json
    └── model_merged.gguf          # Final merged GGUF

JSONL Format (training data):
{"messages": [
  {"role": "system", "content": "..."},
  {"role": "user", "content": "..."},
  {"role": "assistant", "content": "...", "tool_calls": [...]},
  {"role": "tool", "content": "...", "tool_call_id": "..."},
  {"role": "assistant", "content": "..."}
]}"""

        dataflow_label = ttk.Label(
            dataflow_section,
            text=dataflow_text,
            font=("Courier", 8),
            foreground='#ffdd88',
            justify=tk.LEFT
        )
        dataflow_label.pack(padx=10, pady=10, anchor=tk.W)

        # Development Blueprint v2 Section (Internal)
        dev_section = ttk.LabelFrame(content_frame, text="🧭 Development Blueprint (v2)", style='TLabelframe')
        dev_section.pack(fill=tk.X, padx=10, pady=10)

        dev_text = """SCOPE & STATUS (Internal Artifact)

COMPLETED IN V2
• Temperature Controls: Legacy header controls removed; Manual/Auto persisted; bottom indicator authoritative and accurate; metadata includes temp_mode; Quick View shows Temp Mode.
• Conversations QoL: Rename Chat (Chat + Projects); Projects bottom indicators de-duplicated.
• ToDo v2: Categories (Tasks, Bugs, Work-Orders, Notes, Completed); priority (High/Medium/Low) with colors; creation flow (Category→Priority→Title→Details); inline edit; Mark Complete → green Completed.

IN FLIGHT
• Agents Panel: Receive selections from Collections; display, select, and persist agent sets.
• Orchestrator Wiring: Agent types bound to type-variant training pipeline; expose tool chain controls; log telemetry.
• Dataset Auto-Generation: Profiles per type variant; synthetic generation with provenance; versioned storage.
• Evaluation Suites: Registry, schema-aware checks, multi-metric scoring; trend and baseline compare.
• End-to-End Pipeline: Agents → Profiles → Training → Eval → Compare; resumable runs and artifact indexing.

REMOVED (REDUNDANT)
• Legacy temperature header label/slider/icon (functional duplicate of Quick Actions popup + indicator).

NOTES
• UI state keys: extend the indicator state-key pattern used for temperature to other indicators to avoid duplication across tabs.
• Docs: See extras/blueprints/Trainer_Blue_Print_v2.0.txt for full external blueprint; this section reflects the GUI-internal dev plan.
"""

        dev_label = ttk.Label(
            dev_section,
            text=dev_text,
            font=("Arial", 9),
            foreground='#b8e2ff',
            justify=tk.LEFT,
            wraplength=700
        )
        dev_label.pack(padx=10, pady=10, anchor=tk.W)

    def create_help_tab(self, parent):
        """Create Help & Guide tab"""
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

        # Header
        header_section = ttk.Frame(content_frame)
        header_section.pack(fill=tk.X, padx=10, pady=10)
        ttk.Label(
            header_section,
            text="📖 OpenCode Trainer User Guide",
            font=("Arial", 14, "bold"),
            foreground='#4db8ff'
        ).pack(anchor=tk.W)
        ttk.Label(
            header_section,
            text="Complete guide to using the integrated training pipeline",
            font=("Arial", 10),
            foreground='#888888'
        ).pack(anchor=tk.W)

        # Quick Start Section
        quickstart_section = ttk.LabelFrame(content_frame, text="🚀 Quick Start Guide", style='TLabelframe')
        quickstart_section.pack(fill=tk.X, padx=10, pady=10)

        quickstart_text = """1. DOWNLOAD A MODEL
   • Go to Models Tab
   • Click "Download Model from Hugging Face"
   • Enter model ID (e.g., "Qwen/Qwen2.5-0.5B")
   • Wait for download and GGUF conversion

2. EVALUATE BASELINE SKILLS
   • Select your model in Models Tab
   • Click "Evaluate Model"
   • Review baseline skills in Skills section

3. COLLECT RUNTIME DATA
   • Go to Custom Code Tab → Chat Interface
   • Enable "Training Mode" checkbox
   • Use the model for real tasks with tool calls
   • System automatically logs all tool usage

4. VERIFY REAL SKILLS
   • Return to Models Tab
   • Review Skills display showing:
     - Verified Runtime (green): Actually works
     - Claimed Eval (yellow): Test says it works
     - Failed (red): Doesn't work in practice

5. GENERATE TRAINING DATA
   • In Custom Code Chat Interface:
     - Click "Export Runtime to Training" for tool logs
     - Click "Extract Chat Training Data" for conversations
   • Or use Evaluation Tab for corrective data generation

6. FINE-TUNE THE MODEL
   • Go to Training Tab
   • Select generated training data file
   • Configure LoRA settings (defaults work well)
   • Click "Start Training"
   • System auto-evaluates and records lineage

7. VERIFY IMPROVEMENTS
   • Check Models Tab Skills display
   • Runtime scores should improve
   • Re-train with corrective data if regressions detected"""

        quickstart_label = ttk.Label(
            quickstart_section,
            text=quickstart_text,
            font=("Courier", 8),
            foreground='#cccccc',
            justify=tk.LEFT
        )
        quickstart_label.pack(padx=10, pady=10, anchor=tk.W)

        # Training Mode Section
        training_mode_section = ttk.LabelFrame(content_frame, text="🎯 Using Training Mode", style='TLabelframe')
        training_mode_section.pack(fill=tk.X, padx=10, pady=10)

        training_mode_text = """WHAT IS TRAINING MODE?
Training Mode enables real-time data collection during chat interactions.
When enabled, the system logs every tool call with detailed success metrics.

HOW TO ENABLE:
1. Go to Custom Code Tab → Chat Interface sub-tab
2. Check the "Training Mode" checkbox at the top
3. Green indicator shows mode is active

WHAT GETS COLLECTED:
✓ Every tool call (name, arguments, result)
✓ Success/failure status with enhanced validation
✓ User message context for each tool call
✓ Complete conversation history
✓ Timestamp and execution metadata

WHERE DATA IS SAVED:
• Tool Call Logs: Training_Data-Sets/ToolCallLogs/{model}_calls.jsonl
• Chat History: Training_Data-Sets/ChatHistories/{session_id}.json

BEST PRACTICES:
• Enable for new/unverified models to collect baseline data
• Disable for production use after sufficient data collected
• Use diverse tasks to cover multiple tool types
• Review Models Tab regularly to check skill improvement

AUTO‑TRAINING (Hands‑Free, Custom Code → Training → Models):
• Quick Actions (⚙️) → 🏋️ Training Mode ON (button turns green)
• Failures/refusals generate strict JSONL automatically (Tools/auto_runtime_*.jsonl)
• Training tab auto‑selects dataset and saves profile
• If auto‑start is ON (Settings → Training), training begins immediately
• Progress popup shows run/percent; “View Logs” focuses Runner
• After training complete, export + re‑eval can run automatically (Models tab handler)
• Per‑chat Tools: ⚙️ → 🔧 lets you override tool set for this chat (diff summary printed in Chat)

FAILURE MODES & FIXES:
• Mount failed: Ensure a model is selected (right panel) and Ollama is reachable; errors show stderr/stdout in Chat.
• No dataset generated: Most recent interaction had no failing/ refusal cases — try a task that exercises tools or enable more tools.
• No re‑eval context: The system applies a strict fallback (suite/prompt/schema) based on variant type.
• Pane resizing: If panes disappear, lock widths (🔒) to persist defaults and disable drag.

DATA PRIVACY:
All data stays local on your machine. Nothing is sent externally."""

        training_mode_label = ttk.Label(
            training_mode_section,
            text=training_mode_text,
            font=("Arial", 9),
            foreground='#aaffaa',
            justify=tk.LEFT,
            wraplength=700
        )
        training_mode_label.pack(padx=10, pady=10, anchor=tk.W)

        # Skill Verification Section
        skills_section = ttk.LabelFrame(content_frame, text="✅ Understanding Skill Verification", style='TLabelframe')
        skills_section.pack(fill=tk.X, padx=10, pady=10)

        skills_text = """DUAL VERIFICATION SYSTEM:
The system shows TWO types of skills to identify false positives.

VERIFIED RUNTIME SKILLS (Green)
• Source: Actual tool usage in Chat Interface
• Criteria: ≥80% success rate with ≥3 attempts
• Meaning: Model REALLY has this skill
• Example: file_read: 15 calls, 93% success → VERIFIED

CLAIMED EVALUATION SKILLS (Yellow)
• Source: Test suite results (Models Tab → Evaluate)
• Warning: May test base model, not your fine-tuned GGUF
• Meaning: Tests say it works, but no runtime proof
• Example: web_search: Passed tests but 0 real usage → CLAIMED

FAILED RUNTIME SKILLS (Red)
• Source: Runtime usage with poor success rate
• Criteria: <80% success rate
• Meaning: Model tried but failed
• Action: Generate corrective training data

WHY DUAL VERIFICATION MATTERS:
The evaluation tests run against the base PyTorch model, but you're
using the fine-tuned GGUF. This can create FALSE POSITIVES where
tests pass but the actual model fails.

Runtime verification proves skills by actual usage, not just tests.

HOW TO INTERPRET:
• Green + Yellow = Truly verified skill
• Yellow only = Possible false positive, needs runtime testing
• Red = Needs training
• No color = Never tested or used"""

        skills_label = ttk.Label(
            skills_section,
            text=skills_text,
            font=("Arial", 9),
            foreground='#ffffaa',
            justify=tk.LEFT,
            wraplength=700
        )
        skills_label.pack(padx=10, pady=10, anchor=tk.W)

        # Training Data Section
        training_data_section = ttk.LabelFrame(content_frame, text="📦 Training Data Generation", style='TLabelframe')
        training_data_section.pack(fill=tk.X, padx=10, pady=10)

        training_data_text = """THREE AUTOMATED SOURCES:

1. RUNTIME LOG CONVERSION
   Location: Chat Interface → "Export Runtime to Training"
   What: Converts tool call logs to training format
   Best for: Models with lots of usage data
   Output: Training_Data-Sets/Training/{model}_runtime_{timestamp}.jsonl

2. CHAT HISTORY EXTRACTION
   Location: Chat Interface → "Extract Chat Training Data"
   What: Extracts successful conversation patterns
   Filters: Min tool calls, successful only
   Best for: High-quality conversational patterns
   Output: Training_Data-Sets/Training/chat_extracted_{model}_{timestamp}.jsonl

3. CORRECTIVE DATA GENERATION
   Location: Evaluation Tab → Auto-triggered on regression
   What: Generates correct examples for failed skills
   Targets: Skills with <60% success rate
   Best for: Fixing specific skill failures
   Output: Training_Data-Sets/Training/{model}_corrective_{timestamp}.jsonl

MANUAL DATA CREATION:
You can also manually create training data in JSONL format:
{"messages": [
  {"role": "user", "content": "Search for Python tutorials"},
  {"role": "assistant", "content": "", "tool_calls": [...]},
  {"role": "tool", "content": "...", "tool_call_id": "..."},
  {"role": "assistant", "content": "I found..."}
]}

COMBINING SOURCES:
For best results, merge multiple sources:
• Runtime logs: Real usage patterns
• Chat extractions: Successful conversations
• Corrective data: Targeted fixes for failures"""

        training_data_label = ttk.Label(
            training_data_section,
            text=training_data_text,
            font=("Arial", 9),
            foreground='#ffaaff',
            justify=tk.LEFT,
            wraplength=700
        )
        training_data_label.pack(padx=10, pady=10, anchor=tk.W)

        # Regression Detection Section
        regression_section = ttk.LabelFrame(content_frame, text="⚠️ Regression Detection & Auto-Correction", style='TLabelframe')
        regression_section.pack(fill=tk.X, padx=10, pady=10)

        regression_text = """WHAT IS REGRESSION?
Regression occurs when a model's skills degrade after training.
Example: file_read was 90% accurate, now it's 75% after fine-tuning.

HOW DETECTION WORKS:
1. First evaluation creates BASELINE
2. Subsequent evaluations compare to baseline
3. Skills that drop >5% accuracy = REGRESSED
4. System identifies specific skills that degraded

AUTO-CORRECTION FLOW:
When regression detected:
1. EvaluationEngine.auto_trigger_corrective_training() runs
2. Identifies regressed skills (e.g., ["file_read", "web_search"])
3. Generates corrective training data from:
   - Runtime failures (shows what went wrong)
   - Chat history successes (shows correct patterns)
4. Saves corrective data files
5. Provides re-training recommendation

MANUAL REGRESSION CHECK:
• Go to Models Tab
• Click "Evaluate Model"
• Review evaluation report for regressions
• If found, check Training_Data-Sets/Training/ for corrective files

RE-TRAINING AFTER REGRESSION:
1. Use generated corrective training data
2. Reduce learning rate (try 1e-4 instead of 2e-4)
3. Fewer epochs (1-2) to avoid over-fitting
4. Re-evaluate to confirm improvement

PREVENTION TIPS:
• Don't over-train (3 epochs is usually enough)
• Use diverse training data
• Keep learning rate moderate (2e-4 default)
• Regular evaluation checks after training"""

        regression_label = ttk.Label(
            regression_section,
            text=regression_text,
            font=("Arial", 9),
            foreground='#ffaa88',
            justify=tk.LEFT,
            wraplength=700
        )
        regression_label.pack(padx=10, pady=10, anchor=tk.W)

        # Troubleshooting Section
        troubleshooting_section = ttk.LabelFrame(content_frame, text="🔧 Troubleshooting Common Issues", style='TLabelframe')
        troubleshooting_section.pack(fill=tk.X, padx=10, pady=10)

        troubleshooting_text = """ISSUE: "Model shows skills but fails in chat"
SOLUTION: False positive from evaluation. The test ran on base model,
          not your GGUF. Enable Training Mode and collect real usage data.

ISSUE: "Training data file is empty"
SOLUTION: No tool calls logged yet. Enable Training Mode and use the
          model with tools before exporting training data.

ISSUE: "Skills not improving after training"
SOLUTION:
  1. Check training data quality (open JSONL file)
  2. Increase epochs (try 5-10)
  3. Increase LoRA rank (try r=32)
  4. Ensure training data matches your use case

ISSUE: "Runtime scores not updating"
SOLUTION: Scores persist to config.py on:
  - Model switch
  - Training mode disable
  - Manual export
  Check Models Tab to verify persistence.

ISSUE: "Can't find generated training data"
SOLUTION: Check Training_Data-Sets/Training/ directory.
          Files named: {model}_runtime_{timestamp}.jsonl

ISSUE: "Regression detected after every training"
SOLUTION: You may be over-training. Reduce:
  - Epochs: 1-2 instead of 3+
  - Learning rate: 1e-4 instead of 2e-4
  - Use more diverse training data

ISSUE: "Models Tab shows no skills"
SOLUTION:
  1. Run evaluation first (Models Tab → Evaluate)
  2. Or use model in chat with Training Mode enabled
  3. Skills appear after either evaluation or runtime usage"""

        troubleshooting_label = ttk.Label(
            troubleshooting_section,
            text=troubleshooting_text,
            font=("Arial", 9),
            foreground='#ff8888',
            justify=tk.LEFT,
            wraplength=700
        )
        troubleshooting_label.pack(padx=10, pady=10, anchor=tk.W)

        # Best Practices Section
        best_practices_section = ttk.LabelFrame(content_frame, text="⭐ Best Practices", style='TLabelframe')
        best_practices_section.pack(fill=tk.X, padx=10, pady=10)

        best_practices_text = """MODEL LIFECYCLE:
1. Download → 2. Evaluate → 3. Runtime Test → 4. Collect Data →
5. Generate Training → 6. Fine-tune → 7. Re-evaluate → 8. Deploy

DATA COLLECTION:
• Collect at least 20-30 tool calls before training
• Use diverse tasks covering all tool types
• Include both successes and failures for balance
• Save conversations with good tool usage patterns

TRAINING:
• Start with defaults: 3 epochs, 2e-4 LR, r=16, alpha=32
• Use batch size 2 for 8GB RAM, 4 for 16GB+
• Combine multiple training data sources for best results
• Always run evaluation after training

SKILL VERIFICATION:
• Trust VERIFIED (green) skills - they're proven
• Test CLAIMED (yellow) skills - they may be false positives
• Re-train FAILED (red) skills with corrective data
• Regularly review Models Tab for skill status

REGRESSION HANDLING:
• Check for regressions after every training run
• Use auto-generated corrective data
• Reduce training intensity if regression persists
• Keep baseline evaluation for comparison

SYSTEM MAINTENANCE:
• Clear old logs periodically (Settings → Clear Cache)
• Archive successful training data for reuse
• Keep lineage.json for model tracking
• Regular evaluations to monitor skill drift"""

        best_practices_label = ttk.Label(
            best_practices_section,
            text=best_practices_text,
            font=("Arial", 9),
            foreground='#88ffff',
            justify=tk.LEFT,
            wraplength=700
        )
        best_practices_label.pack(padx=10, pady=10, anchor=tk.W)

    def _on_tab_visibility_changed(self):
        """Callback when a tab visibility checkbox is toggled."""
        # Immediately save settings to persist the change
        self.save_settings_to_file()
        messagebox.showinfo("Tab Visibility Changed", "Tab visibility settings saved. Please Quick Restart the application to apply changes.")
