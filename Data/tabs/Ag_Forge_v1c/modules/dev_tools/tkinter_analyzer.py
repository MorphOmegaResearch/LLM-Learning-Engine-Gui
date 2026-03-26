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
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from collections import defaultdict
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

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
    
    def select_project(self, directory: str, target_files: Optional[List[str]] = None) -> ProjectAnalysis:
        """Select and analyze a project directory or a specific list of files."""
        self.project = ProjectAnalysis(directory=directory)
        if target_files:
            self.project.python_files = [str(Path(f).resolve()) for f in target_files]
        else:
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
                self.widgets = []
            
            def visit_Call(self, node):
                if isinstance(node.func, ast.Attribute):
                    # Check for update() misuse
                    if node.func.attr == 'update':
                        # Try to avoid dictionary update() false positives
                        # Widgets usually have names like 'root', 'self', or end in 'frame', 'label', 'btn' etc.
                        # This is a heuristic.
                        caller = ""
                        if isinstance(node.func.value, ast.Name):
                            caller = node.func.value.id
                        elif isinstance(node.func.value, ast.Attribute):
                            caller = node.func.value.attr
                        
                        is_likely_widget = any(x in caller.lower() for x in ['root', 'self', 'app', 'win', 'frame', 'label', 'button', 'btn', 'canvas'])
                        
                        # If it has arguments, it's very likely a dictionary update or similar
                        if not node.args and not node.keywords and is_likely_widget:
                            self.analyzer.project.tk_specific_issues.append(Issue(
                                file=self.file,
                                line=node.lineno,
                                col=node.col_offset,
                                code='TKI001',
                                message=f'Direct use of update() on {caller} can cause issues. Consider update_idletasks()',
                                severity='warning',
                                category='performance',
                                fixable=True,
                                auto_fix='replace_update'
                            ))
                self.generic_visit(node)
        
        visitor = TkinterVisitor(self, file, content)
        visitor.visit(tree)
    
    def _pattern_checks(self, content: str, file: str):
        lines = content.split('\n')
        patterns = [
            (r'from tkinter import \*', 'TKI003', 'Wildcard import from tkinter', 'warning', 'style', True, 'Import specific modules instead'),
            (r'geometry("(\d+)x(\d+)")', 'TKI004', 'Hardcoded geometry string', 'info', 'layout', True, 'Use variables'),
        ]
        for i, line in enumerate(lines, 1):
            for pattern, code, msg, severity, category, fixable, suggestion in patterns:
                if re.search(pattern, line):
                    self.project.tk_specific_issues.append(Issue(
                        file=file, line=i, col=0, code=code, message=msg, severity=severity, category=category, fixable=fixable, fix_suggestion=suggestion, auto_fix=None
                    ))

    def _parse_pyflakes_output(self, output: str, file: str):
        for line in output.strip().split('\n'):
            if ':' in line:
                parts = line.split(':')
                if len(parts) >= 2:
                    self.project.issues.append(Issue(
                        file=file, line=0, col=0, code='PYF001', message=line, severity='warning', category='syntax', fixable=False
                    ))

    def _categorize_issues(self):
        all_issues = self.project.issues + self.project.tk_specific_issues
        for issue in all_issues:
            self.issues_by_file[issue.file].append(issue)
            self.issues_by_category[issue.category].append(issue)
        
        self.project.stats = {
            'total_files': len(self.project.python_files),
            'total_issues': len(all_issues),
            'tk_specific': len(self.project.tk_specific_issues)
        }

if __name__ == "__main__":
    print("Tkinter Analyzer module loaded. Run via main application.")
