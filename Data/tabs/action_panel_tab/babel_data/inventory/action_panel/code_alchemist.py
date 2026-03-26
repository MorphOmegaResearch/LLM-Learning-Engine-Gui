#!/usr/bin/env python3
"""
Code Alchemist - GUI Code Analysis, Hybridization & Iterative Refinement
A Tkinter tool for analyzing, mixing, and refining Python GUI code with confidence scoring.
"""

import os
import sys
import re
import ast
import json
import math
import random
import hashlib
import argparse
import subprocess
import difflib
import traceback
import tempfile
import shutil
import threading
import statistics
import itertools
import textwrap
import inspect
import time
import pickle
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple, Set, Optional, Any, Union
from collections import defaultdict, Counter
from dataclasses import dataclass, field, asdict
from enum import Enum, auto
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog, simpledialog
import tkinter.font as tkfont

# ============================================================================
# ANALYTICAL IMPORTS WITH FALLBACKS
# ============================================================================

ANALYSIS_MODULES = {}

try:
    import py_compile

    ANALYSIS_MODULES["py_compile"] = py_compile
except ImportError:
    ANALYSIS_MODULES["py_compile"] = None

try:
    import black
    from black import Mode, format_str

    ANALYSIS_MODULES["black"] = black
except ImportError:
    ANALYSIS_MODULES["black"] = None

try:
    import pyflakes.api
    import pyflakes.reporter

    ANALYSIS_MODULES["pyflakes"] = pyflakes
except ImportError:
    ANALYSIS_MODULES["pyflakes"] = None

try:
    import pylint.lint

    ANALYSIS_MODULES["pylint"] = pylint
except ImportError:
    ANALYSIS_MODULES["pylint"] = None

try:
    import ruff

    ANALYSIS_MODULES["ruff"] = ruff
except ImportError:
    ANALYSIS_MODULES["ruff"] = None

try:
    import mypy.api

    ANALYSIS_MODULES["mypy"] = mypy
except ImportError:
    ANALYSIS_MODULES["mypy"] = None

try:
    import bandit.core.manager

    ANALYSIS_MODULES["bandit"] = bandit
except ImportError:
    ANALYSIS_MODULES["bandit"] = None

try:
    import radon.complexity
    import radon.raw
    import radon.metrics

    ANALYSIS_MODULES["radon"] = radon
except ImportError:
    ANALYSIS_MODULES["radon"] = None

# ============================================================================
# ENUMS AND DATA STRUCTURES
# ============================================================================


class CodeQuality(Enum):
    EXCELLENT = "excellent"
    GOOD = "good"
    FAIR = "fair"
    POOR = "poor"
    BROKEN = "broken"


class ElementCategory(Enum):
    WIDGET = "widget"
    LAYOUT = "layout"
    EVENT = "event"
    MENU = "menu"
    DIALOG = "dialog"
    CUSTOM = "custom"
    UTILITY = "utility"


class FeatureType(Enum):
    UI_ELEMENT = "ui_element"
    LAYOUT_MANAGER = "layout_manager"
    EVENT_HANDLER = "event_handler"
    DATA_BINDING = "data_binding"
    VALIDATION = "validation"
    ANIMATION = "animation"
    THEME = "theme"
    LOCALIZATION = "localization"
    ACCESSIBILITY = "accessibility"


@dataclass
class CodeElement:
    """Represents a code element with metadata"""

    name: str
    element_type: str
    category: ElementCategory
    source_file: Path
    line_start: int
    line_end: int
    ast_node: Optional[ast.AST] = None
    dependencies: List[str] = field(default_factory=list)
    quality_score: float = 0.0
    complexity_score: float = 0.0
    confidence: float = 0.0
    features: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def id(self) -> str:
        """Generate unique ID for element"""
        return f"{self.source_file.stem}_{self.name}_{self.line_start}_{self.line_end}"


@dataclass
class HybridBuild:
    """Represents a hybrid code build"""

    id: str
    name: str
    created: datetime
    parent_files: List[Path]
    elements: List[CodeElement]
    quality_score: float = 0.0
    compatibility_score: float = 0.0
    innovation_score: float = 0.0
    stability_score: float = 0.0
    syntax_valid: bool = False
    runnable: bool = False
    output_path: Optional[Path] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def overall_score(self) -> float:
        """Calculate overall score"""
        weights = {
            "quality": 0.3,
            "compatibility": 0.25,
            "innovation": 0.2,
            "stability": 0.25,
        }
        return (
            self.quality_score * weights["quality"]
            + self.compatibility_score * weights["compatibility"]
            + self.innovation_score * weights["innovation"]
            + self.stability_score * weights["stability"]
        )


@dataclass
class VariableParameter:
    """Configuration parameter for hybridization"""

    name: str
    value_type: type
    default_value: Any
    current_value: Any
    min_value: Optional[Any] = None
    max_value: Optional[Any] = None
    step: Optional[Any] = None
    description: str = ""
    impact_weight: float = 1.0
    category: str = "general"

    def validate(self) -> bool:
        """Validate current value"""
        if self.value_type == int or self.value_type == float:
            if self.min_value is not None and self.current_value < self.min_value:
                return False
            if self.max_value is not None and self.current_value > self.max_value:
                return False
        return True


@dataclass
class IterationResult:
    """Results from an iteration"""

    iteration: int
    timestamp: datetime
    build: HybridBuild
    changes_applied: List[str]
    quality_before: float
    quality_after: float
    confidence_score: float
    execution_time: float
    success: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    @property
    def improvement(self) -> float:
        """Calculate improvement percentage"""
        if self.quality_before == 0:
            return self.quality_after * 100 if self.quality_after > 0 else 0
        return ((self.quality_after - self.quality_before) / self.quality_before) * 100


# ============================================================================
# CORE ANALYSIS ENGINE
# ============================================================================


class CodeAnalyzer:
    """Comprehensive code analysis engine"""

    def __init__(self, config: Dict = None):
        self.config = config or {}
        self.console_output = []
        self.analysis_cache = {}
        self.element_registry = {}

        # Tkinter-specific patterns
        self.tkinter_widgets = {
            "Button",
            "Label",
            "Entry",
            "Text",
            "Canvas",
            "Listbox",
            "Scrollbar",
            "Checkbutton",
            "Radiobutton",
            "Scale",
            "Spinbox",
            "Combobox",
            "Progressbar",
            "Treeview",
            "Notebook",
            "Frame",
            "Labelframe",
            "PanedWindow",
            "Message",
        }

        self.tkinter_methods = {
            "pack",
            "grid",
            "place",
            "configure",
            "bind",
            "unbind",
            "focus",
            "insert",
            "delete",
            "get",
            "set",
            "update",
            "update_idletasks",
        }

        self.layout_managers = {"pack", "grid", "place"}

    def log(self, message: str, level: str = "INFO"):
        """Log message with timestamp"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] [{level}] {message}"
        self.console_output.append(log_entry)
        print(log_entry)

    def analyze_file(self, filepath: Path) -> Dict[str, Any]:
        """Comprehensive analysis of a Python file"""
        if filepath in self.analysis_cache:
            return self.analysis_cache[filepath]

        self.log(f"Analyzing {filepath.name}...")

        analysis = {
            "file": str(filepath),
            "name": filepath.stem,
            "size": filepath.stat().st_size,
            "modified": datetime.fromtimestamp(filepath.stat().st_mtime),
            "analysis_time": datetime.now(),
            "elements": [],
            "imports": [],
            "classes": [],
            "functions": [],
            "widgets": [],
            "layouts": [],
            "events": [],
            "quality_metrics": {},
            "dependencies": [],
            "risk_factors": [],
            "syntax_valid": False,
            "ast_valid": False,
            "hash": self._file_hash(filepath),
        }

        try:
            # Read file content
            with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()

            # Basic syntax check
            syntax_result = self._check_syntax(filepath)
            analysis["syntax_valid"] = syntax_result["valid"]

            # Parse AST
            try:
                tree = ast.parse(content)
                analysis["ast_valid"] = True

                # Extract imports
                analysis["imports"] = self._extract_imports(tree)

                # Extract classes and functions
                analysis["classes"] = self._extract_classes(tree, filepath)
                analysis["functions"] = self._extract_functions(tree, filepath)

                # Extract Tkinter elements
                analysis["widgets"] = self._extract_widgets(tree, filepath)
                analysis["layouts"] = self._extract_layouts(tree, filepath)
                analysis["events"] = self._extract_events(tree, filepath)

                # Combine all elements
                analysis["elements"] = (
                    analysis["widgets"] + analysis["layouts"] + analysis["events"]
                )

                # Quality metrics
                analysis["quality_metrics"] = self._calculate_quality_metrics(
                    content, tree, filepath
                )

                # Dependencies
                analysis["dependencies"] = self._analyze_dependencies(tree, content)

                # Risk factors
                analysis["risk_factors"] = self._identify_risk_factors(content, tree)

                # Store elements in registry
                for element in analysis["elements"]:
                    self.element_registry[element.id] = element

            except SyntaxError as e:
                analysis["ast_error"] = str(e)
                self.log(f"AST parse error in {filepath.name}: {e}", "WARNING")

            # Run external tools
            analysis["linting"] = self._run_linting(filepath)
            analysis["formatting"] = self._check_formatting(filepath)
            analysis["complexity"] = self._analyze_complexity(content)
            analysis["security"] = self._check_security(filepath)

            # Calculate overall score
            analysis["overall_score"] = self._calculate_overall_score(analysis)

        except Exception as e:
            self.log(f"Error analyzing {filepath.name}: {e}", "ERROR")
            analysis["error"] = str(e)
            analysis["traceback"] = traceback.format_exc()

        self.analysis_cache[filepath] = analysis
        return analysis

    def _check_syntax(self, filepath: Path) -> Dict[str, Any]:
        """Check Python syntax"""
        result = {"valid": False, "error": None}

        if ANALYSIS_MODULES["py_compile"]:
            try:
                py_compile.compile(str(filepath), doraise=True)
                result["valid"] = True
            except py_compile.PyCompileError as e:
                result["error"] = str(e)
            except Exception as e:
                result["error"] = str(e)
        else:
            # Fallback: try to parse with ast
            try:
                with open(filepath, "r") as f:
                    ast.parse(f.read())
                result["valid"] = True
            except SyntaxError as e:
                result["error"] = str(e)

        return result

    def _extract_imports(self, tree: ast.AST) -> List[Dict]:
        """Extract import statements from AST"""
        imports = []

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(
                        {
                            "module": alias.name,
                            "alias": alias.asname,
                            "type": "import",
                            "line": node.lineno if hasattr(node, "lineno") else 0,
                        }
                    )
            elif isinstance(node, ast.ImportFrom):
                imports.append(
                    {
                        "module": node.module,
                        "names": [alias.name for alias in node.names],
                        "level": node.level,
                        "type": "from_import",
                        "line": node.lineno if hasattr(node, "lineno") else 0,
                    }
                )

        return imports

    def _extract_classes(self, tree: ast.AST, filepath: Path) -> List[CodeElement]:
        """Extract class definitions"""
        classes = []

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                # Calculate class complexity
                complexity = self._calculate_node_complexity(node)

                # Check if it's a Tkinter class
                is_tkinter = any(
                    base.id in ["Tk", "Toplevel", "Frame", "Widget"]
                    for base in node.bases
                    if isinstance(base, ast.Name)
                )

                # Extract methods
                methods = []
                for item in node.body:
                    if isinstance(item, ast.FunctionDef):
                        methods.append(item.name)

                element = CodeElement(
                    name=node.name,
                    element_type="class",
                    category=ElementCategory.CUSTOM,
                    source_file=filepath,
                    line_start=node.lineno,
                    line_end=(
                        node.end_lineno if hasattr(node, "end_lineno") else node.lineno
                    ),
                    ast_node=node,
                    dependencies=self._extract_class_dependencies(node),
                    complexity_score=complexity,
                    confidence=0.8 if is_tkinter else 0.5,
                    features={
                        "bases": [self._ast_to_source(base) for base in node.bases],
                        "methods": methods,
                        "is_tkinter": is_tkinter,
                        "docstring": ast.get_docstring(node),
                    },
                )
                classes.append(element)

        return classes

    def _extract_functions(self, tree: ast.AST, filepath: Path) -> List[CodeElement]:
        """Extract function definitions"""
        functions = []

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                # Calculate function complexity
                complexity = self._calculate_node_complexity(node)

                # Check if it's an event handler
                is_event_handler = (
                    any(
                        kw.arg in ["command", "bind"]
                        for kw in node.args.defaults
                        if isinstance(kw, ast.keyword)
                    )
                    or "event" in node.name.lower()
                )

                element = CodeElement(
                    name=node.name,
                    element_type="function",
                    category=(
                        ElementCategory.EVENT
                        if is_event_handler
                        else ElementCategory.UTILITY
                    ),
                    source_file=filepath,
                    line_start=node.lineno,
                    line_end=(
                        node.end_lineno if hasattr(node, "end_lineno") else node.lineno
                    ),
                    ast_node=node,
                    dependencies=self._extract_function_dependencies(node),
                    complexity_score=complexity,
                    confidence=0.7 if is_event_handler else 0.6,
                    features={
                        "args": [arg.arg for arg in node.args.args],
                        "returns": self._extract_return_type(node),
                        "is_event_handler": is_event_handler,
                        "docstring": ast.get_docstring(node),
                    },
                )
                functions.append(element)

        return functions

    def _extract_widgets(self, tree: ast.AST, filepath: Path) -> List[CodeElement]:
        """Extract Tkinter widget creations"""
        widgets = []

        for node in ast.walk(tree):
            # Look for widget instantiations: Button(...), Label(...), etc.
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    widget_name = node.func.id
                    if widget_name in self.tkinter_widgets:
                        element = CodeElement(
                            name=widget_name,
                            element_type="widget",
                            category=ElementCategory.WIDGET,
                            source_file=filepath,
                            line_start=node.lineno,
                            line_end=(
                                node.end_lineno
                                if hasattr(node, "end_lineno")
                                else node.lineno
                            ),
                            ast_node=node,
                            confidence=0.9,
                            features={
                                "args": [self._ast_to_source(arg) for arg in node.args],
                                "keywords": {
                                    kw.arg: self._ast_to_source(kw.value)
                                    for kw in node.keywords
                                },
                                "parent": self._find_widget_parent(node),
                            },
                        )
                        widgets.append(element)

        return widgets

    def _extract_layouts(self, tree: ast.AST, filepath: Path) -> List[CodeElement]:
        """Extract layout manager calls"""
        layouts = []

        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Attribute):
                    method_name = node.func.attr
                    if method_name in self.layout_managers:
                        element = CodeElement(
                            name=method_name,
                            element_type="layout",
                            category=ElementCategory.LAYOUT,
                            source_file=filepath,
                            line_start=node.lineno,
                            line_end=(
                                node.end_lineno
                                if hasattr(node, "end_lineno")
                                else node.lineno
                            ),
                            ast_node=node,
                            confidence=0.85,
                            features={
                                "widget": self._ast_to_source(node.func.value),
                                "options": {
                                    kw.arg: self._ast_to_source(kw.value)
                                    for kw in node.keywords
                                },
                            },
                        )
                        layouts.append(element)

        return layouts

    def _extract_events(self, tree: ast.AST, filepath: Path) -> List[CodeElement]:
        """Extract event bindings"""
        events = []

        for node in ast.walk(tree):
            # Look for bind() calls
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Attribute):
                    if node.func.attr == "bind":
                        element = CodeElement(
                            name="bind",
                            element_type="event",
                            category=ElementCategory.EVENT,
                            source_file=filepath,
                            line_start=node.lineno,
                            line_end=(
                                node.end_lineno
                                if hasattr(node, "end_lineno")
                                else node.lineno
                            ),
                            ast_node=node,
                            confidence=0.8,
                            features={
                                "widget": self._ast_to_source(node.func.value),
                                "sequence": (
                                    self._ast_to_source(node.args[0])
                                    if node.args
                                    else None
                                ),
                                "handler": (
                                    self._ast_to_source(node.args[1])
                                    if len(node.args) > 1
                                    else None
                                ),
                            },
                        )
                        events.append(element)

        return events

    def _calculate_quality_metrics(
        self, content: str, tree: ast.AST, filepath: Path
    ) -> Dict[str, float]:
        """Calculate various code quality metrics"""
        metrics = {
            "lines_of_code": len(content.splitlines()),
            "function_count": sum(
                1 for _ in ast.walk(tree) if isinstance(_, ast.FunctionDef)
            ),
            "class_count": sum(
                1 for _ in ast.walk(tree) if isinstance(_, ast.ClassDef)
            ),
            "comment_density": self._calculate_comment_density(content),
            "cyclomatic_complexity": 0.0,
            "maintainability_index": 0.0,
            "halstead_volume": 0.0,
        }

        # Calculate cyclomatic complexity if radon is available
        if ANALYSIS_MODULES["radon"]:
            try:
                cc_results = ANALYSIS_MODULES["radon"].complexity.cc_visit(content)
                if cc_results:
                    metrics["cyclomatic_complexity"] = statistics.mean(
                        [block.complexity for block in cc_results]
                    )

                # Calculate maintainability index
                raw_metrics = ANALYSIS_MODULES["radon"].raw.analyze(content)
                mi = ANALYSIS_MODULES["radon"].metrics.mi_visit(content, True)
                metrics["maintainability_index"] = mi

            except Exception as e:
                self.log(f"Error calculating radon metrics: {e}", "WARNING")

        return metrics

    def _run_linting(self, filepath: Path) -> Dict[str, Any]:
        """Run various linters on the file"""
        lint_results = {}

        # Run ruff if available
        if ANALYSIS_MODULES["ruff"]:
            try:
                result = subprocess.run(
                    ["ruff", "check", "--output-format", "json", str(filepath)],
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                if (
                    result.returncode == 0 or result.returncode == 1
                ):  # 1 means issues found
                    try:
                        lint_results["ruff"] = json.loads(result.stdout)
                    except json.JSONDecodeError:
                        lint_results["ruff"] = {"output": result.stdout}
            except Exception as e:
                lint_results["ruff_error"] = str(e)

        # Run pyflakes if available
        if ANALYSIS_MODULES["pyflakes"]:
            try:
                from io import StringIO

                with open(filepath, "r") as f:
                    content = f.read()

                stream = StringIO()
                reporter = ANALYSIS_MODULES["pyflakes"].reporter.Reporter(
                    stream, stream
                )
                warnings = ANALYSIS_MODULES["pyflakes"].api.check(
                    content, str(filepath), reporter
                )
                lint_results["pyflakes"] = {
                    "warnings": warnings,
                    "output": stream.getvalue(),
                }
            except Exception as e:
                lint_results["pyflakes_error"] = str(e)

        # Run pylint if available
        if ANALYSIS_MODULES["pylint"]:
            try:
                # Run pylint with JSON output
                result = subprocess.run(
                    ["pylint", "--output-format=json", str(filepath)],
                    capture_output=True,
                    text=True,
                    timeout=60,
                )
                if result.stdout:
                    try:
                        lint_results["pylint"] = json.loads(result.stdout)
                    except json.JSONDecodeError:
                        lint_results["pylint_output"] = result.stdout
            except Exception as e:
                lint_results["pylint_error"] = str(e)

        return lint_results

    def _check_formatting(self, filepath: Path) -> Dict[str, Any]:
        """Check code formatting"""
        formatting = {"needs_formatting": False, "diff": ""}

        if ANALYSIS_MODULES["black"]:
            try:
                with open(filepath, "r") as f:
                    original = f.read()

                # Check if formatting is needed
                mode = ANALYSIS_MODULES["black"].Mode()
                try:
                    ANALYSIS_MODULES["black"].format_file_contents(
                        original, fast=False, mode=mode
                    )
                    formatting["needs_formatting"] = False
                except ANALYSIS_MODULES["black"].NothingChanged:
                    formatting["needs_formatting"] = False
                except Exception:
                    formatting["needs_formatting"] = True

                    # Get diff
                    result = subprocess.run(
                        ["black", "--diff", str(filepath)],
                        capture_output=True,
                        text=True,
                    )
                    formatting["diff"] = result.stdout

            except Exception as e:
                formatting["error"] = str(e)

        return formatting

    def _analyze_complexity(self, content: str) -> Dict[str, float]:
        """Analyze code complexity"""
        complexity = {
            "average_complexity": 0.0,
            "max_complexity": 0.0,
            "complex_functions": 0,
        }

        if ANALYSIS_MODULES["radon"]:
            try:
                cc_results = ANALYSIS_MODULES["radon"].complexity.cc_visit(content)
                if cc_results:
                    complexities = [block.complexity for block in cc_results]
                    complexity["average_complexity"] = statistics.mean(complexities)
                    complexity["max_complexity"] = max(complexities)
                    complexity["complex_functions"] = sum(
                        1 for c in complexities if c > 10
                    )
            except Exception as e:
                self.log(f"Error calculating complexity: {e}", "WARNING")

        return complexity

    def _check_security(self, filepath: Path) -> Dict[str, Any]:
        """Check for security issues"""
        security = {"issues": [], "score": 100}

        if ANALYSIS_MODULES["bandit"]:
            try:
                # Run bandit with JSON output
                result = subprocess.run(
                    ["bandit", "-f", "json", "-r", str(filepath)],
                    capture_output=True,
                    text=True,
                    timeout=60,
                )
                if result.stdout:
                    try:
                        report = json.loads(result.stdout)
                        issues = report.get("results", [])
                        security["issues"] = issues

                        # Calculate security score
                        high_sev = sum(
                            1 for i in issues if i.get("issue_severity") == "HIGH"
                        )
                        med_sev = sum(
                            1 for i in issues if i.get("issue_severity") == "MEDIUM"
                        )
                        security["score"] = max(0, 100 - (high_sev * 20 + med_sev * 10))
                    except json.JSONDecodeError:
                        security["bandit_output"] = result.stdout
            except Exception as e:
                security["bandit_error"] = str(e)

        return security

    def _calculate_overall_score(self, analysis: Dict) -> float:
        """Calculate overall quality score (0-100)"""
        score = 0.0

        # Base score for syntax validity
        if analysis.get("syntax_valid"):
            score += 30

        # Quality metrics contribution
        quality = analysis.get("quality_metrics", {})
        if quality.get("maintainability_index", 0) > 85:
            score += 20
        elif quality.get("maintainability_index", 0) > 70:
            score += 15
        elif quality.get("maintainability_index", 0) > 50:
            score += 10

        # Complexity penalty
        if quality.get("cyclomatic_complexity", 0) < 10:
            score += 15
        elif quality.get("cyclomatic_complexity", 0) < 20:
            score += 10
        elif quality.get("cyclomatic_complexity", 0) < 30:
            score += 5

        # Security score contribution
        security = analysis.get("security", {}).get("score", 100)
        score += (security / 100) * 20

        # Linting penalty
        linting = analysis.get("linting", {})
        if "ruff" in linting and isinstance(linting["ruff"], list):
            issues = len(linting["ruff"])
            if issues == 0:
                score += 15
            elif issues < 5:
                score += 10
            elif issues < 10:
                score += 5

        return min(100, max(0, score))

    # Helper methods
    def _file_hash(self, filepath: Path) -> str:
        """Calculate file hash"""
        hasher = hashlib.sha256()
        with open(filepath, "rb") as f:
            hasher.update(f.read())
        return hasher.hexdigest()

    def _calculate_comment_density(self, content: str) -> float:
        """Calculate comment density percentage"""
        lines = content.splitlines()
        if not lines:
            return 0.0

        code_lines = 0
        comment_lines = 0

        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.startswith("#"):
                comment_lines += 1
            else:
                code_lines += 1

        total_lines = code_lines + comment_lines
        return (comment_lines / total_lines * 100) if total_lines > 0 else 0.0

    def _calculate_node_complexity(self, node: ast.AST) -> float:
        """Calculate complexity of an AST node"""
        complexity = 1  # Base complexity

        for child in ast.walk(node):
            # Add complexity for control flow structures
            if isinstance(child, (ast.If, ast.While, ast.For, ast.Try, ast.With)):
                complexity += 1
            elif isinstance(child, ast.BoolOp):
                complexity += len(child.values) - 1
            elif isinstance(child, ast.Compare):
                complexity += len(child.ops) - 1

        return complexity

    def _extract_class_dependencies(self, node: ast.ClassDef) -> List[str]:
        """Extract dependencies from a class"""
        dependencies = set()

        for base in node.bases:
            if isinstance(base, ast.Name):
                dependencies.add(base.id)

        for item in node.body:
            if isinstance(item, ast.FunctionDef):
                deps = self._extract_function_dependencies(item)
                dependencies.update(deps)

        return list(dependencies)

    def _extract_function_dependencies(self, node: ast.FunctionDef) -> List[str]:
        """Extract dependencies from a function"""
        dependencies = set()

        for child in ast.walk(node):
            if isinstance(child, ast.Name):
                # Check if it's a function call
                if isinstance(child.ctx, ast.Load):
                    # This is simplistic - should check parent context
                    dependencies.add(child.id)

        return list(dependencies)

    def _extract_return_type(self, node: ast.FunctionDef) -> Optional[str]:
        """Extract return type annotation"""
        if node.returns:
            return self._ast_to_source(node.returns)
        return None

    def _find_widget_parent(self, node: ast.Call) -> Optional[str]:
        """Find the parent widget for a widget creation"""
        # Walk up the AST to find assignment
        parent = node
        while hasattr(parent, "parent"):
            parent = parent.parent
            if isinstance(parent, ast.Assign):
                if len(parent.targets) > 0:
                    return self._ast_to_source(parent.targets[0])

        return None

    def _analyze_dependencies(self, tree: ast.AST, content: str) -> List[Dict]:
        """Analyze module dependencies"""
        imports = self._extract_imports(tree)
        dependencies = []

        for imp in imports:
            dep = {
                "module": imp["module"],
                "type": imp["type"],
                "line": imp.get("line", 0),
            }

            # Check if it's a standard library module
            try:
                import importlib

                spec = importlib.util.find_spec(imp["module"].split(".")[0])
                if spec:
                    dep["location"] = spec.origin or "builtin"
                    dep["is_standard"] = "site-packages" not in (spec.origin or "")
                else:
                    dep["location"] = "unknown"
                    dep["is_standard"] = False
            except (ImportError, ValueError):
                dep["location"] = "unknown"
                dep["is_standard"] = False

            dependencies.append(dep)

        return dependencies

    def _identify_risk_factors(self, content: str, tree: ast.AST) -> List[str]:
        """Identify potential risk factors in code"""
        risks = []

        # Check for eval/exec
        if "eval(" in content or "exec(" in content:
            risks.append("Uses eval/exec")

        # Check for system calls
        if "os.system" in content or "subprocess.call" in content:
            risks.append("Uses system calls")

        # Check for dynamic imports
        if "__import__" in content:
            risks.append("Uses dynamic imports")

        # Check for bare except
        if "except:" in content or "except Exception:" in content:
            risks.append("Uses bare except")

        # Check for large functions/classes
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                lines = (
                    node.end_lineno - node.lineno if hasattr(node, "end_lineno") else 1
                )
                if lines > 50:
                    risks.append(f"Large function: {node.name} ({lines} lines)")

            elif isinstance(node, ast.ClassDef):
                lines = (
                    node.end_lineno - node.lineno if hasattr(node, "end_lineno") else 1
                )
                if lines > 200:
                    risks.append(f"Large class: {node.name} ({lines} lines)")

        return risks

    def _ast_to_source(self, node: ast.AST) -> str:
        """Convert AST node to source code string"""
        try:
            return ast.unparse(node) if hasattr(ast, "unparse") else ast.dump(node)
        except:
            return str(node)


# ============================================================================
# HYBRIDIZATION ENGINE
# ============================================================================


class HybridizationEngine:
    """Engine for creating hybrid code builds"""

    def __init__(self, analyzer: CodeAnalyzer, config: Dict = None):
        self.analyzer = analyzer
        self.config = config or {}
        self.builds = {}
        self.iteration_history = []
        self.variable_parameters = self._initialize_parameters()

    def _initialize_parameters(self) -> Dict[str, VariableParameter]:
        """Initialize variable parameters for hybridization"""
        return {
            "mutation_rate": VariableParameter(
                name="mutation_rate",
                value_type=float,
                default_value=0.1,
                current_value=0.1,
                min_value=0.0,
                max_value=1.0,
                step=0.01,
                description="Rate of random mutations during hybridization",
                impact_weight=0.8,
                category="mutation",
            ),
            "crossover_rate": VariableParameter(
                name="crossover_rate",
                value_type=float,
                default_value=0.7,
                current_value=0.7,
                min_value=0.0,
                max_value=1.0,
                step=0.01,
                description="Rate of crossover between parent elements",
                impact_weight=0.9,
                category="crossover",
            ),
            "innovation_bias": VariableParameter(
                name="innovation_bias",
                value_type=float,
                default_value=0.3,
                current_value=0.3,
                min_value=0.0,
                max_value=1.0,
                step=0.01,
                description="Bias towards innovative/unusual combinations",
                impact_weight=0.6,
                category="selection",
            ),
            "quality_weight": VariableParameter(
                name="quality_weight",
                value_type=float,
                default_value=0.4,
                current_value=0.4,
                min_value=0.0,
                max_value=1.0,
                step=0.01,
                description="Weight given to quality scores in selection",
                impact_weight=0.7,
                category="selection",
            ),
            "compatibility_weight": VariableParameter(
                name="compatibility_weight",
                value_type=float,
                default_value=0.3,
                current_value=0.3,
                min_value=0.0,
                max_value=1.0,
                step=0.01,
                description="Weight given to compatibility scores",
                impact_weight=0.8,
                category="selection",
            ),
            "max_iterations": VariableParameter(
                name="max_iterations",
                value_type=int,
                default_value=50,
                current_value=50,
                min_value=1,
                max_value=1000,
                step=1,
                description="Maximum iterations for refinement",
                impact_weight=0.5,
                category="iteration",
            ),
            "confidence_threshold": VariableParameter(
                name="confidence_threshold",
                value_type=float,
                default_value=0.7,
                current_value=0.7,
                min_value=0.0,
                max_value=1.0,
                step=0.01,
                description="Minimum confidence for element inclusion",
                impact_weight=0.9,
                category="filtering",
            ),
            "temperature": VariableParameter(
                name="temperature",
                value_type=float,
                default_value=1.0,
                current_value=1.0,
                min_value=0.1,
                max_value=5.0,
                step=0.1,
                description="Controls exploration vs exploitation",
                impact_weight=0.6,
                category="search",
            ),
        }

    def create_hybrid(self, parent_files: List[Path], name: str = None) -> HybridBuild:
        """Create a hybrid build from parent files"""
        self.analyzer.log(f"Creating hybrid from {len(parent_files)} parent files")

        # Analyze all parent files
        parent_analyses = []
        for filepath in parent_files:
            analysis = self.analyzer.analyze_file(filepath)
            parent_analyses.append(analysis)

        # Extract elements from parents
        all_elements = []
        for analysis in parent_analyses:
            elements = analysis.get("elements", [])
            all_elements.extend(elements)

        # Filter elements by confidence
        confidence_threshold = self.variable_parameters[
            "confidence_threshold"
        ].current_value
        filtered_elements = [
            elem for elem in all_elements if elem.confidence >= confidence_threshold
        ]

        if not filtered_elements:
            self.analyzer.log("No elements passed confidence threshold", "WARNING")
            filtered_elements = all_elements

        # Apply crossover and mutation
        hybrid_elements = self._apply_genetic_operations(filtered_elements)

        # Create hybrid build
        build_id = hashlib.sha256(str(datetime.now()).encode()).hexdigest()[:16]
        build_name = name or f"hybrid_{build_id[:8]}"

        build = HybridBuild(
            id=build_id,
            name=build_name,
            created=datetime.now(),
            parent_files=parent_files,
            elements=hybrid_elements,
            metadata={
                "parent_count": len(parent_files),
                "element_count": len(hybrid_elements),
                "confidence_threshold": confidence_threshold,
            },
        )

        # Calculate scores
        self._calculate_build_scores(build)

        # Generate output code
        output_path = self._generate_output_code(build)
        build.output_path = output_path

        # Validate build
        self._validate_build(build)

        # Store build
        self.builds[build_id] = build

        self.analyzer.log(f"Created hybrid build: {build_name} (ID: {build_id})")
        self.analyzer.log(f"  Elements: {len(hybrid_elements)}")
        self.analyzer.log(f"  Overall Score: {build.overall_score:.2f}")
        self.analyzer.log(f"  Output: {output_path}")

        return build

    def _apply_genetic_operations(
        self, elements: List[CodeElement]
    ) -> List[CodeElement]:
        """Apply genetic operations to elements"""
        mutation_rate = self.variable_parameters["mutation_rate"].current_value
        crossover_rate = self.variable_parameters["crossover_rate"].current_value
        innovation_bias = self.variable_parameters["innovation_bias"].current_value

        result_elements = []

        # Group elements by type
        elements_by_type = defaultdict(list)
        for elem in elements:
            elements_by_type[elem.element_type].append(elem)

        # For each element type, apply operations
        for elem_type, type_elements in elements_by_type.items():
            if len(type_elements) < 2:
                # No crossover possible, just mutate
                for elem in type_elements:
                    if random.random() < mutation_rate:
                        mutated = self._mutate_element(elem, innovation_bias)
                        result_elements.append(mutated)
                    else:
                        result_elements.append(elem)
            else:
                # Apply crossover between elements
                for i in range(0, len(type_elements), 2):
                    if i + 1 < len(type_elements):
                        elem1 = type_elements[i]
                        elem2 = type_elements[i + 1]

                        if random.random() < crossover_rate:
                            crossed = self._crossover_elements(elem1, elem2)
                            result_elements.append(crossed)
                        else:
                            # Keep one based on innovation bias
                            if random.random() < innovation_bias:
                                # Prefer more innovative (lower confidence = more innovative)
                                chosen = (
                                    elem1
                                    if elem1.confidence < elem2.confidence
                                    else elem2
                                )
                            else:
                                # Prefer higher quality
                                chosen = (
                                    elem1
                                    if elem1.quality_score > elem2.quality_score
                                    else elem2
                                )

                            # Mutate with probability
                            if random.random() < mutation_rate:
                                chosen = self._mutate_element(chosen, innovation_bias)

                            result_elements.append(chosen)

        return result_elements

    def _mutate_element(
        self, element: CodeElement, innovation_bias: float
    ) -> CodeElement:
        """Mutate a code element"""
        mutated = CodeElement(
            name=element.name,
            element_type=element.element_type,
            category=element.category,
            source_file=element.source_file,
            line_start=element.line_start,
            line_end=element.line_end,
            ast_node=element.ast_node,
            dependencies=element.dependencies.copy(),
            quality_score=element.quality_score,
            complexity_score=element.complexity_score,
            confidence=element.confidence,
            features=element.features.copy(),
            metadata=element.metadata.copy(),
        )

        # Apply mutations based on element type
        mutation_type = random.choice(
            ["rename", "param_change", "feature_mod", "confidence_adjust"]
        )

        if mutation_type == "rename":
            # Add suffix to name
            suffixes = ["_mod", "_alt", "_v2", "_enhanced"]
            mutated.name = element.name + random.choice(suffixes)
            mutated.confidence = max(0.1, element.confidence - 0.1)

        elif mutation_type == "param_change" and "features" in mutated.features:
            # Change a parameter value
            if "keywords" in mutated.features:
                keywords = mutated.features["keywords"]
                if keywords:
                    key = random.choice(list(keywords.keys()))
                    # Simple mutation: add prefix or change value slightly
                    old_val = keywords[key]
                    if isinstance(old_val, str) and old_val.startswith('"'):
                        mutated.features["keywords"][key] = f'"{old_val[1:-1]}_mod"'

        elif mutation_type == "feature_mod":
            # Modify features
            if "features" in mutated.features:
                mutated.features["mutated"] = True
                mutated.features["mutation_type"] = mutation_type

        elif mutation_type == "confidence_adjust":
            # Adjust confidence
            adjustment = random.uniform(-0.2, 0.2) * innovation_bias
            mutated.confidence = max(0.1, min(1.0, element.confidence + adjustment))

        mutated.metadata["mutated"] = True
        mutated.metadata["original_id"] = element.id

        return mutated

    def _crossover_elements(
        self, elem1: CodeElement, elem2: CodeElement
    ) -> CodeElement:
        """Crossover two elements"""
        # Choose which element contributes more based on confidence
        if elem1.confidence > elem2.confidence:
            base_elem = elem1
            donor_elem = elem2
        else:
            base_elem = elem2
            donor_elem = elem1

        # Create crossed element
        crossed = CodeElement(
            name=base_elem.name,
            element_type=base_elem.element_type,
            category=base_elem.category,
            source_file=base_elem.source_file,
            line_start=base_elem.line_start,
            line_end=base_elem.line_end,
            ast_node=base_elem.ast_node,
            dependencies=list(set(base_elem.dependencies + donor_elem.dependencies)),
            quality_score=(base_elem.quality_score + donor_elem.quality_score) / 2,
            complexity_score=(base_elem.complexity_score + donor_elem.complexity_score)
            / 2,
            confidence=(base_elem.confidence + donor_elem.confidence) / 2,
            features=self._merge_features(base_elem.features, donor_elem.features),
            metadata={
                "crossover": True,
                "parents": [elem1.id, elem2.id],
                "parent_names": [elem1.name, elem2.name],
            },
        )

        return crossed

    def _merge_features(self, features1: Dict, features2: Dict) -> Dict:
        """Merge features from two elements"""
        merged = features1.copy()

        for key, value in features2.items():
            if key not in merged:
                merged[key] = value
            elif isinstance(value, dict) and isinstance(merged[key], dict):
                # Recursively merge dictionaries
                merged[key] = self._merge_features(merged[key], value)
            elif random.random() < 0.5:
                # Randomly choose which value to keep
                merged[key] = value

        return merged

    def _calculate_build_scores(self, build: HybridBuild):
        """Calculate various scores for a build"""
        elements = build.elements

        if not elements:
            build.quality_score = 0
            build.compatibility_score = 0
            build.innovation_score = 0
            build.stability_score = 0
            return

        # Quality score based on element qualities
        quality_scores = [
            elem.quality_score for elem in elements if elem.quality_score > 0
        ]
        if quality_scores:
            build.quality_score = statistics.mean(quality_scores) * 100
        else:
            build.quality_score = 50  # Default

        # Compatibility score (how well elements work together)
        # Based on shared dependencies and element types
        dependencies = set()
        element_types = set()
        for elem in elements:
            dependencies.update(elem.dependencies)
            element_types.add(elem.element_type)

        # More diverse element types = potentially less compatible
        type_compatibility = 1.0 / max(1, len(element_types))

        # Shared dependencies = more compatible
        dep_compatibility = len(dependencies) / max(1, len(elements) * 5)

        build.compatibility_score = (type_compatibility + dep_compatibility) / 2 * 100

        # Innovation score (uniqueness, mutations, crossovers)
        innovative_count = sum(
            1
            for elem in elements
            if elem.metadata.get("mutated") or elem.metadata.get("crossover")
        )
        build.innovation_score = (innovative_count / len(elements)) * 100

        # Stability score (based on confidence and complexity)
        confidences = [elem.confidence for elem in elements]
        complexities = [elem.complexity_score for elem in elements]

        if confidences:
            avg_confidence = statistics.mean(confidences)
            confidence_stability = avg_confidence * 100
        else:
            confidence_stability = 50

        if complexities:
            # Lower complexity = more stable
            avg_complexity = statistics.mean(complexities)
            complexity_stability = max(0, 100 - (avg_complexity * 10))
        else:
            complexity_stability = 50

        build.stability_score = (confidence_stability + complexity_stability) / 2

    def _generate_output_code(self, build: HybridBuild) -> Path:
        """Generate Python code from hybrid build"""
        # Create output directory
        output_dir = Path("hybrid_outputs") / build.id
        output_dir.mkdir(parents=True, exist_ok=True)

        output_path = output_dir / f"{build.name}.py"

        # Generate import statements
        imports = set()
        for elem in build.elements:
            imports.update(elem.dependencies)

        # Add Tkinter imports
        imports.add("tkinter")
        imports.add("tkinter.ttk")

        # Generate code
        lines = []
        lines.append(f"# Hybrid Build: {build.name}")
        lines.append(f"# Generated: {build.created}")
        lines.append(f"# Parent Files: {len(build.parent_files)}")
        lines.append(f"# Elements: {len(build.elements)}")
        lines.append(f"# Overall Score: {build.overall_score:.2f}")
        lines.append("")

        # Add imports
        for imp in sorted(imports):
            if imp in ["tkinter", "tkinter.ttk"]:
                lines.append(f"import {imp} as tk")
            else:
                lines.append(f"import {imp}")
        lines.append("")

        lines.append("class HybridApp:")
        lines.append('    """Auto-generated hybrid Tkinter application"""')
        lines.append("    ")
        lines.append("    def __init__(self, root):")
        lines.append("        self.root = root")
        lines.append('        self.root.title(f"Hybrid: {build.name}")')
        lines.append("        self.setup_ui()")
        lines.append("    ")

        # Add setup_ui method with elements
        lines.append("    def setup_ui(self):")
        lines.append('        """Setup the user interface"""')

        # Group elements by category
        widgets = [e for e in build.elements if e.category == ElementCategory.WIDGET]
        layouts = [e for e in build.elements if e.category == ElementCategory.LAYOUT]
        events = [e for e in build.elements if e.category == ElementCategory.EVENT]

        # Add widgets
        for i, widget in enumerate(widgets[:10]):  # Limit to 10 widgets
            widget_name = f"widget_{i}"
            widget_class = widget.name
            lines.append(f"        self.{widget_name} = tk.{widget_class}(self.root)")

            # Add configuration if available
            if (
                "features" in widget.features
                and "keywords" in widget.features["features"]
            ):
                configs = widget.features["features"]["keywords"]
                for key, value in list(configs.items())[:3]:  # Limit to 3 configs
                    lines.append(f"        self.{widget_name}.config({key}={value})")

        # Add layouts
        for i, layout in enumerate(layouts[:5]):  # Limit to 5 layouts
            if i < len(widgets):
                widget_name = f"widget_{i}"
                layout_method = layout.name
                lines.append(f"        self.{widget_name}.{layout_method}()")

        # Add events
        for i, event in enumerate(events[:3]):  # Limit to 3 events
            if i < len(widgets):
                widget_name = f"widget_{i}"
                lines.append(f"        # Event binding would go here")

        lines.append("")
        lines.append("    def run(self):")
        lines.append('        """Run the application"""')
        lines.append("        self.root.mainloop()")
        lines.append("")
        lines.append("")
        lines.append('if __name__ == "__main__":')
        lines.append("    root = tk.Tk()")
        lines.append("    app = HybridApp(root)")
        lines.append("    app.run()")

        # Write to file
        with open(output_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

        return output_path

    def _validate_build(self, build: HybridBuild):
        """Validate the generated build"""
        if not build.output_path or not build.output_path.exists():
            build.syntax_valid = False
            build.runnable = False
            return

        # Check syntax
        analyzer = self.analyzer
        syntax_result = analyzer._check_syntax(build.output_path)
        build.syntax_valid = syntax_result["valid"]

        # Try to run a simple test
        build.runnable = build.syntax_valid  # Simplified for now

    def run_iteration(self, build: HybridBuild) -> IterationResult:
        """Run a refinement iteration on a build"""
        start_time = time.time()
        iteration = len(self.iteration_history) + 1

        self.analyzer.log(f"Starting iteration {iteration} on build: {build.name}")

        # Store before state
        quality_before = build.overall_score

        # Apply refinement strategies
        changes = []

        # Strategy 1: Improve low-confidence elements
        low_conf_elements = [e for e in build.elements if e.confidence < 0.5]
        if low_conf_elements and random.random() < 0.7:
            for elem in random.sample(
                low_conf_elements, min(3, len(low_conf_elements))
            ):
                # Try to improve confidence
                old_conf = elem.confidence
                elem.confidence = min(1.0, old_conf + random.uniform(0.1, 0.3))
                changes.append(
                    f"Improved confidence of {elem.name}: {old_conf:.2f} -> {elem.confidence:.2f}"
                )

        # Strategy 2: Replace problematic elements
        problematic = [e for e in build.elements if e.complexity_score > 5]
        if problematic and random.random() < 0.5:
            # Replace with simpler alternative if available
            elem_to_replace = random.choice(problematic)
            # For now, just remove it (in practice, would find replacement)
            build.elements.remove(elem_to_replace)
            changes.append(f"Removed complex element: {elem_to_replace.name}")

        # Strategy 3: Add missing imports based on dependencies
        current_deps = set()
        for elem in build.elements:
            current_deps.update(elem.dependencies)

        # Recalculate scores
        self._calculate_build_scores(build)

        # Regenerate code
        output_path = self._generate_output_code(build)
        build.output_path = output_path

        # Validate
        self._validate_build(build)

        # Calculate results
        quality_after = build.overall_score
        execution_time = time.time() - start_time

        # Calculate confidence score for this iteration
        improvement = quality_after - quality_before
        confidence = 0.5 + (improvement / 100)  # Base 0.5, adjust based on improvement

        success = build.syntax_valid and improvement >= -10  # Allow small regression

        result = IterationResult(
            iteration=iteration,
            timestamp=datetime.now(),
            build=build,
            changes_applied=changes,
            quality_before=quality_before,
            quality_after=quality_after,
            confidence_score=confidence,
            execution_time=execution_time,
            success=success,
        )

        self.iteration_history.append(result)

        self.analyzer.log(f"Iteration {iteration} completed:")
        self.analyzer.log(f"  Quality: {quality_before:.2f} -> {quality_after:.2f}")
        self.analyzer.log(f"  Improvement: {improvement:+.2f}")
        self.analyzer.log(f"  Confidence: {confidence:.2f}")
        self.analyzer.log(f"  Changes: {len(changes)}")

        return result

    def run_iterative_refinement(
        self, build: HybridBuild, max_iterations: int = None
    ) -> List[IterationResult]:
        """Run multiple refinement iterations"""
        if max_iterations is None:
            max_iterations = self.variable_parameters["max_iterations"].current_value

        self.analyzer.log(
            f"Starting iterative refinement (max {max_iterations} iterations)"
        )

        results = []
        stagnation_count = 0
        best_score = build.overall_score

        for i in range(max_iterations):
            result = self.run_iteration(build)
            results.append(result)

            # Check for stagnation
            if result.quality_after <= best_score + 0.1:  # No significant improvement
                stagnation_count += 1
            else:
                stagnation_count = 0
                best_score = result.quality_after

            # Early stopping if stagnated for too long
            if stagnation_count >= 10:
                self.analyzer.log(
                    f"Stopping early due to stagnation after {i+1} iterations"
                )
                break

            # Stop if perfect score
            if result.quality_after >= 95:
                self.analyzer.log(
                    f"Stopping early: reached excellent quality ({result.quality_after:.2f})"
                )
                break

        self.analyzer.log(f"Refinement completed: {len(results)} iterations")
        self.analyzer.log(f"Final quality: {build.overall_score:.2f}")

        return results

    def get_variable_recommendations(self) -> List[Dict]:
        """Get recommendations for variable adjustments based on iteration history"""
        if not self.iteration_history:
            return []

        recommendations = []

        # Analyze iteration patterns
        improvements = [r.improvement for r in self.iteration_history]
        avg_improvement = statistics.mean(improvements) if improvements else 0

        if avg_improvement < 0:
            # Negative improvement, suggest more conservative approach
            recommendations.append(
                {
                    "parameter": "mutation_rate",
                    "action": "decrease",
                    "reason": f"Average improvement is negative ({avg_improvement:.2f}%)",
                    "suggested_change": -0.05,
                    "confidence": 0.7,
                }
            )

            recommendations.append(
                {
                    "parameter": "temperature",
                    "action": "decrease",
                    "reason": "Reduce exploration to focus on exploitation",
                    "suggested_change": -0.5,
                    "confidence": 0.6,
                }
            )

        else:
            # Positive improvement, could be more aggressive
            if avg_improvement < 1:
                recommendations.append(
                    {
                        "parameter": "innovation_bias",
                        "action": "increase",
                        "reason": f"Small improvements ({avg_improvement:.2f}%), try more innovation",
                        "suggested_change": 0.1,
                        "confidence": 0.5,
                    }
                )

        # Check for confidence issues
        low_conf_iterations = [
            r for r in self.iteration_history if r.confidence_score < 0.6
        ]
        if len(low_conf_iterations) > len(self.iteration_history) * 0.5:
            recommendations.append(
                {
                    "parameter": "confidence_threshold",
                    "action": "decrease",
                    "reason": f"Many low-confidence iterations ({len(low_conf_iterations)}/{len(self.iteration_history)})",
                    "suggested_change": -0.1,
                    "confidence": 0.8,
                }
            )

        # Check iteration count
        if (
            len(self.iteration_history)
            >= self.variable_parameters["max_iterations"].current_value
        ):
            recommendations.append(
                {
                    "parameter": "max_iterations",
                    "action": "increase",
                    "reason": f"Reached max iterations ({len(self.iteration_history)}) with potential for more improvement",
                    "suggested_change": 50,
                    "confidence": 0.4,
                }
            )

        return recommendations


# ============================================================================
# MAIN GUI APPLICATION
# ============================================================================


class CodeAlchemistGUI:
    """Main GUI application for Code Alchemist"""

    def __init__(self, root):
        self.root = root
        self.root.title("Code Alchemist v1.0")
        self.root.geometry("1400x900")

        # Setup project structure
        self.project_root = Path.cwd() / "code_alchemist_projects"
        self.setup_project_structure()

        # Initialize core components
        self.analyzer = CodeAnalyzer()
        self.hybrid_engine = HybridizationEngine(self.analyzer)

        # State
        self.selected_files = []
        self.current_build = None
        self.iteration_results = []
        self.variable_history = []

        # Setup GUI
        self.setup_styles()
        self.create_widgets()
        self.setup_bindings()

        # Start with console output
        self.log("Code Alchemist initialized")
        self.log(f"Project root: {self.project_root}")
        self.log(
            f"Analysis modules: {', '.join([k for k, v in ANALYSIS_MODULES.items() if v])}"
        )

    def setup_project_structure(self):
        """Create project directory structure"""
        directories = [
            self.project_root,
            self.project_root / "inventory",
            self.project_root / "stash",
            self.project_root / "stable_hybrids",
            self.project_root / "weird_keepers",
            self.project_root / "in_dev",
            self.project_root / "sandbox",
            self.project_root / "reports",
            self.project_root / "logs",
            self.project_root / "exports",
        ]

        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)

        # Create readme
        readme = self.project_root / "README.txt"
        if not readme.exists():
            with open(readme, "w") as f:
                f.write("Code Alchemist Project Structure\n")
                f.write("=" * 40 + "\n\n")
                f.write("inventory/      - Source files for analysis\n")
                f.write("stash/          - Temporary hybrid builds\n")
                f.write("stable_hybrids/ - Tested and working hybrids\n")
                f.write("weird_keepers/  - Interesting but unusual builds\n")
                f.write("in_dev/         - Builds under active development\n")
                f.write("sandbox/        - Experimental/test builds\n")
                f.write("reports/        - Analysis reports\n")
                f.write("logs/           - Session logs\n")
                f.write("exports/        - Final export location\n")

    def setup_styles(self):
        """Setup Tkinter styles"""
        style = ttk.Style()

        # Configure colors
        self.colors = {
            "bg_dark": "#1e1e1e",
            "bg_medium": "#2d2d2d",
            "bg_light": "#3c3c3c",
            "fg_light": "#d4d4d4",
            "fg_dark": "#858585",
            "accent": "#007acc",
            "success": "#4ec9b0",
            "warning": "#d7ba7d",
            "error": "#f44747",
            "info": "#569cd6",
        }

        # Configure root
        self.root.configure(bg=self.colors["bg_dark"])

        # Configure styles
        style.theme_use("clam")

        # Configure ttk styles
        style.configure(
            "Title.TLabel",
            font=("Segoe UI", 16, "bold"),
            foreground=self.colors["accent"],
        )

        style.configure(
            "Subtitle.TLabel",
            font=("Segoe UI", 12, "bold"),
            foreground=self.colors["fg_light"],
        )

        style.configure("Console.TFrame", background=self.colors["bg_medium"])

        style.configure(
            "Console.TText",
            background=self.colors["bg_medium"],
            foreground=self.colors["fg_light"],
            insertbackground=self.colors["fg_light"],
            font=("Consolas", 10),
        )

        style.configure("Score.TLabel", font=("Segoe UI", 10, "bold"), padding=5)

        style.configure(
            "Good.TLabel", background="#2d5a27", foreground=self.colors["success"]
        )

        style.configure(
            "Fair.TLabel", background="#5a4d27", foreground=self.colors["warning"]
        )

        style.configure(
            "Poor.TLabel", background="#5a2727", foreground=self.colors["error"]
        )

    def create_widgets(self):
        """Create all GUI widgets"""
        # Create main container
        main_container = ttk.Frame(self.root)
        main_container.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Create notebook for tabs
        self.notebook = ttk.Notebook(main_container)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        # Create tabs
        self.create_file_explorer_tab()
        self.create_analysis_tab()
        self.create_hybridization_tab()
        self.create_iteration_tab()
        self.create_variables_tab()
        self.create_console_tab()

        # Create status bar
        self.create_status_bar()

        # Create quick action toolbar
        self.create_toolbar()

    def create_file_explorer_tab(self):
        """Create file explorer tab"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="📁 File Explorer")

        # Split into left (tree) and right (preview)
        paned = ttk.PanedWindow(tab, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Left: File tree
        left_frame = ttk.Frame(paned)
        paned.add(left_frame, weight=1)

        ttk.Label(left_frame, text="Project Files", style="Subtitle.TLabel").pack(
            anchor=tk.W, padx=5, pady=5
        )

        # Create treeview with scrollbar
        tree_frame = ttk.Frame(left_frame)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.file_tree = ttk.Treeview(tree_frame, show="tree")
        scrollbar = ttk.Scrollbar(
            tree_frame, orient=tk.VERTICAL, command=self.file_tree.yview
        )
        self.file_tree.configure(yscrollcommand=scrollbar.set)

        self.file_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Populate tree
        self.populate_file_tree()

        # Right: File preview and controls
        right_frame = ttk.Frame(paned)
        paned.add(right_frame, weight=2)

        # Preview area
        ttk.Label(right_frame, text="File Preview", style="Subtitle.TLabel").pack(
            anchor=tk.W, padx=5, pady=5
        )

        preview_frame = ttk.Frame(right_frame)
        preview_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.preview_text = scrolledtext.ScrolledText(
            preview_frame,
            wrap=tk.WORD,
            font=("Consolas", 10),
            bg=self.colors["bg_medium"],
            fg=self.colors["fg_light"],
            insertbackground=self.colors["fg_light"],
        )
        self.preview_text.pack(fill=tk.BOTH, expand=True)

        # Control buttons
        button_frame = ttk.Frame(right_frame)
        button_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Button(
            button_frame, text="Add to Pot", command=self.add_selected_to_pot
        ).pack(side=tk.LEFT, padx=2)
        ttk.Button(
            button_frame, text="Analyze Selected", command=self.analyze_selected_file
        ).pack(side=tk.LEFT, padx=2)
        ttk.Button(
            button_frame, text="Refresh Tree", command=self.populate_file_tree
        ).pack(side=tk.LEFT, padx=2)

        # Bind tree selection
        self.file_tree.bind("<<TreeviewSelect>>", self.on_file_selected)

    def create_analysis_tab(self):
        """Create analysis results tab"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="🔍 Analysis")

        # Create notebook within tab for different analyses
        analysis_notebook = ttk.Notebook(tab)
        analysis_notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Overview tab
        overview_frame = ttk.Frame(analysis_notebook)
        analysis_notebook.add(overview_frame, text="Overview")

        # Create grid for metrics
        metrics_frame = ttk.Frame(overview_frame)
        metrics_frame.pack(fill=tk.X, padx=10, pady=10)

        # Quality metrics display
        self.metric_labels = {}
        metrics = [
            ("Overall Score", "overall_score"),
            ("Syntax Valid", "syntax_valid"),
            ("Lines of Code", "lines_of_code"),
            ("Functions", "function_count"),
            ("Classes", "class_count"),
            ("Complexity", "cyclomatic_complexity"),
            ("Maintainability", "maintainability_index"),
            ("Security Score", "security_score"),
            ("Comment Density", "comment_density"),
        ]

        for i, (label, key) in enumerate(metrics):
            row = i // 3
            col = i % 3

            frame = ttk.LabelFrame(metrics_frame, text=label, padding=5)
            frame.grid(row=row, column=col, padx=5, pady=5, sticky="nsew")

            label = ttk.Label(frame, text="N/A", font=("Segoe UI", 12, "bold"))
            label.pack()
            self.metric_labels[key] = label

        # Make grid columns expand equally
        for i in range(3):
            metrics_frame.columnconfigure(i, weight=1)

        # Details tab
        details_frame = ttk.Frame(analysis_notebook)
        analysis_notebook.add(details_frame, text="Details")

        self.details_text = scrolledtext.ScrolledText(
            details_frame,
            wrap=tk.WORD,
            font=("Consolas", 10),
            bg=self.colors["bg_medium"],
            fg=self.colors["fg_light"],
        )
        self.details_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Elements tab
        elements_frame = ttk.Frame(analysis_notebook)
        analysis_notebook.add(elements_frame, text="Elements")

        # Create treeview for elements
        element_frame = ttk.Frame(elements_frame)
        element_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        columns = ("name", "type", "category", "confidence", "complexity")
        self.element_tree = ttk.Treeview(
            element_frame, columns=columns, show="headings"
        )

        for col in columns:
            self.element_tree.heading(col, text=col.title())
            self.element_tree.column(col, width=100)

        scrollbar = ttk.Scrollbar(
            element_frame, orient=tk.VERTICAL, command=self.element_tree.yview
        )
        self.element_tree.configure(yscrollcommand=scrollbar.set)

        self.element_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    def create_hybridization_tab(self):
        """Create hybridization control tab"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="🧪 Hybridization")

        # Top: Pot display
        pot_frame = ttk.LabelFrame(tab, text="Mixing Pot", padding=10)
        pot_frame.pack(fill=tk.X, padx=10, pady=10)

        # Pot listbox
        list_frame = ttk.Frame(pot_frame)
        list_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        self.pot_listbox = tk.Listbox(
            list_frame,
            bg=self.colors["bg_medium"],
            fg=self.colors["fg_light"],
            selectbackground=self.colors["accent"],
            font=("Segoe UI", 10),
        )
        scrollbar = ttk.Scrollbar(
            list_frame, orient=tk.VERTICAL, command=self.pot_listbox.yview
        )
        self.pot_listbox.configure(yscrollcommand=scrollbar.set)

        self.pot_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Pot controls
        control_frame = ttk.Frame(pot_frame)
        control_frame.pack(fill=tk.X, pady=5)

        ttk.Button(control_frame, text="Clear Pot", command=self.clear_pot).pack(
            side=tk.LEFT, padx=2
        )
        ttk.Button(
            control_frame, text="Remove Selected", command=self.remove_from_pot
        ).pack(side=tk.LEFT, padx=2)

        # Middle: Hybridization controls
        hybrid_frame = ttk.LabelFrame(tab, text="Create Hybrid", padding=10)
        hybrid_frame.pack(fill=tk.X, padx=10, pady=10)

        # Hybrid name
        name_frame = ttk.Frame(hybrid_frame)
        name_frame.pack(fill=tk.X, pady=5)

        ttk.Label(name_frame, text="Hybrid Name:").pack(side=tk.LEFT)
        self.hybrid_name_var = tk.StringVar(value="hybrid_build")
        ttk.Entry(name_frame, textvariable=self.hybrid_name_var, width=30).pack(
            side=tk.LEFT, padx=5
        )

        # Create button
        ttk.Button(
            hybrid_frame,
            text="⚗️ Create Hybrid Build",
            command=self.create_hybrid,
            style="Accent.TButton",
        ).pack(pady=10)

        # Bottom: Current hybrid info
        info_frame = ttk.LabelFrame(tab, text="Current Hybrid", padding=10)
        info_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Score display
        scores_frame = ttk.Frame(info_frame)
        scores_frame.pack(fill=tk.X, pady=5)

        self.score_vars = {}
        score_types = [
            ("Overall", "overall"),
            ("Quality", "quality"),
            ("Compatibility", "compatibility"),
            ("Innovation", "innovation"),
            ("Stability", "stability"),
        ]

        for label, key in score_types:
            frame = ttk.Frame(scores_frame)
            frame.pack(side=tk.LEFT, padx=10)

            ttk.Label(frame, text=f"{label}:").pack()
            var = tk.StringVar(value="0.00")
            score_label = ttk.Label(
                frame, textvariable=var, font=("Segoe UI", 14, "bold")
            )
            score_label.pack()

            self.score_vars[key] = (var, score_label)

        # Hybrid info text
        self.hybrid_info_text = scrolledtext.ScrolledText(
            info_frame,
            height=8,
            wrap=tk.WORD,
            font=("Consolas", 9),
            bg=self.colors["bg_medium"],
            fg=self.colors["fg_light"],
        )
        self.hybrid_info_text.pack(fill=tk.BOTH, expand=True, pady=5)

    def create_iteration_tab(self):
        """Create iteration refinement tab"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="🔄 Iteration")

        # Left: Iteration controls
        left_frame = ttk.Frame(tab)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Iteration settings
        settings_frame = ttk.LabelFrame(
            left_frame, text="Iteration Settings", padding=10
        )
        settings_frame.pack(fill=tk.X, pady=5)

        # Max iterations
        iter_frame = ttk.Frame(settings_frame)
        iter_frame.pack(fill=tk.X, pady=2)

        ttk.Label(iter_frame, text="Max Iterations:").pack(side=tk.LEFT)
        self.max_iter_var = tk.StringVar(value="50")
        ttk.Entry(iter_frame, textvariable=self.max_iter_var, width=10).pack(
            side=tk.LEFT, padx=5
        )

        # Auto-stop threshold
        threshold_frame = ttk.Frame(settings_frame)
        threshold_frame.pack(fill=tk.X, pady=2)

        ttk.Label(threshold_frame, text="Improvement Threshold:").pack(side=tk.LEFT)
        self.threshold_var = tk.StringVar(value="0.1")
        ttk.Entry(threshold_frame, textvariable=self.threshold_var, width=10).pack(
            side=tk.LEFT, padx=5
        )

        # Control buttons
        button_frame = ttk.Frame(settings_frame)
        button_frame.pack(fill=tk.X, pady=10)

        ttk.Button(
            button_frame,
            text="▶️ Run Single Iteration",
            command=self.run_single_iteration,
        ).pack(side=tk.LEFT, padx=2)
        ttk.Button(
            button_frame, text="⏯️ Run Full Refinement", command=self.run_full_refinement
        ).pack(side=tk.LEFT, padx=2)
        ttk.Button(
            button_frame, text="🔄 Reset Iteration", command=self.reset_iteration
        ).pack(side=tk.LEFT, padx=2)

        # Iteration history
        history_frame = ttk.LabelFrame(left_frame, text="Iteration History", padding=10)
        history_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        # Create treeview for history
        tree_frame = ttk.Frame(history_frame)
        tree_frame.pack(fill=tk.BOTH, expand=True)

        columns = ("iter", "quality", "improvement", "confidence", "time", "changes")
        self.history_tree = ttk.Treeview(tree_frame, columns=columns, show="headings")

        headings = {
            "iter": "Iter",
            "quality": "Quality",
            "improvement": "Improvement",
            "confidence": "Confidence",
            "time": "Time (s)",
            "changes": "Changes",
        }

        for col in columns:
            self.history_tree.heading(col, text=headings[col])
            self.history_tree.column(col, width=80 if col != "changes" else 150)

        scrollbar = ttk.Scrollbar(
            tree_frame, orient=tk.VERTICAL, command=self.history_tree.yview
        )
        self.history_tree.configure(yscrollcommand=scrollbar.set)

        self.history_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Right: Iteration details
        right_frame = ttk.Frame(tab)
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Progress visualization
        progress_frame = ttk.LabelFrame(right_frame, text="Progress", padding=10)
        progress_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        # Create canvas for chart
        self.progress_canvas = tk.Canvas(
            progress_frame, bg=self.colors["bg_medium"], highlightthickness=0
        )
        self.progress_canvas.pack(fill=tk.BOTH, expand=True)

        # Iteration details
        details_frame = ttk.LabelFrame(
            right_frame, text="Iteration Details", padding=10
        )
        details_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        self.iteration_details_text = scrolledtext.ScrolledText(
            details_frame,
            wrap=tk.WORD,
            font=("Consolas", 9),
            bg=self.colors["bg_medium"],
            fg=self.colors["fg_light"],
        )
        self.iteration_details_text.pack(fill=tk.BOTH, expand=True)

        # Bind tree selection
        self.history_tree.bind("<<TreeviewSelect>>", self.on_iteration_selected)

    def create_variables_tab(self):
        """Create variable parameters tab"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="🎛️ Variables")

        # Split into left (controls) and right (effects)
        paned = ttk.PanedWindow(tab, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Left: Variable controls
        left_frame = ttk.Frame(paned)
        paned.add(left_frame, weight=2)

        ttk.Label(left_frame, text="Variable Parameters", style="Subtitle.TLabel").pack(
            anchor=tk.W, padx=5, pady=5
        )

        # Create scrollable frame for variables
        canvas = tk.Canvas(left_frame, bg=self.colors["bg_dark"])
        scrollbar = ttk.Scrollbar(left_frame, orient=tk.VERTICAL, command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)

        scrollable_frame.bind(
            "<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        # Create variable controls
        self.variable_widgets = {}
        variables = self.hybrid_engine.variable_parameters

        for var_name, param in variables.items():
            var_frame = ttk.LabelFrame(scrollable_frame, text=param.name, padding=10)
            var_frame.pack(fill=tk.X, padx=5, pady=5)

            # Description
            ttk.Label(var_frame, text=param.description, wraplength=400).pack(
                anchor=tk.W
            )

            # Value controls
            control_frame = ttk.Frame(var_frame)
            control_frame.pack(fill=tk.X, pady=5)

            # Current value label
            value_var = tk.StringVar(value=f"Current: {param.current_value}")
            value_label = ttk.Label(control_frame, textvariable=value_var)
            value_label.pack(side=tk.LEFT, padx=5)

            # Scale for numeric values
            if param.value_type in [int, float]:
                scale = tk.Scale(
                    control_frame,
                    from_=param.min_value,
                    to=param.max_value,
                    resolution=param.step,
                    orient=tk.HORIZONTAL,
                    length=200,
                    bg=self.colors["bg_medium"],
                    fg=self.colors["fg_light"],
                    highlightthickness=0,
                )
                scale.set(param.current_value)
                scale.pack(side=tk.LEFT, padx=5)

                # Update function
                def make_update_func(v_name, scale_widget, label_widget):
                    def update_func(event=None):
                        value = scale_widget.get()
                        self.hybrid_engine.variable_parameters[v_name].current_value = (
                            value
                        )
                        label_widget.set(f"Current: {value:.2f}")
                        self.log(f"Updated {v_name} = {value:.2f}")

                    return update_func

                scale.bind(
                    "<ButtonRelease-1>", make_update_func(var_name, scale, value_var)
                )

                self.variable_widgets[var_name] = (scale, value_var)

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Right: Recommendations and effects
        right_frame = ttk.Frame(paned)
        paned.add(right_frame, weight=1)

        # Recommendations
        rec_frame = ttk.LabelFrame(right_frame, text="Recommendations", padding=10)
        rec_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.recommendations_text = scrolledtext.ScrolledText(
            rec_frame,
            wrap=tk.WORD,
            height=15,
            font=("Consolas", 9),
            bg=self.colors["bg_medium"],
            fg=self.colors["fg_light"],
        )
        self.recommendations_text.pack(fill=tk.BOTH, expand=True)

        # Update recommendations button
        ttk.Button(
            right_frame,
            text="Update Recommendations",
            command=self.update_recommendations,
        ).pack(pady=5)

        # Effects visualization
        effects_frame = ttk.LabelFrame(
            right_frame, text="Parameter Effects", padding=10
        )
        effects_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.effects_text = scrolledtext.ScrolledText(
            effects_frame,
            wrap=tk.WORD,
            height=10,
            font=("Consolas", 9),
            bg=self.colors["bg_medium"],
            fg=self.colors["fg_light"],
        )
        self.effects_text.pack(fill=tk.BOTH, expand=True)

    def create_console_tab(self):
        """Create console/output tab"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="📝 Console")

        # Console text area
        self.console_text = scrolledtext.ScrolledText(
            tab,
            wrap=tk.WORD,
            font=("Consolas", 10),
            bg=self.colors["bg_medium"],
            fg=self.colors["fg_light"],
            insertbackground=self.colors["fg_light"],
        )
        self.console_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Make console read-only
        self.console_text.configure(state="disabled")

        # Console controls
        control_frame = ttk.Frame(tab)
        control_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Button(
            control_frame, text="Clear Console", command=self.clear_console
        ).pack(side=tk.LEFT, padx=2)
        ttk.Button(control_frame, text="Save Log", command=self.save_log).pack(
            side=tk.LEFT, padx=2
        )
        ttk.Button(
            control_frame, text="Copy to Clipboard", command=self.copy_console
        ).pack(side=tk.LEFT, padx=2)

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
            self.status_bar, variable=self.progress_var, mode="determinate", length=200
        )
        self.progress_bar.pack(side=tk.RIGHT, padx=5)

        # Iteration counter
        self.iteration_var = tk.StringVar(value="Iter: 0")
        ttk.Label(self.status_bar, textvariable=self.iteration_var).pack(
            side=tk.RIGHT, padx=10
        )

        # Build info
        self.build_var = tk.StringVar(value="Build: None")
        ttk.Label(self.status_bar, textvariable=self.build_var).pack(
            side=tk.RIGHT, padx=10
        )

    def create_toolbar(self):
        """Create quick action toolbar"""
        toolbar = ttk.Frame(self.root)
        toolbar.pack(side=tk.TOP, fill=tk.X, padx=5, pady=2)

        # Quick action buttons
        actions = [
            ("📂 Open File", self.open_file),
            ("🔍 Analyze All", self.analyze_all_files),
            ("⚗️ Quick Hybrid", self.quick_hybrid),
            ("🔄 Auto-Iterate", self.auto_iterate),
            ("💾 Save Session", self.save_session),
            ("📊 Export Report", self.export_report),
        ]

        for text, command in actions:
            ttk.Button(toolbar, text=text, command=command).pack(side=tk.LEFT, padx=2)

        # Add separator
        ttk.Separator(toolbar, orient=tk.VERTICAL).pack(
            side=tk.LEFT, padx=10, fill=tk.Y
        )

        # Add mode selector
        ttk.Label(toolbar, text="Mode:").pack(side=tk.LEFT, padx=2)
        self.mode_var = tk.StringVar(value="balanced")
        mode_menu = ttk.OptionMenu(
            toolbar,
            self.mode_var,
            "balanced",
            "balanced",
            "aggressive",
            "conservative",
            "experimental",
        )
        mode_menu.pack(side=tk.LEFT, padx=2)

    def setup_bindings(self):
        """Setup keyboard bindings"""
        self.root.bind("<Control-o>", lambda e: self.open_file())
        self.root.bind("<Control-s>", lambda e: self.save_session())
        self.root.bind("<Control-r>", lambda e: self.run_single_iteration())
        self.root.bind("<F5>", lambda e: self.refresh_all())
        self.root.bind("<Escape>", lambda e: self.root.quit())

    # ============================================================================
    # CORE FUNCTIONALITY
    # ============================================================================

    def log(self, message: str, level: str = "INFO"):
        """Log message to console"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] [{level}] {message}\n"

        self.console_text.configure(state="normal")
        self.console_text.insert(tk.END, log_entry)
        self.console_text.see(tk.END)
        self.console_text.configure(state="disabled")

        self.analyzer.console_output.append(log_entry.strip())

        # Update status for important messages
        if level in ["ERROR", "WARNING"]:
            self.status_var.set(f"{level}: {message[:50]}")

    def populate_file_tree(self):
        """Populate file tree with project structure"""
        self.file_tree.delete(*self.file_tree.get_children())

        # Add project root
        root_id = self.file_tree.insert(
            "",
            "end",
            text=self.project_root.name,
            values=[str(self.project_root)],
            open=True,
        )

        # Add directories
        for directory in self.project_root.iterdir():
            if directory.is_dir() and not directory.name.startswith("."):
                dir_id = self.file_tree.insert(
                    root_id,
                    "end",
                    text=directory.name,
                    values=[str(directory)],
                    open=True,
                )

                # Add Python files
                for py_file in directory.glob("*.py"):
                    self.file_tree.insert(
                        dir_id, "end", text=py_file.name, values=[str(py_file)]
                    )

    def on_file_selected(self, event):
        """Handle file selection in tree"""
        selection = self.file_tree.selection()
        if not selection:
            return

        item = self.file_tree.item(selection[0])
        filepath = Path(item["values"][0])

        if filepath.is_file() and filepath.suffix == ".py":
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    content = f.read()

                self.preview_text.delete(1.0, tk.END)
                self.preview_text.insert(1.0, content)

                # Syntax highlighting (basic)
                self.apply_syntax_highlighting(filepath)

            except Exception as e:
                self.log(f"Error reading file {filepath}: {e}", "ERROR")

    def apply_syntax_highlighting(self, filepath: Path):
        """Apply basic syntax highlighting"""
        # This is a simplified version - in production, use a proper syntax highlighter
        content = self.preview_text.get(1.0, tk.END)

        # Configure tags
        self.preview_text.tag_configure("keyword", foreground="#569cd6")
        self.preview_text.tag_configure("string", foreground="#ce9178")
        self.preview_text.tag_configure("comment", foreground="#6a9955")
        self.preview_text.tag_configure("function", foreground="#dcdcaa")
        self.preview_text.tag_configure("class", foreground="#4ec9b0")

        # Remove existing tags
        for tag in ["keyword", "string", "comment", "function", "class"]:
            self.preview_text.tag_remove(tag, 1.0, tk.END)

        # Apply highlighting (simplified)
        keywords = [
            "import",
            "from",
            "class",
            "def",
            "if",
            "else",
            "elif",
            "for",
            "while",
            "try",
            "except",
            "with",
            "as",
        ]

        lines = content.split("\n")
        pos = 0

        for line in lines:
            # Highlight keywords
            for keyword in keywords:
                idx = line.find(keyword)
                while idx != -1:
                    # Check if it's a whole word
                    if (idx == 0 or not line[idx - 1].isalnum()) and (
                        idx + len(keyword) == len(line)
                        or not line[idx + len(keyword)].isalnum()
                    ):
                        start = f"1.0+{pos + idx}c"
                        end = f"1.0+{pos + idx + len(keyword)}c"
                        self.preview_text.tag_add("keyword", start, end)
                    idx = line.find(keyword, idx + 1)

            # Highlight strings
            in_string = False
            string_char = None
            for i, char in enumerate(line):
                if char in ['"', "'"] and (i == 0 or line[i - 1] != "\\"):
                    if not in_string:
                        in_string = True
                        string_char = char
                        string_start = i
                    elif char == string_char:
                        in_string = False
                        start = f"1.0+{pos + string_start}c"
                        end = f"1.0+{pos + i + 1}c"
                        self.preview_text.tag_add("string", start, end)

            # Highlight comments
            if "#" in line:
                comment_start = line.find("#")
                start = f"1.0+{pos + comment_start}c"
                end = f"1.0+{pos + len(line)}c"
                self.preview_text.tag_add("comment", start, end)

            pos += len(line) + 1  # +1 for newline

    def add_selected_to_pot(self):
        """Add selected file to mixing pot"""
        selection = self.file_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a file first")
            return

        for item_id in selection:
            item = self.file_tree.item(item_id)
            filepath = Path(item["values"][0])

            if filepath.is_file() and filepath.suffix == ".py":
                if str(filepath) not in self.pot_listbox.get(0, tk.END):
                    self.pot_listbox.insert(tk.END, str(filepath))
                    self.selected_files.append(filepath)
                    self.log(f"Added to pot: {filepath.name}")

        self.update_pot_stats()

    def clear_pot(self):
        """Clear mixing pot"""
        self.pot_listbox.delete(0, tk.END)
        self.selected_files.clear()
        self.log("Cleared mixing pot")

    def remove_from_pot(self):
        """Remove selected item from pot"""
        selection = self.pot_listbox.curselection()
        if not selection:
            return

        for idx in reversed(selection):
            filepath = Path(self.pot_listbox.get(idx))
            self.pot_listbox.delete(idx)

            if filepath in self.selected_files:
                self.selected_files.remove(filepath)

            self.log(f"Removed from pot: {filepath.name}")

        self.update_pot_stats()

    def update_pot_stats(self):
        """Update pot statistics display"""
        count = self.pot_listbox.size()
        self.status_var.set(f"Pot contains {count} file(s)")

    def analyze_selected_file(self):
        """Analyze selected file"""
        selection = self.file_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a file first")
            return

        item = self.file_tree.item(selection[0])
        filepath = Path(item["values"][0])

        if not filepath.is_file() or filepath.suffix != ".py":
            messagebox.showwarning("Warning", "Please select a Python file")
            return

        self.log(f"Analyzing {filepath.name}...")
        self.status_var.set(f"Analyzing {filepath.name}...")

        # Run analysis in thread
        def analyze_thread():
            try:
                analysis = self.analyzer.analyze_file(filepath)

                # Update UI in main thread
                self.root.after(0, self.update_analysis_display, analysis)
                self.root.after(0, self.log, f"Analysis complete for {filepath.name}")
                self.root.after(0, lambda: self.status_var.set("Analysis complete"))

            except Exception as e:
                self.root.after(0, self.log, f"Analysis error: {e}", "ERROR")
                self.root.after(0, lambda: self.status_var.set("Analysis failed"))

        threading.Thread(target=analyze_thread, daemon=True).start()

    def analyze_all_files(self):
        """Analyze all Python files in project"""
        python_files = list(self.project_root.rglob("*.py"))
        if not python_files:
            messagebox.showinfo("Info", "No Python files found in project")
            return

        self.log(f"Analyzing {len(python_files)} Python files...")

        def analyze_all_thread():
            total = len(python_files)
            for i, filepath in enumerate(python_files):
                try:
                    self.analyzer.analyze_file(filepath)

                    # Update progress
                    progress = (i + 1) / total * 100
                    self.root.after(0, self.progress_var.set, progress)

                    if (i + 1) % 10 == 0:
                        self.root.after(0, self.log, f"Analyzed {i+1}/{total} files")

                except Exception as e:
                    self.root.after(
                        0, self.log, f"Error analyzing {filepath}: {e}", "ERROR"
                    )

            self.root.after(0, self.log, f"Complete: Analyzed {total} files")
            self.root.after(0, self.progress_var.set, 0)
            self.root.after(0, lambda: self.status_var.set("Analysis complete"))

        threading.Thread(target=analyze_all_thread, daemon=True).start()

    def update_analysis_display(self, analysis: Dict):
        """Update analysis display with results"""
        # Update metrics
        metrics = analysis.get("quality_metrics", {})

        # Overall score
        if "overall_score" in analysis:
            score = analysis["overall_score"]
            self.metric_labels["overall_score"].configure(text=f"{score:.1f}")
            self.set_score_color(self.metric_labels["overall_score"], score)

        # Syntax valid
        valid = analysis.get("syntax_valid", False)
        self.metric_labels["syntax_valid"].configure(
            text="✓" if valid else "✗",
            foreground=self.colors["success"] if valid else self.colors["error"],
        )

        # Other metrics
        metric_map = {
            "lines_of_code": ("lines_of_code", "N/A"),
            "function_count": ("function_count", "N/A"),
            "class_count": ("class_count", "N/A"),
            "cyclomatic_complexity": ("cyclomatic_complexity", "N/A"),
            "maintainability_index": ("maintainability_index", "N/A"),
            "comment_density": ("comment_density", "N/A"),
        }

        for key, (label_key, default) in metric_map.items():
            value = metrics.get(key, default)
            if value != default:
                if key == "maintainability_index" and isinstance(value, (int, float)):
                    self.metric_labels[label_key].configure(text=f"{value:.1f}")
                    self.set_score_color(self.metric_labels[label_key], value)
                elif isinstance(value, (int, float)):
                    self.metric_labels[label_key].configure(text=f"{value:.1f}")
                else:
                    self.metric_labels[label_key].configure(text=str(value))

        # Security score
        security = analysis.get("security", {}).get("score", "N/A")
        if security != "N/A":
            self.metric_labels["security_score"].configure(text=f"{security:.1f}")
            self.set_score_color(self.metric_labels["security_score"], security)

        # Update details text
        self.details_text.delete(1.0, tk.END)

        details = [
            f"File: {analysis.get('file', 'N/A')}",
            f"Name: {analysis.get('name', 'N/A')}",
            f"Size: {analysis.get('size', 0)} bytes",
            f"Modified: {analysis.get('modified', 'N/A')}",
            "",
            "=== IMPORTS ===",
            *[f"  • {imp}" for imp in analysis.get("imports", [])],
            "",
            "=== RISK FACTORS ===",
            *[f"  • {risk}" for risk in analysis.get("risk_factors", [])],
            "",
            "=== LINTING ===",
        ]

        linting = analysis.get("linting", {})
        for tool, result in linting.items():
            if isinstance(result, dict) and "output" in result:
                details.append(f"  {tool.upper()}: {result.get('output', '')[:100]}...")

        self.details_text.insert(1.0, "\n".join(details))

        # Update elements tree
        self.element_tree.delete(*self.element_tree.get_children())

        elements = analysis.get("elements", [])
        for elem in elements[:50]:  # Limit to 50 elements
            self.element_tree.insert(
                "",
                tk.END,
                values=(
                    elem.name,
                    elem.element_type,
                    elem.category.value,
                    f"{elem.confidence:.2f}",
                    f"{elem.complexity_score:.1f}",
                ),
            )

    def set_score_color(self, label, score: float):
        """Set label color based on score"""
        if score >= 80:
            label.configure(foreground=self.colors["success"])
        elif score >= 60:
            label.configure(foreground=self.colors["warning"])
        else:
            label.configure(foreground=self.colors["error"])

    def create_hybrid(self):
        """Create a hybrid build from pot contents"""
        if len(self.selected_files) < 2:
            messagebox.showwarning(
                "Warning", "Need at least 2 files in pot to create hybrid"
            )
            return

        name = self.hybrid_name_var.get().strip()
        if not name:
            name = f"hybrid_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        self.log(f"Creating hybrid '{name}' from {len(self.selected_files)} files...")
        self.status_var.set("Creating hybrid...")

        def create_hybrid_thread():
            try:
                build = self.hybrid_engine.create_hybrid(self.selected_files, name)
                self.current_build = build

                # Update UI
                self.root.after(0, self.update_hybrid_display, build)
                self.root.after(0, self.log, f"Created hybrid: {build.name}")
                self.root.after(0, self.build_var.set, f"Build: {build.name}")
                self.root.after(0, lambda: self.status_var.set("Hybrid created"))

            except Exception as e:
                self.root.after(0, self.log, f"Error creating hybrid: {e}", "ERROR")
                self.root.after(
                    0, lambda: self.status_var.set("Hybrid creation failed")
                )

        threading.Thread(target=create_hybrid_thread, daemon=True).start()

    def update_hybrid_display(self, build: HybridBuild):
        """Update hybrid build display"""
        # Update scores
        self.score_vars["overall"][0].set(f"{build.overall_score:.2f}")
        self.score_vars["quality"][0].set(f"{build.quality_score:.2f}")
        self.score_vars["compatibility"][0].set(f"{build.compatibility_score:.2f}")
        self.score_vars["innovation"][0].set(f"{build.innovation_score:.2f}")
        self.score_vars["stability"][0].set(f"{build.stability_score:.2f}")

        # Set score colors
        for key, (var, label) in self.score_vars.items():
            score = float(var.get().split(":")[-1].strip())
            self.set_score_color(label, score)

        # Update info text
        self.hybrid_info_text.delete(1.0, tk.END)

        info = [
            f"Hybrid: {build.name}",
            f"ID: {build.id}",
            f"Created: {build.created}",
            f"Parent Files: {len(build.parent_files)}",
            f"Elements: {len(build.elements)}",
            f"Syntax Valid: {'✓' if build.syntax_valid else '✗'}",
            f"Runnable: {'✓' if build.runnable else '✗'}",
            "",
            "=== PARENT FILES ===",
            *[f"  • {p.name}" for p in build.parent_files],
            "",
            "=== METADATA ===",
            *[f"  {k}: {v}" for k, v in build.metadata.items()],
        ]

        self.hybrid_info_text.insert(1.0, "\n".join(info))

    def run_single_iteration(self):
        """Run a single refinement iteration"""
        if not self.current_build:
            messagebox.showwarning("Warning", "No hybrid build selected")
            return

        self.log(f"Running iteration on {self.current_build.name}...")
        self.status_var.set("Running iteration...")

        def iteration_thread():
            try:
                result = self.hybrid_engine.run_iteration(self.current_build)
                self.iteration_results.append(result)

                # Update UI
                self.root.after(0, self.update_iteration_display, result)
                self.root.after(0, self.update_progress_chart)
                self.root.after(0, self.update_hybrid_display, self.current_build)
                self.root.after(
                    0, self.iteration_var.set, f"Iter: {len(self.iteration_results)}"
                )

                self.root.after(
                    0,
                    self.log,
                    f"Iteration {result.iteration}: Quality {result.quality_after:.2f} "
                    f"(Δ{result.improvement:+.2f}%)",
                )
                self.root.after(
                    0,
                    lambda: self.status_var.set(
                        f"Iteration {result.iteration} complete"
                    ),
                )

            except Exception as e:
                self.root.after(0, self.log, f"Iteration error: {e}", "ERROR")
                self.root.after(0, lambda: self.status_var.set("Iteration failed"))

        threading.Thread(target=iteration_thread, daemon=True).start()

    def run_full_refinement(self):
        """Run full iterative refinement"""
        if not self.current_build:
            messagebox.showwarning("Warning", "No hybrid build selected")
            return

        try:
            max_iter = int(self.max_iter_var.get())
        except ValueError:
            max_iter = 50

        self.log(f"Starting full refinement (max {max_iter} iterations)...")

        def refinement_thread():
            results = self.hybrid_engine.run_iterative_refinement(
                self.current_build, max_iter
            )

            # Update iteration count
            self.root.after(0, self.iteration_var.set, f"Iter: {len(results)}")
            self.root.after(0, self.update_progress_chart)
            self.root.after(0, lambda: self.status_var.set("Refinement complete"))

            # Show summary
            if results:
                last = results[-1]
                improvement = last.quality_after - results[0].quality_before
                self.root.after(
                    0,
                    self.log,
                    f"Refinement complete: {len(results)} iterations, "
                    f"total improvement: {improvement:+.2f}",
                )

        threading.Thread(target=refinement_thread, daemon=True).start()

    def reset_iteration(self):
        """Reset iteration history"""
        self.iteration_results.clear()
        self.hybrid_engine.iteration_history.clear()

        # Clear history tree
        self.history_tree.delete(*self.history_tree.get_children())

        # Clear progress chart
        self.progress_canvas.delete("all")
        self.iteration_details_text.delete(1.0, tk.END)

        self.iteration_var.set("Iter: 0")
        self.log("Iteration history reset")

    def update_iteration_display(self, result: IterationResult):
        """Update iteration history display"""
        # Add to history tree
        self.history_tree.insert(
            "",
            tk.END,
            values=(
                result.iteration,
                f"{result.quality_after:.2f}",
                f"{result.improvement:+.2f}%",
                f"{result.confidence_score:.2f}",
                f"{result.execution_time:.2f}",
                f"{len(result.changes_applied)} changes",
            ),
        )

    def update_progress_chart(self):
        """Update progress chart with iteration history"""
        if not self.iteration_results:
            return

        # Clear canvas
        self.progress_canvas.delete("all")

        # Get dimensions
        width = self.progress_canvas.winfo_width()
        height = self.progress_canvas.winfo_height()

        if width < 10 or height < 10:
            return

        # Calculate scales
        max_iter = max(r.iteration for r in self.iteration_results)
        qualities = [r.quality_after for r in self.iteration_results]

        if not qualities:
            return

        min_quality = min(qualities)
        max_quality = max(qualities)
        quality_range = max_quality - min_quality

        if quality_range == 0:
            quality_range = 1

        # Draw axes
        padding = 40
        plot_width = width - 2 * padding
        plot_height = height - 2 * padding

        # X-axis
        self.progress_canvas.create_line(
            padding,
            height - padding,
            width - padding,
            height - padding,
            fill=self.colors["fg_light"],
        )

        # Y-axis
        self.progress_canvas.create_line(
            padding, padding, padding, height - padding, fill=self.colors["fg_light"]
        )

        # Draw quality line
        points = []
        for i, result in enumerate(self.iteration_results):
            x = padding + (i / max_iter) * plot_width
            y = (
                height
                - padding
                - ((result.quality_after - min_quality) / quality_range) * plot_height
            )

            points.extend([x, y])

            # Draw point
            self.progress_canvas.create_oval(
                x - 3, y - 3, x + 3, y + 3, fill=self.colors["accent"], outline=""
            )

        # Draw line connecting points
        if len(points) >= 4:
            self.progress_canvas.create_line(
                *points, fill=self.colors["accent"], width=2, smooth=True
            )

        # Draw labels
        self.progress_canvas.create_text(
            width // 2,
            height - padding + 20,
            text="Iteration",
            fill=self.colors["fg_light"],
        )

        self.progress_canvas.create_text(
            padding - 30,
            height // 2,
            text="Quality",
            fill=self.colors["fg_light"],
            angle=90,
        )

    def on_iteration_selected(self, event):
        """Handle iteration selection"""
        selection = self.history_tree.selection()
        if not selection:
            return

        item = self.history_tree.item(selection[0])
        values = item["values"]

        if not values:
            return

        iter_num = values[0]

        # Find corresponding result
        result = None
        for r in self.iteration_results:
            if r.iteration == iter_num:
                result = r
                break

        if not result:
            return

        # Update details text
        self.iteration_details_text.delete(1.0, tk.END)

        details = [
            f"Iteration: {result.iteration}",
            f"Timestamp: {result.timestamp}",
            f"Quality Before: {result.quality_before:.2f}",
            f"Quality After: {result.quality_after:.2f}",
            f"Improvement: {result.improvement:+.2f}%",
            f"Confidence: {result.confidence_score:.2f}",
            f"Execution Time: {result.execution_time:.2f}s",
            f"Success: {'✓' if result.success else '✗'}",
            "",
            "=== CHANGES APPLIED ===",
            *[f"  • {change}" for change in result.changes_applied],
            "",
            "=== ERRORS ===",
            *(
                [f"  • {error}" for error in result.errors]
                if result.errors
                else ["  None"]
            ),
            "",
            "=== WARNINGS ===",
            *(
                [f"  • {warning}" for warning in result.warnings]
                if result.warnings
                else ["  None"]
            ),
        ]

        self.iteration_details_text.insert(1.0, "\n".join(details))

    def update_recommendations(self):
        """Update variable recommendations"""
        recommendations = self.hybrid_engine.get_variable_recommendations()

        self.recommendations_text.delete(1.0, tk.END)

        if not recommendations:
            self.recommendations_text.insert(
                1.0, "No recommendations available.\nRun some iterations first."
            )
            return

        # Group recommendations by parameter
        rec_by_param = defaultdict(list)
        for rec in recommendations:
            rec_by_param[rec["parameter"]].append(rec)

        # Display recommendations
        lines = ["=== VARIABLE RECOMMENDATIONS ===\n"]

        for param, recs in rec_by_param.items():
            lines.append(f"\n{param.upper()}:")

            for rec in recs:
                action = rec["action"]
                change = rec["suggested_change"]
                reason = rec["reason"]
                confidence = rec["confidence"]

                lines.append(f"  {action.title()} by {change}")
                lines.append(f"    Reason: {reason}")
                lines.append(f"    Confidence: {confidence:.1%}")
                lines.append("")

        self.recommendations_text.insert(1.0, "\n".join(lines))

        # Update effects text
        self.update_effects_text()

    def update_effects_text(self):
        """Update parameter effects text"""
        # This would analyze how parameters affect outcomes
        # For now, show some placeholder text
        effects = [
            "=== PARAMETER EFFECTS ===",
            "",
            "Mutation Rate:",
            "  • Higher = More variation, less stability",
            "  • Lower = More predictable, less innovation",
            "",
            "Crossover Rate:",
            "  • Higher = More combination of parent features",
            "  • Lower = More preservation of individual features",
            "",
            "Innovation Bias:",
            "  • Higher = More experimental combinations",
            "  • Lower = More conservative, proven approaches",
            "",
            "Confidence Threshold:",
            "  • Higher = Only high-quality elements used",
            "  • Lower = More elements available for mixing",
            "",
            "Temperature:",
            "  • Higher = More exploration, less exploitation",
            "  • Lower = Focus on local optimization",
        ]

        self.effects_text.delete(1.0, tk.END)
        self.effects_text.insert(1.0, "\n".join(effects))

    def clear_console(self):
        """Clear console output"""
        self.console_text.configure(state="normal")
        self.console_text.delete(1.0, tk.END)
        self.console_text.configure(state="disabled")
        self.analyzer.console_output.clear()

    def save_log(self):
        """Save console log to file"""
        filename = filedialog.asksaveasfilename(
            defaultextension=".log",
            filetypes=[
                ("Log files", "*.log"),
                ("Text files", "*.txt"),
                ("All files", "*.*"),
            ],
        )

        if filename:
            try:
                with open(filename, "w") as f:
                    f.write(self.console_text.get(1.0, tk.END))
                self.log(f"Log saved to {filename}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save log: {e}")

    def copy_console(self):
        """Copy console content to clipboard"""
        content = self.console_text.get(1.0, tk.END)
        self.root.clipboard_clear()
        self.root.clipboard_append(content)
        self.log("Console content copied to clipboard")

    def open_file(self):
        """Open file dialog to add files to project"""
        files = filedialog.askopenfilenames(
            title="Select Python files",
            filetypes=[("Python files", "*.py"), ("All files", "*.*")],
        )

        if files:
            for filepath in files:
                dest = self.project_root / "inventory" / Path(filepath).name
                shutil.copy2(filepath, dest)
                self.log(f"Added to inventory: {dest.name}")

            self.populate_file_tree()

    def quick_hybrid(self):
        """Create a quick hybrid with default settings"""
        # Add some random files from inventory if pot is empty
        if not self.selected_files:
            inventory_files = list((self.project_root / "inventory").glob("*.py"))
            if len(inventory_files) >= 2:
                self.selected_files = random.sample(
                    inventory_files, min(3, len(inventory_files))
                )
                for filepath in self.selected_files:
                    self.pot_listbox.insert(tk.END, str(filepath))

        if len(self.selected_files) >= 2:
            self.create_hybrid()
        else:
            messagebox.showwarning("Warning", "Need at least 2 files for hybridization")

    def auto_iterate(self):
        """Auto-run iterations until good quality is reached"""
        if not self.current_build:
            messagebox.showwarning("Warning", "No hybrid build selected")
            return

        self.log("Starting auto-iteration mode...")

        def auto_iterate_thread():
            target_quality = 85.0
            max_auto_iterations = 100
            iterations = 0

            while (
                self.current_build.overall_score < target_quality
                and iterations < max_auto_iterations
            ):
                iterations += 1

                self.log(f"Auto-iteration {iterations}...")
                result = self.hybrid_engine.run_iteration(self.current_build)
                self.iteration_results.append(result)

                # Update UI
                self.root.after(
                    0, self.iteration_var.set, f"Iter: {len(self.iteration_results)}"
                )
                self.root.after(0, self.update_hybrid_display, self.current_build)

                # Check for stagnation
                if iterations > 10 and result.improvement < 0.1:
                    self.root.after(
                        0, self.log, "Auto-iteration stopped: stagnation detected"
                    )
                    break

            self.root.after(
                0,
                self.log,
                f"Auto-iteration complete: {iterations} iterations, "
                f"quality: {self.current_build.overall_score:.2f}",
            )
            self.root.after(0, self.update_progress_chart)

        threading.Thread(target=auto_iterate_thread, daemon=True).start()

    def save_session(self):
        """Save current session state"""
        session_file = self.project_root / "session_state.pkl"

        try:
            session_data = {
                "selected_files": self.selected_files,
                "current_build": self.current_build,
                "iteration_results": self.iteration_results,
                "variable_parameters": self.hybrid_engine.variable_parameters,
                "console_log": self.analyzer.console_output,
            }

            with open(session_file, "wb") as f:
                pickle.dump(session_data, f)

            self.log(f"Session saved to {session_file}")

        except Exception as e:
            self.log(f"Error saving session: {e}", "ERROR")

    def export_report(self):
        """Export comprehensive report"""
        report_file = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[
                ("JSON files", "*.json"),
                ("Text files", "*.txt"),
                ("All files", "*.*"),
            ],
        )

        if not report_file:
            return

        try:
            report_data = {
                "timestamp": datetime.now().isoformat(),
                "project": str(self.project_root),
                "selected_files": [str(f) for f in self.selected_files],
                "current_build": (
                    asdict(self.current_build) if self.current_build else None
                ),
                "iteration_count": len(self.iteration_results),
                "variable_parameters": {
                    name: asdict(param)
                    for name, param in self.hybrid_engine.variable_parameters.items()
                },
                "analysis_cache_size": len(self.analyzer.analysis_cache),
                "element_registry_size": len(self.analyzer.element_registry),
            }

            with open(report_file, "w") as f:
                json.dump(report_data, f, indent=2, default=str)

            self.log(f"Report exported to {report_file}")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to export report: {e}")

    def refresh_all(self):
        """Refresh all displays"""
        self.populate_file_tree()
        self.update_pot_stats()

        if self.current_build:
            self.update_hybrid_display(self.current_build)

        self.update_progress_chart()
        self.update_recommendations()

        self.log("All displays refreshed")


# ============================================================================
# COMMAND LINE INTERFACE
# ============================================================================


def main():
    """Main entry point with CLI support"""
    parser = argparse.ArgumentParser(
        description="Code Alchemist - GUI Code Hybridization Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                         # Launch GUI
  %(prog)s --analyze file.py       # Analyze single file
  %(prog)s --hybrid file1.py file2.py  # Create hybrid from files
  %(prog)s --batch /path/to/files  # Batch analyze directory
  %(prog)s --iterations 100        # Run iterations on current build
        
Features:
  • Analyze Python/Tkinter code structure
  • Create hybrid builds from multiple sources
  • Iterative refinement with confidence scoring
  • Variable parameter tuning
  • Real-time statistics and logging
        """,
    )

    parser.add_argument("--analyze", "-a", metavar="FILE", help="Analyze a Python file")
    parser.add_argument(
        "--hybrid", nargs="+", metavar="FILE", help="Create hybrid from files"
    )
    parser.add_argument("--batch", "-b", metavar="DIR", help="Batch analyze directory")
    parser.add_argument(
        "--iterations", "-i", type=int, default=0, help="Number of iterations to run"
    )
    parser.add_argument("--output", "-o", metavar="DIR", help="Output directory")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("--no-gui", action="store_true", help="Run in CLI mode only")

    args = parser.parse_args()

    # CLI mode
    if args.no_gui or args.analyze or args.hybrid or args.batch:
        print("Code Alchemist - CLI Mode")
        print("=" * 50)

        analyzer = CodeAnalyzer()

        if args.analyze:
            print(f"Analyzing: {args.analyze}")
            analysis = analyzer.analyze_file(Path(args.analyze))
            print(f"\nResults for {analysis['name']}:")
            print(f"  Overall Score: {analysis.get('overall_score', 0):.2f}")
            print(f"  Syntax Valid: {analysis.get('syntax_valid', False)}")
            print(f"  Elements: {len(analysis.get('elements', []))}")
            print(f"  Risk Factors: {len(analysis.get('risk_factors', []))}")

        elif args.hybrid:
            print(f"Creating hybrid from {len(args.hybrid)} files...")
            files = [Path(f) for f in args.hybrid]

            hybrid_engine = HybridizationEngine(analyzer)
            build = hybrid_engine.create_hybrid(files, "cli_hybrid")

            print(f"\nHybrid Created: {build.name}")
            print(f"  Overall Score: {build.overall_score:.2f}")
            print(f"  Quality: {build.quality_score:.2f}")
            print(f"  Innovation: {build.innovation_score:.2f}")
            print(f"  Output: {build.output_path}")

        elif args.batch:
            print(f"Batch analyzing: {args.batch}")
            directory = Path(args.batch)
            python_files = list(directory.rglob("*.py"))

            for i, filepath in enumerate(python_files, 1):
                print(f"[{i}/{len(python_files)}] Analyzing {filepath.name}...")
                analyzer.analyze_file(filepath)

            print(f"\nBatch complete: {len(python_files)} files analyzed")

        if args.iterations > 0 and "build" in locals():
            print(f"\nRunning {args.iterations} iterations...")
            results = hybrid_engine.run_iterative_refinement(build, args.iterations)

            if results:
                last = results[-1]
                print(f"  Final Quality: {last.quality_after:.2f}")
                print(
                    f"  Total Improvement: {last.quality_after - results[0].quality_before:+.2f}"
                )
                print(f"  Iterations Run: {len(results)}")

        return

    # GUI mode
    try:
        root = tk.Tk()
        app = CodeAlchemistGUI(root)

        # Center window
        root.update_idletasks()
        width = root.winfo_width()
        height = root.winfo_height()
        x = (root.winfo_screenwidth() // 2) - (width // 2)
        y = (root.winfo_screenheight() // 2) - (height // 2)
        root.geometry(f"{width}x{height}+{x}+{y}")

        root.mainloop()

    except Exception as e:
        print(f"Error starting GUI: {e}")
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
