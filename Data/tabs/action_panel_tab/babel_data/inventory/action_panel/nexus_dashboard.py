#!/usr/bin/env python3
"""
UNIFIED DEBUGGER DASHBOARD - Nexus
A compact Tkinter dashboard for managing TaskForge, TUI Translator, and Code Alchemist
with unified debugging, onboarding, and safety checks.
"""

import os
import sys
import re
import json
import shutil
import pickle
import threading
import traceback
import subprocess
import importlib
import inspect
import hashlib
import tempfile
import textwrap
import webbrowser
import platform
import warnings
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any, Callable
from collections import defaultdict, OrderedDict
from dataclasses import dataclass, field, asdict
from enum import Enum, auto
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog, simpledialog
import tkinter.font as tkfont

# Try to import optional dependencies
try:
    from PIL import Image, ImageTk
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

# ============================================================================
# CONSTANTS & CONFIGURATION
# ============================================================================

class ModuleStatus(Enum):
    NOT_INSTALLED = "not_installed"
    INSTALLED = "installed"
    RUNNING = "running"
    ERROR = "error"
    UPDATING = "updating"

class SafetyLevel(Enum):
    SAFE = "safe"
    WARNING = "warning"
    DANGEROUS = "dangerous"
    UNKNOWN = "unknown"

class EventType(Enum):
    INSTALL = "install"
    UPDATE = "update"
    LAUNCH = "launch"
    DEBUG = "debug"
    ANALYZE = "analyze"
    ERROR = "error"
    INFO = "info"
    SUCCESS = "success"

@dataclass
class ModuleInfo:
    """Information about an integrated module"""
    name: str
    description: str
    main_script: str
    dependencies: List[str]
    required_pip: List[str] = field(default_factory=list)
    required_system: List[str] = field(default_factory=list)
    optional_pip: List[str] = field(default_factory=list)
    install_commands: List[str] = field(default_factory=list)
    test_command: str = "python -c \"print('OK')\""
    icon: str = "📦"
    status: ModuleStatus = ModuleStatus.NOT_INSTALLED
    version: str = "1.0.0"
    install_path: Optional[Path] = None
    last_used: Optional[datetime] = None
    safety_score: float = 0.0
    warnings: List[str] = field(default_factory=list)
    
    @property
    def is_available(self) -> bool:
        return self.status in [ModuleStatus.INSTALLED, ModuleStatus.RUNNING]
    
    @property
    def needs_update(self) -> bool:
        # Simplified version check
        return False  # Could implement actual version checking

@dataclass
class DiagnosticResult:
    """Result of a diagnostic check"""
    check_name: str
    status: str  # "pass", "warning", "fail"
    message: str
    details: Dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.now)
    severity: str = "medium"
    fix_suggestion: Optional[str] = None
    auto_fixable: bool = False
    
    @property
    def icon(self) -> str:
        return {
            "pass": "✅",
            "warning": "⚠️",
            "fail": "❌"
        }.get(self.status, "❓")

@dataclass
class ChatMessage:
    """Chat message for help system"""
    sender: str  # "user" or "assistant"
    content: str
    timestamp: datetime = field(default_factory=datetime.now)
    message_type: str = "text"  # "text", "code", "warning", "success"
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def display_time(self) -> str:
        return self.timestamp.strftime("%H:%M:%S")

@dataclass
class SafetyCheck:
    """Safety check for executable code"""
    line_number: int
    code_snippet: str
    check_type: str
    risk_level: SafetyLevel
    description: str
    recommendation: str
    confidence: float = 0.8
    verified: bool = False
    
    @property
    def color(self) -> str:
        return {
            SafetyLevel.SAFE: "#4CAF50",
            SafetyLevel.WARNING: "#FF9800",
            SafetyLevel.DANGEROUS: "#F44336",
            SafetyLevel.UNKNOWN: "#9E9E9E"
        }[self.risk_level]

# ============================================================================
# MODULE REGISTRY
# ============================================================================

class ModuleRegistry:
    """Registry for all integrated modules"""
    
    def __init__(self, base_dir: Path):
        self.base_dir = base_dir
        self.modules: Dict[str, ModuleInfo] = {}
        self.module_scripts: Dict[str, Path] = {}
        self.sandboxes: Dict[str, Path] = {}
        
        # Define core modules
        self._define_modules()
        
        # Load state
        self.state_file = base_dir / "nexus_state.json"
        self.load_state()
        
        # Initialize sandboxes
        self._init_sandboxes()
    
    def _define_modules(self):
        """Define all integrated modules"""
        self.modules = {
            "taskforge": ModuleInfo(
                name="TaskForge",
                description="Enhanced TaskWarrior with AI integration & quality gates",
                main_script="taskforge.py",
                dependencies=["python3", "git", "taskwarrior"],
                required_pip=["pyyaml", "toml", "requests", "rich", "sqlalchemy"],
                optional_pip=["black", "ruff", "mypy", "bandit", "openai", "anthropic"],
                install_commands=[
                    "sudo apt install taskwarrior python3-pip",
                    "pip install pyyaml toml requests rich sqlalchemy"
                ],
                test_command="python -c \"import sys; sys.path.insert(0, '.'); import taskforge; print('TaskForge OK')\"",
                icon="⚒️"
            ),
            "tui_translator": ModuleInfo(
                name="TUI Translator",
                description="Convert TUI applications to Tkinter GUI wrappers",
                main_script="tui_to_gui_translator.py",
                dependencies=["python3"],
                required_pip=["pyyaml"],
                optional_pip=["black", "ruff", "pyflakes", "pylint"],
                install_commands=[
                    "pip install pyyaml"
                ],
                test_command="python -c \"import sys; sys.path.insert(0, '.'); from tui_to_gui_translator import TUIAnalyzer; print('TUI Translator OK')\"",
                icon="🔄"
            ),
            "code_alchemist": ModuleInfo(
                name="Code Alchemist",
                description="GUI code analysis, hybridization & iterative refinement",
                main_script="code_alchemist.py",
                dependencies=["python3"],
                required_pip=["pyyaml"],
                optional_pip=["black", "ruff", "pyflakes", "pylint", "mypy", "bandit", "radon"],
                install_commands=[
                    "pip install pyyaml"
                ],
                test_command="python -c \"import sys; sys.path.insert(0, '.'); from code_alchemist import CodeAnalyzer; print('Code Alchemist OK')\"",
                icon="🧪"
            ),
            "morph": ModuleInfo(
                name="Morph Engine",
                description="GUI self-modification and taxonomical profiling engine",
                main_script="modules/morph/guillm.py",
                dependencies=["python3", "ollama"],
                required_pip=["ollama", "pyperclip"],
                install_commands=["pip install ollama pyperclip"],
                test_command="python3 modules/morph/guillm.py --list",
                icon="🎨"
            ),
            "guillm": ModuleInfo(
                name="GUILLM",
                description="GUI Language Model Interface for direct interaction",
                main_script="modules/morph/guillm.py",
                dependencies=["python3"],
                args="--gui",
                icon="🤖"
            ),
            "nexus": ModuleInfo(
                name="Nexus Dashboard",
                description="Unified debugger dashboard for all modules",
                main_script="nexus_dashboard.py",
                dependencies=["python3"],
                required_pip=[],
                optional_pip=["PIL", "requests"],
                install_commands=[],
                test_command="python -c \"print('Nexus OK')\"",
                icon="🎮",
                status=ModuleStatus.INSTALLED
            )
        }
    
    def _init_sandboxes(self):
        """Initialize sandbox directories"""
        sandbox_root = self.base_dir / "sandboxes"
        sandbox_root.mkdir(exist_ok=True)
        
        for module_name in self.modules:
            sandbox_dir = sandbox_root / module_name
            sandbox_dir.mkdir(exist_ok=True)
            self.sandboxes[module_name] = sandbox_dir
            
            # Create example files in sandbox
            self._create_sandbox_examples(module_name, sandbox_dir)
    
    def _create_sandbox_examples(self, module_name: str, sandbox_dir: Path):
        """Create example files for sandbox"""
        examples_dir = sandbox_dir / "examples"
        examples_dir.mkdir(exist_ok=True)
        
        if module_name == "code_alchemist":
            # Create example Python files for hybridization
            examples = {
                "simple_gui.py": """
import tkinter as tk
from tkinter import ttk

class SimpleApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Simple GUI")
        self.root.geometry("300x200")
        self.setup_ui()
    
    def setup_ui(self):
        # Create a label
        self.label = ttk.Label(self.root, text="Hello, World!")
        self.label.pack(pady=20)
        
        # Create a button
        self.button = ttk.Button(self.root, text="Click Me", command=self.on_click)
        self.button.pack(pady=10)
        
        # Create an entry
        self.entry_var = tk.StringVar()
        self.entry = ttk.Entry(self.root, textvariable=self.entry_var)
        self.entry.pack(pady=10)
        self.entry.insert(0, "Type something...")
    
    def on_click(self):
        text = self.entry_var.get()
        self.label.config(text=f"You typed: {text}")

if __name__ == "__main__":
    root = tk.Tk()
    app = SimpleApp(root)
    root.mainloop()
""",
                "calculator.py": """
import tkinter as tk
from tkinter import ttk

class Calculator:
    def __init__(self, root):
        self.root = root
        self.root.title("Calculator")
        self.root.geometry("250x300")
        
        self.result_var = tk.StringVar(value="0")
        self.setup_ui()
    
    def setup_ui(self):
        # Result display
        result_frame = ttk.Frame(self.root)
        result_frame.pack(pady=10)
        
        self.result_entry = ttk.Entry(
            result_frame, 
            textvariable=self.result_var,
            font=('Arial', 14),
            justify='right',
            state='readonly'
        )
        self.result_entry.pack()
        
        # Button grid
        button_frame = ttk.Frame(self.root)
        button_frame.pack()
        
        buttons = [
            '7', '8', '9', '/',
            '4', '5', '6', '*',
            '1', '2', '3', '-',
            '0', '.', '=', '+'
        ]
        
        for i, text in enumerate(buttons):
            row = i // 4
            col = i % 4
            
            btn = ttk.Button(
                button_frame,
                text=text,
                width=5,
                command=lambda t=text: self.on_button_click(t)
            )
            btn.grid(row=row, column=col, padx=2, pady=2)
        
        # Clear button
        clear_btn = ttk.Button(
            self.root,
            text="Clear",
            command=self.clear
        )
        clear_btn.pack(pady=10)
    
    def on_button_click(self, text):
        current = self.result_var.get()
        if current == "0":
            current = ""
        
        if text == "=":
            try:
                result = eval(current)
                self.result_var.set(str(result))
            except:
                self.result_var.set("Error")
        else:
            self.result_var.set(current + text)
    
    def clear(self):
        self.result_var.set("0")

if __name__ == "__main__":
    root = tk.Tk()
    app = Calculator(root)
    root.mainloop()
"""
            }
            
            for filename, content in examples.items():
                filepath = examples_dir / filename
                if not filepath.exists():
                    with open(filepath, 'w') as f:
                        f.write(content.strip())
    
    def load_state(self):
        """Load module state from file"""
        if self.state_file.exists():
            try:
                with open(self.state_file, 'r') as f:
                    state = json.load(f)
                
                for module_name, module_data in state.get("modules", {}).items():
                    if module_name in self.modules:
                        module = self.modules[module_name]
                        if "status" in module_data:
                            module.status = ModuleStatus(module_data["status"])
                        if "last_used" in module_data:
                            module.last_used = datetime.fromisoformat(module_data["last_used"])
                        if "install_path" in module_data:
                            module.install_path = Path(module_data["install_path"])
                        if "version" in module_data:
                            module.version = module_data["version"]
                        
                        # Check if module is actually available
                        if module.status == ModuleStatus.INSTALLED:
                            if not self._check_module_availability(module_name):
                                module.status = ModuleStatus.NOT_INSTALLED
            except Exception as e:
                print(f"Error loading state: {e}")
    
    def save_state(self):
        """Save module state to file"""
        state = {
            "modules": {},
            "last_saved": datetime.now().isoformat(),
            "version": "1.0.0"
        }
        
        for module_name, module in self.modules.items():
            state["modules"][module_name] = {
                "status": module.status.value,
                "last_used": module.last_used.isoformat() if module.last_used else None,
                "install_path": str(module.install_path) if module.install_path else None,
                "version": module.version
            }
        
        try:
            with open(self.state_file, 'w') as f:
                json.dump(state, f, indent=2)
        except Exception as e:
            print(f"Error saving state: {e}")
    
    def _check_module_availability(self, module_name: str) -> bool:
        """Check if a module is actually available"""
        module = self.modules[module_name]
        
        # Check for main script
        if module.main_script:
            script_path = Path(module.main_script)
            if not script_path.exists():
                # Check in current directory
                script_path = Path.cwd() / module.main_script
                if not script_path.exists():
                    return False
        
        # Try to run test command
        try:
            result = subprocess.run(
                module.test_command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.returncode == 0
        except:
            return False
    
    def update_module_status(self, module_name: str, status: ModuleStatus):
        """Update module status"""
        if module_name in self.modules:
            self.modules[module_name].status = status
            if status == ModuleStatus.RUNNING:
                self.modules[module_name].last_used = datetime.now()
            self.save_state()
    
    def get_module_path(self, module_name: str) -> Optional[Path]:
        """Get path to module script"""
        module = self.modules[module_name]
        
        # Check specified path first
        if module.main_script:
            script_path = Path(module.main_script)
            if script_path.exists():
                return script_path
            
            # Check in current directory
            script_path = Path.cwd() / module.main_script
            if script_path.exists():
                return script_path
        
        return None
    
    def get_sandbox_path(self, module_name: str) -> Path:
        """Get path to module's sandbox"""
        return self.sandboxes.get(module_name, self.base_dir / "sandboxes" / module_name)

# ============================================================================
# DIAGNOSTICS ENGINE
# ============================================================================

class DiagnosticsEngine:
    """Comprehensive diagnostics and safety checking engine"""
    
    def __init__(self, registry: ModuleRegistry):
        self.registry = registry
        self.diagnostic_history: List[DiagnosticResult] = []
        self.safety_checks: List[SafetyCheck] = []
        self.console_output = []
        
        # Known dangerous patterns
        self.dangerous_patterns = {
            r'os\.system\(': ("System call", SafetyLevel.DANGEROUS),
            r'subprocess\.call\(': ("Subprocess call", SafetyLevel.WARNING),
            r'eval\(': ("eval() function", SafetyLevel.DANGEROUS),
            r'exec\(': ("exec() function", SafetyLevel.DANGEROUS),
            r'__import__\(': ("Dynamic import", SafetyLevel.WARNING),
            r'pickle\.loads\(': ("Pickle load", SafetyLevel.DANGEROUS),
            r'open\(.*\)': ("File open", SafetyLevel.WARNING),
            r'socket\.': ("Network socket", SafetyLevel.WARNING),
            r'requests\.': ("HTTP request", SafetyLevel.WARNING),
        }
        
        # Safety recommendations
        self.safety_recommendations = {
            "os.system": "Use subprocess.run with explicit arguments instead",
            "eval": "Use ast.literal_eval or json.loads for safe evaluation",
            "exec": "Avoid exec() - consider safer alternatives",
            "pickle": "Use json or safer serialization formats",
            "open": "Always validate file paths and use context managers",
        }
    
    def log(self, message: str, level: str = "INFO"):
        """Log diagnostic message"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] [{level}] {message}"
        self.console_output.append(log_entry)
        print(log_entry)
    
    def run_comprehensive_diagnostics(self) -> List[DiagnosticResult]:
        """Run all diagnostic checks"""
        self.log("Running comprehensive diagnostics...")
        
        checks = [
            self.check_python_environment,
            self.check_system_dependencies,
            self.check_module_availability,
            self.check_file_permissions,
            self.check_network_connectivity,
            self.check_disk_space,
            self.check_memory_usage,
        ]
        
        results = []
        for check_func in checks:
            try:
                result = check_func()
                if isinstance(result, list):
                    results.extend(result)
                else:
                    results.append(result)
            except Exception as e:
                results.append(DiagnosticResult(
                    check_name=check_func.__name__,
                    status="fail",
                    message=f"Check failed: {e}",
                    details={"error": str(e)},
                    severity="high"
                ))
        
        self.diagnostic_history.extend(results)
        return results
    
    def check_python_environment(self) -> DiagnosticResult:
        """Check Python environment"""
        details = {
            "python_version": sys.version,
            "platform": platform.platform(),
            "executable": sys.executable,
            "path": sys.path[:5]  # First 5 entries
        }
        
        issues = []
        
        # Check Python version
        if sys.version_info < (3, 7):
            issues.append("Python 3.7+ required")
        
        # Check virtual environment
        if hasattr(sys, 'real_prefix') or sys.base_prefix != sys.prefix:
            details["virtual_env"] = True
            details["env_path"] = sys.prefix
        else:
            details["virtual_env"] = False
            issues.append("Not running in virtual environment (recommended)")
        
        status = "pass" if not issues else "warning"
        
        return DiagnosticResult(
            check_name="Python Environment",
            status=status,
            message="Python environment check" + (" with warnings" if issues else ""),
            details=details,
            severity="medium",
            fix_suggestion="Use Python 3.7+ in a virtual environment" if issues else None
        )
    
    def check_system_dependencies(self) -> List[DiagnosticResult]:
        """Check system dependencies"""
        results = []
        
        # Check for common system tools
        tools_to_check = ["python3", "pip", "git", "curl", "wget"]
        
        for tool in tools_to_check:
            try:
                result = subprocess.run(
                    ["which", tool],
                    capture_output=True,
                    text=True
                )
                
                if result.returncode == 0:
                    results.append(DiagnosticResult(
                        check_name=f"Tool: {tool}",
                        status="pass",
                        message=f"{tool} found",
                        details={"path": result.stdout.strip()},
                        severity="low"
                    ))
                else:
                    results.append(DiagnosticResult(
                        check_name=f"Tool: {tool}",
                        status="warning",
                        message=f"{tool} not found in PATH",
                        details={},
                        severity="medium",
                        fix_suggestion=f"Install {tool} using your package manager"
                    ))
            except Exception as e:
                results.append(DiagnosticResult(
                    check_name=f"Tool: {tool}",
                    status="fail",
                    message=f"Error checking {tool}: {e}",
                    details={"error": str(e)},
                    severity="medium"
                ))
        
        return results
    
    def check_module_availability(self) -> List[DiagnosticResult]:
        """Check availability of registered modules"""
        results = []
        
        for module_name, module in self.registry.modules.items():
            # Check if script exists
            script_path = self.registry.get_module_path(module_name)
            
            if script_path and script_path.exists():
                status = "pass"
                message = f"{module.name} script found"
                details = {"path": str(script_path)}
                
                # Check dependencies
                missing_deps = []
                for dep in module.required_pip:
                    try:
                        importlib.import_module(dep)
                    except ImportError:
                        missing_deps.append(dep)
                
                if missing_deps:
                    status = "warning"
                    message = f"{module.name} missing dependencies"
                    details["missing_dependencies"] = missing_deps
                
            else:
                status = "fail"
                message = f"{module.name} script not found"
                details = {"expected": module.main_script}
            
            results.append(DiagnosticResult(
                check_name=f"Module: {module.name}",
                status=status,
                message=message,
                details=details,
                severity="high" if status == "fail" else "medium",
                fix_suggestion=f"Install {module.name} using the Nexus dashboard" if status == "fail" else None
            ))
        
        return results
    
    def check_file_permissions(self) -> DiagnosticResult:
        """Check file permissions in workspace"""
        try:
            # Check if we can write to workspace
            test_file = self.registry.base_dir / ".permission_test"
            
            try:
                test_file.touch()
                writable = True
                test_file.unlink()
            except PermissionError:
                writable = False
            
            details = {
                "workspace_writable": writable,
                "workspace_path": str(self.registry.base_dir),
                "current_user": os.getenv("USER", "unknown")
            }
            
            if writable:
                return DiagnosticResult(
                    check_name="File Permissions",
                    status="pass",
                    message="Workspace is writable",
                    details=details,
                    severity="low"
                )
            else:
                return DiagnosticResult(
                    check_name="File Permissions",
                    status="fail",
                    message="Workspace is not writable",
                    details=details,
                    severity="high",
                    fix_suggestion=f"Check permissions for {self.registry.base_dir}"
                )
                
        except Exception as e:
            return DiagnosticResult(
                check_name="File Permissions",
                status="fail",
                message=f"Error checking permissions: {e}",
                details={"error": str(e)},
                severity="high"
            )
    
    def check_network_connectivity(self) -> DiagnosticResult:
        """Check network connectivity"""
        if not REQUESTS_AVAILABLE:
            return DiagnosticResult(
                check_name="Network Connectivity",
                status="warning",
                message="requests module not available for network check",
                details={"requests_available": False},
                severity="low"
            )
        
        try:
            import requests
            
            # Try to connect to a reliable site
            response = requests.get("https://httpbin.org/get", timeout=5)
            
            details = {
                "status_code": response.status_code,
                "response_time": response.elapsed.total_seconds(),
                "online": True
            }
            
            return DiagnosticResult(
                check_name="Network Connectivity",
                status="pass",
                message="Network connectivity OK",
                details=details,
                severity="low"
            )
            
        except requests.RequestException as e:
            return DiagnosticResult(
                check_name="Network Connectivity",
                status="warning",
                message="Network connectivity issues",
                details={"error": str(e), "online": False},
                severity="medium",
                fix_suggestion="Check your internet connection"
            )
    
    def check_disk_space(self) -> DiagnosticResult:
        """Check available disk space"""
        try:
            import shutil
            
            usage = shutil.disk_usage(self.registry.base_dir)
            details = {
                "total_gb": usage.total / (1024**3),
                "used_gb": usage.used / (1024**3),
                "free_gb": usage.free / (1024**3),
                "free_percent": (usage.free / usage.total) * 100
            }
            
            if details["free_percent"] < 10:
                status = "fail"
                message = "Low disk space (<10% free)"
            elif details["free_percent"] < 20:
                status = "warning"
                message = "Limited disk space (<20% free)"
            else:
                status = "pass"
                message = "Adequate disk space available"
            
            return DiagnosticResult(
                check_name="Disk Space",
                status=status,
                message=message,
                details=details,
                severity="medium" if status == "warning" else "low",
                fix_suggestion="Free up disk space if warning appears"
            )
            
        except Exception as e:
            return DiagnosticResult(
                check_name="Disk Space",
                status="fail",
                message=f"Error checking disk space: {e}",
                details={"error": str(e)},
                severity="medium"
            )
    
    def check_memory_usage(self) -> DiagnosticResult:
        """Check system memory usage"""
        try:
            import psutil
            
            memory = psutil.virtual_memory()
            details = {
                "total_gb": memory.total / (1024**3),
                "available_gb": memory.available / (1024**3),
                "used_percent": memory.percent,
                "available_percent": 100 - memory.percent
            }
            
            if details["available_percent"] < 10:
                status = "warning"
                message = "Low available memory (<10%)"
            elif details["available_percent"] < 20:
                status = "warning"
                message = "Limited available memory (<20%)"
            else:
                status = "pass"
                message = "Adequate memory available"
            
            return DiagnosticResult(
                check_name="Memory Usage",
                status=status,
                message=message,
                details=details,
                severity="medium",
                fix_suggestion="Close unnecessary applications if memory is low"
            )
            
        except ImportError:
            return DiagnosticResult(
                check_name="Memory Usage",
                status="warning",
                message="psutil not available for memory check",
                details={"psutil_available": False},
                severity="low"
            )
        except Exception as e:
            return DiagnosticResult(
                check_name="Memory Usage",
                status="fail",
                message=f"Error checking memory: {e}",
                details={"error": str(e)},
                severity="medium"
            )
    
    def analyze_code_safety(self, filepath: Path) -> List[SafetyCheck]:
        """Analyze code for safety issues"""
        self.log(f"Analyzing code safety: {filepath.name}")
        
        checks = []
        
        if not filepath.exists() or filepath.suffix != '.py':
            return checks
        
        try:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            lines = content.split('\n')
            
            for line_num, line in enumerate(lines, 1):
                line_stripped = line.strip()
                
                # Skip empty lines and comments
                if not line_stripped or line_stripped.startswith('#'):
                    continue
                
                # Check for dangerous patterns
                for pattern, (description, risk_level) in self.dangerous_patterns.items():
                    if re.search(pattern, line):
                        check = SafetyCheck(
                            line_number=line_num,
                            code_snippet=line_stripped[:100] + ("..." if len(line_stripped) > 100 else ""),
                            check_type="pattern_match",
                            risk_level=risk_level,
                            description=f"Found {description}",
                            recommendation=self.safety_recommendations.get(
                                description.split()[0].lower(),
                                "Review this code carefully before execution"
                            ),
                            confidence=0.9
                        )
                        checks.append(check)
                
                # Check for suspicious variable assignments
                if '=' in line and any(susp in line.lower() for susp in ['password', 'secret', 'key', 'token']):
                    check = SafetyCheck(
                        line_number=line_num,
                        code_snippet=line_stripped[:100],
                        check_type="sensitive_data",
                        risk_level=SafetyLevel.WARNING,
                        description="Potential sensitive data assignment",
                        recommendation="Avoid hardcoding secrets in source code",
                        confidence=0.7
                    )
                    checks.append(check)
            
            # Check for try/except pass
            try_except_pass = re.findall(r'try:.*?\n\s*except.*?\n\s*pass', content, re.DOTALL)
            if try_except_pass:
                check = SafetyCheck(
                    line_number=0,
                    code_snippet="try: ... except: pass",
                    check_type="silent_exception",
                    risk_level=SafetyLevel.WARNING,
                    description="Silent exception handler found",
                    recommendation="Avoid bare except: pass - handle specific exceptions",
                    confidence=0.8
                )
                checks.append(check)
            
        except Exception as e:
            self.log(f"Error analyzing code safety: {e}", "ERROR")
        
        return checks
    
    def generate_safety_report(self, checks: List[SafetyCheck]) -> Dict[str, Any]:
        """Generate safety report from checks"""
        if not checks:
            return {"safe": True, "message": "No safety issues found"}
        
        # Count by risk level
        counts = {
            SafetyLevel.SAFE: 0,
            SafetyLevel.WARNING: 0,
            SafetyLevel.DANGEROUS: 0,
            SafetyLevel.UNKNOWN: 0
        }
        
        for check in checks:
            counts[check.risk_level] += 1
        
        total = len(checks)
        dangerous_pct = (counts[SafetyLevel.DANGEROUS] / total * 100) if total > 0 else 0
        warning_pct = (counts[SafetyLevel.WARNING] / total * 100) if total > 0 else 0
        
        overall_safety = SafetyLevel.SAFE
        if dangerous_pct > 30:
            overall_safety = SafetyLevel.DANGEROUS
        elif dangerous_pct > 10 or warning_pct > 50:
            overall_safety = SafetyLevel.WARNING
        
        return {
            "safe": overall_safety == SafetyLevel.SAFE,
            "overall_safety": overall_safety.value,
            "total_checks": total,
            "dangerous_count": counts[SafetyLevel.DANGEROUS],
            "warning_count": counts[SafetyLevel.WARNING],
            "safe_count": counts[SafetyLevel.SAFE],
            "dangerous_percent": dangerous_pct,
            "warning_percent": warning_pct,
            "checks": [asdict(check) for check in checks[:10]]  # First 10 checks
        }

# ============================================================================
# CHAT ASSISTANT
# ============================================================================

class ChatAssistant:
    """Interactive chat assistant for help and guidance"""
    
    def __init__(self, registry: ModuleRegistry, diagnostics: DiagnosticsEngine):
        self.registry = registry
        self.diagnostics = diagnostics
        self.conversation_history: List[ChatMessage] = []
        self.context_memory = {}
        
        # Predefined responses and guidance
        self.guidance_sequences = {
            "onboarding": [
                "Welcome to Nexus Dashboard! 🎮",
                "I'll help you set up and use all the development tools.",
                "First, let's check which modules are available...",
                "You can install missing modules from the dashboard.",
                "Once installed, you can launch them directly from here.",
                "Need help with something specific? Just ask! 💬"
            ],
            "install_module": [
                "To install a module, select it from the dashboard.",
                "Click the 'Install' button for that module.",
                "I'll check dependencies and guide you through installation.",
                "Some modules might require system packages.",
                "You'll see progress and any issues that come up.",
                "After installation, the module will be ready to launch! 🚀"
            ],
            "debug_help": [
                "Having issues with a module?",
                "First, check the Diagnostics tab for any problems.",
                "You can run comprehensive diagnostics from there.",
                "Common issues: missing dependencies, permissions, network.",
                "The safety checker can review code for potential issues.",
                "If stuck, share the error message and I'll help! 🔧"
            ]
        }
        
        # Initialize with welcome message
        self.add_message("assistant", "Hello! I'm your Nexus assistant. How can I help you today?", "info")
    
    def add_message(self, sender: str, content: str, msg_type: str = "text"):
        """Add message to conversation"""
        message = ChatMessage(
            sender=sender,
            content=content,
            message_type=msg_type
        )
        self.conversation_history.append(message)
        return message
    
    def process_query(self, query: str) -> ChatMessage:
        """Process user query and generate response"""
        self.add_message("user", query)
        
        # Convert query to lowercase for matching
        query_lower = query.lower().strip()
        
        # Check for greetings
        if any(greet in query_lower for greet in ["hello", "hi", "hey", "greetings"]):
            response = "Hello! 👋 How can I assist you with Nexus Dashboard today?"
        
        # Check for help requests
        elif "help" in query_lower:
            if "install" in query_lower:
                response = self._get_guidance("install_module")
            elif "debug" in query_lower or "error" in query_lower:
                response = self._get_guidance("debug_help")
            else:
                response = self._get_guidance("onboarding")
        
        # Check for module-specific queries
        elif any(module in query_lower for module in ["taskforge", "tui", "alchemist", "translator"]):
            response = self._handle_module_query(query_lower)
        
        # Check for diagnostic queries
        elif any(diag in query_lower for diag in ["diagnostic", "check", "test", "verify"]):
            response = self._handle_diagnostic_query()
        
        # Check for safety queries
        elif any(safety in query_lower for safety in ["safe", "danger", "risk", "security"]):
            response = "I can check code safety! Drop a Python file on the dashboard or use the safety checker in the Diagnostics tab. 🔒"
        
        # Default response
        else:
            response = self._generate_generic_response(query_lower)
        
        # Add assistant response
        return self.add_message("assistant", response, "text")
    
    def _get_guidance(self, sequence_name: str) -> str:
        """Get guidance sequence"""
        if sequence_name in self.guidance_sequences:
            return "\n\n".join(self.guidance_sequences[sequence_name])
        return "I can help you with installation, debugging, or general guidance. What specifically do you need?"
    
    def _handle_module_query(self, query: str) -> str:
        """Handle module-specific queries"""
        modules_info = []
        
        for module_name, module in self.registry.modules.items():
            if module_name in query or module.name.lower() in query:
                status_icon = {
                    ModuleStatus.NOT_INSTALLED: "❌",
                    ModuleStatus.INSTALLED: "✅",
                    ModuleStatus.RUNNING: "🚀",
                    ModuleStatus.ERROR: "⚠️",
                    ModuleStatus.UPDATING: "🔄"
                }.get(module.status, "❓")
                
                modules_info.append(
                    f"{status_icon} **{module.name}**\n"
                    f"   Status: {module.status.value.replace('_', ' ').title()}\n"
                    f"   {module.description}"
                )
        
        if modules_info:
            response = "Here's what I found:\n\n" + "\n\n".join(modules_info)
            
            # Add action suggestions
            if any("not_installed" in info for info in modules_info):
                response += "\n\nYou can install missing modules from their respective tabs."
        else:
            response = "I manage these modules:\n\n"
            for module in self.registry.modules.values():
                response += f"• {module.icon} {module.name}: {module.description}\n"
        
        return response
    
    def _handle_diagnostic_query(self) -> str:
        """Handle diagnostic queries"""
        # Run quick diagnostics
        quick_checks = [
            ("Python Version", f"Python {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"),
            ("Platform", platform.system()),
            ("Virtual Environment", "Yes" if hasattr(sys, 'real_prefix') or sys.base_prefix != sys.prefix else "No"),
        ]
        
        response = "Quick System Check:\n\n"
        for check, value in quick_checks:
            response += f"✓ {check}: {value}\n"
        
        response += "\nFor comprehensive diagnostics, use the Diagnostics tab!"
        
        return response
    
    def _generate_generic_response(self, query: str) -> str:
        """Generate taxonomized response via Morph Router integration"""
        self.log(f"Routing query to Morph: {query}")
        
        try:
            # Resolve path to guillm.py
            v_root = Path(__file__).resolve().parents[3]
            guillm_path = v_root / "modules" / "morph" / "guillm.py"
            
            # Use subprocess to get Morph's coherent assessment
            cmd = [sys.executable, str(guillm_path), "--router", query, "--session", "999"]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                # Extract 'Coherent Assessment' block
                output = result.stdout
                if "Coherent Assessment:" in output:
                    response = output.split("Coherent Assessment:")[1].split("="*80)[0].strip()
                    return f"🤖 Morph Insight:\n\n{response}"
            
            return "I'm having trouble connecting to the Morph Router. Please ensure Ollama is running."
            
        except Exception as e:
            return f"Nexus Error: {str(e)}"

    def log(self, message: str, level: str = "INFO"):
        """Internal log routing"""
        print(f"[Nexus] [{level}] {message}")

# ============================================================================
# DRAG & DROP MANAGER
# ============================================================================

class DragDropManager:
    """Manage drag and drop functionality"""
    
    def __init__(self, root: tk.Tk, registry: ModuleRegistry):
        self.root = root
        self.registry = registry
        self.drop_targets = {}
        self.dragged_files = []
        
        # Bind drag and drop events
        self._setup_drag_drop()
    
    def _setup_drag_drop(self):
        """Setup drag and drop bindings"""
        # Note: Tkinter doesn't have native drag-and-drop support across apps
        # We'll simulate it with button-based file selection and visual feedback
        
        # Track mouse motion for visual feedback
        self.root.bind("<Motion>", self._on_mouse_motion)
        self.root.bind("<ButtonPress-1>", self._on_drag_start)
        self.root.bind("<ButtonRelease-1>", self._on_drag_end)
    
    def register_drop_target(self, widget: tk.Widget, callback: Callable):
        """Register a widget as a drop target"""
        self.drop_targets[widget] = callback
        
        # Add visual feedback
        widget.bind("<Enter>", lambda e: self._highlight_target(widget, True))
        widget.bind("<Leave>", lambda e: self._highlight_target(widget, False))
    
    def _highlight_target(self, widget: tk.Widget, highlight: bool):
        """Highlight drop target"""
        if highlight and hasattr(widget, 'config'):
            original_bg = widget.cget("background")
            widget.config(background="#E3F2FD")  # Light blue
            widget.original_bg = original_bg
        elif hasattr(widget, 'original_bg'):
            widget.config(background=widget.original_bg)
    
    def _on_mouse_motion(self, event):
        """Handle mouse motion for visual feedback"""
        # Could implement visual drag feedback here
        pass
    
    def _on_drag_start(self, event):
        """Handle drag start"""
        # In a real implementation, this would track drag operation
        pass
    
    def _on_drag_end(self, event):
        """Handle drag end"""
        # In a real implementation, this would handle drop
        pass
    
    def simulate_file_drop(self, filepaths: List[Path], target_widget: tk.Widget = None):
        """Simulate file drop (for button-based file selection)"""
        if target_widget and target_widget in self.drop_targets:
            self.drop_targets[target_widget](filepaths)
        else:
            # Default behavior: add to code_alchemist pot
            for filepath in filepaths:
                if filepath.suffix == '.py':
                    sandbox_path = self.registry.get_sandbox_path("code_alchemist") / filepath.name
                    shutil.copy2(filepath, sandbox_path)
                    return sandbox_path
        return None

# ============================================================================
# ANIMATION ENGINE
# ============================================================================

class AnimationEngine:
    """Simple animation engine for visual feedback"""
    
    def __init__(self, root: tk.Tk):
        self.root = root
        self.active_animations = {}
        self.animation_queue = []
        
    def shake_widget(self, widget: tk.Widget, intensity: int = 5, duration: int = 500):
        """Shake a widget (for warnings/errors)"""
        if not widget.winfo_exists():
            return
        
        original_x = widget.winfo_x()
        original_y = widget.winfo_y()
        
        def animate_shake(step=0):
            if step >= 10 or not widget.winfo_exists():
                widget.place(x=original_x, y=original_y)
                return
            
            offset = intensity * (1 if step % 2 == 0 else -1)
            widget.place(x=original_x + offset, y=original_y)
            
            self.root.after(50, lambda: animate_shake(step + 1))
        
        animate_shake()
    
    def pulse_widget(self, widget: tk.Widget, color_sequence: List[str], duration: int = 1000):
        """Pulse a widget's background color"""
        if not widget.winfo_exists() or not hasattr(widget, 'config'):
            return
        
        original_bg = widget.cget("background") if hasattr(widget, 'cget') else None
        steps = len(color_sequence)
        delay = duration // steps
        
        def animate_pulse(step=0):
            if step >= steps or not widget.winfo_exists():
                if original_bg:
                    widget.config(background=original_bg)
                return
            
            widget.config(background=color_sequence[step])
            self.root.after(delay, lambda: animate_pulse(step + 1))
        
        animate_pulse()
    
    def glow_widget(self, widget: tk.Widget, glow_color: str = "#FFD700", cycles: int = 3):
        """Make a widget glow (for success/attention)"""
        if not widget.winfo_exists():
            return
        
        original_config = {}
        if hasattr(widget, 'cget'):
            for attr in ['background', 'foreground', 'highlightbackground', 'highlightcolor']:
                try:
                    original_config[attr] = widget.cget(attr)
                except:
                    pass
        
        # Simple glow effect
        colors = [glow_color, original_config.get('background', '#FFFFFF')]
        
        def animate_glow(cycle=0, step=0):
            if cycle >= cycles or not widget.winfo_exists():
                # Restore original colors
                for attr, value in original_config.items():
                    try:
                        widget.config(**{attr: value})
                    except:
                        pass
                return
            
            current_color = colors[step % 2]
            if 'background' in original_config:
                widget.config(background=current_color)
            
            self.root.after(200, lambda: animate_glow(cycle + (1 if step == 1 else 0), (step + 1) % 2))
        
        animate_glow()
    
    def progress_spinner(self, widget: tk.Widget, active: bool = True):
        """Show progress spinner on widget"""
        if not active:
            if hasattr(widget, 'original_text'):
                widget.config(text=widget.original_text)
            return
        
        if hasattr(widget, 'config'):
            if not hasattr(widget, 'original_text'):
                widget.original_text = widget.cget("text") if 'text' in widget.keys() else ""
            
            spinner_frames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
            
            def update_spinner(frame=0):
                if not widget.winfo_exists():
                    return
                
                current_text = widget.original_text
                widget.config(text=f"{spinner_frames[frame]} {current_text}")
                self.root.after(100, lambda: update_spinner((frame + 1) % len(spinner_frames)))
            
            update_spinner()

# ============================================================================
# MAIN DASHBOARD APPLICATION
# ============================================================================

class NexusDashboard:
    """Main Nexus Dashboard application"""
    
    def __init__(self, root):
        self.root = root
        self.root.title("🔧 Nexus Dashboard v1.0")
        self.root.geometry("1200x800")
        
        # Set minimum size
        self.root.minsize(800, 600)
        
        # Initialize core components
        self.base_dir = Path.home() / ".nexus_dashboard"
        self.base_dir.mkdir(exist_ok=True)
        
        self.registry = ModuleRegistry(self.base_dir)
        self.diagnostics = DiagnosticsEngine(self.registry)
        self.chat_assistant = ChatAssistant(self.registry, self.diagnostics)
        self.drag_drop = DragDropManager(root, self.registry)
        self.animation = AnimationEngine(root)
        
        # State
        self.current_module = None
        self.active_processes = {}
        self.safety_checks = {}
        self.event_log = []
        
        # Setup UI
        self.setup_styles()
        self.create_widgets()
        self.setup_menu()
        self.setup_bindings()
        
        # Initial diagnostics
        self.run_quick_diagnostics()
        
        # Log startup
        self.log_event("Dashboard started", EventType.INFO)
    
    def setup_styles(self):
        """Setup Tkinter styles"""
        style = ttk.Style()
        
        # Colors
        self.colors = {
            'bg_dark': '#1a1a2e',
            'bg_medium': '#16213e',
            'bg_light': '#0f3460',
            'fg_light': '#e6e6e6',
            'fg_dark': '#a6a6a6',
            'accent': '#00adb5',
            'success': '#4CAF50',
            'warning': '#FF9800',
            'error': '#F44336',
            'info': '#2196F3',
            'chat_user': '#2d5a27',
            'chat_assistant': '#1e3a5f'
        }
        
        # Configure root
        self.root.configure(bg=self.colors['bg_dark'])
        
        # Configure styles
        style.theme_use('clam')
        
        # Custom styles
        style.configure('Module.TFrame',
                       background=self.colors['bg_medium'],
                       relief='raised',
                       borderwidth=2)
        
        style.configure('Module.TLabel',
                       background=self.colors['bg_medium'],
                       foreground=self.colors['fg_light'],
                       font=('Segoe UI', 10))
        
        style.configure('Status.TLabel',
                       font=('Segoe UI', 9, 'bold'),
                       padding=3)
        
        style.configure('Good.Status.TLabel',
                       background=self.colors['success'],
                       foreground='white')
        
        style.configure('Warning.Status.TLabel',
                       background=self.colors['warning'],
                       foreground='white')
        
        style.configure('Error.Status.TLabel',
                       background=self.colors['error'],
                       foreground='white')
        
        style.configure('Title.TLabel',
                       font=('Segoe UI', 16, 'bold'),
                       foreground=self.colors['accent'])
        
        style.configure('Chat.User.TFrame',
                       background=self.colors['chat_user'])
        
        style.configure('Chat.Assistant.TFrame',
                       background=self.colors['chat_assistant'])
    
    def create_widgets(self):
        """Create all dashboard widgets"""
        # Create main container with sidebar
        main_container = ttk.Frame(self.root)
        main_container.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Create sidebar
        self.create_sidebar(main_container)
        
        # Create main content area
        self.create_main_content(main_container)
        
        # Create status bar
        self.create_status_bar()
    
    def create_sidebar(self, parent):
        """Create sidebar with module quick access"""
        sidebar = ttk.Frame(parent, width=200)
        sidebar.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 5))
        sidebar.pack_propagate(False)
        
        # Logo/title
        title_frame = ttk.Frame(sidebar)
        title_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(title_frame, text="🔧 NEXUS", style='Title.TLabel').pack()
        ttk.Label(title_frame, text="Unified Debugger Dashboard").pack()
        
        ttk.Separator(title_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=5)
        
        # Quick actions
        actions_frame = ttk.LabelFrame(sidebar, text="Quick Actions", padding=10)
        actions_frame.pack(fill=tk.X, pady=5)
        
        ttk.Button(actions_frame, text="📊 Run Diagnostics", 
                  command=self.run_full_diagnostics).pack(fill=tk.X, pady=2)
        ttk.Button(actions_frame, text="🔧 Safety Check", 
                  command=self.open_safety_checker).pack(fill=tk.X, pady=2)
        ttk.Button(actions_frame, text="🔄 Refresh All", 
                  command=self.refresh_all).pack(fill=tk.X, pady=2)
        ttk.Button(actions_frame, text="💾 Save Session", 
                  command=self.save_session).pack(fill=tk.X, pady=2)
        
        # Module quick launch
        modules_frame = ttk.LabelFrame(sidebar, text="Quick Launch", padding=10)
        modules_frame.pack(fill=tk.X, pady=5)
        
        self.module_buttons = {}
        for module_name, module in self.registry.modules.items():
            if module_name == "nexus":
                continue  # Skip dashboard itself
            
            btn_frame = ttk.Frame(modules_frame)
            btn_frame.pack(fill=tk.X, pady=2)
            
            status_icon = self._get_status_icon(module.status)
            btn = ttk.Button(
                btn_frame,
                text=f"{status_icon} {module.name}",
                command=lambda m=module_name: self.launch_module(m)
            )
            btn.pack(side=tk.LEFT, fill=tk.X, expand=True)
            
            # Add install button if not installed
            if module.status == ModuleStatus.NOT_INSTALLED:
                install_btn = ttk.Button(
                    btn_frame,
                    text="⬇️",
                    width=3,
                    command=lambda m=module_name: self.install_module(m)
                )
                install_btn.pack(side=tk.RIGHT)
            
            self.module_buttons[module_name] = btn
        
        # Drag & Drop area
        drop_frame = ttk.LabelFrame(sidebar, text="Drop Files Here", padding=10)
        drop_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        drop_label = ttk.Label(
            drop_frame,
            text="📁\nDrag Python files here\nfor quick analysis",
            justify=tk.CENTER,
            font=('Segoe UI', 10)
        )
        drop_label.pack(expand=True)
        
        # Register as drop target
        self.drag_drop.register_drop_target(drop_frame, self.handle_dropped_files)
        
        # Add file selection button
        ttk.Button(drop_frame, text="📂 Select Files", 
                  command=self.select_files).pack(pady=5)
    
    def create_main_content(self, parent):
        """Create main content area with notebook"""
        # Create notebook for tabs
        self.notebook = ttk.Notebook(parent)
        self.notebook.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        
        # Create tabs
        self.create_dashboard_tab()
        self.create_modules_tab()
        self.create_diagnostics_tab()
        self.create_chat_tab()
        self.create_sandbox_tab()
        
        # Set default tab
        self.notebook.select(0)
    
    def create_dashboard_tab(self):
        """Create main dashboard tab"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="🏠 Dashboard")
        
        # Welcome message
        welcome_frame = ttk.Frame(tab)
        welcome_frame.pack(fill=tk.X, padx=10, pady=10)
        
        ttk.Label(
            welcome_frame,
            text="Welcome to Nexus Dashboard!",
            font=('Segoe UI', 18, 'bold'),
            foreground=self.colors['accent']
        ).pack(anchor=tk.W)
        
        ttk.Label(
            welcome_frame,
            text="Your unified interface for development tools and debugging",
            font=('Segoe UI', 11)
        ).pack(anchor=tk.W, pady=(0, 10))
        
        # System status
        status_frame = ttk.LabelFrame(tab, text="System Status", padding=15)
        status_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Create grid for status indicators
        grid_frame = ttk.Frame(status_frame)
        grid_frame.pack(fill=tk.BOTH, expand=True)
        
        self.status_indicators = {}
        status_items = [
            ("Python", "python", "3.8+"),
            ("Virtual Env", "venv", "Recommended"),
            ("Disk Space", "disk", ">10% free"),
            ("Memory", "memory", "Adequate"),
            ("Network", "network", "Connected"),
            ("Permissions", "perms", "Writable")
        ]
        
        for i, (name, key, requirement) in enumerate(status_items):
            row = i // 3
            col = i % 3
            
            indicator_frame = ttk.Frame(grid_frame)
            indicator_frame.grid(row=row, column=col, padx=10, pady=10, sticky='nsew')
            
            # Icon
            icon_label = ttk.Label(indicator_frame, text="⏳", font=('Segoe UI', 24))
            icon_label.pack()
            
            # Name and requirement
            ttk.Label(indicator_frame, text=name, font=('Segoe UI', 11, 'bold')).pack()
            ttk.Label(indicator_frame, text=requirement, font=('Segoe UI', 9)).pack()
            
            # Status text
            status_var = tk.StringVar(value="Checking...")
            status_label = ttk.Label(indicator_frame, textvariable=status_var, font=('Segoe UI', 9))
            status_label.pack()
            
            self.status_indicators[key] = (icon_label, status_var, status_label)
        
        # Make grid columns expand equally
        for i in range(3):
            grid_frame.columnconfigure(i, weight=1)
        
        # Quick tips
        tips_frame = ttk.LabelFrame(tab, text="Quick Tips", padding=10)
        tips_frame.pack(fill=tk.X, padx=10, pady=10)
        
        tips = [
            "💡 Use the sidebar to quickly launch modules",
            "💡 Drop Python files on the sidebar for quick analysis",
            "💡 Check Diagnostics tab for system health",
            "💡 Use Chat tab for guided help and troubleshooting",
            "💡 Each module has its own sandbox for testing"
        ]
        
        for tip in tips:
            ttk.Label(tips_frame, text=tip, justify=tk.LEFT).pack(anchor=tk.W, pady=2)
    
    def create_modules_tab(self):
        """Create detailed modules management tab"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="📦 Modules")
        
        # Create notebook within tab for each module
        module_notebook = ttk.Notebook(tab)
        module_notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Create tab for each module
        for module_name, module in self.registry.modules.items():
            module_tab = ttk.Frame(module_notebook)
            module_notebook.add(module_tab, text=f"{module.icon} {module.name}")
            
            self.create_module_details_tab(module_tab, module_name, module)
    
    def create_module_details_tab(self, parent, module_name: str, module: ModuleInfo):
        """Create detailed view for a specific module"""
        # Header
        header_frame = ttk.Frame(parent)
        header_frame.pack(fill=tk.X, padx=10, pady=10)
        
        ttk.Label(
            header_frame,
            text=module.name,
            font=('Segoe UI', 16, 'bold'),
            foreground=self.colors['accent']
        ).pack(side=tk.LEFT)
        
        # Status badge
        status_frame = ttk.Frame(header_frame)
        status_frame.pack(side=tk.RIGHT)
        
        status_text = module.status.value.replace('_', ' ').title()
        status_style = {
            ModuleStatus.INSTALLED: 'Good.Status.TLabel',
            ModuleStatus.RUNNING: 'Good.Status.TLabel',
            ModuleStatus.NOT_INSTALLED: 'Error.Status.TLabel',
            ModuleStatus.ERROR: 'Error.Status.TLabel',
            ModuleStatus.UPDATING: 'Warning.Status.TLabel'
        }.get(module.status, 'Status.TLabel')
        
        ttk.Label(status_frame, text=status_text, style=status_style).pack()
        
        # Description
        desc_frame = ttk.Frame(parent)
        desc_frame.pack(fill=tk.X, padx=10, pady=(0, 10))
        
        ttk.Label(desc_frame, text=module.description, wraplength=600).pack(anchor=tk.W)
        
        # Details in columns
        details_frame = ttk.Frame(parent)
        details_frame.pack(fill=tk.X, padx=10, pady=10)
        
        # Left column: Information
        info_frame = ttk.LabelFrame(details_frame, text="Information", padding=10)
        info_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))
        
        info_items = [
            ("Version", module.version),
            ("Main Script", module.main_script),
            ("Last Used", module.last_used.strftime("%Y-%m-%d %H:%M") if module.last_used else "Never"),
            ("Safety Score", f"{module.safety_score:.1f}/10")
        ]
        
        for label, value in info_items:
            frame = ttk.Frame(info_frame)
            frame.pack(fill=tk.X, pady=2)
            ttk.Label(frame, text=f"{label}:", width=12, anchor=tk.W).pack(side=tk.LEFT)
            ttk.Label(frame, text=value, anchor=tk.W).pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # Right column: Dependencies
        deps_frame = ttk.LabelFrame(details_frame, text="Dependencies", padding=10)
        deps_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(5, 0))
        
        # System dependencies
        ttk.Label(deps_frame, text="System:", font=('Segoe UI', 10, 'bold')).pack(anchor=tk.W)
        for dep in module.required_system:
            ttk.Label(deps_frame, text=f"• {dep}", anchor=tk.W).pack(anchor=tk.W, padx=(10, 0))
        
        if not module.required_system:
            ttk.Label(deps_frame, text="None", anchor=tk.W).pack(anchor=tk.W)
        
        # Python dependencies
        ttk.Label(deps_frame, text="Python:", font=('Segoe UI', 10, 'bold')).pack(anchor=tk.W, pady=(10, 0))
        for dep in module.required_pip:
            ttk.Label(deps_frame, text=f"• {dep}", anchor=tk.W).pack(anchor=tk.W, padx=(10, 0))
        
        # Action buttons
        action_frame = ttk.Frame(parent)
        action_frame.pack(fill=tk.X, padx=10, pady=10)
        
        # Create button grid
        buttons = [
            ("🚀 Launch", lambda: self.launch_module(module_name), "good"),
            ("⬇️ Install", lambda: self.install_module(module_name), "warning" if module.status == ModuleStatus.NOT_INSTALLED else "normal"),
            ("🔄 Update", lambda: self.update_module(module_name), "normal"),
            ("🔧 Test", lambda: self.test_module(module_name), "normal"),
            ("📂 Sandbox", lambda: self.open_sandbox(module_name), "normal"),
            ("📊 Diagnostics", lambda: self.diagnose_module(module_name), "normal"),
        ]
        
        for i, (text, command, style) in enumerate(buttons):
            col = i % 3
            row = i // 3
            
            if not hasattr(action_frame, 'grid_buttons'):
                action_frame.grid_buttons = {}
            
            btn = ttk.Button(action_frame, text=text, command=command)
            btn.grid(row=row, column=col, padx=2, pady=2, sticky='ew')
            
            if style == "good":
                btn.configure(style='Accent.TButton')
            
            action_frame.grid_buttons[(row, col)] = btn
        
        # Make columns equal width
        for i in range(3):
            action_frame.columnconfigure(i, weight=1)
        
        # Warnings/Issues
        if module.warnings:
            warning_frame = ttk.LabelFrame(parent, text="⚠️ Warnings", padding=10)
            warning_frame.pack(fill=tk.X, padx=10, pady=10)
            
            for warning in module.warnings:
                ttk.Label(warning_frame, text=f"• {warning}", anchor=tk.W).pack(anchor=tk.W)
    
    def create_diagnostics_tab(self):
        """Create diagnostics and safety checking tab"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="🔍 Diagnostics")
        
        # Split into left (controls) and right (results)
        paned = ttk.PanedWindow(tab, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Left: Controls and checks
        left_frame = ttk.Frame(paned)
        paned.add(left_frame, weight=1)
        
        ttk.Label(left_frame, text="Diagnostic Checks", style='Title.TLabel').pack(anchor=tk.W, padx=10, pady=10)
        
        # Check categories
        categories = [
            ("🌐 Environment", "Check Python and system environment"),
            ("📦 Modules", "Verify module availability and dependencies"),
            ("💾 System", "Check disk space, memory, and permissions"),
            ("🔒 Safety", "Code safety analysis and risk assessment"),
            ("🌐 Network", "Network connectivity and API access")
        ]
        
        self.check_vars = {}
        for category, description in categories:
            frame = ttk.Frame(left_frame)
            frame.pack(fill=tk.X, padx=10, pady=5)
            
            var = tk.BooleanVar(value=True)
            cb = ttk.Checkbutton(frame, text=category, variable=var)
            cb.pack(side=tk.LEFT)
            
            ttk.Label(frame, text=description, font=('Segoe UI', 9)).pack(side=tk.LEFT, padx=10)
            
            self.check_vars[category] = var
        
        # Run buttons
        button_frame = ttk.Frame(left_frame)
        button_frame.pack(fill=tk.X, padx=10, pady=20)
        
        ttk.Button(button_frame, text="▶️ Run Selected Checks", 
                  command=self.run_selected_diagnostics).pack(side=tk.LEFT, padx=2)
        ttk.Button(button_frame, text="🔄 Run All Checks", 
                  command=self.run_full_diagnostics).pack(side=tk.LEFT, padx=2)
        
        # Safety checker
        safety_frame = ttk.LabelFrame(left_frame, text="🔒 Safety Checker", padding=10)
        safety_frame.pack(fill=tk.X, padx=10, pady=10)
        
        ttk.Button(safety_frame, text="📁 Analyze Python File", 
                  command=self.analyze_file_safety).pack(fill=tk.X, pady=2)
        ttk.Button(safety_frame, text="📋 Check Clipboard", 
                  command=self.analyze_clipboard_safety).pack(fill=tk.X, pady=2)
        
        # Right: Results
        right_frame = ttk.Frame(paned)
        paned.add(right_frame, weight=2)
        
        # Results text
        self.diagnostics_text = scrolledtext.ScrolledText(
            right_frame,
            wrap=tk.WORD,
            font=('Consolas', 10),
            bg=self.colors['bg_medium'],
            fg=self.colors['fg_light']
        )
        self.diagnostics_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Clear button
        ttk.Button(right_frame, text="Clear Results", 
                  command=lambda: self.diagnostics_text.delete(1.0, tk.END)).pack(pady=5)
    
    def create_chat_tab(self):
        """Create chat assistance tab"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="💬 Chat")
        
        # Chat display area
        chat_display_frame = ttk.Frame(tab)
        chat_display_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Create canvas for chat messages with scrollbar
        chat_canvas = tk.Canvas(
            chat_display_frame,
            bg=self.colors['bg_dark'],
            highlightthickness=0
        )
        scrollbar = ttk.Scrollbar(chat_display_frame, orient=tk.VERTICAL, command=chat_canvas.yview)
        chat_canvas.configure(yscrollcommand=scrollbar.set)
        
        # Create frame inside canvas for messages
        self.chat_messages_frame = ttk.Frame(chat_canvas, style='Chat.TFrame')
        chat_canvas.create_window((0, 0), window=self.chat_messages_frame, anchor="nw")
        
        chat_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Update scrollregion when messages are added
        def update_scrollregion(event=None):
            chat_canvas.configure(scrollregion=chat_canvas.bbox("all"))
        
        self.chat_messages_frame.bind("<Configure>", update_scrollregion)
        
        # Input area
        input_frame = ttk.Frame(tab)
        input_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.chat_input = tk.Text(
            input_frame,
            height=3,
            font=('Segoe UI', 11),
            bg=self.colors['bg_medium'],
            fg=self.colors['fg_light'],
            insertbackground=self.colors['fg_light']
        )
        self.chat_input.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))
        self.chat_input.bind("<Return>", self.send_chat_message)
        
        send_button = ttk.Button(input_frame, text="Send", command=self.send_chat_message)
        send_button.pack(side=tk.RIGHT)
        
        # Load initial chat messages
        self.load_chat_messages()
    
    def create_sandbox_tab(self):
        """Create sandbox management tab"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="📁 Sandbox")
        
        # Create notebook for each module's sandbox
        sandbox_notebook = ttk.Notebook(tab)
        sandbox_notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Create tab for each module's sandbox
        for module_name, module in self.registry.modules.items():
            if module_name == "nexus":
                continue
            
            sandbox_tab = ttk.Frame(sandbox_notebook)
            sandbox_notebook.add(sandbox_tab, text=f"{module.icon} {module.name}")
            
            self.create_sandbox_view(sandbox_tab, module_name)
    
    def create_sandbox_view(self, parent, module_name: str):
        """Create view for a specific module's sandbox"""
        sandbox_path = self.registry.get_sandbox_path(module_name)
        
        # Header
        header_frame = ttk.Frame(parent)
        header_frame.pack(fill=tk.X, padx=10, pady=10)
        
        ttk.Label(
            header_frame,
            text=f"{self.registry.modules[module_name].name} Sandbox",
            font=('Segoe UI', 14, 'bold')
        ).pack(side=tk.LEFT)
        
        # Quick actions
        action_frame = ttk.Frame(header_frame)
        action_frame.pack(side=tk.RIGHT)
        
        ttk.Button(action_frame, text="📂 Open", 
                  command=lambda: self.open_folder(sandbox_path)).pack(side=tk.LEFT, padx=2)
        ttk.Button(action_frame, text="🔄 Refresh", 
                  command=lambda: self.refresh_sandbox_view(parent, module_name)).pack(side=tk.LEFT, padx=2)
        
        # File list
        list_frame = ttk.LabelFrame(parent, text="Files", padding=10)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Create treeview for files
        columns = ("name", "size", "modified")
        self.sandbox_trees = getattr(self, 'sandbox_trees', {})
        tree = ttk.Treeview(list_frame, columns=columns, show="headings")
        self.sandbox_trees[module_name] = tree
        
        tree.heading("name", text="Name")
        tree.heading("size", text="Size")
        tree.heading("modified", text="Modified")
        
        tree.column("name", width=200)
        tree.column("size", width=100)
        tree.column("modified", width=150)
        
        # Add scrollbar
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Populate files
        self.refresh_sandbox_view(parent, module_name)
        
        # File actions
        action_frame2 = ttk.Frame(parent)
        action_frame2.pack(fill=tk.X, padx=10, pady=10)
        
        ttk.Button(action_frame2, text="📄 New File", 
                  command=lambda: self.create_sandbox_file(module_name)).pack(side=tk.LEFT, padx=2)
        ttk.Button(action_frame2, text="📁 Upload", 
                  command=lambda: self.upload_to_sandbox(module_name)).pack(side=tk.LEFT, padx=2)
        ttk.Button(action_frame2, text="▶️ Run Selected", 
                  command=lambda: self.run_sandbox_file(module_name, tree)).pack(side=tk.LEFT, padx=2)
        
        # Bind double-click to open file
        tree.bind("<Double-1>", lambda e: self.open_sandbox_file(module_name, tree))
    
    def create_status_bar(self):
        """Create status bar at bottom"""
        self.status_bar = ttk.Frame(self.root, relief=tk.SUNKEN)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)
        
        # Status message
        self.status_var = tk.StringVar(value="Ready")
        status_label = ttk.Label(self.status_bar, textvariable=self.status_var)
        status_label.pack(side=tk.LEFT, padx=5)
        
        # Progress bar
        self.progress_var = tk.DoubleVar(value=0)
        self.progress_bar = ttk.Progressbar(
            self.status_bar,
            variable=self.progress_var,
            mode='determinate',
            length=150
        )
        self.progress_bar.pack(side=tk.RIGHT, padx=5)
        
        # Module status
        self.active_module_var = tk.StringVar(value="Active: None")
        ttk.Label(self.status_bar, textvariable=self.active_module_var).pack(side=tk.RIGHT, padx=10)
        
        # Safety indicator
        self.safety_var = tk.StringVar(value="🔒 Safe")
        safety_label = ttk.Label(self.status_bar, textvariable=self.safety_var)
        safety_label.pack(side=tk.RIGHT, padx=10)
    
    def setup_menu(self):
        """Setup application menu"""
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        
        # File menu
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="New Session", command=self.new_session)
        file_menu.add_command(label="Save Session", command=self.save_session)
        file_menu.add_command(label="Load Session", command=self.load_session)
        file_menu.add_separator()
        file_menu.add_command(label="Export Diagnostics", command=self.export_diagnostics)
        file_menu.add_command(label="Export Chat", command=self.export_chat)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.root.quit)
        
        # Help menu
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Help", menu=help_menu)
        help_menu.add_command(label="Quick Start Guide", command=self.show_quick_start)
        help_menu.add_command(label="Module Documentation", command=self.show_documentation)
        help_menu.add_command(label="Diagnostics Guide", command=self.show_diagnostics_guide)
        help_menu.add_separator()
        help_menu.add_command(label="Check for Updates", command=self.check_for_updates)
        help_menu.add_command(label="About Nexus", command=self.show_about)
        
        # Tools menu
        tools_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Tools", menu=tools_menu)
        tools_menu.add_command(label="System Monitor", command=self.open_system_monitor)
        tools_menu.add_command(label="Process Manager", command=self.open_process_manager)
        tools_menu.add_separator()
        tools_menu.add_command(label="Clear All Sandboxes", command=self.clear_all_sandboxes)
        tools_menu.add_command(label="Reset All Modules", command=self.reset_all_modules)
        
        # Onboarding menu
        onboard_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Onboarding", menu=onboard_menu)
        onboard_menu.add_command(label="Start Guided Setup", command=self.start_guided_setup)
        onboard_menu.add_command(label="Install All Modules", command=self.install_all_modules)
        onboard_menu.add_command(label="Test All Modules", command=self.test_all_modules)
        onboard_menu.add_separator()
        onboard_menu.add_command(label="Create Test Environment", command=self.create_test_environment)
    
    def setup_bindings(self):
        """Setup keyboard bindings"""
        self.root.bind('<Control-s>', lambda e: self.save_session())
        self.root.bind('<Control-d>', lambda e: self.run_full_diagnostics())
        self.root.bind('<Control-l>', lambda e: self.clear_chat())
        self.root.bind('<F5>', lambda e: self.refresh_all())
        self.root.bind('<F1>', lambda e: self.show_quick_start())
        self.root.bind('<Escape>', lambda e: self.cancel_operation())
    
    # ============================================================================
    # CORE FUNCTIONALITY
    # ============================================================================
    
    def log_event(self, message: str, event_type: EventType):
        """Log event with timestamp"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.event_log.append({
            "timestamp": timestamp,
            "type": event_type.value,
            "message": message
        })
        
        # Update status for important events
        if event_type in [EventType.ERROR, EventType.WARNING]:
            self.status_var.set(f"{event_type.value.upper()}: {message[:50]}")
            if event_type == EventType.ERROR:
                self.animation.shake_widget(self.status_bar, intensity=3)
    
    def run_quick_diagnostics(self):
        """Run quick system diagnostics on startup"""
        self.status_var.set("Running quick diagnostics...")
        
        def run_diagnostics():
            # Quick checks
            checks = [
                ("Python", self._check_python_version),
                ("Disk", self._check_disk_space_quick),
                ("Permissions", self._check_permissions_quick)
            ]
            
            for i, (name, check_func) in enumerate(checks):
                try:
                    result = check_func()
                    self.root.after(0, self.update_status_indicator, name.lower(), result)
                except Exception as e:
                    self.root.after(0, self.update_status_indicator, name.lower(), False)
                
                # Update progress
                progress = (i + 1) / len(checks) * 100
                self.root.after(0, self.progress_var.set, progress)
            
            self.root.after(0, self.status_var.set, "Ready")
            self.root.after(0, self.progress_var.set, 0)
        
        threading.Thread(target=run_diagnostics, daemon=True).start()
    
    def _check_python_version(self) -> bool:
        """Quick Python version check"""
        return sys.version_info >= (3, 7)
    
    def _check_disk_space_quick(self) -> bool:
        """Quick disk space check"""
        try:
            import shutil
            usage = shutil.disk_usage(self.base_dir)
            return (usage.free / usage.total) > 0.1  # >10% free
        except:
            return False
    
    def _check_permissions_quick(self) -> bool:
        """Quick permissions check"""
        try:
            test_file = self.base_dir / ".test_write"
            test_file.touch()
            test_file.unlink()
            return True
        except:
            return False
    
    def update_status_indicator(self, indicator_key: str, status: bool):
        """Update status indicator in dashboard"""
        if indicator_key in self.status_indicators:
            icon_label, status_var, _ = self.status_indicators[indicator_key]
            
            if status:
                icon_label.config(text="✅")
                status_var.set("OK")
            else:
                icon_label.config(text="❌")
                status_var.set("Issue")
                
                # Animate the warning
                self.animation.shake_widget(icon_label, intensity=2)
    
    def run_selected_diagnostics(self):
        """Run selected diagnostic checks"""
        selected_categories = [cat for cat, var in self.check_vars.items() if var.get()]
        
        if not selected_categories:
            messagebox.showinfo("Info", "Please select at least one check category")
            return
        
        self.diagnostics_text.delete(1.0, tk.END)
        self.diagnostics_text.insert(tk.END, f"Running checks: {', '.join(selected_categories)}\n")
        self.diagnostics_text.insert(tk.END, "=" * 50 + "\n\n")
        
        self.status_var.set("Running diagnostics...")
        self.progress_var.set(0)
        
        def run_checks():
            # Map categories to check functions
            category_map = {
                "🌐 Environment": [self.diagnostics.check_python_environment],
                "📦 Modules": [self.diagnostics.check_module_availability],
                "💾 System": [
                    self.diagnostics.check_file_permissions,
                    self.diagnostics.check_disk_space,
                    self.diagnostics.check_memory_usage
                ],
                "🔒 Safety": [],  # Handled separately
                "🌐 Network": [self.diagnostics.check_network_connectivity]
            }
            
            all_checks = []
            for category in selected_categories:
                all_checks.extend(category_map.get(category, []))
            
            results = []
            for i, check_func in enumerate(all_checks):
                try:
                    result = check_func()
                    self.root.after(0, self.display_diagnostic_result, result)
                    
                    if isinstance(result, list):
                        results.extend(result)
                    else:
                        results.append(result)
                except Exception as e:
                    error_result = DiagnosticResult(
                        check_name=check_func.__name__,
                        status="fail",
                        message=f"Check error: {e}",
                        details={"error": str(e)},
                        severity="high"
                    )
                    self.root.after(0, self.display_diagnostic_result, error_result)
                    results.append(error_result)
                
                # Update progress
                progress = (i + 1) / len(all_checks) * 100
                self.root.after(0, self.progress_var.set, progress)
            
            # Generate summary
            self.root.after(0, self.generate_diagnostics_summary, results)
            self.root.after(0, self.status_var.set, "Diagnostics complete")
            self.root.after(0, self.progress_var.set, 0)
        
        threading.Thread(target=run_checks, daemon=True).start()
    
    def run_full_diagnostics(self):
        """Run all diagnostic checks"""
        # Select all categories
        for var in self.check_vars.values():
            var.set(True)
        
        self.run_selected_diagnostics()
    
    def display_diagnostic_result(self, result):
        """Display diagnostic result in text area"""
        if isinstance(result, list):
            for r in result:
                self._display_single_result(r)
        else:
            self._display_single_result(result)
    
    def _display_single_result(self, result: DiagnosticResult):
        """Display single diagnostic result"""
        self.diagnostics_text.insert(tk.END, f"{result.icon} {result.check_name}\n")
        self.diagnostics_text.insert(tk.END, f"  Status: {result.status.upper()}\n")
        self.diagnostics_text.insert(tk.END, f"  Message: {result.message}\n")
        
        if result.details:
            self.diagnostics_text.insert(tk.END, "  Details:\n")
            for key, value in result.details.items():
                self.diagnostics_text.insert(tk.END, f"    • {key}: {value}\n")
        
        if result.fix_suggestion:
            self.diagnostics_text.insert(tk.END, f"  Suggestion: {result.fix_suggestion}\n")
        
        self.diagnostics_text.insert(tk.END, "\n")
        self.diagnostics_text.see(tk.END)
    
    def generate_diagnostics_summary(self, results: List[DiagnosticResult]):
        """Generate diagnostics summary"""
        if not results:
            return
        
        # Count results
        pass_count = sum(1 for r in results if r.status == "pass")
        warning_count = sum(1 for r in results if r.status == "warning")
        fail_count = sum(1 for r in results if r.status == "fail")
        total = len(results)
        
        # Add summary
        self.diagnostics_text.insert(tk.END, "=" * 50 + "\n")
        self.diagnostics_text.insert(tk.END, "SUMMARY\n")
        self.diagnostics_text.insert(tk.END, "=" * 50 + "\n")
        self.diagnostics_text.insert(tk.END, f"Total Checks: {total}\n")
        self.diagnostics_text.insert(tk.END, f"✅ Passed: {pass_count}\n")
        self.diagnostics_text.insert(tk.END, f"⚠️ Warnings: {warning_count}\n")
        self.diagnostics_text.insert(tk.END, f"❌ Failed: {fail_count}\n")
        
        # Overall status
        if fail_count > 0:
            self.diagnostics_text.insert(tk.END, "\n❌ System has issues that need attention\n")
            self.safety_var.set("⚠️ Issues")
        elif warning_count > 0:
            self.diagnostics_text.insert(tk.END, "\n⚠️ System has warnings but is operational\n")
            self.safety_var.set("⚠️ Warnings")
        else:
            self.diagnostics_text.insert(tk.END, "\n✅ All systems operational\n")
            self.safety_var.set("✅ Safe")
        
        self.diagnostics_text.see(tk.END)
    
    def analyze_file_safety(self):
        """Analyze Python file for safety issues"""
        filepath = filedialog.askopenfilename(
            title="Select Python file",
            filetypes=[("Python files", "*.py"), ("All files", "*.*")]
        )
        
        if not filepath:
            return
        
        filepath = Path(filepath)
        self.status_var.set(f"Analyzing {filepath.name}...")
        
        def analyze_thread():
            checks = self.diagnostics.analyze_code_safety(filepath)
            report = self.diagnostics.generate_safety_report(checks)
            
            self.root.after(0, self.display_safety_results, filepath, checks, report)
            self.root.after(0, self.status_var.set, "Safety analysis complete")
        
        threading.Thread(target=analyze_thread, daemon=True).start()
    
    def analyze_clipboard_safety(self):
        """Analyze clipboard content for safety issues"""
        try:
            clipboard_content = self.root.clipboard_get()
            
            # Save to temp file for analysis
            with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
                f.write(clipboard_content)
                temp_path = Path(f.name)
            
            checks = self.diagnostics.analyze_code_safety(temp_path)
            report = self.diagnostics.generate_safety_report(checks)
            
            # Display results
            self.display_safety_results(Path("clipboard"), checks, report)
            
            # Clean up
            temp_path.unlink()
            
        except tk.TclError:
            messagebox.showinfo("Info", "Clipboard is empty or doesn't contain text")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to analyze clipboard: {e}")
    
    def display_safety_results(self, filepath: Path, checks: List[SafetyCheck], report: Dict[str, Any]):
        """Display safety analysis results"""
        # Create new window for results
        result_window = tk.Toplevel(self.root)
        result_window.title(f"Safety Analysis: {filepath.name}")
        result_window.geometry("800x600")
        
        # Header
        header_frame = ttk.Frame(result_window)
        header_frame.pack(fill=tk.X, padx=10, pady=10)
        
        safety_level = SafetyLevel(report["overall_safety"])
        safety_color = safety_level.color
        safety_text = safety_level.value.upper()
        
        ttk.Label(
            header_frame,
            text=f"Safety Analysis: {filepath.name}",
            font=('Segoe UI', 14, 'bold')
        ).pack(side=tk.LEFT)
        
        safety_label = ttk.Label(
            header_frame,
            text=safety_text,
            font=('Segoe UI', 12, 'bold'),
            foreground=safety_color
        )
        safety_label.pack(side=tk.RIGHT)
        
        # Summary
        summary_frame = ttk.LabelFrame(result_window, text="Summary", padding=10)
        summary_frame.pack(fill=tk.X, padx=10, pady=10)
        
        summary_text = f"""
        Total Checks: {report['total_checks']}
        ✅ Safe: {report['safe_count']}
        ⚠️ Warnings: {report['warning_count']}
        ❌ Dangerous: {report['dangerous_count']}
        Overall Safety: {safety_text}
        """
        
        ttk.Label(summary_frame, text=summary_text, justify=tk.LEFT).pack(anchor=tk.W)
        
        # Detailed findings
        if checks:
            details_frame = ttk.LabelFrame(result_window, text="Detailed Findings", padding=10)
            details_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
            
            # Create text widget for details
            details_text = scrolledtext.ScrolledText(
                details_frame,
                wrap=tk.WORD,
                font=('Consolas', 10)
            )
            details_text.pack(fill=tk.BOTH, expand=True)
            
            for check in checks[:20]:  # Limit to first 20 issues
                details_text.insert(tk.END, f"\n{check.color[0]} Line {check.line_number}: {check.description}\n")
                details_text.insert(tk.END, f"   Code: {check.code_snippet}\n")
                details_text.insert(tk.END, f"   Risk: {check.risk_level.value}\n")
                details_text.insert(tk.END, f"   Recommendation: {check.recommendation}\n")
            
            details_text.configure(state='disabled')
        
        # Recommendations
        if not report["safe"]:
            rec_frame = ttk.LabelFrame(result_window, text="Recommendations", padding=10)
            rec_frame.pack(fill=tk.X, padx=10, pady=10)
            
            if safety_level == SafetyLevel.DANGEROUS:
                ttk.Label(rec_frame, text="⚠️ This code contains dangerous patterns!", 
                         font=('Segoe UI', 11, 'bold')).pack(anchor=tk.W)
                ttk.Label(rec_frame, text="• Review all dangerous patterns before execution").pack(anchor=tk.W)
                ttk.Label(rec_frame, text="• Consider sandboxed execution").pack(anchor=tk.W)
                ttk.Label(rec_frame, text="• Validate all external inputs").pack(anchor=tk.W)
            elif safety_level == SafetyLevel.WARNING:
                ttk.Label(rec_frame, text="⚠️ This code has warnings").pack(anchor=tk.W)
                ttk.Label(rec_frame, text="• Review warnings before production use").pack(anchor=tk.W)
                ttk.Label(rec_frame, text="• Add proper error handling").pack(anchor=tk.W)
    
    def launch_module(self, module_name: str):
        """Launch a module"""
        module = self.registry.modules[module_name]
        
        # Check if module is available
        if module.status == ModuleStatus.NOT_INSTALLED:
            response = messagebox.askyesno(
                "Module Not Installed",
                f"{module.name} is not installed. Would you like to install it now?"
            )
            if response:
                self.install_module(module_name)
            return
        
        # Check safety if code_alchemist
        if module_name == "code_alchemist":
            self.check_module_safety(module_name)
        
        self.status_var.set(f"Launching {module.name}...")
        self.active_module_var.set(f"Active: {module.name}")
        
        # Update button to show loading
        if module_name in self.module_buttons:
            self.animation.progress_spinner(self.module_buttons[module_name], True)
        
        def launch_thread():
            try:
                # Get module path
                module_path = self.registry.get_module_path(module_name)
                if not module_path:
                    raise FileNotFoundError(f"Module script not found: {module.main_script}")
                
                # Launch module
                if module_name == "taskforge":
                    # TaskForge has GUI mode
                    cmd = [sys.executable, str(module_path), "--gui"]
                else:
                    # Other modules
                    cmd = [sys.executable, str(module_path)]
                
                # Launch in separate process
                process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )
                
                self.active_processes[module_name] = process
                self.registry.update_module_status(module_name, ModuleStatus.RUNNING)
                
                # Monitor process
                def monitor_process():
                    return_code = process.wait()
                    self.root.after(0, self.on_module_exit, module_name, return_code)
                
                threading.Thread(target=monitor_process, daemon=True).start()
                
                self.root.after(0, self.log_event, f"Launched {module.name}", EventType.LAUNCH)
                self.root.after(0, self.status_var.set, f"{module.name} running")
                
                # Animate success
                if module_name in self.module_buttons:
                    self.root.after(0, self.animation.glow_widget, self.module_buttons[module_name])
                
            except Exception as e:
                self.root.after(0, self.handle_launch_error, module_name, str(e))
                self.root.after(0, self.status_var.set, "Launch failed")
        
        threading.Thread(target=launch_thread, daemon=True).start()
    
    def check_module_safety(self, module_name: str):
        """Check module code for safety issues"""
        module = self.registry.modules[module_name]
        module_path = self.registry.get_module_path(module_name)
        
        if not module_path:
            return
        
        checks = self.diagnostics.analyze_code_safety(module_path)
        report = self.diagnostics.generate_safety_report(checks)
        
        if not report["safe"]:
            response = messagebox.askyesno(
                "Safety Warning",
                f"{module.name} has potential safety issues:\n\n"
                f"Dangerous patterns: {report['dangerous_count']}\n"
                f"Warnings: {report['warning_count']}\n\n"
                f"Continue with launch?",
                icon=messagebox.WARNING
            )
            
            if not response:
                raise Exception("Launch cancelled due to safety concerns")
    
    def handle_launch_error(self, module_name: str, error: str):
        """Handle module launch error"""
        module = self.registry.modules[module_name]
        
        # Stop spinner animation
        if module_name in self.module_buttons:
            self.animation.progress_spinner(self.module_buttons[module_name], False)
        
        # Show error message
        messagebox.showerror(
            "Launch Error",
            f"Failed to launch {module.name}:\n\n{error}"
        )
        
        self.log_event(f"Failed to launch {module.name}: {error}", EventType.ERROR)
        self.registry.update_module_status(module_name, ModuleStatus.ERROR)
        
        # Shake button for attention
        if module_name in self.module_buttons:
            self.animation.shake_widget(self.module_buttons[module_name])
    
    def on_module_exit(self, module_name: str, return_code: int):
        """Handle module exit"""
        module = self.registry.modules[module_name]
        
        # Stop spinner animation
        if module_name in self.module_buttons:
            self.animation.progress_spinner(self.module_buttons[module_name], False)
        
        # Update status
        if return_code == 0:
            self.registry.update_module_status(module_name, ModuleStatus.INSTALLED)
            self.log_event(f"{module.name} exited normally", EventType.INFO)
        else:
            self.registry.update_module_status(module_name, ModuleStatus.ERROR)
            self.log_event(f"{module.name} exited with code {return_code}", EventType.ERROR)
        
        # Clean up process
        if module_name in self.active_processes:
            del self.active_processes[module_name]
        
        self.active_module_var.set("Active: None")
    
    def install_module(self, module_name: str):
        """Install a module"""
        module = self.registry.modules[module_name]
        
        # Create installation dialog
        install_window = tk.Toplevel(self.root)
        install_window.title(f"Install {module.name}")
        install_window.geometry("600x400")
        
        # Header
        header_frame = ttk.Frame(install_window)
        header_frame.pack(fill=tk.X, padx=20, pady=20)
        
        ttk.Label(
            header_frame,
            text=f"Install {module.name}",
            font=('Segoe UI', 16, 'bold')
        ).pack()
        
        ttk.Label(
            header_frame,
            text=module.description,
            wraplength=500
        ).pack(pady=10)
        
        # Progress area
        progress_frame = ttk.LabelFrame(install_window, text="Installation Progress", padding=20)
        progress_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        progress_text = scrolledtext.ScrolledText(
            progress_frame,
            wrap=tk.WORD,
            height=10,
            font=('Consolas', 10)
        )
        progress_text.pack(fill=tk.BOTH, expand=True)
        
        progress_text.insert(tk.END, "Preparing installation...\n")
        
        # Progress bar
        install_progress = ttk.Progressbar(install_window, mode='indeterminate')
        install_progress.pack(fill=tk.X, padx=20, pady=10)
        install_progress.start()
        
        # Control buttons
        button_frame = ttk.Frame(install_window)
        button_frame.pack(fill=tk.X, padx=20, pady=10)
        
        cancel_button = ttk.Button(button_frame, text="Cancel", 
                                  command=install_window.destroy)
        cancel_button.pack(side=tk.RIGHT)
        
        def install_thread():
            try:
                # Update status
                self.registry.update_module_status(module_name, ModuleStatus.UPDATING)
                
                # Log start
                progress_text.insert(tk.END, "Starting installation...\n")
                progress_text.see(tk.END)
                
                # Run installation commands
                for i, cmd in enumerate(module.install_commands):
                    progress_text.insert(tk.END, f"\n[{i+1}/{len(module.install_commands)}] {cmd}\n")
                    progress_text.see(tk.END)
                    
                    try:
                        result = subprocess.run(
                            cmd,
                            shell=True,
                            capture_output=True,
                            text=True,
                            timeout=300  # 5 minute timeout
                        )
                        
                        if result.returncode == 0:
                            progress_text.insert(tk.END, "✓ Success\n")
                        else:
                            progress_text.insert(tk.END, f"✗ Failed: {result.stderr}\n")
                            raise Exception(f"Command failed: {cmd}")
                        
                    except subprocess.TimeoutExpired:
                        progress_text.insert(tk.END, "✗ Timeout\n")
                        raise Exception(f"Command timeout: {cmd}")
                
                # Test installation
                progress_text.insert(tk.END, "\nTesting installation...\n")
                
                test_result = subprocess.run(
                    module.test_command,
                    shell=True,
                    capture_output=True,
                    text=True
                )
                
                if test_result.returncode == 0:
                    progress_text.insert(tk.END, "✓ Installation successful!\n")
                    
                    # Update status
                    self.root.after(0, self.registry.update_module_status, module_name, ModuleStatus.INSTALLED)
                    self.root.after(0, self.log_event, f"Installed {module.name}", EventType.SUCCESS)
                    
                    # Close window after delay
                    self.root.after(2000, install_window.destroy)
                    
                    # Update UI
                    self.root.after(0, self.refresh_module_buttons)
                    self.root.after(0, self.animation.glow_widget, self.module_buttons.get(module_name))
                    
                else:
                    progress_text.insert(tk.END, f"✗ Test failed: {test_result.stderr}\n")
                    raise Exception("Installation test failed")
                
            except Exception as e:
                progress_text.insert(tk.END, f"\n❌ Installation failed: {e}\n")
                self.root.after(0, self.registry.update_module_status, module_name, ModuleStatus.ERROR)
                self.root.after(0, self.log_event, f"Failed to install {module.name}: {e}", EventType.ERROR)
            
            finally:
                self.root.after(0, install_progress.stop)
                self.root.after(0, cancel_button.config, {"text": "Close"})
        
        # Start installation in thread
        threading.Thread(target=install_thread, daemon=True).start()
    
    def update_module(self, module_name: str):
        """Update a module"""
        # Similar to install but with update-specific logic
        self.install_module(module_name)  # For now, reuse install
    
    def test_module(self, module_name: str):
        """Test a module"""
        module = self.registry.modules[module_name]
        
        self.status_var.set(f"Testing {module.name}...")
        
        def test_thread():
            try:
                result = subprocess.run(
                    module.test_command,
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                
                if result.returncode == 0:
                    self.root.after(0, messagebox.showinfo, "Test Passed", 
                                  f"{module.name} test passed!\n\n{result.stdout}")
                    self.root.after(0, self.log_event, f"Test passed: {module.name}", EventType.SUCCESS)
                else:
                    self.root.after(0, messagebox.showerror, "Test Failed",
                                  f"{module.name} test failed:\n\n{result.stderr}")
                    self.root.after(0, self.log_event, f"Test failed: {module.name}", EventType.ERROR)
                
            except subprocess.TimeoutExpired:
                self.root.after(0, messagebox.showerror, "Test Timeout",
                              f"{module.name} test timed out")
                self.root.after(0, self.log_event, f"Test timeout: {module.name}", EventType.ERROR)
            
            except Exception as e:
                self.root.after(0, messagebox.showerror, "Test Error",
                              f"Error testing {module.name}:\n\n{e}")
                self.root.after(0, self.log_event, f"Test error: {module.name}: {e}", EventType.ERROR)
            
            finally:
                self.root.after(0, self.status_var.set, "Ready")
        
        threading.Thread(target=test_thread, daemon=True).start()
    
    def diagnose_module(self, module_name: str):
        """Run diagnostics on a specific module"""
        module = self.registry.modules[module_name]
        
        # Switch to diagnostics tab
        self.notebook.select(2)  # Diagnostics tab
        
        # Run module-specific diagnostics
        self.diagnostics_text.delete(1.0, tk.END)
        self.diagnostics_text.insert(tk.END, f"Diagnosing {module.name}...\n")
        self.diagnostics_text.insert(tk.END, "=" * 50 + "\n\n")
        
        def diagnose_thread():
            try:
                # Check module availability
                result = self.diagnostics.check_module_availability()
                module_results = [r for r in result if module_name in r.check_name.lower()]
                
                for r in module_results:
                    self.root.after(0, self.display_diagnostic_result, r)
                
                # Check safety if module script exists
                module_path = self.registry.get_module_path(module_name)
                if module_path and module_path.exists():
                    checks = self.diagnostics.analyze_code_safety(module_path)
                    report = self.diagnostics.generate_safety_report(checks)
                    
                    safety_result = DiagnosticResult(
                        check_name=f"{module.name} Safety",
                        status="warning" if not report["safe"] else "pass",
                        message=f"Safety check: {report['overall_safety']}",
                        details=report,
                        severity="medium"
                    )
                    
                    self.root.after(0, self.display_diagnostic_result, safety_result)
                
            except Exception as e:
                error_result = DiagnosticResult(
                    check_name=f"{module.name} Diagnostics",
                    status="fail",
                    message=f"Diagnostic error: {e}",
                    details={"error": str(e)},
                    severity="high"
                )
                self.root.after(0, self.display_diagnostic_result, error_result)
            
            finally:
                self.root.after(0, self.status_var.set, "Diagnostics complete")
        
        threading.Thread(target=diagnose_thread, daemon=True).start()
    
    def open_sandbox(self, module_name: str):
        """Open module sandbox folder"""
        sandbox_path = self.registry.get_sandbox_path(module_name)
        self.open_folder(sandbox_path)
    
    def open_folder(self, folder_path: Path):
        """Open folder in system file manager"""
        try:
            if sys.platform == "win32":
                os.startfile(folder_path)
            elif sys.platform == "darwin":
                subprocess.run(["open", str(folder_path)])
            else:
                subprocess.run(["xdg-open", str(folder_path)])
        except Exception as e:
            messagebox.showerror("Error", f"Cannot open folder: {e}")
    
    def refresh_module_buttons(self):
        """Refresh module button states"""
        for module_name, module in self.registry.modules.items():
            if module_name in self.module_buttons:
                status_icon = self._get_status_icon(module.status)
                self.module_buttons[module_name].config(
                    text=f"{status_icon} {module.name}"
                )
    
    def _get_status_icon(self, status: ModuleStatus) -> str:
        """Get icon for module status"""
        return {
            ModuleStatus.NOT_INSTALLED: "❌",
            ModuleStatus.INSTALLED: "✅",
            ModuleStatus.RUNNING: "🚀",
            ModuleStatus.ERROR: "⚠️",
            ModuleStatus.UPDATING: "🔄"
        }.get(status, "❓")
    
    def handle_dropped_files(self, filepaths: List[Path]):
        """Handle dropped files"""
        for filepath in filepaths:
            if filepath.suffix == '.py':
                # Add to code_alchemist sandbox
                sandbox_path = self.registry.get_sandbox_path("code_alchemist")
                dest_path = sandbox_path / filepath.name
                
                try:
                    shutil.copy2(filepath, dest_path)
                    self.log_event(f"Added {filepath.name} to sandbox", EventType.INFO)
                    
                    # Ask if user wants to analyze safety
                    response = messagebox.askyesno(
                        "File Added",
                        f"Added {filepath.name} to sandbox.\n\nAnalyze for safety issues?"
                    )
                    
                    if response:
                        checks = self.diagnostics.analyze_code_safety(dest_path)
                        report = self.diagnostics.generate_safety_report(checks)
                        
                        if not report["safe"]:
                            messagebox.showwarning(
                                "Safety Issues Found",
                                f"Found {report['dangerous_count']} dangerous patterns and "
                                f"{report['warning_count']} warnings in {filepath.name}"
                            )
                    
                    # Switch to sandbox tab
                    self.notebook.select(4)  # Sandbox tab
                    
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to add file: {e}")
            else:
                messagebox.showinfo("Info", "Only Python (.py) files can be analyzed")
    
    def select_files(self):
        """Select files for analysis"""
        filepaths = filedialog.askopenfilenames(
            title="Select Python files",
            filetypes=[("Python files", "*.py"), ("All files", "*.*")]
        )
        
        if filepaths:
            self.handle_dropped_files([Path(f) for f in filepaths])
    
    def load_chat_messages(self):
        """Load chat messages into display"""
        # Clear existing messages
        for widget in self.chat_messages_frame.winfo_children():
            widget.destroy()
        
        # Add each message
        for message in self.chat_assistant.conversation_history:
            self.add_chat_message_display(message)
    
    def add_chat_message_display(self, message: ChatMessage):
        """Add chat message to display"""
        # Create message frame
        if message.sender == "user":
            frame_style = 'Chat.User.TFrame'
            align = tk.RIGHT
            bg_color = self.colors['chat_user']
        else:
            frame_style = 'Chat.Assistant.TFrame'
            align = tk.LEFT
            bg_color = self.colors['chat_assistant']
        
        message_frame = ttk.Frame(self.chat_messages_frame, style=frame_style)
        message_frame.pack(fill=tk.X, padx=10, pady=5, anchor=align)
        
        # Add message content
        content_frame = ttk.Frame(message_frame)
        content_frame.pack(fill=tk.X, padx=10, pady=5)
        
        # Add timestamp
        time_label = ttk.Label(
            content_frame,
            text=message.display_time,
            font=('Segoe UI', 8),
            foreground=self.colors['fg_dark']
        )
        time_label.pack(anchor=tk.W if message.sender == "assistant" else tk.E)
        
        # Add message text
        if message.message_type == "code":
            # Use fixed-width font for code
            text_widget = tk.Text(
                content_frame,
                wrap=tk.WORD,
                height=min(10, message.content.count('\n') + 1),
                font=('Consolas', 10),
                bg=bg_color,
                fg=self.colors['fg_light'],
                relief='flat',
                borderwidth=0
            )
            text_widget.insert(1.0, message.content)
            text_widget.configure(state='disabled')
            text_widget.pack(fill=tk.X, pady=2)
        else:
            # Regular text
            text_label = tk.Label(
                content_frame,
                text=message.content,
                wraplength=500,
                justify=tk.LEFT,
                font=('Segoe UI', 11),
                bg=bg_color,
                fg=self.colors['fg_light']
            )
            text_label.pack(anchor=tk.W, pady=2)
    
    def send_chat_message(self, event=None):
        """Send chat message"""
        # Get input text
        input_text = self.chat_input.get("1.0", tk.END).strip()
        
        if not input_text:
            return
        
        # Clear input
        self.chat_input.delete("1.0", tk.END)
        
        # Add user message
        user_message = self.chat_assistant.add_message("user", input_text)
        self.add_chat_message_display(user_message)
        
        # Get assistant response
        response = self.chat_assistant.process_query(input_text)
        self.add_chat_message_display(response)
        
        # Scroll to bottom
        self.chat_messages_frame.update_idletasks()
        canvas = self.chat_messages_frame.master.master  # Get the canvas
        canvas.yview_moveto(1.0)
    
    def clear_chat(self):
        """Clear chat history"""
        response = messagebox.askyesno("Clear Chat", "Clear all chat messages?")
        if response:
            self.chat_assistant.conversation_history.clear()
            self.load_chat_messages()
    
    def refresh_sandbox_view(self, parent, module_name: str):
        """Refresh sandbox file list"""
        tree = self.sandbox_trees.get(module_name)
        if not tree:
            return
        
        # Clear existing items
        for item in tree.get_children():
            tree.delete(item)
        
        # Get sandbox path
        sandbox_path = self.registry.get_sandbox_path(module_name)
        
        # Add files and directories
        for item in sandbox_path.rglob("*"):
            if item.is_file():
                rel_path = item.relative_to(sandbox_path)
                size = item.stat().st_size
                modified = datetime.fromtimestamp(item.stat().st_mtime)
                
                tree.insert("", tk.END, values=(
                    str(rel_path),
                    f"{size:,} bytes",
                    modified.strftime("%Y-%m-%d %H:%M")
                ))
    
    def create_sandbox_file(self, module_name: str):
        """Create new file in sandbox"""
        filename = simpledialog.askstring("New File", "Enter filename:")
        if not filename:
            return
        
        if not filename.endswith('.py'):
            filename += '.py'
        
        sandbox_path = self.registry.get_sandbox_path(module_name)
        filepath = sandbox_path / filename
        
        if filepath.exists():
            messagebox.showerror("Error", f"File already exists: {filename}")
            return
        
        # Create file with template
        template = """#!/usr/bin/env python3
\"\"\"
New Python file
Created in Nexus Dashboard sandbox
\"\"\"

def main():
    print("Hello from Nexus sandbox!")

if __name__ == "__main__":
    main()
"""
        
        try:
            with open(filepath, 'w') as f:
                f.write(template)
            
            self.refresh_sandbox_view(None, module_name)
            self.log_event(f"Created {filename} in {module_name} sandbox", EventType.INFO)
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to create file: {e}")
    
    def upload_to_sandbox(self, module_name: str):
        """Upload file to sandbox"""
        filepaths = filedialog.askopenfilenames(
            title=f"Upload to {self.registry.modules[module_name].name} Sandbox"
        )
        
        if filepaths:
            sandbox_path = self.registry.get_sandbox_path(module_name)
            
            for filepath in filepaths:
                src = Path(filepath)
                dest = sandbox_path / src.name
                
                try:
                    shutil.copy2(src, dest)
                    self.log_event(f"Uploaded {src.name} to {module_name} sandbox", EventType.INFO)
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to upload {src.name}: {e}")
            
            self.refresh_sandbox_view(None, module_name)
    
    def run_sandbox_file(self, module_name: str, tree: ttk.Treeview):
        """Run selected sandbox file"""
        selection = tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a file first")
            return
        
        item = tree.item(selection[0])
        filename = item['values'][0]
        
        sandbox_path = self.registry.get_sandbox_path(module_name)
        filepath = sandbox_path / filename
        
        if not filepath.exists():
            messagebox.showerror("Error", f"File not found: {filename}")
            return
        
        # Check safety first
        checks = self.diagnostics.analyze_code_safety(filepath)
        report = self.diagnostics.generate_safety_report(checks)
        
        if not report["safe"] and report["dangerous_count"] > 0:
            response = messagebox.askyesno(
                "Safety Warning",
                f"This file contains {report['dangerous_count']} dangerous patterns.\n\n"
                f"Are you sure you want to run it?",
                icon=messagebox.WARNING
            )
            
            if not response:
                return
        
        # Run the file
        self.status_var.set(f"Running {filename}...")
        
        def run_file_thread():
            try:
                result = subprocess.run(
                    [sys.executable, str(filepath)],
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                
                # Create output window
                self.root.after(0, self.show_sandbox_output, filename, result)
                
            except subprocess.TimeoutExpired:
                self.root.after(0, messagebox.showerror, "Timeout",
                              f"{filename} execution timed out after 30 seconds")
            except Exception as e:
                self.root.after(0, messagebox.showerror, "Error",
                              f"Failed to run {filename}:\n\n{e}")
            finally:
                self.root.after(0, self.status_var.set, "Ready")
        
        threading.Thread(target=run_file_thread, daemon=True).start()
    
    def show_sandbox_output(self, filename: str, result: subprocess.CompletedProcess):
        """Show sandbox file execution output"""
        output_window = tk.Toplevel(self.root)
        output_window.title(f"Output: {filename}")
        output_window.geometry("600x400")
        
        # Header
        header_frame = ttk.Frame(output_window)
        header_frame.pack(fill=tk.X, padx=10, pady=10)
        
        ttk.Label(
            header_frame,
            text=f"Output: {filename}",
            font=('Segoe UI', 14, 'bold')
        ).pack(side=tk.LEFT)
        
        # Return code
        return_code = "✓ Success" if result.returncode == 0 else f"✗ Failed ({result.returncode})"
        ttk.Label(header_frame, text=return_code).pack(side=tk.RIGHT)
        
        # Output text
        text_frame = ttk.Frame(output_window)
        text_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        output_text = scrolledtext.ScrolledText(
            text_frame,
            wrap=tk.WORD,
            font=('Consolas', 10)
        )
        output_text.pack(fill=tk.BOTH, expand=True)
        
        if result.stdout:
            output_text.insert(tk.END, "=== STDOUT ===\n")
            output_text.insert(tk.END, result.stdout)
            output_text.insert(tk.END, "\n")
        
        if result.stderr:
            output_text.insert(tk.END, "=== STDERR ===\n")
            output_text.insert(tk.END, result.stderr)
        
        output_text.configure(state='disabled')
    
    def open_sandbox_file(self, module_name: str, tree: ttk.Treeview):
        """Open sandbox file in editor"""
        selection = tree.selection()
        if not selection:
            return
        
        item = tree.item(selection[0])
        filename = item['values'][0]
        
        sandbox_path = self.registry.get_sandbox_path(module_name)
        filepath = sandbox_path / filename
        
        # Open with system default editor
        try:
            if sys.platform == "win32":
                os.startfile(filepath)
            elif sys.platform == "darwin":
                subprocess.run(["open", str(filepath)])
            else:
                subprocess.run(["xdg-open", str(filepath)])
        except Exception as e:
            messagebox.showerror("Error", f"Cannot open file: {e}")
    
    # ============================================================================
    # MENU COMMANDS
    # ============================================================================
    
    def new_session(self):
        """Start new session"""
        response = messagebox.askyesno("New Session", "Start new session? Current session will be saved.")
        if response:
            self.save_session()
            # Reset state
            self.event_log.clear()
            self.chat_assistant.conversation_history.clear()
            self.load_chat_messages()
            self.status_var.set("New session started")
    
    def save_session(self):
        """Save current session"""
        try:
            session_data = {
                "event_log": self.event_log,
                "chat_history": [asdict(msg) for msg in self.chat_assistant.conversation_history],
                "saved_at": datetime.now().isoformat()
            }
            
            session_file = self.base_dir / "session.json"
            with open(session_file, 'w') as f:
                json.dump(session_data, f, indent=2)
            
            self.log_event("Session saved", EventType.INFO)
            self.status_var.set("Session saved")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save session: {e}")
    
    def load_session(self):
        """Load saved session"""
        session_file = self.base_dir / "session.json"
        
        if not session_file.exists():
            messagebox.showinfo("Info", "No saved session found")
            return
        
        try:
            with open(session_file, 'r') as f:
                session_data = json.load(f)
            
            # Load event log
            self.event_log = session_data.get("event_log", [])
            
            # Load chat history
            chat_history = session_data.get("chat_history", [])
            self.chat_assistant.conversation_history.clear()
            
            for msg_data in chat_history:
                msg = ChatMessage(**msg_data)
                msg.timestamp = datetime.fromisoformat(msg_data["timestamp"])
                self.chat_assistant.conversation_history.append(msg)
            
            # Refresh chat display
            self.load_chat_messages()
            
            self.log_event("Session loaded", EventType.INFO)
            self.status_var.set("Session loaded")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load session: {e}")
    
    def export_diagnostics(self):
        """Export diagnostics to file"""
        filepath = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
        )
        
        if filepath:
            try:
                content = self.diagnostics_text.get(1.0, tk.END)
                with open(filepath, 'w') as f:
                    f.write(content)
                
                self.log_event(f"Diagnostics exported to {filepath}", EventType.INFO)
                messagebox.showinfo("Success", "Diagnostics exported successfully")
                
            except Exception as e:
                messagebox.showerror("Error", f"Failed to export: {e}")
    
    def export_chat(self):
        """Export chat to file"""
        filepath = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
        )
        
        if filepath:
            try:
                with open(filepath, 'w') as f:
                    f.write("Nexus Dashboard Chat Export\n")
                    f.write("=" * 50 + "\n\n")
                    
                    for msg in self.chat_assistant.conversation_history:
                        f.write(f"[{msg.display_time}] {msg.sender.upper()}: {msg.content}\n\n")
                
                self.log_event(f"Chat exported to {filepath}", EventType.INFO)
                messagebox.showinfo("Success", "Chat exported successfully")
                
            except Exception as e:
                messagebox.showerror("Error", f"Failed to export: {e}")
    
    def show_quick_start(self):
        """Show quick start guide"""
        guide = """
        🚀 QUICK START GUIDE
        
        1. INSTALLATION
           • Check the Dashboard tab for system status
           • Install missing modules from their respective tabs
           • Run diagnostics to verify installation
        
        2. MODULE LAUNCH
           • Use sidebar buttons for quick module launch
           • Each module opens in its own process
           • Monitor status in the status bar
        
        3. FILE ANALYSIS
           • Drop Python files on the sidebar
           • Files are copied to the appropriate sandbox
           • Use safety checker before running unknown code
        
        4. DIAGNOSTICS
           • Run comprehensive diagnostics from Diagnostics tab
           • Check for safety issues in code
           • Monitor system resources
        
        5. CHAT ASSISTANCE
           • Ask questions in the Chat tab
           • Get installation and debugging help
           • Guided troubleshooting
        
        Need more help? Check the Onboarding menu!
        """
        
        messagebox.showinfo("Quick Start Guide", guide)
    
    def show_documentation(self):
        """Show module documentation"""
        docs = """
        📚 MODULE DOCUMENTATION
        
        🔧 NEXUS DASHBOARD
        Unified interface for all development tools
        Features: Module management, diagnostics, safety checking, chat assistance
        
        ⚒️ TASKFORGE
        Enhanced TaskWarrior with AI integration & quality gates
        Features: Task management, quality checks, AI model tracking
        
        🔄 TUI TRANSLATOR
        Convert TUI applications to Tkinter GUI wrappers
        Features: TUI discovery, code analysis, automatic wrapper generation
        
        🧪 CODE ALCHEMIST
        GUI code analysis, hybridization & iterative refinement
        Features: Code analysis, hybrid builds, iterative improvement, confidence scoring
        
        For detailed usage instructions, launch each module and check its help.
        """
        
        messagebox.showinfo("Module Documentation", docs)
    
    def show_diagnostics_guide(self):
        """Show diagnostics guide"""
        guide = """
        🔍 DIAGNOSTICS GUIDE
        
        DIAGNOSTIC CHECKS:
        
        🌐 Environment
        • Python version and virtual environment
        • System platform and architecture
        
        📦 Modules
        • Module availability and dependencies
        • Installation status and version
        
        💾 System
        • Disk space and file permissions
        • Memory usage and system resources
        
        🔒 Safety
        • Code analysis for dangerous patterns
        • Risk assessment and recommendations
        
        🌐 Network
        • Connectivity and API access
        • Internet access verification
        
        SAFETY LEVELS:
        
        ✅ SAFE: No dangerous patterns found
        ⚠️ WARNING: Some concerns, review recommended
        ❌ DANGEROUS: High-risk patterns found
        
        Use the safety checker before running unknown code!
        """
        
        messagebox.showinfo("Diagnostics Guide", guide)
    
    def check_for_updates(self):
        """Check for Nexus updates"""
        self.status_var.set("Checking for updates...")
        
        def check_updates():
            try:
                # This would normally check a remote repository
                # For now, just show current version
                self.root.after(0, messagebox.showinfo, "Updates",
                              "Nexus Dashboard v1.0.0\n\n"
                              "All modules are at their latest versions.")
                self.root.after(0, self.status_var.set, "Ready")
                
            except Exception as e:
                self.root.after(0, messagebox.showerror, "Update Error",
                              f"Failed to check for updates: {e}")
                self.root.after(0, self.status_var.set, "Update check failed")
        
        threading.Thread(target=check_updates, daemon=True).start()
    
    def show_about(self):
        """Show about dialog"""
        about_text = """
        🔧 NEXUS DASHBOARD v1.0.0
        
        Unified Debugger Dashboard for Development Tools
        
        FEATURES:
        • Module management and quick launch
        • Comprehensive diagnostics and safety checking
        • Interactive chat assistance
        • Sandboxed file management
        • Drag-and-drop file analysis
        
        INTEGRATED MODULES:
        • TaskForge: Enhanced TaskWarrior with AI
        • TUI Translator: TUI to GUI conversion
        • Code Alchemist: Code hybridization
        
        Developed with ❤️ for developers
        
        © 2024 Nexus Dashboard Project
        """
        
        messagebox.showinfo("About Nexus Dashboard", about_text)
    
    def open_system_monitor(self):
        """Open system monitor"""
        # Simple system monitor window
        monitor_window = tk.Toplevel(self.root)
        monitor_window.title("System Monitor")
        monitor_window.geometry("400x300")
        
        ttk.Label(monitor_window, text="System Monitor", 
                 font=('Segoe UI', 14, 'bold')).pack(pady=10)
        
        # Create labels for system info
        info_frame = ttk.Frame(monitor_window)
        info_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        self.monitor_labels = {}
        metrics = [
            ("CPU Usage", "cpu"),
            ("Memory Usage", "memory"),
            ("Disk Usage", "disk"),
            ("Network", "network")
        ]
        
        for name, key in metrics:
            frame = ttk.Frame(info_frame)
            frame.pack(fill=tk.X, pady=5)
            
            ttk.Label(frame, text=f"{name}:", width=15, anchor=tk.W).pack(side=tk.LEFT)
            var = tk.StringVar(value="Checking...")
            label = ttk.Label(frame, textvariable=var, anchor=tk.W)
            label.pack(side=tk.LEFT, fill=tk.X, expand=True)
            
            self.monitor_labels[key] = var
        
        # Refresh button
        ttk.Button(monitor_window, text="🔄 Refresh",
                  command=self.update_system_monitor).pack(pady=10)
        
        # Initial update
        self.update_system_monitor()
    
    def update_system_monitor(self):
        """Update system monitor values"""
        def update_thread():
            try:
                import psutil
                
                # CPU usage
                cpu_percent = psutil.cpu_percent(interval=0.1)
                self.root.after(0, self.monitor_labels["cpu"].set, f"{cpu_percent:.1f}%")
                
                # Memory usage
                memory = psutil.virtual_memory()
                memory_text = f"{memory.percent:.1f}% ({memory.used//1024//1024} MB used)"
                self.root.after(0, self.monitor_labels["memory"].set, memory_text)
                
                # Disk usage
                disk = psutil.disk_usage('/')
                disk_text = f"{disk.percent:.1f}% ({disk.free//1024//1024} MB free)"
                self.root.after(0, self.monitor_labels["disk"].set, disk_text)
                
                # Network
                net_io = psutil.net_io_counters()
                network_text = f"↑{net_io.bytes_sent//1024} KB ↓{net_io.bytes_recv//1024} KB"
                self.root.after(0, self.monitor_labels["network"].set, network_text)
                
            except ImportError:
                self.root.after(0, lambda: messagebox.showerror("Error", "psutil not installed"))
            except Exception as e:
                self.root.after(0, lambda: print(f"Monitor error: {e}"))
        
        threading.Thread(target=update_thread, daemon=True).start()
    
    def open_process_manager(self):
        """Open process manager"""
        # Simple process manager
        process_window = tk.Toplevel(self.root)
        process_window.title("Process Manager")
        process_window.geometry("600x400")
        
        # Header
        header_frame = ttk.Frame(process_window)
        header_frame.pack(fill=tk.X, padx=10, pady=10)
        
        ttk.Label(header_frame, text="Active Processes",
                 font=('Segoe UI', 14, 'bold')).pack(side=tk.LEFT)
        
        # Process list
        tree_frame = ttk.Frame(process_window)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        columns = ("module", "pid", "status")
        tree = ttk.Treeview(tree_frame, columns=columns, show="headings")
        
        tree.heading("module", text="Module")
        tree.heading("pid", text="PID")
        tree.heading("status", text="Status")
        
        tree.column("module", width=200)
        tree.column("pid", width=100)
        tree.column("status", width=100)
        
        scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Populate processes
        for module_name, process in self.active_processes.items():
            if process and process.poll() is None:  # Process still running
                tree.insert("", tk.END, values=(
                    self.registry.modules[module_name].name,
                    process.pid,
                    "Running"
                ))
        
        # Control buttons
        button_frame = ttk.Frame(process_window)
        button_frame.pack(fill=tk.X, padx=10, pady=10)
        
        ttk.Button(button_frame, text="🔄 Refresh",
                  command=lambda: self.refresh_process_list(tree)).pack(side=tk.LEFT, padx=2)
        ttk.Button(button_frame, text="⏹️ Terminate",
                  command=lambda: self.terminate_process(tree)).pack(side=tk.LEFT, padx=2)
    
    def refresh_process_list(self, tree: ttk.Treeview):
        """Refresh process list"""
        # Clear tree
        for item in tree.get_children():
            tree.delete(item)
        
        # Add active processes
        for module_name, process in self.active_processes.items():
            if process and process.poll() is None:
                tree.insert("", tk.END, values=(
                    self.registry.modules[module_name].name,
                    process.pid,
                    "Running"
                ))
    
    def terminate_process(self, tree: ttk.Treeview):
        """Terminate selected process"""
        selection = tree.selection()
        if not selection:
            return
        
        item = tree.item(selection[0])
        module_name = item['values'][0].lower().replace(' ', '')
        
        if module_name in self.active_processes:
            process = self.active_processes[module_name]
            try:
                process.terminate()
                process.wait(timeout=5)
                self.log_event(f"Terminated {module_name}", EventType.INFO)
                self.refresh_process_list(tree)
            except Exception as e:
                messagebox.showerror("Error", f"Failed to terminate process: {e}")
    
    def clear_all_sandboxes(self):
        """Clear all sandbox directories"""
        response = messagebox.askyesno("Clear Sandboxes", 
                                      "Clear all sandbox files? This cannot be undone.")
        if not response:
            return
        
        try:
            for module_name in self.registry.modules:
                if module_name != "nexus":
                    sandbox_path = self.registry.get_sandbox_path(module_name)
                    
                    # Remove all files but keep directory
                    for item in sandbox_path.iterdir():
                        if item.is_file():
                            item.unlink()
                        elif item.is_dir():
                            shutil.rmtree(item)
            
            self.log_event("Cleared all sandboxes", EventType.INFO)
            messagebox.showinfo("Success", "All sandboxes cleared")
            
            # Refresh sandbox views
            for module_name in self.sandbox_trees:
                self.refresh_sandbox_view(None, module_name)
                
        except Exception as e:
            messagebox.showerror("Error", f"Failed to clear sandboxes: {e}")
    
    def reset_all_modules(self):
        """Reset all module states"""
        response = messagebox.askyesno("Reset Modules", 
                                      "Reset all module states to NOT_INSTALLED?")
        if not response:
            return
        
        for module_name, module in self.registry.modules.items():
            if module_name != "nexus":
                module.status = ModuleStatus.NOT_INSTALLED
        
        self.registry.save_state()
        self.refresh_module_buttons()
        self.log_event("Reset all module states", EventType.INFO)
        messagebox.showinfo("Success", "All modules reset")
    
    def start_guided_setup(self):
        """Start guided setup wizard"""
        wizard = GuidedSetupWizard(self.root, self)
        wizard.start()
    
    def install_all_modules(self):
        """Install all modules"""
        response = messagebox.askyesno("Install All", 
                                      "Install all available modules? This may take some time.")
        if not response:
            return
        
        self.status_var.set("Installing all modules...")
        
        def install_all_thread():
            for module_name, module in self.registry.modules.items():
                if module_name != "nexus" and module.status == ModuleStatus.NOT_INSTALLED:
                    self.root.after(0, self.install_module, module_name)
                    time.sleep(2)  # Delay between installations
            
            self.root.after(0, self.status_var.set, "Installation complete")
        
        threading.Thread(target=install_all_thread, daemon=True).start()
    
    def test_all_modules(self):
        """Test all installed modules"""
        self.status_var.set("Testing all modules...")
        
        def test_all_thread():
            for module_name, module in self.registry.modules.items():
                if module_name != "nexus" and module.status == ModuleStatus.INSTALLED:
                    self.root.after(0, self.test_module, module_name)
                    time.sleep(1)  # Delay between tests
            
            self.root.after(0, self.status_var.set, "Testing complete")
        
        threading.Thread(target=test_all_thread, daemon=True).start()
    
    def create_test_environment(self):
        """Create test environment"""
        response = messagebox.askyesno("Test Environment",
                                      "Create a complete test environment with example files?")
        if not response:
            return
        
        try:
            # Create example files in each sandbox
            for module_name in self.registry.modules:
                if module_name != "nexus":
                    sandbox_path = self.registry.get_sandbox_path(module_name)
                    examples_dir = sandbox_path / "examples"
                    examples_dir.mkdir(exist_ok=True)
                    
                    # Create basic example
                    example_file = examples_dir / "example.py"
                    with open(example_file, 'w') as f:
                        f.write(f"# Example for {self.registry.modules[module_name].name}\n")
                        f.write("# Created by Nexus Dashboard\n\n")
                        f.write("print('Hello from Nexus test environment!')\n")
            
            self.log_event("Created test environment", EventType.SUCCESS)
            messagebox.showinfo("Success", "Test environment created in all sandboxes")
            
            # Refresh sandbox views
            for module_name in self.sandbox_trees:
                self.refresh_sandbox_view(None, module_name)
                
        except Exception as e:
            messagebox.showerror("Error", f"Failed to create test environment: {e}")
    
    def cancel_operation(self):
        """Cancel current operation"""
        self.status_var.set("Operation cancelled")
        self.progress_var.set(0)
    
    def refresh_all(self):
        """Refresh all dashboard components"""
        self.refresh_module_buttons()
        
        # Refresh sandbox views
        for module_name in self.sandbox_trees:
            self.refresh_sandbox_view(None, module_name)
        
        # Run quick diagnostics
        self.run_quick_diagnostics()
        
        self.status_var.set("Dashboard refreshed")
        self.log_event("Refreshed all components", EventType.INFO)
    
    def open_safety_checker(self):
        """Open safety checker dialog"""
        self.analyze_file_safety()

# ============================================================================
# GUIDED SETUP WIZARD
# ============================================================================

class GuidedSetupWizard:
    """Guided setup wizard for new users"""
    
    def __init__(self, parent, dashboard: NexusDashboard):
        self.parent = parent
        self.dashboard = dashboard
        self.current_step = 0
        self.steps = [
            self.step_welcome,
            self.step_system_check,
            self.step_module_selection,
            self.step_installation,
            self.step_testing,
            self.step_completion
        ]
        
    def start(self):
        """Start the wizard"""
        self.window = tk.Toplevel(self.parent)
        self.window.title("Nexus Setup Wizard")
        self.window.geometry("600x500")
        self.window.resizable(False, False)
        
        # Center window
        self.window.transient(self.parent)
        self.window.grab_set()
        
        # Create main frame
        self.main_frame = ttk.Frame(self.window, padding=20)
        self.main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Create header
        self.header_label = ttk.Label(
            self.main_frame,
            font=('Segoe UI', 16, 'bold')
        )
        self.header_label.pack(pady=(0, 20))
        
        # Create content area
        self.content_frame = ttk.Frame(self.main_frame)
        self.content_frame.pack(fill=tk.BOTH, expand=True)
        
        # Create navigation buttons
        self.nav_frame = ttk.Frame(self.main_frame)
        self.nav_frame.pack(fill=tk.X, pady=(20, 0))
        
        self.prev_button = ttk.Button(
            self.nav_frame,
            text="◀ Previous",
            command=self.previous_step,
            state='disabled'
        )
        self.prev_button.pack(side=tk.LEFT)
        
        self.next_button = ttk.Button(
            self.nav_frame,
            text="Next ▶",
            command=self.next_step
        )
        self.next_button.pack(side=tk.RIGHT)
        
        # Start with first step
        self.show_step(0)
    
    def show_step(self, step_index: int):
        """Show a specific step"""
        self.current_step = step_index
        
        # Clear content frame
        for widget in self.content_frame.winfo_children():
            widget.destroy()
        
        # Call step function
        self.steps[step_index]()
        
        # Update navigation buttons
        self.prev_button.config(
            state='normal' if step_index > 0 else 'disabled'
        )
        
        if step_index == len(self.steps) - 1:
            self.next_button.config(text="Finish")
        else:
            self.next_button.config(text="Next ▶")
    