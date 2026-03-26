#!/usr/bin/env python3
"""
Multi-purpose Python Development Toolkit
Combines CLI workflows, code analysis, formatting, and Tkinter GUI generation
"""

import argparse
import sys
import os
import py_compile
import subprocess
import difflib
import logging
import traceback
import json
import ast
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext

# Try to import optional dependencies
try:
    import radon
    from radon.complexity import cc_visit
    RADON_AVAILABLE = True
except ImportError:
    RADON_AVAILABLE = False

try:
    import autopep8
    AUTOPEP8_AVAILABLE = True
except ImportError:
    AUTOPEP8_AVAILABLE = False

try:
    import black
    BLACK_AVAILABLE = True
except ImportError:
    BLACK_AVAILABLE = True

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('pydev_toolkit.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class CodeAnalyzer:
    """Code complexity and quality analysis"""
    
    @staticmethod
    def analyze_complexity(file_path: str) -> Dict[str, Any]:
        """Analyze cyclomatic complexity of Python file"""
        results = {
            'file': file_path,
            'complexity': [],
            'errors': []
        }
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                code = f.read()
            
            if RADON_AVAILABLE:
                blocks = cc_visit(code)
                for block in blocks:
                    results['complexity'].append({
                        'name': block.name,
                        'type': block.type,
                        'complexity': block.complexity,
                        'lineno': block.lineno,
                        'col_offset': block.col_offset
                    })
            else:
                # Simple AST-based complexity analysis
                tree = ast.parse(code)
                for node in ast.walk(tree):
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                        complexity = 1  # Base complexity
                        for child in ast.walk(node):
                            if isinstance(child, (ast.If, ast.While, ast.For, ast.AsyncFor,
                                                ast.Try, ast.ExceptHandler, ast.With, ast.AsyncWith)):
                                complexity += 1
                            elif isinstance(child, (ast.BoolOp, ast.Compare)):
                                complexity += len(child.ops)
                        
                        results['complexity'].append({
                            'name': node.name,
                            'type': type(node).__name__,
                            'complexity': complexity,
                            'lineno': node.lineno
                        })
        
        except Exception as e:
            results['errors'].append(str(e))
            logger.error(f"Complexity analysis error: {e}")
        
        return results
    
    @staticmethod
    def compile_check(file_path: str) -> bool:
        """Check if Python file compiles successfully"""
        try:
            py_compile.compile(file_path, doraise=True)
            return True
        except py_compile.PyCompileError as e:
            logger.error(f"Compilation error in {file_path}: {e}")
            return False
        except Exception as e:
            logger.error(f"Error compiling {file_path}: {e}")
            return False

class CodeFormatter:
    """Code formatting utilities"""
    
    @staticmethod
    def format_with_autopep8(code: str) -> str:
        """Format code using autopep8 if available"""
        if AUTOPEP8_AVAILABLE:
            return autopep8.fix_code(code)
        return code
    
    @staticmethod
    def format_with_black(code: str) -> str:
        """Format code using black if available"""
        if BLACK_AVAILABLE:
            try:
                return black.format_str(code, mode=black.Mode())
            except Exception:
                return code
        return code
    
    @staticmethod
    def indent_code(code: str, spaces: int = 4) -> str:
        """Basic indentation formatter"""
        lines = code.split('\n')
        formatted_lines = []
        indent_level = 0
        
        for line in lines:
            stripped = line.strip()
            if not stripped:
                formatted_lines.append('')
                continue
            
            # Decrease indent for dedent keywords
            if stripped.startswith(('return', 'break', 'continue', 'pass')):
                pass
            if stripped.startswith(('elif ', 'else:', 'except ', 'finally:')):
                indent_level -= 1
            
            # Apply current indent
            formatted_lines.append(' ' * (indent_level * spaces) + stripped)
            
            # Increase indent for indent keywords
            if stripped.endswith(':'):
                indent_level += 1
            if stripped.startswith(('return ', 'break ', 'continue ', 'pass ')):
                indent_level -= 1
        
        return '\n'.join(formatted_lines)

class DiffManager:
    """Manage code diffs and snapshots"""
    
    def __init__(self, snapshot_dir: str = '.snapshots'):
        self.snapshot_dir = Path(snapshot_dir)
        self.snapshot_dir.mkdir(exist_ok=True)
    
    def create_snapshot(self, file_path: str, description: str = "") -> str:
        """Create a snapshot of a file"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        snapshot_name = f"{Path(file_path).stem}_{timestamp}.snap"
        snapshot_path = self.snapshot_dir / snapshot_name
        
        try:
            with open(file_path, 'r') as f:
                content = f.read()
            
            snapshot_data = {
                'file': file_path,
                'timestamp': timestamp,
                'description': description,
                'content': content
            }
            
            with open(snapshot_path, 'w') as f:
                json.dump(snapshot_data, f, indent=2)
            
            logger.info(f"Snapshot created: {snapshot_path}")
            return str(snapshot_path)
        
        except Exception as e:
            logger.error(f"Error creating snapshot: {e}")
            return ""
    
    def compare_with_snapshot(self, file_path: str, snapshot_path: str) -> List[str]:
        """Compare current file with snapshot"""
        try:
            with open(snapshot_path, 'r') as f:
                snapshot = json.load(f)
            
            with open(file_path, 'r') as f:
                current_content = f.readlines()
            
            snapshot_content = snapshot['content'].splitlines(keepends=True)
            
            diff = difflib.unified_diff(
                snapshot_content,
                current_content,
                fromfile=f"snapshot: {snapshot_path}",
                tofile=f"current: {file_path}",
                lineterm=''
            )
            
            return list(diff)
        
        except Exception as e:
            logger.error(f"Error comparing with snapshot: {e}")
            return []

class TkinterGUIBuilder:
    """Tkinter GUI template builder"""
    
    @staticmethod
    def generate_template(config: Dict[str, Any]) -> str:
        """Generate Tkinter GUI template based on configuration"""
        
        panels = config.get('panels', [])
        data_fields = config.get('data_fields', [])
        notebook_tabs = config.get('notebook_tabs', [])
        
        template = f'''#!/usr/bin/env python3
"""
Generated Tkinter GUI Application
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext
from pathlib import Path
import json
import os

class Application(tk.Tk):
    """Main Application Window"""
    
    def __init__(self):
        super().__init__()
        
        self.title("{config.get('title', 'Tkinter Application')}")
        self.geometry("{config.get('geometry', '1200x800')}")
        
        # Configure styles
        self.style = ttk.Style()
        self.style.theme_use('clam')
        
        # Data storage
        self.data = {{}}
{chr(10).join([f'        self.data["{field["name"]}"] = {repr(field.get("default", ""))}' for field in data_fields])}
        
        # Setup UI
        self.setup_ui()
        
    def setup_ui(self):
        """Setup user interface"""
        # Main container
        main_container = ttk.PanededWindow(self, orient=tk.HORIZONTAL)
        main_container.pack(fill=tk.BOTH, expand=True)
        
        # Left panel container
        left_panel = ttk.Frame(main_container)
        main_container.add(left_panel, width=300)
        
        # Treeview for directories
        self.setup_treeview(left_panel)
        
        # Right panel container
        right_panel = ttk.Frame(main_container)
        main_container.add(right_panel, weight=1)
        
        # Notebook for tabs
        self.setup_notebook(right_panel)
        
        # Data fields panel
        self.setup_data_fields(right_panel)
        
        # Menu bar
        self.setup_menubar()
        
        # Status bar
        self.setup_statusbar()
    
    def setup_treeview(self, parent):
        """Setup directory treeview"""
        tree_frame = ttk.LabelFrame(parent, text="Directories", padding=10)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Treeview
        self.tree = ttk.Treeview(tree_frame)
        self.tree.pack(fill=tk.BOTH, expand=True)
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.tree.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.configure(yscrollcommand=scrollbar.set)
        
        # Treeview columns
        self.tree["columns"] = ("type", "size")
        self.tree.column("#0", width=200)
        self.tree.column("type", width=100)
        self.tree.column("size", width=100)
        
        self.tree.heading("#0", text="Name")
        self.tree.heading("type", text="Type")
        self.tree.heading("size", text="Size")
        
        # Buttons
        btn_frame = ttk.Frame(tree_frame)
        btn_frame.pack(fill=tk.X, pady=5)
        
        ttk.Button(btn_frame, text="Add Directory", command=self.add_directory).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="Refresh", command=self.refresh_tree).pack(side=tk.LEFT, padx=2)
    
    def setup_notebook(self, parent):
        """Setup notebook with tabs"""
        notebook_frame = ttk.LabelFrame(parent, text="Workspace", padding=10)
        notebook_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.notebook = ttk.Notebook(notebook_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)
        
        # Add tabs
{chr(10).join([TkinterGUIBuilder._generate_tab_code(tab) for tab in notebook_tabs])}
    
    def setup_data_fields(self, parent):
        """Setup data entry fields"""
        fields_frame = ttk.LabelFrame(parent, text="Data Fields", padding=10)
        fields_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # Create fields
        fields_container = ttk.Frame(fields_frame)
        fields_container.pack(fill=tk.X, pady=5)
        
        row = 0
{chr(10).join([TkinterGUIBuilder._generate_field_code(field, idx) for idx, field in enumerate(data_fields)])}
        
        # Action buttons
        btn_frame = ttk.Frame(fields_frame)
        btn_frame.pack(fill=tk.X, pady=10)
        
        ttk.Button(btn_frame, text="Save Data", command=self.save_data).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Load Data", command=self.load_data).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Clear All", command=self.clear_data).pack(side=tk.LEFT, padx=5)
    
    def setup_menubar(self):
        """Setup menu bar"""
        menubar = tk.Menu(self)
        self.config(menu=menubar)
        
        # File menu
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="New", command=self.on_new)
        file_menu.add_command(label="Open", command=self.on_open)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.quit)
        
        # Tools menu
        tools_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Tools", menu=tools_menu)
        tools_menu.add_command(label="Run Script", command=self.run_script)
        tools_menu.add_command(label="Check Syntax", command=self.check_syntax)
        
        # Help menu
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Help", menu=help_menu)
        help_menu.add_command(label="About", command=self.show_about)
    
    def setup_statusbar(self):
        """Setup status bar"""
        self.statusbar = ttk.Label(self, text="Ready", relief=tk.SUNKEN)
        self.statusbar.pack(side=tk.BOTTOM, fill=tk.X)
    
    # Event handlers
    def add_directory(self):
        """Add directory to treeview"""
        directory = filedialog.askdirectory()
        if directory:
            self.populate_tree(directory)
    
    def refresh_tree(self):
        """Refresh treeview"""
        for item in self.tree.get_children():
            self.tree.delete(item)
    
    def populate_tree(self, path):
        """Populate treeview with directory contents"""
        pass  # Implementation needed
    
    def save_data(self):
        """Save data to file"""
        filename = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        if filename:
            with open(filename, 'w') as f:
                json.dump(self.data, f, indent=2)
            self.statusbar.config(text=f"Data saved to {{filename}}")
    
    def load_data(self):
        """Load data from file"""
        filename = filedialog.askopenfilename(
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        if filename:
            with open(filename, 'r') as f:
                loaded_data = json.load(f)
                self.data.update(loaded_data)
                self.update_fields_from_data()
            self.statusbar.config(text=f"Data loaded from {{filename}}")
    
    def clear_data(self):
        """Clear all data fields"""
        for key in self.data:
            self.data[key] = ""
        self.update_fields_from_data()
        self.statusbar.config(text="Data cleared")
    
    def update_fields_from_data(self):
        """Update UI fields from data dictionary"""
        # Implementation depends on field structure
        pass
    
    def on_new(self):
        """Handle New menu item"""
        self.clear_data()
    
    def on_open(self):
        """Handle Open menu item"""
        self.load_data()
    
    def run_script(self):
        """Run a Python script"""
        filename = filedialog.askopenfilename(
            filetypes=[("Python files", "*.py"), ("All files", "*.*")]
        )
        if filename:
            try:
                result = subprocess.run([sys.executable, filename], 
                                      capture_output=True, text=True)
                self.show_output(result.stdout, result.stderr)
            except Exception as e:
                messagebox.showerror("Error", f"Failed to run script: {{e}}")
    
    def check_syntax(self):
        """Check Python syntax"""
        filename = filedialog.askopenfilename(
            filetypes=[("Python files", "*.py"), ("All files", "*.*")]
        )
        if filename:
            try:
                with open(filename, 'r') as f:
                    compile(f.read(), filename, 'exec')
                messagebox.showinfo("Syntax Check", "Syntax is valid!")
            except SyntaxError as e:
                messagebox.showerror("Syntax Error", f"{{e}}")
    
    def show_output(self, stdout, stderr):
        """Show script output in dialog"""
        output_window = tk.Toplevel(self)
        output_window.title("Script Output")
        output_window.geometry("600x400")
        
        text_area = scrolledtext.ScrolledText(output_window, wrap=tk.WORD)
        text_area.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        if stdout:
            text_area.insert(tk.END, "STDOUT:\\n" + stdout + "\\n")
        if stderr:
            text_area.insert(tk.END, "STDERR:\\n" + stderr + "\\n")
    
    def show_about(self):
        """Show about dialog"""
        messagebox.showinfo(
            "About",
            f"""{config.get('title', 'Tkinter Application')}
Generated by PyDev Toolkit
            
Version: 1.0
Generated on: {datetime.now().strftime('%Y-%m-%d')}
"""
        )
    
    def run(self):
        """Start the application"""
        self.mainloop()

if __name__ == "__main__":
    import subprocess
    import sys
    
    app = Application()
    app.run()
'''
        return template
    
    @staticmethod
    def _generate_tab_code(tab_config: Dict[str, Any]) -> str:
        """Generate code for a notebook tab"""
        tab_name = tab_config.get('name', 'Tab')
        widgets = tab_config.get('widgets', [])
        
        widget_code = []
        for widget in widgets:
            if widget['type'] == 'text':
                widget_code.append(f'        text_widget = scrolledtext.ScrolledText(tab, wrap=tk.WORD)')
                widget_code.append(f'        text_widget.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)')
            elif widget['type'] == 'button':
                widget_code.append(f'        ttk.Button(tab, text="{widget.get("label", "Button")}").pack(pady=5)')
        
        return f'''
        # Tab: {tab_name}
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="{tab_name}")
        {chr(10).join(widget_code)}
'''
    
    @staticmethod
    def _generate_field_code(field_config: Dict[str, Any], index: int) -> str:
        """Generate code for a data field"""
        name = field_config['name']
        label = field_config.get('label', name)
        field_type = field_config.get('type', 'entry')
        
        if field_type == 'entry':
            return f'''        # Field: {name}
        ttk.Label(fields_container, text="{label}:").grid(row={index}, column=0, sticky=tk.W, padx=5, pady=2)
        self.entry_{name} = ttk.Entry(fields_container)
        self.entry_{name}.grid(row={index}, column=1, sticky=tk.EW, padx=5, pady=2)
        self.entry_{name}.insert(0, self.data["{name}"])
        self.entry_{name}.bind("<KeyRelease>", lambda e: self._on_field_change("{name}"))
'''
        elif field_type == 'checkbox':
            return f'''        # Field: {name}
        self.var_{name} = tk.BooleanVar(value=self.data["{name}"])
        ttk.Checkbutton(fields_container, text="{label}", variable=self.var_{name},
                       command=lambda: self._on_field_change("{name}")).grid(
                       row={index}, column=0, columnspan=2, sticky=tk.W, padx=5, pady=2)
'''
        return ""

def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description='Python Development Toolkit - CLI workflows, code analysis, and GUI generation',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  %(prog)s --analyze example.py
  %(prog)s --format example.py
  %(prog)s --gui --template default --output app.py
  %(prog)s --diff example.py
  %(prog)s --run script.py --arg "arg1" --arg "arg2"
  %(prog)s --workflows
'''
    )
    
    # Analysis and formatting
    parser.add_argument('--analyze', metavar='FILE', help='Analyze code complexity')
    parser.add_argument('--format', metavar='FILE', help='Format Python code')
    parser.add_argument('--compile-check', metavar='FILE', help='Check if file compiles')
    
    # GUI generation
    parser.add_argument('--gui', action='store_true', help='Generate Tkinter GUI template')
    parser.add_argument('--template', choices=['default', 'minimal', 'advanced'], 
                       default='default', help='GUI template type')
    parser.add_argument('--output', metavar='FILE', help='Output file for generated GUI')
    parser.add_argument('--panels', type=int, default=2, help='Number of panels')
    parser.add_argument('--fields', nargs='+', help='Data field names')
    
    # Diff and snapshot
    parser.add_argument('--diff', metavar='FILE', help='Compare file with snapshot')
    parser.add_argument('--snapshot', metavar='FILE', help='Create snapshot of file')
    parser.add_argument('--snapshot-desc', help='Description for snapshot')
    
    # Execution
    parser.add_argument('--run', metavar='SCRIPT', help='Run Python script')
    parser.add_argument('--arg', action='append', help='Arguments for script execution')
    
    # Information
    parser.add_argument('--workflows', action='store_true', help='Show available workflows')
    parser.add_argument('--variables', action='store_true', help='Show all variables')
    
    # Logging
    parser.add_argument('--log-level', choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
                       default='INFO', help='Set logging level')
    
    args = parser.parse_args()
    
    # Set logging level
    logger.setLevel(getattr(logging, args.log_level))
    
    # Show workflows if requested
    if args.workflows:
        print_workflows()
        return 0
    
    # Show variables if requested
    if args.variables:
        print_variables()
        return 0
    
    # Handle analysis
    if args.analyze:
        analyzer = CodeAnalyzer()
        results = analyzer.analyze_complexity(args.analyze)
        print(f"Complexity analysis for {args.analyze}:")
        for item in results['complexity']:
            print(f"  {item['name']} ({item['type']}): complexity = {item['complexity']}")
        if results['errors']:
            print(f"Errors: {results['errors']}")
    
    # Handle compilation check
    if args.compile_check:
        analyzer = CodeAnalyzer()
        if analyzer.compile_check(args.compile_check):
            print(f"✓ {args.compile_check} compiles successfully")
        else:
            print(f"✗ {args.compile_check} has compilation errors")
    
    # Handle formatting
    if args.format:
        formatter = CodeFormatter()
        with open(args.format, 'r') as f:
            code = f.read()
        
        formatted = formatter.format_with_autopep8(code)
        if formatted != code:
            with open(args.format, 'w') as f:
                f.write(formatted)
            print(f"Formatted {args.format}")
        else:
            print(f"No formatting changes needed for {args.format}")
    
    # Handle GUI generation
    if args.gui:
        config = {
            'title': 'Generated Application',
            'geometry': '1200x800',
            'panels': [{'name': f'Panel {i+1}'} for i in range(args.panels)],
            'data_fields': [{'name': field, 'type': 'entry', 'label': field.replace('_', ' ').title()} 
                          for field in (args.fields or ['name', 'value', 'description'])],
            'notebook_tabs': [
                {'name': 'Editor', 'widgets': [{'type': 'text'}]},
                {'name': 'Console', 'widgets': [{'type': 'text'}]},
                {'name': 'Tools', 'widgets': [{'type': 'button', 'label': 'Run'}]}
            ]
        }
        
        builder = TkinterGUIBuilder()
        template = builder.generate_template(config)
        
        output_file = args.output or 'generated_gui.py'
        with open(output_file, 'w') as f:
            f.write(template)
        
        print(f"GUI template generated: {output_file}")
        print(f"Run with: python {output_file}")
    
    # Handle diff
    if args.diff:
        diff_manager = DiffManager()
        snapshots = list(Path('.snapshots').glob('*.snap'))
        if snapshots:
            latest = max(snapshots, key=lambda p: p.stat().st_mtime)
            diffs = diff_manager.compare_with_snapshot(args.diff, str(latest))
            if diffs:
                print(f"Differences between {args.diff} and snapshot {latest.name}:")
                for line in diffs:
                    if line.startswith('+'):
                        print(f'\033[92m{line}\033[0m')  # Green for additions
                    elif line.startswith('-'):
                        print(f'\033[91m{line}\033[0m')  # Red for deletions
                    else:
                        print(line)
            else:
                print(f"No differences found")
        else:
            print("No snapshots found")
    
    # Handle snapshot
    if args.snapshot:
        diff_manager = DiffManager()
        snapshot_path = diff_manager.create_snapshot(args.snapshot, args.snapshot_desc)
        if snapshot_path:
            print(f"Snapshot created: {snapshot_path}")
    
    # Handle script execution
    if args.run:
        cmd = [sys.executable, args.run]
        if args.arg:
            cmd.extend(args.arg)
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            print(f"Exit code: {result.returncode}")
            if result.stdout:
                print(f"STDOUT:\n{result.stdout}")
            if result.stderr:
                print(f"STDERR:\n{result.stderr}")
        except Exception as e:
            logger.error(f"Failed to run script: {e}")
    
    return 0

def print_workflows():
    """Print available workflows"""
    workflows = {
        'Code Analysis': [
            '--analyze FILE       : Analyze code complexity',
            '--compile-check FILE : Check compilation',
        ],
        'Code Formatting': [
            '--format FILE        : Format Python code',
        ],
        'GUI Generation': [
            '--gui                : Generate Tkinter GUI',
            '--template TYPE      : Template type (default, minimal, advanced)',
            '--output FILE        : Output file',
            '--panels N           : Number of panels',
            '--fields FIELD ...   : Data fields',
        ],
        'Diff & Snapshot': [
            '--diff FILE          : Compare with snapshot',
            '--snapshot FILE      : Create snapshot',
            '--snapshot-desc DESC : Snapshot description',
        ],
        'Execution': [
            '--run SCRIPT         : Run Python script',
            '--arg ARG            : Script argument (can be used multiple times)',
        ],
        'Information': [
            '--workflows          : Show this help',
            '--variables          : Show all variables',
        ]
    }
    
    print("AVAILABLE WORKFLOWS:")
    print("=" * 60)
    for category, items in workflows.items():
        print(f"\n{category}:")
        print("-" * 40)
        for item in items:
            print(f"  {item}")

def print_variables():
    """Print all available variables"""
    variables = {
        'Environment': [
            'PYTHONPATH          : Python module search path',
            'TKINTER_LIBRARY     : Tkinter library path',
        ],
        'Analysis': [
            'RADON_AVAILABLE     : Radon complexity tool available',
            'AUTOPEP8_AVAILABLE  : autopep8 formatter available',
            'BLACK_AVAILABLE     : black formatter available',
        ],
        'Paths': [
            '.snapshots/         : Snapshot storage directory',
            'pydev_toolkit.log   : Log file',
        ],
        'GUI Templates': [
            'default             : Standard template with treeview',
            'minimal             : Minimal template',
            'advanced            : Advanced template with tabs',
        ]
    }
    
    print("AVAILABLE VARIABLES:")
    print("=" * 60)
    for category, items in variables.items():
        print(f"\n{category}:")
        print("-" * 40)
        for item in items:
            print(f"  {item}")

if __name__ == '__main__':
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\nInterrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unhandled exception: {e}")
        traceback.print_exc()
        sys.exit(1)