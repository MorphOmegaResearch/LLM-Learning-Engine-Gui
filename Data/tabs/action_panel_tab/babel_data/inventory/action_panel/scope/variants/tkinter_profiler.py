#!/usr/bin/env python3
"""
Tkinter Profiler - A CLI-based tool for profiling and learning from Tkinter applications
with assumption confirmation, entity tracking, and integration capabilities.
"""

import argparse
import json
import os
import sys
import sqlite3
import pickle
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
import hashlib
import yaml
import subprocess
from dataclasses import dataclass, asdict, field
from enum import Enum
import inspect

# ==================== Data Models ====================

class ConfidenceLevel(Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    GUESS = "guess"

@dataclass
class Assumption:
    """Represents a single assumption about the target system."""
    id: str
    description: str
    confidence: ConfidenceLevel
    category: str
    tags: List[str] = field(default_factory=list)
    evidence: List[str] = field(default_factory=list)
    user_confirmed: bool = False
    user_corrected: str = None
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    parent_id: Optional[str] = None
    related_entities: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class EntityProfile:
    """Profile for an observed entity in the system."""
    id: str
    name: str
    entity_type: str
    attributes: Dict[str, Any] = field(default_factory=dict)
    assumptions: List[str] = field(default_factory=list)
    relationships: Dict[str, List[str]] = field(default_factory=dict)
    observed_behaviors: List[Dict[str, Any]] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())

@dataclass
class SystemManifest:
    """Manifest for the entire profiled system."""
    system_id: str
    name: str
    description: str
    target_type: str
    entities: Dict[str, EntityProfile] = field(default_factory=dict)
    assumptions: Dict[str, Assumption] = field(default_factory=dict)
    layers: Dict[str, List[str]] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    lexicon_used: str = "default"
    version: str = "1.0.0"

# ==================== Core Profiler Class ====================

class TkinterProfiler:
    """Main profiler class for Tkinter applications."""
    
    def __init__(self, base_dir: str = None):
        self.base_dir = base_dir or os.path.expanduser("~/.tkinter_profiler")
        self.systems_dir = os.path.join(self.base_dir, "systems_&_entities")
        self.lexicon_dir = os.path.join(self.base_dir, "lexicons")
        self.config_dir = os.path.join(self.base_dir, "config")
        
        # Create directories
        for directory in [self.base_dir, self.systems_dir, self.lexicon_dir, self.config_dir]:
            os.makedirs(directory, exist_ok=True)
        
        # Initialize database
        self.db_path = os.path.join(self.base_dir, "profiler.db")
        self.init_database()
        
        # Load lexicon
        self.lexicon = self.load_lexicon("default")
        
        # Current session state
        self.current_system = None
        self.current_target = None
        self.interactive_mode = True
        
    def init_database(self):
        """Initialize SQLite database for persistent storage."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Create tables
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS systems (
                id TEXT PRIMARY KEY,
                name TEXT,
                description TEXT,
                target_type TEXT,
                manifest_path TEXT,
                created_at TEXT,
                updated_at TEXT
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS assumptions (
                id TEXT PRIMARY KEY,
                system_id TEXT,
                description TEXT,
                confidence TEXT,
                category TEXT,
                tags TEXT,
                evidence TEXT,
                user_confirmed INTEGER,
                user_corrected TEXT,
                timestamp TEXT,
                parent_id TEXT,
                related_entities TEXT,
                metadata TEXT,
                FOREIGN KEY (system_id) REFERENCES systems (id)
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS entities (
                id TEXT PRIMARY KEY,
                system_id TEXT,
                name TEXT,
                entity_type TEXT,
                attributes TEXT,
                assumptions TEXT,
                relationships TEXT,
                observed_behaviors TEXT,
                created_at TEXT,
                updated_at TEXT,
                FOREIGN KEY (system_id) REFERENCES systems (id)
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS interaction_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                system_id TEXT,
                action TEXT,
                details TEXT,
                timestamp TEXT
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def load_lexicon(self, lexicon_name: str) -> Dict:
        """Load a lexicon file."""
        lexicon_path = os.path.join(self.lexicon_dir, f"{lexicon_name}.yaml")
        
        if os.path.exists(lexicon_path):
            with open(lexicon_path, 'r') as f:
                return yaml.safe_load(f)
        else:
            # Create default lexicon
            default_lexicon = {
                "assumption_categories": {
                    "widget_type": "Type of Tkinter widget",
                    "widget_property": "Widget property or configuration",
                    "widget_hierarchy": "Parent-child relationships",
                    "event_binding": "Event handlers and bindings",
                    "layout_management": "Geometry manager usage",
                    "variable_usage": "Tkinter variable usage",
                    "callback_function": "Callback or command function",
                    "style_theme": "Styling and theming",
                    "resource_usage": "Images, fonts, other resources"
                },
                "response_templates": {
                    "assumption_confirmation": [
                        "I assume {assumption} with {confidence} confidence. Is this correct? (Y/n/edit/skip)",
                        "Based on {evidence}, I think {assumption}. Confirm? (Y/n/edit/skip)"
                    ],
                    "assumption_correction": [
                        "What should this be instead?",
                        "Please provide the correct value:"
                    ],
                    "entity_identification": [
                        "I've identified {entity_type} named '{name}'. Should I track it? (Y/n)",
                        "Found potential {entity_type}. Add to profile? (Y/n)"
                    ]
                },
                "entity_types": {
                    "root": "Tkinter root window",
                    "toplevel": "Toplevel window",
                    "frame": "Frame container",
                    "button": "Button widget",
                    "label": "Label widget",
                    "entry": "Entry widget",
                    "text": "Text widget",
                    "canvas": "Canvas widget",
                    "listbox": "Listbox widget",
                    "combobox": "Combobox widget",
                    "menu": "Menu widget",
                    "menubutton": "Menubutton widget",
                    "scrollbar": "Scrollbar widget",
                    "scale": "Scale widget",
                    "checkbutton": "Checkbutton widget",
                    "radiobutton": "Radiobutton widget",
                    "spinbox": "Spinbox widget",
                    "panedwindow": "PanedWindow widget",
                    "labelframe": "LabelFrame widget"
                }
            }
            
            with open(lexicon_path, 'w') as f:
                yaml.dump(default_lexicon, f)
            
            return default_lexicon
    
    # ==================== Core Profiling Methods ====================
    
    def scan_file(self, file_path: str) -> Dict:
        """Scan a Python file for Tkinter usage."""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")
        
        with open(file_path, 'r') as f:
            content = f.read()
        
        # Simple AST parsing for Tkinter patterns
        import ast
        
        try:
            tree = ast.parse(content)
        except SyntaxError:
            return {"error": "Invalid Python syntax"}
        
        findings = {
            "imports": [],
            "widget_creations": [],
            "variable_assignments": [],
            "method_calls": [],
            "event_bindings": []
        }
        
        for node in ast.walk(tree):
            # Find imports
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if 'tkinter' in alias.name.lower():
                        findings["imports"].append(alias.name)
            
            # Find widget creations (patterns like tk.Button() or Button())
            elif isinstance(node, ast.Call):
                # Check for widget creations
                if isinstance(node.func, ast.Attribute):
                    widget_name = node.func.attr
                    if any(widget in widget_name.lower() for widget in ['button', 'label', 'entry', 'frame', 'canvas']):
                        findings["widget_creations"].append({
                            "widget": widget_name,
                            "line": node.lineno if hasattr(node, 'lineno') else 'unknown'
                        })
        
        return findings
    
    def make_assumption(self, evidence: List[str], category: str, 
                       initial_confidence: ConfidenceLevel = ConfidenceLevel.MEDIUM) -> Assumption:
        """Create a new assumption based on evidence."""
        assumption_id = hashlib.md5(
            f"{category}:{':'.join(evidence)}:{datetime.now().isoformat()}".encode()
        ).hexdigest()[:12]
        
        # Generate description from template
        template = self.lexicon["response_templates"]["assumption_confirmation"][0]
        description = f"Based on {len(evidence)} piece(s) of evidence: {', '.join(evidence[:3])}"
        
        assumption = Assumption(
            id=assumption_id,
            description=description,
            confidence=initial_confidence,
            category=category,
            evidence=evidence,
            tags=[category]
        )
        
        return assumption
    
    def present_assumption(self, assumption: Assumption) -> Tuple[bool, Optional[str]]:
        """Present assumption to user and get response."""
        if not self.interactive_mode:
            return True, None
        
        print(f"\n[{assumption.category.upper()}]")
        print(f"Assumption: {assumption.description}")
        print(f"Confidence: {assumption.confidence.value}")
        print(f"Evidence: {', '.join(assumption.evidence[:3])}")
        if len(assumption.evidence) > 3:
            print(f"  ... and {len(assumption.evidence) - 3} more")
        
        while True:
            response = input("\n(Y)es / (n)o / (e)dit / (s)kip / show (a)ll evidence / show (l)ower confidence options: ").lower().strip()
            
            if response in ['y', 'yes', '']:
                assumption.user_confirmed = True
                return True, None
            elif response in ['n', 'no']:
                assumption.user_confirmed = False
                return False, None
            elif response in ['e', 'edit']:
                correction = input("Enter correction: ").strip()
                assumption.user_corrected = correction
                return True, correction
            elif response in ['s', 'skip']:
                return None, None  # Skip this assumption
            elif response in ['a', 'all']:
                print("\nAll evidence:")
                for i, ev in enumerate(assumption.evidence, 1):
                    print(f"  {i}. {ev}")
            elif response in ['l', 'lower']:
                # Show lower confidence alternatives
                alternatives = self.generate_alternatives(assumption)
                if alternatives:
                    print("\nAlternative assumptions (lower confidence):")
                    for i, alt in enumerate(alternatives, 1):
                        print(f"  {i}. {alt.description} [{alt.confidence.value}]")
                    
                    select = input("Select alternative (number) or (c)ancel: ").lower().strip()
                    if select.isdigit() and 1 <= int(select) <= len(alternatives):
                        selected = alternatives[int(select) - 1]
                        assumption.description = selected.description
                        assumption.confidence = selected.confidence
                        continue
                else:
                    print("No alternatives available.")
            else:
                print("Invalid response. Please try again.")
    
    def generate_alternatives(self, assumption: Assumption) -> List[Assumption]:
        """Generate alternative assumptions with lower confidence."""
        alternatives = []
        
        # Simple alternative generation based on category
        if assumption.category == "widget_type":
            # Suggest other widget types
            for widget_type in self.lexicon["entity_types"].keys():
                if widget_type not in assumption.description.lower():
                    alt = Assumption(
                        id=f"{assumption.id}_alt_{len(alternatives)}",
                        description=f"This might be a {widget_type} widget instead",
                        confidence=ConfidenceLevel.LOW,
                        category=assumption.category,
                        evidence=assumption.evidence,
                        tags=assumption.tags + ["alternative"]
                    )
                    alternatives.append(alt)
        
        return alternatives[:3]  # Return top 3 alternatives
    
    def profile_tkinter_file(self, file_path: str, system_name: str = None) -> SystemManifest:
        """Main profiling function for a Tkinter Python file."""
        print(f"Profiling: {file_path}")
        
        # Create system manifest
        system_id = hashlib.md5(file_path.encode()).hexdigest()[:12]
        system_name = system_name or Path(file_path).stem
        
        manifest = SystemManifest(
            system_id=system_id,
            name=system_name,
            description=f"Profile of {file_path}",
            target_type="python_file",
            layers={
                "widget_hierarchy": [],
                "event_system": [],
                "layout_management": []
            }
        )
        
        # Scan file
        findings = self.scan_file(file_path)
        
        if "error" in findings:
            print(f"Error: {findings['error']}")
            return manifest
        
        # Process findings and make assumptions
        assumptions_made = []
        
        # Process imports
        for imp in findings.get("imports", []):
            assumption = self.make_assumption(
                evidence=[f"Import statement: {imp}"],
                category="widget_type",
                initial_confidence=ConfidenceLevel.HIGH
            )
            
            response, correction = self.present_assumption(assumption)
            if response is not None:
                assumption.user_confirmed = response
                if correction:
                    assumption.user_corrected = correction
                
                assumptions_made.append(assumption)
                manifest.assumptions[assumption.id] = assumption
        
        # Process widget creations
        for widget in findings.get("widget_creations", []):
            assumption = self.make_assumption(
                evidence=[f"Widget creation at line {widget['line']}: {widget['widget']}"],
                category="widget_type",
                initial_confidence=ConfidenceLevel.MEDIUM
            )
            
            response, correction = self.present_assumption(assumption)
            if response is not None:
                assumption.user_confirmed = response
                if correction:
                    assumption.user_corrected = correction
                
                assumptions_made.append(assumption)
                manifest.assumptions[assumption.id] = assumption
                
                # Create entity profile for confirmed widgets
                if assumption.user_confirmed:
                    entity_id = f"entity_{len(manifest.entities)}"
                    entity = EntityProfile(
                        id=entity_id,
                        name=f"Widget_{len(manifest.entities)}",
                        entity_type=widget['widget'].lower(),
                        attributes={
                            "source_line": widget['line'],
                            "assumption_id": assumption.id
                        },
                        assumptions=[assumption.id]
                    )
                    manifest.entities[entity_id] = entity
        
        # Save manifest
        self.save_manifest(manifest, file_path)
        
        # Log interaction
        self.log_interaction(system_id, "profile_created", {
            "file": file_path,
            "assumptions_made": len(assumptions_made),
            "entities_found": len(manifest.entities)
        })
        
        print(f"\n✓ Profiling complete!")
        print(f"  - Assumptions made: {len(assumptions_made)}")
        print(f"  - Entities identified: {len(manifest.entities)}")
        print(f"  - Manifest saved to: {self.get_manifest_path(system_id)}")
        
        return manifest
    
    def save_manifest(self, manifest: SystemManifest, source_file: str = None):
        """Save system manifest to file and database."""
        # Save to JSON file
        manifest_dir = os.path.join(self.systems_dir, manifest.system_id)
        os.makedirs(manifest_dir, exist_ok=True)
        
        manifest_path = os.path.join(manifest_dir, "manifest.json")
        
        # Convert to serializable format
        manifest_dict = asdict(manifest)
        
        with open(manifest_path, 'w') as f:
            json.dump(manifest_dict, f, indent=2)
        
        # Save to database
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Save system
        cursor.execute('''
            INSERT OR REPLACE INTO systems (id, name, description, target_type, manifest_path, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            manifest.system_id,
            manifest.name,
            manifest.description,
            manifest.target_type,
            manifest_path,
            manifest.created_at,
            datetime.now().isoformat()
        ))
        
        # Save assumptions
        for assumption in manifest.assumptions.values():
            cursor.execute('''
                INSERT OR REPLACE INTO assumptions 
                (id, system_id, description, confidence, category, tags, evidence, 
                 user_confirmed, user_corrected, timestamp, parent_id, related_entities, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                assumption.id,
                manifest.system_id,
                assumption.description,
                assumption.confidence.value,
                assumption.category,
                json.dumps(assumption.tags),
                json.dumps(assumption.evidence),
                int(assumption.user_confirmed),
                assumption.user_corrected or "",
                assumption.timestamp,
                assumption.parent_id or "",
                json.dumps(assumption.related_entities),
                json.dumps(assumption.metadata)
            ))
        
        # Save entities
        for entity in manifest.entities.values():
            cursor.execute('''
                INSERT OR REPLACE INTO entities 
                (id, system_id, name, entity_type, attributes, assumptions, 
                 relationships, observed_behaviors, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                entity.id,
                manifest.system_id,
                entity.name,
                entity.entity_type,
                json.dumps(entity.attributes),
                json.dumps(entity.assumptions),
                json.dumps(entity.relationships),
                json.dumps(entity.observed_behaviors),
                entity.created_at,
                entity.updated_at
            ))
        
        conn.commit()
        conn.close()
        
        # If source file provided, copy it to the manifest directory
        if source_file and os.path.exists(source_file):
            target_path = os.path.join(manifest_dir, "source.py")
            shutil.copy2(source_file, target_path)
    
    def log_interaction(self, system_id: str, action: str, details: Dict = None):
        """Log an interaction to the database."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO interaction_log (system_id, action, details, timestamp)
            VALUES (?, ?, ?, ?)
        ''', (
            system_id,
            action,
            json.dumps(details or {}),
            datetime.now().isoformat()
        ))
        
        conn.commit()
        conn.close()
    
    def get_manifest_path(self, system_id: str) -> str:
        """Get the path to a system's manifest."""
        return os.path.join(self.systems_dir, system_id, "manifest.json")
    
    def load_manifest(self, system_id: str) -> SystemManifest:
        """Load a system manifest from file."""
        manifest_path = self.get_manifest_path(system_id)
        
        if not os.path.exists(manifest_path):
            raise FileNotFoundError(f"Manifest not found: {manifest_path}")
        
        with open(manifest_path, 'r') as f:
            manifest_dict = json.load(f)
        
        # Convert back to SystemManifest object
        # This is simplified - in reality you'd need proper deserialization
        return SystemManifest(**manifest_dict)
    
    def list_systems(self) -> List[Dict]:
        """List all profiled systems."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT id, name, description, created_at FROM systems ORDER BY created_at DESC')
        systems = cursor.fetchall()
        
        conn.close()
        
        return [{"id": s[0], "name": s[1], "description": s[2], "created_at": s[3]} for s in systems]
    
    def get_system_stats(self, system_id: str) -> Dict:
        """Get statistics for a system."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Count assumptions
        cursor.execute('SELECT COUNT(*) FROM assumptions WHERE system_id = ?', (system_id,))
        assumption_count = cursor.fetchone()[0]
        
        # Count confirmed assumptions
        cursor.execute('SELECT COUNT(*) FROM assumptions WHERE system_id = ? AND user_confirmed = 1', (system_id,))
        confirmed_count = cursor.fetchone()[0]
        
        # Count entities
        cursor.execute('SELECT COUNT(*) FROM entities WHERE system_id = ?', (system_id,))
        entity_count = cursor.fetchone()[0]
        
        conn.close()
        
        return {
            "assumptions_total": assumption_count,
            "assumptions_confirmed": confirmed_count,
            "entities": entity_count,
            "confidence_ratio": confirmed_count / assumption_count if assumption_count > 0 else 0
        }

# ==================== CLI Interface ====================

def setup_argparse():
    """Set up command line argument parser."""
    parser = argparse.ArgumentParser(
        description="Tkinter Profiler - CLI tool for profiling Tkinter applications with learning capabilities",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
EXAMPLES:
  # Profile a Tkinter file interactively
  tkinter-profiler profile my_app.py
  
  # Profile non-interactively (batch mode)
  tkinter-profiler profile --non-interactive my_app.py
  
  # List all profiled systems
  tkinter-profiler list
  
  # Show stats for a specific system
  tkinter-profiler stats SYSTEM_ID
  
  # Export system data
  tkinter-profiler export SYSTEM_ID --format json
  
  # Compare two systems
  tkinter-profiler compare SYSTEM_ID_1 SYSTEM_ID_2
  
  # Create UCA (Thunar context menu) integration
  tkinter-profiler setup-uca
  
  # Generate shell scripts for context menu
  tkinter-profiler generate-scripts

ADVANCED USAGE:
  # Profile with custom lexicon
  tkinter-profiler profile --lexicon custom_lexicon my_app.py
  
  # Profile directory recursively
  tkinter-profiler profile --recursive ./tkinter_apps/
  
  # Skip confirmation for low-confidence assumptions
  tkinter-profiler profile --skip-low my_app.py
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Command to execute')
    
    # Profile command
    profile_parser = subparsers.add_parser('profile', help='Profile a Tkinter file or directory')
    profile_parser.add_argument('target', help='File or directory to profile')
    profile_parser.add_argument('--name', '-n', help='Custom name for the system profile')
    profile_parser.add_argument('--non-interactive', '-ni', action='store_true', 
                               help='Run without user interaction')
    profile_parser.add_argument('--recursive', '-r', action='store_true',
                               help='Recursively profile directory')
    profile_parser.add_argument('--lexicon', '-l', default='default',
                               help='Lexicon to use (default: default)')
    profile_parser.add_argument('--skip-low', action='store_true',
                               help='Skip low-confidence assumptions')
    profile_parser.add_argument('--output-dir', '-o',
                               help='Custom output directory')
    
    # List command
    list_parser = subparsers.add_parser('list', help='List all profiled systems')
    list_parser.add_argument('--verbose', '-v', action='store_true',
                            help='Show detailed information')
    
    # Stats command
    stats_parser = subparsers.add_parser('stats', help='Show statistics for a system')
    stats_parser.add_argument('system_id', help='System ID to show stats for')
    
    # Export command
    export_parser = subparsers.add_parser('export', help='Export system data')
    export_parser.add_argument('system_id', help='System ID to export')
    export_parser.add_argument('--format', '-f', choices=['json', 'yaml', 'csv'], 
                              default='json', help='Export format')
    export_parser.add_argument('--output', '-o', help='Output file')
    
    # Compare command
    compare_parser = subparsers.add_parser('compare', help='Compare two systems')
    compare_parser.add_argument('system_id_1', help='First system ID')
    compare_parser.add_argument('system_id_2', help='Second system ID')
    
    # Setup UCA command
    uca_parser = subparsers.add_parser('setup-uca', help='Setup Thunar UCA integration')
    uca_parser.add_argument('--force', '-f', action='store_true',
                           help='Force overwrite existing UCA entries')
    
    # Generate scripts command
    scripts_parser = subparsers.add_parser('generate-scripts', 
                                          help='Generate shell scripts for context menu')
    scripts_parser.add_argument('--output-dir', '-o', 
                               default='~/.local/share/tkinter-profiler/scripts',
                               help='Output directory for scripts')
    
    # Review command
    review_parser = subparsers.add_parser('review', help='Review and edit assumptions')
    review_parser.add_argument('system_id', help='System ID to review')
    review_parser.add_argument('--assumption-id', '-a', help='Specific assumption to review')
    
    # Interactive mode
    interactive_parser = subparsers.add_parser('interactive', 
                                              help='Enter interactive mode')
    
    return parser

def main():
    """Main CLI entry point."""
    parser = setup_argparse()
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    profiler = TkinterProfiler()
    
    try:
        if args.command == 'profile':
            # Set interactive mode
            profiler.interactive_mode = not args.non_interactive
            
            # Profile target
            if os.path.isdir(args.target):
                if args.recursive:
                    # Profile all Python files in directory recursively
                    python_files = []
                    for root, dirs, files in os.walk(args.target):
                        for file in files:
                            if file.endswith('.py'):
                                python_files.append(os.path.join(root, file))
                    
                    print(f"Found {len(python_files)} Python files")
                    for i, file_path in enumerate(python_files, 1):
                        print(f"\n[{i}/{len(python_files)}] Profiling: {file_path}")
                        profiler.profile_tkinter_file(file_path, args.name)
                else:
                    print("Directory profiling requires --recursive flag")
                    return
            else:
                # Profile single file
                profiler.profile_tkinter_file(args.target, args.name)
        
        elif args.command == 'list':
            systems = profiler.list_systems()
            if not systems:
                print("No systems profiled yet.")
                return
            
            print(f"\nProfiled Systems ({len(systems)}):")
            print("=" * 80)
            for system in systems:
                stats = profiler.get_system_stats(system['id'])
                print(f"ID: {system['id']}")
                print(f"Name: {system['name']}")
                print(f"Description: {system['description']}")
                print(f"Created: {system['created_at']}")
                print(f"Assumptions: {stats['assumptions_total']} ({stats['assumptions_confirmed']} confirmed)")
                print(f"Entities: {stats['entities']}")
                print(f"Confidence: {stats['confidence_ratio']:.1%}")
                print("-" * 80)
        
        elif args.command == 'stats':
            stats = profiler.get_system_stats(args.system_id)
            print(f"\nStatistics for system {args.system_id}:")
            print(f"  Total assumptions: {stats['assumptions_total']}")
            print(f"  Confirmed assumptions: {stats['assumptions_confirmed']}")
            print(f"  Entities identified: {stats['entities']}")
            print(f"  Confidence ratio: {stats['confidence_ratio']:.1%}")
        
        elif args.command == 'export':
            manifest = profiler.load_manifest(args.system_id)
            output_data = asdict(manifest)
            
            if args.format == 'json':
                output = json.dumps(output_data, indent=2)
                ext = '.json'
            elif args.format == 'yaml':
                output = yaml.dump(output_data, default_flow_style=False)
                ext = '.yaml'
            else:  # csv (simplified)
                # Simplified CSV export - in reality would need proper flattening
                import csv
                from io import StringIO
                
                output_io = StringIO()
                writer = csv.writer(output_io)
                
                # Write headers
                writer.writerow(['type', 'id', 'name', 'confidence', 'confirmed'])
                
                # Write assumptions
                for assumption in manifest.assumptions.values():
                    writer.writerow([
                        'assumption',
                        assumption.id,
                        assumption.description[:50],
                        assumption.confidence.value,
                        assumption.user_confirmed
                    ])
                
                # Write entities
                for entity in manifest.entities.values():
                    writer.writerow([
                        'entity',
                        entity.id,
                        entity.name,
                        entity.entity_type,
                        len(entity.assumptions)
                    ])
                
                output = output_io.getvalue()
                ext = '.csv'
            
            # Write output
            if args.output:
                output_file = args.output
            else:
                output_file = f"tkinter_profile_{args.system_id}{ext}"
            
            with open(output_file, 'w') as f:
                f.write(output)
            
            print(f"Exported to: {output_file}")
        
        elif args.command == 'compare':
            manifest1 = profiler.load_manifest(args.system_id_1)
            manifest2 = profiler.load_manifest(args.system_id_2)
            
            print(f"\nComparing {manifest1.name} vs {manifest2.name}:")
            print("=" * 80)
            print(f"Assumptions: {len(manifest1.assumptions)} vs {len(manifest2.assumptions)}")
            print(f"Entities: {len(manifest1.entities)} vs {len(manifest2.entities)}")
            
            # Find common widget types
            types1 = set(e.entity_type for e in manifest1.entities.values())
            types2 = set(e.entity_type for e in manifest2.entities.values())
            
            common_types = types1.intersection(types2)
            unique_to_1 = types1 - types2
            unique_to_2 = types2 - types1
            
            print(f"\nCommon widget types: {', '.join(sorted(common_types))}")
            print(f"Unique to {manifest1.name}: {', '.join(sorted(unique_to_1))}")
            print(f"Unique to {manifest2.name}: {', '.join(sorted(unique_to_2))}")
        
        elif args.command == 'setup-uca':
            setup_uca_integration(force=args.force)
        
        elif args.command == 'generate-scripts':
            generate_context_menu_scripts(args.output_dir)
        
        elif args.command == 'review':
            review_assumptions(profiler, args.system_id, args.assumption_id)
        
        elif args.command == 'interactive':
            run_interactive_mode(profiler)
        
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

# ==================== UCA (Thunar Context Menu) Integration ====================

def setup_uca_integration(force=False):
    """Setup Thunar UCA (User Custom Actions) integration."""
    uca_dir = os.path.expanduser("~/.config/Thunar/uca.xml")
    uca_dir_path = os.path.dirname(uca_dir)
    
    if not os.path.exists(uca_dir_path):
        os.makedirs(uca_dir_path, exist_ok=True)
    
    # Check if UCA file exists
    if os.path.exists(uca_dir) and not force:
        print("UCA file already exists. Use --force to overwrite.")
        return
    
    uca_entries = """<?xml version="1.0" encoding="UTF-8"?>
<actions>
<action>
    <icon>utilities-terminal</icon>
    <name>Profile Tkinter File</name>
    <unique-id>1678290234567890</unique-id>
    <command>tkinter-profiler profile %f</command>
    <description>Profile Tkinter application with learning</description>
    <patterns>*.py</patterns>
    <directories/>
</action>
<action>
    <icon>view-list-details</icon>
    <name>List Tkinter Profiles</name>
    <unique-id>1678290234567891</unique-id>
    <command>tkinter-profiler list</command>
    <description>List all profiled Tkinter systems</description>
    <directories/>
</action>
<action>
    <icon>document-export</icon>
    <name>Export Tkinter Profile</name>
    <unique-id>1678290234567892</unique-id>
    <command>tkinter-profiler export $(basename %f .json) --output %f_profile.json</command>
    <description>Export profile data</description>
    <patterns>manifest.json</patterns>
    <directories/>
</action>
<action>
    <icon>edit-find</icon>
    <name>Quick Tkinter Scan</name>
    <unique-id>1678290234567893</unique-id>
    <command>tkinter-profiler profile --non-interactive %f</command>
    <description>Quick scan without interaction</description>
    <patterns>*.py</patterns>
    <directories/>
</action>
</actions>"""
    
    with open(uca_dir, 'w') as f:
        f.write(uca_entries)
    
    print("✓ Thunar UCA integration setup complete!")
    print("  Restart Thunar to see the new context menu items.")
    print("\nAvailable actions:")
    print("  • Profile Tkinter File - Right-click on .py files")
    print("  • List Tkinter Profiles - Available anywhere")
    print("  • Export Tkinter Profile - Right-click on manifest.json")
    print("  • Quick Tkinter Scan - Fast profiling without interaction")

def generate_context_menu_scripts(output_dir):
    """Generate shell scripts for context menu integration."""
    output_dir = os.path.expanduser(output_dir)
    os.makedirs(output_dir, exist_ok=True)
    
    scripts = {
        "profile_tkinter.sh": """#!/bin/bash
# Profile Tkinter file
FILE="$1"
tkinter-profiler profile "$FILE"
read -p "Press enter to continue..."""",
        
        "quick_profile.sh": """#!/bin/bash
# Quick profile (non-interactive)
FILE="$1"
tkinter-profiler profile --non-interactive "$FILE" """,
        
        "batch_profile.sh": """#!/bin/bash
# Batch profile directory
DIR="$1"
tkinter-profiler profile --recursive "$DIR" """,
        
        "open_profile.sh": """#!/bin/bash
# Open profile in default viewer
FILE="$1"
if [[ "$FILE" == *.json ]]; then
    python3 -m json.tool "$FILE" | less
else
    echo "Not a JSON file"
fi""",
        
        "compare_profiles.sh": """#!/bin/bash
# Compare two profiles
PROFILE1="$1"
PROFILE2="$2"
tkinter-profiler compare "$PROFILE1" "$PROFILE2"
read -p "Press enter to continue..." """
    }
    
    for script_name, script_content in scripts.items():
        script_path = os.path.join(output_dir, script_name)
        with open(script_path, 'w') as f:
            f.write(script_content)
        
        # Make executable
        os.chmod(script_path, 0o755)
    
    print(f"✓ Generated {len(scripts)} shell scripts in {output_dir}")
    print("\nTo use with other file managers:")
    print(f"  - Point context menu actions to scripts in {output_dir}")
    print("  - Scripts accept file paths as arguments")

# ==================== Review Mode ====================

def review_assumptions(profiler, system_id, specific_assumption_id=None):
    """Review and edit assumptions for a system."""
    manifest = profiler.load_manifest(system_id)
    
    print(f"\nReviewing assumptions for: {manifest.name}")
    print("=" * 80)
    
    assumptions = list(manifest.assumptions.values())
    
    if specific_assumption_id:
        assumptions = [a for a in assumptions if a.id == specific_assumption_id]
        if not assumptions:
            print(f"Assumption {specific_assumption_id} not found.")
            return
    
    for i, assumption in enumerate(assumptions, 1):
        print(f"\n[{i}/{len(assumptions)}] Assumption ID: {assumption.id}")
        print(f"Description: {assumption.description}")
        print(f"Category: {assumption.category}")
        print(f"Confidence: {assumption.confidence.value}")
        print(f"Confirmed: {'Yes' if assumption.user_confirmed else 'No'}")
        if assumption.user_corrected:
            print(f"Correction: {assumption.user_corrected}")
        
        action = input("\n(a)ccept / (r)eject / (e)dit / (s)kip / (q)uit: ").lower().strip()
        
        if action == 'a':
            assumption.user_confirmed = True
            print("✓ Accepted")
        elif action == 'r':
            assumption.user_confirmed = False
            print("✗ Rejected")
        elif action == 'e':
            new_desc = input("Enter new description: ").strip()
            if new_desc:
                assumption.description = new_desc
                print("✓ Updated")
        elif action == 'q':
            print("Quitting review...")
            break
    
    # Save changes
    profiler.save_manifest(manifest)
    print(f"\n✓ Review complete. Changes saved.")

# ==================== Interactive Mode ====================

def run_interactive_mode(profiler):
    """Run interactive mode for exploring and managing profiles."""
    print("\n" + "=" * 60)
    print("Tkinter Profiler - Interactive Mode")
    print("=" * 60)
    
    while True:
        print("\nAvailable commands:")
        print("  1. List systems")
        print("  2. Profile new file")
        print("  3. Review assumptions")
        print("  4. View system stats")
        print("  5. Compare systems")
        print("  6. Export data")
        print("  7. Setup UCA integration")
        print("  8. Generate scripts")
        print("  9. Exit")
        
        choice = input("\nEnter choice (1-9): ").strip()
        
        if choice == '1':
            systems = profiler.list_systems()
            for sys in systems:
                print(f"  {sys['id']}: {sys['name']} - {sys['description']}")
        
        elif choice == '2':
            file_path = input("Enter file path to profile: ").strip()
            if os.path.exists(file_path):
                profiler.profile_tkinter_file(file_path)
            else:
                print("File not found.")
        
        elif choice == '3':
            system_id = input("Enter system ID to review: ").strip()
            try:
                review_assumptions(profiler, system_id)
            except Exception as e:
                print(f"Error: {e}")
        
        elif choice == '4':
            system_id = input("Enter system ID: ").strip()
            stats = profiler.get_system_stats(system_id)
            for key, value in stats.items():
                print(f"  {key}: {value}")
        
        elif choice == '5':
            id1 = input("Enter first system ID: ").strip()
            id2 = input("Enter second system ID: ").strip()
            try:
                manifest1 = profiler.load_manifest(id1)
                manifest2 = profiler.load_manifest(id2)
                print(f"\nComparing {manifest1.name} vs {manifest2.name}")
                print(f"Assumptions: {len(manifest1.assumptions)} vs {len(manifest2.assumptions)}")
                print(f"Entities: {len(manifest1.entities)} vs {len(manifest2.entities)}")
            except Exception as e:
                print(f"Error: {e}")
        
        elif choice == '6':
            system_id = input("Enter system ID to export: ").strip()
            format_choice = input("Format (json/yaml/csv): ").strip().lower()
            if format_choice in ['json', 'yaml', 'csv']:
                output_file = input("Output file (optional): ").strip()
                # Simplified - in reality would call export function
                print(f"Would export {system_id} as {format_choice} to {output_file or 'default'}")
            else:
                print("Invalid format")
        
        elif choice == '7':
            setup_uca_integration()
        
        elif choice == '8':
            output_dir = input("Output directory (default: ~/.local/share/tkinter-profiler/scripts): ").strip()
            if not output_dir:
                output_dir = "~/.local/share/tkinter-profiler/scripts"
            generate_context_menu_scripts(output_dir)
        
        elif choice == '9':
            print("Exiting interactive mode.")
            break
        
        else:
            print("Invalid choice.")

# ==================== Setup Script ====================

def create_setup_script():
    """Create setup.sh script for easy installation."""
    setup_content = """#!/bin/bash
# Tkinter Profiler Setup Script

echo "Setting up Tkinter Profiler..."

# Install Python dependencies
pip3 install pyyaml

# Make the main script executable
chmod +x "$(dirname "$0")/tkinter_profiler.py"

# Create symlink for easy access
if [ ! -f "/usr/local/bin/tkinter-profiler" ]; then
    sudo ln -sf "$(realpath "$(dirname "$0")/tkinter_profiler.py")" /usr/local/bin/tkinter-profiler
    echo "✓ Created symlink: /usr/local/bin/tkinter-profiler"
fi

# Generate shell scripts
mkdir -p ~/.local/share/tkinter-profiler/scripts
"$(dirname "$0")/tkinter_profiler.py" generate-scripts

echo ""
echo "Setup complete!"
echo ""
echo "Usage examples:"
echo "  tkinter-profiler profile my_app.py"
echo "  tkinter-profiler list"
echo "  tkinter-profiler setup-uca"
echo ""
echo "For Thunar integration, run:"
echo "  tkinter-profiler setup-uca"
echo "Then restart Thunar."
"""

    with open("setup_tkinter_profiler.sh", "w") as f:
        f.write(setup_content)
    
    os.chmod("setup_tkinter_profiler.sh", 0o755)
    print("✓ Created setup script: setup_tkinter_profiler.sh")

# ==================== Main Guard ====================

if __name__ == "__main__":
    # Create setup script if requested
    if len(sys.argv) > 1 and sys.argv[1] == "--create-setup":
        create_setup_script()
        print("\nTo complete setup:")
        print("  chmod +x setup_tkinter_profiler.sh")
        print("  ./setup_tkinter_profiler.sh")
    else:
        main()