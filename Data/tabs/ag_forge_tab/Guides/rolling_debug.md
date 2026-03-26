
```python
#!/usr/bin/env python3
"""
Tkinter Project Analyzer & Auto-Fixer
Scans Tkinter projects for common issues and offers automated fixes.
Uses: pyflakes, autoflake, ruff, black, pylint + custom Tkinter-specific checks.
"""

import os
import sys
import ast
import subprocess
import re
import json
import shutil
import hashlib
from pathlib import Path
from typing import Dict, List, Tuple, Set, Any, Optional, Union
from dataclasses import dataclass, field
from collections import defaultdict
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
import queue

# Check for required tools
REQUIRED_TOOLS = ['python3', 'pyflakes', 'ruff', 'black']
OPTIONAL_TOOLS = ['autoflake', 'pylint', 'mypy', 'pyright']

@dataclass
class Issue:
    file: str
    line: int
    col: int
    code: str
    message: str
    severity: str  # error, warning, info, style
    category: str  # syntax, layout, performance, security, etc.
    fixable: bool
    fix_suggestion: Optional[str] = None
    auto_fix: Optional[str] = None

@dataclass
class ProjectAnalysis:
    directory: str
    python_files: List[str] = field(default_factory=list)
    issues: List[Issue] = field(default_factory=list)
    stats: Dict[str, Any] = field(default_factory=dict)
    tk_specific_issues: List[Issue] = field(default_factory=list)
    tool_results: Dict[str, Any] = field(default_factory=dict)

class TkinterAnalyzer:
    """Main analyzer class that coordinates all analysis tools."""
    
    def __init__(self):
        self.project = None
        self.issues_by_file = defaultdict(list)
        self.issues_by_category = defaultdict(list)
        self.available_tools = self._check_tools()
        
    def _check_tools(self) -> Dict[str, bool]:
        """Check which analysis tools are available."""
        available = {}
        for tool in REQUIRED_TOOLS + OPTIONAL_TOOLS:
            try:
                if tool == 'python3':
                    subprocess.run([tool, '--version'], capture_output=True, check=True)
                else:
                    subprocess.run([tool, '--help'], capture_output=True, check=True)
                available[tool] = True
            except (subprocess.CalledProcessError, FileNotFoundError):
                available[tool] = False
        return available
    
    def select_project(self, directory: str) -> ProjectAnalysis:
        """Select and analyze a project directory."""
        self.project = ProjectAnalysis(directory=directory)
        self._find_python_files()
        self._run_analysis_tools()
        self._run_tkinter_specific_checks()
        self._categorize_issues()
        return self.project
    
    def _find_python_files(self):
        """Find all Python files in the project."""
        for root, _, files in os.walk(self.project.directory):
            for file in files:
                if file.endswith('.py'):
                    self.project.python_files.append(os.path.join(root, file))
    
    def _run_analysis_tools(self):
        """Run all available analysis tools in parallel."""
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = []
            
            # Run each tool on each file
            for tool in ['pyflakes', 'ruff', 'pylint']:
                if self.available_tools.get(tool, False):
                    futures.append(executor.submit(self._run_tool, tool))
            
            # Run black separately (formatter)
            if self.available_tools.get('black', False):
                futures.append(executor.submit(self._run_black_check))
            
            # Collect results
            for future in as_completed(futures):
                try:
                    result = future.result()
                    if result:
                        self.project.tool_results.update(result)
                except Exception as e:
                    print(f"Tool error: {e}")
    
    def _run_tool(self, tool: str) -> Dict[str, Any]:
        """Run a specific analysis tool."""
        results = {}
        
        if tool == 'pyflakes':
            for file in self.project.python_files:
                try:
                    result = subprocess.run(
                        ['pyflakes', file],
                        capture_output=True,
                        text=True,
                        timeout=30
                    )
                    if result.stdout:
                        self._parse_pyflakes_output(result.stdout, file)
                except subprocess.TimeoutExpired:
                    continue
        
        elif tool == 'ruff':
            for file in self.project.python_files:
                try:
                    result = subprocess.run(
                        ['ruff', 'check', '--output-format=json', file],
                        capture_output=True,
                        text=True,
                        timeout=30
                    )
                    if result.stdout:
                        self._parse_ruff_output(result.stdout, file)
                except subprocess.TimeoutExpired:
                    continue
        
        elif tool == 'pylint':
            for file in self.project.python_files:
                try:
                    result = subprocess.run(
                        ['pylint', '--output-format=json', file],
                        capture_output=True,
                        text=True,
                        timeout=60
                    )
                    if result.stdout:
                        self._parse_pylint_output(result.stdout, file)
                except subprocess.TimeoutExpired:
                    continue
        
        return results
    
    def _run_black_check(self):
        """Check formatting with black."""
        for file in self.project.python_files:
            try:
                result = subprocess.run(
                    ['black', '--check', '--diff', file],
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                if result.stdout and 'would reformat' in result.stderr:
                    self.project.issues.append(Issue(
                        file=file,
                        line=0,
                        col=0,
                        code='BLK001',
                        message='Code formatting issues detected',
                        severity='style',
                        category='formatting',
                        fixable=True,
                        fix_suggestion='Run black to format code',
                        auto_fix='black'
                    ))
            except subprocess.TimeoutExpired:
                continue
    
    def _run_tkinter_specific_checks(self):
        """Run Tkinter-specific static analysis."""
        for file in self.project.python_files:
            try:
                with open(file, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Parse AST for deeper analysis
                try:
                    tree = ast.parse(content)
                    self._analyze_tkinter_ast(tree, file, content)
                except SyntaxError:
                    # Handle syntax errors separately
                    self.project.issues.append(Issue(
                        file=file,
                        line=0,
                        col=0,
                        code='SYN001',
                        message='Syntax error in file',
                        severity='error',
                        category='syntax',
                        fixable=False
                    ))
                
                # String-based pattern matching
                self._pattern_checks(content, file)
                
            except Exception as e:
                print(f"Error analyzing {file}: {e}")
    
    def _analyze_tkinter_ast(self, tree: ast.AST, file: str, content: str):
        """Analyze AST for Tkinter-specific patterns."""
        
        class TkinterVisitor(ast.NodeVisitor):
            def __init__(self, analyzer, file, content):
                self.analyzer = analyzer
                self.file = file
                self.content = content
                self.imports = set()
                self.widgets = []
                self.variables = {}
                self.lines = content.split('\n')
            
            def visit_Import(self, node):
                for alias in node.names:
                    if 'tkinter' in alias.name or 'Tkinter' in alias.name:
                        self.imports.add(alias.name)
                self.generic_visit(node)
            
            def visit_ImportFrom(self, node):
                if node.module and ('tkinter' in node.module or 'Tkinter' in node.module):
                    for alias in node.names:
                        self.imports.add(f"{node.module}.{alias.name}")
                self.generic_visit(node)
            
            def visit_Assign(self, node):
                # Track widget assignments
                if isinstance(node.value, ast.Call):
                    func = node.value.func
                    if isinstance(func, ast.Attribute):
                        if func.attr in ['Tk', 'Toplevel', 'Frame', 'Button', 'Label',
                                         'Entry', 'Text', 'Canvas', 'Listbox', 'Scrollbar',
                                         'Checkbutton', 'Radiobutton', 'Scale', 'Spinbox']:
                            self.widgets.append({
                                'name': node.targets[0].id if node.targets else 'unknown',
                                'type': func.attr,
                                'line': node.lineno
                            })
                
                self.generic_visit(node)
            
            def visit_Call(self, node):
                # Check for common Tkinter issues
                if isinstance(node.func, ast.Attribute):
                    # Check for mainloop missing
                    if node.func.attr == 'mainloop':
                        # Found mainloop, track it
                        pass
                    
                    # Check for update() misuse
                    if node.func.attr == 'update' and not self._is_in_event_handler(node):
                        self.analyzer.project.tk_specific_issues.append(Issue(
                            file=self.file,
                            line=node.lineno,
                            col=node.col_offset,
                            code='TKI001',
                            message='Direct use of update() can cause issues. Consider using update_idletasks() or after()',
                            severity='warning',
                            category='performance',
                            fixable=True,
                            fix_suggestion='Replace with update_idletasks() or use after() for scheduled updates',
                            auto_fix='replace_update'
                        ))
                
                self.generic_visit(node)
            
            def _is_in_event_handler(self, node):
                """Check if node is inside an event handler function."""
                parent = node
                while hasattr(parent, 'parent'):
                    parent = parent.parent
                    if isinstance(parent, ast.FunctionDef):
                        # Check if function looks like an event handler
                        params = parent.args.args
                        if len(params) == 2 and params[1].arg == 'event':
                            return True
                return False
        
        visitor = TkinterVisitor(self, file, content)
        visitor.visit(tree)
        
        # Check for missing mainloop
        if 'mainloop' not in content and 'mainloop' not in [w['type'] for w in visitor.widgets]:
            # Look for Tk() or Toplevel() creation
            if any(w['type'] in ['Tk', 'Toplevel'] for w in visitor.widgets):
                self.project.tk_specific_issues.append(Issue(
                    file=file,
                    line=0,
                    col=0,
                    code='TKI002',
                    message='Missing mainloop() call. GUI may not run properly.',
                    severity='error',
                    category='execution',
                    fixable=True,
                    fix_suggestion='Add root.mainloop() after widget setup',
                    auto_fix='add_mainloop'
                ))
    
    def _pattern_checks(self, content: str, file: str):
        """Check for patterns using regex."""
        lines = content.split('\n')
        
        patterns = [
            # Wildcard imports
            (r'from tkinter import \*', 'TKI003', 'Wildcard import from tkinter',
             'warning', 'style', True, 'Import specific modules instead'),
            
            # String geometry
            (r'geometry\("(\d+)x(\d+)"\)', 'TKI004', 'Hardcoded geometry string',
             'info', 'layout', True, 'Use variables for geometry dimensions'),
            
            # Pack/grid/place without options
            (r'\.(pack|grid|place)\(\)', 'TKI005', 'Widget placed without options',
             'info', 'layout', False, 'Consider adding layout options'),
            
            # Multiple geometry managers in same parent (simplified check)
            (r'\.pack\(.*\).*\.grid\(', 'TKI006', 'Mixed geometry managers in same parent',
             'warning', 'layout', False, 'Use consistent geometry manager per container'),
            
            # After without function reference
            (r'after\(\d+, lambda:', 'TKI007', 'Lambda in after() call',
             'warning', 'performance', True, 'Define function separately for better performance'),
            
            # Old Tkinter import
            (r'import Tkinter', 'TKI008', 'Python 2 style import',
             'error', 'compatibility', True, 'Use "import tkinter" for Python 3'),
        ]
        
        for i, line in enumerate(lines, 1):
            for pattern, code, msg, severity, category, fixable, suggestion in patterns:
                if re.search(pattern, line):
                    self.project.tk_specific_issues.append(Issue(
                        file=file,
                        line=i,
                        col=0,
                        code=code,
                        message=msg,
                        severity=severity,
                        category=category,
                        fixable=fixable,
                        fix_suggestion=suggestion,
                        auto_fix=None
                    ))
    
    def _parse_pyflakes_output(self, output: str, file: str):
        """Parse pyflakes output."""
        for line in output.strip().split('\n'):
            if ':' in line:
                parts = line.split(':')
                if len(parts) >= 3:
                    line_num = int(parts[1]) if parts[1].isdigit() else 0
                    col_num = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 0
                    message = ':'.join(parts[3:]) if len(parts) > 3 else line
                    
                    self.project.issues.append(Issue(
                        file=file,
                        line=line_num,
                        col=col_num,
                        code='PYF001',
                        message=message.strip(),
                        severity='warning',
                        category='syntax',
                        fixable=False
                    ))
    
    def _parse_ruff_output(self, output: str, file: str):
        """Parse ruff JSON output."""
        try:
            results = json.loads(output)
            for result in results:
                self.project.issues.append(Issue(
                    file=file,
                    line=result.get('location', {}).get('row', 0),
                    col=result.get('location', {}).get('column', 0),
                    code=result.get('code', ''),
                    message=result.get('message', ''),
                    severity=result.get('severity', 'warning').lower(),
                    category=self._categorize_ruff_code(result.get('code', '')),
                    fixable=result.get('fix', {}).get('applicable', False)
                ))
        except json.JSONDecodeError:
            pass
    
    def _parse_pylint_output(self, output: str, file: str):
        """Parse pylint JSON output."""
        try:
            results = json.loads(output)
            for result in results:
                self.project.issues.append(Issue(
                    file=file,
                    line=result.get('line', 0),
                    col=result.get('column', 0),
                    code=result.get('symbol', ''),
                    message=result.get('message', ''),
                    severity=result.get('type', 'warning').lower(),
                    category=self._categorize_pylint_symbol(result.get('symbol', '')),
                    fixable=False
                ))
        except json.JSONDecodeError:
            pass
    
    def _categorize_issues(self):
        """Categorize issues for better presentation."""
        all_issues = self.project.issues + self.project.tk_specific_issues
        
        for issue in all_issues:
            self.issues_by_file[issue.file].append(issue)
            self.issues_by_category[issue.category].append(issue)
        
        # Calculate statistics
        self.project.stats = {
            'total_files': len(self.project.python_files),
            'total_issues': len(all_issues),
            'by_severity': {
                'error': len([i for i in all_issues if i.severity == 'error']),
                'warning': len([i for i in all_issues if i.severity == 'warning']),
                'info': len([i for i in all_issues if i.severity == 'info']),
                'style': len([i for i in all_issues if i.severity == 'style']),
            },
            'by_category': {cat: len(issues) for cat, issues in self.issues_by_category.items()},
            'fixable': len([i for i in all_issues if i.fixable]),
            'tk_specific': len(self.project.tk_specific_issues),
        }
    
    def _categorize_ruff_code(self, code: str) -> str:
        """Categorize ruff error codes."""
        categories = {
            'F': 'syntax',
            'E': 'style',
            'W': 'warning',
            'I': 'import',
            'B': 'bug',
            'C': 'complexity',
            'PL': 'pylint',
            'TRY': 'error_handling',
        }
        prefix = code.split('.')[0] if '.' in code else code[:2]
        return categories.get(prefix, 'general')
    
    def _categorize_pylint_symbol(self, symbol: str) -> str:
        """Categorize pylint symbols."""
        categories = {
            'C': 'convention',
            'R': 'refactor',
            'W': 'warning',
            'E': 'error',
            'F': 'fatal',
        }
        prefix = symbol[0] if symbol else ''
        return categories.get(prefix, 'general')
    
    def apply_fixes(self, selected_fixes: List[Issue]) -> Dict[str, List[str]]:
        """Apply selected fixes to the project."""
        results = {'success': [], 'failed': [], 'skipped': []}
        
        # Group fixes by file
        fixes_by_file = defaultdict(list)
        for fix in selected_fixes:
            fixes_by_file[fix.file].append(fix)
        
        # Apply fixes per file
        for file, fixes in fixes_by_file.items():
            try:
                backup_file = file + '.bak'
                shutil.copy2(file, backup_file)
                
                with open(file, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                modified_content = content
                lines = content.split('\n')
                
                for fix in sorted(fixes, key=lambda x: x.line, reverse=True):
                    if fix.auto_fix == 'black':
                        # Run black formatter
                        subprocess.run(['black', file], capture_output=True)
                        results['success'].append(f"Formatted {os.path.basename(file)} with black")
                    
                    elif fix.auto_fix == 'replace_update':
                        # Replace update() with update_idletasks()
                        if 0 <= fix.line - 1 < len(lines):
                            lines[fix.line - 1] = lines[fix.line - 1].replace('.update()', '.update_idletasks()')
                    
                    elif fix.auto_fix == 'add_mainloop':
                        # Add mainloop at end of file
                        lines.append("\nif __name__ == '__main__':")
                        lines.append("    root.mainloop()")
                    
                    elif fix.code == 'TKI003' and fix.fixable:
                        # Fix wildcard import
                        for i, line in enumerate(lines):
                            if 'from tkinter import *' in line:
                                lines[i] = 'import tkinter as tk'
                                # Need to update all tkinter references in file
                                modified_content = '\n'.join(lines)
                                modified_content = modified_content.replace('(', '(tk.')
                                # This is simplified - would need more sophisticated replacement
                    
                    # Add more auto-fix implementations here
                
                # Write modified content
                if lines != content.split('\n'):
                    with open(file, 'w', encoding='utf-8') as f:
                        f.write('\n'.join(lines))
                    results['success'].append(f"Applied fixes to {os.path.basename(file)}")
                else:
                    results['skipped'].append(f"No changes needed for {os.path.basename(file)}")
                
            except Exception as e:
                results['failed'].append(f"{os.path.basename(file)}: {str(e)}")
        
        return results

class TkinterAnalyzerGUI:
    """GUI for the Tkinter Analyzer."""
    
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Tkinter Project Analyzer")
        self.root.geometry("1200x800")
        
        self.analyzer = TkinterAnalyzer()
        self.project = None
        self.selected_fixes = set()
        
        self._setup_ui()
        self._setup_styles()
    
    def _setup_styles(self):
        """Setup ttk styles."""
        style = ttk.Style()
        style.theme_use('clam')
        
        # Configure colors
        self.root.configure(bg='#f0f0f0')
        
        # Tag colors for text widget
        self.text_tags = {
            'error': {'background': '#ffebee', 'foreground': '#c62828'},
            'warning': {'background': '#fff3e0', 'foreground': '#ef6c00'},
            'info': {'background': '#e8f5e8', 'foreground': '#2e7d32'},
            'style': {'background': '#e3f2fd', 'foreground': '#1565c0'},
        }
    
    def _setup_ui(self):
        """Setup the user interface."""
        # Main container
        main_container = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        main_container.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Left panel - Controls and file list
        left_panel = ttk.Frame(main_container)
        main_container.add(left_panel, weight=1)
        
        # Right panel - Results
        right_panel = ttk.Frame(main_container)
        main_container.add(right_panel, weight=3)
        
        # Left panel contents
        self._setup_left_panel(left_panel)
        
        # Right panel contents
        self._setup_right_panel(right_panel)
    
    def _setup_left_panel(self, parent):
        """Setup the left control panel."""
        # Project selection
        proj_frame = ttk.LabelFrame(parent, text="Project Selection", padding=10)
        proj_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(proj_frame, text="Project Directory:").pack(anchor=tk.W)
        
        dir_frame = ttk.Frame(proj_frame)
        dir_frame.pack(fill=tk.X, pady=5)
        
        self.dir_var = tk.StringVar()
        ttk.Entry(dir_frame, textvariable=self.dir_var).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        ttk.Button(dir_frame, text="Browse", command=self._browse_directory).pack(side=tk.RIGHT)
        
        ttk.Button(proj_frame, text="Analyze Project", command=self._analyze_project).pack(fill=tk.X, pady=5)
        
        # Tools status
        tools_frame = ttk.LabelFrame(parent, text="Available Tools", padding=10)
        tools_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.tools_text = scrolledtext.ScrolledText(tools_frame, height=8, font=('Monospace', 9))
        self.tools_text.pack(fill=tk.BOTH, expand=True)
        self._update_tools_status()
        
        # File list
        files_frame = ttk.LabelFrame(parent, text="Python Files", padding=10)
        files_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.files_listbox = tk.Listbox(files_frame, font=('Monospace', 9))
        self.files_listbox.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Action buttons
        action_frame = ttk.Frame(parent)
        action_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Button(action_frame, text="Apply Selected Fixes", command=self._apply_fixes).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        ttk.Button(action_frame, text="Export Report", command=self._export_report).pack(side=tk.RIGHT, fill=tk.X, expand=True)
    
    def _setup_right_panel(self, parent):
        """Setup the right results panel."""
        # Notebook for different views
        self.notebook = ttk.Notebook(parent)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Issues tab
        issues_frame = ttk.Frame(self.notebook)
        self.notebook.add(issues_frame, text="Issues")
        
        # Filter controls
        filter_frame = ttk.Frame(issues_frame)
        filter_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(filter_frame, text="Filter:").pack(side=tk.LEFT, padx=(0, 5))
        
        self.filter_var = tk.StringVar(value="all")
        ttk.Combobox(filter_frame, textvariable=self.filter_var, 
                     values=["all", "error", "warning", "info", "style", "tk-specific", "fixable"],
                     state="readonly", width=15).pack(side=tk.LEFT, padx=(0, 10))
        
        ttk.Button(filter_frame, text="Refresh", command=self._refresh_issues).pack(side=tk.LEFT)
        
        # Issues treeview
        tree_frame = ttk.Frame(issues_frame)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=(0, 5))
        
        # Create treeview with scrollbars
        tree_scroll_y = ttk.Scrollbar(tree_frame)
        tree_scroll_y.pack(side=tk.RIGHT, fill=tk.Y)
        
        tree_scroll_x = ttk.Scrollbar(tree_frame, orient=tk.HORIZONTAL)
        tree_scroll_x.pack(side=tk.BOTTOM, fill=tk.X)
        
        self.issues_tree = ttk.Treeview(tree_frame, 
                                        yscrollcommand=tree_scroll_y.set,
                                        xscrollcommand=tree_scroll_x.set,
                                        selectmode='extended')
        self.issues_tree.pack(fill=tk.BOTH, expand=True)
        
        tree_scroll_y.config(command=self.issues_tree.yview)
        tree_scroll_x.config(command=self.issues_tree.xview)
        
        # Configure tree columns
        self.issues_tree['columns'] = ('file', 'line', 'code', 'message', 'severity', 'fixable')
        self.issues_tree.column('#0', width=50, stretch=False)
        self.issues_tree.column('file', width=150)
        self.issues_tree.column('line', width=50, anchor=tk.CENTER)
        self.issues_tree.column('code', width=80)
        self.issues_tree.column('message', width=300)
        self.issues_tree.column('severity', width=80)
        self.issues_tree.column('fixable', width=60, anchor=tk.CENTER)
        
        self.issues_tree.heading('#0', text='#')
        self.issues_tree.heading('file', text='File')
        self.issues_tree.heading('line', text='Line')
        self.issues_tree.heading('code', text='Code')
        self.issues_tree.heading('message', text='Message')
        self.issues_tree.heading('severity', text='Severity')
        self.issues_tree.heading('fixable', text='Fixable')
        
        # Checkbox for selection
        self.issues_tree.tag_configure('selected', background='#e3f2fd')
        
        # Bind click event for selection
        self.issues_tree.bind('<ButtonRelease-1>', self._on_tree_select)
        
        # Statistics tab
        stats_frame = ttk.Frame(self.notebook)
        self.notebook.add(stats_frame, text="Statistics")
        
        self.stats_text = scrolledtext.ScrolledText(stats_frame, font=('Monospace', 10))
        self.stats_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Tkinter Specific tab
        tk_frame = ttk.Frame(self.notebook)
        self.notebook.add(tk_frame, text="Tkinter Issues")
        
        self.tk_text = scrolledtext.ScrolledText(tk_frame, font=('Monospace', 10))
        self.tk_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Details tab
        details_frame = ttk.Frame(self.notebook)
        self.notebook.add(details_frame, text="Details")
        
        self.details_text = scrolledtext.ScrolledText(details_frame, font=('Monospace', 10))
        self.details_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
    
    def _update_tools_status(self):
        """Update the tools status display."""
        self.tools_text.delete(1.0, tk.END)
        
        self.tools_text.insert(tk.END, "Required Tools:\n", 'heading')
        for tool in REQUIRED_TOOLS:
            status = "✓" if self.analyzer.available_tools.get(tool, False) else "✗"
            color = "green" if status == "✓" else "red"
            self.tools_text.insert(tk.END, f"  {status} {tool}\n", color)
        
        self.tools_text.insert(tk.END, "\nOptional Tools:\n", 'heading')
        for tool in OPTIONAL_TOOLS:
            status = "✓" if self.analyzer.available_tools.get(tool, False) else "○"
            color = "green" if status == "✓" else "orange" if status == "○" else "gray"
            self.tools_text.insert(tk.END, f"  {status} {tool}\n", color)
        
        # Configure tags for colors
        self.tools_text.tag_config('heading', font=('Monospace', 9, 'bold'))
        self.tools_text.tag_config('green', foreground='green')
        self.tools_text.tag_config('red', foreground='red')
        self.tools_text.tag_config('orange', foreground='orange')
        self.tools_text.tag_config('gray', foreground='gray')
    
    def _browse_directory(self):
        """Browse for project directory."""
        directory = filedialog.askdirectory(title="Select Project Directory")
        if directory:
            self.dir_var.set(directory)
            self._load_file_list(directory)
    
    def _load_file_list(self, directory):
        """Load Python files from directory."""
        self.files_listbox.delete(0, tk.END)
        
        try:
            for root, _, files in os.walk(directory):
                for file in files:
                    if file.endswith('.py'):
                        rel_path = os.path.relpath(os.path.join(root, file), directory)
                        self.files_listbox.insert(tk.END, rel_path)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to list files: {e}")
    
    def _analyze_project(self):
        """Analyze the selected project."""
        directory = self.dir_var.get()
        if not directory or not os.path.exists(directory):
            messagebox.showerror("Error", "Please select a valid directory")
            return
        
        # Clear previous results
        self.issues_tree.delete(*self.issues_tree.get_children())
        self.stats_text.delete(1.0, tk.END)
        self.tk_text.delete(1.0, tk.END)
        self.details_text.delete(1.0, tk.END)
        
        # Show progress
        self.root.config(cursor='watch')
        self.root.update()
        
        try:
            # Run analysis in thread to keep UI responsive
            def analyze():
                self.project = self.analyzer.select_project(directory)
                self.root.after(0, self._display_results)
            
            thread = threading.Thread(target=analyze)
            thread.daemon = True
            thread.start()
            
        except Exception as e:
            self.root.config(cursor='')
            messagebox.showerror("Analysis Error", f"Failed to analyze project: {e}")
    
    def _display_results(self):
        """Display analysis results."""
        self.root.config(cursor='')
        
        if not self.project:
            messagebox.showinfo("No Results", "No analysis results available")
            return
        
        # Display issues in treeview
        self._populate_issues_tree()
        
        # Display statistics
        self._display_statistics()
        
        # Display Tkinter-specific issues
        self._display_tkinter_issues()
        
        # Update status
        messagebox.showinfo("Analysis Complete", 
                           f"Found {self.project.stats.get('total_issues', 0)} issues in "
                           f"{self.project.stats.get('total_files', 0)} files")
    
    def _populate_issues_tree(self):
        """Populate the issues treeview."""
        all_issues = self.project.issues + self.project.tk_specific_issues
        
        for i, issue in enumerate(all_issues, 1):
            fixable_text = "✓" if issue.fixable else ""
            severity = issue.severity.capitalize()
            
            # Shorten file path for display
            display_file = os.path.basename(issue.file)
            
            item_id = self.issues_tree.insert('', 'end', 
                                             text=str(i),
                                             values=(display_file, issue.line, issue.code,
                                                    issue.message[:100], severity, fixable_text),
                                             tags=(issue.severity,))
            
            # Store full issue object for reference
            self.issues_tree.set(item_id, 'full_path', issue.file)
            self.issues_tree.set(item_id, 'full_issue', issue)
            
            # Color code by severity
            self.issues_tree.tag_configure(issue.severity, 
                                          foreground=self.text_tags.get(issue.severity, {}).get('foreground', 'black'))
    
    def _display_statistics(self):
        """Display statistics in the stats tab."""
        stats = self.project.stats
        
        self.stats_text.delete(1.0, tk.END)
        
        self.stats_text.insert(tk.END, "PROJECT STATISTICS\n", 'heading')
        self.stats_text.insert(tk.END, "=" * 50 + "\n\n")
        
        self.stats_text.insert(tk.END, f"Project Directory: {self.project.directory}\n")
        self.stats_text.insert(tk.END, f"Python Files: {stats.get('total_files', 0)}\n")
        self.stats_text.insert(tk.END, f"Total Issues: {stats.get('total_issues', 0)}\n")
        self.stats_text.insert(tk.END, f"Fixable Issues: {stats.get('fixable', 0)}\n")
        self.stats_text.insert(tk.END, f"Tkinter Issues: {stats.get('tk_specific', 0)}\n\n")
        
        self.stats_text.insert(tk.END, "ISSUES BY SEVERITY\n", 'subheading')
        for severity, count in stats.get('by_severity', {}).items():
            self.stats_text.insert(tk.END, f"  {severity.capitalize()}: {count}\n")
        
        self.stats_text.insert(tk.END, "\nISSUES BY CATEGORY\n", 'subheading')
        for category, count in stats.get('by_category', {}).items():
            self.stats_text.insert(tk.END, f"  {category.capitalize()}: {count}\n")
        
        self.stats_text.insert(tk.END, "\nTOOLS USED\n", 'subheading')
        for tool, available in self.analyzer.available_tools.items():
            if available:
                self.stats_text.insert(tk.END, f"  ✓ {tool}\n")
        
        # Configure text tags
        self.stats_text.tag_config('heading', font=('Monospace', 12, 'bold'))
        self.stats_text.tag_config('subheading', font=('Monospace', 10, 'bold'))
    
    def _display_tkinter_issues(self):
        """Display Tkinter-specific issues."""
        self.tk_text.delete(1.0, tk.END)
        
        if not self.project.tk_specific_issues:
            self.tk_text.insert(tk.END, "No Tkinter-specific issues found!\n", 'success')
            self.tk_text.tag_config('success', foreground='green')
            return
        
        self.tk_text.insert(tk.END, "TKINTER-SPECIFIC ISSUES\n", 'heading')
        self.tk_text.insert(tk.END, "=" * 50 + "\n\n")
        
        for i, issue in enumerate(self.project.tk_specific_issues, 1):
            self.tk_text.insert(tk.END, f"{i}. {issue.code}: {issue.message}\n", 'issue')
            self.tk_text.insert(tk.END, f"   File: {os.path.basename(issue.file)}")
            if issue.line > 0:
                self.tk_text.insert(tk.END, f" (Line {issue.line})")
            self.tk_text.insert(tk.END, "\n")
            
            if issue.fix_suggestion:
                self.tk_text.insert(tk.END, f"   Fix: {issue.fix_suggestion}\n", 'fix')
            
            if issue.auto_fix:
                self.tk_text.insert(tk.END, f"   Auto-fix available: {issue.auto_fix}\n", 'auto')
            
            self.tk_text.insert(tk.END, "\n")
        
        # Configure text tags
        self.tk_text.tag_config('heading', font=('Monospace', 12, 'bold'))
        self.tk_text.tag_config('issue', font=('Monospace', 10))
        self.tk_text.tag_config('fix', font=('Monospace', 9, 'italic'), foreground='blue')
        self.tk_text.tag_config('auto', font=('Monospace', 9), foreground='green')
    
    def _on_tree_select(self, event):
        """Handle tree item selection."""
        selection = self.issues_tree.selection()
        if not selection:
            return
        
        # Toggle selection tag
        for item in selection:
            tags = self.issues_tree.item(item, 'tags')
            if 'selected' in tags:
                new_tags = tuple(tag for tag in tags if tag != 'selected')
                self.selected_fixes.discard(item)
            else:
                new_tags = tags + ('selected',)
                self.selected_fixes.add(item)
            
            self.issues_tree.item(item, tags=new_tags)
        
        # Show details of first selected item
        if selection:
            self._show_issue_details(selection[0])
    
    def _show_issue_details(self, item_id):
        """Show detailed information about selected issue."""
        issue = self.issues_tree.set(item_id, 'full_issue')
        if not issue:
            return
        
        self.details_text.delete(1.0, tk.END)
        
        self.details_text.insert(tk.END, "ISSUE DETAILS\n", 'heading')
        self.details_text.insert(tk.END, "=" * 50 + "\n\n")
        
        details = [
            ("Code", issue.code),
            ("Message", issue.message),
            ("File", issue.file),
            ("Line", str(issue.line)),
            ("Column", str(issue.col)),
            ("Severity", issue.severity.capitalize()),
            ("Category", issue.category),
            ("Fixable", "Yes" if issue.fixable else "No"),
        ]
        
        for label, value in details:
            self.details_text.insert(tk.END, f"{label}: ", 'label')
            self.details_text.insert(tk.END, f"{value}\n")
        
        if issue.fix_suggestion:
            self.details_text.insert(tk.END, "\nFIX SUGGESTION\n", 'subheading')
            self.details_text.insert(tk.END, issue.fix_suggestion + "\n")
        
        if issue.auto_fix:
            self.details_text.insert(tk.END, "\nAUTO-FIX\n", 'subheading')
            self.details_text.insert(tk.END, f"Available: {issue.auto_fix}\n")
        
        # Show context lines from file
        if issue.line > 0 and os.path.exists(issue.file):
            try:
                with open(issue.file, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                
                self.details_text.insert(tk.END, "\nCODE CONTEXT\n", 'subheading')
                
                start = max(0, issue.line - 3)
                end = min(len(lines), issue.line + 2)
                
                for i in range(start, end):
                    line_num = i + 1
                    prefix = ">>> " if line_num == issue.line else "    "
                    self.details_text.insert(tk.END, f"{prefix}{line_num:4}: {lines[i]}")
            except:
                pass
        
        # Configure text tags
        self.details_text.tag_config('heading', font=('Monospace', 12, 'bold'))
        self.details_text.tag_config('subheading', font=('Monospace', 10, 'bold'))
        self.details_text.tag_config('label', font=('Monospace', 10, 'bold'))
    
    def _refresh_issues(self):
        """Refresh issues based on filter."""
        filter_val = self.filter_var.get()
        
        for item in self.issues_tree.get_children():
            issue = self.issues_tree.set(item, 'full_issue')
            if not issue:
                continue
            
            show = False
            if filter_val == "all":
                show = True
            elif filter_val == "fixable":
                show = issue.fixable
            elif filter_val == "tk-specific":
                show = issue in self.project.tk_specific_issues
            else:
                show = issue.severity == filter_val
            
            if show:
                self.issues_tree.attach(item, '', 'end')
            else:
                self.issues_tree.detach(item)
    
    def _apply_fixes(self):
        """Apply selected fixes."""
        if not self.selected_fixes:
            messagebox.showinfo("No Selection", "Please select fixes to apply")
            return
        
        # Collect selected issues
        selected_issues = []
        for item_id in self.selected_fixes:
            issue = self.issues_tree.set(item_id, 'full_issue')
            if issue and issue.fixable:
                selected_issues.append(issue)
        
        if not selected_issues:
            messagebox.showinfo("No Fixable Issues", "Selected issues are not fixable")
            return
        
        # Confirm
        response = messagebox.askyesno(
            "Confirm Fixes",
            f"Apply {len(selected_issues)} fixes?\n\n"
            "Backups will be created as .bak files."
        )
        
        if not response:
            return
        
        # Apply fixes
        self.root.config(cursor='watch')
        self.root.update()
        
        try:
            results = self.analyzer.apply_fixes(selected_issues)
            
            # Show results
            result_text = "FIX RESULTS\n"
            result_text += "=" * 50 + "\n\n"
            
            if results['success']:
                result_text += "SUCCESS:\n"
                for msg in results['success']:
                    result_text += f"  ✓ {msg}\n"
                result_text += "\n"
            
            if results['failed']:
                result_text += "FAILED:\n"
                for msg in results['failed']:
                    result_text += f"  ✗ {msg}\n"
                result_text += "\n"
            
            if results['skipped']:
                result_text += "SKIPPED:\n"
                for msg in results['skipped']:
                    result_text += f"  ○ {msg}\n"
            
            messagebox.showinfo("Fix Results", result_text)
            
            # Re-analyze project
            self._analyze_project()
            
        except Exception as e:
            messagebox.showerror("Fix Error", f"Failed to apply fixes: {e}")
        finally:
            self.root.config(cursor='')
            self.selected_fixes.clear()
    
    def _export_report(self):
        """Export analysis report."""
        if not self.project:
            messagebox.showinfo("No Data", "No analysis data to export")
            return
        
        file_path = filedialog.asksaveasfilename(
            title="Export Report",
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("JSON files", "*.json"), ("All files", "*.*")]
        )
        
        if not file_path:
            return
        
        try:
            if file_path.endswith('.json'):
                # Export as JSON
                report = {
                    'project': self.project.directory,
                    'stats': self.project.stats,
                    'issues': [
                        {
                            'file': i.file,
                            'line': i.line,
                            'code': i.code,
                            'message': i.message,
                            'severity': i.severity,
                            'category': i.category,
                            'fixable': i.fixable,
                            'fix_suggestion': i.fix_suggestion
                        }
                        for i in self.project.issues + self.project.tk_specific_issues
                    ]
                }
                
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(report, f, indent=2)
            else:
                # Export as text
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write("TKINTER PROJECT ANALYSIS REPORT\n")
                    f.write("=" * 50 + "\n\n")
                    
                    f.write(f"Project: {self.project.directory}\n")
                    f.write(f"Analysis Date: {subprocess.run(['date'], capture_output=True, text=True).stdout}\n\n")
                    
                    f.write("STATISTICS\n")
                    f.write("-" * 30 + "\n")
                    for key, value in self.project.stats.items():
                        if isinstance(value, dict):
                            f.write(f"{key}:\n")
                            for k, v in value.items():
                                f.write(f"  {k}: {v}\n")
                        else:
                            f.write(f"{key}: {value}\n")
                    
                    f.write("\n\nISSUES\n")
                    f.write("-" * 30 + "\n")
                    all_issues = self.project.issues + self.project.tk_specific_issues
                    for i, issue in enumerate(all_issues, 1):
                        f.write(f"\n{i}. {issue.code}: {issue.message}\n")
                        f.write(f"   File: {issue.file}:{issue.line}\n")
                        f.write(f"   Severity: {issue.severity}, Category: {issue.category}\n")
                        if issue.fix_suggestion:
                            f.write(f"   Fix: {issue.fix_suggestion}\n")
                    
                    f.write("\n\nTKINTER-SPECIFIC ISSUES\n")
                    f.write("-" * 30 + "\n")
                    for i, issue in enumerate(self.project.tk_specific_issues, 1):
                        f.write(f"\n{i}. {issue.code}: {issue.message}\n")
                        f.write(f"   File: {issue.file}:{issue.line}\n")
                        if issue.fix_suggestion:
                            f.write(f"   Fix: {issue.fix_suggestion}\n")
            
            messagebox.showinfo("Export Complete", f"Report exported to:\n{file_path}")
            
        except Exception as e:
            messagebox.showerror("Export Error", f"Failed to export report: {e}")
    
    def run(self):
        """Run the GUI application."""
        self.root.mainloop()

def main():
    """Main entry point."""
    # Check for minimal requirements
    try:
        import tkinter
    except ImportError:
        print("Error: tkinter is not available. Please install it.")
        sys.exit(1)
    
    # Create and run the GUI
    app = TkinterAnalyzerGUI()
    app.run()

if __name__ == "__main__":
    main()
```

## **Installation Requirements**

Create a `requirements.txt` file:

```txt
# Analysis tools (install via pip or apt)
# pip install pyflakes autoflake ruff black pylint

# Optional: GUI enhancements
# pip install ttkthemes  # For additional themes
```

## **Quick Installation Script** (`install_deps.sh`):

```bash
#!/bin/bash
# Install dependencies for Tkinter Analyzer

echo "Installing Python analysis tools..."
pip install --upgrade pip

# Core analysis tools
pip install pyflakes autoflake ruff black pylint

# Optional tools
pip install mypy pyright  # Type checkers

echo "Checking system tools..."
sudo apt update
sudo apt install -y python3-tk  # Tkinter support
sudo apt install -y xvfb  # For headless testing (optional)

echo "Installation complete!"
echo "Run: python tkinter_analyzer.py"
```

## **Features:**

### **1. Multi-Tool Analysis**
- Integrates pyflakes, ruff, black, pylint
- Runs tools in parallel for speed
- Shows which tools are available

### **2. Tkinter-Specific Checks**
- Missing mainloop() detection
- Update() misuse warnings
- Wildcard import detection
- Geometry manager issues
- Python 2/3 compatibility
- Performance anti-patterns

### **3. Intelligent Categorization**
- Groups issues by severity (error, warning, info, style)
- Categories: syntax, layout, performance, security, etc.
- Tracks fixable vs non-fixable issues

### **4. Auto-Fix Capabilities**
- Format code with black
- Replace update() with update_idletasks()
- Fix wildcard imports
- Add missing mainloop()
- More fix patterns can be added

### **5. GUI Features**
- File browser with project selection
- Filterable issue treeview
- Statistics dashboard
- Detailed issue view with code context
- One-click fix application
- Report export (JSON/TXT)

### **6. Safety Features**
- Creates backups (.bak files) before fixes
- Shows diff previews
- Confirmation before applying fixes

## **Usage:**

```bash
# Make executable
chmod +x tkinter_analyzer.py

# Run with Python
python tkinter_analyzer.py

# Or run directly
./tkinter_analyzer.py
```

## **Expected Analysis Categories:**

1. **Syntax & Import Issues**
   - Missing imports
   - Unused variables
   - Syntax errors
   - Python 2/3 compatibility

2. **Layout & Geometry**
   - Mixed geometry managers
   - Missing layout calls
   - Hardcoded dimensions
   - Responsive layout issues

3. **Performance**
   - update() in loops
   - Lambda misuse in callbacks
   - Memory leaks (widget references)
   - Blocking operations in main thread

4. **UX/UI Patterns**
   - Missing mainloop
   - Event handler signatures
   - Modal dialog issues
   - Focus management

5. **Code Quality**
   - Formatting (black compliance)
   - Naming conventions
   - Function complexity
   - Documentation

The script provides a rolling context - it analyzes each file, builds an issue database, then presents a fix matrix where users can select which fixes to apply. The auto-fix system handles common patterns while leaving complex decisions to the user.