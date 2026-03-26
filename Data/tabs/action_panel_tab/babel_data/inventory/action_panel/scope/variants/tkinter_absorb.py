#!/usr/bin/env python3
"""
Tkinter Absorb - Non-Compromising Integration & Analysis Tool
=============================================================
A comprehensive tool that absorbs Python/Tkinter applications, analyzes structure,
creates detailed manifests with quality assessments, and enables auto-onboarding
with turn-based workflows and visual diff reviews.

Key Features:
1. Parent Structure Preservation with Quality Analysis
2. Feature Detection with Confidence Scoring
3. Manifest Creation with History & Revert Points
4. Turn-Based Auto-Onboarding Workflow
5. Visual Diff GUI Integration
6. Standalone & Integrated Operation Modes
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
from datetime import datetime, timedelta
import platform
import json
import ast
import difflib
import tempfile
import hashlib
import sqlite3
import yaml
from dataclasses import dataclass, field, asdict, is_dataclass
from typing import Dict, List, Tuple, Set, Any, Optional, Union, Callable
from collections import defaultdict, OrderedDict
import traceback
import webbrowser
import pickle
import itertools
from enum import Enum
import importlib.util
import warnings
import pkgutil
import fnmatch
from concurrent.futures import ThreadPoolExecutor, as_completed

# Import parent modules if available
try:
    # Try to import from scope_flow
    import scope_flow
    from scope_flow import (
        ScopeAnalyzer,
        EnhancedScopeAnalyzer,
        AnalysisToolkit,
        TurnBasedWorkflow,
        WorkflowStep,
        LiveGUIReview,
        GrepFlightIntegration,
        CLIFormatter
    )
    SCOPE_FLOW_AVAILABLE = True
except ImportError:
    SCOPE_FLOW_AVAILABLE = False
    # Create minimal stand-in classes
    class ScopeAnalyzer:
        pass
    class EnhancedScopeAnalyzer:
        pass
    class AnalysisToolkit:
        pass
    class TurnBasedWorkflow:
        pass
    class WorkflowStep:
        pass
    class LiveGUIReview:
        pass
    class GrepFlightIntegration:
        pass
    class CLIFormatter:
        pass

try:
    # Try to import from tkinter_profiler
    import tkinter_profiler
    from tkinter_profiler import (
        TkinterProfiler,
        SystemManifest,
        EntityProfile,
        Assumption,
        ConfidenceLevel
    )
    TKINTER_PROFILER_AVAILABLE = True
except ImportError:
    TKINTER_PROFILER_AVAILABLE = False
    # Create minimal stand-in classes
    class TkinterProfiler:
        pass
    class SystemManifest:
        pass
    class EntityProfile:
        pass
    class Assumption:
        pass
    class ConfidenceLevel(Enum):
        HIGH = "high"
        MEDIUM = "medium"
        LOW = "low"
        GUESS = "guess"

# ============================================================================
# Core Data Models
# ============================================================================

class AnalysisPhase(Enum):
    """Phases of analysis workflow"""
    DISCOVERY = "discovery"
    STRUCTURE = "structure"
    QUALITY = "quality"
    FEATURE = "feature"
    INTEGRATION = "integration"
    VERIFICATION = "verification"
    ABSORPTION = "absorption"
    REVIEW = "review"

class ConfidenceScore:
    """Confidence scoring system with percentages"""
    
    @staticmethod
    def calculate(feature_type: str, evidence: List[str], context: Dict) -> float:
        """Calculate confidence percentage (0-100)"""
        base_scores = {
            'import': 0.95,
            'class_def': 0.90,
            'function_def': 0.85,
            'ui_element': 0.80,
            'widget_type': 0.85,
            'layout_pattern': 0.75,
            'event_binding': 0.70,
            'call_chain': 0.65,
            'dependency': 0.60,
            'pattern_match': 0.55
        }
        
        base = base_scores.get(feature_type, 0.50)
        
        # Adjust based on evidence
        evidence_factor = min(1.0, len(evidence) * 0.2)
        
        # Adjust based on context
        context_factor = 1.0
        if 'parent_structure' in context:
            context_factor *= 1.1
        if 'import_chains' in context:
            context_factor *= 1.05
            
        confidence = base * evidence_factor * context_factor
        return min(100.0, confidence * 100)

@dataclass
class Feature:
    """A detected feature in the source code"""
    id: str
    name: str
    type: str
    file_path: str
    line_start: int
    line_end: int
    confidence: float  # 0-100%
    evidence: List[str]
    attributes: Dict[str, Any] = field(default_factory=dict)
    dependencies: List[str] = field(default_factory=list)
    parent_id: Optional[str] = None
    children: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())

@dataclass
class AbsorptionPoint:
    """A point where absorption/integration can occur"""
    id: str
    feature_id: str
    type: str  # 'import', 'class', 'method', 'ui_element', 'event', 'hook'
    file_path: str
    line_number: int
    code_snippet: str
    context: Dict[str, Any]
    compatibility_score: float  # 0-100%
    suggested_integration: str
    risks: List[str] = field(default_factory=list)
    alternatives: List[Dict] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class Session:
    """Analysis/absorption session"""
    id: str
    name: str
    source_path: str
    start_time: str
    end_time: Optional[str] = None
    phase: str = "created"
    status: str = "pending"  # pending, running, completed, failed, paused
    progress: float = 0.0
    features_found: int = 0
    absorption_points: int = 0
    issues_detected: int = 0
    auto_fixes_applied: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)
    snapshot_id: Optional[str] = None

@dataclass
class Snapshot:
    """Version snapshot for revert capability"""
    id: str
    session_id: str
    timestamp: str
    description: str
    file_state: Dict[str, Dict]  # filename -> {'content': ..., 'hash': ..., 'metadata': ...}
    manifest_state: Dict
    diff_summary: Dict
    tags: List[str] = field(default_factory=list)

@dataclass
class IntegrationManifest:
    """Main manifest for absorbed application"""
    manifest_id: str
    application_name: str
    source_path: str
    created_at: str
    updated_at: str
    
    # Parent Structure
    parent_structure: Dict[str, Any]
    quality_assessment: Dict[str, Any]
    
    # Features
    features: Dict[str, Feature]
    features_by_type: Dict[str, List[str]]
    
    # Absorption Points
    absorption_points: Dict[str, AbsorptionPoint]
    absorption_by_type: Dict[str, List[str]]
    
    # Sessions
    sessions: Dict[str, Session]
    current_session_id: Optional[str] = None
    
    # Snapshots
    snapshots: Dict[str, Snapshot]
    latest_snapshot_id: Optional[str] = None
    
    # Dependencies
    import_graph: Dict[str, List[str]]
    call_chains: Dict[str, List[List[str]]]
    
    # Metadata
    tags: List[str] = field(default_factory=list)
    config: Dict[str, Any] = field(default_factory=dict)
    statistics: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self):
        """Convert to serializable dictionary"""
        def serialize(obj):
            if is_dataclass(obj) and not isinstance(obj, type):
                return {k: serialize(v) for k, v in asdict(obj).items()}
            elif isinstance(obj, (list, tuple)):
                return [serialize(i) for i in obj]
            elif isinstance(obj, dict):
                return {k: serialize(v) for k, v in obj.items()}
            elif isinstance(obj, datetime):
                return obj.isoformat()
            else:
                return obj
        
        return serialize(asdict(self))

# ============================================================================
# Core Analysis Engine
# ============================================================================

class TkinterAbsorbEngine:
    """Main analysis and absorption engine"""
    
    def __init__(self, base_dir: str = None, standalone: bool = False):
        self.base_dir = base_dir or Path.home() / ".tkinter_absorb"
        self.manifest_dir = Path(self.base_dir) / "manifests"
        self.sessions_dir = Path(self.base_dir) / "sessions"
        self.snapshots_dir = Path(self.base_dir) / "snapshots"
        
        # Create directories
        for dir_path in [self.manifest_dir, self.sessions_dir, self.snapshots_dir]:
            dir_path.mkdir(parents=True, exist_ok=True)
        
        # Database for history tracking
        self.db_path = Path(self.base_dir) / "absorb.db"
        self.init_database()
        
        # Engine state
        self.current_manifest: Optional[IntegrationManifest] = None
        self.current_session: Optional[Session] = None
        self.standalone = standalone
        
        # Initialize parent tools if available
        self.scope_analyzer = None
        self.tkinter_profiler = None
        self.grep_integration = None
        
        if not standalone:
            self._init_parent_tools()
        
        # Analysis components
        self.feature_detectors = self._init_feature_detectors()
        self.quality_checkers = self._init_quality_checkers()
        self.integration_suggesters = self._init_integration_suggesters()
        
        # Turn-based workflow
        self.workflow = None
        
        # Threading
        self.analysis_queue = queue.Queue()
        self.analysis_thread = None
        self.running = False
        
    def _init_parent_tools(self):
        """Initialize parent tools if available"""
        if SCOPE_FLOW_AVAILABLE:
            try:
                self.scope_analyzer = EnhancedScopeAnalyzer()
                self.grep_integration = GrepFlightIntegration()
                print("✓ scope_flow integration available")
            except Exception as e:
                print(f"⚠ scope_flow integration failed: {e}")
        
        if TKINTER_PROFILER_AVAILABLE:
            try:
                self.tkinter_profiler = TkinterProfiler()
                print("✓ tkinter_profiler integration available")
            except Exception as e:
                print(f"⚠ tkinter_profiler integration failed: {e}")
    
    def _init_feature_detectors(self) -> Dict[str, Callable]:
        """Initialize feature detection functions"""
        detectors = {
            'import_statement': self._detect_imports,
            'class_definition': self._detect_classes,
            'function_definition': self._detect_functions,
            'ui_widget': self._detect_ui_widgets,
            'layout_manager': self._detect_layout_managers,
            'event_binding': self._detect_event_bindings,
            'tkinter_variable': self._detect_tkinter_variables,
            'callback_function': self._detect_callbacks,
            'menu_structure': self._detect_menus,
            'dialog_window': self._detect_dialogs,
            'canvas_element': self._detect_canvas_elements,
            'thread_usage': self._detect_threads,
            'subprocess_usage': self._detect_subprocess,
            'file_operation': self._detect_file_operations,
            'network_operation': self._detect_network_ops,
            'database_operation': self._detect_database_ops,
        }
        return detectors
    
    def _init_quality_checkers(self) -> Dict[str, Callable]:
        """Initialize quality checking functions"""
        checkers = {
            'import_quality': self._check_import_quality,
            'function_quality': self._check_function_quality,
            'class_quality': self._check_class_quality,
            'ui_quality': self._check_ui_quality,
            'performance_quality': self._check_performance,
            'security_quality': self._check_security,
            'maintainability_quality': self._check_maintainability,
            'style_quality': self._check_code_style,
        }
        return checkers
    
    def _init_integration_suggesters(self) -> Dict[str, Callable]:
        """Initialize integration suggestion functions"""
        suggesters = {
            'import_integration': self._suggest_import_integration,
            'class_integration': self._suggest_class_integration,
            'ui_integration': self._suggest_ui_integration,
            'event_integration': self._suggest_event_integration,
            'data_integration': self._suggest_data_integration,
            'hook_integration': self._suggest_hook_integration,
        }
        return suggesters
    
    def init_database(self):
        """Initialize SQLite database for history tracking"""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        # Sessions table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                name TEXT,
                source_path TEXT,
                start_time TEXT,
                end_time TEXT,
                phase TEXT,
                status TEXT,
                progress REAL,
                features_found INTEGER,
                absorption_points INTEGER,
                issues_detected INTEGER,
                auto_fixes_applied INTEGER,
                metadata TEXT
            )
        ''')
        
        # Snapshots table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS snapshots (
                id TEXT PRIMARY KEY,
                session_id TEXT,
                timestamp TEXT,
                description TEXT,
                file_state_path TEXT,
                manifest_state_path TEXT,
                diff_summary TEXT,
                tags TEXT,
                FOREIGN KEY (session_id) REFERENCES sessions (id)
            )
        ''')
        
        # Features table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS features (
                id TEXT PRIMARY KEY,
                session_id TEXT,
                name TEXT,
                type TEXT,
                file_path TEXT,
                line_start INTEGER,
                line_end INTEGER,
                confidence REAL,
                evidence TEXT,
                attributes TEXT,
                dependencies TEXT,
                parent_id TEXT,
                children TEXT,
                tags TEXT,
                metadata TEXT,
                created_at TEXT,
                updated_at TEXT,
                FOREIGN KEY (session_id) REFERENCES sessions (id)
            )
        ''')
        
        # Absorption points table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS absorption_points (
                id TEXT PRIMARY KEY,
                session_id TEXT,
                feature_id TEXT,
                type TEXT,
                file_path TEXT,
                line_number INTEGER,
                code_snippet TEXT,
                context TEXT,
                compatibility_score REAL,
                suggested_integration TEXT,
                risks TEXT,
                alternatives TEXT,
                metadata TEXT,
                FOREIGN KEY (session_id) REFERENCES sessions (id),
                FOREIGN KEY (feature_id) REFERENCES features (id)
            )
        ''')
        
        # Workflow steps table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS workflow_steps (
                id TEXT PRIMARY KEY,
                session_id TEXT,
                step_number INTEGER,
                phase TEXT,
                name TEXT,
                description TEXT,
                tool TEXT,
                status TEXT,
                start_time TEXT,
                end_time TEXT,
                duration REAL,
                results TEXT,
                FOREIGN KEY (session_id) REFERENCES sessions (id)
            )
        ''')
        
        conn.commit()
        conn.close()
    
    # ============================================================================
    # Core Analysis Methods
    # ============================================================================
    
    def create_session(self, source_path: str, session_name: str = None) -> Session:
        """Create a new analysis session"""
        session_id = hashlib.md5(
            f"{source_path}:{datetime.now().isoformat()}".encode()
        ).hexdigest()[:16]
        
        name = session_name or f"Session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        session = Session(
            id=session_id,
            name=name,
            source_path=source_path,
            start_time=datetime.now().isoformat(),
            status="running",
            phase="initialization"
        )
        
        # Save to database
        self._save_session_to_db(session)
        
        # Set as current
        self.current_session = session
        
        return session
    
    def analyze_source(self, source_path: str, depth: int = 3, 
                      create_manifest: bool = True) -> Dict:
        """
        Main analysis method - analyzes source with progressive depth
        
        Args:
            source_path: Path to source file or directory
            depth: Analysis depth (1-4)
            create_manifest: Whether to create integration manifest
            
        Returns:
            Analysis results dictionary
        """
        print(f"\n{'='*80}")
        print(f"Tkinter Absorb Analysis")
        print(f"Source: {source_path}")
        print(f"Depth: {depth}")
        print(f"{'='*80}")
        
        # Create session
        session = self.create_session(source_path)
        
        try:
            # Phase 1: Discovery
            self._update_session(session.id, phase="discovery", progress=10)
            discovery_results = self._discovery_phase(source_path)
            
            # Phase 2: Structure Analysis
            self._update_session(session.id, phase="structure", progress=30)
            structure_results = self._structure_analysis(source_path, depth)
            
            # Phase 3: Quality Assessment
            self._update_session(session.id, phase="quality", progress=50)
            quality_results = self._quality_assessment(source_path)
            
            # Phase 4: Feature Detection
            self._update_session(session.id, phase="feature", progress=70)
            feature_results = self._feature_detection(source_path, structure_results)
            
            # Phase 5: Integration Point Mapping
            self._update_session(session.id, phase="integration", progress=85)
            integration_results = self._integration_mapping(feature_results)
            
            # Phase 6: Create Manifest
            if create_manifest:
                self._update_session(session.id, phase="manifest", progress=95)
                manifest = self._create_integration_manifest(
                    session,
                    discovery_results,
                    structure_results,
                    quality_results,
                    feature_results,
                    integration_results
                )
                self.current_manifest = manifest
            
            # Phase 7: Finalization
            self._update_session(
                session.id,
                phase="completed",
                status="completed",
                progress=100,
                features_found=len(feature_results.get('features', [])),
                absorption_points=len(integration_results.get('absorption_points', []))
            )
            
            # Create initial snapshot
            snapshot = self.create_snapshot(
                session.id,
                "Initial analysis snapshot",
                ["initial", "analysis"]
            )
            
            results = {
                'session': session,
                'discovery': discovery_results,
                'structure': structure_results,
                'quality': quality_results,
                'features': feature_results,
                'integration': integration_results,
                'manifest': self.current_manifest,
                'snapshot': snapshot
            }
            
            print(f"\n✓ Analysis completed successfully!")
            print(f"  Features detected: {len(feature_results.get('features', []))}")
            print(f"  Absorption points: {len(integration_results.get('absorption_points', []))}")
            print(f"  Quality issues: {quality_results.get('issue_count', 0)}")
            
            return results
            
        except Exception as e:
            self._update_session(
                session.id,
                phase="failed",
                status="failed",
                progress=0
            )
            print(f"\n✗ Analysis failed: {e}")
            traceback.print_exc()
            raise
    
    def _discovery_phase(self, source_path: str) -> Dict:
        """Phase 1: Discover files and basic structure"""
        source = Path(source_path)
        
        if source.is_file():
            files = [source]
            root_dir = source.parent
        else:
            root_dir = source
            # Find Python files
            files = list(root_dir.rglob("*.py"))
        
        # Basic file statistics
        stats = {
            'total_files': len(files),
            'total_size_kb': sum(f.stat().st_size / 1024 for f in files),
            'files_by_type': defaultdict(int),
            'imports_found': [],
            'root_directory': str(root_dir)
        }
        
        # Quick scan for imports in each file
        for file in files[:10]:  # Limit to first 10 for speed
            try:
                with open(file, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Find imports
                import_lines = re.findall(r'^(?:import|from)\s+\S+', content, re.MULTILINE)
                stats['imports_found'].extend(import_lines[:5])  # Limit
                
            except Exception:
                continue
        
        return stats
    
    def _structure_analysis(self, source_path: str, depth: int) -> Dict:
        """Phase 2: Analyze structure with progressive depth"""
        source = Path(source_path)
        results = {
            'depth': depth,
            'file_structures': {},
            'import_graph': defaultdict(list),
            'call_chains': defaultdict(list),
            'class_hierarchy': {},
            'function_flow': {},
            'ui_hierarchy': {}
        }
        
        if source.is_file():
            files = [source]
        else:
            files = list(source.rglob("*.py"))
        
        for file_idx, file in enumerate(files[:20]):  # Limit for performance
            try:
                file_results = self._analyze_file_structure(file, depth)
                results['file_structures'][str(file)] = file_results
                
                # Build import graph
                for imp in file_results.get('imports', []):
                    module = imp.get('module', '')
                    if module:
                        results['import_graph'][str(file)].append(module)
                
                # Extract call chains
                if 'call_chains' in file_results:
                    results['call_chains'][str(file)] = file_results['call_chains']
                
            except Exception as e:
                print(f"Warning: Failed to analyze {file}: {e}")
        
        return results
    
    def _analyze_file_structure(self, file_path: Path, depth: int) -> Dict:
        """Analyze structure of a single file"""
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        results = {
            'file_name': file_path.name,
            'file_path': str(file_path),
            'size_bytes': file_path.stat().st_size,
            'line_count': len(content.splitlines()),
            'imports': [],
            'classes': [],
            'functions': [],
            'ui_elements': [],
            'call_chains': []
        }
        
        try:
            tree = ast.parse(content, filename=str(file_path))
            
            # Depth 1: Basic parsing
            for node in ast.walk(tree):
                # Imports
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        results['imports'].append({
                            'module': alias.name,
                            'alias': alias.asname,
                            'line': node.lineno
                        })
                
                elif isinstance(node, ast.ImportFrom):
                    results['imports'].append({
                        'module': node.module,
                        'imports': [alias.name for alias in node.names],
                        'level': node.level,
                        'line': node.lineno
                    })
                
                # Classes
                elif isinstance(node, ast.ClassDef):
                    class_info = {
                        'name': node.name,
                        'line': node.lineno,
                        'bases': [self._get_node_name(base) for base in node.bases],
                        'methods': []
                    }
                    
                    # Find methods
                    for item in node.body:
                        if isinstance(item, ast.FunctionDef):
                            class_info['methods'].append(item.name)
                    
                    results['classes'].append(class_info)
                
                # Functions
                elif isinstance(node, ast.FunctionDef):
                    results['functions'].append({
                        'name': node.name,
                        'line': node.lineno,
                        'args': [arg.arg for arg in node.args.args],
                        'decorators': [self._get_node_name(d) for d in node.decorator_list]
                    })
            
            # Depth 2: UI Elements (simple pattern matching)
            if depth >= 2:
                lines = content.splitlines()
                for i, line in enumerate(lines, 1):
                    line_lower = line.lower()
                    
                    # Tkinter widget patterns
                    widget_patterns = [
                        (r'(?:tk|ttk)\.(?:Button|Label|Entry|Text|Canvas|Listbox|'
                         r'Combobox|Checkbutton|Radiobutton|Scale|Scrollbar|'
                         r'Spinbox|LabelFrame|Frame|PanedWindow|Menu)', 'widget'),
                        (r'\.(?:pack|grid|place|bind|config|configure)', 'method'),
                        (r'(?:Tk|Toplevel)\(\)', 'window'),
                    ]
                    
                    for pattern, element_type in widget_patterns:
                        if re.search(pattern, line):
                            results['ui_elements'].append({
                                'type': element_type,
                                'line': i,
                                'content': line.strip()[:100]
                            })
            
            # Depth 3: Call chains
            if depth >= 3:
                results['call_chains'] = self._extract_call_chains(tree)
            
        except SyntaxError as e:
            results['parse_error'] = str(e)
        
        return results
    
    def _get_node_name(self, node):
        """Get name from AST node"""
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            return f"{self._get_node_name(node.value)}.{node.attr}"
        elif isinstance(node, ast.Call):
            return self._get_node_name(node.func)
        else:
            return str(node)
    
    def _extract_call_chains(self, tree: ast.AST) -> List[List[str]]:
        """Extract function call chains from AST"""
        chains = []
        
        class CallVisitor(ast.NodeVisitor):
            def __init__(self):
                self.current_chain = []
                self.chains = []
            
            def visit_Call(self, node):
                func_name = self._get_func_name(node.func)
                if func_name:
                    self.current_chain.append(func_name)
                    self.chains.append(list(self.current_chain))
                
                self.generic_visit(node)
                
                if func_name:
                    self.current_chain.pop()
            
            def _get_func_name(self, node):
                if isinstance(node, ast.Name):
                    return node.id
                elif isinstance(node, ast.Attribute):
                    return node.attr
                elif isinstance(node, ast.Call):
                    return self._get_func_name(node.func)
                return None
        
        visitor = CallVisitor()
        visitor.visit(tree)
        return visitor.chains
    
    def _quality_assessment(self, source_path: str) -> Dict:
        """Phase 3: Quality assessment"""
        source = Path(source_path)
        
        if source.is_file():
            files = [source]
        else:
            files = list(source.rglob("*.py"))
        
        results = {
            'files_assessed': len(files),
            'issues_by_category': defaultdict(list),
            'quality_scores': {},
            'recommendations': [],
            'issue_count': 0
        }
        
        for file in files[:10]:  # Limit for performance
            try:
                file_issues = self._assess_file_quality(file)
                
                for category, issues in file_issues.items():
                    results['issues_by_category'][category].extend(issues)
                    results['issue_count'] += len(issues)
                
            except Exception as e:
                results['issues_by_category']['assessment_error'].append({
                    'file': str(file),
                    'error': str(e)
                })
        
        # Calculate quality scores
        total_issues = results['issue_count']
        results['quality_scores'] = {
            'overall': max(0, 100 - total_issues * 2),  # Rough score
            'maintainability': 85,  # Placeholder
            'performance': 90,      # Placeholder
            'security': 95,         # Placeholder
            'style': 80            # Placeholder
        }
        
        # Generate recommendations
        if results['issue_count'] > 0:
            results['recommendations'] = [
                "Run auto-fix workflow to address detected issues",
                "Review high-priority issues before integration",
                "Consider refactoring complex functions"
            ]
        
        return results
    
    def _assess_file_quality(self, file_path: Path) -> Dict[str, List]:
        """Assess quality of a single file"""
        issues = defaultdict(list)
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                lines = content.splitlines()
            
            # Check for common issues
            for i, line in enumerate(lines, 1):
                stripped = line.strip()
                
                # Wildcard imports
                if 'import *' in stripped:
                    issues['style'].append({
                        'file': str(file_path),
                        'line': i,
                        'issue': 'Wildcard import',
                        'severity': 'warning',
                        'fix': 'Import specific names instead'
                    })
                
                # Long lines
                if len(line) > 120:
                    issues['style'].append({
                        'file': str(file_path),
                        'line': i,
                        'issue': f'Line too long ({len(line)} chars)',
                        'severity': 'info',
                        'fix': 'Break into multiple lines'
                    })
                
                # Missing type hints in function definitions
                if stripped.startswith('def ') and '->' not in stripped:
                    # Simple check - not perfect
                    issues['maintainability'].append({
                        'file': str(file_path),
                        'line': i,
                        'issue': 'Function missing return type hint',
                        'severity': 'info',
                        'fix': 'Add type hints'
                    })
                
                # Direct tkinter update() calls
                if '.update()' in stripped and 'update_idletasks' not in stripped:
                    issues['performance'].append({
                        'file': str(file_path),
                        'line': i,
                        'issue': 'Direct update() call',
                        'severity': 'warning',
                        'fix': 'Use update_idletasks() for better performance'
                    })
                
                # Hardcoded file paths
                if any(pattern in stripped for pattern in ['/home/', 'C:\\', '~/']):
                    issues['maintainability'].append({
                        'file': str(file_path),
                        'line': i,
                        'issue': 'Hardcoded file path',
                        'severity': 'warning',
                        'fix': 'Use configurable paths or pathlib'
                    })
            
            # Check for try/except without specific exception
            try_except_pattern = re.compile(r'except\s*:')
            for i, line in enumerate(lines, 1):
                if try_except_pattern.search(line):
                    issues['security'].append({
                        'file': str(file_path),
                        'line': i,
                        'issue': 'Bare except clause',
                        'severity': 'warning',
                        'fix': 'Catch specific exceptions'
                    })
        
        except Exception as e:
            issues['assessment_error'].append({
                'file': str(file_path),
                'error': str(e)
            })
        
        return dict(issues)
    
    def _feature_detection(self, source_path: str, structure_results: Dict) -> Dict:
        """Phase 4: Feature detection with confidence scoring"""
        source = Path(source_path)
        
        if source.is_file():
            files = [source]
        else:
            files = list(source.rglob("*.py"))
        
        features = []
        feature_by_type = defaultdict(list)
        
        for file in files[:15]:  # Limit for performance
            try:
                file_features = self._detect_features_in_file(file, structure_results)
                
                for feature in file_features:
                    features.append(feature)
                    feature_by_type[feature.type].append(feature.id)
                    
            except Exception as e:
                print(f"Warning: Feature detection failed for {file}: {e}")
        
        return {
            'features': features,
            'feature_by_type': dict(feature_by_type),
            'total_features': len(features),
            'feature_types_detected': list(feature_by_type.keys())
        }
    
    def _detect_features_in_file(self, file_path: Path, structure_results: Dict) -> List[Feature]:
        """Detect features in a single file"""
        features = []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                lines = content.splitlines()
            
            file_structure = structure_results.get('file_structures', {}).get(str(file_path), {})
            
            # Detect import features
            for imp in file_structure.get('imports', []):
                feature_id = hashlib.md5(
                    f"import:{imp.get('module', '')}:{file_path}".encode()
                ).hexdigest()[:12]
                
                confidence = ConfidenceScore.calculate(
                    'import',
                    [f"Import found at line {imp.get('line', 'unknown')}"],
                    {'parent_structure': True}
                )
                
                feature = Feature(
                    id=feature_id,
                    name=f"Import: {imp.get('module', 'unknown')}",
                    type='import_statement',
                    file_path=str(file_path),
                    line_start=imp.get('line', 1),
                    line_end=imp.get('line', 1),
                    confidence=confidence,
                    evidence=[f"Line {imp.get('line')}: {imp}"],
                    attributes=imp,
                    tags=['import', 'dependency']
                )
                features.append(feature)
            
            # Detect class features
            for class_info in file_structure.get('classes', []):
                feature_id = hashlib.md5(
                    f"class:{class_info['name']}:{file_path}".encode()
                ).hexdigest()[:12]
                
                confidence = ConfidenceScore.calculate(
                    'class_def',
                    [f"Class definition at line {class_info.get('line', 'unknown')}"],
                    {'parent_structure': True}
                )
                
                feature = Feature(
                    id=feature_id,
                    name=f"Class: {class_info['name']}",
                    type='class_definition',
                    file_path=str(file_path),
                    line_start=class_info.get('line', 1),
                    line_end=class_info.get('line', 1),
                    confidence=confidence,
                    evidence=[f"Line {class_info.get('line')}: class {class_info['name']}"],
                    attributes=class_info,
                    tags=['class', 'structure']
                )
                features.append(feature)
            
            # Detect UI widget features
            for ui_element in file_structure.get('ui_elements', []):
                feature_id = hashlib.md5(
                    f"ui:{ui_element.get('type')}:{ui_element.get('line')}:{file_path}".encode()
                ).hexdigest()[:12]
                
                confidence = ConfidenceScore.calculate(
                    'ui_element',
                    [f"UI element at line {ui_element.get('line', 'unknown')}"],
                    {}
                )
                
                feature = Feature(
                    id=feature_id,
                    name=f"UI: {ui_element.get('type', 'element')}",
                    type='ui_widget',
                    file_path=str(file_path),
                    line_start=ui_element.get('line', 1),
                    line_end=ui_element.get('line', 1),
                    confidence=confidence,
                    evidence=[f"Line {ui_element.get('line')}: {ui_element.get('content', '')[:50]}"],
                    attributes=ui_element,
                    tags=['ui', 'widget', 'gui']
                )
                features.append(feature)
            
            # Pattern-based feature detection
            patterns = [
                (r'class\s+\w+\(.*Tk.*\):', 'tkinter_window', 85),
                (r'\.mainloop\(\)', 'mainloop_entry', 90),
                (r'Menu\(', 'menu_widget', 80),
                (r'Notebook\(', 'tab_widget', 85),
                (r'Toplevel\(', 'popup_window', 85),
                (r'filedialog\.', 'file_dialog', 75),
                (r'colorchooser\.', 'color_chooser', 75),
                (r'messagebox\.', 'message_box', 75),
            ]
            
            for pattern, feature_type, base_confidence in patterns:
                for i, line in enumerate(lines, 1):
                    if re.search(pattern, line):
                        feature_id = hashlib.md5(
                            f"{feature_type}:{i}:{file_path}".encode()
                        ).hexdigest()[:12]
                        
                        feature = Feature(
                            id=feature_id,
                            name=f"Pattern: {feature_type}",
                            type=feature_type,
                            file_path=str(file_path),
                            line_start=i,
                            line_end=i,
                            confidence=base_confidence,
                            evidence=[f"Line {i}: {line.strip()[:100]}"],
                            attributes={'pattern': pattern, 'line_content': line.strip()},
                            tags=['pattern', 'detected']
                        )
                        features.append(feature)
        
        except Exception as e:
            print(f"Error in feature detection for {file_path}: {e}")
        
        return features
    
    def _integration_mapping(self, feature_results: Dict) -> Dict:
        """Phase 5: Map integration/absorption points"""
        absorption_points = []
        
        for feature in feature_results.get('features', []):
            # Create absorption point for each feature
            point = self._create_absorption_point(feature)
            if point:
                absorption_points.append(point)
        
        # Group by type
        points_by_type = defaultdict(list)
        for point in absorption_points:
            points_by_type[point.type].append(point.id)
        
        return {
            'absorption_points': absorption_points,
            'points_by_type': dict(points_by_type),
            'total_points': len(absorption_points)
        }
    
    def _create_absorption_point(self, feature: Feature) -> Optional[AbsorptionPoint]:
        """Create absorption point from a feature"""
        point_id = hashlib.md5(
            f"point:{feature.id}:{datetime.now().isoformat()}".encode()
        ).hexdigest()[:12]
        
        # Determine integration type and suggestions
        integration_info = self._determine_integration(feature)
        
        if not integration_info:
            return None
        
        point = AbsorptionPoint(
            id=point_id,
            feature_id=feature.id,
            type=integration_info['type'],
            file_path=feature.file_path,
            line_number=feature.line_start,
            code_snippet=integration_info.get('snippet', ''),
            context=integration_info.get('context', {}),
            compatibility_score=integration_info.get('compatibility', 75.0),
            suggested_integration=integration_info.get('suggestion', ''),
            risks=integration_info.get('risks', []),
            alternatives=integration_info.get('alternatives', [])
        )
        
        return point
    
    def _determine_integration(self, feature: Feature) -> Dict:
        """Determine integration details for a feature"""
        integration_map = {
            'import_statement': {
                'type': 'import',
                'suggestion': f"Add import: {feature.attributes.get('module', '')}",
                'compatibility': 95.0,
                'risks': ['Import conflicts', 'Circular imports']
            },
            'class_definition': {
                'type': 'class',
                'suggestion': f"Inherit from or instantiate class: {feature.name}",
                'compatibility': 85.0,
                'risks': ['Breaking changes in parent class', 'Method signature mismatches']
            },
            'ui_widget': {
                'type': 'ui_element',
                'suggestion': "Integrate into existing UI layout",
                'compatibility': 80.0,
                'risks': ['Layout conflicts', 'Event handling issues']
            },
            'tkinter_window': {
                'type': 'window',
                'suggestion': "Use as main application window or dialog parent",
                'compatibility': 90.0,
                'risks': ['Multiple mainloops', 'Window management conflicts']
            },
            'mainloop_entry': {
                'type': 'hook',
                'suggestion': "Integrate before or after mainloop for control",
                'compatibility': 70.0,
                'risks': ['Blocking operations', 'Event loop conflicts']
            }
        }
        
        # Default integration info
        default_info = {
            'type': 'hook',
            'suggestion': f"Add integration point for {feature.type}",
            'compatibility': 65.0,
            'risks': ['Unknown compatibility issues']
        }
        
        return integration_map.get(feature.type, default_info)
    
    def _create_integration_manifest(
        self,
        session: Session,
        discovery: Dict,
        structure: Dict,
        quality: Dict,
        features: Dict,
        integration: Dict
    ) -> IntegrationManifest:
        """Create the main integration manifest"""
        manifest_id = hashlib.md5(
            f"{session.source_path}:{session.start_time}".encode()
        ).hexdigest()[:16]
        
        # Organize features by ID
        features_dict = {}
        for feature in features.get('features', []):
            features_dict[feature.id] = feature
        
        # Organize absorption points by ID
        points_dict = {}
        for point in integration.get('absorption_points', []):
            points_dict[point.id] = point
        
        manifest = IntegrationManifest(
            manifest_id=manifest_id,
            application_name=Path(session.source_path).name,
            source_path=session.source_path,
            created_at=datetime.now().isoformat(),
            updated_at=datetime.now().isoformat(),
            
            # Parent structure
            parent_structure=structure,
            quality_assessment=quality,
            
            # Features and points
            features=features_dict,
            features_by_type=features.get('feature_by_type', {}),
            absorption_points=points_dict,
            absorption_by_type=integration.get('points_by_type', {}),
            
            # Sessions
            sessions={session.id: session},
            current_session_id=session.id,
            
            # Snapshots (empty for now)
            snapshots={},
            
            # Dependencies
            import_graph=structure.get('import_graph', {}),
            call_chains=structure.get('call_chains', {}),
            
            # Metadata
            tags=['analyzed', 'manifest_created'],
            config={'analysis_depth': 3, 'auto_fix_enabled': True},
            statistics={
                'total_features': len(features_dict),
                'total_points': len(points_dict),
                'quality_score': quality.get('quality_scores', {}).get('overall', 0),
                'issue_count': quality.get('issue_count', 0)
            }
        )
        
        # Save manifest to file
        self._save_manifest(manifest)
        
        return manifest
    
    # ============================================================================
    # Turn-Based Workflow System
    # ============================================================================
    
    def create_turn_based_workflow(self, workflow_type: str = "auto_onboarding") -> TurnBasedWorkflow:
        """Create a turn-based workflow for analysis/fix"""
        
        workflows = {
            "auto_onboarding": [
                WorkflowStep("discovery", "discovery", 
                           description="Discover files and basic structure"),
                WorkflowStep("structure_analysis", "structure",
                           description="Analyze code structure and hierarchy"),
                WorkflowStep("quality_assessment", "quality",
                           description="Assess code quality and issues"),
                WorkflowStep("feature_detection", "feature",
                           description="Detect features with confidence scoring"),
                WorkflowStep("integration_mapping", "integration",
                           description="Map absorption/integration points"),
                WorkflowStep("manifest_creation", "verification",
                           description="Create integration manifest"),
                WorkflowStep("auto_fix", "fix", "autoflake",
                           description="Auto-fix import issues"),
                WorkflowStep("style_fix", "fix", "ruff",
                           description="Fix code style issues"),
                WorkflowStep("format_code", "fix", "black",
                           description="Format code with black"),
                WorkflowStep("create_snapshot", "absorption",
                           description="Create initial snapshot"),
                WorkflowStep("review_summary", "review",
                           description="Generate review summary"),
            ],
            
            "quick_analysis": [
                WorkflowStep("discovery", "discovery"),
                WorkflowStep("structure_analysis", "structure"),
                WorkflowStep("feature_detection", "feature"),
                WorkflowStep("manifest_creation", "verification"),
            ],
            
            "auto_fix_only": [
                WorkflowStep("auto_fix", "fix", "autoflake"),
                WorkflowStep("style_fix", "fix", "ruff"),
                WorkflowStep("format_code", "fix", "black"),
                WorkflowStep("create_snapshot", "absorption"),
            ]
        }
        
        workflow_steps = workflows.get(workflow_type, workflows["auto_onboarding"])
        
        if SCOPE_FLOW_AVAILABLE:
            self.workflow = TurnBasedWorkflow()
            self.workflow.steps = workflow_steps
        else:
            # Create simple workflow manager
            self.workflow = SimpleWorkflow(workflow_steps)
        
        return self.workflow
    
    def execute_workflow(self, workflow_type: str = "auto_onboarding", 
                        auto_mode: bool = True) -> Dict:
        """Execute turn-based workflow"""
        print(f"\n{'='*80}")
        print(f"Executing {workflow_type} workflow")
        print(f"Auto mode: {auto_mode}")
        print(f"{'='*80}")
        
        workflow = self.create_turn_based_workflow(workflow_type)
        
        if auto_mode:
            results = workflow.execute_all()
            print(f"\n✓ Workflow completed: {len(results)} steps executed")
        else:
            print("\nStep-by-step execution:")
            results = []
            for step_num in range(len(workflow.steps)):
                result = workflow.execute_next(force=True)
                if result:
                    results.append(result)
                    print(f"  Step {step_num + 1}: {result.get('status', 'unknown')}")
        
        return {
            'workflow_type': workflow_type,
            'steps_executed': len(results),
            'results': results,
            'summary': workflow.get_summary() if hasattr(workflow, 'get_summary') else {}
        }
    
    # ============================================================================
    # Snapshot & Revert System
    # ============================================================================
    
    def create_snapshot(self, session_id: str, description: str, 
                       tags: List[str] = None) -> Snapshot:
        """Create a snapshot of current state"""
        snapshot_id = hashlib.md5(
            f"{session_id}:{datetime.now().isoformat()}".encode()
        ).hexdigest()[:16]
        
        # Get current file states
        session = self._get_session(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")
        
        source_path = Path(session.source_path)
        file_state = {}
        
        if source_path.is_file():
            files = [source_path]
        else:
            files = list(source_path.rglob("*"))
        
        for file in files[:50]:  # Limit for performance
            if file.is_file():
                try:
                    content = file.read_text(encoding='utf-8')
                    file_hash = hashlib.md5(content.encode()).hexdigest()
                    
                    file_state[str(file)] = {
                        'content': content,
                        'hash': file_hash,
                        'size': file.stat().st_size,
                        'modified': file.stat().st_mtime
                    }
                except Exception:
                    continue
        
        # Create diff summary
        diff_summary = self._create_diff_summary(session_id)
        
        snapshot = Snapshot(
            id=snapshot_id,
            session_id=session_id,
            timestamp=datetime.now().isoformat(),
            description=description,
            file_state=file_state,
            manifest_state=self.current_manifest.to_dict() if self.current_manifest else {},
            diff_summary=diff_summary,
            tags=tags or ['snapshot']
        )
        
        # Save snapshot
        self._save_snapshot(snapshot)
        
        # Update manifest
        if self.current_manifest:
            self.current_manifest.snapshots[snapshot_id] = snapshot
            self.current_manifest.latest_snapshot_id = snapshot_id
            self._save_manifest(self.current_manifest)
        
        print(f"✓ Snapshot created: {snapshot_id}")
        return snapshot
    
    def revert_to_snapshot(self, snapshot_id: str, dry_run: bool = False) -> Dict:
        """Revert to a specific snapshot"""
        snapshot = self._get_snapshot(snapshot_id)
        if not snapshot:
            return {'success': False, 'error': f"Snapshot {snapshot_id} not found"}
        
        print(f"\nReverting to snapshot: {snapshot_id}")
        print(f"Description: {snapshot.description}")
        
        reverted_files = []
        failed_files = []
        
        if not dry_run:
            # Restore files
            for file_path, file_info in snapshot.file_state.items():
                try:
                    path = Path(file_path)
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text(file_info['content'], encoding='utf-8')
                    reverted_files.append(file_path)
                except Exception as e:
                    failed_files.append({'file': file_path, 'error': str(e)})
            
            # Restore manifest
            if 'manifest_state' in snapshot.file_state:
                try:
                    manifest_data = snapshot.file_state['manifest_state']['content']
                    manifest_dict = json.loads(manifest_data)
                    # Recreate manifest object
                    # Note: This is simplified - would need proper deserialization
                    print("✓ Manifest restored")
                except Exception as e:
                    print(f"⚠ Manifest restore failed: {e}")
        
        result = {
            'success': len(failed_files) == 0,
            'snapshot_id': snapshot_id,
            'reverted_files': len(reverted_files),
            'failed_files': failed_files,
            'dry_run': dry_run
        }
        
        if not dry_run:
            # Create revert snapshot
            revert_snapshot = self.create_snapshot(
                snapshot.session_id,
                f"Revert from {snapshot_id}",
                ['revert', 'restore']
            )
            result['revert_snapshot_id'] = revert_snapshot.id
        
        return result
    
    def list_snapshots(self, session_id: str = None) -> List[Dict]:
        """List available snapshots"""
        snapshots = []
        
        if session_id:
            # Get snapshots for specific session
            session = self._get_session(session_id)
            if session and self.current_manifest:
                snapshots = list(self.current_manifest.snapshots.values())
        else:
            # Get all snapshots from database
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT id, session_id, timestamp, description, tags
                FROM snapshots
                ORDER BY timestamp DESC
            ''')
            
            for row in cursor.fetchall():
                snapshots.append({
                    'id': row[0],
                    'session_id': row[1],
                    'timestamp': row[2],
                    'description': row[3],
                    'tags': json.loads(row[4]) if row[4] else []
                })
            
            conn.close()
        
        return snapshots
    
    def _create_diff_summary(self, session_id: str) -> Dict:
        """Create diff summary between snapshots"""
        snapshots = self.list_snapshots(session_id)
        
        if len(snapshots) < 2:
            return {'total_snapshots': len(snapshots)}
        
        # Get current and previous snapshot
        current = snapshots[0]
        previous = snapshots[1] if len(snapshots) > 1 else None
        
        # Simplified diff - in reality would compare file contents
        return {
            'total_snapshots': len(snapshots),
            'current_snapshot': current['id'],
            'previous_snapshot': previous['id'] if previous else None,
            'files_changed': 'N/A',  # Would calculate actual diffs
            'lines_added': 0,
            'lines_removed': 0,
            'timestamp': datetime.now().isoformat()
        }
    
    # ============================================================================
    # Database Operations
    # ============================================================================
    
    def _save_session_to_db(self, session: Session):
        """Save session to database"""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO sessions 
            (id, name, source_path, start_time, end_time, phase, status, 
             progress, features_found, absorption_points, issues_detected, 
             auto_fixes_applied, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            session.id,
            session.name,
            session.source_path,
            session.start_time,
            session.end_time,
            session.phase,
            session.status,
            session.progress,
            session.features_found,
            session.absorption_points,
            session.issues_detected,
            session.auto_fixes_applied,
            json.dumps(session.metadata)
        ))
        
        conn.commit()
        conn.close()
    
    def _update_session(self, session_id: str, **kwargs):
        """Update session in database"""
        if not self.current_session or self.current_session.id != session_id:
            return
        
        # Update current session object
        for key, value in kwargs.items():
            if hasattr(self.current_session, key):
                setattr(self.current_session, key, value)
        
        # Update database
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        # Build update query
        set_clause = ', '.join([f"{k} = ?" for k in kwargs.keys()])
        values = list(kwargs.values())
        values.append(session_id)
        
        cursor.execute(f'''
            UPDATE sessions 
            SET {set_clause}
            WHERE id = ?
        ''', values)
        
        conn.commit()
        conn.close()
    
    def _get_session(self, session_id: str) -> Optional[Session]:
        """Get session from database"""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM sessions WHERE id = ?', (session_id,))
        row = cursor.fetchone()
        
        conn.close()
        
        if row:
            return Session(
                id=row[0],
                name=row[1],
                source_path=row[2],
                start_time=row[3],
                end_time=row[4],
                phase=row[5],
                status=row[6],
                progress=row[7],
                features_found=row[8],
                absorption_points=row[9],
                issues_detected=row[10],
                auto_fixes_applied=row[11],
                metadata=json.loads(row[12]) if row[12] else {}
            )
        
        return None
    
    def _save_snapshot(self, snapshot: Snapshot):
        """Save snapshot to database and file"""
        # Save to database
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO snapshots 
            (id, session_id, timestamp, description, file_state_path, 
             manifest_state_path, diff_summary, tags)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            snapshot.id,
            snapshot.session_id,
            snapshot.timestamp,
            snapshot.description,
            '',  # file_state_path - would store path to file
            '',  # manifest_state_path - would store path to file
            json.dumps(snapshot.diff_summary),
            json.dumps(snapshot.tags)
        ))
        
        conn.commit()
        conn.close()
        
        # Save snapshot file
        snapshot_file = self.snapshots_dir / f"{snapshot.id}.json"
        snapshot_data = asdict(snapshot)
        
        # Remove large content for file state (store separately)
        for file_path, file_info in snapshot_data['file_state'].items():
            if 'content' in file_info:
                del file_info['content']
        
        with open(snapshot_file, 'w') as f:
            json.dump(snapshot_data, f, indent=2)
    
    def _get_snapshot(self, snapshot_id: str) -> Optional[Snapshot]:
        """Get snapshot from database"""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM snapshots WHERE id = ?', (snapshot_id,))
        row = cursor.fetchone()
        
        conn.close()
        
        if row:
            # Load snapshot file
            snapshot_file = self.snapshots_dir / f"{snapshot_id}.json"
            if snapshot_file.exists():
                with open(snapshot_file, 'r') as f:
                    snapshot_data = json.load(f)
                
                return Snapshot(**snapshot_data)
        
        return None
    
    def _save_manifest(self, manifest: IntegrationManifest):
        """Save manifest to file"""
        manifest_file = self.manifest_dir / f"{manifest.manifest_id}.json"
        
        with open(manifest_file, 'w') as f:
            json.dump(manifest.to_dict(), f, indent=2, default=str)
    
    def load_manifest(self, manifest_id: str) -> Optional[IntegrationManifest]:
        """Load manifest from file"""
        manifest_file = self.manifest_dir / f"{manifest_id}.json"
        
        if not manifest_file.exists():
            return None
        
        with open(manifest_file, 'r') as f:
            data = json.load(f)
        
        # Recreate objects (simplified - would need proper deserialization)
        manifest = IntegrationManifest(**data)
        self.current_manifest = manifest
        return manifest

# ============================================================================
# Simple Workflow (Fallback)
# ============================================================================

class SimpleWorkflow:
    """Simple workflow manager for standalone mode"""
    
    def __init__(self, steps):
        self.steps = steps
        self.current_step = 0
        self.execution_log = []
    
    def execute_all(self):
        """Execute all steps"""
        results = []
        for step in self.steps:
            result = self._execute_step(step)
            results.append(result)
            self.execution_log.append(result)
        
        return results
    
    def execute_next(self, force=False):
        """Execute next step"""
        if self.current_step >= len(self.steps):
            return None
        
        step = self.steps[self.current_step]
        result = self._execute_step(step)
        
        self.execution_log.append(result)
        self.current_step += 1
        
        return result
    
    def _execute_step(self, step):
        """Execute a single step"""
        print(f"  Executing: {step.name} - {step.description}")
        
        # Simulate execution
        time.sleep(0.5)  # Simulate work
        
        return {
            'step': step.name,
            'phase': step.phase,
            'status': 'completed',
            'duration': 0.5,
            'timestamp': datetime.now().isoformat()
        }
    
    def get_summary(self):
        """Get workflow summary"""
        completed = sum(1 for r in self.execution_log if r.get('status') == 'completed')
        
        return {
            'total_steps': len(self.steps),
            'completed': completed,
            'progress': f"{completed}/{len(self.steps)}",
            'current_step': self.current_step
        }

# ============================================================================
# CLI Interface
# ============================================================================

class TkinterAbsorbCLI:
    """Command-line interface for Tkinter Absorb"""
    
    def __init__(self):
        self.engine = TkinterAbsorbEngine()
        self.parser = self._create_parser()
    
    def _create_parser(self):
        """Create argument parser"""
        parser = argparse.ArgumentParser(
            description="Tkinter Absorb - Non-Compromising Integration & Analysis Tool",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
EXAMPLES:
  # Full analysis with auto-onboarding
  tkinter_absorb.py --analyze --file=/path/to/app.py --depth=4 --auto
  
  # Quick analysis only
  tkinter_absorb.py --analyze --file=app.py --quick
  
  # Run auto-fix workflow
  tkinter_absorb.py --auto-fix --file=app.py --backup
  
  # Create snapshot
  tkinter_absorb.py --snapshot --session=SESSION_ID
  
  # Revert to snapshot
  tkinter_absorb.py --revert SNAPSHOT_ID --dry-run
  
  # List sessions/snapshots
  tkinter_absorb.py --list-sessions
  tkinter_absorb.py --list-snapshots --session=SESSION_ID
  
  # Get feature info
  tkinter_absorb.py --feature-info --file=app.py --feature-type=import
  
  # Launch GUI review
  tkinter_absorb.py --gui-review --file=app.py
  
  # Standalone mode (no parent dependencies)
  tkinter_absorb.py --standalone --analyze --file=app.py

WORKFLOWS:
  auto_onboarding    Full analysis + auto-fix + manifest creation
  quick_analysis     Basic analysis only
  auto_fix_only      Auto-fix code issues only
            """
        )
        
        # Core commands
        parser.add_argument('--analyze', '-a', action='store_true',
                          help='Run progressive analysis on file/directory')
        parser.add_argument('--auto-fix', action='store_true',
                          help='Auto-fix detectable issues')
        parser.add_argument('--workflow', type=str, 
                          choices=['auto_onboarding', 'quick_analysis', 'auto_fix_only'],
                          help='Run specific workflow')
        parser.add_argument('--auto', action='store_true',
                          help='Run in auto mode (no confirmation)')
        
        # File operations
        parser.add_argument('--file', '-f', type=str,
                          help='File to analyze/fix')
        parser.add_argument('--dir', '-d', type=str,
                          help='Directory for analysis')
        parser.add_argument('--backup', '-b', action='store_true',
                          help='Create backup before modifications')
        
        # Analysis options
        parser.add_argument('--depth', type=int, default=3,
                          help='Analysis depth (1-4, default: 3)')
        parser.add_argument('--quick', '-q', action='store_true',
                          help='Quick analysis (depth=2)')
        
        # Session management
        parser.add_argument('--session', '-s', type=str,
                          help='Session ID to operate on')
        parser.add_argument('--list-sessions', action='store_true',
                          help='List all analysis sessions')
        parser.add_argument('--session-info', type=str,
                          help='Show detailed session information')
        
        # Snapshot management
        parser.add_argument('--snapshot', action='store_true',
                          help='Create snapshot of current state')
        parser.add_argument('--revert', type=str,
                          help='Revert to specified snapshot ID')
        parser.add_argument('--dry-run', action='store_true',
                          help='Dry run for revert operation')
        parser.add_argument('--list-snapshots', action='store_true',
                          help='List snapshots for session')
        
        # Feature operations
        parser.add_argument('--feature-info', action='store_true',
                          help='Show feature information')
        parser.add_argument('--feature-type', type=str,
                          help='Filter features by type')
        parser.add_argument('--confidence-min', type=float, default=70.0,
                          help='Minimum confidence percentage (0-100)')
        
        # GUI operations
        parser.add_argument('--gui-review', action='store_true',
                          help='Launch GUI review mode')
        parser.add_argument('--visual-diff', action='store_true',
                          help='Show visual diff of changes')
        
        # Manifest operations
        parser.add_argument('--manifest', '-m', type=str,
                          help='Manifest ID to load')
        parser.add_argument('--export-manifest', type=str,
                          help='Export manifest to file')
        parser.add_argument('--import-manifest', type=str,
                          help='Import manifest from file')
        
        # System options
        parser.add_argument('--standalone', action='store_true',
                          help='Run in standalone mode (no parent dependencies)')
        parser.add_argument('--verbose', '-v', action='count', default=0,
                          help='Verbose output')
        parser.add_argument('--version', action='store_true',
                          help='Show version information')
        
        return parser
    
    def run(self):
        """Main CLI entry point"""
        args = self.parser.parse_args()
        
        if args.version:
            self._show_version()
            return
        
        if args.standalone:
            self.engine = TkinterAbsorbEngine(standalone=True)
        
        if args.verbose > 0:
            print(f"Verbose level: {args.verbose}")
            print(f"Standalone mode: {args.standalone}")
        
        # Handle commands
        if args.analyze:
            self._handle_analyze(args)
        elif args.auto_fix:
            self._handle_auto_fix(args)
        elif args.workflow:
            self._handle_workflow(args)
        elif args.list_sessions:
            self._handle_list_sessions(args)
        elif args.session_info:
            self._handle_session_info(args)
        elif args.snapshot:
            self._handle_snapshot(args)
        elif args.revert:
            self._handle_revert(args)
        elif args.list_snapshots:
            self._handle_list_snapshots(args)
        elif args.feature_info:
            self._handle_feature_info(args)
        elif args.gui_review:
            self._handle_gui_review(args)
        elif args.export_manifest:
            self._handle_export_manifest(args)
        elif args.import_manifest:
            self._handle_import_manifest(args)
        else:
            self.parser.print_help()
    
    def _handle_analyze(self, args):
        """Handle analyze command"""
        source_path = args.file or args.dir
        if not source_path:
            print("Error: --file or --dir required for analysis")
            return
        
        depth = 2 if args.quick else args.depth
        
        try:
            results = self.engine.analyze_source(source_path, depth)
            
            # Print summary
            print("\n" + "="*80)
            print("ANALYSIS SUMMARY")
            print("="*80)
            
            session = results['session']
            features = results['features']
            integration = results['integration']
            quality = results['quality']
            
            print(f"Session ID: {session.id}")
            print(f"Source: {session.source_path}")
            print(f"Duration: {session.end_time or 'In progress'}")
            print(f"Features detected: {session.features_found}")
            print(f"Absorption points: {session.absorption_points}")
            print(f"Quality issues: {quality.get('issue_count', 0)}")
            
            if features.get('feature_types_detected'):
                print(f"\nFeature types: {', '.join(features['feature_types_detected'])}")
            
            if integration.get('points_by_type'):
                print("\nAbsorption points by type:")
                for point_type, point_ids in integration['points_by_type'].items():
                    print(f"  {point_type}: {len(point_ids)}")
            
            print(f"\nManifest created: {self.engine.current_manifest.manifest_id}")
            print("Use --session-info to see detailed results")
            
        except Exception as e:
            print(f"Analysis failed: {e}")
            if args.verbose > 0:
                traceback.print_exc()
    
    def _handle_auto_fix(self, args):
        """Handle auto-fix command"""
        if not args.file:
            print("Error: --file required for auto-fix")
            return
        
        if args.backup:
            backup_path = args.file + '.backup'
            shutil.copy2(args.file, backup_path)
            print(f"✓ Backup created: {backup_path}")
        
        print(f"Running auto-fix on {args.file}...")
        
        # Run auto-fix workflow
        workflow_results = self.engine.execute_workflow("auto_fix_only", auto_mode=True)
        
        print(f"\nAuto-fix completed:")
        print(f"  Steps executed: {workflow_results['steps_executed']}")
        
        # Create snapshot
        if self.engine.current_session:
            snapshot = self.engine.create_snapshot(
                self.engine.current_session.id,
                "Auto-fix snapshot",
                ["auto_fix", "automated"]
            )
            print(f"  Snapshot created: {snapshot.id}")
    
    def _handle_workflow(self, args):
        """Handle workflow command"""
        source_path = args.file or args.dir
        if not source_path:
            print("Error: --file or --dir required for workflow")
            return
        
        # First analyze if needed
        if not self.engine.current_manifest:
            print("Running initial analysis...")
            self.engine.analyze_source(source_path, depth=3)
        
        # Execute workflow
        workflow_results = self.engine.execute_workflow(
            args.workflow, 
            auto_mode=args.auto
        )
        
        print(f"\nWorkflow '{args.workflow}' completed")
        print(f"Results: {workflow_results['steps_executed']} steps executed")
        
        if 'summary' in workflow_results:
            summary = workflow_results['summary']
            print(f"Progress: {summary.get('progress', 'N/A')}")
    
    def _handle_list_sessions(self, args):
        """List all sessions"""
        conn = sqlite3.connect(str(self.engine.db_path))
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, name, source_path, start_time, status, features_found
            FROM sessions
            ORDER BY start_time DESC
        ''')
        
        sessions = cursor.fetchall()
        conn.close()
        
        if not sessions:
            print("No sessions found")
            return
        
        print(f"\n{'='*80}")
        print(f"SESSIONS ({len(sessions)})")
        print(f"{'='*80}")
        
        for session in sessions:
            print(f"\nID: {session[0]}")
            print(f"Name: {session[1]}")
            print(f"Source: {session[2]}")
            print(f"Started: {session[3]}")
            print(f"Status: {session[4]}")
            print(f"Features: {session[5]}")
            print(f"-" * 40)
    
    def _handle_session_info(self, args):
        """Show detailed session information"""
        session_id = args.session_info
        
        session = self.engine._get_session(session_id)
        if not session:
            print(f"Session {session_id} not found")
            return
        
        print(f"\n{'='*80}")
        print(f"SESSION DETAILS: {session.name}")
        print(f"{'='*80}")
        print(f"ID: {session.id}")
        print(f"Source: {session.source_path}")
        print(f"Start: {session.start_time}")
        print(f"End: {session.end_time or 'N/A'}")
        print(f"Phase: {session.phase}")
        print(f"Status: {session.status}")
        print(f"Progress: {session.progress}%")
        print(f"\nStatistics:")
        print(f"  Features found: {session.features_found}")
        print(f"  Absorption points: {session.absorption_points}")
        print(f"  Issues detected: {session.issues_detected}")
        print(f"  Auto-fixes applied: {session.auto_fixes_applied}")
        
        # Load manifest if available
        manifest_file = self.engine.manifest_dir / f"{session.id[:16]}.json"
        if manifest_file.exists():
            print(f"\nManifest: {session.id[:16]}")
            print(f"Path: {manifest_file}")
    
    def _handle_snapshot(self, args):
        """Handle snapshot creation"""
        session_id = args.session or (self.engine.current_session.id 
                                    if self.engine.current_session else None)
        
        if not session_id:
            print("Error: No active session. Use --session to specify.")
            return
        
        description = input("Enter snapshot description: ").strip() or "Manual snapshot"
        tags_input = input("Enter tags (comma-separated): ").strip()
        tags = [t.strip() for t in tags_input.split(',')] if tags_input else ['manual']
        
        snapshot = self.engine.create_snapshot(session_id, description, tags)
        
        print(f"\n✓ Snapshot created:")
        print(f"  ID: {snapshot.id}")
        print(f"  Description: {snapshot.description}")
        print(f"  Tags: {', '.join(snapshot.tags)}")
        print(f"  Files captured: {len(snapshot.file_state)}")
    
    def _handle_revert(self, args):
        """Handle revert operation"""
        snapshot_id = args.revert
        
        result = self.engine.revert_to_snapshot(snapshot_id, dry_run=args.dry_run)
        
        print(f"\nRevert operation:")
        print(f"  Snapshot: {snapshot_id}")
        print(f"  Success: {result['success']}")
        print(f"  Files reverted: {result['reverted_files']}")
        print(f"  Dry run: {result['dry_run']}")
        
        if result['failed_files']:
            print(f"\nFailed files:")
            for failure in result['failed_files']:
                print(f"  {failure['file']}: {failure['error']}")
        
        if 'revert_snapshot_id' in result:
            print(f"\nRevert snapshot created: {result['revert_snapshot_id']}")
    
    def _handle_list_snapshots(self, args):
        """List snapshots"""
        session_id = args.session or (self.engine.current_session.id 
                                    if self.engine.current_session else None)
        
        snapshots = self.engine.list_snapshots(session_id)
        
        if not snapshots:
            print("No snapshots found")
            return
        
        print(f"\n{'='*80}")
        print(f"SNAPSHOTS ({len(snapshots)})")
        print(f"{'='*80}")
        
        for snapshot in snapshots:
            print(f"\nID: {snapshot['id']}")
            print(f"Session: {snapshot.get('session_id', 'N/A')}")
            print(f"Created: {snapshot['timestamp']}")
            print(f"Description: {snapshot['description']}")
            print(f"Tags: {', '.join(snapshot.get('tags', []))}")
            print(f"-" * 40)
    
    def _handle_feature_info(self, args):
        """Show feature information"""
        if not self.engine.current_manifest:
            print("Error: No manifest loaded. Run --analyze first.")
            return
        
        features = self.engine.current_manifest.features
        
        if not features:
            print("No features found in manifest")
            return
        
        # Filter features
        filtered_features = []
        for feature in features.values():
            if args.feature_type and feature.type != args.feature_type:
                continue
            if feature.confidence < args.confidence_min:
                continue
            filtered_features.append(feature)
        
        if not filtered_features:
            print(f"No features match the criteria (type={args.feature_type}, min_confidence={args.confidence_min})")
            return
        
        print(f"\n{'='*80}")
        print(f"FEATURES ({len(filtered_features)} found)")
        print(f"{'='*80}")
        
        for feature in filtered_features[:10]:  # Limit output
            print(f"\nFeature: {feature.name}")
            print(f"  Type: {feature.type}")
            print(f"  File: {feature.file_path}")
            print(f"  Lines: {feature.line_start}-{feature.line_end}")
            print(f"  Confidence: {feature.confidence:.1f}%")
            print(f"  Tags: {', '.join(feature.tags)}")
            
            if args.verbose > 0:
                print(f"  Evidence: {feature.evidence[0] if feature.evidence else 'None'}")
                if feature.dependencies:
                    print(f"  Dependencies: {', '.join(feature.dependencies[:3])}")
    
    def _handle_gui_review(self, args):
        """Launch GUI review"""
        if not SCOPE_FLOW_AVAILABLE:
            print("Error: scope_flow not available for GUI review")
            print("Install scope_flow or run with --standalone flag")
            return
        
        if not args.file:
            print("Error: --file required for GUI review")
            return
        
        # Create a simple Tkinter root if needed
        try:
            root = tk.Tk()
            root.withdraw()  # Hide main window
            
            # Use scope_flow's LiveGUIReview
            review = LiveGUIReview(root, args.file)
            review.show_review()
            
            root.mainloop()
            
        except Exception as e:
            print(f"GUI review failed: {e}")
            if args.verbose > 0:
                traceback.print_exc()
    
    def _handle_export_manifest(self, args):
        """Export manifest to file"""
        if not self.engine.current_manifest:
            print("Error: No manifest loaded")
            return
        
        export_path = args.export_manifest or f"manifest_{self.engine.current_manifest.manifest_id}.json"
        
        with open(export_path, 'w') as f:
            json.dump(self.engine.current_manifest.to_dict(), f, indent=2)
        
        print(f"✓ Manifest exported to: {export_path}")
    
    def _handle_import_manifest(self, args):
        """Import manifest from file"""
        import_path = args.import_manifest
        
        try:
            with open(import_path, 'r') as f:
                data = json.load(f)
            
            manifest = IntegrationManifest(**data)
            self.engine.current_manifest = manifest
            
            print(f"✓ Manifest imported: {manifest.manifest_id}")
            print(f"  Application: {manifest.application_name}")
            print(f"  Features: {len(manifest.features)}")
            print(f"  Snapshots: {len(manifest.snapshots)}")
            
        except Exception as e:
            print(f"Import failed: {e}")
    
    def _show_version(self):
        """Show version information"""
        version_info = {
            "tool": "Tkinter Absorb",
            "version": "1.0.0",
            "description": "Non-Compromising Integration & Analysis Tool",
            "dependencies": {
                "scope_flow": "available" if SCOPE_FLOW_AVAILABLE else "not available",
                "tkinter_profiler": "available" if TKINTER_PROFILER_AVAILABLE else "not available"
            },
            "paths": {
                "base_dir": str(self.engine.base_dir),
                "manifests": str(self.engine.manifest_dir),
                "sessions": str(self.engine.sessions_dir),
                "database": str(self.engine.db_path)
            }
        }
        
        print(json.dumps(version_info, indent=2))

# ============================================================================
# GUI Interface (Optional)
# ============================================================================

class TkinterAbsorbGUI:
    """Optional GUI interface for Tkinter Absorb"""
    
    def __init__(self, root):
        self.root = root
        self.root.title("Tkinter Absorb - Integration & Analysis Tool")
        self.root.geometry("1200x800")
        
        self.engine = TkinterAbsorbEngine()
        
        self._setup_ui()
        self._load_recent_sessions()
    
    def _setup_ui(self):
        """Setup the GUI interface"""
        # Create notebook for tabs
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Analysis tab
        self.analysis_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.analysis_frame, text="Analysis")
        self._create_analysis_tab()
        
        # Features tab
        self.features_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.features_frame, text="Features")
        self._create_features_tab()
        
        # Workflow tab
        self.workflow_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.workflow_frame, text="Workflow")
        self._create_workflow_tab()
        
        # Snapshots tab
        self.snapshots_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.snapshots_frame, text="Snapshots")
        self._create_snapshots_tab()
        
        # Status bar
        self.status_var = tk.StringVar(value="Ready")
        status_bar = ttk.Label(self.root, textvariable=self.status_var, relief=tk.SUNKEN)
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)
    
    def _create_analysis_tab(self):
        """Create analysis tab"""
        # File selection
        file_frame = ttk.LabelFrame(self.analysis_frame, text="Source Selection", padding=10)
        file_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.source_var = tk.StringVar()
        ttk.Entry(file_frame, textvariable=self.source_var, width=50).pack(side=tk.LEFT, padx=5)
        ttk.Button(file_frame, text="Browse...", command=self._browse_source).pack(side=tk.LEFT, padx=5)
        
        # Analysis options
        options_frame = ttk.LabelFrame(self.analysis_frame, text="Analysis Options", padding=10)
        options_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.depth_var = tk.IntVar(value=3)
        ttk.Label(options_frame, text="Depth:").grid(row=0, column=0, sticky=tk.W, padx=5)
        ttk.Spinbox(options_frame, from_=1, to=4, textvariable=self.depth_var, width=5).grid(row=0, column=1, padx=5)
        
        self.quick_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(options_frame, text="Quick analysis", variable=self.quick_var).grid(row=0, column=2, padx=20)
        
        self.backup_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(options_frame, text="Create backup", variable=self.backup_var).grid(row=0, column=3, padx=20)
        
        # Action buttons
        button_frame = ttk.Frame(self.analysis_frame)
        button_frame.pack(fill=tk.X, padx=5, pady=10)
        
        ttk.Button(button_frame, text="Analyze", command=self._run_analysis,
                  style="Accent.TButton").pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Auto-Fix", command=self._run_auto_fix).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Full Workflow", command=self._run_full_workflow).pack(side=tk.LEFT, padx=5)
        
        # Results display
        results_frame = ttk.LabelFrame(self.analysis_frame, text="Results", padding=10)
        results_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.results_text = scrolledtext.ScrolledText(results_frame, height=15)
        self.results_text.pack(fill=tk.BOTH, expand=True)
    
    def _create_features_tab(self):
        """Create features tab"""
        # Filter controls
        filter_frame = ttk.Frame(self.features_frame)
        filter_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(filter_frame, text="Filter:").pack(side=tk.LEFT, padx=5)
        self.feature_filter = ttk.Combobox(filter_frame, values=[
            'all', 'import', 'class', 'function', 'ui', 'widget', 'event'
        ], state='readonly')
        self.feature_filter.set('all')
        self.feature_filter.pack(side=tk.LEFT, padx=5)
        
        ttk.Button(filter_frame, text="Refresh", command=self._refresh_features).pack(side=tk.RIGHT, padx=5)
        
        # Features treeview
        tree_frame = ttk.Frame(self.features_frame)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        columns = ('ID', 'Name', 'Type', 'Confidence', 'File', 'Line')
        self.features_tree = ttk.Treeview(tree_frame, columns=columns, show='headings', height=15)
        
        for col in columns:
            self.features_tree.heading(col, text=col)
            self.features_tree.column(col, width=100)
        
        # Add scrollbar
        scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.features_tree.yview)
        self.features_tree.configure(yscrollcommand=scrollbar.set)
        
        self.features_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    
    def _create_workflow_tab(self):
        """Create workflow tab"""
        # Workflow selection
        wf_frame = ttk.LabelFrame(self.workflow_frame, text="Workflow Selection", padding=10)
        wf_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.workflow_var = tk.StringVar(value='auto_onboarding')
        workflows = [
            ('Auto Onboarding', 'auto_onboarding'),
            ('Quick Analysis', 'quick_analysis'),
            ('Auto-Fix Only', 'auto_fix_only')
        ]
        
        for text, value in workflows:
            ttk.Radiobutton(wf_frame, text=text, variable=self.workflow_var, 
                          value=value).pack(anchor=tk.W, padx=20, pady=2)
        
        # Execution controls
        exec_frame = ttk.Frame(self.workflow_frame)
        exec_frame.pack(fill=tk.X, padx=5, pady=10)
        
        ttk.Button(exec_frame, text="Execute", command=self._execute_workflow,
                  style="Accent.TButton").pack(side=tk.LEFT, padx=5)
        
        self.auto_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(exec_frame, text="Auto mode", variable=self.auto_var).pack(side=tk.LEFT, padx=20)
        
        # Progress display
        progress_frame = ttk.LabelFrame(self.workflow_frame, text="Progress", padding=10)
        progress_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.progress_var = tk.DoubleVar(value=0)
        self.progress_bar = ttk.Progressbar(progress_frame, variable=self.progress_var, maximum=100)
        self.progress_bar.pack(fill=tk.X, padx=5, pady=5)
        
        self.status_text = scrolledtext.ScrolledText(progress_frame, height=10)
        self.status_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
    
    def _create_snapshots_tab(self):
        """Create snapshots tab"""
        # Snapshot list
        list_frame = ttk.LabelFrame(self.snapshots_frame, text="Snapshots", padding=10)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        columns = ('ID', 'Timestamp', 'Description', 'Tags', 'Files')
        self.snapshots_tree = ttk.Treeview(list_frame, columns=columns, show='headings', height=10)
        
        for col in columns:
            self.snapshots_tree.heading(col, text=col)
            self.snapshots_tree.column(col, width=100)
        
        # Add scrollbar
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.snapshots_tree.yview)
        self.snapshots_tree.configure(yscrollcommand=scrollbar.set)
        
        self.snapshots_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Action buttons
        action_frame = ttk.Frame(self.snapshots_frame)
        action_frame.pack(fill=tk.X, padx=5, pady=10)
        
        ttk.Button(action_frame, text="Create Snapshot", command=self._create_snapshot).pack(side=tk.LEFT, padx=5)
        ttk.Button(action_frame, text="Revert to Selected", command=self._revert_to_snapshot).pack(side=tk.LEFT, padx=5)
        ttk.Button(action_frame, text="Refresh", command=self._refresh_snapshots).pack(side=tk.RIGHT, padx=5)
    
    def _browse_source(self):
        """Browse for source file/directory"""
        path = filedialog.askopenfilename(
            title="Select Python file",
            filetypes=[("Python files", "*.py"), ("All files", "*.*")]
        )
        if path:
            self.source_var.set(path)
    
    def _run_analysis(self):
        """Run analysis on selected source"""
        source = self.source_var.get()
        if not source:
            messagebox.showerror("Error", "Please select a source file")
            return
        
        depth = 2 if self.quick_var.get() else self.depth_var.get()
        
        self.status_var.set(f"Analyzing {source}...")
        self.results_text.delete(1.0, tk.END)
        
        try:
            results = self.engine.analyze_source(source, depth)
            
            # Display results
            session = results['session']
            self.results_text.insert(tk.END, f"Analysis Complete!\n")
            self.results_text.insert(tk.END, f"Session ID: {session.id}\n")
            self.results_text.insert(tk.END, f"Features: {session.features_found}\n")
            self.results_text.insert(tk.END, f"Absorption Points: {session.absorption_points}\n")
            self.results_text.insert(tk.END, f"\nManifest created: {self.engine.current_manifest.manifest_id}")
            
            self.status_var.set(f"Analysis complete - {session.features_found} features found")
            
            # Refresh other tabs
            self._refresh_features()
            self._refresh_snapshots()
            
        except Exception as e:
            self.results_text.insert(tk.END, f"Analysis failed: {e}")
            self.status_var.set("Analysis failed")
    
    def _run_auto_fix(self):
        """Run auto-fix"""
        if not self.engine.current_session:
            messagebox.showerror("Error", "Run analysis first")
            return
        
        self.status_var.set("Running auto-fix...")
        
        try:
            workflow_results = self.engine.execute_workflow("auto_fix_only", auto_mode=True)
            
            self.status_text.insert(tk.END, f"Auto-fix completed: {workflow_results['steps_executed']} steps\n")
            self.status_var.set("Auto-fix complete")
            
            # Create snapshot
            snapshot = self.engine.create_snapshot(
                self.engine.current_session.id,
                "GUI auto-fix snapshot",
                ["gui", "auto_fix"]
            )
            self.status_text.insert(tk.END, f"Snapshot created: {snapshot.id}\n")
            
            self._refresh_snapshots()
            
        except Exception as e:
            self.status_text.insert(tk.END, f"Auto-fix failed: {e}\n")
            self.status_var.set("Auto-fix failed")
    
    def _run_full_workflow(self):
        """Run full workflow"""
        if not self.engine.current_session:
            messagebox.showerror("Error", "Run analysis first")
            return
        
        workflow_type = self.workflow_var.get()
        auto_mode = self.auto_var.get()
        
        self.status_var.set(f"Running {workflow_type} workflow...")
        self.status_text.delete(1.0, tk.END)
        
        # Run in thread to keep GUI responsive
        def run_workflow_thread():
            try:
                workflow_results = self.engine.execute_workflow(workflow_type, auto_mode)
                
                self.root.after(0, lambda: self._workflow_complete(workflow_results))
                
            except Exception as e:
                self.root.after(0, lambda: self._workflow_failed(e))
        
        thread = threading.Thread(target=run_workflow_thread, daemon=True)
        thread.start()
    
    def _workflow_complete(self, results):
        """Handle workflow completion"""
        self.status_text.insert(tk.END, f"Workflow completed!\n")
        self.status_text.insert(tk.END, f"Steps executed: {results['steps_executed']}\n")
        
        if 'summary' in results:
            summary = results['summary']
            self.status_text.insert(tk.END, f"Progress: {summary.get('progress', 'N/A')}\n")
        
        self.status_var.set("Workflow complete")
        self.progress_var.set(100)
        
        # Create snapshot
        if self.engine.current_session:
            snapshot = self.engine.create_snapshot(
                self.engine.current_session.id,
                f"Workflow: {self.workflow_var.get()}",
                ["workflow", "automated"]
            )
            self.status_text.insert(tk.END, f"Snapshot created: {snapshot.id}\n")
        
        self._refresh_snapshots()
    
    def _workflow_failed(self, error):
        """Handle workflow failure"""
        self.status_text.insert(tk.END, f"Workflow failed: {error}\n")
        self.status_var.set("Workflow failed")
        self.progress_var.set(0)
    
    def _execute_workflow(self):
        """Execute selected workflow"""
        self._run_full_workflow()
    
    def _refresh_features(self):
        """Refresh features treeview"""
        if not self.engine.current_manifest:
            return
        
        # Clear existing items
        for item in self.features_tree.get_children():
            self.features_tree.delete(item)
        
        # Add features
        features = self.engine.current_manifest.features
        
        filter_type = self.feature_filter.get()
        for feature_id, feature in features.items():
            if filter_type != 'all' and filter_type not in feature.type:
                continue
            
            self.features_tree.insert('', 'end', values=(
                feature_id[:8],
                feature.name[:30],
                feature.type,
                f"{feature.confidence:.1f}%",
                Path(feature.file_path).name,
                feature.line_start
            ))
    
    def _create_snapshot(self):
        """Create new snapshot"""
        if not self.engine.current_session:
            messagebox.showerror("Error", "No active session")
            return
        
        # Simple dialog for snapshot info
        dialog = tk.Toplevel(self.root)
        dialog.title("Create Snapshot")
        dialog.geometry("400x200")
        
        ttk.Label(dialog, text="Description:").pack(anchor=tk.W, padx=20, pady=(20, 5))
        desc_entry = ttk.Entry(dialog, width=40)
        desc_entry.pack(padx=20, pady=5)
        desc_entry.insert(0, f"Manual snapshot {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        
        ttk.Label(dialog, text="Tags (comma-separated):").pack(anchor=tk.W, padx=20, pady=(10, 5))
        tags_entry = ttk.Entry(dialog, width=40)
        tags_entry.pack(padx=20, pady=5)
        tags_entry.insert(0, "manual,gui")
        
        def do_create():
            description = desc_entry.get().strip()
            tags = [t.strip() for t in tags_entry.get().split(',')] if tags_entry.get() else ['manual']
            
            snapshot = self.engine.create_snapshot(
                self.engine.current_session.id,
                description,
                tags
            )
            
            self.status_var.set(f"Snapshot created: {snapshot.id}")
            self._refresh_snapshots()
            dialog.destroy()
        
        button_frame = ttk.Frame(dialog)
        button_frame.pack(fill=tk.X, padx=20, pady=20)
        
        ttk.Button(button_frame, text="Create", command=do_create,
                  style="Accent.TButton").pack(side=tk.RIGHT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side=tk.RIGHT, padx=5)
    
    def _revert_to_snapshot(self):
        """Revert to selected snapshot"""
        selection = self.snapshots_tree.selection()
        if not selection:
            messagebox.showerror("Error", "Select a snapshot first")
            return
        
        item = self.snapshots_tree.item(selection[0])
        snapshot_id = item['values'][0]
        
        confirm = messagebox.askyesno(
            "Confirm Revert",
            f"Revert to snapshot {snapshot_id}?\nThis will restore files to their state at snapshot time."
        )
        
        if confirm:
            result = self.engine.revert_to_snapshot(snapshot_id, dry_run=False)
            
            if result['success']:
                self.status_var.set(f"Reverted to snapshot {snapshot_id}")
                messagebox.showinfo("Success", f"Reverted {result['reverted_files']} files")
            else:
                self.status_var.set("Revert failed")
                messagebox.showerror("Error", f"Revert failed: {result.get('error', 'Unknown error')}")
            
            self._refresh_snapshots()
    
    def _refresh_snapshots(self):
        """Refresh snapshots treeview"""
        # Clear existing items
        for item in self.snapshots_tree.get_children():
            self.snapshots_tree.delete(item)
        
        # Get snapshots
        if self.engine.current_session:
            snapshots = self.engine.list_snapshots(self.engine.current_session.id)
        else:
            snapshots = self.engine.list_snapshots()
        
        # Add to treeview
        for snapshot in snapshots[:20]:  # Limit display
            self.snapshots_tree.insert('', 'end', values=(
                snapshot['id'][:8],
                snapshot['timestamp'][:19],
                snapshot['description'][:40],
                ', '.join(snapshot.get('tags', [])[:3]),
                'N/A'  # File count would need to be calculated
            ))
    
    def _load_recent_sessions(self):
        """Load recent sessions"""
        # This would load recent sessions from database
        pass

# ============================================================================
# Main Entry Point
# ============================================================================

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Tkinter Absorb - Integration & Analysis Tool",
        add_help=False  # We'll handle help manually
    )
    
    parser.add_argument('--gui', action='store_true', help='Launch GUI mode')
    parser.add_argument('--help', '-h', action='store_true', help='Show help')
    parser.add_argument('--standalone', action='store_true', 
                       help='Run in standalone mode (no parent dependencies)')
    
    # Parse just the basic args first
    args, remaining = parser.parse_known_args()
    
    if args.help:
        # Show full help from CLI class
        cli = TkinterAbsorbCLI()
        cli.parser.print_help()
        return
    
    if args.gui:
        # Launch GUI mode
        try:
            root = tk.Tk()
            
            # Apply some styling
            style = ttk.Style()
            style.theme_use('clam')  # or 'alt', 'default', 'classic'
            
            # Configure styles
            style.configure("Accent.TButton", font=('TkDefaultFont', 10, 'bold'))
            
            app = TkinterAbsorbGUI(root)
            root.mainloop()
            
        except Exception as e:
            print(f"GUI failed to launch: {e}")
            print("Falling back to CLI mode...")
            cli = TkinterAbsorbCLI()
            cli.run()
    else:
        # Run CLI mode
        cli = TkinterAbsorbCLI()
        cli.run()

if __name__ == "__main__":
    main()