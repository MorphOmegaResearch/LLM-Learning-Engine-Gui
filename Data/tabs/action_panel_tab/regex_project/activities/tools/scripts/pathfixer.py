#!/usr/bin/env python3
"""
PathFixer - File System Consistency Scanner & Fixer
===================================================

Scans files and directories for path mismatches and inconsistencies.
Provides interactive session-based fixing with safety snapshots.

Features:
- Deep recursive scanning with pattern matching
- Session-based workflow with undo capability
- Safe editing with snapshots
- Interactive checklist for batch operations
- Path mismatch detection and debugging
- Automatic py_compile validation
- Edge case variable handling
"""

import argparse
import os
import re
import sys
import json
import shutil
import hashlib
import tempfile
import py_compile
import subprocess
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Set, Union
from dataclasses import dataclass, field, asdict
from enum import Enum
import difflib


# =============================================================================
# DATA STRUCTURES
# =============================================================================

class IssueSeverity(Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class IssueType(Enum):
    PATH_MISMATCH = "path_mismatch"
    RELATIVE_PATH = "relative_path"
    HARDCODED_PATH = "hardcoded_path"
    IMPORT_ERROR = "import_error"
    MISSING_MODULE = "missing_module"
    SYNTAX_ERROR = "syntax_error"
    PERMISSION_ERROR = "permission_error"
    FILE_NOT_FOUND = "file_not_found"
    DIRECTORY_MISMATCH = "directory_mismatch"
    ENV_VARIABLE = "env_variable"


@dataclass
class FileIssue:
    """An issue found in a file."""
    id: str
    file_path: Path
    line_number: int
    issue_type: IssueType
    severity: IssueSeverity
    description: str
    original_line: str
    suggested_fix: str = ""
    context_before: List[str] = field(default_factory=list)
    context_after: List[str] = field(default_factory=list)
    matched_pattern: str = ""
    confidence: float = 0.0  # 0.0 to 1.0
    auto_fixable: bool = False
    dependencies: List[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class SessionState:
    """State of a scanning/fixing session."""
    session_id: str
    created_at: str
    base_directory: Path
    target_path: Path
    deep_scan: bool = False
    files_scanned: int = 0
    issues_found: int = 0
    issues_fixed: int = 0
    snapshots_created: int = 0
    current_step: int = 0
    selected_files: Set[str] = field(default_factory=set)
    selected_issues: Set[str] = field(default_factory=set)
    applied_fixes: List[Dict[str, Any]] = field(default_factory=list)
    session_log: List[Dict[str, Any]] = field(default_factory=list)
    checklist: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class ScanResult:
    """Results of a file scan."""
    target_path: Path
    scan_time: str
    files_scanned: int
    total_lines: int
    issues_by_severity: Dict[str, int]
    issues_by_type: Dict[str, int]
    files_with_issues: List[Dict[str, Any]]
    detailed_issues: List[FileIssue]
    scan_duration_seconds: float
    patterns_used: List[str]


@dataclass
class FixPlan:
    """Plan for fixing issues."""
    plan_id: str
    session_id: str
    created_at: str
    target_files: List[Path]
    issues_to_fix: List[FileIssue]
    estimated_changes: int
    risk_level: str
    validation_steps: List[Dict[str, Any]]
    rollback_plan: Dict[str, Any]
    prerequisites: List[str]


# =============================================================================
# PATTERN MATCHERS
# =============================================================================

class PathPatternMatcher:
    """Matches patterns in files that might indicate path issues."""
    
    PATTERNS = {
        IssueType.PATH_MISMATCH: [
            # Windows path patterns that might be problematic on Unix
            r'[A-Z]:\\[^"\']+',  # Windows absolute paths
            r'\\\\[^"\']+',  # Windows UNC paths
            # Unix paths that might be problematic on Windows
            r'/home/[^/"\']+',
            r'/usr/[^"\']+',
            r'/etc/[^"\']+',
            r'/var/[^"\']+',
        ],
        IssueType.RELATIVE_PATH: [
            r'"(\.\.[\\/][^"\']+)"',
            r"'(\.[\\/][^\"']+)'",
            r'(\.[\\/][a-zA-Z0-9_\-\.]+[\\/][^"\']+)',  # ./something/else
        ],
        IssueType.HARDCODED_PATH: [
            r'["\'](/[^"\']+\.(?:py|txt|json|yaml|yml|md|csv))["\']',
            r'["\']([A-Z]:\\[^"\']+\.(?:py|txt|json|yaml|yml|md|csv))["\']',
            r'["\'](C:\\[^"\']+)["\']',  # Hardcoded C: drive
            r'["\'](D:\\[^"\']+)["\']',  # Hardcoded D: drive
        ],
        IssueType.IMPORT_ERROR: [
            r'^import\s+([a-zA-Z_][a-zA-Z0-9_\.]*)\s*$',
            r'^from\s+([a-zA-Z_][a-zA-Z0-9_\.]*)\s+import',
        ],
        IssueType.ENV_VARIABLE: [
            r'os\.environ\[["\'][^"\']+["\']\]',
            r'os\.getenv\(["\'][^"\']+["\']\)',
            r'\$\{[^}]+\}',  # ${VAR} style
        ],
    }
    
    FILE_EXTENSIONS = {
        '.py': 'python',
        '.txt': 'text',
        '.md': 'markdown',
        '.json': 'json',
        '.yaml': 'yaml',
        '.yml': 'yaml',
        '.ini': 'config',
        '.cfg': 'config',
        '.toml': 'config',
        '.sh': 'shell',
        '.bat': 'batch',
        '.ps1': 'powershell',
    }
    
    def __init__(self, base_dir: Path):
        self.base_dir = base_dir
        self.compiled_patterns = self._compile_patterns()
    
    def _compile_patterns(self) -> Dict[IssueType, List[re.Pattern]]:
        """Compile regex patterns."""
        compiled = {}
        for issue_type, patterns in self.PATTERNS.items():
            compiled[issue_type] = [re.compile(pattern, re.IGNORECASE) for pattern in patterns]
        return compiled
    
    def scan_file(self, file_path: Path) -> List[FileIssue]:
        """Scan a single file for issues."""
        if not file_path.exists() or not file_path.is_file():
            return []
        
        issues = []
        content = ""
        
        try:
            content = file_path.read_text(encoding='utf-8', errors='ignore')
            lines = content.split('\n')
            
            for line_num, line in enumerate(lines, 1):
                line_issues = self._scan_line(line, line_num, file_path, lines, line_num - 1)
                issues.extend(line_issues)
                
        except UnicodeDecodeError:
            # Skip binary files
            return []
        except Exception as e:
            # Add error issue
            issues.append(FileIssue(
                id=f"err_{hashlib.md5(str(file_path).encode()).hexdigest()[:8]}_{line_num}",
                file_path=file_path,
                line_number=line_num,
                issue_type=IssueType.SYNTAX_ERROR,
                severity=IssueSeverity.HIGH,
                description=f"Error reading file: {str(e)}",
                original_line="",
                confidence=1.0
            ))
        
        return issues
    
    def _scan_line(self, line: str, line_num: int, file_path: Path, 
                  all_lines: List[str], line_index: int) -> List[FileIssue]:
        """Scan a single line for issues."""
        issues = []
        
        for issue_type, patterns in self.compiled_patterns.items():
            for pattern in patterns:
                matches = pattern.finditer(line)
                for match in matches:
                    issue = self._create_issue_from_match(
                        match, issue_type, line, line_num, 
                        file_path, all_lines, line_index
                    )
                    if issue:
                        issues.append(issue)
        
        return issues
    
    def _create_issue_from_match(self, match: re.Match, issue_type: IssueType,
                                line: str, line_num: int, file_path: Path,
                                all_lines: List[str], line_index: int) -> Optional[FileIssue]:
        """Create a FileIssue from a regex match."""
        matched_text = match.group(0)
        issue_id = f"{issue_type.value}_{hashlib.md5(f'{file_path}:{line_num}:{matched_text}'.encode()).hexdigest()[:12]}"
        
        # Get context
        context_before = all_lines[max(0, line_index - 2):line_index]
        context_after = all_lines[line_index + 1:min(len(all_lines), line_index + 3)]
        
        # Determine severity
        severity = self._determine_severity(issue_type, matched_text, file_path)
        
        # Generate description
        description = self._generate_description(issue_type, matched_text, file_path)
        
        # Check if auto-fixable
        auto_fixable = self._is_auto_fixable(issue_type, matched_text)
        
        # Generate suggested fix
        suggested_fix = self._generate_suggested_fix(issue_type, matched_text, file_path, line)
        
        return FileIssue(
            id=issue_id,
            file_path=file_path,
            line_number=line_num,
            issue_type=issue_type,
            severity=severity,
            description=description,
            original_line=line.strip(),
            suggested_fix=suggested_fix,
            context_before=context_before,
            context_after=context_after,
            matched_pattern=matched_text,
            confidence=self._calculate_confidence(issue_type, matched_text),
            auto_fixable=auto_fixable,
            dependencies=self._get_dependencies(issue_type, matched_text)
        )
    
    def _determine_severity(self, issue_type: IssueType, matched_text: str, 
                           file_path: Path) -> IssueSeverity:
        """Determine severity of an issue."""
        if issue_type == IssueType.SYNTAX_ERROR:
            return IssueSeverity.CRITICAL
        elif issue_type == IssueType.PATH_MISMATCH:
            # Check if it's an absolute path that doesn't exist
            if re.match(r'^[A-Z]:\\', matched_text) or re.match(r'^/', matched_text):
                # Check if path exists
                test_path = Path(matched_text.strip('"\''))
                if not test_path.exists():
                    return IssueSeverity.HIGH
            return IssueSeverity.MEDIUM
        elif issue_type == IssueType.HARDCODED_PATH:
            return IssueSeverity.HIGH
        elif issue_type == IssueType.IMPORT_ERROR:
            return IssueSeverity.MEDIUM
        elif issue_type == IssueType.RELATIVE_PATH:
            return IssueSeverity.LOW
        else:
            return IssueSeverity.INFO
    
    def _generate_description(self, issue_type: IssueType, matched_text: str, 
                             file_path: Path) -> str:
        """Generate human-readable description."""
        descriptions = {
            IssueType.PATH_MISMATCH: f"Path mismatch detected: {matched_text}",
            IssueType.RELATIVE_PATH: f"Relative path that may break in different directories: {matched_text}",
            IssueType.HARDCODED_PATH: f"Hardcoded absolute path: {matched_text}",
            IssueType.IMPORT_ERROR: f"Potential import issue: {matched_text}",
            IssueType.MISSING_MODULE: f"Missing module reference: {matched_text}",
            IssueType.SYNTAX_ERROR: f"Syntax error in file",
            IssueType.PERMISSION_ERROR: f"Permission issue with path: {matched_text}",
            IssueType.FILE_NOT_FOUND: f"File not found: {matched_text}",
            IssueType.DIRECTORY_MISMATCH: f"Directory structure mismatch",
            IssueType.ENV_VARIABLE: f"Environment variable usage: {matched_text}",
        }
        
        return descriptions.get(issue_type, f"Issue detected: {matched_text}")
    
    def _is_auto_fixable(self, issue_type: IssueType, matched_text: str) -> bool:
        """Check if issue can be auto-fixed."""
        auto_fixable_types = {
            IssueType.RELATIVE_PATH,
            IssueType.PATH_MISMATCH,
            IssueType.HARDCODED_PATH
        }
        
        if issue_type not in auto_fixable_types:
            return False
        
        # Don't auto-fix very complex paths
        if '..' in matched_text and matched_text.count('..') > 3:
            return False
        
        return True
    
    def _generate_suggested_fix(self, issue_type: IssueType, matched_text: str,
                               file_path: Path, original_line: str) -> str:
        """Generate suggested fix for an issue."""
        if issue_type == IssueType.RELATIVE_PATH:
            # Convert to absolute path relative to base_dir
            rel_path = matched_text.strip('"\'')
            abs_path = (self.base_dir / rel_path).resolve()
            if abs_path.exists():
                return original_line.replace(matched_text, f'"{str(abs_path.relative_to(self.base_dir))}"')
        
        elif issue_type == IssueType.HARDCODED_PATH:
            # Try to make path relative to base_dir
            hard_path = Path(matched_text.strip('"\''))
            try:
                rel_path = hard_path.relative_to(self.base_dir)
                return original_line.replace(matched_text, f'"{str(rel_path)}"')
            except ValueError:
                # Path is not under base_dir
                pass
        
        elif issue_type == IssueType.PATH_MISMATCH:
            # Normalize path separators
            normalized = matched_text.replace('\\', '/')
            if normalized != matched_text:
                return original_line.replace(matched_text, normalized)
        
        return original_line  # No change
    
    def _calculate_confidence(self, issue_type: IssueType, matched_text: str) -> float:
        """Calculate confidence score for an issue (0.0 to 1.0)."""
        base_confidence = {
            IssueType.PATH_MISMATCH: 0.9,
            IssueType.HARDCODED_PATH: 0.85,
            IssueType.RELATIVE_PATH: 0.7,
            IssueType.IMPORT_ERROR: 0.6,
            IssueType.ENV_VARIABLE: 0.5,
            IssueType.SYNTAX_ERROR: 1.0,
        }.get(issue_type, 0.5)
        
        # Adjust based on pattern specifics
        if 'C:\\' in matched_text or 'D:\\' in matched_text:
            base_confidence = min(1.0, base_confidence + 0.1)
        
        return base_confidence
    
    def _get_dependencies(self, issue_type: IssueType, matched_text: str) -> List[str]:
        """Get dependencies for an issue."""
        if issue_type == IssueType.IMPORT_ERROR:
            module_name = matched_text.split()[-1].strip()
            return [module_name]
        
        return []


# =============================================================================
# FILE SCANNER
# =============================================================================

class FileScanner:
    """Scans files and directories for issues."""
    
    IGNORE_PATTERNS = {
        '.git', '__pycache__', '.pytest_cache', '.vscode', '.idea',
        'node_modules', 'venv', '.venv', 'env', '.env',
        'build', 'dist', '*.pyc', '*.pyo', '*.pyd',
        '*.so', '*.dll', '*.exe', '*.bin'
    }
    
    def __init__(self, base_dir: Path, deep_scan: bool = False):
        self.base_dir = base_dir.resolve()
        self.deep_scan = deep_scan
        self.pattern_matcher = PathPatternMatcher(self.base_dir)
        self.scan_results = []
        self.total_files = 0
        self.total_lines = 0
        
    def scan(self, target_path: Path) -> ScanResult:
        """Scan a file or directory."""
        start_time = time.time()
        target_path = target_path.resolve()
        
        if not target_path.exists():
            raise FileNotFoundError(f"Target not found: {target_path}")
        
        # Collect files to scan
        files_to_scan = []
        
        if target_path.is_file():
            files_to_scan = [target_path]
        elif target_path.is_dir():
            if self.deep_scan:
                files_to_scan = self._collect_files_deep(target_path)
            else:
                files_to_scan = self._collect_files_shallow(target_path)
        
        # Scan each file
        all_issues = []
        files_with_issues = []
        
        for file_path in files_to_scan:
            if self._should_ignore(file_path):
                continue
            
            issues = self.pattern_matcher.scan_file(file_path)
            
            if issues:
                all_issues.extend(issues)
                files_with_issues.append({
                    "path": str(file_path.relative_to(self.base_dir)),
                    "issues": len(issues),
                    "severities": [i.severity.value for i in issues]
                })
            
            self.total_files += 1
            
            # Count lines
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    self.total_lines += sum(1 for _ in f)
            except:
                pass
        
        # Categorize issues
        issues_by_severity = {}
        issues_by_type = {}
        
        for issue in all_issues:
            sev = issue.severity.value
            typ = issue.issue_type.value
            
            issues_by_severity[sev] = issues_by_severity.get(sev, 0) + 1
            issues_by_type[typ] = issues_by_type.get(typ, 0) + 1
        
        scan_duration = time.time() - start_time
        
        return ScanResult(
            target_path=target_path,
            scan_time=datetime.now().isoformat(),
            files_scanned=self.total_files,
            total_lines=self.total_lines,
            issues_by_severity=issues_by_severity,
            issues_by_type=issues_by_type,
            files_with_issues=files_with_issues,
            detailed_issues=all_issues,
            scan_duration_seconds=scan_duration,
            patterns_used=list(self.pattern_matcher.PATTERNS.keys())
        )
    
    def _collect_files_deep(self, directory: Path) -> List[Path]:
        """Collect all files recursively."""
        files = []
        
        for item in directory.rglob('*'):
            if item.is_file() and not self._should_ignore(item):
                files.append(item)
        
        return files
    
    def _collect_files_shallow(self, directory: Path) -> List[Path]:
        """Collect files only in the given directory."""
        files = []
        
        for item in directory.iterdir():
            if item.is_file() and not self._should_ignore(item):
                files.append(item)
        
        return files
    
    def _should_ignore(self, path: Path) -> bool:
        """Check if a path should be ignored."""
        path_str = str(path)
        
        # Check ignore patterns
        for pattern in self.IGNORE_PATTERNS:
            if pattern.startswith('*.'):
                # Extension pattern
                if path_str.endswith(pattern[1:]):
                    return True
            elif pattern in path.parts:
                # Directory/File name pattern
                return True
        
        return False


# =============================================================================
# SESSION MANAGER
# =============================================================================

class SessionManager:
    """Manages scanning/fixing sessions."""
    
    def __init__(self, sessions_dir: Path = None):
        if sessions_dir is None:
            sessions_dir = Path.cwd() / ".pathfixer_sessions"
        
        self.sessions_dir = sessions_dir
        self.sessions_dir.mkdir(parents=True, exist_ok=True)
        
        self.current_session = None
        self.snapshots_dir = self.sessions_dir / "snapshots"
        self.snapshots_dir.mkdir(exist_ok=True)
    
    def create_session(self, base_dir: Path, target_path: Path, 
                      deep_scan: bool = False) -> SessionState:
        """Create a new session."""
        session_id = f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        session = SessionState(
            session_id=session_id,
            created_at=datetime.now().isoformat(),
            base_directory=base_dir.resolve(),
            target_path=target_path.resolve(),
            deep_scan=deep_scan
        )
        
        self.current_session = session
        self._save_session(session)
        
        return session
    
    def load_session(self, session_id: str) -> Optional[SessionState]:
        """Load a session by ID."""
        session_file = self.sessions_dir / f"{session_id}.json"
        
        if not session_file.exists():
            return None
        
        with open(session_file, 'r', encoding='utf-8') as f:
            session_data = json.load(f)
        
        # Convert paths back to Path objects
        session_data['base_directory'] = Path(session_data['base_directory'])
        session_data['target_path'] = Path(session_data['target_path'])
        
        # Convert sets back from lists
        session_data['selected_files'] = set(session_data.get('selected_files', []))
        session_data['selected_issues'] = set(session_data.get('selected_issues', []))
        
        session = SessionState(**session_data)
        self.current_session = session
        
        return session
    
    def save_current_session(self):
        """Save the current session."""
        if self.current_session:
            self._save_session(self.current_session)
    
    def _save_session(self, session: SessionState):
        """Save a session to disk."""
        session_data = asdict(session)
        
        # Convert Path objects to strings
        session_data['base_directory'] = str(session.base_directory)
        session_data['target_path'] = str(session.target_path)
        
        # Convert sets to lists for JSON serialization
        session_data['selected_files'] = list(session.selected_files)
        session_data['selected_issues'] = list(session.selected_issues)
        
        session_file = self.sessions_dir / f"{session.session_id}.json"
        
        with open(session_file, 'w', encoding='utf-8') as f:
            json.dump(session_data, f, indent=2)
    
    def create_snapshot(self, file_path: Path) -> Path:
        """Create a snapshot of a file."""
        if not file_path.exists():
            raise FileNotFoundError(f"Cannot snapshot non-existent file: {file_path}")
        
        # Create snapshot filename
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        file_hash = hashlib.md5(str(file_path).encode()).hexdigest()[:8]
        snapshot_name = f"{file_path.stem}_{timestamp}_{file_hash}{file_path.suffix}"
        snapshot_path = self.snapshots_dir / snapshot_name
        
        # Copy file
        shutil.copy2(file_path, snapshot_path)
        
        # Update session
        if self.current_session:
            self.current_session.snapshots_created += 1
            self.save_current_session()
        
        return snapshot_path
    
    def get_snapshot_info(self, file_path: Path) -> List[Dict[str, Any]]:
        """Get information about snapshots for a file."""
        snapshots = []
        
        if not self.snapshots_dir.exists():
            return snapshots
        
        file_pattern = f"{file_path.stem}_*_{hashlib.md5(str(file_path).encode()).hexdigest()[:8]}{file_path.suffix}"
        
        for snapshot in self.snapshots_dir.glob(file_pattern):
            stat = snapshot.stat()
            snapshots.append({
                "path": snapshot,
                "created": datetime.fromtimestamp(stat.st_ctime).isoformat(),
                "size": stat.st_size,
                "hash": hashlib.md5(snapshot.read_bytes()).hexdigest()[:16]
            })
        
        return sorted(snapshots, key=lambda x: x["created"], reverse=True)
    
    def list_sessions(self) -> List[Dict[str, Any]]:
        """List all sessions."""
        sessions = []
        
        for session_file in self.sessions_dir.glob("session_*.json"):
            try:
                with open(session_file, 'r', encoding='utf-8') as f:
                    session_data = json.load(f)
                
                sessions.append({
                    "id": session_file.stem,
                    "created": session_data.get('created_at', ''),
                    "target": session_data.get('target_path', ''),
                    "files_scanned": session_data.get('files_scanned', 0),
                    "issues_found": session_data.get('issues_found', 0),
                    "issues_fixed": session_data.get('issues_fixed', 0)
                })
            except:
                continue
        
        return sorted(sessions, key=lambda x: x["created"], reverse=True)


# =============================================================================
# FIX MANAGER
# =============================================================================

class FixManager:
    """Manages fixing of issues."""
    
    def __init__(self, session_manager: SessionManager):
        self.session_manager = session_manager
        self.validation_results = []
        
    def create_fix_plan(self, issues: List[FileIssue]) -> FixPlan:
        """Create a plan for fixing issues."""
        plan_id = f"plan_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # Group issues by file
        issues_by_file = {}
        for issue in issues:
            file_str = str(issue.file_path)
            if file_str not in issues_by_file:
                issues_by_file[file_str] = []
            issues_by_file[file_str].append(issue)
        
        # Estimate changes
        estimated_changes = sum(len(issues) for issues in issues_by_file.values())
        
        # Determine risk level
        risk_level = self._calculate_risk_level(issues)
        
        # Create validation steps
        validation_steps = [
            {"step": 1, "description": "Create snapshots of all target files", "status": "pending"},
            {"step": 2, "description": "Validate syntax of original files", "status": "pending"},
            {"step": 3, "description": "Apply fixes to copied files", "status": "pending"},
            {"step": 4, "description": "Validate syntax of modified files", "status": "pending"},
            {"step": 5, "description": "Compare changes with original", "status": "pending"},
            {"step": 6, "description": "Create backup of successful changes", "status": "pending"},
        ]
        
        # Create rollback plan
        rollback_plan = {
            "snapshots": [],
            "steps": [
                "Restore from snapshots if validation fails",
                "Keep original files unchanged",
                "Log all changes for manual review"
            ]
        }
        
        return FixPlan(
            plan_id=plan_id,
            session_id=self.session_manager.current_session.session_id if self.session_manager.current_session else "",
            created_at=datetime.now().isoformat(),
            target_files=[Path(file) for file in issues_by_file.keys()],
            issues_to_fix=issues,
            estimated_changes=estimated_changes,
            risk_level=risk_level,
            validation_steps=validation_steps,
            rollback_plan=rollback_plan,
            prerequisites=["Backup original files", "Validate current state"]
        )
    
    def _calculate_risk_level(self, issues: List[FileIssue]) -> str:
        """Calculate risk level for fixing issues."""
        critical_count = sum(1 for i in issues if i.severity == IssueSeverity.CRITICAL)
        high_count = sum(1 for i in issues if i.severity == IssueSeverity.HIGH)
        
        if critical_count > 0:
            return "critical"
        elif high_count > 3:
            return "high"
        elif high_count > 0:
            return "medium"
        else:
            return "low"
    
    def apply_fix(self, issue: FileIssue, snapshot: bool = True) -> Dict[str, Any]:
        """Apply a fix to a single issue."""
        result = {
            "issue_id": issue.id,
            "file_path": str(issue.file_path),
            "success": False,
            "changes_made": 0,
            "validation_passed": False,
            "snapshot_created": None,
            "error": None
        }
        
        try:
            # Create snapshot if requested
            if snapshot:
                snapshot_path = self.session_manager.create_snapshot(issue.file_path)
                result["snapshot_created"] = str(snapshot_path)
            
            # Read original content
            content = issue.file_path.read_text(encoding='utf-8')
            lines = content.split('\n')
            
            # Apply fix
            if issue.line_number <= len(lines):
                original_line = lines[issue.line_number - 1]
                
                if issue.suggested_fix and issue.suggested_fix != original_line:
                    lines[issue.line_number - 1] = issue.suggested_fix
                    result["changes_made"] = 1
                    
                    # Write modified content
                    modified_content = '\n'.join(lines)
                    issue.file_path.write_text(modified_content, encoding='utf-8')
                    
                    # Validate syntax
                    try:
                        py_compile.compile(str(issue.file_path), doraise=True)
                        result["validation_passed"] = True
                        result["success"] = True
                        
                        # Update session
                        if self.session_manager.current_session:
                            self.session_manager.current_session.issues_fixed += 1
                            self.session_manager.save_current_session()
                        
                    except py_compile.PyCompileError as e:
                        result["error"] = f"Syntax validation failed: {e}"
                        # Revert changes
                        issue.file_path.write_text(content, encoding='utf-8')
                else:
                    result["error"] = "No fix suggested or fix is identical to original"
            else:
                result["error"] = f"Line number {issue.line_number} out of range"
                
        except Exception as e:
            result["error"] = f"Error applying fix: {str(e)}"
        
        return result
    
    def batch_fix(self, issues: List[FileIssue], snapshot: bool = True) -> List[Dict[str, Any]]:
        """Apply fixes to multiple issues."""
        results = []
        
        # Group issues by file
        issues_by_file = {}
        for issue in issues:
            file_str = str(issue.file_path)
            if file_str not in issues_by_file:
                issues_by_file[file_str] = []
            issues_by_file[file_str].append(issue)
        
        # Process each file
        for file_str, file_issues in issues_by_file.items():
            file_path = Path(file_str)
            
            # Sort issues by line number (descending) to avoid line number shifts
            file_issues.sort(key=lambda x: x.line_number, reverse=True)
            
            # Create snapshot for the file
            if snapshot:
                self.session_manager.create_snapshot(file_path)
            
            # Read original content
            try:
                content = file_path.read_text(encoding='utf-8')
                lines = content.split('\n')
                original_lines = lines.copy()
                
                changes_made = 0
                
                # Apply all fixes for this file
                for issue in file_issues:
                    if issue.line_number <= len(lines):
                        original_line = lines[issue.line_number - 1]
                        
                        if issue.suggested_fix and issue.suggested_fix != original_line:
                            lines[issue.line_number - 1] = issue.suggested_fix
                            changes_made += 1
                
                # Write modified content if changes were made
                if changes_made > 0:
                    modified_content = '\n'.join(lines)
                    file_path.write_text(modified_content, encoding='utf-8')
                    
                    # Validate syntax
                    try:
                        py_compile.compile(str(file_path), doraise=True)
                        
                        # Calculate diff
                        diff = list(difflib.unified_diff(
                            original_lines,
                            lines,
                            fromfile=f"original/{file_path.name}",
                            tofile=f"modified/{file_path.name}",
                            lineterm=''
                        ))
                        
                        result = {
                            "file_path": file_str,
                            "success": True,
                            "changes_made": changes_made,
                            "validation_passed": True,
                            "issues_fixed": len(file_issues),
                            "diff_lines": len(diff)
                        }
                        
                        # Update session
                        if self.session_manager.current_session:
                            self.session_manager.current_session.issues_fixed += len(file_issues)
                            self.session_manager.save_current_session()
                        
                    except py_compile.PyCompileError as e:
                        # Revert changes
                        file_path.write_text(content, encoding='utf-8')
                        result = {
                            "file_path": file_str,
                            "success": False,
                            "changes_made": 0,
                            "validation_passed": False,
                            "error": f"Syntax validation failed: {e}",
                            "issues_fixed": 0
                        }
                else:
                    result = {
                        "file_path": file_str,
                        "success": True,
                        "changes_made": 0,
                        "validation_passed": True,
                        "notes": "No changes needed",
                        "issues_fixed": 0
                    }
                
            except Exception as e:
                result = {
                    "file_path": file_str,
                    "success": False,
                    "changes_made": 0,
                    "validation_passed": False,
                    "error": f"Error processing file: {str(e)}",
                    "issues_fixed": 0
                }
            
            results.append(result)
        
        return results


# =============================================================================
# CLI INTERFACE
# =============================================================================

def print_header(text: str):
    """Print a formatted header."""
    print("\n" + "=" * 80)
    print(f" {text}")
    print("=" * 80)

def print_section(text: str):
    """Print a section header."""
    print(f"\n{text}")
    print("-" * len(text))

def print_issue(issue: FileIssue, show_context: bool = True):
    """Print an issue in a readable format."""
    severity_colors = {
        IssueSeverity.CRITICAL: "🔴",
        IssueSeverity.HIGH: "🟠",
        IssueSeverity.MEDIUM: "🟡",
        IssueSeverity.LOW: "🟢",
        IssueSeverity.INFO: "🔵"
    }
    
    color = severity_colors.get(issue.severity, "⚪")
    
    print(f"{color} [{issue.severity.value.upper():8}] {issue.description}")
    print(f"   File: {issue.file_path.relative_to(Path.cwd())}:{issue.line_number}")
    print(f"   Type: {issue.issue_type.value}")
    
    if show_context:
        if issue.context_before:
            for i, line in enumerate(issue.context_before):
                print(f"   {issue.line_number - len(issue.context_before) + i:4}: {line}")
        
        print(f"   {issue.line_number:4}: {issue.original_line}")
        
        if issue.context_after:
            for i, line in enumerate(issue.context_after, 1):
                print(f"   {issue.line_number + i:4}: {line}")
    
    if issue.suggested_fix:
        print(f"   Fix: {issue.suggested_fix}")
    
    if issue.auto_fixable:
        print(f"   ⚡ Auto-fixable")
    
    print()

def interactive_selection_menu(items: List[Any], item_type: str = "item") -> List[int]:
    """Display an interactive selection menu."""
    if not items:
        return []
    
    print(f"\nSelect {item_type}s (comma-separated numbers, 'all', or 'none'):")
    
    for i, item in enumerate(items, 1):
        if isinstance(item, FileIssue):
            print(f"  [{i:3}] {item.file_path.name}:{item.line_number} - {item.description[:50]}...")
        elif isinstance(item, dict) and 'path' in item:
            print(f"  [{i:3}] {item['path']} ({item.get('issues', 0)} issues)")
        else:
            print(f"  [{i:3}] {str(item)[:60]}...")
    
    while True:
        selection = input("\nSelection: ").strip().lower()
        
        if selection == 'all':
            return list(range(len(items)))
        elif selection == 'none':
            return []
        elif selection == 'q' or selection == 'quit':
            return []
        
        try:
            selected_indices = []
            for part in selection.split(','):
                part = part.strip()
                if '-' in part:
                    # Range selection
                    start, end = map(int, part.split('-'))
                    selected_indices.extend(range(start - 1, end))
                else:
                    # Single selection
                    selected_indices.append(int(part) - 1)
            
            # Validate indices
            valid_indices = [i for i in selected_indices if 0 <= i < len(items)]
            
            if valid_indices:
                return valid_indices
            else:
                print("Invalid selection. Please try again.")
                
        except ValueError:
            print("Invalid input. Please enter numbers, 'all', 'none', or 'q' to quit.")

def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="PathFixer - File System Consistency Scanner & Fixer",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Scan a single file
  pathfixer.py scan my_script.py
  
  # Deep scan a directory
  pathfixer.py scan my_project/ --deep
  
  # Start interactive session
  pathfixer.py session start my_project/ --deep
  
  # Continue existing session
  pathfixer.py session continue SESSION_ID
  
  # List all sessions
  pathfixer.py session list
  
  # Fix specific issues interactively
  pathfixer.py fix --interactive
  
  # Batch fix with selection
  pathfixer.py fix --select 1,3,5-7
  
  # Create snapshot before fixing
  pathfixer.py fix --snapshot
  
  # Validate files after changes
  pathfixer.py validate my_project/
  
  # Show session summary
  pathfixer.py summary SESSION_ID

Quick Reference:
  - Use letters A-Z for quick file selection: -f A,C,E
  - Use numbers 1-N for issue selection: -i 1,3,5-7
  - Combine selections: -f A,B -i 1-3
  - Use --snapshot for safe editing
  - Use --deep for recursive scanning
  - Use --session to work within a session context

Session Workflow:
  1. Start session: pathfixer.py session start <target>
  2. Scan for issues: pathfixer.py scan (within session)
  3. Review issues: pathfixer.py summary
  4. Select fixes: pathfixer.py fix --interactive
  5. Apply fixes: pathfixer.py fix --apply
  6. Validate: pathfixer.py validate
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Command to execute')
    
    # Scan command
    scan_parser = subparsers.add_parser('scan', help='Scan files for issues')
    scan_parser.add_argument('target', help='File or directory to scan')
    scan_parser.add_argument('--deep', '-d', action='store_true', help='Recursive deep scan')
    scan_parser.add_argument('--output', '-o', help='Output results to JSON file')
    scan_parser.add_argument('--brief', '-b', action='store_true', help='Brief output')
    scan_parser.add_argument('--session', '-s', help='Session ID to associate with scan')
    
    # Session commands
    session_parser = subparsers.add_parser('session', help='Session management')
    session_subparsers = session_parser.add_subparsers(dest='session_command', help='Session command')
    
    # Start session
    start_parser = session_subparsers.add_parser('start', help='Start new session')
    start_parser.add_argument('target', help='Target file or directory')
    start_parser.add_argument('--deep', '-d', action='store_true', help='Deep scan mode')
    start_parser.add_argument('--name', '-n', help='Session name')
    
    # Continue session
    continue_parser = session_subparsers.add_parser('continue', help='Continue existing session')
    continue_parser.add_argument('session_id', help='Session ID to continue')
    
    # List sessions
    session_subparsers.add_parser('list', help='List all sessions')
    
    # Fix command
    fix_parser = subparsers.add_parser('fix', help='Fix detected issues')
    fix_parser.add_argument('--issues', '-i', help='Issue IDs to fix (comma-separated or range)')
    fix_parser.add_argument('--files', '-f', help='File letters to fix (A,B,C or A-C)')
    fix_parser.add_argument('--all', '-a', action='store_true', help='Fix all auto-fixable issues')
    fix_parser.add_argument('--interactive', '-I', action='store_true', help='Interactive selection')
    fix_parser.add_argument('--snapshot', '-S', action='store_true', help='Create snapshots before fixing')
    fix_parser.add_argument('--apply', action='store_true', help='Apply fixes (without this, just show plan)')
    fix_parser.add_argument('--dry-run', action='store_true', help='Show what would be fixed without applying')
    fix_parser.add_argument('--session', '-s', help='Session ID')
    
    # Validate command
    validate_parser = subparsers.add_parser('validate', help='Validate files')
    validate_parser.add_argument('target', nargs='?', help='File or directory to validate')
    validate_parser.add_argument('--syntax', action='store_true', help='Check Python syntax')
    validate_parser.add_argument('--imports', action='store_true', help='Check imports')
    validate_parser.add_argument('--session', '-s', help='Session ID')
    
    # Summary command
    summary_parser = subparsers.add_parser('summary', help='Show session summary')
    summary_parser.add_argument('session_id', nargs='?', help='Session ID (current if not specified)')
    summary_parser.add_argument('--detailed', '-d', action='store_true', help='Detailed output')
    
    # Snapshot command
    snapshot_parser = subparsers.add_parser('snapshot', help='Snapshot management')
    snapshot_parser.add_argument('file', nargs='?', help='File to snapshot')
    snapshot_parser.add_argument('--create', '-c', action='store_true', help='Create snapshot')
    snapshot_parser.add_argument('--list', '-l', action='store_true', help='List snapshots')
    snapshot_parser.add_argument('--restore', '-r', help='Restore from snapshot ID')
    snapshot_parser.add_argument('--session', '-s', help='Session ID')
    
    # Checklist command
    checklist_parser = subparsers.add_parser('checklist', help='Generate/display checklist')
    checklist_parser.add_argument('--generate', '-g', action='store_true', help='Generate checklist')
    checklist_parser.add_argument('--show', action='store_true', help='Show current checklist')
    checklist_parser.add_argument('--mark', '-m', help='Mark item as done (format: 1,2,3 or 1-3)')
    checklist_parser.add_argument('--session', '-s', help='Session ID')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    # Initialize session manager
    session_manager = SessionManager()
    
    # Handle commands
    if args.command == 'scan':
        scan_command(args, session_manager)
    
    elif args.command == 'session':
        session_command(args, session_manager)
    
    elif args.command == 'fix':
        fix_command(args, session_manager)
    
    elif args.command == 'validate':
        validate_command(args, session_manager)
    
    elif args.command == 'summary':
        summary_command(args, session_manager)
    
    elif args.command == 'snapshot':
        snapshot_command(args, session_manager)
    
    elif args.command == 'checklist':
        checklist_command(args, session_manager)
    
    else:
        parser.print_help()

def scan_command(args, session_manager: SessionManager):
    """Handle scan command."""
    target_path = Path(args.target).resolve()
    
    # Check if we're in a session
    current_session = None
    if args.session:
        current_session = session_manager.load_session(args.session)
    elif session_manager.current_session:
        current_session = session_manager.current_session
    
    # Create scanner
    base_dir = current_session.base_directory if current_session else Path.cwd()
    scanner = FileScanner(base_dir, args.deep)
    
    print_header(f"SCANNING: {target_path}")
    print(f"Mode: {'Deep recursive' if args.deep else 'Shallow'}")
    print(f"Base directory: {base_dir}")
    
    # Perform scan
    try:
        result = scanner.scan(target_path)
        
        # Print summary
        print_section("SCAN RESULTS")
        print(f"Files scanned: {result.files_scanned}")
        print(f"Total lines: {result.total_lines}")
        print(f"Scan duration: {result.scan_duration_seconds:.2f} seconds")
        
        print(f"\nIssues found: {len(result.detailed_issues)}")
        for severity, count in result.issues_by_severity.items():
            print(f"  {severity}: {count}")
        
        # Print files with issues
        if result.files_with_issues:
            print_section("FILES WITH ISSUES")
            for i, file_info in enumerate(result.files_with_issues[:20], 1):  # Limit to 20
                print(f"[{chr(64 + i)}] {file_info['path']} ({file_info['issues']} issues)")
        
        # Print detailed issues if not brief
        if not args.brief and result.detailed_issues:
            print_section("DETAILED ISSUES")
            for i, issue in enumerate(result.detailed_issues[:50], 1):  # Limit to 50
                print(f"Issue {i}:")
                print_issue(issue, show_context=True)
        
        # Save to file if requested
        if args.output:
            output_path = Path(args.output)
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(asdict(result), f, indent=2, default=str)
            print(f"\nResults saved to: {output_path}")
        
        # Update session if we have one
        if current_session:
            current_session.files_scanned = result.files_scanned
            current_session.issues_found = len(result.detailed_issues)
            session_manager.save_current_session()
            
            # Store scan results in session log
            scan_log = {
                "timestamp": datetime.now().isoformat(),
                "action": "scan",
                "target": str(target_path),
                "files_scanned": result.files_scanned,
                "issues_found": len(result.detailed_issues),
                "scan_id": hashlib.md5(str(target_path).encode()).hexdigest()[:8]
            }
            current_session.session_log.append(scan_log)
            session_manager.save_current_session()
        
    except Exception as e:
        print(f"Error during scan: {e}")
        import traceback
        traceback.print_exc()

def session_command(args, session_manager: SessionManager):
    """Handle session commands."""
    if args.session_command == 'start':
        target_path = Path(args.target).resolve()
        
        session = session_manager.create_session(
            base_dir=Path.cwd(),
            target_path=target_path,
            deep_scan=args.deep
        )
        
        print_header(f"SESSION STARTED: {session.session_id}")
        print(f"Target: {target_path}")
        print(f"Deep scan: {'Yes' if args.deep else 'No'}")
        print(f"Created: {session.created_at}")
        print(f"\nTo continue: pathfixer.py session continue {session.session_id}")
        
        # Do initial scan
        print("\nPerforming initial scan...")
        scanner = FileScanner(session.base_directory, args.deep)
        result = scanner.scan(target_path)
        
        session.files_scanned = result.files_scanned
        session.issues_found = len(result.detailed_issues)
        session_manager.save_current_session()
        
        print(f"Found {session.issues_found} issues in {session.files_scanned} files")
        
    elif args.session_command == 'continue':
        session = session_manager.load_session(args.session_id)
        if session:
            print_header(f"SESSION CONTINUED: {session.session_id}")
            print(f"Target: {session.target_path}")
            print(f"Files scanned: {session.files_scanned}")
            print(f"Issues found: {session.issues_found}")
            print(f"Issues fixed: {session.issues_fixed}")
            print(f"Created: {session.created_at}")
            
            # Set as current session
            session_manager.current_session = session
        else:
            print(f"Session not found: {args.session_id}")
            
    elif args.session_command == 'list':
        sessions = session_manager.list_sessions()
        
        print_header("SESSIONS")
        
        if not sessions:
            print("No sessions found.")
            return
        
        for session in sessions:
            print(f"{session['id']}")
            print(f"  Target: {session['target']}")
            print(f"  Created: {session['created']}")
            print(f"  Issues: {session['issues_found']} found, {session['issues_fixed']} fixed")
            print()

def fix_command(args, session_manager: SessionManager):
    """Handle fix command."""
    # Check if we have a session
    if args.session:
        session = session_manager.load_session(args.session)
        if not session:
            print(f"Session not found: {args.session}")
            return
        session_manager.current_session = session
    elif not session_manager.current_session:
        print("No active session. Start a session first or specify one with --session")
        return
    
    session = session_manager.current_session
    
    # We need scan results to fix issues
    # For now, we'll just show how the fix command would work
    print_header("FIX COMMAND")
    print(f"Session: {session.session_id}")
    print(f"Issues found in session: {session.issues_found}")
    print(f"Issues already fixed: {session.issues_fixed}")
    
    # In a real implementation, we would:
    # 1. Load the scan results for this session
    # 2. Filter issues based on selection criteria (--issues, --files, --all)
    # 3. Create a fix plan
    # 4. Show the plan or apply fixes based on --apply flag
    
    if args.dry_run:
        print("\nDRY RUN: No changes will be made.")
    
    if args.snapshot:
        print("Snapshots will be created before fixing.")
    
    if args.interactive:
        print("Interactive selection mode.")
        # Here we would show an interactive menu
        
    print("\nFix functionality requires scan results to be loaded.")
    print("Run 'scan' command first or continue an existing session.")

def validate_command(args, session_manager: SessionManager):
    """Handle validate command."""
    target_path = Path(args.target).resolve() if args.target else None
    
    print_header("VALIDATION")
    
    # Check syntax
    if args.syntax or (not args.imports):
        print("Checking Python syntax...")
        
        if target_path and target_path.is_file():
            files_to_check = [target_path]
        elif target_path and target_path.is_dir():
            files_to_check = list(target_path.rglob("*.py"))
        else:
            # Check current directory
            files_to_check = list(Path.cwd().rglob("*.py"))
        
        valid_files = 0
        invalid_files = []
        
        for py_file in files_to_check[:100]:  # Limit to 100 files
            try:
                py_compile.compile(str(py_file), doraise=True)
                valid_files += 1
            except py_compile.PyCompileError as e:
                invalid_files.append((py_file, str(e)))
        
        print(f"Python files checked: {len(files_to_check)}")
        print(f"Valid files: {valid_files}")
        print(f"Invalid files: {len(invalid_files)}")
        
        if invalid_files:
            print("\nInvalid files:")
            for file, error in invalid_files[:10]:  # Show first 10
                print(f"  {file}: {error[:100]}...")
    
    # Check imports
    if args.imports:
        print("\nImport checking not fully implemented.")
        print("Use 'scan' command to detect import issues.")

def summary_command(args, session_manager: SessionManager):
    """Handle summary command."""
    session_id = args.session_id
    
    if session_id:
        session = session_manager.load_session(session_id)
    else:
        session = session_manager.current_session
    
    if not session:
        print("No session specified and no active session.")
        return
    
    print_header(f"SESSION SUMMARY: {session.session_id}")
    
    print(f"Created: {session.created_at}")
    print(f"Target: {session.target_path}")
    print(f"Deep scan: {'Yes' if session.deep_scan else 'No'}")
    print()
    print(f"Files scanned: {session.files_scanned}")
    print(f"Issues found: {session.issues_found}")
    print(f"Issues fixed: {session.issues_fixed}")
    print(f"Snapshots created: {session.snapshots_created}")
    print(f"Current step: {session.current_step}")
    
    if args.detailed and session.session_log:
        print_section("SESSION LOG")
        for log_entry in session.session_log[-10:]:  # Last 10 entries
            print(f"{log_entry.get('timestamp', '')}: {log_entry.get('action', '')}")
    
    if args.detailed and session.checklist:
        print_section("CHECKLIST")
        for item in session.checklist:
            status = "✓" if item.get('completed', False) else " "
            print(f"[{status}] {item.get('description', '')}")

def snapshot_command(args, session_manager: SessionManager):
    """Handle snapshot commands."""
    if args.create and args.file:
        file_path = Path(args.file).resolve()
        
        if file_path.exists():
            snapshot_path = session_manager.create_snapshot(file_path)
            print(f"Snapshot created: {snapshot_path}")
        else:
            print(f"File not found: {file_path}")
    
    elif args.list and args.file:
        file_path = Path(args.file).resolve()
        snapshots = session_manager.get_snapshot_info(file_path)
        
        if snapshots:
            print_header(f"SNAPSHOTS FOR: {file_path}")
            for i, snap in enumerate(snapshots, 1):
                print(f"{i}. {snap['path'].name}")
                print(f"   Created: {snap['created']}")
                print(f"   Size: {snap['size']} bytes")
                print(f"   Hash: {snap['hash']}")
                print()
        else:
            print(f"No snapshots found for: {file_path}")
    
    elif args.restore:
        print("Restore functionality not implemented in this example.")
    
    else:
        print("Snapshot command requires --create, --list, or --restore")

def checklist_command(args, session_manager: SessionManager):
    """Handle checklist commands."""
    # Check if we have a session
    if args.session:
        session = session_manager.load_session(args.session)
        if not session:
            print(f"Session not found: {args.session}")
            return
        session_manager.current_session = session
    elif not session_manager.current_session:
        print("No active session.")
        return
    
    session = session_manager.current_session
    
    if args.generate:
        # Generate a default checklist
        checklist = [
            {"id": 1, "description": "Backup original files", "completed": False},
            {"id": 2, "description": "Scan for path issues", "completed": False},
            {"id": 3, "description": "Review detected issues", "completed": False},
            {"id": 4, "description": "Create fix plan", "completed": False},
            {"id": 5, "description": "Apply fixes to copies", "completed": False},
            {"id": 6, "description": "Validate modified files", "completed": False},
            {"id": 7, "description": "Compare changes with original", "completed": False},
            {"id": 8, "description": "Apply fixes to original", "completed": False},
            {"id": 9, "description": "Final validation", "completed": False},
            {"id": 10, "description": "Document changes", "completed": False},
        ]
        
        session.checklist = checklist
        session_manager.save_current_session()
        print("Checklist generated.")
    
    if args.show:
        if not session.checklist:
            print("No checklist. Generate one with --generate")
            return
        
        print_header(f"CHECKLIST - Session: {session.session_id}")
        for item in session.checklist:
            status = "✓" if item.get('completed', False) else " "
            print(f"[{status}] {item['id']:2}. {item['description']}")
    
    if args.mark:
        if not session.checklist:
            print("No checklist to mark.")
            return
        
        # Parse mark selection
        try:
            items_to_mark = []
            for part in args.mark.split(','):
                part = part.strip()
                if '-' in part:
                    start, end = map(int, part.split('-'))
                    items_to_mark.extend(range(start, end + 1))
                else:
                    items_to_mark.append(int(part))
            
            # Mark items as completed
            for item in session.checklist:
                if item['id'] in items_to_mark:
                    item['completed'] = True
            
            session_manager.save_current_session()
            print(f"Marked items {args.mark} as completed.")
            
        except ValueError:
            print("Invalid mark specification. Use format: 1,2,3 or 1-3")

if __name__ == "__main__":
    main()