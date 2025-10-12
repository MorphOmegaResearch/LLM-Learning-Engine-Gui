"""
Tab Generator - Automatically create new tabs with proper structure
"""

from pathlib import Path
from datetime import datetime
import re


class TabGenerator:
    """Generate new tabs with proper file structure and templates"""

    def __init__(self, data_dir):
        self.data_dir = Path(data_dir)
        self.tabs_dir = self.data_dir / "tabs"

    def sanitize_name(self, name):
        """Convert user input to valid Python identifier"""
        # Remove special characters, replace spaces with underscore
        sanitized = re.sub(r'[^a-zA-Z0-9_]', '_', name)
        # Remove leading numbers
        sanitized = re.sub(r'^[0-9]+', '', sanitized)
        # Convert to lowercase
        sanitized = sanitized.lower()
        # Remove consecutive underscores
        sanitized = re.sub(r'_+', '_', sanitized)
        return sanitized.strip('_')

    def create_tab(self, tab_name, num_subtabs=3, has_side_menu=True):
        """
        Create a new tab with all necessary files and structure

        Args:
            tab_name: Display name of the tab
            num_subtabs: Number of sub-tabs to create
            has_side_menu: Whether to include a side menu

        Returns:
            dict with created files and status
        """
        # Sanitize tab name for file/class names
        safe_name = self.sanitize_name(tab_name)
        class_name = ''.join(word.capitalize() for word in safe_name.split('_'))

        # Create tab directory
        tab_dir = self.tabs_dir / f"{safe_name}_tab"
        if tab_dir.exists():
            return {
                'success': False,
                'error': f"Tab '{tab_name}' already exists"
            }

        tab_dir.mkdir(parents=True, exist_ok=True)

        created_files = []

        # Create __init__.py
        init_content = f'''"""
{class_name}Tab - {tab_name} functionality
Auto-generated on {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
"""

from .{safe_name}_tab import {class_name}Tab

__all__ = ['{class_name}Tab']
'''
        init_file = tab_dir / "__init__.py"
        init_file.write_text(init_content)
        created_files.append(str(init_file))

        # Create panel files
        panel_files = []
        for i in range(1, num_subtabs + 1):
            panel_name = f"panel{i}"
            panel_content = self._generate_panel_template(
                safe_name, class_name, panel_name, i
            )
            panel_file = tab_dir / f"{panel_name}.py"
            panel_file.write_text(panel_content)
            created_files.append(str(panel_file))
            panel_files.append({
                'name': panel_name,
                'class': f"Panel{i}",
                'file': panel_name
            })

        # Create main tab file
        tab_content = self._generate_tab_template(
            safe_name, class_name, tab_name, panel_files, has_side_menu
        )
        tab_file = tab_dir / f"{safe_name}_tab.py"
        tab_file.write_text(tab_content)
        created_files.append(str(tab_file))

        return {
            'success': True,
            'tab_dir': str(tab_dir),
            'tab_name': tab_name,
            'safe_name': safe_name,
            'class_name': class_name,
            'files': created_files,
            'import_statement': f"from tabs.{safe_name}_tab import {class_name}Tab"
        }

    def _generate_panel_template(self, safe_name, class_name, panel_name, panel_num):
        """Generate a panel template file"""
        return f'''"""
{class_name}Tab - Panel {panel_num}
Auto-generated panel template
"""

import tkinter as tk
from tkinter import ttk


class Panel{panel_num}:
    """Panel {panel_num} for {class_name}Tab"""

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
            text="Panel {panel_num}",
            font=("Arial", 12, "bold"),
            style='CategoryPanel.TLabel'
        ).pack(pady=10)

        # Content area
        content_frame = ttk.Frame(container)
        content_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        ttk.Label(
            content_frame,
            text="This is Panel {panel_num}. Add your content here.",
            style='Config.TLabel'
        ).pack(pady=20)

        # Example: Add a button
        ttk.Button(
            content_frame,
            text="Example Button",
            command=self.on_button_click,
            style='Action.TButton'
        ).pack(pady=10)

    def on_button_click(self):
        """Example button handler"""
        print(f"Panel {panel_num} button clicked!")
'''

    def _generate_tab_template(self, safe_name, class_name, tab_name, panels, has_side_menu):
        """Generate main tab file template"""
        # Create side menu call (avoid backslash in f-string)
        if has_side_menu:
            create_side_menu_call = "\n        # Create side menu\n        self.create_side_menu(self.parent)"
        else:
            create_side_menu_call = ""

        # Import statements
        panel_imports = '\n'.join([
            f"from .{panel['file']} import {panel['class']}"
            for panel in panels
        ])

        # Panel initialization
        panel_init = '\n        '.join([
            f"self.{panel['name']} = {panel['class']}({panel['name']}_frame, self.style)\n        self.{panel['name']}.create_ui()"
            for panel in panels
        ])

        # Panel frames creation
        panel_frames = '\n\n        '.join([
            f"# Panel {i}\n        {panel['name']}_frame = ttk.Frame(self.notebook)\n        self.notebook.add({panel['name']}_frame, text=\"Panel {i}\")"
            for i, panel in enumerate(panels, 1)
        ])

        # Side menu buttons
        menu_buttons = ''
        if has_side_menu:
            menu_buttons = '\n'.join([
                f'        ttk.Button(\n'
                f'            menu_buttons_frame,\n'
                f'            text="📄 Panel {i}",\n'
                f'            command=lambda: self.notebook.select({i-1}),\n'
                f'            style="Select.TButton"\n'
                f'        ).pack(fill=tk.X, pady=2, padx=5)'
                for i in range(1, len(panels) + 1)
            ])

        side_menu_code = ''
        if has_side_menu:
            side_menu_code = f'''
    def create_side_menu(self, parent):
        """Create side menu for quick navigation"""
        menu_frame = ttk.Frame(parent, style='Category.TFrame')
        menu_frame.grid(row=0, column=1, sticky=tk.NSEW, padx=10, pady=10)
        menu_frame.columnconfigure(0, weight=1)
        menu_frame.rowconfigure(1, weight=1)

        ttk.Label(
            menu_frame,
            text="📋 Quick Access",
            font=("Arial", 11, "bold"),
            style='CategoryPanel.TLabel'
        ).grid(row=0, column=0, pady=5, sticky=tk.W, padx=5)

        # Scrollable menu
        menu_canvas = tk.Canvas(menu_frame, bg="#2b2b2b", highlightthickness=0)
        menu_scrollbar = ttk.Scrollbar(menu_frame, orient="vertical", command=menu_canvas.yview)
        menu_buttons_frame = ttk.Frame(menu_canvas)

        menu_buttons_frame.bind(
            "<Configure>",
            lambda e: menu_canvas.configure(scrollregion=menu_canvas.bbox("all"))
        )

        menu_canvas_window = menu_canvas.create_window((0, 0), window=menu_buttons_frame, anchor="nw")
        menu_canvas.configure(yscrollcommand=menu_scrollbar.set)

        menu_canvas.grid(row=1, column=0, sticky=tk.NSEW)
        menu_scrollbar.grid(row=1, column=1, sticky=tk.NS)

        menu_canvas.bind("<Configure>", lambda e: menu_canvas.itemconfig(menu_canvas_window, width=e.width))

        # Menu buttons
{menu_buttons}
'''

        return f'''"""
{class_name}Tab - {tab_name}
Auto-generated on {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
"""

import tkinter as tk
from tkinter import ttk
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from tabs.base_tab import BaseTab

# Import panels
{panel_imports}


class {class_name}Tab(BaseTab):
    """{tab_name} tab with multiple panels"""

    def __init__(self, parent, root, style):
        super().__init__(parent, root, style)

    def create_ui(self):
        """Create the tab UI"""
        self.parent.columnconfigure(0, weight=1)
        self.parent.columnconfigure(1, weight=0)
        self.parent.rowconfigure(0, weight=1)

        # Main content area
        content_frame = ttk.Frame(self.parent, style='Category.TFrame')
        content_frame.grid(row=0, column=0, sticky=tk.NSEW, padx=10, pady=10)
        content_frame.columnconfigure(0, weight=1)
        content_frame.rowconfigure(0, weight=1)

        # Title
        ttk.Label(
            content_frame,
            text="📋 {tab_name}",
            font=("Arial", 14, "bold"),
            style='CategoryPanel.TLabel'
        ).pack(pady=5)

        # Sub-tabs notebook
        self.notebook = ttk.Notebook(content_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        {panel_frames}

        # Initialize panels
        {panel_init}
{create_side_menu_call}
{side_menu_code if has_side_menu else ''}
'''

    def get_available_tabs(self):
        """Get list of all available tabs"""
        tabs = []
        if self.tabs_dir.exists():
            for tab_dir in self.tabs_dir.iterdir():
                if tab_dir.is_dir() and tab_dir.name.endswith('_tab'):
                    tab_name = tab_dir.name.replace('_tab', '')
                    tabs.append({
                        'name': tab_name,
                        'dir': str(tab_dir),
                        'display_name': tab_name.replace('_', ' ').title()
                    })
        return tabs
