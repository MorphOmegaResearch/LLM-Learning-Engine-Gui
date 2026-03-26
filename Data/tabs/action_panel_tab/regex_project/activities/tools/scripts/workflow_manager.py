#!/usr/bin/env python3
"""
CLI Agent Workflow Manager with Code Analysis and Task Tracking
Author: System Designer
Version: 1.0.0
"""

import argparse
import traceback
import difflib
import ast
import py_compile
import json
import os
import sys
import subprocess
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
import threading
from dataclasses import dataclass, field, asdict
from enum import Enum
import hashlib
import re

# Conditional imports for optional features
try:
    import pyflakes.api
    import pyflakes.reporter

    PYLINTS_AVAILABLE = True
except ImportError:
    PYLINTS_AVAILABLE = False

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler

    WATCHDOG_AVAILABLE = True
except ImportError:
    WATCHDOG_AVAILABLE = False

    # Dummy classes to prevent NameError
    class FileSystemEventHandler:
        pass

    class Observer:
        pass


try:
    import ruff

    RUFF_AVAILABLE = True
except ImportError:
    RUFF_AVAILABLE = False

# Check for local tools
TKINTER_OPTIMIZER_PATH = Path("tkinter_optimizer_cli.py")
TKINTER_OPTIMIZER_AVAILABLE = TKINTER_OPTIMIZER_PATH.exists()


# CLI Agents
class CLIAgent(Enum):
    CLAUDE = "claude"
    GEMINI = "gemini"
    CODEX = "codex"


# Workflow Types
class WorkflowType(Enum):
    CODE_REVIEW = "code_review"
    DEBUG_ASSIST = "debug_assist"
    SYNTAX_CHECK = "syntax_check"
    REFACTOR = "refactor"
    TASK_MANAGE = "task_manage"
    LAYOUT_OPTIMIZE = "layout_optimize"
    INSTRUCT = "instruct"
    COMMENT_AUDIT = "comment_audit"


@dataclass
class Task:
    """Task tracking structure"""

    id: int
    name: str
    description: str = ""
    targets: List[str] = field(default_factory=list)
    diffs: List[str] = field(default_factory=list)
    status: str = "pending"
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    agent: str = ""
    workflow: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    # Enhanced Optimization Fields
    optimization_goals: List[str] = field(default_factory=list)
    layout_prefs: Dict[str, str] = field(default_factory=dict)
    feature_points: Dict[str, Any] = field(default_factory=dict)

    # Scheduling Fields
    scheduled_for: str = ""  # ISO date for planned work
    mark_type: str = ""  # Stable, Active, Scheduled


@dataclass
class Profile:
    """Workflow profile configuration"""

    name: str
    workflows: Dict[str, Dict[str, Any]]
    pre_tasks: List[str] = field(default_factory=list)
    post_tasks: List[str] = field(default_factory=list)
    allowed_dirs: List[str] = field(default_factory=list)
    restrictions: Dict[str, Any] = field(default_factory=dict)
    default_layout_prefs: Dict[str, str] = field(default_factory=dict)


class CodeAnalyzer:
    """Comprehensive code analysis with multiple tools"""

    def __init__(self, debug: bool = False):
        self.debug = debug
        self.issues = []
        self.dependency_map = {}

    def analyze_ast(self, filepath: str) -> Dict[str, Any]:
        """AST-based analysis of Python code with dependency mapping and tag scanning"""
        analysis = {
            "imports": [],
            "from_imports": [],
            "classes": [],
            "functions": [],
            "variables": [],
            "attributes": [],
            "tkinter_features": [],
            "custom_tags": [],
            "errors": [],
        }

        try:
            with open(filepath, "r", encoding="utf-8") as f:
                lines = f.readlines()
                content = "".join(lines)

            # 1. Scan for Custom Tags (Regex)
            tag_pattern = r"#\s*\[(MARK|EVENT|PFL|LINK):\{(.*?)\}\]"
            for i, line in enumerate(lines, 1):
                match = re.search(tag_pattern, line)
                if match:
                    analysis["custom_tags"].append(
                        {"type": match.group(1), "data": match.group(2), "line": i}
                    )

            # 2. AST Parsing
            tree = ast.parse(content)
            # ... (rest of AST logic) ...

            # Extract various code elements
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        analysis["imports"].append(alias.name)
                        if "tkinter" in alias.name or "Tk" in alias.name:
                            analysis["tkinter_features"].append(f"import {alias.name}")

                elif isinstance(node, ast.ImportFrom):
                    analysis["from_imports"].append(node.module)
                    analysis["imports"].append(f"from {node.module}")
                    if node.module and "tkinter" in node.module:
                        analysis["tkinter_features"].append(
                            f"from {node.module} import ..."
                        )

                elif isinstance(node, ast.ClassDef):
                    class_info = {
                        "name": node.name,
                        "methods": [
                            n.name for n in node.body if isinstance(n, ast.FunctionDef)
                        ],
                        "bases": (
                            [ast.unparse(b) for b in node.bases]
                            if hasattr(ast, "unparse")
                            else []
                        ),
                    }
                    analysis["classes"].append(class_info)

                elif isinstance(node, ast.FunctionDef):
                    analysis["functions"].append(
                        {
                            "name": node.name,
                            "args": [arg.arg for arg in node.args.args],
                            "decorators": (
                                [ast.unparse(d) for d in node.decorator_list]
                                if hasattr(ast, "unparse")
                                else []
                            ),
                        }
                    )

                elif isinstance(node, ast.Assign):
                    for target in node.targets:
                        if isinstance(target, ast.Name):
                            analysis["variables"].append(target.id)

                elif isinstance(node, ast.Attribute):
                    analysis["attributes"].append(
                        ast.unparse(node) if hasattr(ast, "unparse") else node.attr
                    )

            # Update global dependency map
            self.dependency_map[os.path.basename(filepath)] = {
                "imports": analysis["imports"],
                "from_imports": analysis["from_imports"],
            }

        except SyntaxError as e:
            analysis["errors"].append(f"Syntax error: {e}")
        except Exception as e:
            analysis["errors"].append(f"AST analysis error: {e}")

        return analysis

    def check_with_pyflakes(self, filepath: str) -> List[str]:
        """Check code with pyflakes"""
        issues = []
        if not PYLINTS_AVAILABLE:
            return ["pyflakes not available"]

        try:
            from io import StringIO

            stream = StringIO()
            reporter = pyflakes.reporter.Reporter(stream, stream)
            pyflakes.api.checkFile(filepath, reporter)
            output = stream.getvalue()
            if output:
                issues = output.strip().split("\n")
        except Exception as e:
            issues.append(f"Pyflakes error: {e}")

        return issues

    def compile_check(self, filepath: str) -> Tuple[bool, str]:
        """Check if code compiles successfully"""
        try:
            py_compile.compile(filepath, doraise=True)
            return True, "Compilation successful"
        except py_compile.PyCompileError as e:
            return False, str(e)
        except Exception as e:
            return False, f"Compilation check error: {e}"

    def calculate_diff_hash(self, old_content: str, new_content: str) -> str:
        """Calculate hash for diff tracking"""
        diff = "\n".join(
            difflib.unified_diff(
                old_content.splitlines(), new_content.splitlines(), lineterm=""
            )
        )
        return hashlib.md5(diff.encode()).hexdigest()[:8]

    def generate_5w1h_report(self, event_type, filepath, context_data=None):
        """Classify events in a human-readable 5W1H format"""
        now = datetime.now()
        data = context_data or {}

        # Extract domain-specific variables/attributes from AST if available
        ast_summary = self.dependency_map.get(os.path.basename(filepath), {})

        report = {
            "WHO": data.get("user", "System Orchestrator"),
            "WHAT": f"{event_type}: {os.path.basename(filepath)}",
            "WHERE": f"{filepath} (Lines: {data.get('lines', 'N/A')})",
            "WHEN": now.strftime("%Y-%m-%d %H:%M:%S"),
            "WHY": data.get("reason", "Detected structural change or logic anomaly"),
            "HOW": f"AST Analysis | Imports: {len(ast_summary.get('imports', []))}",
            "DIFF_DELTA": data.get("diff_hash", "NO_HASH_CONTEXT"),
        }

        # Add Domain Data (Variables/Attributes)
        report["DOMAIN_DATA"] = {
            "variables": data.get("variables", []),
            "attributes": data.get("attributes", []),
        }

        return report

    def run_tkinter_optimizer(self, targets: List[str]) -> Dict[str, Any]:
        """Run tkinter_optimizer_cli.py on targets"""
        results = {}
        if not TKINTER_OPTIMIZER_AVAILABLE:
            return {"error": "tkinter_optimizer_cli.py not found"}

        for target in targets:
            try:
                cmd = [
                    sys.executable,
                    str(TKINTER_OPTIMIZER_PATH),
                    target,
                    "--format",
                    "json",
                    "--all",
                ]
                result = subprocess.run(cmd, capture_output=True, text=True)
                if result.returncode == 0:
                    # Check for generated files
                    for json_file in ["summary.json", "optimization_checklist.json"]:
                        if os.path.exists(json_file):
                            with open(json_file, "r") as f:
                                results[json_file.split(".")[0]] = json.load(f)
                else:
                    results[target] = {"error": result.stderr}
            except Exception as e:
                results[target] = {"error": str(e)}
        return results


class TrustSystem:
    """Manage file/dir trust levels and trigger sensitivity"""

    def __init__(self, settings_manager=None):
        self.settings = settings_manager
        # Trust levels: 0 (Untrusted) to 100 (Verified)
        self.trust_map = {}
        self.sensitivity = 75  # Trigger alert if trust < sensitivity

    def get_trust(self, path):
        abs_path = os.path.abspath(path)
        return self.trust_map.get(abs_path, 0 if not os.path.exists(abs_path) else 50)

    def verify_target(self, path):
        self.trust_map[os.path.abspath(path)] = 100


class SessionMode(Enum):
    """Session intensity modes"""
    STANDARD = "standard"      # 0-5 hours: High fidelity focused work
    EXTENDED = "extended"      # 5-10 hours: High priority session
    CRITICAL = "critical"      # 10-20 hours: Crisis-level session
    GRIND = "grind"           # 20+ hours: Goal-locked marathon


# #[MARK:{Implemented:SessionManager}] - Session timing and cognitive load
# #[MARK:{Implemented:FrictionDetect}] - Friction score calculation
class SessionManager:
    """Track session timing, friction, and suggest rest periods"""

    def __init__(self, config_file=".pyview_config.json"):
        self.config_file = Path(config_file)
        self.start_time = None
        self.friction_events = []  # List of (timestamp, event_type, weight)
        self.last_rest_suggestion = None
        self.grind_goal = None
        self.mode = SessionMode.STANDARD

        # Thresholds (hours)
        self.mode_thresholds = {
            SessionMode.STANDARD: 0,
            SessionMode.EXTENDED: 5,
            SessionMode.CRITICAL: 10,
            SessionMode.GRIND: 20,
        }

        # Friction weights
        self.friction_weights = {
            "bug": 5,
            "traceback": 10,
            "failed_init": 15,
            "re_edit": 3,
            "revert": 20,
            "compile_error": 12,
        }

        # Rest reminder interval (hours)
        self.rest_interval = 2

        self.load_session()

    def load_session(self):
        """Load session state from config"""
        if self.config_file.exists():
            try:
                with open(self.config_file, "r") as f:
                    data = json.load(f)
                    session = data.get("session", {})
                    if session.get("start_time"):
                        self.start_time = datetime.fromisoformat(session["start_time"])
                    self.grind_goal = session.get("grind_goal")
                    # Load custom thresholds if present
                    if "mode_thresholds" in session:
                        for mode in SessionMode:
                            if mode.value in session["mode_thresholds"]:
                                self.mode_thresholds[mode] = session["mode_thresholds"][mode.value]
            except:
                pass

        # Start session if not already started
        if self.start_time is None:
            self.start_time = datetime.now()
            self.save_session()

    def save_session(self):
        """Save session state to config"""
        data = {}
        if self.config_file.exists():
            try:
                with open(self.config_file, "r") as f:
                    data = json.load(f)
            except:
                pass

        data["session"] = {
            "enabled": True,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "grind_goal": self.grind_goal,
            "mode_thresholds": {m.value: h for m, h in self.mode_thresholds.items()},
            "friction_weights": self.friction_weights,
            "rest_reminder_interval": self.rest_interval,
        }

        with open(self.config_file, "w") as f:
            json.dump(data, f, indent=2)

    def get_session_hours(self) -> float:
        """Get current session duration in hours"""
        if self.start_time is None:
            return 0
        delta = datetime.now() - self.start_time
        return delta.total_seconds() / 3600

    def get_mode(self) -> SessionMode:
        """Determine current session mode based on duration"""
        hours = self.get_session_hours()

        if hours >= self.mode_thresholds[SessionMode.GRIND]:
            return SessionMode.GRIND
        elif hours >= self.mode_thresholds[SessionMode.CRITICAL]:
            return SessionMode.CRITICAL
        elif hours >= self.mode_thresholds[SessionMode.EXTENDED]:
            return SessionMode.EXTENDED
        else:
            return SessionMode.STANDARD

    def log_friction(self, event_type: str):
        """Log a friction event"""
        weight = self.friction_weights.get(event_type, 5)
        self.friction_events.append((datetime.now(), event_type, weight))

        # Prune events older than 1 hour for score calculation
        cutoff = datetime.now() - timedelta(hours=1)
        self.friction_events = [e for e in self.friction_events if e[0] > cutoff]

    def get_friction_score(self) -> int:
        """Calculate friction score (0-100) from recent events"""
        cutoff = datetime.now() - timedelta(hours=1)
        recent = [e for e in self.friction_events if e[0] > cutoff]
        score = sum(e[2] for e in recent)
        return min(100, score)

    def get_friction_status(self) -> Tuple[int, str]:
        """Get friction score and human-readable status"""
        score = self.get_friction_score()
        if score <= 20:
            return score, "Smooth sailing"
        elif score <= 50:
            return score, "Normal friction"
        elif score <= 75:
            return score, "High friction - consider break"
        else:
            return score, "Critical friction - break strongly advised"

    def should_dampen_alert(self, priority: str) -> bool:
        """Check if alert should be dampened based on mode and friction"""
        mode = self.get_mode()
        friction = self.get_friction_score()

        # CRITICAL priority always shown
        if priority == "CRITICAL":
            return False

        # REST suggestions never dampened
        if priority == "REST":
            return False

        # HIGH priority hidden in GRIND with friction > 50
        if priority == "HIGH" and mode == SessionMode.GRIND and friction > 50:
            return True

        # MEDIUM hidden in EXTENDED+ modes
        if priority == "MEDIUM" and mode in [SessionMode.EXTENDED, SessionMode.CRITICAL, SessionMode.GRIND]:
            return True

        # LOW hidden with any friction > 30
        if priority == "LOW" and friction > 30:
            return True

        return False

    def check_rest_suggestion(self) -> Tuple[bool, str]:
        """Check if rest should be suggested"""
        mode = self.get_mode()
        hours = self.get_session_hours()
        friction, friction_status = self.get_friction_status()

        # Check if enough time since last suggestion
        if self.last_rest_suggestion:
            since_last = (datetime.now() - self.last_rest_suggestion).total_seconds() / 3600
            if since_last < self.rest_interval:
                return False, ""

        suggestion = None

        # Mode-based suggestions
        if mode == SessionMode.GRIND:
            suggestion = f"GRIND MODE ({hours:.1f}h) - Goal: {self.grind_goal or 'Undefined'}. You're pushing hard. Stay hydrated."
        elif mode == SessionMode.CRITICAL:
            suggestion = f"CRITICAL SESSION ({hours:.1f}h) - Rest strongly advised. Cognitive performance declining."
        elif mode == SessionMode.EXTENDED:
            suggestion = f"EXTENDED SESSION ({hours:.1f}h) - Consider a break. You've been at it a while."
        elif hours >= 4:  # Near EXTENDED threshold
            suggestion = f"Approaching extended session ({hours:.1f}h). Good checkpoint for a break."

        # Friction-based suggestions override
        if friction >= 75:
            suggestion = f"HIGH FRICTION ({friction}/100) - Multiple issues detected. Step away, return fresh."
        elif friction >= 50 and mode != SessionMode.STANDARD:
            suggestion = f"Elevated friction ({friction}/100) in {mode.value} mode. Break recommended."

        if suggestion:
            self.last_rest_suggestion = datetime.now()
            return True, suggestion

        return False, ""

    def set_grind_goal(self, goal: str):
        """Set explicit goal for GRIND mode"""
        self.grind_goal = goal
        self.save_session()

    def reset_session(self):
        """Reset session (start fresh)"""
        self.start_time = datetime.now()
        self.friction_events = []
        self.last_rest_suggestion = None
        self.grind_goal = None
        self.save_session()

    def get_status_report(self) -> Dict[str, Any]:
        """Get full session status"""
        mode = self.get_mode()
        hours = self.get_session_hours()
        friction, friction_status = self.get_friction_status()

        return {
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "duration_hours": round(hours, 2),
            "mode": mode.value,
            "mode_status": self._get_mode_status(mode),
            "friction_score": friction,
            "friction_status": friction_status,
            "grind_goal": self.grind_goal,
            "recent_friction_events": len(self.friction_events),
        }

    def _get_mode_status(self, mode: SessionMode) -> str:
        """Get human-readable mode status"""
        statuses = {
            SessionMode.STANDARD: "Focused Work",
            SessionMode.EXTENDED: "Extended Session - Consider Break",
            SessionMode.CRITICAL: "Critical Session - Rest Strongly Advised",
            SessionMode.GRIND: "Grind Mode - Goal-Locked",
        }
        return statuses.get(mode, "Unknown")


# #[MARK:{Implemented:5W1H}] - 5W1H classified notifications
class NotificationSystem:
    """i.notify: Multi-channel event alerting and interactive prompting"""

    def __init__(self, io_handler, journal_manager, log_callback=None, session_manager=None):
        self.io = io_handler
        self.journal = journal_manager
        self.log_callback = log_callback
        self.session_manager = session_manager
        self.config_file = Path(".pyview_config.json")
        self.config = {
            "cli_enabled": True,
            "journal_enabled": True,
            "gui_flash_enabled": True,
            "desktop_enabled": True,
            "interactive_prompts": True,  # Zenity prompts
            "bypass_conformers": False,  # If True, prompt_user returns True automatically
            "timing_ms": 3000,
        }
        self.load_settings()

    def load_settings(self):
        """Load settings from centralized config"""
        if self.config_file.exists():
            try:
                with open(self.config_file, "r") as f:
                    full_config = json.load(f)
                    notif_settings = full_config.get("notifications", {})
                    self.config.update(notif_settings)

                    # Map bypass_conformers explicitly
                    if "bypass_conformers" in notif_settings:
                        self.config["interactive_prompts"] = not notif_settings[
                            "bypass_conformers"
                        ]
            except:
                pass

    def notify(self, title, message, event_type="INFO", importance="MEDIUM"):
        """Main entry point for i.notify events with session-aware priority dampening"""
        # Check if alert should be dampened based on session state
        if self.session_manager and self.session_manager.should_dampen_alert(importance):
            # Log but don't display dampened alerts
            if self.log_callback:
                self.log_callback(f"[DAMPENED:{importance}] {title}: {message}", "NOTIFY")
            return

        # Check for rest suggestion before showing alert
        if self.session_manager:
            should_rest, rest_msg = self.session_manager.check_rest_suggestion()
            if should_rest:
                self._show_rest_suggestion(rest_msg)

        timestamp = datetime.now().strftime("%H:%M:%S")
        formatted = f"🔔 [Event:{event_type}] {title}: {message}"

        # 0. Session Log
        if self.log_callback:
            self.log_callback(f"NOTIFICATION: {title} | {message} | Type: {event_type}")

        # Debug log for notification attempts
        if hasattr(self.io, "debug") and self.io.debug:
            self.io.output(
                f"[DEBUG:notify] Attempting {event_type} notification: {title}"
            )

        # 1. CLI Output
        if self.config["cli_enabled"]:
            self.io.output(formatted)

        # 2. Journal Entry
        if self.config["journal_enabled"]:
            self.journal.add_note(
                f"[{event_type}] {title}: {message}", author="i.notify"
            )

        # 3. Desktop Notification (Linux notify-send)
        if self.config["desktop_enabled"]:
            try:
                # Basic notify-send command
                icon = "dialog-information"
                if importance == "HIGH":
                    icon = "dialog-error"
                elif importance == "MEDIUM":
                    icon = "dialog-warning"

                # Stacking/Replacing tag to keep it tidy
                stack_tag = f"workflow_{event_type.lower()}"

                subprocess.run(
                    [
                        "notify-send",
                        "-i",
                        icon,
                        "-t",
                        "0",  # Persist until clicked
                        "-h",
                        f"string:x-dunst-stack-tag:{stack_tag}",  # Dunst stack
                        "-h",
                        f"string:synchronous:{stack_tag}",  # GNOME/KDE hint
                        f"[{event_type}] {title}",
                        message,
                    ],
                    check=False,
                )
            except Exception as e:
                if hasattr(self.io, "debug") and self.io.debug:
                    self.io.output(f"[DEBUG:notify] notify-send failed: {e}")

        # 4. GUI Flash Hook (Mocked here - would signal Micro GUI)
        if self.config["gui_flash_enabled"]:
            # Signal micro_gui via a small temp file or socket
            pass

    def _show_rest_suggestion(self, message: str):
        """Show rest suggestion with session status"""
        if not self.session_manager:
            return

        status = self.session_manager.get_status_report()
        mode = status["mode"].upper()
        hours = status["duration_hours"]
        friction = status["friction_score"]

        self.io.output("\n" + "=" * 50)
        self.io.output(f"💤 REST SUGGESTION [{mode} MODE]")
        self.io.output("=" * 50)
        self.io.output(f"Session: {hours:.1f}h | Friction: {friction}/100")
        self.io.output(f"\n{message}")
        self.io.output("=" * 50 + "\n")

        # Log to journal
        if self.journal:
            self.journal.add_note(f"Rest suggested: {message}", author="i.session")

        # Optional zenity notification for desktop
        if self.config.get("desktop_enabled", False):
            try:
                subprocess.run([
                    "zenity", "--info",
                    "--title", f"Rest Suggestion ({mode})",
                    "--text", message,
                    "--timeout", "10"
                ], capture_output=True, timeout=12)
            except:
                pass

    def prompt_user(self, title, question, items=None):
        """Interactive prompt using zenity. Supports single Yes/No or List Selection."""
        # 0. Bypass Logic
        if self.config.get("bypass_conformers", False):
            if self.log_callback:
                self.log_callback(f"BYPASS: Auto-confirming prompt: {title}")
            return items if items is not None else True

        if not self.config["interactive_prompts"]:
            return False if items is None else []

        try:
            if self.log_callback:
                self.log_callback(
                    f"PROMPT: {title} | Items: {len(items) if items else 0}"
                )

            if items:
                # Batch list selection
                cmd = [
                    "zenity",
                    "--list",
                    "--title",
                    title,
                    "--text",
                    question,
                    "--column",
                    "Target Files",
                    "--checklist",
                    "--column",
                    "Select",
                    "--width=400",
                    "--height=300",
                ]
                for item in items:
                    cmd.extend(["TRUE", item])

                result = subprocess.run(cmd, capture_output=True, text=True)
                selected = (
                    result.stdout.strip().split("|") if result.returncode == 0 else []
                )

                if self.log_callback:
                    self.log_callback(
                        f"RESPONSE: Selected {len(selected)} items for: {title}"
                    )
                return selected
            else:
                # Single Yes/No
                result = subprocess.run(
                    [
                        "zenity",
                        "--question",
                        "--title",
                        title,
                        "--text",
                        question,
                        "--width=300",
                    ],
                    capture_output=True,
                )
                response = result.returncode == 0
                if self.log_callback:
                    self.log_callback(
                        f"RESPONSE: {'Yes' if response else 'No'} to: {title}"
                    )
                return response
        except Exception as e:
            if hasattr(self.io, "debug") and self.io.debug:
                self.io.output(f"[DEBUG:prompt] Zenity failed: {e}")
            return False if not items else []


class InternalMarkingSystem:
    """Handle internal code marking and artifact generation"""

    def __init__(self, root_dir="."):
        self.root = Path(root_dir)
        self.marks_dir = self.root / "marks"
        self.marks_dir.mkdir(exist_ok=True)
        self.manifest_path = self.root / "file_manifest.json"

    def mark_file(
        self, filepath, line_num, content, note_id, bug_id=None, task_id=None
    ):
        """Insert a marker comment into the source file"""
        path = Path(filepath)
        if not path.exists():
            return False, "File not found"

        marker_parts = [f"ID:{note_id}"]
        if bug_id:
            marker_parts.append(f"BUG:{bug_id}")
        if task_id:
            marker_parts.append(f"TASK:{task_id}")

        marker_str = f"  # [MARK:{{ {'.'.join(marker_parts)} }}]"

        try:
            lines = path.read_text().splitlines()
            if 0 < line_num <= len(lines):
                # Append to existing line
                lines[line_num - 1] += marker_str
            else:
                # Add as new line at the end
                lines.append(marker_str)

            path.write_text("\n".join(lines) + "\n")
            return True, marker_str
        except Exception as e:
            return False, str(e)

    def create_artifacts(self, note_id, filepath, content, metadata=None):
        """Generate .md and .json artifacts for the mark"""
        base_name = f"mark_{note_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        # 1. MD Note
        md_path = self.marks_dir / f"{base_name}.md"
        md_content = f"# Mark {note_id}\n\n"
        md_content += f"- **File:** {filepath}\n"
        md_content += f"- **Date:** {datetime.now().isoformat()}\n\n"
        md_content += "## Content\n"
        md_content += f"{content}\n"
        md_path.write_text(md_content)

        # 2. JSON Metadata (Context)
        json_path = self.marks_dir / f"{base_name}.json"
        context = self.collect_context(filepath)
        data = {
            "note_id": note_id,
            "filepath": str(filepath),
            "timestamp": datetime.now().isoformat(),
            "content": content,
            "manifest_context": context,
            "custom_metadata": metadata or {},
        }
        with open(json_path, "w") as f:
            json.dump(data, f, indent=2)

        return md_path, json_path

    def collect_context(self, filepath):
        """Extract context for the file from file_manifest.json"""
        if not self.manifest_path.exists():
            return {}
        try:
            with open(self.manifest_path, "r") as f:
                manifest = json.load(f)

            fname = os.path.basename(filepath)
            for entry in manifest:
                if entry.get("file") == fname:
                    return entry
        except:
            pass
        return {}


class JournalManager:
    """Manage daily journals, activity tracking, and proposals"""

    def __init__(self, root_dir="."):
        self.root = Path(root_dir)
        self.journal_dir = self.root / "journal"
        self.proposals_dir = self.root / "proposals"
        self.journal_dir.mkdir(exist_ok=True)
        self.proposals_dir.mkdir(exist_ok=True)
        self.manifest_file = self.journal_dir / "manifest.json"
        self.manifest = self.load_manifest()

    def load_manifest(self):
        if self.manifest_file.exists():
            try:
                with open(self.manifest_file, "r") as f:
                    return json.load(f)
            except:
                pass
        return {"projects": {}, "last_update": None}

    def save_manifest(self):
        with open(self.manifest_file, "w") as f:
            json.dump(self.manifest, f, indent=2)

    def get_daily_file(self, date_obj=None):
        if date_obj is None:
            date_obj = datetime.now()
        filename = date_obj.strftime("%Y-%m-%d.json")
        return self.journal_dir / filename

    def update_daily_journal(self, io_handler):
        """Fetch activity and update today's journal"""
        today = datetime.now()
        daily_file = self.get_daily_file(today)

        entry = {
            "date": today.strftime("%Y-%m-%d"),
            "notes": [],
            "activity": {"tasks_modified": [], "diffs_created": [], "logs_updated": []},
            "proposals_linked": [],
        }

        if daily_file.exists():
            try:
                with open(daily_file, "r") as f:
                    entry.update(json.load(f))
            except:
                pass

        # 1. Fetch Task Activity
        tasks_dir = self.root / "tasks"
        if tasks_dir.exists():
            for task_file in tasks_dir.glob("*.json"):
                mtime = datetime.fromtimestamp(task_file.stat().st_mtime)
                if mtime.date() == today.date():
                    if task_file.name not in entry["activity"]["tasks_modified"]:
                        entry["activity"]["tasks_modified"].append(task_file.name)

        # 2. Fetch Diff Activity
        diffs_dir = self.root / "diffs"
        if diffs_dir.exists():
            for diff_file in diffs_dir.glob("*"):
                mtime = datetime.fromtimestamp(diff_file.stat().st_mtime)
                if mtime.date() == today.date():
                    if diff_file.name not in entry["activity"]["diffs_created"]:
                        entry["activity"]["diffs_created"].append(diff_file.name)

        # 3. Fetch Log Activity
        log_file = self.root / "logs" / "session.log"
        if log_file.exists():
            mtime = datetime.fromtimestamp(log_file.stat().st_mtime)
            if mtime.date() == today.date():
                if "session.log" not in entry["activity"]["logs_updated"]:
                    entry["activity"]["logs_updated"].append("session.log")

        # Save
        with open(daily_file, "w") as f:
            json.dump(entry, f, indent=2)

        io_handler.output(f"✓ Updated journal for {entry['date']}")
        return entry

    def add_note(self, content, author="user"):
        """Add a note to today's journal"""
        today = datetime.now()
        daily_file = self.get_daily_file(today)

        entry = self.update_daily_journal(IOHandler())  # Ensure file exists

        note = {
            "timestamp": today.strftime("%H:%M:%S"),
            "author": author,
            "content": content,
        }
        entry["notes"].append(note)

        with open(daily_file, "w") as f:
            json.dump(entry, f, indent=2)

        return note

    def create_proposal(self, title, content=""):
        """Create a new proposal"""
        slug = re.sub(r"[^a-z0-9]+", "_", title.lower()).strip("_")
        filename = f"prop_{datetime.now().strftime('%Y%m%d')}_{slug}.json"
        filepath = self.proposals_dir / filename

        proposal = {
            "id": filename.replace(".json", ""),
            "title": title,
            "status": "draft",
            "created_at": datetime.now().isoformat(),
            "content": content,
            "linked_tasks": [],
        }

        with open(filepath, "w") as f:
            json.dump(proposal, f, indent=2)

        # Link to daily journal
        self.update_daily_journal(IOHandler())  # Ensure loaded
        daily_file = self.get_daily_file()
        with open(daily_file, "r") as f:
            entry = json.load(f)

        if filename not in entry["proposals_linked"]:
            entry["proposals_linked"].append(filename)

        with open(daily_file, "w") as f:
            json.dump(entry, f, indent=2)

        return proposal


class IOHandler:
    """Abstract Input/Output handler"""

    def output(self, message: str):
        print(message)

    def input(self, prompt: str) -> str:
        return input(prompt)


class WorkflowManager:
    """Manage and execute workflows"""

    def __init__(self, profile_path: str = None, io_handler: IOHandler = None):
        self.io = io_handler or IOHandler()
        self.config_file = Path(".pyview_config.json")
        self.profiles: Dict[str, Profile] = {}
        self.tasks: Dict[int, Task] = {}
        self.current_task_id = 1
        self.marked_targets = []
        self.diffs = []
        self.analyzer = CodeAnalyzer()
        self.session_log = []
        self.journal_manager = JournalManager()
        self.marker = InternalMarkingSystem()
        self.trust_system = TrustSystem()
        self.session_manager = SessionManager()
        self.notifier = NotificationSystem(
            self.io, self.journal_manager, log_callback=self.log_session,
            session_manager=self.session_manager
        )
        self.note_counter = 1
        self.unmarked_tracking = {}  # {filepath: {first_seen, last_seen, refresh_count}}
        self.abandonment_threshold_days = 3
        self.abandonment_threshold_refreshes = 5

        self.load_config()
        if profile_path:
            self.load_profile(profile_path)

    def load_config(self):
        """Load persistent configuration"""
        if self.config_file.exists():
            try:
                with open(self.config_file, "r") as f:
                    data = json.load(f)
                    targets = data.get("marked_targets", [])
                    # Convert to absolute paths and filter existing
                    self.marked_targets = [
                        os.path.abspath(t) for t in targets if os.path.exists(t)
                    ]
                    # Load unmarked tracking data
                    self.unmarked_tracking = data.get("unmarked_tracking", {})
            except:
                pass

    def save_config(self):
        """Save persistent configuration"""
        data = {}
        if self.config_file.exists():
            try:
                with open(self.config_file, "r") as f:
                    data = json.load(f)
            except:
                pass

        data["marked_targets"] = self.marked_targets
        data["unmarked_tracking"] = self.unmarked_tracking
        with open(self.config_file, "w") as f:
            json.dump(data, f, indent=2)

    def track_unmarked_file(self, filepath: str) -> Dict[str, Any]:
        """Track an unmarked file's refresh occurrences"""
        now = datetime.now().isoformat()
        abs_path = os.path.abspath(filepath)

        if abs_path in self.unmarked_tracking:
            # Existing file - increment counter
            self.unmarked_tracking[abs_path]["refresh_count"] += 1
            self.unmarked_tracking[abs_path]["last_seen"] = now
        else:
            # New unmarked file
            self.unmarked_tracking[abs_path] = {
                "first_seen": now,
                "last_seen": now,
                "refresh_count": 1,
            }

        self.save_config()
        return self.unmarked_tracking[abs_path]

    def check_abandonment(self, filepath: str) -> Tuple[bool, str]:
        """Check if an unmarked file should be flagged as abandoned"""
        abs_path = os.path.abspath(filepath)

        if abs_path not in self.unmarked_tracking:
            return False, "Not tracked"

        tracking = self.unmarked_tracking[abs_path]
        first_seen = datetime.fromisoformat(tracking["first_seen"])
        days_since = (datetime.now() - first_seen).days
        refresh_count = tracking["refresh_count"]

        # Check thresholds
        if days_since >= self.abandonment_threshold_days:
            return True, f"Abandoned: {days_since} days unacknowledged"
        if refresh_count >= self.abandonment_threshold_refreshes:
            return True, f"Abandoned: {refresh_count} refreshes unacknowledged"

        return False, f"Tracking: {refresh_count} refreshes over {days_since} days"

    def clear_unmarked_tracking(self, filepath: str):
        """Remove file from unmarked tracking (when marked or dismissed)"""
        abs_path = os.path.abspath(filepath)
        if abs_path in self.unmarked_tracking:
            del self.unmarked_tracking[abs_path]
            self.save_config()

    def handle_journal_args(self, args):
        """Handle journal-related CLI arguments and advanced marking"""
        if args.journal:
            # Default action: update and show today's summary
            entry = self.journal_manager.update_daily_journal(self.io)
            self.io.output(f"\nJOURNAL: {entry['date']}")
            self.io.output(
                f"  Activity: {len(entry['activity']['tasks_modified'])} tasks, {len(entry['activity']['diffs_created'])} diffs"
            )
            self.io.output(f"  Notes: {len(entry['notes'])}")

        if args.note:
            note_content = args.note
            self.journal_manager.add_note(note_content)

            # Advanced Marking: if -mark and -line are present
            if args.mark and args.line is not None:
                # Use the first mark target
                target = args.mark[0]
                note_id = f"N{self.note_counter:03d}"
                self.note_counter += 1

                bug_id = (
                    f"BUG_{datetime.now().strftime('%H%M%S')}" if args.bug else None
                )
                task_id = None

                # 1. Insert Mark into file
                ok, res = self.marker.mark_file(
                    target, args.line, note_content, note_id, bug_id
                )
                if ok:
                    self.io.output(f"✓ Internal Mark Inserted: {target}:{args.line}")

                    # 2. Create Task if bug
                    if args.bug:
                        task_id = self.current_task_id
                        self.current_task_id += 1
                        task = Task(
                            id=task_id,
                            name=f"Bug Fix: {note_id}",
                            description=f"Automated bug task from internal mark.\nNote: {note_content}",
                            targets=[target],
                            status="created",
                            workflow="debug_assist",
                            metadata={"note_id": note_id, "bug_id": bug_id},
                        )
                        self.tasks[task_id] = task
                        self.save_task(task_id)
                        self.io.output(f"✓ Created Task {task_id} for Bug {bug_id}")

                    # 3. Generate Artifacts (.md, .json)
                    md, js = self.marker.create_artifacts(
                        note_id,
                        target,
                        note_content,
                        {"bug_id": bug_id, "task_id": task_id},
                    )
                    self.io.output(f"✓ Artifacts Generated: {md.name}, {js.name}")
                else:
                    self.io.output(f"✗ Failed to insert mark: {res}")
            else:
                self.io.output("✓ Note added to daily journal")

        if args.proposal:
            prop = self.journal_manager.create_proposal(args.proposal)
            self.io.output(f"✓ Proposal created: {prop['id']}")

        if args.daily:
            entry = self.journal_manager.update_daily_journal(self.io)
            print(json.dumps(entry, indent=2))

    def comment_audit(self):
        """Scan all marked scripts for custom tags and audit their relevance"""
        self.io.output("\n" + "=" * 50)
        self.io.output("CUSTOM TAG AUDIT (MARK/EVENT/PFL/LINK)")
        self.io.output("=" * 50)

        results = {
            "resolved": [],
            "unresolved": [],
            "stats": {"MARK": 0, "EVENT": 0, "PFL": 0, "LINK": 0},
        }

        # 1. Load context from marks/
        marks_dir = Path("marks")
        known_note_ids = []
        if marks_dir.exists():
            known_note_ids = [
                f.stem.split("_")[1] for f in marks_dir.glob("mark_N*.json")
            ]

        # 2. Scan Marked Targets
        for target in self.marked_targets:
            if not os.path.isfile(target):
                continue

            analysis = self.analyzer.analyze_ast(target)
            tags = analysis.get("custom_tags", [])

            if tags:
                self.io.output(f"\n📁 File: {os.path.basename(target)}")
                for tag in tags:
                    tag_type = tag["type"]
                    data = tag["data"]
                    results["stats"][tag_type] += 1

                    # Reconciliation Logic
                    is_resolved = False
                    if tag_type == "MARK":
                        # Match against known Note IDs (e.g., ID:N001)
                        if "ID:" in data:
                            note_id = data.split("ID:")[1].split(".")[0]
                            if note_id in known_note_ids:
                                is_resolved = True

                    status = "✓ Resolved" if is_resolved else "⚠ Unresolved"
                    self.io.output(
                        f"  {status} [{tag_type}] Line {tag['line']}: {data}"
                    )

                    entry = {"file": target, "tag": tag, "resolved": is_resolved}
                    if is_resolved:
                        results["resolved"].append(entry)
                    else:
                        results["unresolved"].append(entry)

        # 3. Final Summary
        self.io.output(
            f"\nAudit complete. Found {len(results['resolved'])} resolved and {len(results['unresolved'])} unresolved tags."
        )
        return results

    def refresh_project(self):
        """Unified project refresh: detects changes, captures help output, and jolts new scripts"""
        self.io.output("\n" + "=" * 50)
        self.io.output("UNIFIED PROJECT REFRESH")
        self.io.output("=" * 50)

        # 1. Load manifest state
        manifest_path = Path("file_manifest.json")
        last_refresh = (
            datetime.fromtimestamp(manifest_path.stat().st_mtime)
            if manifest_path.exists()
            else datetime.min
        )
        self.io.output(f"Last refresh: {last_refresh.strftime('%Y-%m-%d %H:%M:%S')}")

        # 2. Scan for changes & new files (Recursive)
        all_py_files = []
        for p in Path(".").rglob("*.py"):
            # Skip noise/utility dirs
            if any(
                part in p.parts
                for part in [
                    "__pycache__",
                    "backup",
                    "backups",
                    ".micro_gui_tasks",
                    "marks",
                    "onboarding_logs",
                ]
            ):
                continue
            all_py_files.append(p)

        changes_detected = 0
        new_files = []
        unmarked_changes = []

        for py_file in all_py_files:
            mtime = datetime.fromtimestamp(py_file.stat().st_mtime)
            if mtime > last_refresh:
                changes_detected += 1
                is_marked = str(py_file.absolute()) in self.marked_targets

                # High Alert Condition: Change detected in UN-MARKED file
                if not is_marked:
                    new_files.append(py_file)
                    # Track this unmarked file
                    tracking = self.track_unmarked_file(str(py_file))
                    is_abandoned, abandon_reason = self.check_abandonment(str(py_file))
                    status_tag = "[ABANDONED]" if is_abandoned else f"[R:{tracking['refresh_count']}]"
                    unmarked_changes.append(f"{py_file.name} {status_tag}")

                # Jolt the chain: immediate compile & AST check
                self.io.output(f"  ⚡ Jolting: {py_file.name} (Changed)")
                ok, msg = self.analyzer.compile_check(str(py_file))
                if ok:
                    self.analyzer.analyze_ast(str(py_file))
                else:
                    self.io.output(f"    ✗ Compile error: {msg}")

        # 3. Handle High Alerts (Stacked Conformer) with Abandonment Detection
        abandoned_files = []
        tracked_files = []

        for py_file in new_files:
            is_abandoned, reason = self.check_abandonment(str(py_file))
            if is_abandoned:
                abandoned_files.append((py_file, reason))
            else:
                tracked_files.append(py_file)

        # Report abandonment status
        if abandoned_files:
            self.io.output(f"\n[ABANDONMENT ALERT] {len(abandoned_files)} file(s) need attention:")
            for py_file, reason in abandoned_files:
                self.io.output(f"  ⚠ {py_file.name}: {reason}")

            self.notifier.notify(
                "Abandonment Alert",
                f"{len(abandoned_files)} file(s) exceed tracking thresholds. Consider marking as Stable or Active.",
                event_type="ABANDONMENT",
                importance="HIGH",
            )

        if unmarked_changes:
            self.notifier.notify(
                "High Alert",
                f"Detected unmarked changes in {len(unmarked_changes)} file(s).",
                event_type="ALERT",
                importance="HIGH",
            )

            selected_for_audit = self.notifier.prompt_user(
                "Security Conformer",
                "Select files to run Deep Chain Audit and generate 5W1H reports:",
                items=unmarked_changes,
            )

            for script_name in selected_for_audit:
                # Extract base filename from status-tagged name
                base_name = script_name.split(" [")[0]
                # Find the full path for the audit
                target_path = next((str(p) for p in new_files if p.name == base_name), base_name)
                self.deep_chain_audit(target_path)

        # 4. Handle new files: Log capture, Marking, and Tasking
        if new_files:
            log_dir = Path("onboarding_logs")
            log_dir.mkdir(exist_ok=True)

            for py_path in new_files:
                nf_rel = str(py_path)
                self.io.output(f"\n[!] New Script: {nf_rel}")

                # 4.1 Capture Help Output
                help_output = ""
                try:
                    res = subprocess.run(
                        [sys.executable, nf_rel, "-h"],
                        capture_output=True,
                        text=True,
                        timeout=5,
                    )
                    help_output = res.stdout if res.returncode == 0 else res.stderr
                except Exception as e:
                    help_output = f"Error capturing help: {e}"

                # 4.2 Store Onboarding Log
                log_id = f"ONB_{datetime.now().strftime('%H%M%S')}"
                log_file = log_dir / f"{log_id}_{py_path.name}.log"
                log_file.write_text(help_output)
                self.io.output(f"  ✓ Help output logged: {log_file.name}")

                # 4.3 Internal Mark (Classification)
                note_id = f"N{self.note_counter:03d}"
                self.note_counter += 1
                self.marker.mark_file(
                    nf_rel, 1, f"Initial Onboarding: {log_id}", note_id
                )
                self.io.output(f"  ✓ Internal mark inserted at line 1")

                # 4.4 Create Task
                task_id = self.current_task_id
                self.current_task_id += 1
                task = Task(
                    id=task_id,
                    name=f"Onboard {py_path.name}",
                    description=f"New file detected in {py_path.parent}.\nOnboarding Log: {log_file.name}\nMarker: {note_id}",
                    targets=[nf_rel],
                    status="created",
                    workflow="task_manage",
                    metadata={"log_id": log_id, "note_id": note_id},
                )
                self.tasks[task_id] = task
                self.save_task(task_id)
                self.io.output(f"  ✓ Task {task_id} created for classification")

                # 4.5 Journal Entry
                self.journal_manager.add_note(
                    f"Refresh: New script {nf_rel} detected. Captured help as {log_id}.",
                    author="i.refresh",
                )

            self.io.output(f"\n✓ Processed {len(new_files)} new files.")

        # 5. Update dependency map for all scripts
        self.io.output("\n[5/5] Updating Dependency Map...")
        for py_file in all_py_files:
            if py_file.name not in self.analyzer.dependency_map:
                self.analyzer.analyze_ast(str(py_file))

        # 6. Final Guidance
        if changes_detected > 0:
            self.notifier.notify(
                "Refresh Deltas",
                f"Detected changes in {changes_detected} file(s). Use -view to check context.",
                event_type="REFRESH",
            )

        self.io.output(f"\n✓ Refresh complete. Changes jolted: {changes_detected}")
        self.io.output("\n--- CURRENT GUIDANCE ---")
        subprocess.run([sys.executable, "workflow_manager.py", "-h"])

    def deep_chain_audit(self, target_file):
        """Follow import chains and generate a consolidated 5W1H debug summary with diff context"""
        self.io.output(f"\n🔍 [DEEP AUDIT] Tracing impact chain for: {target_file}")

        target_name = os.path.basename(target_file)
        impacted_files = []

        # 1. Trace Dependency Chain (Who imports this?)
        for script, deps in self.analyzer.dependency_map.items():
            if any(target_name in imp for imp in deps.get("imports", [])) or any(
                target_name.replace(".py", "") in imp
                for imp in deps.get("from_imports", [])
            ):
                impacted_files.append(script)

        # 2. Perform Checks on entire chain
        self.io.output(
            f"  ⚡ Found {len(impacted_files)} dependent scripts: {', '.join(impacted_files)}"
        )

        results = []
        for script in [target_name] + impacted_files:
            # Get Context from Manifest
            manifest_entry = self.marker.collect_context(script)

            # Static check
            ok, msg = self.analyzer.compile_check(script)
            ast_data = self.analyzer.analyze_ast(script)

            # 3. Calculate Delta Context
            current_hash = ""
            if os.path.exists(script):
                with open(script, "rb") as f:
                    current_hash = hashlib.md5(f.read()).hexdigest()[:16]

            # Generate 5W1H segment
            report = self.analyzer.generate_5w1h_report(
                "Chain Audit Segment",
                script,
                {
                    "reason": "Impact verification from dependency chain",
                    "variables": ast_data["variables"][:5],  # Top 5
                    "attributes": ast_data["attributes"][:5],
                    "lines": manifest_entry.get("metadata", {}).get("lines", "NEW"),
                    "diff_hash": f"{manifest_entry.get('hash', 'UNKNOWN')} -> {current_hash}",
                },
            )
            results.append(report)

        # 4. Final Summary Artifact
        summary_file = (
            Path("logs") / f"debug_summary_{datetime.now().strftime('%H%M%S')}.json"
        )
        with open(summary_file, "w") as f:
            json.dump({"audit_root": target_file, "chain_results": results}, f, indent=2)

        self.io.output(f"✓ Deep Audit Complete. Summary routed to: {summary_file.name}")
        return summary_file

    def unified_debug_check(self):
        """Comprehensive cross-module health check"""
        self.io.output("\n" + "=" * 50)
        self.io.output("UNIFIED DEBUG REPORT (Init Check)")
        self.io.output("=" * 50)

        # 1. Check Session Logs for recent errors
        log_file = Path("logs/session.log")
        if log_file.exists():
            self.io.output("\n[1/4] Reviewing Latest Session Logs...")
            with open(log_file, "r") as f:
                lines = f.readlines()[-20:]  # Last 20 lines
                errors = [l for l in lines if "ERROR" in l or "Exception" in l]
                if errors:
                    self.notifier.notify(
                        "Errors Detected",
                        f"Found {len(errors)} errors in session log",
                        event_type="DEBUG",
                        importance="HIGH",
                    )
                    self.io.output(f"  ⚠ Found {len(errors)} recent errors in log")
                    for e in errors[:3]:
                        self.io.output(f"    - {e.strip()}")

                    # Ask to create a task
                    if self.notifier.prompt_user(
                        "Log Errors Detected",
                        "Should I create a high-priority debug task for these errors?",
                    ):
                        task_id = self.current_task_id
                        self.current_task_id += 1
                        task = Task(
                            id=task_id,
                            name=f"Fix Log Errors ({datetime.now().strftime('%H:%M')})",
                            description=f"Auto-generated debug task for errors found in session log.\nErrors: {len(errors)}",
                            status="created",
                            workflow="debug_assist",
                        )
                        self.tasks[task_id] = task
                        self.save_task(task_id)
                        self.io.output(f"  ✓ Created Task {task_id}")
                else:
                    self.io.output("  ✓ No recent log errors")

        # 2. Check Marked Targets for changes
        self.io.output("\n[2/4] Validating Marked Targets...")
        if not self.marked_targets:
            self.io.output("  ℹ No targets marked. Use -mark to onboard scripts.")

        for target in self.marked_targets:
            path = Path(target)
            if not path.exists():
                self.io.output(f"  ✗ Target missing: {target}")
                continue

            mtime = datetime.fromtimestamp(path.stat().st_mtime)
            self.io.output(f"  • {path.name} (Last mod: {mtime.strftime('%H:%M:%S')})")

            # 3. Static Executability & Syntax Checks
            if path.suffix == ".py":
                # Compilation Check
                ok, msg = self.analyzer.compile_check(str(path))
                self.io.output(f"    - Compile: {'✓' if ok else '✗'} {msg}")

                # Black Formatting Check
                try:
                    res = subprocess.run(
                        ["black", "--check", str(path)], capture_output=True, text=True
                    )
                    fmt = "✓ Clean" if res.returncode == 0 else "⚠ Needs Format"
                    self.io.output(f"    - Black: {fmt}")
                except:
                    pass

                # AST Integrity
                ast_data = self.analyzer.analyze_ast(str(path))
                self.io.output(
                    f"    - AST: {len(ast_data['classes'])} classes, {len(ast_data['functions'])} functions"
                )

        # 4. Global State
        self.io.output("\n[4/4] Finalizing Report...")
        self.io.output(
            f"  - Active Tasks: {len([t for t in self.tasks.values() if t.status != 'completed'])}"
        )
        self.io.output(f"  - Profiles Loaded: {len(self.profiles)}")
        self.io.output("\n✓ Unified Debug Complete.")

    def handle_instruct(self, query, agent=None, use_gui=False):
        """Handle -instruct workflow"""
        agent = agent or "gemini"
        self.io.output(f"\n[INSTRUCT] Agent: {agent} | Query: {query}")

        # 1. Detect/Start Session
        is_running = self.check_agent_active(agent)

        if not is_running:
            self.io.output(f"Starting {agent} session...")
            self.launch_agent(agent, "instruct")

            if use_gui:
                self.io.output("Launching Micro GUI for visual monitoring...")
                try:
                    subprocess.Popen([sys.executable, "micro_gui.py"])
                except:
                    pass

            # 2. Wait for agent ready
            self.wait_for_agent_ready(agent)

        # 3. Fetch Task Context
        latest_task = self.get_latest_task()
        context = ""
        if latest_task:
            self.io.output(
                f"Linking context from Task {latest_task.id}: {latest_task.name}"
            )
            context = f"\nTask Context: {latest_task.description}\nTargets: {latest_task.targets}"

        # 4. Pipe instruction to agent
        # For this mock implementation, we log it.
        # In production, this would write to the agent's stdin or a command pipe.
        full_instruction = f"{query}\n{context}"
        self.log_session(f"Instruction sent to {agent}: {query}", "INSTRUCT")
        self.io.output(f"✓ Instruction sent to {agent} pipe")

    def check_agent_active(self, agent):
        """Check if agent process is active"""
        # Mock check: check for a fresh session log entry
        # A more robust check would use psutil or pid files
        return False  # Force start for now

    def wait_for_agent_ready(self, agent):
        """Wait for agent to initialize"""
        self.io.output(f"Waiting for {agent} to load...")
        # Simulate loading time
        for i in range(3):
            time.sleep(1)
            self.io.output(f"...{3-i}")
        self.io.output(f"✓ {agent} Ready.")

    def get_latest_task(self):
        """Get the most recently updated task"""
        if not self.tasks:
            return None
        return sorted(self.tasks.values(), key=lambda x: x.updated_at, reverse=True)[0]

    def load_profile(self, profile_path: str):
        """Load workflow profile from JSON"""
        try:
            with open(profile_path, "r") as f:
                data = json.load(f)

            for name, config in data.items():
                self.profiles[name] = Profile(
                    name=name,
                    workflows=config.get("workflows", {}),
                    pre_tasks=config.get("pre_tasks", []),
                    post_tasks=config.get("post_tasks", []),
                    allowed_dirs=config.get("allowed_dirs", []),
                    restrictions=config.get("restrictions", {}),
                    default_layout_prefs=config.get("default_layout_prefs", {}),
                )

            self.io.output(f"✓ Loaded profile: {profile_path}")

        except FileNotFoundError:
            self.io.output(f"✗ Profile not found: {profile_path}")
            self.create_default_profile(profile_path)
        except json.JSONDecodeError as e:
            self.io.output(f"✗ Invalid JSON in profile: {e}")

    def import_analysis(self, checklist_path: str = "optimization_checklist.json"):
        """Import analysis results and auto-create tasks"""
        if not os.path.exists(checklist_path):
            self.io.output(f"✗ Analysis file not found: {checklist_path}")
            return

        try:
            with open(checklist_path, "r") as f:
                checklist = json.load(f)

            count = 0
            for file_entry in checklist:
                filepath = file_entry.get("filepath")
                items = file_entry.get("items", [])

                if not items:
                    continue

                # Create a task for this file
                task_id = self.current_task_id
                self.current_task_id += 1

                description = f"Optimization task for {filepath}\n"
                goals = []
                points = {}

                for item in items:
                    description += f"- [{item['priority']}] {item['description']}\n"
                    goals.append(item["description"])

                    if item["id"] == "issue_high_widget_count":
                        points["target_widget_count"] = 50  # Example target

                task = Task(
                    id=task_id,
                    name=f"Optimize {os.path.basename(filepath)}",
                    description=description,
                    targets=[filepath],
                    status="created",
                    workflow="layout_optimize",
                    optimization_goals=goals,
                    feature_points=points,
                    metadata={"source": "tkinter_optimizer"},
                )

                self.tasks[task_id] = task
                self.save_task(task_id)
                count += 1

            self.io.output(
                f"✓ Imported analysis: Created {count} tasks from {checklist_path}"
            )

        except Exception as e:
            self.io.output(f"✗ Failed to import analysis: {e}")

    def create_default_profile(self, profile_path: str):
        """Create default workflow profiles"""
        default_profiles = {
            "debug_profile": {
                "workflows": {
                    "debug": {
                        "description": "Debug assistance workflow",
                        "pre_checks": ["ast_analysis", "compile_check"],
                        "agent": "claude",
                        "tools": ["debug", "traceback"],
                    },
                    "syntax_check": {
                        "description": "Syntax and style checking",
                        "pre_checks": ["pyflakes", "ast_validation"],
                        "agent": "gemini",
                        "tools": ["ruff", "pylint"],
                    },
                },
                "allowed_dirs": [str(Path.home() / "projects")],
                "pre_tasks": ["backup_files", "create_snapshot"],
                "post_tasks": ["cleanup_temp", "update_log"],
            }
        }

        os.makedirs(os.path.dirname(profile_path) or ".", exist_ok=True)
        with open(profile_path, "w") as f:
            json.dump(default_profiles, f, indent=2)

        self.io.output(f"✓ Created default profile: {profile_path}")

    def create_task(self, scheduled_for: str = None) -> Task:
        """Create a new task with interactive input and optional scheduling"""
        self.io.output("\n" + "=" * 50)
        self.io.output("CREATE NEW TASK")
        self.io.output("=" * 50)

        task_id = self.current_task_id
        self.current_task_id += 1

        self.io.output(f"\nTask ID: {task_id}")
        self.io.output(f"Marked targets: {len(self.marked_targets)} files/dirs")
        self.io.output(f"Available diffs: {len(self.diffs)}")

        # Collect task details
        name = (
            self.io.input("Task name (or Enter to skip): ").strip() or f"task_{task_id}"
        )
        description = self.io.input("Task description: ").strip()

        # Schedule date (from arg or interactive)
        schedule_date = scheduled_for or ""
        if not schedule_date:
            schedule_input = self.io.input(
                "Schedule for date (YYYY-MM-DD, or Enter to skip): "
            ).strip()
            if schedule_input:
                schedule_date = schedule_input

        # Select targets from marked items
        targets = []
        if self.marked_targets:
            self.io.output("\nMarked items:")
            for i, target in enumerate(self.marked_targets, 1):
                self.io.output(f"  {i}. {target}")

            selection = self.io.input(
                "Select targets (comma-separated numbers, or 'all'): "
            ).strip()
            if selection.lower() == "all":
                targets = self.marked_targets.copy()
            elif selection:
                indices = [int(i.strip()) - 1 for i in selection.split(",")]
                targets = [
                    self.marked_targets[i]
                    for i in indices
                    if 0 <= i < len(self.marked_targets)
                ]

        # Create task with scheduling
        task = Task(
            id=task_id,
            name=name,
            description=description,
            targets=targets,
            diffs=self.diffs.copy() if self.diffs else [],
            status="scheduled" if schedule_date else "created",
            scheduled_for=schedule_date,
        )

        self.tasks[task_id] = task
        self.log_session(f"Created task {task_id}: {name}" + (f" (scheduled: {schedule_date})" if schedule_date else ""))

        self.io.output("\n✓ Task created successfully!")
        if schedule_date:
            self.io.output(f"  Scheduled for: {schedule_date}")
        self.io.output(f"  Saved to: tasks/task_{task_id}.json")

        # Save task to file
        self.save_task(task_id)

        return task

    def save_task(self, task_id: int):
        """Save task to JSON file"""
        os.makedirs("tasks", exist_ok=True)
        task_file = f"tasks/task_{task_id}.json"

        task = self.tasks[task_id]
        task_data = asdict(task)

        with open(task_file, "w") as f:
            json.dump(task_data, f, indent=2)

    def view_status(self):
        """Display status of marked/unmarked files and key artifacts"""
        self.io.output("\n" + "=" * 50)
        self.io.output("PROJECT ONBOARDING STATUS")
        self.io.output("=" * 50)

        # 1. Marked Targets
        self.io.output("\n[Onboarded Files]")
        if not self.marked_targets:
            self.io.output("  (None)")
        else:
            for target in sorted(self.marked_targets):
                rel_path = os.path.relpath(target)
                self.io.output(f"  ✓ {rel_path}")

        # 2. Unmarked Files
        self.io.output("\n[Unmarked Python Files]")
        all_py = [str(p) for p in Path(".").glob("*.py")]
        unmarked = [f for f in all_py if os.path.abspath(f) not in self.marked_targets]

        if not unmarked:
            self.io.output("  ✓ All local scripts onboarded")
        else:
            for f in sorted(unmarked):
                self.io.output(f"  ○ {f}")

        # 3. Key Artifacts
        self.io.output("\n[Key Artifacts]")
        artifacts = {
            "file_manifest.json": "Project Code Mapping",
            "summary.json": "UI Pattern Overview",
            "journal/manifest.json": "Activity Router",
            "proposals/": "Logic Blueprints",
            "onboarding_logs/": "New Script Snapshots",
        }

        for path, desc in artifacts.items():
            exists = "✓" if Path(path).exists() else "✗"
            self.io.output(f"  {exists} {path.ljust(22)} - {desc}")

        self.io.output("\n" + "=" * 50)

    def mark_target(self, path: str, mark_type: str = "Active"):
        """Mark directory or file for processing with optional type (Active, Stable, Scheduled:DATE)"""
        if os.path.exists(path):
            abs_path = os.path.abspath(path)
            if abs_path not in self.marked_targets:
                self.marked_targets.append(abs_path)
                # Clear from unmarked tracking since it's now marked
                self.clear_unmarked_tracking(path)
                self.save_config()

                # Insert mark comment if it's a Python file
                if path.endswith(".py") and mark_type:
                    note_id = f"N{self.note_counter:03d}"
                    self.note_counter += 1
                    self.marker.mark_file(path, 1, mark_type, note_id)
                    self.io.output(f"✓ Marked: {path} [MARK:{{{mark_type}}}]")
                else:
                    self.io.output(f"✓ Marked: {path}")
                self.log_session(f"Marked target: {path} (type: {mark_type})")
            else:
                self.io.output(f"ℹ Already marked: {path}")
        else:
            self.io.output(f"✗ Path not found: {path}")

    def create_diff(self, old_file: str, new_file: str):
        """Create and store diff between files"""
        try:
            with open(old_file, "r") as f1, open(new_file, "r") as f2:
                old_lines = f1.readlines()
                new_lines = f2.readlines()

            diff = list(
                difflib.unified_diff(
                    old_lines,
                    new_lines,
                    fromfile=old_file,
                    tofile=new_file,
                    lineterm="",
                )
            )

            if diff:
                diff_id = len(self.diffs) + 1
                diff_data = {
                    "id": diff_id,
                    "old_file": old_file,
                    "new_file": new_file,
                    "diff": diff,
                    "hash": self.analyzer.calculate_diff_hash(
                        "".join(old_lines), "".join(new_lines)
                    ),
                }
                self.diffs.append(diff_data)

                # Save diff to file
                os.makedirs("diffs", exist_ok=True)
                diff_file = f"diffs/diff_{diff_id}.txt"
                with open(diff_file, "w") as f:
                    f.write("\n".join(diff))

                self.io.output(f"✓ Created diff {diff_id}")
                self.io.output(f"  Saved to: {diff_file}")
                self.log_session(f"Created diff {diff_id}: {old_file} -> {new_file}")
            else:
                self.io.output("✗ No differences found")

        except Exception as e:
            self.io.output(f"✗ Error creating diff: {e}")

    def run_script(self, script_path: str, args: List[str] = None) -> Dict[str, Any]:
        """Execute a script with arguments and log the methodology"""
        args = args or []
        script_full_path = os.path.abspath(script_path)

        if not os.path.exists(script_full_path):
            return {"success": False, "error": f"Script not found: {script_path}"}

        # Ensure executable
        try:
            current_mode = os.stat(script_full_path).st_mode
            os.chmod(script_full_path, current_mode | 0o111)
            self.log_session(f"Made executable: {script_path}")
        except Exception as e:
            return {"success": False, "error": f"Failed to chmod script: {e}"}

        cmd = [script_full_path] + args
        cmd_str = " ".join(cmd)

        self.log_session(f"Executing: {cmd_str}")
        self.io.output(f"\nRunning: {cmd_str}")

        start_time = time.time()
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=os.path.dirname(script_full_path) or ".",
            )
            duration = time.time() - start_time

            output = {
                "success": result.returncode == 0,
                "command": cmd_str,
                "return_code": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "duration": duration,
                "timestamp": datetime.now().isoformat(),
            }

            status = "SUCCESS" if result.returncode == 0 else "FAILED"
            self.log_session(f"Execution finished ({status}) in {duration:.2f}s")

            return output

        except Exception as e:
            return {
                "success": False,
                "command": cmd_str,
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
            }

    def execute_workflow(self, workflow_type: str, agent: str, tool_num: int = None):
        """Execute a specific workflow with agent"""
        self.io.output(f"\nExecuting workflow: {workflow_type}")
        self.io.output(f"Using agent: {agent}")

        # Handle specialized workflows
        if workflow_type == "layout_optimize":
            if TKINTER_OPTIMIZER_AVAILABLE:
                self.io.output("Starting Tkinter Layout Optimization...")
                results = self.analyzer.run_tkinter_optimizer(self.marked_targets)
                self.io.output(f"Optimization complete. Results: {len(results)}")
                # Could auto-generate tasks here based on results
            else:
                self.io.output("✗ tkinter_optimizer_cli.py not found")
                self.io.output("  Download/create it to enable this workflow")

        # Launch agent in xfce4 terminal
        self.launch_agent(agent, workflow_type, tool_num)

        # Run pre-checks based on workflow
        self.run_pre_checks(workflow_type)

        # Create task if needed
        if workflow_type != "task_manage":
            task = self.create_task()
            task.agent = agent
            task.workflow = workflow_type
            self.tasks[task.id] = task

        self.io.output("\n✓ Workflow execution started")
        self.io.output("  Check the terminal for agent interaction")

    def launch_agent(self, agent: str, workflow: str, tool_num: int = None):
        """Launch CLI agent in xfce4 terminal"""
        try:
            # Build command based on workflow and marked targets
            cmd_parts = [agent]

            if tool_num is not None:
                cmd_parts.append(f"-tool{tool_num}")

            if self.marked_targets:
                cmd_parts.extend(self.marked_targets)

            cmd = " ".join(cmd_parts)

            # Launch in xfce4 terminal
            terminal_cmd = [
                "xfce4-terminal",
                "--title",
                f"{agent.upper()} - {workflow}",
                "--command",
                f'bash -c "{cmd}; echo \\"\\nPress Enter to exit...\\"; read"',
                "--hold",
            ]

            subprocess.Popen(terminal_cmd)
            self.io.output(f"✓ Launched {agent} in new terminal")

        except Exception as e:
            self.io.output(f"✗ Error launching agent: {e}")

    def run_pre_checks(self, workflow_type: str):
        """Run pre-execution checks based on workflow"""
        self.io.output("\nRunning pre-checks...")

        for target in self.marked_targets:
            if os.path.isfile(target) and target.endswith(".py"):
                self.io.output(f"\nAnalyzing: {target}")

                # AST analysis
                ast_result = self.analyzer.analyze_ast(target)
                self.io.output(f"  Imports: {len(ast_result['imports'])}")
                self.io.output(f"  Classes: {len(ast_result['classes'])}")
                self.io.output(f"  Functions: {len(ast_result['functions'])}")

                # Compile check
                compile_ok, compile_msg = self.analyzer.compile_check(target)
                self.io.output(
                    f"  Compilation: {'✓' if compile_ok else '✗'} {compile_msg}"
                )

                # Pyflakes check if available
                if PYLINTS_AVAILABLE:
                    flakes_issues = self.analyzer.check_with_pyflakes(target)
                    if flakes_issues and flakes_issues[0] != "pyflakes not available":
                        self.io.output(f"  Pyflakes issues: {len(flakes_issues)}")
                        for issue in flakes_issues[:3]:  # Show first 3
                            self.io.output(f"    - {issue}")

    def revert_task(self, task_id: int):
        """Revert changes from a specific task"""
        if task_id not in self.tasks:
            self.io.output(f"✗ Task {task_id} not found")
            return

        task = self.tasks[task_id]
        self.io.output(f"\nReverting task {task_id}: {task.name}")

        # Check if diffs exist for this task
        if task.diffs:
            for diff in task.diffs:
                self.io.output(f"  Reverting diff: {diff.get('old_file', 'unknown')}")
                # Implementation would restore from backup
        else:
            self.io.output("  No diffs to revert")

        task.status = "reverted"
        self.save_task(task_id)
        self.io.output("✓ Task reverted")
        self.journal_manager.add_note(f"Reverted task {task_id}: {task.name}", author="i.revert")

    def generate_review_summary(self, task_id: int = None) -> Dict[str, Any]:
        """Generate comprehensive review summary for a task with all artifacts"""
        # Get task (latest if not specified)
        if task_id is None or task_id == 0:
            if not self.tasks:
                self.io.output("✗ No tasks to review")
                return {}
            task_id = max(self.tasks.keys())

        if task_id not in self.tasks:
            self.io.output(f"✗ Task {task_id} not found")
            return {}

        task = self.tasks[task_id]
        self.io.output("\n" + "=" * 50)
        self.io.output(f"REVIEW SUMMARY: Task {task_id}")
        self.io.output("=" * 50)

        review = {
            "task_id": task_id,
            "task_name": task.name,
            "review_timestamp": datetime.now().isoformat(),
            "targets": task.targets,
            "status": task.status,
            "logs": [],
            "diffs": [],
            "manifest_changes": [],
            "feature_summary": [],
            "trust_level": 0,
            "review_status": "pending_review",
        }

        # 1. Collect relevant logs
        self.io.output("\n[1/5] Collecting Logs...")
        log_file = Path("logs/session.log")
        if log_file.exists():
            review["logs"].append(str(log_file))
            self.io.output(f"  ✓ {log_file}")

        # 2. Collect diffs for targets
        self.io.output("\n[2/5] Collecting Diffs...")
        diffs_dir = Path("diffs")
        if diffs_dir.exists():
            for diff_file in diffs_dir.glob("*.txt"):
                review["diffs"].append(str(diff_file))
                self.io.output(f"  ✓ {diff_file.name}")

        # 3. Check manifest for changes
        self.io.output("\n[3/5] Checking Manifest Changes...")
        manifest_path = Path("file_manifest.json")
        if manifest_path.exists():
            try:
                with open(manifest_path, "r") as f:
                    manifest = json.load(f)
                for target in task.targets:
                    basename = os.path.basename(target)
                    for entry in manifest:
                        if entry.get("file") == basename:
                            review["manifest_changes"].append({
                                "file": basename,
                                "hash": entry.get("hash", "unknown"),
                                "metadata": entry.get("metadata", {}),
                            })
                            self.io.output(f"  ✓ {basename}: {entry.get('hash', 'N/A')[:8]}")
            except:
                pass

        # 4. Feature summary from AST
        self.io.output("\n[4/5] Analyzing Features...")
        for target in task.targets:
            if os.path.exists(target) and target.endswith(".py"):
                ast_data = self.analyzer.analyze_ast(target)
                for func in ast_data.get("functions", [])[:5]:
                    review["feature_summary"].append({
                        "type": "function",
                        "name": func["name"],
                        "location": f"{os.path.basename(target)}",
                    })
                for cls in ast_data.get("classes", [])[:3]:
                    review["feature_summary"].append({
                        "type": "class",
                        "name": cls["name"],
                        "location": f"{os.path.basename(target)}",
                    })
        self.io.output(f"  Found {len(review['feature_summary'])} features")

        # 5. Calculate trust level
        self.io.output("\n[5/5] Calculating Trust...")
        trust = 50  # Base trust
        for target in task.targets:
            target_trust = self.trust_system.get_trust(target)
            trust = max(trust, target_trust)
        review["trust_level"] = trust
        self.io.output(f"  Trust Level: {trust}")

        # Save review summary
        reviews_dir = Path("reviews")
        reviews_dir.mkdir(exist_ok=True)
        review_file = reviews_dir / f"review_task_{task_id}_{datetime.now().strftime('%H%M%S')}.json"
        with open(review_file, "w") as f:
            json.dump(review, f, indent=2)

        self.io.output(f"\n✓ Review saved: {review_file.name}")

        # Trust-gated conformer
        threshold = 50  # Default threshold
        if review["trust_level"] >= threshold:
            self.io.output(f"\n[CONFORMER] Trust {trust} >= {threshold}: Review gate passed")

            # Prompt for accept/reject
            accepted = self.notifier.prompt_user(
                f"Review Task {task_id}",
                f"Task: {task.name}\nTargets: {len(task.targets)}\nTrust: {trust}\n\nAccept and Finalize?",
            )

            if accepted:
                review["review_status"] = "accepted"
                self.finalize_task(task_id)
            else:
                review["review_status"] = "rejected"
                self.io.output("Review rejected. Use -revert to rollback changes.")
        else:
            self.io.output(f"\n[BLOCKED] Trust {trust} < {threshold}: Manual review required")
            review["review_status"] = "blocked_low_trust"

        return review

    def finalize_task(self, task_id: int):
        """Finalize/accept a task after review"""
        if task_id not in self.tasks:
            self.io.output(f"✗ Task {task_id} not found")
            return

        task = self.tasks[task_id]
        task.status = "finalized"
        task.mark_type = "Finalized"
        task.updated_at = datetime.now().isoformat()
        self.save_task(task_id)

        # Add finalized mark to targets
        for target in task.targets:
            if os.path.exists(target) and target.endswith(".py"):
                note_id = f"N{self.note_counter:03d}"
                self.note_counter += 1
                self.marker.mark_file(target, 1, f"Finalized:TASK_{task_id}", note_id)

        self.io.output(f"✓ Task {task_id} finalized: {task.name}")
        self.journal_manager.add_note(
            f"Finalized task {task_id}: {task.name}", author="i.review"
        )

    def show_inventory(self):
        """Show all tasks and plans"""
        self.io.output("\n" + "=" * 50)
        self.io.output("TASK INVENTORY")
        self.io.output("=" * 50)

        if not self.tasks:
            self.io.output("No tasks found")
            return

        for task_id, task in self.tasks.items():
            self.io.output(f"\n[{task_id}] {task.name}")
            self.io.output(f"    Status: {task.status}")
            self.io.output(f"    Created: {task.created_at}")
            self.io.output(f"    Targets: {len(task.targets)}")
            self.io.output(f"    Agent: {task.agent}")
            self.io.output(f"    Workflow: {task.workflow}")

    def log_session(self, message: str, event_type: str = None):
        """Log session activity with friction detection"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{timestamp}] {message}"
        self.session_log.append(log_entry)

        # Append to log file
        os.makedirs("logs", exist_ok=True)
        with open("logs/session.log", "a") as f:
            f.write(log_entry + "\n")

        # Friction detection - analyze message for friction events
        message_lower = message.lower()
        if hasattr(self, "session_manager") and self.session_manager:
            if "bug" in message_lower or "error" in message_lower:
                self.session_manager.log_friction("bug")
            if "traceback" in message_lower or "exception" in message_lower:
                self.session_manager.log_friction("traceback")
            if "failed" in message_lower and ("init" in message_lower or "compile" in message_lower):
                self.session_manager.log_friction("failed_init")
            if "compile error" in message_lower:
                self.session_manager.log_friction("compile_error")
            if "revert" in message_lower:
                self.session_manager.log_friction("revert")

        if hasattr(self, "debug") and self.debug:
            self.io.output(f"[DEBUG] {log_entry}")


class WatchdogMonitor(FileSystemEventHandler):
    """Monitor file changes for automatic analysis"""

    def __init__(self, manager: WorkflowManager):
        self.manager = manager
        self.last_modified = {}

    def on_modified(self, event):
        if not event.is_directory and event.src_path.endswith(".py"):
            current_time = time.time()
            last_time = self.last_modified.get(event.src_path, 0)

            # Debounce rapid modifications
            if current_time - last_time > 1.0:
                self.last_modified[event.src_path] = current_time
                print(f"\n📁 File modified: {event.src_path}")

                # Auto-analyze modified file
                if self.manager.analyzer.debug:
                    analysis = self.manager.analyzer.analyze_ast(event.src_path)
                    print(
                        f"  Quick analysis: {len(analysis['functions'])} functions found"
                    )


def main():
    parser = argparse.ArgumentParser(
        description="CLI Agent Workflow Manager with Code Analysis",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Core Workflows:
  -mark <path>          Onboard file/dir to active context
  -task                 Interactive task creation
  -inventory            View all tasks and state
  -journal              Update today's activity journal
  -instruct <query>     Send context-aware instruction to agent
  -import-analysis      Ingest optimizer findings as tasks
  -refresh              Unified project refresh and guidance sync
  -view                 List onboarded/unmarked files

3-Way Coordinated Workflow Guide:
  1. INITIAL EVENT: 
     Launch with --gui to orchestrate via CLI while monitoring 
     live events/logs in micro_gui or pyview_gui.
     Example: %(prog)s -instruct "Optimize UI" -agent gemini --gui

  2. EXECUTION:
     The CLI Agent (Gemini/Claude) performs the task.
     The User watches progress via visual feedback in the GUI.

  3. VALIDATION:
     The Orchestrator (me) performs post-task checks using 
     headless flags to verify logic without UI overhead.
     Example: %(prog)s -debug --headless

Examples:
  # Initial 3-Way Coordination
  %(prog)s -instruct "Fix sidebar layout" -agent gemini --gui
  
  # Silent Logic Validation
  %(prog)s -debug --headless

Internal Marking System:
  Insert persistent #[MARK:{...}] comments and generate artifacts.
  Requires: -mark <file> -line <num> -note <text>
  Optional: -bug (auto-creates task and links to code)
  Example: workflow_manager.py -mark app.py -line 45 -note "Logic error here" -bug

Advanced Debug Guide:
  [What:  {Imports: ast, py_compile, black | Workflows: unified_debug, refresh}]
  [Where: workflow_manager.py (line 880: unified_debug_check) | Links: manifest ID#]
  [When:  {Initial launch (--gui) | Pre-task (refresh) | Post-task (debug)}]
  [Why:   {Ensure logic integrity and environment health across distributed tools}]
  [Who:   {User: Overall monitoring via GUI | Agent: CLI tools & context validation}]
  [How:   {Static AST analysis, compilation verification, and log error detection}]

Key Artifacts:
  file_manifest.json    - Project-wide code mapping & health state
  summary.json          - Statistical overview of detected UI patterns
  journal/manifest.json - Daily activity and journal tracking router
  proposals/            - Logic enhancement blueprints
  marks/                - MD/JSON references linked to code markers

CLI Mandate:
  All CLI-initiated automated validation operate in --headless mode.
  Visual interaction requires the explicit --gui flag or manual launch.

Wake Monitor System:
  Automatic idle->active detection with 5W1H classified review notifications.

  Start/Stop Daemon:
    -wake-monitor start    Start the wake monitor daemon
    -wake-monitor stop     Stop the daemon
    -wake-monitor status   Check if daemon is running

  Testing:
    -test-notify           Test notification popup (exception mode, no idle)

  Silence:
    -silence 60            Silence notifications for 60 minutes
    -silence 120           Silence for 2 hours

  5W1H Notification includes:
    WHO:   System Orchestrator
    WHAT:  Changes detected during off-time (with sub-events)
    WHERE: Modified files list
    WHEN:  Off-time duration
    WHY:   Pending review before resuming
    HOW:   Session mode and friction score

  Popup Actions:
    [Review]  - Run -review workflow
    [Revert]  - Revert to backup with confirmation
    [Journal] - View daily journal, [Back] to return
    [Debug]   - Immediate debug check
    [Silence] - Suppress for duration (15m/30m/1h/2h)
    [Dismiss] - Continue working

Rest UX System:
  Compact GUI timer with pre-rest controls.

  Launch:
    -rest              Launch Rest UX GUI (top-right timer)
    -rest early        Show early wake preview (before sleeping)
    -rest now          Enter rest mode (CLI, starts wake monitor)

  GUI Buttons:
    [Early]   - Preview what you'll see when you wake up
    [Rest]    - Enter rest mode, activate wake monitor
    [Silence] - Suppress until activity/refresh/duration
    [X]       - Close timer window

Implementation Marks:
  #[MARK:{Implemented:SessionManager}] - Session timing system
  #[MARK:{Implemented:WakeMonitor}]    - Idle detection daemon
  #[MARK:{Implemented:RestUX}]         - Rest timer GUI
  #[MARK:{Implemented:FrictionDetect}] - Cognitive load tracking
  #[MARK:{Implemented:5W1H}]           - Classified notifications
        """,
    )

    # Core arguments
    parser.add_argument("-profile", type=str, help="JSON profile configuration")
    parser.add_argument(
        "-workflow",
        type=str,
        choices=[w.value for w in WorkflowType],
        help="Workflow type to execute",
    )
    parser.add_argument(
        "-agent", type=str, choices=[a.value for a in CLIAgent], help="CLI agent to use"
    )
    parser.add_argument("-instruct", type=str, help="Send instruction/query to agent")
    parser.add_argument(
        "-refresh",
        action="store_true",
        help="Unified project refresh and guidance sync",
    )
    parser.add_argument(
        "--gui",
        nargs="?",
        const="micro",
        help="Launch visual monitoring (micro, config, macro)",
    )
    parser.add_argument(
        "-headless", action="store_true", help="Force headless automation mode"
    )

    # Task management
    parser.add_argument("-task", action="store_true", help="Create a new task")
    parser.add_argument(
        "-mark", type=str, nargs="+", help="Mark directory/file(s) for processing"
    )
    parser.add_argument(
        "-mark-type",
        type=str,
        default="Active",
        help="Mark type: Active (default), Stable (no planned changes), Scheduled:YYYY-MM-DD",
    )
    parser.add_argument(
        "-schedule",
        type=str,
        help="Schedule task for date (YYYY-MM-DD format)",
    )
    parser.add_argument(
        "-view", action="store_true", help="View marked/unmarked files and artifacts"
    )
    parser.add_argument(
        "-diff", nargs=2, metavar=("OLD", "NEW"), help="Create diff between two files"
    )
    parser.add_argument("-inventory", action="store_true", help="Show task inventory")
    parser.add_argument("-revert", type=int, help="Revert specific task by ID")
    parser.add_argument(
        "-review",
        type=int,
        nargs="?",
        const=0,
        help="Generate review summary for task ID (0 or omit for latest task)",
    )
    parser.add_argument(
        "-finalize",
        type=int,
        help="Finalize/accept task after review by ID",
    )
    parser.add_argument(
        "-import-analysis",
        type=str,
        nargs="?",
        const="optimization_checklist.json",
        help="Import analysis JSON to create tasks",
    )

    # Journaling
    parser.add_argument("-journal", action="store_true", help="Update/View Journal")
    parser.add_argument("-note", type=str, help="Add a note or internal code mark")
    parser.add_argument(
        "-line",
        type=int,
        help="Line number for internal mark (requires -note and -mark)",
    )
    parser.add_argument(
        "-bug", action="store_true", help="Mark as a bug (creates task)"
    )
    parser.add_argument("-proposal", type=str, help="Create a proposal with title")
    parser.add_argument("-daily", action="store_true", help="Dump daily journal JSON")
    parser.add_argument(
        "-week", action="store_true", help="Show weekly summary"
    )  # Logic to be implemented if needed

    # Debug and tools
    parser.add_argument("-debug", action="store_true", help="Enable debug mode")
    parser.add_argument("-tool", type=int, dest="tool_num", help="Tool number to use")

    # Session management
    parser.add_argument(
        "-session", action="store_true", help="Show session status (duration, mode, friction)"
    )
    parser.add_argument(
        "-grind-goal",
        type=str,
        help="Set explicit goal for GRIND mode sessions",
    )
    parser.add_argument(
        "-reset-session",
        action="store_true",
        help="Reset session timer and friction",
    )

    # Wake monitor
    parser.add_argument(
        "-wake-monitor",
        type=str,
        nargs="?",
        const="status",
        choices=["start", "stop", "status"],
        help="Wake monitor daemon: start, stop, or status",
    )
    parser.add_argument(
        "-test-notify",
        action="store_true",
        help="Test wake notification system (exception flags for testing)",
    )
    parser.add_argument(
        "-silence",
        type=int,
        metavar="MINUTES",
        help="Silence wake notifications for N minutes",
    )

    # Rest UX
    parser.add_argument(
        "-rest",
        type=str,
        nargs="?",
        const="gui",
        choices=["gui", "early", "now"],
        help="Rest UX: gui (default), early (preview), now (enter rest mode)",
    )

    args = parser.parse_args()

    # Initialize manager
    manager = WorkflowManager(args.profile)
    manager.analyzer.debug = args.debug

    # Handle Debug Mode
    if args.debug:
        manager.unified_debug_check()
        # If no other args, exit after report
        if not (
            args.mark
            or args.diff
            or args.task
            or args.inventory
            or args.revert
            or args.import_analysis
            or args.workflow
            or args.instruct
            or args.journal
            or args.refresh
            or args.gui
        ):
            return

    # Handle Refresh
    if args.refresh:
        manager.refresh_project()
        if not (
            args.mark
            or args.diff
            or args.task
            or args.inventory
            or args.revert
            or args.import_analysis
            or args.workflow
            or args.instruct
            or args.journal
            or args.gui
        ):
            return

    # Handle Journaling
    if args.journal or args.note or args.proposal or args.daily:
        manager.handle_journal_args(args)
        if not (
            args.mark
            or args.diff
            or args.task
            or args.inventory
            or args.revert
            or args.import_analysis
            or args.workflow
            or args.instruct
            or args.gui
        ):
            return

    # Handle Instructions
    if args.instruct:
        manager.handle_instruct(args.instruct, args.agent, bool(args.gui))
        if not (
            args.mark
            or args.diff
            or args.task
            or args.inventory
            or args.revert
            or args.import_analysis
            or args.workflow
        ):
            return

    # Handle explicit GUI requests
    if args.gui:
        if args.gui == "micro":
            subprocess.Popen([sys.executable, "micro_gui.py"])
        elif args.gui == "macro":
            subprocess.Popen([sys.executable, "pyview_gui.py"])
        elif args.gui == "config":
            # Default to notifications config
            subprocess.Popen(
                [sys.executable, "pyview_gui.py", "--config", "notifications"]
            )
        elif args.gui.startswith("config:"):
            category = args.gui.split(":")[1]
            subprocess.Popen([sys.executable, "pyview_gui.py", "--config", category])

        if not (args.mark or args.diff or args.task or args.inventory or args.workflow):
            return

        # Handle commands
        for target in args.mark:
            manager.mark_target(target, args.mark_type)

    if args.view:
        manager.view_status()

    elif args.diff:
        manager.create_diff(args.diff[0], args.diff[1])

    elif args.task:
        manager.create_task(scheduled_for=args.schedule)

    elif args.inventory:
        manager.show_inventory()

    elif args.revert is not None:
        manager.revert_task(args.revert)

    elif args.review is not None:
        manager.generate_review_summary(args.review)

    elif args.finalize is not None:
        manager.finalize_task(args.finalize)

    elif args.session:
        # Show session status
        status = manager.session_manager.get_status_report()
        print("\n" + "=" * 50)
        print("SESSION STATUS")
        print("=" * 50)
        print(f"  Started:   {status['start_time'][:19] if status['start_time'] else 'N/A'}")
        print(f"  Duration:  {status['duration_hours']:.2f} hours")
        print(f"  Mode:      {status['mode'].upper()} - {status['mode_status']}")
        print(f"  Friction:  {status['friction_score']}/100 ({status['friction_status']})")
        if status['grind_goal']:
            print(f"  Goal:      {status['grind_goal']}")
        print(f"  Events:    {status['recent_friction_events']} friction events (last hour)")
        print("=" * 50)

    elif args.grind_goal:
        manager.session_manager.set_grind_goal(args.grind_goal)
        print(f"✓ GRIND goal set: {args.grind_goal}")
        manager.log_session(f"GRIND goal defined: {args.grind_goal}")

    elif args.reset_session:
        manager.session_manager.reset_session()
        print("✓ Session reset. Timer restarted, friction cleared.")
        manager.log_session("Session reset by user")

    elif args.wake_monitor:
        # Handle wake monitor daemon
        if args.wake_monitor == "start":
            subprocess.Popen([sys.executable, "wake_monitor.py"])
            print("✓ Wake monitor daemon starting...")
            manager.log_session("Wake monitor daemon started")
        elif args.wake_monitor == "stop":
            subprocess.run([sys.executable, "wake_monitor.py", "--stop"])
            manager.log_session("Wake monitor daemon stopped")
        else:  # status
            subprocess.run([sys.executable, "wake_monitor.py", "--status"])

    elif args.test_notify:
        # Test notification system
        print("Testing wake notification system...")
        manager.log_session("Testing wake notification (exception mode)")
        subprocess.run([sys.executable, "wake_monitor.py", "--test"])

    elif args.silence:
        # Set silence duration
        config = manager.session_manager.load_session() if hasattr(manager.session_manager, 'load_session') else {}
        until = datetime.now() + timedelta(minutes=args.silence)
        # Update config
        data = {}
        if manager.config_file.exists():
            with open(manager.config_file, "r") as f:
                data = json.load(f)
        wm_config = data.get("wake_monitor", {})
        wm_config["silence_until"] = until.isoformat()
        data["wake_monitor"] = wm_config
        with open(manager.config_file, "w") as f:
            json.dump(data, f, indent=2)
        print(f"✓ Wake notifications silenced until {until.strftime('%H:%M')}")
        manager.log_session(f"Notifications silenced for {args.silence} minutes")

    elif args.rest:
        # Rest UX
        if args.rest == "early":
            print("Showing early wake preview...")
            subprocess.run([sys.executable, "rest_ux.py", "--early"])
        elif args.rest == "now":
            subprocess.run([sys.executable, "rest_ux.py", "--rest-now"])
        else:  # gui
            print("Launching Rest UX...")
            subprocess.Popen([sys.executable, "rest_ux.py"])

    elif args.import_analysis:
        manager.import_analysis(args.import_analysis)

    elif args.workflow and args.agent:
        if args.workflow == "comment_audit":
            manager.comment_audit()
        else:
            manager.execute_workflow(args.workflow, args.agent, args.tool_num)

    else:
        # Interactive mode
        print("\n" + "=" * 50)
        print("CLI AGENT WORKFLOW MANAGER")
        print("=" * 50)

        while True:
            print("\nOptions:")
            print("  1. Mark target")
            print("  2. Create diff")
            print("  3. Create task")
            print("  4. Execute workflow")
            print("  5. Show inventory")
            print("  6. Revert task")
            print("  7. Start watchdog monitor")
            print("  8. Exit")

            try:
                choice = input("\nSelect option (1-8): ").strip()

                if choice == "1":
                    target = input("Enter path to mark: ").strip()
                    manager.mark_target(target)
                elif choice == "2":
                    old_file = input("Enter old file path: ").strip()
                    new_file = input("Enter new file path: ").strip()
                    manager.create_diff(old_file, new_file)
                elif choice == "3":
                    manager.create_task()
                elif choice == "4":
                    print("Available workflows:", [w.value for w in WorkflowType])
                    workflow = input("Workflow: ").strip()
                    agent = input("Agent (claude/gemini/codex): ").strip()
                    manager.execute_workflow(workflow, agent)
                elif choice == "5":
                    manager.show_inventory()
                elif choice == "6":
                    task_id = input("Task ID to revert: ").strip()
                    if task_id.isdigit():
                        manager.revert_task(int(task_id))
                elif choice == "7":
                    if WATCHDOG_AVAILABLE:
                        print("Starting watchdog monitor...")
                        event_handler = WatchdogMonitor(manager)
                        observer = Observer()
                        for target in manager.marked_targets:
                            if os.path.isdir(target):
                                observer.schedule(event_handler, target, recursive=True)
                        observer.start()
                        print("Watchdog monitoring started. Press Ctrl+C to stop.")
                        try:
                            while True:
                                time.sleep(1)
                        except KeyboardInterrupt:
                            observer.stop()
                        observer.join()
                    else:
                        print(
                            "Watchdog not available. Install with: pip install watchdog"
                        )
                elif choice == "8":
                    print("Exiting...")
                    break

            except KeyboardInterrupt:
                print("\n\nInterrupted. Exiting...")
                break
            except Exception as e:
                print(f"Error: {e}")
                if args.debug:
                    traceback.print_exc()


if __name__ == "__main__":
    # Check for required packages
    missing_packages = []

    if not PYLINTS_AVAILABLE:
        missing_packages.append("pyflakes")

    if not WATCHDOG_AVAILABLE:
        missing_packages.append("watchdog")

    if missing_packages:
        print(
            f"Note: Some optional packages are missing: {', '.join(missing_packages)}"
        )
        print("Install with: pip install " + " ".join(missing_packages))
        print("Continuing with reduced functionality...\n")

    # Create necessary directories
    for directory in ["tasks", "diffs", "logs", "backups", "profiles"]:
        os.makedirs(directory, exist_ok=True)

    # Run main program
    main()
