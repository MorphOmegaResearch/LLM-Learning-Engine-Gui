#!/usr/bin/env python3
"""
TUI to GUI Translator
Discovers TUI applications and creates Tkinter wrapper GUIs for them.
"""

import sys
import re
import subprocess
import argparse
import json
import shutil
import ast
import hashlib
from pathlib import Path
from datetime import datetime
from typing import Dict, List
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import threading

# Debug/analysis imports
try:
    import py_compile
    PY_COMPILE_AVAILABLE = True
except ImportError:
    PY_COMPILE_AVAILABLE = False

try:
    import black
    BLACK_AVAILABLE = True
except ImportError:
    BLACK_AVAILABLE = False

try:
    import pyflakes.api
    import pyflakes.reporter
    PYFLAKES_AVAILABLE = True
except ImportError:
    PYFLAKES_AVAILABLE = False

try:
    import ruff
    RUFF_AVAILABLE = True
except ImportError:
    RUFF_AVAILABLE = False


class TUIAnalyzer:
    """Analyze Python files to identify TUI applications."""
    
    TUI_INDICATORS = [
        'curses', 'npyscreen', 'urwid', 'prompt_toolkit', 'textual', 'asciimatics',
        'blessed', 'pick', 'simple_term_menu', 'pick', 'PyInquirer', 'questionary',
        'cmd', 'cmd2', 'argparse', 'click', 'sys.argv', 'input(', 'print(',
        'getch', 'keyboard', 'readchar', 'terminal_menu', 'tqdm', 'rich.console'
    ]
    
    GUI_INDICATORS = [
        'tkinter', 'PyQt', 'PySide', 'wx', 'kivy', 'dearpygui', 'pygame',
        'remi', 'flask', 'dash', 'streamlit', 'gradio', 'fastapi', 'bokeh'
    ]
    
    def __init__(self, base_dir: str):
        self.base_dir = Path(base_dir).resolve()
        self.discoveries_dir = self.base_dir / 'discoveries'
        self.tui_apps_dir = self.discoveries_dir / 'tui_apps'
        self.manifest_file = self.discoveries_dir / 'manifest.json'
        self.wrappers_dir = self.discoveries_dir / 'wrappers'
        
        # Create directories
        self.discoveries_dir.mkdir(exist_ok=True)
        self.tui_apps_dir.mkdir(exist_ok=True)
        self.wrappers_dir.mkdir(exist_ok=True)
        
        self.discovered_apps = []
        self.manifest = self._load_manifest()
        
    def _load_manifest(self) -> Dict:
        """Load existing manifest or create new one."""
        if self.manifest_file.exists():
            try:
                with open(self.manifest_file, 'r') as f:
                    return json.load(f)
            except json.JSONDecodeError:
                return {}
        return {
            "created": datetime.now().isoformat(),
            "base_dir": str(self.base_dir),
            "discoveries": [],
            "wrappers": [],
            "analyses": {}
        }
    
    def _save_manifest(self):
        """Save manifest to file."""
        with open(self.manifest_file, 'w') as f:
            json.dump(self.manifest, f, indent=2)
    
    def discover_tui_apps(self) -> List[Dict]:
        """Discover potential TUI applications in base directory."""
        print(f"Discovering TUI apps in {self.base_dir}...")
        
        discovered = []
        for py_file in self.base_dir.rglob("*.py"):
            # Skip files in discoveries directory
            if self.discoveries_dir in py_file.parents:
                continue
            
            try:
                with open(py_file, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                
                # Check for TUI indicators
                tui_score = 0
                gui_score = 0
                
                for indicator in self.TUI_INDICATORS:
                    if indicator in content:
                        tui_score += 1
                
                for indicator in self.GUI_INDICATORS:
                    if indicator in content:
                        gui_score += 1
                
                # Check for shebang and executable
                is_executable = False
                if content.startswith('#!'):
                    is_executable = True
                    tui_score += 2  # Bonus for being executable
                
                # Check for main guard
                if 'if __name__ == "__main__"' in content:
                    tui_score += 1
                
                # Check for command line arguments
                if any(cmd in content for cmd in ['sys.argv', 'argparse', 'click']):
                    tui_score += 1
                
                # Calculate probability
                total_indicators = tui_score + gui_score
                tui_probability = tui_score / max(total_indicators, 1)
                
                # Consider it a TUI app if probability > 0.3 and not primarily GUI
                if tui_probability > 0.3 and gui_score < 3:
                    app_info = {
                        "path": str(py_file),
                        "name": py_file.stem,
                        "tui_score": tui_score,
                        "gui_score": gui_score,
                        "probability": tui_probability,
                        "is_executable": is_executable,
                        "size": py_file.stat().st_size,
                        "modified": py_file.stat().st_mtime,
                        "imports": self._extract_imports(content),
                        "hash": self._file_hash(py_file)
                    }
                    discovered.append(app_info)
                    
                    # Copy to discoveries directory
                    dest = self.tui_apps_dir / py_file.name
                    if not dest.exists():
                        shutil.copy2(py_file, dest)
                    
            except Exception as e:
                print(f"Error analyzing {py_file}: {e}")
        
        self.discovered_apps = sorted(discovered, key=lambda x: x['probability'], reverse=True)
        
        # Update manifest
        self.manifest["discoveries"] = self.discovered_apps
        self.manifest["last_discovery"] = datetime.now().isoformat()
        self._save_manifest()
        
        print(f"Discovered {len(self.discovered_apps)} potential TUI applications")
        return self.discovered_apps
    
    def _extract_imports(self, content: str) -> List[str]:
        """Extract import statements from Python code."""
        imports = set()
        
        # Simple regex-based import extraction
        import_patterns = [
            r'^import\s+([\w\.]+)',
            r'^from\s+([\w\.]+)\s+import',
            r'^\s+import\s+([\w\.]+)',
            r'^\s+from\s+([\w\.]+)\s+import'
        ]
        
        for line in content.split('\n'):
            for pattern in import_patterns:
                match = re.search(pattern, line)
                if match:
                    imports.add(match.group(1).split('.')[0])  # Get root module
        
        return list(imports)
    
    def _file_hash(self, filepath: Path) -> str:
        """Calculate file hash."""
        hasher = hashlib.md5()
        with open(filepath, 'rb') as f:
            hasher.update(f.read())
        return hasher.hexdigest()
    
    def analyze_app(self, app_info: Dict) -> Dict:
        """Perform detailed analysis on a TUI app."""
        app_path = Path(app_info['path'])
        
        analysis = {
            "app_name": app_info['name'],
            "analysis_time": datetime.now().isoformat(),
            "syntax_check": self._check_syntax(app_path),
            "linting": self._run_linting(app_path),
            "import_chain": self._analyze_import_chain(app_path),
            "risk_factors": [],
            "integration_points": []
        }
        
        # Identify risk factors
        with open(app_path, 'r') as f:
            content = f.read()
        
        risk_factors = []
        if 'os.system' in content or 'subprocess' in content:
            risk_factors.append("Uses system calls")
        if 'eval(' in content or 'exec(' in content:
            risk_factors.append("Uses eval/exec")
        if '__import__' in content:
            risk_factors.append("Uses dynamic imports")
        
        # Find integration points (input/output locations)
        integration_points = []
        lines = content.split('\n')
        for i, line in enumerate(lines):
            if 'input(' in line:
                integration_points.append(f"Line {i+1}: User input")
            elif 'print(' in line:
                integration_points.append(f"Line {i+1}: Output")
            elif 'sys.stdout' in line:
                integration_points.append(f"Line {i+1}: Stdout redirection")
        
        analysis["risk_factors"] = risk_factors
        analysis["integration_points"] = integration_points
        
        # Calculate risk score (0-100, higher = riskier)
        risk_score = len(risk_factors) * 10
        if 'curses' in content:
            risk_score += 20  # Curses is complex to wrap
        
        # Calculate wrapping score (0-100, higher = easier to wrap)
        wrapping_score = 100 - risk_score
        if len(integration_points) > 0:
            wrapping_score = min(90, wrapping_score + 10)  # Input/output points make wrapping easier
        
        analysis["risk_score"] = max(0, min(100, risk_score))
        analysis["wrapping_score"] = max(0, min(100, wrapping_score))
        
        # Update manifest with analysis
        if "analyses" not in self.manifest:
            self.manifest["analyses"] = {}
        self.manifest["analyses"][app_info['name']] = analysis
        self._save_manifest()
        
        return analysis
    
    def _check_syntax(self, filepath: Path) -> Dict:
        """Check Python syntax using py_compile."""
        result = {"valid": False, "error": None}
        
        if not PY_COMPILE_AVAILABLE:
            result["error"] = "py_compile not available"
            return result
        
        try:
            py_compile.compile(str(filepath), doraise=True)
            result["valid"] = True
        except py_compile.PyCompileError as e:
            result["error"] = str(e)
        except Exception as e:
            result["error"] = str(e)
        
        return result
    
    def _run_linting(self, filepath: Path) -> Dict:
        """Run various linters on the file."""
        lint_results = {}
        
        # Try ruff
        if RUFF_AVAILABLE:
            try:
                # This is simplified - in reality would use ruff's API
                result = subprocess.run(
                    ['ruff', 'check', str(filepath)],
                    capture_output=True,
                    text=True
                )
                lint_results["ruff"] = {
                    "output": result.stdout + result.stderr,
                    "success": result.returncode == 0
                }
            except Exception as e:
                lint_results["ruff"] = {"error": str(e)}
        
        # Try pyflakes
        if PYFLAKES_AVAILABLE:
            try:
                from io import StringIO
                import pyflakes.api
                import pyflakes.reporter
                
                with open(filepath, 'r') as f:
                    content = f.read()
                
                stream = StringIO()
                reporter = pyflakes.reporter.Reporter(stream, stream)
                warnings = pyflakes.api.check(content, str(filepath), reporter)
                
                lint_results["pyflakes"] = {
                    "output": stream.getvalue(),
                    "warnings": warnings
                }
            except Exception as e:
                lint_results["pyflakes"] = {"error": str(e)}
        
        # Try black formatting check
        if BLACK_AVAILABLE:
            try:
                with open(filepath, 'r') as f:
                    content = f.read()
                
                # Check if file would be reformatted
                try:
                    mode = black.FileMode()
                    black.format_file_contents(content, fast=False, mode=mode)
                    lint_results["black"] = {"needs_formatting": False}
                except black.NothingChanged:
                    lint_results["black"] = {"needs_formatting": False}
                except Exception as e:
                    lint_results["black"] = {"needs_formatting": True, "error": str(e)}
            except Exception as e:
                lint_results["black"] = {"error": str(e)}
        
        return lint_results
    
    def _analyze_import_chain(self, filepath: Path) -> List[str]:
        """Analyze import chain for dependency resolution."""
        imports = set()
        
        with open(filepath, 'r') as f:
            content = f.read()
        
        # Parse AST to get imports
        try:
            tree = ast.parse(content)
            
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        imports.add(alias.name.split('.')[0])
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        imports.add(node.module.split('.')[0])
        except SyntaxError:
            # Fall back to regex if AST fails
            import_pattern = r'^(?:from\s+(\S+)|import\s+(\S+))'
            for line in content.split('\n'):
                match = re.search(import_pattern, line.strip())
                if match:
                    module = match.group(1) or match.group(2)
                    if module:
                        imports.add(module.split('.')[0])
        
        return sorted(list(imports))
    
    def create_tkinter_wrapper(self, app_info: Dict, analysis: Dict) -> str:
        """Create a Tkinter wrapper for a TUI app."""
        app_name = app_info['name']
        wrapper_path = self.wrappers_dir / f"{app_name}_wrapper.py"
        
        wrapper_code = f'''#!/usr/bin/env python3
"""
Tkinter wrapper for {app_name}
Auto-generated by TUI to GUI Translator
"""

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import subprocess
import sys
import os
import threading
from pathlib import Path

class TUIWrapper:
    def __init__(self, root):
        self.root = root
        self.root.title("{app_name} - TUI Wrapper")
        self.root.geometry("800x600")
        
        # Store original app path
        self.app_path = Path(r"{app_info['path']}")
        
        # Setup UI
        self.setup_ui()
        
        # Runtime info
        self.process = None
        self.is_running = False
        
    def setup_ui(self):
        """Setup the Tkinter interface."""
        # Create main frame
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Configure grid weights
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(1, weight=1)
        
        # Control panel
        control_frame = ttk.LabelFrame(main_frame, text="Controls", padding="5")
        control_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        
        ttk.Button(control_frame, text="Run TUI App", command=self.run_app).pack(side=tk.LEFT, padx=2)
        ttk.Button(control_frame, text="Stop", command=self.stop_app).pack(side=tk.LEFT, padx=2)
        ttk.Button(control_frame, text="Clear Output", command=self.clear_output).pack(side=tk.LEFT, padx=2)
        ttk.Button(control_frame, text="Send Input", command=self.send_input).pack(side=tk.LEFT, padx=2)
        
        # Input field
        input_frame = ttk.Frame(main_frame)
        input_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 5))
        
        ttk.Label(input_frame, text="Input:").pack(side=tk.LEFT)
        self.input_var = tk.StringVar()
        self.input_entry = ttk.Entry(input_frame, textvariable=self.input_var, width=50)
        self.input_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(5, 0))
        self.input_entry.bind('<Return>', lambda e: self.send_input())
        
        # Output display
        output_frame = ttk.LabelFrame(main_frame, text="TUI Output", padding="5")
        output_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S))
        output_frame.columnconfigure(0, weight=1)
        output_frame.rowconfigure(0, weight=1)
        
        self.output_text = scrolledtext.ScrolledText(output_frame, wrap=tk.WORD, width=80, height=20)
        self.output_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Status bar
        self.status_var = tk.StringVar(value="Ready")
        status_bar = ttk.Label(main_frame, textvariable=self.status_var, relief=tk.SUNKEN)
        status_bar.grid(row=3, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(5, 0))
        
        # Info panel
        info_frame = ttk.LabelFrame(main_frame, text="App Info", padding="5")
        info_frame.grid(row=0, column=2, rowspan=4, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(10, 0))
        
        info_text = f"""
Application: {app_name}
Path: {app_info['path']}
TUI Probability: {app_info['probability']:.2%}
Risk Score: {analysis.get('risk_score', 0)}/100
Wrap Score: {analysis.get('wrapping_score', 0)}/100
        
Imports: {', '.join(app_info.get('imports', []))}
        
Risk Factors:
{'\\n'.join(f'• {rf}' for rf in analysis.get('risk_factors', [])) or 'None'}
        
Integration Points:
{'\\n'.join(f'• {ip}' for ip in analysis.get('integration_points', [])) or 'None'}
        """
        
        ttk.Label(info_frame, text=info_text, justify=tk.LEFT).pack(anchor=tk.W)
        
    def run_app(self):
        """Run the TUI application in a subprocess."""
        if self.is_running:
            messagebox.showwarning("Warning", "App is already running!")
            return
            
        def run_in_thread():
            try:
                self.is_running = True
                self.status_var.set("Running...")
                
                # Run the TUI app
                env = os.environ.copy()
                env['PYTHONUNBUFFERED'] = '1'
                
                self.process = subprocess.Popen(
                    [sys.executable, str(self.app_path)],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    stdin=subprocess.PIPE,
                    text=True,
                    bufsize=1,
                    universal_newlines=True,
                    env=env
                )
                
                # Read output in real-time
                for line in iter(self.process.stdout.readline, ''):
                    self.root.after(0, self.append_output, line)
                    
                self.process.stdout.close()
                return_code = self.process.wait()
                
                self.root.after(0, self.on_app_exit, return_code)
                
            except Exception as e:
                self.root.after(0, self.append_output, f"Error: {e}\\n")
                self.root.after(0, self.status_var.set, f"Error: {e}")
                self.is_running = False
                
        # Start the thread
        thread = threading.Thread(target=run_in_thread, daemon=True)
        thread.start()
        
    def stop_app(self):
        """Stop the running application."""
        if self.process and self.is_running:
            self.process.terminate()
            self.status_var.set("Stopped")
            self.is_running = False
            
    def send_input(self):
        """Send input to the running application."""
        if self.process and self.is_running:
            input_text = self.input_var.get() + '\\n'
            try:
                self.process.stdin.write(input_text)
                self.process.stdin.flush()
                self.input_var.set("")
                self.append_output(f"> {input_text}")
            except Exception as e:
                self.append_output(f"Input error: {e}\\n")
                
    def append_output(self, text):
        """Append text to the output display."""
        self.output_text.insert(tk.END, text)
        self.output_text.see(tk.END)
        self.output_text.update_idletasks()
        
    def clear_output(self):
        """Clear the output display."""
        self.output_text.delete(1.0, tk.END)
        
    def on_app_exit(self, return_code):
        """Handle application exit."""
        self.append_output(f"\\n--- Process exited with code: {return_code} ---\\n")
        self.status_var.set(f"Exited (code: {return_code})")
        self.is_running = False

def main():
    root = tk.Tk()
    app = TUIWrapper(root)
    root.mainloop()

if __name__ == "__main__":
    main()
'''
        
        # Write wrapper file
        with open(wrapper_path, 'w') as f:
            f.write(wrapper_code)
        
        # Make executable on Linux
        wrapper_path.chmod(0o755)
        
        # Update manifest
        wrapper_info = {
            "app_name": app_name,
            "wrapper_path": str(wrapper_path),
            "created": datetime.now().isoformat(),
            "analysis_ref": analysis.get("analysis_time", "")
        }
        
        if "wrappers" not in self.manifest:
            self.manifest["wrappers"] = []
        self.manifest["wrappers"].append(wrapper_info)
        self._save_manifest()
        
        # Create launcher script
        self.create_launcher_script(app_name, wrapper_path)
        
        return str(wrapper_path)
    
    def create_launcher_script(self, app_name: str, wrapper_path: Path):
        """Create a shell launcher script."""
        launcher_path = self.discoveries_dir / f"launch_{app_name}.sh"
        
        launcher_script = f'''#!/bin/bash
#
# Launcher for {app_name} TUI wrapper
# Generated by TUI to GUI Translator
#

cd "$(dirname "$0")" || exit 1

echo "Starting {app_name} wrapper..."
echo "Wrapper: {wrapper_path}"
echo ""

# Check for Python
if ! command -v python3 &> /dev/null; then
    echo "Error: python3 not found!" >&2
    exit 1
fi

# Run the wrapper
exec python3 "{wrapper_path}"
'''
        
        with open(launcher_path, 'w') as f:
            f.write(launcher_script)
        
        launcher_path.chmod(0o755)
        
        print(f"Created launcher: {launcher_path}")
    
    def generate_report(self) -> Dict:
        """Generate a comprehensive report."""
        report = {
            "timestamp": datetime.now().isoformat(),
            "base_dir": str(self.base_dir),
            "total_discovered": len(self.discovered_apps),
            "wrappers_created": len(self.manifest.get("wrappers", [])),
            "analyses_performed": len(self.manifest.get("analyses", {})),
            "overall_risk_score": 0,
            "overall_wrap_score": 0,
            "app_details": []
        }
        
        total_risk = 0
        total_wrap = 0
        count = 0
        
        for app in self.discovered_apps:
            analysis = self.manifest.get("analyses", {}).get(app['name'], {})
            
            if analysis:
                total_risk += analysis.get('risk_score', 0)
                total_wrap += analysis.get('wrapping_score', 0)
                count += 1
            
            report["app_details"].append({
                "name": app['name'],
                "tui_probability": app['probability'],
                "risk_score": analysis.get('risk_score', 0),
                "wrap_score": analysis.get('wrapping_score', 0),
                "has_wrapper": any(w.get('app_name') == app['name'] 
                                 for w in self.manifest.get("wrappers", [])),
                "imports": app.get('imports', [])
            })
        
        if count > 0:
            report["overall_risk_score"] = total_risk / count
            report["overall_wrap_score"] = total_wrap / count
        
        # Save report
        report_path = self.discoveries_dir / "analysis_report.json"
        with open(report_path, 'w') as f:
            json.dump(report, f, indent=2)
        
        print(f"Report saved to: {report_path}")
        return report


class TUITranslatorGUI:
    """Main GUI for the TUI Translator."""
    
    def __init__(self, root):
        self.root = root
        self.root.title("TUI to GUI Translator")
        self.root.geometry("1000x700")
        
        self.analyzer = None
        self.current_apps = []
        
        self.setup_ui()
        
    def setup_ui(self):
        """Setup the main GUI."""
        # Create menu
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="Set Base Directory", command=self.set_base_dir)
        file_menu.add_command(label="Refresh", command=self.refresh_discoveries)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.root.quit)
        
        tools_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Tools", menu=tools_menu)
        tools_menu.add_command(label="Generate Report", command=self.generate_report)
        tools_menu.add_command(label="Open Discoveries", command=self.open_discoveries)
        
        # Create main notebook
        notebook = ttk.Notebook(self.root)
        notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Discovery tab
        discovery_frame = ttk.Frame(notebook)
        notebook.add(discovery_frame, text="Discoveries")
        self.setup_discovery_tab(discovery_frame)
        
        # Analysis tab
        analysis_frame = ttk.Frame(notebook)
        notebook.add(analysis_frame, text="Analysis")
        self.setup_analysis_tab(analysis_frame)
        
        # Status bar
        self.status_var = tk.StringVar(value="Ready")
        status_bar = ttk.Label(self.root, textvariable=self.status_var, relief=tk.SUNKEN)
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)
        
    def setup_discovery_tab(self, parent):
        """Setup the discovery tab."""
        # Control frame
        control_frame = ttk.Frame(parent)
        control_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(control_frame, text="Base Directory:").pack(side=tk.LEFT)
        self.dir_var = tk.StringVar(value=str(Path.cwd()))
        dir_entry = ttk.Entry(control_frame, textvariable=self.dir_var, width=50)
        dir_entry.pack(side=tk.LEFT, padx=5)
        
        ttk.Button(control_frame, text="Browse", command=self.browse_dir).pack(side=tk.LEFT)
        ttk.Button(control_frame, text="Discover", command=self.discover_apps).pack(side=tk.LEFT, padx=5)
        
        # App list frame
        list_frame = ttk.LabelFrame(parent, text="Discovered TUI Applications", padding="5")
        list_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Create treeview
        columns = ("name", "path", "probability", "tui_score", "gui_score", "size")
        self.tree = ttk.Treeview(list_frame, columns=columns, show="headings")
        
        # Define headings
        self.tree.heading("name", text="Name")
        self.tree.heading("path", text="Path")
        self.tree.heading("probability", text="TUI Probability")
        self.tree.heading("tui_score", text="TUI Score")
        self.tree.heading("gui_score", text="GUI Score")
        self.tree.heading("size", text="Size (KB)")
        
        # Define columns
        self.tree.column("name", width=150)
        self.tree.column("path", width=300)
        self.tree.column("probability", width=100)
        self.tree.column("tui_score", width=80)
        self.tree.column("gui_score", width=80)
        self.tree.column("size", width=80)
        
        # Add scrollbar
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Action buttons
        button_frame = ttk.Frame(parent)
        button_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Button(button_frame, text="Analyze Selected", 
                  command=self.analyze_selected).pack(side=tk.LEFT, padx=2)
        ttk.Button(button_frame, text="Create Wrapper", 
                  command=self.create_wrapper).pack(side=tk.LEFT, padx=2)
        ttk.Button(button_frame, text="Run Wrapper", 
                  command=self.run_wrapper).pack(side=tk.LEFT, padx=2)
        
    def setup_analysis_tab(self, parent):
        """Setup the analysis tab."""
        # Create text widget for analysis output
        self.analysis_text = scrolledtext.ScrolledText(parent, wrap=tk.WORD, width=100, height=30)
        self.analysis_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Clear button
        ttk.Button(parent, text="Clear Analysis", 
                  command=lambda: self.analysis_text.delete(1.0, tk.END)).pack(pady=5)
    
    def browse_dir(self):
        """Browse for base directory."""
        from tkinter import filedialog
        directory = filedialog.askdirectory(initialdir=self.dir_var.get())
        if directory:
            self.dir_var.set(directory)
    
    def discover_apps(self):
        """Discover TUI applications."""
        self.status_var.set("Discovering...")
        self.root.update()
        
        try:
            self.analyzer = TUIAnalyzer(self.dir_var.get())
            self.current_apps = self.analyzer.discover_tui_apps()
            
            # Clear tree
            for item in self.tree.get_children():
                self.tree.delete(item)
            
            # Add discovered apps to tree
            for app in self.current_apps:
                self.tree.insert("", tk.END, values=(
                    app['name'],
                    app['path'],
                    f"{app['probability']:.2%}",
                    app['tui_score'],
                    app['gui_score'],
                    f"{app['size'] / 1024:.1f}"
                ))
            
            self.status_var.set(f"Discovered {len(self.current_apps)} applications")
            
        except Exception as e:
            messagebox.showerror("Error", f"Discovery failed: {e}")
            self.status_var.set("Discovery failed")
    
    def analyze_selected(self):
        """Analyze selected application."""
        selection = self.tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select an application first")
            return
        
        item = self.tree.item(selection[0])
        app_name = item['values'][0]
        
        # Find the app in current apps
        app_info = None
        for app in self.current_apps:
            if app['name'] == app_name:
                app_info = app
                break
        
        if not app_info:
            messagebox.showerror("Error", "Application not found")
            return
        
        self.status_var.set(f"Analyzing {app_name}...")
        self.root.update()
        
        try:
            analysis = self.analyzer.analyze_app(app_info)
            
            # Display analysis
            self.analysis_text.delete(1.0, tk.END)
            self.analysis_text.insert(tk.END, f"Analysis for: {app_name}\n")
            self.analysis_text.insert(tk.END, "=" * 50 + "\n\n")
            
            self.analysis_text.insert(tk.END, f"Risk Score: {analysis['risk_score']}/100\n")
            self.analysis_text.insert(tk.END, f"Wrapping Score: {analysis['wrapping_score']}/100\n\n")
            
            self.analysis_text.insert(tk.END, "Risk Factors:\n")
            for risk in analysis['risk_factors']:
                self.analysis_text.insert(tk.END, f"  • {risk}\n")
            
            self.analysis_text.insert(tk.END, "\nIntegration Points:\n")
            for point in analysis['integration_points']:
                self.analysis_text.insert(tk.END, f"  • {point}\n")
            
            self.analysis_text.insert(tk.END, "\nImport Chain:\n")
            for imp in analysis['import_chain']:
                self.analysis_text.insert(tk.END, f"  • {imp}\n")
            
            self.status_var.set(f"Analysis complete for {app_name}")
            
        except Exception as e:
            messagebox.showerror("Error", f"Analysis failed: {e}")
            self.status_var.set("Analysis failed")
    
    def create_wrapper(self):
        """Create wrapper for selected application."""
        selection = self.tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select an application first")
            return
        
        item = self.tree.item(selection[0])
        app_name = item['values'][0]
        
        # Find the app in current apps
        app_info = None
        for app in self.current_apps:
            if app['name'] == app_name:
                app_info = app
                break
        
        if not app_info:
            messagebox.showerror("Error", "Application not found")
            return
        
        # Get analysis
        analysis = self.analyzer.manifest.get("analyses", {}).get(app_name)
        if not analysis:
            if messagebox.askyesno("Warning", 
                                  "No analysis found. Analyze first?"):
                self.analyze_selected()
                analysis = self.analyzer.manifest.get("analyses", {}).get(app_name)
        
        if analysis:
            self.status_var.set(f"Creating wrapper for {app_name}...")
            self.root.update()
            
            try:
                wrapper_path = self.analyzer.create_tkinter_wrapper(app_info, analysis)
                self.status_var.set(f"Wrapper created: {wrapper_path}")
                messagebox.showinfo("Success", f"Wrapper created:\n{wrapper_path}")
            except Exception as e:
                messagebox.showerror("Error", f"Wrapper creation failed: {e}")
                self.status_var.set("Wrapper creation failed")
    
    def run_wrapper(self):
        """Run the wrapper for selected application."""
        selection = self.tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select an application first")
            return
        
        item = self.tree.item(selection[0])
        app_name = item['values'][0]
        
        # Find wrapper
        wrapper = None
        for w in self.analyzer.manifest.get("wrappers", []):
            if w.get('app_name') == app_name:
                wrapper = w
                break
        
        if not wrapper:
            messagebox.showwarning("Warning", f"No wrapper found for {app_name}")
            return
        
        wrapper_path = wrapper.get('wrapper_path')
        if not Path(wrapper_path).exists():
            messagebox.showerror("Error", f"Wrapper not found: {wrapper_path}")
            return
        
        self.status_var.set(f"Running wrapper for {app_name}...")
        
        # Run in separate thread
        def run_wrapper_thread():
            try:
                subprocess.Popen([sys.executable, wrapper_path])
                self.root.after(0, lambda: self.status_var.set(f"Started wrapper for {app_name}"))
            except Exception:
                self.root.after(0, lambda: messagebox.showerror("Error", f"Failed to run wrapper: {e}"))
                self.root.after(0, lambda: self.status_var.set("Failed to run wrapper"))
        
        thread = threading.Thread(target=run_wrapper_thread, daemon=True)
        thread.start()
    
    def generate_report(self):
        """Generate analysis report."""
        if not self.analyzer:
            messagebox.showwarning("Warning", "Discover apps first")
            return
        
        self.status_var.set("Generating report...")
        self.root.update()
        
        try:
            report = self.analyzer.generate_report()
            
            # Display summary
            summary = f"""
Report Generated:
• Total Apps: {report['total_discovered']}
• Wrappers Created: {report['wrappers_created']}
• Overall Risk Score: {report['overall_risk_score']:.1f}/100
• Overall Wrap Score: {report['overall_wrap_score']:.1f}/100

Report saved to discoveries/analysis_report.json
            """
            
            self.analysis_text.delete(1.0, tk.END)
            self.analysis_text.insert(tk.END, summary)
            
            self.status_var.set("Report generated successfully")
            
        except Exception as e:
            messagebox.showerror("Error", f"Report generation failed: {e}")
            self.status_var.set("Report generation failed")
    
    def open_discoveries(self):
        """Open discoveries directory."""
        if not self.analyzer:
            messagebox.showwarning("Warning", "Discover apps first")
            return
        
        discoveries_path = self.analyzer.discoveries_dir
        if sys.platform == "linux":
            subprocess.Popen(["xdg-open", str(discoveries_path)])
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(discoveries_path)])
    
    def refresh_discoveries(self):
        """Refresh discoveries."""
        if self.analyzer:
            self.discover_apps()
    
    def set_base_dir(self):
        """Set base directory from dialog."""
        self.browse_dir()
        if self.analyzer and self.dir_var.get():
            self.discover_apps()


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="TUI to GUI Translator - Discover and wrap TUI applications with Tkinter",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --discover /path/to/apps
  %(prog)s --analyze myapp.py
  %(prog)s --gui
  %(prog)s --report
        
Features:
  • Discovers TUI applications in directory
  • Analyzes code for risk and integration points
  • Creates Tkinter wrappers
  • Generates launcher scripts
  • Tracks dependencies and imports
        """
    )
    
    parser.add_argument('--discover', '-d', metavar='DIR', 
                       help='Discover TUI apps in directory')
    parser.add_argument('--analyze', '-a', metavar='FILE',
                       help='Analyze specific Python file')
    parser.add_argument('--wrapper', '-w', action='store_true',
                       help='Create wrapper for analyzed file')
    parser.add_argument('--gui', '-g', action='store_true',
                       help='Launch GUI interface')
    parser.add_argument('--report', '-r', action='store_true',
                       help='Generate analysis report')
    parser.add_argument('--base-dir', '-b', default='.',
                       help='Base directory for operations (default: current)')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Verbose output')
    
    args = parser.parse_args()
    
    # Check for GUI mode
    if args.gui or (not args.discover and not args.analyze and not args.report):
        root = tk.Tk()
        app = TUITranslatorGUI(root)
        root.mainloop()
        return
    
    # CLI mode
    analyzer = TUIAnalyzer(args.base_dir)
    
    if args.discover:
        print(f"Discovering TUI apps in {args.discover}...")
        analyzer.base_dir = Path(args.discover).resolve()
        apps = analyzer.discover_tui_apps()
        
        print(f"\nDiscovered {len(apps)} potential TUI applications:")
        for i, app in enumerate(apps[:10], 1):  # Show first 10
            print(f"{i}. {app['name']} (TUI probability: {app['probability']:.2%})")
        
        if len(apps) > 10:
            print(f"... and {len(apps) - 10} more")
    
    if args.analyze:
        print(f"Analyzing {args.analyze}...")
        app_info = {
            'path': args.analyze,
            'name': Path(args.analyze).stem
        }
        
        # Read file to get basic info
        with open(args.analyze, 'r') as f:
            content = f.read()
        
        app_info['imports'] = analyzer._extract_imports(content)
        app_info['tui_score'] = sum(1 for ind in analyzer.TUI_INDICATORS if ind in content)
        app_info['gui_score'] = sum(1 for ind in analyzer.GUI_INDICATORS if ind in content)
        total = app_info['tui_score'] + app_info['gui_score']
        app_info['probability'] = app_info['tui_score'] / max(total, 1)
        
        analysis = analyzer.analyze_app(app_info)
        
        print("\nAnalysis Results:")
        print(f"Risk Score: {analysis['risk_score']}/100")
        print(f"Wrapping Score: {analysis['wrapping_score']}/100")
        print(f"\nImport Chain: {', '.join(analysis['import_chain'])}")
        
        if args.wrapper:
            wrapper_path = analyzer.create_tkinter_wrapper(app_info, analysis)
            print(f"\nWrapper created: {wrapper_path}")
            print("Launcher script created in discoveries directory")
    
    if args.report:
        print("Generating report...")
        report = analyzer.generate_report()
        print("\nReport Summary:")
        print(f"Total Apps: {report['total_discovered']}")
        print(f"Wrappers Created: {report['wrappers_created']}")
        print(f"Overall Risk Score: {report['overall_risk_score']:.1f}/100")
        print(f"Overall Wrap Score: {report['overall_wrap_score']:.1f}/100")
        print(f"\nReport saved to: {analyzer.discoveries_dir / 'analysis_report.json'}")


if __name__ == "__main__":
    # Check for required Python version
    if sys.version_info < (3, 7):
        print("Error: Python 3.7 or higher required")
        sys.exit(1)
    
    main()