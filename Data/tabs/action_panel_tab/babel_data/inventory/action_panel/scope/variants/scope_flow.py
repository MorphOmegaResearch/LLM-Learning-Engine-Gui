#!/usr/bin/env python3
"""
Enhanced Tkinter Object Inspector with Multi-Phase Analysis & Auto-Fixer
===============================================================
Usage:
    python3 inspector.py                       # Run hover inspector
    python3 inspector.py --scope               # Open scope analysis dialog
    python3 inspector.py --analyze --auto      # Full automated analysis/fix
    python3 inspector.py --analyze --stepwise  # Interactive turn-based
    python3 inspector.py --gui-review          # Live GUI review mode
    python3 inspector.py --workflow=all        # Run complete workflow
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext, colorchooser
import argparse
import os
import sys
import time
import threading
import queue
import subprocess
import inspect
from pathlib import Path
import shutil
import re
from datetime import datetime
import platform
import json
import ast
import difflib
import tempfile
import hashlib
from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Set, Any, Optional, Union
from collections import defaultdict
import traceback
import webbrowser

# ============================================================================
# grep_flight Integration Module
# ============================================================================
class GrepFlightIntegration:
    """Integration with grep_flight for target setting"""

    def __init__(self):
        self.stable_script = Path("/home/commander/3_Inventory/Warrior_Flow/target_stable.sh")
        self.dev_script = Path("/home/commander/3_Inventory/Warrior_Flow/versions/Warrior_Flow_v0_9v_Monkeys_Toolsv2b/Modules/action_panel/grep_flight_v0_2b/target.sh")
        self.log_file = Path(os.getenv('XDG_RUNTIME_DIR', '/tmp')) / f"scope_grep_integration_{os.getenv('USER', 'user')}.log"

    def log_debug(self, message, level="INFO"):
        """Log debug message with timestamp"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%3N")
        log_entry = f"[{timestamp}] [{level}] {message}"
        print(log_entry)
        try:
            with open(self.log_file, 'a') as f:
                f.write(log_entry + '\n')
        except Exception as e:
            print(f"Warning: Could not write to log file: {e}")
        return log_entry

    def send_to_grep_flight(self, file_path, stable=True, context=None):
        """
        Send file path to grep_flight as target

        Args:
            file_path: Path to file to set as target
            stable: True for stable version, False for dev version
            context: Additional context info (widget class, etc.)

        Returns:
            (success: bool, message: str)
        """
        self.log_debug("="*60)
        self.log_debug("SCOPE → grep_flight Target Request")
        self.log_debug("="*60)

        # Step 1: Validate file path
        self.log_debug(f"Step 1: Validating file path: {file_path}")
        file_path = Path(file_path).resolve()

        if not file_path.exists():
            error_msg = f"File does not exist: {file_path}"
            self.log_debug(error_msg, "ERROR")
            return False, error_msg

        self.log_debug(f"✓ File exists: {file_path}")

        # Step 2: Determine which script to use
        script = self.stable_script if stable else self.dev_script
        version = "Stable" if stable else "Dev"
        self.log_debug(f"Step 2: Using {version} version")
        self.log_debug(f"  Script: {script}")

        if not script.exists():
            error_msg = f"Target script not found: {script}"
            self.log_debug(error_msg, "ERROR")
            return False, error_msg

        self.log_debug(f"✓ Target script exists")

        # Step 3: Prepare context information
        context_str = ""
        if context:
            context_str = f" | Context: {context}"
            self.log_debug(f"Step 3: Context provided: {context}")
        else:
            self.log_debug(f"Step 3: No context provided")

        # Step 4: Execute target script
        self.log_debug(f"Step 4: Executing target script...")
        self.log_debug(f"  Command: {script} {file_path}")

        try:
            result = subprocess.run(
                [str(script), str(file_path)],
                capture_output=True,
                text=True,
                timeout=10
            )

            # Step 5: Check result
            self.log_debug(f"Step 5: Script execution completed")
            self.log_debug(f"  Exit code: {result.returncode}")

            if result.stdout:
                self.log_debug(f"  Stdout: {result.stdout.strip()}")
            if result.stderr:
                self.log_debug(f"  Stderr: {result.stderr.strip()}", "WARNING")

            if result.returncode == 0:
                success_msg = f"✓ Target sent to grep_flight [{version}]: {file_path.name}{context_str}"
                self.log_debug(success_msg)
                self.log_debug("="*60)
                return True, success_msg
            else:
                error_msg = f"Script failed with exit code {result.returncode}"
                if result.stderr:
                    error_msg += f": {result.stderr.strip()}"
                self.log_debug(error_msg, "ERROR")
                self.log_debug("="*60)
                return False, error_msg

        except subprocess.TimeoutExpired:
            error_msg = "Script execution timed out (10s)"
            self.log_debug(error_msg, "ERROR")
            self.log_debug("="*60)
            return False, error_msg

        except Exception as e:
            error_msg = f"Exception during script execution: {str(e)}"
            self.log_debug(error_msg, "ERROR")
            self.log_debug(f"  Exception type: {type(e).__name__}")
            self.log_debug("="*60)
            return False, error_msg

# ============================================================================
# Base Scope Analyzer
# ============================================================================
class ScopeAnalyzer:
    """Basic file scope analysis"""

    def __init__(self):
        self.file_counter = 0
        self.log_file = "scope_analysis.log"

    def analyze_file(self, source_path, copy=True):
        """Copy and analyze a Python file"""
        try:
            source_path = Path(source_path).resolve()

            if not source_path.exists():
                return False, f"File not found: {source_path}"

            if not source_path.suffix == '.py':
                return False, "Only .py files are supported"

            # Generate copy filename
            self.file_counter += 1
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            copy_name = f"scoped_{timestamp}_{self.file_counter:03d}.py"
            dest_path = source_path.parent / copy_name

            # Copy file if requested
            if copy:
                shutil.copy2(source_path, dest_path)
                dest_info = f"Copied to: {dest_path.name}"
            else:
                dest_path = source_path
                dest_info = "Original file (no copy made)"

            # Analyze file
            stats = self._get_file_stats(source_path)
            analysis = self._analyze_content(source_path)

            # Write to log
            log_entry = self._write_log(source_path, dest_path, stats, analysis)

            return True, {
                'source': source_path,
                'destination': dest_path if copy else None,
                'stats': stats,
                'analysis': analysis,
                'log_entry': log_entry,
                'copy_made': copy
            }

        except Exception as e:
            return False, f"Error: {str(e)}"

    def _get_file_stats(self, filepath):
        """Get basic file statistics"""
        stats = os.stat(filepath)
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
            lines = content.split('\n')

        return {
            'size_bytes': stats.st_size,
            'size_kb': stats.st_size / 1024,
            'total_lines': len(lines),
            'non_empty_lines': len([l for l in lines if l.strip()]),
            'name': filepath.name,
            'path': str(filepath.parent),
            'modified': datetime.fromtimestamp(stats.st_mtime)
        }

    def _analyze_content(self, filepath):
        """Analyze file content for imports, functions, etc."""
        with open(filepath, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        analysis = {
            'imports': [],
            'functions': [],
            'classes': [],
            'calls': [],
            'ui_elements': [],
            'line_details': {}
        }

        for idx, line in enumerate(lines, 1):
            stripped = line.strip()
            analysis['line_details'][idx] = {
                'content': line.rstrip('\n'),
                'type': 'normal'
            }

            # Detect imports
            if stripped.startswith(('import ', 'from ')):
                analysis['imports'].append((idx, stripped))
                analysis['line_details'][idx]['type'] = 'import'

            # Detect function definitions
            elif stripped.startswith('def '):
                func_name = stripped[4:].split('(')[0].strip()
                analysis['functions'].append((idx, func_name))
                analysis['line_details'][idx]['type'] = 'function_def'

            # Detect class definitions
            elif stripped.startswith('class '):
                class_name = stripped[6:].split('(')[0].split(':')[0].strip()
                analysis['classes'].append((idx, class_name))
                analysis['line_details'][idx]['type'] = 'class_def'

            # Detect UI elements (tkinter)
            elif any(pattern in line for pattern in ['.pack(', '.grid(', '.place(', '=tk.', '=ttk.']):
                analysis['ui_elements'].append((idx, stripped))
                analysis['line_details'][idx]['type'] = 'ui_element'

            # Detect function calls
            elif re.search(r'\b[\w_]+\([^)]*\)', stripped) and not stripped.startswith('#'):
                analysis['calls'].append((idx, stripped))

        return analysis

    def _write_log(self, source, dest, stats, analysis):
        """Write analysis to log file"""
        log_entry = f"""
{'='*80}
Analysis Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
Source File: {source.name}
Source Path: {source.parent}
Destination: {dest.name if hasattr(dest, 'name') else 'N/A'}
{'='*80}
File Size: {stats['size_kb']:.2f} KB ({stats['size_bytes']} bytes)
Total Lines: {stats['total_lines']}
Non-empty Lines: {stats['non_empty_lines']}
Last Modified: {stats['modified']}
{'='*80}
IMPORTS ({len(analysis['imports'])}):
{chr(10).join(f'  Line {ln}: {imp}' for ln, imp in analysis['imports'])}
{'='*80}
FUNCTIONS ({len(analysis['functions'])}):
{chr(10).join(f'  Line {ln}: def {func}' for ln, func in analysis['functions'])}
{'='*80}
CLASSES ({len(analysis['classes'])}):
{chr(10).join(f'  Line {ln}: class {cls}' for ln, cls in analysis['classes'])}
{'='*80}
UI ELEMENTS ({len(analysis['ui_elements'])}):
{chr(10).join(f'  Line {ln}: {elem}' for ln, elem in analysis['ui_elements'][:10])}
{'='*80}
"""

        with open(self.log_file, 'a', encoding='utf-8') as f:
            f.write(log_entry)

        return log_entry

# ============================================================================
# Core Analysis Toolkit Integration
# ============================================================================
class AnalysisToolkit:
    """Manages all analysis tools with progressive execution"""
    
    TOOL_CONFIG = {
        'pylint': {'args': ['--output-format=json', '--reports=n']},
        'pyflakes': {'args': []},
        'autoflake': {'args': ['--remove-all-unused-imports', '--in-place']},
        'ruff': {'args': ['check', '--fix']},
        'black': {'args': []},
        'reindent': {'args': ['-n']},
        'mypy': {'args': []},
        'bandit': {'args': ['-f', 'json']},
    }
    
    def __init__(self):
        self.tool_status = {}
        self.check_tools()
    
    def check_tools(self):
        """Check which tools are available"""
        for tool in self.TOOL_CONFIG.keys():
            try:
                subprocess.run([tool, '--version'], 
                             capture_output=True, check=True)
                self.tool_status[tool] = True
            except:
                self.tool_status[tool] = False
    
    def run_tool(self, tool: str, file_path: str, fix: bool = False) -> Dict:
        """Run a specific tool on a file"""
        if not self.tool_status.get(tool, False):
            return {'available': False, 'error': f'{tool} not installed'}
        
        try:
            args = [tool] + self.TOOL_CONFIG[tool]['args']
            
            if tool == 'autoflake' and fix:
                args.append('--in-place')
            elif tool == 'ruff' and fix:
                args.append('--fix')
            
            args.append(file_path)
            
            result = subprocess.run(args, capture_output=True, text=True, timeout=30)
            
            output = {
                'tool': tool,
                'exit_code': result.returncode,
                'stdout': result.stdout,
                'stderr': result.stderr,
                'timestamp': datetime.now().isoformat()
            }
            
            # Parse tool-specific output
            if tool == 'pylint' and result.stdout:
                try:
                    output['parsed'] = json.loads(result.stdout)
                except:
                    output['parsed'] = []
            
            return output
            
        except subprocess.TimeoutExpired:
            return {'error': f'{tool} timed out after 30s'}
        except Exception as e:
            return {'error': f'{tool} failed: {str(e)}'}

# ============================================================================
# Turn-Based Sequence System
# ============================================================================
@dataclass
class WorkflowStep:
    """Represents a step in the analysis workflow"""
    name: str
    phase: str  # discovery, analysis, fix, review, verify
    tool: Optional[str] = None
    description: str = ""
    auto_execute: bool = True
    requires_confirmation: bool = False
    timeout: int = 30
    dependencies: List[str] = field(default_factory=list)
    results: Dict = field(default_factory=dict)
    status: str = "pending"  # pending, running, completed, failed, skipped
    
    def execute(self, context: Dict) -> Dict:
        """Execute this step"""
        self.status = "running"
        self.results = {
            'start_time': datetime.now().isoformat(),
            'step': self.name,
            'phase': self.phase
        }
        
        try:
            # Execute based on step type
            if self.tool and context.get('file_path'):
                toolkit = AnalysisToolkit()
                self.results['tool_output'] = toolkit.run_tool(
                    self.tool, 
                    context['file_path'],
                    fix=(self.phase == 'fix')
                )
            
            self.status = "completed"
            self.results['end_time'] = datetime.now().isoformat()
            self.results['duration'] = (
                datetime.fromisoformat(self.results['end_time']) - 
                datetime.fromisoformat(self.results['start_time'])
            ).total_seconds()
            
        except Exception as e:
            self.status = "failed"
            self.results['error'] = str(e)
            self.results['traceback'] = traceback.format_exc()
        
        return self.results

class TurnBasedWorkflow:
    """Manages turn-based execution of analysis workflow"""
    
    WORKFLOWS = {
        'full_analysis': [
            WorkflowStep("discover_files", "discovery", 
                        description="Find all Python files in project"),
            WorkflowStep("initial_scan", "analysis", "pylint",
                        description="Initial code quality scan"),
            WorkflowStep("syntax_check", "analysis", "pyflakes",
                        description="Check for syntax errors"),
            WorkflowStep("security_scan", "analysis", "bandit",
                        description="Security vulnerability check"),
            WorkflowStep("type_check", "analysis", "mypy",
                        description="Type checking"),
            WorkflowStep("tkinter_analysis", "analysis",
                        description="Tkinter-specific pattern detection"),
            WorkflowStep("import_cleanup", "fix", "autoflake",
                        description="Clean up unused imports"),
            WorkflowStep("code_style_fix", "fix", "ruff",
                        description="Fix code style issues"),
            WorkflowStep("format_code", "fix", "black",
                        description="Format code with black"),
            WorkflowStep("indent_fix", "fix", "reindent",
                        description="Fix indentation"),
            WorkflowStep("gui_layout_analysis", "analysis",
                        description="Analyze GUI layout patterns"),
            WorkflowStep("data_piping_analysis", "analysis",
                        description="Analyze data flow"),
            WorkflowStep("generate_report", "review",
                        description="Generate comprehensive report"),
            WorkflowStep("diff_review", "review",
                        description="Show before/after diffs"),
            WorkflowStep("final_verification", "verify",
                        description="Verify all fixes applied correctly"),
        ],
        
        'quick_fix': [
            WorkflowStep("import_cleanup", "fix", "autoflake"),
            WorkflowStep("code_style_fix", "fix", "ruff"),
            WorkflowStep("format_code", "fix", "black"),
        ],
        
        'tkinter_only': [
            WorkflowStep("tkinter_analysis", "analysis"),
            WorkflowStep("gui_layout_analysis", "analysis"),
            WorkflowStep("tkinter_fixes", "fix"),
        ]
    }
    
    def __init__(self, workflow_name: str = 'full_analysis'):
        self.workflow_name = workflow_name
        self.steps = self.WORKFLOWS.get(workflow_name, [])
        self.current_step = 0
        self.context = {}
        self.execution_log = []
        self.paused = False
        self.auto_mode = False
        
    def set_context(self, **kwargs):
        """Set context for workflow execution"""
        self.context.update(kwargs)
    
    def execute_next(self, force: bool = False) -> Optional[Dict]:
        """Execute the next step in sequence"""
        if self.paused and not force:
            return None
        
        if self.current_step >= len(self.steps):
            return {'status': 'complete', 'message': 'Workflow finished'}
        
        step = self.steps[self.current_step]
        
        # Check dependencies
        for dep in step.dependencies:
            dep_step = next((s for s in self.steps[:self.current_step] 
                           if s.name == dep), None)
            if not dep_step or dep_step.status != "completed":
                step.status = "skipped"
                step.results = {'reason': f'Dependency {dep} not met'}
                self.current_step += 1
                return self.execute_next(force)
        
        # Execute step
        result = step.execute(self.context)
        self.execution_log.append(result)
        
        # Auto-proceed in auto mode
        self.current_step += 1
        if self.auto_mode and not step.requires_confirmation:
            return self.execute_next(force)
        
        return result
    
    def execute_all(self):
        """Execute all steps automatically"""
        self.auto_mode = True
        results = []
        while self.current_step < len(self.steps):
            result = self.execute_next(force=True)
            if result:
                results.append(result)
        return results
    
    def pause(self):
        """Pause workflow execution"""
        self.paused = True
    
    def resume(self):
        """Resume workflow execution"""
        self.paused = False
    
    def reset(self):
        """Reset workflow to beginning"""
        self.current_step = 0
        for step in self.steps:
            step.status = "pending"
            step.results = {}
        self.execution_log = []
    
    def get_summary(self) -> Dict:
        """Get workflow execution summary"""
        completed = sum(1 for s in self.steps if s.status == "completed")
        failed = sum(1 for s in self.steps if s.status == "failed")
        skipped = sum(1 for s in self.steps if s.status == "skipped")
        
        return {
            'total_steps': len(self.steps),
            'completed': completed,
            'failed': failed,
            'skipped': skipped,
            'progress': f"{completed}/{len(self.steps)}",
            'current_step': self.current_step,
            'workflow_name': self.workflow_name
        }

# ============================================================================
# Enhanced Scope Analyzer with Progressive Analysis
# ============================================================================
class EnhancedScopeAnalyzer(ScopeAnalyzer):
    """Enhanced analyzer with multi-phase progressive analysis"""
    
    def __init__(self):
        super().__init__()
        self.toolkit = AnalysisToolkit()
        self.workflow = None
        self.analysis_depth = 0
        self.tag_registry = {}  # For module tagging
        self.import_graph = defaultdict(set)
        self.call_chains = defaultdict(list)
        
    def progressive_analyze(self, file_path: str, depth: int = 3) -> Dict:
        """
        Progressive analysis with increasing depth
        Returns analysis at each depth level
        """
        results = {'depth_levels': []}
        
        for current_depth in range(1, depth + 1):
            self.analysis_depth = current_depth
            depth_result = self._analyze_at_depth(file_path, current_depth)
            results['depth_levels'].append(depth_result)
            
            # Stop if we've reached maximum useful depth
            if depth_result.get('analysis_complete', False):
                break
        
        results['final'] = results['depth_levels'][-1]
        return results
    
    def _analyze_at_depth(self, file_path: str, depth: int) -> Dict:
        """Analyze file at specific depth level"""
        result = {
            'depth': depth,
            'file': file_path,
            'timestamp': datetime.now().isoformat(),
            'tags_found': [],
            'imports_resolved': [],
            'call_chains': [],
            'issues_by_severity': defaultdict(list),
            'suggested_fixes': []
        }
        
        # Depth 1: Basic file analysis
        success, basic_result = self.analyze_file(file_path, copy=False)
        if not success:
            result['error'] = basic_result
            return result
        
        result.update(basic_result)
        
        # Depth 2: Import resolution and tagging
        if depth >= 2:
            self._resolve_imports(file_path, result)
            self._tag_modules(file_path, result)
        
        # Depth 3: Call chain analysis and pattern detection
        if depth >= 3:
            self._analyze_call_chains(file_path, result)
            self._detect_patterns(file_path, result)
        
        # Depth 4: Progressive fixing suggestions
        if depth >= 4:
            self._generate_fix_suggestions(result)
        
        return result
    
    def _resolve_imports(self, file_path: str, result: Dict):
        """Resolve imports to actual file paths"""
        with open(file_path, 'r') as f:
            content = f.read()
        
        tree = ast.parse(content)
        
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    module_name = alias.name
                    resolved = self._find_module_path(module_name, file_path)
                    if resolved:
                        result['imports_resolved'].append({
                            'module': module_name,
                            'path': str(resolved),
                            'line': node.lineno
                        })
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    resolved = self._find_module_path(node.module, file_path)
                    if resolved:
                        result['imports_resolved'].append({
                            'module': node.module,
                            'path': str(resolved),
                            'line': node.lineno,
                            'imports': [alias.name for alias in node.names]
                        })
    
    def _find_module_path(self, module_name: str, reference_file: str) -> Optional[Path]:
        """Find actual path of imported module"""
        # Check if module is in sys.path
        for path in sys.path:
            if not path:
                continue
            
            # Check for .py file
            py_file = Path(path) / f"{module_name.replace('.', '/')}.py"
            if py_file.exists():
                return py_file
            
            # Check for package
            init_file = Path(path) / f"{module_name.replace('.', '/')}/__init__.py"
            if init_file.exists():
                return init_file
        
        # Check relative to reference file
        ref_dir = Path(reference_file).parent
        possibilities = [
            ref_dir / f"{module_name}.py",
            ref_dir / module_name / "__init__.py",
            ref_dir / f"{module_name.replace('.', '/')}.py",
        ]
        
        for poss in possibilities:
            if poss.exists():
                return poss
        
        return None
    
    def _tag_modules(self, file_path: str, result: Dict):
        """Tag modules based on content and relationships"""
        tags = set()
        
        with open(file_path, 'r') as f:
            content = f.read().lower()
        
        # Detect module type
        if 'tkinter' in content or 'tk.' in content:
            tags.add('tkinter_gui')
        if 'class' in content and 'def ' in content:
            tags.add('has_classes_functions')
        if 'import ' in content and 'from ' in content:
            tags.add('has_imports')
        if 'mainloop' in content or 'tk.tk()' in content:
            tags.add('has_mainloop')
        if 'thread' in content or 'threading' in content:
            tags.add('uses_threads')
        if 'queue' in content or 'queue.' in content:
            tags.add('uses_queues')
        if 'subprocess' in content:
            tags.add('uses_subprocess')
        
        result['tags_found'] = list(tags)
        
        # Register tags for this file
        self.tag_registry[file_path] = tags
    
    def _analyze_call_chains(self, file_path: str, result: Dict):
        """Analyze function call chains"""
        with open(file_path, 'r') as f:
            content = f.read()
        
        tree = ast.parse(content)
        call_chains = []
        
        class CallVisitor(ast.NodeVisitor):
            def __init__(self):
                self.current_chain = []
                self.chains = []
            
            def visit_Call(self, node):
                if isinstance(node.func, ast.Name):
                    func_name = node.func.id
                    self.current_chain.append(func_name)
                elif isinstance(node.func, ast.Attribute):
                    func_name = node.func.attr
                    self.current_chain.append(func_name)
                
                self.generic_visit(node)
                
                if self.current_chain:
                    self.chains.append(list(self.current_chain))
                    self.current_chain.pop()
        
        visitor = CallVisitor()
        visitor.visit(tree)
        
        result['call_chains'] = visitor.chains
    
    def _detect_patterns(self, file_path: str, result: Dict):
        """Detect code patterns and issues"""
        with open(file_path, 'r') as f:
            lines = f.readlines()
        
        issues = []
        
        for i, line in enumerate(lines, 1):
            # Tkinter-specific patterns
            if '.update()' in line and 'update_idletasks' not in line:
                issues.append({
                    'line': i,
                    'issue': 'Direct update() call',
                    'severity': 'warning',
                    'suggestion': 'Consider using update_idletasks() instead',
                    'category': 'performance'
                })
            
            if '.pack()' in line and 'side' not in line and 'expand' not in line:
                issues.append({
                    'line': i,
                    'issue': 'Pack without options',
                    'severity': 'info',
                    'suggestion': 'Specify side/expand/fill options',
                    'category': 'layout'
                })
            
            if 'import *' in line:
                issues.append({
                    'line': i,
                    'issue': 'Wildcard import',
                    'severity': 'warning',
                    'suggestion': 'Import specific names instead',
                    'category': 'style'
                })
            
            # Performance patterns
            if 'time.sleep(' in line and 'thread' not in line:
                issues.append({
                    'line': i,
                    'issue': 'Blocking sleep in main thread',
                    'severity': 'warning',
                    'suggestion': 'Use after() for timing in Tkinter',
                    'category': 'performance'
                })
        
        result['detected_patterns'] = issues
    
    def _generate_fix_suggestions(self, result: Dict):
        """Generate prioritized fix suggestions"""
        suggestions = []
        
        # Categorize issues
        categories = defaultdict(list)
        for pattern in result.get('detected_patterns', []):
            categories[pattern['category']].append(pattern)
        
        # Generate suggestions by category
        for category, issues in categories.items():
            if issues:
                suggestions.append({
                    'category': category,
                    'priority': self._calculate_priority(category, issues),
                    'issues_count': len(issues),
                    'issues': issues[:5],  # Show first 5
                    'auto_fix_available': category in ['style', 'imports'],
                    'suggested_tools': self._get_tools_for_category(category)
                })
        
        result['suggested_fixes'] = suggestions
    
    def _calculate_priority(self, category: str, issues: List) -> str:
        """Calculate priority for fix category"""
        priorities = {
            'security': 'critical',
            'performance': 'high',
            'layout': 'medium',
            'style': 'low',
            'imports': 'low'
        }
        return priorities.get(category, 'medium')
    
    def _get_tools_for_category(self, category: str) -> List[str]:
        """Get appropriate tools for fixing category"""
        tool_map = {
            'style': ['black', 'ruff', 'autoflake'],
            'imports': ['autoflake', 'isort'],
            'security': ['bandit'],
            'performance': [],  # Manual fixes
            'layout': []  # Manual fixes
        }
        return tool_map.get(category, [])

# ============================================================================
# Live GUI Review Mode
# ============================================================================
class LiveGUIReview:
    """Interactive GUI for reviewing and accepting changes"""
    
    def __init__(self, root, original_file: str, modified_file: str = None):
        self.root = root
        self.original_file = original_file
        self.modified_file = modified_file
        self.current_file = original_file
        self.changes = []
        self.accepted_changes = []
        self.rejected_changes = []
        self.review_window = None
        
        # Load original content
        with open(original_file, 'r') as f:
            self.original_content = f.read().splitlines()
        
        # Generate modified content if not provided
        if not modified_file:
            self._generate_modified_content()
        else:
            with open(modified_file, 'r') as f:
                self.modified_content = f.read().splitlines()
        
        self._calculate_diff()
    
    def _generate_modified_content(self):
        """Generate modified content by applying suggested fixes"""
        analyzer = EnhancedScopeAnalyzer()
        result = analyzer.progressive_analyze(self.original_file, depth=4)
        
        # Apply auto-fixes
        temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False)
        temp_file.close()
        
        shutil.copy2(self.original_file, temp_file.name)
        
        # Apply tools
        toolkit = AnalysisToolkit()
        for tool in ['autoflake', 'ruff', 'black']:
            if toolkit.tool_status.get(tool, False):
                toolkit.run_tool(tool, temp_file.name, fix=True)
        
        with open(temp_file.name, 'r') as f:
            self.modified_content = f.read().splitlines()
        
        # Clean up
        os.unlink(temp_file.name)
    
    def _calculate_diff(self):
        """Calculate diff between original and modified"""
        diff = difflib.unified_diff(
            self.original_content,
            self.modified_content,
            fromfile='Original',
            tofile='Modified',
            lineterm=''
        )
        self.diff_lines = list(diff)
        self._parse_diff_to_changes()
    
    def _parse_diff_to_changes(self):
        """Parse diff lines into individual changes"""
        changes = []
        current_change = None
        
        for line in self.diff_lines:
            if line.startswith('@@'):
                # New change block
                if current_change:
                    changes.append(current_change)
                match = re.match(r'@@ -(\d+),?(\d*) \+(\d+),?(\d*) @@', line)
                if match:
                    current_change = {
                        'orig_start': int(match.group(1)),
                        'orig_len': int(match.group(2) or 1),
                        'mod_start': int(match.group(3)),
                        'mod_len': int(match.group(4) or 1),
                        'lines': []
                    }
            elif current_change and (line.startswith('-') or line.startswith('+') or line.startswith(' ')):
                current_change['lines'].append(line)
        
        if current_change:
            changes.append(current_change)
        
        self.changes = changes
    
    def show_review(self):
        """Show the review GUI"""
        if self.review_window and self.review_window.winfo_exists():
            self.review_window.destroy()
        
        self.review_window = tk.Toplevel(self.root)
        self.review_window.title(f"Live Review: {Path(self.original_file).name}")
        self.review_window.geometry("1200x800")
        
        # Create notebook for different views
        notebook = ttk.Notebook(self.review_window)
        notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Diff view tab
        diff_frame = ttk.Frame(notebook)
        notebook.add(diff_frame, text="Diff View")
        self._create_diff_view(diff_frame)
        
        # Side-by-side tab
        side_frame = ttk.Frame(notebook)
        notebook.add(side_frame, text="Side-by-Side")
        self._create_side_by_side_view(side_frame)
        
        # Change list tab
        changes_frame = ttk.Frame(notebook)
        notebook.add(changes_frame, text="Change List")
        self._create_changes_list_view(changes_frame)
        
        # Statistics tab
        stats_frame = ttk.Frame(notebook)
        notebook.add(stats_frame, text="Statistics")
        self._create_statistics_view(stats_frame)
        
        # Control panel
        control_frame = ttk.Frame(self.review_window)
        control_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Button(control_frame, text="Accept All", 
                  command=self.accept_all).pack(side=tk.LEFT, padx=2)
        ttk.Button(control_frame, text="Reject All", 
                  command=self.reject_all).pack(side=tk.LEFT, padx=2)
        ttk.Button(control_frame, text="Apply Selected", 
                  command=self.apply_selected).pack(side=tk.LEFT, padx=2)
        ttk.Button(control_frame, text="Export Report", 
                  command=self.export_report).pack(side=tk.LEFT, padx=2)
        
        # Status
        self.status_var = tk.StringVar(value="Ready to review changes")
        ttk.Label(control_frame, textvariable=self.status_var).pack(side=tk.RIGHT, padx=10)
    
    def _create_diff_view(self, parent):
        """Create diff view with color coding"""
        text = scrolledtext.ScrolledText(parent, font=('Monospace', 10))
        text.pack(fill=tk.BOTH, expand=True)
        
        # Configure tags
        text.tag_config('removed', background='#ffcccc', foreground='#990000')
        text.tag_config('added', background='#ccffcc', foreground='#009900')
        text.tag_config('context', background='#f0f0f0', foreground='#666666')
        text.tag_config('header', background='#e0e0e0', foreground='#000000', font=('Monospace', 10, 'bold'))
        
        # Insert diff lines
        for line in self.diff_lines:
            if line.startswith('---') or line.startswith('+++'):
                text.insert(tk.END, line + '\n', 'header')
            elif line.startswith('-'):
                text.insert(tk.END, line + '\n', 'removed')
            elif line.startswith('+'):
                text.insert(tk.END, line + '\n', 'added')
            elif line.startswith('@'):
                text.insert(tk.END, line + '\n', 'header')
            else:
                text.insert(tk.END, line + '\n', 'context')
        
        text.config(state=tk.DISABLED)
    
    def _create_side_by_side_view(self, parent):
        """Create side-by-side comparison view"""
        paned = ttk.PanedWindow(parent, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True)
        
        # Original panel
        orig_frame = ttk.Frame(paned)
        paned.add(orig_frame, weight=1)
        
        ttk.Label(orig_frame, text="ORIGINAL", font=('Monospace', 10, 'bold')).pack()
        orig_text = scrolledtext.ScrolledText(orig_frame, font=('Monospace', 10))
        orig_text.pack(fill=tk.BOTH, expand=True)
        orig_text.insert(1.0, '\n'.join(self.original_content))
        orig_text.config(state=tk.DISABLED)
        
        # Modified panel
        mod_frame = ttk.Frame(paned)
        paned.add(mod_frame, weight=1)
        
        ttk.Label(mod_frame, text="MODIFIED", font=('Monospace', 10, 'bold')).pack()
        mod_text = scrolledtext.ScrolledText(mod_frame, font=('Monospace', 10))
        mod_text.pack(fill=tk.BOTH, expand=True)
        mod_text.insert(1.0, '\n'.join(self.modified_content))
        mod_text.config(state=tk.DISABLED)
    
    def _create_changes_list_view(self, parent):
        """Create list of changes with accept/reject toggles"""
        # Treeview for changes
        tree_frame = ttk.Frame(parent)
        tree_frame.pack(fill=tk.BOTH, expand=True)
        
        columns = ('#', 'Type', 'Location', 'Content', 'Status')
        tree = ttk.Treeview(tree_frame, columns=columns, show='headings', height=15)
        
        for col in columns:
            tree.heading(col, text=col)
            tree.column(col, width=100)
        
        # Add scrollbar
        scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Populate tree
        for i, change in enumerate(self.changes, 1):
            change_type = "Modify" if change['lines'] else "Context"
            location = f"Line {change['orig_start']}"
            preview = change['lines'][0][:50] + "..." if change['lines'] else ""
            
            tree.insert('', 'end', values=(
                i, change_type, location, preview, 'Pending'
            ), tags=(f'change_{i}',))
        
        # Context menu for change actions
        def on_tree_select(event):
            item = tree.selection()[0]
            values = tree.item(item, 'values')
            change_idx = int(values[0]) - 1
            
            # Create context menu
            menu = tk.Menu(tree_frame, tearoff=0)
            menu.add_command(label="Accept Change", 
                           command=lambda: self._accept_change(tree, item, change_idx))
            menu.add_command(label="Reject Change", 
                           command=lambda: self._reject_change(tree, item, change_idx))
            menu.add_command(label="View Details", 
                           command=lambda: self._show_change_details(change_idx))
            
            menu.tk_popup(event.x_root, event.y_root)
        
        tree.bind('<Button-3>', on_tree_select)
    
    def _create_statistics_view(self, parent):
        """Create statistics view"""
        text = scrolledtext.ScrolledText(parent, font=('Monospace', 10))
        text.pack(fill=tk.BOTH, expand=True)
        
        stats = self._calculate_statistics()
        
        report = "CHANGE STATISTICS\n"
        report += "=" * 50 + "\n\n"
        
        for category, data in stats.items():
            if isinstance(data, dict):
                report += f"{category}:\n"
                for k, v in data.items():
                    report += f"  {k}: {v}\n"
                report += "\n"
            else:
                report += f"{category}: {data}\n"
        
        text.insert(1.0, report)
        text.config(state=tk.DISABLED)
    
    def _calculate_statistics(self) -> Dict:
        """Calculate change statistics"""
        added = sum(1 for line in self.diff_lines if line.startswith('+') and not line.startswith('+++'))
        removed = sum(1 for line in self.diff_lines if line.startswith('-') and not line.startswith('---'))
        modified = len(self.changes)
        
        return {
            'Total Lines Original': len(self.original_content),
            'Total Lines Modified': len(self.modified_content),
            'Lines Added': added,
            'Lines Removed': removed,
            'Change Blocks': modified,
            'Lines Changed': added + removed,
            'Change Percentage': f"{(added + removed) / max(len(self.original_content), 1) * 100:.1f}%"
        }
    
    def _accept_change(self, tree, item, change_idx):
        """Accept a specific change"""
        tree.set(item, 'Status', 'Accepted')
        self.accepted_changes.append(change_idx)
        if change_idx in self.rejected_changes:
            self.rejected_changes.remove(change_idx)
    
    def _reject_change(self, tree, item, change_idx):
        """Reject a specific change"""
        tree.set(item, 'Status', 'Rejected')
        self.rejected_changes.append(change_idx)
        if change_idx in self.accepted_changes:
            self.accepted_changes.remove(change_idx)
    
    def _show_change_details(self, change_idx):
        """Show details of a specific change"""
        if 0 <= change_idx < len(self.changes):
            change = self.changes[change_idx]
            
            detail_win = tk.Toplevel(self.review_window)
            detail_win.title(f"Change Details #{change_idx + 1}")
            detail_win.geometry("600x400")
            
            text = scrolledtext.ScrolledText(detail_win, font=('Monospace', 10))
            text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
            
            detail = f"Change #{change_idx + 1}\n"
            detail += f"Original: Lines {change['orig_start']}-{change['orig_start'] + change['orig_len']}\n"
            detail += f"Modified: Lines {change['mod_start']}-{change['mod_start'] + change['mod_len']}\n"
            detail += "\nChanges:\n"
            
            for line in change['lines']:
                if line.startswith('-'):
                    detail += f"  - {line[1:]}\n"
                elif line.startswith('+'):
                    detail += f"  + {line[1:]}\n"
                else:
                    detail += f"    {line}\n"
            
            text.insert(1.0, detail)
            text.config(state=tk.DISABLED)
    
    def accept_all(self):
        """Accept all changes"""
        self.accepted_changes = list(range(len(self.changes)))
        self.rejected_changes = []
        self.status_var.set(f"Accepted all {len(self.changes)} changes")
    
    def reject_all(self):
        """Reject all changes"""
        self.rejected_changes = list(range(len(self.changes)))
        self.accepted_changes = []
        self.status_var.set(f"Rejected all {len(self.changes)} changes")
    
    def apply_selected(self):
        """Apply selected changes to a new file"""
        if not self.accepted_changes:
            messagebox.showwarning("No Changes", "No changes selected for application")
            return
        
        # Create new file with accepted changes
        file_path = filedialog.asksaveasfilename(
            title="Save Modified File",
            defaultextension=".py",
            initialfile=f"modified_{Path(self.original_file).name}"
        )
        
        if file_path:
            # Apply changes
            self._apply_changes_to_file(file_path)
            messagebox.showinfo("Success", f"Changes applied to {file_path}")
            self.status_var.set(f"Applied to {Path(file_path).name}")
    
    def _apply_changes_to_file(self, output_path: str):
        """Apply accepted changes to create new file"""
        # For simplicity, we'll use the modified content
        # In a real implementation, we'd apply only accepted changes
        with open(output_path, 'w') as f:
            f.write('\n'.join(self.modified_content))
    
    def export_report(self):
        """Export review report"""
        file_path = filedialog.asksaveasfilename(
            title="Export Review Report",
            defaultextension=".json",
            filetypes=[("JSON", "*.json"), ("Text", "*.txt"), ("All", "*.*")]
        )
        
        if file_path:
            report = {
                'original_file': self.original_file,
                'review_date': datetime.now().isoformat(),
                'statistics': self._calculate_statistics(),
                'changes_total': len(self.changes),
                'changes_accepted': len(self.accepted_changes),
                'changes_rejected': len(self.rejected_changes),
                'accepted_changes': self.accepted_changes,
                'rejected_changes': self.rejected_changes,
                'diff': self.diff_lines
            }
            
            if file_path.endswith('.json'):
                with open(file_path, 'w') as f:
                    json.dump(report, f, indent=2)
            else:
                with open(file_path, 'w') as f:
                    f.write("CODE REVIEW REPORT\n")
                    f.write("=" * 50 + "\n\n")
                    for key, value in report.items():
                        if key != 'diff':
                            f.write(f"{key}: {value}\n")
                    
                    f.write("\n\nDIFF:\n")
                    f.write("=" * 50 + "\n")
                    f.write('\n'.join(report['diff']))
            
            messagebox.showinfo("Export Complete", f"Report saved to {file_path}")

# ============================================================================
# CLI Output Formatter for Turn-Based Sequences
# ============================================================================
class CLIFormatter:
    """Format CLI output for turn-based sequences"""
    
    COLORS = {
        'header': '\033[95m',
        'success': '\033[92m',
        'warning': '\033[93m',
        'error': '\033[91m',
        'info': '\033[94m',
        'step': '\033[96m',
        'phase': '\033[95m',
        'reset': '\033[0m'
    }
    
    @staticmethod
    def print_step(step_num: int, total: int, step: WorkflowStep, result: Dict = None):
        """Print step information"""
        phase_color = CLIFormatter.COLORS.get('phase', '')
        step_color = CLIFormatter.COLORS.get('step', '')
        reset = CLIFormatter.COLORS.get('reset', '')
        
        print(f"\n{phase_color}[Phase: {step.phase.upper()}]{reset}")
        print(f"{step_color}Step {step_num}/{total}: {step.name}{reset}")
        print(f"  Description: {step.description}")
        
        if step.tool:
            print(f"  Tool: {step.tool}")
        
        if result:
            status = result.get('status', 'unknown')
            if status == 'completed':
                color = CLIFormatter.COLORS['success']
                symbol = '✓'
            elif status == 'failed':
                color = CLIFormatter.COLORS['error']
                symbol = '✗'
            else:
                color = CLIFormatter.COLORS['warning']
                symbol = '○'
            
            print(f"  Status: {color}{symbol} {status}{reset}")
            
            if 'duration' in result:
                print(f"  Duration: {result['duration']:.2f}s")
    
    @staticmethod
    def print_feature_info(feature: Dict):
        """Print feature information"""
        print(f"\n{CLIFormatter.COLORS['header']}[Feature Analysis]{CLIFormatter.COLORS['reset']}")
        print(f"Name: {feature.get('name', 'Unknown')}")
        print(f"File: {feature.get('file', 'Unknown')}")
        
        if 'line' in feature:
            print(f"Line: {feature['line']}")
        
        if 'imports' in feature:
            print(f"Imports: {', '.join(feature['imports'])}")
        
        if 'class' in feature:
            print(f"Class: {feature['class']}")
        
        if 'function' in feature:
            print(f"Function: {feature['function']}")
        
        if 'issues' in feature and feature['issues']:
            print(f"Issues: {len(feature['issues'])} found")
            for issue in feature['issues'][:3]:  # Show first 3
                print(f"  - {issue}")
    
    @staticmethod
    def print_workflow_summary(summary: Dict):
        """Print workflow summary"""
        print(f"\n{CLIFormatter.COLORS['header']}WORKFLOW SUMMARY{CLIFormatter.COLORS['reset']}")
        print(f"Workflow: {summary.get('workflow_name', 'Unknown')}")
        print(f"Steps: {summary.get('completed', 0)}/{summary.get('total_steps', 0)} completed")
        print(f"Failed: {summary.get('failed', 0)}")
        print(f"Skipped: {summary.get('skipped', 0)}")
        print(f"Progress: {summary.get('progress', '0/0')}")

# ============================================================================
def enhanced_parse_arguments():
    """Parse enhanced CLI arguments"""
    parser = argparse.ArgumentParser(
        description='Enhanced Tkinter Inspector with Analysis Workflows',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Enhanced Workflow Examples:
    python3 inspector.py --analyze --file=app.py --depth=4
    python3 inspector.py --workflow=full_analysis --auto
    python3 inspector.py --workflow=quick_fix --file=app.py
    python3 inspector.py --gui-review --file=app.py
    python3 inspector.py --turnbased --interactive
    python3 inspector.py --organization --dir=./project
    python3 inspector.py --auto-fix --file=app.py --backup

Workflow Types:
    full_analysis: Complete analysis and fixing (15 steps)
    quick_fix: Import/style/format fixes (3 steps)
    tkinter_only: Tkinter-specific analysis (3 steps)
        '''
    )
    
    parser.add_argument('--analyze', action='store_true',
                       help='Run progressive analysis on file')
    parser.add_argument('--workflow', type=str, choices=['full_analysis', 'quick_fix', 'tkinter_only'],
                       help='Run specific workflow')
    parser.add_argument('--auto', action='store_true',
                       help='Run workflow in auto mode (no confirmation)')
    parser.add_argument('--turnbased', action='store_true',
                       help='Run turn-based workflow')
    parser.add_argument('--interactive', action='store_true',
                       help='Run in interactive mode')
    parser.add_argument('--gui-review', action='store_true',
                       help='Open live GUI review')
    parser.add_argument('--organization', action='store_true',
                       help='Generate organization schema')
    parser.add_argument('--auto-fix', action='store_true',
                       help='Auto-fix all detectable issues')
    
    parser.add_argument('--file', type=str, help='File to analyze/fix')
    parser.add_argument('--dir', type=str, help='Directory for schema analysis')
    parser.add_argument('--depth', type=int, default=3,
                       help='Analysis depth (1-4, default: 3)')
    parser.add_argument('--backup', action='store_true',
                       help='Create backup before auto-fix')
    
    # Original arguments
    parser.add_argument('--scope', action='store_true',
                       help='Enter scope analysis mode')
    parser.add_argument('--copy', type=str, metavar='FILE',
                       help='Copy and analyze specified file')
    parser.add_argument('--monitor', action='store_true',
                       help='Show runtime activity monitor')
    parser.add_argument('--lines', type=int, default=50,
                       help='Lines per page (default: 50)')
    
    return parser.parse_args()

def run_cli_workflow(args):
    """Run workflow from CLI"""
    
    if not args.file and (args.analyze or args.workflow or args.gui_review or args.auto_fix):
        print("Error: --file argument required for analysis workflows")
        return
    
    # Progressive analysis
    if args.analyze and args.file:
        print(f"Running progressive analysis on {args.file} (depth: {args.depth})")
        analyzer = EnhancedScopeAnalyzer()
        result = analyzer.progressive_analyze(args.file, args.depth)
        
        CLIFormatter.print_step(1, 1, WorkflowStep("progressive_analysis", "analysis"), 
                               {'status': 'completed'})
        
        print(f"\nAnalysis complete for {args.file}")
        print(f"Depth levels analyzed: {len(result['depth_levels'])}")
        
        final = result['final']
        if 'tags_found' in final:
            print(f"Tags: {', '.join(final['tags_found'])}")
        if 'suggested_fixes' in final:
            print(f"Suggested fixes: {len(final['suggested_fixes'])}")
    
    # Workflow execution
    elif args.workflow and args.file:
        print(f"Running {args.workflow} workflow on {args.file}")
        
        workflow = TurnBasedWorkflow(args.workflow)
        workflow.set_context(file_path=args.file)
        
        if args.auto:
            print("Running in auto mode...")
            results = workflow.execute_all()
            
            for i, result in enumerate(results, 1):
                step = workflow.steps[i-1]
                CLIFormatter.print_step(i, len(workflow.steps), step, result)
            
            summary = workflow.get_summary()
            CLIFormatter.print_workflow_summary(summary)
        
        else:
            print("Running step-by-step...")
            for i in range(len(workflow.steps)):
                result = workflow.execute_next(force=True)
                if result:
                    step = workflow.steps[i]
                    CLIFormatter.print_step(i+1, len(workflow.steps), step, result)
    
    # Auto-fix
    elif args.auto_fix and args.file:
        if args.backup:
            backup_path = args.file + '.backup'
            shutil.copy2(args.file, backup_path)
            print(f"Backup created: {backup_path}")
        
        print(f"Auto-fixing {args.file}...")
        
        toolkit = AnalysisToolkit()
        tools = ['autoflake', 'ruff', 'black']
        
        for tool in tools:
            if toolkit.tool_status.get(tool, False):
                print(f"  Running {tool}...")
                result = toolkit.run_tool(tool, args.file, fix=True)
                if 'error' in result:
                    print(f"    Error: {result['error']}")
                else:
                    print(f"    Completed (exit: {result.get('exit_code', 0)})")
        
        print(f"\nAuto-fix complete for {args.file}")
    
    # Organization schema
    elif args.organization:
        if not args.dir:
            print("Error: --dir argument required for organization schema")
            return
        
        print(f"Generating organization schema for {args.dir}")
        
        analyzer = EnhancedScopeAnalyzer()
        schema = analyzer._create_organization_schema(args.dir)
        
        print(f"\nSchema generated for {schema['project_root']}")
        print(f"Modules analyzed: {len(schema['modules'])}")
        
        if schema['recommendations']:
            print(f"\nRecommendations ({len(schema['recommendations'])}):")
            for rec in schema['recommendations']:
                print(f"  • {rec}")
        else:
            print("\nNo recommendations - project is well organized!")
    
    else:
        print("No workflow specified or invalid arguments")
        print("Use --help to see available options")

# ============================================================================
# Enhanced Main Application
# ============================================================================
def enhanced_main():
    args = enhanced_parse_arguments()

    # Handle enhanced CLI workflows
    if args.analyze or args.workflow or args.auto_fix or args.organization or args.gui_review:
        run_cli_workflow(args)
        return

    # scope_flow.py is CLI-focused - no default GUI mode
    # For widget inspection GUI, use the original scope.py
    print("\nscope_flow.py - Analysis & Workflow Tool")
    print("=" * 60)
    print("This is a CLI-focused analysis tool.")
    print("For GUI widget inspection, use: scope.py\n")
    print("Available workflows:")
    print("  --analyze --file=<file>          Progressive analysis")
    print("  --workflow=<type> --file=<file>  Run specific workflow")
    print("  --gui-review --file=<file>       Launch diff review GUI")
    print("  --organization --dir=<dir>       Analyze project structure")
    print("  --auto-fix --file=<file>         Auto-fix issues\n")
    print("Use --help for full documentation")
    print("=" * 60)

# ============================================================================
# Entry Point
# ============================================================================
if __name__ == "__main__":
    # Replace original main with enhanced version
    sys.exit(enhanced_main())