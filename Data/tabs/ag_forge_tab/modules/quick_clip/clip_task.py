#!/usr/bin/env python3
"""
Ollama Task Planner - Complete Integration System
Integrates Clipman, Taskwarrior, Ollama AI models, file tracking, and notifications
"""

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog, font
import json
import yaml
import os
import sys
import subprocess
import threading
import queue
import difflib
import time
import hashlib
from datetime import datetime, timedelta
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Any, Tuple
import sqlite3
from enum import Enum
import shlex
import re

# ============================================================================
# DATA MODELS AND ENUMS
# ============================================================================

class TaskStatus(Enum):
    PENDING = "pending"
    ACTIVE = "active"
    COMPLETED = "completed"
    DELETED = "deleted"
    WAITING = "waiting"

class ProfileType(Enum):
    CODE_REVIEW = "code_review"
    DOCUMENTATION = "documentation"
    PLANNING = "planning"
    DEBUGGING = "debugging"
    RESEARCH = "research"
    CUSTOM = "custom"

@dataclass
class Task:
    """Task data model"""
    id: str
    description: str
    status: TaskStatus
    created: datetime
    modified: datetime
    due: Optional[datetime] = None
    priority: str = "M"
    tags: List[str] = field(default_factory=list)
    project: str = ""
    dependencies: List[str] = field(default_factory=list)
    assigned_profile: Optional[str] = None
    notes: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class OllamaProfile:
    """Ollama model profile for specific task types"""
    name: str
    model: str
    profile_type: ProfileType
    system_prompt: str
    temperature: float = 0.7
    top_p: float = 0.9
    max_tokens: int = 2048
    context_window: int = 4096
    enabled: bool = True
    executable_paths: List[str] = field(default_factory=list)
    file_extensions: List[str] = field(default_factory=list)
    task_tags: List[str] = field(default_factory=list)
    auto_trigger: bool = False

@dataclass
class TrackedFile:
    """File tracking with task associations"""
    path: str
    task_id: str
    last_modified: datetime
    checksum: str
    profile_hint: Optional[str] = None
    annotations: List[str] = field(default_factory=list)

class OllamaPlannerGUI:
    """Main GUI Application"""
    
    def __init__(self, root):
        self.root = root
        self.root.title("Ollama Task Planner - Complete Integration Suite")
        self.root.geometry("1600x900")
        
        # Configuration paths
        self.config_dir = Path.home() / ".config" / "ollama-planner"
        self.config_dir.mkdir(parents=True, exist_ok=True)
        
        # Database
        self.db_path = self.config_dir / "planner.db"
        self.init_database()
        
        # State management
        self.current_task = None
        self.profiles: Dict[str, OllamaProfile] = {}
        self.tasks: Dict[str, Task] = {}
        self.tracked_files: Dict[str, TrackedFile] = {}
        self.clipboard_history = []
        self.ollama_models = []
        
        # Thread-safe queues
        self.task_queue = queue.Queue()
        self.notification_queue = queue.Queue()
        
        # Initialize components
        self.load_profiles()
        self.load_tasks()
        self.load_tracked_files()
        
        # Set up GUI
        self.setup_styles()
        self.setup_main_window()
        self.setup_menus()
        
        # Start background services
        self.start_background_services()
        
        # Initial updates
        self.refresh_ollama_models()
        self.update_status("Ready - System Initialized")
    
    # ============================================================================
    # DATABASE MANAGEMENT
    # ============================================================================
    
    def init_database(self):
        """Initialize SQLite database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Tasks table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS tasks (
                id TEXT PRIMARY KEY,
                description TEXT,
                status TEXT,
                created TIMESTAMP,
                modified TIMESTAMP,
                due TIMESTAMP,
                priority TEXT,
                tags TEXT,
                project TEXT,
                dependencies TEXT,
                assigned_profile TEXT,
                notes TEXT,
                metadata TEXT
            )
        ''')
        
        # Profiles table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS profiles (
                name TEXT PRIMARY KEY,
                model TEXT,
                profile_type TEXT,
                system_prompt TEXT,
                temperature REAL,
                top_p REAL,
                max_tokens INTEGER,
                context_window INTEGER,
                enabled INTEGER,
                executable_paths TEXT,
                file_extensions TEXT,
                task_tags TEXT,
                auto_trigger INTEGER
            )
        ''')
        
        # Files table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS tracked_files (
                path TEXT PRIMARY KEY,
                task_id TEXT,
                last_modified TIMESTAMP,
                checksum TEXT,
                profile_hint TEXT,
                annotations TEXT
            )
        ''')
        
        # Clipboard history
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS clipboard_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                content TEXT,
                timestamp TIMESTAMP,
                source TEXT,
                task_id TEXT
            )
        ''')
        
        conn.commit()
        conn.close()
    
    # ============================================================================
    # DATA LOADING/SAVING
    # ============================================================================
    
    def load_profiles(self):
        """Load profiles from database"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM profiles")
            rows = cursor.fetchall()
            
            self.profiles = {}
            for row in rows:
                profile = OllamaProfile(
                    name=row[0],
                    model=row[1],
                    profile_type=ProfileType(row[2]),
                    system_prompt=row[3],
                    temperature=row[4],
                    top_p=row[5],
                    max_tokens=row[6],
                    context_window=row[7],
                    enabled=bool(row[8]),
                    executable_paths=json.loads(row[9]) if row[9] else [],
                    file_extensions=json.loads(row[10]) if row[10] else [],
                    task_tags=json.loads(row[11]) if row[11] else [],
                    auto_trigger=bool(row[12])
                )
                self.profiles[profile.name] = profile
            
            # Load default profiles if none exist
            if not self.profiles:
                self.create_default_profiles()
                self.save_profiles()
            
            conn.close()
        except Exception as e:
            print(f"Error loading profiles: {e}")
            self.create_default_profiles()
    
    def create_default_profiles(self):
        """Create default Ollama profiles"""
        default_profiles = [
            OllamaProfile(
                name="Code Assistant",
                model="codellama",
                profile_type=ProfileType.CODE_REVIEW,
                system_prompt="You are an expert code assistant. Review code, suggest improvements, and write clean, efficient code.",
                executable_paths=["/usr/bin/python3", "/usr/bin/node", "/usr/bin/gcc"],
                file_extensions=[".py", ".js", ".java", ".cpp", ".c", ".rs", ".go"],
                task_tags=["code", "develop", "programming", "bug", "fix"]
            ),
            OllamaProfile(
                name="Documentation Writer",
                model="llama2",
                profile_type=ProfileType.DOCUMENTATION,
                system_prompt="You are a technical writer. Create clear, comprehensive documentation and explanations.",
                file_extensions=[".md", ".txt", ".rst", ".tex"],
                task_tags=["docs", "documentation", "write", "explain"]
            ),
            OllamaProfile(
                name="System Planner",
                model="mistral",
                profile_type=ProfileType.PLANNING,
                system_prompt="You are a system architect and planner. Analyze requirements and create implementation plans.",
                task_tags=["plan", "design", "architecture", "system"]
            ),
            OllamaProfile(
                name="Research Assistant",
                model="neural-chat",
                profile_type=ProfileType.RESEARCH,
                system_prompt="You are a research assistant. Gather information, analyze data, and provide insights.",
                task_tags=["research", "analyze", "study", "investigate"]
            )
        ]
        
        for profile in default_profiles:
            self.profiles[profile.name] = profile
    
    def save_profiles(self):
        """Save profiles to database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("DELETE FROM profiles")
        
        for profile in self.profiles.values():
            cursor.execute('''
                INSERT INTO profiles VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                profile.name,
                profile.model,
                profile.profile_type.value,
                profile.system_prompt,
                profile.temperature,
                profile.top_p,
                profile.max_tokens,
                profile.context_window,
                int(profile.enabled),
                json.dumps(profile.executable_paths),
                json.dumps(profile.file_extensions),
                json.dumps(profile.task_tags),
                int(profile.auto_trigger)
            ))
        
        conn.commit()
        conn.close()
    
    def load_tasks(self):
        """Load tasks from Taskwarrior and database"""
        # First try to load from Taskwarrior
        self.tasks = self.load_tasks_from_taskwarrior()
        
        # If Taskwarrior not available, load from database
        if not self.tasks:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM tasks")
            rows = cursor.fetchall()
            
            for row in rows:
                task = Task(
                    id=row[0],
                    description=row[1],
                    status=TaskStatus(row[2]),
                    created=datetime.fromisoformat(row[3]),
                    modified=datetime.fromisoformat(row[4]),
                    due=datetime.fromisoformat(row[5]) if row[5] else None,
                    priority=row[6],
                    tags=json.loads(row[7]) if row[7] else [],
                    project=row[8],
                    dependencies=json.loads(row[9]) if row[9] else [],
                    assigned_profile=row[10],
                    notes=row[11],
                    metadata=json.loads(row[12]) if row[12] else {}
                )
                self.tasks[task.id] = task
            
            conn.close()
    
    def load_tasks_from_taskwarrior(self) -> Dict[str, Task]:
        """Load tasks from Taskwarrior CLI"""
        tasks = {}
        try:
            # Export tasks from Taskwarrior
            result = subprocess.run(
                ['task', 'export'],
                capture_output=True,
                text=True,
                check=True
            )
            
            task_data = json.loads(result.stdout)
            
            for item in task_data:
                task_id = str(item.get('id', item.get('uuid', '')))
                if task_id:
                    task = Task(
                        id=task_id,
                        description=item.get('description', ''),
                        status=TaskStatus(item.get('status', 'pending')),
                        created=datetime.fromisoformat(item.get('entry', datetime.now().isoformat())),
                        modified=datetime.now(),
                        due=datetime.fromisoformat(item['due']) if 'due' in item else None,
                        priority=item.get('priority', 'M'),
                        tags=item.get('tags', []),
                        project=item.get('project', ''),
                        dependencies=item.get('depends', []),
                        assigned_profile=None,
                        notes=item.get('annotations', ''),
                        metadata={}
                    )
                    tasks[task.id] = task
            
            return tasks
        except (subprocess.CalledProcessError, FileNotFoundError, json.JSONDecodeError):
            print("Taskwarrior not available, using local database")
            return {}
    
    def load_tracked_files(self):
        """Load tracked files from database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM tracked_files")
        rows = cursor.fetchall()
        
        self.tracked_files = {}
        for row in rows:
            file = TrackedFile(
                path=row[0],
                task_id=row[1],
                last_modified=datetime.fromisoformat(row[2]),
                checksum=row[3],
                profile_hint=row[4],
                annotations=json.loads(row[5]) if row[5] else []
            )
            self.tracked_files[file.path] = file
        
        conn.close()
    
    # ============================================================================
    # GUI SETUP
    # ============================================================================
    
    def setup_styles(self):
        """Configure ttk styles"""
        style = ttk.Style()
        
        # Configure colors
        self.root.configure(bg='#2b2b2b')
        
        # Define custom styles
        style.theme_use('clam')
        
        # Configure colors
        style.configure('Main.TFrame', background='#2b2b2b')
        style.configure('Header.TLabel', 
                       background='#3c3c3c', 
                       foreground='white',
                       font=('Helvetica', 12, 'bold'))
        
        style.configure('Task.Treeview',
                      background='#2b2b2b',
                      foreground='white',
                      fieldbackground='#2b2b2b')
        
        style.map('Task.Treeview',
                 background=[('selected', '#4a6984')])
        
        style.configure('Red.TButton',
                       background='#d32f2f',
                       foreground='white')
        style.map('Red.TButton',
                 background=[('active', '#f44336')])
        
        style.configure('Green.TButton',
                       background='#388e3c',
                       foreground='white')
        style.map('Green.TButton',
                 background=[('active', '#4caf50')])
        
        style.configure('Blue.TButton',
                       background='#1976d2',
                       foreground='white')
        style.map('Blue.TButton',
                 background=[('active', '#2196f3')])
    
    def setup_main_window(self):
        """Set up the main window with notebook tabs"""
        # Create main container with status bar
        self.main_container = ttk.Frame(self.root)
        self.main_container.pack(fill='both', expand=True)
        
        # Create notebook for tabs
        self.notebook = ttk.Notebook(self.main_container)
        self.notebook.pack(fill='both', expand=True, padx=5, pady=5)
        
        # Create all tabs
        self.create_task_dashboard_tab()
        self.create_clipman_integration_tab()
        self.create_profile_management_tab()
        self.create_file_tracking_tab()
        self.create_agent_control_tab()
        self.create_ollama_chat_tab()
        
        # Status bar
        self.status_frame = ttk.Frame(self.root)
        self.status_frame.pack(side='bottom', fill='x')
        
        self.status_label = ttk.Label(
            self.status_frame, 
            text="Ready",
            relief='sunken',
            anchor='w'
        )
        self.status_label.pack(side='left', fill='x', expand=True, padx=2)
        
        self.task_count_label = ttk.Label(
            self.status_frame,
            text="Tasks: 0",
            relief='sunken',
            width=15
        )
        self.task_count_label.pack(side='right', padx=2)
        
        self.profile_count_label = ttk.Label(
            self.status_frame,
            text="Profiles: 0",
            relief='sunken',
            width=15
        )
        self.profile_count_label.pack(side='right', padx=2)
    
    def create_task_dashboard_tab(self):
        """Create task dashboard tab"""
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text="📋 Task Dashboard")
        
        # Top control panel
        control_frame = ttk.Frame(frame)
        control_frame.pack(fill='x', padx=10, pady=10)
        
        ttk.Button(control_frame, text="Refresh Tasks", 
                  command=self.refresh_tasks).pack(side='left', padx=5)
        
        ttk.Button(control_frame, text="New Task", 
                  command=self.create_new_task).pack(side='left', padx=5)
        
        ttk.Button(control_frame, text="Import from Taskwarrior", 
                  command=self.import_taskwarrior).pack(side='left', padx=5)
        
        ttk.Button(control_frame, text="Export to Taskwarrior", 
                  command=self.export_to_taskwarrior).pack(side='left', padx=5)
        
        # Search/filter
        filter_frame = ttk.Frame(frame)
        filter_frame.pack(fill='x', padx=10, pady=(0, 10))
        
        ttk.Label(filter_frame, text="Filter:").pack(side='left', padx=5)
        self.task_filter_var = tk.StringVar()
        self.task_filter_entry = ttk.Entry(filter_frame, 
                                         textvariable=self.task_filter_var,
                                         width=30)
        self.task_filter_entry.pack(side='left', padx=5)
        self.task_filter_entry.bind('<KeyRelease>', lambda e: self.filter_tasks())
        
        # Task list treeview
        tree_frame = ttk.Frame(frame)
        tree_frame.pack(fill='both', expand=True, padx=10, pady=(0, 10))
        
        columns = ('id', 'description', 'status', 'priority', 'project', 'due', 'profile')
        self.task_tree = ttk.Treeview(tree_frame, columns=columns, show='headings', height=15)
        
        # Define headings
        self.task_tree.heading('id', text='ID', command=lambda: self.sort_tasks('id'))
        self.task_tree.heading('description', text='Description', command=lambda: self.sort_tasks('description'))
        self.task_tree.heading('status', text='Status', command=lambda: self.sort_tasks('status'))
        self.task_tree.heading('priority', text='Priority', command=lambda: self.sort_tasks('priority'))
        self.task_tree.heading('project', text='Project', command=lambda: self.sort_tasks('project'))
        self.task_tree.heading('due', text='Due Date', command=lambda: self.sort_tasks('due'))
        self.task_tree.heading('profile', text='Profile', command=lambda: self.sort_tasks('profile'))
        
        # Define columns
        self.task_tree.column('id', width=50)
        self.task_tree.column('description', width=300)
        self.task_tree.column('status', width=80)
        self.task_tree.column('priority', width=60)
        self.task_tree.column('project', width=100)
        self.task_tree.column('due', width=100)
        self.task_tree.column('profile', width=100)
        
        # Scrollbars
        tree_scroll_y = ttk.Scrollbar(tree_frame, orient='vertical', command=self.task_tree.yview)
        tree_scroll_x = ttk.Scrollbar(tree_frame, orient='horizontal', command=self.task_tree.xview)
        self.task_tree.configure(yscrollcommand=tree_scroll_y.set, xscrollcommand=tree_scroll_x.set)
        
        # Grid layout
        self.task_tree.grid(row=0, column=0, sticky='nsew')
        tree_scroll_y.grid(row=0, column=1, sticky='ns')
        tree_scroll_x.grid(row=1, column=0, sticky='ew')
        
        tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)
        
        # Bind selection
        self.task_tree.bind('<<TreeviewSelect>>', self.on_task_select)
        
        # Task details panel
        details_frame = ttk.LabelFrame(frame, text="Task Details")
        details_frame.pack(fill='x', padx=10, pady=10)
        
        # Details in grid
        details_inner = ttk.Frame(details_frame)
        details_inner.pack(fill='x', padx=5, pady=5)
        
        # Description
        ttk.Label(details_inner, text="Description:").grid(row=0, column=0, sticky='w', pady=2)
        self.task_desc_var = tk.StringVar()
        ttk.Entry(details_inner, textvariable=self.task_desc_var, width=60).grid(row=0, column=1, padx=5, pady=2)
        
        # Status
        ttk.Label(details_inner, text="Status:").grid(row=1, column=0, sticky='w', pady=2)
        self.task_status_var = tk.StringVar()
        status_combo = ttk.Combobox(details_inner, textvariable=self.task_status_var,
                                  values=[s.value for s in TaskStatus], width=15)
        status_combo.grid(row=1, column=1, sticky='w', padx=5, pady=2)
        
        # Priority
        ttk.Label(details_inner, text="Priority:").grid(row=1, column=2, sticky='w', padx=20, pady=2)
        self.task_priority_var = tk.StringVar(value='M')
        priority_combo = ttk.Combobox(details_inner, textvariable=self.task_priority_var,
                                    values=['H', 'M', 'L'], width=5)
        priority_combo.grid(row=1, column=3, sticky='w', pady=2)
        
        # Profile assignment
        ttk.Label(details_inner, text="AI Profile:").grid(row=2, column=0, sticky='w', pady=2)
        self.task_profile_var = tk.StringVar()
        profile_combo = ttk.Combobox(details_inner, textvariable=self.task_profile_var,
                                   values=list(self.profiles.keys()), width=20)
        profile_combo.grid(row=2, column=1, sticky='w', padx=5, pady=2)
        
        # Due date
        ttk.Label(details_inner, text="Due Date:").grid(row=2, column=2, sticky='w', padx=20, pady=2)
        self.task_due_var = tk.StringVar()
        ttk.Entry(details_inner, textvariable=self.task_due_var, width=15).grid(row=2, column=3, sticky='w', pady=2)
        
        # Notes
        ttk.Label(details_inner, text="Notes:").grid(row=3, column=0, sticky='nw', pady=2)
        self.task_notes_text = scrolledtext.ScrolledText(details_inner, width=60, height=4)
        self.task_notes_text.grid(row=3, column=1, columnspan=3, padx=5, pady=2, sticky='ew')
        
        # Tags
        ttk.Label(details_inner, text="Tags:").grid(row=4, column=0, sticky='w', pady=2)
        self.task_tags_var = tk.StringVar()
        ttk.Entry(details_inner, textvariable=self.task_tags_var, width=60).grid(row=4, column=1, columnspan=3, padx=5, pady=2, sticky='w')
        
        # Action buttons
        button_frame = ttk.Frame(details_frame)
        button_frame.pack(fill='x', padx=5, pady=5)
        
        ttk.Button(button_frame, text="Update Task", 
                  command=self.update_selected_task, style='Green.TButton').pack(side='left', padx=5)
        
        ttk.Button(button_frame, text="Complete Task", 
                  command=self.complete_selected_task).pack(side='left', padx=5)
        
        ttk.Button(button_frame, text="Delete Task", 
                  command=self.delete_selected_task, style='Red.TButton').pack(side='left', padx=5)
        
        ttk.Button(button_frame, text="Run Profile on Task", 
                  command=self.run_profile_on_task).pack(side='left', padx=5)
        
        # Initial refresh
        self.refresh_task_tree()
    
    def create_clipman_integration_tab(self):
        """Create Clipman integration tab"""
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text="📋 Clipman Integration")
        
        # Control panel
        control_frame = ttk.Frame(frame)
        control_frame.pack(fill='x', padx=10, pady=10)
        
        ttk.Button(control_frame, text="Start Monitoring", 
                  command=self.start_clipman_monitoring).pack(side='left', padx=5)
        
        ttk.Button(control_frame, text="Stop Monitoring", 
                  command=self.stop_clipman_monitoring).pack(side='left', padx=5)
        
        ttk.Button(control_frame, text="Clear History", 
                  command=self.clear_clipboard_history).pack(side='left', padx=5)
        
        ttk.Checkbutton(control_frame, text="Auto-process new clips", 
                       variable=tk.BooleanVar(value=True)).pack(side='left', padx=20)
        
        # Clipboard history display
        history_frame = ttk.LabelFrame(frame, text="Clipboard History")
        history_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Treeview for clipboard history
        columns = ('time', 'content_preview', 'source', 'task')
        self.clip_tree = ttk.Treeview(history_frame, columns=columns, show='headings', height=10)
        
        self.clip_tree.heading('time', text='Time')
        self.clip_tree.heading('content_preview', text='Content')
        self.clip_tree.heading('source', text='Source')
        self.clip_tree.heading('task', text='Task')
        
        self.clip_tree.column('time', width=120)
        self.clip_tree.column('content_preview', width=400)
        self.clip_tree.column('source', width=100)
        self.clip_tree.column('task', width=100)
        
        # Scrollbars
        clip_scroll_y = ttk.Scrollbar(history_frame, orient='vertical', command=self.clip_tree.yview)
        clip_scroll_x = ttk.Scrollbar(history_frame, orient='horizontal', command=self.clip_tree.xview)
        self.clip_tree.configure(yscrollcommand=clip_scroll_y.set, xscrollcommand=clip_scroll_x.set)
        
        self.clip_tree.grid(row=0, column=0, sticky='nsew')
        clip_scroll_y.grid(row=0, column=1, sticky='ns')
        clip_scroll_x.grid(row=1, column=0, sticky='ew')
        
        history_frame.grid_rowconfigure(0, weight=1)
        history_frame.grid_columnconfigure(0, weight=1)
        
        # Bind selection
        self.clip_tree.bind('<<TreeviewSelect>>', self.on_clip_select)
        
        # Action panel
        action_frame = ttk.Frame(frame)
        action_frame.pack(fill='x', padx=10, pady=10)
        
        ttk.Button(action_frame, text="Create Task from Clip", 
                  command=self.create_task_from_clip).pack(side='left', padx=5)
        
        ttk.Button(action_frame, text="Analyze with AI", 
                  command=self.analyze_clipboard).pack(side='left', padx=5)
        
        ttk.Button(action_frame, text="Save to File", 
                  command=self.save_clip_to_file).pack(side='left', padx=5)
        
        # Preview area
        preview_frame = ttk.LabelFrame(frame, text="Clip Preview")
        preview_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        self.clip_preview_text = scrolledtext.ScrolledText(preview_frame, width=80, height=10)
        self.clip_preview_text.pack(fill='both', expand=True, padx=5, pady=5)
    
    def create_profile_management_tab(self):
        """Create profile management tab"""
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text="⚙️ Profile Management")
        
        # Split view
        paned = ttk.PanedWindow(frame, orient='horizontal')
        paned.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Left panel - Profile list
        list_frame = ttk.Frame(paned)
        
        # Control buttons
        list_control_frame = ttk.Frame(list_frame)
        list_control_frame.pack(fill='x', pady=(0, 10))
        
        ttk.Button(list_control_frame, text="New Profile", 
                  command=self.create_new_profile).pack(side='left', padx=2)
        
        ttk.Button(list_control_frame, text="Delete Profile", 
                  command=self.delete_profile).pack(side='left', padx=2)
        
        ttk.Button(list_control_frame, text="Duplicate Profile", 
                  command=self.duplicate_profile).pack(side='left', padx=2)
        
        # Profile list treeview
        profile_tree_frame = ttk.Frame(list_frame)
        profile_tree_frame.pack(fill='both', expand=True)
        
        columns = ('name', 'model', 'type', 'enabled')
        self.profile_tree = ttk.Treeview(profile_tree_frame, columns=columns, show='headings', height=15)
        
        self.profile_tree.heading('name', text='Name')
        self.profile_tree.heading('model', text='Ollama Model')
        self.profile_tree.heading('type', text='Type')
        self.profile_tree.heading('enabled', text='Enabled')
        
        self.profile_tree.column('name', width=150)
        self.profile_tree.column('model', width=100)
        self.profile_tree.column('type', width=100)
        self.profile_tree.column('enabled', width=60)
        
        # Scrollbars
        profile_scroll_y = ttk.Scrollbar(profile_tree_frame, orient='vertical', command=self.profile_tree.yview)
        self.profile_tree.configure(yscrollcommand=profile_scroll_y.set)
        
        self.profile_tree.grid(row=0, column=0, sticky='nsew')
        profile_scroll_y.grid(row=0, column=1, sticky='ns')
        
        profile_tree_frame.grid_rowconfigure(0, weight=1)
        profile_tree_frame.grid_columnconfigure(0, weight=1)
        
        self.profile_tree.bind('<<TreeviewSelect>>', self.on_profile_select)
        
        paned.add(list_frame, weight=1)
        
        # Right panel - Profile editor
        editor_frame = ttk.Frame(paned)
        
        # Editor notebook for different sections
        editor_notebook = ttk.Notebook(editor_frame)
        editor_notebook.pack(fill='both', expand=True)
        
        # Basic info tab
        basic_frame = ttk.Frame(editor_notebook)
        editor_notebook.add(basic_frame, text="Basic")
        
        # Name
        ttk.Label(basic_frame, text="Profile Name:").grid(row=0, column=0, sticky='w', pady=5, padx=5)
        self.profile_name_var = tk.StringVar()
        ttk.Entry(basic_frame, textvariable=self.profile_name_var, width=30).grid(row=0, column=1, pady=5, padx=5)
        
        # Model selection
        ttk.Label(basic_frame, text="Ollama Model:").grid(row=1, column=0, sticky='w', pady=5, padx=5)
        self.profile_model_var = tk.StringVar()
        self.model_combo = ttk.Combobox(basic_frame, textvariable=self.profile_model_var, width=30)
        self.model_combo.grid(row=1, column=1, pady=5, padx=5)
        
        # Profile type
        ttk.Label(basic_frame, text="Profile Type:").grid(row=2, column=0, sticky='w', pady=5, padx=5)
        self.profile_type_var = tk.StringVar()
        type_combo = ttk.Combobox(basic_frame, textvariable=self.profile_type_var,
                                 values=[t.value for t in ProfileType], width=30)
        type_combo.grid(row=2, column=1, pady=5, padx=5)
        
        # Enabled
        self.profile_enabled_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(basic_frame, text="Enabled", 
                       variable=self.profile_enabled_var).grid(row=3, column=0, columnspan=2, pady=5, padx=5)
        
        # Auto-trigger
        self.profile_auto_trigger_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(basic_frame, text="Auto-trigger on matching tasks", 
                       variable=self.profile_auto_trigger_var).grid(row=4, column=0, columnspan=2, pady=5, padx=5)
        
        # System prompt tab
        prompt_frame = ttk.Frame(editor_notebook)
        editor_notebook.add(prompt_frame, text="System Prompt")
        
        self.profile_prompt_text = scrolledtext.ScrolledText(prompt_frame, width=60, height=15)
        self.profile_prompt_text.pack(fill='both', expand=True, padx=5, pady=5)
        
        # Configuration tab
        config_frame = ttk.Frame(editor_notebook)
        editor_notebook.add(config_frame, text="Configuration")
        
        # Temperature
        ttk.Label(config_frame, text="Temperature:").grid(row=0, column=0, sticky='w', pady=5, padx=5)
        self.profile_temp_var = tk.DoubleVar(value=0.7)
        ttk.Scale(config_frame, from_=0.0, to=2.0, variable=self.profile_temp_var, 
                 orient='horizontal', length=200).grid(row=0, column=1, pady=5, padx=5)
        ttk.Label(config_frame, textvariable=self.profile_temp_var).grid(row=0, column=2, padx=5)
        
        # Max tokens
        ttk.Label(config_frame, text="Max Tokens:").grid(row=1, column=0, sticky='w', pady=5, padx=5)
        self.profile_max_tokens_var = tk.IntVar(value=2048)
        ttk.Entry(config_frame, textvariable=self.profile_max_tokens_var, width=10).grid(row=1, column=1, sticky='w', pady=5, padx=5)
        
        # File extensions
        ttk.Label(config_frame, text="File Extensions:").grid(row=2, column=0, sticky='nw', pady=5, padx=5)
        self.profile_extensions_var = tk.StringVar()
        ttk.Entry(config_frame, textvariable=self.profile_extensions_var, width=30).grid(row=2, column=1, pady=5, padx=5)
        
        # Task tags
        ttk.Label(config_frame, text="Task Tags:").grid(row=3, column=0, sticky='nw', pady=5, padx=5)
        self.profile_tags_var = tk.StringVar()
        ttk.Entry(config_frame, textvariable=self.profile_tags_var, width=30).grid(row=3, column=1, pady=5, padx=5)
        
        # Executable paths
        ttk.Label(config_frame, text="Executable Paths:").grid(row=4, column=0, sticky='nw', pady=5, padx=5)
        self.profile_executables_var = tk.StringVar()
        ttk.Entry(config_frame, textvariable=self.profile_executables_var, width=30).grid(row=4, column=1, pady=5, padx=5)
        
        # Save button
        ttk.Button(editor_frame, text="Save Profile", 
                  command=self.save_profile_editor, style='Green.TButton').pack(pady=10)
        
        paned.add(editor_frame, weight=2)
        
        # Refresh profile list
        self.refresh_profile_tree()
    
    def create_file_tracking_tab(self):
        """Create file tracking tab"""
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text="📁 File Tracking")
        
        # Control panel
        control_frame = ttk.Frame(frame)
        control_frame.pack(fill='x', padx=10, pady=10)
        
        ttk.Button(control_frame, text="Add Files", 
                  command=self.add_files_to_tracking).pack(side='left', padx=5)
        
        ttk.Button(control_frame, text="Add Directory", 
                  command=self.add_directory_to_tracking).pack(side='left', padx=5)
        
        ttk.Button(control_frame, text="Remove Selected", 
                  command=self.remove_tracked_files).pack(side='left', padx=5)
        
        ttk.Button(control_frame, text="Scan for Changes", 
                  command=self.scan_file_changes).pack(side='left', padx=5)
        
        # File tree
        tree_frame = ttk.LabelFrame(frame, text="Tracked Files")
        tree_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        columns = ('path', 'task', 'modified', 'profile_hint')
        self.file_tree = ttk.Treeview(tree_frame, columns=columns, show='headings', height=15)
        
        self.file_tree.heading('path', text='Path')
        self.file_tree.heading('task', text='Task')
        self.file_tree.heading('modified', text='Last Modified')
        self.file_tree.heading('profile_hint', text='Profile Hint')
        
        self.file_tree.column('path', width=400)
        self.file_tree.column('task', width=100)
        self.file_tree.column('modified', width=150)
        self.file_tree.column('profile_hint', width=100)
        
        # Scrollbars
        file_scroll_y = ttk.Scrollbar(tree_frame, orient='vertical', command=self.file_tree.yview)
        file_scroll_x = ttk.Scrollbar(tree_frame, orient='horizontal', command=self.file_tree.xview)
        self.file_tree.configure(yscrollcommand=file_scroll_y.set, xscrollcommand=file_scroll_x.set)
        
        self.file_tree.grid(row=0, column=0, sticky='nsew')
        file_scroll_y.grid(row=0, column=1, sticky='ns')
        file_scroll_x.grid(row=1, column=0, sticky='ew')
        
        tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)
        
        self.file_tree.bind('<<TreeviewSelect>>', self.on_file_select)
        
        # Action panel
        action_frame = ttk.Frame(frame)
        action_frame.pack(fill='x', padx=10, pady=10)
        
        ttk.Button(action_frame, text="Assign to Task", 
                  command=self.assign_file_to_task).pack(side='left', padx=5)
        
        ttk.Button(action_frame, text="Set Profile Hint", 
                  command=self.set_file_profile_hint).pack(side='left', padx=5)
        
        ttk.Button(action_frame, text="Run Profile on File", 
                  command=self.run_profile_on_file).pack(side='left', padx=5)
        
        ttk.Button(action_frame, text="Compare with Previous", 
                  command=self.compare_file_versions).pack(side='left', padx=5)
        
        # Refresh file list
        self.refresh_file_tree()
    
    def create_agent_control_tab(self):
        """Create agent control center tab"""
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text="🎮 Agent Control")
        
        # Split view
        paned = ttk.PanedWindow(frame, orient='vertical')
        paned.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Top panel - Active agents
        agents_frame = ttk.LabelFrame(paned, text="Active Agents")
        
        # Agent list
        self.agent_listbox = tk.Listbox(agents_frame, height=8)
        self.agent_listbox.pack(fill='both', expand=True, padx=5, pady=5)
        
        # Agent controls
        agent_control_frame = ttk.Frame(agents_frame)
        agent_control_frame.pack(fill='x', padx=5, pady=5)
        
        ttk.Button(agent_control_frame, text="Start Agent", 
                  command=self.start_agent).pack(side='left', padx=2)
        
        ttk.Button(agent_control_frame, text="Stop Agent", 
                  command=self.stop_agent).pack(side='left', padx=2)
        
        ttk.Button(agent_control_frame, text="Restart Agent", 
                  command=self.restart_agent).pack(side='left', padx=2)
        
        ttk.Button(agent_control_frame, text="View Logs", 
                  command=self.view_agent_logs).pack(side='left', padx=2)
        
        paned.add(agents_frame, weight=1)
        
        # Bottom panel - System monitor
        monitor_frame = ttk.LabelFrame(paned, text="System Monitor")
        
        # Monitoring controls
        monitor_control_frame = ttk.Frame(monitor_frame)
        monitor_control_frame.pack(fill='x', padx=5, pady=5)
        
        ttk.Button(monitor_control_frame, text="Start Monitoring", 
                  command=self.start_system_monitoring).pack(side='left', padx=2)
        
        ttk.Button(monitor_control_frame, text="Stop Monitoring", 
                  command=self.stop_system_monitoring).pack(side='left', padx=2)
        
        # Resource display
        resource_frame = ttk.Frame(monitor_frame)
        resource_frame.pack(fill='both', expand=True, padx=5, pady=5)
        
        # CPU usage
        ttk.Label(resource_frame, text="CPU Usage:").grid(row=0, column=0, sticky='w', pady=2)
        self.cpu_var = tk.StringVar(value="0%")
        ttk.Label(resource_frame, textvariable=self.cpu_var).grid(row=0, column=1, sticky='w', padx=10, pady=2)
        
        # Memory usage
        ttk.Label(resource_frame, text="Memory Usage:").grid(row=1, column=0, sticky='w', pady=2)
        self.memory_var = tk.StringVar(value="0 MB")
        ttk.Label(resource_frame, textvariable=self.memory_var).grid(row=1, column=1, sticky='w', padx=10, pady=2)
        
        # Ollama status
        ttk.Label(resource_frame, text="Ollama Status:").grid(row=2, column=0, sticky='w', pady=2)
        self.ollama_status_var = tk.StringVar(value="Unknown")
        ttk.Label(resource_frame, textvariable=self.ollama_status_var).grid(row=2, column=1, sticky='w', padx=10, pady=2)
        
        # Active models
        ttk.Label(resource_frame, text="Active Models:").grid(row=3, column=0, sticky='w', pady=2)
        self.active_models_var = tk.StringVar(value="0")
        ttk.Label(resource_frame, textvariable=self.active_models_var).grid(row=3, column=1, sticky='w', padx=10, pady=2)
        
        paned.add(monitor_frame, weight=1)
        
        # Auto-refresh
        self.update_system_monitor()
    
    def create_ollama_chat_tab(self):
        """Create Ollama chat interface tab"""
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text="🤖 Ollama Chat")
        
        # Top control panel
        chat_control_frame = ttk.Frame(frame)
        chat_control_frame.pack(fill='x', padx=10, pady=10)
        
        # Model selection
        ttk.Label(chat_control_frame, text="Model:").pack(side='left', padx=5)
        self.chat_model_var = tk.StringVar()
        self.chat_model_combo = ttk.Combobox(chat_control_frame, textvariable=self.chat_model_var, width=20)
        self.chat_model_combo.pack(side='left', padx=5)
        
        # Profile selection
        ttk.Label(chat_control_frame, text="Profile:").pack(side='left', padx=5)
        self.chat_profile_var = tk.StringVar()
        chat_profile_combo = ttk.Combobox(chat_control_frame, textvariable=self.chat_profile_var,
                                         values=list(self.profiles.keys()), width=20)
        chat_profile_combo.pack(side='left', padx=5)
        
        # Temperature
        ttk.Label(chat_control_frame, text="Temp:").pack(side='left', padx=5)
        self.chat_temp_var = tk.DoubleVar(value=0.7)
        ttk.Scale(chat_control_frame, from_=0.0, to=2.0, variable=self.chat_temp_var,
                 orient='horizontal', length=100).pack(side='left', padx=5)
        
        # Chat area
        chat_frame = ttk.Frame(frame)
        chat_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Conversation display
        self.chat_display = scrolledtext.ScrolledText(chat_frame, width=80, height=20, wrap='word')
        self.chat_display.pack(fill='both', expand=True, pady=(0, 10))
        self.chat_display.config(state='disabled')
        
        # Input area
        input_frame = ttk.Frame(chat_frame)
        input_frame.pack(fill='x', pady=5)
        
        self.chat_input = scrolledtext.ScrolledText(input_frame, width=80, height=4, wrap='word')
        self.chat_input.pack(side='left', fill='both', expand=True)
        
        # Send button
        ttk.Button(input_frame, text="Send", 
                  command=self.send_chat_message, style='Blue.TButton').pack(side='right', padx=5)
        
        # Action buttons
        action_frame = ttk.Frame(frame)
        action_frame.pack(fill='x', padx=10, pady=10)
        
        ttk.Button(action_frame, text="Clear Chat", 
                  command=self.clear_chat).pack(side='left', padx=5)
        
        ttk.Button(action_frame, text="Load Context from Task", 
                  command=self.load_chat_context).pack(side='left', padx=5)
        
        ttk.Button(action_frame, text="Save Conversation", 
                  command=self.save_conversation).pack(side='left', padx=5)
        
        ttk.Button(action_frame, text="Execute Code", 
                  command=self.execute_chat_code).pack(side='left', padx=5)
        
        # Initial model refresh
        self.refresh_chat_models()
    
    def setup_menus(self):
        """Set up menu bar"""
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        
        # File menu
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="Save Configuration", command=self.save_configuration)
        file_menu.add_command(label="Load Configuration", command=self.load_configuration)
        file_menu.add_separator()
        file_menu.add_command(label="Export Tasks...", command=self.export_tasks)
        file_menu.add_command(label="Import Tasks...", command=self.import_tasks)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.root.quit)
        
        # Tools menu
        tools_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Tools", menu=tools_menu)
        tools_menu.add_command(label="Scan for Ollama Models", command=self.refresh_ollama_models)
        tools_menu.add_command(label="Sync with Taskwarrior", command=self.sync_taskwarrior)
        tools_menu.add_command(label="Cleanup Database", command=self.cleanup_database)
        tools_menu.add_separator()
        tools_menu.add_command(label="Run Diagnostics", command=self.run_diagnostics)
        
        # View menu
        view_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="View", menu=view_menu)
        view_menu.add_command(label="Refresh All", command=self.refresh_all)
        view_menu.add_separator()
        view_menu.add_command(label="Show Notifications", command=self.show_notifications)
        view_menu.add_command(label="Show Logs", command=self.show_logs)
        
        # Help menu
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Help", menu=help_menu)
        help_menu.add_command(label="Documentation", command=self.show_documentation)
        help_menu.add_command(label="About", command=self.show_about)
    
    # ============================================================================
    # TASK MANAGEMENT FUNCTIONS
    # ============================================================================
    
    def refresh_task_tree(self):
        """Refresh the task treeview"""
        # Clear existing items
        for item in self.task_tree.get_children():
            self.task_tree.delete(item)
        
        # Filter tasks
        filter_text = self.task_filter_var.get().lower()
        filtered_tasks = []
        
        for task in self.tasks.values():
            if filter_text:
                if (filter_text in task.description.lower() or 
                    filter_text in task.project.lower() or 
                    any(filter_text in tag.lower() for tag in task.tags)):
                    filtered_tasks.append(task)
            else:
                filtered_tasks.append(task)
        
        # Add tasks to tree
        for task in filtered_tasks:
            due_str = task.due.strftime("%Y-%m-%d") if task.due else ""
            self.task_tree.insert('', 'end', values=(
                task.id[:8],
                task.description,
                task.status.value,
                task.priority,
                task.project,
                due_str,
                task.assigned_profile or ""
            ), tags=(task.id,))
        
        # Update status
        self.task_count_label.config(text=f"Tasks: {len(self.tasks)}")
        self.update_status(f"Loaded {len(self.tasks)} tasks")
    
    def on_task_select(self, event):
        """Handle task selection"""
        selection = self.task_tree.selection()
        if not selection:
            return
        
        item = self.task_tree.item(selection[0])
        task_id = item['tags'][0] if item['tags'] else item['values'][0]
        
        if task_id in self.tasks:
            task = self.tasks[task_id]
            self.current_task = task
            
            # Update detail fields
            self.task_desc_var.set(task.description)
            self.task_status_var.set(task.status.value)
            self.task_priority_var.set(task.priority)
            self.task_profile_var.set(task.assigned_profile or "")
            self.task_due_var.set(task.due.strftime("%Y-%m-%d") if task.due else "")
            self.task_tags_var.set(", ".join(task.tags))
            
            # Clear and set notes
            self.task_notes_text.delete(1.0, tk.END)
            self.task_notes_text.insert(1.0, task.notes)
    
    def create_new_task(self):
        """Create a new task"""
        # Create a dialog for new task
        dialog = tk.Toplevel(self.root)
        dialog.title("Create New Task")
        dialog.geometry("500x400")
        dialog.transient(self.root)
        dialog.grab_set()
        
        # Form fields
        ttk.Label(dialog, text="Description:").pack(pady=(10, 0), padx=20, anchor='w')
        desc_var = tk.StringVar()
        ttk.Entry(dialog, textvariable=desc_var, width=50).pack(padx=20, pady=5)
        
        ttk.Label(dialog, text="Project:").pack(padx=20, anchor='w')
        project_var = tk.StringVar()
        ttk.Entry(dialog, textvariable=project_var, width=50).pack(padx=20, pady=5)
        
        ttk.Label(dialog, text="Tags (comma-separated):").pack(padx=20, anchor='w')
        tags_var = tk.StringVar()
        ttk.Entry(dialog, textvariable=tags_var, width=50).pack(padx=20, pady=5)
        
        ttk.Label(dialog, text="Priority:").pack(padx=20, anchor='w')
        priority_var = tk.StringVar(value="M")
        ttk.Combobox(dialog, textvariable=priority_var, 
                    values=['H', 'M', 'L'], width=10).pack(padx=20, pady=5)
        
        ttk.Label(dialog, text="Due Date (YYYY-MM-DD):").pack(padx=20, anchor='w')
        due_var = tk.StringVar()
        ttk.Entry(dialog, textvariable=due_var, width=20).pack(padx=20, pady=5)
        
        # Profile suggestion
        ttk.Label(dialog, text="Suggested Profile:").pack(padx=20, anchor='w')
        suggested_profile = self.suggest_profile_for_text(desc_var.get())
        profile_var = tk.StringVar(value=suggested_profile)
        profile_combo = ttk.Combobox(dialog, textvariable=profile_var,
                                   values=list(self.profiles.keys()), width=30)
        profile_combo.pack(padx=20, pady=5)
        
        # Update suggestion when description changes
        def update_suggestion(*args):
            suggestion = self.suggest_profile_for_text(desc_var.get())
            profile_combo.set(suggestion)
        
        desc_var.trace('w', update_suggestion)
        
        # Create button
        def create_task():
            # Generate task ID
            task_id = hashlib.md5(f"{desc_var.get()}{datetime.now()}".encode()).hexdigest()[:12]
            
            # Parse due date
            due_date = None
            if due_var.get():
                try:
                    due_date = datetime.strptime(due_var.get(), "%Y-%m-%d")
                except ValueError:
                    messagebox.showerror("Error", "Invalid date format. Use YYYY-MM-DD")
                    return
            
            # Create task object
            task = Task(
                id=task_id,
                description=desc_var.get(),
                status=TaskStatus.PENDING,
                created=datetime.now(),
                modified=datetime.now(),
                due=due_date,
                priority=priority_var.get(),
                tags=[tag.strip() for tag in tags_var.get().split(",") if tag.strip()],
                project=project_var.get(),
                assigned_profile=profile_var.get() if profile_var.get() else None,
                notes=""
            )
            
            # Save task
            self.tasks[task_id] = task
            self.save_task_to_db(task)
            self.refresh_task_tree()
            
            dialog.destroy()
            self.update_status(f"Created task: {desc_var.get()}")
        
        ttk.Button(dialog, text="Create Task", 
                  command=create_task, style='Green.TButton').pack(pady=20)
    
    def suggest_profile_for_text(self, text: str) -> str:
        """Suggest a profile based on text content"""
        if not text:
            return ""
        
        text_lower = text.lower()
        best_match = ""
        best_score = 0
        
        for profile_name, profile in self.profiles.items():
            if not profile.enabled:
                continue
            
            # Check task tags
            for tag in profile.task_tags:
                if tag.lower() in text_lower:
                    score = text_lower.count(tag.lower())
                    if score > best_score:
                        best_score = score
                        best_match = profile_name
            
            # Check profile type keywords
            type_keywords = {
                ProfileType.CODE_REVIEW: ["code", "program", "bug", "fix", "develop"],
                ProfileType.DOCUMENTATION: ["document", "write", "explain", "manual"],
                ProfileType.PLANNING: ["plan", "design", "architecture", "system"],
                ProfileType.RESEARCH: ["research", "analyze", "study", "investigate"]
            }
            
            if profile.profile_type in type_keywords:
                for keyword in type_keywords[profile.profile_type]:
                    if keyword in text_lower:
                        score = text_lower.count(keyword)
                        if score > best_score:
                            best_score = score
                            best_match = profile_name
        
        return best_match
    
    def update_selected_task(self):
        """Update the currently selected task"""
        if not self.current_task:
            messagebox.showwarning("No Task", "Please select a task first")
            return
        
        # Update task object
        self.current_task.description = self.task_desc_var.get()
        self.current_task.status = TaskStatus(self.task_status_var.get())
        self.current_task.priority = self.task_priority_var.get()
        self.current_task.assigned_profile = self.task_profile_var.get() or None
        self.current_task.modified = datetime.now()
        self.current_task.tags = [tag.strip() for tag in self.task_tags_var.get().split(",") if tag.strip()]
        self.current_task.notes = self.task_notes_text.get(1.0, tk.END).strip()
        
        # Parse due date
        if self.task_due_var.get():
            try:
                self.current_task.due = datetime.strptime(self.task_due_var.get(), "%Y-%m-%d")
            except ValueError:
                messagebox.showerror("Error", "Invalid date format. Use YYYY-MM-DD")
                return
        
        # Save to database
        self.save_task_to_db(self.current_task)
        
        # Refresh display
        self.refresh_task_tree()
        self.update_status(f"Updated task: {self.current_task.description}")
    
    def complete_selected_task(self):
        """Mark selected task as completed"""
        if not self.current_task:
            return
        
        self.current_task.status = TaskStatus.COMPLETED
        self.current_task.modified = datetime.now()
        self.save_task_to_db(self.current_task)
        self.refresh_task_tree()
        self.update_status(f"Completed task: {self.current_task.description}")
        
        # Send notification
        self.send_notification("Task Completed", 
                              f"Task '{self.current_task.description}' has been marked as completed.")
    
    def delete_selected_task(self):
        """Delete selected task"""
        if not self.current_task:
            return
        
        if messagebox.askyesno("Confirm Delete", 
                              f"Delete task '{self.current_task.description}'?"):
            del self.tasks[self.current_task.id]
            
            # Remove from database
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("DELETE FROM tasks WHERE id = ?", (self.current_task.id,))
            conn.commit()
            conn.close()
            
            self.current_task = None
            self.refresh_task_tree()
            self.update_status("Task deleted")
    
    def run_profile_on_task(self):
        """Run assigned profile on selected task"""
        if not self.current_task:
            messagebox.showwarning("No Task", "Please select a task first")
            return
        
        profile_name = self.current_task.assigned_profile
        if not profile_name:
            messagebox.showwarning("No Profile", "No profile assigned to this task")
            return
        
        if profile_name not in self.profiles:
            messagebox.showerror("Error", f"Profile '{profile_name}' not found")
            return
        
        profile = self.profiles[profile_name]
        
        # Run in background thread
        def run_task():
            try:
                # Prepare prompt
                prompt = f"Task: {self.current_task.description}\n"
                prompt += f"Status: {self.current_task.status.value}\n"
                prompt += f"Notes: {self.current_task.notes}\n"
                prompt += f"Tags: {', '.join(self.current_task.tags)}\n"
                prompt += f"Project: {self.current_task.project}\n\n"
                prompt += "Please analyze this task and provide recommendations:"
                
                # Call Ollama
                response = self.call_ollama(profile.model, prompt, profile.system_prompt)
                
                # Show response
                self.root.after(0, self.show_task_analysis, response)
                
            except Exception as e:
                self.root.after(0, messagebox.showerror, "Error", f"Failed to run profile: {str(e)}")
        
        threading.Thread(target=run_task, daemon=True).start()
        self.update_status(f"Running {profile_name} on task...")
    
    def show_task_analysis(self, response):
        """Show task analysis results"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Task Analysis Results")
        dialog.geometry("800x600")
        
        text = scrolledtext.ScrolledText(dialog, width=80, height=30, wrap='word')
        text.pack(fill='both', expand=True, padx=10, pady=10)
        
        text.insert(1.0, response)
        text.config(state='disabled')
        
        ttk.Button(dialog, text="Close", command=dialog.destroy).pack(pady=10)
    
    # ============================================================================
    # PROFILE MANAGEMENT FUNCTIONS
    # ============================================================================
    
    def refresh_profile_tree(self):
        """Refresh profile treeview"""
        for item in self.profile_tree.get_children():
            self.profile_tree.delete(item)
        
        for profile in self.profiles.values():
            self.profile_tree.insert('', 'end', values=(
                profile.name,
                profile.model,
                profile.profile_type.value,
                "Yes" if profile.enabled else "No"
            ))
        
        self.profile_count_label.config(text=f"Profiles: {len(self.profiles)}")
    
    def on_profile_select(self, event):
        """Handle profile selection"""
        selection = self.profile_tree.selection()
        if not selection:
            return
        
        item = self.profile_tree.item(selection[0])
        profile_name = item['values'][0]
        
        if profile_name in self.profiles:
            profile = self.profiles[profile_name]
            
            # Update editor fields
            self.profile_name_var.set(profile.name)
            self.profile_model_var.set(profile.model)
            self.profile_type_var.set(profile.profile_type.value)
            self.profile_enabled_var.set(profile.enabled)
            self.profile_auto_trigger_var.set(profile.auto_trigger)
            self.profile_temp_var.set(profile.temperature)
            self.profile_max_tokens_var.set(profile.max_tokens)
            
            # Set prompt
            self.profile_prompt_text.delete(1.0, tk.END)
            self.profile_prompt_text.insert(1.0, profile.system_prompt)
            
            # Set lists
            self.profile_extensions_var.set(", ".join(profile.file_extensions))
            self.profile_tags_var.set(", ".join(profile.task_tags))
            self.profile_executables_var.set(", ".join(profile.executable_paths))
    
    def create_new_profile(self):
        """Create a new profile"""
        # Reset editor fields
        self.profile_name_var.set("")
        self.profile_model_var.set("")
        self.profile_type_var.set(ProfileType.CUSTOM.value)
        self.profile_enabled_var.set(True)
        self.profile_auto_trigger_var.set(False)
        self.profile_temp_var.set(0.7)
        self.profile_max_tokens_var.set(2048)
        self.profile_prompt_text.delete(1.0, tk.END)
        self.profile_extensions_var.set("")
        self.profile_tags_var.set("")
        self.profile_executables_var.set("")
        
        # Focus on name field
        self.notebook.select(2)  # Switch to profile tab
        # Find and focus the name entry (implementation depends on widget structure)
    
    def save_profile_editor(self):
        """Save current profile editor contents"""
        name = self.profile_name_var.get().strip()
        if not name:
            messagebox.showerror("Error", "Profile name is required")
            return
        
        # Get or create profile
        if name in self.profiles:
            profile = self.profiles[name]
        else:
            profile = OllamaProfile(
                name=name,
                model="llama2",
                profile_type=ProfileType.CUSTOM,
                system_prompt=""
            )
        
        # Update profile
        profile.model = self.profile_model_var.get()
        profile.profile_type = ProfileType(self.profile_type_var.get())
        profile.enabled = self.profile_enabled_var.get()
        profile.auto_trigger = self.profile_auto_trigger_var.get()
        profile.temperature = self.profile_temp_var.get()
        profile.max_tokens = self.profile_max_tokens_var.get()
        profile.system_prompt = self.profile_prompt_text.get(1.0, tk.END).strip()
        
        # Parse lists
        profile.file_extensions = [ext.strip() for ext in self.profile_extensions_var.get().split(",") if ext.strip()]
        profile.task_tags = [tag.strip() for tag in self.profile_tags_var.get().split(",") if tag.strip()]
        profile.executable_paths = [path.strip() for path in self.profile_executables_var.get().split(",") if path.strip()]
        
        # Save
        self.profiles[name] = profile
        self.save_profiles()
        self.refresh_profile_tree()
        
        self.update_status(f"Saved profile: {name}")
    
    def delete_profile(self):
        """Delete selected profile"""
        selection = self.profile_tree.selection()
        if not selection:
            return
        
        item = self.profile_tree.item(selection[0])
        profile_name = item['values'][0]
        
        if messagebox.askyesno("Confirm Delete", f"Delete profile '{profile_name}'?"):
            if profile_name in self.profiles:
                del self.profiles[profile_name]
                self.save_profiles()
                self.refresh_profile_tree()
                self.update_status(f"Deleted profile: {profile_name}")
    
    def duplicate_profile(self):
        """Duplicate selected profile"""
        selection = self.profile_tree.selection()
        if not selection:
            return
        
        item = self.profile_tree.item(selection[0])
        profile_name = item['values'][0]
        
        if profile_name in self.profiles:
            # Create copy with suffix
            new_name = f"{profile_name}_copy"
            copy_num = 1
            while new_name in self.profiles:
                copy_num += 1
                new_name = f"{profile_name}_copy{copy_num}"
            
            # Deep copy profile
            import copy
            new_profile = copy.deepcopy(self.profiles[profile_name])
            new_profile.name = new_name
            
            self.profiles[new_name] = new_profile
            self.save_profiles()
            self.refresh_profile_tree()
            
            self.update_status(f"Duplicated profile as: {new_name}")
    
    # ============================================================================
    # FILE TRACKING FUNCTIONS
    # ============================================================================
    
    def refresh_file_tree(self):
        """Refresh file tracking treeview"""
        for item in self.file_tree.get_children():
            self.file_tree.delete(item)
        
        for file_path, file_obj in self.tracked_files.items():
            # Get task description
            task_desc = ""
            if file_obj.task_id in self.tasks:
                task_desc = self.tasks[file_obj.task_id].description[:30] + "..."
            
            self.file_tree.insert('', 'end', values=(
                file_path,
                task_desc,
                file_obj.last_modified.strftime("%Y-%m-%d %H:%M:%S"),
                file_obj.profile_hint or ""
            ))
    
    def on_file_select(self, event):
        """Handle file selection"""
        # Implementation for file selection
        pass
    
    def add_files_to_tracking(self):
        """Add files to tracking"""
        files = filedialog.askopenfilenames(
            title="Select files to track",
            filetypes=[("All files", "*.*")]
        )
        
        for file_path in files:
            self.track_file(file_path)
        
        self.refresh_file_tree()
        self.update_status(f"Added {len(files)} files to tracking")
    
    def add_directory_to_tracking(self):
        """Add directory to tracking"""
        directory = filedialog.askdirectory(title="Select directory to track")
        if not directory:
            return
        
        # Walk through directory
        file_count = 0
        for root, dirs, files in os.walk(directory):
            for file in files:
                file_path = os.path.join(root, file)
                self.track_file(file_path)
                file_count += 1
        
        self.refresh_file_tree()
        self.update_status(f"Added {file_count} files from directory")
    
    def track_file(self, file_path: str):
        """Track a file"""
        try:
            stat = os.stat(file_path)
            last_modified = datetime.fromtimestamp(stat.st_mtime)
            
            # Calculate checksum
            checksum = self.calculate_file_checksum(file_path)
            
            # Create tracked file object
            tracked_file = TrackedFile(
                path=file_path,
                task_id="",
                last_modified=last_modified,
                checksum=checksum,
                profile_hint=self.suggest_profile_for_file(file_path)
            )
            
            self.tracked_files[file_path] = tracked_file
            
            # Save to database
            self.save_tracked_file_to_db(tracked_file)
            
        except Exception as e:
            print(f"Error tracking file {file_path}: {e}")
    
    def calculate_file_checksum(self, file_path: str) -> str:
        """Calculate MD5 checksum of file"""
        hash_md5 = hashlib.md5()
        try:
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_md5.update(chunk)
            return hash_md5.hexdigest()
        except:
            return ""
    
    def suggest_profile_for_file(self, file_path: str) -> str:
        """Suggest profile based on file extension"""
        ext = os.path.splitext(file_path)[1].lower()
        
        for profile_name, profile in self.profiles.items():
            if not profile.enabled:
                continue
            
            if ext in [e.lower() for e in profile.file_extensions]:
                return profile_name
        
        return ""
    
    def scan_file_changes(self):
        """Scan tracked files for changes"""
        changed_files = []
        for file_path, tracked_file in list(self.tracked_files.items()):
            if not os.path.exists(file_path):
                # File deleted
                del self.tracked_files[file_path]
                continue
            
            # Check modification time
            stat = os.stat(file_path)
            current_mtime = datetime.fromtimestamp(stat.st_mtime)
            
            if current_mtime > tracked_file.last_modified:
                # Check checksum
                current_checksum = self.calculate_file_checksum(file_path)
                if current_checksum != tracked_file.checksum:
                    changed_files.append(file_path)
                    
                    # Update tracked file
                    tracked_file.last_modified = current_mtime
                    tracked_file.checksum = current_checksum
                    self.save_tracked_file_to_db(tracked_file)
        
        if changed_files:
            self.update_status(f"Found {len(changed_files)} changed files")
            self.refresh_file_tree()
            
            # Notify about changes
            if len(changed_files) <= 5:
                file_list = "\n".join(changed_files)
                self.send_notification("Files Changed", 
                                      f"The following files have changed:\n{file_list}")
        else:
            self.update_status("No file changes detected")
    
    def assign_file_to_task(self):
        """Assign selected file to a task"""
        selection = self.file_tree.selection()
        if not selection:
            return
        
        item = self.file_tree.item(selection[0])
        file_path = item['values'][0]
        
        if file_path not in self.tracked_files:
            return
        
        # Show task selection dialog
        dialog = tk.Toplevel(self.root)
        dialog.title("Assign to Task")
        dialog.geometry("400x300")
        
        # Task list
        task_listbox = tk.Listbox(dialog, height=10)
        task_listbox.pack(fill='both', expand=True, padx=10, pady=10)
        
        for task in self.tasks.values():
            task_listbox.insert(tk.END, f"{task.id[:8]}: {task.description}")
        
        def assign():
            selection = task_listbox.curselection()
            if not selection:
                return
            
            task_index = selection[0]
            task_id = list(self.tasks.keys())[task_index]
            
            # Update tracked file
            tracked_file = self.tracked_files[file_path]
            tracked_file.task_id = task_id
            self.save_tracked_file_to_db(tracked_file)
            
            dialog.destroy()
            self.refresh_file_tree()
            self.update_status(f"Assigned file to task")
        
        ttk.Button(dialog, text="Assign", command=assign).pack(pady=10)
    
    # ============================================================================
    # OLLAMA INTEGRATION FUNCTIONS
    # ============================================================================
    
    def refresh_ollama_models(self):
        """Refresh list of available Ollama models"""
        try:
            result = subprocess.run(['ollama', 'list'], 
                                  capture_output=True, 
                                  text=True, 
                                  timeout=10)
            
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')[1:]  # Skip header
                self.ollama_models = []
                
                for line in lines:
                    if line.strip():
                        parts = line.split()
                        if len(parts) >= 1:
                            self.ollama_models.append(parts[0])
                
                # Update model combos
                self.model_combo['values'] = self.ollama_models
                self.chat_model_combo['values'] = self.ollama_models
                
                if self.ollama_models:
                    self.model_combo.set(self.ollama_models[0])
                    self.chat_model_combo.set(self.ollama_models[0])
                
                self.update_status(f"Found {len(self.ollama_models)} Ollama models")
                return True
            else:
                self.update_status("Ollama not available")
                return False
                
        except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
            self.update_status("Ollama not available")
            return False
    
    def refresh_chat_models(self):
        """Refresh models in chat tab"""
        self.refresh_ollama_models()
    
    def call_ollama(self, model: str, prompt: str, system_prompt: str = "") -> str:
        """Call Ollama API"""
        try:
            # Prepare the request
            import requests
            
            url = "http://localhost:11434/api/generate"
            
            data = {
                "model": model,
                "prompt": prompt,
                "system": system_prompt,
                "stream": False,
                "options": {
                    "temperature": 0.7,
                    "num_predict": 2048
                }
            }
            
            response = requests.post(url, json=data, timeout=300)
            
            if response.status_code == 200:
                result = response.json()
                return result.get("response", "")
            else:
                raise Exception(f"Ollama API error: {response.status_code}")
                
        except requests.exceptions.ConnectionError:
            raise Exception("Cannot connect to Ollama. Make sure Ollama is running.")
        except Exception as e:
            raise Exception(f"Error calling Ollama: {str(e)}")
    
    def send_chat_message(self):
        """Send chat message to Ollama"""
        message = self.chat_input.get(1.0, tk.END).strip()
        if not message:
            return
        
        model = self.chat_model_var.get()
        if not model:
            messagebox.showerror("Error", "Please select a model")
            return
        
        # Add user message to chat
        self.add_to_chat(f"You: {message}\n\n")
        
        # Clear input
        self.chat_input.delete(1.0, tk.END)
        
        # Get temperature
        temperature = self.chat_temp_var.get()
        
        # Get system prompt from profile if selected
        system_prompt = ""
        profile_name = self.chat_profile_var.get()
        if profile_name and profile_name in self.profiles:
            system_prompt = self.profiles[profile_name].system_prompt
        
        # Run in background thread
        def generate_response():
            try:
                # Call Ollama
                response = self.call_ollama(model, message, system_prompt)
                
                # Add response to chat
                self.root.after(0, self.add_to_chat, f"Assistant: {response}\n\n{'='*60}\n\n")
                
            except Exception as e:
                self.root.after(0, self.add_to_chat, f"Error: {str(e)}\n\n")
        
        threading.Thread(target=generate_response, daemon=True).start()
    
    def add_to_chat(self, text: str):
        """Add text to chat display"""
        self.chat_display.config(state='normal')
        self.chat_display.insert(tk.END, text)
        self.chat_display.see(tk.END)
        self.chat_display.config(state='disabled')
    
    def clear_chat(self):
        """Clear chat history"""
        self.chat_display.config(state='normal')
        self.chat_display.delete(1.0, tk.END)
        self.chat_display.config(state='disabled')
    
    def load_chat_context(self):
        """Load context from selected task into chat"""
        if not self.current_task:
            messagebox.showwarning("No Task", "Please select a task first")
            return
        
        context = f"Task Context:\n"
        context += f"Description: {self.current_task.description}\n"
        context += f"Status: {self.current_task.status.value}\n"
        context += f"Project: {self.current_task.project}\n"
        context += f"Tags: {', '.join(self.current_task.tags)}\n"
        context += f"Notes: {self.current_task.notes}\n\n"
        
        self.chat_input.insert(1.0, context)
        self.update_status("Loaded task context into chat")
    
    def execute_chat_code(self):
        """Execute code from chat"""
        # Get the last assistant message
        chat_content = self.chat_display.get(1.0, tk.END)
        
        # Find code blocks
        import re
        code_blocks = re.findall(r'```(?:python|bash|sh)?\n(.*?)\n```', chat_content, re.DOTALL)
        
        if not code_blocks:
            messagebox.showinfo("No Code", "No code blocks found in chat")
            return
        
        # Show code selection dialog
        dialog = tk.Toplevel(self.root)
        dialog.title("Execute Code")
        dialog.geometry("600x400")
        
        # Code selection
        ttk.Label(dialog, text="Select code to execute:").pack(pady=10)
        
        code_listbox = tk.Listbox(dialog, height=10)
        code_listbox.pack(fill='both', expand=True, padx=10, pady=5)
        
        for i, code in enumerate(code_blocks):
            preview = code[:50].replace('\n', ' ') + "..."
            code_listbox.insert(tk.END, f"Code block {i+1}: {preview}")
        
        # Language selection
        lang_var = tk.StringVar(value="python")
        ttk.Combobox(dialog, textvariable=lang_var, 
                    values=["python", "bash", "shell"], width=10).pack(pady=5)
        
        def execute_selected():
            selection = code_listbox.curselection()
            if not selection:
                return
            
            index = selection[0]
            code = code_blocks[index]
            lang = lang_var.get()
            
            dialog.destroy()
            
            # Execute based on language
            if lang == "python":
                self.execute_python_code(code)
            elif lang in ["bash", "shell"]:
                self.execute_shell_code(code)
        
        ttk.Button(dialog, text="Execute", command=execute_selected).pack(pady=10)
    
    def execute_python_code(self, code: str):
        """Execute Python code"""
        try:
            # Create a temporary file
            import tempfile
            with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
                f.write(code)
                temp_file = f.name
            
            # Execute
            result = subprocess.run(['python3', temp_file], 
                                  capture_output=True, 
                                  text=True, 
                                  timeout=30)
            
            # Show results
            self.show_execution_result(result.stdout, result.stderr)
            
            # Cleanup
            os.unlink(temp_file)
            
        except Exception as e:
            messagebox.showerror("Execution Error", str(e))
    
    def execute_shell_code(self, code: str):
        """Execute shell code"""
        try:
            result = subprocess.run(code, 
                                  shell=True, 
                                  capture_output=True, 
                                  text=True, 
                                  timeout=30)
            
            self.show_execution_result(result.stdout, result.stderr)
            
        except Exception as e:
            messagebox.showerror("Execution Error", str(e))
    
    def show_execution_result(self, stdout: str, stderr: str):
        """Show code execution results"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Execution Results")
        dialog.geometry("800x600")
        
        notebook = ttk.Notebook(dialog)
        notebook.pack(fill='both', expand=True, padx=10, pady=10)
        
        # STDOUT tab
        stdout_frame = ttk.Frame(notebook)
        stdout_text = scrolledtext.ScrolledText(stdout_frame, width=80, height=20)
        stdout_text.pack(fill='both', expand=True, padx=5, pady=5)
        stdout_text.insert(1.0, stdout or "(No output)")
        stdout_text.config(state='disabled')
        notebook.add(stdout_frame, text="Output")
        
        # STDERR tab
        if stderr:
            stderr_frame = ttk.Frame(notebook)
            stderr_text = scrolledtext.ScrolledText(stderr_frame, width=80, height=20)
            stderr_text.pack(fill='both', expand=True, padx=5, pady=5)
            stderr_text.insert(1.0, stderr)
            stderr_text.config(state='disabled')
            notebook.add(stderr_frame, text="Errors")
        
        ttk.Button(dialog, text="Close", command=dialog.destroy).pack(pady=10)
    
    # ============================================================================
    # CLIPMAN INTEGRATION FUNCTIONS
    # ============================================================================
    
    def start_clipman_monitoring(self):
        """Start monitoring clipboard"""
        self.update_status("Clipboard monitoring started")
        # Implementation for clipboard monitoring would go here
        # This would typically involve using pyperclip or similar library
    
    def stop_clipman_monitoring(self):
        """Stop monitoring clipboard"""
        self.update_status("Clipboard monitoring stopped")
    
    def clear_clipboard_history(self):
        """Clear clipboard history"""
        self.clipboard_history = []
        # Clear treeview
        for item in self.clip_tree.get_children():
            self.clip_tree.delete(item)
        
        self.update_status("Clipboard history cleared")
    
    def create_task_from_clip(self):
        """Create task from clipboard content"""
        # Implementation would get current clipboard content
        # and create a task dialog pre-filled with it
        pass
    
    def analyze_clipboard(self):
        """Analyze clipboard content with AI"""
        # Implementation would analyze clipboard content
        # with the most appropriate AI profile
        pass
    
    # ============================================================================
    # AGENT CONTROL FUNCTIONS
    # ============================================================================
    
    def start_agent(self):
        """Start an AI agent"""
        self.update_status("Starting agent...")
        # Implementation for starting agents
    
    def stop_agent(self):
        """Stop an AI agent"""
        self.update_status("Stopping agent...")
        # Implementation for stopping agents
    
    def restart_agent(self):
        """Restart an AI agent"""
        self.update_status("Restarting agent...")
        # Implementation for restarting agents
    
    def view_agent_logs(self):
        """View agent logs"""
        # Implementation for viewing logs
        pass
    
    def start_system_monitoring(self):
        """Start system monitoring"""
        self.update_status("System monitoring started")
    
    def stop_system_monitoring(self):
        """Stop system monitoring"""
        self.update_status("System monitoring stopped")
    
    def update_system_monitor(self):
        """Update system monitor display"""
        # This would normally get real system stats
        # For now, use placeholder values
        self.cpu_var.set("25%")
        self.memory_var.set("512 MB")
        self.ollama_status_var.set("Running" if self.ollama_models else "Stopped")
        self.active_models_var.set(str(len(self.ollama_models)))
        
        # Schedule next update
        self.root.after(5000, self.update_system_monitor)
    
    # ============================================================================
    # DATABASE OPERATIONS
    # ============================================================================
    
    def save_task_to_db(self, task: Task):
        """Save task to database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO tasks VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            task.id,
            task.description,
            task.status.value,
            task.created.isoformat(),
            task.modified.isoformat(),
            task.due.isoformat() if task.due else None,
            task.priority,
            json.dumps(task.tags),
            task.project,
            json.dumps(task.dependencies),
            task.assigned_profile,
            task.notes,
            json.dumps(task.metadata)
        ))
        
        conn.commit()
        conn.close()
    
    def save_tracked_file_to_db(self, file: TrackedFile):
        """Save tracked file to database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO tracked_files VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            file.path,
            file.task_id,
            file.last_modified.isoformat(),
            file.checksum,
            file.profile_hint,
            json.dumps(file.annotations)
        ))
        
        conn.commit()
        conn.close()
    
    # ============================================================================
    # UTILITY FUNCTIONS
    # ============================================================================
    
    def update_status(self, message: str):
        """Update status bar"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.status_label.config(text=f"{timestamp} - {message}")
        print(f"[{timestamp}] {message}")
    
    def send_notification(self, title: str, message: str):
        """Send desktop notification"""
        try:
            # Try to use notify-send on Linux
            subprocess.run(['notify-send', title, message])
        except:
            # Fallback to messagebox
            self.root.after(0, messagebox.showinfo, title, message)
    
    def start_background_services(self):
        """Start background services"""
        # Start periodic tasks
        self.root.after(60000, self.periodic_tasks)  # Every minute
        self.root.after(300000, self.periodic_sync)  # Every 5 minutes
    
    def periodic_tasks(self):
        """Run periodic background tasks"""
        # Check for file changes
        self.scan_file_changes()
        
        # Check for task due dates
        self.check_due_tasks()
        
        # Reschedule
        self.root.after(60000, self.periodic_tasks)
    
    def periodic_sync(self):
        """Periodic sync with Taskwarrior"""
        if hasattr(self, 'auto_sync') and self.auto_sync:
            self.sync_taskwarrior()
        
        # Reschedule
        self.root.after(300000, self.periodic_sync)
    
    def check_due_tasks(self):
        """Check for due or overdue tasks"""
        now = datetime.now()
        due_soon = []
        overdue = []
        
        for task in self.tasks.values():
            if task.due and task.status not in [TaskStatus.COMPLETED, TaskStatus.DELETED]:
                if task.due < now:
                    overdue.append(task)
                elif (task.due - now).days <= 1:
                    due_soon.append(task)
        
        # Send notifications
        if overdue:
            self.send_notification("Overdue Tasks", 
                                  f"You have {len(overdue)} overdue tasks")
        
        if due_soon:
            self.send_notification("Tasks Due Soon", 
                                  f"You have {len(due_soon)} tasks due within 24 hours")
    
    def sync_taskwarrior(self):
        """Sync with Taskwarrior"""
        try:
            # Export from Taskwarrior
            result = subprocess.run(['task', 'export'], 
                                  capture_output=True, 
                                  text=True, 
                                  check=True)
            
            task_data = json.loads(result.stdout)
            
            # Update local tasks
            for item in task_data:
                task_id = str(item.get('id', item.get('uuid', '')))
                if task_id and task_id not in self.tasks:
                    # Import new task
                    task = Task(
                        id=task_id,
                        description=item.get('description', ''),
                        status=TaskStatus(item.get('status', 'pending')),
                        created=datetime.fromisoformat(item.get('entry', datetime.now().isoformat())),
                        modified=datetime.now(),
                        due=datetime.fromisoformat(item['due']) if 'due' in item else None,
                        priority=item.get('priority', 'M'),
                        tags=item.get('tags', []),
                        project=item.get('project', ''),
                        dependencies=item.get('depends', []),
                        notes=str(item.get('annotations', ''))
                    )
                    self.tasks[task_id] = task
                    self.save_task_to_db(task)
            
            self.refresh_task_tree()
            self.update_status("Synced with Taskwarrior")
            
        except Exception as e:
            self.update_status(f"Taskwarrior sync failed: {str(e)}")
    
    def import_taskwarrior(self):
        """Import tasks from Taskwarrior"""
        self.sync_taskwarrior()
    
    def export_to_taskwarrior(self):
        """Export tasks to Taskwarrior"""
        self.update_status("Export to Taskwarrior not implemented yet")
        # Implementation would convert tasks to Taskwarrior format and import
    
    def save_configuration(self):
        """Save configuration to file"""
        config = {
            'profiles': {name: asdict(profile) for name, profile in self.profiles.items()},
            'auto_sync': getattr(self, 'auto_sync', True),
            'clipboard_monitoring': getattr(self, 'clipboard_monitoring', True),
            'file_tracking_paths': list(self.tracked_files.keys())
        }
        
        config_file = self.config_dir / "config.json"
        with open(config_file, 'w') as f:
            json.dump(config, f, indent=2, default=str)
        
        self.update_status("Configuration saved")
    
    def load_configuration(self):
        """Load configuration from file"""
        config_file = self.config_dir / "config.json"
        if config_file.exists():
            with open(config_file, 'r') as f:
                config = json.load(f)
            
            # Load profiles
            for name, profile_data in config.get('profiles', {}).items():
                # Convert string enum back
                if 'profile_type' in profile_data:
                    profile_data['profile_type'] = ProfileType(profile_data['profile_type'])
                
                self.profiles[name] = OllamaProfile(**profile_data)
            
            self.save_profiles()
            self.refresh_profile_tree()
            
            self.update_status("Configuration loaded")
    
    def export_tasks(self):
        """Export tasks to file"""
        file_path = filedialog.asksaveasfilename(
            title="Export Tasks",
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        
        if file_path:
            tasks_data = [asdict(task) for task in self.tasks.values()]
            with open(file_path, 'w') as f:
                json.dump(tasks_data, f, indent=2, default=str)
            
            self.update_status(f"Exported {len(tasks_data)} tasks to {file_path}")
    
    def import_tasks(self):
        """Import tasks from file"""
        file_path = filedialog.askopenfilename(
            title="Import Tasks",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        
        if file_path:
            with open(file_path, 'r') as f:
                tasks_data = json.load(f)
            
            for task_data in tasks_data:
                # Convert string enum back
                if 'status' in task_data:
                    task_data['status'] = TaskStatus(task_data['status'])
                
                # Convert string dates back to datetime
                for date_field in ['created', 'modified', 'due']:
                    if date_field in task_data and task_data[date_field]:
                        task_data[date_field] = datetime.fromisoformat(task_data[date_field])
                
                task = Task(**task_data)
                self.tasks[task.id] = task
                self.save_task_to_db(task)
            
            self.refresh_task_tree()
            self.update_status(f"Imported {len(tasks_data)} tasks")
    
    def cleanup_database(self):
        """Cleanup database"""
        if messagebox.askyesno("Confirm Cleanup", 
                              "This will remove completed and deleted tasks. Continue?"):
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Remove completed and deleted tasks
            cursor.execute("DELETE FROM tasks WHERE status IN ('completed', 'deleted')")
            
            # Remove orphaned file references
            cursor.execute('''
                DELETE FROM tracked_files 
                WHERE task_id != '' AND task_id NOT IN (SELECT id FROM tasks)
            ''')
            
            conn.commit()
            conn.close()
            
            # Reload tasks
            self.load_tasks()
            self.refresh_task_tree()
            
            self.update_status("Database cleaned up")
    
    def run_diagnostics(self):
        """Run system diagnostics"""
        dialog = tk.Toplevel(self.root)
        dialog.title("System Diagnostics")
        dialog.geometry("600x400")
        
        text = scrolledtext.ScrolledText(dialog, width=70, height=20)
        text.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Run diagnostics
        diagnostics = []
        
        # Check Ollama
        diagnostics.append("=== Ollama Status ===")
        if self.refresh_ollama_models():
            diagnostics.append(f"✓ Ollama running with {len(self.ollama_models)} models")
        else:
            diagnostics.append("✗ Ollama not available")
        
        # Check Taskwarrior
        diagnostics.append("\n=== Taskwarrior Status ===")
        try:
            subprocess.run(['task', '--version'], capture_output=True, check=True)
            diagnostics.append("✓ Taskwarrior available")
        except:
            diagnostics.append("✗ Taskwarrior not available")
        
        # Check database
        diagnostics.append("\n=== Database Status ===")
        diagnostics.append(f"Tasks: {len(self.tasks)}")
        diagnostics.append(f"Profiles: {len(self.profiles)}")
        diagnostics.append(f"Tracked files: {len(self.tracked_files)}")
        
        # Check configuration directory
        diagnostics.append("\n=== Configuration ===")
        diagnostics.append(f"Config dir: {self.config_dir}")
        diagnostics.append(f"Database: {self.db_path}")
        diagnostics.append(f"Config exists: {(self.config_dir / 'config.json').exists()}")
        
        text.insert(1.0, "\n".join(diagnostics))
        text.config(state='disabled')
        
        ttk.Button(dialog, text="Close", command=dialog.destroy).pack(pady=10)
    
    def refresh_all(self):
        """Refresh all displays"""
        self.refresh_task_tree()
        self.refresh_profile_tree()
        self.refresh_file_tree()
        self.refresh_ollama_models()
        self.update_status("All displays refreshed")
    
    def show_notifications(self):
        """Show notifications panel"""
        # Implementation for notifications panel
        pass
    
    def show_logs(self):
        """Show application logs"""
        # Implementation for log viewer
        pass
    
    def show_documentation(self):
        """Show documentation"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Documentation")
        dialog.geometry("800x600")
        
        text = scrolledtext.ScrolledText(dialog, width=90, height=35)
        text.pack(fill='both', expand=True, padx=10, pady=10)
        
        docs = """
        OLLAMA TASK PLANNER - DOCUMENTATION
        
        1. TASK DASHBOARD
        - View all tasks from Taskwarrior or local database
        - Filter tasks by text search
        - Create, update, complete, and delete tasks
        - Assign AI profiles to tasks
        
        2. CLIPMAN INTEGRATION
        - Monitor clipboard history
        - Create tasks from clipboard content
        - Analyze clipboard text with AI
        
        3. PROFILE MANAGEMENT
        - Create and manage AI profiles for different task types
        - Configure system prompts, temperature, and other parameters
        - Set file extensions and task tags for auto-suggestion
        
        4. FILE TRACKING
        - Track files and associate them with tasks
        - Monitor file changes
        - Assign profile hints for automatic AI suggestions
        
        5. AGENT CONTROL
        - Monitor system resources
        - Control AI agents
        - View agent logs
        
        6. OLLAMA CHAT
        - Direct chat interface with Ollama models
        - Load task context into chat
        - Execute code from chat responses
        
        KEY FEATURES:
        - Automatic profile suggestion based on task content
        - File change detection and notification
        - Integration with Taskwarrior for task management
        - Desktop notifications for due tasks
        - Background monitoring and periodic sync
        
        TIPS:
        - Use tags in task descriptions for better profile matching
        - Configure file extensions in profiles for automatic file type detection
        - Enable auto-sync to keep tasks synchronized with Taskwarrior
        - Use the chat interface for quick AI assistance
        """
        
        text.insert(1.0, docs)
        text.config(state='disabled')
    
    def show_about(self):
        """Show about dialog"""
        messagebox.showinfo("About Ollama Task Planner",
                          "Ollama Task Planner v1.0\n\n"
                          "Complete integration system for task management,\n"
                          "AI assistance, file tracking, and automation.\n\n"
                          "Integrates: Clipman, Taskwarrior, Ollama AI models")
    
    def sort_tasks(self, column):
        """Sort tasks by column"""
        # Implementation for sorting tasks
        pass
    
    def filter_tasks(self):
        """Filter tasks based on search text"""
        self.refresh_task_tree()
    
    # ============================================================================
    # MAIN ENTRY POINT
    # ============================================================================

def main():
    """Main entry point"""
    root = tk.Tk()
    
    # Set window icon if available
    try:
        root.iconbitmap(default='icon.ico')
    except:
        pass
    
    app = OllamaPlannerGUI(root)
    
    # Handle window close
    def on_closing():
        if messagebox.askokcancel("Quit", "Do you want to save configuration before quitting?"):
            app.save_configuration()
        root.destroy()
    
    root.protocol("WM_DELETE_WINDOW", on_closing)
    
    # Start main loop
    root.mainloop()

if __name__ == "__main__":
    main()