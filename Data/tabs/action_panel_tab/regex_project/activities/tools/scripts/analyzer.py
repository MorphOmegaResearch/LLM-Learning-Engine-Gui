#!/usr/bin/env python3  # [MARK:{ ID:N001 }]  # [MARK:{ ID:N001 }]  # [MARK:{ ID:N001 }]  # [MARK:{ ID:N001 }]  # [MARK:{ ID:N001 }]  # [MARK:{ ID:N001 }]
"""
Comprehensive Code Analysis & Refactoring Tool
Analyzes argparse, tkinter, and shell executable relationships
Generates manifest, diffs, and refactoring patches
"""

import ast
import argparse
import tkinter as tk
from tkinter import ttk
import json
import difflib
import logging
import threading
import subprocess
import sys
import os
import inspect
import hashlib
import time
from datetime import datetime
from typing import Dict, List, Set, Tuple, Any, Optional
import py_compile
import tempfile
import shutil
from pathlib import Path

# Try to import optional dependencies
try:
    import black
    BLACK_AVAILABLE = True
except ImportError:
    BLACK_AVAILABLE = False
    print("[WARNING] black not installed, code formatting unavailable")

try:
    import pylint.lint
    PYLINT_AVAILABLE = True
except ImportError:
    PYLINT_AVAILABLE = False
    print("[WARNING] pylint not installed, linting unavailable")

try:
    import pyflakes.api
    import pyflakes.reporter
    PYFLAKES_AVAILABLE = True
except ImportError:
    PYFLAKES_AVAILABLE = False
    print("[WARNING] pyflakes not installed, syntax checking unavailable")

# #[EVENT] Setup logging and configuration
# NOTE: Logging setup moved to main() to prevent spam log files on import
logger = logging.getLogger(__name__)

class ManifestManager:
    """Manages manifest.json storage and session tracking"""
    
    def __init__(self, manifest_path: str = "manifests"):
        self.manifest_path = Path(manifest_path)
        self.manifest_path.mkdir(exist_ok=True)
        self.session_id = None
        self.current_manifest = {}
        
    def generate_session_id(self, source_file: str) -> str:
        """Generate unique session ID based on file and timestamp"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_hash = hashlib.md5(source_file.encode()).hexdigest()[:8]
        self.session_id = f"{timestamp}_{file_hash}"
        return self.session_id
    
    def save_manifest(self, manifest_data: Dict) -> str:
        """Save manifest to file"""
        if not self.session_id:
            self.session_id = self.generate_session_id(manifest_data.get("source_file", ""))
        
        manifest_file = self.manifest_path / f"manifest_{self.session_id}.json"
        self.current_manifest = manifest_data
        self.current_manifest["session_id"] = self.session_id
        self.current_manifest["timestamp"] = datetime.now().isoformat()
        
        with open(manifest_file, 'w') as f:
            json.dump(self.current_manifest, f, indent=2, default=str)
        
        logger.info(f"[EVENT] Manifest saved: {manifest_file}")
        return str(manifest_file)
    
    def load_manifest(self, session_id: str) -> Optional[Dict]:
        """Load manifest by session ID"""
        manifest_file = self.manifest_path / f"manifest_{session_id}.json"
        if manifest_file.exists():
            with open(manifest_file, 'r') as f:
                self.current_manifest = json.load(f)
            logger.info(f"[EVENT] Manifest loaded: {manifest_file}")
            return self.current_manifest
        return None
    
    def get_manifest_delta(self, old_session_id: str, new_manifest: Dict) -> Dict:
        """Calculate delta between two manifests"""
        old_manifest = self.load_manifest(old_session_id)
        if not old_manifest:
            return new_manifest
        
        delta = {
            "session_id": new_manifest.get("session_id"),
            "timestamp": new_manifest.get("timestamp"),
            "changes": {}
        }
        
        # Compare sections
        for section in ["argparse", "tkinter", "shell", "imports", "functions"]:
            if section in old_manifest and section in new_manifest:
                old_set = set(str(item) for item in old_manifest[section])
                new_set = set(str(item) for item in new_manifest[section])
                delta["changes"][section] = {
                    "added": list(new_set - old_set),
                    "removed": list(old_set - new_set),
                    "unchanged": list(old_set & new_set)
                }
        
        return delta

# #[EVENT] AST Analysis Classes
class ArgParseAnalyzer(ast.NodeVisitor):
    """Analyzes argparse usage in Python code"""
    
    def __init__(self):
        self.arguments = []
        self.parsers = []
        self.subparsers = []
        self.current_parser = None
        
    def visit_Call(self, node):
        """Detect argparse method calls"""
        if isinstance(node.func, ast.Attribute):
            # Check for add_argument calls
            if node.func.attr == 'add_argument':
                arg_info = self._extract_argument_info(node)
                if arg_info:
                    self.arguments.append(arg_info)
                    logger.info(f"[EVENT] Found argparse argument: {arg_info}")
            
            # Check for ArgumentParser creation
            elif node.func.attr == 'ArgumentParser':
                parser_info = self._extract_parser_info(node)
                if parser_info:
                    self.parsers.append(parser_info)
                    logger.info(f"[EVENT] Found ArgumentParser: {parser_info}")
            
            # Check for subparsers
            elif node.func.attr == 'add_subparsers':
                self.subparsers.append({
                    "line": node.lineno,
                    "parser": self.current_parser
                })
        
        self.generic_visit(node)
    
    def _extract_argument_info(self, node) -> Dict:
        """Extract information from add_argument call"""
        arg_info = {"flags": [], "help": "", "default": None, "type": None, "required": False}
        
        for arg in node.args:
            if isinstance(arg, ast.Str):
                arg_info["flags"].append(arg.s)
        
        for keyword in node.keywords:
            if keyword.arg == "help" and isinstance(keyword.value, ast.Str):
                arg_info["help"] = keyword.value.s
            elif keyword.arg == "default":
                arg_info["default"] = self._extract_value(keyword.value)
            elif keyword.arg == "type":
                arg_info["type"] = self._extract_type(keyword.value)
            elif keyword.arg == "required":
                arg_info["required"] = self._extract_value(keyword.value)
        
        return arg_info
    
    def _extract_parser_info(self, node) -> Dict:
        """Extract parser configuration"""
        parser_info = {"line": node.lineno, "description": "", "prog": ""}
        
        for keyword in node.keywords:
            if keyword.arg == "description" and isinstance(keyword.value, ast.Str):
                parser_info["description"] = keyword.value.s
            elif keyword.arg == "prog" and isinstance(keyword.value, ast.Str):
                parser_info["prog"] = keyword.value.s
        
        return parser_info
    
    def _extract_value(self, node):
        """Extract value from AST node"""
        if isinstance(node, ast.Str):
            return node.s
        elif isinstance(node, ast.Num):
            return node.n
        elif isinstance(node, ast.NameConstant):
            return node.value
        elif isinstance(node, ast.Name):
            return node.id
        return None
    
    def _extract_type(self, node):
        """Extract type information"""
        if isinstance(node, ast.Name):
            return node.id
        return None

class TkinterAnalyzer(ast.NodeVisitor):
    """Analyzes tkinter usage in Python code"""
    
    def __init__(self):
        self.widgets = []
        self.variables = []
        self.bindings = []
        self.layouts = []
        
    def visit_Call(self, node):
        """Detect tkinter widget creation and configuration"""
        if isinstance(node.func, ast.Attribute):
            # Widget creation (Button, Label, Entry, etc.)
            widget_types = ['Button', 'Label', 'Entry', 'Text', 'Frame', 
                          'Canvas', 'Listbox', 'Scrollbar', 'Scale', 'Checkbutton']
            
            if node.func.attr in widget_types:
                widget_info = self._extract_widget_info(node)
                if widget_info:
                    self.widgets.append(widget_info)
                    logger.info(f"[EVENT] Found tkinter widget: {widget_info}")
            
            # Variable classes
            elif node.func.attr in ['StringVar', 'IntVar', 'DoubleVar', 'BooleanVar']:
                var_info = self._extract_variable_info(node)
                if var_info:
                    self.variables.append(var_info)
            
            # Bindings
            elif node.func.attr == 'bind':
                binding_info = self._extract_binding_info(node)
                if binding_info:
                    self.bindings.append(binding_info)
            
            # Layout methods
            elif node.func.attr in ['pack', 'grid', 'place']:
                layout_info = self._extract_layout_info(node)
                if layout_info:
                    self.layouts.append(layout_info)
        
        self.generic_visit(node)
    
    def _extract_widget_info(self, node) -> Dict:
        """Extract widget creation information"""
        widget_info = {
            "type": node.func.attr,
            "line": node.lineno,
            "parent": None,
            "options": {}
        }
        
        # Get parent from first arg if it exists
        if node.args:
            parent = self._extract_value(node.args[0])
            if parent:
                widget_info["parent"] = parent
        
        # Extract keyword arguments
        for keyword in node.keywords:
            widget_info["options"][keyword.arg] = self._extract_value(keyword.value)
        
        return widget_info
    
    def _extract_variable_info(self, node) -> Dict:
        """Extract tkinter variable information"""
        return {
            "type": node.func.attr,
            "line": node.lineno,
            "value": self._extract_value(node.args[0]) if node.args else None
        }
    
    def _extract_binding_info(self, node) -> Dict:
        """Extract event binding information"""
        if len(node.args) >= 2:
            return {
                "event": self._extract_value(node.args[0]),
                "callback": self._extract_value(node.args[1]),
                "line": node.lineno
            }
        return None
    
    def _extract_layout_info(self, node) -> Dict:
        """Extract layout management information"""
        layout_info = {
            "method": node.func.attr,
            "line": node.lineno,
            "options": {}
        }
        
        for keyword in node.keywords:
            layout_info["options"][keyword.arg] = self._extract_value(keyword.value)
        
        return layout_info
    
    def _extract_value(self, node):
        """Extract value from AST node"""
        if isinstance(node, ast.Str):
            return node.s
        elif isinstance(node, ast.Num):
            return node.n
        elif isinstance(node, ast.NameConstant):
            return node.value
        elif isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            return f"{node.value.id}.{node.attr}"
        return None

class ShellExecutableAnalyzer(ast.NodeVisitor):
    """Analyzes shell executable and function calls"""
    
    def __init__(self):
        self.functions = []
        self.subprocess_calls = []
        self.os_calls = []
        self.system_calls = []
        
    def visit_FunctionDef(self, node):
        """Analyze function definitions"""
        func_info = {
            "name": node.name,
            "line": node.lineno,
            "args": [arg.arg for arg in node.args.args],
            "docstring": ast.get_docstring(node),
            "calls": []
        }
        
        # Find calls within function
        for child in ast.walk(node):
            if isinstance(child, ast.Call):
                call_info = self._extract_call_info(child)
                if call_info:
                    func_info["calls"].append(call_info)
        
        self.functions.append(func_info)
        logger.info(f"[EVENT] Found function: {func_info['name']}")
        self.generic_visit(node)
    
    def visit_Call(self, node):
        """Detect subprocess and system calls"""
        call_info = self._extract_call_info(node)
        if call_info:
            if call_info["module"] == "subprocess":
                self.subprocess_calls.append(call_info)
                logger.info(f"[EVENT] Found subprocess call: {call_info}")
            elif call_info["module"] == "os":
                self.os_calls.append(call_info)
            elif call_info["module"] == "sys":
                self.system_calls.append(call_info)
        
        self.generic_visit(node)
    
    def _extract_call_info(self, node) -> Dict:
        """Extract information about a function/method call"""
        if isinstance(node.func, ast.Attribute):
            # Method call like subprocess.run
            module = self._get_module_name(node.func.value)
            return {
                "line": node.lineno,
                "module": module,
                "function": node.func.attr,
                "args": [self._extract_value(arg) for arg in node.args],
                "full_call": self._node_to_string(node)
            }
        elif isinstance(node.func, ast.Name):
            # Direct function call
            return {
                "line": node.lineno,
                "module": "__main__",
                "function": node.func.id,
                "args": [self._extract_value(arg) for arg in node.args],
                "full_call": self._node_to_string(node)
            }
        return None
    
    def _get_module_name(self, node):
        """Extract module name from AST node"""
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            return self._get_module_name(node.value)
        return "unknown"
    
    def _extract_value(self, node):
        """Extract value from AST node"""
        if isinstance(node, ast.Str):
            return node.s
        elif isinstance(node, ast.Num):
            return node.n
        elif isinstance(node, ast.NameConstant):
            return node.value
        elif isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.List):
            return [self._extract_value(e) for e in node.elts]
        elif isinstance(node, ast.Dict):
            return {self._extract_value(k): self._extract_value(v) 
                   for k, v in zip(node.keys, node.values)}
        return None
    
    def _node_to_string(self, node):
        """Convert AST node to string representation"""
        try:
            return ast.unparse(node) if hasattr(ast, 'unparse') else str(node)
        except:
            return str(node)

class ImportAnalyzer(ast.NodeVisitor):
    """Analyzes import statements and hierarchy"""
    
    def __init__(self):
        self.imports = []
        self.from_imports = []
        
    def visit_Import(self, node):
        """Process import statements"""
        for alias in node.names:
            self.imports.append({
                "module": alias.name,
                "alias": alias.asname,
                "line": node.lineno
            })
            logger.info(f"[EVENT] Found import: {alias.name}")
        self.generic_visit(node)
    
    def visit_ImportFrom(self, node):
        """Process from ... import statements"""
        module = node.module or ""
        for alias in node.names:
            self.from_imports.append({
                "module": module,
                "name": alias.name,
                "alias": alias.asname,
                "line": node.lineno,
                "level": node.level
            })
            logger.info(f"[EVENT] Found from import: {module}.{alias.name}")
        self.generic_visit(node)

# #[EVENT] Main Analysis Engine
class CodeAnalyzer:
    """Main analysis engine coordinating all analyzers"""
    
    def __init__(self, source_file: str):
        self.source_file = source_file
        self.source_code = ""
        self.tree = None
        self.manifest = {}
        self.manifest_manager = ManifestManager()
        
        # Initialize analyzers
        self.argparse_analyzer = ArgParseAnalyzer()
        self.tkinter_analyzer = TkinterAnalyzer()
        self.shell_analyzer = ShellExecutableAnalyzer()
        self.import_analyzer = ImportAnalyzer()
        
    def load_source(self):
        """Load and parse source code"""
        logger.info(f"[EVENT] Loading source file: {self.source_file}")
        with open(self.source_file, 'r') as f:
            self.source_code = f.read()
        
        self.tree = ast.parse(self.source_code)
        logger.info(f"[EVENT] AST parsed successfully")
    
    def analyze(self):
        """Run all analyses"""
        logger.info("[EVENT] Starting comprehensive analysis")
        
        # Run analyzers
        analyzers = [
            (self.import_analyzer, "Import Analysis"),
            (self.argparse_analyzer, "ArgParse Analysis"),
            (self.tkinter_analyzer, "Tkinter Analysis"),
            (self.shell_analyzer, "Shell Executable Analysis"),
        ]
        
        for analyzer, name in analyzers:
            logger.info(f"[EVENT] Running {name}")
            analyzer.visit(self.tree)
        
        # Build manifest
        self.manifest = {
            "source_file": self.source_file,
            "session_id": self.manifest_manager.generate_session_id(self.source_file),
            "imports": {
                "imports": self.import_analyzer.imports,
                "from_imports": self.import_analyzer.from_imports
            },
            "argparse": {
                "arguments": self.argparse_analyzer.arguments,
                "parsers": self.argparse_analyzer.parsers,
                "subparsers": self.argparse_analyzer.subparsers
            },
            "tkinter": {
                "widgets": self.tkinter_analyzer.widgets,
                "variables": self.tkinter_analyzer.variables,
                "bindings": self.tkinter_analyzer.bindings,
                "layouts": self.tkinter_analyzer.layouts
            },
            "shell": {
                "functions": self.shell_analyzer.functions,
                "subprocess_calls": self.shell_analyzer.subprocess_calls,
                "os_calls": self.shell_analyzer.os_calls,
                "system_calls": self.shell_analyzer.system_calls
            }
        }
        
        # Analyze connections and disconnections
        self._analyze_connections()
        
        logger.info("[EVENT] Analysis completed")
        return self.manifest
    
    def _analyze_connections(self):
        """Analyze connections between argparse, tkinter, and shell"""
        connections = []
        disconnections = []
        
        # Map argparse arguments to tkinter widgets
        for arg in self.argparse_analyzer.arguments:
            connected = False
            for widget in self.tkinter_analyzer.widgets:
                # Check if widget text/name matches argument help/flag
                widget_text = widget["options"].get("text", "")
                if any(flag in widget_text for flag in arg["flags"]):
                    connections.append({
                        "type": "argparse->tkinter",
                        "argparse": arg["flags"],
                        "tkinter": f"{widget['type']} (text: {widget_text})",
                        "line": widget["line"]
                    })
                    connected = True
            
            # Check connection to shell functions
            for func in self.shell_analyzer.functions:
                func_name_lower = func["name"].lower()
                for flag in arg["flags"]:
                    flag_clean = flag.strip("-").lower()
                    if flag_clean in func_name_lower:
                        connections.append({
                            "type": "argparse->shell",
                            "argparse": arg["flags"],
                            "shell": func["name"],
                            "line": func["line"]
                        })
                        connected = True
            
            if not connected:
                disconnections.append({
                    "type": "argparse",
                    "element": arg["flags"],
                    "reason": "No matching tkinter widget or shell function"
                })
        
        # Map tkinter events to shell functions
        for binding in self.tkinter_analyzer.bindings:
            connected = False
            callback = binding.get("callback", "")
            for func in self.shell_analyzer.functions:
                if func["name"] == callback:
                    connections.append({
                        "type": "tkinter->shell",
                        "tkinter": f"{binding['event']} -> {callback}",
                        "shell": func["name"],
                        "line": binding["line"]
                    })
                    connected = True
            
            if not connected and callback:
                disconnections.append({
                    "type": "tkinter",
                    "element": f"Binding: {binding['event']} -> {callback}",
                    "reason": "Callback function not found"
                })
        
        self.manifest["connections"] = connections
        self.manifest["disconnections"] = disconnections
        
        logger.info(f"[EVENT] Found {len(connections)} connections and {len(disconnections)} disconnections")
    
    def calculate_efficiency_score(self):
        """Calculate efficiency score for executable chains"""
        score = 0
        max_score = 100
        
        # Score based on connections
        connections = self.manifest.get("connections", [])
        disconnections = self.manifest.get("disconnections", [])
        
        total_elements = len(connections) + len(disconnections)
        if total_elements > 0:
            connectivity_ratio = len(connections) / total_elements
        else:
            connectivity_ratio = 1
        
        # Score based on code structure
        functions = self.manifest["shell"]["functions"]
        if functions:
            avg_args = sum(len(func["args"]) for func in functions) / len(functions)
            # Lower average args is generally better (simpler interface)
            args_score = max(0, 100 - (avg_args * 10))
        else:
            args_score = 50
        
        # Combine scores
        score = int((connectivity_ratio * 60) + (args_score * 0.4))
        
        self.manifest["efficiency_score"] = {
            "overall": score,
            "connectivity": int(connectivity_ratio * 100),
            "complexity": int(args_score),
            "breakpoints": len(disconnections)
        }
        
        return score
    
    def generate_refactor_suggestions(self):
        """Generate refactoring suggestions based on analysis"""
        suggestions = []
        
        # Suggest consolidation for disconnections
        for disc in self.manifest.get("disconnections", []):
            if disc["type"] == "argparse":
                suggestions.append({
                    "type": "consolidation",
                    "description": f"Connect argparse argument {disc['element']} to tkinter or shell function",
                    "priority": "medium",
                    "action": "Add corresponding tkinter widget or shell function call"
                })
        
        # Suggest removing redundant imports
        imports = self.manifest["imports"]["imports"]
        import_modules = [imp["module"] for imp in imports]
        
        # Check for unused imports by looking at actual usage
        # This is simplified - a real implementation would track usage
        if len(import_modules) > len(set(import_modules)):
            suggestions.append({
                "type": "optimization",
                "description": "Potential redundant imports detected",
                "priority": "low",
                "action": "Review and remove unused imports"
            })
        
        # Suggest function consolidation
        functions = self.manifest["shell"]["functions"]
        similar_functions = {}
        for func in functions:
            key = f"{len(func['args'])}_{func.get('docstring', '')[:20]}"
            similar_functions.setdefault(key, []).append(func["name"])
        
        for key, func_list in similar_functions.items():
            if len(func_list) > 1:
                suggestions.append({
                    "type": "consolidation",
                    "description": f"Similar functions detected: {', '.join(func_list)}",
                    "priority": "high",
                    "action": "Consider merging into a single parameterized function"
                })
        
        self.manifest["suggestions"] = suggestions
        return suggestions

# #[EVENT] Code Quality Checkers
class CodeQualityChecker:
    """Run various code quality checks"""
    
    def __init__(self, source_file: str):
        self.source_file = source_file
        self.results = {}
        
    def run_all_checks(self):
        """Run all available code quality checks"""
        logger.info("[EVENT] Running code quality checks")
        
        checks = [
            self.check_syntax,
            self.check_compile,
        ]
        
        if PYFLAKES_AVAILABLE:
            checks.append(self.check_pyflakes)
        
        if PYLINT_AVAILABLE:
            checks.append(self.check_pylint)
        
        # Run checks
        for check_func in checks:
            check_name = check_func.__name__.replace("check_", "")
            try:
                logger.info(f"[EVENT] Running {check_name} check")
                self.results[check_name] = check_func()
            except Exception as e:
                self.results[check_name] = {"error": str(e)}
                logger.error(f"[EVENT] Check {check_name} failed: {e}")
        
        return self.results
    
    def check_syntax(self):
        """Check Python syntax"""
        try:
            with open(self.source_file, 'r') as f:
                source = f.read()
            ast.parse(source)
            return {"status": "passed", "issues": []}
        except SyntaxError as e:
            return {
                "status": "failed",
                "issues": [{
                    "line": e.lineno,
                    "message": e.msg,
                    "severity": "error"
                }]
            }
    
    def check_compile(self):
        """Check if code can be compiled"""
        try:
            with tempfile.NamedTemporaryFile(suffix='.pyc', delete=False) as tmp:
                tmp_path = tmp.name
            
            py_compile.compile(self.source_file, cfile=tmp_path)
            os.unlink(tmp_path)
            return {"status": "passed", "issues": []}
        except py_compile.PyCompileError as e:
            return {
                "status": "failed",
                "issues": [{
                    "line": e.lineno,
                    "message": e.msg,
                    "severity": "error"
                }]
            }
    
    def check_pyflakes(self):
        """Run pyflakes check"""
        if not PYFLAKES_AVAILABLE:
            return {"status": "skipped", "reason": "pyflakes not available"}
        
        class CollectorReporter(pyflakes.reporter.Reporter):
            def __init__(self):
                self.issues = []
            
            def unexpectedError(self, filename, msg):
                self.issues.append({"type": "error", "message": msg})
            
            def syntaxError(self, filename, msg, lineno, offset, text):
                self.issues.append({
                    "type": "syntax",
                    "line": lineno,
                    "message": msg
                })
            
            def flake(self, message):
                self.issues.append({
                    "type": "flake",
                    "line": message.lineno,
                    "message": message.message % message.message_args
                })
        
        reporter = CollectorReporter()
        try:
            pyflakes.api.checkFile(self.source_file, reporter)
            return {
                "status": "passed" if not reporter.issues else "warnings",
                "issues": reporter.issues
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}
    
    def check_pylint(self):
        """Run pylint check"""
        if not PYLINT_AVAILABLE:
            return {"status": "skipped", "reason": "pylint not available"}
        
        try:
            # Run pylint with minimal output
            from pylint import epylint as lint
            pylint_output = lint.py_run(self.source_file, return_std=True)
            
            # Parse output would go here
            # This is simplified - real implementation would parse pylint output
            return {
                "status": "completed",
                "note": "Pylint check completed (output parsing not implemented)"
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}

# #[EVENT] Diff and Patch Generator
class DiffPatchGenerator:
    """Generate diffs and patches based on analysis"""
    
    def __init__(self, original_file: str, manifest: Dict):
        self.original_file = original_file
        self.manifest = manifest
        self.diffs = []
        self.patches = []
        
    def generate_diffs(self, reference_file: str = None):
        """Generate diffs between current and reference file"""
        with open(self.original_file, 'r') as f:
            original_lines = f.readlines()
        
        if reference_file and os.path.exists(reference_file):
            with open(reference_file, 'r') as f:
                reference_lines = f.readlines()
            
            diff = list(difflib.unified_diff(
                reference_lines, original_lines,
                fromfile=reference_file, tofile=self.original_file,
                lineterm=''
            ))
            self.diffs = diff
            
            logger.info(f"[EVENT] Generated diff with {len(diff)} lines")
        
        return self.diffs
    
    def generate_patch(self, suggestions: List[Dict]) -> str:
        """Generate patch based on refactoring suggestions"""
        patch_content = []
        patch_content.append("# Refactoring Patch")
        patch_content.append(f"# Generated: {datetime.now().isoformat()}")
        patch_content.append(f"# Session: {self.manifest.get('session_id', 'unknown')}")
        patch_content.append("")
        
        for i, suggestion in enumerate(suggestions, 1):
            patch_content.append(f"# Suggestion {i}: {suggestion['type'].upper()}")
            patch_content.append(f"# Priority: {suggestion['priority']}")
            patch_content.append(f"# {suggestion['description']}")
            patch_content.append(f"# Action: {suggestion['action']}")
            
            # Generate example patch based on suggestion type
            if suggestion["type"] == "consolidation" and "argparse" in suggestion["description"]:
                patch_content.extend(self._generate_argparse_patch(suggestion))
            elif suggestion["type"] == "consolidation" and "functions" in suggestion["description"]:
                patch_content.extend(self._generate_function_patch(suggestion))
            
            patch_content.append("")
        
        self.patches = patch_content
        return "\n".join(patch_content)
    
    def _generate_argparse_patch(self, suggestion: Dict) -> List[str]:
        """Generate example argparse consolidation patch"""
        return [
            "# Example argparse-tkinter bridge:",
            "def connect_argparse_to_tkinter(arg_name, tk_var):",
            "    \"\"\"Connect argparse argument to tkinter variable\"\"\"",
            "    # Implementation would map argparse value to tkinter widget",
            "    pass",
            ""
        ]
    
    def _generate_function_patch(self, suggestion: Dict) -> List[str]:
        """Generate example function consolidation patch"""
        return [
            "# Example function consolidation:",
            "def unified_function(*args, operation=None, **kwargs):",
            "    \"\"\"Unified function handling multiple operations\"\"\"",
            "    if operation == 'process_a':",
            "        return process_a(*args, **kwargs)",
            "    elif operation == 'process_b':",
            "        return process_b(*args, **kwargs)",
            "    else:",
            "        raise ValueError(f\"Unknown operation: {operation}\")",
            ""
        ]
    
    def save_patch(self, patch_file: str = None):
        """Save patch to file"""
        if not patch_file:
            session_id = self.manifest.get('session_id', 'unknown')
            patch_file = f"patch_{session_id}.diff"
        
        with open(patch_file, 'w') as f:
            f.write("\n".join(self.patches))
        
        logger.info(f"[EVENT] Patch saved to: {patch_file}")
        return patch_file

# #[EVENT] GUI Viewer
class AnalysisViewer:
    """Tkinter GUI to view analysis results"""
    
    def __init__(self, manifest: Dict):
        self.manifest = manifest
        self.root = None
        
    def show(self):
        """Display the analysis viewer GUI"""
        self.root = tk.Tk()
        self.root.title(f"Code Analysis - Session: {self.manifest.get('session_id', 'Unknown')}")
        self.root.geometry("1200x800")
        
        # Create notebook for tabs
        notebook = ttk.Notebook(self.root)
        notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Create tabs
        tabs = [
            ("Overview", self._create_overview_tab),
            ("Imports", self._create_imports_tab),
            ("ArgParse", self._create_argparse_tab),
            ("Tkinter", self._create_tkinter_tab),
            ("Shell", self._create_shell_tab),
            ("Connections", self._create_connections_tab),
            ("Suggestions", self._create_suggestions_tab),
        ]
        
        for tab_name, tab_func in tabs:
            frame = ttk.Frame(notebook)
            notebook.add(frame, text=tab_name)
            tab_func(frame)
        
        # Status bar
        status_frame = ttk.Frame(self.root)
        status_frame.pack(fill=tk.X, padx=5, pady=2)
        
        score = self.manifest.get("efficiency_score", {}).get("overall", 0)
        status_text = f"Efficiency Score: {score}/100 | Breakpoints: {self.manifest.get('efficiency_score', {}).get('breakpoints', 0)}"
        ttk.Label(status_frame, text=status_text).pack(side=tk.LEFT)
        
        ttk.Button(self.root, text="Export JSON", command=self._export_json).pack(pady=5)
        ttk.Button(self.root, text="Close", command=self.root.destroy).pack(pady=5)
        
        self.root.mainloop()
    
    def _create_overview_tab(self, parent):
        """Create overview tab"""
        text = tk.Text(parent, wrap=tk.WORD)
        scrollbar = ttk.Scrollbar(parent, orient=tk.VERTICAL, command=text.yview)
        text.configure(yscrollcommand=scrollbar.set)
        
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        text.pack(fill=tk.BOTH, expand=True)
        
        overview = [
            f"Source File: {self.manifest.get('source_file', 'Unknown')}",
            f"Session ID: {self.manifest.get('session_id', 'Unknown')}",
            f"Timestamp: {self.manifest.get('timestamp', 'Unknown')}",
            "",
            "=== Summary ===",
            f"Imports: {len(self.manifest['imports']['imports'])} direct, {len(self.manifest['imports']['from_imports'])} from imports",
            f"ArgParse Arguments: {len(self.manifest['argparse']['arguments'])}",
            f"Tkinter Widgets: {len(self.manifest['tkinter']['widgets'])}",
            f"Shell Functions: {len(self.manifest['shell']['functions'])}",
            f"Connections: {len(self.manifest.get('connections', []))}",
            f"Disconnections: {len(self.manifest.get('disconnections', []))}",
            f"Suggestions: {len(self.manifest.get('suggestions', []))}",
            "",
            "=== Efficiency Score ===",
        ]
        
        efficiency = self.manifest.get("efficiency_score", {})
        for key, value in efficiency.items():
            overview.append(f"  {key}: {value}")
        
        text.insert(tk.END, "\n".join(overview))
        text.config(state=tk.DISABLED)
    
    def _create_imports_tab(self, parent):
        """Create imports tab"""
        self._create_list_tab(parent, "imports")
    
    def _create_argparse_tab(self, parent):
        """Create argparse tab"""
        self._create_list_tab(parent, "argparse")
    
    def _create_tkinter_tab(self, parent):
        """Create tkinter tab"""
        self._create_list_tab(parent, "tkinter")
    
    def _create_shell_tab(self, parent):
        """Create shell tab"""
        self._create_list_tab(parent, "shell")
    
    def _create_connections_tab(self, parent):
        """Create connections tab"""
        frame = ttk.Frame(parent)
        frame.pack(fill=tk.BOTH, expand=True)
        
        # Connections
        conn_label = ttk.LabelFrame(frame, text="Connections")
        conn_label.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        conn_text = tk.Text(conn_label, height=10)
        conn_scroll = ttk.Scrollbar(conn_label, orient=tk.VERTICAL, command=conn_text.yview)
        conn_text.configure(yscrollcommand=conn_scroll.set)
        
        conn_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        conn_text.pack(fill=tk.BOTH, expand=True)
        
        for conn in self.manifest.get("connections", []):
            conn_text.insert(tk.END, f"{conn['type']}: {conn.get('argparse', conn.get('tkinter', ''))} -> {conn.get('shell', '')}\n")
        
        # Disconnections
        disc_label = ttk.LabelFrame(frame, text="Disconnections (Breakpoints)")
        disc_label.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        disc_text = tk.Text(disc_label, height=10)
        disc_scroll = ttk.Scrollbar(disc_label, orient=tk.VERTICAL, command=disc_text.yview)
        disc_text.configure(yscrollcommand=disc_scroll.set)
        
        disc_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        disc_text.pack(fill=tk.BOTH, expand=True)
        
        for disc in self.manifest.get("disconnections", []):
            disc_text.insert(tk.END, f"{disc['type']}: {disc['element']} - {disc['reason']}\n")
    
    def _create_suggestions_tab(self, parent):
        """Create suggestions tab"""
        self._create_list_tab(parent, "suggestions")
    
    def _create_list_tab(self, parent, section: str):
        """Generic list tab creator"""
        text = tk.Text(parent, wrap=tk.WORD)
        scrollbar = ttk.Scrollbar(parent, orient=tk.VERTICAL, command=text.yview)
        text.configure(yscrollcommand=scrollbar.set)
        
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        text.pack(fill=tk.BOTH, expand=True)
        
        if section == "imports":
            content = []
            for imp in self.manifest["imports"]["imports"]:
                alias = f" as {imp['alias']}" if imp['alias'] else ""
                content.append(f"import {imp['module']}{alias}")
            
            for imp in self.manifest["imports"]["from_imports"]:
                alias = f" as {imp['alias']}" if imp['alias'] else ""
                content.append(f"from {imp['module']} import {imp['name']}{alias}")
        
        elif section == "argparse":
            content = []
            for arg in self.manifest["argparse"]["arguments"]:
                content.append(f"Flags: {arg['flags']}")
                if arg['help']:
                    content.append(f"  Help: {arg['help']}")
                if arg['type']:
                    content.append(f"  Type: {arg['type']}")
                content.append("")
        
        elif section == "tkinter":
            content = []
            for widget in self.manifest["tkinter"]["widgets"]:
                content.append(f"{widget['type']} (line {widget['line']})")
                for key, value in widget["options"].items():
                    content.append(f"  {key}: {value}")
                content.append("")
        
        elif section == "shell":
            content = []
            for func in self.manifest["shell"]["functions"]:
                content.append(f"{func['name']}({', '.join(func['args'])})")
                if func['docstring']:
                    content.append(f"  Doc: {func['docstring'][:50]}...")
                content.append(f"  Line: {func['line']}")
                content.append("")
        
        elif section == "suggestions":
            content = []
            for i, suggestion in enumerate(self.manifest.get("suggestions", []), 1):
                content.append(f"{i}. [{suggestion['priority'].upper()}] {suggestion['type']}")
                content.append(f"   {suggestion['description']}")
                content.append(f"   Action: {suggestion['action']}")
                content.append("")
        
        text.insert(tk.END, "\n".join(content))
        text.config(state=tk.DISABLED)
    
    def _export_json(self):
        """Export manifest as JSON"""
        filename = f"manifest_{self.manifest.get('session_id', 'export')}.json"
        with open(filename, 'w') as f:
            json.dump(self.manifest, f, indent=2, default=str)
        logger.info(f"[EVENT] Manifest exported to {filename}")

# #[EVENT] Main Application
class CodeAnalysisApp:
    """Main application orchestrating all components"""
    
    def __init__(self):
        self.parser = self._create_argparse()
        self.args = None
        self.manifest_manager = ManifestManager()
        self.current_manifest = None
        
    def _create_argparse(self):
        """Create command line argument parser"""
        parser = argparse.ArgumentParser(
            description="Comprehensive Code Analysis & Refactoring Tool",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
Examples:
  %(prog)s analyze my_script.py
  %(prog)s analyze my_script.py --view
  %(prog)s diff --session 20240101_120000_abc123
  %(prog)s patch --session 20240101_120000_abc123 --apply
  
Code Line References:
  #[EVENT] markers indicate major processing steps in the code
  Check the log file for detailed progression tracking
            """
        )
        
        subparsers = parser.add_subparsers(dest="command", help="Command")
        
        # Analyze command
        analyze_parser = subparsers.add_parser("analyze", help="Analyze a Python file")
        analyze_parser.add_argument("file", help="Python file to analyze")
        analyze_parser.add_argument("--view", action="store_true", help="Open GUI viewer")
        analyze_parser.add_argument("--checks", action="store_true", help="Run code quality checks")
        analyze_parser.add_argument("--save", action="store_true", help="Save manifest")
        
        # Diff command
        diff_parser = subparsers.add_parser("diff", help="Generate diffs")
        diff_parser.add_argument("--session", help="Session ID to compare")
        diff_parser.add_argument("--reference", help="Reference file for diff")
        
        # Patch command
        patch_parser = subparsers.add_parser("patch", help="Generate or apply patches")
        patch_parser.add_argument("--session", help="Session ID for patch generation")
        patch_parser.add_argument("--apply", action="store_true", help="Apply patch")
        patch_parser.add_argument("--patch-file", help="Patch file to apply")
        
        # View command
        view_parser = subparsers.add_parser("view", help="View manifest")
        view_parser.add_argument("--session", help="Session ID to view")
        
        # Summary command
        summary_parser = subparsers.add_parser("summary", help="Show summary")
        summary_parser.add_argument("--session", help="Session ID for summary")
        summary_parser.add_argument("--latest", action="store_true", help="Use latest manifest")
        
        return parser
    
    def run(self):
        """Main entry point"""
        self.args = self.parser.parse_args()
        
        if not self.args.command:
            self.parser.print_help()
            return
        
        # Dispatch to appropriate handler
        handler_name = f"handle_{self.args.command}"
        if hasattr(self, handler_name):
            getattr(self, handler_name)()
        else:
            logger.error(f"Unknown command: {self.args.command}")
    
    def handle_analyze(self):
        """Handle analyze command"""
        logger.info(f"[EVENT] Starting analysis of {self.args.file}")
        
        if not os.path.exists(self.args.file):
            logger.error(f"File not found: {self.args.file}")
            return
        
        # Run analysis
        analyzer = CodeAnalyzer(self.args.file)
        analyzer.load_source()
        manifest = analyzer.analyze()
        
        # Calculate efficiency score
        score = analyzer.calculate_efficiency_score()
        logger.info(f"[EVENT] Efficiency score: {score}/100")
        
        # Generate suggestions
        suggestions = analyzer.generate_refactor_suggestions()
        logger.info(f"[EVENT] Generated {len(suggestions)} suggestions")
        
        # Run code quality checks if requested
        if self.args.checks:
            logger.info("[EVENT] Running code quality checks")
            checker = CodeQualityChecker(self.args.file)
            check_results = checker.run_all_checks()
            manifest["quality_checks"] = check_results
        
        # Save manifest if requested
        if self.args.save:
            manifest_file = self.manifest_manager.save_manifest(manifest)
            logger.info(f"[EVENT] Manifest saved to {manifest_file}")
        
        self.current_manifest = manifest
        
        # Show GUI if requested
        if self.args.view:
            logger.info("[EVENT] Launching GUI viewer")
            viewer = AnalysisViewer(manifest)
            viewer.show()
        else:
            # Print summary
            self._print_summary(manifest)
    
    def handle_diff(self):
        """Handle diff command"""
        if self.args.session:
            manifest = self.manifest_manager.load_manifest(self.args.session)
            if not manifest:
                logger.error(f"Session not found: {self.args.session}")
                return
            
            source_file = manifest.get("source_file")
            if source_file and os.path.exists(source_file):
                diff_gen = DiffPatchGenerator(source_file, manifest)
                diffs = diff_gen.generate_diffs(self.args.reference)
                
                print("\n=== DIFF ===\n")
                for line in diffs:
                    print(line)
            else:
                logger.error("Source file not found in manifest")
        else:
            logger.error("Session ID required for diff")
    
    def handle_patch(self):
        """Handle patch command"""
        if self.args.session:
            manifest = self.manifest_manager.load_manifest(self.args.session)
            if not manifest:
                logger.error(f"Session not found: {self.args.session}")
                return
            
            suggestions = manifest.get("suggestions", [])
            if not suggestions:
                logger.warning("No suggestions found in manifest")
                return
            
            source_file = manifest.get("source_file")
            if not source_file or not os.path.exists(source_file):
                logger.error("Source file not found")
                return
            
            diff_gen = DiffPatchGenerator(source_file, manifest)
            patch = diff_gen.generate_patch(suggestions)
            
            print("\n=== PATCH ===\n")
            print(patch)
            
            if self.args.apply:
                logger.warning("Patch application not fully implemented - this is a preview")
                # In a full implementation, this would apply the patch
            else:
                patch_file = diff_gen.save_patch(self.args.patch_file)
                logger.info(f"Patch saved to {patch_file}")
        else:
            logger.error("Session ID required for patch")
    
    def handle_view(self):
        """Handle view command"""
        if self.args.session:
            manifest = self.manifest_manager.load_manifest(self.args.session)
            if manifest:
                viewer = AnalysisViewer(manifest)
                viewer.show()
            else:
                logger.error(f"Session not found: {self.args.session}")
        else:
            logger.error("Session ID required for view")
    
    def handle_summary(self):
        """Handle summary command"""
        manifest = None
        
        if self.args.session:
            manifest = self.manifest_manager.load_manifest(self.args.session)
        elif self.args.latest:
            # Find latest manifest
            manifest_dir = Path("manifests")
            if manifest_dir.exists():
                manifest_files = list(manifest_dir.glob("manifest_*.json"))
                if manifest_files:
                    latest = max(manifest_files, key=os.path.getctime)
                    with open(latest, 'r') as f:
                        manifest = json.load(f)
        
        if manifest:
            self._print_summary(manifest)
        else:
            logger.error("No manifest found. Run 'analyze' first or specify --session")
    
    def _print_summary(self, manifest: Dict):
        """Print summary of manifest"""
        print("\n" + "="*60)
        print("CODE ANALYSIS SUMMARY")
        print("="*60)
        
        print(f"\nSource: {manifest.get('source_file', 'Unknown')}")
        print(f"Session: {manifest.get('session_id', 'Unknown')}")
        print(f"Timestamp: {manifest.get('timestamp', 'Unknown')}")
        
        print("\n" + "-"*60)
        print("STATISTICS:")
        print("-"*60)
        
        stats = [
            ("Imports", len(manifest['imports']['imports']) + len(manifest['imports']['from_imports'])),
            ("ArgParse Arguments", len(manifest['argparse']['arguments'])),
            ("Tkinter Widgets", len(manifest['tkinter']['widgets'])),
            ("Shell Functions", len(manifest['shell']['functions'])),
            ("Connections", len(manifest.get('connections', []))),
            ("Disconnections", len(manifest.get('disconnections', []))),
            ("Suggestions", len(manifest.get('suggestions', []))),
        ]
        
        for label, count in stats:
            print(f"  {label:<25}: {count}")
        
        efficiency = manifest.get('efficiency_score', {})
        if efficiency:
            print("\n" + "-"*60)
            print("EFFICIENCY SCORE:")
            print("-"*60)
            print(f"  Overall: {efficiency.get('overall', 0)}/100")
            print(f"  Connectivity: {efficiency.get('connectivity', 0)}%")
            print(f"  Breakpoints: {efficiency.get('breakpoints', 0)}")
        
        suggestions = manifest.get('suggestions', [])
        if suggestions:
            print("\n" + "-"*60)
            print("TOP SUGGESTIONS:")
            print("-"*60)
            
            high_priority = [s for s in suggestions if s.get('priority') == 'high']
            for i, suggestion in enumerate(high_priority[:3], 1):
                print(f"  {i}. {suggestion['description'][:60]}...")
        
        print("\n" + "="*60)
        print("Use 'view --session {session_id}' for detailed GUI view")
        print("Use 'patch --session {session_id}' for refactoring patches")
        print("="*60 + "\n")

# #[EVENT] Main execution
def main():
    """Main entry point with comprehensive error handling"""
    # Setup logging ONLY when running as main (not on import)
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(f"analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"),
            logging.StreamHandler()
        ]
    )

    logger.info("[EVENT] Starting Comprehensive Code Analysis Tool")
    logger.info(f"[EVENT] Python version: {sys.version}")
    logger.info(f"[EVENT] Working directory: {os.getcwd()}")
    
    try:
        app = CodeAnalysisApp()
        app.run()
        logger.info("[EVENT] Tool execution completed successfully")
    except KeyboardInterrupt:
        logger.info("[EVENT] Execution interrupted by user")
    except Exception as e:
        logger.error(f"[EVENT] Fatal error: {e}", exc_info=True)
        print(f"\nError: {e}")
        print("\nPlease check the log file for details.")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
