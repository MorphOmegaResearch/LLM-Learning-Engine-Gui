#!/usr/bin/env python3
#[Version:#<#v1.1.0-unification_taxonomy_integration#>#]
"""
FOREKIT - Forensic OS Toolkit v1.0
Universal system analyzer, classifier, and forensic query engine
Complete single-script solution with session management and hierarchical taxonomy
"""

import os
import sys
import json
import re
import subprocess
import platform
import shutil
import hashlib
import argparse
import sqlite3
import csv
import time
import uuid
import warnings
import stat
import pwd
import grp
import glob
from datetime import datetime, timedelta
from pathlib import Path, PurePath, PurePosixPath, PureWindowsPath
from dataclasses import dataclass, field, asdict, is_dataclass
from typing import Dict, List, Optional, Any, Tuple, Set, Union, Callable
from enum import Enum, auto
from collections import defaultdict, OrderedDict, deque, Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
import textwrap
import mimetypes
import pickle
import itertools
import threading
import queue
try:
    from onboarder import OnboardingManager, ToolMetadata, ArgParseArgument, ArgParseCommand, ToolCategory
except ImportError as _onboarder_err:
    import sys as _sys
    print(f"[Os_Toolkit] WARNING: onboarder module not available ({_onboarder_err}). Some features disabled.", file=_sys.stderr)
    OnboardingManager = None
    ToolMetadata = ArgParseArgument = ArgParseCommand = ToolCategory = None

# ============================================================================
# SHARED LOGGING - BABEL UNIFICATION
# ============================================================================

def log_event(event_name, message, level="INFO", context=None):
    """Log an event to the unified Babel traceback system"""
    try:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        module_name = "os_toolkit"
        
        # Construct event tag
        event_tag = f"#[Event:{event_name}]"
        
        # Construct full log message
        full_message = f"[{timestamp}] [{module_name}] [{level}] {event_tag} {message}"
        if context:
            full_message += f" | Context: {context}"
        
        # Write to console (prefixed for clarity)
        print(f"BABEL_LOG: {full_message}")
        
        # Write to shared log
        babel_root = Path(__file__).resolve().parent
        log_dir = babel_root / "babel_data" / "logs"
        if log_dir.exists():
            shared_log = log_dir / "unified_traceback.log"
            with open(shared_log, 'a') as f:
                f.write(full_message + "\n")
    except Exception:
        pass

warnings.filterwarnings('ignore')

# ============================================================================
# CONSTANTS & GLOBAL CONFIG
# ============================================================================

VERSION = "1.0.0"
TOOLKIT_NAME = "FOREKIT"
AUTHOR = "Forensic OS Toolkit Team"

# Default paths - prefer babel_data/profile if it exists, fall back to centralized forekit_data
_babel_profile = Path.cwd() / "babel_data" / "profile"

# Fix: Anchor DEFAULT_BASE_DIR to the project root (Trainer/forekit_data) relative to this script
# Script location: Trainer/Data/tabs/action_panel_tab/Os_Toolkit.py
# Root location:   Trainer/
try:
    _script_root = Path(__file__).resolve().parents[3]
    _central_forekit = _script_root / "forekit_data"
except Exception:
    _central_forekit = Path.cwd() / "forekit_data"

if _babel_profile.exists():
    DEFAULT_BASE_DIR = _babel_profile
elif _central_forekit.parent.exists(): # Ensure Trainer/ exists
    DEFAULT_BASE_DIR = _central_forekit
else:
    DEFAULT_BASE_DIR = Path.cwd() / "forekit_data"

SESSION_DIR = DEFAULT_BASE_DIR / "sessions"
MANIFEST_DIR = DEFAULT_BASE_DIR / "manifests"
JOURNAL_DIR = DEFAULT_BASE_DIR / "journals"
SCHEMA_DIR = DEFAULT_BASE_DIR / "schemas"
LOG_DIR = DEFAULT_BASE_DIR / "logs"
EXPORT_DIR = DEFAULT_BASE_DIR / "exports"

# File size limits (for performance)
MAX_FILE_SIZE_ANALYSIS = 50 * 1024 * 1024  # 50MB
MAX_STRING_SCAN_SIZE = 10 * 1024 * 1024    # 10MB

# ============================================================================
# SYSTEM DNA (Pre-installed "Why" Associations)
# ============================================================================
# Core OS components have inherent purpose. We map these to avoid false
# positives in workflow audits and provide better automated 6W1H.
SYSTEM_DNA = {
    '/etc/passwd': 'User account management',
    '/etc/shadow': 'Secure password storage',
    '/etc/group': 'System group definitions',
    '/etc/hosts': 'Static hostname resolution',
    '/etc/resolv.conf': 'DNS resolver configuration',
    '/var/log/auth.log': 'Security and authentication history',
    '/var/log/syslog': 'General system event logging',
    '/proc/': 'Kernel process information interface',
    '/sys/': 'Kernel hardware configuration interface',
    'systemd': 'System and service manager',
    'journald': 'System logging service',
    'dbus': 'System message bus',
    'network-dispatcher': 'Network state change handler',
    'timesyncd': 'Network time synchronization',
    'at-spi': 'Assistive technology interface',
    'irqbalance': 'CPU interrupt distribution'
    # EXTERNAL AGENTS REMOVED (Security Fix 2026-02-07)
    # External agents (Claude, Gemini, etc.) are NOT native OS components.
    # After security breach, these MUST be tracked in trust_registry.json
    # with first-seen verification, NOT assumed as "Core System".
    # When offline, they don't exist; when online, they require conditional trust.
}

# ============================================================================
# ENUMERATIONS
# ============================================================================

class OSType(Enum):
    LINUX = "linux"
    WINDOWS = "windows"
    MACOS = "darwin"
    BSD = "bsd"
    SOLARIS = "solaris"
    UNKNOWN = "unknown"

class HardwareTaxonomy(Enum):
    """Taxonomic classification for hardware"""
    PROCESSOR = "processor"
    MEMORY = "memory"
    STORAGE = "storage"
    NETWORK = "network"
    GRAPHICS = "graphics"
    INPUT = "input"
    OUTPUT = "output"
    POWER = "power"
    SENSOR = "sensor"
    BUS = "bus"
    CONTROLLER = "controller"
    FIRMWARE = "firmware"
    EXPANSION = "expansion"
    VIRTUAL = "virtual"
    UNKNOWN = "unknown"

class SoftwareTaxonomy(Enum):
    """Taxonomic classification for software"""
    OS_KERNEL = "os_kernel"
    OS_SYSTEM = "os_system"
    OS_UTILITY = "os_utility"
    APPLICATION = "application"
    SERVICE = "service"
    DRIVER = "driver"
    LIBRARY = "library"
    FRAMEWORK = "framework"
    DEVELOPMENT = "development"
    SECURITY = "security"
    NETWORK = "network"
    DATABASE = "database"
    CONTAINER = "container"
    VIRTUALIZATION = "virtualization"
    MONITORING = "monitoring"
    UNKNOWN = "unknown"

class SecurityContext(Enum):
    """Security classification"""
    SYSTEM_TRUSTED = "system_trusted"
    VENDOR_TRUSTED = "vendor_trusted"
    USER_TRUSTED = "user_trusted"
    THIRD_PARTY = "third_party"
    SUSPICIOUS = "suspicious"
    MALICIOUS = "malicious"
    UNTRUSTED = "untrusted"
    UNKNOWN = "unknown"

class ArtifactType(Enum):
    """Types of forensic artifacts"""
    FILE = "file"
    DIRECTORY = "directory"
    PROCESS = "process"
    NETWORK_CONN = "network_connection"
    NETWORK_SOCKET = "network_socket"
    USER = "user"
    GROUP = "group"
    SERVICE = "service"
    SCHEDULED_TASK = "scheduled_task"
    REGISTRY_KEY = "registry_key"
    ENVIRONMENT = "environment"
    CONFIGURATION = "configuration"
    LOG = "log"
    DATABASE = "database"
    CACHE = "cache"
    TEMPORARY = "temporary"
    UNKNOWN = "unknown"

class VerbDomain(Enum):
    """Command/verb domains"""
    SYSTEM = "system"
    FILESYSTEM = "filesystem"
    PROCESS = "process"
    NETWORK = "network"
    HARDWARE = "hardware"
    USER = "user"
    PACKAGE = "package"
    SERVICE = "service"
    SECURITY = "security"
    MONITORING = "monitoring"
    DEVELOPMENT = "development"
    UNKNOWN = "unknown"

# ============================================================================
# CORE DATA STRUCTURES
# ============================================================================

@dataclass
class SixW1H:
    """Unified 6W1H classification structure"""
    what: str = ""
    why: str = ""
    who: str = ""
    where: str = ""
    when: str = ""
    which: str = ""
    how: str = ""
    
    def to_dict(self):
        return asdict(self)
    
    def to_tuple(self):
        return (self.what, self.why, self.who, self.where, self.when, self.which, self.how)
    
    def to_markdown(self):
        return f"""## 6W1H Classification
- **What**: {self.what}
- **Why**: {self.why}
- **Who**: {self.who}
- **Where**: {self.where}
- **When**: {self.when}
- **Which**: {self.which}
- **How**: {self.how}"""

@dataclass
class TaxonomicNode:
    """Node in the taxonomic tree"""
    node_id: str
    name: str
    taxonomy_type: Union[HardwareTaxonomy, SoftwareTaxonomy]
    sixw1h: SixW1H
    parent_id: Optional[str] = None
    children_ids: List[str] = field(default_factory=list)
    attributes: Dict[str, Any] = field(default_factory=dict)
    relationships: List[Tuple[str, str, str]] = field(default_factory=list)  # (target_id, relation_type, details)
    
    def add_child(self, child_id: str):
        if child_id not in self.children_ids:
            self.children_ids.append(child_id)
    
    def add_relationship(self, target_id: str, relation_type: str, details: str = ""):
        self.relationships.append((target_id, relation_type, details))
    
    def to_dict(self):
        return {
            'node_id': self.node_id,
            'name': self.name,
            'taxonomy_type': self.taxonomy_type.value if hasattr(self.taxonomy_type, 'value') else self.taxonomy_type,
            'sixw1h': self.sixw1h.to_dict(),
            'parent_id': self.parent_id,
            'children_ids': self.children_ids,
            'attributes': self.attributes,
            'relationships': self.relationships
        }

@dataclass
class ForensicArtifact:
    """Forensic artifact with chain of custody"""
    artifact_id: str
    artifact_type: ArtifactType
    sixw1h: SixW1H
    
    # Temporal metadata
    timestamp_created: str
    timestamp_modified: str
    timestamp_accessed: str
    
    # Identity metadata
    hash_md5: str = ""
    hash_sha1: str = ""
    hash_sha256: str = ""
    size_bytes: int = 0
    
    # Security context
    security_context: SecurityContext = SecurityContext.UNKNOWN
    owner_uid: int = 0
    owner_gid: int = 0
    permissions: str = ""
    
    # Taxonomic links
    taxonomic_node_id: Optional[str] = None
    
    # Raw data and properties
    properties: Dict[str, Any] = field(default_factory=dict)
    raw_content: Optional[str] = None
    binary_preview: Optional[bytes] = None
    
    # Chain of custody
    custody_chain: List[Dict[str, str]] = field(default_factory=list)
    
    def add_custody_event(self, event_type: str, timestamp: str, user: str, details: str):
        self.custody_chain.append({
            'event_type': event_type,
            'timestamp': timestamp,
            'user': user,
            'details': details
        })
    
    def to_dict(self):
        return {
            'artifact_id': self.artifact_id,
            'artifact_type': self.artifact_type.value,
            'sixw1h': self.sixw1h.to_dict(),
            'timestamps': {
                'created': self.timestamp_created,
                'modified': self.timestamp_modified,
                'accessed': self.timestamp_accessed
            },
            'hashes': {
                'md5': self.hash_md5,
                'sha1': self.hash_sha1,
                'sha256': self.hash_sha256
            },
            'security': {
                'context': self.security_context.value,
                'owner_uid': self.owner_uid,
                'owner_gid': self.owner_gid,
                'permissions': self.permissions
            },
            'taxonomic_link': self.taxonomic_node_id,
            'properties': self.properties,
            'custody_chain': self.custody_chain,
            'size_bytes': self.size_bytes
        }

@dataclass
class SystemVerb:
    """System command/verb with cross-OS mapping"""
    verb_id: str
    name: str
    domain: VerbDomain
    os_type: OSType
    sixw1h: SixW1H
    
    # Syntax and usage
    native_syntax: str
    arguments: List[str]
    options: Dict[str, str]
    
    # Cross-OS equivalents
    equivalents: Dict[OSType, str] = field(default_factory=dict)
    
    # Dependencies and requirements
    dependencies: List[str] = field(default_factory=list)
    required_permissions: List[str] = field(default_factory=list)
    
    # Examples
    examples: List[str] = field(default_factory=list)
    
    def to_dict(self):
        return {
            'verb_id': self.verb_id,
            'name': self.name,
            'domain': self.domain.value,
            'os_type': self.os_type.value,
            'sixw1h': self.sixw1h.to_dict(),
            'native_syntax': self.native_syntax,
            'arguments': self.arguments,
            'options': self.options,
            'equivalents': {k.value: v for k, v in self.equivalents.items()},
            'dependencies': self.dependencies,
            'required_permissions': self.required_permissions,
            'examples': self.examples
        }

@dataclass
class Session:
    """Analysis session container"""
    session_id: str
    session_name: str
    created_at: str
    updated_at: str
    
    # Session metadata
    os_type: OSType
    hostname: str
    architecture: str
    
    # Session data
    taxonomic_tree: Dict[str, TaxonomicNode] = field(default_factory=dict)
    artifacts: Dict[str, ForensicArtifact] = field(default_factory=dict)
    verbs: Dict[str, SystemVerb] = field(default_factory=dict)
    
    # Journal entries
    journal_entries: List[Dict[str, Any]] = field(default_factory=list)
    
    # Query history
    query_history: List[Dict[str, Any]] = field(default_factory=list)
    
    def add_journal_entry(self, entry_type: str, content: str, tags: List[str] = None):
        entry = {
            'timestamp': datetime.now().isoformat(),
            'entry_type': entry_type,
            'content': content,
            'tags': tags or []
        }
        self.journal_entries.append(entry)
        self.updated_at = entry['timestamp']
    
    def add_query(self, query: str, result_count: int, duration_ms: int):
        self.query_history.append({
            'timestamp': datetime.now().isoformat(),
            'query': query,
            'result_count': result_count,
            'duration_ms': duration_ms
        })
    
    def save(self, base_dir: Path):
        """Save session to disk"""
        session_dir = base_dir / self.session_id
        session_dir.mkdir(parents=True, exist_ok=True)
        
        # Save session metadata
        metadata = {
            'session_id': self.session_id,
            'session_name': self.session_name,
            'created_at': self.created_at,
            'updated_at': self.updated_at,
            'os_type': self.os_type.value,
            'hostname': self.hostname,
            'architecture': self.architecture,
            'statistics': {
                'taxonomic_nodes': len(self.taxonomic_tree),
                'artifacts': len(self.artifacts),
                'verbs': len(self.verbs),
                'journal_entries': len(self.journal_entries),
                'queries': len(self.query_history)
            }
        }
        
        with open(session_dir / 'metadata.json', 'w') as f:
            json.dump(metadata, f, indent=2)
        
        # Save taxonomic tree
        tree_data = {k: v.to_dict() for k, v in self.taxonomic_tree.items()}
        with open(session_dir / 'taxonomic_tree.json', 'w') as f:
            json.dump(tree_data, f, indent=2)
        
        # Save artifacts (in chunks for large sessions)
        artifacts_data = {k: v.to_dict() for k, v in self.artifacts.items()}
        with open(session_dir / 'artifacts.json', 'w') as f:
            json.dump(artifacts_data, f, indent=2)
        
        # Save verbs
        verbs_data = {k: v.to_dict() for k, v in self.verbs.items()}
        with open(session_dir / 'verbs.json', 'w') as f:
            json.dump(verbs_data, f, indent=2)
        
        # Save journal
        with open(session_dir / 'journal.jsonl', 'w') as f:
            for entry in self.journal_entries:
                f.write(json.dumps(entry) + '\n')
        
        # Save query history
        with open(session_dir / 'queries.jsonl', 'w') as f:
            for query in self.query_history:
                f.write(json.dumps(query) + '\n')
        
        return session_dir

# ============================================================================
# SCHEMA DEFINITION FOR TREE VIEW MANIFEST
# ============================================================================

SCHEMA_DEFINITION = {
    "version": "1.0",
    "schema_type": "hierarchical_taxonomic_manifest",
    "root_nodes": [
        {
            "id": "root_system",
            "name": "System",
            "description": "Root of the system taxonomy",
            "children": ["hardware", "software", "network", "security", "users"]
        },
        {
            "id": "hardware",
            "name": "Hardware",
            "description": "Physical and virtual hardware components",
            "children": ["processors", "memory", "storage", "network_hw", "graphics", "input_output", "firmware"]
        },
        {
            "id": "software",
            "name": "Software",
            "description": "Operating system, applications, and services",
            "children": ["os_kernel", "os_system", "applications", "services", "drivers", "libraries", "containers"]
        },
        {
            "id": "network",
            "name": "Network",
            "description": "Network interfaces, connections, and configurations",
            "children": ["interfaces", "connections", "routing", "firewall", "dns", "services"]
        },
        {
            "id": "security",
            "name": "Security",
            "description": "Security configurations, policies, and events",
            "children": ["users", "groups", "permissions", "policies", "logs", "alerts"]
        },
        {
            "id": "users",
            "name": "Users",
            "description": "User accounts and sessions",
            "children": ["local_users", "domain_users", "sessions", "privileges"]
        }
    ],
    "classification_fields": [
        "sixw1h_what",
        "sixw1h_why",
        "sixw1h_who",
        "sixw1h_where",
        "sixw1h_when",
        "sixw1h_which",
        "sixw1h_how",
        "taxonomic_type",
        "security_context",
        "artifact_type",
        "timestamps",
        "hashes",
        "size_bytes",
        "owner",
        "permissions",
        "dependencies",
        "relationships"
    ],
    "relationship_types": [
        "parent_child",
        "dependency",
        "communication",
        "ownership",
        "access",
        "modification",
        "execution",
        "network_connection",
        "file_reference",
        "configuration"
    ]
}

@dataclass
class ConformityAction:
    """Action suggested by the system to maintain conformity/health"""
    action_id: str
    name: str
    description: str
    impact: str
    command_func: Callable
    
    def to_dict(self):
        return {
            'action_id': self.action_id,
            'name': self.name,
            'description': self.description,
            'impact': self.impact
        }

# ============================================================================
# PROJECT COORDINATION MANAGERS
# ============================================================================

class TodoManager:
    """Manages project tasks (todos.json)"""
    def __init__(self, base_dir: Path):
        # Intelligent search for plans dir
        self.plans_dir = None

        # Candidate 1: Data/plans (primary — phase-dict todos.json lives here)
        c0 = Path(__file__).parent.parent.parent / "plans"
        # Candidate 2: standard babel structure
        c1 = base_dir.parent.parent / "plans"
        # Candidate 3: current working directory
        c2 = Path.cwd() / "plans"
        # Candidate 4: parent of current directory
        c3 = Path.cwd().parent / "plans"

        for c in [c0, c1, c2, c3]:
            if c.exists() and (c / "todos.json").exists():
                self.plans_dir = c
                break

        if not self.plans_dir:
            self.plans_dir = c0 if c0.exists() else c2  # Default to Data/plans
            
        self.todo_file = self.plans_dir / "todos.json"

    def load_todos(self) -> List[Dict[str, Any]]:
        if not self.todo_file.exists():
            return []
        try:
            with open(self.todo_file, 'r') as f:
                return json.load(f)
        except:
            return []

    def load_todos_flat(self) -> List[Dict[str, Any]]:
        """Load todos and flatten to a list of task dicts regardless of storage format.
        Handles both list-style and dict-style (phase-grouped) todos.json.
        Preserves originating phase key as '_phase' on each task."""
        raw = self.load_todos()
        if isinstance(raw, list):
            return [t for t in raw if isinstance(t, dict)]
        elif isinstance(raw, dict):
            flat = []
            for phase, tblock in raw.items():
                if isinstance(tblock, dict):
                    for tid, t in tblock.items():
                        if isinstance(t, dict):
                            if 'id' not in t:
                                t['id'] = tid
                            t['_phase'] = phase
                            flat.append(t)
            return flat
        return []

    def save_todos(self, todos):
        self.plans_dir.mkdir(parents=True, exist_ok=True)
        with open(self.todo_file, 'w') as f:
            json.dump(todos, f, indent=2)

    def add_todo(self, title: str, description: str = ""):
        todos = self.load_todos()
        new_todo = {
            "id": uuid.uuid4().hex[:8],
            "title": title,
            "description": description,
            "status": "open",
            "directory": ".",
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        }
        if isinstance(todos, list):
            todos.append(new_todo)
        elif isinstance(todos, dict):
            # Add to a general phase bucket
            phase_key = f"phase_cli_{datetime.now().strftime('%y%m')}"
            todos.setdefault(phase_key, {})[new_todo["id"]] = new_todo
        self.save_todos(todos)
        print(f"[+] Added Todo: {title} (ID: {new_todo['id']})")

    def list_todos(self, status_filter: str = "all"):
        todos = self.load_todos_flat()
        print(f"\n{'='*60}")
        print(f"PROJECT TASKS ({status_filter.upper()})")
        print(f"{'='*60}")

        count = 0
        for t in todos:
            if status_filter != "all" and t.get('status') != status_filter:
                continue

            mark = "[x]" if t.get('status') == "done" else "[ ]"
            print(f"{mark} {t.get('title', '?')} (ID: {t.get('id', '?')})")
            if t.get('description'):
                print(f"    {t['description']}")
            count += 1

        print(f"\nTotal: {count} tasks")

    def update_todo(self, todo_id: str, status: str):
        todos = self.load_todos()
        found = False
        if isinstance(todos, list):
            for t in todos:
                if isinstance(t, dict) and t.get('id') == todo_id:
                    t['status'] = status
                    t['updated_at'] = datetime.now().isoformat()
                    found = True
                    break
        elif isinstance(todos, dict):
            for phase, tblock in todos.items():
                if isinstance(tblock, dict) and todo_id in tblock:
                    tblock[todo_id]['status'] = status
                    tblock[todo_id]['updated_at'] = datetime.now().isoformat()
                    found = True
                    break

        if found:
            self.save_todos(todos)
            print(f"[+] Updated Todo {todo_id} to '{status}'")
        else:
            print(f"[-] Todo {todo_id} not found")

    def complete_todo_interactive(self, todo_id: str, use_zenity: bool = False) -> str:
        """Interactive task completion with Zenity test verification.
        #[Mark:BIG-BANG-2A]
        """
        todos = self.load_todos()
        todo = None
        # Handle both list-style and dict-style todos.json
        if isinstance(todos, list):
            todo = next((t for t in todos if t.get('id') == todo_id), None)
        elif isinstance(todos, dict):
            for phase, tasks in todos.items():
                if isinstance(tasks, dict) and todo_id in tasks:
                    todo = tasks[todo_id]
                    break

        if not todo:
            return f"Todo {todo_id} not found"

        expectations = todo.get("test_expectations", [])
        if not expectations:
            # No expectations: simple confirmation
            if use_zenity:
                if zenity_question(f"Mark '{todo.get('title',todo_id)}' as complete?\nNo test expectations defined."):
                    self._set_todo_status(todos, todo_id, "complete")
                    return "Marked complete"
                return "Cancelled"
            else:
                self._set_todo_status(todos, todo_id, "complete")
                return "Marked complete (no test expectations)"

        if use_zenity:
            items = [{"id": f"exp_{i}", "label": exp, "checked": False}
                     for i, exp in enumerate(expectations)]
            selected = zenity_checklist(items,
                title=f"Verify: {todo.get('title', todo_id)}",
                text="Check all passing test expectations:")

            if not selected:
                return "Cancelled — no expectations confirmed"

            passed = len(selected)
            total = len(expectations)
            if passed < total:
                if not zenity_question(
                    f"Only {passed}/{total} expectations passed.\nMark as complete anyway?"):
                    self._set_todo_status(todos, todo_id, "test:in_progress")
                    return f"Status: test:in_progress ({passed}/{total})"
        else:
            # Non-zenity: auto-pass
            selected = [f"exp_{i}" for i in range(len(expectations))]
            passed = len(expectations)
            total = len(expectations)

        # Write test results back
        test_results = [
            {"expectation": exp, "passed": f"exp_{i}" in selected,
             "timestamp": datetime.now().isoformat()}
            for i, exp in enumerate(expectations)
        ]

        # Update the todo
        if isinstance(todos, list):
            for t in todos:
                if t.get('id') == todo_id:
                    t['status'] = 'complete'
                    t['test_status'] = 'test:passed' if passed == total else 'test:partial'
                    t['test_results'] = test_results
                    t['updated_at'] = datetime.now().isoformat()
                    break
        elif isinstance(todos, dict):
            for phase, tasks in todos.items():
                if isinstance(tasks, dict) and todo_id in tasks:
                    tasks[todo_id]['status'] = 'complete'
                    tasks[todo_id]['test_status'] = 'test:passed' if passed == total else 'test:partial'
                    tasks[todo_id]['test_results'] = test_results
                    tasks[todo_id]['updated_at'] = datetime.now().isoformat()
                    break

        self.save_todos(todos)
        return f"Marked complete ({passed}/{total} passed)"

    def _set_todo_status(self, todos, todo_id: str, status: str):
        """Helper to set status on either list or dict todos."""
        if isinstance(todos, list):
            for t in todos:
                if t.get('id') == todo_id:
                    t['status'] = status
                    t['updated_at'] = datetime.now().isoformat()
                    break
        elif isinstance(todos, dict):
            for phase, tasks in todos.items():
                if isinstance(tasks, dict) and todo_id in tasks:
                    tasks[todo_id]['status'] = status
                    tasks[todo_id]['updated_at'] = datetime.now().isoformat()
                    break
        self.save_todos(todos)

class PlanManager:
    """Manages strategic plans"""
    def __init__(self, base_dir: Path):
        self.plans_dir = base_dir.parent.parent / "plans"
        
    def show_plan(self):
        """Show high-level strategy"""
        # Look for strategy files
        strategy_files = list(self.plans_dir.glob("*strategy*.md")) + \
                        list(self.plans_dir.glob("PLAN*.md"))
        
        if not strategy_files:
            print("[-] No strategy plan found in plans/")
            return

        latest_plan = sorted(strategy_files)[-1]
        print(f"\n{'='*60}")
        print(f"STRATEGIC PLAN: {latest_plan.name}")
        print(f"{'='*60}\n")
        with open(latest_plan, 'r') as f:
            print(f.read())

    def scan_marks(self):
        """Scan codebase for #[Mark] annotations"""
        print("[*] Scanning codebase for Strategic Marks...")
        root_dir = self.plans_dir.parent
        marks = []
        
        _skip_dirs = {"archive", "node_modules", "__pycache__", ".onboarding", "backup", "history", ".git", "babel_data"}
        for root, dirs, files in os.walk(root_dir):
            dirs[:] = [d for d in dirs if d not in _skip_dirs]
            for file in files:
                if not file.endswith(('.py', '.md', '.js', '.json')):
                    continue
                
                path = Path(root) / file
                try:
                    with open(path, 'r', errors='ignore') as f:
                        for i, line in enumerate(f):
                            if "#[Mark:" in line:
                                start = line.find("#[Mark:") + 7
                                end = line.find("]", start)
                                if end != -1:
                                    mark_id = line[start:end]
                                    marks.append((mark_id, file, i+1))
                except:
                    pass
        return marks

    def project_report(self) -> str:
        """#[Mark:P3-Report] High-level health check"""
        tm = TodoManager(self.plans_dir.parent)
        todos = tm.load_todos_flat()
        marks = self.scan_marks()

        # Stats
        total_tasks = len(todos)
        done_tasks = len([t for t in todos if t.get('status') == 'done'])
        in_progress = len([t for t in todos if t.get('status', '').lower() in ('in-progress', 'in_progress', 'ready')])

        mark_ids = {m[0] for m in marks}
        todo_ids = {t.get('id', '') for t in todos}
        
        # Orphaned Marks (Mark in code but no Todo)
        # Exclude generic examples like "TaskID" or "<ID>"
        orphans = [m for m in marks if m[0] not in todo_ids and m[0] not in ['TaskID', '<ID>', '...']]
        
        # Unimplemented Tasks (Todo but no Mark)
        unimplemented = [t for t in todos if t.get('id', '') not in mark_ids and t.get('status', '') != 'done']
        
        report = []
        report.append(f"PROJECT HEALTH REPORT: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        report.append("="*40)
        report.append(f"Tasks: {total_tasks} Total | {done_tasks} Done | {in_progress} In-Progress")
        report.append(f"Code Marks: {len(marks)} detected")
        report.append("-"*40)
        
        if orphans:
            report.append(f"[!] ORPHANED MARKS ({len(orphans)}): Marks found with no matching Todo ID")
            for o in orphans[:5]: report.append(f"    - {o[0]} in {o[1]}")
            if len(orphans) > 5: report.append("    ...")
            
        if unimplemented:
            report.append(f"[?] PENDING IMPLEMENTATION ({len(unimplemented)}): Open tasks with no code marks")
            for u in unimplemented[:5]: report.append(f"    - {u.get('title', '?')} ({u.get('id', '?')})")
            if len(unimplemented) > 5: report.append("    ...")
            
        if not orphans and not unimplemented:
            report.append("[✓] Alignment Perfect: All active marks match todos.")

        return "\n".join(report)

class TrustRegistry:
    """Manages trust verification for processes, PIDs, and network IPs.

    After security breach (2026-02), external agents MUST be tracked with
    first-seen verification, NOT assumed as native OS components.
    """
    def __init__(self, base_dir: Path):
        self.registry_file = base_dir / "trust_registry.json"
        self.registry = self._load_or_initialize()

    def _load_or_initialize(self) -> Dict[str, Any]:
        """Load existing registry or create default."""
        if not self.registry_file.exists():
            # Create default registry
            default = {
                "version": "1.0",
                "created_at": datetime.now().isoformat(),
                "last_updated": datetime.now().isoformat(),
                "baseline_snapshot": {
                    "os_components": {},
                    "external_agents": {
                        "claude-code": {
                            "first_seen": None,
                            "verified_ips": [],
                            "pid_history": [],
                            "last_verified": None,
                            "trust_level": "untrusted",
                            "requires_network": False,
                            "notes": "Local CLI tool. Trusted when invoked by user."
                        },
                        "gemini-agent": {
                            "first_seen": None,
                            "verified_ips": [],
                            "trust_level": "untrusted",
                            "requires_network": True,
                            "notes": "Only trusted when user explicitly invokes."
                        }
                    }
                },
                "network_trust": {"known_ips": {}, "verification_log": []},
                "telemetry_log": []
            }
            self.registry_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.registry_file, 'w') as f:
                json.dump(default, f, indent=2)
            return default

        with open(self.registry_file, 'r') as f:
            return json.load(f)

    def save(self):
        """Persist registry to disk."""
        self.registry['last_updated'] = datetime.now().isoformat()
        with open(self.registry_file, 'w') as f:
            json.dump(self.registry, f, indent=2)

    def register_first_seen(self, entity_type: str, name: str, **metadata):
        """Record first appearance of process/IP.

        Args:
            entity_type: 'os_component', 'external_agent', 'network_ip'
            name: Process name or IP address
            metadata: pid, timestamp, parent_pid, etc.
        """
        timestamp = datetime.now().isoformat()

        if entity_type == "os_component":
            target = self.registry['baseline_snapshot']['os_components']
        elif entity_type == "external_agent":
            target = self.registry['baseline_snapshot']['external_agents']
        elif entity_type == "network_ip":
            target = self.registry['network_trust']['known_ips']
        else:
            raise ValueError(f"Unknown entity_type: {entity_type}")

        if name not in target:
            target[name] = {
                "first_seen": timestamp,
                "trust_level": "untrusted",
                **metadata
            }
            self.registry['telemetry_log'].append({
                "event": "first_seen",
                "entity_type": entity_type,
                "name": name,
                "timestamp": timestamp
            })
            self.save()

    def verify_pid_telemetry(self, process_name: str, pid: int, session_id: str) -> Dict[str, Any]:
        """Check if PID telemetry is consistent with baseline.

        Returns:
            {
                "verified": bool,
                "trust_status": "native|trusted|conditional|untrusted",
                "first_seen": timestamp or None,
                "pid_changes": int,
                "notes": str
            }
        """
        # Check OS components first (native trust)
        os_comps = self.registry['baseline_snapshot']['os_components']
        if process_name in os_comps:
            comp = os_comps[process_name]
            if comp['first_seen'] is None:
                comp['first_seen'] = datetime.now().isoformat()
                comp['pid_history'] = [pid]
                self.save()
            elif pid not in comp.get('pid_history', []):
                comp.setdefault('pid_history', []).append(pid)
                self.save()

            return {
                "verified": True,
                "trust_status": "native",
                "first_seen": comp['first_seen'],
                "pid_changes": len(comp.get('pid_history', [])),
                "notes": "Native OS component"
            }

        # Check external agents (conditional trust)
        ext_agents = self.registry['baseline_snapshot']['external_agents']
        if process_name in ext_agents:
            agent = ext_agents[process_name]
            if agent['first_seen'] is None:
                agent['first_seen'] = datetime.now().isoformat()
                agent['pid_history'] = [pid]
                agent['last_verified'] = session_id
                self.save()
            elif pid not in agent.get('pid_history', []):
                agent['pid_history'].append(pid)
                agent['last_verified'] = session_id
                self.save()

            return {
                "verified": agent.get('requires_network', False) == False,  # Local agents OK
                "trust_status": agent.get('trust_level', 'conditional'),
                "first_seen": agent['first_seen'],
                "pid_changes": len(agent.get('pid_history', [])),
                "notes": agent.get('notes', '')
            }

        # Unknown process - untrusted
        return {
            "verified": False,
            "trust_status": "untrusted",
            "first_seen": None,
            "pid_changes": 0,
            "notes": "Unknown process, not in registry"
        }

    def check_ip_trust(self, ip: str, verify_dns: bool = False) -> str:
        """Check trust level of network IP.

        Args:
            ip: IP address
            verify_dns: If True, perform DNS lookup + TLS cert check

        Returns:
            trust_level: "native|trusted|conditional|untrusted"
        """
        known_ips = self.registry['network_trust']['known_ips']

        # Localhost is always trusted
        if ip in ['127.0.0.1', '::1', 'localhost']:
            return "native"

        if ip in known_ips:
            return known_ips[ip].get('trust_level', 'conditional')

        # Unknown IP - untrusted by default
        if verify_dns:
            # TODO: Implement DNS reverse lookup + TLS verification
            pass

        return "untrusted"

    def add_verified_ip(self, ip: str, domain: str, trust_level: str = "conditional"):
        """Add IP to trusted registry after manual verification."""
        self.registry['network_trust']['known_ips'][ip] = {
            "domain": domain,
            "first_seen": datetime.now().isoformat(),
            "last_verified": datetime.now().isoformat(),
            "trust_level": trust_level,
            "verification_method": "manual"
        }
        self.registry['network_trust']['verification_log'].append({
            "event": "ip_verified",
            "ip": ip,
            "domain": domain,
            "timestamp": datetime.now().isoformat()
        })
        self.save()

    def has_untrusted(self) -> bool:
        """Quick check if any untrusted entities detected."""
        # Check for untrusted external agents with recent activity
        for name, agent in self.registry['baseline_snapshot']['external_agents'].items():
            if agent.get('trust_level') == 'untrusted' and agent.get('first_seen'):
                return True

        # Check for untrusted IPs
        for ip, data in self.registry['network_trust']['known_ips'].items():
            if data.get('trust_level') == 'untrusted':
                return True

        return False

class UnifiedTodoSync:
    """Bidirectional sync between Claude tasks, Os_Toolkit todos, and code marks.

    Reconciles three sources:
    1. ~/.claude/todos/{session_id}-agent-{session_id}.json (Claude's TaskCreate/TaskUpdate)
    2. Data/plans/todos.json (shared canonical task store — phase-dict format)
    3. #[Mark:ID-STATUS] annotations in codebase (PlanManager scan_marks)
    """

    def __init__(self, project_root: Path = None):
        self.claude_tasks_dir = Path.home() / ".claude" / "todos"
        # Primary: Data/plans/todos.json (shared with planner_tab — phase-dict format)
        _data_plans = Path(__file__).resolve().parents[2] / "plans" / "todos.json"
        _cwd_plans = Path("plans/todos.json")
        self.os_toolkit_file = _data_plans if _data_plans.exists() else _cwd_plans
        self.project_root = project_root or Path(".")

    def read_claude_tasks(self, session_id: str = None) -> List[Dict[str, Any]]:
        """Read tasks from ~/.claude/todos/{session}-agent-{session}.json (JSON array format)."""
        if not self.claude_tasks_dir.exists():
            return []

        # Find target file: {session}-agent-{session}.json
        if session_id:
            target = self.claude_tasks_dir / f"{session_id}-agent-{session_id}.json"
            candidates = [target] if target.exists() else []
        else:
            candidates = sorted(
                self.claude_tasks_dir.glob("*-agent-*.json"),
                key=lambda x: x.stat().st_mtime, reverse=True
            )

        if not candidates:
            return []

        try:
            raw = json.loads(candidates[0].read_text(encoding="utf-8"))
        except Exception:
            return []

        if not isinstance(raw, list):
            return []

        tasks = []
        for task in raw:
            if not isinstance(task, dict):
                continue
            try:
                tasks.append({
                    "source": "claude",
                    "id": f"claude_{task['id']}",
                    "original_id": task['id'],
                    "title": task.get('subject', task.get('title', '')),
                    "description": task.get('description', ''),
                    "status": task.get('status', 'pending'),
                    "file": str(candidates[0])
                })
            except Exception:
                continue
        return tasks

    def read_os_toolkit_todos(self) -> List[Dict[str, Any]]:
        """Read all tasks from plans/todos.json"""
        if not self.os_toolkit_file.exists():
            return []

        try:
            with open(self.os_toolkit_file) as f:
                todos = json.load(f)
        except:
            return []

        # Flatten dict-style (phase-grouped) or list-style todos
        flat = []
        if isinstance(todos, list):
            flat = [t for t in todos if isinstance(t, dict)]
        elif isinstance(todos, dict):
            for phase, tblock in todos.items():
                if isinstance(tblock, dict):
                    for tid, t in tblock.items():
                        if isinstance(t, dict):
                            if 'id' not in t:
                                t['id'] = tid
                            flat.append(t)

        return [{
            "source": "os_toolkit",
            "id": t.get('id', ''),
            "title": t.get('title', ''),
            "description": t.get('description', ''),
            "status": t.get('status', 'open'),
            "created_at": t.get('created_at'),
            "updated_at": t.get('updated_at'),
            # Extended fields
            "project_id": t.get('project_id'),
            "plan_id": t.get('plan_id'),
            "diffs": t.get('diffs', []),
            "meta_links": t.get('meta_links', []),
            "wherein": t.get('wherein', ''),
            "plan_doc": t.get('plan_doc', ''),
            "test_expectations": t.get('test_expectations', []),
        } for t in flat]

    def read_gemini_tasks(self) -> List[Dict[str, Any]]:
        """Read all tasks from Gemini's dynamic session plans/ directory"""
        gemini_tmp = Path.home() / ".gemini" / "tmp"
        if not gemini_tmp.exists():
            return []

        # Find latest session by modification time
        try:
            sessions = sorted([d for d in gemini_tmp.iterdir() if d.is_dir() and len(d.name) > 32],
                            key=lambda x: x.stat().st_mtime, reverse=True)
        except Exception:
            return []

        if not sessions:
            return []

        # Check the top few sessions in case the very latest one hasn't set up plans yet
        target_plans_dir = None
        for session in sessions[:3]:
             p_dir = session / "plans"
             if p_dir.exists():
                 target_plans_dir = p_dir
                 break
        
        if not target_plans_dir:
            return []

        tasks = []
        todos_file = target_plans_dir / "todos.json"
        
        if todos_file.exists():
            try:
                with open(todos_file) as f:
                    data = json.load(f)
                    for t in data:
                        tasks.append({
                            "source": "gemini",
                            "id": f"gemini_{t['id']}",
                            "original_id": t['id'],
                            "title": t['title'],
                            "description": t.get('description', ''),
                            "status": t['status']
                        })
            except:
                pass
        return tasks

    def read_guillm_sessions(self) -> List[Dict[str, Any]]:
        """Read action items from GUILLM session logs (if any exist)."""
        guillm_dir = self.project_root / "tabs" / "custom_code_tab" / "sub_tabs" / "guillm_data" / "sessions"
        if not guillm_dir.exists():
            return []
        tasks = []
        for sess_file in sorted(guillm_dir.glob("*.txt"), reverse=True)[:5]:
            try:
                content = sess_file.read_text(encoding='utf-8', errors='replace')
                # Extract TODO-like lines from chat sessions
                for line in content.splitlines():
                    if any(kw in line.lower() for kw in ['todo:', 'task:', 'fix:', 'bug:']):
                        tasks.append({
                            "source": "guillm",
                            "id": f"guillm_{sess_file.stem}_{len(tasks)}",
                            "title": line.strip()[:100],
                            "status": "pending",
                            "description": f"From GUILLM session {sess_file.name}",
                        })
            except Exception:
                continue
        return tasks

    def scan_code_marks(self) -> List[Dict[str, Any]]:
        """Scan codebase for #[Mark:ID-STATUS] annotations"""
        marks = []

        for file_path in self.project_root.rglob("*"):
            if file_path.suffix not in ['.py', '.md', '.json', '.sh']:
                continue
            if any(x in str(file_path) for x in ['archive', '__pycache__', 'node_modules', '.git']):
                continue

            try:
                with open(file_path, 'r', errors='ignore') as f:
                    for i, line in enumerate(f, 1):
                        if "#[Mark:" in line:
                            start = line.find("#[Mark:") + 7
                            end = line.find("]", start)
                            if end != -1:
                                mark_id = line[start:end]

                                # Parse status from mark_id (e.g., "P0-1-COMPLETE")
                                status = "PENDING"
                                if "COMPLETE" in mark_id or "DONE" in mark_id:
                                    status = "COMPLETE"
                                elif "IN_PROGRESS" in mark_id or "IN-PROGRESS" in mark_id:
                                    status = "IN_PROGRESS"
                                elif "BLOCKED" in mark_id:
                                    status = "BLOCKED"

                                marks.append({
                                    "source": "mark",
                                    "id": mark_id,
                                    "file": str(file_path),
                                    "line": i,
                                    "status": status,
                                    "context": line.strip()[:100]
                                })
            except:
                continue

        return marks

    def reconcile(self) -> Dict[str, Any]:
        """Find conflicts and create unified view."""
        claude_tasks = self.read_claude_tasks()
        gemini_tasks = self.read_gemini_tasks()
        guillm_tasks = self.read_guillm_sessions()
        os_todos = self.read_os_toolkit_todos()
        code_marks = self.scan_code_marks()

        unified = {}

        # Start with Os_Toolkit todos as base (authoritative source)
        for todo in os_todos:
            unified[todo['id']] = {
                "id": todo['id'],
                "title": todo['title'],
                "description": todo['description'],
                "status": {
                    "os_toolkit": todo['status'],
                    "claude": None,
                    "gemini": None,
                    "mark": None
                },
                "sources": ["os_toolkit"],
                "conflicts": [],
                "created_at": todo.get('created_at'),
                "updated_at": todo.get('updated_at'),
                # Extended fields for project coordination
                "project_id": todo.get('project_id'),
                "plan_id": todo.get('plan_id'),
                "diffs": todo.get('diffs', []),
                "meta_links": todo.get('meta_links', [])
            }

        # Match Claude tasks
        for task in claude_tasks:
            matched = False
            for uid, entry in unified.items():
                if self._similar(task['title'][:50], entry['title'][:50]):
                    entry['status']['claude'] = task['status']
                    entry['sources'].append('claude')
                    entry['claude_id'] = task['original_id']
                    matched = True
                    break
            if not matched:
                unified[task['id']] = {
                    "id": task['id'], "title": task['title'], "description": task['description'],
                    "status": {"os_toolkit": None, "claude": task['status'], "gemini": None, "mark": None},
                    "sources": ["claude"], "conflicts": [], "claude_id": task['original_id'],
                    "project_id": task.get('project_id'), "plan_id": task.get('plan_id'),
                    "diffs": task.get('diffs', []), "meta_links": task.get('meta_links', [])
                }

        # Match Gemini tasks
        for task in gemini_tasks:
            matched = False
            for uid, entry in unified.items():
                if self._similar(task['title'][:50], entry['title'][:50]):
                    entry['status']['gemini'] = task['status']
                    entry['sources'].append('gemini')
                    entry['gemini_id'] = task['original_id']
                    matched = True
                    break
            if not matched:
                unified[task['id']] = {
                    "id": task['id'], "title": task['title'], "description": task['description'],
                    "status": {"os_toolkit": None, "claude": None, "gemini": task['status'], "mark": None},
                    "sources": ["gemini"], "conflicts": [], "gemini_id": task['original_id'],
                    # Gemini might not have these extended fields populated yet, but we include them for consistency
                    "project_id": None, "plan_id": None, "diffs": [], "meta_links": []
                }

        # Match GUILLM session tasks
        for task in guillm_tasks:
            matched = False
            for uid, entry in unified.items():
                if self._similar(task['title'][:50], entry['title'][:50]):
                    entry['sources'].append('guillm')
                    matched = True
                    break
            if not matched:
                unified[task['id']] = {
                    "id": task['id'], "title": task['title'],
                    "description": task.get('description', ''),
                    "status": {"os_toolkit": None, "claude": None, "gemini": None, "mark": None},
                    "sources": ["guillm"], "conflicts": [],
                    "project_id": None, "plan_id": None, "diffs": [], "meta_links": []
                }

        # Status priority: COMPLETE > IN_PROGRESS > BLOCKED > PENDING (prefer higher-priority status)
        _status_rank = {"COMPLETE": 4, "IN_PROGRESS": 3, "BLOCKED": 2, "PENDING": 1}

        def _set_mark_status(entry, mark):
            """Update mark status only if new status is higher priority than existing."""
            cur = entry['status'].get('mark')
            new_rank = _status_rank.get(mark['status'], 0)
            cur_rank = _status_rank.get(cur, 0)
            if new_rank >= cur_rank:
                entry['status']['mark'] = mark['status']
                entry['mark_location'] = f"{mark['file']}:{mark['line']}"
            if 'mark' not in entry['sources']:
                entry['sources'].append('mark')

        # Match code marks by ID
        for mark in code_marks:
            # Try exact match first
            if mark['id'] in unified:
                _set_mark_status(unified[mark['id']], mark)
            else:
                # Try fuzzy match on partial ID (e.g., "P0-COMPLETE" matches "P0-1")
                matched = False
                for uid in list(unified.keys()):
                    if uid in mark['id'] or mark['id'].startswith(uid):
                        _set_mark_status(unified[uid], mark)
                        matched = True
                        break

                if not matched:
                    # Orphaned mark (no matching todo)
                    unified[mark['id']] = {
                        "id": mark['id'],
                        "title": f"Orphaned mark in {Path(mark['file']).name}",
                        "description": mark['context'],
                        "status": {"os_toolkit": None, "claude": None, "gemini": None, "mark": mark['status']},
                        "sources": ["mark"],
                        "conflicts": [],
                        "mark_location": f"{mark['file']}:{mark['line']}"
                    }

        # Detect conflicts (different statuses between sources)
        for uid, entry in unified.items():
            statuses = {k: v for k, v in entry['status'].items() if v}
            if len(set(statuses.values())) > 1:
                # Normalize statuses for comparison
                normalized = {k: self._normalize_status(v) for k, v in statuses.items()}
                if len(set(normalized.values())) > 1:
                    entry['conflicts'].append(f"Status mismatch: {statuses}")

        # L3+L5: Enrich unified entries with marks[] + wherein from task_context_*.json sidecars.
        # task_context files hold the per-task AoE context: changes[] event IDs → marks,
        # _meta.wherein → file path. When the task_id is not already in unified (e.g. planner
        # tasks that only exist in checklist.json + task_context sidecars), add a synthesised
        # entry so marks/wherein propagate through to sync_to_claude.
        tasks_dir = self.os_toolkit_file.parent / "Tasks"
        if tasks_dir.exists():
            for ctx_file in tasks_dir.glob("task_context_*.json"):
                try:
                    ctx = json.loads(ctx_file.read_text(encoding="utf-8"))
                    meta = ctx.get("_meta") or {}
                    ctx_task_id = meta.get("task_id") or ""
                    ctx_wherein = meta.get("wherein") or ""
                    ctx_title = meta.get("title") or ctx_task_id
                    # Build marks list from changes[] event IDs (L5: event → task bridge)
                    ctx_marks = [
                        ch.get("eid") or ch.get("event_id", "")
                        for ch in (ctx.get("changes") or [])
                        if ch.get("eid") or ch.get("event_id")
                    ]
                    if not ctx_task_id:
                        continue
                    if ctx_task_id in unified:
                        entry = unified[ctx_task_id]
                    else:
                        # Synthesise entry for planner tasks not yet in any sync source
                        unified[ctx_task_id] = {
                            "id": ctx_task_id,
                            "title": ctx_title,
                            "description": meta.get("description", ""),
                            "status": {
                                "os_toolkit": None, "claude": None,
                                "gemini": None, "mark": None
                            },
                            "sources": ["task_context"],
                            "conflicts": [],
                            "project_id": meta.get("project_id"),
                            "plan_id": meta.get("plan_id"),
                            "diffs": [], "meta_links": [],
                            "marks": [],
                            "wherein": ctx_wherein,
                        }
                        entry = unified[ctx_task_id]
                    # Apply marks and wherein
                    if ctx_marks:
                        existing_marks = list(entry.get("marks") or [])
                        for m in ctx_marks:
                            if m and m not in existing_marks:
                                existing_marks.append(m)
                        entry["marks"] = existing_marks
                    if ctx_wherein and not entry.get("wherein"):
                        entry["wherein"] = ctx_wherein
                except Exception:
                    continue

        # L7: Enrich plan_id from Epic .md references (scan Data/plans/Epics/*.md).
        # Each Epic file is treated as a plan doc; task IDs referenced in it get that plan_id.
        epics_dir = self.os_toolkit_file.parent / "Epics"
        _task_ref_re = re.compile(r"\btask[_\-](\w+)", re.IGNORECASE)
        if epics_dir.exists():
            for epic_file in epics_dir.glob("*.md"):
                try:
                    epic_text = epic_file.read_text(encoding="utf-8", errors="replace")
                    plan_id = epic_file.stem  # e.g. "epic_settings_overhaul"
                    for m in _task_ref_re.finditer(epic_text):
                        tid = "task_" + m.group(1)
                        if tid in unified and not unified[tid].get("plan_id"):
                            unified[tid]["plan_id"] = plan_id
                except Exception:
                    continue

        # V2: Promote OPEN runtime_bugs.json entries to unified dict as auto_bug tasks.
        # These are warning-level bugs written by logger_util._auto_create_warn_task().
        # Without this, 37+ entries sit dead in runtime_bugs.json with no downstream consumer.
        rb_path = self.os_toolkit_file.parent / "runtime_bugs.json"
        if rb_path.exists():
            try:
                rb_entries = json.loads(rb_path.read_text(encoding="utf-8"))
                for i, bug in enumerate(rb_entries or []):
                    if not isinstance(bug, dict):
                        continue
                    if bug.get("status", "").upper() != "OPEN":
                        continue
                    # Derive a stable ID from index + timestamp fragment
                    ts_frag = (bug.get("timestamp") or "")[:16].replace(":", "").replace("-", "").replace("T", "_").replace(" ", "_")
                    bug_id = f"auto_bug_{i:03d}_{ts_frag}"
                    if bug_id in unified:
                        continue  # already present from prior sync
                    msg = (bug.get("message") or bug.get("type") or "")[:120]
                    unified[bug_id] = {
                        "id": bug_id,
                        "title": f"[auto_bug] {msg}",
                        "description": json.dumps(bug),
                        "status": {"os_toolkit": None, "claude": None, "gemini": None, "mark": None},
                        "sources": ["auto_bug"],
                        "conflicts": [],
                        "project_id": None, "plan_id": None,
                        "diffs": [], "meta_links": [],
                        "marks": [],
                        "wherein": bug.get("file") or "",
                    }
            except Exception:
                pass

        # Write agent_context.json — shared context doc any agent can read
        self._write_agent_context(unified)

        return unified

    def _write_agent_context(self, unified: Dict[str, Any]):
        """
        Writes Data/plans/agent_context.json — a compact, agent-readable summary
        of current task state. Any agent (Claude, Gemini, future) can read this
        to get oriented without running a full sync.

        Includes: top P0/P1 open tasks, active debug log path, Claude session ref,
        bug count, and task store health stats.
        #[Mark:AGENT_CONTEXT]
        """
        try:
            _plans_dir = self.os_toolkit_file.parent  # os_toolkit_file = Data/plans/todos.json → parent = Data/plans/

            # Select top priority open tasks (P0/P1, not completed, not orphaned marks)
            _priority_order = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}
            _open_tasks = []
            for uid, entry in unified.items():
                _status = entry.get("status", {})
                _effective = (
                    _status.get("claude") or _status.get("os_toolkit") or
                    _status.get("mark") or "pending"
                ) if isinstance(_status, dict) else str(_status or "pending")
                if _effective.lower() in ("completed", "done", "cancelled"):
                    continue
                _title = (entry.get("title") or "")
                # Skip orphaned marks and pure-numeric IDs (auto-generated mark artifacts).
                # Real task IDs use task_YYMM_N or gemini_xxxxx format — never bare digits.
                _is_real = (not _title.startswith("Orphaned mark")
                            and uid not in ("", "...")
                            and not uid.strip().isdigit())
                if not _is_real:
                    continue
                _prio = (entry.get("priority") or "P3").upper()
                _open_tasks.append({
                    "id": uid,
                    "title": _title[:80],
                    "priority": _prio,
                    "wherein": entry.get("wherein", ""),
                    "marks": (entry.get("marks") or [])[:5],
                    "sources": list(entry.get("sources") or []),
                    "_prio_sort": _priority_order.get(_prio, 9),
                })
            _open_tasks.sort(key=lambda x: (x["_prio_sort"], x["id"]))
            _top_tasks = [{k: v for k, v in t.items() if k != "_prio_sort"}
                          for t in _open_tasks[:20]]

            # Find current Claude session (newest JSONL by mtime)
            _claude_session = ""
            _trainer_proj = Path.home() / ".claude" / "projects" / "-home-commander-Trainer"
            if _trainer_proj.exists():
                _sessions = sorted(
                    _trainer_proj.glob("*.jsonl"),
                    key=lambda f: f.stat().st_mtime, reverse=True
                )
                if _sessions:
                    _claude_session = str(_sessions[0])

            # Find latest debug log (Data/DeBug/ — one level up from Data/plans/)
            _debug_dir = self.os_toolkit_file.parent.parent / "DeBug"
            _latest_log = ""
            if _debug_dir.exists():
                _logs = sorted(_debug_dir.glob("debug_log_*.txt"),
                               key=lambda f: f.stat().st_mtime, reverse=True)
                if _logs:
                    _latest_log = str(_logs[0])

            _ctx = {
                "generated": datetime.now().isoformat(),
                "task_store_health": {
                    "total_tasks": len(unified),
                    "open_tasks": len(_open_tasks),
                    "p0_count": sum(1 for t in _open_tasks if t["priority"] == "P0"),
                    "p1_count": sum(1 for t in _open_tasks if t["priority"] == "P1"),
                    "sources": ["todos.json", "checklist.json", "task_context", "auto_bug"],
                },
                "top_priority_tasks": _top_tasks,
                "active_debug_log": _latest_log,
                "claude_session_jsonl": _claude_session,
                "claude_session_refs": str(_debug_dir / "claude_session_refs.json"),
                "plans_dir": str(_plans_dir),
                "signal_debug_script": str(_plans_dir / "signal_debug.py"),
            }

            _ctx_path = _plans_dir / "agent_context.json"
            with open(_ctx_path, "w", encoding="utf-8") as _f:
                json.dump(_ctx, _f, indent=2)

        except Exception:
            pass  # Never crash reconcile

    def _similar(self, a: str, b: str) -> bool:
        """Simple similarity check."""
        a_lower = a.lower().strip()
        b_lower = b.lower().strip()
        return a_lower == b_lower or a_lower in b_lower or b_lower in a_lower

    def _normalize_status(self, status: str) -> str:
        """Normalize status to common format for comparison.

        Lifecycle: pending → in_progress → completed
                       ↓
                   deferred (preserves idea with temporal context)
        """
        if not status:
            return 'pending'
        status_lower = status.lower()
        if status_lower in ['done', 'complete', 'completed']:
            return 'completed'
        elif status_lower in ['in-progress', 'in_progress', 'in progress']:
            return 'in_progress'
        elif status_lower in ['open', 'pending']:
            return 'pending'
        elif status_lower in ['deferred', 'defer', 'postponed', 'later']:
            return 'deferred'
        elif status_lower in ['cancelled', 'blocked']:
            return 'cancelled'
        return status_lower

    def sync_to_os_toolkit(self, unified: Dict[str, Any]) -> int:
        """Update plans/todos.json with unified state.

        Returns:
            Number of todos updated
        """
        todos = []

        for uid, entry in unified.items():
            # Choose authoritative status (priority: Claude > Gemini > Os_Toolkit > Mark)
            status = entry['status']['claude'] or entry['status']['gemini'] or entry['status']['os_toolkit'] or entry['status']['mark']

            # NORMALIZE to canonical vocabulary (Claude's format)
            # This harmonizes vocabulary across all 3 sources
            normalized_status = self._normalize_status(status)

            # Skip orphaned marks (no title)
            if not entry.get('title'):
                continue

            todos.append({
                "id": uid,
                "title": entry['title'],
                "description": entry.get('description', ''),
                "status": normalized_status,
                "directory": ".",
                "created_at": entry.get('created_at', datetime.now().isoformat()),
                "updated_at": datetime.now().isoformat(),
                # Preserve extended fields
                "project_id": entry.get('project_id'),
                "plan_id": entry.get('plan_id'),
                "diffs": entry.get('diffs', []),
                "meta_links": entry.get('meta_links', []),
                # L3+L5: structural anchors — event marks and file path
                "marks": entry.get('marks', []),
                "wherein": entry.get('wherein', ''),
            })

        # Backup existing and preserve dict format if present
        if self.os_toolkit_file.exists():
            _bkup_dir = self.os_toolkit_file.parent / "Refs" / "todo_backups"
            _bkup_dir.mkdir(parents=True, exist_ok=True)
            backup_file = _bkup_dir / f"todos_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            shutil.copy2(self.os_toolkit_file, backup_file)

            # If existing file is dict (phase-grouped), merge rather than overwrite
            try:
                existing = json.loads(self.os_toolkit_file.read_text(encoding="utf-8"))
                if isinstance(existing, dict):
                    # Collect all IDs from authoritative (non-sync) phases
                    _existing_ids = set()
                    for _pk, _pv in existing.items():
                        if isinstance(_pv, dict) and not _pk.startswith("phase_sync"):
                            for _tid, _tv in _pv.items():
                                if isinstance(_tv, dict):
                                    _existing_ids.add(_tv.get("id", _tid))
                    # Only sync genuinely new tasks (not already in authoritative phases)
                    sync_key = f"phase_sync_{datetime.now().strftime('%y%m')}"
                    sync_bucket = {}
                    for t in todos:
                        _tid = t.get("id", "")
                        if _tid and _tid not in _existing_ids:
                            t["_source"] = "sync"
                            sync_bucket[_tid] = t
                    existing[sync_key] = sync_bucket
                    todos = existing  # Write back as dict with all phases preserved
            except Exception:
                pass

        # Write updated
        self.os_toolkit_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.os_toolkit_file, 'w') as f:
            json.dump(todos, f, indent=2)

        return len(todos) if isinstance(todos, list) else sum(
            len(v) for v in todos.values() if isinstance(v, dict)
        )

    def sync_to_claude(self, unified: Dict[str, Any], session_id: str = None) -> int:
        """Sync Os_Toolkit todos TO Claude's task file (bidirectional sync!)

        Writes/merges into ~/.claude/todos/{session}-agent-{session}.json (JSON array).
        This is the file Claude Code reads for the /tasks command.

        Args:
            unified: Reconciled todo data
            session_id: Claude session ID (auto-detect if None)

        Returns:
            Number of Claude tasks created/updated
        """
        if not self.claude_tasks_dir.exists():
            print("[-] ~/.claude/todos/ not found - cannot sync to Claude")
            return 0

        # Find target file: {session}-agent-{session}.json
        # V1: detect active Claude session via CLAUDE_SESSION_ID env var so /tasks shows live todos
        if not session_id:
            import os as _os
            session_id = _os.environ.get("CLAUDE_SESSION_ID") or ""
        if session_id:
            target_file = self.claude_tasks_dir / f"{session_id}-agent-{session_id}.json"
            if not target_file.exists():
                # Create the file for this session so sync can populate it
                print(f"[*] Creating Claude todos file for session: {session_id[:8]}...")
                target_file.write_text("[]", encoding="utf-8")
        else:
            # Fallback: most recently modified file (legacy behaviour)
            candidates = sorted(
                self.claude_tasks_dir.glob("*-agent-*.json"),
                key=lambda x: x.stat().st_mtime, reverse=True
            )
            if not candidates:
                print("[-] No Claude todos files found - cannot sync to Claude")
                return 0
            target_file = candidates[0]

        # Load existing tasks array
        existing_tasks = []
        try:
            raw = json.loads(target_file.read_text(encoding="utf-8"))
            if isinstance(raw, list):
                existing_tasks = raw
        except Exception:
            pass

        # Build dedup set from existing subjects
        existing_subjects = {t.get("subject", "").lower().strip() for t in existing_tasks if isinstance(t, dict)}
        existing_ids_int = [int(t["id"]) for t in existing_tasks if isinstance(t, dict) and str(t.get("id", "")).isdigit()]
        next_id = max(existing_ids_int, default=0) + 1

        synced_count = 0
        for uid, entry in unified.items():
            title = (entry.get('title') or '').strip()
            if not title:
                continue
            # Skip orphaned code marks
            if title.startswith("Orphaned mark"):
                continue
            # Skip if already in Claude by subject
            if title.lower() in existing_subjects:
                continue

            status_raw = (
                entry['status'].get('os_toolkit') or
                entry['status'].get('claude') or
                entry['status'].get('mark') or 'pending'
            )
            normalized_status = self._normalize_status(status_raw)

            # L4: Preserve original task_id (task_YYMM_N format) — do not re-number as int.
            # marks[] and wherein are passed through so Claude's task store carries the full context.
            task_id_val = entry.get('id') or str(next_id)
            claude_task = {
                "id": task_id_val,
                "subject": title,
                "description": entry.get('description', ''),
                "activeForm": f"Working on {title[:60]}...",
                "status": normalized_status,
                "marks": entry.get('marks', []),
                "wherein": entry.get('wherein', ''),
                "blocks": [],
                "blockedBy": []
            }

            existing_tasks.append(claude_task)
            existing_subjects.add(title.lower())
            if not entry.get('id'):
                next_id += 1
            synced_count += 1

        # Write back as single JSON array
        target_file.write_text(json.dumps(existing_tasks, indent=2), encoding="utf-8")
        return synced_count

    def sync_to_gemini(self, unified: Dict[str, Any]) -> int:
        """Sync todos TO Gemini's ~/plans/todos.json (coordination system)

        Creates ~/plans directory structure if missing and writes todos
        in format compatible with Gemini CLI's coordination commands.

        Args:
            unified: Reconciled todo data

        Returns:
            Number of todos synced to Gemini
        """
        # Dynamic Detection of Gemini Session
        gemini_tmp = Path.home() / ".gemini" / "tmp"
        gemini_plans_dir = Path.home() / "plans" # Default fallback

        if gemini_tmp.exists():
            try:
                # Find latest session
                sessions = sorted([d for d in gemini_tmp.iterdir() if d.is_dir() and len(d.name) > 32],
                                key=lambda x: x.stat().st_mtime, reverse=True)
                if sessions:
                     # Check top sessions for one that has a plans dir or is just the newest
                     for session in sessions[:3]:
                         p_dir = session / "plans"
                         if p_dir.exists():
                             gemini_plans_dir = p_dir
                             print(f"[*] Detected Active Gemini Session: {gemini_plans_dir}")
                             break
                     else:
                         # If no plans dir exists yet, use the absolute newest and create it
                         gemini_plans_dir = sessions[0] / "plans"
                         print(f"[*] Initializing Gemini Session Plans: {gemini_plans_dir}")
            except Exception as e:
                print(f"[!] Error detecting Gemini session: {e}")

        gemini_todos_file = gemini_plans_dir / "todos.json"

        # Create directory if missing
        gemini_plans_dir.mkdir(parents=True, exist_ok=True)

        # Load existing Gemini todos if present
        existing_gemini = {}
        if gemini_todos_file.exists():
            try:
                with open(gemini_todos_file) as f:
                    gemini_data = json.load(f)
                    if isinstance(gemini_data, list):
                        existing_gemini = {todo['id']: todo for todo in gemini_data}
            except:
                pass

        # Build Gemini todos list
        gemini_todos = []
        synced_count = 0

        for uid, entry in unified.items():
            # Skip orphaned marks
            if not entry.get('title'):
                continue

            # Normalize status to canonical format
            status = entry['status']['claude'] or entry['status']['os_toolkit'] or entry['status']['mark'] or 'pending'
            normalized_status = self._normalize_status(status)

            # Map to Gemini's expected format
            gemini_status = {
                'pending': 'open',
                'in_progress': 'in-progress',
                'completed': 'done',
                'deferred': 'deferred',
                'cancelled': 'cancelled'
            }.get(normalized_status, 'open')

            gemini_todo = {
                "id": uid,
                "title": entry['title'],
                "description": entry.get('description', ''),
                "status": gemini_status,
                "directory": entry.get('directory', '.'),
                "wherein": entry.get('wherein', ''),
                "created_at": entry.get('created_at', datetime.now().isoformat()),
                "updated_at": datetime.now().isoformat(),
                "marks": entry.get('marks', []),
                "sources": list(entry.get('sources', []))
            }
            
            # Add extended project fields
            if entry.get('project_id'): gemini_todo['project_id'] = entry['project_id']
            if entry.get('plan_id'): gemini_todo['plan_id'] = entry['plan_id']
            if entry.get('diffs'): gemini_todo['diffs'] = entry['diffs']
            if entry.get('meta_links'): gemini_todo['meta_links'] = entry['meta_links']

            gemini_todos.append(gemini_todo)

            # Count if new or updated
            if uid not in existing_gemini or existing_gemini[uid] != gemini_todo:
                synced_count += 1

        # Backup existing if present
        if gemini_todos_file.exists():
            _gbk_dir = gemini_plans_dir / "todo_backups"
            _gbk_dir.mkdir(parents=True, exist_ok=True)
            backup_file = _gbk_dir / f"todos_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            shutil.copy2(gemini_todos_file, backup_file)

        # Write to Gemini's ~/plans/todos.json
        with open(gemini_todos_file, 'w') as f:
            json.dump(gemini_todos, f, indent=2)

        return synced_count

    def _map_status_to_os(self, status: str) -> str:
        """Map any status to Os_Toolkit format."""
        mapping = {
            "pending": "open", "PENDING": "open",
            "in_progress": "in-progress", "IN_PROGRESS": "in-progress",
            "in-progress": "in-progress",
            "completed": "done", "COMPLETE": "done", "done": "done",
            "cancelled": "cancelled", "CANCELLED": "cancelled", "BLOCKED": "cancelled"
        }
        return mapping.get(status, "open")

# ============================================================================
# MAIN FORENSIC OS TOOLKIT CLASS
# ============================================================================

class SystemProfiler:
    """Provides deep analysis of system-level files (binaries, configs)."""
    
    def __init__(self, os_type: OSType):
        self.os_type = os_type
        self.is_debian_based = self._check_debian()

    def _check_debian(self) -> bool:
        """Check if the system is Debian-based (for dpkg)."""
        if self.os_type != OSType.LINUX:
            return False
        return Path("/etc/debian_version").exists()

    def _run_command(self, cmd: List[str]) -> str:
        """Helper to run a shell command and return its output."""
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=False)
            return result.stdout.strip()
        except (subprocess.CalledProcessError, FileNotFoundError):
            return ""

    def get_package_info(self, file_path: str) -> Dict[str, str]:
        """Get package information for a given file path."""
        if not self.is_debian_based:
            return {}
        
        # dpkg -S: find package that owns a file
        package_name = self._run_command(['dpkg', '-S', file_path])
        if package_name:
            package_name = package_name.split(':')[0]
            # dpkg -s: get package status and metadata
            package_status = self._run_command(['dpkg', '-s', package_name])
            
            info = {}
            for line in package_status.split('\n'):
                if ':' in line:
                    key, val = line.split(':', 1)
                    info[key.strip()] = val.strip()
            return {
                'package': info.get('Package'),
                'version': info.get('Version'),
                'status': info.get('Status'),
                'maintainer': info.get('Maintainer'),
                'description': info.get('Description'),
            }
        return {}

    def get_package_info_by_name(self, package_name: str) -> Dict[str, str]:
        """Get package information by package name (not file path)."""
        if not self.is_debian_based or not package_name:
            return {}

        # dpkg -s: get package status and metadata directly
        package_status = self._run_command(['dpkg', '-s', package_name])

        if not package_status:
            return {}

        info = {}
        for line in package_status.split('\n'):
            if ':' in line:
                key, val = line.split(':', 1)
                info[key.strip()] = val.strip()

        return {
            'package': info.get('Package'),
            'version': info.get('Version'),
            'status': info.get('Status'),
            'maintainer': info.get('Maintainer'),
            'description': info.get('Description'),
        }

    def get_install_date(self, package_name: str) -> Optional[str]:
        """Get installation date for a package."""
        if not self.is_debian_based or not package_name:
            return None
        
        # Check dpkg log for installation time
        log_path = Path("/var/log/dpkg.log")
        if log_path.exists():
            try:
                log_content = log_path.read_text()
                # Pattern: YYYY-MM-DD HH:MM:SS status installed <package> <version>
                match = re.search(fr"(\d{{4}}-\d{{2}}-\d{{2}} \d{{2}}:\d{{2}}:\d{{2}}).+status installed {re.escape(package_name)}", log_content)
                if match:
                    return match.group(1)
            except Exception:
                pass
        return None

    def verify_checksum(self, file_path: str, package_name: str) -> Dict[str, str]:
        """Verify checksum of a file against its package manifest."""
        if not self.is_debian_based or not package_name:
            return {}
        
        # debsums: check md5sums of installed packages
        checksum_output = self._run_command(['debsums', '-s', package_name])
        
        status = "unknown"
        expected_md5 = None
        
        for line in checksum_output.split('\n'):
            if file_path in line:
                if "OK" in line:
                    status = "OK"
                elif "FAILED" in line:
                    status = "FAILED"
                break
        
        # If verification failed, try to get expected hash
        if status == "FAILED":
            md5sums_file = f"/var/lib/dpkg/info/{package_name}.md5sums"
            if Path(md5sums_file).exists():
                try:
                    content = Path(md5sums_file).read_text()
                    rel_path = file_path.lstrip('/')
                    match = re.search(fr"([a-f0-9]{{32}})\s+{re.escape(rel_path)}", content)
                    if match:
                        expected_md5 = match.group(1)
                except Exception:
                    pass
            
        return {
            'verification_status': status,
            'expected_md5': expected_md5
        }

    def run_all_checks(self, file_path: str) -> Optional[Dict[str, Any]]:
        """Run all system profiling checks on a file."""
        if not self.is_debian_based or not Path(file_path).is_absolute():
            return None
            
        package_info = self.get_package_info(file_path)
        if not package_info:
            return None

        package_name = package_info.get('package')
        install_date = self.get_install_date(package_name)
        checksum_info = self.verify_checksum(file_path, package_name)
        
        return {
            "package": package_info,
            "install_date": install_date,
            "checksum": checksum_info,
        }

class ForensicOSToolkit:
    """Main forensic toolkit class"""
    
    def __init__(self, session_id: Optional[str] = None, base_dir: Path = DEFAULT_BASE_DIR):
        self.base_dir = base_dir
        self._init_directories()
        
        # Detect OS
        self.os_type = self._detect_os()
        self.hostname = platform.node()
        self.architecture = platform.machine()
        self.os_version = platform.version()

        # Initialize System Profiler
        self.system_profiler = SystemProfiler(self.os_type)
        
        # Current session
        self.session = None
        self.session_id = session_id or self._generate_session_id()
        
        # Caches and indexes
        self.string_index = defaultdict(list)  # string -> [artifact_ids]
        self.hash_index = {}  # hash -> artifact_id
        self.path_index = {}  # path -> artifact_id
        
        # Verb mappings
        self.verb_mappings = self._load_verb_mappings()
        
        # Load Universal Taxonomy
        self.taxonomy = {}
        self.regex_library = {}
        self._load_universal_taxonomy()

        # Trust Registry (P0-2: Security verification)
        self.trust_registry = TrustRegistry(self.base_dir)

        # Journal
        self.journal_file = None
        
        # Performance tracking
        self.stats = {
            'artifacts_analyzed': 0,
            'files_processed': 0,
            'queries_executed': 0,
            'start_time': datetime.now()
        }
        
        # Load or create session
        if session_id and self._session_exists(session_id):
            self._load_session(session_id)
        else:
            self._create_new_session()

        # Available Actions
        self.actions = self._generate_actions()

    def _generate_actions(self) -> Dict[str, ConformityAction]:
        """Generate list of available actions"""
        actions = {}
        
        # Action: Backup Project Files
        def action_backup():
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            # Trainer/ is at self.base_dir.parent
            project_root = self.base_dir.parent
            archive_dir = project_root / "archive"
            archive_dir.mkdir(exist_ok=True)

            targets = ["Os_Toolkit.py", "Filesync.py", "generate_project_status.py", "onboarder.py"]
            backed_up = []

            # These files are in Data/tabs/action_panel_tab/ directory
            toolkit_dir = project_root / "Data" / "tabs" / "action_panel_tab"

            for target in targets:
                src = toolkit_dir / target
                if src.exists():
                    dst = archive_dir / f"{target}_{timestamp}.bak"
                    shutil.copy2(src, dst)
                    backed_up.append(target)
            
            return f"Backed up {len(backed_up)} files to {archive_dir}"

        actions['backup_core'] = ConformityAction(
            action_id='backup_core',
            name='Backup Core Scripts',
            description='Create immediate backup of Os_Toolkit, Filesync, etc.',
            impact='Low (File Copy)',
            command_func=action_backup
        )
        
        # Action: Scan Active Processes
        def action_scan_procs():
            self._analyze_processes()
            return "Scanned active processes and updated session."

        actions['scan_procs'] = ConformityAction(
            action_id='scan_procs',
            name='Scan Active Processes',
            description='Refresh process list in current session.',
            impact='Low (Read Only)',
            command_func=action_scan_procs
        )

        # Action: Security Check (Baseline Wakeup Component)
        def action_security_check():
            self._analyze_active_connections()
            warnings = []
            
            # Check for high ports or external IPs
            for artifact in self.session.artifacts.values():
                if artifact.artifact_type == ArtifactType.NETWORK_CONN:
                    peer = artifact.properties.get('peer_addr', '')
                    if '127.0.0.1' not in peer and '::1' not in peer and '0.0.0.0' not in peer:
                        warnings.append(f"External Connection: {peer}")
            
            # Check for suspicious processes
            # Use word boundaries to avoid substrings like 'sync' matching 'nc'
            suspicious_keywords = [r'\bnc\b', r'\bncat\b', r'\bnetcat\b', r'\breverse\b', r'\bshell\b']
            
            # Whitelist known system processes that might trigger false positives
            whitelist = [
                'systemd-timesyncd', 
                'at-spi-bus-launcher', 
                'irqbalance', 
                'gnome-shell',
                'bash -c', # Often us
                'ps -ef'
            ]
            
            for artifact in self.session.artifacts.values():
                if artifact.artifact_type == ArtifactType.PROCESS:
                    cmd = artifact.properties.get('command', '').lower()
                    
                    # Skip whitelisted
                    if any(wl in cmd for wl in whitelist):
                        continue
                        
                    # Check keywords
                    for kw in suspicious_keywords:
                        if re.search(kw, cmd):
                            warnings.append(f"Suspicious Process ({kw}): {cmd[:100]}")

            if warnings:
                return f"SECURITY WARNINGS FOUND:\n" + "\n".join(f"- {w}" for w in warnings)
            return "Security Check Passed: No obvious threats detected."

        actions['check_security'] = ConformityAction(
            action_id='check_security',
            name='Security Audit',
            description='Check active connections and processes for anomalies.',
            impact='Low (Read Only)',
            command_func=action_security_check
        )

        # Action: Verify Backups (Coordinated with GUI Recovery System)
        def action_verify_backups():
            # 1. Check GUI Version Manifest (The Source of Truth)
            manifest_path = self.base_dir.parent / "Data" / "backup" / "version_manifest.json"
            history_dir = self.base_dir.parent / "Data" / "backup" / "history"
            
            report = []
            
            if manifest_path.exists():
                try:
                    with open(manifest_path, 'r') as f:
                        v_data = json.load(f)
                    versions = v_data.get("versions", {})
                    active_v = v_data.get("active_version", "Unknown")
                    default_v = v_data.get("default_version", "None")
                    
                    # Count recent versions (last 24h)
                    now = datetime.now()
                    recent_count = 0
                    for ts in versions.keys():
                        try:
                            v_time = datetime.strptime(ts, "%Y%m%d_%H%M%S")
                            if (now - v_time).total_seconds() < 86400:
                                recent_count += 1
                        except: pass
                        
                    report.append(f"Version System: Active")
                    report.append(f"  Total Versions: {len(versions)}")
                    report.append(f"  Recent (24h): {recent_count}")
                    report.append(f"  Active Session: {active_v}")
                    report.append(f"  Default Rollback: {default_v}")
                except Exception as e:
                    report.append(f"Version Manifest Error: {e}")
            else:
                report.append("Version Manifest: NOT FOUND (GUI backup system may be inactive)")

            # 2. Check History Directory (Recursive File Backups)
            if history_dir.exists():
                recent_history_backups = 0
                now = datetime.now()
                # history dir structure: history/path/to/file/timestamp_filename.py
                try:
                    for f in history_dir.rglob("*"):
                        if f.is_file():
                            # Check mtime
                            mtime = datetime.fromtimestamp(f.stat().st_mtime)
                            if (now - mtime).total_seconds() < 86400:
                                recent_history_backups += 1
                    report.append(f"History File Backups (24h): {recent_history_backups}")
                except Exception as e:
                    report.append(f"History Scan Error: {e}")

            # 3. Check Archive Directory (Legacy/Manual Backups)
            archive_dir = self.base_dir.parent.parent / "archive"
            if archive_dir.exists():
                recent_archived = []
                now = datetime.now()
                for f in archive_dir.glob("*.bak"):
                    mtime = datetime.fromtimestamp(f.stat().st_mtime)
                    if (now - mtime).total_seconds() < 86400:
                        recent_archived.append(f.name)
                if recent_archived:
                    report.append(f"Archive Backups (24h): {len(recent_archived)}")
            
            return "\n".join(report)

        actions['verify_backups'] = ConformityAction(
            action_id='verify_backups',
            name='Verify Backups',
            description='Check system version manifest and archive status.',
            impact='None',
            command_func=action_verify_backups
        )

        # Action: Baseline Wakeup
        def action_baseline_wakeup():
            results = []
            results.append(action_backup())
            self._analyze_processes()
            self._analyze_active_connections()
            results.append(action_security_check())
            results.append(action_verify_backups())
            return "\n".join(results)

        actions['baseline_wakeup'] = ConformityAction(
            action_id='baseline_wakeup',
            name='Baseline Wakeup',
            description='Full start-of-day sequence: Backup -> Scan -> Security Check.',
            impact='Medium (Backup + Scans)',
            command_func=action_baseline_wakeup
        )

        # Action: Workflow Audit (Coordinated Conformity Watchdog)
        def action_audit_workflow():
            """
            #[Mark:P2.5-Conformity] Audit workflow state using live system data.
            Checks:
            1. Pending Live Changes (from version_manifest).
            2. Todo Status (from plans/todos.json).
            3. Onboarder State (new files vs catalog).
            4. Unmarked Changes (Heuristic).
            """
            results = []
            now = datetime.now()
            
            # 1. Check Live Watcher State
            manifest_path = self.base_dir.parent / "Data" / "backup" / "version_manifest.json"
            pending_changes = {}
            if manifest_path.exists():
                try:
                    with open(manifest_path, 'r') as f:
                        v_data = json.load(f)
                    pending_changes = v_data.get("pending_live_changes", {})
                except: pass
            
            results.append(f"Workflow Audit Report ({now.strftime('%H:%M:%S')})")
            results.append(f"  Live Pending Changes: {len(pending_changes)}")
            
            # 2. Check Plan Alignment
            tm = TodoManager(self.base_dir)
            todos = tm.load_todos()
            # Handle both list-style and dict-style (phase-grouped) todos
            _all_tasks = []
            if isinstance(todos, list):
                _all_tasks = [t for t in todos if isinstance(t, dict)]
            elif isinstance(todos, dict):
                for _phase, _tblock in todos.items():
                    if isinstance(_tblock, dict):
                        for _tid, _t in _tblock.items():
                            if isinstance(_t, dict):
                                _all_tasks.append(_t)
            active_tasks = [t for t in _all_tasks if t.get('status', '').lower() in ('in-progress', 'in_progress', 'ready')]
            
            results.append(f"  Active Tasks: {len(active_tasks)}")
            
            if pending_changes and not active_tasks:
                results.append("  [!] WARNING: Code is changing but no tasks are In-Progress.")
                results.append("      SUGGESTION: Create or start a task for these changes.")
            
            if pending_changes:
                results.append("  Modified Files (Live):")
                for fpath in list(pending_changes.keys())[:5]:
                    results.append(f"    - {fpath}")
                if len(pending_changes) > 5: results.append("    ...")

            # 3. Check for Marks in modified files (Heuristic - Restored)
            # Scan files in pending_changes for #[Mark:...] tags
            unmarked_files = []
            project_root = self.base_dir.parent.parent # Trainer/
            
            for rel_path in pending_changes.keys():
                filepath = project_root / rel_path
                if filepath.exists() and filepath.is_file():
                    try:
                        content = filepath.read_text(errors='ignore')
                        if "#[Mark:" not in content:
                            unmarked_files.append(rel_path)
                    except: pass
            
            if unmarked_files:
                results.append(f"  [?] NOTICE: {len(unmarked_files)} pending modified files have no #[Mark] tags.")
                for f in unmarked_files[:3]:
                    results.append(f"      - {f}")
                if len(unmarked_files) > 3: results.append("      ...")

            # 4. Check AoE Inbox (checklist.json) for unprocessed alerts
            _cl_path = Path(__file__).parent.parent.parent / "plans" / "checklist.json"
            try:
                if _cl_path.exists():
                    _cl_data = json.loads(_cl_path.read_text(encoding="utf-8"))
                    _inbox = _cl_data.get("aoe_inbox", [])
                    if _inbox:
                        _gaps = sum(1 for e in _inbox if e.get("status") == "ATTRIBUTION_GAP")
                        results.append(f"  AoE Inbox: {len(_inbox)} unprocessed alerts ({_gaps} attribution gaps)")
                        results.append(f"      SUGGESTION: Run 'Os_Toolkit.py actions --run process_inbox'")
            except Exception:
                pass

            return "\n".join(results)

        actions['audit_workflow'] = ConformityAction(
            action_id='audit_workflow',
            name='Workflow Audit',
            description='Check for live code changes vs plan synchronization.',
            impact='Low (Read Only)',
            command_func=action_audit_workflow
        )

        # Action: Sync Marks with Todos (Zenity Integration)
        def action_sync_marks():
            """
            #[Mark:P2.5-Sync] Sync code marks with todo status.
            Uses Zenity to prompt user for confirmation.
            """
            print("[*] Scanning for marks to sync with todos...")
            
            # 1. Scan for marks (reuse plan_manager logic or similar)
            pm = PlanManager(self.base_dir)
            # Capture stdout of pm.scan_marks() is messy, let's just re-implement simple scan
            root_dir = self.base_dir.parent.parent
            detected_mark_ids = set()
            for root, _, files in os.walk(root_dir):
                if any(x in root for x in ["archive", "node_modules", "__pycache__", ".onboarding"]): continue
                for file in files:
                    if not file.endswith(('.py', '.md', '.js')): continue
                    try:
                        content = (Path(root) / file).read_text(errors='ignore')
                        marks = re.findall(r'#\[Mark:([^\]]+)\]', content)
                        for m in marks: detected_mark_ids.add(m)
                    except: pass

            # 2. Load Todos
            tm = TodoManager(self.base_dir)
            todos = tm.load_todos_flat()
            updates = []

            for t in todos:
                if t.get('id') in detected_mark_ids and t.get('status') in ['open', 'pending']:
                    # Suggest moving to in-progress
                    updates.append((t['id'], t['title'], 'in-progress'))
                elif t['id'] in detected_mark_ids and t['status'] == 'in-progress':
                    # Suggest moving to done? (Maybe too aggressive, let's stick to in-progress)
                    pass

            if not updates:
                return "No sync updates needed."

            summary = ""
            for tid, title, new_status in updates:
                summary += f"• {title} ({tid}) -> {new_status}\n"

            # 3. zenity --question
            try:
                msg = f"Detected code marks for open tasks. Update statuses?\n\n{summary}"
                res = subprocess.run(['zenity', '--question', '--text', msg, '--title', 'Babel Sync', '--width', '400'], 
                                   capture_output=True)
                
                if res.returncode == 0: # User clicked Yes
                    for tid, title, new_status in updates:
                        tm.update_todo(tid, new_status)
                    return f"Successfully synced {len(updates)} tasks."
                else:
                    return "Sync cancelled by user."
            except Exception as e:
                return f"Error during Zenity prompt: {e}"

        actions['sync_marks'] = ConformityAction(
            action_id='sync_marks',
            name='Sync Code Marks',
            description='Update task status based on detected #[Mark] tags (with GUI prompt).',
            impact='Medium (Updates Todos)',
            command_func=action_sync_marks
        )

        # Action: Sync All Todos (Bidirectional)
        def action_sync_all_todos():
            """
            #[Mark:P1-TodoSync] Bidirectional sync: Claude ↔ Os_Toolkit ↔ Gemini ↔ Code marks.
            """
            sync_engine = UnifiedTodoSync(Path(__file__).parents[3])

            print("[*] Reconciling todos from 3 sources...")
            print("    1. ~/.claude/tasks/ (Claude TaskCreate/TaskUpdate)")
            print("    2. plans/todos.json (Os_Toolkit TodoManager)")
            print("    3. #[Mark:ID] annotations in code")
            print("    4. ~/plans/todos.json (Gemini coordination system)")

            unified = sync_engine.reconcile()

            # Count by source
            claude_count = sum(1 for e in unified.values() if 'claude' in e['sources'])
            os_count = sum(1 for e in unified.values() if 'os_toolkit' in e['sources'])
            mark_count = sum(1 for e in unified.values() if 'mark' in e['sources'])
            conflicts = [e for e in unified.values() if e['conflicts']]

            results = []
            results.append(f"[+] Reconciliation Complete:")
            results.append(f"    Total tasks: {len(unified)}")
            results.append(f"    Claude tasks: {claude_count}")
            results.append(f"    Os_Toolkit todos: {os_count}")
            results.append(f"    Code marks: {mark_count}")

            if conflicts:
                results.append(f"    ⚠️  Conflicts detected: {len(conflicts)}")
                results.append("")
                results.append("[!] CONFLICTS:")
                for c in conflicts[:5]:
                    results.append(f"    - {c['title'][:60]}")
                    results.append(f"      Status: Claude={c['status']['claude']}, Os={c['status']['os_toolkit']}, Mark={c['status']['mark']}")
                if len(conflicts) > 5:
                    results.append(f"    ... and {len(conflicts) - 5} more")
                results.append("")
                results.append("[?] Sync all todos to unified state? (Updates plans/todos.json)")
                # Note: Actual user prompt would happen via GUI/CLI
            else:
                results.append("    ✅ No conflicts - all sources in sync")

            # BIDIRECTIONAL SYNC: Update both directions!
            # 1. Os_Toolkit direction (Claude → Os_Toolkit)
            updated_count = sync_engine.sync_to_os_toolkit(unified)
            results.append(f"[+] Synced {updated_count} todos to plans/todos.json")

            # 2. Claude direction (Os_Toolkit → Claude)
            claude_synced = sync_engine.sync_to_claude(unified)
            if claude_synced > 0:
                results.append(f"[+] Synced {claude_synced} new todos TO Claude CLI!")
            else:
                results.append(f"[+] Claude CLI already has all todos")

            # 3. Gemini direction (Os_Toolkit → Gemini ~/plans/todos.json)
            gemini_synced = sync_engine.sync_to_gemini(unified)
            if gemini_synced > 0:
                results.append(f"[+] Synced {gemini_synced} todos TO Gemini ~/plans/todos.json!")
            else:
                results.append(f"[+] Gemini ~/plans/todos.json already up to date")

            return "\n".join(results)

        actions['sync_all_todos'] = ConformityAction(
            action_id='sync_all_todos',
            name='Sync All Todos',
            description='Bidirectional sync: Claude ↔ Os_Toolkit ↔ Gemini ↔ Code marks.',
            impact='Medium (Updates plans/todos.json + ~/plans/todos.json)',
            command_func=action_sync_all_todos
        )

        # --- process_inbox: triage aoe_inbox alerts from checklist.json ---
        def action_process_inbox():
            """
            #[Mark:P2.5-Inbox] Process aoe_inbox alerts: group by task, display, allow dismiss/link.
            Reads checklist.json aoe_inbox, shows grouped summary, optionally clears processed items.
            """
            _plans_dir = Path(__file__).parent.parent.parent / "plans"
            _cl_path = _plans_dir / "checklist.json"
            if not _cl_path.exists():
                return "[-] checklist.json not found"

            _cl = json.loads(_cl_path.read_text(encoding="utf-8"))
            _inbox = _cl.get("aoe_inbox", [])
            if not _inbox:
                return "[+] aoe_inbox is empty — no alerts to process."

            # Group by task_id
            _by_task = {}
            for entry in _inbox:
                tid = entry.get("task_id", "") or "unlinked"
                _by_task.setdefault(tid, []).append(entry)

            results = []
            results.append(f"AoE INBOX TRIAGE ({len(_inbox)} alerts, {len(_by_task)} tasks)")
            results.append("=" * 60)

            for tid, entries in sorted(_by_task.items(), key=lambda x: len(x[1]), reverse=True):
                risk_counts = {}
                files = set()
                for e in entries:
                    rl = e.get("risk_level", "LOW")
                    risk_counts[rl] = risk_counts.get(rl, 0) + 1
                    files.add(os.path.basename(e.get("file", "?")))
                risk_str = ", ".join(f"{v} {k}" for k, v in sorted(risk_counts.items()))
                results.append(f"\n  Task: {tid} ({len(entries)} alerts)")
                results.append(f"    Risk: {risk_str}")
                results.append(f"    Files: {', '.join(sorted(files))}")
                # Show unlinked attribution gaps
                gaps = [e for e in entries if e.get("status") == "ATTRIBUTION_GAP"]
                if gaps:
                    results.append(f"    ⚠️  {len(gaps)} ATTRIBUTION_GAP(s) — need manual linking")
                    for g in gaps[:3]:
                        results.append(f"      {g.get('event_id', '?')}: {g.get('message', '')[:80]}")

            # Summary actions
            results.append(f"\n{'=' * 60}")
            results.append("ACTIONS:")
            results.append(f"  Link gaps:  Os_Toolkit.py todo link <task_id> --events <eid1> <eid2>")
            results.append(f"  Link by file: Os_Toolkit.py todo link <task_id> --file <filename>")
            results.append(f"  Clear processed: Os_Toolkit.py actions --run clear_inbox")

            return "\n".join(results)

        actions['process_inbox'] = ConformityAction(
            action_id='process_inbox',
            name='Process AoE Inbox',
            description='Triage aoe_inbox alerts: group by task, show gaps, suggest links.',
            impact='Low (Read Only)',
            command_func=action_process_inbox
        )

        # --- clear_inbox: remove processed/resolved aoe_inbox entries ---
        def action_clear_inbox():
            """Remove aoe_inbox entries that have been resolved (task_ids populated in enriched_changes)."""
            _plans_dir = Path(__file__).parent.parent.parent / "plans"
            _cl_path = _plans_dir / "checklist.json"
            _vm_path = Path(__file__).parent.parent.parent / "backup" / "version_manifest.json"
            if not _cl_path.exists():
                return "[-] checklist.json not found"

            _cl = json.loads(_cl_path.read_text(encoding="utf-8"))
            _inbox = _cl.get("aoe_inbox", [])
            if not _inbox:
                return "[+] aoe_inbox already empty."

            # Load enriched_changes to check which events are now linked
            _linked_eids = set()
            if _vm_path.exists():
                _vm = json.loads(_vm_path.read_text(encoding="utf-8"))
                for eid, ch in _vm.get("enriched_changes", {}).items():
                    tids = ch.get("task_ids") or []
                    if tids:
                        _linked_eids.add(eid)

            _before = len(_inbox)
            _remaining = [e for e in _inbox if e.get("event_id") not in _linked_eids]
            _cl["aoe_inbox"] = _remaining
            _cl_path.write_text(json.dumps(_cl, indent=2), encoding="utf-8")
            _cleared = _before - len(_remaining)
            return f"[+] Cleared {_cleared} resolved alerts ({len(_remaining)} remaining)"

        actions['clear_inbox'] = ConformityAction(
            action_id='clear_inbox',
            name='Clear Resolved Inbox',
            description='Remove aoe_inbox entries whose events are now linked to tasks.',
            impact='Low (Updates checklist.json)',
            command_func=action_clear_inbox
        )

        # Helper: Infer bug resolutions from version transitions
        def _infer_bug_resolutions(plans_dir, vm):
            """Scan version transitions for damaged→stable fixes and map to BUG tasks.
            Returns list of {bug_task_id, fixed_in_version, fixed_file, evidence} dicts."""
            inferred = []
            versions = vm.get("versions", {})
            ec = vm.get("enriched_changes", {})

            ls_path = plans_dir / "Refs" / "latest_sync.json"
            if not ls_path.exists():
                return inferred
            ls = json.loads(ls_path.read_text(encoding="utf-8"))
            bug_tasks = {tid: t for tid, t in ls.get("tasks", {}).items()
                         if "BUG" in (t.get("title", "") or "").upper()}
            if not bug_tasks:
                return inferred

            sorted_vids = sorted(versions.keys())
            for i, vid in enumerate(sorted_vids):
                v = versions[vid]
                if v.get("status") != "stable" or i == 0:
                    continue
                prev_vid = sorted_vids[i-1]
                prev_v = versions[prev_vid]
                if prev_v.get("status") != "damaged":
                    continue

                fixed_files = v.get("files_changed", [])
                failed_tabs = prev_v.get("failed_tabs", [])

                for tid, t in bug_tasks.items():
                    t_wherein = (t.get("wherein", "") or "")
                    t_title = (t.get("title", "") or "")
                    for ff in fixed_files:
                        ff_base = ff.split("/")[-1]
                        if ff_base in t_wherein or ff_base in t_title:
                            inferred.append({
                                "bug_task_id": tid,
                                "bug_title": t_title[:60],
                                "fixed_in_version": vid,
                                "damaged_version": prev_vid,
                                "fixed_file": ff,
                                "failed_tabs": failed_tabs,
                                "evidence": "damaged→stable transition",
                            })

                for eid, ch in ec.items():
                    ch_ts = ch.get("timestamp", "")
                    if ch_ts and vid[:8] in ch_ts.replace("-","")[:8]:
                        ba = ch.get("before_after_values") or []
                        for bav in ba:
                            before = str(bav.get("before_value", ""))
                            after = str(bav.get("after_value", ""))
                            if any(kw in before.lower() for kw in ["except", "raise", "error"]) and \
                               any(kw in after.lower() for kw in ["try", "except", "pass", "fix"]):
                                ch_file = (ch.get("file", "") or "").split("/")[-1]
                                for tid, t in bug_tasks.items():
                                    if ch_file in (t.get("wherein", "") or "") or ch_file in (t.get("title", "") or ""):
                                        if not any(inf["bug_task_id"] == tid and inf["fixed_file"] == ch.get("file","") for inf in inferred):
                                            inferred.append({
                                                "bug_task_id": tid,
                                                "bug_title": t.get("title", "")[:60],
                                                "fixed_in_version": vid,
                                                "fixed_file": ch.get("file", ""),
                                                "evidence": f"before/after fix pattern in {eid}",
                                            })
            return inferred

        # Helper: Auto-template a raw plan doc through Project_Template_001.md format
        def _auto_template_plan(plan_path, project_type, filesync_data, output_path=None):
            """Process a raw plan doc into template format, populating from enriched_changes + py_manifest + todos.

            Args:
                plan_path: Path to the (already-organized) plan file
                project_type: Classified project type string
                filesync_data: Timeline context dict
                output_path: Optional explicit output path (e.g. Epics/{pid}.md). Default: {name}_TEMPLATED.md alongside source.

            Returns:
                Path to templated file, or None on failure
            """
            try:
                _data_root = Path(__file__).resolve().parents[2]
                content = plan_path.read_text(encoding="utf-8", errors="ignore")

                # Already templated? Skip (unless output_path given — epic refresh always regenerates).
                if not output_path and "</High_Level>:" in content and "</Diffs>:" in content:
                    return None

                # --- Load enrichment sources ---
                _vm_path = _data_root / "backup" / "version_manifest.json"
                _enriched = {}
                if _vm_path.exists():
                    _vm = json.loads(_vm_path.read_text(encoding="utf-8"))
                    _enriched = _vm.get("enriched_changes", {})

                _manifest_path = _data_root / "backup" / "py_manifest.json"
                _py_manifest = {}
                if _manifest_path.exists():
                    _py_manifest = json.loads(_manifest_path.read_text(encoding="utf-8"))

                _todos_path = _data_root / "plans" / "todos.json"
                _todos = {}
                if _todos_path.exists():
                    _todos = json.loads(_todos_path.read_text(encoding="utf-8"))

                # --- Extract references from raw content ---
                _mark_refs = re.findall(r'#\[Mark:([^\]]+)\]', content)
                _event_refs = re.findall(r'#\[Event:([^\]]+)\]', content)
                _file_refs = list(set(re.findall(r'[\w/]+\.(?:py|json|md|txt|yaml|toml)', content)))

                # Strategy 2: match enriched_changes via task_ids from todos.json
                _plan_task_ids = set()
                _plan_stem = plan_path.stem.replace("_TEMPLATED", "").replace("_", " ").lower()
                for _phase_key, _phase_data in _todos.items():
                    if isinstance(_phase_data, dict):
                        for _tk, _tv in _phase_data.items():
                            if isinstance(_tv, dict):
                                _ttl = (_tv.get("title", "") or "").lower()
                                _pid = (_tv.get("project_id", "") or "").lower()
                                _wh = (_tv.get("wherein", "") or "")
                                if (_plan_stem and (_plan_stem in _pid or _pid in _plan_stem)) or \
                                   (_plan_stem and _plan_stem in _ttl):
                                    _plan_task_ids.add(_tv.get("id", _tk))
                                    if _wh:
                                        _file_refs.append(_wh.split("/")[-1])

                # --- Build </High_Level>: from project type + first lines ---
                _title = plan_path.stem.replace("_", " ")
                _first_lines = [l.strip() for l in content.split("\n")[:10] if l.strip() and not l.startswith("#")]
                _high_level = [
                    f"- Category: {project_type.replace('_', ' ')}",
                    f"- Title: {_title}",
                    f"- Cluster: {filesync_data.get('cluster_id', 'unclustered')}",
                    f"- First Seen: {filesync_data.get('first_seen', 'unknown')}",
                    f"- Summary: {_first_lines[0] if _first_lines else 'No summary available'}",
                ]

                # --- Build </Mid_Level>: from original content (trimmed) ---
                _mid_level_lines = content.split("\n")  # Preserve ALL original lines
                _mid_level = [f"- {l}" if not l.startswith("-") else l for l in _mid_level_lines if l.strip()]

                # --- Build </Diffs>: from matched enriched_changes ---
                _diffs_entries = []
                for _eid, _ec in _enriched.items():
                    _ec_file = (_ec.get("file") or "").split("/")[-1]
                    _ec_tids = _ec.get("task_ids") or []
                    if (_ec_file and any(_ec_file in fr for fr in _file_refs)) or \
                       any(tid in _plan_task_ids for tid in _ec_tids):
                        _verb = _ec.get("verb", "modify")
                        _risk = _ec.get("risk_level", "?")
                        _methods = ", ".join(_ec.get("methods_changed", [])[:3]) or "—"
                        _tids = ", ".join(_ec.get("task_ids") or []) or "—"
                        _diffs_entries.append(
                            f"[File/Doc] - [{_ec_file}]\n"
                            f"-{_ec.get('file', _ec_file)}\n"
                            f" -Lines\n"
                            f"  -{_ec.get('lines_removed', 0)}\n"
                            f"  +{_ec.get('lines_added', 0)}\n"
                            f"-#[Event:{_eid}] ({_verb}, risk:{_risk}, tasks:{_tids})\n"
                            f" -{_methods}"
                        )

                # Also add mark/event refs found in raw text
                for _mr in _mark_refs:
                    _diffs_entries.append(f"-#[Mark:{_mr}]\n -")
                for _er in _event_refs:
                    if not any(_er in d for d in _diffs_entries):
                        _diffs_entries.append(f"-#[Event:{_er}]\n -")

                # --- Build </Provisions>: provisions_catalog (bundled) + py_manifest imports ---
                _packages = []
                _tools = []
                # Prepend bundled/installed Trainer/Provisions packages
                try:
                    _pc_path = Path(__file__).resolve().parent / "babel_data" / "inventory" / "provisions_catalog.json"
                    if _pc_path.exists():
                        _pc_data = json.loads(_pc_path.read_text(encoding='utf-8')).get('packages', [])
                        for _p in _pc_data:
                            _badge = f"[installed {_p['installed_version']}]" if _p.get('installed_version') else "[bundled]"
                            _entry = f"- {_p['name']}=={_p['version']} {_badge}"
                            if _entry not in _packages:
                                _packages.append(_entry)
                except Exception:
                    pass
                # Then add imports from py_manifest for matched files
                for _fr in _file_refs:
                    _fr_name = _fr.split("/")[-1]
                    for _mkey, _mval in _py_manifest.items():
                        if isinstance(_mval, dict) and _fr_name in _mkey:
                            _imports = _mval.get("imports", [])[:5]
                            _classes = _mval.get("classes", [])[:3]
                            if _imports:
                                _packages.extend([f"- {imp}" for imp in _imports if f"- {imp}" not in _packages])
                            if _classes:
                                _tools.extend([f"- {cls}" for cls in _classes if f"- {cls}" not in _tools])

                # --- Build </Current_Targets>: from file refs ---
                _targets_files = [f"- {fr}" for fr in _file_refs[:10]]

                # --- Build </Current_Tasks>: from matched todos ---
                _task_entries = []
                for _phase, _tblock in _todos.items():
                    if not isinstance(_tblock, dict):
                        continue
                    for _tid, _tv in _tblock.items():
                        if not isinstance(_tv, dict):
                            continue
                        _wherein = _tv.get("wherein", "")
                        if any(fr in _wherein for fr in _file_refs):
                            _title_t = _tv.get("title", _tid)
                            _status = _tv.get("status", "PENDING")
                            _task_entries.append(
                                f"-TYPE:{{'FILE'}}\n"
                                f" - {_tv.get('id', _tid)}: {_title_t} [{_status}]\n"
                                f" - wherein: {_wherein}"
                            )

                # --- Assemble template ---
                _templated = []
                _templated.append(f"</PROJECT_TEMPLATE_001>")
                _templated.append(f"###")
                _templated.append(f"</High_Level>:")
                _templated.extend(_high_level)
                _templated.append(f"")
                _templated.append(f"<High_Level>. |")
                _templated.append(f"##")
                _templated.append(f"</Mid_Level>:")
                _templated.extend(_mid_level)  # ALL original content preserved
                _templated.append(f"")
                _templated.append(f"<Mid_Level/>. |")
                _templated.append(f"##")
                _templated.append(f"</Low_Level>:")
                _templated.append(f"- (auto-generated from consolidation)")
                _templated.append(f"")
                _templated.append(f"<Low_Level/>. |")
                _templated.append(f"##")
                _templated.append(f"</Meta_Links>:")
                _templated.append(f"- Source: {plan_path.name}")
                _templated.append(f"- Cluster: {filesync_data.get('cluster_id', 'unknown')}")
                _templated.append(f"- Organized: {datetime.now().isoformat()[:10]}")
                _templated.append(f"")
                _templated.append(f"<Meta_Links/>. |")
                _templated.append(f"##")
                _templated.append(f"</Provisions>:")
                _templated.append(f"#")
                _templated.append(f"[Packages]")
                _templated.extend(_packages[:10] or ["- (none detected)"])
                _templated.append(f"#")
                _templated.append(f"[Tools/Scripts]")
                _templated.extend(_tools[:10] or ["- (none detected)"])
                _templated.append(f"")
                _templated.append(f"<Provisions/>. |")
                _templated.append(f"##")
                _templated.append(f"</Current_Targets>:")
                _templated.append(f"")
                _templated.append(f"[Files]:")
                _templated.extend(_targets_files or ["- (none referenced)"])
                _templated.append(f"")
                _templated.append(f"[Goal(s)]:")
                _templated.append(f"- {_first_lines[0] if _first_lines else 'TBD'}")
                _templated.append(f"")
                _templated.append(f"<Current_Targets/>. |")
                _templated.append(f"##")
                _templated.append(f"</Diffs>: (New/Modify/Remove)")
                _templated.append(f"#")
                if _diffs_entries:
                    _templated.extend(_diffs_entries[:15])
                else:
                    _templated.append(f"- (no enriched_changes matched)")
                _templated.append(f"")
                _templated.append(f"<Diffs/>. |")
                _templated.append(f"#")
                _templated.append(f"</Plans_manifested>:")
                _templated.append(f"-{{'{_title}'}} [TODOS: {len(_task_entries)} matched]")
                _templated.append(f"")
                _templated.append(f"<Plans_Manifested>. |")
                _templated.append(f"##")
                _templated.append(f"</Current_Tasks>:")
                if _task_entries:
                    _templated.extend(_task_entries[:10])
                else:
                    _templated.append(f"- (no tasks matched)")
                _templated.append(f"")
                _templated.append(f"<Current_Tasks>. |")
                _templated.append(f"###")

                # Write templated version
                if output_path:
                    _out_path = Path(output_path)
                    _out_path.parent.mkdir(parents=True, exist_ok=True)
                else:
                    _out_path = plan_path.with_name(plan_path.stem + "_TEMPLATED.md")
                _out_path.write_text("\n".join(_templated), encoding="utf-8")
                return _out_path

            except Exception as _e:
                logger.error(f"Auto-template error for {plan_path.name}: {_e}")
                return None

        # Expose _auto_template_plan as a toolkit method for CLI access
        self._auto_template_plan = _auto_template_plan

        # Action: Consolidate Scattered Plans with Template Validation
        def action_consolidate_plans(diff_mode: bool = False):
            """
            #[Mark:P0-PlanConsolidate] Discover scattered .md files, validate against Project_Template_1.md,
            organize by inferred type using Filesync temporal clustering.

            Args:
                diff_mode: If True, preview changes without executing (--diff)
            """
            results = []
            # Anchor to Trainer/ (3 levels up from Os_Toolkit.py: action_panel_tab → tabs → Data → Trainer)
            # Previous: self.base_dir.parent.parent resolved to /home/commander (HOME) — too broad
            babel_root = Path(__file__).resolve().parents[3]

            # #[Event:CONSOLIDATE_START]
            self._log_event("CONSOLIDATE_START", {"diff_mode": diff_mode, "babel_root": str(babel_root)})

            results.append("[*] Executing action: Consolidate Scattered Plans")
            if diff_mode:
                results.append("[DIFF MODE] Preview only - no files will be moved")
            results.append("")

            try:
                # Import PlanConsolidator via importlib — avoids sys.path mutation
                import importlib.util, sys as _sys
                _mod_name = "plan_consolidator"
                if _mod_name not in _sys.modules:
                    _pc_path = Path(__file__).parent / "babel_data" / "inventory" / "core" / "plan_consolidator.py"
                    _spec = importlib.util.spec_from_file_location(_mod_name, _pc_path)
                    _mod = importlib.util.module_from_spec(_spec)
                    _sys.modules[_mod_name] = _mod
                    _spec.loader.exec_module(_mod)
                PlanConsolidator = _sys.modules[_mod_name].PlanConsolidator

                # Step 1: Discover scattered plans
                results.append("[1/5] Discovering scattered .md files...")
                consolidator = PlanConsolidator(babel_root)
                scattered = consolidator.discover_scattered_plans()

                # #[Event:PLANS_DISCOVERED]
                self._log_event("PLANS_DISCOVERED", {"count": len(scattered)})

                results.append(f"  ✓ Found {len(scattered)} scattered .md files")

                if not scattered:
                    results.append("\n[✓] No scattered plans to consolidate!")
                    return "\n".join(results)

                # Step 2: Analyze with Filesync for temporal clustering
                results.append("\n[2/5] Analyzing with Filesync (temporal clustering)...")
                plan_contexts = []

                for i, plan_info in enumerate(scattered, 1):
                    plan_path = Path(plan_info['path'])
                    results.append(f"  [{i}/{len(scattered)}] Analyzing: {plan_path.name}")

                    # Get Filesync context
                    filesync_data = consolidator.analyze_plan_with_filesync(plan_path)

                    # #[Event:PLAN_ANALYZED]
                    self._log_event("PLAN_ANALYZED", {
                        "file": str(plan_path),
                        "cluster": filesync_data.get('cluster_id'),
                        "first_seen": filesync_data.get('first_seen')
                    })

                    # Classify project type
                    project_type = consolidator.classify_plan_type(plan_path, use_morph=False)

                    # Check template structure
                    with open(plan_path, encoding='utf-8', errors='ignore') as f:
                        content = f.read()

                    required_sections = {
                        "</High_Level>:": "High-level goals and overview",
                        "</Mid_Level>:": "Mid-level implementation details",
                        "</Diffs>:": "Code changes and file modifications",
                        "</Current_Todos>:": "Active tasks and todos"
                    }

                    missing_sections = {sec: desc for sec, desc in required_sections.items() if sec not in content}

                    plan_contexts.append({
                        'plan_info': plan_info,
                        'plan_path': plan_path,
                        'filesync_data': filesync_data,
                        'project_type': project_type,
                        'missing_sections': missing_sections
                    })

                # Step 3: Show diff/preview for each plan
                results.append("\n[3/5] Template Validation & Diff Preview")
                results.append("="*60)

                for ctx in plan_contexts[:10]:  # Show first 10 in detail
                    plan_name = ctx['plan_path'].name
                    results.append(f"\n📄 {plan_name}")
                    results.append(f"   Type: {ctx['project_type']}")
                    results.append(f"   Cluster: {ctx['filesync_data'].get('cluster_id', 'unknown')}")
                    results.append(f"   First Seen: {ctx['filesync_data'].get('first_seen', 'unknown')}")

                    if ctx['missing_sections']:
                        results.append(f"   ⚠️  Missing {len(ctx['missing_sections'])} template sections:")
                        for sec, desc in list(ctx['missing_sections'].items())[:3]:
                            results.append(f"      - {sec.strip(':')}: {desc}")

                        # #[Event:TEMPLATE_INCOMPLETE]
                        self._log_event("TEMPLATE_INCOMPLETE", {
                            "file": str(ctx['plan_path']),
                            "missing_count": len(ctx['missing_sections'])
                        })
                    else:
                        results.append(f"   ✓ Template structure complete")

                    # Show target location
                    type_dir = babel_root / "plans" / ctx['project_type'].lower()
                    cluster = ctx['filesync_data'].get('cluster_id', 'unclustered').replace("/", "_")[:30]
                    timestamp = ctx['filesync_data'].get('first_seen', '').split('T')[0].replace("-", "")
                    new_name = f"{timestamp}_{cluster}_{plan_name}"
                    target_path = type_dir / new_name

                    results.append(f"   → Target: plans/{ctx['project_type'].lower()}/{new_name}")

                if len(plan_contexts) > 10:
                    results.append(f"\n... and {len(plan_contexts) - 10} more plans")

                # Step 4: Run Filesync organize with --diff if requested
                if diff_mode:
                    results.append("\n[4/5] Filesync Dry Run (--diff)")
                    results.append("  (Skipped - manual consolidation only)")
                else:
                    results.append("\n[4/5] Organizing plans...")
                    organized_count = 0

                    for ctx in plan_contexts:
                        new_path = consolidator.organize_plan(
                            ctx['plan_path'],
                            ctx['project_type'],
                            ctx['filesync_data']
                        )

                        if new_path:
                            organized_count += 1
                            # #[Event:PLAN_MOVED]
                            self._log_event("PLAN_MOVED", {
                                "from": str(ctx['plan_path']),
                                "to": str(new_path),
                                "type": ctx['project_type']
                            })

                            # Auto-template if missing structure
                            if ctx['missing_sections']:
                                _tmpl_path = _auto_template_plan(
                                    new_path, ctx['project_type'], ctx['filesync_data']
                                )
                                if _tmpl_path:
                                    results.append(f"    📋 Templated → {_tmpl_path.name}")
                                    self._log_event("PLAN_TEMPLATED", {
                                        "source": str(new_path),
                                        "templated": str(_tmpl_path),
                                        "type": ctx['project_type']
                                    })

                    results.append(f"  ✓ Organized {organized_count}/{len(plan_contexts)} plans")

                # Step 5: Update todos.json with reformatting tasks for incomplete templates
                results.append("\n[5/5] Creating reformatting todos for incomplete templates...")
                incomplete_plans = [ctx for ctx in plan_contexts if ctx['missing_sections']]

                if incomplete_plans:
                    todo_mgr = TodoManager(self.base_dir)
                    todos = todo_mgr.load_todos()

                    for ctx in incomplete_plans:
                        # Check if todo already exists
                        todo_exists = any(
                            ctx['plan_path'].name in t.get('description', '')
                            for t in todos
                        )

                        if not todo_exists and not diff_mode:
                            todo_mgr.add_todo(
                                title=f"Reformat {ctx['plan_path'].name} to match Project_Template_1.md",
                                description=f"Missing sections: {', '.join([s.strip(':') for s in ctx['missing_sections'].keys()])}. "
                                           f"See babel_data/templates/project_templates/ for reference."
                            )

                            # #[Event:TODO_CREATED]
                            self._log_event("TODO_CREATED", {
                                "file": str(ctx['plan_path']),
                                "missing_sections": list(ctx['missing_sections'].keys())
                            })

                    results.append(f"  ✓ Created {len(incomplete_plans)} reformatting todos")
                else:
                    results.append(f"  ✓ All plans have complete template structure!")

                # #[Event:CONSOLIDATE_COMPLETE]
                self._log_event("CONSOLIDATE_COMPLETE", {
                    "total_plans": len(scattered),
                    "organized": organized_count if not diff_mode else 0,
                    "incomplete": len(incomplete_plans)
                })

                results.append("\n[✓] Plan consolidation complete!")

                if diff_mode:
                    results.append("\n💡 Run without --diff to actually consolidate plans")
                else:
                    results.append("\n💡 Run 'python3 Os_Toolkit.py latest' to see updated state")

            except Exception as e:
                error_msg = f"[✗] Consolidation error: {e}"
                results.append(error_msg)
                # #[Event:CONSOLIDATE_ERROR]
                self._log_event("CONSOLIDATE_ERROR", {"error": str(e)})
                import traceback
                results.append(traceback.format_exc())

            return "\n".join(results)

        actions['consolidate_plans'] = ConformityAction(
            action_id='consolidate_plans',
            name='Consolidate Scattered Plans',
            description='Discover, validate, and organize scattered .md files using Filesync clustering',
            impact='Medium (Moves .md files, creates reformatting todos)',
            command_func=lambda: action_consolidate_plans(diff_mode=False)
        )

        # Action: Update Memory for Session Continuity
        def action_update_memory():
            """
            Update MEMORY.md with session progress for continuity across Claude spawns.
            Captures: completed tasks, deferred todos, key findings, manifest links.
            """
            from pathlib import Path
            import json
            from datetime import datetime

            results = []
            results.append("[*] Capturing session state...")

            # 1. Get completed Claude tasks (current session)
            claude_tasks_dir = Path.home() / ".claude" / "tasks"
            completed_tasks = []
            if claude_tasks_dir.exists():
                # Find latest session
                sessions = sorted(claude_tasks_dir.iterdir(),
                                key=lambda p: p.stat().st_mtime, reverse=True)
                if sessions:
                    session_dir = sessions[0]
                    for task_file in session_dir.glob("*.json"):
                        try:
                            with open(task_file) as f:
                                task = json.load(f)
                                if task.get('status') == 'completed':
                                    completed_tasks.append(task.get('subject', task.get('title', '')))
                        except:
                            pass

            # 2. Get completed/deferred Os_Toolkit todos (updated today)
            todos_file = Path("plans/todos.json")
            completed_todos = []
            deferred_todos = []
            if todos_file.exists():
                try:
                    with open(todos_file) as f:
                        todos = json.load(f)
                        today = datetime.now().date()
                        for todo in todos:
                            updated = datetime.fromisoformat(todo.get('updated_at', '2000-01-01'))
                            if updated.date() == today:
                                if todo.get('status') == 'done':
                                    completed_todos.append(todo['title'])
                                elif todo.get('status') == 'deferred':
                                    deferred_todos.append(todo['title'])
                except:
                    pass

            # 3. Find modified files (quick check)
            import subprocess
            try:
                git_status = subprocess.run(
                    ['git', 'diff', '--name-only', 'HEAD'],
                    capture_output=True, text=True, timeout=5
                )
                modified_files = git_status.stdout.strip().split('\n') if git_status.stdout else []
                modified_files = [f for f in modified_files if f and not f.startswith('.')]
            except:
                modified_files = []

            # 4. Build memory update text
            date_str = datetime.now().strftime("%Y-%m-%d")
            update_lines = [
                f"\n### {date_str} (Today)",
                "**Focus:** Todo sync review + Auto-marking design + Memory continuity",
            ]

            if completed_tasks or completed_todos:
                update_lines.append("**Completed:**")
                for task in completed_tasks[:5]:  # Limit to 5
                    update_lines.append(f"- ✅ {task}")
                for todo in completed_todos[:3]:
                    update_lines.append(f"- ✅ {todo[:70]}...")

            if deferred_todos:
                update_lines.append("\n**Deferred:**")
                for todo in deferred_todos[:3]:
                    update_lines.append(f"- ⏸️ {todo[:70]}...")

            if modified_files:
                update_lines.append(f"\n**Files Modified:** {', '.join(modified_files[:5])}")

            update_lines.append("\n**Session Summary:** See WORK_PLAN_2026-02-08.md")
            update_lines.append("---\n")

            update_text = "\n".join(update_lines)

            # 5. Find memory file
            memory_paths = list(Path.home().glob(".claude/projects/*/memory/MEMORY.md"))
            if not memory_paths:
                return "Error: Could not find MEMORY.md file"

            memory_file = memory_paths[0]  # Use first match

            # 6. Update memory (insert after "## Recent Work" or at end of file)
            try:
                with open(memory_file, 'r') as f:
                    content = f.read()

                # Find insertion point
                if "## Recent Work" in content:
                    # Insert after "## Recent Work" header
                    parts = content.split("## Recent Work", 1)
                    if len(parts) == 2:
                        header, rest = parts
                        # Find next section or end
                        next_section = rest.find("\n## ")
                        if next_section != -1:
                            middle = rest[:next_section]
                            tail = rest[next_section:]
                            new_content = f"{header}## Recent Work{middle}{update_text}{tail}"
                        else:
                            new_content = f"{header}## Recent Work{rest}{update_text}"
                    else:
                        new_content = content + f"\n## Recent Work (Last 7 Days)\n{update_text}"
                else:
                    # Add new section before "## Implemented Solutions"
                    if "## Implemented Solutions" in content:
                        new_content = content.replace(
                            "## Implemented Solutions",
                            f"## Recent Work (Last 7 Days)\n{update_text}\n## Implemented Solutions"
                        )
                    else:
                        new_content = content + f"\n## Recent Work (Last 7 Days)\n{update_text}"

                # Write back
                with open(memory_file, 'w') as f:
                    f.write(new_content)

                results.append(f"[+] Updated memory: {memory_file}")
                results.append(f"    - Claude tasks completed: {len(completed_tasks)}")
                results.append(f"    - Os todos completed: {len(completed_todos)}")
                results.append(f"    - Deferred todos: {len(deferred_todos)}")
                results.append(f"    - Files modified: {len(modified_files)}")

            except Exception as e:
                return f"Error updating memory: {e}"

            return "\n".join(results)

        actions['update_memory'] = ConformityAction(
            action_id='update_memory',
            name='Update Memory',
            description='Update MEMORY.md with session progress for continuity.',
            impact='Low (Updates MEMORY.md)',
            command_func=action_update_memory
        )

        # Action: Update Gemini Context (GEMINI.md)
        def action_update_gemini_context():
            """
            Update GEMINI.md with session progress for continuity.
            """
            from pathlib import Path
            import json
            from datetime import datetime
            import subprocess

            results = []
            results.append("[*] Capturing session state for Gemini...")

            # 1. Get completed/deferred Os_Toolkit todos (updated today)
            todos_file = Path("plans/todos.json")
            completed_todos = []
            deferred_todos = []
            if todos_file.exists():
                try:
                    with open(todos_file) as f:
                        todos = json.load(f)
                        today = datetime.now().date()
                        for todo in todos:
                            updated = datetime.fromisoformat(todo.get('updated_at', '2000-01-01'))
                            if updated.date() == today:
                                if todo.get('status') == 'done':
                                    completed_todos.append(todo['title'])
                                elif todo.get('status') == 'deferred':
                                    deferred_todos.append(todo['title'])
                except:
                    pass

            # 2. Find modified files
            try:
                git_status = subprocess.run(
                    ['git', 'diff', '--name-only', 'HEAD'],
                    capture_output=True, text=True, timeout=5
                )
                modified_files = git_status.stdout.strip().split('\n') if git_status.stdout else []
                modified_files = [f for f in modified_files if f and not f.startswith('.')]
            except:
                modified_files = []

            # Mini-Inference for Context
            inference_cats = []
            if modified_files:
                has_gui = any(f.endswith('.py') and ('grep_flight' in f or 'gui' in f) for f in modified_files)
                has_cli = any(f.endswith('.py') and 'toolkit' in f.lower() for f in modified_files)
                has_tests = any('test' in f for f in modified_files)
                has_docs = any(f.endswith('.md') for f in modified_files)
                
                if has_gui: inference_cats.append("GUI Components")
                if has_cli: inference_cats.append("CLI Tools")
                if has_tests: inference_cats.append("Test Suite")
                if has_docs: inference_cats.append("Documentation")
                
            context_summary = f"({', '.join(inference_cats)})" if inference_cats else ""

            # 3. Build update text
            date_str = datetime.now().strftime("%Y-%m-%d %H:%M")
            update_lines = [
                f"\n### Session Update: {date_str}",
                f"- **Status:** Active",
            ]

            if completed_todos:
                update_lines.append(f"- **Completed:** {len(completed_todos)} tasks")
                for todo in completed_todos[:3]:
                    update_lines.append(f"  - ✅ {todo[:70]}...")
            
            if modified_files:
                update_lines.append(f"- **Modified:** {len(modified_files)} files {context_summary}")
                for f in modified_files[:3]:
                    update_lines.append(f"  - 📝 {f}")

            # 4. Find GEMINI.md
            # Look in parent directories
            gemini_md = None
            curr = Path.cwd()
            for _ in range(8): # Look up to 8 levels
                if (curr / "GEMINI.md").exists():
                    gemini_md = curr / "GEMINI.md"
                    break
                curr = curr.parent
            
            if not gemini_md:
                # Try absolute path fallback based on known structure
                candidates = [
                    Path.home() / "GEMINI.md",
                    Path.home() / "Desktop" / "System_Journal" / "System_Journal" / "GEMINI.md"
                ]
                for c in candidates:
                    if c.exists():
                        gemini_md = c
                        break
            
            if not gemini_md:
                return "Error: Could not find GEMINI.md in parent directories."

            # 5. Update
            try:
                with open(gemini_md, 'r') as f:
                    content = f.read()
                
                # Append to "Project Coordination Context" or similar, or just append to end
                if "## Session History" in content:
                     # Insert after header
                     parts = content.split("## Session History", 1)
                     new_content = parts[0] + "## Session History\n" + "\n".join(update_lines) + parts[1]
                else:
                     new_content = content + f"\n\n## Session History\n" + "\n".join(update_lines)
                
                with open(gemini_md, 'w') as f:
                    f.write(new_content)
                    
                results.append(f"[+] Updated Gemini Context: {gemini_md}")
                results.append(f"    - Completed: {len(completed_todos)}")
                results.append(f"    - Modified: {len(modified_files)}")

            except Exception as e:
                return f"Error updating GEMINI.md: {e}"
            
            return "\n".join(results)

        actions['update_gemini_context'] = ConformityAction(
            action_id='update_gemini_context',
            name='Update Gemini Context',
            description='Update GEMINI.md with recent session activity.',
            impact='Low (Updates GEMINI.md)',
            command_func=action_update_gemini_context
        )

        return actions

    def execute_action(self, action_id: str) -> str:
        """Execute a conformity action"""
        if action_id not in self.actions:
            return f"Error: Action {action_id} not found."
            
        action = self.actions[action_id]
        print(f"[*] Executing action: {action.name}...")
        try:
            result = action.command_func()
            self.session.add_journal_entry(
                "action_executed",
                f"Executed action {action_id}: {result}",
                ["action", action_id]
            )
            return result
        except Exception as e:
            return f"Error executing {action_id}: {e}"

    def _log_event(self, event_type: str, context: Dict[str, Any] = None):
        """
        Log an event to unified logger with #[Event:###] format

        Args:
            event_type: Type of event (e.g., "CONSOLIDATE_START", "PLAN_MOVED")
            context: Dict of contextual information
        """
        context = context or {}
        event_id = f"Event:{event_type}"

        # Log to unified logger (BABEL_LOG format)
        try:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
            unified_log = f"BABEL_LOG: [{timestamp}] [os_toolkit] [INFO] #[{event_id}] {event_type}"
            if context:
                import json
                unified_log += f" | Context: {json.dumps(context)}"

            print(unified_log)  # Output to console/logs

        except Exception:
            # Silently fail if logging unavailable
            pass

    def _save_suggested_actions(self, suggestions: List[Dict[str, Any]], confidence_scores: Dict[str, float] = None):
        """
        Save suggested actions to persistent file with confidence scoring

        Args:
            suggestions: List of action dicts from SuggestiveGrepEngine
            confidence_scores: Optional dict mapping action_id -> confidence (0.0-1.0)

        Saves to: babel_data/profile/suggested_actions.json
        """
        confidence_scores = confidence_scores or {}

        # Enrich suggestions with confidence scores and metadata
        enriched = []
        for action in suggestions:
            enriched_action = action.copy()

            # Add confidence score (default 0.5 if not provided)
            action_id = action.get('id', '')
            enriched_action['confidence'] = confidence_scores.get(action_id, 0.5)

            # Add timestamp
            enriched_action['generated_at'] = datetime.now().isoformat()

            # Calculate priority based on confidence and selected flag
            priority = enriched_action['confidence']
            if action.get('selected', False):
                priority += 0.2  # Boost selected items
            enriched_action['priority'] = min(priority, 1.0)

            enriched.append(enriched_action)

        # Sort by priority (highest first)
        enriched.sort(key=lambda x: x['priority'], reverse=True)

        # Save to file
        suggestions_file = self.base_dir.parent / "profile/suggested_actions.json"
        suggestions_file.parent.mkdir(parents=True, exist_ok=True)

        # Include metadata
        data = {
            'metadata': {
                'generated_at': datetime.now().isoformat(),
                'session_id': self.session_id,
                'count': len(enriched),
                'high_confidence_count': sum(1 for a in enriched if a['confidence'] >= 0.7),
                'schema_version': '1.0'
            },
            'actions': enriched
        }

        with open(suggestions_file, 'w') as f:
            json.dump(data, f, indent=2)

        self._log_event("ACTIONS_SAVED", {
            "count": len(enriched),
            "high_confidence": data['metadata']['high_confidence_count'],
            "path": str(suggestions_file)
        })

        return suggestions_file

    def _load_suggested_actions(self) -> Dict[str, Any]:
        """
        Load saved suggested actions from persistent file

        Returns:
            Dict with 'metadata' and 'actions' keys, or empty structure if file doesn't exist
        """
        suggestions_file = self.base_dir.parent / "profile/suggested_actions.json"

        if not suggestions_file.exists():
            return {
                'metadata': {'count': 0},
                'actions': []
            }

        try:
            with open(suggestions_file, 'r') as f:
                data = json.load(f)

            self._log_event("ACTIONS_LOADED", {
                "count": len(data.get('actions', [])),
                "path": str(suggestions_file)
            })

            return data
        except Exception as e:
            print(f"⚠️  Error loading suggested actions: {e}")
            return {
                'metadata': {'count': 0},
                'actions': []
            }

    def _get_filesync_confidence(self, action_id: str, action_context: Dict[str, Any] = None) -> float:
        """
        #[Mark:P1-DynamicConfidence] Data-driven confidence scoring using manifest + Filesync + Os_Toolkit

        Args:
            action_id: Action identifier
            action_context: Context with: scattered_plan_count, security_anomalies, todo_conflicts, file_path, etc.

        Returns:
            Confidence score (0.0-1.0) based on ACTUAL system state

        Data sources:
        1. Latest Filesync manifest: babel_data/timeline/manifests/manifest_latest.json
        2. Filesync project associations: manifest['files'][file_id]['project_association']
        3. Os_Toolkit artifact properties: self.session.artifacts[artifact_id].properties
        4. Timeline correlation: Compare modified_time across related files
        """
        action_context = action_context or {}

        # Base confidence by action type (starting point)
        base_map = {
            'backup_now': 0.85, 'run_security': 0.80, 'check_security': 0.80,
            'audit_workflow': 0.75, 'sync_todos': 0.75, 'view_conflicts': 0.70,
            'consolidate_plans': 0.50,  # Will be dynamically adjusted
            'debug_file': 0.60, 'fix_syntax': 0.70, 'add_mark': 0.50,
            'update_memory': 0.60, 'view_todos': 0.50, 'classify_events': 0.50
        }
        confidence = base_map.get(action_id, 0.5)

        # DYNAMIC ADJUSTMENTS USING MANIFEST DATA
        try:
            # Load latest Filesync manifest
            manifest_dir = self.base_dir.parent / "timeline/manifests"
            if manifest_dir.exists():
                manifests = sorted(manifest_dir.glob("manifest_*.json"),
                                 key=lambda p: p.stat().st_mtime, reverse=True)
                if manifests:
                    with open(manifests[0]) as f:
                        manifest = json.load(f)

                    # PLAN CONSOLIDATION SCORING
                    if 'consolidate' in action_id:
                        scattered_count = action_context.get('scattered_plan_count', 0)

                        # Check .md files in manifest for structure quality
                        md_files = {fid: props for fid, props in manifest.get('files', {}).items()
                                   if props.get('extension') == '.md'}

                        if md_files and scattered_count > 0:
                            # Analyze .md file placement and properties
                            top_level_md = sum(1 for f in md_files.values() if f.get('depth_from_root', 99) == 1)
                            nested_md = len(md_files) - top_level_md

                            # Check project associations
                            associated_md = sum(1 for f in md_files.values()
                                              if f.get('project_association'))
                            unassociated_md = len(md_files) - associated_md

                            # Scoring logic:
                            # - Many scattered plans → higher confidence
                            if scattered_count > 50:
                                confidence += 0.20
                            elif scattered_count > 20:
                                confidence += 0.15
                            elif scattered_count > 10:
                                confidence += 0.10

                            # - Many unassociated .md files → needs consolidation
                            if unassociated_md > 30:
                                confidence += 0.10

                            # - Top-level .md files (likely scattered docs) → boost
                            if top_level_md > 15:
                                confidence += 0.08

                    # SECURITY ACTION SCORING
                    elif 'security' in action_id:
                        if action_context.get('security_anomalies', False):
                            confidence += 0.10

                        # Check for external network connections in manifest
                        # (Future: read from manifest statistics)

                    # TODO SYNC ACTION SCORING
                    elif 'sync' in action_id or 'conflict' in action_id:
                        todo_conflicts = action_context.get('todo_conflicts', 0)
                        if todo_conflicts > 10:
                            confidence += 0.15
                        elif todo_conflicts > 5:
                            confidence += 0.10
                        elif todo_conflicts > 0:
                            confidence += 0.05

                    # FILE-SPECIFIC ACTION SCORING (mark, debug, backup)
                    elif action_id.startswith(('mark_', 'debug_', 'backup_')):
                        file_path = action_context.get('file_path')
                        if file_path:
                            # Find file in manifest
                            file_entry = next((f for f in manifest.get('files', {}).values()
                                             if file_path in f.get('original_path', '')), None)

                            if file_entry:
                                # Check if file has project association
                                if file_entry.get('project_association'):
                                    confidence += 0.15  # Active project file

                                # Check if file is recently modified
                                mtime = file_entry.get('modified_time', '')
                                if mtime:
                                    try:
                                        from datetime import datetime, timedelta
                                        mod_dt = datetime.fromisoformat(mtime.replace('Z', '+00:00'))
                                        if datetime.now().astimezone() - mod_dt < timedelta(hours=24):
                                            confidence += 0.10  # Recent activity
                                    except:
                                        pass

                                # Check file category from Filesync
                                category = file_entry.get('category', '')
                                if category in ['source_code', 'script']:
                                    confidence += 0.05  # Core code files

        except Exception as e:
            # Fallback to basic scoring if manifest unavailable
            self._log_event("CONFIDENCE_CALC_ERROR", {"action_id": action_id, "error": str(e)})
            pass

        # Clamp to Filesync correction system range (0.4-0.85)
        return min(max(confidence, 0.4), 0.85)

    def _init_directories(self):
        """Initialize toolkit directory structure"""
        self.session_dir = self.base_dir / "sessions"
        self.manifest_dir = self.base_dir / "manifests"
        self.journal_dir = self.base_dir / "journals"
        self.schema_dir = self.base_dir / "schemas"
        self.log_dir = self.base_dir / "logs"
        self.export_dir = self.base_dir / "exports"
        
        directories = [
            self.session_dir, self.manifest_dir, self.journal_dir,
            self.schema_dir, self.log_dir, self.export_dir
        ]
        
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)
        
        # Save schema
        schema_file = self.schema_dir / "taxonomic_schema.json"
        if not schema_file.exists():
            with open(schema_file, 'w') as f:
                json.dump(SCHEMA_DEFINITION, f, indent=2)
    
    def _detect_os(self) -> OSType:
        """Detect operating system type"""
        system = platform.system().lower()
        
        if 'linux' in system:
            return OSType.LINUX
        elif 'windows' in system or 'win32' in system:
            return OSType.WINDOWS
        elif 'darwin' in system:
            return OSType.MACOS
        elif 'bsd' in system:
            return OSType.BSD
        elif 'sunos' in system or 'solaris' in system:
            return OSType.SOLARIS
        else:
            return OSType.UNKNOWN
    
    def _generate_session_id(self) -> str:
        """Generate a unique session ID"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        hostname_short = self.hostname.split('.')[0][:8]
        return f"{timestamp}_{hostname_short}_{uuid.uuid4().hex[:6]}"
    
    def _session_exists(self, session_id: str) -> bool:
        """Check if session exists"""
        session_dir = self.session_dir / session_id
        return session_dir.exists() and (session_dir / 'metadata.json').exists()

    @staticmethod
    def find_latest_session(base_dir: Path) -> Optional[str]:
        """Find the latest session ID in base_dir/sessions/, preferring babel_catalog_* sessions."""
        sessions_dir = base_dir / "sessions"
        if not sessions_dir.exists():
            return None

        # Collect all valid session dirs (must have metadata.json)
        catalog_sessions = []
        other_sessions = []
        for d in sessions_dir.iterdir():
            if d.is_dir() and (d / 'metadata.json').exists():
                if d.name.startswith('babel_catalog_'):
                    catalog_sessions.append(d.name)
                else:
                    other_sessions.append(d.name)

        # Prefer babel_catalog sessions (they have the richest data), fall back to any
        pool = sorted(catalog_sessions) if catalog_sessions else sorted(other_sessions)
        return pool[-1] if pool else None
    
    def _create_new_session(self):
        """Create a new analysis session"""
        self.session = Session(
            session_id=self.session_id,
            session_name=f"Session_{self.session_id}",
            created_at=datetime.now().isoformat(),
            updated_at=datetime.now().isoformat(),
            os_type=self.os_type,
            hostname=self.hostname,
            architecture=self.architecture
        )
        
        # Initialize taxonomic tree with root nodes
        self._initialize_taxonomic_tree()
        
        # Load system verbs
        self._load_system_verbs()
        
        # Start journal
        self._start_journal()
        
        print(f"[+] Created new session: {self.session_id}")
    
    def _load_session(self, session_id: str):
        """Load an existing session"""
        session_dir = self.session_dir / session_id
        
        try:
            with open(session_dir / 'metadata.json', 'r') as f:
                metadata = json.load(f)
            
            # Reconstruct session
            self.session = Session(
                session_id=metadata['session_id'],
                session_name=metadata['session_name'],
                created_at=metadata['created_at'],
                updated_at=metadata['updated_at'],
                os_type=OSType(metadata['os_type']),
                hostname=metadata['hostname'],
                architecture=metadata['architecture']
            )
            
            # Load taxonomic tree
            with open(session_dir / 'taxonomic_tree.json', 'r') as f:
                tree_data = json.load(f)
                for node_id, node_data in tree_data.items():
                    # Determine taxonomy type from either Hardware or Software Enums
                    taxonomy_val = node_data['taxonomy_type']
                    taxonomy_type = taxonomy_val
                    try:
                        taxonomy_type = HardwareTaxonomy(taxonomy_val)
                    except ValueError:
                        try:
                            taxonomy_type = SoftwareTaxonomy(taxonomy_val)
                        except ValueError:
                            pass

                    node = TaxonomicNode(
                        node_id=node_data['node_id'],
                        name=node_data['name'],
                        taxonomy_type=taxonomy_type,
                        sixw1h=SixW1H(**node_data['sixw1h']),
                        parent_id=node_data['parent_id'],
                        children_ids=node_data['children_ids'],
                        attributes=node_data['attributes'],
                        relationships=node_data['relationships']
                    )
                    self.session.taxonomic_tree[node_id] = node
            
            # Load artifacts
            with open(session_dir / 'artifacts.json', 'r') as f:
                artifacts_data = json.load(f)
                for artifact_id, artifact_data in artifacts_data.items():
                    artifact = ForensicArtifact(
                        artifact_id=artifact_data['artifact_id'],
                        artifact_type=ArtifactType(artifact_data['artifact_type']),
                        sixw1h=SixW1H(**artifact_data['sixw1h']),
                        timestamp_created=artifact_data['timestamps']['created'],
                        timestamp_modified=artifact_data['timestamps']['modified'],
                        timestamp_accessed=artifact_data['timestamps']['accessed'],
                        hash_md5=artifact_data['hashes']['md5'],
                        hash_sha1=artifact_data['hashes']['sha1'],
                        hash_sha256=artifact_data['hashes']['sha256'],
                        security_context=SecurityContext(artifact_data['security']['context']),
                        owner_uid=artifact_data['security']['owner_uid'],
                        owner_gid=artifact_data['security']['owner_gid'],
                        permissions=artifact_data['security']['permissions'],
                        taxonomic_node_id=artifact_data['taxonomic_link'],
                        properties=artifact_data['properties'],
                        custody_chain=artifact_data['custody_chain'],
                        size_bytes=artifact_data['size_bytes']
                    )
                    self.session.artifacts[artifact_id] = artifact
            
            # Load verbs
            with open(session_dir / 'verbs.json', 'r') as f:
                verbs_data = json.load(f)
                for verb_id, verb_data in verbs_data.items():
                    verb = SystemVerb(
                        verb_id=verb_data['verb_id'],
                        name=verb_data['name'],
                        domain=VerbDomain(verb_data['domain']),
                        os_type=OSType(verb_data['os_type']),
                        sixw1h=SixW1H(**verb_data['sixw1h']),
                        native_syntax=verb_data['native_syntax'],
                        arguments=verb_data['arguments'],
                        options=verb_data['options'],
                        equivalents={OSType(k): v for k, v in verb_data['equivalents'].items()},
                        dependencies=verb_data['dependencies'],
                        required_permissions=verb_data['required_permissions'],
                        examples=verb_data['examples']
                    )
                    self.session.verbs[verb_id] = verb
            
            # Load journal
            journal_file = session_dir / 'journal.jsonl'
            if journal_file.exists():
                with open(journal_file, 'r') as f:
                    for line in f:
                        if line.strip():
                            self.session.journal_entries.append(json.loads(line.strip()))
            
            # Load query history
            queries_file = session_dir / 'queries.jsonl'
            if queries_file.exists():
                with open(queries_file, 'r') as f:
                    for line in f:
                        if line.strip():
                            self.session.query_history.append(json.loads(line.strip()))
            
            # Rebuild path and string indexes after loading artifacts
            for artifact_id, artifact in self.session.artifacts.items():
                # Consistently extract path from sixw1h.where
                if artifact.artifact_type == ArtifactType.FILE and "Path:" in artifact.sixw1h.where:
                    path_from_6w1h = artifact.sixw1h.where.split("Path: ", 1)[1].split(",", 1)[0].strip()
                    self.path_index[path_from_6w1h] = artifact_id

                if artifact.properties.get('content_analysis', {}).get('strings'):
                    for s in artifact.properties['content_analysis']['strings'][:100]:
                        self.string_index[s].append(artifact_id)

            print(f"[+] Loaded existing session: {session_id}")
            
        except Exception as e:
            print(f"[-] Error loading session: {e}")
            self._create_new_session()
    
    def _initialize_taxonomic_tree(self):
        """Initialize the taxonomic tree with root nodes"""
        # System root
        root_node = TaxonomicNode(
            node_id="system_root",
            name=f"System: {self.hostname}",
            taxonomy_type=HardwareTaxonomy.FIRMWARE,
            sixw1h=SixW1H(
                what=f"Computer System: {self.hostname}",
                why="Hardware and software platform",
                who="System Manufacturer",
                where=f"Location: {self.hostname}",
                when=f"Boot time: {self._get_boot_time()}",
                which=f"OS: {self.os_type.value}, Arch: {self.architecture}",
                how="Integrated hardware and software components"
            )
        )
        self.session.taxonomic_tree["system_root"] = root_node
        
        # Hardware branch
        hardware_node = TaxonomicNode(
            node_id="hardware_branch",
            name="Hardware Components",
            taxonomy_type=HardwareTaxonomy.CONTROLLER,
            sixw1h=SixW1H(
                what="Hardware subsystem",
                why="Physical and virtual hardware resources",
                who="Various manufacturers",
                where="Internal system components",
                when="System assembly time",
                which="Processors, memory, storage, etc.",
                how="Interconnected via buses and controllers"
            ),
            parent_id="system_root"
        )
        self.session.taxonomic_tree["hardware_branch"] = hardware_node
        root_node.add_child("hardware_branch")
        
        # Software branch
        software_node = TaxonomicNode(
            node_id="software_branch",
            name="Software Components",
            taxonomy_type=SoftwareTaxonomy.OS_SYSTEM,
            sixw1h=SixW1H(
                what="Software subsystem",
                why="Operating system, applications, services",
                who="Various developers and vendors",
                where="Installed on storage devices",
                when="Installation and update times",
                which="OS, apps, libraries, drivers, etc.",
                how="Executed by processor, loaded into memory"
            ),
            parent_id="system_root"
        )
        self.session.taxonomic_tree["software_branch"] = software_node
        root_node.add_child("software_branch")
    
    def _load_universal_taxonomy(self):
        """Load universal taxonomy and regex library from schemas"""
        tax_path = self.schema_dir / "universal_taxonomy.json"
        reg_path = self.schema_dir / "master_regex.json"
        
        if tax_path.exists():
            try:
                with open(tax_path, 'r', encoding='utf-8') as f:
                    self.taxonomy = json.load(f)
            except Exception as e:
                print(f"[!] Error loading taxonomy: {e}")
                
        if reg_path.exists():
            try:
                with open(reg_path, 'r', encoding='utf-8') as f:
                    self.regex_library = json.load(f)
            except Exception as e:
                print(f"[!] Error loading regex library: {e}")

    def _generate_6w1h(self, what: str, category: str = "general") -> SixW1H:
        """Generate 6W1H data using the Universal Taxonomy"""
        sixw1h = SixW1H(what=what)
        
        def find_in_dict(d, target):
            if not isinstance(d, dict): return None
            for k, v in d.items():
                if target.lower() in k.lower() or k.lower() in target.lower():
                    if isinstance(v, str): return v
                if isinstance(v, dict):
                    res = find_in_dict(v, target)
                    if res: return res
            return None

        # 1. Search taxonomy for "Why" (Description)
        if self.taxonomy:
            sixw1h.why = find_in_dict(self.taxonomy, category) or ""

        # 2. Search regex library for "Which" (Classification)
        if self.regex_library:
            for level, patterns in self.regex_library.items():
                for p_name, p_regex in patterns.items():
                    try:
                        if re.search(p_regex, what, re.IGNORECASE):
                            sixw1h.which = f"{level} ({p_name})"
                            break
                    except:
                        continue
                if sixw1h.which: break

        # 3. Default fallbacks
        sixw1h.who = f"{self.os_type.value} system"
        sixw1h.when = datetime.now().isoformat()
        sixw1h.where = "Local Environment"
        sixw1h.how = f"Identified via {category} scan"
        
        return sixw1h

    def _load_verb_mappings(self) -> Dict[str, Dict[str, Any]]:
        """Load verb mappings for current OS"""
        base_verbs = {
            OSType.LINUX.value: {
                'system': {
                    'uname': {'args': ['-a', '-r', '-m'], 'desc': 'System information'},
                    'hostname': {'args': [], 'desc': 'Display/set hostname'},
                    'uptime': {'args': [], 'desc': 'System uptime'},
                    'dmesg': {'args': ['-T', '-w'], 'desc': 'Kernel messages'},
                    'shutdown': {'args': ['-h', '-r', 'now'], 'desc': 'Shutdown/reboot'},
                    'reboot': {'args': [], 'desc': 'Reboot system'},
                },
                'filesystem': {
                    'ls': {'args': ['-l', '-a', '-h'], 'desc': 'List directory'},
                    'cd': {'args': ['path'], 'desc': 'Change directory'},
                    'pwd': {'args': [], 'desc': 'Print working directory'},
                    'cp': {'args': ['-r', '-v'], 'desc': 'Copy files'},
                    'mv': {'args': [], 'desc': 'Move/rename files'},
                    'rm': {'args': ['-r', '-f', '-v'], 'desc': 'Remove files'},
                    'mkdir': {'args': ['-p', '-v'], 'desc': 'Create directory'},
                    'find': {'args': ['-name', '-type', '-exec'], 'desc': 'Find files'},
                    'grep': {'args': ['-r', '-i', '-n'], 'desc': 'Search text'},
                },
                'process': {
                    'ps': {'args': ['aux', '-ef'], 'desc': 'Process status'},
                    'top': {'args': [], 'desc': 'Interactive process viewer'},
                    'kill': {'args': ['-9', '-15'], 'desc': 'Terminate process'},
                    'pkill': {'args': [], 'desc': 'Kill by name'},
                    'nice': {'args': ['-n'], 'desc': 'Set priority'},
                    'renice': {'args': [], 'desc': 'Change priority'},
                },
                'hardware': {
                    'lspci': {'args': ['-v', '-k'], 'desc': 'PCI devices'},
                    'lsusb': {'args': ['-v'], 'desc': 'USB devices'},
                    'lscpu': {'args': [], 'desc': 'CPU information'},
                    'lsblk': {'args': [], 'desc': 'Block devices'},
                    'free': {'args': ['-h', '-m'], 'desc': 'Memory usage'},
                    'dmidecode': {'args': ['-t'], 'desc': 'DMI table decoder'},
                },
                'network': {
                    'ip': {'args': ['addr', 'link', 'route'], 'desc': 'Network configuration'},
                    'ifconfig': {'args': [], 'desc': 'Interface configuration'},
                    'netstat': {'args': ['-tulpn', '-r'], 'desc': 'Network statistics'},
                    'ss': {'args': ['-tulpn'], 'desc': 'Socket statistics'},
                    'ping': {'args': ['-c', '-i'], 'desc': 'Network connectivity'},
                    'traceroute': {'args': [], 'desc': 'Trace network route'},
                }
            },
            OSType.WINDOWS.value: {
                'system': {
                    'systeminfo': {'args': [], 'desc': 'System information'},
                    'hostname': {'args': [], 'desc': 'Display hostname'},
                    'wmic os': {'args': ['get'], 'desc': 'OS information'},
                    'shutdown': {'args': ['/s', '/r', '/t'], 'desc': 'Shutdown/reboot'},
                    'date': {'args': [], 'desc': 'Display/set date'},
                    'time': {'args': [], 'desc': 'Display/set time'},
                },
                'filesystem': {
                    'dir': {'args': ['/p', '/w', '/s'], 'desc': 'List directory'},
                    'cd': {'args': [], 'desc': 'Change directory'},
                    'copy': {'args': [], 'desc': 'Copy files'},
                    'move': {'args': [], 'desc': 'Move files'},
                    'del': {'args': ['/s', '/q'], 'desc': 'Delete files'},
                    'rmdir': {'args': ['/s', '/q'], 'desc': 'Remove directory'},
                    'where': {'args': ['/r'], 'desc': 'Find files'},
                    'findstr': {'args': ['/i', '/s'], 'desc': 'Search text'},
                },
                'process': {
                    'tasklist': {'args': ['/v', '/svc'], 'desc': 'Process list'},
                    'taskkill': {'args': ['/pid', '/im', '/f'], 'desc': 'Terminate process'},
                    'wmic process': {'args': ['list', 'get', 'delete'], 'desc': 'Process management'},
                },
                'hardware': {
                    'wmic cpu': {'args': ['get'], 'desc': 'CPU information'},
                    'wmic memorychip': {'args': ['get'], 'desc': 'Memory information'},
                    'wmic diskdrive': {'args': ['get'], 'desc': 'Disk information'},
                    'wmic bios': {'args': ['get'], 'desc': 'BIOS information'},
                    'driverquery': {'args': ['/v'], 'desc': 'Driver information'},
                },
                'network': {
                    'ipconfig': {'args': ['/all'], 'desc': 'IP configuration'},
                    'netstat': {'args': ['-ano'], 'desc': 'Network statistics'},
                    'ping': {'args': ['-n', '-t'], 'desc': 'Network connectivity'},
                    'tracert': {'args': [], 'desc': 'Trace route'},
                    'netsh': {'args': [], 'desc': 'Network shell'},
                }
            }
        }
        
        return base_verbs.get(self.os_type.value, {})
    
    def _load_system_verbs(self):
        """Load and classify system verbs"""
        os_key = self.os_type.value
        
        for domain, verbs in self.verb_mappings.items():
            for verb_name, verb_info in verbs.items():
                verb_id = f"verb_{domain}_{verb_name}"
                
                # Create 6W1H for verb using Universal Taxonomy
                sixw1h = self._generate_6w1h(verb_name, domain)
                sixw1h.where = f"Command path: {self._find_command_path(verb_name)}"
                sixw1h.how = f"Arguments: {', '.join(verb_info['args'])}"
                
                # Enrich Why if desc is better
                if verb_info['desc']:
                    sixw1h.why = f"{sixw1h.why} | {verb_info['desc']}" if sixw1h.why else verb_info['desc']
                
                # Create SystemVerb
                verb = SystemVerb(
                    verb_id=verb_id,
                    name=verb_name,
                    domain=VerbDomain(domain),
                    os_type=self.os_type,
                    sixw1h=sixw1h,
                    native_syntax=f"{verb_name} [options]",
                    arguments=verb_info['args'],
                    options={arg: "See documentation" for arg in verb_info['args']},
                    examples=[f"{verb_name} {arg}" for arg in verb_info['args'][:2]]
                )
                
                self.session.verbs[verb_id] = verb
    
    def _start_journal(self):
        """Start session journal"""
        journal_file = self.journal_dir / f"journal_{self.session_id}.jsonl"
        self.journal_file = journal_file
        
        # Initial journal entry
        self.session.add_journal_entry(
            "session_start",
            f"Forensic OS Toolkit session started for {self.hostname}",
            ["session", "start", self.os_type.value]
        )
    
    def _get_boot_time(self) -> str:
        """Get system boot time"""
        try:
            if self.os_type == OSType.LINUX:
                with open('/proc/stat', 'r') as f:
                    for line in f:
                        if line.startswith('btime'):
                            timestamp = int(line.split()[1])
                            return datetime.fromtimestamp(timestamp).isoformat()
        except:
            pass
        return "Unknown"
    
    def _find_command_path(self, command: str) -> str:
        """Find path of a command"""
        try:
            return shutil.which(command) or "Unknown"
        except:
            return "Unknown"
    
    # ============================================================================
    # CORE ANALYSIS METHODS
    # ============================================================================
    
    def _analyze_active_connections(self):
        """Analyze active network connections"""
        print("  [-] Analyzing active connections...")
        
        try:
            # Use ss command (faster than netstat)
            # Format: State, Recv-Q, Send-Q, Local Address:Port, Peer Address:Port, Process
            cmd = ['ss', '-tunap'] 
            if self.os_type == OSType.WINDOWS:
                return # Placeholder
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')
                
                for line in lines[1:]: # Skip header
                    parts = line.split()
                    if len(parts) < 5: 
                        continue
                        
                    state = parts[0]
                    if state not in ['ESTAB', 'LISTEN']:
                        continue
                        
                    local_addr = parts[4]
                    peer_addr = parts[5]
                    process_info = parts[6] if len(parts) > 6 else "Unknown"
                    
                    # Create artifact ID
                    conn_hash = hashlib.md5(f"{local_addr}-{peer_addr}".encode()).hexdigest()[:8]
                    artifact_id = f"conn_{conn_hash}_{self.session_id}"

                    # P0-3: Check IP trust level
                    peer_ip = peer_addr.split(':')[0]  # Extract IP from addr:port
                    ip_trust = self.trust_registry.check_ip_trust(peer_ip, verify_dns=False)

                    # Generate 6W1H
                    sixw1h = self._generate_6w1h(f"Connection: {local_addr} -> {peer_addr}", "network_connection")
                    sixw1h.who = f"Process: {process_info}"
                    sixw1h.where = f"Local: {local_addr}"
                    sixw1h.when = datetime.now().isoformat()
                    sixw1h.which = f"State: {state}, Peer: {peer_addr}"
                    sixw1h.how = "TCP/UDP Protocol"
                    
                    # Create Artifact
                    artifact = ForensicArtifact(
                        artifact_id=artifact_id,
                        artifact_type=ArtifactType.NETWORK_CONN,
                        sixw1h=sixw1h,
                        timestamp_created=datetime.now().isoformat(),
                        timestamp_modified=datetime.now().isoformat(),
                        timestamp_accessed=datetime.now().isoformat(),
                        security_context=SecurityContext.THIRD_PARTY if '127.0.0.1' not in peer_addr else SecurityContext.SYSTEM_TRUSTED,
                        properties={
                            'state': state,
                            'local_addr': local_addr,
                            'peer_addr': peer_addr,
                            'process_info': process_info,
                            # P0-3: Telemetry tracking for network connections
                            'telemetry': {
                                'peer_ip': peer_ip,
                                'ip_trust_level': ip_trust,
                                'first_seen_session': self.session_id,
                                'first_seen_timestamp': datetime.now().isoformat(),
                                'verified': ip_trust in ['native', 'trusted']
                            }
                        }
                    )
                    
                    self.session.artifacts[artifact_id] = artifact
                    
                    # Journal external connections
                    if '127.0.0.1' not in peer_addr and '::1' not in peer_addr and state == 'ESTAB':
                        self.session.add_journal_entry(
                            "connection_detected",
                            f"Active external connection: {local_addr} -> {peer_addr} ({process_info})",
                            ["network", "external", state]
                        )

        except Exception as e:
            print(f"    [!] Connection analysis error: {e}")

    def analyze_system_baseline(self, depth: int = 2):
        """Perform comprehensive system analysis"""
        print(f"[*] Starting system baseline analysis (depth: {depth})...")
        
        start_time = time.time()
        
        # Hardware analysis
        self._analyze_hardware()
        
        # Software analysis
        self._analyze_software()
        
        # Network analysis
        self._analyze_network()
        
        # User analysis
        self._analyze_users()
        
        # File system analysis (limited for performance)
        if depth >= 2:
            self._analyze_critical_paths()
        
        if depth >= 1:
            self._analyze_processes()
        
        elapsed = time.time() - start_time
        print(f"[+] System baseline analysis completed in {elapsed:.2f} seconds")
        
        self.session.add_journal_entry(
            "analysis_complete",
            f"System baseline analysis completed. Depth: {depth}, Duration: {elapsed:.2f}s",
            ["analysis", "baseline", f"depth_{depth}"]
        )
    
    def _analyze_hardware(self):
        """Analyze hardware components"""
        print("  [-] Analyzing hardware...")
        
        hardware_methods = {
            'cpu': self._analyze_cpu,
            'memory': self._analyze_memory,
            'storage': self._analyze_storage,
            'network_hw': self._analyze_network_hardware,
            'pci': self._analyze_pci_devices,
            'usb': self._analyze_usb_devices,
        }
        
        for name, method in hardware_methods.items():
            try:
                method()
            except Exception as e:
                print(f"    [!] Error in {name}: {e}")
    
    def _analyze_cpu(self):
        """Analyze CPU information"""
        if self.os_type == OSType.LINUX:
            try:
                cpu_info = {}
                with open('/proc/cpuinfo', 'r') as f:
                    for line in f:
                        if ':' in line:
                            key, value = line.split(':', 1)
                            cpu_info[key.strip()] = value.strip()
                
                if cpu_info:
                    node_id = f"cpu_{cpu_info.get('processor', '0')}"
                    model_name = cpu_info.get('model name', 'Unknown CPU')
                    
                    # Generate 6W1H from Universal Taxonomy
                    sixw1h = self._generate_6w1h(model_name, "hardware_software")
                    sixw1h.who = cpu_info.get('vendor_id', 'Unknown manufacturer')
                    sixw1h.where = "CPU socket on motherboard"
                    sixw1h.which = f"Model: {model_name}, Cores: {cpu_info.get('cpu cores', 'Unknown')}"
                    sixw1h.how = f"Architecture: {cpu_info.get('architecture', 'Unknown')}, Frequency: {cpu_info.get('cpu MHz', 'Unknown')} MHz"
                    
                    node = TaxonomicNode(
                        node_id=node_id,
                        name=cpu_info.get('model name', 'CPU'),
                        taxonomy_type=HardwareTaxonomy.PROCESSOR,
                        sixw1h=sixw1h,
                        parent_id="hardware_branch",
                        attributes=cpu_info
                    )
                    
                    self.session.taxonomic_tree[node_id] = node
                    self.session.taxonomic_tree["hardware_branch"].add_child(node_id)
                    
            except Exception as e:
                print(f"    [!] CPU analysis error: {e}")
    
    def _analyze_memory(self):
        """Analyze memory information"""
        if self.os_type == OSType.LINUX:
            try:
                mem_info = {}
                with open('/proc/meminfo', 'r') as f:
                    for line in f:
                        if ':' in line:
                            key, value = line.split(':', 1)
                            mem_info[key.strip()] = value.strip()
                
                if mem_info:
                    node_id = "memory_system"
                    
                    # Generate 6W1H from Universal Taxonomy
                    sixw1h = self._generate_6w1h("System Memory (RAM)", "hardware_software")
                    sixw1h.where = "Memory slots on motherboard"
                    sixw1h.which = f"Total: {mem_info.get('MemTotal', 'Unknown')}, Type: DRAM"
                    sixw1h.how = "Connected via memory bus, accessed by memory controller"
                    
                    node = TaxonomicNode(
                        node_id=node_id,
                        name="System Memory",
                        taxonomy_type=HardwareTaxonomy.MEMORY,
                        sixw1h=sixw1h,
                        parent_id="hardware_branch",
                        attributes=mem_info
                    )
                    
                    self.session.taxonomic_tree[node_id] = node
                    self.session.taxonomic_tree["hardware_branch"].add_child(node_id)
                    
            except Exception as e:
                print(f"    [!] Memory analysis error: {e}")
    
    def _analyze_storage(self):
        """Analyze storage devices"""
        if self.os_type == OSType.LINUX:
            try:
                result = subprocess.run(['lsblk', '-o', 'NAME,TYPE,SIZE,MODEL,VENDOR', '--json'],
                                      capture_output=True, text=True)
                if result.returncode == 0:
                    data = json.loads(result.stdout)
                    for i, device in enumerate(data.get('blockdevices', [])):
                        node_id = f"storage_{device.get('name', f'dev_{i}')}"
                        model = device.get('model', 'Unknown')
                        
                        # Generate 6W1H from Universal Taxonomy
                        sixw1h = self._generate_6w1h(f"Storage device: {model}", "hardware_software")
                        sixw1h.who = device.get('vendor', 'Unknown manufacturer')
                        sixw1h.where = f"Device: /dev/{device.get('name', 'unknown')}"
                        sixw1h.which = f"Type: {device.get('type', 'Unknown')}, Size: {device.get('size', 'Unknown')}"
                        sixw1h.how = "Connected via SATA/NVMe/USB interface"
                        
                        node = TaxonomicNode(
                            node_id=node_id,
                            name=f"Storage: {device.get('name')}",
                            taxonomy_type=HardwareTaxonomy.STORAGE,
                            sixw1h=sixw1h,
                            parent_id="hardware_branch",
                            attributes=device
                        )
                        
                        self.session.taxonomic_tree[node_id] = node
                        self.session.taxonomic_tree["hardware_branch"].add_child(node_id)
                        
            except Exception as e:
                print(f"    [!] Storage analysis error: {e}")

    def _analyze_network_hardware(self):
        """Analyze network hardware interfaces"""
        if self.os_type == OSType.LINUX:
            try:
                if os.path.exists('/sys/class/net'):
                    for interface in os.listdir('/sys/class/net'):
                        node_id = f"net_hw_{interface}"
                        
                        # Get address if possible
                        address = "Unknown"
                        addr_path = f"/sys/class/net/{interface}/address"
                        if os.path.exists(addr_path):
                            with open(addr_path, 'r') as f:
                                address = f.read().strip()
                        
                        sixw1h = SixW1H(
                            what=f"Network Interface: {interface}",
                            why="Network communication hardware",
                            who="System Hardware",
                            where=f"/sys/class/net/{interface}",
                            when=f"Detected: {datetime.now().isoformat()}",
                            which=f"MAC: {address}",
                            how="Handles data packets"
                        )
                        
                        node = TaxonomicNode(
                            node_id=node_id,
                            name=interface,
                            taxonomy_type=HardwareTaxonomy.CONTROLLER,
                            sixw1h=sixw1h,
                            parent_id="hardware_branch",
                            attributes={'mac': address}
                        )
                        
                        self.session.taxonomic_tree[node_id] = node
                        self.session.taxonomic_tree["hardware_branch"].add_child(node_id)
            except Exception as e:
                print(f"    [!] Network hardware analysis error: {e}")

    def _analyze_pci_devices(self):
        """Analyze PCI devices (Placeholder)"""
        # TODO: Implement lspci parsing
        pass

    def _analyze_usb_devices(self):
        """Analyze USB devices (Placeholder)"""
        # TODO: Implement lsusb parsing
        pass
    
    def _analyze_software(self):
        """Analyze software components"""
        print("  [-] Analyzing software...")
        
        # Analyze installed packages
        self._analyze_packages()
        
        # Analyze running services
        self._analyze_services()
        
        # Analyze critical system files
        self._analyze_system_files()
    
    def _analyze_packages(self):
        """Analyze installed packages"""
        packages = []
        
        if self.os_type == OSType.LINUX:
            # Try different package managers
            package_cmds = [
                (['dpkg', '-l'], 'deb'),
                (['rpm', '-qa'], 'rpm'),
                (['pacman', '-Q'], 'arch'),
                (['apk', 'info'], 'alpine'),
            ]
            
            for cmd, pkg_type in package_cmds:
                try:
                    result = subprocess.run(cmd, capture_output=True, text=True)
                    if result.returncode == 0:
                        lines = result.stdout.strip().split('\n')
                        for line in lines[5:]:  # Skip headers
                            if line:
                                parts = line.split()
                                if len(parts) >= 2:
                                    pkg_name = parts[1]
                                    packages.append({
                                        'name': pkg_name,
                                        'type': pkg_type,
                                        'manager': cmd[0]
                                    })
                        break
                except:
                    continue
        
        # Create taxonomic nodes for packages
        for i, pkg in enumerate(packages[:50]):  # Limit to 50 packages
            node_id = f"package_{i:04d}"
            pkg_name = pkg['name']
            
            # Generate 6W1H from Universal Taxonomy
            sixw1h = self._generate_6w1h(f"Package: {pkg_name}", "application")
            sixw1h.who = "Package maintainer"
            sixw1h.where = f"Installed via {pkg['manager']}"
            sixw1h.which = f"Type: {pkg['type']}, Manager: {pkg['manager']}"
            sixw1h.how = "Installed via package manager, files in system directories"
            
            node = TaxonomicNode(
                node_id=node_id,
                name=pkg['name'],
                taxonomy_type=SoftwareTaxonomy.APPLICATION,
                sixw1h=sixw1h,
                parent_id="software_branch",
                attributes=pkg
            )
            
            self.session.taxonomic_tree[node_id] = node
            self.session.taxonomic_tree["software_branch"].add_child(node_id)

    def _analyze_services(self):
        """Analyze running services (Placeholder)"""
        # TODO: Implement systemctl/service parsing
        pass

    def _analyze_system_files(self):
        """Analyze critical system files (Placeholder)"""
        # TODO: Implement hash analysis of critical files
        pass
    
    def _analyze_network(self):
        """Analyze network configuration"""
        print("  [-] Analyzing network...")
        
        if self.os_type == OSType.LINUX:
            try:
                # Get network interfaces
                result = subprocess.run(['ip', 'addr', 'show'], capture_output=True, text=True)
                if result.returncode == 0:
                    interfaces = []
                    current_iface = {}
                    
                    for line in result.stdout.split('\n'):
                        if not line.startswith(' '):
                            if current_iface:
                                interfaces.append(current_iface)
                            parts = line.split(':')
                            if len(parts) >= 2:
                                current_iface = {
                                    'index': parts[0].strip(),
                                    'name': parts[1].strip(),
                                    'mac': '',
                                    'ips': []
                                }
                        elif 'link/ether' in line:
                            current_iface['mac'] = line.split()[1]
                        elif 'inet ' in line:
                            ip_parts = line.strip().split()
                            current_iface['ips'].append(ip_parts[1])
                    
                    if current_iface:
                        interfaces.append(current_iface)
                    
                    # Create nodes for interfaces
                    for iface in interfaces:
                        if iface['name']:
                            node_id = f"net_iface_{iface['name']}"
                            iface_name = iface['name']
                            
                            # Generate 6W1H from Universal Taxonomy
                            sixw1h = self._generate_6w1h(f"Network Interface: {iface_name}", "network")
                            sixw1h.where = f"System network interface #{iface['index']}"
                            sixw1h.which = f"MAC: {iface.get('mac', 'Unknown')}"
                            sixw1h.how = f"IPs: {', '.join(iface.get('ips', []))}"
                            
                            node = TaxonomicNode(
                                node_id=node_id,
                                name=f"Interface: {iface['name']}",
                                taxonomy_type=HardwareTaxonomy.NETWORK,
                                sixw1h=sixw1h,
                                parent_id="hardware_branch",
                                attributes=iface
                            )
                            
                            self.session.taxonomic_tree[node_id] = node
                            self.session.taxonomic_tree["hardware_branch"].add_child(node_id)
                            
            except Exception as e:
                print(f"    [!] Network analysis error: {e}")
    
    def _analyze_users(self):
        """Analyze user accounts"""
        print("  [-] Analyzing users...")
        
        users = []
        
        if self.os_type == OSType.LINUX:
            try:
                with open('/etc/passwd', 'r') as f:
                    for line in f:
                        if line.strip() and not line.startswith('#'):
                            parts = line.strip().split(':')
                            if len(parts) >= 7:
                                users.append({
                                    'username': parts[0],
                                    'uid': parts[2],
                                    'gid': parts[3],
                                    'gecos': parts[4],
                                    'home': parts[5],
                                    'shell': parts[6]
                                })
            except Exception as e:
                print(f"    [!] User analysis error: {e}")
        
        # Create nodes for users
        for user in users[:20]:  # Limit to 20 users
            node_id = f"user_{user['username']}"
            username = user['username']
            
            # Generate 6W1H from Universal Taxonomy
            sixw1h = self._generate_6w1h(f"User account: {username}", "security")
            sixw1h.who = "System administrator"
            sixw1h.where = f"UID: {user['uid']}, GID: {user['gid']}"
            sixw1h.which = f"Home: {user['home']}, Shell: {user['shell']}"
            sixw1h.how = "Authenticated via PAM, permissions via UID/GID"
            
            node = TaxonomicNode(
                node_id=node_id,
                name=user['username'],
                taxonomy_type=SoftwareTaxonomy.SECURITY,
                sixw1h=sixw1h,
                parent_id="software_branch",
                attributes=user
            )
            
            self.session.taxonomic_tree[node_id] = node
            self.session.taxonomic_tree["software_branch"].add_child(node_id)
    
    def _analyze_critical_paths(self):
        """Analyze critical system paths"""
        critical_paths = []
        
        if self.os_type == OSType.LINUX:
            critical_paths = [
                '/etc/passwd', '/etc/shadow', '/etc/group',
                '/etc/hosts', '/etc/resolv.conf',
                '/etc/fstab', '/etc/crontab',
                '/var/log/auth.log', '/var/log/syslog',
                '/tmp', '/var/tmp'
            ]
        elif self.os_type == OSType.WINDOWS:
            critical_paths = [
                'C:\\Windows\\System32\\config\\SAM',
                'C:\\Windows\\System32\\config\\SYSTEM',
                'C:\\Windows\\System32\\drivers\\etc\\hosts',
                'C:\\Windows\\Tasks',
                'C:\\Windows\\Temp'
            ]
        
        for path_str in critical_paths:
            path = Path(path_str)
            if path.exists():
                self.analyze_file(path_str, depth=1)

    def _analyze_processes(self):
        """Analyze running processes"""
        print("  [-] Analyzing processes...")
        
        try:
            # Use ps command to get process list
            # Format: pid, user, start_time, command
            cmd = ['ps', '-eo', 'pid,user,lstart,command']
            if self.os_type == OSType.WINDOWS:
                # Windows implementation placeholder
                return
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')
                headers = lines[0].split()
                
                for line in lines[1:]:
                    parts = line.split(maxsplit=3)
                    if len(parts) < 4:
                        continue
                        
                    pid = parts[0]
                    user = parts[1]
                    start_time = " ".join(parts[2:-1]) # lstart format is weird
                    command = parts[-1]
                    
                    # Get CWD if possible
                    cwd = "Unknown"
                    try:
                        cwd = os.readlink(f"/proc/{pid}/cwd")
                    except:
                        pass

                    # Create artifact ID
                    artifact_id = f"proc_{pid}_{self.session_id}"

                    # P0-3: Verify telemetry against trust registry
                    process_name = command.split()[0].split('/')[-1]  # Extract binary name
                    telemetry = self.trust_registry.verify_pid_telemetry(
                        process_name, int(pid), self.session_id
                    )

                    # Generate 6W1H
                    sixw1h = self._generate_6w1h(f"Process {pid}: {process_name}", "process")
                    sixw1h.who = f"User: {user}, PID: {pid}"
                    sixw1h.where = f"CWD: {cwd}"
                    sixw1h.when = f"Started: {start_time}"
                    sixw1h.which = f"Command: {command}"
                    sixw1h.how = "Executed from shell/system"
                    
                    # Create Artifact
                    artifact = ForensicArtifact(
                        artifact_id=artifact_id,
                        artifact_type=ArtifactType.PROCESS,
                        sixw1h=sixw1h,
                        timestamp_created=datetime.now().isoformat(), # Approximation
                        timestamp_modified=datetime.now().isoformat(),
                        timestamp_accessed=datetime.now().isoformat(),
                        security_context=SecurityContext.UNKNOWN, # Could infer from user
                        properties={
                            'pid': pid,
                            'user': user,
                            'command': command,
                            'cwd': cwd,
                            'args': command.split()[1:],
                            # P0-3: Telemetry tracking
                            'telemetry': {
                                'first_seen_session': telemetry['first_seen'] or self.session_id,
                                'first_seen_timestamp': telemetry['first_seen'] or datetime.now().isoformat(),
                                'pid_changes': telemetry['pid_changes'],
                                'baseline_verified': telemetry['verified'],
                                'trust_status': telemetry['trust_status'],
                                'notes': telemetry.get('notes', '')
                            }
                        }
                    )
                    
                    self.session.artifacts[artifact_id] = artifact
                    
                    # Link to CWD if it exists in artifacts
                    # (This links process to the directory it's running in)
                    # We might want to link to the executable file too if we can resolve it.
                    
                    # Journal interesting processes (e.g., python scripts)
                    if 'python' in command or 'node' in command or 'sh ' in command:
                         self.session.add_journal_entry(
                            "process_detected",
                            f"Detected active process: {pid} ({command}) in {cwd}",
                            ["process", "active", user]
                        )

        except Exception as e:
            print(f"    [!] Process analysis error: {e}")
    
    def _get_project_status_for_file(self, filepath: str) -> Dict[str, Any]:
        """
        #[Mark:P3-1] Retrieve active #[Mark] tags and related Todos for a specific file.
        """
        status_info = {
            'marks': [],
            'todos': []
        }
        
        try:
            # 1. Scan file content for #[Mark:...]
            path = Path(filepath)
            if path.exists() and path.is_file():
                try:
                    with open(path, 'r', errors='ignore') as f:
                        for i, line in enumerate(f):
                            if "#[Mark:" in line:
                                # Extract Mark ID
                                start = line.find("#[Mark:") + 7
                                end = line.find("]", start)
                                if end != -1:
                                    mark_id = line[start:end]
                                    status_info['marks'].append({
                                        "line": i + 1,
                                        "mark_id": mark_id,
                                        "content": line.strip()
                                    })
                except Exception:
                    pass

            # 2. Load plans/todos.json
            todos_path = Path.cwd() / "plans" / "todos.json"
            if not todos_path.exists():
                # Try finding it in typical location relative to script
                todos_path = self.base_dir.parent.parent.parent.parent / "plans" / "todos.json"

            if todos_path.exists():
                try:
                    with open(todos_path, 'r') as f:
                        todos = json.load(f)
                        
                    # Find todos related to the marks
                    mark_ids = [m['mark_id'] for m in status_info['marks']]
                    for todo in todos:
                        # Check if todo ID is in marks (e.g. todo ID "P2-6" matches mark "P2-6")
                        # Or if todo has a tag/mark field
                        if str(todo.get('id')) in mark_ids:
                             status_info['todos'].append(todo)
                        # Heuristic: Check if file name mentioned in todo title
                        elif path.name in todo.get('title', ''):
                             status_info['todos'].append(todo)

                except Exception:
                    pass

        except Exception as e:
            print(f"[-] Error getting project status: {e}")
            
        return status_info

    def analyze_file(self, filepath: str, depth: int = 2):
        """Analyze a specific file with forensic detail"""
        path = Path(filepath).resolve()
        
        if not path.exists():
            print(f"[-] File not found: {filepath}")
            return None
        
        print(f"[*] Analyzing file: {path}")
        
        try:
            # Get file stats
            stat_info = path.stat()
            
            # Calculate hashes
            hashes = self._calculate_file_hashes(path)
            
            # Create artifact ID
            artifact_id = f"file_{hashes['sha256'][:16]}"
            
            # Determine file type and content
            file_type = self._determine_file_type(path)
            content_analysis = self._analyze_file_content(path, depth)
            
            # Determine security context
            security_context = self._determine_security_context(path, stat_info)
            
            # Build 6W1H
            sixw1h = self._build_file_6w1h(path, stat_info, file_type, content_analysis, security_context)
            
            # Create artifact
            artifact = ForensicArtifact(
                artifact_id=artifact_id,
                artifact_type=ArtifactType.FILE,
                sixw1h=sixw1h,
                timestamp_created=datetime.fromtimestamp(stat_info.st_ctime).isoformat(),
                timestamp_modified=datetime.fromtimestamp(stat_info.st_mtime).isoformat(),
                timestamp_accessed=datetime.fromtimestamp(stat_info.st_atime).isoformat(),
                hash_md5=hashes['md5'],
                hash_sha1=hashes['sha1'],
                hash_sha256=hashes['sha256'],
                security_context=security_context,
                owner_uid=stat_info.st_uid,
                owner_gid=stat_info.st_gid,
                permissions=oct(stat_info.st_mode),
                size_bytes=stat_info.st_size,
                properties={
                    'file_type': file_type,
                    'content_analysis': content_analysis,
                    'inode': stat_info.st_ino,
                    'device': stat_info.st_dev,
                    'links': stat_info.st_nlink,
                }
            )
            
            # Add to session
            self.session.artifacts[artifact_id] = artifact
            
            # Update indexes
            self.hash_index[hashes['sha256']] = artifact_id
            self.path_index[str(path)] = artifact_id
            
            # Add to string index
            if content_analysis.get('strings'):
                for s in content_analysis['strings'][:100]:  # Limit indexing
                    self.string_index[s].append(artifact_id)
            
            self.stats['artifacts_analyzed'] += 1
            self.stats['files_processed'] += 1
            
            print(f"[+] File analyzed: {path.name} ({artifact.size_bytes} bytes)")

            # Print 6W1H details explicitly
            sixw1h = artifact.sixw1h
            print(textwrap.indent(f"""
   6W1H Breakdown:
     What: {sixw1h.what}
     Why: {sixw1h.why}
     Who: {sixw1h.who}
     Where: {sixw1h.where}
     When: {sixw1h.when}
     Which: {sixw1h.which}
     How: {sixw1h.how}
                        """, '   '))
            
            # Journal entry
            self.session.add_journal_entry(
                "file_analyzed",
                f"Analyzed file: {path} ({stat_info.st_size} bytes, {hashes['sha256'][:16]}...)",
                ["file", "analysis", file_type]
            )

            # System Profiling for root-level files
            if path.is_absolute() and any(path.is_relative_to(p) for p in ['/usr', '/etc', '/bin', '/sbin', '/lib']):
                system_profile = self.system_profiler.run_all_checks(str(path))
                if system_profile:
                    print(f"\n   SYSTEM PROFILE")
                    pkg = system_profile.get('package', {})
                    chk = system_profile.get('checksum', {})
                    print(f"     Package: {pkg.get('package', 'N/A')} (v{pkg.get('version', 'N/A')})")
                    print(f"     Install Date: {system_profile.get('install_date', 'N/A')}")
                    print(f"     Checksum Status: {chk.get('verification_status', 'Unknown')}")
                    if chk.get('verification_status') == 'FAILED':
                        print(f"     [!] Expected MD5: {chk.get('expected_md5')}")
                        print(f"     [!] Current MD5:  {hashes['md5']}")
            
            return artifact
            
        except Exception as e:
            print(f"[-] Error analyzing file {path}: {e}")

    def _analyze_system_packages(self):
        """Profile all installed system packages (Debian-based systems)."""
        if not self.system_profiler.is_debian_based:
            print("[-] System package analysis is only supported on Debian-based systems.")
            return

        print("[*] Starting system-wide package analysis. This may take a few minutes...")
        log_event("SYSTEM_ANALYSIS_START", "Starting system-wide package analysis")

        try:
            # Get list of all installed packages
            package_list_str = subprocess.check_output(
                ['dpkg-query', '-W', '-f=${Package}\\n'],
                text=True
            )
            package_list = package_list_str.strip().split('\n')
            
            total_packages = len(package_list)
            print(f"[+] Found {total_packages} installed packages.")
            
            all_packages_data = {}
            
            # Use a ThreadPoolExecutor for faster processing
            with ThreadPoolExecutor(max_workers=4) as executor:
                future_to_package = {executor.submit(self._profile_package, pkg_name): pkg_name for pkg_name in package_list}
                
                for i, future in enumerate(as_completed(future_to_package)):
                    pkg_name = future_to_package[future]
                    try:
                        pkg_data = future.result()
                        if pkg_data:
                            all_packages_data[pkg_name] = pkg_data
                        
                        progress = (i + 1) / total_packages * 100
                        print(f"    -> Progress: {progress:.1f}% ({i+1}/{total_packages}) - {pkg_name}", end='\\r')

                    except Exception as exc:
                        print(f"[-] Error profiling package {pkg_name}: {exc}")

            print("\\n[*] Analysis complete. Saving manifest...")
            
            # Save the manifest
            manifest_path = self.manifest_dir / "system_package_manifest.json"
            manifest_data = {
                "manifest_version": "1.0",
                "created_at": datetime.now().isoformat(),
                "hostname": self.hostname,
                "os_type": self.os_type.value,
                "total_packages": len(all_packages_data),
                "packages": all_packages_data
            }
            
            with open(manifest_path, 'w') as f:
                json.dump(manifest_data, f, indent=2)
            
            log_event("SYSTEM_ANALYSIS_COMPLETE", f"System package manifest saved to {manifest_path}", context={"path": str(manifest_path)})
            print(f"[+] System package manifest saved to: {manifest_path}")

        except Exception as e:
            print(f"[-] An error occurred during system package analysis: {e}")

    def _profile_package(self, package_name: str) -> Optional[Dict[str, Any]]:
        """Helper to profile a single package."""
        if not package_name:
            return None

        package_info = self.system_profiler.get_package_info_by_name(package_name)
        if not package_info:
            return None # Likely a virtual package

        install_date = self.system_profiler.get_install_date(package_name)
        
        # Get all files owned by the package
        files_str = self.system_profiler._run_command(['dpkg', '-L', package_name])
        files = files_str.strip().split('\\n')
        
        # Checksum (optional, can be slow)
        # For performance, we'll just note if debsums is available
        checksum_available = bool(shutil.which('debsums'))

        return {
            "package_info": package_info,
            "install_date": install_date,
            "owned_files": files,
            "checksum_verification_available": checksum_available
        }
    
    def _calculate_file_hashes(self, path: Path) -> Dict[str, str]:
        """Calculate multiple hash digests for a file"""
        hashers = {
            'md5': hashlib.md5(),
            'sha1': hashlib.sha1(),
            'sha256': hashlib.sha256()
        }
        
        try:
            with open(path, 'rb') as f:
                while chunk := f.read(8192):
                    for hasher in hashers.values():
                        hasher.update(chunk)
            
            return {k: v.hexdigest() for k, v in hashers.items()}
        except:
            return {k: '' for k in hashers.keys()}
    
    def _determine_file_type(self, path: Path) -> str:
        """Determine file type"""
        try:
            # Try file command
            result = subprocess.run(['file', '-b', str(path)], 
                                  capture_output=True, text=True)
            if result.returncode == 0:
                return result.stdout.strip()
        except:
            pass
        
        # Fallback to MIME type
        mime_type, _ = mimetypes.guess_type(str(path))
        if mime_type:
            return mime_type
        
        # Check extension
        ext_map = {
            '.py': 'Python script',
            '.sh': 'Shell script',
            '.js': 'JavaScript',
            '.html': 'HTML document',
            '.css': 'CSS stylesheet',
            '.json': 'JSON data',
            '.xml': 'XML document',
            '.txt': 'Text file',
            '.md': 'Markdown',
            '.pdf': 'PDF document',
            '.jpg': 'JPEG image',
            '.png': 'PNG image',
            '.gz': 'GZip archive',
            '.tar': 'Tar archive',
            '.zip': 'Zip archive',
            '.deb': 'Debian package',
            '.rpm': 'RPM package',
        }
        
        return ext_map.get(path.suffix.lower(), 'Unknown file type')
    
    def _analyze_file_content(self, path: Path, depth: int) -> Dict[str, Any]:
        """Analyze file content"""
        analysis = {
            'is_text': False,
            'is_binary': False,
            'is_executable': False,
            'line_count': 0,
            'strings': [],
            'imports': [],
            'urls': [],
            'ips': [],
            'emails': [],
            'suspicious_patterns': [],
        }
        
        try:
            # Check file size
            file_size = path.stat().st_size
            if file_size > MAX_FILE_SIZE_ANALYSIS and depth < 3:
                analysis['note'] = f"File too large for deep analysis ({file_size} bytes)"
                return analysis
            
            # Check if executable
            analysis['is_executable'] = os.access(path, os.X_OK)
            
            # Try to read as text first
            try:
                with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read(MAX_STRING_SCAN_SIZE)
                    analysis['is_text'] = True
                    
                    # Count lines
                    analysis['line_count'] = content.count('\n') + 1
                    
                    # Extract strings (words longer than 3 chars)
                    words = re.findall(r'\b\w{4,}\b', content)
                    analysis['strings'] = words[:1000]  # Limit
                    
                    # Extract patterns
                    analysis['urls'] = re.findall(r'https?://[^\s<>"]+|www\.[^\s<>"]+', content)
                    analysis['ips'] = re.findall(r'\b(?:\d{1,3}\.){3}\d{1,3}\b', content)
                    analysis['emails'] = re.findall(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', content)
                    
                    # Check for imports/includes based on extension
                    if path.suffix == '.py':
                        analysis['imports'] = re.findall(r'^(?:import|from)\s+(\S+)', content, re.MULTILINE)

                        # NEW: Class profiling with AST (sits "above" fostering other properties)
                        try:
                            import ast
                            tree = ast.parse(content)

                            analysis['classes'] = {}
                            analysis['functions'] = {}

                            # Extract classes
                            for node in ast.walk(tree):
                                if isinstance(node, ast.ClassDef):
                                    class_info = {
                                        'line_start': node.lineno,
                                        'line_end': getattr(node, 'end_lineno', None),
                                        'methods': [],
                                        'docstring': ast.get_docstring(node),
                                        'bases': [],
                                        'decorators': [],
                                    }

                                    # Extract methods
                                    for item in node.body:
                                        if isinstance(item, ast.FunctionDef):
                                            class_info['methods'].append({
                                                'name': item.name,
                                                'line': item.lineno,
                                                'args': [arg.arg for arg in item.args.args],
                                                'decorators': [d.id if isinstance(d, ast.Name) else str(d) for d in item.decorator_list],
                                                'docstring': ast.get_docstring(item),
                                            })

                                    # Extract inheritance
                                    for base in node.bases:
                                        if isinstance(base, ast.Name):
                                            class_info['bases'].append(base.id)
                                        elif isinstance(base, ast.Attribute):
                                            class_info['bases'].append(f"{base.value.id}.{base.attr}" if isinstance(base.value, ast.Name) else str(base))

                                    # Extract decorators
                                    for dec in node.decorator_list:
                                        if isinstance(dec, ast.Name):
                                            class_info['decorators'].append(dec.id)
                                        else:
                                            class_info['decorators'].append(str(dec))

                                    analysis['classes'][node.name] = class_info

                            # Extract top-level functions (not in classes)
                            for node in ast.iter_child_nodes(tree):
                                if isinstance(node, ast.FunctionDef):
                                    analysis['functions'][node.name] = {
                                        'line': node.lineno,
                                        'args': [arg.arg for arg in node.args.args],
                                        'decorators': [d.id if isinstance(d, ast.Name) else str(d) for d in node.decorator_list],
                                        'docstring': ast.get_docstring(node),
                                    }

                            # Add validation (syntax already validated by successful parse)
                            analysis['validation'] = {
                                'syntax_valid': True,
                                'ast_parsed': True,
                                'class_count': len(analysis['classes']),
                                'function_count': len(analysis['functions']),
                                'indentation': self._validate_indentation(content),
                                'naming': self._validate_naming_conventions(tree),
                            }

                        except SyntaxError as e:
                            analysis['validation'] = {
                                'syntax_valid': False,
                                'syntax_error': str(e),
                                'line': e.lineno,
                            }
                        except Exception as e:
                            analysis['class_profiling_error'] = str(e)

                    elif path.suffix == '.sh':
                        analysis['imports'] = re.findall(r'^\.\s+(\S+)', content, re.MULTILINE)

                    # Look for suspicious patterns
                    suspicious = []
                    patterns = {
                        'base64': r'[A-Za-z0-9+/]{40,}={0,2}',
                        'hex': r'(?:\\x[0-9a-f]{2}){10,}',
                        'eval': r'eval\s*\([^)]+\)',
                        'exec': r'exec\s*\([^)]+\)',
                        'system': r'system\s*\([^)]+\)',
                    }
                    
                    for name, pattern in patterns.items():
                        if re.search(pattern, content, re.IGNORECASE):
                            suspicious.append(name)
                    
                    analysis['suspicious_patterns'] = suspicious
                    
            except UnicodeDecodeError:
                analysis['is_binary'] = True
                
                # Try to extract strings from binary
                try:
                    with open(path, 'rb') as f:
                        binary_data = f.read(MAX_STRING_SCAN_SIZE)
                        # Simple ASCII string extraction
                        strings = re.findall(b'[ -~]{4,}', binary_data)
                        analysis['strings'] = [s.decode('ascii', errors='ignore') for s in strings[:500]]
                except:
                    pass
        
        except Exception as e:
            analysis['error'] = str(e)

        return analysis

    def _validate_indentation(self, content: str) -> Dict:
        """Detect indentation style and check consistency."""
        lines = content.split('\n')
        indents = {}

        for line in lines:
            if line and line[0] in ' \t':
                indent = len(line) - len(line.lstrip())
                if indent > 0:
                    indents[indent] = indents.get(indent, 0) + 1

        if not indents:
            return {'style': 'no_indents', 'consistent': True}

        # Detect most common indent level
        most_common = max(indents, key=indents.get)

        # Determine style
        if most_common >= 4 and most_common % 4 == 0:
            style = '4_spaces'
            expected_multiple = 4
        elif most_common >= 2 and most_common % 2 == 0:
            style = '2_spaces'
            expected_multiple = 2
        else:
            style = f'{most_common}_custom'
            expected_multiple = most_common

        # Check consistency (all indents should be multiples)
        inconsistent = [i for i in indents if expected_multiple > 0 and i % expected_multiple != 0]

        return {
            'style': style,
            'consistent': len(inconsistent) == 0,
            'violations': inconsistent if inconsistent else []
        }

    def _validate_naming_conventions(self, tree) -> Dict:
        """Check naming conventions (snake_case for functions, PascalCase for classes)."""
        import ast
        violations = []

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                # Functions should be snake_case (lowercase with underscores)
                if not all(c.islower() or c == '_' or c.isdigit() for c in node.name):
                    if not node.name.startswith('__'):  # Allow dunder methods
                        violations.append(f"Function '{node.name}' not snake_case (line {node.lineno})")
            elif isinstance(node, ast.ClassDef):
                # Classes should be PascalCase (start with uppercase)
                if not node.name[0].isupper():
                    violations.append(f"Class '{node.name}' should start with uppercase (line {node.lineno})")

        return {
            'compliant': len(violations) == 0,
            'violations': violations
        }

    def _determine_security_context(self, path: Path, stat_info) -> SecurityContext:
        """Determine security context of a file"""
        path_str = str(path)
        
        # Check system directories
        system_dirs = ['/bin', '/sbin', '/usr/bin', '/usr/sbin', 
                      '/lib', '/usr/lib', '/etc', '/boot']
        
        for sys_dir in system_dirs:
            if path_str.startswith(sys_dir):
                return SecurityContext.SYSTEM_TRUSTED
        
        # Check setuid/setgid
        mode = stat_info.st_mode
        if mode & stat.S_ISUID or mode & stat.S_ISGID:
            return SecurityContext.SUSPICIOUS
        
        # Check hidden files
        if path.name.startswith('.'):
            return SecurityContext.SUSPICIOUS
        
        # Check user home directories
        if '/home/' in path_str or '/Users/' in path_str:
            return SecurityContext.USER_TRUSTED
        
        # Check temporary directories
        if '/tmp/' in path_str or '/var/tmp/' in path_str:
            return SecurityContext.UNTRUSTED
        
        return SecurityContext.UNKNOWN
    
    def _build_file_6w1h(self, path: Path, stat_info, file_type: str, 
                        content_analysis: Dict[str, Any], security_context: SecurityContext) -> SixW1H:
        """Build 6W1H classification for a file"""
        
        # Get owner info
        try:
            owner = pwd.getpwuid(stat_info.st_uid).pw_name
        except:
            owner = str(stat_info.st_uid)
        
        try:
            group = grp.getgrgid(stat_info.st_gid).gr_name
        except:
            group = str(stat_info.st_gid)
        
        # Build content summary
        content_summary = []
        if content_analysis.get('is_text'):
            content_summary.append(f"text file, {content_analysis.get('line_count', 0)} lines")
        if content_analysis.get('is_binary'):
            content_summary.append("binary file")
        if content_analysis.get('is_executable'):
            content_summary.append("executable")
        
        # Count patterns found
        pattern_counts = []
        if content_analysis.get('urls'):
            pattern_counts.append(f"{len(content_analysis['urls'])} URLs")
        if content_analysis.get('ips'):
            pattern_counts.append(f"{len(content_analysis['ips'])} IPs")
        if content_analysis.get('imports'):
            pattern_counts.append(f"{len(content_analysis['imports'])} imports")
        
        content_desc = ", ".join(content_summary + pattern_counts)
        
        # Generate 6W1H from Universal Taxonomy
        sixw1h = self._generate_6w1h(f"File: {path.name}", "file")
        sixw1h.who = f"Owner: {owner}, Group: {group}"
        sixw1h.where = f"Path: {path}, Inode: {stat_info.st_ino}"
        sixw1h.when = f"Created: {datetime.fromtimestamp(stat_info.st_ctime).isoformat()}, Modified: {datetime.fromtimestamp(stat_info.st_mtime).isoformat()}"
        sixw1h.which = f"Type: {file_type}, Size: {stat_info.st_size} bytes, Content: {content_desc}"
        sixw1h.how = f"Permissions: {oct(stat_info.st_mode)}, Security: {security_context.value}"
        
        return sixw1h
    
    # ============================================================================
    # QUERY SYSTEM
    # ============================================================================
    
    def profile_entity(self, query_str: str) -> Optional[str]:
        """Search manifests for a system entity and build a profile."""
        query_lower = query_str.lower().replace('-', '_')
        output = []

        # 1. Load Manifests
        try:
            sys_manifest_path = self.manifest_dir / "system_package_manifest.json"
            proj_manifest_path = Path(__file__).resolve().parent / "babel_data" / "inventory" / "consolidated_menu.json"

            sys_manifest = json.loads(sys_manifest_path.read_text()) if sys_manifest_path.exists() else {}
            proj_manifest = json.loads(proj_manifest_path.read_text()) if proj_manifest_path.exists() else {}
        except Exception as e:
            return f"Error loading manifests: {e}"

        # ── TIER 1: Provisions catalog (bundled .whl / .tar.gz in Trainer/Provisions/) ──
        found_pkg = None
        _prov_catalog_path = Path(__file__).resolve().parent / "babel_data" / "inventory" / "provisions_catalog.json"
        if _prov_catalog_path.exists():
            try:
                _prov_cat = json.loads(_prov_catalog_path.read_text(encoding='utf-8'))
                for _pkg in _prov_cat.get('packages', []):
                    _pname = _pkg.get('name', '').lower().replace('-', '_')
                    if _pname == query_lower or _pname.startswith(query_lower):
                        found_pkg = _pkg  # provision entry dict
                        _status = _pkg.get('install_status', 'bundled')
                        _scope  = _pkg.get('scope', 'internal_bundle')
                        output.append(f"[PROVISION PROFILE: {_pkg['name']}]")
                        output.append(f"  Version : {_pkg.get('version', '?')}")
                        output.append(f"  Status  : {_status} ({_scope})")
                        output.append(f"  File    : {_pkg.get('filename', '?')}")
                        if _pkg.get('installed_version'):
                            output.append(f"  Installed: {_pkg['installed_version']} (system)")
                        if _status == 'bundled':
                            output.append(f"  Install : pip install Provisions/{_pkg.get('filename', '')}")
                        break
            except Exception:
                pass

        # ── TIER 2: Live importlib.metadata check (installed pip packages) ──
        if not found_pkg:
            try:
                import importlib.metadata as _im
                # Try original name + normalized variants
                _candidates = [query_str, query_str.replace('_', '-'), query_str.replace('-', '_')]
                for _cand in _candidates:
                    try:
                        _ver = _im.version(_cand)
                        found_pkg = {'name': query_str, 'version': _ver, '_tier': 'pip'}
                        output.append(f"[INSTALLED PACKAGE: {query_str}]")
                        output.append(f"  Version  : {_ver}")
                        output.append(f"  Scope    : system_installed (pip)")
                        # Try to find install location
                        try:
                            _dist = _im.distribution(_cand)
                            _loc = str(_dist._path.parent) if hasattr(_dist, '_path') else '?'
                            output.append(f"  Location : {_loc}")
                        except Exception:
                            pass
                        break
                    except _im.PackageNotFoundError:
                        continue
            except ImportError:
                pass

        # ── TIER 3a: system_package_manifest.json cache (built by 'analyze --system-packages') ──
        if not found_pkg:
            partial_matches = []
            for pkg_name, pkg_data in sys_manifest.get('packages', {}).items():
                if query_lower == pkg_name.lower():
                    found_pkg = pkg_data
                    break
                pkg_info = pkg_data.get('package_info', {})
                desc = str(pkg_info.get('description', pkg_info.get('Description', ''))).lower()
                if query_lower in pkg_name.lower() or query_lower in desc:
                    partial_matches.append(pkg_data)
            if not found_pkg and partial_matches:
                found_pkg = partial_matches[0]

        # ── TIER 3b: live dpkg query (no manifest needed — instant, per-package) ──
        # Tries exact name first, then common variant prefixes (python → python3, python3-X)
        if not found_pkg:
            _dpkg_candidates = [query_str]
            _ql = query_str.lower()
            # Common prefix variants: "python" → try "python3"; "cargo" → try as-is
            if _ql in ('python', 'python3'):
                _dpkg_candidates = ['python3', 'python3-dev', 'python3-pip']
            try:
                for _cand in _dpkg_candidates:
                    _pkg_data = self._profile_package(_cand)
                    if _pkg_data and _pkg_data.get('package_info'):
                        found_pkg = _pkg_data
                        break
            except Exception:
                pass

        # Only emit the dpkg [SYSTEM PROFILE] block for Tier 3 matches that have
        # package_info (provision/pip entries from Tiers 1+2 already emitted their block).
        if found_pkg and found_pkg.get('package_info'):
            output.append(f"[SYSTEM PROFILE: {query_str}]")
            info = found_pkg.get('package_info', {})
            # Flexible key matching (handle both lowercase and capitalized)
            pkg_name = info.get('package') or info.get('Package', 'N/A')
            version = info.get('version') or info.get('Version', 'N/A')
            desc = info.get('description') or info.get('Description', 'N/A')

            output.append(f"  - Package Name: {pkg_name}")
            output.append(f"  - Version: {version}")
            output.append(f"  - Install Date: {found_pkg.get('install_date', 'N/A')}")
            output.append(f"  - Integrity: {'[✓] Available' if found_pkg.get('checksum_verification_available') else '[?] Not Available'}")
            output.append(f"  - Description: {desc}")

            # Show file count if available
            files = found_pkg.get('owned_files', [])
            if files:
                file_count = len(files) if isinstance(files, list) else len(str(files).split('\n'))
                output.append(f"  - Files Owned: {file_count}")

            # Add 6W1H context layers
            output.append("")  # Blank line for readability

            # Check for active processes using this package
            try:
                import subprocess
                # Find processes related to this package
                ps_result = subprocess.run(['ps', 'aux'], capture_output=True, text=True, timeout=2)
                related_procs = [line for line in ps_result.stdout.split('\n') if pkg_name.lower() in line.lower()]
                if related_procs:
                    output.append(f"   [USER I/O - Active Processes]")
                    output.append(f"   Running Processes: {len(related_procs)}")
                    # Show first 3 processes
                    for proc in related_procs[:3]:
                        parts = proc.split()
                        if len(parts) > 1:
                            output.append(f"     • User: {parts[0]}, PID: {parts[1]}")
            except Exception:
                pass

            # Check network/firewall context (for network-related packages)
            if any(keyword in pkg_name.lower() for keyword in ['network', 'ssh', 'http', 'ftp', 'curl', 'wget']):
                try:
                    # Check if package has network capabilities
                    output.append(f"\n   [NETWORK & FIREWALL]")
                    # Check for listening ports (requires elevated permissions, so may be empty)
                    ss_result = subprocess.run(['ss', '-tulpn'], capture_output=True, text=True, timeout=2)
                    related_ports = [line for line in ss_result.stdout.split('\n') if pkg_name.lower() in line.lower()]
                    if related_ports:
                        output.append(f"   Listening Ports: {len(related_ports)}")
                    else:
                        output.append(f"   Listening Ports: None detected")
                except Exception:
                    output.append(f"   Network Info: Requires elevated permissions")

        # 3. Search Session Artifacts for files that USE this package/module
        # Runs unconditionally — searches by query_str regardless of whether a catalog match was found
        _search_name = query_str
        if found_pkg:
            _search_name = (
                found_pkg.get('name')
                or (found_pkg.get('package_info') or {}).get('package')
                or (found_pkg.get('package_info') or {}).get('Package')
                or query_str
            )
        _sname_lower = _search_name.lower()
        using_files = []
        for artifact_id, artifact in self.session.artifacts.items():
            if artifact.artifact_type == ArtifactType.FILE:
                fname = artifact.sixw1h.what
                props = artifact.properties

                imports = props.get('imports', [])
                if any(_sname_lower in str(imp).lower() for imp in imports):
                    using_files.append(fname)
                elif artifact.raw_content and _sname_lower in artifact.raw_content[:500].lower():
                    using_files.append(fname)

        if using_files:
            output.append(f"\n   [CHAIN OF CUSTODY - Files Using {_search_name}]")
            output.append(f"   Found {len(using_files)} file(s) in current session:")
            for fname in using_files[:10]:
                output.append(f"     • {fname}")

        # 4. Search Project Manifest for Associations (name, display_name, tool_id, command, tags, description)
        associations = []
        for tool in proj_manifest.get('tools', []):
            _tname = (tool.get('name') or tool.get('display_name') or '').lower()
            _tcmd = (tool.get('command') or '').lower()
            _tid = (tool.get('id') or tool.get('tool_id') or '').lower()
            _matched = (query_lower in _tname or query_lower in _tcmd or query_lower in _tid
                        or any(query_lower in (t or '').lower() for t in tool.get('tags', []))
                        or query_lower in (tool.get('description') or '').lower())
            if _matched:
                _label = tool.get('display_name') or tool.get('name') or _tid
                _cat = tool.get('category', 'unknown')
                _src = tool.get('source_path', '')
                _extra = f" [{_src}]" if _src else ""
                associations.append(f"  - {_label} (Category: {_cat}){_extra}")

        if associations:
            output.append(f"\n[PROJECT ASSOCIATIONS: {len(associations)} tools use this technology]")
            output.extend(sorted(list(set(associations))))

        return "\n".join(output) if output else None
        
    def query(self, query_str: str, query_type: str = "natural", max_results: int = 50):
        """Execute a query against the session data"""
        start_time = time.time()
        
        print(f"[*] Executing query: {query_str}")
        
        # Parse query
        parsed_query = self._parse_query(query_str, query_type)
        
        # Execute based on query type
        if parsed_query.get('type') == 'file':
            results = self._query_file_pattern(parsed_query['pattern'], max_results)
        elif parsed_query.get('type') == 'string':
            results = self._query_string(parsed_query['pattern'], max_results)
        elif parsed_query.get('type') == 'hash':
            results = self._query_hash(parsed_query['pattern'])
        elif parsed_query.get('type') == 'taxonomic':
            results = self._query_taxonomic(parsed_query['pattern'], max_results)
        elif parsed_query.get('type') == 'verb':
            results = self._query_verb(parsed_query['pattern'], max_results)
        elif parsed_query.get('type') == 'imports':
            results = self._query_imports(parsed_query['pattern'], max_results)
        else:
            results = self._query_natural(parsed_query['pattern'], max_results)
        
        # ALWAYS enrich with persistent data stores (change history, temporal, tasks, catalog)
        # These provide context that session artifacts alone cannot: WHO changed it, WHEN, WHY, risk level
        _enrichment = self._query_cold_start(parsed_query['pattern'], max_results)
        if _enrichment:
            if not results:
                results = _enrichment
                print(f"[+] Cold-start fallback returned {len(_enrichment)} results from persistent stores")
            else:
                results.extend(_enrichment)
                print(f"[+] Enriched with {len(_enrichment)} context entries from persistent stores")

        elapsed_ms = int((time.time() - start_time) * 1000)

        # Update query history
        self.session.add_query(query_str, len(results), elapsed_ms)

        print(f"[+] Query returned {len(results)} results in {elapsed_ms}ms")
        
        return {
            'query': query_str,
            'type': parsed_query.get('type', 'unknown'),
            'results': results,
            'count': len(results),
            'duration_ms': elapsed_ms,
            'timestamp': datetime.now().isoformat()
        }
    
    def _parse_query(self, query_str: str, query_type: str) -> Dict[str, Any]:
        """Parse query string"""
        parsed = {
            'original': query_str,
            'type': query_type,
            'pattern': query_str
        }
        
        # Auto-detect query type
        _file_extensions = {'.py', '.sh', '.js', '.ts', '.json', '.yaml', '.yml',
                            '.toml', '.cfg', '.ini', '.conf', '.xml', '.html', '.css',
                            '.md', '.txt', '.csv', '.log', '.bash', '.zsh', '.pl',
                            '.rb', '.go', '.rs', '.c', '.cpp', '.h', '.java', '.kt',
                            '.swift', '.r', '.sql', '.lua', '.php', '.ex', '.exs'}
        if query_type == "auto":
            ql = query_str.lower()
            # Check for file path or filename with known extension
            if (query_str.startswith('/') or 'path:' in ql
                    or any(ql.endswith(ext) for ext in _file_extensions)
                    or ('/' in query_str and '.' in query_str.split('/')[-1])):
                parsed['type'] = 'file'
            elif 'hash:' in ql or (len(query_str) in [32, 40, 64] and all(c in '0123456789abcdef' for c in ql)):
                parsed['type'] = 'hash'
            elif 'type:' in ql or 'taxon:' in ql:
                parsed['type'] = 'taxonomic'
            elif 'verb:' in ql or 'cmd:' in ql:
                parsed['type'] = 'verb'
            elif 'import:' in ql:
                parsed['type'] = 'imports'
            elif any(word in ql for word in ['find', 'search', 'look for']):
                parsed['type'] = 'string'
            else:
                parsed['type'] = 'natural'
        elif query_type == "imports":
            parsed['type'] = 'imports'
        
        # Extract patterns
        if parsed['type'] == 'file' and 'path:' in query_str.lower():
            parsed['pattern'] = query_str.lower().split('path:', 1)[1].strip()
        elif parsed['type'] == 'hash' and 'hash:' in query_str.lower():
            parsed['pattern'] = query_str.lower().split('hash:', 1)[1].strip()
        elif parsed['type'] == 'taxonomic' and 'type:' in query_str.lower():
            parsed['pattern'] = query_str.lower().split('type:', 1)[1].strip()
        elif parsed['type'] == 'verb' and 'verb:' in query_str.lower():
            parsed['pattern'] = query_str.lower().split('verb:', 1)[1].strip()
        elif parsed['type'] == 'imports' and 'import:' in query_str.lower():
            parsed['pattern'] = query_str.lower().split('import:', 1)[1].strip()
        
        return parsed
    
    def _query_file_pattern(self, pattern: str, max_results: int) -> List[Dict[str, Any]]:
        """Query files by path pattern"""
        results = []
        
        # Check path index
        for path, artifact_id in self.path_index.items():
            if pattern.lower() in path.lower():
                artifact = self.session.artifacts.get(artifact_id)
                if artifact:
                    results.append({
                        'type': 'file',
                        'artifact_id': artifact_id,
                        'path': path,
                        'artifact': artifact.to_dict()
                    })
                
                if len(results) >= max_results:
                    break
        
        return results
    
    def _query_string(self, pattern: str, max_results: int) -> List[Dict[str, Any]]:
        """Query by string content"""
        results = []
        
        # Search in string index
        if pattern in self.string_index:
            for artifact_id in self.string_index[pattern][:max_results]:
                artifact = self.session.artifacts.get(artifact_id)
                if artifact:
                    results.append({
                        'type': 'string_match',
                        'artifact_id': artifact_id,
                        'string': pattern,
                        'artifact': artifact.to_dict()
                    })
        
        # Also search in taxonomic node names and descriptions
        for node_id, node in self.session.taxonomic_tree.items():
            if (pattern.lower() in node.name.lower() or 
                pattern.lower() in node.sixw1h.what.lower()):
                results.append({
                    'type': 'taxonomic_match',
                    'node_id': node_id,
                    'node': node.to_dict()
                })
                
                if len(results) >= max_results:
                    break
        
        return results

    def _query_imports(self, pattern: str, max_results: int) -> List[Dict[str, Any]]:
        """Query files by imported modules."""
        results = []
        pattern_lower = pattern.lower()

        for artifact_id, artifact in self.session.artifacts.items():
            if artifact.artifact_type == ArtifactType.FILE:
                imports = artifact.properties.get('content_analysis', {}).get('imports', [])
                if any(pattern_lower in imp.lower() for imp in imports):
                    results.append({
                        'type': 'import_match',
                        'artifact_id': artifact_id,
                        'import_pattern': pattern,
                        'artifact': artifact.to_dict()
                    })
                    if len(results) >= max_results:
                        break
        return results

    
    def _query_hash(self, hash_pattern: str) -> List[Dict[str, Any]]:
        """Query by hash"""
        results = []
        
        # Check hash index
        for hash_val, artifact_id in self.hash_index.items():
            if hash_pattern.lower() in hash_val.lower():
                artifact = self.session.artifacts.get(artifact_id)
                if artifact:
                    results.append({
                        'type': 'hash_match',
                        'artifact_id': artifact_id,
                        'hash': hash_val,
                        'artifact': artifact.to_dict()
                    })
        
        return results
    
    def _query_taxonomic(self, pattern: str, max_results: int) -> List[Dict[str, Any]]:
        """Query taxonomic tree"""
        results = []
        
        pattern_lower = pattern.lower()
        
        for node_id, node in self.session.taxonomic_tree.items():
            # Check taxonomy type
            tax_type = node.taxonomy_type.value if hasattr(node.taxonomy_type, 'value') else node.taxonomy_type
            tax_type = str(tax_type).lower()
            
            # Match pattern
            if (pattern_lower in tax_type or
                pattern_lower in node.name.lower() or
                pattern_lower in node.sixw1h.what.lower()):
                
                results.append({
                    'type': 'taxonomic_node',
                    'node_id': node_id,
                    'node': node.to_dict()
                })
                
                if len(results) >= max_results:
                    break
        
        return results
    
    def _query_verb(self, pattern: str, max_results: int) -> List[Dict[str, Any]]:
        """Query system verbs"""
        results = []
        
        pattern_lower = pattern.lower()
        
        for verb_id, verb in self.session.verbs.items():
            if (pattern_lower in verb.name.lower() or
                pattern_lower in verb.domain.value.lower() or
                pattern_lower in verb.sixw1h.what.lower()):
                
                results.append({
                    'type': 'verb',
                    'verb_id': verb_id,
                    'verb': verb.to_dict()
                })
                
                if len(results) >= max_results:
                    break
        
        return results
    
    def _query_natural(self, pattern: str, max_results: int) -> List[Dict[str, Any]]:
        """Natural language query - search across everything"""
        results = []
        
        # Search in artifacts
        for artifact_id, artifact in self.session.artifacts.items():
            artifact_dict = artifact.to_dict()
            artifact_str = json.dumps(artifact_dict).lower()
            
            if pattern.lower() in artifact_str:
                results.append({
                    'type': 'artifact',
                    'artifact_id': artifact_id,
                    'artifact': artifact_dict
                })
                
                if len(results) >= max_results:
                    break
        
        # Search in taxonomic nodes
        if len(results) < max_results:
            for node_id, node in self.session.taxonomic_tree.items():
                node_dict = node.to_dict()
                node_str = json.dumps(node_dict).lower()
                
                if pattern.lower() in node_str:
                    results.append({
                        'type': 'taxonomic_node',
                        'node_id': node_id,
                        'node': node_dict
                    })
                    
                    if len(results) >= max_results:
                        break
        
        return results
    
    # ============================================================================
    # COLD-START QUERY (persistent data store fallback)
    # ============================================================================

    def _query_cold_start(self, pattern: str, max_results: int = 10) -> list:
        """Fallback query across persistent data stores when session artifacts are empty."""
        results = []
        _pattern_lower = pattern.lower()
        _pattern_base = pattern.split('/')[-1].lower()
        # Also try without extension for matching (e.g. "onboarder.py" → "onboarder")
        _pattern_stem = Path(_pattern_base).stem.lower() if '.' in _pattern_base else _pattern_base
        _data_root = Path(__file__).resolve().parents[2]

        # Source 1: enriched_changes (version_manifest)
        try:
            _vm_path = _data_root / "backup" / "version_manifest.json"
            if _vm_path.exists():
                _vm = json.loads(_vm_path.read_text(encoding="utf-8"))
                _ec = _vm.get("enriched_changes", {})
                _matching = [(eid, ch) for eid, ch in _ec.items()
                            if (_pattern_base in ch.get("file", "").lower().split("/")[-1]
                                or _pattern_stem in ch.get("file", "").lower().split("/")[-1])]
                if _matching:
                    _latest = max(_matching, key=lambda x: x[1].get("timestamp", ""))
                    eid, ch = _latest
                    # Aggregate probe stats across all events for this file
                    _probe_pass = sum(1 for _, c in _matching if c.get("probe_status") == "PASS")
                    _probe_warn = sum(1 for _, c in _matching if c.get("probe_status") == "WARN")
                    _probe_fail = sum(1 for _, c in _matching if c.get("probe_status") == "FAIL")
                    _risk_high = sum(1 for _, c in _matching if c.get("risk_level") in ("HIGH", "CRITICAL"))
                    _unresolved = sum(1 for _, c in _matching
                                      if c.get("probe_status") == "FAIL" and not c.get("resolved_by"))
                    results.append({
                        "source": "enriched_changes",
                        "artifact_id": eid,
                        "artifact_type": "change_event",
                        "file": ch.get("file", ""),
                        "verb": ch.get("verb", ""),
                        "risk_level": ch.get("risk_level", ""),
                        "methods": ch.get("methods", []),
                        "imports_added": ch.get("imports_added", []),
                        "timestamp": ch.get("timestamp", ""),
                        "task_ids": ch.get("task_ids") or [],
                        "test_status": ch.get("test_status", ""),
                        "probe_status": ch.get("probe_status", ""),
                        "probe_errors": ch.get("probe_errors", []),
                        "project_id": ch.get("project_id", ""),
                        "total_changes": len(_matching),
                        "all_events": [eid for eid, _ in _matching],
                        "probe_summary": f"{_probe_pass}✓ {_probe_warn}⚠ {_probe_fail}✗",
                        "risk_high_count": _risk_high,
                        "unresolved_probes": _unresolved,
                    })

                # Source 1b: imports_added reverse search — "which files recently added import X?"
                # Only runs when the filename search produced nothing (query looks like a module name)
                if not _matching and '.' not in _pattern_lower and '/' not in _pattern_lower:
                    _import_hits = [
                        (eid, ch) for eid, ch in _ec.items()
                        if any(_pattern_lower in (imp or "").lower()
                               for imp in ch.get("imports_added", []))
                    ]
                    if _import_hits:
                        _files_adding = list(dict.fromkeys(
                            ch.get("file", "") for _, ch in _import_hits if ch.get("file")
                        ))
                        results.append({
                            "source": "enriched_changes",
                            "artifact_type": "import_usage_history",
                            "module": pattern,
                            "files": [(f, "") for f in _files_adding[:50]],
                            "total": len(_files_adding),
                        })
        except Exception:
            pass

        # Source 2: consolidated_menu.json (onboarder catalog)
        try:
            _menu_path = Path(__file__).resolve().parent / "babel_data" / "inventory" / "consolidated_menu.json"
            if _menu_path.exists():
                _menu = json.loads(_menu_path.read_text(encoding="utf-8"))
                for tool in _menu.get("tools", []):
                    _tname = (tool.get("name") or tool.get("display_name") or "").lower()
                    _tcmd = (tool.get("command") or "").lower()
                    _tid = (tool.get("id") or tool.get("tool_id") or "").lower()
                    if (_pattern_lower in _tname or _pattern_stem in _tname
                            or _pattern_lower in _tcmd or _pattern_stem in _tcmd
                            or _pattern_lower in _tid
                            or any(_pattern_stem in (t or "").lower() for t in tool.get("tags", []))
                            or _pattern_stem in (tool.get("description") or "").lower()):
                        results.append({
                            "source": "onboarder_catalog",
                            "artifact_type": "cataloged_tool",
                            "tool_id": tool.get("tool_id") or tool.get("id"),
                            "name": tool.get("display_name") or tool.get("name"),
                            "category": tool.get("category"),
                            "description": (tool.get("description") or "")[:200],
                            "tags": tool.get("tags", []),
                            "source_path": tool.get("source_path", ""),
                        })
                        if len(results) >= max_results:
                            break
        except Exception:
            pass

        # Source 3: py_manifest (AST analysis + call graph)
        _MAX_MANIFEST_BYTES = 50 * 1024 * 1024  # 50 MB safety cap — py_manifest.json can be 800MB+
        try:
            _pm_found = None  # (fpath, info, pm_data) best match
            for _pm_name in ["py_manifest_augmented.json", "py_manifest.json"]:
                _pm_path = _data_root / "pymanifest" / _pm_name
                if not _pm_path.exists():
                    continue
                if _pm_path.stat().st_size > _MAX_MANIFEST_BYTES:
                    continue  # Skip oversized manifest — would OOM on load
                _pm = json.loads(_pm_path.read_text(encoding="utf-8"))
                _pm_fallback = None
                for fpath, info in _pm.get("files", {}).items():
                    if "/backup/" in fpath or "/history/" in fpath:
                        continue
                    _fbase = fpath.split("/")[-1]
                    if ".backup_" in _fbase or _fbase.startswith("LEGACY"):
                        continue
                    if _fbase.lower() == _pattern_base:
                        _pm_found = (fpath, info, _pm)
                        break  # Exact match
                    elif (_pattern_base in _fbase.lower()
                            or _pattern_stem in _fbase.lower()):
                        if not _pm_fallback:
                            _pm_fallback = (fpath, info, _pm)
                if _pm_found:
                    break
                if _pm_fallback:
                    _pm_found = _pm_fallback
                    break

            if _pm_found:
                fpath, info, _pm = _pm_found
                results.append({
                    "source": "py_manifest",
                    "artifact_type": "ast_profile",
                    "file_path": fpath,
                    "classes": [c.get("name") for c in info.get("classes", [])],
                    "functions": [f.get("name") for f in info.get("functions", [])],
                    "imports": [i.get("module") for i in info.get("imports", [])],
                    "loc": info.get("loc", "?"),
                })

                # Source 6: Call graph from same py_manifest entry
                _cg_deps = [d.split("/")[-1] for d in info.get("dependencies", [])]
                _cg_edges = []
                for _fn in info.get("functions", []):
                    for _ct, _cl in _fn.get("calls", []):
                        _cg_edges.append(f"{_fn.get('name', '?')}→{_ct}:{_cl}")
                for _cls in info.get("classes", []):
                    for _mth in _cls.get("methods", []):
                        for _ct, _cl in _mth.get("calls", []):
                            _cg_edges.append(f"{_cls.get('name','?')}.{_mth.get('name','?')}→{_ct}:{_cl}")
                # Reverse deps: who imports this file?
                _cg_importers = []
                for _fp2, _info2 in _pm.get("files", {}).items():
                    if _fp2 == fpath or "/backup/" in _fp2 or "/history/" in _fp2:
                        continue
                    _bn2 = _fp2.split("/")[-1]
                    if ".backup_" in _bn2 or _bn2.startswith("LEGACY"):
                        continue
                    for _dep2 in _info2.get("dependencies", []):
                        if _dep2 == fpath:
                            _cg_importers.append(_bn2)
                            break
                if _cg_deps or _cg_edges or _cg_importers:
                    results.append({
                        "source": "py_manifest",
                        "artifact_type": "call_graph",
                        "imports": _cg_deps,
                        "imported_by": _cg_importers,
                        "call_edges": len(_cg_edges),
                        "top_edges": _cg_edges,
                    })
        except Exception:
            pass

        # Source 3b: reverse-import search — "which files in this project import X?"
        # Reuses the already-loaded py_manifest (_pm) from Source 3 if available.
        # Separate try so a failure here doesn't block Source 3 results.
        try:
            _rev_pm = None
            # Try to reuse already-parsed manifest; fall back to loading it
            if '_pm_found' in dir() and _pm_found:
                _, _, _rev_pm = _pm_found
            else:
                for _pm_name in ["py_manifest_augmented.json", "py_manifest.json"]:
                    _rp = _data_root / "pymanifest" / _pm_name
                    if _rp.exists() and _rp.stat().st_size <= _MAX_MANIFEST_BYTES:
                        _rev_pm = json.loads(_rp.read_text(encoding="utf-8"))
                        break

            if _rev_pm:
                _using_files = []
                for _fp, _info in _rev_pm.get("files", {}).items():
                    if "/backup/" in _fp or "/history/" in _fp:
                        continue
                    _bn = _fp.split("/")[-1]
                    if ".backup_" in _bn or _bn.startswith("LEGACY"):
                        continue
                    # Match against each import module name in this file
                    for _imp in _info.get("imports", []):
                        _imp_mod = (_imp.get("module") or _imp if isinstance(_imp, str) else "").lower()
                        # Exact or prefix match: "ollama" matches "ollama", "ollama.api"
                        if _imp_mod == _pattern_lower or _imp_mod.startswith(_pattern_lower + "."):
                            _using_files.append((_fp, _info.get("loc", "?")))
                            break
                if _using_files:
                    results.append({
                        "source": "py_manifest",
                        "artifact_type": "import_usage",
                        "module": pattern,
                        "files": _using_files[:50],  # cap at 50
                        "total": len(_using_files),
                    })
        except Exception:
            pass

        # Source 4: latest_sync.json (task associations)
        try:
            _ls_path = _data_root / "plans" / "Refs" / "latest_sync.json"
            if _ls_path.exists():
                _ls = json.loads(_ls_path.read_text(encoding="utf-8"))
                _task_matches = [(tid, t) for tid, t in _ls.get("tasks", {}).items()
                                if (_pattern_base in (t.get("wherein") or "").lower()
                                    or _pattern_stem in (t.get("wherein") or "").lower())]
                if _task_matches:
                    results.append({
                        "source": "task_sync",
                        "artifact_type": "task_association",
                        "tasks": [{"id": tid, "title": t.get("title", ""), "status": t.get("status", "")}
                                 for tid, t in _task_matches[:10]],
                        "task_count": len(_task_matches),
                    })
        except Exception:
            pass

        # Source 5: history temporal manifest (backup activity)
        try:
            _tm_path = Path(__file__).resolve().parent / "babel_data" / "timeline" / "manifests" / "history_temporal_manifest.json"
            if _tm_path.exists():
                _tm = json.loads(_tm_path.read_text(encoding="utf-8"))
                for _hname, _hprof in _tm.get("profiles", {}).items():
                    if _pattern_base.replace(".py", "") in _hname.lower():
                        results.append({
                            "source": "history_temporal",
                            "artifact_type": "temporal_profile",
                            "history_name": _hname,
                            "backup_count": _hprof.get("backup_count", 0),
                            "first_seen": _hprof.get("first_seen", ""),
                            "last_seen": _hprof.get("last_seen", ""),
                            "span_days": _hprof.get("span_days", 0),
                            "activity_score": _hprof.get("activity_score", 0),
                        })
                        break
        except Exception:
            pass

        # Source 7: provisions_catalog — bundled offline packages in Trainer/Provisions/
        try:
            _prov_path = Path(__file__).resolve().parent / "babel_data" / "inventory" / "provisions_catalog.json"
            if _prov_path.exists():
                _prov = json.loads(_prov_path.read_text(encoding="utf-8"))
                for _pkg in _prov.get("packages", []):
                    _pname = _pkg.get("name", "").lower().replace('-', '_')
                    if _pattern_lower in _pname:
                        results.append({
                            "source": "provisions_catalog",
                            "artifact_type": "provision",
                            "name": _pkg.get("name"),
                            "version": _pkg.get("version"),
                            "scope": _pkg.get("scope"),
                            "install_status": _pkg.get("install_status"),
                            "installed_version": _pkg.get("installed_version"),
                            "path": _pkg.get("path"),
                            "filename": _pkg.get("filename"),
                        })
        except Exception:
            pass

        return results[:max_results]

    def _assess_change_impact(self, file_pattern: str, intent_text: str, cold_results: list) -> str:
        """Pre-change impact assessment. Pools enriched_changes, call_graph, tasks,
        project context, and AoE warn/risk vectors into a prospective report."""
        _data_root = Path(__file__).resolve().parents[2]
        _plans_root = _data_root / "plans"

        # Unpack cold_results by artifact_type
        _ce  = next((r for r in cold_results if r.get('artifact_type') == 'change_event'), {})
        _ast = next((r for r in cold_results if r.get('artifact_type') == 'ast_profile'), {})
        _cg  = next((r for r in cold_results if r.get('artifact_type') == 'call_graph'), {})
        _ta  = next((r for r in cold_results if r.get('artifact_type') == 'task_association'), {})
        _tp  = next((r for r in cold_results if r.get('artifact_type') == 'temporal_profile'), {})

        out = []

        # ═══════════════════════════════════════
        # SECTION 1: FILE IDENTITY
        # ═══════════════════════════════════════
        out.append("=" * 60)
        out.append("ASSESS: PRE-CHANGE IMPACT REPORT")
        out.append("=" * 60)
        out.append(f"Target  : {file_pattern}")
        if intent_text:
            out.append(f"Intent  : {intent_text}")
        out.append(f"Run At  : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        out.append("")

        out.append("[FILE IDENTITY]")
        if _ast:
            out.append(f"  File     : {_ast.get('file_path', file_pattern)}")
            out.append(f"  LOC      : {_ast.get('loc', '?')}")
            _cls = _ast.get('classes', [])
            _fns = _ast.get('functions', [])
            if _cls:
                out.append(f"  Classes  : {len(_cls)} ({', '.join(_cls[:5])}{'...' if len(_cls) > 5 else ''})")
            if _fns:
                out.append(f"  Functions: {len(_fns)}")
        elif _ce:
            out.append(f"  File     : {_ce.get('file', file_pattern)}")
        else:
            out.append(f"  File     : {file_pattern} (not in py_manifest)")
        if _tp:
            out.append(f"  Backups  : {_tp.get('backup_count', 0)} | Activity: {_tp.get('activity_score', 0)} | Span: {_tp.get('span_days', 0)}d")
        out.append("")

        # ═══════════════════════════════════════
        # SECTION 2: AoE WARNING PANEL
        # ═══════════════════════════════════════
        out.append("[AoE WARNING PANEL]")
        _warnings = []

        # 2a: Core file check
        CRITICAL_FILES = ["logger_util.py", "recovery_util.py", "interactive_trainer_gui_NEW.py"]
        _file_base = file_pattern.split('/')[-1]
        if any(cf in _file_base for cf in CRITICAL_FILES):
            out.append(f"  AoE {{CRITICAL}}: '{_file_base}' is a CORE system file — changes affect the recovery pipeline")
            _warnings.append('critical')

        # 2b: Historical risk from enriched_changes
        if _ce:
            _total = _ce.get('total_changes', 0)
            _risk = _ce.get('risk_level', 'LOW')
            _probe = _ce.get('probe_status', '')
            _unresolved = _ce.get('unresolved_probes', 0)
            _risk_high = _ce.get('risk_high_count', 0)

            # Aggregate risk_reasons from all events for this file
            _reasons = []
            try:
                _vm_path = _data_root / "backup" / "version_manifest.json"
                if _vm_path.exists():
                    _vm = json.loads(_vm_path.read_text(encoding="utf-8"))
                    _ec_all = _vm.get("enriched_changes", {})
                    _pat_base = _file_base.lower()
                    for _eid, _ch in _ec_all.items():
                        _ch_base = _ch.get("file", "").lower().split("/")[-1]
                        if _pat_base in _ch_base:
                            _rr = _ch.get("risk_reasons", [])
                            if isinstance(_rr, list):
                                _reasons.extend(_rr)
                            elif isinstance(_rr, str) and _rr:
                                _reasons.append(_rr)
            except Exception:
                pass
            _unique_reasons = list(dict.fromkeys(_reasons))[:5]

            out.append(f"  History  : {_total} change events | Latest risk: {_risk}")
            if _risk_high:
                out.append(f"  AoE {{RISK}}: {_risk_high} HIGH/CRITICAL risk events in history")
                _warnings.append('risk')
            if _unresolved:
                out.append(f"  AoE {{CRITICAL}}: {_unresolved} probe FAIL(s) unresolved — fix before modifying")
                _warnings.append('critical')
            elif _probe == 'FAIL':
                out.append(f"  AoE {{WARN}}: Latest probe status is FAIL")
                _warnings.append('warn')
            if _unique_reasons:
                out.append(f"  Risk Reasons:")
                for _r in _unique_reasons:
                    out.append(f"    - {_r}")
            _test_status = _ce.get('test_status', '')
            if _test_status and _test_status.upper() not in ('OK', 'PASS', ''):
                out.append(f"  AoE {{WARN}}: Test status is '{_test_status}'")
                _warnings.append('warn')
        else:
            out.append("  History  : No enriched_changes data for this file")

        # 2c: Blast radius from call_graph
        _importers = _cg.get('imported_by', [])
        _imports = _cg.get('imports', [])
        _n_importers = len(_importers)
        if _n_importers > 0:
            out.append(f"  Blast Radius: {_n_importers} file(s) import this")
            out.append(f"    Imported By: {', '.join(_importers)}")
            if _n_importers >= 5:
                out.append(f"  AoE {{WARN}}: {_n_importers} downstream dependents — test all importers after changes")
                _warnings.append('warn')
        if _imports:
            out.append(f"  Depends On: {', '.join(_imports)}")

        # 2d: Intent keyword analysis
        _intent_lower = intent_text.lower() if intent_text else ''
        if _intent_lower:
            if 'import' in _intent_lower or 'from ' in _intent_lower:
                out.append(f"  AoE {{WARN}}: Intent mentions imports — verify dependencies are available")
                _warnings.append('warn')
            if any(kw in _intent_lower for kw in ['checklist', 'todos', 'latest_sync', 'version_manifest']):
                out.append(f"  AoE {{WARN}}: Intent touches coordination data store — risk of format corruption")
                _warnings.append('warn')
            if any(kw in _intent_lower for kw in ['delete', 'remove', 'drop']):
                out.append(f"  AoE {{RISK}}: Intent mentions deletion — risk of irreversible data loss")
                _warnings.append('risk')
            if any(kw in _intent_lower for kw in ['refactor', 'rewrite', 'overhaul']):
                out.append(f"  AoE {{WARN}}: Intent is large-scope refactor — high change volume expected")
                _warnings.append('warn')

        # 2e: AoE vector config warn/risk scan
        try:
            _avc_path = _plans_root / "aoe_vector_config.json"
            if _avc_path.exists():
                _avc = json.loads(_avc_path.read_text(encoding="utf-8"))
                _vector_checks = {
                    'ec_risk_level':      ('risk_level',   _ce, lambda v: v in ('HIGH', 'CRITICAL'), 'RISK'),
                    'ec_risk_reasons':    ('risk_reasons',  _ce, lambda v: bool(v),                   'WARN'),
                    'ec_test_status':     ('test_status',   _ce, lambda v: v and v.upper() not in ('OK','PASS',''), 'WARN'),
                    'ec_probe_status':    ('probe_status',  _ce, lambda v: v == 'FAIL',               'WARN'),
                }
                _vec_fired = set()
                for _layer in _avc.get("layers", []):
                    for _vec in _layer.get("vectors", []):
                        _vid = _vec.get("id")
                        if _vid in _vector_checks and (_vec.get("warn_field") or _vec.get("risk_field")):
                            _field, _src_dict, _check_fn, _level = _vector_checks[_vid]
                            _val = _src_dict.get(_field)
                            try:
                                if _check_fn(_val) and _vid not in _vec_fired:
                                    _disp = _vec.get("display", _vid)
                                    out.append(f"  AoE {{{_level}}} [{_vid}]: '{_disp}' = {_val}")
                                    _vec_fired.add(_vid)
                            except Exception:
                                pass
        except Exception:
            pass

        # Summary line
        _crit = _warnings.count('critical')
        _risk = _warnings.count('risk')
        _warn = _warnings.count('warn')
        out.append("")
        _parts = []
        if _crit: _parts.append(f"{_crit} CRITICAL")
        if _risk: _parts.append(f"{_risk} RISK")
        if _warn: _parts.append(f"{_warn} WARN")
        if _parts:
            out.append(f"  AoE Summary: {' | '.join(_parts)}")
        else:
            out.append(f"  AoE Summary: AoE {{INFO}} — no elevated risk detected")
        out.append("")

        # ═══════════════════════════════════════
        # SECTION 3: PROJECT CONTEXT
        # ═══════════════════════════════════════
        out.append("[PROJECT CONTEXT]")
        _project_found = False
        _proj_id = None
        _proj_doc = None
        try:
            _pat_scan = _file_base.lower()

            # Scan Plans/*/
            _plans_dir = _plans_root / "Plans"
            if _plans_dir.exists():
                for _pdir in sorted(_plans_dir.iterdir()):
                    if not _pdir.is_dir():
                        continue
                    for _md in _pdir.glob("*.md"):
                        try:
                            if _pat_scan in _md.read_text(encoding="utf-8", errors="ignore").lower()[:3000]:
                                _proj_id = _pdir.name
                                _proj_doc = str(_md)
                                break
                        except Exception:
                            pass
                    if _proj_id:
                        break

            # Scan Epics/
            if not _proj_id:
                _epics_dir = _plans_root / "Epics"
                if _epics_dir.exists():
                    for _epic in sorted(_epics_dir.glob("*.md")):
                        try:
                            if _pat_scan in _epic.read_text(encoding="utf-8", errors="ignore").lower()[:3000]:
                                _proj_id = _epic.stem
                                _proj_doc = str(_epic)
                                break
                        except Exception:
                            pass

            # Fallback: project_id from enriched_changes
            if not _proj_id and _ce.get('project_id'):
                _proj_id = _ce['project_id']

            if _proj_id:
                _project_found = True
                out.append(f"  Project  : {_proj_id}")
                if _proj_doc:
                    out.append(f"  Plan Doc : {_proj_doc}")
                # Active tasks for this project
                try:
                    _ls_path = _data_root / "plans" / "Refs" / "latest_sync.json"
                    if _ls_path.exists():
                        _ls = json.loads(_ls_path.read_text(encoding="utf-8"))
                        _proj_tasks = [(tid, t) for tid, t in _ls.get("tasks", {}).items()
                                       if _proj_id.lower() in (t.get("project_id") or "").lower()]
                        if _proj_tasks:
                            out.append(f"  Project Tasks ({len(_proj_tasks)}):")
                            for _tid, _t in _proj_tasks:
                                _st = _t.get('status', '?')[:12]
                                _ttl = _t.get('title', '')[:55]
                                out.append(f"    [{_st}] {_tid}: {_ttl}")
                except Exception:
                    pass
            else:
                out.append("  (unlinked — no Plans/ or Epics/ document references this file)")
        except Exception as _pe:
            out.append(f"  (project resolution error: {_pe})")
        out.append("")

        # ═══════════════════════════════════════
        # SECTION 3b: CALL GRAPH
        # ═══════════════════════════════════════
        _call_edges_total = _cg.get('call_edges', 0)
        _top_edges        = _cg.get('top_edges', [])
        _cg_imports       = _cg.get('imports', [])
        _cg_importers     = _cg.get('imported_by', [])
        _has_cg_data      = bool(_call_edges_total or _cg_imports or _cg_importers)

        # Try to load pymanifest/state.json for NetworkX-generated callgraph metrics
        _cg_crash      = []
        _cg_suspicious = {}
        _cg_sha        = "none"
        try:
            _state_path = _data_root / "pymanifest" / "state.json"
            if _state_path.exists():
                _state         = json.loads(_state_path.read_text(encoding="utf-8"))
                _cg_state      = _state.get("call_graph", {})
                _cg_crash      = _cg_state.get("crash_points", [])
                _cg_suspicious = _cg_state.get("suspicious_paths", {})
                _cg_sha        = _cg_state.get("graph_sha", "none")
        except Exception:
            pass

        if _has_cg_data or _cg_crash or _cg_suspicious:
            out.append("[CALL GRAPH]")
            if _cg_sha != "none":
                out.append(f"  sha:{_cg_sha[:8]}  crash_points:{len(_cg_crash)}  suspicious:{len(_cg_suspicious)}")
                if _cg_crash[:3]:
                    for _cp in _cg_crash[:3]:
                        out.append(f"    ⚠ {_cp}")
            if _cg_imports:
                _imp_preview = ', '.join(_cg_imports[:3])
                _imp_more = f"  (+{len(_cg_imports)-3} more)" if len(_cg_imports) > 3 else ""
                out.append(f"  Imports     ({len(_cg_imports)}): {_imp_preview}{_imp_more}")
            if _cg_importers:
                _iby_preview = ', '.join(_cg_importers[:3])
                _iby_more = f"  (+{len(_cg_importers)-3} more)" if len(_cg_importers) > 3 else ""
                out.append(f"  Imported By ({len(_cg_importers)}): {_iby_preview}{_iby_more}")
            if _call_edges_total:
                out.append(f"  Call Edges  : {_call_edges_total}")
                if _top_edges[:3]:
                    for _e in _top_edges[:3]:
                        out.append(f"    → {_e}")
            out.append("")

        # ═══════════════════════════════════════
        # SECTION 4: RECOMMENDED TASKS
        # ═══════════════════════════════════════
        out.append("[RECOMMENDED TASKS]")
        _recs = []
        _unresolved_p = _ce.get('unresolved_probes', 0) if _ce else 0
        _risk_latest = (_ce.get('risk_level', 'LOW') if _ce else 'LOW').upper()
        _n_imp = len(_cg.get('imported_by', []))

        if _unresolved_p:
            _recs.append(("P0", f"Resolve {_unresolved_p} existing probe FAIL(s) before making new changes"))
        if _risk_latest in ('HIGH', 'CRITICAL'):
            _recs.append(("P0", "Create a versioned backup before touching this file (high-risk history)"))
        if _intent_lower and 'import' in _intent_lower:
            _recs.append(("P1", "Verify all new imports are available in the runtime environment"))
        if _intent_lower and any(kw in _intent_lower for kw in ['checklist', 'todos', 'latest_sync', 'version_manifest']):
            _recs.append(("P1", "Validate JSON schema of coordination data store after write"))
        if _n_imp >= 5:
            _recs.append(("P1", f"Run downstream tests: {_n_imp} files import this — verify none break"))
        _recs.append(("P2", f"Run py_compile after changes: python3 -m py_compile <file>"))
        _recs.append(("P2", "Run AUTO_TEST probe to confirm PASS status"))
        if not _project_found:
            _recs.append(("P3", "Link this file to a project: reference it in Plans/ or Epics/"))

        for _idx, (_pri, _desc) in enumerate(_recs, 1):
            out.append(f"  {_idx}. [{_pri}] {_desc}")
        out.append("")

        # ═══════════════════════════════════════
        # SECTION 4b: TASK LIFECYCLE
        # ═══════════════════════════════════════
        try:
            _cfg_path = _plans_root / "config.json"
            if _cfg_path.exists():
                _cfg = json.loads(_cfg_path.read_text(encoding="utf-8"))
                _atid = _cfg.get("active_task_id", "")
                _awh = _cfg.get("active_task_wherein", "")
                _aat = _cfg.get("activated_at", "")
                if _atid:
                    out.append("[TASK LIFECYCLE]")
                    out.append(f"  Active: {_atid} (since {_aat[:16] if _aat else '?'})")
                    # Check if assessing a different file than the active task
                    if _awh and _file_base.lower() not in _awh.lower():
                        out.append(f"  ⚠ Assessing '{file_pattern}' but active task targets '{Path(_awh).name}'")
                        # Find matching tasks for the assessed file
                        _ls_lc_path = _data_root / "plans" / "Refs" / "latest_sync.json"
                        if _ls_lc_path.exists():
                            _ls_lc = json.loads(_ls_lc_path.read_text(encoding="utf-8"))
                            _matching = [(tid, t) for tid, t in _ls_lc.get("tasks", {}).items()
                                         if _file_base.lower() in (t.get("wherein", "") or "").lower()
                                         and t.get("status", "").upper() in ("READY", "IN_PROGRESS", "OPEN")]
                            if _matching:
                                _best_tid, _best_t = _matching[0]
                                out.append(f"  → Suggest: todo activate {_best_tid}  ({_best_t.get('title', '')[:40]})")
                    # Check probe resolution status for active task
                    _vm_path_lc = _data_root / "backup" / "version_manifest.json"
                    if _vm_path_lc.exists():
                        _vm_lc = json.loads(_vm_path_lc.read_text(encoding="utf-8"))
                        _ec_lc = _vm_lc.get("enriched_changes", {})
                        _active_probes = [(eid, ch) for eid, ch in _ec_lc.items()
                                          if _atid in (ch.get('task_ids') or []) and ch.get('probe_status') == 'FAIL'
                                          and not ch.get('resolved_by')]
                        if not _active_probes:
                            out.append(f"  ✓ No unresolved probe failures for {_atid}")
                        else:
                            out.append(f"  ✗ {len(_active_probes)} unresolved probe FAIL(s) for {_atid}")
                    out.append("")
        except Exception:
            pass

        # ═══════════════════════════════════════
        # SECTION 5: RELATED ACTIVE TASKS
        # ═══════════════════════════════════════
        out.append("[RELATED ACTIVE TASKS]")
        _task_list = _ta.get('tasks', [])
        _task_total = _ta.get('task_count', 0)
        if _task_list:
            out.append(f"  {_task_total} task(s) matching '{file_pattern}':")
            try:
                _ls_path = _data_root / "plans" / "Refs" / "latest_sync.json"
                if _ls_path.exists():
                    _ls = json.loads(_ls_path.read_text(encoding="utf-8"))
                    _ls_tasks = _ls.get("tasks", {})
                    for _t_summary in _task_list:
                        _tid = _t_summary.get('id', '?')
                        _full = _ls_tasks.get(_tid, _t_summary)
                        _st = _full.get('status', '?')
                        _pri = _full.get('priority', '')
                        _ttl = _full.get('title', '')[:60]
                        _pd = _full.get('plan_doc', '')
                        _icon = "✓" if _st.upper() in ('COMPLETE', 'DONE') else "○"
                        _line = f"  {_icon} {_tid}: {_ttl} [{_st}"
                        if _pri:
                            _line += f" | {_pri}"
                        _line += "]"
                        out.append(_line)
                        if _pd:
                            out.append(f"      plan: {_pd}")
            except Exception:
                for _t in _task_list:
                    _icon = "✓" if _t.get('status', '').upper() in ('COMPLETE', 'DONE') else "○"
                    out.append(f"  {_icon} {_t.get('id','?')}: {_t.get('title','')[:60]} ({_t.get('status','?')})")
        else:
            out.append(f"  No tasks in latest_sync.json with wherein='{file_pattern}'")
        out.append("")

        # ── ACTIVE TASK ──
        try:
            _cfg_path = _data_root / "plans" / "config.json"
            if _cfg_path.exists():
                _cfg = json.loads(_cfg_path.read_text(encoding="utf-8"))
                _atid = _cfg.get("active_task_id", "")
                if _atid:
                    _awh = _cfg.get("active_task_wherein", "")
                    _aat = _cfg.get("activated_at", "?")[:16]
                    _lat = _cfg.get("last_activity_at", "")[:16]
                    out.append("[ACTIVE TASK]")
                    out.append(f"  Task: {_atid}  |  File: {Path(_awh).name if _awh else '?'}  |  Since: {_aat}")
                    if _lat:
                        out.append(f"  Last Activity: {_lat}")
                    # Smart intent suggestion
                    _qf = file_pattern if file_pattern else 'FILE'
                    if _awh and Path(_awh).name != _qf:
                        out.append(f"  ⚠ You're querying {_qf} but active task targets {Path(_awh).name}")
                        out.append(f"  → todo activate TASK_ID         Switch active task")
                    out.append("")
        except Exception:
            pass

        # ── NEXT STEPS ──
        out.append("[NEXT STEPS]")
        out.append(f"  → query {file_pattern} --graph       See call graph edges")
        out.append(f"  → query {file_pattern} --suggest     Get actionable CLI suggestions")
        if _project_found and _proj_id:
            out.append(f"  → plan report                    Project health report")
        out.append(f"  → latest                         Recent changes + probe status")
        out.append(f"  → todo view                      Full task board")
        out.append("")
        out.append("=" * 60)

        return "\n".join(out)

    # ============================================================================
    # EXPORT AND REPORTING
    # ============================================================================

    def generate_manifest(self, format: str = "json") -> str:
        """Generate hierarchical manifest of the system"""
        print("[*] Generating system manifest...")
        
        # Build hierarchical structure
        manifest = {
            'metadata': {
                'generated': datetime.now().isoformat(),
                'session_id': self.session_id,
                'hostname': self.hostname,
                'os_type': self.os_type.value,
                'architecture': self.architecture,
                'statistics': {
                    'taxonomic_nodes': len(self.session.taxonomic_tree),
                    'artifacts': len(self.session.artifacts),
                    'verbs': len(self.session.verbs),
                    'journal_entries': len(self.session.journal_entries),
                }
            },
            'taxonomic_tree': self._build_hierarchical_tree(),
            'artifacts_summary': self._build_artifacts_summary(),
            'verbs_summary': self._build_verbs_summary(),
            'timeline': self._build_timeline(),
        }
        
        # Save manifest
        manifest_file = self.manifest_dir / f"manifest_{self.session_id}.json"
        with open(manifest_file, 'w') as f:
            json.dump(manifest, f, indent=2)
        
        log_event("MANIFEST_SAVED", f"System manifest saved to {manifest_file}", context={"path": str(manifest_file), "session": self.session_id})
        print(f"[+] Manifest saved to: {manifest_file}")
        
        if format == "text":
            return self._manifest_to_text(manifest)
        else:
            return json.dumps(manifest, indent=2)
    
    def _build_hierarchical_tree(self) -> Dict[str, Any]:
        """Build hierarchical tree structure from taxonomic nodes"""
        tree = {}
        
        # Find root nodes (nodes without parents)
        roots = []
        for node_id, node in self.session.taxonomic_tree.items():
            if not node.parent_id:
                roots.append(node_id)
        
        # Build tree recursively
        def build_branch(node_id: str) -> Dict[str, Any]:
            node = self.session.taxonomic_tree.get(node_id)
            if not node:
                return {}
            
            branch = {
                'node_id': node_id,
                'name': node.name,
                'taxonomy_type': node.taxonomy_type.value if hasattr(node.taxonomy_type, 'value') else node.taxonomy_type,
                'sixw1h': node.sixw1h.to_dict(),
                'children': []
            }
            
            for child_id in node.children_ids:
                child_branch = build_branch(child_id)
                if child_branch:
                    branch['children'].append(child_branch)
            
            return branch
        
        # Build from roots
        for root_id in roots:
            tree[root_id] = build_branch(root_id)
        
        return tree
    
    def _build_artifacts_summary(self) -> Dict[str, Any]:
        """Build summary of artifacts"""
        summary = {
            'total': len(self.session.artifacts),
            'by_type': defaultdict(int),
            'by_security_context': defaultdict(int),
            'size_distribution': {
                'tiny': 0,      # < 1KB
                'small': 0,     # 1KB - 1MB
                'medium': 0,    # 1MB - 100MB
                'large': 0,     # 100MB - 1GB
                'huge': 0,      # > 1GB
            },
            'recent_artifacts': []
        }
        
        # Categorize artifacts
        for artifact in self.session.artifacts.values():
            # Count by type
            summary['by_type'][artifact.artifact_type.value] += 1
            
            # Count by security context
            summary['by_security_context'][artifact.security_context.value] += 1
            
            # Size distribution
            size_mb = artifact.size_bytes / (1024 * 1024)
            if artifact.size_bytes < 1024:
                summary['size_distribution']['tiny'] += 1
            elif size_mb < 1:
                summary['size_distribution']['small'] += 1
            elif size_mb < 100:
                summary['size_distribution']['medium'] += 1
            elif size_mb < 1024:
                summary['size_distribution']['large'] += 1
            else:
                summary['size_distribution']['huge'] += 1
        
        # Get recent artifacts (last 10)
        recent = sorted(self.session.artifacts.values(), 
                       key=lambda x: x.timestamp_modified, 
                       reverse=True)[:10]
        
        for artifact in recent:
            summary['recent_artifacts'].append({
                'artifact_id': artifact.artifact_id,
                'type': artifact.artifact_type.value,
                'size_bytes': artifact.size_bytes,
                'modified': artifact.timestamp_modified,
                'security': artifact.security_context.value
            })
        
        return summary
    
    def _build_verbs_summary(self) -> Dict[str, Any]:
        """Build summary of system verbs"""
        summary = {
            'total': len(self.session.verbs),
            'by_domain': defaultdict(int),
            'common_verbs': []
        }
        
        # Categorize verbs
        for verb in self.session.verbs.values():
            summary['by_domain'][verb.domain.value] += 1
        
        # Get common verbs (most used domains)
        domain_counts = sorted(summary['by_domain'].items(), key=lambda x: x[1], reverse=True)
        summary['common_domains'] = domain_counts[:5]
        
        return summary
    
    def _build_timeline(self) -> List[Dict[str, Any]]:
        """Build timeline of events"""
        timeline = []
        
        # Add artifact creation/modification events
        for artifact in self.session.artifacts.values():
            timeline.append({
                'timestamp': artifact.timestamp_created,
                'event_type': 'artifact_created',
                'artifact_id': artifact.artifact_id,
                'description': f"File created: {artifact.sixw1h.what}"
            })
            
            if artifact.timestamp_modified != artifact.timestamp_created:
                timeline.append({
                    'timestamp': artifact.timestamp_modified,
                    'event_type': 'artifact_modified',
                    'artifact_id': artifact.artifact_id,
                    'description': f"File modified: {artifact.sixw1h.what}"
                })
        
        # Add journal entries
        for entry in self.session.journal_entries:
            timeline.append({
                'timestamp': entry['timestamp'],
                'event_type': f"journal_{entry['entry_type']}",
                'description': entry['content'],
                'tags': entry['tags']
            })
        
        # Sort by timestamp
        timeline.sort(key=lambda x: x['timestamp'])
        
        return timeline[-100:]  # Last 100 events
    
    def _manifest_to_text(self, manifest: Dict[str, Any]) -> str:
        """Convert manifest to text format"""
        lines = []
        
        lines.append("=" * 80)
        lines.append("SYSTEM MANIFEST")
        lines.append("=" * 80)
        
        # Metadata
        meta = manifest['metadata']
        lines.append(f"\n[SYSTEM]")
        lines.append(f"  Hostname: {meta['hostname']}")
        lines.append(f"  OS: {meta['os_type']}")
        lines.append(f"  Architecture: {meta['architecture']}")
        lines.append(f"  Session: {meta['session_id']}")
        lines.append(f"  Generated: {meta['generated']}")
        
        # Statistics
        stats = meta['statistics']
        lines.append(f"\n[STATISTICS]")
        lines.append(f"  Taxonomic Nodes: {stats['taxonomic_nodes']}")
        lines.append(f"  Artifacts: {stats['artifacts']}")
        lines.append(f"  Verbs: {stats['verbs']}")
        lines.append(f"  Journal Entries: {stats['journal_entries']}")
        
        # Taxonomic tree summary
        lines.append(f"\n[TAXONOMIC TREE]")
        for root_id, root in manifest['taxonomic_tree'].items():
            lines.append(f"  Root: {root['name']} ({root['taxonomy_type']})")
            lines.append(f"    Children: {len(root['children'])}")
        
        # Artifacts summary
        art_summary = manifest['artifacts_summary']
        lines.append(f"\n[ARTIFACTS]")
        lines.append(f"  Total: {art_summary['total']}")
        lines.append(f"  By Type:")
        for art_type, count in sorted(art_summary['by_type'].items()):
            lines.append(f"    {art_type}: {count}")
        
        # Recent artifacts
        lines.append(f"\n  Recent Artifacts:")
        for art in art_summary['recent_artifacts'][:5]:
            lines.append(f"    {art['artifact_id'][:8]}...: {art['type']} ({art['size_bytes']} bytes)")
        
        # Verbs summary
        verb_summary = manifest['verbs_summary']
        lines.append(f"\n[VERBS]")
        lines.append(f"  Total: {verb_summary['total']}")
        lines.append(f"  By Domain:")
        for domain, count in sorted(verb_summary['by_domain'].items()):
            lines.append(f"    {domain}: {count}")
        
        # Timeline
        lines.append(f"\n[TIMELINE]")
        lines.append(f"  Last {len(manifest['timeline'])} events")
        for event in manifest['timeline'][-5:]:  # Last 5 events
            time_str = event['timestamp'].split('T')[1][:8]
            lines.append(f"    [{time_str}] {event['event_type']}: {event['description'][:50]}...")
        
        return '\n'.join(lines)
    
    def export_session(self, format: str = "json", custom_dir: Path = None) -> Path:
        """Export complete session with ALL Babel components"""
        print(f"[*] Exporting session: {self.session_id}")

        # Save session first
        session_dir = self.session.save(self.session_dir)

        # Generate manifest
        manifest = self.generate_manifest(format)

        # Create export package
        export_time = datetime.now().strftime("%Y%m%d_%H%M%S")
        export_name = f"babel_export_{self.session_id}_{export_time}"

        # Use custom directory if provided
        base_export_dir = custom_dir if custom_dir else self.export_dir
        export_path = base_export_dir / export_name
        export_path.mkdir(exist_ok=True, parents=True)

        # Copy session data
        import shutil
        for item in session_dir.iterdir():
            if item.is_file():
                shutil.copy2(item, export_path / item.name)
        
        # Save manifest
        manifest_file = export_path / f"manifest_{self.session_id}.{format}"
        if format == "json":
            with open(manifest_file, 'w') as f:
                f.write(manifest)
        else:
            with open(manifest_file, 'w') as f:
                f.write(manifest)

        print("[*] Generating system manifest...")

        # Export Filesync Timeline & Organized Files
        print("[*] Exporting Filesync timeline...")
        filesync_dir = Path.cwd() / "babel_data" / "timeline"
        if filesync_dir.exists():
            filesync_export = export_path / "filesync_timeline"
            filesync_export.mkdir(exist_ok=True)

            # Copy manifests
            if (filesync_dir / "manifests").exists():
                shutil.copytree(filesync_dir / "manifests", filesync_export / "manifests")

            # Copy organized files
            if (filesync_dir / "organized").exists():
                shutil.copytree(filesync_dir / "organized", filesync_export / "organized")

        # Export Onboarder Consolidated Menu & Session
        print("[*] Exporting Onboarder consolidated menu...")
        onboarder_menu = Path.cwd() / "consolidated_menu.json"
        if onboarder_menu.exists():
            shutil.copy2(onboarder_menu, export_path / "consolidated_menu.json")

        onboarder_sessions = Path.cwd() / ".onboarding_sessions"
        if onboarder_sessions.exists():
            shutil.copytree(onboarder_sessions, export_path / "onboarder_sessions")

        # Export Plans & Todos
        print("[*] Exporting plans and todos...")
        plans_dir = Path.cwd() / "plans"
        if plans_dir.exists():
            plans_export = export_path / "plans"
            plans_export.mkdir(exist_ok=True)
            for item in plans_dir.glob("*"):
                if item.is_file():
                    shutil.copy2(item, plans_export / item.name)

        # Export Trust Registry
        print("[*] Exporting trust registry...")
        trust_registry = self.base_dir / "trust_registry.json"
        if trust_registry.exists():
            shutil.copy2(trust_registry, export_path / "trust_registry.json")

        # Copy the Triad scripts themselves
        print("[*] Exporting Babel Triad scripts...")
        bin_dir = export_path / "bin"
        bin_dir.mkdir(exist_ok=True)
        for script in ['Os_Toolkit.py', 'Filesync.py', 'onboarder.py']:
            if Path(script).exists():
                shutil.copy2(script, bin_dir / script)
                # Make executable
                (bin_dir / script).chmod(0o755)

        # Copy the Babel launcher
        print("[*] Exporting Babel launcher...")
        babel_launcher = Path.cwd() / "babel"
        if babel_launcher.exists():
            shutil.copy2(babel_launcher, export_path / "babel")
            # Make executable
            (export_path / "babel").chmod(0o755)

        # Copy the installer script
        print("[*] Exporting installer...")
        install_script = Path.cwd() / "install.sh"
        if install_script.exists():
            shutil.copy2(install_script, export_path / "install.sh")
            # Make executable
            (export_path / "install.sh").chmod(0o755)

        # Export complete babel_data directory structure
        print("[*] Exporting complete babel_data catalog...")
        babel_data_dir = Path.cwd() / "babel_data"
        if babel_data_dir.exists():
            babel_data_export = export_path / "babel_data"
            babel_data_export.mkdir(exist_ok=True)

            # Copy profile directory (sessions, catalogs)
            if (babel_data_dir / "profile").exists():
                shutil.copytree(babel_data_dir / "profile", babel_data_export / "profile")

            # Copy inventory directory
            if (babel_data_dir / "inventory").exists():
                shutil.copytree(babel_data_dir / "inventory", babel_data_export / "inventory")

            # Timeline already copied above, but ensure complete structure
            if (babel_data_dir / "timeline").exists() and not (babel_data_export / "timeline").exists():
                shutil.copytree(babel_data_dir / "timeline", babel_data_export / "timeline")

        # Create README
        readme = f"""# Babel System Export (Complete)

## Export Information
- Session ID: {self.session_id}
- Hostname: {self.hostname}
- OS Type: {self.os_type.value}
- Architecture: {self.architecture}
- Export Time: {datetime.now().isoformat()}

## The Babel System (Complete Package)

### Core Scripts (The Triad)
1. **Os_Toolkit.py** - "The Oracle" - Forensic OS profiler with 6W1H classification
2. **Filesync.py** - "The Librarian" - File organizer & timeline reconstructor
3. **onboarder.py** - "The Bridge" - Tool discovery, consolidation, launcher

### Distribution Components
- **babel** - Unified launcher (single entry point for all commands)
- **install.sh** - Automated installer (dependency checking, directory setup)
- **babel_data/** - Complete system state (all catalogs, manifests, sessions)

## Complete Export Contents

### Core System (bin/)
- **Os_Toolkit.py** - Forensic profiler with 6W1H classification
- **Filesync.py** - File organizer & timeline reconstructor
- **onboarder.py** - Tool discovery & consolidation
- **babel** - Unified launcher (root level)
- **install.sh** - Automated installer (root level)

### System State (babel_data/)
- **profile/** - All catalog sessions with forensic data
- **timeline/** - File organization manifests & temporal maps
- **inventory/** - Tool inventory & discovery sessions

### Session Data (Current Session: {self.session_id})
- Taxonomic Nodes: {len(self.session.taxonomic_tree)}
- Artifacts: {len(self.session.artifacts)}
- Verbs: {len(self.session.verbs)}
- Journal Entries: {len(self.session.journal_entries)}
- Queries Executed: {len(self.session.query_history)}
- System manifest ({format} format)
- Trust registry (security baseline)

### Integration Data
- **Filesync Timeline** - Organized by date, project clustering
- **Onboarder Menu** - Consolidated tool menu with all discovered tools
- **Plans & Todos** - Strategic plans with status tracking

## Quick Start

### 1. Install (Recommended)
```bash
cd {export_name}
./install.sh
```
This will:
- Check Python >= 3.8 and optional dependencies
- Create directory structure
- Make scripts executable
- Optionally add to PATH

### 2. Use Unified Launcher
```bash
# After install, use the unified babel launcher
./babel --help              # Show all commands
./babel morning             # Morning briefing
./babel latest -z           # System state (GUI)
./babel catalog             # Full system catalog
./babel query "filename"    # Query files
./babel sync-todos          # Sync todos
```

### 3. Direct Script Access
```bash
# Restore session with full catalog context
python3 bin/Os_Toolkit.py --session {self.session_id}

# Launch consolidated menu
python3 bin/onboarder.py run-menu

# Query timeline
python3 bin/Filesync.py . --manifest
```

Generated by Babel v{VERSION}
"""

        with open(export_path / "README.md", 'w') as f:
            f.write(readme)

        # Create archive
        archive_path = base_export_dir / f"{export_name}.tar.gz"
        shutil.make_archive(str(archive_path).replace('.tar.gz', ''), 'gztar', export_path)
        
        # Cleanup
        shutil.rmtree(export_path)
        
        print(f"[+] Session exported to: {archive_path}")
        
        return archive_path
    
    # ============================================================================
    # JOURNAL MANAGEMENT
    # ============================================================================
    
    def journal_add(self, entry_type: str, content: str, tags: List[str] = None):
        """Add journal entry"""
        self.session.add_journal_entry(entry_type, content, tags)
        print(f"[+] Journal entry added: {entry_type}")
    
    def journal_query(self, query: str = "", entry_type: str = "", limit: int = 20):
        """Query journal entries"""
        results = []
        
        for entry in self.session.journal_entries:
            # Apply filters
            if query and query.lower() not in entry['content'].lower():
                continue
            if entry_type and entry_type != entry['entry_type']:
                continue
            
            results.append(entry)
            
            if len(results) >= limit:
                break
        
        return {
            'query': query,
            'entry_type_filter': entry_type,
            'results': results,
            'count': len(results),
            'total_entries': len(self.session.journal_entries)
        }
    
    def journal_stats(self):
        """Get journal statistics"""
        stats = {
            'total_entries': len(self.session.journal_entries),
            'by_type': defaultdict(int),
            'by_day': defaultdict(int),
            'recent_entries': []
        }
        
        # Count by type and day
        for entry in self.session.journal_entries:
            stats['by_type'][entry['entry_type']] += 1
            
            # Extract date
            date_str = entry['timestamp'].split('T')[0]
            stats['by_day'][date_str] += 1
        
        # Get recent entries
        stats['recent_entries'] = self.session.journal_entries[-10:] if self.session.journal_entries else []
        
        return stats
    
    # ============================================================================
    # UTILITIES
    # ============================================================================
    
    def get_stats(self) -> Dict[str, Any]:
        """Get toolkit statistics"""
        elapsed = datetime.now() - self.stats['start_time']
        
        stats = {
            'session_id': self.session_id,
            'hostname': self.hostname,
            'os_type': self.os_type.value,
            'runtime_seconds': int(elapsed.total_seconds()),
            'start_time': self.stats['start_time'].isoformat(),
            'artifacts_analyzed': self.stats['artifacts_analyzed'],
            'files_processed': self.stats['files_processed'],
            'queries_executed': self.stats['queries_executed'],
            'session_statistics': {
                'taxonomic_nodes': len(self.session.taxonomic_tree),
                'artifacts': len(self.session.artifacts),
                'verbs': len(self.session.verbs),
                'journal_entries': len(self.session.journal_entries),
                'query_history': len(self.session.query_history),
            }
        }
        
        return stats
    
    def save(self):
        """Save current session"""
        session_dir = self.session.save(self.session_dir)
        print(f"[+] Session saved to: {session_dir}")
        return session_dir
    
    def close(self):
        """Close toolkit and save session"""
        print("[*] Closing toolkit...")
        self.save()
        print("[+] Toolkit closed")

# ============================================================================
# COMMAND LINE INTERFACE
# ============================================================================

def _resolve_base_dir_and_session(args_base_dir, args_session):
    """Resolve base_dir and session, auto-detecting latest session when not specified."""
    base_dir = Path(args_base_dir)

    # Auto-find latest session if none specified
    session_id = args_session
    if not session_id:
        found = ForensicOSToolkit.find_latest_session(base_dir)
        if found:
            session_id = found
            print(f"[+] Auto-loaded session: {session_id}")
        else:
            print("[*] No existing sessions found. A new session will be created.")

    return base_dir, session_id


def display_output(content, title="Babel Center", use_zenity=False):
    """Display output to CLI or Zenity."""
    print(content)
    if use_zenity:
        try:
            subprocess.run(['zenity', '--text-info', '--title', title, '--width', '800', '--height', '600', '--font=Monospace 10'],
                           input=content, text=True)
        except Exception as e:
            print(f"[-] Zenity failed: {e}")


#[Mark:SWEEP1-COMPLETE] Zenity Helper Functions & Interactive Display
# Sweep 1: Foundation - Enable interactive Zenity widgets beyond text-info
# Added 2026-02-07 - Supports forms, checklists, progress, notifications, action dialogs


def zenity_forms(fields: List[Dict[str, str]], title: str = "Input Form") -> Optional[Dict[str, str]]:
    """
    Display Zenity forms dialog for structured input.

    Args:
        fields: List of dicts with {'name': 'field_name', 'label': 'Display Label', 'default': 'value'}
        title: Window title

    Returns:
        Dict mapping field names to user input, or None if cancelled

    Example:
        result = zenity_forms([
            {'name': 'task_id', 'label': 'Task ID', 'default': ''},
            {'name': 'title', 'label': 'Title', 'default': ''},
            {'name': 'priority', 'label': 'Priority', 'default': 'P2'}
        ], title="Add Todo")
    """
    try:
        cmd = ['zenity', '--forms', '--title', title, '--separator', '\n']
        for field in fields:
            cmd.extend(['--add-entry', field.get('label', field['name'])])
            if field.get('default'):
                cmd.append(f"--forms-date-format={field['default']}")  # Hack to set default via unused param

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            return None

        # Parse output - one value per line
        values = result.stdout.strip().split('\n')
        return {fields[i]['name']: values[i] for i in range(min(len(fields), len(values)))}
    except Exception as e:
        print(f"[-] Zenity forms failed: {e}")
        return None


def zenity_checklist(items: List[Dict[str, Any]], title: str = "Select Items",
                     text: str = "Choose items:") -> List[str]:
    """
    Display Zenity checklist for multi-select.

    Args:
        items: List of dicts with {'id': 'unique_id', 'label': 'Display', 'checked': bool}
        title: Window title
        text: Header text

    Returns:
        List of selected item IDs

    Example:
        selected = zenity_checklist([
            {'id': 'P0-1', 'label': 'Remove Gemini from SYSTEM_DNA', 'checked': True},
            {'id': 'P1-2', 'label': 'Add log integration', 'checked': False}
        ], title="Select Tasks", text="Which tasks to work on?")
    """
    try:
        cmd = ['zenity', '--list', '--checklist', '--title', title, '--text', text,
               '--column', 'Select', '--column', 'ID', '--column', 'Description',
               '--separator', '\n', '--width', '700', '--height', '400']

        for item in items:
            checked = 'TRUE' if item.get('checked', False) else 'FALSE'
            cmd.extend([checked, str(item['id']), item.get('label', item['id'])])

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            return []

        # Parse output - selected IDs separated by newlines
        return [line.strip() for line in result.stdout.strip().split('\n') if line.strip()]
    except Exception as e:
        print(f"[-] Zenity checklist failed: {e}")
        return []


def zenity_progress(title: str = "Processing", text: str = "Please wait...",
                    pulsate: bool = False) -> subprocess.Popen:
    """
    Start Zenity progress bar (returns Popen object for updating).

    Args:
        title: Window title
        text: Description text
        pulsate: If True, show activity indicator; if False, expect percentage updates

    Returns:
        Popen object - send "PERCENTAGE\n" to stdin to update, close stdin when done

    Example:
        progress = zenity_progress(title="Scanning", text="Analyzing files...")
        for i in range(0, 101, 10):
            progress.stdin.write(f"{i}\n".encode())
            progress.stdin.flush()
            time.sleep(0.5)
        progress.stdin.close()
        progress.wait()
    """
    try:
        cmd = ['zenity', '--progress', '--title', title, '--text', text, '--width', '400']
        if pulsate:
            cmd.append('--pulsate')

        return subprocess.Popen(cmd, stdin=subprocess.PIPE, text=True)
    except Exception as e:
        print(f"[-] Zenity progress failed: {e}")
        return None


def zenity_notification(message: str, urgency: str = "normal"):
    """
    Display desktop notification.

    Args:
        message: Notification text
        urgency: "low" | "normal" | "critical"

    Example:
        zenity_notification("Security check complete - 3 warnings found", urgency="critical")
    """
    try:
        subprocess.run(['zenity', '--notification', '--text', message], check=False)
    except Exception as e:
        print(f"[-] Zenity notification failed: {e}")


def zenity_question(text: str, title: str = "Confirm", ok_label: str = "Yes",
                   cancel_label: str = "No") -> bool:
    """
    Display yes/no question dialog.

    Args:
        text: Question to ask
        title: Window title
        ok_label: Label for confirm button
        cancel_label: Label for cancel button

    Returns:
        True if user clicked Yes/OK, False otherwise

    Example:
        if zenity_question("Run suggested command: git status?", title="Execute?"):
            subprocess.run(['git', 'status'])
    """
    try:
        result = subprocess.run([
            'zenity', '--question', '--title', title, '--text', text,
            '--ok-label', ok_label, '--cancel-label', cancel_label,
            '--width', '400'
        ])
        return result.returncode == 0
    except Exception as e:
        print(f"[-] Zenity question failed: {e}")
        return False


def zenity_radiolist(items: List[Dict[str, str]], title: str = "Select Option",
                    text: str = "Choose one:") -> Optional[str]:
    """
    Display Zenity radiolist for single-select from options.

    Args:
        items: List of dicts with {'id': 'unique_id', 'label': 'Display', 'selected': bool}
        title: Window title
        text: Header text

    Returns:
        Selected item ID or None if cancelled

    Example:
        action = zenity_radiolist([
            {'id': 'run_tests', 'label': 'Run test suite', 'selected': True},
            {'id': 'check_security', 'label': 'Security scan', 'selected': False},
            {'id': 'sync_todos', 'label': 'Sync all todos', 'selected': False}
        ], title="Suggested Actions", text="What would you like to do next?")
    """
    try:
        cmd = ['zenity', '--list', '--radiolist', '--title', title, '--text', text,
               '--column', 'Select', '--column', 'ID', '--column', 'Action',
               '--width', '600', '--height', '350']

        for item in items:
            selected = 'TRUE' if item.get('selected', False) else 'FALSE'
            cmd.extend([selected, str(item['id']), item.get('label', item['id'])])

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            return None

        return result.stdout.strip()
    except Exception as e:
        print(f"[-] Zenity radiolist failed: {e}")
        return None


def display_output_with_actions(content: str, actions: List[Dict[str, Any]],
                                title: str = "Babel Center", use_zenity: bool = False) -> Optional[str]:
    """
    Enhanced display that shows content then prompts for action selection.

    Args:
        content: Main output text to display
        actions: List of suggested actions with {'id', 'label', 'command', 'selected'}
        title: Window title
        use_zenity: If True, use Zenity GUI; otherwise print to stdout

    Returns:
        Selected action ID, or None if no action chosen

    Workflow:
        1. Display content (text-info or stdout)
        2. Show action radiolist (if actions provided)
        3. Return selected action ID for caller to execute

    Example:
        actions = [
            {'id': 'grep_imports', 'label': 'Find all imports in this file',
             'command': 'grep "^import\\|^from" Os_Toolkit.py', 'selected': True},
            {'id': 'check_todos', 'label': 'Show related todos',
             'command': 'python3 Os_Toolkit.py todo view --grep Os_Toolkit', 'selected': False}
        ]

        action_id = display_output_with_actions(
            query_results,
            actions,
            title="Query Results: Os_Toolkit.py",
            use_zenity=True
        )

        if action_id:
            action = next(a for a in actions if a['id'] == action_id)
            subprocess.run(action['command'], shell=True)
    """
    # Step 1: Display main content
    display_output(content, title=title, use_zenity=use_zenity)

    # Step 2: If no actions or not using Zenity, return early
    if not actions or not use_zenity:
        return None

    # Step 3: Show action selection radiolist
    action_items = [
        {'id': a['id'], 'label': a['label'], 'selected': a.get('selected', False)}
        for a in actions
    ]

    selected_id = zenity_radiolist(
        action_items,
        title=f"{title} - Suggested Actions",
        text="What would you like to do next?"
    )

    return selected_id


def _get_filesync_timeline_for_file(filepath: str) -> Optional[Dict[str, Any]]:
    """
    #[Mark:P2-6-display-COMPLETE] Filesync Integration - Timeline Lookup
    Query Filesync manifests for timeline data about a specific file.
    """
    # Look for babel_data/timeline/manifests/ relative to cwd
    timeline_dir = Path.cwd() / "babel_data" / "timeline" / "manifests"
    if not timeline_dir.exists():
        return None

    # Find latest manifest
    manifests = sorted(timeline_dir.glob("manifest_*.json"))
    if not manifests:
        return None

    latest_manifest = manifests[-1]

    try:
        with open(latest_manifest, 'r') as f:
            manifest_data = json.load(f)

        # Resolve the target filepath for comparison
        target_path = str(Path(filepath).resolve())

        # Search in manifest['files'] for matching path
        files_data = manifest_data.get('files', {})
        for file_id, file_info in files_data.items():
            file_path_candidate = file_info.get('original_path', file_info.get('path', ''))
            if str(Path(file_path_candidate).resolve()) == target_path:
                # Found it - return timeline data
                result = {
                    'file_id': file_id,
                    'first_seen': file_info.get('created_time'),
                    'last_modified': file_info.get('modified_time'),
                    'size': file_info.get('size_bytes', file_info.get('size')),
                    'category': file_info.get('category'),
                    'project': None,
                    'related_files': []
                }

                # Find project membership using the new project_association field
                project_id = file_info.get('project_association')
                if project_id and project_id in manifest_data.get('projects', {}):
                    proj_data = manifest_data['projects'][project_id]
                    result['project'] = {
                        'id': project_id,
                        'name': proj_data.get('name', project_id),
                        'file_count': len(proj_data.get('file_ids', [])),
                        'inference': proj_data.get('inference', {})
                    }
                    # Get related files (same project)
                    proj_file_ids = proj_data.get('file_ids', [])
                    for related_id in proj_file_ids[:5]:  # Limit to 5
                        if related_id != file_id and related_id in files_data:
                            rel_file = files_data[related_id]
                            rel_path = rel_file.get('original_path', rel_file.get('path', 'unknown'))
                            result['related_files'].append({
                                'path': rel_path,
                                'category': rel_file.get('category')
                            })
                else:
                    # Fallback for older manifests
                    for proj_id, proj_data in manifest_data.get('projects', {}).items():
                        if file_id in proj_data.get('file_ids', []):
                            result['project'] = {
                                'id': proj_id,
                                'name': proj_data.get('name', proj_id),
                                'file_count': len(proj_data.get('file_ids', [])),
                                'inference': proj_data.get('inference', {})
                            }
                            break

                return result
    except Exception as e:
        # Silently fail - Filesync data is supplementary
        pass

    return None


#[Mark:SWEEP2-IN_PROGRESS] Suggestive Grep Actions Engine
# Provides context-aware CLI command suggestions based on query results, security alerts, project activity


class SuggestiveGrepEngine:
    """
    Generates context-aware CLI command suggestions based on system state and query results.

    Purpose: Pool grep/CLI commands based on activity, security alerts, project inference.
    Integration: query results, latest output, security checks, file analysis.
    """

    @staticmethod
    def suggest_for_file_query(artifact: Dict[str, Any], filepath: str) -> List[Dict[str, Any]]:
        """
        Generate suggestions for file query results with deep profile awareness.

        Args:
            artifact: Artifact data from query
            filepath: Path to the file

        Returns:
            List of action dicts with {id, label, command, selected}
        """
        suggestions = []
        path_obj = Path(filepath)
        filename = path_obj.name
        
        # Extract richer context from artifact properties
        props = artifact.get('properties', {})
        content_analysis = props.get('content_analysis', {})
        validation = content_analysis.get('validation', {})
        classes = content_analysis.get('classes', {})
        imports = content_analysis.get('imports', [])
        
        # 1. Syntax/Validation Issues
        if validation and not validation.get('syntax_valid', True):
            suggestions.append({
                'id': 'fix_syntax',
                'label': f"⚠️ Fix Syntax Error (Line {validation.get('line')})",
                'command': f"{os.getenv('EDITOR', 'nano')} +{validation.get('line')} '{filepath}'",
                'selected': True
            })
        
        # 2. Python Specific Suggestions
        if path_obj.suffix == '.py':
            # Check for Tkinter/GUI
            is_gui = any('tkinter' in imp or 'pyqt' in imp for imp in imports)
            if is_gui:
                suggestions.append({
                    'id': 'run_gui',
                    'label': "🖥️ Launch GUI",
                    'command': f"python3 '{filepath}'"
                })
            
            # Check for Tests
            if 'test' in filename.lower() or 'test' in str(path_obj.parent).lower():
                suggestions.append({
                    'id': 'run_test',
                    'label': "🧪 Run Test",
                    'command': f"python3 -m pytest '{filepath}'"
                })
            elif classes or content_analysis.get('functions'):
                # Suggest generating tests for logic
                suggestions.append({
                    'id': 'gen_test',
                    'label': "📝 Generate Unit Tests",
                    'command': f"echo 'TODO: Generate tests for {filename}'" # Placeholder for AI gen
                })

            # Code Quality/Linting
            suggestions.append({
                'id': 'lint_check',
                'label': "🔍 Run Linter (Ruff/Flake8)",
                'command': f"ruff check '{filepath}' || flake8 '{filepath}'"
            })
            
            # Profile Classes
            if classes:
                suggestions.append({
                    'id': 'profile_classes',
                    'label': f"📊 Profile {len(classes)} Classes",
                    'command': f"python3 Os_Toolkit.py file '{filepath}' --depth 2" 
                })

        # 3. Text/Config Files
        elif path_obj.suffix in ['.json', '.yaml', '.yml', '.toml']:
            suggestions.append({
                'id': 'validate_config',
                'label': "✅ Validate Config Syntax",
                'command': f"python3 -c 'import json; json.load(open(\"{filepath}\"))' && echo 'Valid JSON'" if path_obj.suffix == '.json' else f"echo 'Validation not implemented for {path_obj.suffix}'"
            })

        # 4. Standard Edit
        suggestions.append({
            'id': 'edit_file',
            'label': "✏️ Edit File",
            'command': f"{os.getenv('EDITOR', 'nano')} '{filepath}'"
        })

        # If imports detected, suggest dependency check
        if imports:
            suggestions.append({
                'id': 'check_dependencies',
                'label': 'Check imports',
                'command': f"grep -E '^import |^from ' '{filepath}'",
                'selected': False
            })

        # If suspicious patterns, suggest security audit
        if content_analysis.get('suspicious_patterns'):
            suggestions.append({
                'id': 'security_audit',
                'label': 'Run full security check on this file',
                'command': f"python3 Os_Toolkit.py actions --run check_security",
                'selected': False
            })

        # View file marks
        suggestions.append({
            'id': 'view_marks',
            'label': 'Scan for #[Mark:] annotations',
            'command': f"grep -n '#\\[Mark:' '{filepath}'",
            'selected': False
        })

        return suggestions

    @staticmethod
    def suggest_for_latest(warnings: List[str], conflicts: List[Dict], unmarked_events: List[str]) -> List[Dict[str, Any]]:
        """
        Generate suggestions for latest command output.

        Args:
            warnings: List of security/workflow warnings (context-aware)
            conflicts: List of todo conflicts
            unmarked_events: List of system events without 6W1H classification

        Returns:
            List of action dicts
        """
        suggestions = []
        _seen_files = set()  # Deduplicate per-file suggestions

        # Smart suggestion based on warning types
        for warning in warnings:
            if "No backups" in warning:
                if 'backup_now' not in _seen_files:
                    _seen_files.add('backup_now')
                    suggestions.append({
                        'id': 'backup_now',
                        'label': '📦 Backup core files (no recent backups!)',
                        'command': 'python3 Os_Toolkit.py actions --run backup_core',
                        'selected': len(suggestions) == 0
                    })
            elif "Python file modified" in warning:
                # Extract clean filename — strip " (probe FAIL)" etc. suffixes
                _raw = warning.split(': ', 1)[-1] if ': ' in warning else warning
                _clean = re.sub(r'\s*\(.*?\)\s*$', '', _raw).strip()
                if _clean and _clean not in _seen_files:
                    _seen_files.add(_clean)
                    suggestions.append({
                        'id': f'debug_{_clean}',
                        'label': f'🐛 Run py_compile on {_clean}',
                        'command': f'python3 -m py_compile {_clean}',
                        'selected': len(suggestions) == 0
                    })
            elif "HIGH risk change" in warning:
                _raw = warning.split(': ', 1)[-1] if ': ' in warning else warning
                _clean = re.sub(r'\s*\(.*?\)\s*$', '', _raw).strip()
                if _clean and f'risk_{_clean}' not in _seen_files:
                    _seen_files.add(f'risk_{_clean}')
                    suggestions.append({
                        'id': f'assess_{_clean}',
                        'label': f'⚠️ Assess {_clean} (HIGH risk change)',
                        'command': f'python3 Os_Toolkit.py assess {_clean}',
                        'selected': len(suggestions) == 0
                    })
            elif "Security anomalies" in warning or "SECURITY" in warning:
                if 'run_security' not in _seen_files:
                    _seen_files.add('run_security')
                    suggestions.append({
                        'id': 'run_security',
                        'label': '🔒 Run full security check',
                        'command': 'python3 Os_Toolkit.py actions --run check_security',
                        'selected': len(suggestions) == 0
                    })
            elif "Workflow sync" in warning:
                if 'audit_workflow' not in _seen_files:
                    _seen_files.add('audit_workflow')
                    suggestions.append({
                        'id': 'audit_workflow',
                        'label': '🔍 Run workflow audit',
                        'command': 'python3 Os_Toolkit.py actions --run audit_workflow',
                        'selected': len(suggestions) == 0
                    })

        # Todo conflicts
        if conflicts:
            suggestions.append({
                'id': 'view_conflicts',
                'label': f'📋 View {len(conflicts)} todo conflicts',
                'command': 'python3 Os_Toolkit.py todo view',
                'selected': len(suggestions) == 0
            })

        # Unmarked events
        if unmarked_events:
            suggestions.append({
                'id': 'classify_events',
                'label': f'🏷️ Classify {len(unmarked_events)} unmarked events',
                'command': 'python3 Os_Toolkit.py logs --correlate',
                'selected': False
            })

        # Always offer: Update memory (session continuity)
        suggestions.append({
            'id': 'update_memory',
            'label': '🧠 Update session memory',
            'command': 'python3 Os_Toolkit.py actions --run update_memory',
            'selected': False
        })

        # Always offer: View all todos
        suggestions.append({
            'id': 'view_todos',
            'label': '📝 View all todos',
            'command': 'python3 Os_Toolkit.py todo view',
            'selected': False
        })

        return suggestions

    @staticmethod
    def suggest_for_security_check(untrusted_processes: List[Dict], new_ips: List[str]) -> List[Dict[str, Any]]:
        """
        Generate suggestions after security check.

        Args:
            untrusted_processes: List of processes with trust_status=untrusted
            new_ips: List of new IPs detected

        Returns:
            List of remediation actions
        """
        suggestions = []

        if untrusted_processes:
            proc_names = "|".join([p['name'] for p in untrusted_processes[:5]])
            suggestions.append({
                'id': 'verify_processes',
                'label': f'Verify {len(untrusted_processes)} untrusted processes',
                'command': f"ps aux | grep -E '{proc_names}'",
                'selected': True
            })

        if new_ips:
            ip_list = ' '.join(new_ips[:3])
            suggestions.append({
                'id': 'verify_ips',
                'label': f'Verify {len(new_ips)} new IPs with DNS lookup',
                'command': f"for ip in {ip_list}; do echo \"$ip:\"; nslookup $ip; done",
                'selected': False
            })

        # Check auth logs
        suggestions.append({
            'id': 'check_auth',
            'label': 'Check recent authentication attempts',
            'command': 'sudo tail -50 /var/log/auth.log | grep -E "Failed|Accepted"',
            'selected': False
        })

        # Check network connections
        suggestions.append({
            'id': 'active_connections',
            'label': 'Show all active network connections',
            'command': 'ss -tunap | grep ESTAB',
            'selected': False
        })

        return suggestions

    @staticmethod
    def suggest_for_project(project_name: str, active_files: List[str]) -> List[Dict[str, Any]]:
        """
        Generate suggestions based on active project.

        Args:
            project_name: Inferred project name
            active_files: List of recently modified files in project

        Returns:
            List of project-specific actions
        """
        suggestions = []

        # Find todos for this project
        suggestions.append({
            'id': 'project_todos',
            'label': f'Show todos for {project_name}',
            'command': f"python3 Os_Toolkit.py todo view | grep -i '{project_name}'",
            'selected': True
        })

        # Show recent changes
        if active_files:
            suggestions.append({
                'id': 'recent_changes',
                'label': 'Show git diff for active files',
                'command': f"git diff {' '.join(active_files[:5])}",
                'selected': False
            })

        # Find marks in project
        suggestions.append({
            'id': 'project_marks',
            'label': f'Scan #[Mark:] in {project_name}',
            'command': f"grep -rn '#\\[Mark:' . | grep -i '{project_name}'",
            'selected': False
        })

        return suggestions


def main():
    """Main command line interface"""
    # ----------------------------------------------------------------
    # Parent Parser for Global Options (Inherited by all subcommands)
    # ----------------------------------------------------------------
    parent_parser = argparse.ArgumentParser(add_help=False)
    parent_parser.add_argument('--session', '-s', help='Session ID to load (default: auto-detect latest)')
    parent_parser.add_argument('--base-dir', '-b', default=str(DEFAULT_BASE_DIR),
                               help='Base directory for data')
    parent_parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output')
    parent_parser.add_argument('--zenity', '-z', action='store_true', help='Display output via Zenity GUI')

    # ----------------------------------------------------------------
    # Quick-query shorthand logic
    # ----------------------------------------------------------------
    known_commands = {'analyze', 'query', 'file', 'manifest', 'journal',
                      'export', 'stats', 'save', 'interactive', 'latest',
                      'actions', 'todo', 'plan', 'sequence', 'suggest', 'assess',
                      'index', 'explain', 'track', 'roadmap'}
    
    first_pos_idx = None
    for i, a in enumerate(sys.argv[1:], start=1):
        if not a.startswith('-'):
            if i >= 2 and sys.argv[i-1] in ('--session', '-s', '--base-dir', '-b'):
                continue
            first_pos_idx = i
            break

    if first_pos_idx is not None and sys.argv[first_pos_idx] not in known_commands:
        sys.argv.insert(first_pos_idx, 'query')

    # ----------------------------------------------------------------
    # Main Parser
    # ----------------------------------------------------------------
    parser = argparse.ArgumentParser(
        prog='Os_Toolkit.py',
        description=f"{TOOLKIT_NAME} v{VERSION} - Forensic OS Toolkit",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
QUICK START:
  {sys.argv[0]} "filename.py"              Query a file (auto-detected)
  {sys.argv[0]} assess filename.py         Pre-change impact assessment
  {sys.argv[0]} assess filename.py -i "adding new imports"
                                           ...with intent for targeted warnings

WORKFLOWS:
  Query → Assess → Change → Verify
    1. Query a file to see its profile, tasks, and call graph
    2. Run 'assess' before changes to get AoE warnings + blast radius
    3. Make your changes
    4. Run 'latest' to see the change captured + probe results

  Coordination Sequences:
    sequence startup     Full morning briefing (Latest + Security + Backups)
    sequence checkin     Workflow audit + Mark sync + Todo list
    sequence shutdown    Final backup + Health report + Session save

DEEP DIVE:
  query FILE --graph         Show top 20 call edges
  query FILE --graph full    Show all call edges
  query FILE --suggest       Append suggested follow-up actions
  suggest FILE               Generate actionable suggestions (JSON/text)
  plan report                Strategic health report across all projects
  latest                     Recent changes, probes, attribution gaps
  todo view                  View task board

COLD-START SEQUENCE (run at session start for full grounding):
  1. latest                        Full project state + probes + attribution gaps
  2. explain --last 24h            What was worked on, phase, domain, files, tasks
  3. todo view open                Pending tasks by priority
  4. assess <active_task_file>     Impact analysis before changes
  5. plan show                     Current strategy + project health

TASK MANAGEMENT:
  todo view --group-by priority    View tasks grouped by priority
  todo view open                   Show only open tasks
  todo add "title" "description"   Create a new task
  todo activate <task_id>          Set active task (persists to config.json)
  todo complete --id <task_id>     Mark task as complete
  todo link <task_id> -e 0002,0003 Link enriched_change events to task
  todo link <task_id> --file f.py  Link all events for a file to task
  todo inbox                       View AoE change alerts + system checks

CHANGE TRACKING (CLI sessions):
  track --file f.py --verb modify --methods "m1,m2" --task tid --risk LOW --desc "..."
  explain --last 24h --init-chain  Explain + trace GUI init chain impact
  explain --morph                  Feed narrative into OmegaBridge

PLAN MANAGEMENT:
  plan show                        Display high-level strategy
  plan scan                        Scan codebase for strategic marks
  plan report                      Health check across projects
  plan refresh <project_id>        Re-render project template
  plan consolidate --preview       Discover/preview scattered plan docs
  plan consolidate --execute       Execute consolidation with backup
  plan consolidate --list-projects List known projects
        """
    )

    subparsers = parser.add_subparsers(dest='command', help='Command to execute')

    # analyze
    analyze_parser = subparsers.add_parser('analyze', parents=[parent_parser], help='Analyze system')
    analyze_parser.add_argument('--depth', '-d', type=int, choices=[1, 2, 3], default=2,
                               help='Depth of analysis (1=basic, 2=detailed, 3=deep)')
    analyze_parser.add_argument('--system-packages', '-sp', action='store_true', help='Profile all installed system packages (Debian-based only)')
    analyze_parser.add_argument('--save', action='store_true', help='Save after analysis')

    # query
    query_parser = subparsers.add_parser('query', parents=[parent_parser], help='Query session data',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
WHAT YOU GET:
  File profile, 6W1H classification, change events, AST profile,
  call graph (deps/importers), task associations, temporal history

CALL GRAPH DEPTH:
  (default)        Dependency lists only (Depends On / Imported By)
  --graph          Top 20 call edges
  --graph full     All call edges (can be 1000s of lines)

NEXT STEPS:
  Add --suggest to see follow-up actions for the queried file
  Use 'assess FILE' before making changes to see AoE warnings
  Use 'assess FILE --intent "description"' for intent-aware warnings
""")
    query_parser.add_argument('query_string', help='Search term (filename, path, keyword)')
    query_parser.add_argument('--type', '-t', default='auto',
                             choices=['auto', 'file', 'string', 'hash', 'taxonomic', 'verb', 'imports', 'natural'],
                             help='Query type')
    query_parser.add_argument('--max-results', '-m', type=int, default=50)
    query_parser.add_argument('--output', '-o', help='Save results to JSON file')
    query_parser.add_argument('--suggest', action='store_true', help='Show suggested follow-up actions (with -z shows interactive radiolist)')
    query_parser.add_argument('--graph', nargs='?', const='summary', default=None,
                             choices=['summary', 'full'],
                             help='Call graph depth: omit=deps only, --graph=top 20, --graph full=all')

    # file
    file_parser = subparsers.add_parser('file', parents=[parent_parser], help='Analyze specific file')
    file_parser.add_argument('filepath', help='Path to file')
    file_parser.add_argument('--depth', '-d', type=int, choices=[1, 2, 3], default=2)
    file_parser.add_argument('--suggest', action='store_true', help='Show suggested actions for this file (with -z shows interactive radiolist)')
    file_parser.add_argument('--save', action='store_true')

    # manifest
    manifest_parser = subparsers.add_parser('manifest', parents=[parent_parser], help='Generate system manifest')
    manifest_parser.add_argument('--format', '-f', choices=['json', 'text'], default='json')
    manifest_parser.add_argument('--output', '-o', help='Save manifest to file')

    # journal
    journal_parser = subparsers.add_parser('journal', parents=[parent_parser], help='Journal management')
    journal_group = journal_parser.add_mutually_exclusive_group(required=True)
    journal_group.add_argument('--add', '-a', help='Add entry')
    journal_group.add_argument('--query', '-q', help='Search entries')
    journal_group.add_argument('--stats', action='store_true', help='Show stats')
    journal_parser.add_argument('--tags', help='Comma-separated tags for --add')
    journal_parser.add_argument('--entry-type', dest='entry_type', default='note', help='Entry type for --add')
    journal_parser.add_argument('--limit', type=int, default=10, help='Max results for --query')

    # export
    export_parser = subparsers.add_parser('export', parents=[parent_parser], help='Export session')
    export_parser.add_argument('--format', '-f', choices=['json', 'text'], default='json')

    # latest
    latest_parser = subparsers.add_parser('latest', parents=[parent_parser], help='Show latest state')
    latest_parser.add_argument('--action-list', '-l', action='store_true',
                              help='List saved suggested actions from last run')
    latest_parser.add_argument('--action-run', '-r', metavar='ACTION_ID',
                              help='Run a specific saved action by ID')
    latest_parser.add_argument('--action-batch', action='store_true',
                              help='Run all high-confidence suggested actions in batch')
    latest_parser.add_argument('--diff', '-d', action='store_true',
                              help='Preview mode - show what actions would do without executing')
    
    # actions
    actions_parser = subparsers.add_parser('actions', parents=[parent_parser], help='Manage actions')
    actions_group = actions_parser.add_mutually_exclusive_group(required=True)
    actions_group.add_argument('--list', '-l', action='store_true')
    actions_group.add_argument('--run', '-r', help='Run by ID')

    # todo
    todo_parser = subparsers.add_parser('todo', parents=[parent_parser], help='Manage tasks',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""EXAMPLES:
  todo view open                   Show pending tasks
  todo view --group-by priority    Group by P0/P1/P2/P3
  todo inbox                       AoE change alerts + system checks
  todo add "Fix bug" "description" Create new task
  todo activate task_25_2          Set as active task (writes config.json)
  todo update task_25_2 done       Update task status
  todo complete --id task_25_2     Interactive completion
  todo link task_25_2 -e 0002 0003 Link events to task (fixes attribution gaps)
  todo link task_25_2 --file f.py  Link all events for file to task
""")
    todo_subparsers = todo_parser.add_subparsers(dest='todo_action')
    todo_view = todo_subparsers.add_parser('view', parents=[parent_parser],
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
GROUPING:
  --group-by priority    Group by P1/P2/P3/P4
  --group-by project     Group by project_id
  --group-by phase       Group by originating phase (source bucket)
  --group-by file        Group by wherein (target file)
  --group-by status      Group by task status
""")
    todo_view.add_argument('status', nargs='?', default='all', choices=['all', 'open', 'done', 'in-progress', 'deferred'])
    todo_view.add_argument('--group-by', '-g', dest='group_by',
        choices=['priority', 'project', 'phase', 'file', 'status'],
        help='Group tasks by dimension')
    todo_inbox = todo_subparsers.add_parser('inbox', parents=[parent_parser],
        help='View aoe_inbox change alerts grouped by task or file')
    todo_inbox.add_argument('--group-by', '-g', dest='group_by',
        choices=['task', 'file'], default='task',
        help='Group inbox entries by task_id (default) or file')
    todo_add = todo_subparsers.add_parser('add', parents=[parent_parser])
    todo_add.add_argument('title')
    todo_add.add_argument('description', nargs='?', default='')
    todo_update = todo_subparsers.add_parser('update', parents=[parent_parser])
    todo_update.add_argument('id')
    todo_update.add_argument('status', choices=['open', 'done', 'in-progress', 'deferred', 'cancelled'])
    todo_complete = todo_subparsers.add_parser('complete', parents=[parent_parser])
    todo_complete.add_argument('--id', required=True, help='Task ID to complete')

    todo_link = todo_subparsers.add_parser('link', parents=[parent_parser],
                                            help='Link event(s) to a task (fix attribution gaps)')
    todo_link.add_argument('id', help='Task ID to link events to')
    todo_link.add_argument('--events', '-e', nargs='+', help='Event IDs (e.g. #[Event:0002] or 0002)')
    todo_link.add_argument('--file', '-f', help='Link all events matching this filename')

    todo_activate = todo_subparsers.add_parser('activate', parents=[parent_parser],
                                                help='Set active task (currently-working-on)')
    todo_activate.add_argument('id', help='Task ID to activate')

    # plan
    plan_parser = subparsers.add_parser('plan', parents=[parent_parser], help='Manage plans')
    plan_subparsers = plan_parser.add_subparsers(dest='plan_action')
    plan_subparsers.add_parser('show', parents=[parent_parser])
    plan_subparsers.add_parser('scan', parents=[parent_parser])
    plan_subparsers.add_parser('report', parents=[parent_parser])
    plan_refresh = plan_subparsers.add_parser('refresh', parents=[parent_parser],
                                               help='Re-render project template from latest data')
    plan_refresh.add_argument('project_id', help='Project ID (e.g. Project_Digital_Kingdom_001)')
    plan_consolidate = plan_subparsers.add_parser('consolidate', parents=[parent_parser],
        help='Discover, preview, and template plan docs into Project_Template_001 format')
    plan_consolidate.add_argument('--preview', '-p', action='store_true',
        help='Show detailed per-plan preview of what templating would produce')
    plan_consolidate.add_argument('--interactive', '-i', action='store_true',
        help='Step through each plan with y/n/v/q approval prompts')
    plan_consolidate.add_argument('--execute', '-x', action='store_true',
        help='Execute consolidation (auto-backup unless --no-backup)')
    plan_consolidate.add_argument('--target', '-t',
        help='Process a single plan file by name (e.g. "latest_bugs.md")')
    plan_consolidate.add_argument('--no-backup', action='store_true',
        help='Skip backup before execution (default: always backup)')
    plan_consolidate.add_argument('--include-organized', action='store_true',
        help='Also scan plans in subdirectories (integration_project/, etc.)')
    plan_consolidate.add_argument('--assign', nargs=2, metavar=('PLAN', 'PROJECT'),
        help='Assign a plan to a project: --assign "plan.md" "Project_Name"')
    plan_consolidate.add_argument('--batch', metavar='FILE',
        help='JSON file with batch decisions: {"plan.md": {"action": "accept|skip|assign", "project": "..."}}')
    plan_consolidate.add_argument('--context', '-c', metavar='PLAN',
        help='Show full context for a plan: content summary, file refs, task matches, project scores')
    plan_consolidate.add_argument('--list-projects', action='store_true',
        help='List known projects with their current doc count and keywords')

    plan_generate = plan_subparsers.add_parser('generate', parents=[parent_parser],
        formatter_class=argparse.RawDescriptionHelpFormatter,
        help='MoE plan generation: run GGUF models on a task, compare outputs',
        epilog=textwrap.dedent("""\
        EXAMPLES:
          plan generate task_25_2                       Generate with all discovered GGUFs
          plan generate task_25_2 --models morph,qwen   Specific models only
          plan generate task_25_2 --compare             Include cross-validation report
          plan generate task_25_2 --list-models         Show available GGUFs
        """))
    plan_generate.add_argument('task_id', nargs='?', default=None,
        help='Task ID to generate plans for')
    plan_generate.add_argument('--models', '-m', default=None,
        help='Comma-separated model names (default: all discovered GGUFs)')
    plan_generate.add_argument('--compare', action='store_true',
        help='Cross-validate outputs and produce comparison report')
    plan_generate.add_argument('--list-models', action='store_true',
        help='List available GGUF models and exit')
    plan_generate.add_argument('--n-ctx', type=int, default=2048,
        help='Context window per model (default: 2048)')
    plan_generate.add_argument('--max-tokens', type=int, default=1024,
        help='Max generation tokens per model (default: 1024)')

    # sequence
    sequence_parser = subparsers.add_parser('sequence', parents=[parent_parser], help='Run coordination sequences')
    sequence_parser.add_argument('name', choices=['startup', 'checkin', 'shutdown'])

    # suggest - Export suggestions for grep_flight integration
    suggest_parser = subparsers.add_parser('suggest', parents=[parent_parser],
                                          help='Generate suggestive actions for target file/path')
    suggest_parser.add_argument('target', help='Target file or directory path')
    suggest_parser.add_argument('--format', '-f', choices=['json', 'text'], default='json',
                               help='Output format (default: json for grep_flight consumption)')
    suggest_parser.add_argument('--context', '-c', choices=['file', 'latest', 'project'], default='file',
                               help='Context type for suggestions')

    # simple ones
    subparsers.add_parser('stats', parents=[parent_parser])
    subparsers.add_parser('save', parents=[parent_parser])
    subparsers.add_parser('interactive', parents=[parent_parser])

    # assess — pre-change impact assessment
    assess_parser = subparsers.add_parser('assess', parents=[parent_parser],
        help='Pre-change impact assessment for a file',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
OUTPUT SECTIONS:
  [FILE IDENTITY]        File path, LOC, classes, backup count
  [AoE WARNING PANEL]    Risk history, blast radius, intent warnings
  [PROJECT CONTEXT]      Linked project, plan doc, project tasks
  [RECOMMENDED TASKS]    Priority-ordered checklist before/after changes
  [RELATED ACTIVE TASKS] Tasks with 'wherein' matching this file

EXAMPLES:
  assess recovery_util.py
    → AoE {CRITICAL}: CORE system file, 9 downstream dependents

  assess planner_tab.py --intent "adding D7 block writing to checklist.json"
    → AoE {WARN}: Intent touches coordination data store

  assess logger_util.py
    → AoE {WARN}: 79 downstream dependents — test all importers

WARNING LEVELS:
  AoE {CRITICAL}  Core file, unresolved probe FAILs
  AoE {RISK}      HIGH/CRITICAL history, deletion intent
  AoE {WARN}      Many importers, coord store changes, test failures
  AoE {INFO}      No elevated risk detected
""")
    assess_parser.add_argument('file', help='File to assess (filename or path fragment)')
    assess_parser.add_argument('--intent', '-i', default='',
        help='Description of planned changes')

    # index — UnifiedContextIndex queries
    index_parser = subparsers.add_parser('index', parents=[parent_parser],
        help='Unified entity index (all catalogs per file)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Subcommands:
  build           Rebuild unified_entity_index.json from all catalog sources
  show <file>     Show full entity record (events, tasks, call_graph, etc.)
  search <term>   Multi-field search across all entities
  graph <file>    Show live call graph (forward + backward edges per function)
  chain <file> <fn>  Show call chain for one function

Examples:
  index build
  index show planner_tab.py
  index search "task_25_2"
  index graph Os_Toolkit.py
  index chain planner_tab.py _do_sync
""")
    index_parser.add_argument('index_subargs', nargs='*',
        help='action [file] [function]  e.g.: show planner_tab.py')

    # --- explain subcommand (Phase L) ---
    explain_parser = subparsers.add_parser('explain', parents=[parent_parser],
        help='Explain what was worked on in a time window; trace init chain impact',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""EXAMPLES:
  explain                          Last 24h (default)
  explain --last 24h               Explicit last 24 hours
  explain --last 48h               Last 2 days
  explain --since "phase-j"        Since Phase J started
  explain --since "2026-02-21"     Since specific date
  explain --last 24h --init-chain  + GUI init chain impact trace
  explain --morph                  Feed narrative into OmegaBridge
  explain --format json            Machine-readable output
""")
    explain_parser.add_argument('--since', default=None,
        help='Start of time window: "yesterday", "last 24h", "2026-02-21", "phase-j"')
    explain_parser.add_argument('--until', default=None,
        help='End of time window (default: now)')
    explain_parser.add_argument('--date', default=None,
        help='Single date (shorthand for --since <date> --until end-of-day)')
    explain_parser.add_argument('--last', default=None, metavar='WINDOW',
        help='Look-back window: "24h", "48h", "7d"')
    explain_parser.add_argument('--incremental', action='store_true',
        help='Use last explain timestamp as start (for repeated calls)')
    explain_parser.add_argument('--init-chain', nargs='?', const='__recent__',
        metavar='FILE', dest='init_chain',
        help='Trace changed files through GUI init chain (optionally specify one file)')
    explain_parser.add_argument('--morph', action='store_true',
        help='Feed narrative into OmegaBridge for Morph-driven response')
    explain_parser.add_argument('--format', '-f', default='text',
        choices=['text', 'json', 'morph-jsonl'],
        help='Output format (default: text)')

    track_parser = subparsers.add_parser('track', parents=[parent_parser],
        help='Record a CLI file change into version_manifest.json (visible to explain)')
    track_parser.add_argument('--file', required=True, metavar='PATH',
        help='File that was changed (relative to Trainer root or absolute)')
    track_parser.add_argument('--verb', default='modify',
        choices=['add', 'modify', 'delete', 'fix', 'refactor', 'import'],
        help='Change verb (default: modify)')
    track_parser.add_argument('--methods', default='', metavar='M1,M2',
        help='Comma-separated method names affected')
    track_parser.add_argument('--task', default='', metavar='TASK_ID',
        help='Comma-separated task IDs this change belongs to')
    track_parser.add_argument('--risk', default='LOW',
        choices=['LOW', 'MEDIUM', 'HIGH', 'CRITICAL'],
        help='Risk level (default: LOW)')
    track_parser.add_argument('--desc', default='', metavar='TEXT',
        help='Short description of what changed')

    # roadmap — Deterministic roadmap to goal completion
    roadmap_parser = subparsers.add_parser('roadmap', parents=[parent_parser],
        formatter_class=argparse.RawDescriptionHelpFormatter,
        help='Compute deterministic roadmap to goal completion',
        epilog=textwrap.dedent("""\
        EXAMPLES:
          roadmap                              Active project roadmap
          roadmap Project_Morph_Alpha          Specific project
          roadmap --format json --save         Save JSON report
          roadmap --top 10                     Top 10 priority items only
        """))
    roadmap_parser.add_argument('project_id', nargs='?', default=None,
        help='Project ID (default: active project from config.json)')
    roadmap_parser.add_argument('--format', '-f', default='text',
        choices=['text', 'json', 'both'], help='Output format (default: text)')
    roadmap_parser.add_argument('--save', action='store_true',
        help='Save JSON to plans/Morph/roadmap_{project}_{ts}.json')
    roadmap_parser.add_argument('--top', type=int, default=0, metavar='N',
        help='Limit to top N items (default: all)')
    roadmap_parser.add_argument('--spawn', action='store_true',
        help='Generate diff templates for MISSING functions (spawn specs)')
    roadmap_parser.add_argument('--spawn-save', action='store_true',
        help='Save spawn diffs to plans/Morph/spawn_{project}_{ts}.json')
    roadmap_parser.add_argument('--propose', metavar='TARGET',
        help='Targeted change proposal for a specific file or package')

    args = parser.parse_args()

    # Log command execution to unified traceback
    log_event("COMMAND_EXEC", f"Running command: {args.command}", level="INFO", 
              context={"args": sys.argv[1:], "session": args.session})

    if not args.command:
        parser.print_help()
        sys.exit(1)

    # Resolve base-dir and session
    base_dir, session_id = _resolve_base_dir_and_session(args.base_dir, args.session)

    # Initialize Managers
    todo_manager = TodoManager(base_dir)
    plan_manager = PlanManager(base_dir)

    # Initialize toolkit
    try:
        toolkit = ForensicOSToolkit(session_id=session_id, base_dir=base_dir)
        onboarding_manager = OnboardingManager(base_dir=Path(__file__).parent)
        latest_onboarder_session_id = onboarding_manager._get_latest_session_id()
        if latest_onboarder_session_id:
            onboarding_manager.load_session(latest_onboarder_session_id)
    except Exception as e:
        print(f"[-] Error initializing toolkit: {e}")
        sys.exit(1)
    
    # Execute command
    try:
        if args.command == 'sequence':
            # Accumulate output for zenity if needed
            def _run_action(action_id):
                action = toolkit.actions.get(action_id)
                if action is None:
                    return f"[SKIP] Action '{action_id}' not registered"
                return action.command_func()
            seq_out = []
            if args.name == 'startup':
                seq_out.append(f"STARTUP SEQUENCE: {datetime.now().isoformat()}")
                seq_out.append(_run_action('baseline_wakeup'))
            elif args.name == 'checkin':
                seq_out.append(f"CHECKIN SEQUENCE")
                seq_out.append(_run_action('audit_workflow'))
                seq_out.append(_run_action('sync_marks'))
                seq_out.append(_run_action('process_inbox'))
            elif args.name == 'shutdown':
                seq_out.append(f"SHUTDOWN SEQUENCE")
                seq_out.append(_run_action('backup_core'))
                seq_out.append(plan_manager.project_report())
                toolkit.save()
            
            display_output("\n".join(seq_out), title=f"Babel Sequence: {args.name}", use_zenity=args.zenity)

        elif args.command == 'suggest':
            # Generate suggestive actions — uses GroundedSuggestEngine when available,
            # falls back to SuggestiveGrepEngine for file/latest/project contexts.
            target_path = Path(args.target).resolve()

            if not target_path.exists():
                print(f"[-] Target does not exist: {target_path}")
                sys.exit(1)

            suggestions = []

            # Try GroundedSuggestEngine first (adds phase/domain/probe context)
            _grounded_engine = None
            try:
                _scripts_dir = Path(__file__).parent / 'regex_project' / 'activities' / 'tools' / 'scripts'
                import sys as _sys_g
                if str(_scripts_dir) not in _sys_g.path:
                    _sys_g.path.insert(0, str(_scripts_dir))
                from grounded_suggest_engine import GroundedSuggestEngine as _GSE
                _trainer_root_g = Path(__file__).resolve().parents[3]
                _grounded_engine = _GSE(_trainer_root_g)
                _grounded_engine.load_context()
            except Exception:
                _grounded_engine = None

            if args.context == 'file' and target_path.is_file():
                # Query the file to get artifact data
                result = toolkit.query(str(target_path), 'file', max_results=1)
                artifact = result['results'][0]['artifact'] if result['results'] else None

                if _grounded_engine is not None:
                    suggestions = _grounded_engine.suggest(
                        query=str(target_path),
                        artifact=artifact,
                        filepath=str(target_path),
                    )
                elif artifact:
                    suggestions = SuggestiveGrepEngine.suggest_for_file_query(artifact, str(target_path))
                else:
                    import os as os_module
                    editor = os_module.getenv('EDITOR', 'nano')
                    suggestions = [
                        {'id': 'profile', 'label': 'Profile with Os_Toolkit',
                         'command': f"python3 Os_Toolkit.py file '{target_path}'", 'selected': True},
                        {'id': 'edit', 'label': 'Edit File',
                         'command': f"{editor} '{target_path}'", 'selected': False}
                    ]

            elif args.context == 'latest':
                if _grounded_engine is not None:
                    suggestions = _grounded_engine.suggest(query='latest')
                else:
                    # Pull real warnings from version_manifest enriched_changes
                    warnings = []
                    conflicts = []
                    unmarked_events = []
                    try:
                        _data_root = Path(__file__).resolve().parents[2]
                        _vm_path = _data_root / "backup" / "version_manifest.json"
                        if _vm_path.exists():
                            _vm = json.loads(_vm_path.read_text(encoding="utf-8"))
                            _ec = _vm.get("enriched_changes", {})
                            _recent = [(eid, ch) for eid, ch in _ec.items()
                                       if ch.get("timestamp", "") > (datetime.now() - timedelta(hours=24)).isoformat()]
                            for eid, ch in _recent:
                                if ch.get("probe_status") == "FAIL":
                                    warnings.append(f"Python file modified: {ch.get('file','?')} (probe FAIL)")
                                if ch.get("risk_level") in ("HIGH", "CRITICAL"):
                                    warnings.append(f"HIGH risk change: {ch.get('file','?')}")
                                if not ch.get("task_ids"):
                                    unmarked_events.append(eid)
                            if not _vm.get("versions"):
                                warnings.append("No backups found in version_manifest")
                    except Exception:
                        pass
                    suggestions = SuggestiveGrepEngine.suggest_for_latest(warnings, conflicts, unmarked_events)

            elif args.context == 'project':
                project_name = target_path.name if target_path.is_dir() else target_path.parent.name
                if _grounded_engine is not None:
                    suggestions = _grounded_engine.suggest(query=project_name)
                else:
                    active_files = []
                    suggestions = SuggestiveGrepEngine.suggest_for_project(project_name, active_files)

            # Output
            if args.format == 'json':
                print(json.dumps(suggestions, indent=2))
            else:
                for i, sug in enumerate(suggestions, 1):
                    print(f"{i}. [{sug['id']}] {sug['label']}")
                    print(f"   Command: {sug['command']}")
                    if sug.get('selected'):
                        print("   [RECOMMENDED]")
                    print()

        elif args.command == 'todo':
            if args.todo_action == 'add':
                todo_manager.add_todo(args.title, args.description)
            elif args.todo_action == 'view':
                todos = todo_manager.load_todos_flat()
                # Filter by status
                _OPEN_STATUSES = {'open', 'pending', 'ready', 'in-progress', 'in_progress'}
                if args.status == 'open':
                    todos = [t for t in todos if t.get('status', '').lower().replace('_', '-') in _OPEN_STATUSES]
                elif args.status != 'all':
                    todos = [t for t in todos if t.get('status', '').lower().replace('_', '-') == args.status]

                _group_field = getattr(args, 'group_by', None)
                _field_map = {
                    'priority': lambda t: t.get('priority', '?'),
                    'project': lambda t: t.get('project_id', '') or '(no project)',
                    'phase': lambda t: t.get('_phase', '?'),
                    'file': lambda t: Path(t.get('wherein', '') or '?').name,
                    'status': lambda t: (t.get('status', '?') or '?').upper(),
                }

                out = [f"PROJECT TASKS ({args.status.upper()}) — {len(todos)} tasks", "=" * 50]

                if _group_field and _group_field in _field_map:
                    _groups = defaultdict(list)
                    _key_fn = _field_map[_group_field]
                    for t in todos:
                        _groups[_key_fn(t)].append(t)
                    # Sort: priority P0-P4 first, then alpha
                    for gkey in sorted(_groups.keys(), key=lambda k: (not k.startswith('P'), k)):
                        items = _groups[gkey]
                        out.append(f"\n── {gkey} ({len(items)} tasks) ──")
                        for t in items:
                            m = "[x]" if t.get('status', '').lower() in ('done', 'complete') else "[ ]"
                            _pri = t.get('priority', '')
                            _pri_tag = f" [{_pri}]" if _pri and _group_field != 'priority' else ""
                            _wh = Path(t.get('wherein', '') or '').name
                            _wh_tag = f" [{_wh}]" if _wh and _group_field != 'file' else ""
                            out.append(f"  {m} {t.get('title', '?')} ({t.get('id', '?')}){_pri_tag}{_wh_tag}")
                else:
                    for t in todos:
                        m = "[x]" if t.get('status', '').lower() in ('done', 'complete') else "[ ]"
                        _pri = t.get('priority', '')
                        _pri_tag = f" [{_pri}]" if _pri else ""
                        out.append(f"{m} {t.get('title', '?')} ({t.get('id', '?')}){_pri_tag}")

                # Summary footer
                _done = sum(1 for t in todos if t.get('status', '').lower() in ('done', 'complete'))
                _by_pri = Counter(t.get('priority', '?') for t in todos)
                _projects = set(t.get('project_id', '') for t in todos if t.get('project_id'))
                _pri_str = " | ".join(f"{cnt} {p}" for p, cnt in sorted(_by_pri.items()) if p != '?')
                _ungraded = _by_pri.get('?', 0)
                out.append(f"\nSUMMARY: {len(todos)} tasks | {_done} done | {_pri_str}")
                if _ungraded:
                    out.append(f"  {_ungraded} ungraded | {len(_projects)} projects")

                out.append(f"\n[NEXT STEPS]")
                out.append(f"  → todo view --group-by priority   Group by priority level")
                out.append(f"  → todo view --group-by project    Group by project")
                out.append(f"  → todo inbox                      View AoE change alerts")

                display_output("\n".join(out), title="Babel Tasks", use_zenity=args.zenity)
            elif args.todo_action == 'inbox':
                # Read checklist.json aoe_inbox
                _plans_dir = todo_manager.plans_dir or (Path(__file__).parent.parent.parent / "plans")
                _cl_path = _plans_dir / "checklist.json"
                _cl = json.loads(_cl_path.read_text(encoding="utf-8")) if _cl_path.exists() else {}
                _inbox = _cl.get("aoe_inbox", [])
                _group_field = getattr(args, 'group_by', 'task') or 'task'

                _groups = defaultdict(list)
                for e in _inbox:
                    if _group_field == 'file':
                        _gkey = Path(e.get('file', '?')).name
                    else:
                        _gkey = e.get('task_id', '?')
                    _groups[_gkey].append(e)

                out = [f"AoE INBOX ({len(_inbox)} entries, {len(_groups)} groups)", "=" * 50]
                for gkey in sorted(_groups.keys()):
                    entries = _groups[gkey]
                    risks = Counter(e.get('risk_level', '?') for e in entries)
                    risk_str = ", ".join(f"{cnt} {lvl}" for lvl, cnt in risks.most_common())
                    _gaps = sum(1 for e in entries if e.get('status') == 'ATTRIBUTION_GAP')
                    _gap_tag = f" | {_gaps} ATTRIBUTION_GAP" if _gaps else ""
                    out.append(f"\n── {gkey} ({len(entries)} changes) ──")
                    out.append(f"   Risk: {risk_str}{_gap_tag}")
                    for e in sorted(entries, key=lambda x: x.get('timestamp', ''), reverse=True)[:5]:
                        _ts = e.get('timestamp', '')[:16]
                        _verb = e.get('verb', '?')
                        _risk = e.get('risk_level', '?')
                        _file = Path(e.get('file', '?')).name
                        _gap = " [ATTRIBUTION_GAP]" if e.get('status') == 'ATTRIBUTION_GAP' else ""
                        out.append(f"   {_ts} | {_verb:8s} | {_risk:8s} | {_file}{_gap}")
                    if len(entries) > 5:
                        out.append(f"   ... +{len(entries) - 5} more")

                # ── Dynamic system checks ──
                out.append(f"\n[SYSTEM CHECKS]")
                _checks = []
                try:
                    # Check 1: Active task staleness
                    _cfg_path = _plans_dir / "config.json"
                    if _cfg_path.exists():
                        _cfg = json.loads(_cfg_path.read_text(encoding="utf-8"))
                        _atid = _cfg.get("active_task_id", "")
                        _aat = _cfg.get("activated_at", "")
                        _lat = _cfg.get("last_activity_at", "")
                        if _atid:
                            if _lat:
                                _delta = (datetime.now() - datetime.fromisoformat(_lat))
                                _hours = _delta.total_seconds() / 3600
                                if _hours > 2:
                                    _checks.append(f"⚠ Active task {_atid} — no file changes in {_hours:.0f}h (last: {_lat[:16]})")
                                else:
                                    _checks.append(f"✓ Active task {_atid} — last activity {_lat[:16]}")
                            elif _aat:
                                _checks.append(f"⚠ Active task {_atid} — activated at {_aat[:16]}, no activity timestamp")

                    # Check 2: Unresolved probe failures
                    _vm_path_ib = Path(__file__).parents[2] / "backup" / "version_manifest.json"
                    if _vm_path_ib.exists():
                        _vm_ib = json.loads(_vm_path_ib.read_text(encoding="utf-8"))
                        _ec_ib = _vm_ib.get("enriched_changes", {})
                        _unresolved = [(eid, ch) for eid, ch in _ec_ib.items()
                                       if ch.get("probe_status") == "FAIL" and not ch.get("resolved_by")]
                        _resolved_recent = [(eid, ch) for eid, ch in _ec_ib.items()
                                            if ch.get("resolved_by") and ch.get("resolved_at", "") > (datetime.now() - timedelta(hours=24)).isoformat()]
                        if _unresolved:
                            _files_ib = set(Path(ch.get('file', '')).name for _, ch in _unresolved)
                            _checks.append(f"✗ {len(_unresolved)} unresolved probe FAIL(s): {', '.join(_files_ib)}")
                        else:
                            _checks.append(f"✓ All probes passing")
                        if _resolved_recent:
                            _checks.append(f"✓ {len(_resolved_recent)} probe(s) resolved in last 24h")

                        # Check 3: Attribution gaps (changes with no task_ids)
                        _ungapped = [(eid, ch) for eid, ch in _ec_ib.items()
                                     if not ch.get("task_ids") and ch.get("timestamp", "") > (datetime.now() - timedelta(hours=24)).isoformat()]
                        if _ungapped:
                            _checks.append(f"⚠ {len(_ungapped)} change(s) in last 24h with no task attribution")

                        # Check 4: File-task mismatch (active task file vs recent changes)
                        if _atid:
                            _awh_ib = _cfg.get("active_task_wherein", "")
                            _awh_base = Path(_awh_ib).name if _awh_ib else ""
                            _recent_files = set()
                            for _eid_ib, _ch_ib in _ec_ib.items():
                                if _ch_ib.get("timestamp", "") > (datetime.now() - timedelta(hours=2)).isoformat():
                                    _recent_files.add(Path(_ch_ib.get("file", "")).name)
                            if _recent_files and _awh_base and _awh_base not in _recent_files:
                                _checks.append(f"⚠ Active task targets {_awh_base} but recent changes are in: {', '.join(_recent_files)}")

                        # Check 5: Bug resolution inference
                        try:
                            _bug_inferred = _infer_bug_resolutions(_plans_dir, _vm_ib)
                            if _bug_inferred:
                                _checks.append(f"🔧 {len(_bug_inferred)} BUG task(s) may be resolved:")
                                for _bi in _bug_inferred[:3]:
                                    _checks.append(f"   {_bi['bug_task_id']}: fixed in {_bi['fixed_in_version']} ({_bi['evidence']})")
                        except Exception:
                            pass
                except Exception:
                    pass

                for _c in _checks:
                    out.append(f"  {_c}")
                if not _checks:
                    out.append(f"  (no checks to report)")

                out.append(f"\n[NEXT STEPS]")
                out.append(f"  → todo inbox --group-by file      Group by changed file")
                out.append(f"  → todo link TASK_ID -e EVENT_ID   Link events to tasks")
                out.append(f"  → todo view --group-by project    View tasks by project")

                display_output("\n".join(out), title="AoE Inbox", use_zenity=args.zenity)
            elif args.todo_action == 'update':
                todo_manager.update_todo(args.id, args.status)
            elif args.todo_action == 'complete':
                result = todo_manager.complete_todo_interactive(args.id, use_zenity=args.zenity)
                display_output(result, title="Task Completion", use_zenity=args.zenity)
            elif args.todo_action == 'activate':
                # Set active task — writes to planner_state (plans/config.json) shared with GUI
                _plans_dir = todo_manager.plans_dir or (Path(__file__).parent.parent.parent / "plans")
                _config_path = _plans_dir / "config.json"
                try:
                    _state = json.loads(_config_path.read_text(encoding="utf-8")) if _config_path.exists() else {}
                except Exception:
                    _state = {}
                _state["active_task_id"] = args.id
                _state["activated_at"] = datetime.now().isoformat()
                # Find wherein from todos.json
                _wherein = ""
                _todos_path = _plans_dir / "todos.json"
                _todos_data = {}
                if _todos_path.exists():
                    try:
                        _todos_data = json.loads(_todos_path.read_text(encoding="utf-8"))
                    except Exception:
                        pass
                for _phase_key, _phase_data in _todos_data.items():
                    if isinstance(_phase_data, dict):
                        for _tk, _tv in _phase_data.items():
                            if isinstance(_tv, dict) and _tv.get("id") == args.id:
                                _wherein = _tv.get("wherein", "")
                                if _tv.get("status") not in ("COMPLETE", "IN_PROGRESS"):
                                    _tv["status"] = "IN_PROGRESS"
                                break
                _state["active_task_wherein"] = _wherein
                _config_path.parent.mkdir(parents=True, exist_ok=True)
                _config_path.write_text(json.dumps(_state, indent=2), encoding="utf-8")
                # Save updated todos if status changed
                if _todos_data and _todos_path.exists():
                    try:
                        _todos_path.write_text(json.dumps(_todos_data, indent=2), encoding="utf-8")
                    except Exception:
                        pass
                print(f"[+] Active task set: {args.id}")
                if _wherein:
                    print(f"    wherein: {_wherein}")
                print(f"    Persisted to {_config_path.name} (shared with GUI planner)")
            elif args.todo_action == 'link':
                # Link event_ids to a task in enriched_changes (fixes attribution gaps)
                _vm_path = Path(__file__).parent.parent.parent / "backup" / "version_manifest.json"
                if not _vm_path.exists():
                    print("[-] version_manifest.json not found")
                else:
                    _vm = json.loads(_vm_path.read_text(encoding="utf-8"))
                    _ec = _vm.get("enriched_changes", {})
                    _linked = 0

                    # Normalize event IDs: accept "0002" or "#[Event:0002]"
                    _target_eids = []
                    if args.events:
                        for e in args.events:
                            if e.startswith("#[Event:"):
                                _target_eids.append(e)
                            else:
                                _target_eids.append(f"#[Event:{e.zfill(4)}]")

                    # If --file given, find all events matching that filename
                    if args.file:
                        _fname = Path(args.file).name
                        for eid, ch in _ec.items():
                            if ch.get("file", "").endswith(_fname):
                                if eid not in _target_eids:
                                    _target_eids.append(eid)

                    if not _target_eids:
                        print(f"[-] No events specified or matched. Use --events or --file")
                    else:
                        for eid in _target_eids:
                            if eid in _ec:
                                _tids = _ec[eid].setdefault("task_ids", [])
                                if args.id not in _tids:
                                    _tids.append(args.id)
                                    _linked += 1
                                    print(f"  [+] {eid} → {args.id}")
                                else:
                                    print(f"  [=] {eid} already linked to {args.id}")
                            else:
                                print(f"  [-] {eid} not found in enriched_changes")
                        if _linked:
                            _vm_path.write_text(json.dumps(_vm, indent=2), encoding="utf-8")
                            print(f"[+] Linked {_linked} event(s) to {args.id}")
                        else:
                            print("[=] No new links needed")
            else:
                todo_manager.list_todos()

        elif args.command == 'plan':
            if args.plan_action == 'show':
                # Capture for zenity
                strategy_files = list(plan_manager.plans_dir.glob("*strategy*.md")) + \
                                list(plan_manager.plans_dir.glob("PLAN*.md"))
                if strategy_files:
                    latest = sorted(strategy_files)[-1]
                    display_output(latest.read_text(), title=f"Plan: {latest.name}", use_zenity=args.zenity)
                else:
                    print("[-] No plan found.")
            elif args.plan_action == 'scan':
                marks = plan_manager.scan_marks()
                out = ["STRATEGIC MARKS DETECTED", "="*40]
                for m in marks: out.append(f"- {m[0]}: {m[1]}:{m[2]}")
                display_output("\n".join(out), title="Babel Marks Scan", use_zenity=args.zenity)
            elif args.plan_action == 'report':
                report = plan_manager.project_report()
                display_output(report, title="Babel Project Health Report", use_zenity=args.zenity)
            elif args.plan_action == 'refresh':
                _pid = args.project_id
                _plans_root = Path(toolkit.base_dir).parent / "Data" / "plans"
                _pdir = _plans_root / "Plans" / _pid
                _epic_dir = _plans_root / "Epics"
                _epic_dir.mkdir(parents=True, exist_ok=True)
                _epic_out = _epic_dir / f"{_pid}.md"

                if _pid == "all":
                    # Refresh ALL projects
                    _pdirs = [d for d in (_plans_root / "Plans").iterdir() if d.is_dir()]
                    if not _pdirs:
                        print("[-] No project directories found in plans/Plans/")
                    else:
                        for _pd in sorted(_pdirs):
                            _p = _pd.name
                            _mds = [m for m in sorted(_pd.glob("*.md")) if "_TEMPLATED" not in m.name]
                            if not _mds:
                                print(f"  ○ {_p}: no plan docs")
                                continue
                            # Synthesize combined content from all plan docs
                            _combined = []
                            for _md in _mds:
                                _combined.append(f"# === {_md.name} ===")
                                _combined.append(_md.read_text(encoding="utf-8", errors="ignore"))
                                _combined.append("")
                            _synth_path = _pd / f"_combined_for_epic.md"
                            _synth_path.write_text("\n".join(_combined), encoding="utf-8")
                            _eo = _epic_dir / f"{_p}.md"
                            _fs = {"cluster_id": _p, "first_seen": ""}
                            _tmpl = toolkit._auto_template_plan(_synth_path, "integration_project", _fs, output_path=str(_eo))
                            _synth_path.unlink(missing_ok=True)
                            if _tmpl:
                                print(f"  ✓ {_p}: Epic refreshed ({len(_mds)} docs → {_eo.name})")
                            else:
                                print(f"  ○ {_p}: already templated or no changes")
                elif not _pdir.exists():
                    print(f"[-] Project directory not found: Plans/{_pid}")
                    _known = [d.name for d in (_plans_root / "Plans").iterdir() if d.is_dir()]
                    if _known:
                        print(f"    Known: {', '.join(sorted(_known))}")
                else:
                    # Synthesize from ALL plan docs in project dir (not just first)
                    _mds = [m for m in sorted(_pdir.glob("*.md")) if "_TEMPLATED" not in m.name]
                    if not _mds:
                        print(f"[-] No plan docs in Plans/{_pid}/")
                    else:
                        # Build combined content from all plan docs
                        _combined = []
                        for _md in _mds:
                            _combined.append(f"# === {_md.name} ===")
                            _combined.append(_md.read_text(encoding="utf-8", errors="ignore"))
                            _combined.append("")
                        # Write temporary combined file, template it, clean up
                        _synth_path = _pdir / f"_combined_for_epic.md"
                        _synth_path.write_text("\n".join(_combined), encoding="utf-8")
                        _filesync_data = {"cluster_id": _pid, "first_seen": ""}
                        _tmpl = toolkit._auto_template_plan(
                            _synth_path, "integration_project", _filesync_data, output_path=str(_epic_out))
                        _synth_path.unlink(missing_ok=True)
                        if _tmpl:
                            print(f"[+] Epic refreshed: {_epic_out} ({len(_mds)} plan docs synthesized)")
                        else:
                            print(f"[=] {_epic_out.name} already templated or no changes")
            elif args.plan_action == 'consolidate':
                # ── Plan Consolidation: discover, preview, template plan docs ──
                _do_preview = getattr(args, 'preview', False)
                _do_interactive = getattr(args, 'interactive', False)
                _do_execute = getattr(args, 'execute', False)
                _target_name = getattr(args, 'target', None)
                _no_backup = getattr(args, 'no_backup', False)
                _include_organized = getattr(args, 'include_organized', False)
                _assign_pair = getattr(args, 'assign', None)
                _batch_file = getattr(args, 'batch', None)
                _context_plan = getattr(args, 'context', None)
                _list_projects = getattr(args, 'list_projects', False)

                # ── Phase A: Discovery ──
                # base_dir = babel_data/profile → parents[3] = Data → / "plans"
                _plans_dir = Path(toolkit.base_dir).parents[3] / "plans"
                _template_name = "Project_Template_001.md"
                _all_plans = []

                for _md in sorted(_plans_dir.glob("*.md")):
                    if _md.name == _template_name:
                        continue
                    _sz = _md.stat().st_size
                    if _sz == 0:
                        continue
                    if _target_name and _md.name != _target_name:
                        continue
                    _content = _md.read_text(encoding="utf-8", errors="ignore")
                    _has_tmpl = "</High_Level>:" in _content and "</Diffs>:" in _content
                    _all_plans.append({
                        "path": _md,
                        "name": _md.name,
                        "size": _sz,
                        "has_template": _has_tmpl,
                        "content": _content,
                        "content_lines": len(_content.split("\n")),
                        "preview": _content[:200].replace("\n", " ")[:120],
                    })

                # Also scan subdirs if requested
                if _include_organized:
                    for _subdir in sorted(_plans_dir.iterdir()):
                        if _subdir.is_dir() and _subdir.name not in ("Tasks", "Refs", "Phases", "Diffs", "Milestones", "Agent_plans", "Plans"):
                            for _md in sorted(_subdir.glob("*.md")):
                                if _md.stat().st_size == 0:
                                    continue
                                if _target_name and _md.name != _target_name:
                                    continue
                                _content = _md.read_text(encoding="utf-8", errors="ignore")
                                _has_tmpl = "</High_Level>:" in _content and "</Diffs>:" in _content
                                _all_plans.append({
                                    "path": _md,
                                    "name": _md.name,
                                    "size": _md.stat().st_size,
                                    "has_template": _has_tmpl,
                                    "content": _content,
                                    "content_lines": len(_content.split("\n")),
                                    "preview": _content[:200].replace("\n", " ")[:120],
                                    "subdir": _subdir.name,
                                })

                _raw_plans = [p for p in _all_plans if not p["has_template"]]
                _tmpl_plans = [p for p in _all_plans if p["has_template"]]

                out = []
                out.append(f"PLAN CONSOLIDATION — {len(_all_plans)} plan(s) found")
                out.append(f"{'=' * 60}")
                out.append(f"  Raw (untemplated):     {len(_raw_plans)}")
                out.append(f"  Already templated:     {len(_tmpl_plans)}")
                if _target_name:
                    out.append(f"  Filter:                --target {_target_name}")
                out.append("")

                if not _raw_plans and not _do_preview:
                    out.append("  All plans already have template structure.")
                    out.append(f"\n[NEXT STEPS]")
                    out.append(f"  → plan consolidate --include-organized   Include subdirectory plans")
                    display_output("\n".join(out), title="Plan Consolidation", use_zenity=args.zenity)

                else:
                    # ── Phase B: Classification & Clustering ──
                    try:
                        import importlib.util, sys as _sys_pc
                        _mod_name_pc = "plan_consolidator"
                        if _mod_name_pc not in _sys_pc.modules:
                            _pc_path = Path(__file__).parent / "babel_data" / "inventory" / "core" / "plan_consolidator.py"
                            _spec_pc = importlib.util.spec_from_file_location(_mod_name_pc, _pc_path)
                            _mod_pc = importlib.util.module_from_spec(_spec_pc)
                            _sys_pc.modules[_mod_name_pc] = _mod_pc
                            _spec_pc.loader.exec_module(_mod_pc)
                        PlanConsolidator = _sys_pc.modules[_mod_name_pc].PlanConsolidator
                        _data_root = Path(toolkit.base_dir).parent / "Data"
                        _consolidator = PlanConsolidator(_data_root)
                        _has_consolidator = True
                    except (ImportError, AttributeError, FileNotFoundError):
                        _has_consolidator = False

                    # ── Discover known projects in plans/Plans/ ──
                    _known_projects = {}
                    _projects_root = _plans_dir / "Plans"
                    if _projects_root.exists():
                        for _pd in sorted(_projects_root.iterdir()):
                            if _pd.is_dir():
                                _pname = _pd.name
                                # Build keyword set from project name
                                _kws = set(_pname.lower().replace("_", " ").replace("-", " ").split())
                                _kws.discard("project")
                                _kws.discard("proposal")
                                _kws = {w for w in _kws if not w.isdigit()}  # Remove "001", "002", etc.
                                # Also scan existing plan docs inside for file refs
                                _proj_files = set()
                                for _pmf in _pd.glob("*.md"):
                                    try:
                                        _pc = _pmf.read_text(encoding="utf-8", errors="ignore")[:2000]
                                        _proj_files.update(re.findall(r'[\w/]+\.py', _pc))
                                    except Exception:
                                        pass
                                _known_projects[_pname] = {
                                    "path": _pd,
                                    "keywords": _kws,
                                    "file_refs": _proj_files,
                                }

                    def _match_to_project(plan_content, plan_name, plan_lines=0):
                        """Try to match a raw plan to a known project. Returns (project_name, score) or (None, 0)."""
                        # Skip very short plans (dir listings, stubs) — too noisy
                        if plan_lines < 20:
                            return (None, 0)
                        _best = (None, 0)
                        _lc = plan_content.lower()
                        _ln = plan_name.lower().replace("_", " ").replace("-", " ")
                        # Count how many project names appear in content (detect cross-ref docs)
                        _projects_mentioned = 0
                        for _pn in _known_projects:
                            if _pn.lower() in _lc:
                                _projects_mentioned += 1
                        _is_cross_ref = _projects_mentioned >= 2
                        # Common words that appear in many plan names — not distinctive
                        _stop_kws = {"debug", "system", "integration",
                                     "intergration", "implementation", "plan", "plans"}
                        for _pname, _pinfo in _known_projects.items():
                            _score = 0
                            # Keyword overlap — only distinctive words (5+ chars), skip stop words
                            for _kw in _pinfo["keywords"]:
                                if len(_kw) >= 5 and _kw not in _stop_kws:
                                    _count = _lc.count(_kw)
                                    _score += min(_count, 3)
                                    if _kw in _ln:
                                        _score += 10  # Strong signal if plan filename matches
                            # File ref overlap (shared .py references)
                            _plan_frefs = set(re.findall(r'[\w/]+\.py', plan_content[:3000]))
                            _overlap = _plan_frefs & _pinfo["file_refs"]
                            _score += len(_overlap) * 4
                            # Direct project name mention in content
                            _name_mentioned = (_pname.lower().replace("_", " ") in _lc) or (_pname.lower() in _lc)
                            if _name_mentioned:
                                # Cross-ref docs get minimal bonus; primary docs get moderate
                                _score += 3 if _is_cross_ref else 8
                            if _score > _best[1]:
                                _best = (_pname, _score)
                        # Require meaningful confidence — multiple signals needed
                        return _best if _best[1] >= 12 else (None, 0)

                    _by_type = defaultdict(list)
                    for _pi in _raw_plans:
                        _ppath = _pi["path"]
                        if _has_consolidator:
                            try:
                                _fs_data = _consolidator.analyze_plan_with_filesync(_ppath)
                                _ptype = _consolidator.classify_plan_type(_ppath)
                            except Exception:
                                _fs_data = {"cluster_id": "unclustered", "first_seen": "?", "activity_score": 0}
                                _ptype = "Unknown_Project"
                        else:
                            _fs_data = {"cluster_id": "unclustered", "first_seen": "?", "activity_score": 0}
                            _ptype = "Unknown_Project"
                        _pi["type"] = _ptype
                        _pi["fs_data"] = _fs_data
                        _pi["cluster"] = _fs_data.get("cluster_id", "unclustered")
                        _pi["activity"] = _fs_data.get("activity_score", 0) or 0

                        # Try to match to a known project
                        _matched_proj, _match_score = _match_to_project(_pi["content"], _pi["name"], _pi.get("content_lines", 0))
                        _pi["matched_project"] = _matched_proj
                        _pi["match_score"] = _match_score
                        if _matched_proj:
                            _pi["dest_dir"] = _plans_dir / "Plans" / _matched_proj
                            _pi["dest_label"] = f"Plans/{_matched_proj}/ (score:{_match_score})"
                        else:
                            _pi["dest_dir"] = _plans_dir / _ptype.lower()
                            _pi["dest_label"] = f"{_ptype.lower()}/ (inferred)"
                        _by_type[_ptype].append(_pi)

                    # ── --list-projects: show known projects with details ──
                    if _list_projects:
                        out.append(f"KNOWN PROJECTS ({len(_known_projects)} in plans/Plans/)")
                        out.append("=" * 60)
                        for _kp in sorted(_known_projects.keys()):
                            _kpi = _known_projects[_kp]
                            _kp_docs = list(_kpi["path"].glob("*.md"))
                            _kp_kws = ", ".join(sorted(k for k in _kpi["keywords"] if len(k) >= 4))
                            _kp_frefs = len(_kpi["file_refs"])
                            out.append(f"\n  {_kp}")
                            out.append(f"    Docs:     {len(_kp_docs)} ({', '.join(d.name[:30] for d in _kp_docs[:5])})")
                            out.append(f"    Keywords: {_kp_kws}")
                            out.append(f"    File refs: {_kp_frefs} .py files from existing docs")
                            # Show which raw plans are assigned here
                            _assigned = [p["name"] for p in _raw_plans if p.get("matched_project") == _kp]
                            if _assigned:
                                out.append(f"    Matched:  {len(_assigned)} plans")
                                for _a in _assigned:
                                    out.append(f"      → {_a}")
                        display_output("\n".join(out), title="Known Projects", use_zenity=args.zenity)

                    # ── --context PLAN: deep view of a single plan ──
                    elif _context_plan:
                        _found = None
                        for _pi in _raw_plans:
                            if _pi["name"] == _context_plan or _context_plan in _pi["name"]:
                                _found = _pi
                                break
                        if not _found:
                            print(f"[-] Plan not found: {_context_plan}")
                            print(f"    Available: {', '.join(p['name'][:35] for p in _raw_plans[:10])}...")
                        else:
                            _c = _found["content"]
                            _lines = _c.split("\n")
                            out.append(f"{'━' * 60}")
                            out.append(f"PLAN: {_found['name']} ({_found['size'] / 1024:.1f}K, {len(_lines)} lines)")
                            out.append(f"{'━' * 60}")
                            out.append(f"  Type:      {_found.get('type', '?')}")
                            out.append(f"  Cluster:   {_found.get('cluster', '?')}")
                            out.append(f"  Current:   {_found.get('dest_label', '?')}")
                            if _found.get("matched_project"):
                                out.append(f"  Project:   ★ {_found['matched_project']} (score:{_found.get('match_score', 0)})")
                            out.append("")
                            # Show scoring breakdown for ALL projects
                            out.append("  PROJECT SCORES:")
                            _lc = _c.lower()
                            _ln = _found["name"].lower().replace("_", " ").replace("-", " ")
                            _stop_kws = {"debug", "system", "integration",
                                         "intergration", "implementation", "plan", "plans"}
                            _projects_mentioned = sum(1 for _pn in _known_projects if _pn.lower() in _lc)
                            _is_xref = _projects_mentioned >= 2
                            for _pname, _pinfo in sorted(_known_projects.items()):
                                _s = 0
                                _detail = []
                                for _kw in _pinfo["keywords"]:
                                    if len(_kw) >= 5 and _kw not in _stop_kws:
                                        _cnt = _lc.count(_kw)
                                        if _cnt > 0:
                                            _ks = min(_cnt, 3)
                                            _s += _ks
                                            _detail.append(f"kw:{_kw}={_ks}")
                                            if _kw in _ln:
                                                _s += 10
                                                _detail.append(f"filename:{_kw}=+10")
                                _plan_frefs = set(re.findall(r'[\w/]+\.py', _c[:3000]))
                                _overlap = _plan_frefs & _pinfo["file_refs"]
                                if _overlap:
                                    _s += len(_overlap) * 4
                                    _detail.append(f"filerefs:{len(_overlap)}x4={len(_overlap)*4}")
                                _nm = (_pname.lower().replace("_", " ") in _lc) or (_pname.lower() in _lc)
                                if _nm:
                                    _nb = 3 if _is_xref else 8
                                    _s += _nb
                                    _detail.append(f"name_mention=+{_nb}{'(xref)' if _is_xref else ''}")
                                if _s > 0:
                                    _pass = "✓" if _s >= 12 else "✗"
                                    out.append(f"    {_pass} {_pname}: {_s}  ({', '.join(_detail)})")
                            out.append("")
                            # File refs found
                            _frefs = list(set(re.findall(r'[\w/]+\.(?:py|json|md)', _c)))
                            out.append(f"  FILE REFS ({len(_frefs)}):")
                            for _fr in sorted(_frefs)[:20]:
                                out.append(f"    {_fr}")
                            if len(_frefs) > 20:
                                out.append(f"    ... +{len(_frefs) - 20} more")
                            out.append("")
                            # Content preview (first 15 + last 5 lines)
                            out.append(f"  CONTENT PREVIEW:")
                            for _li in _lines[:15]:
                                out.append(f"    {_li[:120]}")
                            if len(_lines) > 20:
                                out.append(f"    ... ({len(_lines) - 20} lines omitted) ...")
                                for _li in _lines[-5:]:
                                    out.append(f"    {_li[:120]}")
                            display_output("\n".join(out), title=f"Context: {_found['name']}", use_zenity=args.zenity)

                    # ── --assign PLAN PROJECT: manually assign a plan to a project ──
                    elif _assign_pair:
                        _aplan, _aproj = _assign_pair
                        _found = None
                        for _pi in _raw_plans:
                            if _pi["name"] == _aplan or _aplan in _pi["name"]:
                                _found = _pi
                                break
                        if not _found:
                            print(f"[-] Plan not found: {_aplan}")
                        elif _aproj not in _known_projects:
                            print(f"[-] Unknown project: {_aproj}")
                            print(f"    Known: {', '.join(sorted(_known_projects.keys()))}")
                        else:
                            _dest = _plans_dir / "Plans" / _aproj
                            _dest.mkdir(parents=True, exist_ok=True)
                            # Backup first
                            if not _no_backup:
                                _ts_bk = datetime.now().strftime("%Y%m%d_%H%M%S")
                                _bk_dir = Path(toolkit.base_dir).parent / "archive" / f"plans_backup_{_ts_bk}"
                                _bk_dir.mkdir(parents=True, exist_ok=True)
                                shutil.copy2(_found["path"], _bk_dir / _found["name"])
                                print(f"[+] Backed up: {_found['name']} → {_bk_dir.name}/")
                            # Template it
                            _tmpl = toolkit._auto_template_plan(
                                _found["path"], _found.get("type", "Unknown"), _found.get("fs_data", {}))
                            _tmpl_name = _found["path"].stem + "_TEMPLATED.md"
                            _tmpl_src = _plans_dir / _tmpl_name
                            # Move original + templated to project dir
                            _dst_orig = _dest / _found["name"]
                            shutil.move(str(_found["path"]), str(_dst_orig))
                            print(f"[+] Moved: {_found['name']} → Plans/{_aproj}/")
                            if _tmpl_src.exists():
                                _dst_tmpl = _dest / _tmpl_name
                                shutil.move(str(_tmpl_src), str(_dst_tmpl))
                                print(f"[+] Templated: {_tmpl_name} → Plans/{_aproj}/")
                            # Update consolidation index
                            _cidx_path = _plans_dir / "consolidation_index.json"
                            _cidx = {}
                            if _cidx_path.exists():
                                try:
                                    _cidx = json.loads(_cidx_path.read_text(encoding="utf-8"))
                                except Exception:
                                    pass
                            if "plans" not in _cidx:
                                _cidx["plans"] = []
                            _cidx["plans"].append({
                                "original": _found["name"],
                                "project": _aproj,
                                "action": "assign",
                                "timestamp": datetime.now().isoformat(),
                            })
                            _cidx_path.write_text(json.dumps(_cidx, indent=2), encoding="utf-8")

                    # ── --batch FILE: process batch decisions from JSON ──
                    elif _batch_file:
                        _bf_path = Path(_batch_file)
                        if not _bf_path.exists():
                            print(f"[-] Batch file not found: {_batch_file}")
                        else:
                            try:
                                _decisions = json.loads(_bf_path.read_text(encoding="utf-8"))
                            except Exception as e:
                                print(f"[-] Invalid JSON: {e}")
                                _decisions = {}
                            if _decisions:
                                # Backup all affected plans
                                _affected = [p for p in _raw_plans if p["name"] in _decisions]
                                if _affected and not _no_backup:
                                    _ts_bk = datetime.now().strftime("%Y%m%d_%H%M%S")
                                    _bk_dir = Path(toolkit.base_dir).parent / "archive" / f"plans_backup_{_ts_bk}"
                                    _bk_dir.mkdir(parents=True, exist_ok=True)
                                    for _pi in _affected:
                                        shutil.copy2(_pi["path"], _bk_dir / _pi["name"])
                                    print(f"[+] Backed up {len(_affected)} plans → {_bk_dir.name}/")
                                _n_assigned = 0
                                _n_skipped = 0
                                for _pi in _raw_plans:
                                    _dec = _decisions.get(_pi["name"])
                                    if not _dec:
                                        continue
                                    _action = _dec.get("action", "skip") if isinstance(_dec, dict) else _dec
                                    _proj = _dec.get("project") if isinstance(_dec, dict) else None
                                    if _action == "skip":
                                        _n_skipped += 1
                                        print(f"  ○ Skip: {_pi['name']}")
                                        continue
                                    if _action == "assign" and _proj:
                                        if _proj not in _known_projects:
                                            print(f"  ✗ Unknown project '{_proj}' for {_pi['name']}")
                                            continue
                                        _dest = _plans_dir / "Plans" / _proj
                                        _dest.mkdir(parents=True, exist_ok=True)
                                        _tmpl = toolkit._auto_template_plan(
                                            _pi["path"], _pi.get("type", "Unknown"), _pi.get("fs_data", {}))
                                        _tmpl_name = _pi["path"].stem + "_TEMPLATED.md"
                                        _tmpl_src = _plans_dir / _tmpl_name
                                        shutil.move(str(_pi["path"]), str(_dest / _pi["name"]))
                                        if _tmpl_src.exists():
                                            shutil.move(str(_tmpl_src), str(_dest / _tmpl_name))
                                        print(f"  ✓ Assigned: {_pi['name']} → Plans/{_proj}/")
                                        _n_assigned += 1
                                    elif _action == "accept":
                                        # Accept algorithm's suggestion
                                        _dest = _pi.get("dest_dir", _plans_dir / _pi.get("type", "unknown").lower())
                                        _dest.mkdir(parents=True, exist_ok=True)
                                        _tmpl = toolkit._auto_template_plan(
                                            _pi["path"], _pi.get("type", "Unknown"), _pi.get("fs_data", {}))
                                        _tmpl_name = _pi["path"].stem + "_TEMPLATED.md"
                                        _tmpl_src = _plans_dir / _tmpl_name
                                        shutil.move(str(_pi["path"]), str(_dest / _pi["name"]))
                                        if _tmpl_src.exists():
                                            shutil.move(str(_tmpl_src), str(_dest / _tmpl_name))
                                        print(f"  ✓ Accepted: {_pi['name']} → {_pi.get('dest_label', '?')}")
                                        _n_assigned += 1
                                print(f"\n[BATCH COMPLETE] Assigned: {_n_assigned}, Skipped: {_n_skipped}")
                                # Update consolidation index
                                _cidx_path = _plans_dir / "consolidation_index.json"
                                _cidx = {}
                                if _cidx_path.exists():
                                    try:
                                        _cidx = json.loads(_cidx_path.read_text(encoding="utf-8"))
                                    except Exception:
                                        pass
                                if "plans" not in _cidx:
                                    _cidx["plans"] = []
                                _cidx["last_batch"] = datetime.now().isoformat()
                                _cidx["batch_assigned"] = _n_assigned
                                _cidx_path.write_text(json.dumps(_cidx, indent=2), encoding="utf-8")

                    # ── Default mode (no flags): overview report ──
                    elif not _do_preview and not _do_interactive and not _do_execute:
                        # Show known projects
                        if _known_projects:
                            out.append(f"[KNOWN PROJECTS] ({len(_known_projects)} in plans/Plans/)")
                            for _kp in sorted(_known_projects.keys()):
                                _kp_count = len(list(_known_projects[_kp]["path"].glob("*.md")))
                                out.append(f"   {_kp:50s} {_kp_count} docs")
                            out.append("")

                        # Show matched vs unmatched
                        _matched = [p for p in _raw_plans if p.get("matched_project")]
                        _unmatched = [p for p in _raw_plans if not p.get("matched_project")]
                        if _matched:
                            out.append(f"[MATCHED TO PROJECTS] ({len(_matched)} plans)")
                            for _it in _matched:
                                out.append(f"   {_it['name'][:45]:47s} → {_it['dest_label']}")
                            out.append("")

                        for _ptype in sorted(_by_type.keys()):
                            _items = [i for i in _by_type[_ptype] if not i.get("matched_project")]
                            if not _items:
                                continue
                            out.append(f"── {_ptype} ({len(_items)} unmatched) ──")
                            for _it in sorted(_items, key=lambda x: x["activity"], reverse=True):
                                _sz_k = f"{_it['size'] / 1024:.1f}K"
                                _act = f"activity:{_it['activity']:.1f}" if _it["activity"] else "no-history"
                                _cid = str(_it["cluster"])[:25]
                                out.append(f"   {_it['name'][:48]:50s} {_sz_k:>6s}  cluster:{_cid:25s} {_act}")
                            out.append("")

                        out.append(f"[NEXT STEPS]")
                        out.append(f"  → plan consolidate --preview                 Detailed per-plan preview")
                        out.append(f"  → plan consolidate --interactive             Step through with approval")
                        out.append(f"  → plan consolidate --preview -t file.md      Preview a single plan")
                        out.append(f"  → plan consolidate --execute                 Template all (with backup)")
                        display_output("\n".join(out), title="Plan Consolidation", use_zenity=args.zenity)

                    else:
                        # ── Phase C: Preview / Interactive / Execute ──

                        # Count what _auto_template_plan would match for preview stats
                        _vm_path_pc = Path(__file__).parents[2] / "backup" / "version_manifest.json"
                        _enriched_pc = {}
                        if _vm_path_pc.exists():
                            try:
                                _vm_pc = json.loads(_vm_path_pc.read_text(encoding="utf-8"))
                                _enriched_pc = _vm_pc.get("enriched_changes", {})
                            except Exception:
                                pass

                        _todos_path_pc = _plans_dir / "todos.json"
                        _todos_pc = {}
                        if _todos_path_pc.exists():
                            try:
                                _todos_pc = json.loads(_todos_path_pc.read_text(encoding="utf-8"))
                            except Exception:
                                pass

                        _manifest_path_pc = Path(__file__).parents[2] / "backup" / "py_manifest.json"
                        _manifest_pc = {}
                        if _manifest_path_pc.exists():
                            try:
                                _manifest_pc = json.loads(_manifest_path_pc.read_text(encoding="utf-8"))
                            except Exception:
                                pass

                        _accepted = []
                        _skipped = []

                        for _idx, _pi in enumerate(_raw_plans, 1):
                            # Extract file refs from plan content for stats
                            _file_refs_pc = list(set(re.findall(r'[\w/]+\.(?:py|json|md|txt|yaml|toml)', _pi["content"])))
                            _mark_refs_pc = re.findall(r'#\[Mark:([^\]]+)\]', _pi["content"])
                            _event_refs_pc = re.findall(r'#\[Event:([^\]]+)\]', _pi["content"])

                            # Count enriched_changes that would match
                            _diffs_count = 0
                            for _eid, _ec in _enriched_pc.items():
                                _ec_file = (_ec.get("file") or "").split("/")[-1]
                                if _ec_file and any(_ec_file in fr for fr in _file_refs_pc):
                                    _diffs_count += 1

                            # Count tasks that would match
                            _tasks_count = 0
                            for _phase, _tblock in _todos_pc.items():
                                if not isinstance(_tblock, dict):
                                    continue
                                for _tid, _tv in _tblock.items():
                                    if not isinstance(_tv, dict):
                                        continue
                                    _tw = _tv.get("wherein", "")
                                    if any(fr in _tw for fr in _file_refs_pc):
                                        _tasks_count += 1

                            # Count provisions from py_manifest
                            _prov_count = 0
                            for _fr in _file_refs_pc:
                                _fr_name = _fr.split("/")[-1]
                                for _mk in _manifest_pc:
                                    if isinstance(_manifest_pc[_mk], dict) and _fr_name in _mk:
                                        _prov_count += 1

                            _sz_k = f"{_pi['size'] / 1024:.1f}K"
                            _cid = str(_pi["cluster"])[:30]
                            _act = _pi["activity"]
                            _subdir = _pi.get("subdir", "plans/")

                            if _do_preview or _do_interactive:
                                # Show detailed preview block
                                out.append(f"{'━' * 60}")
                                out.append(f"[{_idx}/{len(_raw_plans)}] {_pi['name']} ({_sz_k}, {_pi['content_lines']} lines)")
                                out.append(f"{'━' * 60}")
                                out.append(f"  Type:      {_pi['type']}")
                                out.append(f"  Cluster:   {_cid} (activity: {_act:.1f})")
                                out.append(f"  Location:  {_subdir}")
                                out.append(f"  Status:    RAW → will template to Project_Template_001 format")
                                if _pi.get("matched_project"):
                                    out.append(f"  Project:   ★ {_pi['matched_project']} (score:{_pi['match_score']})")
                                out.append(f"  Dest:      {_pi['dest_label']}")
                                out.append(f"  File refs: {len(_file_refs_pc)} detected, Marks: {len(_mark_refs_pc)}, Events: {len(_event_refs_pc)}")
                                out.append(f"  Sections:")
                                out.append(f"    </High_Level>    ← from type/cluster + first lines")
                                out.append(f"    </Mid_Level>     ← ALL original content ({_pi['content_lines']} lines preserved)")
                                out.append(f"    </Diffs>         ← {_diffs_count} enriched_changes matched")
                                out.append(f"    </Provisions>    ← {_prov_count} manifest entries matched")
                                out.append(f"    </Current_Tasks> ← {_tasks_count} tasks matched")
                                out.append(f"  Output:    {_pi['dest_label']}/{_pi['name'].replace('.md', '_TEMPLATED.md')}")
                                out.append(f"  Preview:   {_pi['preview'][:100]}...")
                                out.append("")

                            if _do_interactive:
                                # Print what we have so far, prompt user
                                print("\n".join(out))
                                out.clear()
                                # Build project shortcut list for reassignment
                                _proj_list = sorted(_known_projects.keys())
                                _proj_hint = ""
                                if _proj_list:
                                    _proj_hint = "  [p] Assign to project  "
                                while True:
                                    try:
                                        _choice = input(f"  [y] Accept  [n] Skip  [v] View template  {_proj_hint}[q] Quit → ").strip().lower()
                                    except (EOFError, KeyboardInterrupt):
                                        _choice = "q"
                                    if _choice == "y":
                                        _accepted.append(_pi)
                                        print(f"  ✓ Accepted → {_pi['dest_label']}")
                                        break
                                    elif _choice == "n":
                                        _skipped.append(_pi)
                                        print(f"  ○ Skipped: {_pi['name']}")
                                        break
                                    elif _choice == "v":
                                        # Render template preview without writing
                                        _tmpl_preview = toolkit._auto_template_plan(
                                            _pi["path"], _pi["type"], _pi["fs_data"]
                                        )
                                        if _tmpl_preview and _tmpl_preview.exists():
                                            _tv_content = _tmpl_preview.read_text(encoding="utf-8")
                                            print(f"\n{'─' * 40} TEMPLATE PREVIEW {'─' * 40}")
                                            print(_tv_content[:3000])
                                            if len(_tv_content) > 3000:
                                                print(f"\n... ({len(_tv_content)} chars total, truncated for display)")
                                            print(f"{'─' * 40} END PREVIEW {'─' * 40}\n")
                                            _tmpl_preview.unlink(missing_ok=True)
                                        else:
                                            print("  (already templated or template generation failed)")
                                    elif _choice == "p" and _proj_list:
                                        print(f"  Available projects:")
                                        for _j, _pn in enumerate(_proj_list, 1):
                                            _marker = " ★" if _pn == _pi.get("matched_project") else ""
                                            print(f"    {_j}. {_pn}{_marker}")
                                        print(f"    0. Keep as: {_pi['dest_label']}")
                                        try:
                                            _pch = input("  Select project number → ").strip()
                                            _pnum = int(_pch)
                                            if 1 <= _pnum <= len(_proj_list):
                                                _sel_proj = _proj_list[_pnum - 1]
                                                _pi["matched_project"] = _sel_proj
                                                _pi["dest_dir"] = _plans_dir / "Plans" / _sel_proj
                                                _pi["dest_label"] = f"Plans/{_sel_proj}/ (user-assigned)"
                                                print(f"  → Reassigned to: {_pi['dest_label']}")
                                            elif _pnum == 0:
                                                print(f"  → Keeping: {_pi['dest_label']}")
                                        except (ValueError, EOFError):
                                            print("  (cancelled)")
                                    elif _choice == "q":
                                        print(f"\n  Quit — {len(_accepted)} accepted so far")
                                        break
                                    else:
                                        print("  Invalid choice. Use y/n/v/p/q")
                                if _choice == "q":
                                    break
                            elif _do_execute:
                                _accepted.append(_pi)

                        # ── Phase E: Execution ──
                        _to_process = _accepted if (_do_interactive or _do_execute) else []

                        if _to_process:
                            # Backup first (unless --no-backup)
                            if not _no_backup:
                                _ts_bk = datetime.now().strftime("%Y%m%d_%H%M%S")
                                _bk_dir = Path(toolkit.base_dir).parent / "archive" / f"plans_backup_{_ts_bk}"
                                _bk_dir.mkdir(parents=True, exist_ok=True)
                                _bk_manifest = {"timestamp": _ts_bk, "files": []}
                                for _pi in _to_process:
                                    _dst = _bk_dir / _pi["name"]
                                    shutil.copy2(_pi["path"], _dst)
                                    _bk_manifest["files"].append({
                                        "name": _pi["name"],
                                        "size": _pi["size"],
                                        "type": _pi.get("type", "?"),
                                    })
                                (_bk_dir / "backup_manifest.json").write_text(
                                    json.dumps(_bk_manifest, indent=2), encoding="utf-8"
                                )
                                out.append(f"[+] Backed up {len(_to_process)} plan(s) to {_bk_dir.name}/")
                                out.append("")

                            # Template each + move to destination
                            _templated_count = 0
                            _organized_count = 0
                            _index_entries = []
                            for _pi in _to_process:
                                _tmpl_result = toolkit._auto_template_plan(
                                    _pi["path"], _pi.get("type", "Unknown_Project"), _pi.get("fs_data", {})
                                )
                                if _tmpl_result:
                                    _templated_count += 1
                                    # Move original + templated into destination directory
                                    _dest = _pi.get("dest_dir")
                                    _dest_label = _pi.get("dest_label", "?")
                                    if _dest:
                                        _dest.mkdir(parents=True, exist_ok=True)
                                        _org_dst = _dest / _pi["name"]
                                        _tmpl_dst = _dest / _tmpl_result.name
                                        # Only move if not already there
                                        if _pi["path"] != _org_dst and not _org_dst.exists():
                                            shutil.move(str(_pi["path"]), str(_org_dst))
                                        if _tmpl_result != _tmpl_dst and not _tmpl_dst.exists():
                                            shutil.move(str(_tmpl_result), str(_tmpl_dst))
                                        elif _tmpl_result.exists() and _tmpl_result != _tmpl_dst:
                                            shutil.copy2(str(_tmpl_result), str(_tmpl_dst))
                                            _tmpl_result.unlink()
                                        _organized_count += 1
                                        out.append(f"  [+] {_pi['name']} → {_dest_label}")
                                    else:
                                        out.append(f"  [+] Templated: {_pi['name']} → {_tmpl_result.name} (in-place)")
                                    _index_entries.append({
                                        "original": _pi["name"],
                                        "templated": _tmpl_result.name,
                                        "type": _pi.get("type", "?"),
                                        "cluster": str(_pi.get("cluster", "?")),
                                        "project": _pi.get("matched_project"),
                                        "destination": str(_dest) if _dest else None,
                                        "backup": f"archive/plans_backup_{_ts_bk}/{_pi['name']}" if not _no_backup else None,
                                        "size": _pi["size"],
                                        "lines": _pi["content_lines"],
                                    })
                                else:
                                    out.append(f"  [=] {_pi['name']} — already templated or generation failed")

                            out.append("")
                            out.append(f"[CONSOLIDATION COMPLETE]")
                            out.append(f"  Processed:   {len(_to_process)}/{len(_raw_plans)} plans")
                            out.append(f"  Templated:   {_templated_count}")
                            out.append(f"  Organized:   {_organized_count} moved to destination dirs")
                            if not _no_backup:
                                out.append(f"  Backed up:   archive/plans_backup_{_ts_bk}/")
                            _n_skipped = len(_raw_plans) - len(_to_process)
                            if _n_skipped > 0:
                                out.append(f"  Skipped:     {_n_skipped}")

                            # Write consolidation index
                            if _index_entries:
                                _idx_path = _plans_dir / "consolidation_index.json"
                                _idx_data = {"generated": datetime.now().isoformat(), "plans": _index_entries}
                                # Merge with existing index if present
                                if _idx_path.exists():
                                    try:
                                        _existing_idx = json.loads(_idx_path.read_text(encoding="utf-8"))
                                        _existing_plans = _existing_idx.get("plans", [])
                                        _existing_names = {e["original"] for e in _existing_plans}
                                        for _ie in _index_entries:
                                            if _ie["original"] not in _existing_names:
                                                _existing_plans.append(_ie)
                                            else:
                                                # Update existing entry
                                                for _j, _ep in enumerate(_existing_plans):
                                                    if _ep["original"] == _ie["original"]:
                                                        _existing_plans[_j] = _ie
                                                        break
                                        _idx_data["plans"] = _existing_plans
                                    except Exception:
                                        pass
                                _idx_path.write_text(json.dumps(_idx_data, indent=2), encoding="utf-8")
                                out.append(f"  Index:       consolidation_index.json ({len(_idx_data['plans'])} entries)")

                        # Preview-only summary
                        if _do_preview and not _do_interactive and not _do_execute:
                            out.append("")
                            out.append(f"[PREVIEW COMPLETE — no changes made]")

                        out.append("")
                        out.append(f"[NEXT STEPS]")
                        if not _do_execute and not _do_interactive:
                            out.append(f"  → plan consolidate --interactive             Step through with approval")
                            out.append(f"  → plan consolidate --execute                 Template all (with backup)")
                        out.append(f"  → plan consolidate --preview -t file.md      Preview a single plan")
                        out.append(f"  → cat plans/FILE_TEMPLATED.md                Inspect a templated plan")
                        out.append(f"  → plan report                                Project health report")

                        if not _do_interactive:
                            display_output("\n".join(out), title="Plan Consolidation", use_zenity=args.zenity)
                        else:
                            print("\n".join(out))
            elif args.plan_action == 'generate':
                # ── MoE Plan Generation (T4-2) ──────────────────────────────
                _scripts_dir = str(Path(__file__).parent / 'regex_project' / 'activities' / 'tools' / 'scripts')
                if _scripts_dir not in sys.path:
                    sys.path.insert(0, _scripts_dir)
                try:
                    from moe_plan_engine import MoEPlanEngine
                    _trainer_root = Path(__file__).parents[3]
                    engine = MoEPlanEngine(_trainer_root)

                    if getattr(args, 'list_models', False):
                        _models = engine.discover_models()
                        if _models:
                            print(f"\n  Available GGUF models ({len(_models)}):")
                            for m in _models:
                                print(f"    {m.name:<30} {m.gguf_path}")
                        else:
                            print("  No GGUF models found. Check Models/*/exports/gguf/")
                    elif not getattr(args, 'task_id', None):
                        print("  Usage: plan generate <task_id> [--models M1,M2] [--compare]")
                        print("         plan generate --list-models")
                    else:
                        _model_names = args.models.split(',') if args.models else None
                        print(f"\n  MoE Plan Generation: task={args.task_id}")
                        print(f"  Models: {_model_names or 'all discovered'}")
                        print(f"  n_ctx={args.n_ctx}  max_tokens={args.max_tokens}\n")

                        results, comparison = engine.run(
                            args.task_id,
                            model_names=_model_names,
                            compare=getattr(args, 'compare', False),
                        )
                        for r in results:
                            print(f"  [{r.model_name}] {r.duration_seconds:.1f}s, "
                                  f"{r.tokens_generated} tok → {r.output_path.name}")
                        if comparison:
                            print(f"\n  Agreement: {comparison.get('agreement_score', 0):.0%}")
                            _meta_path = comparison.get('metadata_path', '')
                            if _meta_path:
                                print(f"  Report: {_meta_path}")
                except ImportError as _ie:
                    print(f"  [ERROR] Could not import moe_plan_engine: {_ie}")
                except Exception as _e:
                    print(f"  [ERROR] MoE plan generation failed: {_e}")
            else:
                plan_manager.show_plan()

        elif args.command == 'analyze':
            if args.system_packages:
                toolkit._analyze_system_packages()
                return

            toolkit.analyze_system_baseline(depth=args.depth)

            # Show summary of what was analyzed
            summary = []
            summary.append(f"\n{'='*60}")
            summary.append(f"SYSTEM ANALYSIS COMPLETE (Depth {args.depth})")
            summary.append(f"{'='*60}\n")
            summary.append(f"Session: {toolkit.session_id}")
            summary.append(f"Total Artifacts: {len(toolkit.session.artifacts)}")

            # Count by type
            by_type = {}
            for artifact in toolkit.session.artifacts.values():
                t = artifact.artifact_type.value
                by_type[t] = by_type.get(t, 0) + 1

            summary.append("\nArtifacts by Type:")
            for atype, count in sorted(by_type.items(), key=lambda x: x[1], reverse=True):
                summary.append(f"  {atype}: {count}")

            summary_text = "\n".join(summary)
            display_output(summary_text, title=f"System Analysis (Depth {args.depth})", use_zenity=args.zenity)

            if args.save:
                toolkit.save()
        
        elif args.command == 'latest':
            # Handle --action-list flag (show saved actions)
            if hasattr(args, 'action_list') and args.action_list:
                saved_data = toolkit._load_suggested_actions()
                actions = saved_data.get('actions', [])
                metadata = saved_data.get('metadata', {})

                if not actions:
                    print("\n[SUGGESTED ACTIONS]\nNo saved actions found. Run 'latest' first to generate suggestions.\n")
                    return

                output_lines = [
                    f"\n{'='*60}",
                    f"SAVED SUGGESTED ACTIONS ({metadata.get('count', 0)} total)",
                    f"Generated: {metadata.get('generated_at', 'unknown')}",
                    f"High Confidence (≥0.7): {metadata.get('high_confidence_count', 0)}",
                    f"{'='*60}\n"
                ]

                # Group by confidence level
                high_conf = [a for a in actions if a.get('confidence', 0) >= 0.7]
                med_conf = [a for a in actions if 0.5 <= a.get('confidence', 0) < 0.7]
                low_conf = [a for a in actions if a.get('confidence', 0) < 0.5]

                if high_conf:
                    output_lines.append("[HIGH CONFIDENCE (≥0.7) - Recommended for batch]")
                    for i, action in enumerate(high_conf, 1):
                        output_lines.append(f"{i}. [{action.get('confidence', 0):.2f}] {action.get('label', 'Unknown')}")
                        output_lines.append(f"   ID: {action.get('id', 'unknown')}")
                        output_lines.append(f"   Command: {action.get('command', 'N/A')}")
                        output_lines.append("")

                if med_conf:
                    output_lines.append("\n[MEDIUM CONFIDENCE (0.5-0.7)]")
                    for action in med_conf:
                        output_lines.append(f"  [{action.get('confidence', 0):.2f}] {action.get('label', 'Unknown')}")
                        output_lines.append(f"      ID: {action.get('id', 'unknown')}")

                if low_conf:
                    output_lines.append("\n[LOW CONFIDENCE (<0.5)]")
                    for action in low_conf:
                        output_lines.append(f"  [{action.get('confidence', 0):.2f}] {action.get('label', 'Unknown')} (ID: {action.get('id', 'unknown')})")

                output_lines.append("\n" + "="*60)
                output_lines.append("Usage:")
                output_lines.append("  Run specific action:  python3 Os_Toolkit.py latest --action-run <ID>")
                output_lines.append("  Run high-conf batch:  python3 Os_Toolkit.py latest --action-batch")
                output_lines.append("  Preview batch:        python3 Os_Toolkit.py latest --action-batch --diff")
                output_lines.append("="*60)

                display_output("\n".join(output_lines), title="Suggested Actions", use_zenity=args.zenity)
                return

            # Handle --action-run flag (run specific action)
            if hasattr(args, 'action_run') and args.action_run:
                saved_data = toolkit._load_suggested_actions()
                actions = saved_data.get('actions', [])

                target_action = next((a for a in actions if a.get('id') == args.action_run), None)

                if not target_action:
                    print(f"\n⚠️  Action '{args.action_run}' not found in saved actions.")
                    print(f"Run 'python3 Os_Toolkit.py latest --action-list' to see available actions.\n")
                    return

                print(f"\n[EXECUTING ACTION]")
                print(f"Label: {target_action.get('label', 'Unknown')}")
                print(f"Command: {target_action.get('command', 'N/A')}")
                print(f"Confidence: {target_action.get('confidence', 0):.2f}\n")

                result = subprocess.run(target_action.get('command', 'echo "No command"'),
                                      shell=True, capture_output=True, text=True)

                output_text = f"[COMMAND]\n{target_action.get('command')}\n\n[OUTPUT]\n{result.stdout}\n{result.stderr}"
                display_output(output_text, title=f"Action Result: {args.action_run}", use_zenity=args.zenity)
                return

            # Handle --action-batch flag (run all high-confidence actions)
            if hasattr(args, 'action_batch') and args.action_batch:
                saved_data = toolkit._load_suggested_actions()
                actions = saved_data.get('actions', [])

                # Filter to high-confidence actions only (≥0.7)
                batch_actions = [a for a in actions if a.get('confidence', 0) >= 0.7]

                if not batch_actions:
                    print("\n[BATCH MODE]\nNo high-confidence actions (≥0.7) found to run.\n")
                    return

                # Preview mode (--diff)?
                if hasattr(args, 'diff') and args.diff:
                    print(f"\n[BATCH PREVIEW - DIFF MODE]")
                    print(f"Would execute {len(batch_actions)} high-confidence actions:\n")
                    for i, action in enumerate(batch_actions, 1):
                        print(f"{i}. [{action.get('confidence'):.2f}] {action.get('label')}")
                        print(f"   Command: {action.get('command')}")
                        print("")
                    print("Run without --diff to execute these actions.")
                    return

                # Execute batch
                print(f"\n[BATCH EXECUTION]")
                print(f"Running {len(batch_actions)} high-confidence actions...\n")

                results = []
                for i, action in enumerate(batch_actions, 1):
                    print(f"[{i}/{len(batch_actions)}] Executing: {action.get('label')}")
                    result = subprocess.run(action.get('command', 'echo "No command"'),
                                          shell=True, capture_output=True, text=True)

                    results.append({
                        'action': action,
                        'stdout': result.stdout,
                        'stderr': result.stderr,
                        'returncode': result.returncode
                    })

                    if result.returncode == 0:
                        print(f"    ✓ Success")
                    else:
                        print(f"    ✗ Failed (code {result.returncode})")

                # Summary
                success_count = sum(1 for r in results if r['returncode'] == 0)
                print(f"\n[BATCH COMPLETE]")
                print(f"Success: {success_count}/{len(batch_actions)}")
                print(f"Failed: {len(batch_actions) - success_count}/{len(batch_actions)}")

                # Save detailed results
                results_file = toolkit.base_dir.parent / "profile/batch_results.json"
                with open(results_file, 'w') as f:
                    json.dump({
                        'timestamp': datetime.now().isoformat(),
                        'total': len(batch_actions),
                        'success': success_count,
                        'results': results
                    }, f, indent=2)

                print(f"Detailed results saved to: {results_file}")
                return

            # Normal latest command execution
            output = []
            output.append(f"\n{'='*60}")
            output.append(f"LATEST SYSTEM STATE: {datetime.now().isoformat()}")
            output.append(f"{'='*60}\n")
            
            # 1. Project Status (from generated file)
            status_file = Path.cwd() / "PROJECT_STATUS_GENERATED.md"
            if status_file.exists():
                output.append("[PROJECT STATUS]")
                with open(status_file, 'r') as f:
                    # Print first 25 lines
                    for i, line in enumerate(f):
                        if i < 25:
                            output.append(f"  {line.strip()}")
                output.append("  ... (see full file for details)\n")
            
            # 2. Recent Journal Activity
            output.append("[RECENT ACTIVITY]")
            stats = toolkit.journal_stats()
            for entry in stats['recent_entries'][-5:]:
                time_str = entry['timestamp'].split('T')[1][:8]
                output.append(f"  [{time_str}] {entry['entry_type']}: {entry['content'][:60]}...")
            
            # 3. Security & Backups
            output.append("\n[SECURITY & HEALTH]")
            archive_dir = toolkit.base_dir.parent.parent / "archive"
            history_dir = toolkit.base_dir.parent.parent / "Data" / "backup" / "history"
            archive_baks = len(list(archive_dir.glob("*.bak"))) if archive_dir.exists() else 0
            history_versions = len(list(history_dir.iterdir())) if history_dir.exists() else 0
            output.append(f"  Backups: {archive_baks} archive .bak + {history_versions} versioned snapshots")
            
            # 4. CONFORMITY CHECK (Reactive Suggestions)
            output.append("\n[CONFORMITY CHECK]")
            # Run security check (internal call)
            warnings = []
            sec_res = toolkit.actions['check_security'].command_func()
            if "SECURITY WARNINGS FOUND" in sec_res:
                output.append("  ⚠️  SECURITY ALERT: Anomalies detected in PIDs/Connections.")
                warnings.append("Security anomalies detected")
            else:
                output.append("  ✓ Security: Baseline Clean.")

            # Run workflow audit (internal call)
            work_res = toolkit.actions['audit_workflow'].command_func()
            if "[!]" in work_res or "[?]" in work_res:
                output.append("  ⚠️  WORKFLOW ALERT: Plan/Code synchronization issues detected.")
                warnings.append("Workflow sync issues")
            else:
                output.append("  ✓ Workflow: Marks & Todos in sync.")

            # 5. Active Session Stats
            output.append("\n[CURRENT SESSION]")
            output.append(f"  Session ID: {toolkit.session_id}")
            output.append(f"  Artifacts: {len(toolkit.session.artifacts)}")
            output.append(f"  Active Processes: {len([a for a in toolkit.session.artifacts.values() if a.artifact_type == ArtifactType.PROCESS])}")

            # 6. TODO SYNCHRONIZATION (AUTO-RUN - P1-TodoSync)
            output.append("\n[TODO SYNC]")
            conflicts = []
            try:
                sync_engine = UnifiedTodoSync(Path(__file__).parents[3])
                unified = sync_engine.reconcile()

                claude_count = sum(1 for e in unified.values() if 'claude' in e['sources'])
                os_count = sum(1 for e in unified.values() if 'os_toolkit' in e['sources'])
                mark_count = sum(1 for e in unified.values() if 'mark' in e['sources'])
                conflicts = [e for e in unified.values() if e['conflicts']]

                # AUTO-SYNC: Actually run the sync, not just check status
                sync_engine.sync_to_os_toolkit(unified)

                output.append(f"  🔄 Synced: {len(unified)} tasks (Claude: {claude_count}, Os: {os_count}, Marks: {mark_count})")

                if conflicts:
                    output.append(f"  ⚠️  {len(conflicts)} tasks have status conflicts:")
                    for c in conflicts[:3]:  # Show first 3 conflicts
                        output.append(f"     - {c.get('subject', c.get('title', ''))[:50]}")
                    if len(conflicts) > 3:
                        output.append(f"     ... and {len(conflicts)-3} more")
                else:
                    output.append(f"  ✅ All todos in sync across 3 sources")
            except Exception as e:
                output.append(f"  ⚠️  Todo sync error: {e}")

            # 7. FILE CHANGES & BACKUPS (Temporal context + Linux logs + Filesync integration)
            output.append("\n[RECENT FILE CHANGES & WORKFLOW VALIDATION]")
            recent_files = []
            workflow_violations = []

            try:
                # ENHANCED DETECTION: 24-hour window + git/system logs for change count
                # Anchor to project Data/ dir so we scan all tabs, not just action_panel_tab
                cwd = Path(__file__).resolve().parents[2]
                recent_threshold = datetime.now() - timedelta(hours=24)  # 24h coverage!
                yesterday_threshold = datetime.now() - timedelta(hours=48)

                # Track files modified in last 24h
                for py_file in cwd.glob("**/*.py"):
                    if '__pycache__' in str(py_file):
                        continue
                    if not py_file.is_file():
                        continue

                    mtime = datetime.fromtimestamp(py_file.stat().st_mtime)
                    if mtime > recent_threshold:
                        change_count = 1  # mtime-based detection only (no git repo)

                        # Get backup info from archive
                        archive_dir = Path(__file__).resolve().parents[3] / "archive"
                        backup_count = 0
                        latest_backup = None
                        if archive_dir.exists():
                            file_backups = sorted(archive_dir.glob(f"{py_file.stem}*.bak"))
                            backup_count = len(file_backups)
                            if file_backups:
                                latest_backup = file_backups[-1]

                        recent_files.append({
                            'path': str(py_file),
                            'name': py_file.name,
                            'size': py_file.stat().st_size,
                            'modified': mtime,
                            'lines': 0,  # skip read_text for perf; size is sufficient
                            'change_count': change_count,
                            'backup_count': backup_count,
                            'latest_backup': str(latest_backup) if latest_backup else None
                        })

                if recent_files:
                    output.append(f"  📝 {len(recent_files)} files modified in last 24h:")
                    for rf in sorted(recent_files, key=lambda x: x['modified'], reverse=True)[:5]:
                        rel_path = rf['name']
                        backup_status = f"📦 {rf['backup_count']} backups" if rf['backup_count'] > 0 else "⚠️ No backups"
                        output.append(f"     - {rel_path} ({rf['size']} bytes, {rf['lines']} lines)")
                        output.append(f"       🔄 {rf['change_count']} changes | {backup_status}")
                        if rf['latest_backup']:
                            backup_time = datetime.fromtimestamp(Path(rf['latest_backup']).stat().st_mtime)
                            time_ago = (datetime.now() - backup_time).total_seconds() / 3600
                            output.append(f"       📂 Latest backup: {time_ago:.1f}h ago")

                        # WORKFLOW VALIDATION (stat-only, skip read_text for perf)
                        _rf_path = Path(rf['path'])
                        has_debug = any(_rf_path.parent.glob(f"__pycache__/{_rf_path.stem}.*.pyc"))

                        violations = []
                        if not has_debug:
                            violations.append("Not compiled")
                            workflow_violations.append({
                                'file': rf['name'],
                                'issue': 'not_debugged',
                                'suggestion': f"Run py_compile on {rf['name']}"
                            })
                        if rf['backup_count'] == 0 and rf['change_count'] > 5:
                            violations.append("Many changes, no backups!")
                            workflow_violations.append({
                                'file': rf['name'],
                                'issue': 'no_backup',
                                'suggestion': f"Backup {rf['name']} before continuing"
                            })

                        if violations:
                            output.append(f"       ⚠️  {', '.join(violations)}")
                else:
                    output.append(f"  ✓ No recent file changes detected")

                # YESTERDAY'S CHANGES (historical context)
                yesterday_files = []
                for py_file in cwd.glob("**/*.py"):
                    if '__pycache__' in str(py_file):
                        continue
                    mtime = datetime.fromtimestamp(py_file.stat().st_mtime)
                    if yesterday_threshold < mtime <= recent_threshold:
                        yesterday_files.append(py_file.name)

                if yesterday_files:
                    output.append(f"\n  📅 Yesterday: {len(yesterday_files)} files modified")
                    output.append(f"     {', '.join(yesterday_files[:5])}")

            except Exception as e:
                output.append(f"  ⚠️  File detection error: {e}")

            # 7b. MANIFEST REGENERATION TRIGGER
            # If enriched_changes have recent changes, regenerate py_manifest for Code Profile updates
            output.append("\n[MANIFEST SYNC]")
            try:
                import subprocess as _subprocess
                _data_root = Path(__file__).resolve().parents[2]
                manifest_path = _data_root / "backup" / "version_manifest.json"
                if manifest_path.exists():
                    with open(manifest_path) as f:
                        v_manifest = json.load(f)

                    enriched = v_manifest.get("enriched_changes", {})
                    if enriched:
                        # Count recent changes (last 24h)
                        recent_count = sum(
                            1 for e in enriched.values()
                            if datetime.fromisoformat(e.get('timestamp', '2020-01-01')) > datetime.now() - timedelta(hours=24)
                        )

                        # Only regenerate if py_manifest is older than the most recent enriched_change
                        _py_manifest_p = _data_root / "pymanifest" / "py_manifest.json"
                        _py_manifest_mtime = _py_manifest_p.stat().st_mtime if _py_manifest_p.exists() else 0.0
                        _most_recent_ts = max(
                            (datetime.fromisoformat(e.get('timestamp', '2020-01-01')).timestamp()
                             for e in enriched.values()),
                            default=0.0
                        )
                        _needs_regen = recent_count >= 10 and _most_recent_ts > _py_manifest_mtime

                        if _needs_regen:
                            output.append(f"  ✓ Detected {recent_count} recent changes in enriched_changes (py_manifest stale)")

                            # Trigger py_manifest regeneration with visible output
                            manifest_gen = _data_root / "pymanifest" / "py_manifest_augmented.py"
                            if manifest_gen.exists():
                                output.append(f"  ⚙️  Regenerating py_manifest...")
                                try:
                                    # Run synchronously with captured output for visibility
                                    result = _subprocess.run(
                                        [sys.executable, str(manifest_gen), "analyze",
                                         str(_data_root),
                                         "--manifest", str(_data_root / "pymanifest" / "py_manifest.json")],
                                        cwd=str(_data_root),
                                        capture_output=True,
                                        text=True,
                                        timeout=120
                                    )

                                    if result.returncode == 0:
                                        output.append(f"  ✓ py_manifest regeneration completed")
                                        # Show last line of output (usually summary)
                                        if result.stdout:
                                            last_lines = result.stdout.strip().split('\n')[-3:]
                                            for line in last_lines:
                                                if line.strip():
                                                    output.append(f"    {line}")
                                    else:
                                        output.append(f"  ⚠️  py_manifest regeneration failed (exit code {result.returncode})")
                                        if result.stderr:
                                            errors = result.stderr.strip().split('\n')[-5:]
                                            for error in errors:
                                                if error.strip():
                                                    output.append(f"    ERROR: {error}")
                                except _subprocess.TimeoutExpired:
                                    output.append(f"  ⚠️  py_manifest regeneration timed out (>120s)")
                                except Exception as gen_err:
                                    output.append(f"  ⚠️  Could not run regeneration: {gen_err}")
                            else:
                                output.append(f"  → py_manifest_augmented.py not found at {manifest_gen}")
                        else:
                            if recent_count >= 10:
                                output.append(f"  ✓ py_manifest is fresh ({recent_count} changes, manifest up-to-date)")
                            else:
                                output.append(f"  ✓ Manifests are current ({recent_count} changes, threshold=10)")
                    else:
                        output.append(f"  ○ No enriched_changes tracked yet")
                else:
                    output.append(f"  ○ version_manifest not found")
            except Exception as e:
                output.append(f"  ⚠️  Manifest sync error: {e}")

            # 7c. CHANGE DELTA — enriched_changes from logger_util/live watcher
            output.append("\n[CHANGE DELTA]")
            try:
                _data_root_d = Path(__file__).resolve().parents[2]
                _vm_path = _data_root_d / "backup" / "version_manifest.json"
                if _vm_path.exists():
                    _vm = json.loads(_vm_path.read_text(encoding="utf-8"))
                    _enriched = _vm.get("enriched_changes", {})
                    _recent_threshold = datetime.now() - timedelta(hours=24)
                    _recent = sorted(
                        [(eid, e) for eid, e in _enriched.items()
                         if datetime.fromisoformat(e.get("timestamp", "2020-01-01")) > _recent_threshold],
                        key=lambda x: x[1].get("timestamp", ""), reverse=True
                    )
                    if _recent:
                        _fails = [e for _, e in _recent if e.get("test_status") == "FAIL"]
                        _unlinked = [e for _, e in _recent if not e.get("task_ids")]
                        output.append(f"  📊 {len(_recent)} changes (last 24h) | "
                                      f"{'❗ ' + str(len(_fails)) + ' FAIL' if _fails else '✓ all PASS'} | "
                                      f"{len(_unlinked)} unlinked")
                        for eid, e in _recent[:8]:
                            _file = (e.get("file") or "").split("/")[-1]
                            _ts = (e.get("timestamp") or "")[:16].replace("T", " ")
                            _risk = e.get("risk_level", "?")
                            _verb = e.get("verb", "?")
                            _tids = ", ".join(e.get("task_ids") or []) or "—"
                            _tst = e.get("test_status", "")
                            _tst_icon = "✓" if _tst == "PASS" else "❗" if _tst == "FAIL" else "○"
                            output.append(f"  {_tst_icon} [{_risk}] {_ts} {_file} ({_verb}) → {eid} tasks:{_tids}")
                            if e.get("test_errors"):
                                for err in (e.get("test_errors") or [])[:2]:
                                    output.append(f"      ⚠ {err}")
                        # Auto-index changed files into session artifacts so query works
                        _data_root_d2 = Path(__file__).resolve().parents[2]
                        _indexed = 0
                        _already = 0
                        _unique_files = list({e.get("file", "") for _, e in _recent if e.get("file")})
                        for _rel_path in _unique_files:
                            try:
                                # Resolve relative path (stored as Data/tabs/... or absolute)
                                _fp = Path(_rel_path)
                                if not _fp.is_absolute():
                                    _fp = _data_root_d2.parent / _rel_path
                                if not _fp.exists():
                                    continue
                                # Check if already in session artifacts by path
                                _already_indexed = any(
                                    str(_fp) in str(a.get("properties", {}).get("path", ""))
                                    for a in toolkit.session.artifacts.values()
                                    if isinstance(a, dict)
                                ) if hasattr(toolkit.session, "artifacts") else False
                                if _already_indexed:
                                    _already += 1
                                else:
                                    toolkit.analyze_file(str(_fp))
                                    _indexed += 1
                            except Exception:
                                pass
                        if _indexed > 0:
                            output.append(f"  🔍 Auto-indexed {_indexed} changed file(s) → query now available")
                        elif _already > 0:
                            output.append(f"  🔍 {_already} changed file(s) already in query index")

                        # ── Write unlinked MEDIUM/HIGH/CRITICAL events to checklist aoe_inbox ──
                        # This surfaces attribution gaps in the checklist tab even when gui_NEW
                        # wasn't live-watching (e.g. changes made via Claude Code CLI sessions).
                        _cl_path_d = Path(__file__).resolve().parents[2] / "plans" / "checklist.json"
                        if _cl_path_d.exists() and _unlinked:
                            try:
                                _cl_d = json.loads(_cl_path_d.read_text(encoding="utf-8"))
                                _inbox_d = _cl_d.setdefault("aoe_inbox", [])
                                _existing_eids_d = {e.get("event_id") for e in _inbox_d}
                                _added_d = 0
                                for _eid_d, _ec_d in [(eid, e) for eid, e in _recent if not e.get("task_ids")]:
                                    if _eid_d in _existing_eids_d:
                                        continue
                                    _risk_d = _ec_d.get("risk_level", "LOW")
                                    if _risk_d not in ("MEDIUM", "HIGH", "CRITICAL"):
                                        continue
                                    _fname_d = Path(_ec_d.get("file", "")).name
                                    _inbox_d.append({
                                        "event_id": _eid_d,
                                        "task_id": "",
                                        "file": _ec_d.get("file", ""),
                                        "risk_level": _risk_d,
                                        "verb": _ec_d.get("verb", ""),
                                        "timestamp": _ec_d.get("timestamp", ""),
                                        "message": f"[ATTRIBUTION_GAP] {_fname_d} — unlinked {_risk_d} change",
                                        "status": "ATTRIBUTION_GAP",
                                    })
                                    _existing_eids_d.add(_eid_d)
                                    _added_d += 1
                                if _added_d:
                                    _cl_path_d.write_text(json.dumps(_cl_d, indent=2), encoding="utf-8")
                                    output.append(f"  → {_added_d} gap(s) written to checklist aoe_inbox")
                            except Exception:
                                pass
                    else:
                        output.append(f"  ○ No recent changes (last 24h)")
                else:
                    output.append(f"  ○ version_manifest not found")
            except Exception as _de:
                output.append(f"  ⚠️  Delta error: {_de}")

            # 7d-1. AUTO-CATALOG: Add changed files not in onboarder catalog
            try:
                _menu_path_ac = Path(__file__).resolve().parent / "babel_data" / "inventory" / "consolidated_menu.json"
                if _menu_path_ac.exists() and '_unique_files' in dir():
                    _menu_ac = json.loads(_menu_path_ac.read_text(encoding="utf-8"))
                    _cataloged_names = {(t.get('name') or t.get('display_name') or '').lower()
                                        for t in _menu_ac.get('tools', [])}
                    _cataloged_cmds = {(t.get('command') or '').lower()
                                       for t in _menu_ac.get('tools', [])}
                    _uncataloged = []
                    for _rel_path in _unique_files:
                        _fname = Path(_rel_path).stem.lower()
                        _fname_full = Path(_rel_path).name.lower()
                        if (_fname not in _cataloged_names and _fname_full not in _cataloged_cmds
                                and _fname.replace('_', ' ') not in _cataloged_names):
                            _uncataloged.append(_rel_path)

                    if _uncataloged:
                        output.append(f"\n[AUTO-CATALOG]")
                        output.append(f"  📋 {len(_uncataloged)} changed file(s) not in onboarder catalog:")
                        _new_tools = []
                        for _rel in _uncataloged[:20]:
                            _fp = Path(_rel)
                            _tool_entry = {
                                "id": f"tool_auto_{_fp.stem}_{datetime.now().strftime('%H%M%S')}",
                                "tool_id": f"auto_{_fp.stem}",
                                "display_name": _fp.stem.replace('_', ' ').title(),
                                "category": "auto_cataloged",
                                "command": _fp.name,
                                "arguments": [],
                                "shortcut": "",
                                "icon": "",
                                "enabled": True,
                                "order": 999,
                                "source_path": str(_rel),
                                "cataloged_at": datetime.now().isoformat(),
                                "cataloged_by": "latest_auto_catalog"
                            }
                            _new_tools.append(_tool_entry)
                            output.append(f"  + {_fp.name} → auto_{_fp.stem}")

                        _menu_ac['tools'].extend(_new_tools)
                        _menu_path_ac.write_text(json.dumps(_menu_ac, indent=2), encoding="utf-8")
                        output.append(f"  ✓ Added {len(_new_tools)} tool(s) to consolidated_menu.json")
                    else:
                        output.append(f"\n[AUTO-CATALOG]\n  ✓ All changed files already cataloged")
            except Exception as _ace:
                output.append(f"\n[AUTO-CATALOG]\n  ⚠️  Auto-catalog error: {_ace}")

            # 7d-2. HISTORY CATALOG & TEMPORAL INFERENCE (cached)
            output.append("\n[HISTORY CATALOG]")
            try:
                _history_dir = Path(__file__).resolve().parents[2] / "backup" / "history"
                if _history_dir.exists():
                    _history_profiles = {}
                    _cache_path = _history_dir.parent / "history_catalog_cache.json"
                    _history_mtime = _history_dir.stat().st_mtime
                    _cache_valid = False

                    if _cache_path.exists():
                        try:
                            _cache = json.loads(_cache_path.read_text(encoding="utf-8"))
                            if _cache.get("dir_mtime") == _history_mtime:
                                _history_profiles = _cache["profiles"]
                                _cache_valid = True
                                output.append(f"  ⚡ Using cached history catalog")
                        except Exception:
                            pass

                    if not _cache_valid:
                        for _hdir in _history_dir.iterdir():
                            if not _hdir.is_dir():
                                continue
                            _dir_name = _hdir.name
                            _backups = sorted([f for f in _hdir.iterdir() if f.is_file()])
                            _backup_count = len(_backups)
                            if _backup_count == 0:
                                continue

                            _timestamps = []
                            for _bk in _backups:
                                _ts_str = _bk.stem
                                try:
                                    _ts = datetime.strptime(_ts_str, "%Y%m%d_%H%M%S")
                                    _timestamps.append(_ts)
                                except ValueError:
                                    pass

                            if _timestamps:
                                _first = min(_timestamps)
                                _last = max(_timestamps)
                                _span_days = (_last - _first).days
                                _history_profiles[_dir_name] = {
                                    "backup_count": _backup_count,
                                    "first_seen": _first.isoformat(),
                                    "last_seen": _last.isoformat(),
                                    "span_days": _span_days,
                                    "avg_interval_hours": round((_last - _first).total_seconds() / 3600 / max(_backup_count - 1, 1), 1),
                                    "activity_score": round(_backup_count / max(_span_days, 1), 2),
                                }

                        # Write cache
                        try:
                            _cache_path.write_text(json.dumps({
                                "dir_mtime": _history_mtime,
                                "profiles": _history_profiles,
                                "generated": datetime.now().isoformat()
                            }, indent=2), encoding="utf-8")
                        except Exception:
                            pass

                    _sorted_hp = sorted(_history_profiles.items(), key=lambda x: -x[1]["backup_count"])
                    _total_files = len(_history_profiles)
                    _total_backups = sum(p["backup_count"] for p in _history_profiles.values())
                    output.append(f"  📂 {_total_files} tracked files, {_total_backups} total backups")

                    for _name, _prof in _sorted_hp[:8]:
                        _icon = "🔥" if _prof["backup_count"] > 20 else "📄"
                        output.append(f"  {_icon} {_name[:55]}... "
                                     f"({_prof['backup_count']} backups, {_prof['span_days']}d, "
                                     f"score:{_prof['activity_score']})")

                    # Write temporal manifest for planner consumption
                    _timeline_dir = Path(__file__).resolve().parent / "babel_data" / "timeline" / "manifests"
                    _timeline_dir.mkdir(parents=True, exist_ok=True)
                    _timeline_manifest = {
                        "generated": datetime.now().isoformat(),
                        "source": "history_catalog",
                        "total_files": _total_files,
                        "total_backups": _total_backups,
                        "profiles": {n: p for n, p in _sorted_hp}
                    }
                    _tm_path = _timeline_dir / "history_temporal_manifest.json"
                    if not _cache_valid:
                        _tm_path.write_text(json.dumps(_timeline_manifest, indent=2), encoding="utf-8")
                        output.append(f"  ✓ Wrote temporal manifest → {_tm_path.name}")
                    else:
                        output.append(f"  ⚡ Temporal manifest current (cache hit)")

                    # Cross-reference: history files not in enriched_changes
                    try:
                        _ec_files_set = set()
                        if '_enriched' in dir() or 'enriched' in dir():
                            _ec_ref = enriched if 'enriched' in dir() else {}
                            _ec_files_set = {e.get("file", "").split("/")[-1].replace(".py", "").lower()
                                            for e in _ec_ref.values() if e.get("file")}
                        _history_only_count = sum(1 for n in _history_profiles
                                                  if n.split("_")[-1].replace(".py", "").lower() not in _ec_files_set)
                        if _ec_files_set and _history_only_count > 0:
                            output.append(f"  📊 {_history_only_count} files in history with no enriched_change event")
                    except Exception:
                        pass
                else:
                    output.append(f"  ○ History directory not found")
            except Exception as _he:
                output.append(f"  ⚠️  History catalog error: {_he}")

            # 7d. STALENESS WARNINGS (Big Bang Layer 2B)
            try:
                _stale_tasks = []
                _ls_stale_path = Path(__file__).resolve().parents[2] / "plans" / "Refs" / "latest_sync.json"
                _todos_stale_path = Path(__file__).resolve().parents[2] / "plans" / "todos.json"
                _stale_sources = {}
                # Load from latest_sync
                if _ls_stale_path.exists():
                    _ls_stale = json.loads(_ls_stale_path.read_text(encoding="utf-8"))
                    _stale_sources = _ls_stale.get("tasks", {})
                # Merge from todos.json (handles both list and dict formats)
                if _todos_stale_path.exists():
                    _todos_stale = json.loads(_todos_stale_path.read_text(encoding="utf-8"))
                    if isinstance(_todos_stale, dict):
                        for _phase, _tblock in _todos_stale.items():
                            if isinstance(_tblock, dict):
                                for _tid, _t in _tblock.items():
                                    if isinstance(_t, dict) and _t.get("status") and _tid not in _stale_sources:
                                        _stale_sources[_tid] = _t
                    elif isinstance(_todos_stale, list):
                        for _t in _todos_stale:
                            if isinstance(_t, dict) and _t.get("id") and _t.get("status"):
                                _tid = _t["id"]
                                if _tid not in _stale_sources:
                                    _stale_sources[_tid] = _t

                _now_stale = datetime.now()
                for _tid, _t in _stale_sources.items():
                    _updated = _t.get("updated_at") or _t.get("created_at", "")
                    _status = (_t.get("status") or "").upper()
                    if _status in ("PENDING", "IN_PROGRESS", "READY", "OPEN") and _updated:
                        try:
                            _updated_dt = datetime.fromisoformat(_updated)
                            _days = (_now_stale - _updated_dt).days
                            if _days >= 3:
                                _stale_tasks.append((_tid, _t.get("title", ""), _days, _status))
                        except Exception:
                            pass

                if _stale_tasks:
                    output.append(f"\n[STALENESS WARNINGS]")
                    try:
                        _total_ec = len(_vm.get("enriched_changes", {}))
                    except Exception:
                        _total_ec = 0
                    output.append(f"  ⚠ {len(_stale_tasks)} tasks unmarked for 3+ days | {_total_ec} total changes")
                    for _tid, _title, _days, _status in sorted(_stale_tasks, key=lambda x: -x[2])[:10]:
                        output.append(f"  ⏰ [{_days}d] {_tid}: {_title[:50]} ({_status})")
            except Exception as _se:
                output.append(f"\n[STALENESS WARNINGS]\n  ⚠️  Staleness check error: {_se}")

            # 7e. PLAN COVERAGE CROSS-CHECK (Big Bang Layer 2C)
            try:
                _plans_dir_cc = Path(__file__).resolve().parents[2] / "plans"
                _tasks_with_plans = [(tid, t) for tid, t in _stale_sources.items()
                                     if isinstance(t, dict) and t.get("plan_doc")]
                if _tasks_with_plans:
                    output.append(f"\n[PLAN COVERAGE]")
                    for _tid, _t in _tasks_with_plans[:10]:
                        _pd = _t["plan_doc"]
                        _pd_path = _plans_dir_cc / _pd.replace("plans/", "")
                        if not _pd_path.exists():
                            _pd_path = _plans_dir_cc.parent / _pd
                        _exists = _pd_path.exists()
                        _icon = "✓" if _exists else "✗"
                        output.append(f"  {_icon} {_tid} → {_pd}")
            except Exception as _pe:
                pass

            # 7f. TASK SUGGESTIONS FROM ATTRIBUTION REGEX
            try:
                _suggestions = []
                # Use _enriched (from 7c) and _stale_sources (from 7d) if available
                _sg_enriched = locals().get("_enriched", {})
                _sg_tasks = locals().get("_stale_sources", {})
                _sg_hprofiles = locals().get("_history_profiles", {})

                # 7f-a: Unlinked events → suggest task linking by wherein match
                for _eid, _ec in _sg_enriched.items():
                    if not _ec.get("task_ids"):
                        _fname = (_ec.get("file") or "").split("/")[-1]
                        if not _fname:
                            continue
                        for _tid, _tv in _sg_tasks.items():
                            if not isinstance(_tv, dict):
                                continue
                            _wherein = _tv.get("wherein", "")
                            if _fname and _fname in _wherein:
                                _conf = 0.85 if _fname == _wherein.split("/")[-1] else 0.60
                                _suggestions.append({
                                    "type": "link_event",
                                    "event_id": _eid,
                                    "task_id": _tv.get("id", _tid),
                                    "file": _fname,
                                    "confidence": _conf,
                                    "reason": f"{_fname} matches wherein:{_wherein.split('/')[-1]}"
                                })

                # 7f-b: High-activity files with no task → suggest creating one
                for _hname, _hprof in list(_sg_hprofiles.items())[:30]:
                    if _hprof.get("activity_score", 0) > 3.0:
                        _has_task = any(
                            _hname in str(_tv.get("wherein", ""))
                            for _tv in _sg_tasks.values() if isinstance(_tv, dict)
                        )
                        if not _has_task:
                            _suggestions.append({
                                "type": "create_task",
                                "file": _hname,
                                "activity_score": _hprof["activity_score"],
                                "backup_count": _hprof["backup_count"],
                                "confidence": min(0.4 + _hprof["activity_score"] * 0.1, 0.85),
                                "reason": f"High activity ({_hprof['backup_count']} backups, score:{_hprof['activity_score']}) no task"
                            })

                # 7f-c: Display suggestions sorted by confidence
                if _suggestions:
                    _suggestions.sort(key=lambda s: -s["confidence"])
                    output.append(f"\n[TASK SUGGESTIONS]")
                    for _s in _suggestions[:10]:
                        _icon = "🔗" if _s["type"] == "link_event" else "➕"
                        output.append(f"  {_icon} [{_s['confidence']:.0%}] {_s['reason']}")
                        if _s["type"] == "link_event":
                            output.append(f"     → Link {_s['event_id']} to {_s['task_id']}")
                    output.append(f"  📊 {len(_suggestions)} total suggestions")

                    # Save suggestions for planner consumption
                    _sg_out_dir = Path(__file__).resolve().parent / "babel_data" / "profile"
                    _sg_out_dir.mkdir(parents=True, exist_ok=True)
                    _sg_out = {
                        "generated": datetime.now().isoformat(),
                        "source": "latest_attribution_regex",
                        "count": len(_suggestions),
                        "suggestions": _suggestions[:25]
                    }
                    (_sg_out_dir / "suggested_actions.json").write_text(
                        json.dumps(_sg_out, indent=2), encoding="utf-8"
                    )
                else:
                    output.append(f"\n[TASK SUGGESTIONS]\n  ✓ No unlinked events or high-activity gaps")
            except Exception as _sge:
                output.append(f"\n[TASK SUGGESTIONS]\n  ⚠️  Suggestion engine error: {_sge}")

            # 7g. MORPH EXPLAIN — compact narrative (only when recent changes detected)
            if locals().get('_recent'):
                output.append("\n[MORPH EXPLAIN]")
                try:
                    _me_scripts = Path(__file__).parent / "regex_project" / "activities" / "tools" / "scripts"
                    if str(_me_scripts) not in sys.path:
                        sys.path.insert(0, str(_me_scripts))
                    from temporal_narrative_engine import TemporalNarrativeEngine as _TNE
                    _me_root = Path(__file__).resolve().parents[3]  # Trainer root (not Data/)
                    _me_nar = _TNE(_me_root).explain('last 24h')
                    _me_phase = _me_nar.get('phase_summary', 'unknown')
                    _me_domain = _me_nar.get('dominant_domain', 'unknown')
                    _me_dconf = _me_nar.get('domain_confidence', 0.0)
                    _me_files = _me_nar.get('files_touched', [])
                    _me_tasks = _me_nar.get('tasks_active', [])
                    _me_text = _me_nar.get('narrative_text', '')
                    output.append(f"  Phase:  {_me_phase}")
                    output.append(f"  Domain: {_me_domain} ({_me_dconf:.0%} confidence)")
                    output.append(f"  Files:  {len(_me_files)} touched | Tasks: {len(_me_tasks)} active")
                    if _me_text:
                        _me_sentences = _me_text.split('. ')
                        _me_snippet = '. '.join(_me_sentences[:2])
                        if len(_me_snippet) > 200:
                            _me_snippet = _me_snippet[:197] + '...'
                        output.append(f"  Narrative: {_me_snippet}")
                    for _me_t in _me_tasks[:3]:
                        _me_tid = _me_t.get('id', '')
                        _me_ttl = _me_t.get('title', '')[:60]
                        _me_tst = _me_t.get('status', '')
                        output.append(f"  ○ [{_me_tid}] {_me_ttl} ({_me_tst})")
                except Exception as _me_err:
                    output.append(f"  ⚠️  Narrative engine error: {_me_err}")

            # 8. PLAN CONSOLIDATION & TEMPLATE VALIDATION
            output.append("\n[PLAN CONSOLIDATION]")
            try:
                # Import PlanConsolidator via importlib — avoids sys.path mutation
                import importlib.util, sys as _sys
                _mod_name = "plan_consolidator"
                if _mod_name not in _sys.modules:
                    _pc_path = Path(__file__).parent / "babel_data" / "inventory" / "core" / "plan_consolidator.py"
                    _spec = importlib.util.spec_from_file_location(_mod_name, _pc_path)
                    _mod = importlib.util.module_from_spec(_spec)
                    _sys.modules[_mod_name] = _mod
                    _spec.loader.exec_module(_mod)
                PlanConsolidator = _sys.modules[_mod_name].PlanConsolidator

                # Discover scattered plans
                consolidator = PlanConsolidator(toolkit.base_dir.parent.parent)
                scattered = consolidator.discover_scattered_plans()

                if scattered:
                    output.append(f"  ⚠️  Found {len(scattered)} scattered .md files:")
                    for plan in scattered[:5]:  # Show first 5
                        output.append(f"     - {plan['location']}")

                    if len(scattered) > 5:
                        output.append(f"     ... and {len(scattered) - 5} more")

                    # Check template structure for each scattered plan
                    missing_structure = []
                    for plan_info in scattered:
                        plan_path = Path(plan_info['path'])

                        # Read and check for template sections
                        try:
                            with open(plan_path, encoding='utf-8', errors='ignore') as f:
                                content = f.read()

                            # Expected template sections from Project_Template_1.md
                            required_sections = [
                                "</High_Level>:",
                                "</Mid_Level>:",
                                "</Diffs>:",
                                "</Current_Tasks>:"
                            ]

                            missing = [sec for sec in required_sections if sec not in content]

                            if missing:
                                missing_structure.append({
                                    'file': plan_path.name,
                                    'missing': missing
                                })
                                workflow_violations.append({
                                    'file': plan_path.name,
                                    'issue': 'missing_template_structure',
                                    'suggestion': f"Reformat {plan_path.name} to match Project_Template_1.md"
                                })
                        except Exception as e:
                            pass

                    if missing_structure:
                        output.append(f"\n  📋 {len(missing_structure)} plans need template structure:")
                        for item in missing_structure[:3]:
                            output.append(f"     - {item['file']}: missing {len(item['missing'])} sections")
                            warnings.append(f"Missing template: {item['file']}")

                    output.append(f"\n  💡 Recommendation: Run 'python3 Os_Toolkit.py actions --run consolidate_plans'")
                else:
                    output.append(f"  ✓ No scattered plans detected")

            except Exception as e:
                output.append(f"  ⚠️  Plan consolidation check error: {e}")

            # #[Mark:SWEEP2-IN_PROGRESS] Suggestive actions for latest output
            # Generate suggestions based on ACTUAL state + workflow violations (always, not just zenity mode)
            unmarked_events = []  # Will implement with SystemLogAnalyzer

            # Add workflow violation warnings
            for violation in workflow_violations:
                if violation['issue'] == 'missing_mark':
                    warnings.append(f"Missing mark: {violation['file']}")
                elif violation['issue'] == 'not_debugged':
                    warnings.append(f"Not debugged: {violation['file']}")

            # Add backup suggestion if no recent backups
            recent_backups = sum(rf.get('backup_count', 0) for rf in recent_files)
            if recent_backups == 0:
                warnings.append("No backups in last 24h")

            # Generate context-aware suggestions
            suggestions = SuggestiveGrepEngine.suggest_for_latest(warnings, conflicts, unmarked_events)

            # Add workflow-specific suggestions from violations
            for violation in workflow_violations[:3]:  # Top 3 violations
                if violation['issue'] == 'not_debugged':
                    suggestions.insert(0, {
                        'id': f"debug_{violation['file']}",
                        'label': f"🐛 Run py_compile on {violation['file']}",
                        'command': f"python3 -m py_compile {violation['file']}",
                        'selected': len([s for s in suggestions if s.get('selected')]) == 0
                    })
                elif violation['issue'] == 'missing_mark':
                    suggestions.insert(0, {
                        'id': f"mark_{violation['file']}",
                        'label': f"📝 Add #[Mark:] to {violation['file']}",
                        'command': f"echo '# TODO: Add mark' && nano {violation['file']}",
                        'selected': False
                    })
                elif violation['issue'] == 'no_backup':
                    suggestions.insert(0, {
                        'id': f"backup_{violation['file']}",
                        'label': f"📦 Backup {violation['file']} NOW (many changes!)",
                        'command': f"cp {violation['file']} archive/{violation['file']}.$(date +%Y%m%d_%H%M%S).bak",
                        'selected': len([s for s in suggestions if s.get('selected')]) == 0
                    })

            # ADD PLAN CONSOLIDATION SUGGESTIONS (if scattered plans detected)
            try:
                if scattered and len(scattered) > 0:
                    # Add consolidate_plans suggestion
                    suggestions.insert(0, {
                        'id': 'consolidate_plans',
                        'label': f"📋 Consolidate {len(scattered)} scattered plan files",
                        'command': 'python3 Os_Toolkit.py actions --run consolidate_plans',
                        'selected': len(scattered) > 10  # Auto-select if many plans
                    })

                    # Add template reformat suggestion if many plans missing structure
                    if missing_structure and len(missing_structure) > 5:
                        suggestions.insert(1, {
                            'id': 'reformat_templates',
                            'label': f"📝 Reformat {len(missing_structure)} plans to match Project_Template_1.md",
                            'command': 'echo "Manual template reformatting required" && python3 Os_Toolkit.py plan --help',
                            'selected': False
                        })
            except NameError:
                # scattered variable not defined (plan consolidation check failed)
                pass

            # CALCULATE CONFIDENCE SCORES with Filesync integration
            action_context = {
                'scattered_plan_count': len(scattered) if 'scattered' in locals() else 0,
                'security_anomalies': any('SECURITY' in w or 'Security' in w for w in warnings),
                'todo_conflicts': len(conflicts),
                'recent_backups': recent_backups,
                'workflow_violations': len(workflow_violations)
            }

            confidence_scores = {}
            for suggestion in suggestions:
                action_id = suggestion.get('id', '')
                confidence_scores[action_id] = toolkit._get_filesync_confidence(action_id, action_context)

            # SAVE SUGGESTIONS TO PERSISTENT FILE (always, not just in zenity mode)
            if suggestions:
                toolkit._save_suggested_actions(suggestions, confidence_scores)
                output.append(f"\n💾 Saved {len(suggestions)} suggested actions")
                high_conf_count = sum(1 for aid, conf in confidence_scores.items() if conf >= 0.7)
                output.append(f"   - High confidence (≥0.7): {high_conf_count}")
                output.append(f"   - View with: python3 Os_Toolkit.py latest --action-list")
                output.append(f"   - Batch run:  python3 Os_Toolkit.py latest --action-batch\n")

            #TODO: [P0-WORKFLOW] Trigger Filesync → onboarder.py catalog --measurement for unified manifest
            #[Event:SEQUENTIAL_WORKFLOW_POINT] Integration point for 3-system workflow

            # ZENITY INTERACTIVE MODE (if enabled)
            if args.zenity:

                if suggestions:
                    selected = display_output_with_actions(
                        "\n".join(output),
                        suggestions,
                        title="Babel Center - Latest State",
                        use_zenity=True
                    )

                    if selected:
                        action = next(a for a in suggestions if a['id'] == selected)
                        print(f"\n[+] Executing: {action['command']}")
                        result = subprocess.run(action['command'], shell=True, capture_output=True, text=True)
                        output_text = f"[COMMAND]\n{action['command']}\n\n[OUTPUT]\n{result.stdout}\n{result.stderr}"
                        display_output(output_text, title=f"Result: {action['label']}", use_zenity=True)

                        # RE-TRIGGER LOOP: Ask if user wants to run latest again to see updated state
                        if zenity_question(
                            "Action complete! Run latest again to see updated state and new suggestions?",
                            title="Re-trigger Latest?",
                            ok_label="Yes, refresh",
                            cancel_label="No, done"
                        ):
                            # Recursive call to latest with same args
                            print(f"\n[+] Re-triggering latest...")
                            main()  # Re-run main() to execute latest again
                else:
                    display_output("\n".join(output), title="Babel Center - Latest State", use_zenity=args.zenity)
            else:
                display_output("\n".join(output), title="Babel Center - Latest State", use_zenity=args.zenity)
            
        elif args.command == 'actions':
            if args.list:
                if args.zenity:
                    # zenity --list --radiolist
                    cmd = ['zenity', '--list', '--radiolist', '--title', 'Babel Actions', 
                           '--column', 'Select', '--column', 'ID', '--column', 'Name', '--column', 'Impact',
                           '--width', '800', '--height', '400']
                    for aid, action in toolkit.actions.items():
                        cmd.extend(['FALSE', aid, action.name, action.impact])
                    
                    res = subprocess.run(cmd, capture_output=True, text=True)
                    if res.returncode == 0:
                        selected_id = res.stdout.strip()
                        if selected_id:
                            result = toolkit.execute_action(selected_id)
                            display_output(f"[+] Action {selected_id} Result:\n{result}", 
                                           title=f"Action: {selected_id}", use_zenity=args.zenity)
                else:
                    print(f"\nAVAILABLE ACTIONS ({len(toolkit.actions)}):")
                    print(f"{'ID':<15} {'Name':<25} {'Impact':<15} {'Description'}")
                    print("-" * 80)
                    for aid, action in toolkit.actions.items():
                        print(f"{aid:<15} {action.name:<25} {action.impact:<15} {action.description}")
            elif args.run:
                log_event("ACTION_START", f"Executing action: {args.run}", context={"action": args.run})
                result = toolkit.execute_action(args.run)
                log_event("ACTION_COMPLETE", f"Action {args.run} completed", context={"action": args.run})
                print(f"[+] Result: {result}")

        elif args.command == 'query':
            # NEW: Intelligent Entity Resolution
            query_string = args.query_string

            # 1. Attempt to resolve as a system package or onboarded tool
            profile_output = toolkit.profile_entity(query_string)

            # 2. ALWAYS perform artifact search (for files that use it, etc.)
            if not profile_output:
                # Build a structured "not indexed" block so the output is clearly labelled
                _prov_cat_p = Path(__file__).resolve().parent / "babel_data" / "inventory" / "provisions_catalog.json"
                _in_prov = _prov_cat_p.exists()
                _sources_checked = ", ".join(filter(None, [
                    "provisions_catalog" if _in_prov else None,
                    "pip/importlib.metadata",
                    "system_manifest",
                ]))
                profile_output = (
                    f"[PACKAGE: {query_string}]\n"
                    f"  Not found in: {_sources_checked}\n"
                    f"  Run 'os_toolkit analyze' to build full system package manifest\n"
                    f"  Related project context:"
                )
            result = toolkit.query(query_string, args.type, args.max_results)
            
            if args.output:
                with open(args.output, 'w') as f:
                    json.dump(result, f, indent=2)
                print(f"[+] Query results saved to: {args.output}")
            else:
                output = []
                # Show system package/tool profile first if found
                if profile_output:
                    output.append(profile_output)
                    output.append("")  # Blank line

                    # For package queries, show smart summary instead of 50 verbose profiles
                    # Count only actual file artifacts, not enrichment context entries
                    _file_artifact_count = sum(1 for r in result['results'] if 'artifact' in r)
                    if _file_artifact_count > 5:
                        output.append(f"\n[SUMMARY - Files Using This Package]")
                        output.append(f"  Total: {result['count']} files")

                        # Classify by risk
                        risk_items = []
                        normal_items = []
                        warnings = []

                        for item in result['results']:
                            if 'artifact' in item:
                                art = item['artifact']
                                props = art.get('properties', {})
                                ca = props.get('content_analysis', {})

                                # Check for risk indicators
                                is_risky = False
                                if ca.get('suspicious_patterns'):
                                    is_risky = True
                                    warnings.append(f"⚠️ {art['sixw1h']['what']}: Suspicious patterns detected")
                                if ca.get('ips') and any(ip.startswith('0.0.0.0') or ip.startswith('127.0.0.0') for ip in ca.get('ips', [])):
                                    is_risky = True
                                    warnings.append(f"⚠️ {art['sixw1h']['what']}: Risky IP addresses")

                                if is_risky:
                                    risk_items.append(item)
                                else:
                                    normal_items.append(item)

                        # Show warnings
                        if warnings:
                            output.append(f"\n  [WARNINGS]")
                            for warn in warnings[:5]:
                                output.append(f"    {warn}")

                        # Show risk items with full profiles
                        if risk_items:
                            output.append(f"\n  [HIGH PRIORITY - Full Profiles] ({len(risk_items)} items)")

                        # Show normal items as condensed list
                        if normal_items:
                            output.append(f"\n  [Normal Files - Condensed List] ({len(normal_items)} items)")
                            for item in normal_items[:20]:  # Show first 20
                                if 'artifact' in item:
                                    art = item['artifact']
                                    fname = art['sixw1h']['what']
                                    ftype = art['properties'].get('file_type', 'N/A')
                                    size = art['size_bytes']
                                    output.append(f"    • {fname} ({ftype}, {size:,} bytes)")
                            if len(normal_items) > 20:
                                output.append(f"    ... and {len(normal_items) - 20} more files")

                        # Show suggested actions
                        if args.suggest:
                            output.append(f"\n[SUGGESTED ACTIONS]")
                            output.append(f"  1. Review high-priority items for security issues")
                            output.append(f"  2. Check dependencies: dpkg -L {query_string}")
                            output.append(f"  3. Verify integrity: debsums {query_string}")

                        # Now show ONLY risk items with full profiles
                        if risk_items:
                            output.append(f"\n{'='*60}")
                            output.append(f"DETAILED PROFILES FOR HIGH PRIORITY ITEMS")
                            output.append(f"{'='*60}")

                        items_to_show_full = risk_items
                    else:
                        # For small result sets, show all with full profiles
                        items_to_show_full = result['results']
                        output.append(f"\nQuery Results ({result['count']} items):")
                else:
                    # No package profile, show all results normally
                    items_to_show_full = result['results']
                    output.append(f"\nQuery Results ({result['count']} items):")

                # Pre-build onboarder tool-path lookup once (O(N+M) vs O(N×M) nested stat loop)
                _tool_path_map = {}  # resolved_path_str -> tool_meta
                if onboarding_manager.current_session and onboarding_manager.current_session.onboarded_tools:
                    for _tm in onboarding_manager.current_session.onboarded_tools:
                        try:
                            _tp = str(Path(_tm.file_path).resolve())
                            _tool_path_map[_tp] = _tm
                        except Exception:
                            pass

                # Display full profiles for selected items
                for i, item in enumerate(items_to_show_full):
                    _item_type = item.get('type') or item.get('artifact_type', 'unknown')
                    if item.get('source'):
                        continue  # Skip cold-start items here; displayed below
                    output.append(f"\n{i+1}. [{_item_type}]")
                    if 'artifact' in item:
                        art = item['artifact']
                        output.append(f"   ID: {art['artifact_id']}")
                        output.append(f"   Artifact Type: {art['artifact_type']}")
                        
                        # 6W1H
                        sixw1h = art['sixw1h']
                        output.append(textwrap.indent(f"""
   6W1H Breakdown:
     What: {sixw1h['what']}
     Why: {sixw1h['why']}
     Who: {sixw1h['who']}
     Where: {sixw1h['where']}
     When: {sixw1h['when']}
     Which: {sixw1h['which']}
     How: {sixw1h['how']}
                        """, '   '))
                        
                        # Metadata
                        output.append(f"   File Type: {art['properties'].get('file_type', 'N/A')}")
                        output.append(f"   Size: {art['size_bytes']:,} bytes")
                        output.append(f"   Created: {art['timestamps']['created']}")
                        output.append(f"   Modified: {art['timestamps']['modified']}")
                        
                        # Content Analysis
                        if art['artifact_type'] == 'file' and 'content_analysis' in art['properties'] and art['properties']['content_analysis']:
                            ca = art['properties']['content_analysis']
                            output.append(textwrap.indent(f"""
   Content Analysis:
     Line Count: {ca.get('line_count')}
     Imports: {', '.join(ca.get('imports', [])) if ca.get('imports') else 'None'}
     URLs: {', '.join(ca.get('urls', [])) if ca.get('urls') else 'None'}
     IPs: {', '.join(ca.get('ips', [])) if ca.get('ips') else 'None'}
     Suspicious: {', '.join(ca.get('suspicious_patterns', [])) if ca.get('suspicious_patterns') else 'None'}
                            """, '   '))

                            # NEW: Display class profiling if available
                            if ca.get('classes'):
                                output.append(textwrap.indent(f"""
   Class Profiling:
     Classes: {len(ca['classes'])} ({', '.join(list(ca['classes'].keys())[:5])}{', ...' if len(ca['classes']) > 5 else ''})
                                """, '   '))
                                # Show first class details
                                first_class = list(ca['classes'].keys())[0]
                                class_info = ca['classes'][first_class]
                                output.append(textwrap.indent(f"""
     Example: {first_class}
       Lines: {class_info.get('line_start')}-{class_info.get('line_end')}
       Methods: {len(class_info.get('methods', []))} ({', '.join([m['name'] for m in class_info.get('methods', [])][:3])}{', ...' if len(class_info.get('methods', [])) > 3 else ''})
       Inherits: {', '.join(class_info.get('bases', [])) if class_info.get('bases') else 'None'}
                                """, '   '))

                            if ca.get('functions'):
                                output.append(textwrap.indent(f"""
     Top-level Functions: {len(ca['functions'])} ({', '.join(list(ca['functions'].keys())[:5])}{', ...' if len(ca['functions']) > 5 else ''})
                                """, '   '))

                            if ca.get('validation'):
                                val = ca['validation']
                                if val.get('syntax_valid'):
                                    output.append(textwrap.indent(f"""
     Validation: ✓ Syntax valid, {val.get('class_count', 0)} classes, {val.get('function_count', 0)} functions
                                    """, '   '))
                                else:
                                    output.append(textwrap.indent(f"""
     Validation: ✗ Syntax error at line {val.get('line')}: {val.get('syntax_error', 'Unknown')}
                                    """, '   '))

                        # Onboarder / Filesync / Project Status logic (same as before but appending to output list)
                        artifact_filepath = None
                        where_info = art['sixw1h'].get('where', '')
                        if 'Path:' in where_info:
                            path_match = re.search(r'Path:([^,]+)', where_info)
                            if path_match: artifact_filepath = path_match.group(1).strip()
                        
                        # Onboarder — O(1) lookup using pre-built _tool_path_map
                        if artifact_filepath and _tool_path_map:
                            try:
                                _resolved_afp = str(Path(artifact_filepath).resolve())
                                tool_meta = _tool_path_map.get(_resolved_afp)
                                if tool_meta:
                                    output.append(f"\n   {'='*50}\n   ONBOARDER TOOL PROFILE: {tool_meta.name}\n   {'='*50}")
                                    output.append(f"     Category: {tool_meta.category.value}\n     Description: {tool_meta.description}")
                            except Exception:
                                pass
                        
                        # Filesync
                        if artifact_filepath:
                            fs_data = _get_filesync_timeline_for_file(artifact_filepath)
                            if fs_data:
                                output.append(f"\n   {'='*50}\n   FILESYNC TIMELINE PROFILE\n   {'='*50}")
                                output.append(f"     First Seen: {fs_data.get('first_seen')}\n     Last Modified: {fs_data.get('last_modified')}")
                                if fs_data.get('project'):
                                    p = fs_data['project']
                                    output.append(f"     Project: {p['name']} ({p.get('inference', {}).get('type', 'Unknown')})")

                        # Project Status
                        ps = toolkit._get_project_status_for_file(artifact_filepath if artifact_filepath else "")
                        if ps['marks'] or ps['todos']:
                            output.append(f"\n   PROJECT STATUS")
                            if ps['marks']: output.append(f"     Active Marks: {len(ps['marks'])}")
                            if ps['todos']:
                                for t in ps['todos']:
                                    sc = "x" if t.get('status') == 'done' else " "
                                    output.append(f"       - [{sc}] {t.get('title')}")

                    elif 'node' in item:
                        node = item['node']
                        output.append(f"   Name: {node['name']}")
                        output.append(f"   Type: {node['taxonomy_type']}")
                    elif 'verb' in item:
                        verb = item['verb']
                        output.append(f"   Name: {verb['name']}")

                # Display cold-start results (from persistent data stores)
                # No caps — show all enrichment for full vector attribution
                for i, item in enumerate(items_to_show_full):
                    _src = item.get("source", "")
                    _atype = item.get("artifact_type", "")
                    if _src and _atype:  # Cold-start result
                        if _atype == "change_event":
                            output.append(f"\n{i+1}. [CHANGE EVENT] ({_src})")
                            output.append(f"   Event: {item.get('artifact_id', '?')}")
                            output.append(f"   File: {item.get('file', '?')}")
                            _probe = item.get('probe_status', '')
                            _probe_tag = f" | Probe: {_probe}" if _probe else ""
                            output.append(f"   Verb: {item.get('verb', '?')} | Risk: {item.get('risk_level', '?')} | Test: {item.get('test_status', '?')}{_probe_tag}")
                            output.append(f"   Methods: {', '.join(item.get('methods', [])[:5]) or 'none'}")
                            output.append(f"   Imports Added: {', '.join(item.get('imports_added', [])[:5]) or 'none'}")
                            output.append(f"   Tasks: {', '.join(item.get('task_ids', [])) or 'unlinked'}")
                            _pid = item.get('project_id', '')
                            if _pid:
                                output.append(f"   Project: {_pid}")
                            output.append(f"   Timestamp: {item.get('timestamp', '?')}")
                            # Activity summary line
                            _tc = item.get('total_changes', 0)
                            _ps = item.get('probe_summary', '')
                            _rh = item.get('risk_high_count', 0)
                            _ur = item.get('unresolved_probes', 0)
                            _activity = f"   Activity: {_tc} events"
                            if _ps:
                                _activity += f" | Probes: {_ps}"
                            if _rh:
                                _activity += f" | ⚠ {_rh} HIGH/CRITICAL"
                            if _ur:
                                _activity += f" | ✗ {_ur} unresolved"
                            output.append(_activity)
                        elif _atype == "cataloged_tool":
                            output.append(f"\n{i+1}. [CATALOGED TOOL] ({_src})")
                            output.append(f"   Name: {item.get('name', '?')}")
                            output.append(f"   Tool ID: {item.get('tool_id', '?')}")
                            output.append(f"   Category: {item.get('category', '?')}")
                            _desc = item.get('description', '')
                            if _desc:
                                output.append(f"   Description: {_desc}")
                            _tags = item.get('tags', [])
                            if _tags:
                                output.append(f"   Tags: {', '.join(_tags)}")
                            _sp = item.get('source_path', '')
                            if _sp:
                                output.append(f"   Source: {_sp}")
                        elif _atype == "ast_profile":
                            output.append(f"\n{i+1}. [AST PROFILE] ({_src})")
                            output.append(f"   File: {item.get('file_path', '?')}")
                            output.append(f"   LOC: {item.get('loc', '?')}")
                            _classes = item.get('classes', [])
                            if _classes:
                                output.append(f"   Classes ({len(_classes)}): {', '.join(_classes)}")
                            _funcs = item.get('functions', [])
                            if _funcs:
                                output.append(f"   Functions ({len(_funcs)}): {', '.join(_funcs)}")
                            _imps = item.get('imports', [])
                            if _imps:
                                output.append(f"   Imports ({len(_imps)}): {', '.join(str(im) for im in _imps)}")
                        elif _atype == "call_graph":
                            output.append(f"\n{i+1}. [CALL GRAPH] ({_src})")
                            _cg_imports = item.get('imports', [])
                            _cg_importers = item.get('imported_by', [])
                            _cg_edges_n = item.get('call_edges', 0)
                            _cg_top = item.get('top_edges', [])
                            if _cg_imports:
                                output.append(f"   Depends On ({len(_cg_imports)}): {', '.join(_cg_imports)}")
                            if _cg_importers:
                                output.append(f"   Imported By ({len(_cg_importers)}): {', '.join(_cg_importers)}")
                            _graph_mode = getattr(args, 'graph', None)
                            if _graph_mode is None:
                                if _cg_edges_n:
                                    output.append(f"   Call Edges: {_cg_edges_n} (use --graph to expand, --graph full for all)")
                            elif _graph_mode == 'summary':
                                _show = _cg_top[:20]
                                output.append(f"   Call Edges ({_cg_edges_n}, showing {len(_show)}):")
                                for _edge in _show:
                                    output.append(f"     → {_edge}")
                                if _cg_edges_n > 20:
                                    output.append(f"     ... +{_cg_edges_n - 20} more (--graph full)")
                            else:
                                output.append(f"   Call Edges ({_cg_edges_n}):")
                                for _edge in _cg_top:
                                    output.append(f"     → {_edge}")
                            if not _cg_imports and not _cg_importers and not _cg_top:
                                output.append(f"   (no call graph data)")
                        elif _atype == "task_association":
                            output.append(f"\n{i+1}. [TASK ASSOCIATIONS] ({_src})")
                            output.append(f"   Matching Tasks: {item.get('task_count', 0)}")
                            for _t in item.get('tasks', []):
                                _icon = "✓" if _t.get('status', '').upper() in ('COMPLETE', 'DONE') else "○"
                                output.append(f"   {_icon} {_t.get('id', '?')}: {_t.get('title', '')[:60]} ({_t.get('status', '?')})")
                        elif _atype == "import_usage":
                            # Reverse-import search: all project files that import this module
                            _mod = item.get("module", "?")
                            _total = item.get("total", 0)
                            _files = item.get("files", [])
                            output.append(f"\n{i+1}. [FILES USING '{_mod}'] ({_src})")
                            output.append(f"   {_total} file(s) import this module in the project codebase:")
                            for _fpath, _loc in _files[:25]:
                                _fname = _fpath.split("/")[-1]
                                _short = "/".join(_fpath.split("/")[-3:]) if _fpath.count("/") >= 3 else _fpath
                                output.append(f"     • {_fname}  ({_short}, {_loc} lines)")
                            if _total > 25:
                                output.append(f"     ... +{_total - 25} more")
                        elif _atype == "import_usage_history":
                            # Files that recently added this import per enriched_changes
                            _mod = item.get("module", "?")
                            _total = item.get("total", 0)
                            _files = item.get("files", [])
                            output.append(f"\n{i+1}. [FILES THAT ADDED IMPORT '{_mod}'] ({_src})")
                            output.append(f"   {_total} file(s) recently added this import (from change history):")
                            for _fp, _ in _files[:25]:
                                output.append(f"     • {_fp.split('/')[-1]}  ({'/'.join(_fp.split('/')[-3:])})")
                            if _total > 25:
                                output.append(f"     ... +{_total - 25} more")
                        elif _atype == "provision":
                            # Bundled offline package in Trainer/Provisions/
                            _pname = item.get("name", "?")
                            _pver  = item.get("version", "?")
                            _pstat = item.get("install_status", "bundled")
                            _pscope = item.get("scope", "internal_bundle")
                            _pinst = item.get("installed_version")
                            _pfn   = item.get("filename", "")
                            output.append(f"\n{i+1}. [PROVISION: {_pname}] ({_src})")
                            output.append(f"   Version : {_pver}")
                            output.append(f"   Status  : {_pstat} ({_pscope})")
                            if _pinst:
                                output.append(f"   Installed: {_pinst}")
                            if _pfn:
                                output.append(f"   File    : {_pfn}")
                            if _pstat == "bundled" and _pfn:
                                output.append(f"   Install : pip install Provisions/{_pfn}")
                        elif _atype == "temporal_profile":
                            output.append(f"\n{i+1}. [TEMPORAL PROFILE] ({_src})")
                            output.append(f"   History: {item.get('history_name', '?')}")
                            output.append(f"   Backups: {item.get('backup_count', 0)} | Span: {item.get('span_days', 0)}d | Activity: {item.get('activity_score', 0)}")
                            output.append(f"   First Seen: {item.get('first_seen', '?')}")
                            output.append(f"   Last Seen: {item.get('last_seen', '?')}")

                # No truncation — full vector attribution output

                # ── Guided next steps (always shown, contextual) ──
                _next_steps = []
                _has_change_event = any(r.get('artifact_type') == 'change_event' for r in items_to_show_full)
                _has_call_graph = any(r.get('artifact_type') == 'call_graph' for r in items_to_show_full)
                _has_tasks = any(r.get('artifact_type') == 'task_association' for r in items_to_show_full)

                _qf = query_string if query_string else 'FILE'
                _next_steps.append(f"assess {_qf}                    Pre-change impact + AoE warnings")
                _next_steps.append(f"assess {_qf} -i \"your changes\"   Intent-aware blast radius check")

                if _has_call_graph:
                    if not getattr(args, 'graph', None):
                        _next_steps.append(f"query {_qf} --graph            Show top 20 call edges")
                if _has_change_event:
                    _next_steps.append(f"latest                         Recent changes + probe results")
                if _has_tasks:
                    _next_steps.append(f"todo view                      Full task board")

                # ── Active task context ──
                try:
                    _cfg_path_q = Path(__file__).parents[2] / "plans" / "config.json"
                    if _cfg_path_q.exists():
                        _cfg_q = json.loads(_cfg_path_q.read_text(encoding="utf-8"))
                        _atid_q = _cfg_q.get("active_task_id", "")
                        if _atid_q:
                            _awh_q = _cfg_q.get("active_task_wherein", "")
                            _aat_q = _cfg_q.get("activated_at", "?")[:16]
                            _lat_q = _cfg_q.get("last_activity_at", "")[:16]
                            output.append(f"\n[ACTIVE TASK]")
                            output.append(f"  Task: {_atid_q}  |  File: {Path(_awh_q).name if _awh_q else '?'}  |  Since: {_aat_q}")
                            if _lat_q:
                                output.append(f"  Last Activity: {_lat_q}")
                            _qf_at = query_string if query_string else 'FILE'
                            if _awh_q and Path(_awh_q).name != _qf_at:
                                output.append(f"  ⚠ You're querying {_qf_at} but active task targets {Path(_awh_q).name}")
                                output.append(f"  → todo activate TASK_ID         Switch active task")
                except Exception:
                    pass

                output.append(f"\n[NEXT STEPS]")
                for _ns in _next_steps:
                    output.append(f"  → {_ns}")

                # #[Mark:SWEEP2-IN_PROGRESS] Suggestive actions for query results
                if args.suggest and result['results']:
                    # Get first result to generate suggestions
                    first_result = result['results'][0]
                    suggestions = []

                    if 'artifact' in first_result:
                        artifact_filepath = None
                        art = first_result['artifact']
                        where_info = art['sixw1h'].get('where', '')
                        if 'Path:' in where_info:
                            path_match = re.search(r'Path:([^,]+)', where_info)
                            if path_match:
                                artifact_filepath = path_match.group(1).strip()

                        if artifact_filepath:
                            suggestions = SuggestiveGrepEngine.suggest_for_file_query(art, artifact_filepath)

                    elif first_result.get('source') and first_result.get('artifact_type'):
                        # Cold-start result — generate suggestions from enriched data
                        _atype = first_result.get('artifact_type')
                        _src_file = first_result.get('file', '') or first_result.get('file_path', '')
                        if _src_file:
                            _src_base = Path(_src_file).name if '/' in _src_file else _src_file
                            suggestions.append({
                                'id': 'assess_file', 'label': f'Assess {_src_base} (pre-change impact)',
                                'command': f'{sys.argv[0]} assess {_src_base}', 'selected': True
                            })
                            suggestions.append({
                                'id': 'query_graph', 'label': f'Show call graph for {_src_base}',
                                'command': f'{sys.argv[0]} query {_src_base} --graph', 'selected': False
                            })
                        if _atype == 'change_event':
                            _probe = first_result.get('probe_status', '')
                            if _probe == 'FAIL':
                                suggestions.append({
                                    'id': 'probe_detail', 'label': 'View probe errors (latest command)',
                                    'command': f'{sys.argv[0]} latest', 'selected': False
                                })
                        suggestions.append({
                            'id': 'todo_view', 'label': 'View task board',
                            'command': f'{sys.argv[0]} todo view', 'selected': False
                        })

                    if suggestions and args.zenity:
                        # Use interactive action selection
                        selected = display_output_with_actions(
                            "\n".join(output),
                            suggestions,
                            title=f"Babel Query: {args.query_string}",
                            use_zenity=True
                        )

                        if selected:
                            action = next(a for a in suggestions if a['id'] == selected)
                            print(f"\n[+] Executing: {action['command']}")
                            subprocess.run(action['command'], shell=True)
                    elif suggestions:
                        # Just print suggestions without executing
                        output.append("\n\n[SUGGESTED ACTIONS]")
                        for i, sug in enumerate(suggestions, 1):
                            output.append(f"  {i}. {sug['label']}")
                            output.append(f"     Command: {sug['command']}")
                        display_output("\n".join(output), title=f"Babel Query: {args.query_string}", use_zenity=args.zenity)
                    else:
                        display_output("\n".join(output), title=f"Babel Query: {args.query_string}", use_zenity=args.zenity)
                else:
                    display_output("\n".join(output), title=f"Babel Query: {args.query_string}", use_zenity=args.zenity)

        
        elif args.command == 'file':
            artifact = toolkit.analyze_file(args.filepath, args.depth)
            
            # Filesync Integration: Display timeline data if available
            try:
                target_path = str(Path(args.filepath).resolve())
                filesync_data = _get_filesync_timeline_for_file(target_path)
                
                if filesync_data:
                    print(f"\n   FILESYNC TIMELINE PROFILE")
                    print(f"     File ID: {filesync_data.get('file_id', 'N/A')}")
                    print(f"     First Seen: {filesync_data.get('first_seen', 'N/A')}")
                    print(f"     Last Modified: {filesync_data.get('last_modified', 'N/A')}")
                    
                    if filesync_data.get('project'):
                        proj = filesync_data['project']
                        print(f"     Project: {proj.get('name')} (Confidence: {proj.get('inference', {}).get('confidence', 'N/A')})")
                        print(f"     Type: {proj.get('inference', {}).get('type', 'Unknown')}")
                    
                    if filesync_data.get('related_files'):
                        print(f"\n     Related Files ({len(filesync_data['related_files'])}):")
                        for rf in filesync_data['related_files']:
                            print(f"       - {Path(rf['path']).name} ({rf.get('category', 'unknown')})")
            except Exception as e:
                if args.verbose:
                    print(f"[-] Error loading Filesync data: {e}")

            # #[Mark:P3-2] Display Project Status
            try:
                project_status = toolkit._get_project_status_for_file(args.filepath)
                if project_status['marks'] or project_status['todos']:
                    print(f"\n   PROJECT STATUS")
                    if project_status['marks']:
                        print(f"     Active Marks ({len(project_status['marks'])}):")
                        for m in project_status['marks']:
                            print(f"       - #[Mark:{m['mark_id']}] (Line {m['line']})")
                    
                    if project_status['todos']:
                        print(f"     Related Todos ({len(project_status['todos'])}):")
                        for t in project_status['todos']:
                            status_char = "x" if t.get('status') == 'done' else " "
                            print(f"       - [{status_char}] {t.get('title')} (ID: {t.get('id')})")
                    print(f"   {'='*50}\n")
            except Exception as e:
                if args.verbose:
                    print(f"[-] Error loading Project Status: {e}")

            # Retrieve Onboarder information if available
            onboarder_tool_info = None
            
            # 1. Check persistent consolidated_menu.json
            try:
                # Find consolidated_menu.json (relative to this script)
                babel_root = Path(__file__).resolve().parent
                menu_file = babel_root / "babel_data" / "inventory" / "consolidated_menu.json"
                if menu_file.exists():
                    with open(menu_file, 'r') as f:
                        menu_data = json.load(f)
                        target_rel = str(Path(args.filepath).resolve().relative_to(babel_root))
                        for tool in menu_data.get('tools', []):
                            # Check if command or path matches
                            if tool.get('path') and Path(tool['path']).resolve() == Path(args.filepath).resolve():
                                onboarder_tool_info = tool
                                break
                            # Try matching relative path
                            if tool.get('path') == target_rel:
                                onboarder_tool_info = tool
                                break
            except Exception:
                pass

            # 2. Check current session if not found in persistent menu
            if not onboarder_tool_info and onboarding_manager.current_session and onboarding_manager.current_session.onboarded_tools:
                for tool_meta in onboarding_manager.current_session.onboarded_tools:
                    if Path(tool_meta.file_path).resolve() == Path(args.filepath).resolve():
                        onboarder_tool_info = tool_meta
                        break

            if onboarder_tool_info:
                # Normalize data format (since tool_meta and tool_dict differ)
                is_meta = hasattr(onboarder_tool_info, 'name')
                name = onboarder_tool_info.name if is_meta else onboarder_tool_info.get('display_name', 'Unknown')
                tool_id = onboarder_tool_info.tool_id if is_meta else onboarder_tool_info.get('id', 'N/A')
                category = onboarder_tool_info.category.value if is_meta else onboarder_tool_info.get('category', 'N/A')
                desc = onboarder_tool_info.description if is_meta else onboarder_tool_info.get('description', 'N/A')
                
                print(f"\n{'='*60}")
                print(f"ONBOARDER TOOL PROFILE: {name}")
                print(f"{'='*60}")
                print(f"  Tool ID: {tool_id}")
                print(f"  Category: {category}")
                print(f"  Description: {desc}")
                
                if is_meta:
                    print(f"  Has Argparse (CLI): {onboarder_tool_info.has_argparse}")
                    print(f"  Has Tkinter (GUI): {onboarder_tool_info.has_tkinter}")
                else:
                    args_count = len(onboarder_tool_info.get('arguments', []))
                    print(f"  Cataloged Arguments: {args_count}")

                if is_meta and onboarder_tool_info.tags:
                    print(f"  Tags: {', '.join(onboarder_tool_info.tags)}")
                elif not is_meta and onboarder_tool_info.get('tags'):
                     print(f"  Tags: {', '.join(onboarder_tool_info['tags'])}")
                
                print(f"{'='*60}\n")
            else:
                if args.verbose:
                    print("\n[!] File not currently onboarded/cataloged in Babel.")

            # #[Mark:SWEEP2-IN_PROGRESS] Suggestive actions for file analysis
            if args.suggest and artifact:
                # Convert ForensicArtifact to dict for suggestion engine
                from dataclasses import asdict
                artifact_dict = asdict(artifact)
                suggestions = SuggestiveGrepEngine.suggest_for_file_query(artifact_dict, args.filepath)

                if suggestions and args.zenity:
                    # Collect all printed output (we need to capture it for zenity)
                    # For now, just show action selection
                    print("\n" + "="*60)
                    print("SUGGESTED ACTIONS")
                    print("="*60)

                    selected = zenity_radiolist(
                        [{'id': s['id'], 'label': s['label'], 'selected': s.get('selected', False)} for s in suggestions],
                        title=f"Actions for {Path(args.filepath).name}",
                        text="What would you like to do next?"
                    )

                    if selected:
                        action = next(a for a in suggestions if a['id'] == selected)
                        print(f"\n[+] Executing: {action['command']}")
                        result = subprocess.run(action['command'], shell=True, capture_output=True, text=True)
                        output_text = f"[COMMAND]\n{action['command']}\n\n[OUTPUT]\n{result.stdout}\n{result.stderr}"
                        display_output(output_text, title=f"Result: {action['label']}", use_zenity=True)
                elif suggestions:
                    # Just print suggestions
                    print("\n" + "="*60)
                    print("SUGGESTED ACTIONS")
                    print("="*60)
                    for i, sug in enumerate(suggestions, 1):
                        print(f"  {i}. {sug['label']}")
                        print(f"     {sug['command']}")

            if artifact and args.save:
                toolkit.save()

        elif args.command == 'manifest':
            manifest = toolkit.generate_manifest(args.format)

            if args.output:
                with open(args.output, 'w') as f:
                    if args.format == 'json':
                        json.dump(json.loads(manifest), f, indent=2)
                    else:
                        f.write(manifest)
                print(f"[+] Manifest saved to: {args.output}")
            else:
                display_output(manifest, title=f"System Manifest ({args.format})", use_zenity=args.zenity)
        
        elif args.command == 'journal':
            if args.add:
                tags = args.tags.split(',') if args.tags else []
                toolkit.journal_add("user_entry", args.add, tags)
            elif args.query:
                result = toolkit.journal_query(args.query, args.entry_type, args.limit)
                print(f"\nJournal Entries ({result['count']} of {result['total_entries']}):")
                for i, entry in enumerate(result['results']):
                    time_str = entry['timestamp'].split('T')[1][:8]
                    print(f"\n{i+1}. [{time_str}] {entry['entry_type']}")
                    print(f"   {entry['content'][:80]}...")
                    if entry['tags']:
                        print(f"   Tags: {', '.join(entry['tags'])}")
            elif args.stats:
                stats = toolkit.journal_stats()
                print(f"\nJournal Statistics:")
                print(f"  Total Entries: {stats['total_entries']}")
                print(f"  By Type:")
                for entry_type, count in stats['by_type'].items():
                    print(f"    {entry_type}: {count}")
                print(f"  Recent Entries ({len(stats['recent_entries'])}):")
                for entry in stats['recent_entries'][-5:]:
                    time_str = entry['timestamp'].split('T')[1][:8]
                    print(f"    [{time_str}] {entry['entry_type']}: {entry['content'][:60]}...")
        
        elif args.command == 'export':
            # If using Zenity, ask if user wants to choose location
            custom_location = None
            if args.zenity:
                if zenity_question("Export to custom location?",
                                  title="Export Location",
                                  ok_label="Choose Location",
                                  cancel_label="Use Default"):
                    # Show directory chooser
                    result = subprocess.run([
                        'zenity', '--file-selection', '--directory',
                        '--title', 'Choose Export Directory'
                    ], capture_output=True, text=True)

                    if result.returncode == 0:
                        custom_location = Path(result.stdout.strip())

            export_path = toolkit.export_session(args.format, custom_dir=custom_location)

            # Show export details
            import os
            file_size = os.path.getsize(export_path)
            size_mb = file_size / (1024 * 1024)

            output = []
            output.append("="*60)
            output.append("SESSION EXPORT COMPLETE")
            output.append("="*60)
            output.append(f"\nSession: {toolkit.session_id}")
            output.append(f"Format: {args.format}")
            output.append(f"Export File: {export_path}")
            output.append(f"File Size: {size_mb:.2f} MB ({file_size:,} bytes)")
            output.append(f"\nArtifacts Exported: {len(toolkit.session.artifacts)}")
            output.append(f"\nThe tarball contains:")
            output.append("  - Session data (artifacts, taxonomy, queries)")
            output.append("  - Filesync timeline & organized files")
            output.append("  - Onboarder consolidated menu")
            output.append("  - Plans & todos")
            output.append("  - Trust registry")
            output.append("  - System manifest")
            output.append("  - Journal entries")

            # If Zenity, offer to move/open location
            if args.zenity:
                actions = [
                    {'id': 'open', 'label': 'Open export directory', 'selected': True},
                    {'id': 'move', 'label': 'Move export to another location', 'selected': False}
                ]
                selected = zenity_radiolist(actions,
                                           title="Export Complete",
                                           text="What would you like to do?")

                if selected == 'open':
                    subprocess.run(['xdg-open', str(export_path.parent)])
                elif selected == 'move':
                    result = subprocess.run([
                        'zenity', '--file-selection', '--directory',
                        '--title', 'Move Export To...'
                    ], capture_output=True, text=True)

                    if result.returncode == 0:
                        new_location = Path(result.stdout.strip()) / export_path.name
                        shutil.move(str(export_path), str(new_location))
                        zenity_notification(f"Export moved to {new_location}")

            display_output("\n".join(output), title="Export Complete", use_zenity=args.zenity)
        
        elif args.command == 'stats':
            stats = toolkit.get_stats()
            output = []
            output.append("\nToolkit Statistics:")
            output.append(f"  Session ID: {stats['session_id']}")
            output.append(f"  Hostname: {stats['hostname']}")
            output.append(f"  OS Type: {stats['os_type']}")
            output.append(f"  Runtime: {stats['runtime_seconds']} seconds")
            output.append(f"  Artifacts Analyzed: {stats['artifacts_analyzed']}")
            output.append(f"  Files Processed: {stats['files_processed']}")
            output.append(f"  Queries Executed: {stats['queries_executed']}")
            output.append(f"\nSession Statistics:")
            sess_stats = stats['session_statistics']
            output.append(f"  Taxonomic Nodes: {sess_stats['taxonomic_nodes']}")
            output.append(f"  Artifacts: {sess_stats['artifacts']}")
            output.append(f"  Verbs: {sess_stats['verbs']}")
            output.append(f"  Journal Entries: {sess_stats['journal_entries']}")
            output.append(f"  Query History: {sess_stats['query_history']}")
            display_output("\n".join(output), title="Toolkit Statistics", use_zenity=args.zenity)
        
        elif args.command == 'assess':
            _assess_file = args.file
            _assess_intent = getattr(args, 'intent', '')
            print(f"[*] Assessing: '{_assess_file}'" +
                  (f" (intent: {_assess_intent[:60]})" if _assess_intent else ""))
            _cold = toolkit._query_cold_start(_assess_file, max_results=20)
            _report = toolkit._assess_change_impact(_assess_file, _assess_intent, _cold)
            display_output(_report, title=f"Assess: {_assess_file}", use_zenity=args.zenity)

            # ── Write-back: persist assess findings to active task context ──
            try:
                _cfg_path_ab = Path(__file__).parents[2] / "plans" / "config.json"
                if _cfg_path_ab.exists():
                    _cfg_ab = json.loads(_cfg_path_ab.read_text(encoding="utf-8"))
                    _atid_ab = _cfg_ab.get("active_task_id", "")
                    if _atid_ab:
                        _ctx_path = Path(__file__).parents[2] / "plans" / "Tasks" / f"task_context_{_atid_ab}.json"
                        _ctx_ab = {}
                        if _ctx_path.exists():
                            _ctx_ab = json.loads(_ctx_path.read_text(encoding="utf-8"))

                        _warnings_ab = []
                        _ce_ab = next((r for r in _cold if r.get('artifact_type') == 'change_event'), {})
                        _cg_ab = next((r for r in _cold if r.get('artifact_type') == 'call_graph'), {})
                        if _ce_ab.get('unresolved_probes'):
                            _warnings_ab.append({"level": "CRITICAL", "msg": f"{_ce_ab['unresolved_probes']} unresolved probe FAILs"})
                        if _ce_ab.get('risk_high_count'):
                            _warnings_ab.append({"level": "RISK", "msg": f"{_ce_ab['risk_high_count']} HIGH/CRITICAL risk events"})
                        _importers_ab = _cg_ab.get('imported_by', [])
                        if len(_importers_ab) >= 5:
                            _warnings_ab.append({"level": "WARN", "msg": f"{len(_importers_ab)} downstream dependents"})
                        if _assess_intent:
                            _warnings_ab.append({"level": "INFO", "msg": f"Intent: {_assess_intent[:80]}"})

                        _checklist_ab = []
                        _checklist_ab.append({"check": f"py_compile {_assess_file}", "status": "pending"})
                        if _ce_ab.get('unresolved_probes'):
                            _checklist_ab.append({"check": f"Resolve {_ce_ab['unresolved_probes']} probe FAILs", "status": "pending"})
                        if len(_importers_ab) >= 3:
                            _checklist_ab.append({"check": f"Test {len(_importers_ab)} downstream importers", "status": "pending"})
                        _checklist_ab.append({"check": "Run AUTO_TEST probe", "status": "pending"})

                        _ctx_ab["last_assess"] = {
                            "file": _assess_file,
                            "intent": _assess_intent,
                            "timestamp": datetime.now().isoformat(),
                            "warnings": _warnings_ab,
                            "checklist": _checklist_ab,
                            "importers": _importers_ab[:10],
                            "blast_radius": len(_importers_ab),
                        }
                        # _trust_profile: field classification per aoe_vector_config.trust_tiers
                        # Enables roadmap_computer to apply trust guards on read.
                        if "_trust_profile" not in _ctx_ab:
                            _ctx_ab["_trust_profile"] = {
                                "trusted_fields": [
                                    "_meta.task_id", "changes[].event_id",
                                    "changes[].file", "code_profile.classes",
                                    "code_profile.functions", "code_profile.LOC",
                                    "code_profile.imports"
                                ],
                                "provisional_fields": [
                                    "changes[].risk_level", "blame", "peers",
                                    "plan_summary", "session_refs", "ux_events"
                                ],
                                "untrusted_fields": [
                                    "completion_signals.inferred_status",
                                    "metastate.gap_severity",
                                    "metastate.priority_pct",
                                    "metastate.recommended_action",
                                    "morph_opinion_data",
                                    "query_weights_data"
                                ],
                                "source": "aoe_vector_config.trust_tiers",
                                "generated": datetime.now().isoformat()
                            }
                        _ctx_path.parent.mkdir(parents=True, exist_ok=True)
                        _ctx_path.write_text(json.dumps(_ctx_ab, indent=2, default=str), encoding="utf-8")
                        print(f"[+] Assess findings saved to task_context_{_atid_ab}.json")
            except Exception:
                pass

        elif args.command == 'index':
            # H3: UnifiedContextIndex queries
            _uci_scripts_dir = str(Path(__file__).parent / "regex_project" / "activities" / "tools" / "scripts")
            if _uci_scripts_dir not in sys.path:
                sys.path.insert(0, _uci_scripts_dir)
            try:
                from unified_context_index import UnifiedContextIndex, _print_entity
                _trainer_root = Path(__file__).parents[2]
                _uci = UnifiedContextIndex(_trainer_root)
                _all_subargs = getattr(args, 'index_subargs', []) or []
                _idx_action  = _all_subargs[0] if _all_subargs else 'show'
                _idx_args    = _all_subargs[1:]

                if _idx_action == 'build':
                    _uci.build(force=True)
                    print(f"Done. {len(_uci._index)} entities indexed.")

                elif _idx_action == 'show':
                    if not _idx_args:
                        print("[ERR] index show requires a file argument")
                    else:
                        if not _uci._load_cache():
                            _uci.build()
                        _ent = _uci.get(_idx_args[0])
                        if not _ent:
                            print(f"No entity found for: {_idx_args[0]}")
                        else:
                            _print_entity(_ent, verbose=getattr(args, 'verbose', False))

                elif _idx_action == 'search':
                    if not _idx_args:
                        print("[ERR] index search requires a query term")
                    else:
                        if not _uci._load_cache():
                            _uci.build()
                        _results = _uci.search(' '.join(_idx_args))
                        if not _results:
                            print(f"No results for: {' '.join(_idx_args)!r}")
                        for _r in _results:
                            print(f"  [{_r['score']:.1f}] {_r['file_path']}")

                elif _idx_action == 'graph':
                    if not _idx_args:
                        print("[ERR] index graph requires a file argument")
                    else:
                        if not _uci._load_cache():
                            _uci.build()
                        _cg = _uci.get_call_graph(_idx_args[0])
                        if 'error' in _cg:
                            print(f"[ERR] {_cg['error']}")
                        else:
                            _s = _cg.get('summary', {})
                            print(f"\n[CALL GRAPH] {_cg.get('file_path','')}")
                            print(f"  functions: {_s.get('total_functions',0)}  "
                                  f"| forward_edges: {_s.get('forward_edges',0)}")
                            for _fn, _fd in list(_cg.get('functions', {}).items())[:30]:
                                _fwd = ', '.join(_fd['forward'][:6])
                                _bwd = ', '.join(_fd['backward'][:3])
                                _parts = []
                                if _fwd:
                                    _parts.append(f"→ {_fwd}")
                                if _bwd:
                                    _parts.append(f"← {_bwd}")
                                print(f"  {_fn}: {' | '.join(_parts) if _parts else '(no calls)'}")

                elif _idx_action == 'chain':
                    if len(_idx_args) < 2:
                        print("[ERR] index chain requires: <file> <function>")
                    else:
                        if not _uci._load_cache():
                            _uci.build()
                        _cg = _uci.get_call_graph(_idx_args[0])
                        _fn_data = _cg.get('functions', {}).get(_idx_args[1])
                        if _fn_data is None:
                            print(f"Function {_idx_args[1]!r} not found in {_idx_args[0]}")
                        else:
                            print(f"\n[CHAIN] {_idx_args[1]} ({_idx_args[0]})")
                            print(f"  → forward  ({len(_fn_data['forward'])}):  {', '.join(_fn_data['forward'][:15])}")
                            print(f"  ← backward ({len(_fn_data['backward'])}): {', '.join(_fn_data['backward'][:10])}")
                else:
                    print(f"[ERR] Unknown index action: {_idx_action}")
            except ImportError as _e:
                print(f"[ERR] Could not load unified_context_index: {_e}")
            except Exception as _e:
                print(f"[ERR] index command failed: {_e}")
                if getattr(args, 'verbose', False):
                    import traceback
                    traceback.print_exc()

        elif args.command == 'explain':
            # Phase L: Temporal Narrative Engine + Init Chain Tracer
            _scripts = Path(__file__).parent / 'regex_project' / 'activities' / 'tools' / 'scripts'
            import sys as _sys
            _sys.path.insert(0, str(_scripts))
            try:
                from temporal_narrative_engine import TemporalNarrativeEngine
                _trainer_root = Path(__file__).parent.parent.parent.parent
                _engine = TemporalNarrativeEngine(_trainer_root)

                # Resolve time window
                _since = getattr(args, 'since', None) or getattr(args, 'last', None)
                _until = getattr(args, 'until', None) or getattr(args, 'date', None)
                _incremental = getattr(args, 'incremental', False)

                _result = _engine.explain(
                    since=_since,
                    until=_until,
                    incremental=_incremental,
                )

                # Init chain tracing
                _init_chain_target = getattr(args, 'init_chain', None)
                if _init_chain_target is not None:
                    from init_chain_tracer import InitChainTracer
                    _tracer = InitChainTracer(_trainer_root)
                    if _init_chain_target == '__recent__':
                        _files_to_trace = [f['file'] for f in _result['files_touched']]
                    else:
                        _files_to_trace = [_init_chain_target]
                    _chain_report = _tracer.trace(_files_to_trace)
                    _result['init_chain_impact'] = _chain_report
                    print('\n' + _chain_report['text'])

                # Morph bridge
                if getattr(args, 'morph', False):
                    try:
                        from omega_bridge import OmegaBridge
                        _morph_regex_path = _trainer_root / 'Models' / 'Morph0.1-10m-Babble' / 'Morph_regex'
                        _bridge = OmegaBridge(_trainer_root, _morph_regex_path)
                        _morph_resp = _bridge.explain_period(_result)
                        _result['morph_response'] = _morph_resp
                        print('\n[Morph Response]')
                        print(f"  Signal : {_morph_resp.get('control_signal', 'unknown')}")
                        print(f"  Pattern: {_morph_resp.get('pattern_matched', 'unknown')}")
                        print(f"  {_morph_resp.get('response', '')[:300]}")
                    except Exception as _me:
                        print(f"[WARN] Morph bridge unavailable: {_me}")

                _fmt = getattr(args, 'format', 'text')
                _engine.print_narrative(_result, fmt=_fmt)

            except ImportError as _e:
                print(f"[ERR] Could not load explain engine: {_e}")
            except Exception as _e:
                print(f"[ERR] explain command failed: {_e}")
                if getattr(args, 'verbose', False):
                    import traceback
                    traceback.print_exc()

        elif args.command == 'track':
            # Inject CLI-sourced enriched_change into version_manifest.json
            # so it becomes visible to Os_Toolkit explain.
            _scripts_dir_tk = Path(__file__).parent / 'regex_project' / 'activities' / 'tools' / 'scripts'
            try:
                import sys as _sys_tk
                if str(_scripts_dir_tk) not in _sys_tk.path:
                    _sys_tk.path.insert(0, str(_scripts_dir_tk))
                from cli_change_tracker import CLIChangeTracker as _CLT
                _trainer_root_tk = Path(__file__).resolve().parents[3]
                _tracker = _CLT(_trainer_root_tk)
                _methods = [m.strip() for m in (args.methods or '').split(',') if m.strip()]
                _tasks = [t.strip() for t in (args.task or '').split(',') if t.strip()]
                _eid = _tracker.record_change(
                    file_path=args.file,
                    verb=args.verb,
                    methods=_methods,
                    task_ids=_tasks,
                    risk_level=args.risk,
                    description=args.desc,
                    probe_status='PASS',
                )
                print(f"[+] Tracked: {_eid}")
                print(f"    file={args.file}  verb={args.verb}  risk={args.risk}")
                if _methods:
                    print(f"    methods={', '.join(_methods)}")
                if _tasks:
                    print(f"    tasks={', '.join(_tasks)}")
            except Exception as _e_tk:
                print(f"[ERR] track failed: {_e_tk}")
                import traceback
                traceback.print_exc()

        elif args.command == 'roadmap':
            _scripts_dir = str(Path(__file__).parent / 'regex_project' / 'activities' / 'tools' / 'scripts')
            if _scripts_dir not in sys.path:
                sys.path.insert(0, _scripts_dir)
            try:
                from roadmap_computer import RoadmapComputer
                _rc = RoadmapComputer(Path(__file__).parents[3])
                # ── Propose mode (T6) ──
                if getattr(args, 'propose', None):
                    _proposal = _rc.propose(args.propose)
                    _rc.print_proposal_report(_proposal)
                    if getattr(args, 'save', False):
                        _rc.save_proposal_json(_proposal, args.propose)
                else:
                    # ── Standard roadmap mode ──
                    _project = getattr(args, 'project_id', None)
                    if not _project:
                        _cfg_path = Path(__file__).parents[3] / 'Data' / 'plans' / 'config.json'
                        if _cfg_path.exists():
                            _project = json.loads(_cfg_path.read_text()).get('active_project_id')
                    _result = _rc.compute(_project)
                    _fmt = getattr(args, 'format', 'text')
                    _top = getattr(args, 'top', 0)
                    if _fmt in ('text', 'both'):
                        _rc.print_report(_result, top_n=_top)
                    if getattr(args, 'save', False) or _fmt in ('json', 'both'):
                        _rc.save_json(_result, _project)
                    if _fmt == 'json':
                        print(json.dumps(_result, indent=2, default=str))
                    # Spawn diffs
                    if getattr(args, 'spawn', False) or getattr(args, 'spawn_save', False):
                        _diffs = _rc.generate_spawn_diffs(_result)
                        _rc.print_spawn_report(_diffs)
                        if getattr(args, 'spawn_save', False):
                            _rc.save_spawn_json(_diffs, _project)
            except Exception as _e_rm:
                print(f"[ERR] roadmap failed: {_e_rm}")
                import traceback
                traceback.print_exc()

        elif args.command == 'save':
            toolkit.save()

        elif args.command == 'interactive':
            interactive_mode(toolkit, onboarding_manager) # Pass onboarding_manager here
        
        # Always save on exit unless it's a destructive operation
        if args.command not in ['export', 'interactive']:
            toolkit.save()
        
        toolkit.close()
        
    except KeyboardInterrupt:
        print("\n[!] Interrupted by user")
        toolkit.save()
        toolkit.close()
        sys.exit(0)
    except Exception as e:
        print(f"[-] Error executing command: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        toolkit.close()
        sys.exit(1)

def interactive_mode(toolkit: ForensicOSToolkit, onboarding_manager=None):
    """Interactive mode for toolkit"""
    print(f"\n{TOOLKIT_NAME} Interactive Mode")
    print(f"Session: {toolkit.session_id}")
    print(f"Hostname: {toolkit.hostname}")
    print(f"OS: {toolkit.os_type.value}")
    print("\nType 'help' for commands, 'exit' to quit")
    
    while True:
        try:
            command = input(f"\nforekit[{toolkit.session_id[:8]}]> ").strip()
            
            if not command:
                continue
            
            if command.lower() in ['exit', 'quit', 'q']:
                print("[*] Exiting interactive mode")
                break
            
            elif command.lower() in ['help', '?']:
                print("""
Available commands:
  analyze [depth]           - Analyze system (depth: 1-3)
  query <string> [type]    - Query session data
  file <path> [depth]      - Analyze specific file
  manifest [format]        - Generate system manifest
  journal add <text>       - Add journal entry
  journal query <text>     - Query journal
  journal stats           - Show journal statistics
  export [format]         - Export session
  stats                   - Show toolkit statistics
  save                    - Save session
  help                    - Show this help
  exit                    - Exit interactive mode
                """)
            
            elif command.lower().startswith('analyze'):
                parts = command.split()
                depth = 2
                if len(parts) > 1:
                    try:
                        depth = int(parts[1])
                    except:
                        pass
                toolkit.analyze_system_baseline(depth=depth)
            
            elif command.lower().startswith('query'):
                parts = command.split(maxsplit=2)
                if len(parts) < 2:
                    print("Usage: query <string> [type]")
                    continue
                
                query_str = parts[1]
                query_type = 'auto'
                if len(parts) > 2:
                    query_type = parts[2]
                
                result = toolkit.query(query_str, query_type)
                print(f"Found {result['count']} results in {result['duration_ms']}ms")
                
                if result['results']:
                    for i, item in enumerate(result['results'][:5]):
                        print(f"\n{i+1}. [{item['type']}]")
                        if 'artifact' in item:
                            print(f"   ID: {item['artifact']['artifact_id'][:16]}...")
                            print(f"   What: {item['artifact']['sixw1h']['what'][:50]}...")
                        elif 'node' in item:
                            print(f"   Name: {item['node']['name']}")
            
            elif command.lower().startswith('file'):
                parts = command.split(maxsplit=2)
                if len(parts) < 2:
                    print("Usage: file <path> [depth]")
                    continue
                
                filepath = parts[1]
                depth = 2
                if len(parts) > 2:
                    try:
                        depth = int(parts[2])
                    except:
                        pass
                
                artifact = toolkit.analyze_file(filepath, depth)
                if artifact:
                    print(f"Analyzed: {artifact.sixw1h.what}")
                    print(f"Size: {artifact.size_bytes} bytes")
                    print(f"SHA256: {artifact.hash_sha256[:32]}...")
            
            elif command.lower().startswith('manifest'):
                parts = command.split()
                format = 'text'
                if len(parts) > 1:
                    format = parts[1]
                
                manifest = toolkit.generate_manifest(format)
                print(manifest[:2000] + "..." if len(manifest) > 2000 else manifest)
            
            elif command.lower().startswith('journal'):
                parts = command.split(maxsplit=2)
                if len(parts) < 2:
                    print("Usage: journal <add|query|stats> [args]")
                    continue
                
                subcmd = parts[1].lower()
                
                if subcmd == 'add' and len(parts) > 2:
                    toolkit.journal_add("user_entry", parts[2])
                    print("Journal entry added")
                
                elif subcmd == 'query' and len(parts) > 2:
                    result = toolkit.journal_query(parts[2])
                    print(f"Found {result['count']} journal entries")
                    for entry in result['results'][:3]:
                        time_str = entry['timestamp'].split('T')[1][:8]
                        print(f"  [{time_str}] {entry['entry_type']}: {entry['content'][:60]}...")
                
                elif subcmd == 'stats':
                    stats = toolkit.journal_stats()
                    print(f"Journal Statistics:")
                    print(f"  Total Entries: {stats['total_entries']}")
                    print(f"  By Type: {dict(stats['by_type'])}")
            
            elif command.lower() == 'export':
                export_path = toolkit.export_session()
                print(f"Exported to: {export_path}")
            
            elif command.lower() == 'stats':
                stats = toolkit.get_stats()
                print(f"Runtime: {stats['runtime_seconds']}s")
                print(f"Artifacts: {stats['artifacts_analyzed']}")
                print(f"Queries: {stats['queries_executed']}")
                print(f"Session Nodes: {stats['session_statistics']['taxonomic_nodes']}")
            
            elif command.lower() == 'save':
                toolkit.save()
                print("Session saved")
            
            else:
                print(f"Unknown command: {command}")
                print("Type 'help' for available commands")
        
        except KeyboardInterrupt:
            print("\nType 'exit' to quit")
            continue
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    main()