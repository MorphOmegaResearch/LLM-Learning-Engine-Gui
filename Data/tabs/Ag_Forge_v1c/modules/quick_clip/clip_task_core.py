#!/usr/bin/env python3
"""
Core Task Management Library for Quick Clip
-------------------------------------------
Provides data models and database interactions for the Task Planner.
"""

import sqlite3
import json
import uuid
import os
from datetime import datetime
from dataclasses import dataclass, field, asdict
from typing import List, Optional, Dict, Any
from pathlib import Path
from enum import Enum

class TaskStatus(Enum):
    PENDING = "pending"
    ACTIVE = "active"
    COMPLETED = "completed"
    DELETED = "deleted"
    WAITING = "waiting"

@dataclass
class Task:
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

class TaskManager:
    def __init__(self, db_path: Optional[Path] = None):
        if db_path is None:
            self.db_path = Path.home() / ".config" / "ollama-planner" / "planner.db"
        else:
            self.db_path = db_path
        
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.init_db()

    def init_db(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
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
        conn.commit()
        conn.close()

    def add_task(self, description: str, project: str = "", tags: List[str] = None, priority: str = "M") -> str:
        task_id = str(uuid.uuid4())
        created = datetime.now()
        
        task = Task(
            id=task_id,
            description=description,
            status=TaskStatus.PENDING,
            created=created,
            modified=created,
            project=project,
            tags=tags or [],
            priority=priority
        )
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO tasks (id, description, status, created, modified, priority, tags, project)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            task.id,
            task.description,
            task.status.value,
            task.created.isoformat(),
            task.modified.isoformat(),
            task.priority,
            json.dumps(task.tags),
            task.project
        ))
        conn.commit()
        conn.close()
        return task_id

    def list_tasks(self, project: Optional[str] = None) -> List[Task]:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        if project:
            cursor.execute("SELECT * FROM tasks WHERE project = ?", (project,))
        else:
            cursor.execute("SELECT * FROM tasks")
        
        rows = cursor.fetchall()
        tasks = []
        for row in rows:
            tasks.append(Task(
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
            ))
        conn.close()
        return tasks
